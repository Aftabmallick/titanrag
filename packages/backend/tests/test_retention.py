from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from titan_backend.compliance.retention import RetentionPolicyManager
from titan_backend.db.models.compliance import (
    DataRetentionPolicy,
    RetentionAction,
    RetentionTargetResource,
)


@pytest.mark.asyncio
async def test_retention_create_and_dry_run():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_res

    tenant_id = uuid4()
    policy = await RetentionPolicyManager.create_or_update_policy(
        session=session,
        tenant_id=tenant_id,
        target_resource=RetentionTargetResource.CHAT_MESSAGES,
        ttl_days=30,
        action=RetentionAction.HARD_DELETE,
    )

    assert policy.target_resource == RetentionTargetResource.CHAT_MESSAGES
    assert policy.ttl_days == 30
    assert policy.action == RetentionAction.HARD_DELETE

    # Dry-run test
    mock_policy_res = MagicMock()
    mock_policy_res.scalar_one_or_none.return_value = policy

    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 42

    session.execute.side_effect = [mock_policy_res, mock_count_res]

    impact = await RetentionPolicyManager.calculate_dry_run_impact(session, policy.id)
    assert impact["eligible_records"] == 42
    assert impact["estimated_bytes_reclaimable"] > 0
    assert impact["target_resource"] == "CHAT_MESSAGES"


@pytest.mark.asyncio
async def test_retention_policy_sweep_execution():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    tenant_id = uuid4()
    policy = DataRetentionPolicy(
        id=uuid4(),
        tenant_id=tenant_id,
        target_resource=RetentionTargetResource.CHAT_MESSAGES,
        ttl_days=14,
        action=RetentionAction.HARD_DELETE,
        is_active=True,
    )

    # Mock select message IDs and delete execution
    mock_ids_res = MagicMock()
    mock_ids_res.scalars.return_value.all.return_value = [uuid4(), uuid4()]
    mock_del_res = MagicMock()

    session.execute.side_effect = [mock_ids_res, mock_del_res]

    audit_entry = await RetentionPolicyManager.execute_policy_sweep(session, policy)

    assert audit_entry.records_purged == 2
    assert audit_entry.bytes_reclaimed > 0
    assert audit_entry.resource_type == RetentionTargetResource.CHAT_MESSAGES
