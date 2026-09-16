"use client";

import React, { createContext, useContext, useState, ReactNode } from "react";
import { CitationPayload } from "@/lib/api";

interface DashboardContextType {
  activeSessionId: string | null;
  setActiveSessionId: (id: string | null) => void;
  activeSessionTitle: string;
  setActiveSessionTitle: (title: string) => void;
  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;
  pdfViewerOpen: boolean;
  setPdfViewerOpen: (open: boolean) => void;
  activeCitation: CitationPayload | null;
  openPdfCitation: (citation: CitationPayload) => void;
  onboardingOpen: boolean;
  setOnboardingOpen: (open: boolean) => void;
}

const DashboardContext = createContext<DashboardContextType | undefined>(undefined);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeSessionTitle, setActiveSessionTitle] = useState<string>("Grounded Research Session");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [pdfViewerOpen, setPdfViewerOpen] = useState(false);
  const [activeCitation, setActiveCitation] = useState<CitationPayload | null>(null);
  const [onboardingOpen, setOnboardingOpen] = useState(false);

  const openPdfCitation = (citation: CitationPayload) => {
    setActiveCitation(citation);
    setPdfViewerOpen(true);
  };

  return (
    <DashboardContext.Provider
      value={{
        activeSessionId,
        setActiveSessionId,
        activeSessionTitle,
        setActiveSessionTitle,
        settingsOpen,
        setSettingsOpen,
        pdfViewerOpen,
        setPdfViewerOpen,
        activeCitation,
        openPdfCitation,
        onboardingOpen,
        setOnboardingOpen,
      }}
    >
      {children}
    </DashboardContext.Provider>
  );
}

export function useDashboard() {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error("useDashboard must be used within a DashboardProvider");
  }
  return context;
}
