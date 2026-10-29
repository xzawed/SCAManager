"""Bash 로 바뀐 보호 경로를 «탐지» 하는 훅 (회고 2026-09-07 B).

## 이 훅이 존재하는 이유

`check_edit_allowed.py` 는 이 리포의 **유일한 차단 훅**이고 `Write|Edit|MultiEdit` 에만
걸려 있다. 테스트 불가 환경에서 Bash 로 보호 경로를 고치면 그 차단을 통째로 우회하고,
`.pre-commit-config.yaml` 에 동등한 검사가 없어 하류에서도 다시 보지 않는다.

## 🔴 이 시험들이 «단언하지 않는» 것

**차단**을 단언하지 않는다. PostToolUse 는 도구가 끝난 뒤 불리므로 막을 수 없다.
그래서 여기서는 「탐지되는가」와 「조용해지지 않는가」만 잰다 — 그리고 그 한계가
훅 문서와 CLAUDE.md 에 «적혀 있는지» 를 함께 잰다. 부분 방어를 완전 방어로 읽히게
두는 것이 이 리포가 「거짓 집행자」로 부르는 형태다.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_HOOK = _ROOT / ".claude" / "hooks" / "detect_protected_bash_write.py"


def _load():
    sys.path.insert(0, str(_HOOK.parent))
    spec = importlib.util.spec_from_file_location("detect_protected_bash_write", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load()


# ── 판정 ─────────────────────────────────────────────────────────────────────


def test_verifiable_environment_stays_silent(monkeypatch, capsys):
    """🔴 검증 가능한 환경에서는 아무 말도 하지 않는다 — 차단 훅과 같은 조건이다.

    조건이 갈리면 두 훅이 서로 다른 환경을 보호하게 되고, 그 어긋남은 조용하다.
    """
    monkeypatch.setattr(hook, "can_run_tests", lambda: True)
    monkeypatch.setattr(hook, "dirty_protected_paths",
                        lambda: [("src/templates/x.html", "이유")])
    monkeypatch.setattr(sys, "stdin", _stdin('{"tool_name":"Bash"}'))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_unverifiable_environment_reports_the_dirty_protected_path(monkeypatch, capsys, tmp_path):
    """테스트 불가 환경 + 보호 경로가 더러우면 **알린다**."""
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    monkeypatch.setattr(hook, "dirty_protected_paths",
                        lambda: [("src/templates/settings.html", "HTML 템플릿")])
    monkeypatch.setattr(hook, "_STATE", tmp_path / "state")
    monkeypatch.setattr(sys, "stdin", _stdin('{"tool_name":"Bash"}'))
    assert hook.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert "src/templates/settings.html" in payload["systemMessage"]


def test_the_message_says_it_did_not_block(monkeypatch, capsys, tmp_path):
    """🔴 문구가 «막았다» 로 읽히면 안 된다 — 이 훅은 탐지만 한다.

    사람이 이 메시지를 보고 「차단됐구나」라고 읽으면, 실제로는 이미 바뀐 파일을 두고
    안심하게 된다. 그 오독이 이 축의 가장 큰 위험이다.
    """
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    monkeypatch.setattr(hook, "dirty_protected_paths", lambda: [("railway.toml", "배포 설정")])
    monkeypatch.setattr(hook, "_STATE", tmp_path / "state")
    monkeypatch.setattr(sys, "stdin", _stdin("{}"))
    hook.main()
    msg = json.loads(capsys.readouterr().out)["systemMessage"]
    assert "탐지" in msg and "막지도" in msg, f"한계가 문구에 없다: {msg}"


_IN_SESSION = json.dumps({"tool_name": "Bash", "session_id": "s1"})


def test_the_same_path_is_not_reported_twice(monkeypatch, capsys, tmp_path):
    """같은 파일로 매 Bash 호출마다 떠들지 않는다 — 소음은 경고를 죽인다."""
    state = tmp_path / "state"
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    monkeypatch.setattr(hook, "dirty_protected_paths", lambda: [("alembic.ini", "설정")])
    monkeypatch.setattr(hook, "_STATE", state)
    monkeypatch.setattr(sys, "stdin", _stdin(_IN_SESSION))
    hook.main()
    assert capsys.readouterr().out, "첫 알림이 없다"
    monkeypatch.setattr(sys, "stdin", _stdin(_IN_SESSION))
    hook.main()
    assert capsys.readouterr().out == "", "같은 경로를 두 번 알린다"


def test_a_new_path_still_reports_after_an_earlier_one(monkeypatch, capsys, tmp_path):
    """🔴 대조군 — 억제가 «전부» 를 삼키면 두 번째 파일이 조용히 지나간다."""
    state = tmp_path / "state"
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    monkeypatch.setattr(hook, "_STATE", state)
    monkeypatch.setattr(hook, "dirty_protected_paths", lambda: [("alembic.ini", "설정")])
    monkeypatch.setattr(sys, "stdin", _stdin(_IN_SESSION))
    hook.main()
    capsys.readouterr()
    monkeypatch.setattr(hook, "dirty_protected_paths",
                        lambda: [("alembic.ini", "설정"), ("railway.toml", "배포")])
    monkeypatch.setattr(sys, "stdin", _stdin(_IN_SESSION))
    hook.main()
    out = capsys.readouterr().out
    assert "railway.toml" in out, "새 경로를 알리지 않는다"


# ── 억제의 수명 — «한 번 알린 경로는 영원히 침묵» 이 아니다 (#1746 K16) ──────────────
#    수정 전: 상태 파일이 알린 경로를 클론 수명 내내 쌓기만 해서, 그 경로가 커밋·되돌림 뒤
#    다시 바뀌어도, 다른 세션에서 바뀌어도 다시는 알리지 않았다.


def _run(monkeypatch, capsys, *, dirty, prints, session="s1"):
    """한 번의 Bash 뒤 훅 실행 — 더러운 경로 목록과 각 파일의 «내용 지문» 을 준다."""
    monkeypatch.setattr(hook, "dirty_protected_paths", lambda: [(p, "이유") for p in dirty])
    # raising=False — 지문 함수가 없는 판(수정 전)에서도 «행동» 단언으로 red 가 나게 한다.
    monkeypatch.setattr(hook, "_fingerprint", lambda p: prints[p], raising=False)
    monkeypatch.setattr(sys, "stdin", _stdin(json.dumps({"tool_name": "Bash", "session_id": session})))
    hook.main()
    return capsys.readouterr().out


def test_a_path_changed_again_is_reported_again(monkeypatch, capsys, tmp_path):
    """🔴 같은 경로라도 내용이 «다시» 바뀌면 다시 알린다 — 같은 내용이면 조용하다."""
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    monkeypatch.setattr(hook, "_STATE", tmp_path / "state")
    assert _run(monkeypatch, capsys, dirty=["alembic.ini"], prints={"alembic.ini": "A"})
    assert _run(monkeypatch, capsys, dirty=["alembic.ini"], prints={"alembic.ini": "A"}) == "", (
        "같은 내용인데 다시 알린다 — 매 Bash 마다 떠든다")
    assert "alembic.ini" in _run(monkeypatch, capsys, dirty=["alembic.ini"], prints={"alembic.ini": "B"}), (
        "같은 경로가 Bash 로 «다시» 바뀌었는데 침묵한다")


def test_a_path_that_became_clean_is_reported_when_dirty_again(monkeypatch, capsys, tmp_path):
    """🔴 커밋·되돌림으로 깨끗해진 경로는 기록에서 빠진다 — 다시 더러워지면 같은 내용이어도 알린다."""
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    monkeypatch.setattr(hook, "_STATE", tmp_path / "state")
    assert _run(monkeypatch, capsys, dirty=["alembic.ini"], prints={"alembic.ini": "A"})
    assert _run(monkeypatch, capsys, dirty=[], prints={}) == ""
    assert "alembic.ini" in _run(monkeypatch, capsys, dirty=["alembic.ini"], prints={"alembic.ini": "A"}), (
        "한 번 알린 경로가 깨끗해졌다가 다시 바뀌었는데 침묵한다 — 억제가 클론 수명 내내 남는다")


def test_a_new_session_reports_paths_that_are_still_dirty(monkeypatch, capsys, tmp_path):
    """🔴 억제는 세션을 넘지 않는다 — 새 세션은 앞 세션이 Bash 로 바꾼 보호 경로를 모른다."""
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    monkeypatch.setattr(hook, "_STATE", tmp_path / "state")
    assert _run(monkeypatch, capsys, dirty=["alembic.ini"], prints={"alembic.ini": "A"}, session="s1")
    assert "alembic.ini" in _run(monkeypatch, capsys, dirty=["alembic.ini"], prints={"alembic.ini": "A"},
                                 session="s2"), "다른 세션인데 앞 세션의 억제가 남아 침묵한다"


@pytest.mark.parametrize("state_text", [
    "alembic.ini\nrailway.toml\n",                     # 옛 형식(줄 목록)
    "null", "[1, 2]", '{"session": "s1", "reported": []}', '{"session": 1, "reported": {}}',
    "[" * 10000 + "]" * 10000,                          # 깊은 중첩 = RecursionError(ValueError 아님) — Grok 반례
])
def test_any_state_file_content_falls_back_to_reporting(monkeypatch, capsys, tmp_path, state_text):
    """🔴 상태 파일이 무엇이든 훅은 죽지 않고, 모르는 상태면 «알리는» 쪽으로 간다."""
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    state = tmp_path / "state"
    state.write_text(state_text, encoding="utf-8")
    monkeypatch.setattr(hook, "_STATE", state)
    assert "alembic.ini" in _run(monkeypatch, capsys, dirty=["alembic.ini"], prints={"alembic.ini": "A"})


@pytest.mark.parametrize("stdin_text", [
    "", "not json", "[" * 10000 + "]" * 10000, '{"session_id": 1}', '{"session_id": null}',
])
def test_any_stdin_still_runs_the_verdict(monkeypatch, capsys, tmp_path, stdin_text):
    """입력이 깨져도·깊게 중첩돼도 판정은 작업 트리로 한다 — 훅이 예외로 죽지 않는다."""
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    monkeypatch.setattr(hook, "_STATE", tmp_path / "state")
    monkeypatch.setattr(hook, "dirty_protected_paths", lambda: [("alembic.ini", "이유")])
    monkeypatch.setattr(hook, "_fingerprint", lambda p: "A", raising=False)
    monkeypatch.setattr(sys, "stdin", _stdin(stdin_text))
    assert hook.main() == 0
    assert "alembic.ini" in capsys.readouterr().out


def test_a_numeric_session_id_is_not_the_same_session_as_its_string(monkeypatch, capsys, tmp_path):
    """숫자 `1` 과 문자열 `"1"` 은 같은 세션이 아니다 — 앞 세션의 억제를 물려받지 않는다(Grok 반례)."""
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    monkeypatch.setattr(hook, "_STATE", tmp_path / "state")
    assert _run(monkeypatch, capsys, dirty=["alembic.ini"], prints={"alembic.ini": "A"}, session="1")
    monkeypatch.setattr(hook, "dirty_protected_paths", lambda: [("alembic.ini", "이유")])
    monkeypatch.setattr(sys, "stdin", _stdin('{"session_id": 1}'))
    hook.main()
    assert "alembic.ini" in capsys.readouterr().out, "숫자 1 이 문자열 \"1\" 세션의 억제를 물려받았다"


def test_without_a_session_id_nothing_is_suppressed_or_recorded(monkeypatch, capsys, tmp_path):
    """🔴 세션을 모르면 억제를 쓰지 않는다 — «id 없음» 끼리 한 세션으로 합치면 앞 실행의 침묵을
    물려받는다(Grok 재판정 반례: 숫자·null id 가 `""` 로 접혀 저장된 `""` 세션과 합쳐졌다)."""
    monkeypatch.setattr(hook, "can_run_tests", lambda: False)
    state = tmp_path / "state"
    monkeypatch.setattr(hook, "_STATE", state)
    monkeypatch.setattr(hook, "dirty_protected_paths", lambda: [("alembic.ini", "이유")])
    monkeypatch.setattr(hook, "_fingerprint", lambda p: "A", raising=False)
    for stdin_text in ("{}", '{"session_id": null}', '{"session_id": 0}', '{"session_id": ""}', "{}"):
        monkeypatch.setattr(sys, "stdin", _stdin(stdin_text))
        hook.main()
        assert "alembic.ini" in capsys.readouterr().out, f"세션을 모르는 실행({stdin_text})이 억제됐다"
    assert not state.exists(), "세션을 모르는 실행이 억제 기록을 남겼다"


def test_fingerprint_follows_the_file_bytes(tmp_path, monkeypatch):
    """지문은 작업 트리 파일 «내용» 에서 온다 — 지워진 파일도 하나의 상태로 구별한다."""
    monkeypatch.setattr(hook, "_ROOT", tmp_path)
    (tmp_path / "a.ini").write_bytes(b"one")
    first = hook._fingerprint("a.ini")
    (tmp_path / "a.ini").write_bytes(b"two")
    second = hook._fingerprint("a.ini")
    (tmp_path / "a.ini").unlink()
    gone = hook._fingerprint("a.ini")
    assert len({first, second, gone}) == 3, (first, second, gone)


# ── 정의 ↔ 사용 (배선) ────────────────────────────────────────────────────────


def test_protected_definition_is_shared_with_the_blocking_hook():
    """🔴 보호 경로 정의를 «복사» 하지 않는다 — 두 훅이 다른 파일을 보호하면 조용히 갈린다."""
    src = _HOOK.read_text(encoding="utf-8")
    assert "from check_edit_allowed import" in src, (
        "차단 훅의 정의를 import 하지 않는다 — 사본은 한쪽만 고쳐지는 순간 어긋난다")
    assert "PROTECTED_PATTERNS" not in src, "보호 패턴을 여기서 다시 정의한다(사본)"


def test_hook_is_wired_into_settings_for_bash():
    """정의 ≠ 배선 — settings.json 의 **PostToolUse(Bash)** 에 실제로 걸려 있어야 한다.

    Write|Edit 쪽에만 걸면 이 훅이 닫으려는 바로 그 구멍(Bash 경로)을 안 본다.
    """
    cfg = json.loads((_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    entries = cfg["hooks"]["PostToolUse"]
    matched = [e for e in entries
               if any("detect_protected_bash_write.py" in h.get("command", "")
                      for h in e.get("hooks", []))]
    assert matched, "PostToolUse 에 이 훅이 없다 — 정의만 있고 배선이 없다"
    matchers = {e.get("matcher", "") for e in matched}
    assert any("Bash" in m for m in matchers), (
        f"Bash 매처에 걸려 있지 않다 — 닫으려는 구멍이 Bash 다: {matchers}")


def test_claude_md_does_not_claim_bash_is_blocked():
    """🔴 문서가 「훅이 차단한다」만 적으면 Bash 경로가 막힌다고 읽힌다.

    실제로는 `Write|Edit|MultiEdit` 만 막고 Bash 는 탐지에 그친다. 그 한계가 항상
    로드되는 문서에 적혀 있어야 다음 사람이 오독하지 않는다.
    """
    text = (_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    idx = text.find("## 파일 수정 제한")
    assert idx != -1, "CLAUDE.md 에 「파일 수정 제한」 절이 없다"
    section = text[idx:idx + 700]
    assert "Bash" in section, (
        "Bash 경로의 한계가 「파일 수정 제한」 절에 없다 — 차단으로 오독된다")


def test_hook_runs_as_a_script_and_exits_zero():
    """계기 자기검증 — 실제로 실행되어야 한다(import 만 되는 죽은 파일이 아님)."""
    r = subprocess.run([sys.executable, str(_HOOK)], input='{"tool_name":"Bash"}',
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60, check=False)
    assert r.returncode == 0, f"훅이 0 이 아닌 코드로 끝난다: {r.returncode} {r.stderr[:200]}"


def _stdin(payload: str):
    import io
    return io.StringIO(payload)


@pytest.mark.parametrize("path,expected", [
    ("src/templates/x.html", True),
    ("alembic/versions/0001_x.py", True),
    ("railway.toml", True),
    ("Dockerfile", True),
    (".dockerignore", True),
    ("src/main.py", False),
])
def test_shared_predicate_still_classifies_the_documented_paths(path, expected):
    """공유 술어가 문서가 약속한 네 부류를 그대로 가리는지 — import 가 살아 있는지도 함께."""
    assert (hook.protected_reason(path) is not None) is expected
