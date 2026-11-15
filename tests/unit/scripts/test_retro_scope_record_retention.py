"""회고 창이 대화 기록 보존 기간을 넘으면 «안 쟀다» 로 말한다 (회고 원장 L14 P1-24).

## 사고

11-06 회고 창은 52일이었고 대화 기록 보존 기본값은 30일이다. 창 안 109 PR 중 34건(09-16~09-29 머지)의
세션 기록이 이미 없어 그 구간의 사용자 발화 · 승인 · 운영 행위를 원본으로 대조할 수 없었는데, 범위 산출은
`unmeasured: []` 를 냈다 — «안 쟀다» 와 «문제없다» 를 구별하지 못했다.

## 이 파일이 잠그는 것

1. 보존 기간보다 먼저 머지된 창 안 PR 은 `records_expired_prs` 에 들고 `records-older-than-retention` 축이 «안 쟀다» 에 실린다.
2. 대조군 — 보존 기간이 창보다 길면 둘 다 비어 있다(항상 발화하면 아무것도 구별하지 못한다).
3. 보존 일수는 `~/.claude/settings.json` 의 `cleanupPeriodDays`, 없거나 이상하면 기본 30일.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "retro_scope.py"


def _load():
    spec = importlib.util.spec_from_file_location("retro_scope_rr", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rs = _load()


def _run(repo: Path, *args: str, when: dt.datetime | None = None) -> str:
    env = dict(os.environ)
    if when is not None:
        stamp = when.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        env.update(GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True,
                          encoding="utf-8", env=env).stdout.strip()


def _commit(repo: Path, subject: str, when: dt.datetime, path: str = "f.txt") -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text((target.read_text(encoding="utf-8") if target.exists() else "") + subject + "\n",
                      encoding="utf-8")
    _run(repo, "add", path)
    _run(repo, "commit", "-q", "-m", subject, when=when)


@pytest.fixture
def aged_repo(tmp_path, monkeypatch):
    """main: 리포트(#10, 70일 전 · head 기록) → #11(60일 전) → #12(40일 전) → #13(5일 전)  ← origin/main · HEAD."""
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "init", "-q", "-b", "main")
    _run(repo, "config", "user.email", "t@example.com")
    _run(repo, "config", "user.name", "t")
    _run(repo, "config", "commit.gpgsign", "false")
    _commit(repo, "docs: 회고 리포트 (#10)", now - dt.timedelta(days=70), "docs/reports/2026-01-01-retrospective.md")
    _commit(repo, "fix: a (#11)", now - dt.timedelta(days=60))
    _commit(repo, "fix: b (#12)", now - dt.timedelta(days=40))
    _commit(repo, "fix: c (#13)", now - dt.timedelta(days=5))
    _run(repo, "update-ref", "refs/remotes/origin/main", "main")
    monkeypatch.setattr(rs, "_ROOT", repo)
    monkeypatch.setattr(rs, "_REPORTS", repo / "docs" / "reports")
    monkeypatch.setattr(rs, "_gh_json", lambda _a: [])
    monkeypatch.setattr(rs, "report_head", lambda _f: None)
    return repo


def test_prs_merged_before_the_retention_cutoff_are_reported_unmeasured(aged_repo, monkeypatch):
    """🔴 30일 보존이면 60 · 40일 전 머지는 기록 밖이다 — 목록과 축을 싣는다."""
    monkeypatch.setattr(rs, "transcript_retention_days", lambda: 30)
    out = rs.compute(fetched=True)
    assert out["prs"] == [11, 12, 13], out["prs"]
    assert out["records_expired_prs"] == [11, 12], out["records_expired_prs"]
    assert "records-older-than-retention" in out["unmeasured"], out["unmeasured"]


def test_a_window_inside_the_retention_period_reports_nothing(aged_repo, monkeypatch):
    """대조군 — 보존이 창보다 길면 목록도 축도 없다."""
    monkeypatch.setattr(rs, "transcript_retention_days", lambda: 90)
    out = rs.compute(fetched=True)
    assert out["records_expired_prs"] == [], out["records_expired_prs"]
    assert "records-older-than-retention" not in out["unmeasured"], out["unmeasured"]


@pytest.mark.parametrize(("settings", "expected"), [
    ({"cleanupPeriodDays": 7}, 7),
    ({}, 30),
    ({"cleanupPeriodDays": "7"}, 30),
    ({"cleanupPeriodDays": 0}, 30),
    (None, 30),
])
def test_retention_days_come_from_the_claude_settings_file(tmp_path, monkeypatch, settings, expected):
    """보존 일수 = `~/.claude/settings.json` 의 `cleanupPeriodDays` — 없거나 정수가 아니거나 0 이하면 기본 30."""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    if settings is not None:
        (home / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    monkeypatch.setattr(rs.Path, "home", classmethod(lambda cls: home))
    assert rs.transcript_retention_days() == expected
