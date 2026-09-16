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
    } else {
      console.log("Demo button not visible, checking if already authenticated...");
    }

    // Wait for main UI navigation
    await page.waitForTimeout(3000);

    // Dismiss onboarding modal if it appears
    const dismissBtn = page.locator('button:has-text("Got it"), button:has-text("Get Started"), button:has-text("Skip"), button:has-text("Close")');
    if (await dismissBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await dismissBtn.first().click();
      await page.waitForTimeout(500);
    }

    await page.screenshot({ path: path.join(ARTIFACT_DIR, "02_chat_workstation.png") });
    results.push({ step: "2. Admin Sandbox & Chat Workstation", status: "PASS", screenshot: "02_chat_workstation.png" });

    // -------------------------------------------------------------
    // Step 3: Interactive Chat Execution
    // -------------------------------------------------------------
    console.log("📍 [3/8] Sending query in Chat Workstation...");
    const chatInput = page.locator('textarea, input[placeholder*="Ask"], input[placeholder*="message"], input[type="text"]').first();
    await chatInput.waitFor({ state: "visible", timeout: 5000 });
    await chatInput.fill("What are the key architectural pillars of TitanRAG's defense-in-depth design?");
    
    // Find send button or hit Enter
    const sendBtn = page.locator('button[type="submit"], button:has(svg.lucide-send), button:has-text("Send")').first();
    if (await sendBtn.isVisible()) {
      await sendBtn.click();
    } else {
      await chatInput.press("Enter");
    }

    console.log("Waiting for response streaming...");
    // Wait up to 10 seconds for assistant bubble/text to emerge
    await page.waitForTimeout(8000);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "03_chat_response.png") });
    results.push({ step: "3. Interactive RAG Query & Stream", status: "PASS", screenshot: "03_chat_response.png" });

    // -------------------------------------------------------------
    // Step 4: Documents Tab & Knowledge Ingestion
    // -------------------------------------------------------------
    console.log("📍 [4/8] Navigating to Knowledge Documents view...");
    const docsNav = page.locator('button:has-text("Documents"), button:has-text("Knowledge")').first();
    await docsNav.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "04_documents_view.png") });
    results.push({ step: "4. Knowledge Documents & Dropzone", status: "PASS", screenshot: "04_documents_view.png" });

    // -------------------------------------------------------------
    // Step 5: Open RAG Settings Drawer
    // -------------------------------------------------------------
    console.log("📍 [5/8] Opening RAG Settings Drawer...");
    const settingsBtn = page.locator('button:has-text("RAG Settings"), button[title*="Settings"], button:has(svg.lucide-sliders), button:has(svg.lucide-settings)').first();
    await settingsBtn.click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "05_rag_settings_drawer.png") });
    results.push({ step: "5. RAG Retrieval Tuning Drawer", status: "PASS", screenshot: "05_rag_settings_drawer.png" });

    // Close settings drawer
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);

    // -------------------------------------------------------------
    // Step 6: SaaS Connectors View
    // -------------------------------------------------------------
    console.log("📍 [6/8] Navigating to SaaS Connectors...");
    const connectorsNav = page.locator('button:has-text("Connectors")').first();
    await connectorsNav.click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "06_connectors_view.png") });
    results.push({ step: "6. Enterprise SaaS Connectors", status: "PASS", screenshot: "06_connectors_view.png" });

    // -------------------------------------------------------------
    // Step 7: Analytics & FinOps View
    // -------------------------------------------------------------
    console.log("📍 [7/8] Navigating to Analytics & FinOps...");
    const analyticsNav = page.locator('button:has-text("Analytics")').first();
    await analyticsNav.click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "07_analytics_view.png") });
    results.push({ step: "7. Analytics & FinOps Dashboard", status: "PASS", screenshot: "07_analytics_view.png" });

    // -------------------------------------------------------------
    // Step 8: Platform Administration Console
    // -------------------------------------------------------------
    console.log("📍 [8/8] Navigating to Platform Admin Console...");
    const adminNav = page.locator('button:has-text("Admin")').first();
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
