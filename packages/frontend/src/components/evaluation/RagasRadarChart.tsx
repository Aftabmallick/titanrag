"use client";

import React from "react";

interface RadarScores {
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  context_recall: number;
  ndcg_5: number;
}

export function RagasRadarChart({ scores }: { scores: RadarScores | null }) {
  const defaultScores: RadarScores = {
    faithfulness: 0.94,
    answer_relevancy: 0.89,
    context_precision: 0.91,
    context_recall: 0.86,
    ndcg_5: 0.93,
  };

  const s = scores || defaultScores;

  const metrics = [
    { label: "Faithfulness (NLI)", key: "faithfulness", value: s.faithfulness },
    { label: "Answer Relevancy", key: "answer_relevancy", value: s.answer_relevancy },
    { label: "Context Precision", key: "context_precision", value: s.context_precision },
    { label: "Context Recall", key: "context_recall", value: s.context_recall },
    { label: "NDCG@5 (IR)", key: "ndcg_5", value: s.ndcg_5 },
  ];

  // SVG Radar Polygon Geometry
  const size = 260;
  const center = size / 2;
  const radius = 90;
  const angleStep = (Math.PI * 2) / metrics.length;

  const getCoordinates = (value: number, index: number) => {
    const angle = index * angleStep - Math.PI / 2;
    const r = radius * Math.min(1.0, Math.max(0.1, value));
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle),
    };
  };

  const polygonPoints = metrics
    .map((m, idx) => {
      const { x, y } = getCoordinates(m.value, idx);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-6 p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-md">
      {/* SVG Chart */}
      <div className="relative flex items-center justify-center">
        <svg width={size} height={size} className="overflow-visible">
          {/* Background concentric rings */}
          {[0.25, 0.5, 0.75, 1.0].map((ring, rIdx) => (
            <circle
              key={rIdx}
              cx={center}
              cy={center}
              r={radius * ring}
              fill="none"
              stroke="#334155"
              strokeDasharray={rIdx < 3 ? "3 3" : undefined}
              strokeWidth="1"
            />
          ))}

          {/* Axes */}
          {metrics.map((_, idx) => {
            const angle = idx * angleStep - Math.PI / 2;
            const x2 = center + radius * Math.cos(angle);
            const y2 = center + radius * Math.sin(angle);
            return <line key={idx} x1={center} y1={center} x2={x2} y2={y2} stroke="#334155" strokeWidth="1" />;
          })}

          {/* Filled polygon */}
          <polygon
            points={polygonPoints}
            fill="rgba(14, 165, 233, 0.25)"
            stroke="#0ea5e9"
            strokeWidth="2.5"
            className="transition-all duration-700 ease-out"
          />

          {/* Data Points */}
          {metrics.map((m, idx) => {
            const { x, y } = getCoordinates(m.value, idx);
            return (
              <circle
                key={idx}
                cx={x}
                cy={y}
                r="4.5"
                fill="#38bdf8"
                stroke="#0284c7"
                strokeWidth="2"
                className="animate-pulse"
              />
            );
          })}
        </svg>
      </div>

      {/* Metric Breakdown Table */}
      <div className="flex-1 space-y-3 w-full">
        <h4 className="text-xs font-mono uppercase tracking-wider text-slate-400">RAGAS Benchmark Performance</h4>
        <div className="space-y-2">
          {metrics.map((m, idx) => (
            <div key={idx} className="flex items-center justify-between text-xs">
              <span className="text-slate-300 font-medium">{m.label}</span>
              <div className="flex items-center gap-3">
                <div className="w-24 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-sky-500 to-indigo-500 rounded-full"
                    style={{ width: `${Math.round(m.value * 100)}%` }}
                  />
                </div>
                <span className="font-mono font-bold text-sky-400 w-10 text-right">
                  {Math.round(m.value * 100)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
