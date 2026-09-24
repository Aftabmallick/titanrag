"use client";

import React from "react";
import { AlertTriangle, RefreshCw, Bug } from "lucide-react";

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorId: string | null;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  context?: string; // e.g. "chat", "documents", "admin" — for error reporting
}

/**
 * React Error Boundary — wraps every major route segment.
 *
 * On error:
 * - Shows a branded, user-friendly fallback card
 * - Provides "Try Again" (reset state) and "Report Issue" actions
 * - Generates a unique error ID for support reference
 * - In production, errors are reported to Sentry via window.__SENTRY__
 */
export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, errorId: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    const errorId = `err-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
    return { hasError: true, error, errorId };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Report to Sentry if available
    try {
      const sentry = (window as unknown as Record<string, unknown>).__SENTRY__;
      if (sentry && typeof (sentry as Record<string, unknown>).captureException === "function") {
        ((sentry as Record<string, unknown>).captureException as (e: Error, ctx: unknown) => void)(
          error,
          {
            contexts: {
              react: { componentStack: info.componentStack },
              titan: { errorId: this.state.errorId, context: this.props.context },
            },
          }
        );
      }
    } catch {
      // Sentry reporting is best-effort
    }

    console.error(
      `[TitanRAG ErrorBoundary] ${this.props.context || "unknown"} — ${this.state.errorId}`,
      error,
      info.componentStack
    );
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorId: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div
          className="flex items-center justify-center min-h-[300px] p-8"
          role="alert"
          aria-live="assertive"
        >
          <div className="max-w-md w-full glass-card rounded-2xl border border-red-800/30 bg-red-950/10 p-8 text-center shadow-2xl">
            <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-red-900/30 flex items-center justify-center">
              <AlertTriangle className="w-7 h-7 text-red-400" />
            </div>

            <h2 className="text-lg font-bold text-slate-100 mb-2">
              Something went wrong
            </h2>
            <p className="text-sm text-slate-400 mb-1">
              {this.props.context
                ? `The ${this.props.context} panel encountered an unexpected error.`
                : "An unexpected error occurred in this section."}
            </p>

            {this.state.errorId && (
              <p className="text-xs text-slate-600 font-mono mb-6">
                Error ID: {this.state.errorId}
              </p>
            )}

            <div className="flex gap-3 justify-center">
              <button
                id="error-boundary-retry-btn"
                onClick={this.handleReset}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold bg-gradient-to-r from-indigo-600 to-violet-600 text-white hover:from-indigo-500 hover:to-violet-500 transition-all shadow-md"
                aria-label="Try again"
              >
                <RefreshCw className="w-4 h-4" />
                Try Again
              </button>
              <a
                href={`mailto:support@titanrag.io?subject=Error Report [${this.state.errorId}]&body=${encodeURIComponent(
                  `Error ID: ${this.state.errorId}\nContext: ${this.props.context || "unknown"}\nError: ${this.state.error?.message}\n\nPlease describe what you were doing when this error occurred:\n`
                )}`}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-slate-300 border border-slate-700/60 hover:bg-slate-800/60 transition-all"
                aria-label="Report this error to support"
              >
                <Bug className="w-4 h-4" />
                Report Issue
              </a>
            </div>

            {process.env.NODE_ENV === "development" && this.state.error && (
              <details className="mt-6 text-left">
                <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-400">
                  Developer details
                </summary>
                <pre className="mt-2 p-3 bg-slate-900/60 rounded-lg text-xs text-red-300 overflow-auto max-h-40">
                  {this.state.error.stack}
                </pre>
              </details>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
