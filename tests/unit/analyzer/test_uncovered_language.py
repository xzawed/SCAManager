"""정적 분석기가 **등록조차 안 된** 언어를 가시화하는 봉인 (2026-07-31, 사용자 결정 = 가시화만).

Surface languages that have no registered analyzer at all — visibility, never gating.

## 왜 필요한가 (실측)

인식 언어 47개 중 **21개**(lua·perl·haskell·r·julia·elm·erlang·zig·ocaml·graphql·toml·xml 등)는
지원 분석기가 등록돼 있지 않다. 그 파일만 바뀐 PR 은 code_quality 25/25 + security 20/20 =
**45/45 만점**을 받는데, 이는 "분석했더니 깨끗함" 이 아니라 **"제품이 이 언어를 분석하지 않음"** 이다.

## 경계 (3-way 구분 — 섞이면 사유를 알 수 없다)

🔴 **2026-08-01 정정 (backlog R21, 사용자 결정 = 옵션 C)** — 아래 표의 2행이 바뀌었다.
이전 판은 "바이너리 부재 = 조달 문제라 고칠 수 있음 → 차단" 이었는데, **실측 결과 등록
25 분석기 중 9종이 배포 파일 어디에도 조달 흔적이 없었다**(clippy·dart_analyze·
dotnet_format·phpstan·psscriptanalyzer·stylelint·swiftlint·buf_lint·htmlhint).
"고칠 수 있다" 는 전제가 거짓이었고, 그 결과 rust·dart·C#·php·powershell·css/scss·
swift·protobuf·html 리포는 **이 문서가 막으려던 바로 그 영구 차단**에 걸려 있었다.

| 상황 | 필드 | 게이트 |
|------|------|--------|
| 지원 분석기 0개 (제품 미커버) | `uncovered_language` | **차단 안 함** — 조달로 고칠 수 없음 |
| **조달 계약 안** 도구가 부재 | `unavailable_tools` + `incomplete` | **차단** — 실제 배포 회귀 |
| **조달 계약 밖** 도구만 부재 | `uncovered_language` | **차단 안 함** — 제품 미제공 |
| 비-코드 파일(.txt·.md) | 없음 | 해당 없음 |

차단하지 않는 이유: 손댈 수 없는 사유로 막히면 그건 게이트가 아니라 벽이다. 계약은
`src/analyzer/io/static.py::PROVISIONED_ANALYZERS` 이고, 실제 조달 파일과의 대조 가드는
`tests/unit/analyzer/test_procurement_contract.py` 다.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import pytest

from src.analyzer.io.static import analyze_file


@pytest.mark.parametrize("filename, source, lang", [
    ("stats.r", "x <- 1\n", "r"),
    ("init.lua", "local x = 1\n", "lua"),
    ("Main.hs", "main = return ()\n", "haskell"),
])
def test_uncovered_language_is_recorded_but_does_not_block(filename, source, lang):
    """🔴 기록은 하되 `incomplete` 는 세우지 않는다 — 세우면 해당 언어 auto-merge 가 영구 불가."""
    r = analyze_file(filename, source)
    assert r.uncovered_language == lang
    assert r.incomplete is False, "미커버 언어는 차단 대상이 아니다(사용자 결정: 가시화만)"


@pytest.mark.parametrize("filename, source", [
    ("notes.txt", "just text\n"),
    ("README.md", "# hi\n"),
])
def test_non_code_files_are_not_flagged(filename, source):
    """비-코드(확장자 맵 밖 → language='unknown')는 미커버로 세지 않는다 — 노이즈 방지."""
    r = analyze_file(filename, source)
    assert r.uncovered_language is None


def test_covered_language_is_not_flagged():
    """대조군 — pylint 등이 지원하는 python 은 미커버가 아니다."""
    r = analyze_file("app.py", "import os\nx = 1\n")
    assert r.uncovered_language is None


def test_result_dict_aggregates_uncovered_languages():
    """🔴 배선 — analyze_file 이 기록해도 result dict 에 실려야 배너가 뜬다(정의≠배선)."""
    from types import SimpleNamespace

    from src.worker.pipeline import build_analysis_result_dict

    results = [analyze_file("stats.r", "x <- 1\n"), analyze_file("init.lua", "local x = 1\n")]
    ai = SimpleNamespace(
        status="success", truncated=False, summary="", suggestions=[],
        commit_message_feedback="", code_quality_feedback="", security_feedback="",
        direction_feedback="", test_feedback="", file_feedbacks=[],
    )
    score = SimpleNamespace(total=89, grade="B", breakdown={})
    d = build_analysis_result_dict(ai, score, results, "pr")
    assert d["static_uncovered_languages"] == ["lua", "r"], "정렬·중복제거된 언어 목록이 실려야 한다"
