"use client";

import React from "react";
import { useAuth } from "@/lib/auth";
import { useDashboard } from "@/context/DashboardContext";
import { ChatContainer } from "@/components/chat/ChatContainer";

export default function ChatPage() {
  const { activeWorkspace } = useAuth();
  const { activeSessionId, activeSessionTitle, openPdfCitation, setSettingsOpen } = useDashboard();

  return (
    <div className="h-full flex flex-col min-h-0">
      <ChatContainer
        workspaceId={activeWorkspace?.id}
        sessionId={activeSessionId}
        sessionTitle={activeSessionTitle}
        onCitationClick={openPdfCitation}
        onOpenSettingsDrawer={() => setSettingsOpen(true)}
      />
    </div>
  );
}
