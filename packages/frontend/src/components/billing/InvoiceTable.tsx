"use client";

import React, { useEffect, useState } from "react";
import {
  CheckCircle,
  AlertTriangle,
  Clock,
  Download,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

interface InvoiceItem {
  invoice_id: string;
  amount_due: number;
  amount_paid: number;
  currency: string;
  status: string;
  period_start: string | null;
  period_end: string | null;
  invoice_pdf: string | null;
  hosted_invoice_url: string | null;
}

const STATUS_CONFIG: Record<
  string,
  { label: string; icon: React.ReactNode; className: string }
> = {
  paid: {
    label: "Paid",
    icon: <CheckCircle className="w-3.5 h-3.5" />,
    className: "text-emerald-400 bg-emerald-900/40 ring-1 ring-emerald-700/40",
  },
  open: {
    label: "Pending",
    icon: <Clock className="w-3.5 h-3.5" />,
    className: "text-amber-400 bg-amber-900/40 ring-1 ring-amber-700/40",
  },
  uncollectible: {
    label: "Failed",
    icon: <AlertTriangle className="w-3.5 h-3.5" />,
    className: "text-red-400 bg-red-900/40 ring-1 ring-red-700/40",
  },
};

function formatCents(cents: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(cents / 100);
}

function formatPeriod(start: string | null, end: string | null): string {
  if (!start || !end) return "—";
  const s = new Date(parseInt(start) * 1000).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
  const e = new Date(parseInt(end) * 1000).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  return `${s} – ${e}`;
}

export function InvoiceTable() {
  const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 5;

  useEffect(() => {
    async function fetchInvoices() {
      try {
        const res = await fetch("/api/v1/billing/invoices?limit=20", {
          headers: { Authorization: `Bearer ${localStorage.getItem("titan_token")}` },
        });
        if (res.ok) {
          setInvoices(await res.json());
        }
      } finally {
        setLoading(false);
      }
    }
    fetchInvoices();
  }, []);

  const totalPages = Math.ceil(invoices.length / PAGE_SIZE);
  const pageItems = invoices.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div
            key={i}
            className="h-14 bg-slate-800/50 rounded-xl animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (invoices.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-slate-500">
        <Download className="w-10 h-10 mb-3 opacity-30" />
        <p className="text-sm">No invoices yet</p>
        <p className="text-xs mt-1 text-slate-600">Your invoices will appear here after your first billing cycle.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Table header */}
      <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-4 py-2">
        <span className="text-xs text-slate-500 font-medium">Period</span>
        <span className="text-xs text-slate-500 font-medium text-right">Amount</span>
        <span className="text-xs text-slate-500 font-medium text-center">Status</span>
        <span className="text-xs text-slate-500 font-medium text-right">Actions</span>
      </div>

      {/* Invoice rows */}
      {pageItems.map((inv, idx) => {
        const statusCfg = STATUS_CONFIG[inv.status] || STATUS_CONFIG.open;
        return (
          <div
            key={inv.invoice_id}
            className="grid grid-cols-[1fr_auto_auto_auto] gap-4 items-center px-4 py-3.5 rounded-xl border border-slate-700/50 bg-slate-800/30 hover:bg-slate-800/60 transition-colors duration-150 group"
            style={{
              animationDelay: `${idx * 40}ms`,
              animation: "fadeInSlide 0.3s ease-out both",
            }}
          >
            {/* Period */}
            <div>
              <p className="text-sm text-slate-200 font-medium">
                {formatPeriod(inv.period_start, inv.period_end)}
              </p>
              <p className="text-xs text-slate-500 mt-0.5 font-mono">{inv.invoice_id}</p>
            </div>

            {/* Amount */}
            <div className="text-right">
              <p className="text-sm font-semibold text-slate-100">
                {formatCents(inv.amount_paid || inv.amount_due, inv.currency)}
              </p>
            </div>

            {/* Status pill */}
            <div>
              <span
                className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${statusCfg.className}`}
              >
                {statusCfg.icon}
                {statusCfg.label}
              </span>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-1.5 justify-end">
              {inv.invoice_pdf && (
                <a
                  href={inv.invoice_pdf}
                  target="_blank"
                  rel="noreferrer"
                  id={`invoice-download-${inv.invoice_id}`}
                  className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-700/60 transition-all duration-150"
                  title="Download PDF"
                  aria-label="Download invoice PDF"
                >
                  <Download className="w-4 h-4" />
                </a>
              )}
              {inv.hosted_invoice_url && (
                <a
                  href={inv.hosted_invoice_url}
                  target="_blank"
                  rel="noreferrer"
                  id={`invoice-view-${inv.invoice_id}`}
                  className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-700/60 transition-all duration-150"
                  title="View invoice"
                  aria-label="View invoice online"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>
          </div>
        );
      })}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <span className="text-xs text-slate-500">
            {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, invoices.length)} of {invoices.length}
          </span>
          <div className="flex gap-1">
            <button
              id="invoice-prev-page"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-700/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              aria-label="Previous page"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              id="invoice-next-page"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-700/60 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              aria-label="Next page"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
