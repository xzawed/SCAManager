"""CI dead-symbol 가드 정합 (회고 C1 — 자초 CodeQL cascade 근본 차단).
CI dead-symbol guard integrity (retro C1 — root fix for the self-inflicted CodeQL cascade).

tests/ 미사용 import(F401)·변수(F841)가 pre-merge 에서 안 잡혀 main full-scan CodeQL 에 사후
포착 → 별도 fix PR(#516/#517/#520/#521/#522) 을 반복 유발한 cascade 를 차단한다(A2: PR diff 한정).

🔴 불변식 검증 3중 봉인 (Codex mutual R1~R3 적발 반영):
  (R1) lint-changed-tests job 영역에만 한정 — ci.yml 전체 검색은 다른 job(secret-scan base.sha)
       토큰으로 false-pass.
  (R2) flake8 가 변경 파일 변수 `$changed` 에 실행됨을 긍정 단언 — `tests/\b` 부정 정규식은
       `/`가 비단어문자라 \b 미매칭 = 무력.
  (R3) run: 스크립트의 셸 주석 제거 후 매칭 — 정답 명령을 주석 decoy 로 넣고 실제론 full-scan 하는
       comment false-pass 봉인 (#936 학습 — _strip_comments 동일 패턴).
Three-layer sealing from Codex mutual R1-R3: scope to the lint job, assert flake8 runs on $changed,
and strip shell comments before matching (so a decoy command in a comment can't false-pass).
"""
import re
from pathlib import Path

import yaml

# 리포 루트 / repo root
_ROOT = Path(__file__).resolve().parents[3]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"


def _lint_job() -> dict:
    """ci.yml 에서 lint-changed-tests job 만 추출 — 다른 job 토큰 누출 차단 (R1).
    Extract only the lint-changed-tests job (blocks token leakage from other jobs)."""
    data = yaml.safe_load(_CI.read_text(encoding="utf-8"))
    job = data["jobs"].get("lint-changed-tests")
    assert job is not None, "lint-changed-tests job 부재 / job missing"
    return job


def _lint_run_code() -> str:
    """lint job 의 run: 스크립트만 합치고 셸 주석 제거 — 주석 decoy false-pass 봉인 (R3/#936).
    Concatenate only the lint job's run: scripts with shell comments stripped (R3/#936 sealing)."""
    job = _lint_job()
    runs = "\n".join(
        s["run"] for s in job.get("steps", []) if isinstance(s, dict) and "run" in s
    )
    # 셸 주석 제거 — 줄 시작 또는 공백 뒤 `#` 부터 줄 끝까지 (run 블록은 셸, `#` = 주석).
    # Strip shell comments — `#` at line-start or after whitespace to EOL (run block is shell).
    return re.sub(r"(?m)(?:^|\s)#.*$", "", runs)


def test_lint_job_uses_isolated_dead_symbol_check():
    """lint job 의 실행 명령이 flake8 --isolated --select=F401,F841 을 사용한다 (주석 제외, 순서 무관)."""
    code = _lint_run_code()
    has = re.search(
        r"flake8[^\n]*--isolated[^\n]*--select=F401,F841"
        r"|flake8[^\n]*--select=F401,F841[^\n]*--isolated",
        code,
    )
    assert has, "lint-changed-tests 실행 명령에 flake8 --isolated --select=F401,F841 누락"


def test_lint_job_is_pr_diff_scoped():
    """가드는 PR 변경 파일 한정(A2) — flake8 가 변경 파일 변수 $changed 에 실행돼야 함.
    리터럴 전체 경로(`... tests/`)·find 전체 스캔이면 기존 legacy 76건으로 즉시 실패."""
    code = _lint_run_code()
    assert "github.event.pull_request.base.sha" in code, "lint job 이 PR base SHA diff 미사용 (변경 파일 스코프 아님)"
    assert "git diff" in code and "tests/" in code, "lint job 이 변경 파일 diff 미산출"
    # 🔴 flake8 는 변경 파일 변수($changed)에 실행 — 리터럴 경로 full-scan 금지 (R2 긍정 단언).
    assert re.search(r"--select=F401,F841\s+\$changed\b", code), \
        "flake8 가 $changed(변경 파일)이 아닌 리터럴 경로를 스캔 — PR diff 한정이어야 함"
    # find 기반 전체 스캔 금지 (diff 우회 변조 차단 — R1 적발 케이스)
    assert "find tests" not in code, "find 기반 전체 스캔 금지 — git diff 변경 파일 한정이어야 함"


def test_lint_job_is_pr_only():
    """lint job 은 PR 이벤트 한정 — push(main)에서 base.sha 부재로 깨지지 않도록 (job if 단언)."""
    job = _lint_job()
    assert "pull_request" in str(job.get("if", "")), "lint job 이 PR-only(if) 아님 — push 에서 깨질 수 있음"
