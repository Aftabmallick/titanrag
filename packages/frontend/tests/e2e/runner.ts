import { runAuthSpec } from "./auth.spec";
import { runChatStreamSpec } from "./chat-stream.spec";
import { runPdfViewerSpec } from "./pdf-viewer.spec";
import { runRagSettingsSpec } from "./rag-settings.spec";
import { runA11ySpec } from "./a11y.spec";

async function main() {
  console.log("==================================================");
  console.log("🚀 TitanRAG Phase 5 Playwright E2E & A11y Suite");
  console.log("==================================================");

  const results: { suite: string; status: "PASS" | "FAIL"; error?: string }[] = [];

  const suites = [
    { name: "Auth & Session Lifecycle", fn: runAuthSpec },
    { name: "Chat Stream & Grounding", fn: runChatStreamSpec },
    { name: "PDF Viewer & Documents", fn: runPdfViewerSpec },
    { name: "RAG Retrieval Tuning Drawer", fn: runRagSettingsSpec },
    { name: "WCAG 2.1 AA Accessibility & Keyboard Nav", fn: runA11ySpec },
  ];

  for (const suite of suites) {
    try {
      await suite.fn();
      results.push({ suite: suite.name, status: "PASS" });
    } catch (err: any) {
      console.error(`❌ Suite ${suite.name} failed:`, err.message);
      results.push({ suite: suite.name, status: "FAIL", error: err.message });
    }
  }

  console.log("\n==================================================");
  console.log("📊 Test Suite Summary");
  console.log("==================================================");
  console.table(results);

  const anyFailed = results.some((r) => r.status === "FAIL");
  if (anyFailed) {
    process.exit(1);
  } else {
    console.log("🎉 All 5 E2E / A11y test suites passed cleanly!");
  }
}

main();
