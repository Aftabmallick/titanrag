import uuid

from titan_backend.services.retrieval.semantic_cache import semantic_cache


def test_salted_cache_key_isolation() -> None:
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    workspace_1 = uuid.uuid4()

    query = "What is the security compliance policy?"

    key_a = semantic_cache.compute_cache_key(tenant_a, workspace_1, ["engineering"], query)
    key_b = semantic_cache.compute_cache_key(tenant_b, workspace_1, ["engineering"], query)

    # Different tenants MUST generate different keys
    assert key_a != key_b
    assert str(tenant_a) in key_a
    assert str(tenant_b) in key_b

    # Different ACL groups for same user query MUST generate different keys
    key_legal = semantic_cache.compute_cache_key(tenant_a, workspace_1, ["legal"], query)
    assert key_a != key_legal

    # Permuted ACL group lists generate identical deterministic key
    key_permuted_1 = semantic_cache.compute_cache_key(tenant_a, workspace_1, ["admin", "eng"], query)
    key_permuted_2 = semantic_cache.compute_cache_key(tenant_a, workspace_1, ["eng", "admin"], query)
    assert key_permuted_1 == key_permuted_2
