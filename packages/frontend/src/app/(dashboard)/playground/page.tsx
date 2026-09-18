"use client";

import React, { useState, useEffect } from "react";
import { Play, Copy, Check, Terminal, Zap, Shield, RefreshCw, Layers, ChevronLeft, ChevronRight } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { ENDPOINT_CATALOG, EndpointSpec, fetchDynamicEndpointsFromOpenApi } from "@/components/playground/endpointCatalog";
import { CodeSnippetGenerator } from "@/components/playground/CodeSnippetGenerator";

export default function PlaygroundPage() {
  const { activeWorkspace, workspaces } = useAuth();

  const [catalog, setCatalog] = useState<EndpointSpec[]>(ENDPOINT_CATALOG);
  const [selectedEndpoint, setSelectedEndpoint] = useState<EndpointSpec>(ENDPOINT_CATALOG[0]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("http://localhost:8000");
  const [refreshingCatalog, setRefreshingCatalog] = useState(false);
  const [bodyText, setBodyText] = useState("");
  const [pathParamValues, setPathParamValues] = useState<Record<string, string>>({});

  // Execution state
  const [loading, setLoading] = useState(false);
  const [responseStatus, setResponseStatus] = useState<number | null>(null);
  const [responseLatency, setResponseLatency] = useState<number | null>(null);
  const [responseData, setResponseData] = useState<any>(null);
  const [responseHeaders, setResponseHeaders] = useState<Record<string, string>>({});
  const [responseView, setResponseView] = useState<"body" | "headers">("body");
  const [copiedResponse, setCopiedResponse] = useState(false);

  // Initialize path params & body when endpoint changes
  useEffect(() => {
    const initialParams: Record<string, string> = {};
    if (selectedEndpoint.pathParams) {
      for (const p of selectedEndpoint.pathParams) {
        if (p.name === "workspace_id" && activeWorkspace) {
          initialParams[p.name] = activeWorkspace.id;
        } else {
          initialParams[p.name] = p.default || "";
        }
      }
    }
    setPathParamValues(initialParams);

    if (selectedEndpoint.defaultBody) {
      setBodyText(JSON.stringify(selectedEndpoint.defaultBody, null, 2));
    } else {
      setBodyText("");
    }
  }, [selectedEndpoint, activeWorkspace]);

  const loadOpenApiCatalog = async () => {
    setRefreshingCatalog(true);
    try {
      const dynamicEndpoints = await fetchDynamicEndpointsFromOpenApi(baseUrl);
      setCatalog(dynamicEndpoints);
    } catch {
      setCatalog(ENDPOINT_CATALOG);
    } finally {
      setRefreshingCatalog(false);
    }
  };

  useEffect(() => {
    loadOpenApiCatalog();
  }, [baseUrl]);

  // Resolve dynamic path e.g. /workspaces/{workspace_id}/chat -> /workspaces/123/chat
  let resolvedPath = selectedEndpoint.path;
  for (const [k, v] of Object.entries(pathParamValues)) {
    resolvedPath = resolvedPath.replace(`{${k}}`, v || `{${k}}`);
  }

  const handleExecute = async () => {
    setLoading(true);
    setResponseStatus(null);
    setResponseLatency(null);
    setResponseData(null);
    setResponseHeaders({});

    const startTime = performance.now();
    const fullUrl = `${baseUrl.replace(/\/+$/, "")}${resolvedPath}`;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "Accept": "application/json",
    };
    if (apiKey) {
      headers["X-API-Key"] = apiKey;
    } else {
      // Use local session token if available
      const token = localStorage.getItem("titan_token");
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }

    try {
      const options: RequestInit = {
        method: selectedEndpoint.method,
        headers,
      };
      if (selectedEndpoint.method !== "GET" && bodyText.trim()) {
        options.body = bodyText;
      }

      const res = await fetch(fullUrl, options);
      const latency = Math.round(performance.now() - startTime);

      setResponseStatus(res.status);
      setResponseLatency(latency);

      // Collect headers
      const resHeaders: Record<string, string> = {};
      res.headers.forEach((val, key) => {
        resHeaders[key] = val;
      });
      setResponseHeaders(resHeaders);

      try {
        const json = await res.json();
        setResponseData(json);
      } catch {
        const text = await res.text();
        setResponseData(text);
      }
    } catch (err: any) {
      setResponseStatus(500);
      setResponseLatency(Math.round(performance.now() - startTime));
      setResponseData({ error: err.message || "Failed to connect to backend engine" });
    } finally {
      setLoading(false);
    }
  };

  const methodColor = (method: string) => {
    switch (method) {
      case "GET":
        return "bg-sky-500/15 text-sky-400 border-sky-500/30";
      case "POST":
        return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
      case "PUT":
        return "bg-amber-500/15 text-amber-400 border-amber-500/30";
      case "DELETE":
        return "bg-rose-500/15 text-rose-400 border-rose-500/30";
      default:
        return "bg-slate-500/15 text-slate-400 border-slate-500/30";
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono px-2 py-0.5 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-400">
              Developer Studio
            </span>
            <span className="text-xs text-slate-500">TitanRAG v1.0 GA</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Terminal className="w-6 h-6 text-sky-400" />
            Interactive API Playground
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Test and inspect TitanRAG endpoints live, analyze latency & Compute Units, and generate client code.
          </p>
        </div>

        {/* Global Connection Controls */}
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="API Key (tr_...)"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-200 outline-none focus:border-sky-500 w-48"
          />
          <input
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-200 outline-none focus:border-sky-500 w-44 font-mono"
          />
        </div>
      </div>

      {/* Main Studio Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Sidebar: Endpoint Directory */}
        <div
          className={`${
            sidebarCollapsed ? "lg:col-span-1 p-2" : "lg:col-span-4 p-4"
          } bg-slate-900/60 border border-slate-800/80 rounded-2xl space-y-4 transition-all`}
        >
          <div className="flex items-center justify-between px-1">
            {!sidebarCollapsed && (
              <span className="text-xs font-bold text-slate-400 uppercase tracking-wider truncate">
                Endpoints ({catalog.length})
              </span>
            )}
            <div className={`flex items-center gap-1 ${sidebarCollapsed ? "w-full justify-center" : ""}`}>
              {!sidebarCollapsed && (
                <button
                  onClick={loadOpenApiCatalog}
                  disabled={refreshingCatalog}
                  className="text-[11px] text-slate-400 hover:text-sky-400 flex items-center gap-1 transition-colors p-1"
                  title="Refresh endpoints from OpenAPI schema"
                >
                  <RefreshCw className={`w-3 h-3 ${refreshingCatalog ? "animate-spin text-sky-400" : ""}`} />
                  <span>Sync</span>
                </button>
              )}
              <button
                onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
                className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
                title={sidebarCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
              >
                {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div className="space-y-1 overflow-y-auto max-h-[calc(100vh-280px)] pr-1">
            {catalog.map((ep) => {
              const isSelected = selectedEndpoint.id === ep.id;
              if (sidebarCollapsed) {
                return (
                  <button
                    key={ep.id}
                    onClick={() => setSelectedEndpoint(ep)}
                    title={`${ep.method} ${ep.name} - ${ep.path}`}
                    className={`w-full py-2 px-1 rounded-xl text-xs transition-all flex items-center justify-center border ${
                      isSelected
                        ? "bg-slate-800/90 border-sky-500/50 shadow-md shadow-sky-500/5"
                        : "bg-slate-900/30 border-transparent hover:bg-slate-800/50 hover:border-slate-700/50"
                    }`}
                  >
                    <span
                      className={`font-mono text-[9px] font-bold px-1 py-0.5 rounded border ${methodColor(
                        ep.method
                      )}`}
                    >
                      {ep.method.slice(0, 3)}
                    </span>
                  </button>
                );
              }
              return (
                <button
                  key={ep.id}
                  onClick={() => setSelectedEndpoint(ep)}
                  className={`w-full text-left p-3 rounded-xl text-xs transition-all flex flex-col gap-1.5 border ${
                    isSelected
                      ? "bg-slate-800/90 border-sky-500/50 shadow-md shadow-sky-500/5"
                      : "bg-slate-900/30 border-transparent hover:bg-slate-800/50 hover:border-slate-700/50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-200">{ep.name}</span>
                    <span
                      className={`font-mono text-[10px] font-bold px-1.5 py-0.5 rounded border ${methodColor(
                        ep.method
                      )}`}
                    >
                      {ep.method}
                    </span>
                  </div>
                  <span className="font-mono text-[11px] text-slate-400 truncate">{ep.path}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right Panel: Request Builder & Live Response */}
        <div className={`${sidebarCollapsed ? "lg:col-span-11" : "lg:col-span-8"} space-y-6 transition-all`}>
          {/* Active Endpoint Banner */}
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span
                  className={`font-mono text-xs font-bold px-2 py-1 rounded-md border ${methodColor(
                    selectedEndpoint.method
                  )}`}
                >
                  {selectedEndpoint.method}
                </span>
                <span className="font-mono text-sm font-semibold text-slate-200">{resolvedPath}</span>
              </div>

              <button
                onClick={handleExecute}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-semibold text-xs shadow-md shadow-sky-500/20 disabled:opacity-50 transition-all"
              >
                {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-white" />}
                <span>{loading ? "Executing..." : "Send Request"}</span>
              </button>
            </div>

            <p className="text-xs text-slate-400">{selectedEndpoint.description}</p>

            {/* Path Parameters Editor */}
            {selectedEndpoint.pathParams && selectedEndpoint.pathParams.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <div className="text-xs font-semibold text-slate-300">Path Parameters</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {selectedEndpoint.pathParams.map((p) => (
                    <div key={p.name} className="flex flex-col gap-1">
                      <label className="text-[11px] font-mono text-slate-400">
                        {p.name} {p.required && <span className="text-rose-400">*</span>}
                      </label>
                      <input
                        type="text"
                        value={pathParamValues[p.name] || ""}
                        onChange={(e) =>
                          setPathParamValues({ ...pathParamValues, [p.name]: e.target.value })
                        }
                        className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 outline-none focus:border-sky-500 font-mono"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* JSON Body Editor */}
            {selectedEndpoint.method !== "GET" && (
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-300">Request Body (JSON)</span>
                  <button
                    onClick={() =>
                      setBodyText(JSON.stringify(selectedEndpoint.defaultBody || {}, null, 2))
                    }
                    className="text-[11px] text-sky-400 hover:text-sky-300"
                  >
                    Reset to Default Payload
                  </button>
                </div>
                <textarea
                  rows={6}
                  value={bodyText}
                  onChange={(e) => setBodyText(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs font-mono text-slate-200 outline-none focus:border-sky-500 leading-relaxed resize-y"
                  placeholder="{}"
                />
              </div>
            )}
          </div>

          {/* Response Viewer Panel */}
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-3">
                <span className="text-xs font-semibold text-slate-300">Live Response</span>
                {responseStatus !== null && (
                  <span
                    className={`text-xs font-mono px-2 py-0.5 rounded font-bold ${
                      responseStatus >= 200 && responseStatus < 300
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                        : "bg-rose-500/20 text-rose-400 border border-rose-500/40"
                    }`}
                  >
                    HTTP {responseStatus}
                  </span>
                )}
                {responseLatency !== null && (
                  <span className="text-xs font-mono text-slate-400 flex items-center gap-1">
                    <Zap className="w-3.5 h-3.5 text-amber-400" />
                    {responseLatency} ms
                  </span>
                )}
                {responseData && responseLatency !== null && (
                  <span className="text-xs font-mono text-emerald-400 flex items-center gap-1 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                    <Shield className="w-3.5 h-3.5" />
                    ~{(responseLatency * 0.002).toFixed(3)} CU
                  </span>
                )}
              </div>

              {responseData && (
                <div className="flex items-center gap-2">
                  <div className="flex rounded-lg border border-slate-800 overflow-hidden text-xs">
                    <button
                      onClick={() => setResponseView("body")}
                      className={`px-3 py-1 font-medium ${
                        responseView === "body" ? "bg-slate-800 text-sky-400" : "text-slate-400"
                      }`}
                    >
                      JSON Body
                    </button>
                    <button
                      onClick={() => setResponseView("headers")}
                      className={`px-3 py-1 font-medium ${
                        responseView === "headers" ? "bg-slate-800 text-sky-400" : "text-slate-400"
                      }`}
                    >
                      Headers ({Object.keys(responseHeaders).length})
                    </button>
                  </div>

                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(JSON.stringify(responseData, null, 2));
                      setCopiedResponse(true);
                      setTimeout(() => setCopiedResponse(false), 2000);
                    }}
                    className="p-1.5 text-slate-400 hover:text-white rounded hover:bg-slate-800 transition-colors"
                    title="Copy Response"
                  >
                    {copiedResponse ? (
                      <Check className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <Copy className="w-4 h-4" />
                    )}
                  </button>
                </div>
              )}
            </div>

            {/* Response Content */}
            <div className="min-h-36 max-h-96 overflow-auto font-mono text-xs text-slate-300 bg-slate-950 p-4 rounded-xl border border-slate-800/80">
              {loading ? (
                <div className="flex items-center justify-center h-32 text-slate-500 gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
                  <span>Executing request across TitanRAG pipeline...</span>
                </div>
              ) : responseData ? (
                responseView === "body" ? (
                  <pre>{JSON.stringify(responseData, null, 2)}</pre>
                ) : (
                  <div className="space-y-1">
                    {Object.entries(responseHeaders).map(([k, v]) => (
                      <div key={k} className="flex gap-2">
                        <span className="text-sky-400">{k}:</span>
                        <span className="text-slate-300">{v}</span>
                      </div>
                    ))}
                  </div>
                )
              ) : (
                <div className="flex flex-col items-center justify-center h-32 text-slate-500 gap-1">
                  <Play className="w-6 h-6 stroke-1 text-slate-600" />
                  <span className="text-xs">Click &quot;Send Request&quot; to test this endpoint</span>
                </div>
              )}
            </div>
          </div>

          {/* Dynamic Code Snippets */}
          <CodeSnippetGenerator
            endpoint={selectedEndpoint}
            resolvedPath={resolvedPath}
            baseUrl={baseUrl}
            apiKey={apiKey}
            bodyJson={bodyText}
          />
        </div>
      </div>
    </div>
  );
}
