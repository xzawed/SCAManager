"""분석기 출력 오라클 — 고정 시료의 분석 결과가 바뀌면 red 다 (회고 원장 L03 P2-103).

분석기 판 · 고정 룰 · 설정을 바꾸는 PR 이 «CI 초록» 만으로 운영에 들어가지 않게, 운영 이미지 안에서
`tests/fixtures/analyzer_oracle/` 의 시료를 `analyze_file` 로 분석한 결과(부른 분석기 · 이슈 · 정적 점수)를
커밋된 기대값(`expected.json`)과 대조한다. 다르면 red 이고, 고치는 법은 같은 이미지에서 기대값을 다시 만들어
같은 PR 에 커밋하는 것이다 — 그 diff 가 그 bump 의 점수 영향 증거다. 판만 바뀌고 출력이 같으면 초록이다
(판은 분석 행이 `static_provenance` 로 남기고, 여기서는 기록용으로 찍기만 한다).

시료(`*.sample`)는 일부러 결함을 넣은 **분석 입력**이다 — 실행하지 않는다. 확장자를 `.sample` 로 둬서 이 리포
자체의 검사(CodeQL · SonarCloud · flake8 · eslint)가 코드로 읽지 않게 하고, 분석할 때만 원래 이름을 넘긴다.

운영 이미지 안에서 작업 폴더 /app 으로 돈다 — 분석기가 그 폴더의 설정을 읽는다(운영과 같다). 이미지에는
tests/ · scripts/ 가 없어서 시료는 읽기 전용으로 붙이고 이 파일은 표준 입력으로 넣는다:

  대조       docker run --rm -i -v "$PWD/tests/fixtures/analyzer_oracle:/oracle:ro" <이미지> \\
               python - --corpus /oracle < scripts/analyzer_oracle.py
  다시 만들기 docker run --rm -i -v "$PWD/tests/fixtures/analyzer_oracle:/oracle:ro" <이미지> \\
               python - --corpus /oracle --print < scripts/analyzer_oracle.py \\
               > tests/fixtures/analyzer_oracle/expected.json
  (<이미지> = `docker build -t scam-local .` — 운영 Dockerfile 그대로. Windows Git Bash 는 `MSYS_NO_PATHCONV=1` 과
   `D:/…` 꼴 경로로 붙인다)

exit 0 = 같다 · 1 = 출력이 바뀌었다(diff 를 찍는다) · 2 = 잴 수 없다(미분석 · 바이너리 없음 · 이슈 0건 분석기 · 시료 없음)

Analyzer output oracle (retro ledger L03 P2-103): analyze the fixed corpus inside the production image and compare
invoked analyzers, issues and static scores with the committed expectation. A difference stays red until the
expectation is regenerated in the same PR — that diff is the bump's score-impact evidence. Corpus files are
deliberately defective analysis inputs and are never executed.
"""
from __future__ import annotations

# `src` 는 실행 경로가 정해진 뒤에야 불러온다(아래 sys.path · 표준 입력 실행) — 그래서 함수 안에서 불러온다.
# `src` is importable only once the run mode set the path (below), hence the function-level imports.
# pylint: disable=import-outside-toplevel,import-error

import argparse
import difflib
import json
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

# 점수 모듈이 앱 설정을 불러와 필수 값 셋을 검증한다 — 이 스크립트는 DB · 알림을 쓰지 않으므로 비밀값이 아닌
# 자리 값을 넣는다(이미 있는 값은 그대로 둔다). CI `/health` 스텝과 같은 값이다.
# The scorer imports the app settings, which require three values; this script never uses DB or
# notifications, so non-secret placeholders are set unless real values are already present.
for _key, _value in (("DATABASE_URL", "sqlite:///:memory:"), ("TELEGRAM_BOT_TOKEN", "123:ABC"),
                     ("TELEGRAM_CHAT_ID", "-100123")):
    os.environ.setdefault(_key, _value)
# 파일로 돌리면(리포에서 `py -3 scripts/analyzer_oracle.py`) 리포 뿌리를 import 경로에 넣는다. 표준 입력으로 돌리면
# (이미지 안 `python -`) 작업 폴더(/app)가 이미 경로에 있고 `__file__` 은 `"<stdin>"` 이다(실측) — 그때는 넣지 않는다.
# Repo root on the import path only when run from a real .py file; under `python -`, `__file__` is "<stdin>".
_SELF = Path(globals().get("__file__", ""))
if _SELF.suffix == ".py" and _SELF.is_file():
    sys.path.insert(0, str(_SELF.resolve().parent.parent))

_SUFFIX = ".sample"
_EXPECTED = "expected.json"
# 실행마다 바뀌는 임시 폴더 경로 — 메시지에 섞여 나오는 도구가 있다
# Per-run temporary directory paths that some tools echo in their messages.
_TMP_PATH = re.compile(re.escape(tempfile.gettempdir()) + r"[/\\][^/\\\s'\":]+")
_DIFF_LINES = 400


def corpus_files(corpus: Path) -> list[tuple[str, Path]]:
    """`(원래 이름, 경로)` — `.sample` 을 뗀 상대 경로 순. / (logical name, path), sorted."""
    paths = sorted(p for p in corpus.rglob(f"*{_SUFFIX}") if p.is_file())
    return [(p.relative_to(corpus).as_posix()[: -len(_SUFFIX)], p) for p in paths]


def normalize_message(message: str) -> str:
    """임시 폴더 경로를 `<tmp>` 로 바꾼다. / Replace per-run temp paths with `<tmp>`."""
    return _TMP_PATH.sub("<tmp>", message)


def issue_record(issue) -> dict:
    """이슈 하나를 비교용 사전으로. / One issue as a comparable record."""
    return {
        "tool": str(issue.tool),
        "category": str(issue.category),
        "severity": str(issue.severity),
        "line": int(issue.line or 0),
        "message": normalize_message(str(issue.message)),
    }


def file_report(result, score) -> dict:
    """파일 하나의 결과 — 부른 분석기 · 이슈(정렬) · 정적 점수. / Invoked tools, sorted issues, static scores."""
    issues = sorted((issue_record(i) for i in result.issues),
                    key=lambda r: (r["tool"], r["line"], r["message"], r["severity"], r["category"]))
    return {
        "tools": sorted(set(getattr(result, "invoked_tools", None) or ())),
        "score": {"code_quality": int(score.code_quality_score), "security": int(score.security_score)},
        "issues": issues,
    }


def unmeasured(name: str, result) -> list[str]:
    """이 파일을 «잰 것» 으로 볼 수 없는 이유 — 미분석 · 바이너리 없음. / Why this file was not measured."""
    reasons = []
    if getattr(result, "incomplete", False):
        reasons.append(f"{name}: 미분석(시간 초과 · 크래시) / incomplete")
    for tool in getattr(result, "unavailable_tools", None) or ():
        reasons.append(f"{name}: {tool} 바이너리 없음 / binary absent")
    return reasons


def coverage_gaps(report: dict, required: set[str]) -> list[str]:
    """이슈를 하나도 내지 않은 분석기 — 그 도구의 bump 는 이 오라클이 못 본다. / Analyzers with zero issues."""
    seen = {issue["tool"] for entry in report["files"].values() for issue in entry["issues"]}
    return sorted(required - seen)


def required_tools() -> set[str]:
    """이 환경에서 돌 수 있는 조달 분석기 — 각자 시료에서 이슈를 하나 이상 내야 한다.

    ktlint 는 JVM 이 없으면 어댑터가 돌지 않는다(#1578) — 그때만 뺀다. JVM 이 생기면 다시 요구된다.
    Provisioned analyzers runnable here; ktlint is excused only while no JVM is present.
    """
    from src.analyzer.io.static import PROVISIONED_ANALYZERS, analyzer_binary  # noqa: PLC0415

    return {tool for tool in PROVISIONED_ANALYZERS
            if shutil.which(analyzer_binary(tool)) and (tool != "ktlint" or shutil.which("java"))}


def build_report(files: list[tuple[str, Path]], analyze: Callable, score: Callable) -> tuple[dict, list[str]]:
    """시료 전부를 분석해 `{"files": {이름: 결과}}` 와 «못 잰 이유» 목록을 낸다."""
    report: dict = {"files": {}}
    problems: list[str] = []
    for name, path in files:
        result = analyze(name, path.read_text(encoding="utf-8"))
        problems += unmeasured(name, result)
        report["files"][name] = file_report(result, score([result]))
    return report, problems


def render(report: dict) -> str:
    """기대값 파일 글자 — 키 정렬 · 한 칸 들여쓰기 · 끝 줄바꿈. / Canonical JSON text."""
    return json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def score_changes(expected: dict, actual: dict) -> list[str]:
    """파일별 정적 점수 변화 — diff 위에 요약으로 찍는다. / Per-file static score changes."""
    lines = []
    for name in sorted(set(expected.get("files", {})) | set(actual.get("files", {}))):
        before = expected.get("files", {}).get(name, {}).get("score")
        after = actual.get("files", {}).get(name, {}).get("score")
        if before != after:
            lines.append(f"  {name}: {before} → {after}")
    return lines


def compare(expected_text: str | None, actual: dict) -> tuple[int, str]:
    """기대값과 대조 — `(종료 코드, 찍을 글자)`. / Compare with the expectation; (exit code, text)."""
    actual_text = render(actual)
    if expected_text is None:
        return 2, f"기대값 파일이 없다 — `--print` 로 만들어 커밋한다 / no expectation file ({_EXPECTED})"
    if expected_text == actual_text:
        issues = sum(len(entry["issues"]) for entry in actual["files"].values())
        return 0, f"✅ 출력 같음 — 시료 {len(actual['files'])}개 · 이슈 {issues}건 / output identical"
    try:
        expected = json.loads(expected_text)
    except ValueError:
        expected = {}
    diff = list(difflib.unified_diff(expected_text.splitlines(), actual_text.splitlines(),
                                     "expected.json", "actual", lineterm="", n=2))
    shown = diff[:_DIFF_LINES]
    more = [f"… diff {len(diff) - _DIFF_LINES}줄 더 / more lines"] if len(diff) > _DIFF_LINES else []
    text = "\n".join([
        "🔴 분석기 출력이 기대값과 다르다 — 이 PR 이 분석 결과를 바꾼다 / analyzer output changed",
        "정적 점수 변화 / static score changes:", *(score_changes(expected, actual) or ["  (점수 같음 / none)"]),
        "고치는 법: 같은 이미지에서 `--print` 로 기대값을 다시 만들어 같은 PR 에 커밋한다 — 그 diff 가 점수 영향 증거다.",
        *shown, *more,
    ])
    return 1, text


def main(argv: list[str] | None = None, analyze: Callable | None = None, score: Callable | None = None,
         required: set[str] | None = None) -> int:
    """오라클 실행. / Run the oracle."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", required=True, help="시료 폴더 / corpus folder")
    parser.add_argument("--print", dest="print_only", action="store_true",
                        help="대조하지 않고 기대값 JSON 을 표준 출력으로 / print the expectation JSON instead")
    args = parser.parse_args(argv)

    corpus = Path(args.corpus)
    files = corpus_files(corpus)
    if not files:
        print(f"🔴 시료가 없다: {corpus} / empty corpus", file=sys.stderr)
        return 2
    if analyze is None:
        from src.analyzer.io.static import analyze_file as analyze  # noqa: PLC0415
    if score is None:
        from src.scorer.calculator import calculate_score as score  # noqa: PLC0415
    report, problems = build_report(files, analyze, score)
    problems += [f"{tool}: 시료에서 이슈 0건 — 이 도구의 bump 를 못 본다 / zero issues"
                 for tool in coverage_gaps(report, required_tools() if required is None else required)]
    _print_versions(report)
    if problems:
        print("🔴 잴 수 없다 / not measurable:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 2
    if args.print_only:
        sys.stdout.write(render(report))
        return 0
    expected_path = corpus / _EXPECTED
    expected_text = expected_path.read_text(encoding="utf-8") if expected_path.is_file() else None
    code, text = compare(expected_text, report)
    print(text, file=sys.stderr)
    return code


def _print_versions(report: dict) -> None:
    """기록용 — 이번에 부른 분석기의 판(기대값에는 넣지 않는다). / Versions for the record only."""
    try:
        from src.analyzer.io.static_provenance import ensure_probed, probed_versions  # noqa: PLC0415
    except ImportError:
        return
    tools = sorted({tool for entry in report["files"].values() for tool in entry["tools"]})
    ensure_probed(tools)
    versions = probed_versions()
    print("판 / versions: " + " · ".join(f"{t}={versions.get(t)}" for t in tools), file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
