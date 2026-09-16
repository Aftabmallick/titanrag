"use client";

import React from "react";
import { RawBBoxInput, transformBBox } from "@/lib/bbox-utils";

export interface CitationHighlight {
  sourceIndex: number;
  bbox?: RawBBoxInput;
  documentName?: string;
  snippet?: string;
  isActive?: boolean;
}

export interface BoundingBoxOverlayProps {
  highlights: CitationHighlight[];
  viewportWidth: number;
  viewportHeight: number;
  pageHeightPoints?: number;
}

export function BoundingBoxOverlay({
  highlights,
  viewportWidth,
  viewportHeight,
  pageHeightPoints,
}: BoundingBoxOverlayProps) {
  if (!highlights || highlights.length === 0 || viewportWidth <= 0 || viewportHeight <= 0) {
    return null;
  }

  return (
    <svg
      className="absolute inset-0 pointer-events-none z-10"
      width={viewportWidth}
      height={viewportHeight}
      viewBox={`0 0 ${viewportWidth} ${viewportHeight}`}
    >
      <defs>
        <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>

      {highlights.map((h, idx) => {
        const transformed = transformBBox(
          h.bbox,
          viewportWidth,
          viewportHeight,
          pageHeightPoints
        );
        if (!transformed) return null;

        const isHighlighted = h.isActive ?? true;

        return (
          <g key={`${h.sourceIndex}-${idx}`}>
            {/* Background Highlight Rectangle */}
            <rect
              x={transformed.x}
              y={transformed.y}
              width={transformed.width}
              height={transformed.height}
              rx={3}
              fill={isHighlighted ? "rgba(14, 165, 233, 0.25)" : "rgba(168, 85, 247, 0.2)"}
              stroke={isHighlighted ? "#0284c7" : "#9333ea"}
              strokeWidth={isHighlighted ? 2 : 1.5}
              strokeDasharray={isHighlighted ? undefined : "3 3"}
              className="transition-all duration-300 pointer-events-auto cursor-pointer"
              filter={isHighlighted ? "url(#glow)" : undefined}
            >
              <title>{`[Source ${h.sourceIndex}] ${h.snippet || ""}`}</title>
            </rect>

            {/* Source Pill Badge at top-left of box */}
            <g
              transform={`translate(${transformed.x}, ${Math.max(12, transformed.y - 4)})`}
              className="pointer-events-none select-none"
            >
              <rect
                x={0}
                y={-12}
                width={20}
                height={12}
                rx={2}
                fill={isHighlighted ? "#0284c7" : "#9333ea"}
              />
              <text
                x={10}
                y={-3}
                fontSize={9}
                fontFamily="monospace"
                fontWeight="bold"
                fill="#ffffff"
                textAnchor="middle"
              >
                {h.sourceIndex}
              </text>
            </g>
          </g>
        );
      })}
    </svg>
  );
}
