"""토큰 암호화/복호화 유틸리티 — Fernet 대칭 암호화.
Token encryption/decryption utility — Fernet symmetric encryption.

TOKEN_ENCRYPTION_KEY 환경변수가 설정된 경우 Fernet으로 암호화/복호화.
미설정 시 no-op(평문 반환) — 개발/테스트 환경 하위 호환.

키 생성 방법::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# settings가 아직 초기화되지 않은 시점에서 import될 수 있으므로 지연 로딩
# Lazy-loaded: this module may be imported before settings is initialized.
_fernet: "Fernet | None | bool" = False  # False = 미초기화 sentinel  # pylint: disable=invalid-name


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
        # 저장값을 그대로 돌려준다 — 암호화 도입 전 평문 토큰이면 그대로 쓰이고, 옛 키로 암호화된 토큰(키 교체 뒤
        #   재로그인 안 함)이면 GitHub 가 401 로 거절한다(실패로 닫힌다).
        # 🔴 빈 값으로 바꾸지 않는다 — 토큰을 쓰는 경로(분석 · 웹훅 이슈 닫기 · 머지 재시도 · 보안 폴링)가 모두
        #   «소유자 토큰이 비면 운영자 토큰(앱 전역)» 꼴이라, 빈 값이면 다른 사용자의 리포에 운영자 신원으로 접근한다
        #   (회고 원장 R-16 · `tests/unit/test_undecryptable_token_stays_owner_bound.py`).
        # Return the stored value unchanged: legacy plaintext keeps working, a previous-key token fails at GitHub (401).
        # Never return "" here: every caller falls back to the operator's app-wide token when the owner token is empty.
        logger.warning(
            "Stored token could not be decrypted — kept as-is (legacy plaintext, or encrypted with a previous "
            "key: the owner must log in again; the app-wide token is not used for that owner's repos)")
        return ciphertext
