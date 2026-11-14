"""정적 분석 출처 — 분석 행이 어느 빌드 · 어느 분석기 판 · 어느 고정 룰로 만들어졌는지 (회고 원장 L03 P2-104).

분석 행에 이것이 없으면 «분석기를 올린 배포 전후로 운영 분포를 대조» 하는 검증은 행을 분석기 판으로
나눌 수 없어 답을 못 낸다. 빌드 커밋만으로는 모자라다 — Dockerfile 은 apt 분석기와 Node · Python 패치 판을
핀하지 않고 Railway 는 배포마다 이미지를 새로 빌드한다. 그래서 실제로 부른 바이너리의 `--version` 도 남긴다.

Static-analysis provenance (retro ledger L03 P2-104): build commit + the `--version` of every analyzer
actually invoked + the vendored semgrep ruleset, recorded on each analysis row.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("SESSION_SECRET", "0123456789abcdef0123456789abcdef")

import json  # noqa: E402
import subprocess  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402

from src.analyzer.io import static_provenance as sp  # noqa: E402
from src.analyzer.io.static import StaticAnalysisResult, _run_analyzers  # noqa: E402
from src.analyzer.pure.registry import AnalyzeContext  # noqa: E402

_SHA = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    """판 캐시는 프로세스 전역이다 — 시험마다 빈 캐시로 시작한다. / Each test starts with an empty cache."""
    monkeypatch.setattr(sp, "_VERSIONS", {})


def _done(stdout: str = "", stderr: str = "", rc: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


def _results(*tool_lists: list[str]) -> list[StaticAnalysisResult]:
    out = []
    for i, tools in enumerate(tool_lists):
        r = StaticAnalysisResult(filename=f"f{i}.py")
        r.invoked_tools = list(tools)
        out.append(r)
    return out


# ── 파일마다 «실제로 부른» 분석기를 남긴다 ────────────────────────────────


class _Fake:  # pylint: disable=too-few-public-methods
    """레지스트리 어댑터 더블 — 지원 · 조달 · 실행 결과를 정해 준다."""

    category = "code_quality"

    def __init__(self, name: str, *, supports: bool = True, enabled: bool = True, raises: bool = False):
        self.name = name
        self._supports, self._enabled, self._raises = supports, enabled, raises

    def supports(self, _ctx) -> bool:
        return self._supports

    def is_enabled(self, _ctx) -> bool:
        return self._enabled

    def run(self, _ctx) -> list:
        if self._raises:
            raise RuntimeError("boom")
        return []


def test_invoked_tools_are_the_analyzers_actually_called():
    """부른 것(성공 · 크래시)만 남는다 — 끈 것 · 바이너리 없는 것 · 이 언어를 지원 안 하는 것은 빠진다.

    크래시한 도구도 «부른» 도구다: 그 파일은 이미 미분석(incomplete)으로 표시되고, 판은 원인을 읽는 데 쓴다.
    Called analyzers only (success or crash); opted-out, absent and unsupported ones are left out.
    """
    class _Cfg:  # pylint: disable=too-few-public-methods
        disabled_tools = ["opted"]

    ctx = AnalyzeContext(filename="a.py", content="x", language="python", is_test=False,
                         tmp_path="/tmp/a.py", repo_config=_Cfg())  # nosec B108
    fakes = [_Fake("ran"), _Fake("crashed", raises=True), _Fake("opted"),
             _Fake("absent", enabled=False), _Fake("other-language", supports=False)]
    result = StaticAnalysisResult(filename="a.py")
    with patch("src.analyzer.io.static.REGISTRY", fakes):
        _run_analyzers(ctx, result)
    assert result.invoked_tools == ["ran", "crashed"]
    # 대조 — 크래시는 따로 미분석으로 남는다(이 기록과 별개 축)
    assert result.incomplete is True and result.unavailable_tools == ["absent"]


def test_invoked_tools_is_a_union_over_files_sorted():
    """행 하나 = 분석 하나 — 파일마다 부른 도구의 합집합을 정렬해 싣는다."""
    assert sp.invoked_tools(_results(["semgrep", "pylint"], ["pylint", "flake8"], [])) == [
        "flake8", "pylint", "semgrep"]
    # 필드가 없는 더블(옛 시험의 결과 객체)도 빈 것으로 읽는다
    assert sp.invoked_tools([SimpleNamespace(filename="x")]) == []


# ── `--version` 읽기 ──────────────────────────────────────────────────────

# 실측 꼴 — CI docker 잡(«Analyzers run as the runtime user with the pinned versions»)이 운영 이미지
# 안에서 찍은 출력. 둘째 줄에 결과를 바꾸는 하위 판(pylint 의 astroid · tflint 의 룰셋)이 있다.
_REAL_OUTPUTS = [
    ("pylint", "pylint 4.1.3\nastroid 4.3.4\nPython 3.12.3 (main, Aug 31 2026, 10:18:26) [GCC 13.3.0]\n",
     "pylint 4.1.3 astroid 4.3.4"),
    ("flake8", "7.5.0 (mccabe: 0.7.0, pycodestyle: 2.15.0, pyflakes: 4.1.0) CPython 3.12.3 on\nLinux\n",
     "7.5.0 (mccabe: 0.7.0, pycodestyle: 2.15.0, pyflakes: 4.1.0) CPython 3.12.3 on Linux"),
    ("tflint", "TFLint version 0.64.0\n+ ruleset.terraform (0.15.0-bundled)\n",
     "TFLint version 0.64.0 + ruleset.terraform (0.15.0-bundled)"),
    ("shellcheck", "ShellCheck - shell script analysis tool\nversion: 0.9.0\nlicense: GNU General Public "
                   "License, version 3\nwebsite: https://www.shellcheck.net\n",
     "ShellCheck - shell script analysis tool version: 0.9.0"),
    ("eslint", "v9.39.5\n", "v9.39.5"),
]


@pytest.mark.parametrize("tool,stdout,expected", _REAL_OUTPUTS, ids=[t for t, _o, _e in _REAL_OUTPUTS])
def test_version_is_the_first_two_lines_of_the_real_output(tool, stdout, expected):
    """앞 두 줄을 공백 하나로 이어 싣는다 — 하위 판이 남고, 라이선스 · 웹사이트 줄은 빠진다."""
    with patch.object(sp.shutil, "which", return_value=f"/usr/bin/{tool}"), \
         patch.object(sp.subprocess, "run", return_value=_done(stdout=stdout)) as run:
        assert sp.read_version(tool) == expected
    assert run.call_args.args[0] == [f"/usr/bin/{tool}", "--version"]


def test_version_uses_stderr_only_when_stdout_is_empty():
    """판을 stderr 에 찍는 도구가 있다. 🔴 stdout 이 있으면 stderr(경고 줄)는 섞지 않는다 —
    섞으면 «새 판이 나왔다» 같은 경고가 나타나는 날 같은 바이너리의 판 글자가 바뀐다.
    """
    with patch.object(sp.shutil, "which", return_value="/usr/bin/x"):
        with patch.object(sp.subprocess, "run", return_value=_done(stderr="x version 1.2.3\n")):
            assert sp.read_version("x") == "x version 1.2.3"
        with patch.object(sp.subprocess, "run",
                          return_value=_done(stdout="1.184.0\n", stderr="A new version is available\n")):
            assert sp.read_version("x") == "1.184.0"


@pytest.mark.parametrize("outcome", [
    _done(stdout="1.0.0\n", rc=2),
    _done(stdout="  \n\n"),
    subprocess.TimeoutExpired(cmd="x", timeout=1),
    PermissionError("denied"),
], ids=["nonzero-exit", "blank-output", "timeout", "oserror"])
def test_unreadable_version_is_none(outcome):
    """못 읽으면 None(모름)이다 — 예외로 올리지 않는다. 이 기록은 점수 · 게이트에 닿지 않는다."""
    kwargs = {"side_effect": outcome} if isinstance(outcome, BaseException) else {"return_value": outcome}
    with patch.object(sp.shutil, "which", return_value="/usr/bin/x"), \
         patch.object(sp.subprocess, "run", **kwargs):
        assert sp.read_version("x") is None


def test_absent_binary_is_none_without_spawning():
    with patch.object(sp.shutil, "which", return_value=None), \
         patch.object(sp.subprocess, "run") as run:
        assert sp.read_version("x") is None
    run.assert_not_called()


def test_long_version_text_is_capped():
    with patch.object(sp.shutil, "which", return_value="/usr/bin/x"), \
         patch.object(sp.subprocess, "run", return_value=_done(stdout="v" + "9" * 500 + "\n")):
        assert len(sp.read_version("x")) == sp._VERSION_CHARS  # pylint: disable=protected-access


# ── 프로세스마다 도구당 한 번 ──────────────────────────────────────────────


def test_versions_are_read_once_per_tool_per_process():
    """두 번째 분석은 다시 부르지 않는다. 실패(None)도 기억한다 — 깨진 바이너리를 분석마다 다시 부르지 않는다."""
    calls = []

    def fake_read(tool):
        calls.append(tool)
        return None if tool == "broken" else f"{tool} 1.0"

    with patch.object(sp, "read_version", side_effect=fake_read):
        sp.ensure_probed(["pylint", "broken"])
        sp.ensure_probed(["pylint", "broken", "flake8"])
    assert calls == ["broken", "pylint", "flake8"]
    assert sp.probed_versions() == {"pylint": "pylint 1.0", "broken": None, "flake8": "flake8 1.0"}


def test_probed_versions_is_a_copy():
    sp.probed_versions()["pylint"] = "planted"
    assert "pylint" not in sp.probed_versions()


# ── 행에 싣는 모양 ────────────────────────────────────────────────────────


def test_provenance_always_emits_its_three_keys(monkeypatch):
    """🔴 키는 늘 낸다 — 조건부로 넣으면 «키 없음» 이 «도구 없음» 과 «이 필드 이전의 옛 행» 둘을 뜻하게 된다."""
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    assert sp.static_provenance([]) == {"build": None, "tools": {}, "rulesets": {}}


def test_provenance_records_versions_read_and_unknown_as_none(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", _SHA)
    with patch.object(sp, "read_version", side_effect=lambda t: f"{t} 2.0"):
        sp.ensure_probed(["pylint"])
    prov = sp.static_provenance(_results(["pylint"], ["flake8"]))
    assert prov["build"] == _SHA
    # flake8 은 아직 안 읽었다 — 행에는 None(모름). 행에 싣는 쪽은 바이너리를 부르지 않는다
    assert prov["tools"] == {"flake8": None, "pylint": "pylint 2.0"}


@pytest.mark.parametrize("value,expected", [
    (_SHA, _SHA),
    (_SHA.upper(), _SHA),
    ("", None),
    ("main", None),
    ("0123abc; rm -rf /", None),
], ids=["sha", "upper", "empty", "branch-name", "garbage"])
def test_build_commit_comes_from_railway_and_must_look_like_a_sha(monkeypatch, value, expected):
    """Railway 는 GitHub 에서 시작한 배포에만 이 변수를 준다 — 없거나 커밋 꼴이 아니면 None."""
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", value)
    assert sp.static_provenance([])["build"] == expected


def test_semgrep_ruleset_is_recorded_only_when_semgrep_ran():
    """고정 룰 출처는 그 룰을 쓰는 도구가 돈 행에만 — 두 심음(돈 행 · 안 돈 행)으로 뒤집는다."""
    manifest = json.loads(sp._SEMGREP_MANIFEST.read_text(encoding="utf-8"))  # pylint: disable=protected-access
    expected = f"{manifest['source'].rstrip('/').rsplit('/', 1)[-1]} {manifest['version']}"
    assert expected.startswith("sast-rules v"), f"전제 붕괴 — MANIFEST 출처가 바뀌었다: {expected}"
    assert sp.static_provenance(_results(["semgrep"]))["rulesets"] == {"semgrep": expected}
    assert sp.static_provenance(_results(["pylint"]))["rulesets"] == {}


def test_unreadable_manifest_is_none(tmp_path):
    bad = tmp_path / "MANIFEST.json"
    bad.write_text("{not json", encoding="utf-8")
    assert sp._semgrep_ruleset(bad) is None  # pylint: disable=protected-access
    planted = tmp_path / "planted.json"
    planted.write_text(json.dumps({"source": "https://gitlab.com/x/sast-rules/", "version": "v9.9.9"}),
                       encoding="utf-8")
    assert sp._semgrep_ruleset(planted) == "sast-rules v9.9.9"  # pylint: disable=protected-access


# ── 분석 행 JSON ──────────────────────────────────────────────────────────


def test_result_dict_carries_the_provenance(monkeypatch):
    """`Analysis.result` 에 `static_provenance` 가 실린다. CLI 훅 행(정적 분석 결과 없음)은 도구가 비어 있다."""
    from src.worker.pipeline import build_analysis_result_dict  # noqa: PLC0415

    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", _SHA)
    ai = SimpleNamespace(
        status="success", truncated=False, error_type=None, error_status_code=None,
        error_vendor_type=None, error_code=None, error_request_id=None, error_retry_after=None,
        error_derived_cause=None, summary="", suggestions=[], commit_message_feedback="",
        code_quality_feedback="", security_feedback="", direction_feedback="", test_feedback="",
        file_feedbacks=[],
    )
    score = SimpleNamespace(total=80, grade="B", breakdown={})
    with patch.object(sp, "read_version", side_effect=lambda t: f"{t} 3.0"):
        sp.ensure_probed(["bandit"])
    pushed = build_analysis_result_dict(ai, score, _results(["bandit"]), source="push")
    assert pushed["static_provenance"] == {"build": _SHA, "tools": {"bandit": "bandit 3.0"}, "rulesets": {}}
    cli = build_analysis_result_dict(ai, score, [], "cli")
    assert cli["static_provenance"] == {"build": _SHA, "tools": {}, "rulesets": {}}
