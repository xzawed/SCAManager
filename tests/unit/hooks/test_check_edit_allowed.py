"""check_edit_allowed.py (모바일 환경 보호 훅) 행동 계약 테스트 — backlog R31 TDD 선행 (RED).
Behaviour-contract tests for check_edit_allowed.py (mobile-env protection hook) — backlog R31, TDD-first (RED).

## 왜 이 파일이 존재하나 (backlog R31)
## Why this file exists (backlog R31)
- 행동 커버리지 0 — 이 훅의 **차단 동작**을 검증하는 테스트가 리포 전체에 없었다.
- Zero behavioural coverage: no test in the repo verifies the hook's deny behaviour.
- stdin 파싱 실패가 silent fail-open (`.claude/hooks/check_edit_allowed.py` `except Exception: sys.exit(0)`)
  — 훅 입력 계약이 바뀌면 아무 신호 없이 보호가 통째로 꺼진다 (observer-lie 클래스).
- Silent fail-open on stdin parse failure: if the hook input contract drifts, protection
  silently disappears (the observer-lie class).

## 구현될 계약 (리팩터 전 = 신규 테스트 대부분 RED 가 정상)
## The contract to be implemented (pre-refactor, most new tests are expected RED)
- `protected_reason(file_path) -> str | None` — 보호 사유 (백슬래시 경로 정규화 포함).
- `protected_reason(file_path) -> str | None` — reason string, with backslash normalization.
- `can_run_tests() -> bool` — 후보 인터프리터 전수 probe (기존 동작 보존).
- `can_run_tests() -> bool` — probe every candidate interpreter (behaviour preserved).
- `decide(payload) -> dict | None` — 훅 출력 JSON(dict) 또는 None(무출력 통과).
- `decide(payload) -> dict | None` — hook output JSON (dict) or None (silent pass).
- `main() -> int` — stdin → decide → print(json.dumps(..., ensure_ascii=True)) → 0.
  `if __name__ == "__main__"` 가드로 이동 — 이것이 import 가능해지는 조건.
  Moves execution under the `__main__` guard — the precondition for importability.

## 로드 전략
## Load strategy
- `importlib.util.spec_from_file_location` 으로 직접 로드 (패키지 아님 — test_doc_review_gate.py 의
  sys.path 패턴은 모듈 레벨 실행 스크립트에는 collection 자체를 죽이므로 쓸 수 없다).
- Load directly via spec_from_file_location (not a package — the sys.path pattern used by
  test_doc_review_gate.py would kill collection for a module-level-executing script).
- 리팩터 전에는 모듈 레벨 코드가 stdin 을 읽고 `sys.exit(0)` 하므로, stdin 을
  `io.StringIO("{}")` 로 방어하고 SystemExit 를 삼켜 **부분 로드**를 돌려준다 —
  함수 부재(AttributeError)로 각 테스트가 개별 RED 가 된다 (collection 전멸 방지).
- Pre-refactor the module-level code reads stdin and exits; we feed "{}" and swallow
  SystemExit so each test turns RED individually via missing attributes.

## 단언 규율 (guards.md)
## Assertion discipline (guards.md)
- 🔴 텍스트 in 단언이 아니라 **JSON 형태를 파싱해 dict 키 접근**으로 단언한다 —
  텍스트 단언은 채널/형태 회귀를 못 잡는다.
- Assert by parsing the JSON shape and accessing dict keys, never by substring-in-text —
  text assertions cannot catch channel/shape regressions.
"""
import importlib.util
import io
import json
import subprocess  # nosec B404 — 리포 자신의 훅 스크립트만 실행한다 / runs only this repo's own hook script
import sys
from pathlib import Path

import pytest

from tests.unit.scripts._wiring_shape import surface_invokes

# 리포 루트 + 훅 실파일 경로 — parents[3] = tests/unit/hooks 기준 리포 루트.
# Repo root + the real hook file path — parents[3] from tests/unit/hooks.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_HOOK_PATH = _REPO_ROOT / ".claude" / "hooks" / "check_edit_allowed.py"


def _load_hook(monkeypatch):
    """훅 모듈을 파일 경로로 직접 로드 — 리팩터 전 모듈 레벨 stdin 읽기/exit 방어 포함.
    Load the hook module from its file path, defending against the pre-refactor
    module-level stdin read / exit.
    """
    assert _HOOK_PATH.exists(), f"훅 파일이 없다 — 경로 drift: {_HOOK_PATH}"
    # 리팩터 전 모듈 레벨 `json.load(sys.stdin)` 이 파이프를 기다리지 않도록 빈 payload 주입.
    # Feed an empty payload so the pre-refactor module-level json.load(sys.stdin) cannot hang.
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    spec = importlib.util.spec_from_file_location("check_edit_allowed_under_test", _HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit:
        # 리팩터 전: 모듈 레벨 코드가 sys.exit(0) — 부분 로드를 돌려주면 함수 부재로
        # 각 테스트가 개별 RED 가 된다 (여기서 죽이면 collection 전체가 죽는다).
        # Pre-refactor: module-level sys.exit(0). Return the partial module so each test
        # goes RED individually instead of killing collection.
        pass
    return module


@pytest.fixture(name="hook")
def hook_fixture(monkeypatch):
    """테스트마다 새 모듈 인스턴스 — 테스트 간 monkeypatch 오염 차단.
    A fresh module instance per test — no monkeypatch leakage between tests."""
    return _load_hook(monkeypatch)


# ── decide(): 보호 대상 차단 (deny JSON 형태) ─────────────────────────────
# decide(): protected paths are denied (deny JSON shape)

_PROTECTED_PATHS = [
    "alembic/versions/0001_x.py",
    "src/templates/settings.html",
    "railway.toml",
    "alembic.ini",
    # Windows 백슬래시 형 — :56 replace("\\", "/") 정규화 동작 보존 검증.
    # Windows backslash form — preserves the :56 replace("\\", "/") normalization.
    "alembic\\versions\\0001_x.py",
]


@pytest.mark.parametrize("path", _PROTECTED_PATHS)
def test_deny_json_shape_for_each_protected_path(hook, monkeypatch, path):
    # 보호 대상 + 테스트 환경 없음 → 기존과 동일한 deny JSON (dict 키 접근으로 단언).
    # Protected path + no test env → the same deny JSON as today (asserted via dict keys).
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    result = hook.decide({"tool_input": {"file_path": path}})

    assert result is not None, "보호 대상인데 무출력 통과 — 차단이 사라졌다"
    out = result["hookSpecificOutput"]
    # 🔴 텍스트 in 이 아니라 dict 키 접근 — 형태 회귀(채널 변경)를 잡는다 (guards.md).
    # Dict-key access, not substring-in-text — catches shape/channel regressions (guards.md).
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "deny"
    # 사유에는 정규화된 경로가 포함돼야 한다 (Windows 형도 슬래시로 정규화).
    # The reason must contain the normalized path (backslash form normalized to slashes).
    normalized = path.replace("\\", "/")
    assert normalized in out["permissionDecisionReason"]
    # protected_reason 계약 — 백슬래시 형 포함 사유 문자열 반환 + 그 사유가 deny 본문에 실린다.
    # protected_reason contract — returns a reason (backslash form included) carried in the deny body.
    reason = hook.protected_reason(path)
    assert reason, f"protected_reason 이 보호 대상을 놓쳤다: {path}"
    assert reason in out["permissionDecisionReason"]


def test_non_protected_path_passes_silently(hook, monkeypatch):
    # 비보호 경로 → None + 보호 대상이 아니면 probe(can_run_tests) 자체를 호출하지 않는다.
    # Non-protected path → None, and the probe (can_run_tests) must not even be called.
    def _boom():
        raise AssertionError("비보호 경로에서 can_run_tests 가 호출됐다 — probe 는 보호 대상에서만")

    monkeypatch.setattr(hook, "can_run_tests", _boom)
    assert hook.decide({"tool_input": {"file_path": "src/api/routes.py"}}) is None
    # file_path 부재도 무출력 통과 계약이다.
    # A missing file_path also passes silently by contract.
    assert hook.decide({"tool_input": {}}) is None
    assert hook.decide({}) is None


def test_protected_path_allowed_when_test_env_exists(hook, monkeypatch):
    # 보호 대상이라도 테스트 환경이 있으면(can_run_tests True) 무출력 통과.
    # Even a protected path passes silently when the test env exists (can_run_tests True).
    monkeypatch.setattr(hook, "can_run_tests", lambda: True)
    assert hook.decide({"tool_input": {"file_path": "src/templates/settings.html"}}) is None


@pytest.mark.parametrize(
    "path",
    [
        "src/static/app.css",
        "tests/unit/test_x.py",
        # 끝 앵커 $ 라 비매칭 — `railway\.toml$` 는 접미사가 붙으면 매칭되지 않는다.
        # Not matched due to the end anchor — `railway\.toml$` rejects suffixed names.
        "railway.toml.bak",
        "myalembic.ini.md",
    ],
)
def test_similar_but_unprotected_paths_are_not_blocked(hook, monkeypatch, path):
    # 보호 패턴과 유사하지만 비보호인 경로는 차단하지 않는다 (전부 None).
    # Paths merely similar to protected patterns are not blocked (all None).
    #
    # 🔴 주의: `docs/alembic/versions_guide.md` 는 대조군이 아니다 — 실제 정규식이
    # `alembic/versions/` substring 매칭이라 그 경로는 **실제로 차단된다** (기존 동작 보존).
    # Note: `docs/alembic/versions_guide.md` is NOT a control here — the real regex is a
    # substring match on `alembic/versions/`, so that path IS actually blocked (preserved).
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    assert hook.decide({"tool_input": {"file_path": path}}) is None


# ── decide(): stdin 파싱 실패 = loud fail-open ────────────────────────────
# decide(): stdin parse failure = loud fail-open


def test_parse_failure_is_loud_but_not_blocking(hook):
    """silent fail-open(R31) → loud fail-open. deny(fail-closed)로 하지 않는 이유 =
    파싱 실패 시 모든 편집이 전 환경에서 차단되는 가드 자살(정책 17).

    Silent fail-open (R31) becomes loud fail-open. We do NOT go deny/fail-closed because a
    parse failure would then block every edit in every environment — guard suicide (policy 17).
    """
    # 파싱 실패(payload None) → advisory JSON: Claude 채널 + 사용자 채널 + 권한 결정 없음.
    # Parse failure (payload None) → advisory JSON: Claude channel + user channel, no permission decision.
    result = hook.decide(None)

    assert result is not None, "파싱 실패가 여전히 silent — R31 미시정"
    out = result["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    # Claude 가 실제로 보는 유일한 PreToolUse 채널 — 파싱 실패 + 보호 판정 불가 안내가 실려야 한다.
    # The only PreToolUse channel Claude actually sees — must carry the parse-failure notice.
    assert isinstance(out["additionalContext"], str) and out["additionalContext"].strip()
    # 사용자 터미널 채널 — Claude 채널과 다른 대상이라 별도 존재해야 한다.
    # The user's terminal channel — a different audience, must exist separately.
    assert isinstance(result["systemMessage"], str) and result["systemMessage"].strip()
    # 🔴 advisory 에 permissionDecision 을 얹으면 권한 확인 우회 위험 — 절대 없음 (guards.md).
    # An advisory must never carry permissionDecision — it can bypass the permission flow (guards.md).
    assert "permissionDecision" not in result["hookSpecificOutput"]
    assert "permissionDecisionReason" not in result["hookSpecificOutput"]


# ── 실행 축: subprocess 종단 검증 (import 축과 별개) ──────────────────────
# Execution axis: end-to-end subprocess verification (separate from the import axis)


def _run_hook(stdin_text: str) -> subprocess.CompletedProcess:
    """훅 스크립트를 실제 인터프리터로 실행 — 출력 계약은 ensure_ascii JSON 이라 인코딩 안전.
    Run the hook script with a real interpreter — output contract is ensure_ascii JSON."""
    return subprocess.run(  # nosec B603 — 고정 인자, 리포 자신의 스크립트 / fixed args, own script
        [sys.executable, str(_HOOK_PATH)],
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


def test_end_to_end_subprocess_parse_failure():
    # 실행 축 — stdin 이 JSON 이 아니어도 exit 0 + loud JSON(additionalContext) 을 낸다.
    # Execution axis — non-JSON stdin still exits 0 but emits the loud JSON (additionalContext).
    # 리팩터 전 현 구현: exit 0 + 빈 stdout (silent fail-open) → 아래 json.loads 에서 RED.
    # Pre-refactor: exit 0 with empty stdout (silent fail-open) → RED at json.loads below.
    proc = _run_hook("not json")

    assert proc.returncode == 0, f"advisory 훅이 비-0 종료 — stderr: {proc.stderr!r}"
    payload = json.loads(proc.stdout)
    out = payload["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert isinstance(out["additionalContext"], str) and out["additionalContext"].strip()
    assert isinstance(payload["systemMessage"], str) and payload["systemMessage"].strip()
    assert "permissionDecision" not in out
    # main() 출력 계약 = ensure_ascii=True — Windows cp949 stdout 에서 훅이 죽지 않는 조건.
    # main() output contract = ensure_ascii=True — keeps the hook alive on cp949 stdout.
    assert proc.stdout.isascii(), "ensure_ascii 누락 — cp949 에서 훅이 죽는다"


def test_end_to_end_subprocess_non_protected_allow():
    # 실행 축 — 비보호 경로는 exit 0 + 무출력 (stdout 공백/빈 문자열) 으로 통과한다.
    # Execution axis — a non-protected path passes with exit 0 and empty/whitespace stdout.
    proc = _run_hook(json.dumps({"tool_input": {"file_path": "src/api/x.py"}}))

    assert proc.returncode == 0, f"비보호 경로에서 비-0 종료 — stderr: {proc.stderr!r}"
    assert proc.stdout.strip() == "", f"비보호 경로에서 출력이 나왔다: {proc.stdout!r}"


# ── 배선 축: settings.json 이 이 훅을 실제로 실행하는가 ────────────────────
# Wiring axis: does settings.json actually invoke this hook?


def test_hook_is_wired_in_settings():
    # 정의 ≠ 배선 — settings.json 원문이 이 훅을 **실제 실행**하는지 술어로 단언한다.
    # Definition ≠ wiring — assert via the predicate that settings.json actually runs the hook.
    # 🔴 substring 금지: `echo .claude/hooks/check_edit_allowed.py` 는 통과하면 안 된다 (guards.md).
    # No substring test: `echo .claude/hooks/check_edit_allowed.py` must not pass (guards.md).
    settings_text = (_REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert surface_invokes(settings_text, ".claude/hooks/check_edit_allowed.py"), (
        "settings.json 이 check_edit_allowed.py 를 실행하지 않는다 — 보호 훅 배선 소실"
    )


# ── main(): stdout 출력 계약 — Grok claim-review 019fbe49 적발 (GROK-20260802-1/2) ──
# main(): the stdout output contract — Grok claim-review 019fbe49 findings (GROK-20260802-1/2)


def test_main_prints_deny_json_for_protected_path(hook, monkeypatch, capsys):
    """main() 이 deny JSON 을 **stdout 으로 실제 출력**하는 경로를 고정한다 (GROK-20260802-1).

    기존 15건은 decide() 단위까지만 고정 — main() 의 출력 분기(print)를 지워도 전부 green
    인 채 런타임 보호만 조용히 소멸한다(silent-disable). 이 테스트가 유일한 stdout 관측축이다.
    🔴 뮤테이션: main 의 print 분기 제거 시 이 테스트만 red — 현행도 통과할 수 있으나
    (main 이 이미 출력한다) 이 테스트의 존재 이유는 red 가능성 확보다.

    Freezes the path where main() actually PRINTS the deny JSON to stdout (GROK-20260802-1).
    The existing 15 tests stop at decide(): deleting main()'s print branch keeps them all
    green while runtime protection silently disappears (silent-disable). Mutation: removing
    main()'s print branch turns only this test red — it may pass today (main already
    prints), but red-capability is this test's reason to exist.
    """
    # 테스트 환경 없음 강제 + 보호 대상 payload 를 stdin 으로 주입.
    # Force "no test env" and feed a protected-path payload via stdin.
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps({"tool_input": {"file_path": "src/templates/settings.html"}})),
    )

    assert hook.main() == 0

    # 🔴 텍스트 in 이 아니라 stdout JSON 을 파싱해 dict 키 접근으로 단언 (guards.md).
    # Parse the stdout JSON and assert via dict-key access, never substring-in-text (guards.md).
    printed = json.loads(capsys.readouterr().out)
    out = printed["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "deny"
    # 차단 사유에는 대상 경로가 실려야 한다 — 어떤 파일이 막혔는지 사용자가 봐야 한다.
    # The deny reason must carry the target path — the user must see which file was blocked.
    assert "src/templates/settings.html" in out["permissionDecisionReason"]


def test_main_silent_for_non_protected(hook, monkeypatch, capsys):
    """비보호 경로에서 main() 은 stdout 에 아무것도 내지 않는다 — deny 출력축의 대조군.
    On a non-protected path main() prints nothing to stdout — the control group for the
    deny output axis.
    """
    # can_run_tests False 로 고정 — 위 deny 테스트와 유일한 차이가 '경로'가 되도록 한다
    # (환경 덕분에 통과하는 spurious-pass 차단 + 실 subprocess probe 비용 0).
    # Pin can_run_tests to False so the ONLY difference from the deny test is the path
    # (blocks env-dependent spurious pass + zero real subprocess probe cost).
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps({"tool_input": {"file_path": "src/api/routes.py"}})),
    )

    assert hook.main() == 0
    # 대조군 — 여기서 출력이 나오면 위 deny 테스트의 stdout 관측이 무의미해진다.
    # Control — any output here would void the deny test's stdout observation.
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("raw", ["null", "[]", "1"])
def test_main_treats_non_dict_payload_as_parse_failure(hook, monkeypatch, capsys, raw):
    """파싱은 성공하지만 dict 가 아닌 payload(null/[]/1)는 traceback 없이 loud fail-open.

    현행: `payload.get` 에서 TypeError/AttributeError traceback — 구판과 같은 잔여 crash
    클래스 (GROK-20260802-2). 계약: json.load 성공 후 `isinstance(payload, dict)` 가 아니면
    payload 를 None 으로 강등 → 기존 parse-failure advisory 경로와 합류한다.

    Payloads that parse but are not dicts (null/[]/1) must take the loud fail-open path,
    not a traceback. Today `payload.get` raises (the residual crash class of the
    pre-refactor hook, GROK-20260802-2). Contract: after a successful json.load, a
    non-dict payload demotes to None and joins the existing parse-failure advisory path.
    """
    monkeypatch.setattr("sys.stdin", io.StringIO(raw))

    # 예외 없이 0 반환 — 예외가 나면 pytest 가 traceback 으로 그대로 실패 보고한다
    # (testing.md: does-not-raise 는 wrapper 없이 직접 호출).
    # Returns 0 with no exception — an exception fails the test directly via its traceback
    # (testing.md: assert does-not-raise by direct call, no try/except wrapper).
    assert hook.main() == 0

    printed = json.loads(capsys.readouterr().out)
    out = printed["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    # advisory 채널 존재 + 권한 결정 부재 — parse-failure 출력과 동일 형태 계약.
    # Advisory channel present, permission decision absent — same shape as parse failure.
    assert isinstance(out["additionalContext"], str) and out["additionalContext"].strip()
    assert "permissionDecision" not in out
    assert "permissionDecisionReason" not in out


@pytest.mark.parametrize("raw", ["null", "[]", "1"])
def test_end_to_end_subprocess_non_dict_payload(raw):
    """실행 축 — dict 아닌 JSON stdin 에서도 exit 0 + loud advisory JSON (GROK-20260802-2).

    현행 실측: "[]"/"1" 은 `payload.get` traceback 으로 rc=1 (RED 축)이고, "null" 은
    json.load 가 Python None 을 돌려줘 기존 parse-failure 분기와 우연히 합류해 GREEN —
    세 케이스 모두 같은 advisory 계약으로 수렴해야 한다. 지시서의 "null" 단일 케이스를
    포함하되 실제 crash 재현 케이스("[]"/"1")를 같은 실행 축에 고정하기 위해 parametrize
    로 확장했다 (자율 판단 — 본문 보고).

    Execution axis — non-dict JSON stdin must still exit 0 with the loud advisory JSON.
    Measured today: "[]"/"1" crash with rc=1 via `payload.get` (the RED axis), while
    "null" happens to join the parse-failure branch (json null → Python None) and is
    GREEN. All three must converge on the same advisory contract; the spec's single
    "null" case is kept and extended by parametrize to pin the actually-crashing cases.
    """
    proc = _run_hook(raw)

    assert proc.returncode == 0, f"advisory 훅이 비-0 종료 — stderr: {proc.stderr!r}"
    payload = json.loads(proc.stdout)
    out = payload["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert isinstance(out["additionalContext"], str) and out["additionalContext"].strip()
    # advisory 에 권한 결정이 실리면 사용자 권한 확인 우회 위험 — 부재를 실행 축에서도 고정.
    # A permission decision on an advisory can bypass the permission flow — pin its
    # absence on the execution axis too.
    assert "permissionDecision" not in out
