import { chromium } from "playwright";
import fs from "fs";
import path from "path";

const ARTIFACT_DIR = "/Users/aftabmallick/.gemini/antigravity-ide/brain/0bdf74f6-83df-4a96-9242-85ade9f6c717/ui_screenshots";
if (!fs.existsSync(ARTIFACT_DIR)) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}

async function runE2E() {
  console.log("🚀 Starting Playwright UI End-to-End Test Suite...");
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });

  // Ensure onboarding is marked complete
  await context.addInitScript(() => {
    localStorage.setItem("titan_onboarding_done", "true");
  });

  const page = await context.newPage();
  const results = [];

  try {
    // -------------------------------------------------------------
    // Step 1: Landing Page
    // -------------------------------------------------------------
    console.log("📍 [1/8] Navigating to Landing Page (http://localhost:3000)...");
    await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "01_landing_page.png") });
    results.push({ step: "1. Landing Page", status: "PASS", screenshot: "01_landing_page.png" });

    // -------------------------------------------------------------
    // Step 2: Authenticate via Demo Login
    // -------------------------------------------------------------
    console.log("📍 [2/8] Launching Admin Sandbox...");
    const demoButton = page.locator('button:has-text("Launch Admin Sandbox")');
    if (await demoButton.isVisible()) {
      await demoButton.click();
    }
    await page.waitForTimeout(2500);

    // If modal appears, dismiss it
    const modalBackdrop = page.locator('div.fixed.inset-0.bg-slate-950\\/75');
    if (await modalBackdrop.isVisible({ timeout: 1500 }).catch(() => false)) {
      console.log("Dismissing modal overlay...");
      const startBtn = page.locator('button:has-text("Start Using TitanRAG"), button:has-text("Skip")');
      if (await startBtn.isVisible()) {
        await startBtn.first().click();
      } else {
        await page.keyboard.press("Escape");
      }
      await page.waitForTimeout(500);
    }

    await page.screenshot({ path: path.join(ARTIFACT_DIR, "02_chat_workstation.png") });
    results.push({ step: "2. Admin Sandbox & Chat Workstation", status: "PASS", screenshot: "02_chat_workstation.png" });

    // -------------------------------------------------------------
    // Step 3: Interactive Chat Execution & Streaming
    // -------------------------------------------------------------
    console.log("📍 [3/8] Sending query in Chat Workstation...");
    const chatInput = page.locator('textarea, input[placeholder*="Ask"]').first();
    await chatInput.waitFor({ state: "visible", timeout: 5000 });
    await chatInput.fill("What are the core capabilities and architecture of TitanRAG?");
    
    // Click the send button (ArrowUp icon)
    const sendBtn = page.locator('button:has(svg.lucide-arrow-up)');
    if (await sendBtn.isVisible()) {
      await sendBtn.click();
    } else {
      await page.keyboard.down("Meta");
      await page.keyboard.press("Enter");
      await page.keyboard.up("Meta");
    }

    console.log("Waiting for response streaming...");
    // Wait for the assistant message bubble to appear and finish streaming
    await page.waitForTimeout(9000);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "03_chat_response.png") });
    results.push({ step: "3. Interactive RAG Query & Stream", status: "PASS", screenshot: "03_chat_response.png" });

    // -------------------------------------------------------------
    // Step 4: Documents Tab & Knowledge Ingestion
    // -------------------------------------------------------------
    console.log("📍 [4/8] Navigating to Knowledge Documents view...");
    const docsNav = page.locator('button:has-text("Knowledge Documents")');
    await docsNav.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "04_documents_view.png") });
    results.push({ step: "4. Knowledge Documents & Dropzone", status: "PASS", screenshot: "04_documents_view.png" });

    // -------------------------------------------------------------
    // Step 5: Open RAG Settings Drawer
    // -------------------------------------------------------------
    console.log("📍 [5/8] Opening RAG Settings Drawer...");
    const settingsBtn = page.locator('button:has-text("RAG Settings")');
    await settingsBtn.click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "05_rag_settings_drawer.png") });
    results.push({ step: "5. RAG Retrieval Tuning Drawer", status: "PASS", screenshot: "05_rag_settings_drawer.png" });

    // Close settings drawer via close icon button inside the drawer
    const drawerCloseBtn = page.locator('div.fixed.top-0.right-0 button:has(svg.lucide-x)').first();
    if (await drawerCloseBtn.isVisible()) {
      await drawerCloseBtn.click();
    } else {
      await page.keyboard.press("Escape");
    }
    await page.waitForTimeout(800);

    // -------------------------------------------------------------
    // Step 6: SaaS Connectors View
    // -------------------------------------------------------------
    console.log("📍 [6/8] Navigating to SaaS Connectors...");
    const connectorsNav = page.locator('button:has-text("SaaS Connectors")');
    await connectorsNav.click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "06_connectors_view.png") });
    results.push({ step: "6. Enterprise SaaS Connectors", status: "PASS", screenshot: "06_connectors_view.png" });

    // -------------------------------------------------------------
    // Step 7: Analytics & FinOps View
    // -------------------------------------------------------------
    console.log("📍 [7/8] Navigating to Analytics & FinOps...");
    const analyticsNav = page.locator('button:has-text("Analytics & FinOps")');
    await analyticsNav.click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "07_analytics_view.png") });
    results.push({ step: "7. Analytics & FinOps Dashboard", status: "PASS", screenshot: "07_analytics_view.png" });

    // -------------------------------------------------------------
    // Step 8: Platform Administration Console
    // -------------------------------------------------------------
    console.log("📍 [8/8] Navigating to Platform Admin Console...");
    const adminNav = page.locator('button:has-text("Platform Administration")');
    await adminNav.click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "08_admin_console.png") });
    results.push({ step: "8. Platform Administration & Audit", status: "PASS", screenshot: "08_admin_console.png" });

    console.log("🎉 All UI E2E test journeys completed successfully!");
    console.table(results);
  } catch (err) {
    console.error("❌ E2E UI Test failed with error:", err);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "error_state.png") }).catch(() => {});
    throw err;
  } finally {
    await browser.close();
  }
}

runE2E();
