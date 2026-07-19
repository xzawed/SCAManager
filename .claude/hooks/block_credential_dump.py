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


def decide(command):
    """차단 사유를 반환하거나, 통과면 None.
    Return a denial reason, or None when the command may proceed."""
    if not command:
        return None
    if any(pattern.search(command) for pattern in _ALLOWED):
        return None
    for pattern, reason in _BLOCKED:
        if pattern.search(command):
            return reason
    return None


def main():
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
