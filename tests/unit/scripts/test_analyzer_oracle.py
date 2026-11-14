"""분석기 출력 오라클(`scripts/analyzer_oracle.py`) — 판정 로직과 커밋된 기대값의 모양 (회고 원장 L03 P2-103).

실물 대조는 운영 이미지 안에서만 뜻이 있다(CI docker 잡 «Analyzer output oracle»). 여기서는 그 판정이
(1) 같으면 0 · 다르면 1 · 못 재면 2 를 내는지, (2) 커밋된 기대값이 시료 전부를 덮고 조달 분석기마다 이슈를
하나 이상 갖는지 — 즉 오라클이 공허하지 않은지 — 를 잰다.

The oracle's verdict logic and the shape of the committed expectation; the real comparison runs in the
production image in the CI docker job.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "analyzer_oracle.py"
_CORPUS = _ROOT / "tests" / "fixtures" / "analyzer_oracle"


def _load():
    spec = importlib.util.spec_from_file_location("_analyzer_oracle", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_analyzer_oracle"] = mod
    spec.loader.exec_module(mod)
    return mod


oracle = _load()


@pytest.fixture(autouse=True)
def _no_version_probe(monkeypatch):
    """판 찍기는 실물 바이너리를 부르고 프로세스 전역 판 캐시를 채운다 — 판정 시험에서는 끈다."""
    monkeypatch.setattr(oracle, "_print_versions", lambda _report: None)


def _issue(tool="pylint", line=1, message="m", severity="warning", category="code_quality"):
    return SimpleNamespace(tool=tool, line=line, message=message, severity=severity, category=category)


def _result(issues=(), tools=("pylint",), incomplete=False, unavailable=()):
    return SimpleNamespace(issues=list(issues), invoked_tools=list(tools), incomplete=incomplete,
                           unavailable_tools=list(unavailable))


def _score(_results):
    return SimpleNamespace(code_quality_score=24, security_score=20)


def _corpus(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = tmp_path / f"{name}.sample"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


# ── 시료 읽기 · 정규화 ────────────────────────────────────────────────────


def test_corpus_names_drop_the_sample_suffix_and_skip_the_expectation(tmp_path):
    corpus = _corpus(tmp_path, {"python/app.py": "x", "docker/Dockerfile": "FROM x"})
    (tmp_path / "expected.json").write_text("{}", encoding="utf-8")
    assert [name for name, _p in oracle.corpus_files(corpus)] == ["docker/Dockerfile", "python/app.py"]


def test_temp_paths_are_normalized():
    """실행마다 바뀌는 임시 폴더 경로가 남으면 같은 출력이 매번 «다름» 이 된다."""
    raw = f"{tempfile.gettempdir()}/tmpab12cd34/analyze.py:3: unused"
    assert oracle.normalize_message(raw) == "<tmp>/analyze.py:3: unused"


def test_file_report_sorts_issues_and_keeps_scores_and_tools():
    result = _result([_issue(tool="pylint", line=9), _issue(tool="bandit", line=2, category="security")],
                     tools=("pylint", "bandit"))
    report = oracle.file_report(result, _score([result]))
    assert [(i["tool"], i["line"]) for i in report["issues"]] == [("bandit", 2), ("pylint", 9)]
    assert report["tools"] == ["bandit", "pylint"]
    assert report["score"] == {"code_quality": 24, "security": 20}


# ── 판정: 같다 0 · 다르다 1 · 못 잰다 2 ─────────────────────────────────────


def _run(tmp_path, analyze, *extra, expected=None, required=frozenset({"pylint"})):
    corpus = _corpus(tmp_path, {"python/app.py": "x = 1\n"})
    if expected is not None:
        (corpus / "expected.json").write_text(expected, encoding="utf-8")
    return oracle.main(["--corpus", str(corpus), *extra], analyze=analyze, score=_score, required=set(required))


def test_identical_output_is_zero_and_a_changed_issue_is_one(tmp_path, capsys):
    """기대값을 만든 출력으로 대조하면 0 — 이슈 글자 하나가 바뀌면 1 이고 diff 와 점수 요약을 찍는다."""
    same = lambda _n, _c: _result([_issue(message="unused import")])  # noqa: E731
    assert _run(tmp_path, same, "--print") == 0
    expected = capsys.readouterr().out
    assert _run(tmp_path, same, expected=expected) == 0
    changed = lambda _n, _c: _result([_issue(message="unused-import (W0611)")])  # noqa: E731
    assert _run(tmp_path, changed, expected=expected) == 1
    err = capsys.readouterr().err
    assert "-     \"message\": \"unused import\"," in err and "+     \"message\": \"unused-import (W0611)\"," in err


def test_a_score_change_is_summarized_above_the_diff(tmp_path, capsys):
    base = lambda _n, _c: _result([_issue()])  # noqa: E731
    _run(tmp_path, base, "--print")
    expected = capsys.readouterr().out
    worse = json.loads(expected)
    worse["files"]["python/app.py"]["score"]["code_quality"] = 25
    assert _run(tmp_path, base, expected=oracle.render(worse)) == 1
    assert "python/app.py: {'code_quality': 25, 'security': 20} → {'code_quality': 24, 'security': 20}" in (
        capsys.readouterr().err)


@pytest.mark.parametrize("result,needle", [
    (_result([_issue()], incomplete=True), "미분석"),
    (_result([_issue()], unavailable=("pylint",)), "바이너리 없음"),
    (_result([], tools=("pylint",)), "이슈 0건"),
], ids=["incomplete", "binary-absent", "vacuous-tool"])
def test_unmeasurable_runs_are_two_and_print_nothing_to_stdout(tmp_path, capsys, result, needle):
    """🔴 못 잰 실행은 «같다» 도 «다르다» 도 아니다 — 2 다. `--print` 도 기대값을 내지 않는다(빈 기대값이 커밋되지 않게)."""
    assert _run(tmp_path, lambda _n, _c: result, "--print") == 2
    out = capsys.readouterr()
    assert out.out == "" and needle in out.err


def test_missing_expectation_and_empty_corpus_are_two(tmp_path, capsys):
    assert _run(tmp_path, lambda _n, _c: _result([_issue()])) == 2
    assert "기대값 파일이 없다" in capsys.readouterr().err
    empty = tmp_path / "empty"
    empty.mkdir()
    assert oracle.main(["--corpus", str(empty)], analyze=lambda *_: None, score=_score, required=set()) == 2


# ── CI 배선 — 대조 모드로, 그 잡이 빌드한 운영 이미지에서 ───────────────────────


_ORACLE_STEP = "Analyzer output oracle (fixed corpus)"


def _oracle_step() -> tuple[dict, list[str]]:
    """오라클 스텝이 정확히 하나 든 잡 — 없거나 둘 이상이면 red. / The job holding exactly one oracle step."""
    import yaml  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    workflow = yaml.safe_load((_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    found = [(job, [s.get("name") for s in job.get("steps", [])]) for job in workflow["jobs"].values()]
    found = [(job, names) for job, names in found if names.count(_ORACLE_STEP)]
    assert len(found) == 1 and found[0][1].count(_ORACLE_STEP) == 1, f"«{_ORACLE_STEP}» 스텝이 정확히 하나가 아니다"
    return found[0]


def test_ci_runs_the_oracle_in_check_mode_on_the_image_it_built():
    """🔴 CI 스텝이 `--print`(다시 만들기)로 부르면 오라클은 늘 0 이다 — 대조 모드 · 그 잡이 빌드한 이미지 ·
    시료 읽기 전용 마운트 · 표준 입력의 이 스크립트, 그 밖의 꼴(연산자 · `|| true` · 조건 · 실패 무시)은 red.
    Grok claim-review(2556408d)가 `--print` 는 기대값을 보지 않고 0 을 낸다고 짚었다 — 그 모드가 CI 에 오지 않게 고정한다.
    """
    import shlex  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    job, names = _oracle_step()
    step = job["steps"][names.index(_ORACLE_STEP)]
    build = next(s for s in job["steps"] if s.get("name") == "Build image")
    assert names.index("Build image") < names.index(_ORACLE_STEP)
    assert "if" not in step and not step.get("continue-on-error"), "조건 · 실패 무시가 붙었다"
    tokens = shlex.split(step["run"].replace("\\\n", " "), posix=True)
    assert tokens == [
        "docker", "run", "--rm", "-i", "-v", "$PWD/tests/fixtures/analyzer_oracle:/oracle:ro",
        build["with"]["tags"], "python", "-", "--corpus", "/oracle", "<", "scripts/analyzer_oracle.py",
    ], tokens


# ── 커밋된 기대값 — 시료 전부 · 분석기마다 이슈 ───────────────────────────────


def _expected() -> dict:
    return json.loads((_CORPUS / "expected.json").read_text(encoding="utf-8"))


def test_expectation_covers_exactly_the_corpus():
    """시료를 더하거나 지우고 기대값을 다시 만들지 않으면 여기서 red — 이미지 밖에서도 잡는다."""
    assert set(_expected()["files"]) == {name for name, _p in oracle.corpus_files(_CORPUS)}


def test_expectation_is_canonical_text():
    """기대값은 `--print` 가 낸 글자 그대로다 — 손으로 고친 기대값은 대조가 늘 «다름» 이 된다."""
    text = (_CORPUS / "expected.json").read_text(encoding="utf-8")
    assert text == oracle.render(json.loads(text))


def test_every_provisioned_analyzer_has_an_issue_in_the_expectation():
    """🔴 조달 분석기마다 기대값에 이슈가 하나 이상 있다 — 없으면 그 도구의 bump 를 오라클이 못 본다.

    ktlint 만 뺀다: 운영 이미지에 JVM 이 없어 어댑터가 돌지 않는다(#1578 · 스크립트의 `required_tools`).
    """
    from src.analyzer.io.static import PROVISIONED_ANALYZERS  # noqa: PLC0415

    seen = {i["tool"] for entry in _expected()["files"].values() for i in entry["issues"]}
    assert sorted(PROVISIONED_ANALYZERS - {"ktlint"} - seen) == []
