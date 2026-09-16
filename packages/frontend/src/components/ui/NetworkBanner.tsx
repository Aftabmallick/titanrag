"use client";

import React, { useEffect, useState } from "react";
import { WifiOff, RefreshCw } from "lucide-react";

export function NetworkBanner() {
  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);

    if (typeof window !== "undefined") {
      setIsOffline(!window.navigator.onLine);
      window.addEventListener("online", handleOnline);
      window.addEventListener("offline", handleOffline);
    }

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  if (!isOffline) return null;

  return (
    <div
      role="alert"
      className="sticky top-0 z-50 w-full bg-rose-600/90 border-b border-rose-500 text-white text-xs font-semibold py-2 px-4 flex items-center justify-between backdrop-blur-md animate-in slide-in-from-top duration-200"
    >
      <div className="flex items-center gap-2">
        <WifiOff className="w-4 h-4 animate-pulse" />
        <span>Network connection lost. TitanRAG offline queue active — retrying server sync...</span>
      </div>
      <button
        onClick={() => window.location.reload()}
        className="flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-rose-700 hover:bg-rose-800 text-[11px] font-bold transition-colors cursor-pointer"
      >
        <RefreshCw className="w-3 h-3" />
        <span>Retry Now</span>
      </button>
    </div>
  );
}
