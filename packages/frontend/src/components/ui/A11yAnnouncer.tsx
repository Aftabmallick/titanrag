"use client";

import React, { createContext, useContext, useState, useCallback, ReactNode } from "react";

interface A11yContextType {
  announce: (message: string, priority?: "polite" | "assertive") => void;
}

const A11yContext = createContext<A11yContextType | undefined>(undefined);

export function A11yProvider({ children }: { children: ReactNode }) {
  const [politeMessage, setPoliteMessage] = useState("");
  const [assertiveMessage, setAssertiveMessage] = useState("");

  const announce = useCallback((message: string, priority: "polite" | "assertive" = "polite") => {
    if (priority === "assertive") {
      setAssertiveMessage(message);
    } else {
      setPoliteMessage(message);
    }
  }, []);

  return (
    <A11yContext.Provider value={{ announce }}>
      {children}

      {/* Screen Reader Live Regions */}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        id="a11y-polite-announcer"
      >
        {politeMessage}
      </div>

      <div
        aria-live="assertive"
        aria-atomic="true"
        className="sr-only"
        id="a11y-assertive-announcer"
      >
        {assertiveMessage}
      </div>
    </A11yContext.Provider>
  );
}

export function useA11y() {
  const context = useContext(A11yContext);
  if (!context) {
    throw new Error("useA11y must be used within an A11yProvider");
  }
  return context;
}
