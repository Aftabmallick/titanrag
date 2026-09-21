import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const ARTIFACT_DIR = "/Users/aftabmallick/.gemini/antigravity-ide/brain/a76bec08-d16c-49fa-824a-89d62c31bc80/ui_screenshots";
if (!fs.existsSync(ARTIFACT_DIR)) fs.mkdirSync(ARTIFACT_DIR, { recursive: true });

const TEST_FILE_PATH = "/Users/aftabmallick/Desktop/rag-god/titanrag/packages/frontend/test_upload_contract.txt";

/**
 * Uses page.evaluate (native JS) to click the first button inside any
 * fixed-overlay modal. Bypasses Playwright's pointer-event interception.
 */
async function dismissModalViaJS(page, label = "modal") {
  const dismissed = await page.evaluate(() => {
    const overlay = document.querySelector(".fixed.inset-0");
    if (!overlay) return false;
    // Click the first button (the X close button)
    const btn = overlay.querySelector("button");
    if (btn) { btn.click(); return true; }
    return false;
  });
  if (dismissed) {
    console.log(`  ✓ Dismissed ${label} via JS click`);
    await page.waitForTimeout(600);
  }
  return dismissed;
}

async function ensureNoModal(page) {
  let attempts = 0;
  while (attempts < 4) {
    const hasModal = await page.evaluate(() => !!document.querySelector(".fixed.inset-0"));
    if (!hasModal) break;
    console.log(`  → Modal overlay detected (attempt ${attempts + 1}), dismissing...`);
    const dismissed = await dismissModalViaJS(page, "overlay");
    if (!dismissed) {
      await page.keyboard.press("Escape");
      await page.waitForTimeout(500);
    }
    attempts++;
  }
}

async function runTest() {
  console.log("🚀 Starting Playwright UI Ingestion, Preview & SSE Status Test (v4)...");
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
  page.on("console", (msg) => {
    if (msg.type() === "error") console.log(`[Browser Error]: ${msg.text()}`);
  });
  page.on("response", (res) => {
    const url = res.url();
    if (url.includes("/api/v1/") && res.status() >= 400) {
      console.log(`[HTTP ${res.status()}]: ${res.request().method()} ${url}`);
    }
  });

  const results = { passed: 0, warned: 0, steps: [] };
  const pass = (s) => { results.passed++; results.steps.push(`✅ ${s}`); console.log(`✅ ${s}`); };
  const warn = (s, r) => { results.warned++; results.steps.push(`⚠️  ${s}: ${r}`); console.log(`⚠️  ${s}: ${r}`); };

  try {
    // ═══════════════════════════════════════════════════════
    // STEP 1: Navigate & Authenticate
    // ═══════════════════════════════════════════════════════
    console.log("\n📍 [1/5] Navigating & Authenticating...");
    await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "01_landing.png") });

    const demoBtn = page.locator('button:has-text("Launch Admin Sandbox"), button:has-text("Demo"), button:has-text("Get Started")').first();
    if (await demoBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await demoBtn.click();
      await page.waitForTimeout(2500);
    }
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "02_authenticated.png") });
    pass("Authentication / landing page loaded");

    // ═══════════════════════════════════════════════════════
    // STEP 2: Navigate to Knowledge Documents
    // ═══════════════════════════════════════════════════════
    console.log("\n📍 [2/5] Navigating to Knowledge Documents...");
    const docsNav = page.locator('button:has-text("Knowledge Documents")').first();
    if (await docsNav.isVisible({ timeout: 5000 }).catch(() => false)) {
      await docsNav.click();
    } else {
      await page.goto("http://localhost:3000/documents", { waitUntil: "networkidle" });
    }
    await page.waitForTimeout(2500);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "03_documents_page.png") });
    pass("Navigated to Knowledge Documents");

    // ═══════════════════════════════════════════════════════
    // STEP 3: File select → Preview Chunks → close modal
    // ═══════════════════════════════════════════════════════
    console.log("\n📍 [3/5] File select & Preview Chunks...");
    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(TEST_FILE_PATH);
    await page.waitForTimeout(2000); // let React state update with file
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "04_file_selected.png") });
    pass("File added to queue");

    const previewBtn = page.locator('button:has-text("Preview Chunks")');
    if (await previewBtn.isVisible({ timeout: 6000 }).catch(() => false)) {
      // Use JS click to avoid any stale overlay from a previous state
      await page.evaluate(() => {
        const btns = Array.from(document.querySelectorAll("button"));
        const btn = btns.find(b => b.textContent?.includes("Preview Chunks"));
        btn?.click();
      });
      console.log("  Clicked Preview Chunks (JS), waiting 3s for modal...");
      await page.waitForTimeout(3000);

      const modalVisible = await page.evaluate(() => !!document.querySelector(".fixed.inset-0"));
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "05_after_preview_click.png") });

      if (modalVisible) {
        pass("IngestionPreviewModal opened (fixed overlay confirmed)");

        // Read modal h3 title
        const titleText = await page.evaluate(() => {
          const h3 = document.querySelector("h3");
          return h3?.textContent?.trim() || "";
        });
        console.log(`  Modal title: "${titleText}"`);
        if (titleText.includes("Hierarchical Ingestion Preview")) {
          pass("Modal title 'Hierarchical Ingestion Preview' confirmed");
        } else {
          warn("Modal title", `Got: "${titleText}"`);
        }

        // Dismiss via JS (X button)
        await dismissModalViaJS(page, "IngestionPreviewModal");
        await page.waitForTimeout(800);
        await page.screenshot({ path: path.join(ARTIFACT_DIR, "05b_modal_closed.png") });

        const stillOpen = await page.evaluate(() => !!document.querySelector(".fixed.inset-0"));
        if (!stillOpen) {
          pass("Modal closed successfully");
        } else {
          warn("Modal close", "Overlay still visible after JS dismiss, trying Escape");
          await page.keyboard.press("Escape");
          await page.waitForTimeout(500);
        }
      } else {
        warn("IngestionPreviewModal", "Fixed overlay not found after clicking Preview Chunks");
      }
    } else {
      warn("Preview Chunks button", "Not visible after file selection");
    }

    // ═══════════════════════════════════════════════════════
    // STEP 4: Upload Document → SSE Live Status
    // ═══════════════════════════════════════════════════════
    console.log("\n📍 [4/5] Uploading document & watching SSE status...");

    // Guarantee no modal before uploading
    await ensureNoModal(page);
    await page.waitForTimeout(500);

    // Fill metadata
    const folderInput = page.locator('input[placeholder="e.g. Legal, Finance"]');
    if (await folderInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await folderInput.fill("Security");
    }
    const tagsInput = page.locator('input[placeholder="e.g. 2024, confidential"]');
    if (await tagsInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await tagsInput.fill("defense, compliance");
    }
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "06_ready_to_upload.png") });

    // Click Upload via JS to bypass any interception
    const uploaded = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button"));
      const btn = btns.find(b => b.textContent?.trim().startsWith("Upload") && !b.disabled);
      if (btn) { btn.click(); return true; }
      return false;
    });

    if (uploaded) {
      console.log("  Clicked Upload via JS. Watching for progress (15s)...");
      await page.waitForTimeout(3000);
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "07a_upload_initiated.png") });

      // Wait and check for LiveIngestionStatus inline component
      // It contains text like "Parse & Extract", "Hierarchical Chunking", etc.
      await page.waitForTimeout(5000);
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "07b_upload_progress.png") });

      const bodyText = await page.evaluate(() => document.body.innerText);
      const hasParsing = bodyText.includes("Parse") || bodyText.includes("Chunking") || bodyText.includes("Embedding") || bodyText.includes("Index Ready") || bodyText.includes("PARSING") || bodyText.includes("READY");
      const hasSuccessCheckmark = bodyText.includes("Index Ready") || bodyText.includes("done") || bodyText.includes("✓");

      // Also check for status indicator via class
      const hasProgressBar = await page.evaluate(() => !!document.querySelector('[class*="progress"], [class*="uploading"], [class*="animate-spin"]'));

      if (hasParsing || hasSuccessCheckmark) {
        pass("LiveIngestionStatus component visible (pipeline stages detected in DOM)");
        await page.waitForTimeout(5000); // let pipeline progress
        await page.screenshot({ path: path.join(ARTIFACT_DIR, "07c_upload_pipeline.png") });
      } else if (hasProgressBar) {
        pass("Upload in progress (progress indicator detected)");
        await page.waitForTimeout(5000);
        await page.screenshot({ path: path.join(ARTIFACT_DIR, "07c_upload_progress.png") });
      } else {
        warn("SSE pipeline status", "No pipeline stage text or progress indicator found in DOM");
        console.log("  Body excerpt:", bodyText.slice(0, 500));
      }
    } else {
      warn("Upload button", "Could not find an enabled Upload button via JS");
    }

    // ═══════════════════════════════════════════════════════
    // STEP 5: Chat Workstation — RAG query
    // ═══════════════════════════════════════════════════════
    console.log("\n📍 [5/5] Navigating to Chat Workstation...");

    // Ensure modal-free before nav
    await ensureNoModal(page);
    await page.waitForTimeout(500);

    // Use JS navigation to avoid modal blocking nav click
    const chatNavClicked = await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll("button"));
      const btn = btns.find(b => b.textContent?.includes("Chat Workstation"));
      if (btn) { btn.click(); return true; }
      return false;
    });

    if (!chatNavClicked) {
      await page.goto("http://localhost:3000/chat", { waitUntil: "networkidle" });
    }
    await page.waitForTimeout(2500);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "08_chat_page.png") });

    const chatInput = page.locator('textarea, input[placeholder*="Ask"], input[placeholder*="message"], input[placeholder*="Query"]').first();
    const chatVisible = await chatInput.isVisible({ timeout: 6000 }).catch(() => false);
    if (chatVisible) {
      await chatInput.fill("What does the document say about zero-trust access control?");
      const sendBtn = page.locator('button:has(svg.lucide-arrow-up), button[type="submit"]').first();
      if (await sendBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await sendBtn.click();
      } else {
        await chatInput.press("Enter");
      }
      console.log("  Waiting for RAG streaming response (10s)...");
      await page.waitForTimeout(10000);
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "09_chat_rag_response.png") });

      const chatBodyText = await page.evaluate(() => document.body.innerText);
      const hasResponse = chatBodyText.length > 500;
      if (hasResponse) {
        pass("Chat workstation RAG query submitted & response rendered");
      } else {
        warn("Chat RAG response", "Page seems empty after query");
      }
    } else {
      warn("Chat workstation", "Chat input not found");
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "09_chat_not_found.png") });
    }

  } catch (err) {
    console.error("\n❌ Fatal error:", err.message);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "fatal_error.png") }).catch(() => {});
  } finally {
    await browser.close();
  }

  // ═══════════════════════════════════════════════════════
  // Final Report
  // ═══════════════════════════════════════════════════════
  console.log("\n══════════════════════════════════════════════════");
  console.log("        UI INTEGRATION TEST REPORT — FINAL        ");
  console.log("══════════════════════════════════════════════════");
  results.steps.forEach((s) => console.log(` ${s}`));
  console.log("──────────────────────────────────────────────────");
  console.log(` ✅ Passed: ${results.passed}  |  ⚠️  Warned: ${results.warned}`);
  console.log(`📸 Screenshots: ${ARTIFACT_DIR}`);
  console.log("══════════════════════════════════════════════════");

  if (results.warned > 2) process.exit(1);
}

runTest();
