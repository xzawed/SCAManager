"""`check_guard_fail_open.py` (B8) 회귀 가드 — fail-open 저술을 write-time 에 잡는가.

## 배경 (2026-07-20 Grok 최종 적대검증)

문서 재구성은 불변식 3(배선)만 기계화했고, **불변식 1(fail-closed)의 write-time 게이트가
없었다**. B8 은 그 floor — 파일 읽어 판정하는 check 가드가 구조 도구 없이 bare substring 만
쓰면 차단. 이 테스트는 B8 이 (1) 현 baseline 통과 (2) 합성 fail-open 가드를 실제로 잡는지 확인.

🔴 이 게이트도 관측자이므로 3-불변식 적용 — 판정을 AST 호출 관측으로(산문 통과 방지) +
실경로 뮤테이션 red + 배선 확인.
"""
import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "check_guard_fail_open.py"


def _load():
    spec = importlib.util.spec_from_file_location("_b8", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_b8"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_current_guards_have_no_fail_open_candidate():
    """🔴 현 check 가드는 전부 구조 도구 사용(bare-substring fail-open 0) — baseline."""
    mod = _load()
    assert mod.fail_open_candidates() == [], (
        f"fail-open 후보(구조 도구 0): {mod.fail_open_candidates()}"
    )


def test_b8_flags_a_synthetic_bare_substring_guard(tmp_path, monkeypatch):
    """🔴 합성 fail-open 가드(파일 읽고 bare `X in text` 판정)를 실제로 잡는가 — 뮤테이션.

    #1136 클래스(echo 산문이 통과시키는 가드)를 저술 시점에 차단하는 것이 B8 의 존재 이유.
    """
    mod = _load()
    fake = tmp_path / "check_fake_fail_open.py"
    fake.write_text(
        "def main():\n"
        "    text = open('x').read()\n"
        "    return 1 if 'WARNING' in text else 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_SCRIPTS", tmp_path)
    assert "check_fake_fail_open.py" in mod.fail_open_candidates(), (
        "합성 bare-substring 가드를 탐지하지 못했다 — B8 fail-open"
    )


def test_b8_passes_a_guard_that_uses_a_structural_tool(tmp_path, monkeypatch):
    """대조군 — 구조 도구(re)를 **호출**하는 가드는 통과."""
    mod = _load()
    ok = tmp_path / "check_fake_ok.py"
    ok.write_text(
        "import re\n"
        "def main():\n"
        "    text = open('x').read()\n"
        "    return 1 if re.search(r'pat', text) else 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_SCRIPTS", tmp_path)
    assert mod.fail_open_candidates() == []


def test_b8_detection_uses_ast_calls_not_import_mention(tmp_path, monkeypatch):
    """🔴 도구 **import·언급**만으로는 통과시키면 안 된다 — 실제 **호출**을 봐야 한다.

    이 게이트 자신이 산문(import re 만 하고 re 미호출)에 속으면 fail-open 이다.
    check_architecture_tree_sync 가 정확히 그 상태(re import 없이 bare in)였고 B8 이 잡았다.
    """
    mod = _load()
    # re 를 import 만 하고 호출 안 함 + bare substring 판정 → 여전히 fail-open 후보
    trap = tmp_path / "check_fake_trap.py"
    trap.write_text(
        "import re  # 언급만\n"
        "def main():\n"
        "    text = open('x').read()\n"
        "    return 1 if 'X' in text else 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_SCRIPTS", tmp_path)
    assert "check_fake_trap.py" in mod.fail_open_candidates(), (
        "re 를 import 만 하고 호출 안 하는데 통과시켰다 — import 언급에 속음(fail-open)"
    )


def test_escape_hatch_exempts_reviewed_guards(tmp_path, monkeypatch):
    """정당한 substring-only 가드는 `# fail-open-reviewed:` 로 면제 — 과탐(가드 자살) 방지."""
    mod = _load()
    reviewed = tmp_path / "check_fake_reviewed.py"
    reviewed.write_text(
        "# fail-open-reviewed: presence check, tree is not AST-parseable\n"
        "def main():\n"
        "    text = open('x').read()\n"
        "    return 1 if 'X' in text else 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_SCRIPTS", tmp_path)
    assert mod.fail_open_candidates() == []


def test_b8_is_wired():
    """🔴 B8 이 pre-commit·CI 에 배선됐는지."""
    pc = (_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    ci = "\n".join(p.read_text(encoding="utf-8") for p in (_ROOT / ".github" / "workflows").glob("*.yml"))
    assert "check_guard_fail_open" in pc, "pre-commit 미배선"
    assert "check_guard_fail_open" in ci, "CI 미배선"
