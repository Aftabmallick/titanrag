"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { RAGSettingsRecord, api, normalizeRagSettings, DEFAULT_RAG_SETTINGS } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";

export interface UseRagSettingsReturn {
  settings: RAGSettingsRecord | null;
  loading: boolean;
  saving: boolean;
  isDirty: boolean;
  updateSetting: <K extends keyof RAGSettingsRecord>(key: K, value: RAGSettingsRecord[K]) => void;
  resetToDefaults: () => void;
  saveNow: () => Promise<void>;
  reload: () => Promise<void>;
}

export function useRagSettings(workspaceId: string | undefined): UseRagSettingsReturn {
  const [settings, setSettings] = useState<RAGSettingsRecord | null>(
    workspaceId ? { ...DEFAULT_RAG_SETTINGS, workspace_id: workspaceId } : null
  );
  const [originalSettings, setOriginalSettings] = useState<RAGSettingsRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const pendingSettingsRef = useRef<RAGSettingsRecord | null>(null);
  const { success, error } = useToast();

  const loadSettings = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const data = await api.getRagSettings(workspaceId);
      const normalized = normalizeRagSettings(data, workspaceId);
      setSettings(normalized);
      setOriginalSettings(normalized);
      setIsDirty(false);
    } catch (err: any) {
      error("Failed to load settings", err.message || "Please refresh");
      const fallback = normalizeRagSettings(null, workspaceId);
      setSettings(fallback);
      setOriginalSettings(fallback);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, error]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const saveToBackend = useCallback(
    async (payloadToSave: RAGSettingsRecord) => {
      if (!workspaceId) return;
      setSaving(true);
      try {
        const saved = await api.updateRagSettings(workspaceId, payloadToSave);
        setSettings(saved);
        setOriginalSettings(saved);
        setIsDirty(false);
        success("Settings Saved", "RAG configuration updated successfully.");
      } catch (err: any) {
        error("Failed to save settings", err.message || "Please retry");
      } finally {
        setSaving(false);
      }
    },
    [workspaceId, success, error]
  );

  const updateSetting = useCallback(
    <K extends keyof RAGSettingsRecord>(key: K, value: RAGSettingsRecord[K]) => {
      setSettings((prev) => {
        if (!prev) return prev;
        const updated = { ...prev, [key]: value };
        pendingSettingsRef.current = updated;
        setIsDirty(true);

        // Debounce auto-save by 800ms
        if (debounceTimerRef.current) {
          clearTimeout(debounceTimerRef.current);
        }
        debounceTimerRef.current = setTimeout(() => {
          if (pendingSettingsRef.current) {
            saveToBackend(pendingSettingsRef.current);
          }
        }, 800);

        return updated;
      });
    },
    [saveToBackend]
  );

  const saveNow = useCallback(async () => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    if (settings) {
      await saveToBackend(settings);
    }
  }, [settings, saveToBackend]);

  const resetToDefaults = useCallback(() => {
    if (originalSettings) {
      setSettings(originalSettings);
      setIsDirty(false);
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    }
  }, [originalSettings]);

  return {
    settings,
    loading,
    saving,
    isDirty,
    updateSetting,
    resetToDefaults,
    saveNow,
    reload: loadSettings,
  };
}
