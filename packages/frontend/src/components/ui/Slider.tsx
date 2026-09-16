"use client";

import React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: any[]) {
  return twMerge(clsx(inputs));
}

export interface SliderProps {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (val: number) => void;
  label?: string;
  displayValue?: string | number;
  disabled?: boolean;
  className?: string;
}

export function Slider({
  value,
  min,
  max,
  step = 0.05,
  onChange,
  label,
  displayValue,
  disabled = false,
  className,
}: SliderProps) {
  const percentage = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));

  return (
    <div className={cn("w-full space-y-2", className)}>
      {(label || displayValue !== undefined) && (
        <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
          {label && <span>{label}</span>}
          {displayValue !== undefined && (
            <span className="font-mono text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded-md text-[11px]">
              {displayValue}
            </span>
          )}
        </div>
      )}
      <div className="relative flex items-center select-none touch-none w-full h-5">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className={cn(
            "w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer outline-none",
            "accent-sky-500 focus:accent-sky-400 disabled:opacity-50 disabled:cursor-not-allowed"
          )}
          style={{
            background: `linear-gradient(to right, #0ea5e9 ${percentage}%, #1e293b ${percentage}%)`,
          }}
        />
      </div>
    </div>
  );
}
