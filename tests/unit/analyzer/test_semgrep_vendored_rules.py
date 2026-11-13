"""semgrep 은 리포에 고정한 허용 라이선스 룰만 쓴다 (회고 2026-11-06 원장 L03 P1-40).

레지스트리 룰(`p/default`)은 «내부 업무 목적만 · 남에게 서비스로 제공 금지» 라이선스라 서비스로 쓸 수 없고,
실행마다 레지스트리에 기대면 그 장애가 분석 실패가 된다. 그래서 GitLab sast-rules v2.10.1 에서 파일 머리의
라이선스가 MIT(GitLab) · Apache-2.0(gosec) · LGPL-3.0 인 룰만 `src/analyzer/configs/semgrep/rules/<라이선스>/`
에 고정했다. 이 파일은 그 고정이 깨지지 않는지 잰다 — 허용 밖 라이선스의 룰이 섞이지 않는가, 목록 ·
라이선스 원문이 같이 다니는가, semgrep 이 지원한다고 말하는 언어가 실제 룰이 있는 언어와 같은가.

semgrep only runs the vendored allowed-license subset of GitLab sast-rules; this file checks that the
subset stays license-clean, ships with its manifest and license texts, and that the languages semgrep
claims are exactly the languages the vendored rules cover.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest  # noqa: E402
import yaml  # noqa: E402

from src.analyzer.io.tools import semgrep as sg  # noqa: E402

_REPO = Path(__file__).resolve().parents[3]
_SemgrepAnalyzer = sg._SemgrepAnalyzer  # pylint: disable=protected-access


def _rules_dir() -> Path:
    """어댑터가 쓰는 고정 룰 폴더 — 없으면 수집 오류가 아니라 단언으로 실패한다(역-뮤테이션 신호를 단언으로)."""
    rules = getattr(sg, "RULES_DIR", None)
    assert rules is not None and Path(rules).is_dir(), "semgrep 어댑터에 고정 룰 폴더(RULES_DIR)가 없다"
    return Path(rules)

# 폴더 이름 → 그 폴더의 룰이 머리에 적어야 하는 라이선스 줄
# License folder -> the header line every rule in that folder must carry.
_ALLOWED = {
    "mit": re.compile(r"^License:\s*(?:License:\s*)?MIT \(c\) GitLab Inc\.\s*$"),
    "apache-2.0": re.compile(r"^License:\s*Apache 2\.0 \(c\) gosec\s*$"),
    "lgpl-3.0": re.compile(r"^License:\s*GNU Lesser General Public License v3\.0\s*$"),
}
# 룰의 `languages` 값 → 이 앱의 언어 이름. 언어가 아닌 값(generic · regex)은 지원 언어로 세지 않는다.
# Rule `languages` values -> this app's language names; generic/regex are not languages.
_LANG_ALIASES = {"kt": "kotlin", "c#": "csharp", "js": "javascript", "ts": "typescript"}
_NOT_LANGUAGES = {"generic", "regex", "none"}


def _license_of(text: str) -> str | None:
    """파일 머리 40줄 안의 첫 `License:` 줄로 허용 폴더 이름을 고른다 — 허용 밖이면 None."""
    for line in text.splitlines()[:40]:
        stripped = line.strip().lstrip("#").strip()
        if re.match(r"^License:", stripped, re.I):
            return next((name for name, rx in _ALLOWED.items() if rx.match(stripped)), None)
    return None


def _rule_files() -> list[Path]:
    return sorted(p for p in _rules_dir().rglob("*") if p.suffix in (".yml", ".yaml"))


def _covered_languages(rules) -> set[str]:
    """룰들이 선언한 `languages` 를 이 앱의 언어 이름으로 — 언어가 아닌 값(generic · regex · none)은 뺀다."""
    covered = set()
    for rule in rules:
        for lang in rule.get("languages", []) or []:
            name = _LANG_ALIASES.get(str(lang).lower(), str(lang).lower())
            if name not in _NOT_LANGUAGES:
                covered.add(name)
    return covered


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_the_rule_folder_is_not_empty():
    """🔴 전제 — 빈 폴더 위에서는 아래 판정이 모두 공허하게 초록이다."""
    assert len(_rule_files()) >= 400, f"고정한 룰이 {len(_rule_files())}개뿐이다"


@pytest.mark.parametrize("header", [
    "# License: Commons Clause License Condition v1.0[LGPL-2.1-only]",
    "# License: Semgrep Rules License v1.0",
    "# License: GPL 2.0 (c) 1989, 1991 Free Software Foundation, Inc.",
    '# License: The GitLab Enterprise Edition (EE) license (the "EE License")',
    "# License: MIT (c) Someone Else",
    "# no license line at all",
])
def test_the_license_classifier_rejects_disallowed_headers(header):
    """🔴 계기 뒤집기 — 허용 밖 라이선스 머리를 심으면 판정이 받아들이지 않는다.

    «`License:` 줄이 있다» · «MIT 라는 글자가 있다» 같은 싼 판정은 위 값 일부를 받아들인다.
    """
    assert _license_of(f"{header}\nrules:\n- id: x\n") is None


# ─── 고정한 룰 ───────────────────────────────────────────────────────────────


def test_every_vendored_rule_carries_the_license_of_its_folder():
    """🔴 허용 밖 라이선스의 룰이 섞이지 않는다 — 폴더(라이선스)와 파일 머리가 일치한다."""
    wrong = []
    for path in _rule_files():
        folder = path.relative_to(_rules_dir()).parts[0]
        if _license_of(path.read_text(encoding="utf-8")) != folder:
            wrong.append(path.relative_to(_rules_dir()).as_posix())
    assert not wrong, f"폴더와 라이선스가 다른 룰 {len(wrong)}개: {wrong[:5]}"


def test_manifest_lists_exactly_the_vendored_files():
    """목록(MANIFEST.json)과 실제 파일이 어긋나지 않는다 — 출처 · 판 · 파일별 라이선스의 정본이다."""
    manifest = json.loads((_rules_dir().parent / "MANIFEST.json").read_text(encoding="utf-8"))
    listed = {(f["path"], f["license"]) for f in manifest["files"]}
    root = _rules_dir()
    actual = {(p.relative_to(root).as_posix(), p.relative_to(root).parts[0]) for p in _rule_files()}
    assert listed == actual, f"목록에만: {sorted(listed - actual)[:3]} · 파일에만: {sorted(actual - listed)[:3]}"
    assert manifest["version"] == "v2.10.1" and manifest["source"].endswith("/sast-rules")


@pytest.mark.parametrize("relpath,needles", [
    ("mit/LICENSE", ("MIT Expat", "GitLab Inc.")),
    ("apache-2.0/LICENSE", ("Apache License", "Version 2.0")),
    ("lgpl-3.0/COPYING.LESSER", ("GNU LESSER GENERAL PUBLIC LICENSE", "GNU GENERAL PUBLIC LICENSE")),
])
def test_license_texts_ship_with_the_rules(relpath, needles):
    """라이선스 원문이 룰과 함께 다닌다 — 복사본에 고지를 남기는 것이 세 라이선스의 공통 조건이다.

    LGPL-3.0 은 GPL-3.0 에 더한 허가라 두 원문이 함께 있어야 한다.
    """
    text = (_rules_dir() / relpath).read_text(encoding="utf-8")
    for needle in needles:
        assert needle in text, f"{relpath} 에 «{needle}» 가 없다"


def test_supported_languages_are_exactly_the_languages_the_rules_cover():
    """🔴 semgrep 이 지원한다고 말하는 언어 = 고정한 룰이 있는 언어.

    룰이 0개인 언어를 지원한다고 하면 그 언어 파일은 «이슈 0건 · 완전» 으로 기록된다. 거꾸로 룰이 있는데
    지원 목록에 없으면 그 룰은 한 번도 돌지 않는다.
    """
    rules = []
    for path in _rule_files():
        rules.extend((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("rules", []) or [])
    covered = _covered_languages(rules)
    assert covered == set(_SemgrepAnalyzer.SUPPORTED_LANGUAGES), (
        f"룰만 있음: {sorted(covered - _SemgrepAnalyzer.SUPPORTED_LANGUAGES)} · "
        f"지원만 있음: {sorted(_SemgrepAnalyzer.SUPPORTED_LANGUAGES - covered)}"
    )


# witness-corpus: semgrep 문서의 다른 비-언어 모드 이름 — 위 제외 목록에서 뽑지 않았다(generic 의 옛 이름 · 실험 모드)
_OTHER_PSEUDO_LANGUAGES = ["spacegrep", "aliengrep"]


@pytest.mark.parametrize("token", _OTHER_PSEUDO_LANGUAGES)
def test_an_unlisted_pseudo_language_fails_closed(token):
    """🔴 제외 목록에 없는 비-언어 값은 «언어» 로 셈된다 — 그런 룰이 들어오면 위 언어 일치 시험이 빨갛게 된다.

    목록이 모자라면 조용히 초록이 되는 쪽이 아니라 막는 쪽으로 틀린다는 것을 고정한다.
    """
    assert _covered_languages([{"languages": [token, "python"]}]) == {token, "python"}


def test_the_rules_reach_the_runtime_image():
    """`.dockerignore` 가 룰 폴더를 이미지에서 빼지 않는다 — 빠지면 운영 semgrep 이 설정 없음으로 실패한다."""
    sample = _rules_dir().relative_to(_REPO).as_posix() + "/mit/python/x.yml"
    patterns = [line.strip() for line in (_REPO / ".dockerignore").read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#") and not line.startswith("!")]
    hits = [p for p in patterns
            if fnmatch.fnmatch(sample, p) or fnmatch.fnmatch(sample, p.rstrip("/") + "/*")
            or sample.startswith(p.rstrip("/") + "/")]
    assert not hits, f".dockerignore 가 룰 폴더를 뺀다: {hits}"


@pytest.mark.skipif(shutil.which("semgrep") is None, reason="semgrep 바이너리 없음 — CI · 이미지에서 잰다")
def test_real_semgrep_loads_the_rules_offline_and_finds_an_issue(tmp_path):
    """실물 semgrep 이 고정한 룰을 모두 읽고(설정 오류 0) 취약 코드에서 이슈를 낸다 — 네트워크 없이."""
    # 일부러 취약하게 쓴 코드 문자열 — 파일로만 쓰고 실행하지 않는다(semgrep 이 잡아야 하는 표본).
    # A deliberately vulnerable sample written to disk for the scanner; it is never executed.
    sample = tmp_path / "vuln.py"
    sample.write_text("import subprocess\n\ndef run(cmd):\n    subprocess.call(cmd, shell=True)\n"
                      "    return eval(cmd)\n", encoding="utf-8")
    r = subprocess.run(
        ["semgrep", "scan", f"--config={_rules_dir()}", "--json", "--metrics=off",
         "--disable-version-check", str(sample)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, check=False,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    assert r.returncode == 0, f"semgrep 종료 {r.returncode}: {r.stdout[:300]} {r.stderr[-300:]}"
    data = json.loads(r.stdout)
    assert not data.get("errors"), f"룰 · 대상 오류: {data['errors'][:2]}"
    assert data.get("results"), "취약 코드에서 이슈가 하나도 안 나왔다"


# 지원 언어 → 그 언어로 읽히는 확장자. 지원 언어가 늘면 여기서 KeyError — 대응을 강제한다.
# Supported language -> an extension semgrep reads as that language; a new language must be added here.
_EXT = {"python": "py", "javascript": "js", "typescript": "ts", "java": "java", "go": "go",
        "csharp": "cs", "scala": "scala", "kotlin": "kt", "swift": "swift"}


@pytest.mark.skipif(shutil.which("semgrep") is None, reason="semgrep 바이너리 없음 — CI · 이미지에서 잰다")
def test_real_semgrep_applies_at_least_one_rule_to_every_supported_language(tmp_path):
    """🔴 실행 경로에서도 지원 언어마다 룰이 적어도 하나 걸린다 (Grok 1c1278f1 이 짚은 빈칸).

    위 언어 일치 시험은 룰 파일의 선언만 본다. 여기서는 어댑터와 같은 설정으로 실물 semgrep 을 돌려,
    언어마다 만든 파일이 `paths.scanned` 에 오르는지 본다 — semgrep 은 걸리는 룰이 없는 파일을 훑지 않는다
    (실측: 같은 실행의 .rb 파일은 scanned 에 없다). 대조군 .rb 가 오르지 않는 것도 함께 본다.
    """
    for lang in _SemgrepAnalyzer.SUPPORTED_LANGUAGES:
        (tmp_path / f"sample_{lang}.{_EXT[lang]}").write_text("x\n", encoding="utf-8")
    (tmp_path / "control.rb").write_text("puts 1\n", encoding="utf-8")
    r = subprocess.run(
        ["semgrep", "scan", f"--config={_rules_dir()}", "--json", "--metrics=off",
         "--disable-version-check", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, check=False,
        env={**os.environ, "PYTHONUTF8": "1"},
    )
    assert r.returncode == 0, f"semgrep 종료 {r.returncode}: {r.stderr[-300:]}"
    scanned = {Path(p).name for p in (json.loads(r.stdout).get("paths") or {}).get("scanned", [])}
    missing = sorted(lang for lang in _SemgrepAnalyzer.SUPPORTED_LANGUAGES
                     if f"sample_{lang}.{_EXT[lang]}" not in scanned)
    assert not missing, f"룰이 하나도 걸리지 않은 지원 언어: {missing}"
    assert "control.rb" not in scanned, "전제 붕괴 — 룰이 없는 언어도 scanned 에 오른다면 이 판정은 무효다"
