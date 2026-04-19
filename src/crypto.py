"""토큰 암호화/복호화 유틸리티 — Fernet 대칭 암호화.

TOKEN_ENCRYPTION_KEY 환경변수가 설정된 경우 Fernet으로 암호화/복호화.
미설정 시 no-op(평문 반환) — 개발/테스트 환경 하위 호환.

키 생성 방법::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# settings가 아직 초기화되지 않은 시점에서 import될 수 있으므로 지연 로딩
_fernet: "Fernet | None | bool" = False  # False = 미초기화 sentinel


def _get_fernet() -> "Fernet | None":
    """TOKEN_ENCRYPTION_KEY로 Fernet 인스턴스를 반환. 키 없으면 None."""
    global _fernet  # pylint: disable=global-statement
    if _fernet is not False:
        return _fernet  # type: ignore[return-value]
    try:
        from src.config import settings  # pylint: disable=import-outside-toplevel
        key = settings.token_encryption_key
        if not key:
            _fernet = None
        else:
            _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, ImportError, OSError, AttributeError, TypeError):
        _fernet = None
    return _fernet  # type: ignore[return-value]


def encrypt_token(plaintext: str) -> str:
    """토큰을 암호화하여 반환. 키 미설정 시 원문 그대로 반환."""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """암호화된 토큰을 복호화하여 반환. 키 미설정 또는 평문 저장값이면 원문 반환."""
    if not ciphertext:
        return ciphertext
    f = _get_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError):
        # 암호화 키 도입 전 평문 저장된 레거시 토큰 — 그대로 반환
        logger.warning("Token decryption failed — returning as plaintext (legacy token?)")
        return ciphertext
