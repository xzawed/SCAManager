"""main red 관측자의 계약 (P3).

## 왜 (2026-08-08 실측)

`main` 의 CI 실패는 아무도 보지 않았다. 최근 25 run 에서 red 구간 **4회**, 그중 둘은
**20시간 9분**과 **12시간 49분**이었다. 후자는 이 세션이 발행한 잘못된 테스트 수치였고,
사용자가 *"확인해달라"* 고 하기 전까지 아무도 몰랐다.

🔴 **R56 이 이미 증명했다**: loud 관측자만으로는 아무 일도 일어나지 않는다(pre-commit
미설치 배너가 19 PR 동안 매 세션 떴지만 조치는 0). 그래서 이 관측자의 지표는
*"발화했는가"* 가 아니라 **"몇 시간 만에 고쳤는가"** 이고, 그 값을 매번 인쇄한다.

## 고정하는 계약

| 상황 | 기대 |
|---|---|
| 최신 run 성공 | 조용히 "초록" |
| 최신 run 실패 | **loud** + 지속 시간 + 실패 job + run URL |
| 연속 실패 N건 | 지속 시간은 **마지막 성공 이후**로 계산 |
| `gh` 부재·네트워크·파싱 실패 | **"판정 불가" 인쇄** (침묵 금지 — R0-2 클래스) |
| 어떤 경우든 | **exit 0** (SessionStart 차단 금지 — 정책 17) |
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

import scripts.check_main_red as mod

_MOD = "scripts.check_main_red"


def _run(created: str, conclusion: str | None, rid: int = 1) -> dict:
    return {"createdAt": created, "conclusion": conclusion, "status": "completed",
            "databaseId": rid, "url": f"https://example/{rid}"}


_NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


# ── ① 지속 시간 산출 ────────────────────────────────────────────────────


def test_green_latest_is_not_red():
    runs = [_run("2026-08-08T11:00:00Z", "success"), _run("2026-08-08T10:00:00Z", "failure")]
    is_red, hours, latest = mod.red_span(runs, now=_NOW)
    assert is_red is False
    assert hours == 0.0
    assert latest is None


def test_single_failure_measures_from_that_run():
    runs = [_run("2026-08-08T09:00:00Z", "failure"), _run("2026-08-08T08:00:00Z", "success")]
    is_red, hours, latest = mod.red_span(runs, now=_NOW)
    assert is_red is True
    assert hours == pytest.approx(3.0, abs=0.01)
    assert latest["databaseId"] == 1


def test_consecutive_failures_measure_from_the_last_success():
    """🔴 연속 실패는 **마지막 성공 이후** 전체가 red 구간이다.

    최신 실패만 보면 20시간 방치가 '방금 빨개졌다' 로 보인다 — 실측된 두 장기 구간이
    모두 연속 실패였다(5건·2건).
    """
    runs = [
        _run("2026-08-08T09:00:00Z", "failure", 3),
        _run("2026-08-08T05:00:00Z", "failure", 2),
        _run("2026-08-07T23:00:00Z", "failure", 1),
        _run("2026-08-07T20:00:00Z", "success", 0),
    ]
    is_red, hours, latest = mod.red_span(runs, now=_NOW)
    assert is_red is True
    assert hours == pytest.approx(13.0, abs=0.01), (
        f"마지막 성공(23:00 앞) 이후로 재지 않았다 — {hours}시간"
    )
    assert latest["databaseId"] == 3, "최신 실패 run 을 돌려줘야 상세 조회가 가능하다"


def test_in_progress_runs_are_ignored():
    """아직 도는 run 은 판정 재료가 아니다 — 완료된 것만 본다."""
    runs = [
        {"createdAt": "2026-08-08T11:59:00Z", "conclusion": None,
         "status": "in_progress", "databaseId": 9, "url": "u"},
        _run("2026-08-08T09:00:00Z", "success"),
    ]
    assert mod.red_span(runs, now=_NOW)[0] is False


def test_in_progress_run_does_not_hide_a_red_main():
    """🔴 도는 run 이 red 를 **가려서는 안 된다** — 필터가 판정력을 가져야 한다.

    실측: `status == "completed"` 필터를 지우는 뮤테이션에서 스위트가 **GREEN** 이었다
    (위 테스트만으로는 필터가 없어도 통과한다 — `conclusion=None` 이 실패가 아니므로).
    새 run 이 도는 동안 직전 실패가 조용해지면, 재실행마다 red 가 리셋돼 **20시간 방치가
    '방금 시작' 으로 보인다** — 실측된 장기 구간이 모두 연속 실행 중에 있었다.
    """
    runs = [
        {"createdAt": "2026-08-08T11:59:00Z", "conclusion": None,
         "status": "in_progress", "databaseId": 9, "url": "u"},
        _run("2026-08-08T09:00:00Z", "failure", 8),
        _run("2026-08-08T08:00:00Z", "success", 7),
    ]
    is_red, hours, latest = mod.red_span(runs, now=_NOW)
    assert is_red is True, "도는 run 이 직전 red 를 가렸다"
    assert hours == pytest.approx(3.0, abs=0.01)
    assert latest["databaseId"] == 8, "완료된 실패 run 을 돌려줘야 상세 조회가 된다"


def test_empty_history_is_not_red():
    assert mod.red_span([], now=_NOW)[0] is False


# ── ② 판정 불가를 침묵으로 흘리지 않는다 ────────────────────────────────


def test_unavailable_gh_is_reported_not_silent(monkeypatch, capsys):
    """🔴 조용한 exit 0 은 **"main 초록"과 구별되지 않는다** (R0-2 가 고친 클래스)."""
    monkeypatch.setattr(f"{_MOD}.fetch_runs", lambda: None)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "판정하지 못했다" in out, f"판정 불가를 알리지 않았다: {out!r}"
    assert "초록이라는 뜻이 아니다" in out, "판정 불가가 초록으로 오독될 여지를 남겼다"


def test_gh_absent_returns_none(monkeypatch):
    """`gh` 자체가 없으면 None — 호출부가 '판정 불가' 로 처리한다."""
    monkeypatch.setattr(f"{_MOD}.shutil.which", lambda _n: None)
    assert mod._gh(["run", "list"]) is None


def test_unparseable_output_returns_none(monkeypatch):
    """JSON 이 깨지면 None — 빈 리스트(=초록)로 흘리면 fail-open 이다."""
    monkeypatch.setattr(f"{_MOD}._gh", lambda *a, **k: "not json")
    assert mod.fetch_runs() is None


def test_non_list_json_returns_none(monkeypatch):
    """유효 JSON 이지만 리스트가 아니면 None — 형태를 믿지 않는다."""
    monkeypatch.setattr(f"{_MOD}._gh", lambda *a, **k: '{"unexpected": true}')
    assert mod.fetch_runs() is None


# ── ③ 보고 내용 ─────────────────────────────────────────────────────────


def test_red_report_carries_duration_and_jobs(monkeypatch, capsys):
    """🔴 지표는 '발화했는가' 가 아니라 **'몇 시간째인가'** 다 — 그 값이 출력에 있어야 한다."""
    runs = [_run("2026-08-08T09:00:00Z", "failure", 7), _run("2026-08-08T08:00:00Z", "success")]
    monkeypatch.setattr(f"{_MOD}.fetch_runs", lambda: runs)
    monkeypatch.setattr(f"{_MOD}.failing_jobs", lambda _i: ["pytest + Codecov"])
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "빨갛다" in out
    assert "시간째" in out, f"지속 시간을 보고하지 않았다: {out!r}"
    assert "pytest + Codecov" in out, "실패 job 을 알리지 않으면 조사에 도움이 안 된다"
    assert "https://example/7" in out, "run URL 이 없으면 확인 경로가 없다"


def test_green_report_is_quiet(monkeypatch, capsys):
    """초록이면 짧게 — 매번 떠들면 배너 피로로 진짜 경고가 묻힌다."""
    monkeypatch.setattr(
        f"{_MOD}.fetch_runs", lambda: [_run("2026-08-08T11:00:00Z", "success")])
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "초록" in out
    assert "빨갛다" not in out


def test_always_advisory(monkeypatch, capsys):
    """어떤 상태에서도 exit 0 — SessionStart 를 막으면 세션 자체가 안 열린다(정책 17)."""
    for runs in ([_run("2026-08-08T09:00:00Z", "failure")],
                 [_run("2026-08-08T09:00:00Z", "success")],
                 None):
        monkeypatch.setattr(f"{_MOD}.fetch_runs", lambda r=runs: r)
        monkeypatch.setattr(f"{_MOD}.failing_jobs", lambda _i: [])
        assert mod.main() == 0
    capsys.readouterr()


def test_no_state_file_is_written(tmp_path, monkeypatch):
    """🔴 상태를 저장하지 않는다 — 원장을 두면 그 파일이 또 drift 하고 갱신이 기억에 걸린다.

    지속 시간은 매번 `gh run list` 이력에서 **유도**한다.
    """
    import scripts.check_main_red as m  # noqa: PLC0415

    src = (tmp_path / "x")  # 존재만 확인용
    assert not src.exists()
    source = __import__("pathlib").Path(m.__file__).read_text(encoding="utf-8")
    for bad in ("open(", "write_text", "mkdir("):
        assert bad not in source.replace("# ", ""), (
            f"상태 저장으로 보이는 호출이 있다: {bad}"
        )


# ── ④ 배선 ──────────────────────────────────────────────────────────────


def test_wired_into_session_start():
    """정의 ≠ 배선 — SessionStart 에서 **실제로 실행**되는지."""
    import json as _json
    import pathlib

    from tests.unit.scripts._wiring_shape import any_invokes

    root = pathlib.Path(__file__).resolve().parents[3]
    settings = _json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = [
        hook.get("command", "")
        for entry in settings.get("hooks", {}).get("SessionStart", [])
        for hook in entry.get("hooks", [])
    ]
    assert any_invokes(commands, "scripts/check_main_red.py"), (
        f"SessionStart 미배선 — 매 세션 관측이 일어나지 않는다.\n현재 배선: {commands}"
    )
