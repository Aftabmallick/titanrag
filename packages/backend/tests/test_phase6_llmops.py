import pytest
from uuid import uuid4

from titan_backend.services.ab_testing.router import ABExperimentRouter
from titan_backend.services.ab_testing.statistics import calculate_two_proportion_z_test
from titan_backend.services.evaluation.ir_metrics import (
    hit_rate_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from titan_backend.services.evaluation.metrics import (
    calculate_answer_relevancy_heuristic,
    calculate_context_precision,
    calculate_context_recall,
    calculate_faithfulness,
)
from titan_backend.services.finops.calculator import calculate_compute_units, calculate_dollar_cost
from titan_backend.services.finops.gatekeeper import QuotaExceededException
from titan_backend.services.promptops.diff import compute_prompt_diff, count_tokens
from titan_backend.services.promptops.sandbox import SecurityViolation, sandbox


def test_finops_compute_units_calculation():
    # 1.0 * (1000/1000) + 3.0 * (500/1000) + 3.0 * 2 (OCR) + 5.0 * 1 (context) + 10.0 * 1 (colpali) + 2.0 * 1 (rerank)
    # 1.0 + 1.5 + 6.0 + 5.0 + 10.0 + 2.0 = 25.5 CU
    cu = calculate_compute_units(
        prompt_tokens=1000,
        completion_tokens=500,
        ocr_pages=2,
        contextual_windows=1,
        colpali_pages=1,
        rerank_calls=1,
    )
    assert cu == 25.5

    cost = calculate_dollar_cost(cu, rate_per_cu=0.0025)
    assert cost == 0.0638  # 25.5 * 0.0025 = 0.06375 -> rounded to 0.0638


def test_finops_quota_exceeded_exception():
    with pytest.raises(QuotaExceededException) as exc_info:
        raise QuotaExceededException(current_cu=95.0, max_cu=100.0, requested_cu=10.0)
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["error"] == "QUOTA_EXCEEDED"


def test_promptops_sandbox_safe_render():
    template = "Hello {{ user_name }}, your role is {{ role }}."
    rendered = sandbox.render_prompt(template, {"user_name": "Alice", "role": "Engineer"})
    assert rendered == "Hello Alice, your role is Engineer."


def test_promptops_sandbox_blocks_malicious_code():
    malicious = "{{ __import__('os').system('ls') }}"
    with pytest.raises(SecurityViolation):
        sandbox.validate_template_syntax(malicious)

    malicious_eval = "{{ eval('1+1') }}"
    with pytest.raises(SecurityViolation):
        sandbox.validate_template_syntax(malicious_eval)


def test_prompt_diff_and_token_counts():
    old_p = "You are a helpful assistant."
    new_p = "You are a helpful and precise assistant that cites all sources."
    diff_res = compute_prompt_diff(old_p, new_p)

    assert diff_res["new_token_count"] > diff_res["old_token_count"]
    assert diff_res["token_delta"] > 0
    assert "cites all sources" in diff_res["diff_unified"]


def test_ab_testing_deterministic_bucketing():
    exp_id = uuid4()
    u1 = uuid4()
    u2 = uuid4()

    b1_first = ABExperimentRouter.get_variant_bucket(exp_id, u1)
    b1_second = ABExperimentRouter.get_variant_bucket(exp_id, u1)
    assert b1_first == b1_second
    assert 0 <= b1_first < 100


def test_ab_testing_statistics_z_test():
    # Significant difference
    res_sig = calculate_two_proportion_z_test(count_a=40, n_a=100, count_b=75, n_b=100)
    assert res_sig["statistically_significant"] is True
    assert res_sig["p_value"] < 0.05
    assert res_sig["relative_lift_percent"] > 0

    # No significant difference
    res_insig = calculate_two_proportion_z_test(count_a=50, n_a=100, count_b=51, n_b=100)
    assert res_insig["statistically_significant"] is False
    assert res_insig["p_value"] > 0.05


def test_information_retrieval_metrics():
    retrieved = ["chunk_1", "chunk_2", "chunk_3", "chunk_4", "chunk_5"]
    ground_truth = ["chunk_3", "chunk_10"]

    # MRR: chunk_3 is at rank 3 -> 1/3 = 0.3333
    mrr = mean_reciprocal_rank(retrieved, ground_truth)
    assert round(mrr, 2) == 0.33

    # HitRate@5: chunk_3 is in top 5 -> 1.0
    hit = hit_rate_at_k(retrieved, ground_truth, k=5)
    assert hit == 1.0

    # Recall@5: 1 out of 2 ground truth in top 5 -> 0.5
    rec = recall_at_k(retrieved, ground_truth, k=5)
    assert rec == 0.5

    # Precision@5: 1 relevant out of 5 retrieved -> 0.2
    prec = precision_at_k(retrieved, ground_truth, k=5)
    assert prec == 0.2

    # NDCG@5 > 0
    ndcg = ndcg_at_k(retrieved, ground_truth, k=5)
    assert ndcg > 0.0


def test_ragas_metrics():
    retrieved = ["c1", "c2", "c3"]
    gt = ["c1"]
    cp = calculate_context_precision(retrieved, gt, k=3)
    assert cp == 1.0  # c1 is rank 1

    cr = calculate_context_recall(retrieved, gt)
    assert cr == 1.0

    faith = calculate_faithfulness(["claim1", "claim2"], 2)
    assert faith == 1.0

    rel = calculate_answer_relevancy_heuristic(
        "What is the revenue of Acme?", "Acme revenue reached 50 million in 2024."
    )
    assert rel > 0.5


@pytest.mark.asyncio
async def test_finops_api_endpoints(async_client, mock_db_session):
    from titan_backend.api.v1.auth import CurrentUser, get_current_user
    from titan_backend.db.models.workspaces import Workspace
    from titan_backend.main import app

    tenant_id = uuid4()
    workspace_id = uuid4()
    mock_user = CurrentUser(id=uuid4(), tenant_id=tenant_id, email="admin@corp.com", role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_ws = Workspace(id=workspace_id, tenant_id=tenant_id, name="Test WS")
    mock_db_session.get.return_value = mock_ws

    resp = await async_client.get(f"/api/v1/workspaces/{workspace_id}/finops/usage")
    assert resp.status_code == 200
    data = resp.json()
    assert "current_month_compute_units" in data
    assert data["workspace_id"] == str(workspace_id)

    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_prompts_api_endpoints(async_client, mock_db_session):
    from titan_backend.api.v1.auth import CurrentUser, get_current_user
    from titan_backend.db.models.workspaces import Workspace
    from titan_backend.main import app

    tenant_id = uuid4()
    workspace_id = uuid4()
    mock_user = CurrentUser(id=uuid4(), tenant_id=tenant_id, email="admin@corp.com", role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_ws = Workspace(id=workspace_id, tenant_id=tenant_id, name="Test WS")
    mock_db_session.get.return_value = mock_ws

    resp = await async_client.get(f"/api/v1/workspaces/{workspace_id}/prompts")
    assert resp.status_code == 200
    data = resp.json()
    assert "templates" in data

    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_ab_experiments_api_endpoints(async_client, mock_db_session):
    from titan_backend.api.v1.auth import CurrentUser, get_current_user
    from titan_backend.db.models.workspaces import Workspace
    from titan_backend.main import app

    tenant_id = uuid4()
    workspace_id = uuid4()
    mock_user = CurrentUser(id=uuid4(), tenant_id=tenant_id, email="admin@corp.com", role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_ws = Workspace(id=workspace_id, tenant_id=tenant_id, name="Test WS")
    mock_db_session.get.return_value = mock_ws

    resp = await async_client.get(f"/api/v1/workspaces/{workspace_id}/ab-experiments")
    assert resp.status_code == 200
    data = resp.json()
    assert "experiments" in data

    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_golden_datasets_api_endpoints(async_client, mock_db_session):
    from titan_backend.api.v1.auth import CurrentUser, get_current_user
    from titan_backend.db.models.workspaces import Workspace
    from titan_backend.main import app

    tenant_id = uuid4()
    workspace_id = uuid4()
    mock_user = CurrentUser(id=uuid4(), tenant_id=tenant_id, email="admin@corp.com", role="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_ws = Workspace(id=workspace_id, tenant_id=tenant_id, name="Test WS")
    mock_db_session.get.return_value = mock_ws

    resp = await async_client.get(f"/api/v1/workspaces/{workspace_id}/golden-datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert "datasets" in data

    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_failure_clustering_semantic_similarity(mock_db_session):
    from titan_backend.services.analytics.failure_clustering import FailureClusteringService
    from unittest.mock import MagicMock

    class MockRow:
        def __init__(self, comment, content, issues=None):
            self.comment = comment
            self.content = content
            self.citation_issues = issues or []

    # Two queries regarding patent licensing
    rows = [
        MockRow("The patent licensing terms are missing clause 4", "Here is patent information..."),
        MockRow("Patent licensing agreement royalty rate incorrect", "Royalty details..."),
        MockRow("Pricing table tier 2 calculation wrong", "Pricing details..."),
    ]

    mock_result = MagicMock()
    mock_result.all.return_value = rows
    mock_db_session.execute.return_value = mock_result

    clusters = await FailureClusteringService.cluster_failed_queries(mock_db_session, uuid4())
    assert len(clusters) >= 2

    # Should identify Pricing / Billing and an emergent patent licensing cluster
    keys = [c["topic_key"] for c in clusters]
    assert "pricing_billing" in keys
    assert any("patent" in k or "licensing" in k or "emergent" in k for k in keys)


@pytest.mark.asyncio
async def test_chat_finops_quota_enforcement(async_client, mock_db_session):
    from unittest.mock import patch
    from titan_backend.api.v1.auth import CurrentUser, get_current_user
    from titan_backend.db.models.workspaces import Workspace
    from titan_backend.main import app

    tenant_id = uuid4()
    workspace_id = uuid4()
    mock_user = CurrentUser(id=uuid4(), tenant_id=tenant_id, email="user@corp.com", role="MEMBER", is_superuser=True)
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_ws = Workspace(
        id=workspace_id,
        tenant_id=tenant_id,
        name="Test WS",
        settings={"quota_limits": {"max_compute_units": 100.0}},
    )
    mock_db_session.get.return_value = mock_ws

    with patch(
        "titan_backend.services.finops.gatekeeper.FinOpsGatekeeper.check_and_reserve_quota",
        side_effect=QuotaExceededException(current_cu=100.0, max_cu=100.0, requested_cu=1.0),
    ):
        resp = await async_client.post(
            f"/api/v1/workspaces/{workspace_id}/chat",
            json={"query": "What are our terms?"},
        )
        assert resp.status_code == 429
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "QUOTA_EXCEEDED" or "QUOTA_EXCEEDED" in str(data)

    app.dependency_overrides.pop(get_current_user, None)

