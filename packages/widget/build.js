#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const zlib = require("zlib");
const { execSync } = require("child_process");

const ROOT_DIR = __dirname;
const SRC_FILE = path.join(ROOT_DIR, "src", "titan-chat.ts");
const DIST_DIR = path.join(ROOT_DIR, "dist");
const OUT_FILE = path.join(DIST_DIR, "widget.js");

if (!fs.existsSync(DIST_DIR)) {
  fs.mkdirSync(DIST_DIR, { recursive: true });
}

// Locate esbuild binary
let esbuildBin = "esbuild";
const localFrontendEsbuild = path.join(ROOT_DIR, "..", "frontend", "node_modules", ".bin", "esbuild");
if (fs.existsSync(localFrontendEsbuild)) {
  esbuildBin = localFrontendEsbuild;
}

console.log("Building @titanrag/widget...");
try {
  execSync(
    `"${esbuildBin}" "${SRC_FILE}" --bundle --minify --format=iife --target=es2020 --outfile="${OUT_FILE}"`,
    { stdio: "inherit" }
  );

  const stats = fs.statSync(OUT_FILE);
  const rawBytes = stats.size;
  const rawKb = (rawBytes / 1024).toFixed(2);

  const content = fs.readFileSync(OUT_FILE);
  const gzipped = zlib.gzipSync(content);
  const gzipKb = (gzipped.length / 1024).toFixed(2);

  console.log(`\nBuild Succeeded!`);
  console.log(`Bundle output: ${OUT_FILE}`);
  console.log(`Raw size:      ${rawKb} KB`);
  console.log(`Gzipped size:  ${gzipKb} KB (Target: < 40 KB)`);

  if (gzipped.length > 40 * 1024) {
    console.error("WARNING: Bundle exceeds 40KB gzipped limit!");
    process.exit(1);
  }
} catch (err) {
  console.error("Build failed:", err);
  process.exit(1);
}
