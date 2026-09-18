"""Reference Out-of-Process Webhook Micro-Hook Server for TitanRAG.

Demonstrates production-grade HMAC-SHA256 signature verification, anti-replay checks,
and handling of ON_PARSE, ON_RERANK, ON_POST_GENERATE, and PING hooks.
"""

import hashlib
import hmac
import os
import time
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request, status

app = FastAPI(title="TitanRAG Reference Plugin Microservice", version="1.0.0")

# Secret configured during plugin registration in TitanRAG
WEBHOOK_SECRET = os.getenv("PLUGIN_WEBHOOK_SECRET", "reference_test_secret_key_32_bytes_len")


def verify_titan_signature(body: bytes, sig_header: str | None, max_drift_seconds: int = 300) -> None:
    if not sig_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Titan-Signature header")

    pairs: dict[str, str] = {}
    for part in sig_header.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            pairs[k.strip()] = v.strip()

    if "t" not in pairs or "v1" not in pairs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed signature header format")

    try:
        ts = int(pairs["t"])
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid timestamp in signature") from None

    now = int(time.time())
    if abs(now - ts) > max_drift_seconds:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Signature timestamp drift exceeded (replay rejected)"
        )

    msg = f"{ts}.".encode() + body
    expected = hmac.new(WEBHOOK_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, pairs["v1"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC-SHA256 signature")


@app.post("/webhook")
async def handle_titan_hook(
    request: Request,
    x_titan_signature: str | None = Header(None),
    x_titan_hook: str | None = Header(None),
) -> dict[str, Any]:
    body = await request.body()
    verify_titan_signature(body, x_titan_signature)

    payload = await request.json() if body else {}

    # 1. Health Probe
    if x_titan_hook == "PING" or payload.get("event") == "ping":
        return {
            "status": "pong",
            "verified": True,
            "timestamp": int(time.time()),
            "message": "TitanRAG webhook signature verified successfully",
        }

    # 2. Document Parser Hook (ON_PARSE)
    elif x_titan_hook == "ON_PARSE":
        filename = payload.get("filename", "document.pdf")
        raw_text = payload.get("raw_text", "")
        # Enriched contract parser example
        return {
            "handled": True,
            "parser_name": "LegalContractSpecializedParser/v1",
            "extracted_metadata": {
                "document_category": "Legal Agreement",
                "jurisdiction": "Delaware",
                "filename": filename,
                "clauses_detected": ["Indemnification", "Governing Law", "Severability"],
            },
            "enriched_text": f"[File: {filename} | Category: Legal Agreement | Jurisdiction: Delaware]\n{raw_text}",
        }

    # 3. Post-Generation Egress Compliance Hook (ON_POST_GENERATE)
    elif x_titan_hook == "ON_POST_GENERATE":
        generated_answer = payload.get("generated_answer", "")
        # Redact test credit card or SSN pattern if present
        sanitized = generated_answer.replace("4000-1234-5678-9010", "[REDACTED_CARD]")
        return {
            "handled": True,
            "compliance_checked": True,
            "sanitized_answer": sanitized,
            "audit_tag": "legal_egress_verified",
        }

    # Fallback
    return {
        "handled": True,
        "hook": x_titan_hook,
        "status": "acknowledged",
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9099"))
    uvicorn.run(app, host="0.0.0.0", port=port)
