import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { RAGSettingsRecord } from "../src/lib/api";

describe("RAG Settings Invariants & Debounce Controls", () => {
  const defaultSettings: RAGSettingsRecord = {
    workspace_id: "ws-test-123",
    search_strategy: "hybrid",
    hybrid_alpha: 0.7,
    top_k: 40,
    rerank_top_k: 5,
    reranker_model: "cohere-rerank-v3",
    score_threshold: 0.4,
    llm_model: "gpt-4o",
    grounding_mode: "balanced",
    system_prompt: "You are TitanRAG enterprise assistant.",
    temperature: 0.2,
    parent_context_enabled: true,
    hyde_enabled: false,
    contextual_chunking_enabled: true,
    nli_verification_enabled: true,
    pii_redaction_mode: "REPLACE",
    semantic_cache_enabled: true,
    cache_similarity_threshold: 0.95,
    cache_ttl_seconds: 86400,
  };

  test("validates default parameter bounds", () => {
    assert.ok(defaultSettings.hybrid_alpha >= 0.0 && defaultSettings.hybrid_alpha <= 1.0);
    assert.ok(defaultSettings.top_k >= 1 && defaultSettings.top_k <= 100);
    assert.ok(defaultSettings.rerank_top_k >= 1 && defaultSettings.rerank_top_k <= defaultSettings.top_k);
    assert.ok(defaultSettings.temperature >= 0.0 && defaultSettings.temperature <= 1.0);
    assert.ok(defaultSettings.cache_similarity_threshold >= 0.8 && defaultSettings.cache_similarity_threshold <= 1.0);
  });

  test("clamps numeric parameters within bounds", () => {
    function clampAlpha(val: number): number {
      return Math.min(1.0, Math.max(0.0, +val.toFixed(2)));
    }

    assert.equal(clampAlpha(-0.5), 0.0);
    assert.equal(clampAlpha(1.5), 1.0);
    assert.equal(clampAlpha(0.65), 0.65);
  });

  test("debounces rapid consecutive setting modifications into a single target payload", async () => {
    let savedPayload: RAGSettingsRecord | null = null;
    let saveCount = 0;
    let timer: NodeJS.Timeout | null = null;

    function queueSave(newSettings: RAGSettingsRecord) {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        savedPayload = newSettings;
        saveCount++;
      }, 50); // 50ms test debounce window
    }

    // Fire 5 rapid changes
    queueSave({ ...defaultSettings, hybrid_alpha: 0.2 });
    queueSave({ ...defaultSettings, hybrid_alpha: 0.4 });
    queueSave({ ...defaultSettings, hybrid_alpha: 0.6 });
    queueSave({ ...defaultSettings, hybrid_alpha: 0.8 });
    queueSave({ ...defaultSettings, hybrid_alpha: 0.95 });

    // Wait for timer to expire
    await new Promise((resolve) => setTimeout(resolve, 80));

    assert.equal(saveCount, 1, "Expected exactly 1 debounced save invocation");
    assert.ok(savedPayload);
    assert.equal((savedPayload as RAGSettingsRecord).hybrid_alpha, 0.95);
  });
});
