import base64
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from titan_backend.auth.saml import SAMLAssertionData, SAMLServiceProvider
from titan_backend.db.models.saml import SAMLConfiguration

MOCK_SAML_RESPONSE_XML = """<?xml version="1.0"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="_resp_123"
                Version="2.0"
                IssueInstant="{issue_instant}">
  <samlp:Status>
    <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/>
  </samlp:Status>
  <saml:Assertion ID="_assert_456" Version="2.0" IssueInstant="{issue_instant}">
    <saml:Issuer>https://idp.okta.com/exk123</saml:Issuer>
    <saml:Subject>
      <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">alice.doe@enterprise.com</saml:NameID>
    </saml:Subject>
    <saml:Conditions NotBefore="{not_before}" NotOnOrAfter="{not_on_or_after}">
      <saml:AudienceRestriction>
        <saml:Audience>https://titanrag.enterprise.io/sp</saml:Audience>
      </saml:AudienceRestriction>
    </saml:Conditions>
    <saml:AuthnStatement AuthnInstant="{issue_instant}" SessionIndex="_sess_789"/>
    <saml:AttributeStatement>
      <saml:Attribute Name="email">
        <saml:AttributeValue>alice.doe@enterprise.com</saml:AttributeValue>
      </saml:Attribute>
      <saml:Attribute Name="name">
        <saml:AttributeValue>Alice Doe</saml:AttributeValue>
      </saml:Attribute>
      <saml:Attribute Name="groups">
        <saml:AttributeValue>SecOps</saml:AttributeValue>
        <saml:AttributeValue>Executive-Board</saml:AttributeValue>
      </saml:Attribute>
    </saml:AttributeStatement>
  </saml:Assertion>
</samlp:Response>
"""


def test_generate_sp_metadata():
    sp_entity_id = "https://titanrag.io/sp"
    acs_url = "https://titanrag.io/api/v1/auth/sso/saml/acs"
    xml = SAMLServiceProvider.generate_sp_metadata(sp_entity_id, acs_url)

    assert "EntityDescriptor" in xml
    assert 'entityID="https://titanrag.io/sp"' in xml
    assert 'Location="https://titanrag.io/api/v1/auth/sso/saml/acs"' in xml
    assert "AssertionConsumerService" in xml


def test_build_authn_request():
    config = SAMLConfiguration(
        idp_entity_id="https://idp.okta.com/exk123",
        idp_sso_url="https://idp.okta.com/app/sso",
        idp_x509_cert="MOCK_CERT",
        sp_entity_id="https://titanrag.io/sp",
        sp_acs_url="https://titanrag.io/acs",
    )

    redirect_url, req_id = SAMLServiceProvider.build_authn_request(config, relay_state="workspace_1")
    assert redirect_url.startswith("https://idp.okta.com/app/sso?")
    assert "SAMLRequest=" in redirect_url
    assert "RelayState=workspace_1" in redirect_url
    assert len(req_id) > 10


def test_process_saml_response_success():
    now = datetime.now(timezone.utc)
    issue_instant = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    not_before = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    not_on_or_after = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")

    xml = MOCK_SAML_RESPONSE_XML.format(
        issue_instant=issue_instant,
        not_before=not_before,
        not_on_or_after=not_on_or_after,
    )
    b64_response = base64.b64encode(xml.encode("utf-8")).decode("ascii")

    config = SAMLConfiguration(
        idp_entity_id="https://idp.okta.com/exk123",
        idp_sso_url="https://idp.okta.com/app/sso",
        idp_x509_cert="MOCK_CERT",
        sp_entity_id="https://titanrag.enterprise.io/sp",
        sp_acs_url="https://titanrag.enterprise.io/acs",
        attribute_mapping={"email": "email", "name": "name", "groups": "groups"},
        allow_unencrypted_assertions=True,
    )

    assertion = SAMLServiceProvider.process_saml_response(b64_response, config)
    assert assertion.email == "alice.doe@enterprise.com"
    assert assertion.full_name == "Alice Doe"
    assert "SecOps" in assertion.groups
    assert "Executive-Board" in assertion.groups
    assert assertion.session_index == "_sess_789"


def test_process_saml_response_expired():
    now = datetime.now(timezone.utc)
    issue_instant = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    not_before = (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    not_on_or_after = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    xml = MOCK_SAML_RESPONSE_XML.format(
        issue_instant=issue_instant,
        not_before=not_before,
        not_on_or_after=not_on_or_after,
    )
    b64_response = base64.b64encode(xml.encode("utf-8")).decode("ascii")

    config = SAMLConfiguration(
        idp_entity_id="https://idp.okta.com/exk123",
        idp_sso_url="https://idp.okta.com/app/sso",
        idp_x509_cert="MOCK_CERT",
        sp_entity_id="https://titanrag.enterprise.io/sp",
        sp_acs_url="https://titanrag.enterprise.io/acs",
        allow_unencrypted_assertions=False,
    )

    with pytest.raises(ValueError, match="expired"):
        SAMLServiceProvider.process_saml_response(b64_response, config)
