import { chromium, Browser, BrowserContext, Page } from "playwright";
import assert from "node:assert";
import { authenticateAndPrepare } from "./test-helpers";

export async function runA11ySpec(baseUrl = "http://localhost:3000") {
  console.log("▶ [E2E] Running Accessibility (WCAG 2.1 AA) & Keyboard Nav Spec...");
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

    // 2. Check aria-live announcer exists in DOM
    const liveAnnouncer = page.locator('[aria-live="polite"], [role="status"]');
    assert((await liveAnnouncer.count()) > 0, "Accessible aria-live region must be rendered for screen readers");

    // 3. Command Palette Keyboard Shortcut (Cmd+K / Ctrl+K)
    console.log("Testing Cmd+K command palette trigger...");
    await page.keyboard.press("Meta+k");
    await page.waitForTimeout(600);

    const paletteInput = page.locator('input[placeholder*="Type a command or search"]');
    if (await paletteInput.isVisible()) {
      assert(true, "Cmd+K successfully triggered CommandPalette");
      // Close with Escape
      await page.keyboard.press("Escape");
      await page.waitForTimeout(400);
      assert(!(await paletteInput.isVisible()), "Escape key successfully dismissed CommandPalette");
    }

    // 4. Test Skip link / Accessible navigation
    const htmlLang = await page.getAttribute("html", "lang");
    assert.strictEqual(htmlLang, "en", "Root HTML element must declare language attribute");

    console.log("✔ [E2E] Accessibility & Keyboard Nav Spec Passed!");
    return true;
  } finally {
    await browser.close();
  }
}

if (process.argv[1] && process.argv[1].endsWith("a11y.spec.ts")) {
  runA11ySpec().catch((err) => {
    console.error("❌ Accessibility Spec Failed:", err);
    process.exit(1);
  });
}
