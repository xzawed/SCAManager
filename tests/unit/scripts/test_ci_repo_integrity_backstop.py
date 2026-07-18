"""repo-integrity CI 백스톱 배선 가드 (회고 2026-07-18 P2#36 — pre-commit 우회 봉인).
repo-integrity CI backstop wiring guard (retro 2026-07-18 P2#36 — seals pre-commit bypass).

4 whole-repo 상태 가드(docs↔README 배지·cycle-history TOC·config↔env-vars·RepoConfig 3-layer)는
pre-commit-only 라 `--no-verify`·미설치 시 우회됐다. `ci.yml` `repo-integrity` job 이 서버측 백스톱으로
이들을 실행한다 — 이 가드는 그 배선이 조용히 제거되지 않도록 잠근다(test_ci_dead_symbol_guard 선례).
The 4 whole-repo guards were pre-commit-only (bypassable). This locks the CI backstop wiring.
"""
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"

# 서버측 백스톱으로 실행돼야 하는 whole-repo stdlib 가드 (memory-refs·bilingual 은 CI 부적합이라 제외).
# Whole-repo stdlib guards that must run as the server-side backstop (memory-refs/bilingual excluded).
_BACKSTOP_GUARDS = (
    "check_docs_sync.py",
    "check_toc_anchors.py",
    "check_env_vars_sync.py",
    "check_config_5way_sync.py",
)


def _repo_integrity_runs():
    ci = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    job = ci["jobs"].get("repo-integrity")
    assert job is not None, "ci.yml 에 repo-integrity 백스톱 job 누락 (P2#36 회귀)"
    return [s.get("run", "") for s in job["steps"] if "run" in s]


def test_repo_integrity_job_exists():
    """🔴 repo-integrity job 존재 — pre-commit 우회 서버측 백스톱."""
    _repo_integrity_runs()  # 없으면 assert


def test_repo_integrity_runs_all_four_guards():
    """🔴 4 whole-repo 가드가 전부 백스톱 job 에서 실행됨 (조용한 제거 차단)."""
    runs = _repo_integrity_runs()
    for guard in _BACKSTOP_GUARDS:
        assert any(guard in r for r in runs), (
            f"repo-integrity job 이 {guard} 미실행 — pre-commit 우회 시 봉인 갭"
        )


def test_backstop_runs_on_push_and_pr():
    """🔴 백스톱은 push+PR 양쪽 실행 (main drift 도 잡도록 — PR-only 조건 부재)."""
    ci = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    job = ci["jobs"]["repo-integrity"]
    # PR-only(`if: github.event_name == 'pull_request'`) 이면 main push drift 를 놓친다.
    assert "if" not in job or "pull_request" not in str(job.get("if", "")), (
        "repo-integrity 가 PR-only 로 제한됨 — main push drift 미검(whole-repo 백스톱은 양쪽 실행)"
    )
