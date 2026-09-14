from titan_workers.pipeline.deduplication.minhash import MinHashDeduplicator


def test_minhash_signature_and_jaccard():
    dedup = MinHashDeduplicator()
    text_a = "The quick brown fox jumps over the lazy dog in the sunny afternoon."
    text_b = "The quick brown fox jumps over the lazy dog in the warm afternoon."
    text_c = "Completely different content regarding interstellar spacecraft navigation."

    sig_a = dedup.compute_signature(text_a)
    sig_b = dedup.compute_signature(text_b)
    sig_c = dedup.compute_signature(text_c)

    assert len(sig_a) == 64
    assert len(sig_b) == 64
    assert len(sig_c) == 64

    sim_ab = dedup.estimate_jaccard(text_a, text_b)
    sim_ac = dedup.estimate_jaccard(text_a, text_c)

    assert sim_ab > 0.60
    assert sim_ac < 0.20


def test_delta_reembedding_detection():
    dedup = MinHashDeduplicator()
    chunk1_text = "Paragraph 1: Core system capabilities."
    chunk2_text = "Paragraph 2: Unchanged specifications."
    chunk3_text = "Paragraph 3: Revised updated information."

    sig1 = dedup.compute_signature(chunk1_text)
    sig2 = dedup.compute_signature(chunk2_text)
    sig3 = dedup.compute_signature(chunk3_text)

    existing_chunks = [
        {"id": "c1", "minhash_signature": sig1, "content": chunk1_text},
        {"id": "c2", "minhash_signature": sig2, "content": chunk2_text},
    ]

    new_chunks = [
        {"id": "new_c2", "minhash_signature": sig2, "content": chunk2_text},  # Unchanged
        {"id": "new_c3", "minhash_signature": sig3, "content": chunk3_text},  # Changed
    ]

    unchanged, changed = dedup.detect_deltas(new_chunks, existing_chunks)
    assert len(unchanged) == 1
    assert unchanged[0]["id"] == "new_c2"
    assert unchanged[0]["reused_vector_id"] == "c2"

    assert len(changed) == 1
    assert changed[0]["id"] == "new_c3"
