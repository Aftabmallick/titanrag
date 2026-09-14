from titan_workers.pipeline.privacy.presidio_redactor import PIIRedactor


def test_pii_redactor_replace_mode():
    redactor = PIIRedactor(default_mode="REPLACE")
    raw_text = "Please contact Alice at alice@example.com or phone 555-123-4567. SSN is 123-45-6789."
    redacted, entities = redactor.redact(raw_text)

    assert "[EMAIL_ADDRESS]" in redacted
    assert "alice@example.com" not in redacted
    assert "[PHONE_NUMBER]" in redacted
    assert "555-123-4567" not in redacted
    assert "[US_SSN]" in redacted
    assert "123-45-6789" not in redacted
    assert len(entities) == 3


def test_pii_redactor_hash_mode():
    redactor = PIIRedactor(default_mode="HASH")
    raw_text = "Send credentials to bob@secure.org immediately."
    redacted, entities = redactor.redact(raw_text)

    assert "[HASH:" in redacted
    assert "bob@secure.org" not in redacted


def test_pii_redactor_mask_mode():
    redactor = PIIRedactor(default_mode="MASK")
    raw_text = "Contact charlie@domain.com now."
    redacted, entities = redactor.redact(raw_text)

    assert "c***@domain.com" in redacted
    assert "charlie@domain.com" not in redacted


def test_pii_redactor_off_mode():
    redactor = PIIRedactor(default_mode="OFF")
    raw_text = "Sensitive data: dave@company.com with SSN 987-65-4321."
    redacted, entities = redactor.redact(raw_text)

    assert redacted == raw_text
    assert len(entities) == 0
