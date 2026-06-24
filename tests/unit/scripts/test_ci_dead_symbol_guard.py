"""CI dead-symbol 가드 정합 (회고 C1 — 자초 CodeQL cascade 근본 차단).
CI dead-symbol guard integrity (retro C1 — root fix for the self-inflicted CodeQL cascade).

tests/ 미사용 import(F401)·변수(F841)가 pre-merge 에서 안 잡혀 main full-scan CodeQL 에 사후
포착 → 별도 fix PR(#516/#517/#520/#521/#522) 을 반복 유발한 cascade 를 차단한다(A2: PR diff 한정).

🔴 불변식은 반드시 `lint-changed-tests` job 영역에 한정해 검증한다 — ci.yml 전체 문자열 검색은
다른 job(secret-scan 의 base.sha 등)의 동일 토큰에 의해 false-pass 한다(Codex mutual 적발).
🔴 flake8 호출은 반드시 `--isolated` 동반 — 없으면 setup.cfg per-file-ignore(`tests/*:F401,F841`)가
검사를 무력화해 항상 통과(false-pass)한다(실증 확인).
Assertions MUST be scoped to the lint-changed-tests job (a whole-file search false-passes on other
jobs' identical tokens — Codex mutual finding). The flake8 call MUST use `--isolated`, else the
setup.cfg per-file-ignore silently masks the check (empirically verified).
"""
import re
from pathlib import Path

import yaml

# 리포 루트 / repo root
_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"


def _lint_job_text() -> str:
    """ci.yml 에서 lint-changed-tests job 만 추출해 텍스트로 직렬화 — 다른 job 토큰 누출 차단.
    Extract only the lint-changed-tests job and serialize it (blocks token leakage from other jobs)."""
    data = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    job = data["jobs"].get("lint-changed-tests")
    assert job is not None, "lint-changed-tests job 부재 / job missing"
    return yaml.safe_dump(job, allow_unicode=True)


def test_lint_job_uses_isolated_dead_symbol_check():
    """lint job 이 flake8 --isolated --select=F401,F841 로 검사한다 (순서 무관)."""
    job = _lint_job_text()
    has = re.search(
        r"flake8[^\n]*--isolated[^\n]*--select=F401,F841"
        r"|flake8[^\n]*--select=F401,F841[^\n]*--isolated",
        job,
    )
    assert has, "lint-changed-tests job 에 flake8 --isolated --select=F401,F841 누락"


def test_lint_job_is_pr_diff_scoped():
    """가드는 PR 변경 파일 한정(A2) — 전체 tests/ 일괄/`find` 스캔 금지(기존 legacy 76건 회피).
    full-scan 이면 즉시 실패하므로 base.sha diff 로 변경 파일만 검사해야 한다."""
    job = _lint_job_text()
    assert "github.event.pull_request.base.sha" in job, "lint job 이 PR base SHA diff 미사용 (변경 파일 스코프 아님)"
    assert "git diff" in job and "tests/" in job, "lint job 이 변경 파일 diff 미산출"
    # 🔴 flake8 는 변경 파일 변수($changed)에 실행해야 함 — 리터럴 전체 경로(`... tests/`) 스캔 금지.
    #    (긍정 단언: `tests/\b` 부정 정규식은 `/`가 비단어문자라 \b 미매칭 = 무력 — Codex Round 2 적발.)
    #    flake8 must run on the $changed var (diff result), not a literal full path (Codex R2: \b after '/' never matches).
    assert re.search(r"--select=F401,F841\s+\$changed\b", job), \
        "flake8 가 $changed(변경 파일)이 아닌 리터럴 경로를 스캔 — PR diff 한정이어야 함"
    # find 기반 전체 스캔 금지 (diff 우회 변조 차단 — Codex mutual 적발 케이스)
    assert "find tests" not in job, "find 기반 전체 스캔 금지 — git diff 변경 파일 한정이어야 함"


def test_lint_job_is_pr_only():
    """lint job 은 PR 이벤트 한정 — push(main)에서 base.sha 부재로 깨지지 않도록."""
    job = _lint_job_text()
    assert "pull_request" in job, "lint job 이 PR-only(if) 아님 — push 에서 깨질 수 있음"
