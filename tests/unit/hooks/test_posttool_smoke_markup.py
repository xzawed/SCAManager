"""편집 뒤 스모크가 템플릿 · CSS · 워크플로도 본다 (회고 원장 이관 K22 P2-31).

## 사고

09-16 회고: «PostToolUse 스모크가 이 사이클의 주 편집면(템플릿 · CSS · 워크플로)을 전혀 보지 않는다 — 결함이 가장 많은
곳에 조기탐지 0». 훅은 `.py`(src · alembic · scripts · 훅)만 받았다.

## 이 파일이 잠그는 것

1. 템플릿 · CSS 편집은 그 파일을 경로 문자열(`"x.html"` · `".../x.html"`)로 적은 tests/unit 시험 파일들을 돌린다.
2. 이름만 닮은 값(`database.html` · `base.html.bak` · `mybase.html`)과 문장 속 언급은 고르지 않는다 — 두 쪽을 함께 심는다.
3. 그런 시험이 없으면 수집 스모크 + «단언 0건» 배너다(거짓 ✅ 금지).
4. 워크플로 편집은 시험을 돌리지 않는다(그 파일을 읽는 시험이 75 초 벽을 넘는다) — YAML 파싱만 보고 그 사실을 배너에
   적는다. 깨진 YAML 은 ❌.
5. 대조군 — docs 편집엔 여전히 발동하지 않는다.
"""
import io
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / ".claude" / "hooks"))

import posttool_pytest_smoke as hook  # noqa: E402


@pytest.mark.parametrize(("path", "named"), [
    ("src/templates/base.html", True),
    ("src/templates/partials/nav.html", True),
    (r"D:\Source\SCAManager\src\static\css\tokens.css", True),
    ("docs/reports/x.html", False),
    ("src/static/js/app.js", False),
    ("src/templates/base.py", False),
    ("e2e/fixtures/x.css", False),
])
def test_named_files_are_templates_and_stylesheets_only(path, named):
    """템플릿 · 스타일만 «이름으로 고르는» 대상이다 — 다른 html · css · js 는 아니다."""
    assert hook.is_named_file(path) is named


# witness-corpus: 시험이 그 파일을 «적었다» 로 볼 꼴과 아닌 꼴 — 경로 문자열 · 작은따옴표 · f-string 경로 대
# 이름만 닮은 값 · 확장자 뒤 꼬리 · 접두 · 문장 속 언급
_NAMING = {
    "test_exact.py": 'P = "base.html"\n',
    "test_single_quote.py": "P = 'base.html'\n",
    "test_path.py": 'P = "src/templates/base.html"\n',
    "test_fstring.py": 'ROOT = "x"\nP = f"{ROOT}/base.html"\n',
}
_NOT_NAMING = {
    "test_database.py": 'P = "database.html"\n',
    "test_backup.py": 'P = "base.html.bak"\n',
    "test_prefix.py": 'P = "mybase.html"\n',
    "test_prose.py": '"""이 시험은 base.html 을 읽지 않는다."""\n',
}


def _repo_with_tests(tmp_path, files):
    unit = tmp_path / "tests" / "unit"
    unit.mkdir(parents=True)
    for name, text in files.items():
        (unit / name).write_text(text, encoding="utf-8")
    return tmp_path


def test_tests_naming_picks_literal_paths_only(tmp_path):
    """🔴 그 파일을 경로 문자열로 적은 시험만 고른다 — 이름만 닮은 값 · 문장 속 언급은 아니다(두 쪽을 함께 심는다)."""
    repo = _repo_with_tests(tmp_path, {**_NAMING, **_NOT_NAMING})
    got = hook.tests_naming("src/templates/base.html", repo)
    assert got == sorted(f"tests/unit/{n}" for n in _NAMING), got


def _run_main(path, monkeypatch, repo):
    captured = []
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_input": {"file_path": path}})))
    monkeypatch.setattr(hook, "checkout_of", lambda _p, _f: repo)
    monkeypatch.setattr(hook, "_run", lambda cmd, cwd: captured.append(cmd) or (0, ""))
    assert hook.main() == 0
    return captured


def test_a_template_edit_runs_the_tests_that_name_it(tmp_path, monkeypatch, capsys):
    """배선 — `main()` 이 템플릿 편집에 발동해 그 파일을 적은 시험들을 단언 실행으로 돌린다."""
    repo = _repo_with_tests(tmp_path, {**_NAMING, **_NOT_NAMING})
    captured = _run_main(str(repo / "src" / "templates" / "base.html"), monkeypatch, repo)
    assert len(captured) == 1, captured
    cmd = captured[0]
    assert sorted(a for a in cmd if a.startswith("tests/unit/")) == sorted(f"tests/unit/{n}" for n in _NAMING), cmd
    assert "--co" not in cmd
    assert "✅" in capsys.readouterr().out


def test_a_stylesheet_no_test_names_falls_back_to_collection(tmp_path, monkeypatch, capsys):
    """그 파일을 적은 시험이 없으면 수집 스모크 + «단언 0건» — 아무것도 안 잰 실행에 ✅ 를 붙이지 않는다."""
    repo = _repo_with_tests(tmp_path, _NOT_NAMING)
    captured = _run_main(str(repo / "src" / "static" / "css" / "orphan.css"), monkeypatch, repo)
    assert captured and "--co" in captured[0], captured
    out = capsys.readouterr().out
    assert "단언 0건" in out and "✅" not in out, out


def test_a_workflow_edit_parses_yaml_and_runs_no_tests(tmp_path, monkeypatch, capsys):
    """🔴 워크플로는 시험을 돌리지 않고 YAML 파싱만 본다 — 깨진 YAML 은 ❌, 성한 YAML 은 «단언 0건» 을 밝힌다."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    good, bad = wf / "ci.yml", wf / "broken.yml"
    good.write_text("name: CI\non: [push]\njobs:\n  a:\n    runs-on: ubuntu-latest\n", encoding="utf-8")
    bad.write_text("name: CI\njobs:\n  a: [unclosed\n", encoding="utf-8")

    assert _run_main(str(good), monkeypatch, tmp_path) == []
    out = capsys.readouterr().out
    assert "YAML" in out and "단언 0건" in out and "❌" not in out, out

    assert _run_main(str(bad), monkeypatch, tmp_path) == []
    out = capsys.readouterr().out
    assert "❌" in out and "YAML" in out, out


def test_docs_edits_still_do_not_fire(tmp_path, monkeypatch, capsys):
    """대조군 — 문서 편집엔 발동하지 않는다(소음 금지)."""
    assert _run_main(str(tmp_path / "docs" / "STATE.md"), monkeypatch, tmp_path) == []
    assert capsys.readouterr().out == ""
