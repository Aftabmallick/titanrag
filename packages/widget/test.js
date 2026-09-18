#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const WIDGET_PATH = path.join(__dirname, "dist", "widget.js");

if (!fs.existsSync(WIDGET_PATH)) {
  console.error("Test failed: dist/widget.js does not exist. Run npm run build first.");
  process.exit(1);
}

const content = fs.readFileSync(WIDGET_PATH, "utf-8");
if (!content.includes("customElements.define") || !content.includes("titan-chat")) {
  console.error("Test failed: dist/widget.js does not contain customElements.define('titan-chat')");
  process.exit(1);
}

console.log("Widget test passed: dist/widget.js is valid and exports <titan-chat> Custom Element!");
