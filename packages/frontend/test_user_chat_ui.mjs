import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const SCREENSHOT_DIR = "/Users/aftabmallick/.gemini/antigravity-ide/brain/0bdf74f6-83df-4a96-9242-85ade9f6c717/ui_screenshots";
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function run() {
  console.log("🚀 Starting Playwright UI Chat test for aftabmallick000@gmail.com...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on("console", (msg) => {
    if (msg.type() === "error" || msg.text().includes("SSE") || msg.text().includes("chat")) {
      console.log(`[Browser ${msg.type()}]:`, msg.text());
    }
  });

  // 1. Authenticate as aftabmallick000@gmail.com via API and inject into localStorage
  console.log("📍 [1/4] Authenticating aftabmallick000@gmail.com...");
  const loginRes = await fetch("http://localhost:8000/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: "aftabmallick000@gmail.com",
      password: "Aftab@123",
    }),
  });

  if (!loginRes.ok) {
    throw new Error(`Login failed with status ${loginRes.status}: ${await loginRes.text()}`);
  }

  const loginData = await loginRes.json();
  const token = loginData.access_token;
  console.log("Got token for Aftab Mallick");

  // Fetch workspaces
  const wsRes = await fetch("http://localhost:8000/api/v1/workspaces", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const workspaces = await wsRes.json();
  const workspace = workspaces[0];
  console.log("Workspace ID:", workspace.id);

  // Navigate to root and set localStorage
  await page.goto("http://localhost:3000/");
  await page.evaluate(
    ({ token, user, workspace }) => {
      localStorage.setItem("titan_token", token);
      localStorage.setItem("titan_refresh_token", token);
      localStorage.setItem(
        "titan_user",
        JSON.stringify({
          id: user.sub || "37950b2a-c6b0-4928-ae12-1caec483079f",
          email: "aftabmallick000@gmail.com",
          full_name: "Aftab Mallick",
          role: "MEMBER",
          tenant_id: "088fe758-5b81-4faf-98bf-4d9fc0a530e6",
        })
      );
      localStorage.setItem("titan_active_workspace", JSON.stringify(workspace));
      localStorage.setItem("titan_onboarding_done", "true");
    },
    { token, user: { sub: "37950b2a-c6b0-4928-ae12-1caec483079f" }, workspace }
  );

  // Reload to enter workstation
  console.log("📍 [2/4] Entering Chat Workstation...");
  await page.goto("http://localhost:3000/");
  await page.waitForTimeout(2000);

  // Verify chat view is active
  await page.waitForSelector("textarea, input[placeholder*='Ask']", { timeout: 10000 });

  // 3. Type question
  const query = "What are my technical skills and experience according to my documents?";
  console.log(`📍 [3/4] Typing query: "${query}"...`);
  const chatInput = page.locator("textarea").first();
  await chatInput.fill(query);
  await page.waitForTimeout(500);

  // Click submit button
  console.log("Sending message via #chat-send-btn...");
  await page.click("#chat-send-btn");

  // 4. Wait for response to stream and complete
  console.log("📍 [4/4] Waiting for grounded response to stream from LiteLLM...");
  await page.waitForSelector("text=TitanRAG Assistant", { timeout: 35000 });

  // Wait until assistant message has substantive text
  await page.waitForFunction(
    () => {
      const items = document.querySelectorAll(".prose");
      return Array.from(items).some((el) => el.textContent && el.textContent.length > 30);
    },
    { timeout: 35000 }
  );

  // Wait 3 seconds for full completion and citation badges
  await page.waitForTimeout(3000);

  const assistantText = await page.evaluate(() => {
    const el = document.querySelector(".prose");
    return el ? el.textContent : "";
  });
  console.log("💬 Generated Assistant Response Preview:\n", assistantText.slice(0, 300));

  const screenshotPath = path.join(SCREENSHOT_DIR, "fix_04_aftab_chat_reply_success.png");
  await page.screenshot({ path: screenshotPath, fullPage: true });
  console.log(`📸 Captured UI verification screenshot: ${screenshotPath}`);

  console.log("🎉 Chat verification successful!");
  await browser.close();
}

run().catch((err) => {
  console.error("❌ Test failed:", err);
  process.exit(1);
});
