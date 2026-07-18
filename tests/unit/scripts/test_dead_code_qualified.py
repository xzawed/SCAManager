"""dead-code 가드의 **한정 참조** 계약 (회고 2026-07-19 P1 — 이름 전역 매칭 봉인).

결함: `count_ast_references` 가 이름만 보고 `ast.Name(id=N)`·`ast.Attribute(attr=N)` 를 src 전역에서
세었다. 따라서 무관한 객체의 동명 메서드 접근(`repo.get_by_id(1)`)이 참조로 집계돼, **흔한 CRUD
명의 신규 dead 함수는 항상 '✅ all wired'** 로 통과한다. 봉인 대상이던 `find_orphaned` 가 잡힌 것은
**이름이 희귀해서**였을 뿐 — 가드의 성립 근거가 우연이었다.
Defect: references were matched by bare name across all of src/, so an unrelated `x.get_by_id()`
counted. Common CRUD names always passed; `find_orphaned` was caught only because it was rare.

수정: 참조를 **정의 모듈에 한정**한다 — 그 모듈(또는 그 심볼)을 import 한 파일에서만 집계.
Fix: count only references qualified to the defining module (file must import it).
"""
from scripts.check_dead_code import count_qualified_references, module_path_for

_MOD = "src.repositories.foo"


# ── module_path_for ──────────────────────────────────────────────────────


def test_module_path_for_converts_path_to_dotted():
    assert module_path_for("src/repositories/foo.py") == "src.repositories.foo"
    assert module_path_for("src/services/bar_service.py") == "src.services.bar_service"


def test_module_path_for_handles_windows_separators():
    """Windows 경로 구분자도 동일 결과 — 로컬 실행에서 무음 미스매치 차단."""
    assert module_path_for("src\\repositories\\foo.py") == "src.repositories.foo"


# ── 한정 참조: 집계되어야 하는 형태 (긍정 통제) ──────────────────────────


def test_direct_from_import_counts():
    """`from <정의모듈> import <name>` 후 호출 → 참조."""
    src = "from src.repositories.foo import get_by_id\n\nget_by_id(1)\n"
    assert count_qualified_references("get_by_id", _MOD, src) == 1


def test_aliased_from_import_counts():
    """`import ... as alias` 는 alias 사용을 집계."""
    src = "from src.repositories.foo import get_by_id as fetch\n\nfetch(1)\n"
    assert count_qualified_references("get_by_id", _MOD, src) == 1


def test_module_import_attribute_access_counts():
    """`from <부모> import <모듈>` 후 `모듈.name` 접근 → 참조."""
    src = "from src.repositories import foo\n\nfoo.get_by_id(1)\n"
    assert count_qualified_references("get_by_id", _MOD, src) == 1


def test_plain_module_import_counts():
    """`import src.repositories.foo` 후 전체 경로 접근 → 참조."""
    src = "import src.repositories.foo\n\nsrc.repositories.foo.get_by_id(1)\n"
    assert count_qualified_references("get_by_id", _MOD, src) == 1


def test_same_module_internal_reference_counts():
    """정의 파일 내부의 호출은 import 없이도 참조(모듈 내 사용)."""
    src = "def get_by_id(x):\n    return x\n\ndef caller():\n    return get_by_id(1)\n"
    assert count_qualified_references("get_by_id", _MOD, src, same_module=True) == 1


# ── 한정 참조: 집계되면 안 되는 형태 (부정 통제 — 결함의 핵심) ───────────


def test_unrelated_attribute_access_does_not_count():
    """🔴 결함 재현 방지 — 정의 모듈을 import 하지 않은 파일의 동명 속성 접근은 참조 아님.

    이것이 '흔한 CRUD 명은 무조건 통과' 의 원인이었다.
    """
    src = "def use(repo):\n    return repo.get_by_id(1)\n"
    assert count_qualified_references("get_by_id", _MOD, src) == 0


def test_same_name_from_different_module_does_not_count():
    """🔴 다른 모듈의 동명 심볼 import 는 참조 아님 — 이름 충돌 false-negative 봉인."""
    src = "from src.repositories.other import get_by_id\n\nget_by_id(1)\n"
    assert count_qualified_references("get_by_id", _MOD, src) == 0


def test_docstring_mention_does_not_count():
    """docstring/문자열 멘션은 참조 아님(기존 AST 규약 유지)."""
    src = '"""get_by_id 를 설명하는 문서."""\nfrom src.repositories.foo import get_by_id\n'
    # import 만 있고 호출 없음 → 0 (import 자체는 사용이 아니다)
    assert count_qualified_references("get_by_id", _MOD, src) == 0


def test_syntax_error_source_is_zero():
    """파싱 불가 파일은 0 — 예외로 가드가 죽지 않게(단, 전체 판정은 다른 파일이 담당)."""
    assert count_qualified_references("get_by_id", _MOD, "def (((:\n") == 0
