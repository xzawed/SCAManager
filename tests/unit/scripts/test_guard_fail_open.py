"""`check_guard_fail_open.py` (B8) 회귀 가드 — fail-open 저술을 write-time 에 잡는가.

B8 은 floor 다 — 파일을 읽어 판정하는 파이썬 코드가 구조 도구를 하나도 부르지 않으면 차단한다.
이 테스트는 B8 이 (1) 현 baseline 통과 (2) 합성 fail-open 파일을 실제로 잡는지 (3) 정당한
구조 판정(파서 입구 · 파서 상속 · 구조 도구를 부르는 리포 헬퍼)을 오탐하지 않는지 확인한다.

🔴 이 게이트도 관측자이므로 3-불변식 적용 — 판정을 AST 호출 관측으로(산문 통과 방지) +
실경로 뮤테이션 red + 배선 확인.
"""
import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

from tests.unit.scripts._wiring_shape import surface_invokes

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "check_guard_fail_open.py"

# 구조 도구(re)를 **호출**하는 건강한 판정 — 표면을 비우지 않으면서 후보 0 으로 둔다.
# A healthy reader that calls a structural tool: keeps a surface non-empty with zero candidates.
_HEALTHY = (
    "import re\n"
    "def main():\n"
    "    text = open('x').read()\n"
    "    return 1 if re.search(r'p', text) else 0\n"
)
# 파일을 읽고 bare substring 으로 판정 — B8 이 잡아야 하는 모양(#1136 클래스).
# Reads a file and decides by bare substring: the shape B8 exists to block.
_BARE = (
    "def main():\n"
    "    text = open('x').read()\n"
    "    return 1 if 'X' in text else 0\n"
)
# 가짜 리포의 네 표면 — (모듈 속성, 리포 안 디렉터리, 그 표면 glob 에 걸리는 건강한 파일).
# The fake repo's four surfaces: (module attribute, directory, a healthy file its glob matches).
_SURFACES = {
    "_SCRIPTS": ("scripts", "check_ok.py"),
    "_HOOKS": (".claude/hooks", "ok_hook.py"),
    "_TESTS": ("tests", "unit/test_ok.py"),
    "_E2E": ("e2e", "test_ok.py"),
}


def _load():
    spec = importlib.util.spec_from_file_location("_b8", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_b8"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """네 표면을 tmp 가짜 리포의 건강한 파일 하나씩으로 고정한다 — 판정이 실제 리포 상태에 기대지 않게.

    `raising=False` — 표면 속성이 없는 판(되돌린 B8)에서도 픽스처는 서고, 시험은 단언에서 빨개진다.
    Pins all four surfaces to a tmp fake repo, one healthy file each, so verdicts never lean on the
    real tree. raising=False keeps the fixture standing on a reverted B8 so failures are assertions.
    """
    mod = _load()
    monkeypatch.setattr(mod, "_ROOT", tmp_path, raising=False)
    dirs = {}
    for attr, (rel_dir, healthy) in _SURFACES.items():
        d = tmp_path / rel_dir
        (d / healthy).parent.mkdir(parents=True, exist_ok=True)
        (d / healthy).write_text(_HEALTHY, encoding="utf-8")
        monkeypatch.setattr(mod, attr, d, raising=False)
        dirs[attr] = d
    return mod, dirs


def _put(path: Path, src: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(src, encoding="utf-8")


def test_current_guards_have_no_fail_open_candidate():
    """🔴 현 리포의 네 표면은 전부 구조 판정(bare-substring fail-open 0) — baseline."""
    mod = _load()
    assert mod.fail_open_candidates() == [], (
        f"fail-open 후보(구조 도구 0): {mod.fail_open_candidates()}"
    )


def test_fake_repo_baseline_is_green(fake_repo):
    """대조군 — 건강한 가짜 리포는 통과한다. 아래 red 들의 원인이 시험이 심은 한 가지임을 보인다."""
    mod, _ = fake_repo
    assert mod.fail_open_candidates() == []
    assert mod.main() == 0


def test_b8_flags_a_synthetic_bare_substring_guard(fake_repo):
    """🔴 합성 fail-open 가드(파일 읽고 bare `X in text` 판정)를 실제로 잡는가 — 뮤테이션.

    #1136 클래스(echo 산문이 통과시키는 가드)를 저술 시점에 차단하는 것이 B8 의 존재 이유.
    """
    mod, dirs = fake_repo
    _put(dirs["_SCRIPTS"] / "check_fake_fail_open.py", _BARE)
    assert "scripts/check_fake_fail_open.py" in mod.fail_open_candidates(), (
        "합성 bare-substring 가드를 탐지하지 못했다 — B8 fail-open"
    )


def test_b8_passes_a_guard_that_uses_a_structural_tool(fake_repo):
    """대조군 — 구조 도구(re)를 **호출**하는 가드는 통과."""
    mod, dirs = fake_repo
    _put(dirs["_SCRIPTS"] / "check_fake_ok.py", _HEALTHY)
    assert mod.fail_open_candidates() == []


def test_b8_detection_uses_ast_calls_not_import_mention(fake_repo):
    """🔴 도구 **import·언급**만으로는 통과시키면 안 된다 — 실제 **호출**을 봐야 한다.

    이 게이트 자신이 산문(import re 만 하고 re 미호출)에 속으면 fail-open 이다.
    """
    mod, dirs = fake_repo
    # re 를 import 만 하고 호출 안 함 + bare substring 판정 → 여전히 fail-open 후보
    _put(dirs["_SCRIPTS"] / "check_fake_trap.py", "import re  # 언급만\n" + _BARE)
    assert "scripts/check_fake_trap.py" in mod.fail_open_candidates(), (
        "re 를 import 만 하고 호출 안 하는데 통과시켰다 — import 언급에 속음(fail-open)"
    )


def test_escape_hatch_exempts_reviewed_guards(fake_repo):
    """정당한 substring-only 가드는 `# fail-open-reviewed:` 로 면제 — 과탐(가드 자살) 방지."""
    mod, dirs = fake_repo
    _put(dirs["_SCRIPTS"] / "check_fake_reviewed.py",
         "# fail-open-reviewed: presence check, tree is not AST-parseable\n" + _BARE)
    assert mod.fail_open_candidates() == []


def test_escape_in_string_literal_does_not_exempt(fake_repo):
    """🔴 문자열/docstring 안의 `# fail-open-reviewed:` 언급은 면제 아님 — 면제 기제 자체 fail-open 봉인.

    tokenize 로 실제 주석 토큰만 인정한다 — 문자열 안 언급이 파일 전체를 면제시키면
    이 게이트가 잡으려는 클래스(산문 통과)를 면제 기제에서 재생산한다.
    """
    mod, dirs = fake_repo
    _put(dirs["_SCRIPTS"] / "check_fake_string_escape.py",
         'DOC = "이 가드는 # fail-open-reviewed: 방식 설명"  # 문자열 안 언급(주석 아님)\n' + _BARE)
    assert "scripts/check_fake_string_escape.py" in mod.fail_open_candidates(), (
        "문자열 안 escape 언급이 파일 전체를 면제 — 면제 기제 자체가 fail-open"
    )


def test_b8_passes_guard_using_aliased_or_from_structural_import(fake_repo):
    """🔴 alias·from-import 구조 도구도 인정 — `import re as r`·`from re import search`.

    alias 를 못 보면 정당한 구조 가드를 오탐(false-positive)해 저자가 거짓 escape 주석을 달아야 한다.
    """
    mod, dirs = fake_repo
    _put(dirs["_SCRIPTS"] / "check_fake_aliased.py",
         "import re as _re\n"
         "def main():\n"
         "    text = open('x').read()\n"
         "    return 1 if _re.search(r'p', text) else 0\n")
    _put(dirs["_SCRIPTS"] / "check_fake_fromimport.py",
         "from re import search\n"
         "def main():\n"
         "    text = open('x').read()\n"
         "    return 1 if search(r'p', text) else 0\n")
    assert mod.fail_open_candidates() == [], (
        f"alias/from-import 구조 도구 가드를 오탐: {mod.fail_open_candidates()}"
    )


def test_b8_is_wired():
    """🔴 B8 이 pre-commit·CI 에 배선됐는지."""
    pc = (_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    ci = "\n".join(p.read_text(encoding="utf-8") for p in (_ROOT / ".github" / "workflows").glob("*.yml"))
    # 🔴 bare stem substring 이면 실행 엔트리를 지우고 이름만 남겨도 통과한다 — 인터프리터 호출을 요구한다.
    # A bare stem substring passes with the entry gone and only the name left; require an invocation.
    ref = "scripts/check_guard_fail_open.py"
    assert surface_invokes(pc, ref), "pre-commit 에서 실행되지 않음 (이름 언급은 배선 아님)"
    assert surface_invokes(ci, ref), "CI 에서 실행되지 않음 (이름 언급은 배선 아님)"


def test_pre_commit_runs_b8_when_any_scanned_surface_changes():
    """🔴 pre-commit 의 `files:` 가 네 표면 모두를 덮는다 — 시험만 고친 커밋에서도 B8 이 돈다.

    표본은 손 목록이 아니라 B8 자신의 표면에서 파생한다(표면마다 첫 파일). `files:` 가 옛
    `^scripts/check_` 에 머물면 tests/ 편집 커밋은 B8 없이 지나가고 CI 에서야 빨개진다.
    Samples come from B8's own surfaces, so a `files:` pattern stuck on scripts/ turns this red.
    """
    mod = _load()
    hooks = [h for repo in yaml.safe_load((_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))["repos"]
             for h in repo.get("hooks", []) if h.get("id") == "check-guard-fail-open"]
    assert len(hooks) == 1, f"check-guard-fail-open 훅이 {len(hooks)}개다"
    pattern = re.compile(hooks[0]["files"])
    surfaces = mod._scan_targets()  # pylint: disable=protected-access
    assert len(surfaces) == len(_SURFACES), f"표면 수가 바뀌었다: {sorted(surfaces)}"
    for label, files in surfaces.items():
        assert files, f"{label} 표면이 비었다 — 표본을 못 뽑는다"
        sample = files[0].relative_to(_ROOT).as_posix()
        assert pattern.search(sample), f"pre-commit `files:` 가 {label} 의 {sample} 을 안 덮는다"


# ── 표면 붕괴 · 구문 깨짐 (빈 범위 위의 초록 금지) ─────────────────────────
# An empty surface or an unparseable file must never sit under a success banner.

@pytest.mark.parametrize("surface", sorted(_SURFACES))
def test_main_fails_when_any_scan_surface_is_empty(fake_repo, surface, capsys):
    """🔴 표면 하나라도 파일 0개 = exit 1 — glob 경로가 무너진 것을 «위반 0건» 으로 읽으면 안 된다."""
    mod, dirs = fake_repo
    for p in dirs[surface].rglob("*.py"):
        p.unlink()
    assert mod.main() == 1, f"{surface} 표면이 비었는데 성공했다 — 범위 붕괴 fail-open"
    assert "✅" not in capsys.readouterr().out, "범위 붕괴인데 성공 문구가 출력됐다"


_BROKEN_NAMES = {"_SCRIPTS": "check_broken_syntax.py", "_HOOKS": "broken_hook.py",
                 "_TESTS": "unit/test_broken_syntax.py", "_E2E": "test_broken_syntax.py"}


@pytest.mark.parametrize("surface", sorted(_SURFACES))
def test_syntax_broken_file_fails_main(fake_repo, surface, capsys):
    """🔴 어느 표면이든 구문 깨진 파일이 하나라도 있으면 main() = exit 1.

    `ast.parse` 실패를 skip 하면 «파일은 있는데 분석 0개» 위에 ✅ 가 뜬다. 가드·훅·시험은 모두
    실행되는 파일이라 구문 깨짐은 그 자체로 결함이다 — 건강한 파일 옆에 있어도 red 여야 한다.
    A file that cannot parse cannot run: any surface carrying one must turn main() red.
    """
    mod, dirs = fake_repo
    rel = _BROKEN_NAMES[surface]
    _put(dirs[surface] / rel, "def broken(:\n")
    assert mod.main() == 1, f"{surface} 에 구문 깨진 파일이 있는데 성공했다 — silent skip fail-open"
    out = capsys.readouterr().out
    assert "✅" not in out, "구문 깨진 파일 위에 성공 문구가 출력됐다"
    assert Path(rel).name in out, "어느 파일이 구문 깨졌는지 출력에 없다 — 저자가 고칠 대상을 알 수 없다"


# ── 표면 — 훅 · 시험 · e2e 도 같은 floor ──────────────────────────────────

def test_hook_surface_is_scanned_for_fail_open(fake_repo):
    """🔴 `.claude/hooks/*.py` 도 fail-open 판정 대상 — 훅도 파일을 읽어 pass/fail 을 판정한다."""
    mod, dirs = fake_repo
    _put(dirs["_HOOKS"] / "bad_hook.py", _BARE)
    assert ".claude/hooks/bad_hook.py" in mod.fail_open_candidates(), (
        "훅 표면의 bare-substring 판정을 탐지하지 못했다 — hooks 미스캔(fail-open)"
    )


@pytest.mark.parametrize("surface", ["_TESTS", "_E2E"])
def test_test_surfaces_are_scanned_for_fail_open(fake_repo, surface):
    """🔴 시험도 가드다 — `tests/**` · `e2e/**` 의 bare-substring 판정을 하위 디렉터리까지 잡는다.

    가드 인구는 tests/ 로 옮겨 갔다(정적 소스 검사 · 배선 검사). 그 표면을 안 보면 floor 는
    가장 많은 가드를 못 본다. 깊은 경로에 심어 `rglob` 이 아니라 한 층 glob 이면 red 가 되게 한다.
    Tests are guards too; plant the file two levels deep so a one-level glob turns this red.
    """
    mod, dirs = fake_repo
    bad = dirs[surface] / "deep" / "nested" / "test_bad.py"
    _put(bad, _BARE)
    label = bad.relative_to(dirs[surface].parent).as_posix()
    assert label in mod.fail_open_candidates(), f"{label} 의 bare-substring 판정을 탐지하지 못했다"


def test_read_bytes_reader_is_flagged(fake_repo):
    """🔴 `read_bytes` 로 읽는 bare-substring 훅도 후보다 — 읽기 API 를 바꿔 floor 밑으로 못 들어간다."""
    mod, dirs = fake_repo
    _put(dirs["_HOOKS"] / "bytes_probe_hook.py",
         "from pathlib import Path\n"
         "def main():\n"
         "    text = Path('x').read_bytes().decode('utf-8')\n"
         "    return 1 if 'X' in text else 0\n")
    assert ".claude/hooks/bytes_probe_hook.py" in mod.fail_open_candidates(), (
        "read_bytes 로 읽는 bare-substring 훅을 탐지하지 못했다 — _reads_a_file 이름 집합 누락"
    )


def test_failure_message_points_at_helpers_that_exist(fake_repo, capsys):
    """실패 문구가 가리키는 헬퍼 경로는 실제 리포에 있다 — 옮기거나 지우면 문구가 저자를 헛걸음시킨다."""
    mod, dirs = fake_repo
    _put(dirs["_TESTS"] / "unit" / "test_bare.py", _BARE)
    assert mod.main() == 1
    named = re.findall(r"`((?:tests|scripts)/[\w/.-]+\.py)`", capsys.readouterr().out)
    assert named, "실패 문구에서 헬퍼 경로를 하나도 못 읽었다 — 이 대조가 공허하다"
    missing = [p for p in named if not (_ROOT / p).is_file()]
    assert not missing, f"실패 문구가 없는 파일을 가리킨다: {missing}"


def test_every_real_surface_is_scanned():
    """실제 리포의 네 표면이 전부 비어 있지 않다 — 위 baseline 이 공허하지 않다는 바닥."""
    mod = _load()
    surfaces = mod._scan_targets()  # pylint: disable=protected-access
    assert set(surfaces) == {"scripts/check_*.py", ".claude/hooks/*.py", "tests/**/*.py", "e2e/**/*.py"}
    empty = [label for label, files in surfaces.items() if not files]
    assert not empty, f"비어 있는 표면: {empty}"


def test_success_message_states_the_actual_scan_scope(capsys):
    """🔴 성공 문구는 표면마다 **실제로 읽은 개수**와 범위 밖을 적는다 — 개수는 `_scan_targets()` 에서 파생.

    «가드 전부 통과» 처럼 읽히면 범위 밖까지 덮은 것으로 오독된다. 손으로 적은 숫자가 아니라
    표면이 돌려준 개수를 대조해, 문구와 실제 범위가 갈리면 red 가 된다.
    The banner states each surface's scanned count (derived) and what lies outside the floor.
    """
    mod = _load()
    assert mod.main() == 0
    out = capsys.readouterr().out
    for label, files in mod._scan_targets().items():  # pylint: disable=protected-access
        assert f"{len(files)}개({label})" in out, f"성공 문구에 {label} 표면의 실제 개수가 없다:\n{out}"
    assert ".mjs" in out, "성공 문구에 범위 밖(파이썬이 아닌 판정 코드)이 없다"


# ── 구조 도구로 세는 것 — 파서 입구 · 파서 상속 · 리포 헬퍼 ──────────────────
# What counts as a structural tool: parser read entries, parser subclassing, structural helpers.

@pytest.mark.parametrize("src", [
    "import json\ndef test_x():\n    assert json.loads(open('x').read())['k'] == 1\n",
    "from json import load\ndef test_x():\n    assert load(open('x'))['k'] == 1\n",
    "import yaml\ndef test_x():\n    assert yaml.safe_load(open('x').read())['k']\n",
    "import tomllib\ndef test_x():\n    assert tomllib.loads(open('x').read())['k']\n",
    "import jinja2\ndef test_x():\n    assert jinja2.Environment().parse(open('x').read())\n",
    "from html.parser import HTMLParser\nclass P(HTMLParser):\n    pass\n"
    "def test_x():\n    P().feed(open('x').read())\n",
], ids=["json.loads", "from-json-load", "yaml.safe_load", "tomllib.loads", "jinja2.Environment",
        "HTMLParser-subclass"])
def test_parser_read_entries_count_as_structural(fake_repo, src):
    """파서로 구조를 읽는 시험은 후보가 아니다 — 데이터 파일을 파싱해 키로 판정하는 것은 구조 판정이다."""
    mod, dirs = fake_repo
    _put(dirs["_TESTS"] / "unit" / "test_parsed.py", src)
    assert mod.fail_open_candidates() == [], f"파서 판정을 오탐: {mod.fail_open_candidates()}"


@pytest.mark.parametrize("src", [
    "import json\ndef test_x():\n    print(json.dumps({}))\n    assert 'X' in open('x').read()\n",
    "from json import dumps\ndef test_x():\n    dumps({})\n    assert 'X' in open('x').read()\n",
    "import yaml\ndef test_x():\n    yaml.safe_dump({})\n    assert 'X' in open('x').read()\n",
], ids=["json.dumps", "from-json-dumps", "yaml.safe_dump"])
def test_parser_write_calls_do_not_count(fake_repo, src):
    """🔴 파서 모듈의 **쓰기** 호출은 구조 판정이 아니다 — `json.dumps` 하나로 bare substring 이 통과하면 안 된다.

    모듈 이름만 보면 직렬화 한 번이 파일 전체를 면제한다. 읽기 입구만 센다.
    Only read entries count; one serializer call must not exempt a bare-substring file.
    """
    mod, dirs = fake_repo
    _put(dirs["_TESTS"] / "unit" / "test_writes.py", src)
    assert "tests/unit/test_writes.py" in mod.fail_open_candidates(), (
        "직렬화 호출이 bare-substring 판정을 면제했다 — 파서 모듈 전체를 구조 도구로 셌다"
    )


# witness-corpus: 리포가 실제로 쓰는 구조 파서인데 B8 카탈로그 밖 — tokenize(B8) · shlex(_wiring_shape) · xml.etree(check_test_count_sync)
_UNLISTED_PARSERS = {
    "tokenize": "import io\nimport tokenize\n"
                "def test_x():\n    assert list(tokenize.generate_tokens(io.StringIO(open('x').read()).readline))\n",
    "shlex": "import shlex\ndef test_x():\n    assert shlex.split(open('x').read()) == ['a']\n",
    "xml.etree.ElementTree": "import xml.etree.ElementTree as ET\n"
                             "def test_x():\n    assert ET.fromstring(open('x').read()).tag == 'a'\n",
}


@pytest.mark.parametrize("module", sorted(_UNLISTED_PARSERS))
def test_parser_outside_the_catalog_is_flagged_not_waved_through(fake_repo, module):
    """카탈로그 밖의 파서만 쓰는 판정은 후보로 걸린다 — floor 는 모르는 도구를 통과시키는 쪽이 아니라 막는 쪽으로 틀린다.

    그런 파일은 `_PARSE_ENTRIES` 에 그 파서의 읽기 입구를 더하거나 `# fail-open-reviewed:` 로 사유를 단다.
    An unlisted parser errs toward flagging; extend the read-entry catalog or state a reason.
    """
    mod, dirs = fake_repo
    _put(dirs["_TESTS"] / "unit" / "test_unlisted.py", _UNLISTED_PARSERS[module])
    assert "tests/unit/test_unlisted.py" in mod.fail_open_candidates(), (
        f"카탈로그 밖 파서({module}) 판정을 구조 판정으로 셌다 — 카탈로그가 아닌 무언가가 통과시킨다"
    )


_HELPER = "import re\n_P = re.compile(r'#.*')\ndef code(s):\n    return _P.sub('', s)\n"


@pytest.mark.parametrize("importer,line", [
    ("unit/test_rel.py", "from ._clean import code\n"),
    ("unit/test_abs.py", "from tests.unit._clean import code\n"),
    ("unit/test_mod.py", "from tests.unit import _clean\n"),
], ids=["relative", "absolute", "module"])
def test_call_into_a_structural_repo_helper_counts(fake_repo, importer, line):
    """구조 도구를 부르는 리포 헬퍼에 판정을 맡긴 시험은 후보가 아니다 — 판정이 헬퍼에서 일어난다.

    `surface_invokes`(배선) · `start_argv`(Dockerfile) · 템플릿 코드 뷰가 이 모양이다.
    """
    mod, dirs = fake_repo
    _put(dirs["_TESTS"] / "unit" / "_clean.py", _HELPER)
    call = "_clean.code" if "import _clean" in line else "code"
    _put(dirs["_TESTS"] / importer,
         line + f"def test_x():\n    assert 'X' in {call}(open('x').read())\n")
    assert mod.fail_open_candidates() == [], f"구조 헬퍼 판정을 오탐: {mod.fail_open_candidates()}"


@pytest.mark.parametrize("helper,line", [
    ("def code(s):\n    return s\n", "from ._clean import code\n_ = code('')\n"),
    (_HELPER, "from ._clean import _P\n"),
], ids=["helper-without-tool", "imported-but-not-called"])
def test_repo_helper_does_not_count_unless_it_is_structural_and_called(fake_repo, helper, line):
    """🔴 대조축 — 구조 도구가 없는 헬퍼를 부르거나, 구조 헬퍼를 가져오기만 하면 여전히 후보다.

    헬퍼 해소가 «리포 모듈을 import 하면 통과» 로 무너지면 floor 가 사라진다.
    Helper resolution must not collapse into "importing any repo module passes".
    """
    mod, dirs = fake_repo
    _put(dirs["_TESTS"] / "unit" / "_clean.py", helper)
    _put(dirs["_TESTS"] / "unit" / "test_weak.py",
         line + "def test_x():\n    assert 'X' in open('x').read()\n")
    assert "tests/unit/test_weak.py" in mod.fail_open_candidates(), (
        "구조 판정이 아닌 헬퍼 사용이 bare-substring 판정을 면제했다"
    )
