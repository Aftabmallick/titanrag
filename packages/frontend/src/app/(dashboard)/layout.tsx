"use client";

import React, { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { DashboardProvider, useDashboard } from "@/context/DashboardContext";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopNav } from "@/components/layout/TopNav";
import { MobileNav } from "@/components/layout/MobileNav";
import { PdfViewerDrawer } from "@/components/pdf/PdfViewerDrawer";
import { RagSettingsDrawer } from "@/components/settings/RagSettingsDrawer";
import { OnboardingModal } from "@/components/onboarding/OnboardingModal";
import { NetworkBanner } from "@/components/ui/NetworkBanner";
import { A11yProvider } from "@/components/ui/A11yAnnouncer";
import { Sparkles, Lock, ShieldCheck } from "lucide-react";
import Link from "next/link";

function DashboardLayoutContent({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading: authLoading, activeWorkspace, demoLogin } = useAuth();
  const {
    activeSessionId,
    setActiveSessionId,
    settingsOpen,
    setSettingsOpen,
    pdfViewerOpen,
    setPdfViewerOpen,
    activeCitation,
    onboardingOpen,
    setOnboardingOpen,
  } = useDashboard();

  // Check first login onboarding
  useEffect(() => {
    if (user) {
      const done = localStorage.getItem("titan_onboarding_done");
      if (!done && !user.onboarding_completed) {
        setOnboardingOpen(true);
      }
    }
  }, [user, setOnboardingOpen]);

  // Auth checking spinner
  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-400 space-y-4">
        <div className="w-10 h-10 rounded-full border-2 border-sky-500 border-t-transparent animate-spin" />
        <p className="text-sm font-semibold tracking-wide">Connecting to TitanRAG Enterprise Core...</p>
      </div>
    );
  }

  // Unauthenticated Welcome Landing Splash
  if (!user) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col justify-between text-slate-100 relative overflow-hidden">
        <NetworkBanner />
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-tr from-sky-500/15 to-indigo-600/15 rounded-full blur-3xl pointer-events-none" />

        <header className="px-6 h-16 border-b border-slate-800/80 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-extrabold text-base tracking-tight text-white">TitanRAG</span>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-400">
              Enterprise V1.0 GA
            </span>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="text-xs font-semibold text-slate-300 hover:text-white px-3 py-1.5 transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="text-xs font-semibold bg-sky-500 hover:bg-sky-400 text-white px-3.5 py-1.5 rounded-xl shadow-md shadow-sky-500/20 transition-all"
            >
              Get Started
            </Link>
          </div>
        </header>

        <main className="max-w-2xl mx-auto px-6 py-16 text-center space-y-8 relative z-10">
          <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-400 text-xs font-semibold uppercase tracking-wider">
            <ShieldCheck className="w-4 h-4" />
            <span>Zero-Trust Enterprise Multi-Modal RAG</span>
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white leading-tight">
            Grounded Intelligence with{" "}
            <span className="bg-gradient-to-r from-sky-400 via-indigo-300 to-white bg-clip-text text-transparent">
              Verified Citations
            </span>
          </h1>

          <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
            TitanRAG delivers sub-1.8s Fast-Path retrieval, in-process ONNX classification,
            interactive PDF bounding-box overlays, and post-generation NLI claim verification.
          </p>

          <div className="p-6 sm:p-8 rounded-2xl border border-slate-800 bg-slate-900/80 shadow-2xl backdrop-blur-xl space-y-4 max-w-lg mx-auto">
            <div className="flex items-center justify-center p-3 rounded-full bg-sky-500/10 text-sky-400 w-12 h-12 mx-auto">
              <Lock className="w-6 h-6" />
            </div>
            <h3 className="text-base font-bold text-white">Enter Workspace</h3>
            <p className="text-xs text-slate-400">
              Authenticate using your organization account or launch the instant administrator sandbox.
            </p>

            <button
              onClick={() => demoLogin()}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white text-sm font-bold shadow-lg shadow-sky-500/25 transition-all cursor-pointer"
            >
              <Sparkles className="w-4 h-4" />
              <span>Launch Admin Sandbox (admin@titanrag.io)</span>
            </button>
          </div>
        </main>

        <footer className="py-6 text-center text-xs text-slate-600 border-t border-slate-900">
          TitanRAG Enterprise Core • Defense-in-Depth RAG Platform • Row-Level Security Enforced
        </footer>
      </div>
    );
  }

  // Active view computation from route
  const getActiveView = (): "chat" | "documents" | "connectors" | "analytics" | "admin" => {
    if (pathname.startsWith("/documents")) return "documents";
    if (pathname.startsWith("/connectors")) return "connectors";
    if (pathname.startsWith("/analytics")) return "analytics";
    if (pathname.startsWith("/admin")) return "admin";
    return "chat";
  };

  const handleSelectView = (view: "chat" | "documents" | "connectors" | "analytics" | "admin") => {
    if (view === "chat") router.push("/");
    else router.push(`/${view}`);
  };

  return (
    <div className="flex h-screen w-full bg-slate-950 overflow-hidden font-sans">
      <NetworkBanner />

      {/* Left Collapsible Sidebar */}
      <Sidebar
        activeView={getActiveView()}
        onSelectView={handleSelectView}
        onOpenSettings={() => setSettingsOpen(true)}
        activeSessionId={activeSessionId}
        onSelectSession={(sid) => {
          setActiveSessionId(sid);
          router.push("/");
        }}
        onNewChat={() => {
          setActiveSessionId(null);
          router.push("/");
        }}
      />

      {/* Main Workstation View */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden pb-16 md:pb-0">
        <TopNav
          title={
            pathname === "/"
              ? "Chat Workstation"
              : pathname.startsWith("/documents")
              ? "Knowledge Documents"
              : pathname.startsWith("/connectors")
              ? "SaaS Connectors"
              : pathname.startsWith("/analytics")
              ? "Analytics & FinOps"
              : "Platform Administration"
          }
          subtitle={activeWorkspace ? `Workspace: ${activeWorkspace.name}` : undefined}
          onOpenSettings={() => setSettingsOpen(true)}
        />

        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>

      {/* Mobile Bottom Navigation */}
      <MobileNav onOpenSettings={() => setSettingsOpen(true)} />

      {/* Slide-out PDF Viewer Drawer */}
      <PdfViewerDrawer
        isOpen={pdfViewerOpen}
        onClose={() => setPdfViewerOpen(false)}
        workspaceId={activeWorkspace?.id}
        activeCitation={activeCitation}
      />

      {/* Slide-out RAG Settings Drawer */}
      <RagSettingsDrawer
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        workspaceId={activeWorkspace?.id}
      />

      {/* First-login Guided Onboarding Wizard */}
      <OnboardingModal
        isOpen={onboardingOpen}
        onClose={() => setOnboardingOpen(false)}
        onComplete={() => setOnboardingOpen(false)}
      />
    </div>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <A11yProvider>
      <DashboardProvider>
        <DashboardLayoutContent>{children}</DashboardLayoutContent>
      </DashboardProvider>
    </A11yProvider>
  );
}
