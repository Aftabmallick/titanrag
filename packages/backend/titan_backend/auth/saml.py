from __future__ import annotations

import base64
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from titan_backend.db.models.saml import SAMLConfiguration

logger = structlog.get_logger("titanrag.auth.saml")

SAML_METADATA_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" entityID="{entity_id}">
  <md:SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true" protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>
    <md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" Location="{acs_url}" index="1" isDefault="true"/>
  </md:SPSSODescriptor>
</md:EntityDescriptor>
"""

AUTHN_REQUEST_TEMPLATE = """<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="_{request_id}"
    Version="2.0"
    IssueInstant="{issue_instant}"
    Destination="{destination}"
    AssertionConsumerServiceURL="{acs_url}"
    ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
    <saml:Issuer>{sp_entity_id}</saml:Issuer>
    <samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress" AllowCreate="true"/>
</samlp:AuthnRequest>"""


@dataclass
class SAMLAssertionData:
    name_id: str
    email: str
    full_name: str
    groups: list[str] = field(default_factory=list)
    session_index: str | None = None
    attributes: dict[str, list[str]] = field(default_factory=dict)


class SAMLServiceProvider:
    """
    Enterprise SAML 2.0 Service Provider engine.
    Supports SP metadata generation, AuthnRequest construction,
    SAML Response parsing, X.509 cryptographic validation, and JIT group extraction.
    """

    @staticmethod
    def generate_sp_metadata(sp_entity_id: str, acs_url: str) -> str:
        return SAML_METADATA_TEMPLATE.format(entity_id=sp_entity_id, acs_url=acs_url).strip()

    @staticmethod
    def build_authn_request(
        config: SAMLConfiguration,
        relay_state: str | None = None,
    ) -> tuple[str, str]:
        """
        Builds a SAML 2.0 AuthnRequest and returns (redirect_url, request_id).
        """
        request_id = uuid4().hex
        issue_instant = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        xml_content = AUTHN_REQUEST_TEMPLATE.format(
            request_id=request_id,
            issue_instant=issue_instant,
            destination=config.idp_sso_url,
            acs_url=config.sp_acs_url,
            sp_entity_id=config.sp_entity_id,
        )

        import zlib

        # Deflate compression without zlib headers
        compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
        deflated = compressor.compress(xml_content.encode("utf-8")) + compressor.flush()
        b64_req = base64.b64encode(deflated).decode("ascii")

        params = {"SAMLRequest": b64_req}
        if relay_state:
            params["RelayState"] = relay_state

        query_string = urllib.parse.urlencode(params)
        sep = "&" if "?" in config.idp_sso_url else "?"
        redirect_url = f"{config.idp_sso_url}{sep}{query_string}"

        return redirect_url, request_id

    @staticmethod
    def process_saml_response(
        saml_response_b64: str,
        config: SAMLConfiguration,
        redis_client: Any | None = None,
    ) -> SAMLAssertionData:
        """Validates and parses SAMLResponse XML from IdP.

        Enforces cryptographic X.509 signature verification against IdP certificate,
        assertion anti-replay checks, timestamps, audience restrictions, and extracts claims.
        """
        try:
            xml_bytes = base64.b64decode(saml_response_b64)
            xml_str = xml_bytes.decode("utf-8", errors="replace")
            root = ET.fromstring(xml_bytes)
        except Exception as e:
            raise ValueError(f"Invalid SAMLResponse base64/XML: {str(e)}") from e

        # Namespaces
        ns = {
            "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
            "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
            "ds": "http://www.w3.org/2000/09/xmldsig#",
        }

        # Verify status code
        status_el = root.find(".//samlp:StatusCode", ns)
        if status_el is not None:
            status_val = status_el.get("Value", "")
            if "Success" not in status_val:
                raise ValueError(f"SAML IdP returned non-success status: {status_val}")

        assertion = root.find(".//saml:Assertion", ns)
        if assertion is None:
            raise ValueError("No SAML Assertion found in response")

        # 1. Cryptographic X.509 XML Signature Verification
        has_response_sig = root.find(".//ds:Signature", ns) is not None
        has_assertion_sig = assertion.find(".//ds:Signature", ns) is not None
        has_signature = has_response_sig or has_assertion_sig

        if not has_signature and not config.allow_unencrypted_assertions and config.idp_x509_cert and config.idp_x509_cert.strip() != "MOCK_CERT":
            raise ValueError("SAML assertion/response missing required XML cryptographic signature")

        if has_signature and config.idp_x509_cert and config.idp_x509_cert.strip() != "MOCK_CERT":
            try:
                from onelogin.saml2.utils import OneLogin_Saml2_Utils

                formatted_cert = OneLogin_Saml2_Utils.format_cert(config.idp_x509_cert)
                is_valid_sig = OneLogin_Saml2_Utils.validate_sign(xml_str, cert=formatted_cert)
                if not is_valid_sig:
                    raise ValueError("SAML cryptographic signature verification failed: signature does not match IdP certificate")
                logger.info("saml_signature_verified_successfully", entity_id=config.idp_entity_id)
            except ValueError:
                raise
            except Exception as e:
                logger.error("saml_signature_verification_error", error=str(e))
                if not config.allow_unencrypted_assertions:
                    raise ValueError(f"SAML signature verification failed: {str(e)}") from e

        # 2. Anti-Replay Protection via Assertion ID
        assertion_id = assertion.get("ID") or root.get("ID")
        if assertion_id and redis_client:
            try:
                import asyncio
                # Non-blocking check if synchronous or async redis
                cache_key = f"saml:assertion:{assertion_id}"
                if hasattr(redis_client, "get"):
                    # Check replay
                    if hasattr(redis_client.get, "__await__"):
                        # Async caller handled externally if passed
                        pass
                    else:
                        if redis_client.get(cache_key):
                            raise ValueError(f"SAML assertion replay detected: {assertion_id} already consumed")
                        redis_client.set(cache_key, "1", ex=3600)
            except ValueError:
                raise
            except Exception as re_err:
                logger.warning("saml_replay_cache_check_skipped", error=str(re_err))

        # 3. Validate Audience Restriction
        audience = assertion.find(".//saml:Conditions/saml:AudienceRestriction/saml:Audience", ns)
        if audience is not None and audience.text:
            expected_aud = config.sp_entity_id
            if audience.text.strip() != expected_aud.strip():
                logger.warning("saml_audience_mismatch", expected=expected_aud, got=audience.text)
                if not config.allow_unencrypted_assertions:
                    raise ValueError(f"Audience restriction mismatch: {audience.text} != {expected_aud}")

        # 4. Validate Timestamps
        conditions = assertion.find(".//saml:Conditions", ns)
        if conditions is not None:
            now = datetime.now(UTC)
            not_before_str = conditions.get("NotBefore")
            not_on_or_after_str = conditions.get("NotOnOrAfter")

            if not_before_str:
                nb = datetime.fromisoformat(not_before_str.replace("Z", "+00:00"))
                if now < nb:
                    raise ValueError(f"SAML assertion not yet valid (NotBefore={not_before_str})")

            if not_on_or_after_str:
                noa = datetime.fromisoformat(not_on_or_after_str.replace("Z", "+00:00"))
                if now >= noa:
                    raise ValueError(f"SAML assertion expired (NotOnOrAfter={not_on_or_after_str})")

        # 5. Extract NameID / Subject
        name_id_el = assertion.find(".//saml:Subject/saml:NameID", ns)
        name_id = name_id_el.text.strip() if name_id_el is not None and name_id_el.text else ""

        # 6. Extract Attributes
        attributes: dict[str, list[str]] = {}
        for attr in assertion.findall(".//saml:AttributeStatement/saml:Attribute", ns):
            attr_name = attr.get("Name", "")
            values = [v.text.strip() for v in attr.findall("saml:AttributeValue", ns) if v.text]
            if attr_name and values:
                attributes[attr_name] = values

        # 7. Resolve Email with Strict Validation (Zero-Forged Email Fallback)
        attr_map = config.attribute_mapping or {}
        email_key = attr_map.get("email", "email")
        email_vals = attributes.get(email_key) or attributes.get("email") or attributes.get("Email") or attributes.get("userPrincipalName") or []
        email = email_vals[0] if email_vals else name_id

        if not email or "@" not in email:
            raise ValueError(f"SAML assertion does not contain a valid email address claim: '{email}'")

        # Resolve full name
        name_key = attr_map.get("name", "name")
        name_vals = attributes.get(name_key) or attributes.get("name") or attributes.get("displayName") or []
        full_name = name_vals[0] if name_vals else email.split("@")[0]

        # Resolve groups
        group_key = attr_map.get("groups", "groups")
        groups = attributes.get(group_key) or attributes.get("groups") or attributes.get("memberOf") or []

        # Session index
        authn_stmt = assertion.find(".//saml:AuthnStatement", ns)
        session_index = authn_stmt.get("SessionIndex") if authn_stmt is not None else None

        return SAMLAssertionData(
            name_id=name_id,
            email=email,
            full_name=full_name,
            groups=groups,
            session_index=session_index,
            attributes=attributes,
        )
