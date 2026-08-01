#!/usr/bin/env python3
"""
모바일 환경 보호 Hook — PreToolUse (Edit/Write)

테스트 환경이 없는 환경에서 고위험 파일 수정을 차단합니다.

[보호 대상]
- alembic/versions/  : DB 마이그레이션 (pytest로 검증 불가, 데이터 손실 위험)
- src/templates/     : HTML 템플릿 (렌더링 오류는 pytest 미감지)
- railway.toml       : 프로덕션 배포 설정
- alembic.ini        : Alembic 설정

[허용 조건]
- pytest, fastapi, sqlalchemy 가 import 가능한 환경 (make test 실행 가능)

[2026-05-02 fix — Phase 1+2 회고 P0 후속]
기존: subprocess 검증 시 sys.executable 사용 → Claude Code 가 hook 을 시스템
minimal python (/usr/bin/python3, pytest 미설치) 으로 호출 시 항상 차단. 그러나
사용자의 `make test` 는 PATH 의 python (/usr/local/bin/python = pyenv/conda/venv,
pytest 있음) 사용 → 환경 모순.

수정: shutil.which("python") → "python3" → sys.executable fallback. PATH 의 python
(=`make test` 가 사용하는 동일 python) 우선 검증 → false positive 차단 해소.

[2026-08-02 리팩터 — backlog R31]
(1) 행동 커버리지 0 시정: 모듈 레벨 실행 스크립트라 import 자체가 불가능해 차단 동작을
    검증하는 테스트가 리포 전체에 없었다 — 함수 분해 + __main__ 가드로 import 가능화.
    회귀 가드: tests/unit/hooks/test_check_edit_allowed.py.
(2) stdin 파싱 실패 = silent fail-open → **loud fail-open**: 훅 입력 계약이 바뀌면
    조용히 무보호가 되던 것을 additionalContext(Claude 도달 채널 — #1260 실증) +
    systemMessage 로 관측 가능하게 한다. deny(fail-closed)로 하지 않는 이유 = 파싱
    실패 시 모든 편집이 전 환경에서 차단되는 가드 자살(정책 17).
[2026-08-02 refactor — backlog R31]
(1) Zero behavioural coverage fixed: the module-level script could not be imported, so
    no test observed the deny path. Decomposed into functions under a __main__ guard.
(2) Silent fail-open on stdin parse failure becomes LOUD fail-open via additionalContext
    (the channel that actually reaches Claude, measured in #1260) + systemMessage.
    Not deny/fail-closed: that would block every edit in every environment on a contract
    drift — guard suicide (policy 17).
"""
import json
import re
import shutil
import subprocess  # nosec B404 — 후보 인터프리터 probe 전용 / interpreter probes only
import sys


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


# 보호 대상 패턴 / Protected path patterns.
PROTECTED_PATTERNS = [
    (r"alembic/versions/",  "DB 마이그레이션 파일 — 잘못된 수정은 데이터 손실로 이어집니다"),
    (r"src/templates/",     "HTML 템플릿 — 렌더링 오류와 변수명 오류는 pytest로 감지되지 않습니다"),
    (r"railway\.toml$",     "프로덕션 배포 설정 — 오류는 실제 배포 시점에만 드러납니다"),
    (r"alembic\.ini$",      "Alembic 설정 — 경로 오류는 앱 시작 시에만 드러납니다"),
]


def protected_reason(file_path: str) -> str | None:
    """보호 대상이면 사유 문자열, 아니면 None (백슬래시 경로 정규화 포함).
    The protection reason if the path is protected, else None (backslashes normalized)."""
    normalized = (file_path or "").replace("\\", "/")
    for pattern, reason in PROTECTED_PATTERNS:
        if re.search(pattern, normalized):
            return reason
    return None


def can_run_tests() -> bool:
    """후보 인터프리터를 **모두** 시도해 하나라도 테스트 스택 import 가능하면 True.
    Probe every candidate interpreter; True if ANY can import the test stack.

    [2026-06-22 fix — fall-through 버그 수정]
    기존: `shutil.which("python") or ... or sys.executable` 로 **첫 후보 1개만** 검증.
    harness 가 hook 을 PATH 상 패키지 없는 python (예: Windows Store WindowsApps 스텁)
    으로 호출하면 첫 후보에서 import 실패 → 나머지 capable 인터프리터를 시도하지 않고
    차단 (false positive). `make test` 가 정상인 로컬 PC 에서도 settings.html 등
    템플릿 수정이 막히는 사고 발생.
    Previously only the first existing candidate was probed; if the harness invoked the
    hook via a package-less python (e.g. the Windows Store stub on PATH), it denied
    without falling through to a capable interpreter. Now probe all candidates.
    """
    seen: set[str] = set()
    candidates = []
    for cand in (sys.executable, shutil.which("python"), shutil.which("python3"),
                 shutil.which("py")):
        if cand and cand.lower() not in seen:
            seen.add(cand.lower())
            candidates.append(cand)
    for py in candidates:
        try:
            result = subprocess.run(  # nosec B603 — 고정 인자 probe / fixed-args probe
                [py, "-c", "import pytest, fastapi, sqlalchemy"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                return True
        except Exception:  # pylint: disable=broad-except
            continue
    return False


def _deny_output(file_path: str, reason: str) -> dict:
    """보호 대상 차단 JSON — 기존 출력 형태 보존 (permissionDecision: deny).
    The deny JSON, shape-preserved from the pre-refactor hook."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"[모바일 환경 보호] 수정 차단: {file_path}\n\n"
                f"사유: {reason}\n\n"
                "이 파일은 자동화 테스트로 검증이 불가능한 고위험 영역입니다.\n"
                "수정하려면 아래 환경 중 하나에서 작업하세요:\n"
                "  - 로컬 PC: pip install -r requirements.txt → make test\n"
                "  - GitHub Codespaces: Code 버튼 → Codespaces → Create codespace"
            ),
        }
    }


def _parse_failure_output() -> dict:
    """stdin 파싱 실패 = **loud fail-open** (R31) — 관측 가능하되 차단하지 않는다.

    🔴 `permissionDecision` 키를 절대 싣지 않는다 — advisory 에 얹으면 사용자 권한 확인을
    건너뛸 수 있다(guards.md 훅 출력 채널 규칙). `additionalContext` 는 권한 결정과 독립이다.
    Loud fail-open on parse failure: observable, never blocking. Never attach a
    permissionDecision to an advisory — it can bypass the user's permission flow.
    """
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                "check_edit_allowed: stdin payload parse failed - protection cannot be "
                "evaluated (structural fail-open). The hook input contract may have "
                "drifted; verify PreToolUse payload shape (backlog R31)."
            ),
        },
        "systemMessage": (
            "check_edit_allowed: hook payload unreadable - mobile-env file protection "
            "did not run for this edit."
        ),
    }


def decide(payload: dict | None) -> dict | None:
    """훅 결정 — 출력할 JSON(dict) 또는 None(무출력 통과).
    The hook decision: a JSON dict to print, or None for a silent pass.

    🔴 비보호 경로는 probe(can_run_tests)를 **호출하지 않는다** — 모든 Edit/Write 마다
    서브프로세스 probe 를 돌리면 편집 지연이 상시 비용이 된다(보호 대상에서만 지불).
    Non-protected paths never trigger the probe: the subprocess cost is paid only when
    a protected file is actually being edited.
    """
    if payload is None:
        return _parse_failure_output()
    tool_input = payload.get("tool_input", {})
    file_path = (tool_input.get("file_path", "") or "").replace("\\", "/")
    if not file_path:
        return None
    reason = protected_reason(file_path)
    if reason is None:
        return None
    if can_run_tests():
        return None  # 테스트 환경 OK → 통과 / test env present: pass
    return _deny_output(file_path, reason)


def main() -> int:
    """stdin payload → decide → JSON 출력 (ensure_ascii — cp949 안전). 항상 exit 0.
    Read stdin, decide, print JSON (ensure_ascii for cp949 safety). Always exit 0."""
    _make_stdout_safe()
    try:
        payload = json.load(sys.stdin)
    except Exception:  # pylint: disable=broad-except
        payload = None
    # 🔴 파싱은 성공했지만 dict 가 아닌 payload(null·배열·수)는 계약 밖이다 — 구판은
    #    payload.get 에서 traceback(rc=1) 이었다(Grok `019fbe49` GROK-20260802-2).
    #    같은 loud fail-open 경로로 강등해 관측 가능하게 한다.
    # A successfully-parsed non-dict payload (null/array/number) is outside the contract;
    # the old code crashed on payload.get. Demote it to the same loud fail-open path.
    if not isinstance(payload, dict):
        payload = None
    output = decide(payload)
    if output is not None:
        print(json.dumps(output, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
