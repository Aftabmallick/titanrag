"use client";

import React, { useEffect, useState } from "react";
import {
  TrendingDown,
  TrendingUp,
  Minus,
  Info,
  AlertTriangle,
} from "lucide-react";

interface DataPoint {
  date: string;
  value: number;
}

interface QualityTrendChartProps {
  workspaceId: string;
  metric?: string;
  days?: number;
}

interface TrendData {
  metric: string;
  data: DataPoint[];
  current_value: number;
  trend_direction: "up" | "down" | "stable";
  trend_pct: number;
  threshold: number;
  is_regression: boolean;
}

const METRIC_CONFIG: Record<string, { label: string; color: string; fill: string }> = {
  faithfulness: {
    label: "Faithfulness",
    color: "#6366f1",
    fill: "rgba(99,102,241,0.12)",
  },
  context_precision: {
    label: "Context Precision",
    color: "#8b5cf6",
    fill: "rgba(139,92,246,0.12)",
  },
  ndcg_at_5: {
    label: "NDCG@5",
    color: "#10b981",
    fill: "rgba(16,185,129,0.12)",
  },
  answer_relevancy: {
    label: "Answer Relevancy",
    color: "#f59e0b",
    fill: "rgba(245,158,11,0.12)",
  },
};

export function QualityTrendChart({
  workspaceId,
  metric = "faithfulness",
  days = 30,
}: QualityTrendChartProps) {
  const [data, setData] = useState<TrendData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedMetric, setSelectedMetric] = useState(metric);

  useEffect(() => {
    setLoading(true);
    const token = localStorage.getItem("titan_token") || "";

    fetch(
      `/api/v1/workspaces/${workspaceId}/evaluations/trends?metric=${selectedMetric}&days=${days}`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [workspaceId, selectedMetric, days]);

  const metricCfg = METRIC_CONFIG[selectedMetric] || METRIC_CONFIG.faithfulness;

  return (
    <div className="glass-card rounded-2xl border border-slate-700/50 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-base font-semibold text-slate-100">Quality Trends</h3>
          <p className="text-xs text-slate-500 mt-0.5">Last {days} days · Nightly evaluation runs</p>
        </div>

        {/* Metric selector */}
        <div className="flex gap-1 bg-slate-800/60 rounded-xl p-1">
          {Object.entries(METRIC_CONFIG).map(([key, cfg]) => (
            <button
              key={key}
              id={`quality-trend-${key}-btn`}
              onClick={() => setSelectedMetric(key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                selectedMetric === key
                  ? "bg-slate-700 text-slate-100 shadow"
                  : "text-slate-500 hover:text-slate-300"
              }`}
              aria-pressed={selectedMetric === key}
            >
              {cfg.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="h-48 bg-slate-800/30 rounded-xl animate-pulse" />
      ) : !data || data.data.length === 0 ? (
        <div className="h-48 flex flex-col items-center justify-center text-slate-500">
          <Info className="w-8 h-8 mb-2 opacity-40" />
          <p className="text-sm">No evaluation data yet</p>
          <p className="text-xs mt-1 text-slate-600">
            Run an evaluation on a golden dataset to see trends here.
          </p>
        </div>
      ) : (
        <>
          {/* Current score + trend */}
          <div className="flex items-center gap-6 mb-6">
            <div>
              <p className="text-xs text-slate-500 mb-1">{metricCfg.label} (Current)</p>
              <div className="flex items-baseline gap-2">
                <span
                  className="text-4xl font-black"
                  style={{ color: data.is_regression ? "#ef4444" : metricCfg.color }}
                >
                  {(data.current_value * 100).toFixed(1)}
                  <span className="text-lg text-slate-400 ml-0.5">%</span>
                </span>
                <div
                  className={`flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${
                    data.trend_direction === "up"
                      ? "text-emerald-400 bg-emerald-900/30"
                      : data.trend_direction === "down"
                      ? "text-red-400 bg-red-900/30"
                      : "text-slate-400 bg-slate-700/40"
                  }`}
                >
                  {data.trend_direction === "up" ? (
                    <TrendingUp className="w-3 h-3" />
                  ) : data.trend_direction === "down" ? (
                    <TrendingDown className="w-3 h-3" />
                  ) : (
                    <Minus className="w-3 h-3" />
                  )}
                  {data.trend_pct > 0 ? "+" : ""}
                  {data.trend_pct.toFixed(1)}%
                </div>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Threshold: {(data.threshold * 100).toFixed(0)}%
              </p>
            </div>

            {data.is_regression && (
              <div className="flex items-start gap-2 p-3 bg-red-950/30 border border-red-800/40 rounded-xl flex-1">
                <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-semibold text-red-300">Quality Regression Detected</p>
                  <p className="text-xs text-red-400/80 mt-0.5">
                    Score is below threshold. CI gate will block PRs until resolved.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* SVG sparkline */}
          <MiniSparkline
            data={data.data}
            color={data.is_regression ? "#ef4444" : metricCfg.color}
            fill={data.is_regression ? "rgba(239,68,68,0.08)" : metricCfg.fill}
            threshold={data.threshold}
          />
        </>
      )}
    </div>
  );
}

function MiniSparkline({
  data,
  color,
  fill,
  threshold,
}: {
  data: DataPoint[];
  color: string;
  fill: string;
  threshold: number;
}) {
  if (data.length < 2) return null;

  const WIDTH = 700;
  const HEIGHT = 140;
  const PAD = { top: 16, right: 16, bottom: 32, left: 40 };

  const values = data.map((d) => d.value);
  const minVal = Math.max(0, Math.min(...values) - 0.05);
  const maxVal = Math.min(1, Math.max(...values) + 0.05);

  const scaleX = (i: number) =>
    PAD.left + (i / (data.length - 1)) * (WIDTH - PAD.left - PAD.right);
  const scaleY = (v: number) =>
    PAD.top + ((maxVal - v) / (maxVal - minVal)) * (HEIGHT - PAD.top - PAD.bottom);

  const points = data.map((d, i) => `${scaleX(i)},${scaleY(d.value)}`).join(" ");
  const areaPoints = [
    `${scaleX(0)},${HEIGHT - PAD.bottom}`,
    ...data.map((d, i) => `${scaleX(i)},${scaleY(d.value)}`),
    `${scaleX(data.length - 1)},${HEIGHT - PAD.bottom}`,
  ].join(" ");

  const thresholdY = scaleY(threshold);

  // X-axis labels (first, middle, last)
  const labelIndices = [0, Math.floor(data.length / 2), data.length - 1];

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="w-full h-36"
      aria-label="Quality score trend chart"
      role="img"
    >
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
        const y = PAD.top + frac * (HEIGHT - PAD.top - PAD.bottom);
        const val = maxVal - frac * (maxVal - minVal);
        return (
          <g key={frac}>
            <line
              x1={PAD.left}
              y1={y}
              x2={WIDTH - PAD.right}
              y2={y}
              stroke="rgba(148,163,184,0.08)"
              strokeWidth={1}
            />
            <text
              x={PAD.left - 6}
              y={y + 4}
              textAnchor="end"
              className="fill-slate-600 text-[9px]"
              style={{ fontSize: 10 }}
            >
              {(val * 100).toFixed(0)}%
            </text>
          </g>
        );
      })}

      {/* Threshold line */}
      <line
        x1={PAD.left}
        y1={thresholdY}
        x2={WIDTH - PAD.right}
        y2={thresholdY}
        stroke="rgba(245,158,11,0.5)"
        strokeWidth={1}
        strokeDasharray="4,4"
      />
      <text
        x={WIDTH - PAD.right + 4}
        y={thresholdY + 4}
        className="fill-amber-500 text-[9px]"
        style={{ fontSize: 9 }}
      >
        min
      </text>

      {/* Area fill */}
      <polygon points={areaPoints} fill={fill} />

      {/* Line */}
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />

      {/* Data points */}
      {data.map((d, i) => (
        <circle
          key={i}
          cx={scaleX(i)}
          cy={scaleY(d.value)}
          r={3}
          fill={color}
          stroke="rgba(15,23,42,0.8)"
          strokeWidth={1.5}
        />
      ))}

      {/* X-axis labels */}
      {labelIndices.map((i) => (
        <text
          key={i}
          x={scaleX(i)}
          y={HEIGHT - 4}
          textAnchor="middle"
          style={{ fontSize: 9, fill: "rgba(148,163,184,0.5)" }}
        >
          {new Date(data[i].date).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
          })}
        </text>
      ))}
    </svg>
  );
}
