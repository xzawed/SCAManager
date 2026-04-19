"""HMAC-SHA256 GitHub webhook signature verification."""
import hashlib
import hmac


def verify_github_signature(
    payload: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    """HMAC-SHA256으로 GitHub Webhook 서명을 검증한다. 서명 불일치 또는 헤더 없으면 False."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
