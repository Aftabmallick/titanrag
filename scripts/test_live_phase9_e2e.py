"""TitanRAG Phase 9 Comprehensive Live HTTP Integration Test Suite.

Executes live HTTP API requests against the running FastAPI server (http://localhost:8000),
verifying authentication, RoPA reports, consent lifecycle, data retention policies,
residency compliance audits, ZDR verification, BYOK KMS keys, and GDPR right-to-deletion cascades.
"""

import random
import sys
import uuid

import httpx

BASE_URL = "http://localhost:8000"


def log(msg: str) -> None:
    print(f"[LIVE TEST] {msg}")


def main() -> None:
    test_client_ip = f"10.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
    client = httpx.Client(base_url=BASE_URL, timeout=30.0, headers={"X-Forwarded-For": test_client_ip})
    passed_steps = 0
    total_steps = 14

    log("================================================================================")
    log("Starting Phase 9 Live E2E Integration Testing against http://localhost:8000")
    log("================================================================================")

    # 1. Health Probe
    log("Step 1: Checking /health/ready...")
    resp = client.get("/health/ready")
    assert resp.status_code == 200, f"Health check failed: {resp.status_code} {resp.text}"
    health_data = resp.json()
    assert health_data["status"] == "ready"
    assert health_data["dependencies"]["postgres"]["status"] == "ok"
    assert health_data["dependencies"]["qdrant"]["status"] == "ok"
    assert health_data["dependencies"]["redis"]["status"] == "ok"
    assert health_data["dependencies"]["minio"]["status"] == "ok"
    log(f"  -> Health ready: Postgres, Qdrant, Redis, MinIO all operational (latencies: {health_data['dependencies']})")
    passed_steps += 1

    # 2. Live Registration & Auth
    log("Step 2: Registering live enterprise tenant and user...")
    test_id = uuid.uuid4().hex[:8]
    email = f"compliance_officer_{test_id}@titanrag.internal"
    password = "LiveTestingPassword123!"
    tenant_name = f"Live-Corp-{test_id}"

    reg_payload = {
        "email": email,
        "password": password,
        "full_name": "Chief Compliance Officer",
        "tenant_name": tenant_name,
    }
    resp = client.post("/api/v1/auth/register", json=reg_payload)
    assert resp.status_code == 201, f"Registration failed: {resp.status_code} {resp.text}"
    auth_data = resp.json()
    access_token = auth_data["access_token"]
    assert access_token is not None and len(access_token) > 20
    headers = {"Authorization": f"Bearer {access_token}"}
    log(f"  -> Registered tenant '{tenant_name}' with token (length {len(access_token)})")
    passed_steps += 1

    # 3. RoPA Generation
    log("Step 3: Generating GDPR Article 30 RoPA compliance register...")
    resp = client.get("/api/v1/compliance/ropa", headers=headers)
    assert resp.status_code == 200, f"RoPA failed: {resp.status_code} {resp.text}"
    ropa = resp.json()
    assert "controller" in ropa
    assert "processing_activities" in ropa
    assert len(ropa["processing_activities"]) >= 3
    assert len(ropa["security_measures"]) >= 6
    log(
        f"  -> RoPA generated with {len(ropa['processing_activities'])} registered processing activities and {len(ropa['security_measures'])} security measures"
    )
    passed_steps += 1

    # 4. Consent Lifecycle
    log("Step 4: Testing consent management (record, list, and verify)...")
    consent_payload = {
        "purpose": "ANALYTICS",
        "status": "GRANTED",
        "version": "v1.2.0",
    }
    resp = client.post("/api/v1/compliance/consent", json=consent_payload, headers=headers)
    assert resp.status_code == 200, f"Consent record failed: {resp.status_code} {resp.text}"
    consent_rec = resp.json()
    assert consent_rec["purpose"] == "ANALYTICS"
    assert consent_rec["status"] == "GRANTED"

    resp = client.get("/api/v1/compliance/consent", headers=headers)
    assert resp.status_code == 200
    user_consents = resp.json()
    assert len(user_consents) >= 1
    log(f"  -> Consent successfully recorded and listed: purpose={user_consents[0]['purpose']}")
    passed_steps += 1

    # 5. Data Retention Policies
    log("Step 5: Creating and querying data retention policies...")
    retention_payload = {
        "target_resource": "CHAT_MESSAGES",
        "ttl_days": 90,
        "action": "HARD_DELETE",
        "is_active": True,
    }
    resp = client.post("/api/v1/compliance/retention", json=retention_payload, headers=headers)
    assert resp.status_code == 200, f"Retention create failed: {resp.status_code} {resp.text}"
    policy_data = resp.json()
    policy_id = policy_data["id"]
    assert policy_data["target_resource"] == "CHAT_MESSAGES"
    assert policy_data["ttl_days"] == 90

    resp = client.get("/api/v1/compliance/retention", headers=headers)
    assert resp.status_code == 200
    policies = resp.json()
    assert len(policies) >= 1
    log(
        f"  -> Data retention policy created and verified: id={policy_id}, resource={policies[0]['target_resource']}, ttl={policies[0]['ttl_days']}d"
    )
    passed_steps += 1

    # 6. Retention Dry-Run Sweep and Run Now
    log("Step 6: Executing dry-run retention calculation and execution sweep...")
    resp = client.post(f"/api/v1/compliance/retention/{policy_id}/dry-run", headers=headers)
    assert resp.status_code == 200, f"Dry-run failed: {resp.status_code} {resp.text}"
    dry_run_res = resp.json()
    assert "eligible_records" in dry_run_res
    assert dry_run_res["policy_id"] == policy_id
    log(f"  -> Retention dry-run calculated: {dry_run_res['eligible_records']} records eligible for purging")

    # Trigger live sweep now
    sweep_resp = client.post("/api/v1/compliance/retention/run-now", headers=headers)
    assert sweep_resp.status_code == 200, f"Run-now failed: {sweep_resp.status_code} {sweep_resp.text}"
    sweep_data = sweep_resp.json()
    assert "policies_swept" in sweep_data
    log(f"  -> Retention sweep executed live: {sweep_data['policies_swept']} policies swept")

    # Verify audit logs
    logs_resp = client.get("/api/v1/compliance/retention/logs", headers=headers)
    assert logs_resp.status_code == 200
    audit_logs = logs_resp.json()
    assert len(audit_logs) >= 1
    log(f"  -> Verified {len(audit_logs)} retention audit log records stored in PostgreSQL")
    passed_steps += 1

    # 7. Data Residency Configuration
    log("Step 7: Testing regional data residency configuration...")
    resp = client.get("/api/v1/compliance/residency", headers=headers)
    assert resp.status_code == 200, f"Residency get failed: {resp.status_code} {resp.text}"
    residency_info = resp.json()
    assert "region" in residency_info
    log(f"  -> Current data residency region: {residency_info['region']}, bucket: {residency_info['storage_bucket']}")

    update_residency_payload = {
        "region": "EU_WEST",
        "enforce_strict": True,
    }
    resp = client.post("/api/v1/compliance/residency", json=update_residency_payload, headers=headers)
    assert resp.status_code == 200, f"Residency update failed: {resp.status_code} {resp.text}"
    updated_res = resp.json()
    assert updated_res["region"] == "EU_WEST"
    assert updated_res["storage_bucket"] == "titan-documents-eu-west"
    log("  -> Switched tenant residency to EU_WEST (bucket: titan-documents-eu-west)")
    passed_steps += 1

    # 8. Data Residency Audit Probe Scorecard
    log("Step 8: Executing live data residency compliance audit probe...")
    resp = client.post("/api/v1/compliance/residency/audit-probe", headers=headers)
    assert resp.status_code == 200, f"Audit probe failed: {resp.status_code} {resp.text}"
    probe_data = resp.json()
    assert "tenant_id" in probe_data
    assert "overall_status" in probe_data
    assert "checks" in probe_data
    log(
        f"  -> Compliance scorecard: status={probe_data['overall_status']}, score={probe_data['compliance_score']}%, total checks={len(probe_data['checks'])}"
    )
    passed_steps += 1

    # 9. ZDR Model Enforcement Verification
    log("Step 9: Testing Zero Data Retention (ZDR) policy checks...")
    # Test valid ZDR model
    zdr_valid_payload = {
        "model_name": "anthropic/claude-3-5-sonnet-20241022",
        "enforce_zdr": True,
    }
    resp = client.post("/api/v1/compliance/residency/check-zdr", json=zdr_valid_payload, headers=headers)
    assert resp.status_code == 200
    zdr_res = resp.json()
    assert zdr_res["decision"] == "ALLOWED"
    assert zdr_res["zdr_certified"] is True
    log(f"  -> Certified ZDR model approved: {zdr_valid_payload['model_name']} (decision: {zdr_res['decision']})")

    # Test non-ZDR model with enforcement
    zdr_invalid_payload = {
        "model_name": "untrusted-open-model-v1",
        "enforce_zdr": True,
    }
    resp = client.post("/api/v1/compliance/residency/check-zdr", json=zdr_invalid_payload, headers=headers)
    assert resp.status_code == 403
    log("  -> Untrusted model correctly rejected by ZDR policy enforcement (HTTP 403 Forbidden)")
    passed_steps += 1

    # 10. BYOK KMS Configuration & Key Lifecycle
    log("Step 10: Testing BYOK Key Management Service (KMS)...")
    resp = client.get("/api/v1/security/kms", headers=headers)
    assert resp.status_code == 200
    kms_initial = resp.json()
    log(f"  -> Initial KMS state: status={kms_initial['status']}, provider={kms_initial['provider']}")

    kms_configure_payload = {
        "provider": "LOCAL",
        "key_arn_or_path": "local-aes-key-slot-1",
        "rotation_schedule_days": 60,
    }
    resp = client.post("/api/v1/security/kms", json=kms_configure_payload, headers=headers)
    assert resp.status_code == 200, f"KMS config failed: {resp.status_code} {resp.text}"
    kms_conf = resp.json()
    assert kms_conf["status"] == "KMS_CONFIGURED"
    assert kms_conf["dek_version"] == 1
    log("  -> Configured BYOK envelope encryption DEK version 1")
    passed_steps += 1

    # 11. KMS Key Rotation
    log("Step 11: Executing live zero-downtime key rotation...")
    resp = client.post("/api/v1/security/kms/rotate", headers=headers)
    assert resp.status_code == 200, f"Key rotation failed: {resp.status_code} {resp.text}"
    rotate_res = resp.json()
    assert rotate_res["status"] == "ROTATION_SUCCESSFUL"
    assert rotate_res["new_dek_version"] == 2
    log(
        f"  -> KMS key successfully rotated to version {rotate_res['new_dek_version']} (previous version {rotate_res['old_dek_version']})"
    )
    passed_steps += 1

    # 12. GDPR Data Export
    log("Step 12: Generating and downloading signed GDPR data export archive...")
    resp = client.get("/api/v1/compliance/gdpr/export", headers=headers)
    assert resp.status_code == 200, f"GDPR export failed: {resp.status_code} {resp.text}"
    assert resp.headers.get("content-type") == "application/zip"
    zip_bytes = resp.content
    assert len(zip_bytes) > 100
    log(f"  -> GDPR data export archive downloaded ({len(zip_bytes)} bytes zip package)")
    passed_steps += 1

    # 13. GDPR Right-to-Deletion Cascade
    log("Step 13: Initiating GDPR Right-to-Deletion cascade...")
    # Register a temporary user to wipe
    temp_email = f"temp_user_{uuid.uuid4().hex[:6]}@titanrag.internal"
    temp_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": temp_email,
            "password": "Password123!",
            "full_name": "Temporary User",
            "tenant_name": f"TempOrg-{uuid.uuid4().hex[:4]}",
        },
    )
    assert temp_reg.status_code == 201
    temp_token = temp_reg.json()["access_token"]
    temp_headers = {"Authorization": f"Bearer {temp_token}"}

    # User initiates their own deletion
    me_resp = client.get("/api/v1/auth/me", headers=temp_headers)
    assert me_resp.status_code == 200
    temp_user_id = me_resp.json()["id"]

    del_resp = client.post("/api/v1/compliance/gdpr/delete", json={"user_id": temp_user_id}, headers=temp_headers)
    assert del_resp.status_code == 200, f"Initiate deletion failed: {del_resp.status_code} {del_resp.text}"
    del_data = del_resp.json()
    request_id = del_data["request_id"]
    log(f"  -> GDPR deletion request registered: request_id={request_id}, SLA deadline={del_data['sla_deadline']}")

    # Execute cascade deletion
    exec_resp = client.post(f"/api/v1/compliance/gdpr/requests/{request_id}/execute", headers=temp_headers)
    assert exec_resp.status_code == 200, f"Execute deletion failed: {exec_resp.status_code} {exec_resp.text}"
    exec_data = exec_resp.json()
    assert exec_data["status"] == "COMPLETED"
    assert exec_data["verification_hash"] is not None
    log(f"  -> Cascade deletion executed: verification_hash={exec_data['verification_hash'][:16]}...")
    passed_steps += 1

    # 14. GDPR SLA & Certificate Verification
    log("Step 14: Verifying GDPR deletion cryptographic certificate & SLA compliance...")
    ver_resp = client.get(f"/api/v1/compliance/gdpr/requests/{request_id}/verify", headers=temp_headers)
    assert ver_resp.status_code == 200
    ver_data = ver_resp.json()
    assert ver_data["is_sla_met"] is True
    assert ver_data["verification_hash"] is not None
    assert ver_data["integrity_audit"]["clean_cascade_verified"] is True
    log(
        f"  -> Certificate verified: is_sla_met={ver_data['is_sla_met']}, clean_cascade_verified={ver_data['integrity_audit']['clean_cascade_verified']}"
    )
    passed_steps += 1

    log("================================================================================")
    log(f"ALL {passed_steps}/{total_steps} LIVE PHASE 9 TESTS PASSED SUCCESSFULLY!")
    log("================================================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[LIVE TEST ERROR] {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
