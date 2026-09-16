"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { slideInRight } from "@/lib/animations";
import { PdfCanvas } from "./PdfCanvas";
import { CitationHighlight } from "./BoundingBoxOverlay";
import { PdfThumbnailSidebar } from "./PdfThumbnailSidebar";
import {
  X,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Download,
  FileText,
  Maximize2,
  Search,
  LayoutGrid,
} from "lucide-react";
import { CitationPayload, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PdfSearchLayer } from "./PdfSearchLayer";

export interface PdfViewerDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  workspaceId: string | undefined;
  activeCitation: CitationPayload | null;
}

export function PdfViewerDrawer({
  isOpen,
  onClose,
  workspaceId,
  activeCitation,
}: PdfViewerDrawerProps) {
  const { user } = useAuth();
  const isViewer = user?.role === "VIEWER";

  const [pageNumber, setPageNumber] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [scale, setScale] = useState(1.15);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [thumbnailsOpen, setThumbnailsOpen] = useState(false);

  // Sync page and fetch presigned URL when citation changes
  useEffect(() => {
    if (activeCitation) {
      if (activeCitation.page_number) {
        setPageNumber(activeCitation.page_number);
      }
      if (workspaceId && activeCitation.document_id) {
        api
          .getDocumentDownloadUrl(workspaceId, activeCitation.document_id)
          .then((res) => setDownloadUrl(res.presigned_url))
          .catch(() => {
            // fallback URL if presigned route not implemented or local
            setDownloadUrl(`/api/v1/workspaces/${workspaceId}/documents/${activeCitation.document_id}/download`);
          });
      }
    }
  }, [activeCitation, workspaceId]);

  // Handle Esc key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const handleZoomIn = () => setScale((s) => Math.min(2.5, +(s + 0.15).toFixed(2)));
  const handleZoomOut = () => setScale((s) => Math.max(0.7, +(s - 0.15).toFixed(2)));
  const handleResetZoom = () => setScale(1.15);

  const highlights: CitationHighlight[] = activeCitation
    ? [
        {
          sourceIndex: activeCitation.source_index,
          bbox: activeCitation.bbox,
          documentName: activeCitation.document_name,
          snippet: activeCitation.snippet,
          isActive: true,
        },
      ]
    : [];

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          variants={slideInRight}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="fixed top-0 right-0 h-screen w-full sm:w-[500px] md:w-[600px] lg:w-[720px] xl:w-[840px] bg-slate-950/95 border-l border-slate-800 shadow-2xl z-50 flex flex-col backdrop-blur-2xl"
        >
          {/* Header */}
          <div className="h-14 border-b border-slate-800/80 px-4 flex items-center justify-between gap-3 shrink-0">
            <div className="flex items-center gap-2 overflow-hidden flex-1">
              {/* Thumbnails Sidebar Toggle */}
              <button
                onClick={() => setThumbnailsOpen((prev) => !prev)}
                className={`p-1.5 rounded-lg border transition-colors ${
                  thumbnailsOpen
                    ? "bg-sky-500/20 text-sky-400 border-sky-500/30"
                    : "border-slate-800 text-slate-400 hover:text-white hover:bg-slate-800"
                }`}
                title="Toggle Thumbnail Navigation"
              >
                <LayoutGrid className="w-3.5 h-3.5" />
              </button>

              <FileText className="w-4 h-4 text-sky-400 shrink-0" />
              <span className="text-xs font-bold text-slate-200 truncate">
                {activeCitation?.document_name || "Document Verification Viewer"}
              </span>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-1.5">
              {/* Zoom controls */}
              <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-xs text-slate-300">
                <button
                  onClick={handleZoomOut}
                  className="p-1 hover:text-white rounded hover:bg-slate-800"
                  title="Zoom Out"
                >
                  <ZoomOut className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={handleResetZoom}
                  className="px-1.5 text-[11px] font-mono hover:text-sky-400"
                  title="Reset Zoom"
                >
                  {(scale * 100).toFixed(0)}%
                </button>
                <button
                  onClick={handleZoomIn}
                  className="p-1 hover:text-white rounded hover:bg-slate-800"
                  title="Zoom In"
                >
                  <ZoomIn className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Page Stepper */}
              <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-xs text-slate-300">
                <button
                  onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
                  disabled={pageNumber <= 1}
                  className="p-1 hover:text-white disabled:opacity-30 rounded hover:bg-slate-800"
                  title="Previous Page"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </button>
                <span className="px-2 text-[11px] font-mono">
                  {pageNumber} / {totalPages}
                </span>
                <button
                  onClick={() => setPageNumber((p) => Math.min(totalPages, p + 1))}
                  disabled={pageNumber >= totalPages}
                  className="p-1 hover:text-white disabled:opacity-30 rounded hover:bg-slate-800"
                  title="Next Page"
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* In-PDF Search Toggle */}
              <button
                onClick={() => setSearchOpen((prev) => !prev)}
                className={`p-1.5 rounded-lg transition-colors ${
                  searchOpen
                    ? "bg-sky-500/20 text-sky-400 border border-sky-500/30"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`}
                title="Search text in document"
              >
                <Search className="w-4 h-4" />
              </button>

              {/* Download button (restricted for VIEWER role) */}
              {!isViewer && downloadUrl && (
                <a
                  href={downloadUrl}
                  target="_blank"
                  rel="noreferrer"
                  download
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                  title="Download Original File"
                >
                  <Download className="w-4 h-4" />
                </a>
              )}

              {/* Close Drawer */}
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                title="Close Viewer (Esc)"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* In-PDF Interactive Search Bar */}
          <PdfSearchLayer
            isOpen={searchOpen}
            onClose={() => setSearchOpen(false)}
            onJumpToPage={(p) => setPageNumber(p)}
            totalPages={totalPages}
            currentDocumentName={activeCitation?.document_name}
          />

          {/* Active Citation Header Banner */}
          {activeCitation && (
            <div className="bg-sky-500/10 border-b border-sky-500/20 px-4 py-2 flex items-center justify-between text-xs text-sky-300">
              <span className="font-semibold flex items-center gap-1.5 truncate">
                <span>Active Citation [{activeCitation.source_index}]</span>
                <span className="opacity-75">• Relevance: {(activeCitation.relevance_score * 100).toFixed(0)}%</span>
              </span>
              {activeCitation.verified && (
                <span className="text-emerald-400 font-bold text-[10px] uppercase bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                  Verified by NLI
                </span>
              )}
            </div>
          )}

          {/* Main Area: Sidebar + Canvas */}
          <div className="flex-1 flex overflow-hidden bg-slate-950/60">
            <PdfThumbnailSidebar
              isOpen={thumbnailsOpen}
              totalPages={totalPages}
              currentPage={pageNumber}
              onSelectPage={(p) => setPageNumber(p)}
              documentTitle={activeCitation?.document_name}
            />

            <div className="flex-1 overflow-auto p-6 flex items-center justify-center">
              {downloadUrl ? (
                <PdfCanvas
                  pdfUrl={downloadUrl}
                  pageNumber={pageNumber}
                  scale={scale}
                  highlights={highlights}
                  onPageLoaded={(total) => setTotalPages(total)}
                />
              ) : (
                <div className="text-center text-xs text-slate-500 space-y-2">
                  <FileText className="w-8 h-8 mx-auto text-slate-600" />
                  <p>Generating secure presigned URL for document...</p>
                </div>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
