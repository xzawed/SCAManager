"""Bash credential 덤프 차단 훅 — 정책 12 위반의 **기계 집행면**.
PreToolUse hook that blocks Bash commands which dump credential *values* to stdout.

🔴 왜 존재하는가 (2026-07-19 회고 P0): Claude 가 정책 12 를 위반해 credential 을 대화
기록에 평문 출력했다. 의도는 변수 **이름만** 보는 것이었으나 grep 패턴이 값까지 매칭했다:

    railway variables --service SCAManager --kv | grep -iE "SCHEDULER|ENVIRONMENT|LOG_LEVEL|CRON"
                                                                                       ^^^^
                                                       INTERNAL_CRON_API_KEY 의 **값**까지 출력

그 뒤 재발 방지책으로 남긴 것은 **산문뿐**이었다(owed 원장 표 셀 + 로컬 메모리). 2차 회고
(168 에이전트)가 이를 P0 로 확정했다 — "credential 유출 벡터(Bash stdout)에 훅 커버리지 0",
"인지 의존 산문 5회차". 이 파일이 그 시정이다.
The recurrence-prevention rule previously existed only as prose; this hook is the enforcement.

🔴 설계 원칙 — **대안 없는 차단은 훅을 무력화시킨다.** 차단 시 반드시 안전한 관용구를
안내한다(이름만 추출 → `cut -d= -f1`). 그래야 다음 세션이 훅을 우회하지 않는다.
Blocking without an alternative gets hooks disabled; every denial teaches the safe idiom.
"""
import json
import re
import sys

# ── credential **값**을 stdout 으로 쏟는 명령 ─────────────────────────────
# Commands that dump credential *values* to stdout.
# 🔴 `.env\b(?!\.)` 부정 lookahead — 커밋된 템플릿 `.env.example` 은 값이 없고
#    CLAUDE.md 핵심 명령(`cp .env.example .env`)에 등장하므로 차단 대상이 아니다.
#    Negative lookahead so the committed, value-free .env.example template stays usable.
_BLOCKED = (
    (re.compile(r"\brailway\s+variables\b"), "railway variables — 전체 env 값 덤프"),
    (re.compile(r"\bprintenv\b"), "printenv — 프로세스 env 값 덤프"),
    (re.compile(r"\b(?:cat|type)\b[^|&;]*\.env\b(?!\.)"), "cat/type .env — 시크릿 파일 직접 열람"),
)

# ── 예외 — 이 관용구가 있으면 값이 노출되지 않는다 ────────────────────────
# Exceptions: with these present the command cannot surface a value.
_ALLOWED = (
    # 이름만 추출 (따옴표 변형 포함) / name-only extraction, quote variants included
    re.compile(r"""\bcut\s+-d\s*['"]?=['"]?\s+-f\s*1\b"""),
    # 쓰기 작업은 값을 출력하지 않는다 / writes do not print values
    re.compile(r"\brailway\s+variables\b[^|&;]*--set\b"),
)

_SAFE_IDIOM = 'railway variables --kv | cut -d= -f1 | grep -i CRON'


# ── 세그먼트 분해 경계 (2026-07-26 5+1 회고 P0 — 복합 명령 fail-open 봉인) ──
# 🔴 **단일 `|`(파이프)는 분해하지 않는다.** 파이프라인은 하류 필터가 상류 덤프를 실제로
# 중화하므로(`railway variables --kv | cut -d= -f1`) 판정 단위가 하나다. 반면 `;`·`&&`·`||`·`&`
# 로 이어진 명령은 서로를 중화하지 못한다 — 안전한 쪽이 위험한 쪽을 가려주면 안 된다.
# 이 비대칭이 분해 경계의 근거다. `[;&|]{1,2}` 처럼 파이프까지 쪼개면 훅이 **자기가 가르치는
# 안전 관용구**(_SAFE_IDIOM)를 차단해 곧 비활성화된다 — 회귀 가드가 그 대조군을 고정한다.
# 🔴 Do NOT split single `|`: a pipeline's downstream filter genuinely neutralizes the upstream
# dump, so it is one verdict unit. `;`/`&&`/`||`/`&` chain independent commands that cannot
# neutralize one another — a safe one must never whitelist a dangerous sibling.
_SEPARATORS = re.compile(r"&&|\|\||;|\n|&")


def _decide_segment(segment):
    """단일 명령(파이프라인 포함)에 대한 판정 — 예외가 그 세그먼트 안에서만 유효하다.
    Verdict for one command (pipeline included); an exception only covers its own segment."""
    if any(pattern.search(segment) for pattern in _ALLOWED):
        return None
    for pattern, reason in _BLOCKED:
        if pattern.search(segment):
            return reason
    return None


def decide(command):
    """차단 사유를 반환하거나, 통과면 None.
    Return a denial reason, or None when the command may proceed.

    🔴 세그먼트 **하나라도** 차단 대상이면 명령 전체를 deny 한다(fail-closed). 이전 구현은
    `_ALLOWED` 를 명령 문자열 **전체**에 `_BLOCKED` 보다 먼저 적용해, 안전한 세그먼트 하나가
    명령 전체를 화이트리스트했다 — 가장 자연스러운 우회가 `_SAFE_IDIOM` 을 앞에 붙이는 것이라
    ('이름 먼저 보고 값도 하나 확인' 흐름) 실사용 형태 그대로 뚫렸다.
    🔴 Deny if ANY segment is blocked (fail-closed).
    """
    if not command:
        return None
    for segment in _SEPARATORS.split(command):
        reason = _decide_segment(segment)
        if reason:
            return reason
    return None


def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지/한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji/Korean print crash on Windows (UTF-8, replace on miss).

    현재 출력은 `ensure_ascii=True` JSON 뿐이라 크래시 경로가 없지만, 차단 사유 문구를
    한 줄 추가하는 순간 훅이 죽는다 — 그 형태가 실제로 doc_review_gate.py 를 죽였다.
    No crash path today (ASCII-only JSON), but one Korean reason string would introduce one —
    which is exactly what killed doc_review_gate.py.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / captured streams: ignore


def main():
    _make_stdout_safe()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # 입력이 깨져도 작업을 막지 않는다 — 이 훅은 advisory 성격의 안전망이다.
        # Never block on malformed input; this hook is a safety net, not a gate on correctness.
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input") or {}).get("command") or ""
    reason = decide(command)
    if reason is None:
        return 0

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "[credential 보호] Bash 실행 차단 (정책 12)\n\n"
                f"사유: {reason}\n\n"
                "이 명령은 credential **값**을 대화 기록에 평문으로 남깁니다.\n"
                "2026-07-19 에 실제로 발생한 사고입니다 — grep 패턴이 변수 이름뿐 아니라\n"
                "값까지 매칭해 API 키가 그대로 출력됐습니다.\n\n"
                "이름만 필요하면 값을 먼저 잘라내세요:\n"
                f"  {_SAFE_IDIOM}\n\n"
                "값이 정말 필요하면 사용자에게 요청하세요 (정책 12: 사전 승인 의무)."
            ),
        }
    }
    # ensure_ascii=True — Windows cp949 콘솔에서 무음 실패하지 않도록.
    # ensure_ascii keeps the payload decodable on Windows cp949 consoles.
    print(json.dumps(output, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
