"""상수 시간 문자열 비교 — hmac.compare_digest 의 비-ASCII str TypeError 방지.
Constant-time string compare that avoids hmac.compare_digest's non-ASCII TypeError.

hmac.compare_digest(a, b) 는 a 또는 b 가 비-ASCII 문자를 포함한 str 일 때 TypeError
("comparing strings with non-ASCII characters is not supported") 를 던진다. webhook
서명/토큰·API 키 등 공개 인증 엔드포인트에서 공격자가 비-ASCII 헤더를 보내면 401/403
대신 uncaught 500 이 발생한다(Task 9 감사 — 8 호출처 class 결함). UTF-8 bytes 로 인코딩
후 비교해 TypeError 를 차단하면서 상수 시간 비교를 유지한다 (불일치 시 False = 인증 실패).
hmac.compare_digest raises TypeError on non-ASCII str inputs; on public auth endpoints a
non-ASCII header would yield an uncaught 500 instead of 401/403. Encoding both sides to UTF-8
bytes first removes the TypeError while keeping the comparison constant-time.
"""
import hmac


def secure_str_compare(a: str | None, b: str | None) -> bool:
    """두 문자열을 상수 시간으로 비교한다. None 은 ""로, UTF-8 bytes 로 비교(비-ASCII 안전).
    Compare two strings in constant time (None → "", UTF-8 bytes — non-ASCII safe).
    """
    return hmac.compare_digest((a or "").encode("utf-8"), (b or "").encode("utf-8"))
