"use client";

import React, { useEffect, useRef, useState } from "react";
import { BoundingBoxOverlay, CitationHighlight } from "./BoundingBoxOverlay";
import { Loader2, AlertCircle } from "lucide-react";

export interface PdfCanvasProps {
  pdfUrl: string;
  pageNumber: number;
  scale?: number;
  highlights?: CitationHighlight[];
  onPageLoaded?: (totalPages: number, pageHeightPoints: number) => void;
}

export function PdfCanvas({
  pdfUrl,
  pageNumber,
  scale = 1.2,
  highlights = [],
  onPageLoaded,
}: PdfCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewportDims, setViewportDims] = useState<{ width: number; height: number; pointsHeight: number }>({
    width: 0,
    height: 0,
    pointsHeight: 792,
  });

  const renderTaskRef = useRef<any>(null);

  const onPageLoadedRef = useRef(onPageLoaded);
  useEffect(() => {
    onPageLoadedRef.current = onPageLoaded;
  }, [onPageLoaded]);

  useEffect(() => {
    let isCancelled = false;

    async function renderPage() {
      if (!pdfUrl || typeof window === "undefined") return;

      setLoading(true);
      setError(null);

      try {
        const pdfjsLib = await import("pdfjs-dist");
        // Use local public worker
        pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

        // Cancel previous render task if active
        if (renderTaskRef.current) {
          renderTaskRef.current.cancel();
          renderTaskRef.current = null;
        }

        const loadingTask = pdfjsLib.getDocument({
          url: pdfUrl,
          withCredentials: false,
        });
        const pdfDoc = await loadingTask.promise;

        if (isCancelled) return;

        const targetPageNumber = Math.min(Math.max(1, pageNumber), pdfDoc.numPages);
        const page = await pdfDoc.getPage(targetPageNumber);

        if (isCancelled) return;

        const unscaledViewport = page.getViewport({ scale: 1.0 });
        const viewport = page.getViewport({ scale });

        const canvas = canvasRef.current;
        if (!canvas) return;

        const context = canvas.getContext("2d");
        if (!context) return;

        // Retina high-DPI scaling
        const pixelRatio = window.devicePixelRatio || 1;
        canvas.width = Math.floor(viewport.width * pixelRatio);
        canvas.height = Math.floor(viewport.height * pixelRatio);
        canvas.style.width = `${Math.floor(viewport.width)}px`;
        canvas.style.height = `${Math.floor(viewport.height)}px`;

        context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);

        const renderContext = {
          canvasContext: context,
          viewport,
          canvas,
        };

        const renderTask = page.render(renderContext);
        renderTaskRef.current = renderTask;

        await renderTask.promise;
        renderTaskRef.current = null;

        if (!isCancelled) {
          setViewportDims({
            width: viewport.width,
            height: viewport.height,
            pointsHeight: unscaledViewport.height,
          });
          setLoading(false);
          if (onPageLoadedRef.current) {
            onPageLoadedRef.current(pdfDoc.numPages, unscaledViewport.height);
          }
        }
      } catch (err: any) {
        if (err.name === "RenderingCancelledException") {
          return;
        }
        if (!isCancelled) {
          console.error("PDF.js render error:", err);
          setError(err.message || "Failed to render PDF page.");
          setLoading(false);
        }
      }
    }

    renderPage();

    return () => {
      isCancelled = true;
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
      }
    };
  }, [pdfUrl, pageNumber, scale]);

  return (
    <div className="relative inline-block border border-slate-800 rounded-xl overflow-hidden bg-slate-900 shadow-2xl">
      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-950/60 backdrop-blur-sm z-20">
          <Loader2 className="w-8 h-8 text-sky-400 animate-spin" />
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="p-8 text-center text-xs text-rose-400 space-y-2">
          <AlertCircle className="w-6 h-6 mx-auto" />
          <p>{error}</p>
        </div>
      )}

      {/* HTML5 Canvas */}
      <canvas ref={canvasRef} className="block" />

      {/* SVG Bounding Box Highlights */}
      {!loading && !error && (
        <BoundingBoxOverlay
          highlights={highlights}
          viewportWidth={viewportDims.width}
          viewportHeight={viewportDims.height}
          pageHeightPoints={viewportDims.pointsHeight}
        />
      )}
    </div>
  );
}
