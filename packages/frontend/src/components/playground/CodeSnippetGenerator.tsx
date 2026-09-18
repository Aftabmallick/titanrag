"use client";

import React, { useState } from "react";
import { Copy, Check, Terminal, Code2 } from "lucide-react";
import { EndpointSpec } from "./endpointCatalog";

interface CodeSnippetProps {
  endpoint: EndpointSpec;
  resolvedPath: string;
  baseUrl: string;
  apiKey: string;
  bodyJson: string;
}

export function CodeSnippetGenerator({
  endpoint,
  resolvedPath,
  baseUrl,
  apiKey,
  bodyJson,
}: CodeSnippetProps) {
  const [activeTab, setActiveTab] = useState<"python" | "typescript" | "curl" | "cli">("python");
  const [copied, setCopied] = useState(false);

  const fullUrl = `${baseUrl}${resolvedPath}`;
  const effectiveKey = apiKey || "tr_your_api_key";

  // Generate Python snippet
  let pythonCode = "";
  if (endpoint.id === "chat-query") {
    pythonCode = `from titanrag import TitanClient

client = TitanClient(api_key="${effectiveKey}", base_url="${baseUrl}")

response = client.query(
    workspace_id="<workspace_id>",
    query="What are the key findings?",
    grounding_mode="Balanced"
)

print(response.answer)
for c in response.citations:
    print(f"[{c.citation_id}] {c.filename} (p.{c.page}): {c.snippet[:60]}...")`;
  } else if (endpoint.id === "list-docs") {
    pythonCode = `from titanrag import TitanClient

client = TitanClient(api_key="${effectiveKey}", base_url="${baseUrl}")

docs = client.documents.list(workspace_id="<workspace_id>")
for d in docs:
    print(f"{d.filename} - Status: {d.status} ({d.chunk_count} chunks)")`;
  } else {
    pythonCode = `import httpx

headers = {
    "X-API-Key": "${effectiveKey}",
    "Content-Type": "application/json"
}

resp = httpx.${endpoint.method.toLowerCase()}(
    "${fullUrl}",
    headers=headers,
    ${endpoint.method !== "GET" && bodyJson.trim() ? `json=${bodyJson}` : ""}
)

print(resp.json())`;
  }

  // Generate TypeScript snippet
  let tsCode = `const response = await fetch("${fullUrl}", {
  method: "${endpoint.method}",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": "${effectiveKey}"
  }${endpoint.method !== "GET" && bodyJson.trim() ? `,\n  body: JSON.stringify(${bodyJson})` : ""}
});

const data = await response.json();
console.log(data);`;

  // Generate cURL snippet
  let curlCode = `curl -X ${endpoint.method} "${fullUrl}" \\
  -H "X-API-Key: ${effectiveKey}" \\
  -H "Content-Type: application/json"`;
  if (endpoint.method !== "GET" && bodyJson.trim()) {
    curlCode += ` \\\n  -d '${bodyJson.replace(/'/g, "'\\''")}'`;
  }

  // Generate CLI snippet
  let cliCode = "";
  if (endpoint.id === "chat-query") {
    cliCode = `titan query "What are the key findings?" --mode Balanced`;
  } else if (endpoint.id === "list-docs") {
    cliCode = `titan documents list`;
  } else if (endpoint.id === "list-workspaces") {
    cliCode = `titan workspace list`;
  } else if (endpoint.id === "get-settings") {
    cliCode = `titan settings get`;
  } else if (endpoint.id === "list-plugins") {
    cliCode = `titan plugins list`;
  } else {
    cliCode = `# Raw curl equivalent:\n${curlCode}`;
  }

  const currentSnippet =
    activeTab === "python"
      ? pythonCode
      : activeTab === "typescript"
      ? tsCode
      : activeTab === "curl"
      ? curlCode
      : cliCode;

  const handleCopy = () => {
    navigator.clipboard.writeText(currentSnippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-950/80 border-b border-slate-800 text-xs">
        <div className="flex items-center gap-1">
          <Code2 className="w-3.5 h-3.5 text-sky-400 mr-1" />
          <button
            onClick={() => setActiveTab("python")}
            className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
              activeTab === "python" ? "bg-sky-500/20 text-sky-400 border border-sky-500/40" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Python SDK
          </button>
          <button
            onClick={() => setActiveTab("typescript")}
            className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
              activeTab === "typescript" ? "bg-sky-500/20 text-sky-400 border border-sky-500/40" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            TypeScript
          </button>
          <button
            onClick={() => setActiveTab("curl")}
            className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
              activeTab === "curl" ? "bg-sky-500/20 text-sky-400 border border-sky-500/40" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            cURL
          </button>
          <button
            onClick={() => setActiveTab("cli")}
            className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
              activeTab === "cli" ? "bg-sky-500/20 text-sky-400 border border-sky-500/40" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Titan CLI
          </button>
        </div>

        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-slate-400 hover:text-white px-2 py-1 rounded hover:bg-slate-800 transition-colors"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copied ? "Copied" : "Copy Code"}</span>
        </button>
      </div>

      <pre className="p-4 text-xs font-mono text-slate-300 overflow-x-auto max-h-56 leading-relaxed">
        <code>{currentSnippet}</code>
      </pre>
    </div>
  );
}
