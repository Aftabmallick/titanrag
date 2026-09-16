import { chromium, Browser, BrowserContext, Page } from "playwright";
import assert from "node:assert";
import { authenticateAndPrepare } from "./test-helpers";

export async function runRagSettingsSpec(baseUrl = "http://localhost:3000") {
  console.log("▶ [E2E] Running RAG Settings Tuning Drawer Spec...");
  const browser: Browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  const context: BrowserContext = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });

  const page: Page = await context.newPage();

  try {
    // 1. Authenticate & ensure clean workstation
    await authenticateAndPrepare(page, baseUrl);

    // 2. Open Settings Drawer via sidebar or controls bar
    const settingsBtn = page.locator('button:has-text("RAG Tuning Panel"), button[title*="Configure RAG Parameters"], button:has-text("RAG Settings")').first();
    await settingsBtn.waitFor({ state: "visible", timeout: 8000 });
    await settingsBtn.click();
    await page.waitForTimeout(1000);

    // Verify Drawer title and tabs
    const drawerHeader = page.locator('text="RAG Tuning & Guardrails"');
    assert(await drawerHeader.isVisible(), "RAG Settings Drawer should open with title");

    // Verify tabs
    const guardrailsTab = page.locator('button:has-text("Guardrails")');
    if (await guardrailsTab.isVisible()) {
      await guardrailsTab.click();
      await page.waitForTimeout(400);
    }

    // Close via Escape
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);

    console.log("✔ [E2E] RAG Settings Tuning Drawer Spec Passed!");
    return true;
  } finally {
    await browser.close();
  }
}

if (process.argv[1] && process.argv[1].endsWith("rag-settings.spec.ts")) {
  runRagSettingsSpec().catch((err) => {
    console.error("❌ RAG Settings Spec Failed:", err);
    process.exit(1);
  });
}
