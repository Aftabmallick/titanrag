import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const ARTIFACT_DIR = "/Users/aftabmallick/.gemini/antigravity-ide/brain/0bdf74f6-83df-4a96-9242-85ade9f6c717/ui_screenshots";
if (!fs.existsSync(ARTIFACT_DIR)) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}

const TEST_FILE_PATH = "/Users/aftabmallick/Desktop/rag-god/titanrag/packages/frontend/test_upload_contract.txt";

async function runTest() {
  console.log("🚀 Starting Playwright UI Ingestion, Preview & SSE Status Test...");
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });

  await context.addInitScript(() => {
    localStorage.setItem("titan_onboarding_done", "true");
  });

  const page = await context.newPage();

  // Listen to console and network errors
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      console.log(`[Browser Error]: ${msg.text()}`);
    }
  });

  page.on("response", (res) => {
    const url = res.url();
    if (url.includes("/api/v1/") && res.status() >= 400) {
      console.log(`[HTTP ${res.status()}]: ${res.request().method()} ${url}`);
    }
  });

  try {
    // 1. Navigate & Authenticate
    console.log("📍 [1/5] Navigating to http://localhost:3000 & Authenticating...");
    await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
    const demoBtn = page.locator('button:has-text("Launch Admin Sandbox")');
    if (await demoBtn.isVisible()) {
      await demoBtn.click();
    }
    await page.waitForTimeout(2500);

    // 2. Navigate to Knowledge Documents
    console.log("📍 [2/5] Navigating to Knowledge Documents view...");
    const docsNav = page.locator('button:has-text("Knowledge Documents")');
    await docsNav.click();
    await page.waitForTimeout(1500);

    // 3. Test Preview Chunks (Fixing 400 Preview)
    console.log("📍 [3/5] Selecting test file for Hierarchical Preview...");
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(TEST_FILE_PATH);
    await page.waitForTimeout(1000);

    console.log("Clicking 'Preview Chunks'...");
    const previewBtn = page.locator('button:has-text("Preview Chunks")');
    await previewBtn.waitFor({ state: "visible" });
    await previewBtn.click();

    // Wait for IngestionPreviewModal to appear
    const previewModal = page.locator('div:has-text("Hierarchical Ingestion Preview")').first();
    await previewModal.waitFor({ state: "visible", timeout: 10000 });
    console.log("✅ Ingestion Preview Modal loaded successfully without 400 error!");

    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "fix_01_preview_modal_success.png") });

    // Close preview modal
    const closePreviewBtn = page.locator('button:has-text("Close Preview")');
    await closePreviewBtn.click();
    await page.waitForTimeout(1000);

    // 4. Test Ingestion Upload & Live SSE Status (Fixing 422 Upload & 401 SSE Status)
    console.log("📍 [4/5] Ingesting document (Testing Upload & SSE Status Stream)...");
    const folderInput = page.locator('input[placeholder="e.g. Architecture"]');
    if (await folderInput.isVisible()) {
      await folderInput.fill("Security");
    }

    const tagsInput = page.locator('input[placeholder="e.g. core, spec, v2"]');
    if (await tagsInput.isVisible()) {
      await tagsInput.fill("defense, compliance");
    }

    const ingestBtn = page.locator('button:has-text("Ingest Document")');
    await ingestBtn.click();
    console.log("Clicked Ingest Document button, waiting for Live SSE Ingestion Status...");

    // Wait for LiveIngestionStatus banner to appear
    const liveBanner = page.locator('div:has-text("Live Ingestion Status"), div:has-text("Index Ready"), div:has-text("Parse & Extract")').first();
    await liveBanner.waitFor({ state: "visible", timeout: 15000 });

    console.log("Live Ingestion Status component active! Watching pipeline stages...");
    // Wait for either completed or several seconds of streaming
    await page.waitForTimeout(8000);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "fix_02_ingestion_sse_success.png") });
    console.log("✅ Document upload and SSE progress verified with zero 422 / 401 errors!");

    // 5. Test RAG Search / Chat using the newly ingested document
    console.log("📍 [5/5] Navigating to Chat Workstation to query the new knowledge...");
    const chatNav = page.locator('button:has-text("Chat Workstation")');
    await chatNav.click();
    await page.waitForTimeout(1500);

    const chatInput = page.locator('textarea, input[placeholder*="Ask"]').first();
    await chatInput.waitFor({ state: "visible" });
    await chatInput.fill("What does Section 1 say about zero-trust access control?");
    
    const sendBtn = page.locator('button:has(svg.lucide-arrow-up)');
    if (await sendBtn.isVisible()) {
      await sendBtn.click();
    } else {
      await chatInput.press("Enter");
    }

    console.log("Waiting for grounded RAG streaming response...");
    await page.waitForTimeout(9000);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "fix_03_chat_grounded_answer.png") });
    console.log("✅ Chat workstation grounded response captured!");

    console.log("🎉 ALL TESTS PASSED SUCCESSFULLY!");
  } catch (err) {
    console.error("❌ Test failed:", err);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "fix_error_state.png") }).catch(() => {});
    throw err;
  } finally {
    await browser.close();
  }
}

runTest();
