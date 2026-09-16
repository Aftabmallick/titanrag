import { chromium, Browser, BrowserContext, Page } from "playwright";
import assert from "node:assert";

export async function runAuthSpec(baseUrl = "http://localhost:3000") {
  console.log("▶ [E2E] Running Auth & Session Lifecycle Spec...");
  const browser: Browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  const context: BrowserContext = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });

  const page: Page = await context.newPage();

  try {
    // 1. Landing page verification
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    const landingTitle = await page.textContent("h1");
    assert(landingTitle?.includes("Grounded Intelligence"), "Landing page title should match");

    // 2. Unauthenticated protected route redirection
    await page.goto(`${baseUrl}/documents`, { waitUntil: "networkidle" });
    assert(page.url().includes("/login?redirect=%2Fdocuments"), "Unauthenticated access to /documents must redirect to /login");

    // 3. Demo Sandbox Login
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    const demoButton = page.locator('button:has-text("Launch Admin Sandbox")');
    await demoButton.waitFor({ state: "visible", timeout: 5000 });
    await demoButton.click();

    // Wait for session hydration
    await page.waitForTimeout(2500);

    // Verify token exists in localStorage & cookie
    const token = await page.evaluate(() => localStorage.getItem("titan_token"));
    assert(token, "Admin Sandbox should set titan_token in localStorage");

    const cookies = await context.cookies();
    const sessionCookie = cookies.find((c) => c.name === "titan_token");
    assert(sessionCookie, "Session cookie titan_token should be set for Edge Middleware");

    // 4. Authenticated navigation to /documents
    await page.goto(`${baseUrl}/documents`, { waitUntil: "networkidle" });
    assert(page.url().includes("/documents"), "Authenticated user can navigate to /documents directly");

    console.log("✔ [E2E] Auth & Session Lifecycle Spec Passed!");
    return true;
  } finally {
    await browser.close();
  }
}

if (process.argv[1] && process.argv[1].endsWith("auth.spec.ts")) {
  runAuthSpec().catch((err) => {
    console.error("❌ Auth Spec Failed:", err);
    process.exit(1);
  });
}
