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

from tests.unit.scripts._wiring_shape import surface_invokes

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


def test_escape_in_string_literal_does_not_exempt(tmp_path, monkeypatch):
    """🔴 문자열/docstring 안의 `# fail-open-reviewed:` 언급은 면제 아님 — 면제 기제 자체 fail-open 봉인.

    이전 `_ESCAPE in src` bare-substring 면제는 docstring/문자열 안 언급도 파일 전체를 면제시켜,
    이 게이트가 잡으려는 바로 그 클래스(산문 통과)를 면제 기제에서 재생산했다. tokenize 로 실제
    주석 토큰만 인정하게 봉인.
    """
    mod = _load()
    trap = tmp_path / "check_fake_string_escape.py"
    trap.write_text(
        'DOC = "이 가드는 # fail-open-reviewed: 방식 설명"  # 문자열 안 언급(주석 아님)\n'
        "def main():\n"
        "    text = open('x').read()\n"
        "    return 1 if 'X' in text else 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_SCRIPTS", tmp_path)
    assert "check_fake_string_escape.py" in mod.fail_open_candidates(), (
        "문자열 안 escape 언급이 파일 전체를 면제 — 면제 기제 자체가 fail-open"
    )


def test_b8_passes_guard_using_aliased_or_from_structural_import(tmp_path, monkeypatch):
    """🔴 alias·from-import 구조 도구도 인정 — `import re as r`·`from re import search`.

    이전 `root.id in _STRUCTURAL_MODULES` 는 alias 를 못 봐 정당한 구조 가드를 오탐(false-positive)
    → 저자가 실제로는 구조 도구를 쓰는데도 거짓 escape 주석을 달아야 했다. import 해소로 봉인.
    """
    mod = _load()
    aliased = tmp_path / "check_fake_aliased.py"
    aliased.write_text(
        "import re as _re\n"
        "def main():\n"
        "    text = open('x').read()\n"
        "    return 1 if _re.search(r'p', text) else 0\n",
        encoding="utf-8",
    )
    from_import = tmp_path / "check_fake_fromimport.py"
    from_import.write_text(
        "from re import search\n"
        "def main():\n"
        "    text = open('x').read()\n"
        "    return 1 if search(r'p', text) else 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_SCRIPTS", tmp_path)
    assert mod.fail_open_candidates() == [], (
        f"alias/from-import 구조 도구 가드를 오탐: {mod.fail_open_candidates()}"
    )


def test_b8_is_wired():
    """🔴 B8 이 pre-commit·CI 에 배선됐는지."""
    pc = (_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    ci = "\n".join(p.read_text(encoding="utf-8") for p in (_ROOT / ".github" / "workflows").glob("*.yml"))
    # 🔴 bare stem substring 이었다 (실측 뮤테이션 GROK-20260731-7) — B8 자신의 배선 freeze 가
    # 이 파일이 강제하려는 fail-open 을 범하고 있었다. 이제 인터프리터 호출을 요구한다.
    # B8's own wiring freeze committed the very fail-open it exists to block.
    ref = "scripts/check_guard_fail_open.py"
    assert surface_invokes(pc, ref), "pre-commit 에서 실행되지 않음 (이름 언급은 배선 아님)"
    assert surface_invokes(ci, ref), "CI 에서 실행되지 않음 (이름 언급은 배선 아님)"


# ── R16: B8 자기 스캔 범위 관측 (backlog R16 — 뮤테이션 GROK-9 실측) ──────────
# B8 was blind to its own scan scope: an emptied glob still printed the success line.

def test_main_fails_when_script_scan_scope_is_empty(tmp_path, monkeypatch, capsys):
    """🔴 scripts 표면 파일 0개 = exit 1 — 범위 붕괴를 성공으로 읽으면 안 된다 (R16).

    현행 main() 은 스캔 범위가 비어도 `✅ … 0개` 성공 문구 + exit 0 이다(backlog R16:
    "범위를 비워도 성공 문구를 출력" = fail-open). glob 경로가 무너지는(디렉토리 이동·오타)
    최악의 경우가 가장 조용히 통과하는 구조 — GROK-9 뮤테이션이 실측한 미탐과 같은 뿌리다.
    범위 붕괴는 fail-closed(exit 1)로 승격돼야 한다.
    An empty scripts surface must exit 1: scope collapse is not success (fail-closed).
    """
    mod = _load()
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    # 후보가 아닌 정상 훅 1개 — 실패 사유를 "scripts 표면 0개" 로 격리한다.
    # One healthy hook so the only failure cause is the empty scripts surface.
    (hooks / "ok_hook.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_SCRIPTS", tmp_path)   # check_*.py 0개 / zero check_*.py files
    monkeypatch.setattr(mod, "_HOOKS", hooks)
    assert mod.main() == 1, "scripts 스캔 범위가 비었는데 성공했다 — 범위 붕괴 fail-open (R16)"
    assert "✅" not in capsys.readouterr().out, "범위 붕괴인데 성공 문구가 출력됐다"


def test_main_fails_when_hook_scan_scope_is_empty(tmp_path, monkeypatch):
    """🔴 반대 방향 — hooks 표면 파일 0개여도 exit 1 (R16).

    `.claude/hooks/*.py` 는 시크릿 덤프 차단·편집 가드 등 실가드가 사는 표면이다.
    디렉토리 이동/오타로 glob 이 비면 그 전부가 미탐인데 성공으로 읽으면 안 된다.
    The hooks surface going empty is the same scope collapse in the other direction.
    """
    mod = _load()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    # 술어를 통과하는 정상 가드 1개 — 실패 사유를 "hooks 표면 0개" 로 격리한다.
    # One predicate-passing guard so the only failure cause is the empty hooks surface.
    (scripts / "check_ok.py").write_text(
        "import re\n"
        "def main():\n"
        "    text = open('x').read()\n"
        "    return 1 if re.search(r'p', text) else 0\n",
        encoding="utf-8",
    )
    hooks = tmp_path / "hooks"
    hooks.mkdir()  # *.py 0개 / zero hook files
    monkeypatch.setattr(mod, "_SCRIPTS", scripts)
    monkeypatch.setattr(mod, "_HOOKS", hooks)
    assert mod.main() == 1, "hooks 스캔 범위가 비었는데 성공했다 — 범위 붕괴 fail-open (R16)"


def test_hook_surface_is_scanned_for_fail_open(tmp_path, monkeypatch):
    """🔴 `.claude/hooks/*.py` 도 fail-open 판정 대상 — scripts-only 범위 확장 (R16).

    B8 은 `scripts/check_*.py` 만 glob 해서 훅 표면의 bare-substring 판정은 원리적으로
    미탐이었다(GROK-9 뮤테이션과 같은 뿌리 — 관측자 없는 표면). 훅도 파일을 읽어 pass/fail
    을 판정하는 관측자이므로 같은 floor 를 적용해야 한다.
    Hooks read files and decide pass/fail too — the same floor must cover them.
    """
    mod = _load()
    bad = tmp_path / "bad_hook.py"
    bad.write_text(
        "def main():\n"
        "    text = open('x').read()\n"
        "    return 1 if 'X' in text else 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "_HOOKS", tmp_path)
    assert "bad_hook.py" in mod.fail_open_candidates(), (
        "훅 표면의 bare-substring 판정을 탐지하지 못했다 — hooks 미스캔(fail-open, R16)"
    )


def test_real_hooks_pass_the_predicate():
    """실제 리포 훅은 전부 구조 도구 사용 — 범위 확장의 오탐 0 baseline (R16).

    실측(2026-08-02): `.claude/hooks/*.py` 4개 전부 구조 도구 호출 — 확장해도 오탐 0
    (정책 17 guard-suicide 위험 없음). hooks 표면이 비면 이 단언이 공허해지므로
    표면 비어있지 않음을 먼저 고정한다(공허화 방지).
    Anti-vacuity first: an empty hooks surface would make this baseline vacuously true.
    """
    mod = _load()
    assert list(mod._HOOKS.glob("*.py")), "hooks 표면이 비었다 — 이 baseline 은 공허하다"
    assert mod.fail_open_candidates() == [], (
        f"실제 훅에서 fail-open 오탐 발생: {mod.fail_open_candidates()}"
    )


def test_success_message_states_the_actual_scan_scope(capsys):
    """🔴 성공 문구는 실제 스캔 범위 + 범위 밖을 정직하게 명시해야 한다 (R16 최소 조치).

    현행 ✅ 문구는 전 표면을 검증한 듯 읽히지만 실제 범위는 scripts(+hooks)뿐이다 —
    AGENTS.md 가 기록한 최다 재발 사고(#1136·#1156)는 정확히 범위 밖(tests/** test-as-guard)
    에 있었다. backlog R16 이 확정한 오탐 위험 0 의 최소 조치 = 성공 문구를 실제 스캔 범위
    (`scripts/check_*.py` 개수 + `.claude/hooks/*.py` 개수)로 한정하고 범위 밖을 명시하는 것.
    The success line must state what was scanned and what was not (tests/** test-as-guard).
    """
    mod = _load()
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "scripts/check_*.py" in out, "성공 문구에 scripts 스캔 범위 명시 없음 (R16)"
    assert ".claude/hooks" in out, "성공 문구에 hooks 스캔 범위 명시 없음 (R16)"
    assert "tests/" in out, "성공 문구에 범위 밖(tests/** test-as-guard) 명시 없음 (R16)"
