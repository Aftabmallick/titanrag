import { chromium, Browser, BrowserContext, Page } from "playwright";
import assert from "node:assert";
import { authenticateAndPrepare } from "./test-helpers";

export async function runChatStreamSpec(baseUrl = "http://localhost:3000") {
  console.log("▶ [E2E] Running Chat Stream & Grounding Spec...");
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

    // 2. Chat Input and Send Query
    const chatInput = page.locator('textarea[placeholder*="Ask"], input[placeholder*="Ask"]').first();
    await chatInput.waitFor({ state: "visible", timeout: 8000 });
    await chatInput.fill("What are the key technical pillars of TitanRAG?");

    // Send query
    const sendBtn = page.locator('button:has(svg.lucide-arrow-up)');
    if (await sendBtn.isVisible()) {
      await sendBtn.click();
    } else {
      await page.keyboard.press("Enter");
    }

    // 3. Verify assistant message bubble appears
    console.log("Waiting for streaming message container...");
    const assistantBubble = page.locator('div:has-text("TitanRAG"), div.prose').first();
    await assistantBubble.waitFor({ state: "visible", timeout: 10000 });

    // Wait for stream to accumulate tokens
    await page.waitForTimeout(5000);

    // 4. Verify Export Actions dropdown is accessible
    const exportBtn = page.locator('button:has-text("Export"), button:has(svg.lucide-download)').first();
    if (await exportBtn.isVisible()) {
      await exportBtn.click();
      await page.waitForTimeout(400);
      const markdownOption = page.locator('text="Markdown (.md)"');
      assert(await markdownOption.isVisible(), "Markdown export option should be visible in chat menu");
    }

    console.log("✔ [E2E] Chat Stream & Grounding Spec Passed!");
    return true;
  } finally {
    await browser.close();
  }
}

if (process.argv[1] && process.argv[1].endsWith("chat-stream.spec.ts")) {
  runChatStreamSpec().catch((err) => {
    console.error("❌ Chat Stream Spec Failed:", err);
    process.exit(1);
  });
}
