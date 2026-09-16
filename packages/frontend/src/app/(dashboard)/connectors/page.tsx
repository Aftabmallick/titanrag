"use client";

import React from "react";
import { useAuth } from "@/lib/auth";
import { ConnectorConsole } from "@/components/connectors/ConnectorConsole";

export default function ConnectorsPage() {
  const { activeWorkspace } = useAuth();
  return <ConnectorConsole workspaceId={activeWorkspace?.id} />;
}
