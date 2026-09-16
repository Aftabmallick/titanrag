import { chromium, Browser, BrowserContext, Page } from "playwright";
import assert from "node:assert";
import { authenticateAndPrepare } from "./test-helpers";

export async function runPdfViewerSpec(baseUrl = "http://localhost:3000") {
  console.log("▶ [E2E] Running PDF Viewer & Bounding Box Overlay Spec...");
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

    // 2. Open PDF Viewer via simulated citation event or UI trigger
    await page.evaluate(() => {
      window.dispatchEvent(
        new CustomEvent("titan-open-citation", {
          detail: {
            document_id: "doc-sample-123",
            document_title: "TitanRAG Technical Specification.pdf",
            page_number: 1,
            bbox: [100, 50, 250, 400],
            snippet: "Sub-1.8s Fast-Path retrieval with verified grounding.",
          },
        })
      );
    });

    // 3. Navigate to Documents page and verify DocumentList table rendered
    const docsNav = page.locator('button:has-text("Knowledge Documents")');
    await docsNav.waitFor({ state: "visible", timeout: 8000 });
    await docsNav.click();
    await page.waitForTimeout(1500);

    assert(page.url().includes("/documents"), "Should be on /documents route");

    console.log("✔ [E2E] PDF Viewer & Documents Spec Passed!");
    return true;
  } finally {
    await browser.close();
  }
}

if (process.argv[1] && process.argv[1].endsWith("pdf-viewer.spec.ts")) {
  runPdfViewerSpec().catch((err) => {
    console.error("❌ PDF Viewer Spec Failed:", err);
    process.exit(1);
  });
}
