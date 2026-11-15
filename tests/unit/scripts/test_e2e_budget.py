"""E2E 시간 예산 — 스위트가 스텝 벽의 85% 를 넘으면 red, 75% 부터 경고 (회고 원장 L08).
E2E time budget: red above 85% of the suite step's wall, a warning from 75%.

경계는 «넘으면 잡히는 값» 과 «바로 아래라 무시되는 값» 을 쌍으로 심는다. 벽이나 초를 못 읽으면 red 다(못 재면 red).
Boundaries are planted in pairs (just over → caught, just under → ignored); anything unmeasurable is red.
"""
import pytest

from scripts import e2e_budget as eb

_WALL = 40  # 분 / minutes


def _ci(tmp_path, steps_yaml: str):
    path = tmp_path / "ci.yml"
    path.write_text("jobs:\n  e2e:\n    steps:\n" + steps_yaml, encoding="utf-8")
    return path


_SUITE = "      - name: Run E2E suite\n        timeout-minutes: {wall}\n        run: python -m pytest e2e/\n"


# --- 1. 판정 — 경계 쌍 ------------------------------------------------------------------


@pytest.mark.parametrize("seconds,code,mark", [
    (24 * 60, 0, "✅"),                       # 운영 중앙값 근처 — 예산 안
    (0.75 * _WALL * 60 - 1, 0, "✅"),        # 경고 바로 아래
    (0.75 * _WALL * 60, 0, "⚠️"),            # 경고 시작
    (0.85 * _WALL * 60, 0, "⚠️"),            # 85% 정확히 — 아직 red 아님(«넘으면» red)
    (0.85 * _WALL * 60 + 1, 1, "🔴"),        # 85% 바로 위 — red
    (_WALL * 60 * 2, 1, "🔴"),               # 벽을 넘은 값도 red
])
def test_budget_boundaries(seconds, code, mark):
    got, line = eb.judge(seconds, _WALL)
    assert (got, line[:len(mark)]) == (code, mark), line


@pytest.mark.parametrize("seconds,wall", [(None, _WALL), (1000.0, None), (None, None)])
def test_unmeasured_budget_is_red(seconds, wall):
    code, line = eb.judge(seconds, wall)
    assert code == 1 and line.startswith("🔴"), line


@pytest.mark.parametrize("raw,want", [
    ("1450", 1450.0), ("1450.5", 1450.5),
    ("", None), ("abc", None), ("nan", None), ("inf", None), ("-5", None), ("0", None), (None, None),
])
def test_parse_seconds_accepts_only_finite_positive_numbers(raw, want):
    assert eb.parse_seconds(raw) == want


_START = 1_763_190_000


@pytest.mark.parametrize("started_at,now,want", [
    (str(_START), _START + 1450, 1450.0),
    (str(_START), _START, None),            # 0초 — 스위트가 돌았다고 볼 수 없다
    (str(_START + 60), _START, None),       # 미래의 시작 시각
    ("", _START, None),                     # 앞 스텝이 값을 안 남겼다
    ("abc", _START, None),
    ("nan", _START, None),
])
def test_elapsed_is_now_minus_a_readable_past_start(started_at, now, want):
    assert eb.elapsed_seconds(started_at, now) == want


# --- 2. 벽 읽기 — ci.yml 한 곳에서 ---------------------------------------------------------


def test_real_ci_suite_wall_is_readable():
    """운영 ci.yml 에서 스위트 스텝 벽을 읽는다 — 못 읽으면 CI 의 예산 스텝이 매번 red 다."""
    wall = eb.suite_wall_minutes()
    assert type(wall) is int and wall > 0, wall


def test_wall_is_read_from_the_suite_step(tmp_path):
    assert eb.suite_wall_minutes(_ci(tmp_path, _SUITE.format(wall=40))) == 40


@pytest.mark.parametrize("steps_yaml", [
    "      - name: Other step\n        timeout-minutes: 40\n",           # 스위트 스텝이 없다
    _SUITE.format(wall=40) * 2,                                           # 같은 이름이 둘 — 어느 것인지 모른다
    _SUITE.format(wall='"40"'),                                           # 문자열
    _SUITE.format(wall="true"),                                           # bool
    _SUITE.format(wall=0),
    "      - name: Run E2E suite\n        run: python -m pytest e2e/\n",  # 벽이 없다
])
def test_unreadable_wall_is_none(tmp_path, steps_yaml):
    assert eb.suite_wall_minutes(_ci(tmp_path, steps_yaml)) is None


def test_missing_file_or_job_is_none(tmp_path):
    assert eb.suite_wall_minutes(tmp_path / "absent.yml") is None
    garbled = tmp_path / "garbled.yml"
    garbled.write_bytes(b"jobs:\n  e2e: \xff\xfe\n")  # UTF-8 이 아니다 — 읽다 터지지 않고 None
    assert eb.suite_wall_minutes(garbled) is None
    empty = tmp_path / "empty.yml"
    empty.write_text("", encoding="utf-8")
    assert eb.suite_wall_minutes(empty) is None
    other = tmp_path / "ci.yml"
    other.write_text("jobs:\n  lint:\n    steps: []\n", encoding="utf-8")
    assert eb.suite_wall_minutes(other) is None


# --- 3. main — 종료 코드 · 주석 · 잡 요약 ----------------------------------------------------


@pytest.mark.parametrize("started_at,elapsed,code,annotation", [
    (str(_START), 1000, 0, None),
    (str(_START), int(0.8 * _WALL * 60), 0, "::warning"),
    (str(_START), int(0.9 * _WALL * 60), 1, "::error"),
    ("", 1000, 1, "::error"),
])
def test_main_exit_code_annotation_and_summary(tmp_path, monkeypatch, started_at, elapsed, code, annotation):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    lines = []
    got = eb.main(["--started-at", started_at], ci_path=_ci(tmp_path, _SUITE.format(wall=_WALL)),
                  out=lines.append, now=lambda: _START + elapsed)
    assert got == code, lines
    annotations = [line.split(" ", 1)[0] for line in lines if line.startswith("::")]
    assert annotations == ([annotation] if annotation else []), lines
    assert summary.read_text(encoding="utf-8").splitlines() == [lines[0]]
