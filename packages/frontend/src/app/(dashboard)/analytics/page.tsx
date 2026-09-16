"use client";

import React from "react";
import { useAuth } from "@/lib/auth";
import { AnalyticsDashboard } from "@/components/analytics/AnalyticsDashboard";

export default function AnalyticsPage() {
  const { activeWorkspace } = useAuth();
  return <AnalyticsDashboard workspaceId={activeWorkspace?.id} />;
}
