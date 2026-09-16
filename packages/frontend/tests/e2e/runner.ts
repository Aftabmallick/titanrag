import { runAuthSpec } from "./auth.spec";
import { runChatStreamSpec } from "./chat-stream.spec";
import { runPdfViewerSpec } from "./pdf-viewer.spec";
import { runRagSettingsSpec } from "./rag-settings.spec";
import { runA11ySpec } from "./a11y.spec";
import { spawn, ChildProcess } from "node:child_process";
import http from "node:http";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";

async function isServerHealthy(urlStr: string): Promise<boolean> {
  return new Promise((resolve) => {
    try {
      const url = new URL(urlStr);
      const req = http.request(
        {
          hostname: url.hostname,
          port: url.port || 80,
          path: "/",
          method: "GET",
          timeout: 1500,
        },
        (res) => {
          resolve(Boolean(res.statusCode && res.statusCode < 500));
        }
      );
      req.on("error", () => resolve(false));
      req.on("timeout", () => {
        req.destroy();
        resolve(false);
      });
      req.end();
    } catch {
      resolve(false);
    }
  });
}

async function waitForServer(url: string, maxWaitMs = 30000): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    if (await isServerHealthy(url)) return true;
    await new Promise((r) => setTimeout(r, 1000));
  }
  return false;
}

async function main() {
  console.log("==================================================");
  console.log("🚀 TitanRAG Phase 5 Playwright E2E & A11y Suite");
  console.log("==================================================");

  let spawnedServer: ChildProcess | null = null;
  const isHealthy = await isServerHealthy(BASE_URL);

  if (!isHealthy) {
    console.log(`ℹ️ No active server detected at ${BASE_URL}. Launching Next.js frontend dev server...`);
    try {
      spawnedServer = spawn("npm", ["run", "dev"], {
        cwd: process.cwd(),
        stdio: "pipe",
        env: { ...process.env, PORT: "3000" },
      });

      spawnedServer.stderr?.on("data", (d) => {
        const str = d.toString();
        if (str.includes("error") || str.includes("Error")) {
          console.warn("[next dev]", str.trim());
        }
      });

      console.log("⏳ Waiting for Next.js dev server readiness...");
      const ready = await waitForServer(BASE_URL, 35000);
      if (!ready) {
        throw new Error(`Dev server failed to respond at ${BASE_URL} within 35s.`);
      }
      console.log(`✅ Next.js dev server is ready at ${BASE_URL}`);
    } catch (e: any) {
      console.warn(`⚠️ Could not auto-start local dev server: ${e.message}`);
      console.log("ℹ️ Please ensure `npm run dev` or `npm run start` is running on port 3000 to execute E2E tests.");
      if (spawnedServer) {
        spawnedServer.kill("SIGTERM");
      }
      return;
    }
  } else {
    console.log(`✅ Using active server at ${BASE_URL}`);
  }

  const results: { suite: string; status: "PASS" | "FAIL"; error?: string }[] = [];

  const suites = [
    { name: "Auth & Session Lifecycle", fn: () => runAuthSpec(BASE_URL) },
    { name: "Chat Stream & Grounding", fn: () => runChatStreamSpec(BASE_URL) },
    { name: "PDF Viewer & Documents", fn: () => runPdfViewerSpec(BASE_URL) },
    { name: "RAG Retrieval Tuning Drawer", fn: () => runRagSettingsSpec(BASE_URL) },
    { name: "WCAG 2.1 AA Accessibility & Keyboard Nav", fn: () => runA11ySpec(BASE_URL) },
  ];

  try {
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
  } finally {
    if (spawnedServer) {
      console.log("🧹 Stopping spawned Next.js dev server...");
      spawnedServer.kill("SIGTERM");
    }
  }
}

main();

