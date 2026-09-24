import React from "react";
import type { Metadata } from "next";
import Link from "next/link";
import {
  Zap,
  Search,
  FileText,
  Brain,
  Shield,
  ArrowRight,
  Play,
  Star,
} from "lucide-react";

export const metadata: Metadata = {
  title: "TitanRAG Sandbox — Try Enterprise RAG Free, No Sign-Up Required",
  description:
    "Experience TitanRAG's enterprise retrieval-augmented generation platform instantly. Query pre-loaded documents, upload your own, and explore the full RAG pipeline — no account needed.",
  openGraph: {
    title: "TitanRAG Sandbox — Try It Free",
    description:
      "Full enterprise RAG platform in your browser. No sign-up, no credit card. Pre-loaded with diverse demo documents.",
    type: "website",
  },
};

const FEATURES = [
  {
    icon: <Search className="w-6 h-6 text-indigo-400" />,
    title: "Hybrid Semantic Search",
    desc: "Dense + sparse vector retrieval with RRF fusion for maximum recall",
  },
  {
    icon: <Brain className="w-6 h-6 text-violet-400" />,
    title: "Grounded Generation",
    desc: "LLM answers with cited sources, faithfulness checking, and NLI egress",
  },
  {
    icon: <FileText className="w-6 h-6 text-emerald-400" />,
    title: "Multi-Format Ingestion",
    desc: "PDF, DOCX, TXT, Markdown — with OCR, table extraction, and chunking",
  },
  {
    icon: <Shield className="w-6 h-6 text-amber-400" />,
    title: "Zero-Trust Architecture",
    desc: "Every retrieval candidate verified at generation time. No hallucinations.",
  },
];

const DEMO_DOCS = [
  { name: "Enterprise Software Architecture Guide", type: "Technical", pages: 45 },
  { name: "Master Services Agreement Template", type: "Legal", pages: 28 },
  { name: "Q4 2025 Financial Report", type: "Financial", pages: 32 },
  { name: "RAG Research Paper Survey", type: "Research", pages: 22 },
  { name: "Product Roadmap 2026", type: "Planning", pages: 8 },
];

export default function SandboxLandingPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-40 border-b border-slate-800/60 bg-slate-950/80 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-slate-100">TitanRAG</span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="text-sm text-slate-400 hover:text-slate-100 transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="text-sm font-semibold px-4 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white hover:from-indigo-500 hover:to-violet-500 transition-all shadow-lg shadow-indigo-500/20"
            >
              Get Started Free
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-900/40 border border-indigo-700/40 text-indigo-300 text-xs font-semibold mb-8">
            <Star className="w-3 h-3 fill-current" />
            Enterprise RAG · No Sign-Up Required
          </div>

          <h1 className="text-5xl md:text-7xl font-black mb-6 leading-tight">
            <span className="bg-gradient-to-r from-indigo-400 via-violet-400 to-purple-400 bg-clip-text text-transparent">
              Try TitanRAG
            </span>
            <br />
            <span className="text-slate-100">Instantly</span>
          </h1>

          <p className="text-xl text-slate-400 mb-10 max-w-2xl mx-auto leading-relaxed">
            Explore the full enterprise RAG platform with pre-loaded documents.
            Ask questions, upload your own files, and configure retrieval settings —
            <strong className="text-slate-200"> no account, no credit card.</strong>
          </p>

          {/* CTA */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <SandboxCTAButton />
            <Link
              href="/docs/getting-started"
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-2xl text-base font-semibold text-slate-300 border border-slate-700/60 hover:bg-slate-800/60 transition-all"
            >
              View Documentation
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          <p className="text-xs text-slate-600 mt-4">
            Sessions expire after 24 hours · 10 queries/hour limit · 50MB storage
          </p>
        </div>
      </section>

      {/* Features grid */}
      <section
        className="py-20 px-6 border-t border-slate-800/60"
        aria-labelledby="features-heading"
      >
        <div className="max-w-5xl mx-auto">
          <h2
            id="features-heading"
            className="text-3xl font-bold text-center mb-12 text-slate-100"
          >
            Production-Grade RAG in Your Browser
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {FEATURES.map(({ icon, title, desc }) => (
              <div
                key={title}
                className="glass-card rounded-2xl border border-slate-700/50 p-6 flex items-start gap-4 hover:border-slate-600/60 transition-all duration-200"
              >
                <div className="w-12 h-12 rounded-xl bg-slate-800/80 flex items-center justify-center flex-shrink-0">
                  {icon}
                </div>
                <div>
                  <h3 className="font-semibold text-slate-100 mb-1">{title}</h3>
                  <p className="text-sm text-slate-400">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Demo documents */}
      <section
        className="py-20 px-6 border-t border-slate-800/60 bg-slate-900/30"
        aria-labelledby="demo-docs-heading"
      >
        <div className="max-w-3xl mx-auto">
          <h2
            id="demo-docs-heading"
            className="text-2xl font-bold text-center mb-3 text-slate-100"
          >
            Pre-Loaded with Diverse Documents
          </h2>
          <p className="text-slate-400 text-center text-sm mb-8">
            Start asking questions immediately. Or upload your own documents.
          </p>
          <div className="space-y-2">
            {DEMO_DOCS.map(({ name, type, pages }) => (
              <div
                key={name}
                className="flex items-center justify-between px-4 py-3 rounded-xl border border-slate-700/50 bg-slate-800/30 hover:bg-slate-800/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <FileText className="w-4 h-4 text-slate-500" />
                  <span className="text-sm text-slate-200">{name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-500">{pages}p</span>
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-slate-700/60 text-slate-400">
                    {type}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="py-24 px-6 text-center">
        <h2 className="text-4xl font-black text-slate-100 mb-6">
          Ready to explore?
        </h2>
        <SandboxCTAButton size="lg" />
        <p className="mt-4 text-sm text-slate-500">
          Want permanent storage and team features?{" "}
          <Link href="/register" className="text-indigo-400 hover:text-indigo-300 underline">
            Create a free account →
          </Link>
        </p>
      </section>
    </div>
  );
}

// Client component for the sandbox session creation button
function SandboxCTAButton({ size = "md" }: { size?: "md" | "lg" }) {
  "use client";
  return (
    <a
      href="/sandbox/demo"
      id="sandbox-try-now-btn"
      className={`inline-flex items-center gap-2 rounded-2xl font-bold bg-gradient-to-r from-indigo-600 to-violet-600 text-white hover:from-indigo-500 hover:to-violet-500 transition-all shadow-xl shadow-indigo-500/25 hover:shadow-indigo-500/40 hover:scale-105 ${
        size === "lg" ? "px-8 py-4 text-lg" : "px-6 py-3.5 text-base"
      }`}
    >
      <Play className={`fill-current ${size === "lg" ? "w-5 h-5" : "w-4 h-4"}`} />
      Try Now — No Sign-Up Required
    </a>
  );
}
