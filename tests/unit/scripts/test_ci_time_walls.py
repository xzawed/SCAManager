"""모든 워크플로 잡에 벽(timeout-minutes)이 있고, E2E 는 스텝 벽이 잡 벽보다 먼저 닿는다 (회고 원장 L08).
Every workflow job has a wall; in the E2E job every step after checkout has one, the suite wall leaves room
under the job wall, and the time-budget step runs right after the suite with the seconds it measured.

벽이 없으면 설치 단계 하나가 멈춰도 required 검사가 GitHub 기본 6시간 동안 끝나지 않는다.
Without a wall a single stalled install keeps a required check running for GitHub's default 6 hours.
"""
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOWS = sorted((_ROOT / ".github" / "workflows").glob("*.yml"))
_SUITE = "Run E2E suite"


def _wall(value):
    """양의 정수만 벽이다 — 문자열 · bool · 0 은 벽이 아니다 / only a positive int is a wall."""
    return value if type(value) is int and value > 0 else None


def jobs_without_walls(docs: dict) -> list[str]:
    """{파일 이름: 파싱된 워크플로} 에서 벽 없는 잡의 «파일:잡» 목록 / jobs lacking a wall."""
    return [f"{name}:{job_id}" for name, doc in docs.items()
            for job_id, job in (doc.get("jobs") or {}).items() if _wall(job.get("timeout-minutes")) is None]


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _e2e() -> dict:
    return _load(_ROOT / ".github" / "workflows" / "ci.yml")["jobs"]["e2e"]


def test_every_workflow_job_has_a_wall():
    docs = {path.name: _load(path) for path in _WORKFLOWS}
    jobs = sum(len(doc.get("jobs") or {}) for doc in docs.values())
    assert jobs >= 10, f"잡을 {jobs}개밖에 못 읽었다 — 이 시험이 공허하다"
    assert jobs_without_walls(docs) == []


def test_the_detector_flags_every_kind_of_missing_wall():
    """두 심음 — 벽 있는 잡은 무시되고, 벽 없음 · 0 · 문자열 · bool 은 모두 잡힌다."""
    doc = {"jobs": {"walled": {"timeout-minutes": 10}, "bare": {}, "zero": {"timeout-minutes": 0},
                    "text": {"timeout-minutes": "10"}, "flag": {"timeout-minutes": True}}}
    assert jobs_without_walls({"x.yml": doc}) == ["x.yml:bare", "x.yml:zero", "x.yml:text", "x.yml:flag"]


def test_e2e_steps_have_walls_and_the_suite_wall_fits_under_the_job_wall():
    """준비 스텝이 멈추면 그 스텝이 실패로 끝나고(잡 취소가 아니다), 스위트가 느려지면 스위트 벽이 잡 벽보다 먼저 닿는다."""
    job = _e2e()
    steps = job["steps"]
    unwalled = [step.get("name") for step in steps[1:] if _wall(step.get("timeout-minutes")) is None]
    assert unwalled == [], f"벽 없는 E2E 스텝(체크아웃 뒤): {unwalled}"
    suites = [step for step in steps if step.get("name") == _SUITE]
    assert len(suites) == 1, suites
    job_wall, suite_wall = _wall(job.get("timeout-minutes")), _wall(suites[0].get("timeout-minutes"))
    # 준비 단계가 관측 정상(약 3분)보다 한참 느려져도 스위트 벽이 먼저 닿을 여유
    # Room for a slow-but-not-stalled setup before the job wall preempts the suite wall
    assert job_wall is not None and suite_wall is not None and job_wall >= suite_wall + 15, (job_wall, suite_wall)


def test_budget_step_runs_right_after_the_suite_with_its_measured_seconds():
    """시간 예산 스텝의 배선 — 스위트 스텝이 초를 출력으로 내고, 바로 다음 스텝이 그 값으로 예산 스크립트를 부른다."""
    steps = _e2e()["steps"]
    names = [step.get("name") for step in steps]
    index = names.index(_SUITE)
    suite, budget = steps[index], steps[index + 1]
    assert suite.get("id") == "suite"
    suite_lines = [line.strip() for line in suite["run"].splitlines()]
    assert suite_lines[0] == "start=$(date +%s)"
    assert suite_lines[-1] == 'echo "seconds=$(( $(date +%s) - start ))" >> "$GITHUB_OUTPUT"'
    assert (budget.get("env") or {}).get("SUITE_SECONDS") == "${{ steps.suite.outputs.seconds }}"
    assert budget["run"].split() == ["python", "scripts/e2e_budget.py", "--seconds", '"$SUITE_SECONDS"']
