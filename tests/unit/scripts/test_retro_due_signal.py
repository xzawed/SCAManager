"""회고 착수 신호 — 직전 회고 뒤 머지가 임계를 넘으면 세션 시작 때 한 줄로 알린다 (회고 원장 L15 · 사용자 11-15 결정).

## 사고

«임계 15 PR» 은 09-07 회고 리포트에만 있었고 그것을 내는 표면은 하나도 없었다. 세 회고 연속 «신호 부재» 가
확정됐는데도 창은 45 → 55 → 109 PR 로 자랐다(P1-2 · P2-29 · P2-97).

## 이 파일이 잠그는 것

1. 창이 임계 이상이면 `--signal` 이 한 줄을 낸다 — 임계 미만이면 아무것도 내지 않는다(대조군 — 늘 내면 아무것도 안 알린다).
2. 신호는 네트워크를 쓰지 않는다(세션 시작을 막지 않게) — `gh` 를 부르면 red.
3. 범위를 못 재면 조용히 넘기지 않고 «못 쟀다» 한 줄을 낸다. 어느 경우든 종료 코드는 0(세션을 막지 않는다).
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "retro_scope.py"


def _load():
    spec = importlib.util.spec_from_file_location("retro_scope_sig", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rs = _load()


def _run(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def _repo_with_prs(tmp_path: Path, n: int) -> Path:
    """main: 리포트(#100 · head 기록 없음) → #101 … #(100+n)  ← origin/main · HEAD."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "init", "-q", "-b", "main")
    _run(repo, "config", "user.email", "t@example.com")
    _run(repo, "config", "user.name", "t")
    _run(repo, "config", "commit.gpgsign", "false")
    report = repo / "docs" / "reports" / "2026-01-01-retrospective.md"
    report.parent.mkdir(parents=True)
    report.write_text("x\n", encoding="utf-8")
    _run(repo, "add", ".")
    _run(repo, "commit", "-q", "-m", "docs: 회고 리포트 (#100)")
    for i in range(1, n + 1):
        (repo / "f.txt").write_text(f"{i}\n", encoding="utf-8")
        _run(repo, "add", "f.txt")
        _run(repo, "commit", "-q", "-m", f"fix: {i} (#{100 + i})")
    _run(repo, "update-ref", "refs/remotes/origin/main", "main")
    return repo


@pytest.fixture
def no_network(monkeypatch):
    def _forbidden(_args):
        raise AssertionError("신호 모드가 gh(네트워크)를 불렀다 — 세션 시작이 막힐 수 있다")
    monkeypatch.setattr(rs, "_gh_json", _forbidden)


def _signal(monkeypatch, capsys, repo: Path) -> tuple[int, str]:
    monkeypatch.setattr(rs, "_ROOT", repo)
    monkeypatch.setattr(rs, "_REPORTS", repo / "docs" / "reports")
    monkeypatch.setattr(sys, "argv", ["retro_scope.py", "--signal"])
    code = rs.main()
    return code, capsys.readouterr().out


def test_a_window_at_the_threshold_prints_the_signal(tmp_path, monkeypatch, capsys, no_network):
    """🔴 임계 이상이면 한 줄 — PR 수 · 임계 · 다음 행동이 들어 있다."""
    repo = _repo_with_prs(tmp_path, rs.RETRO_THRESHOLD)
    code, out = _signal(monkeypatch, capsys, repo)
    assert code == 0
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 1, f"신호는 한 줄이어야 한다: {out!r}"
    assert f"{rs.RETRO_THRESHOLD} PR" in lines[0] and "retro_scope.py" in lines[0], lines[0]


def test_a_window_below_the_threshold_prints_nothing(tmp_path, monkeypatch, capsys, no_network):
    """대조군 — 임계 미만이면 아무것도 내지 않는다."""
    repo = _repo_with_prs(tmp_path, rs.RETRO_THRESHOLD - 1)
    code, out = _signal(monkeypatch, capsys, repo)
    assert code == 0
    assert out.strip() == "", f"임계 미만인데 무언가를 냈다: {out!r}"


def test_an_unmeasurable_scope_says_so_and_still_exits_zero(tmp_path, monkeypatch, capsys, no_network):
    """범위를 못 재면(리포트 없음) «못 쟀다» 한 줄 — 조용한 0줄은 «창이 작다» 와 구별되지 않는다."""
    repo = _repo_with_prs(tmp_path, 3)
    (repo / "docs" / "reports" / "2026-01-01-retrospective.md").unlink()
    code, out = _signal(monkeypatch, capsys, repo)
    assert code == 0
    assert "못 쟀다" in out, out
