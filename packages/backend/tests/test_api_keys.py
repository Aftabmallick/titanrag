from uuid import uuid4

import pytest
from titan_backend.core.dependencies import CurrentUser, require_scope
from titan_backend.core.errors import AppException
from titan_backend.core.security import generate_secure_api_key, hash_api_key


def test_api_key_generation_and_hashing():
    raw_key, prefix, hashed = generate_secure_api_key(prefix="rg_live")
    assert raw_key.startswith("rg_live_")
    assert prefix.startswith("rg_live_")
    assert len(hashed) == 64  # SHA-256 hex string

    # Verify matching hash
    assert hash_api_key(raw_key) == hashed
    assert hash_api_key("wrong_key") != hashed


@pytest.mark.asyncio
async def test_scope_enforcement():
    # User with only read scope
    read_user = CurrentUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="reader@corp.com",
        scopes=["read"],
        is_api_key=True,
    )

    read_dep = require_scope("read")
    res = await read_dep(read_user)
    assert res == read_user

    # Attempting write scope must raise AppException 403
    write_dep = require_scope("write")
    with pytest.raises(AppException) as exc_info:
        await write_dep(read_user)
    assert exc_info.value.status_code == 403
    assert exc_info.value.error_code == "INSUFFICIENT_SCOPE"

    # User with wildcard '*' scope
    admin_user = CurrentUser(
        id=uuid4(),
        tenant_id=uuid4(),
        email="admin@corp.com",
        scopes=["*"],
        is_api_key=True,
    )
    res_admin = await write_dep(admin_user)
    assert res_admin == admin_user
