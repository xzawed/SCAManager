"""로그 인젝션 방어 헬퍼 — 사용자 입력을 로깅 전 sanitize.

CR/LF/TAB 등 로그 라인 조작에 사용될 수 있는 제어 문자를 제거하고 길이를
제한한다. `%r` 포맷만으로는 SonarCloud taint analysis 가 sanitize 로 인정하지
않아 명시적 함수를 거치도록 한다.
"""
import re

_UNSAFE_CHARS = {"\r": "", "\n": "", "\t": " ", "\x00": ""}
_MAX_LOG_LEN = 200


def sanitize_for_log(value: object, max_len: int = _MAX_LOG_LEN) -> str:
    """사용자 입력을 로그 안전 문자열로 변환한다.

    - CR/LF 제거 (로그 라인 삽입 방지)
    - TAB → 공백, NUL 제거
    - repr 기반 이스케이프 적용(제어문자 가시화)
    - 최대 길이 max_len 으로 절단
    """
    if value is None:
        return ""
    text = str(value)
    for bad, good in _UNSAFE_CHARS.items():
        text = text.replace(bad, good)
    text = repr(text)[1:-1]
    if len(text) > max_len:
        text = text[:max_len] + "…"
    return text


# ── 리포 전체이름 형태 검증 (CodeQL sanitizer) ────────────────────────────
#
# 🔴 CodeQL 은 「접근 가능 목록에 있는가」 같은 **의미 검증**을 sanitizer 로 인식하지
#    못한다. URL 경로·리다이렉트에 들어가는 값은 **형태**를 명시적으로 좁혀야
#    py/url-redirection · py/partial-ssrf 의 taint 가 끊긴다.
#    (자초 CodeQL 재발 3회의 근본 — 게이트가 note 까지 잡는 이유다.)
# CodeQL does not treat membership checks as sanitizers; narrow the *shape* explicitly.
# 🔴 유계 반복 `{0,99}` — 무제한 `*` 두 개는 겹치는 문자군에서 다항 백트래킹을 만든다
#    (CodeQL py/polynomial-redos). GitHub 의 owner·repo 는 각각 100자 이하다.
# Bounded repetition: two unbounded `*` over overlapping classes backtrack polynomially.
_REPO_FULL_NAME = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}/[A-Za-z0-9][A-Za-z0-9._-]{0,99}"
)


def safe_repo_full_name(value: object) -> str | None:
    """`owner/repo` 형태면 그 값을, 아니면 `None`.

    🔴 `None` 은 「비어 있다」가 아니라 **「믿을 수 없다」** 다 — 호출부는 URL 을
    만들지 않아야 한다. 슬래시가 2개 이상이거나 `@`·`:`·공백이 있으면 거부한다
    (`https://evil@host` 류 호스트 주입 차단).
    Returns the value only when it matches `owner/repo`; None means "do not build a URL".
    """
    if not isinstance(value, str):
        return None
    return value if _REPO_FULL_NAME.fullmatch(value) else None
