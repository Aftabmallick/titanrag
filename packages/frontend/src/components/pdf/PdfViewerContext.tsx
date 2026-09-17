"use client";

import React, { createContext, useContext, useState, useCallback } from "react";
import { CitationPayload } from "@/lib/api";

export interface PdfViewerState {
  isOpen: boolean;
  activeCitation: CitationPayload | null;
  documentId: string | null;
  documentName: string | null;
  pageNumber: number;
  totalPages: number;
  scale: number;
  searchOpen: boolean;
  thumbnailsOpen: boolean;
}

export interface PdfViewerContextType extends PdfViewerState {
  openViewer: (citation: CitationPayload, docName?: string) => void;
  openDocument: (docId: string, docName: string, initialPage?: number) => void;
  closeViewer: () => void;
  setPageNumber: (page: number | ((prev: number) => number)) => void;
  setTotalPages: (total: number) => void;
  setScale: (scale: number | ((prev: number) => number)) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  resetZoom: () => void;
  setSearchOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
  setThumbnailsOpen: (open: boolean | ((prev: boolean) => boolean)) => void;
}

const PdfViewerContext = createContext<PdfViewerContextType | null>(null);

export function PdfViewerProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeCitation, setActiveCitation] = useState<CitationPayload | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [documentName, setDocumentName] = useState<string | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [scale, setScale] = useState(1.15);
  const [searchOpen, setSearchOpen] = useState(false);
  const [thumbnailsOpen, setThumbnailsOpen] = useState(false);

  const openViewer = useCallback((citation: CitationPayload, docName?: string) => {
    setActiveCitation(citation);
    setDocumentId(citation.document_id);
    setDocumentName(docName || citation.document_name);
    if (citation.page_number) {
      setPageNumber(citation.page_number);
    }
    setIsOpen(true);
  }, []);

  const openDocument = useCallback((docId: string, docName: string, initialPage: number = 1) => {
    setActiveCitation(null);
    setDocumentId(docId);
    setDocumentName(docName);
    setPageNumber(initialPage);
    setIsOpen(true);
  }, []);

  const closeViewer = useCallback(() => {
    setIsOpen(false);
    setActiveCitation(null);
  }, []);

  const zoomIn = useCallback(() => {
    setScale((s) => Math.min(2.5, +(s + 0.15).toFixed(2)));
  }, []);

  const zoomOut = useCallback(() => {
    setScale((s) => Math.max(0.6, +(s - 0.15).toFixed(2)));
  }, []);

  const resetZoom = useCallback(() => {
    setScale(1.15);
  }, []);

  return (
    <PdfViewerContext.Provider
      value={{
        isOpen,
        activeCitation,
        documentId,
        documentName,
        pageNumber,
        totalPages,
        scale,
        searchOpen,
        thumbnailsOpen,
        openViewer,
        openDocument,
        closeViewer,
        setPageNumber,
        setTotalPages,
        setScale,
        zoomIn,
        zoomOut,
        resetZoom,
        setSearchOpen,
        setThumbnailsOpen,
      }}
    >
      {children}
    </PdfViewerContext.Provider>
  );
}

export function usePdfViewer(): PdfViewerContextType {
  const context = useContext(PdfViewerContext);
  if (!context) {
    throw new Error("usePdfViewer must be used within a PdfViewerProvider");
  }
  return context;
}
