import io
import json
import zipfile
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from titan_backend.compliance.consent import ConsentManager
from titan_backend.compliance.export import GDPRExportService
from titan_backend.compliance.gdpr import GDPRDeletionManager
from titan_backend.compliance.ropa import RoPAService
from titan_backend.db.models.compliance import (
    ConsentPurpose,
    ConsentStatus,
    GDPRDeletionStatus,
)
from titan_backend.db.models.users import User


@pytest.mark.asyncio
async def test_consent_record_and_check():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_res

    tenant_id = uuid4()
    user_id = uuid4()

    with patch("titan_backend.compliance.consent.get_redis_client") as mock_redis_getter:
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis_getter.return_value = mock_redis

        consent = await ConsentManager.record_consent(
            session=session,
            tenant_id=tenant_id,
            user_id=user_id,
            purpose=ConsentPurpose.TRAINING,
            status=ConsentStatus.GRANTED,
        )

        assert consent.user_id == user_id
        assert consent.purpose == ConsentPurpose.TRAINING
        assert consent.status == ConsentStatus.GRANTED

        # Check grant
        mock_res.scalar_one_or_none.return_value = ConsentStatus.GRANTED
        is_granted = await ConsentManager.is_consent_granted(
            session=session,
            tenant_id=tenant_id,
            user_id=user_id,
            purpose=ConsentPurpose.TRAINING,
        )
        assert is_granted is True


@pytest.mark.asyncio
async def test_gdpr_deletion_initiation_and_sla():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    tenant_id = uuid4()
    user_id = uuid4()
    admin_id = uuid4()

    fake_user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="test_gdpr@example.com",
        full_name="Test User",
        hashed_password="hash",
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.side_effect = [fake_user, None]
    session.execute.return_value = mock_res

    req = await GDPRDeletionManager.initiate_deletion(
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        requested_by_id=admin_id,
    )

    assert req.user_id == user_id
    assert req.status == GDPRDeletionStatus.PENDING
    assert req.sla_deadline > datetime.now(UTC)


@pytest.mark.asyncio
async def test_gdpr_export_package_structure():
    session = AsyncMock()
    tenant_id = uuid4()
    user_id = uuid4()

    fake_user = User(
        id=user_id,
        tenant_id=tenant_id,
        email="export_user@example.com",
        full_name="Export User",
        hashed_password="hash",
        created_at=datetime.now(UTC),
    )

    mock_user_res = MagicMock()
    mock_user_res.scalar_one_or_none.return_value = fake_user

    mock_empty_res = MagicMock()
    mock_empty_res.scalars.return_value.all.return_value = []

    session.execute.side_effect = [
        mock_user_res,  # User
        mock_empty_res,  # Workspaces
        mock_empty_res,  # Chat sessions
        mock_empty_res,  # Feedback
        mock_empty_res,  # Consents
        mock_empty_res,  # Documents
    ]

    with patch("titan_backend.compliance.export.get_minio_client", return_value=None):
        zip_buf = await GDPRExportService.generate_export_package(
            session=session,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    assert isinstance(zip_buf, io.BytesIO)
    with zipfile.ZipFile(zip_buf, "r") as zf:
        file_list = zf.namelist()
        assert "profile.json" in file_list
        assert "workspaces.json" in file_list
        assert "chat_history.json" in file_list
        assert "feedback.json" in file_list
        assert "consents.json" in file_list
        assert "manifest.json" in file_list

        manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest_data["user_id"] == str(user_id)
        assert "profile.json" in manifest_data["files"]


@pytest.mark.asyncio
async def test_ropa_report_generation():
    session = AsyncMock()
    tenant_id = uuid4()

    mock_tenant_res = MagicMock()
    mock_tenant_res.scalar_one_or_none.return_value = None

    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 10

    mock_policies_res = MagicMock()
    mock_policies_res.scalars.return_value.all.return_value = []

    session.execute.side_effect = [
        mock_tenant_res,
        mock_count_res,
        mock_count_res,
        mock_policies_res,
    ]

    report = await RoPAService.generate_ropa_report(session, tenant_id)
    assert "Article 30" in report["title"]
    assert len(report["processing_activities"]) >= 3
    assert len(report["security_measures"]) >= 4
