import hashlib
import hmac
from src.webhook.validator import verify_github_signature


def _make_sig(payload: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def test_valid_signature():
    payload = b'{"action": "opened"}'
    secret = "my_secret"
    sig = _make_sig(payload, secret)
    assert verify_github_signature(payload, sig, secret) is True


def test_invalid_signature():
    payload = b'{"action": "opened"}'
    assert verify_github_signature(payload, "sha256=wrongvalue", "my_secret") is False


def test_missing_signature():
    assert verify_github_signature(b"payload", None, "secret") is False


def test_wrong_prefix():
    assert verify_github_signature(b"payload", "md5=abc123", "secret") is False


def test_tampered_payload():
    secret = "my_secret"
    original = b'{"action": "opened"}'
    sig = _make_sig(original, secret)
    tampered = b'{"action": "closed"}'
    assert verify_github_signature(tampered, sig, secret) is False
