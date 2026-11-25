"""스모크 훅의 결과가 «누구에게 닿는가» — 출력 채널 계약 (회고 원장 #1917 M01 P1-4).

## 사고

PostToolUse 의 plain stdout 은 에이전트에게 가지 않는다(디버그 로그 · 세션 기록의 `hook_success` — 모델 맥락에서 버려진다).
스모크 훅은 결과를 plain stdout 으로만 냈다 — 11-06~11-24 창의 배너 746건(❌ 225 · ⚠️ 186)이 하나도 에이전트에게 닿지 않았다.
같은 PostToolUse 의 메모리 훅(`check_memory_after_write.py`)은 JSON `additionalContext` 라 닿았다.

## 이 파일이 잠그는 것

1. ❌(실패) · ⚠️(미완 — 타임아웃 · 실행 오류 · 못 잰 워크플로)는 stdout 전체가 JSON 한 개다 —
   `hookSpecificOutput.additionalContext`(에이전트) = `systemMessage`(사람). 배너 한 줄과 pytest 출력의 끝 줄들을 담는다.
2. ✅(통과) · ℹ️(수집만 · 단언 0건)는 에이전트 맥락에 아무것도 더하지 않는다 — 배너는 plain stdout(세션 기록)에만 남는다.
3. 계기 뒤집기 — 같은 편집 경로에서 결과만 바꿔 두 쪽을 함께 심는다(`claimed` = ❌ · ⚠️ 는 닿아야,
   `cheap` = «출력이 있으면 JSON» 이 맞힐 ✅ + 꼬리 출력은 닿지 않아야).
4. 에이전트에게 가는 글은 짧다 — 꼬리가 길어도 줄 수 · 줄 길이에 상한이 있다.
"""
import io
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / ".claude" / "hooks"))

import posttool_pytest_smoke as hook  # noqa: E402

# 대응 시험 파일이 있는 감시 경로(→ tests/unit/scripts/test_check_main_red.py) · 없는 감시 경로(→ 수집 스모크).
# A watched path with its own test file, and one without (collection smoke).
_WITH_TEST = "scripts/check_main_red.py"
_WITHOUT_TEST = "scripts/no_such_script_for_channel_test.py"

# pytest -q -x 실패 출력의 끝 8줄(`_run` 이 돌려주는 꼬리) — 끝 세 줄이 FAILED 줄 · 멈춤 줄 · 건수 줄이다.
# The last 8 lines pytest -q -x prints on a failure, as `_run` returns them.
_FAILED_TAIL = "\n".join([
    "    def test_red():",
    ">       assert 1 == 2",
    "E       assert 1 == 2",
    "",
    "tests/unit/scripts/test_check_main_red.py:12: AssertionError",
    "FAILED tests/unit/scripts/test_check_main_red.py::test_red - assert 1 == 2",
    "!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!",
    "1 failed, 3 passed in 0.52s",
])


def _main(monkeypatch, capsys, path, rc, tail):
    """`main()` 을 실제 stdin 으로 돌리고 pytest 결과만 갈아 끼운다 — stdout 전체를 돌려준다."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_input": {"file_path": path}})))
    monkeypatch.setattr(hook, "_run", lambda cmd, cwd: (rc, tail))
    assert hook.main() == 0
    return capsys.readouterr().out


def _agent_context(out):
    """stdout 이 에이전트 맥락 채널이면 (additionalContext, systemMessage), 아니면 None.

    Claude Code 는 stdout **전체**가 JSON 일 때만 필드를 읽는다 — 앞뒤에 다른 글이 붙으면 plain stdout 이 된다.
    """
    try:
        payload = json.loads(out)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    spec = payload.get("hookSpecificOutput")
    if not isinstance(spec, dict) or spec.get("hookEventName") != "PostToolUse":
        return None
    return spec.get("additionalContext"), payload.get("systemMessage")


def test_a_failed_smoke_reaches_the_agent_and_the_person(monkeypatch, capsys):
    """🔴 ❌ 는 에이전트 맥락(additionalContext)과 사람(systemMessage) 모두에게 같은 글로 닿는다."""
    channel = _agent_context(_main(monkeypatch, capsys, _WITH_TEST, 1, _FAILED_TAIL))
    assert channel is not None, "❌ 가 plain stdout 으로만 나갔다 — 에이전트에게 안 닿는다"
    context, system = channel
    assert context == system, channel
    first, *rest = context.splitlines()
    assert first.startswith("❌") and "[tests/unit/scripts/test_check_main_red.py]" in first, first
    assert rest == _FAILED_TAIL.splitlines()[-3:], rest


@pytest.mark.parametrize("tail", [
    f"⏱️ 스모크 타임아웃({hook._RUN_TIMEOUT}s) — 전체 게이트는 push-time 에 실행 / smoke timed out",
    "실행 오류 / run error: [WinError 2] 지정된 파일을 찾을 수 없습니다",
], ids=["timeout", "run-error"])
def test_an_unfinished_smoke_reaches_the_agent_too(tail, monkeypatch, capsys):
    """⚠️(미완)도 닿는다 — 이 편집은 아직 아무것도 안 쟀다는 사실이 «조용함» 과 구별돼야 한다."""
    channel = _agent_context(_main(monkeypatch, capsys, _WITH_TEST, None, tail))
    assert channel is not None, "⚠️ 가 에이전트에게 안 닿는다"
    first, *rest = channel[0].splitlines()
    assert first.startswith("⚠️"), first
    assert rest == [tail], rest


@pytest.mark.parametrize(("path", "rc", "banner"), [
    (_WITH_TEST, 0, "✅"),
    (_WITHOUT_TEST, 0, "ℹ️"),
], ids=["passed", "collect-only"])
def test_a_passing_or_collect_only_smoke_adds_nothing_to_the_agent_context(path, rc, banner, monkeypatch, capsys):
    """대조군(뒤집기) — 같은 경로 · 꼬리 출력이 있어도 ✅ · ℹ️ 는 에이전트 맥락에 아무것도 더하지 않는다.

    «출력이 있으면 JSON» 같은 싼 과정은 여기서 걸린다. 배너는 plain stdout 에 남는다(세션 기록 · 디버그 로그).
    """
    out = _main(monkeypatch, capsys, path, rc, "4 passed in 0.31s")
    assert _agent_context(out) is None, out
    assert out.startswith(banner), out


def test_a_collection_failure_reaches_the_agent(monkeypatch, capsys):
    """대응 시험이 없어 수집만 돌린 경로라도 수집이 깨졌으면(import 파손) ❌ 로 닿는다 — 뒤집기의 짝."""
    tail = "\n".join([
        "ERROR tests/unit/scripts/test_broken.py",
        "!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!",
        "1 error in 0.40s",
    ])
    channel = _agent_context(_main(monkeypatch, capsys, _WITHOUT_TEST, 2, tail))
    assert channel is not None, "수집 실패가 에이전트에게 안 닿는다"
    first, *rest = channel[0].splitlines()
    assert first.startswith("❌") and "(collect)" in first, first
    assert rest == tail.splitlines(), rest


def test_the_agent_message_stays_short_however_long_the_output(monkeypatch, capsys):
    """에이전트 맥락은 비용이다 — 꼬리가 길어도 배너 + 끝 줄 몇 개, 줄마다 길이 상한."""
    long_line = "FAILED tests/unit/scripts/test_check_main_red.py::test_red - " + "x" * 5000
    tail = "\n".join([*(f"noise {i}" for i in range(40)), long_line, "1 failed in 0.10s"])
    context, _ = _agent_context(_main(monkeypatch, capsys, _WITH_TEST, 1, tail))
    lines = context.splitlines()
    assert len(lines) <= 1 + hook._AGENT_LINES, lines
    assert max(len(line) for line in lines[1:]) <= hook._AGENT_WIDTH, [len(line) for line in lines]
    assert lines[-1] == "1 failed in 0.10s", lines


def test_failure_without_any_output_still_reaches_the_agent(monkeypatch, capsys):
    """출력이 비어도(사용 오류는 stderr 로 간다) ❌ 배너 한 줄은 닿는다 — 이유가 없다고 조용해지지 않는다."""
    channel = _agent_context(_main(monkeypatch, capsys, _WITH_TEST, 4, ""))
    assert channel is not None
    assert channel[0].splitlines()[0].startswith("❌"), channel


def _workflows(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    good, bad = wf / "ci.yml", wf / "broken.yml"
    good.write_text("name: CI\non: [push]\njobs:\n  a:\n    runs-on: ubuntu-latest\n", encoding="utf-8")
    bad.write_text("name: CI\njobs:\n  a: [unclosed\n", encoding="utf-8")
    return good, bad


def test_a_broken_workflow_reaches_the_agent_and_a_sound_one_stays_silent(tmp_path, monkeypatch, capsys):
    """워크플로는 YAML 파싱만 본다 — 깨졌으면 ❌ 로 닿고, 성하면(ℹ️ 단언 0건) 에이전트 맥락에 더하지 않는다."""
    good, bad = _workflows(tmp_path)
    channel = _agent_context(_main(monkeypatch, capsys, str(bad), 0, ""))
    assert channel is not None, "깨진 워크플로가 에이전트에게 안 닿는다"
    assert channel[0].startswith("❌") and "YAML" in channel[0], channel
    out = _main(monkeypatch, capsys, str(good), 0, "")
    assert _agent_context(out) is None and out.startswith("ℹ️"), out


def test_a_workflow_left_unparsed_for_lack_of_a_parser_is_unmeasured(tmp_path, monkeypatch, capsys):
    """YAML 파서가 없으면 «못 쟀다» 다 — ⚠️ 로 닿는다. ℹ️(단언 0건)는 설계상 시험이 없는 경로의 몫이다."""
    good, _ = _workflows(tmp_path)
    monkeypatch.setitem(sys.modules, "ruamel.yaml", None)
    channel = _agent_context(_main(monkeypatch, capsys, str(good), 0, ""))
    assert channel is not None, "못 잰 워크플로가 조용했다"
    assert channel[0].startswith("⚠️"), channel
