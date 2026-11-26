from app.core.redaction import REDACTED, Redactor

r = Redactor(extra_keys=["national_id"])


def test_sensitive_keys_masked_recursively():
    data = {
        "user": {"name": "a", "Password": "x", "profile": {"api-key": "k"}},
        "items": [{"access_token": "t"}, {"value": 1}],
        "national_id": "123",
    }
    out = r.redact(data)
    assert out["user"]["Password"] == REDACTED
    assert out["user"]["profile"]["api-key"] == REDACTED
    assert out["items"][0]["access_token"] == REDACTED
    assert out["items"][1]["value"] == 1
    assert out["national_id"] == REDACTED
    assert data["user"]["Password"] == "x"  # original untouched


def test_text_patterns():
    text = (
        "Authorization: Bearer abc123.xyz "
        "url=postgresql://user:s3cret@host/db "
        "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig_part "
        'payload {"password": "p@ss", "token": "tok"} '
        "card 4111 1111 1111 1111 "
        "mail john.doe@example.com"
    )
    out = r.redact_text(text)
    for secret in ("abc123.xyz", "s3cret", "eyJhbGciOiJIUzI1NiJ9", "p@ss", "tok\"", "4111 1111"):
        assert secret not in out
    assert "postgresql://user:[REDACTED]@host/db" in out
    assert "[REDACTED]-1111" in out
    assert "j***@example.com" in out


def test_non_card_numbers_are_kept():
    # 13-digit millisecond timestamp, fails the Luhn check
    assert r.redact_text("ts=1732636800123") == "ts=1732636800123"


def test_email_masking_can_be_disabled():
    assert Redactor(redact_emails=False).redact_text("a@b.io") == "a@b.io"
