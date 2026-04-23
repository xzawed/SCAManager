"""로그 인젝션 방어 헬퍼 — 사용자 입력을 로깅 전 sanitize.

CR/LF/TAB 등 로그 라인 조작에 사용될 수 있는 제어 문자를 제거하고 길이를
제한한다. `%r` 포맷만으로는 SonarCloud taint analysis 가 sanitize 로 인정하지
않아 명시적 함수를 거치도록 한다.
"""

_UNSAFE_CHARS = {"\r": "", "\n": "", "\t": " ", "\x00": ""}
_MAX_LOG_LEN = 200


def sanitize_for_log(value: object, max_len: int = _MAX_LOG_LEN) -> str:
    """사용자 입력을 로그 안전 문자열로 변환한다.

    - CR/LF 제거 (로그 라인 삽입 방지)
    - TAB → 공백, NUL 제거
    - 최대 길이 max_len 으로 절단
    """
    if value is None:
        return ""
    text = str(value)
    for bad, good in _UNSAFE_CHARS.items():
        text = text.replace(bad, good)
    if len(text) > max_len:
        text = text[:max_len] + "…"
    return text
