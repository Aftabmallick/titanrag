"use client";

import React from "react";
import { Palette, Globe, Mail } from "lucide-react";
import { BrandConfigEditor } from "@/components/brand/BrandConfigEditor";

export default function BrandPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-600 to-purple-600 flex items-center justify-center">
            <Palette className="w-5 h-5 text-white" />
          </div>
          White-Label Branding
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Customize your platform&apos;s appearance with your company logo, colors, and custom domain.
        </p>
      </div>

      {/* Feature callouts */}
      <div className="grid grid-cols-3 gap-4">
        {[
          {
            icon: <Palette className="w-4 h-4 text-violet-400" />,
            title: "Dynamic Theming",
            desc: "Colors applied instantly across all UI",
          },
          {
            icon: <Globe className="w-4 h-4 text-indigo-400" />,
            title: "Custom Domain",
            desc: "Serve from your own domain with SSL",
          },
          {
            icon: <Mail className="w-4 h-4 text-emerald-400" />,
            title: "Branded Emails",
            desc: "Invite and reset emails with your logo",
          },
        ].map(({ icon, title, desc }) => (
          <div
            key={title}
            className="glass-card rounded-xl border border-slate-700/50 p-4"
          >
            <div className="flex items-center gap-2 mb-1">
              {icon}
              <span className="text-xs font-semibold text-slate-200">{title}</span>
            </div>
            <p className="text-xs text-slate-500">{desc}</p>
          </div>
        ))}
      </div>

      {/* Main editor */}
      <div className="glass-card rounded-2xl border border-slate-700/50 p-6">
        <BrandConfigEditor />
      </div>
    </div>
  );
}
