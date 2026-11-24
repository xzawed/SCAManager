"""src 가 import 하는 서드파티 모듈은 `requirements.txt` 의존 폐포 안에 있어야 한다 (원장 #1917 M06 P1-15 · P1-17).

#1857 이 semgrep 을 다른 venv 로 옮기자, semgrep 전이로만 있던 `semantic_version` 이 앱 환경에서 빠졌다.
그 import 는 `try … except ImportError` 안에 있어 pylint E0401 도, 부재 시 skip 하던 시험도 보지 못했다.
여기서는 **설치본이 아니라 요구 파일 이름에서 출발한 폐포**로 판정한다 — 로컬에 남은 설치본이 결과를 가리지 않는다.

- 수집: `src/**/*.py` AST 의 절대 import 전부(함수 안 · try 안 포함) → 최상위 이름 → stdlib · `src` 제외.
- 배포판: `importlib.metadata.packages_distributions()`. 못 찾으면 red 다 — 못 재면 red.
- 폐포: `requirements.txt` 의 이름(+ 요청한 extra)에서 출발해 `importlib.metadata.requires` 를 마커로 평가하며 넓힌다.

Third-party imports under src/ must belong to the dependency closure of requirements.txt. The closure starts
from requirement names, not from what happens to be installed, so a leftover local install cannot mask a gap.
"""
from __future__ import annotations

import ast
import importlib.metadata as md
import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

_ROOT = Path(__file__).resolve().parents[2]

# 일부러 선택적인 import — 모듈 이름 → 사유. 여기 넣으려면 사유가 «없어도 동작이 맞다» 를 말해야 한다.
# Deliberately optional imports — module → reason; the reason must say why behavior stays correct without it.
_OPTIONAL: dict[str, str] = {}

Root = tuple[str, frozenset[str]]


def third_party_imports(source: str) -> set[str]:
    """한 소스의 서드파티 최상위 import 이름 — 함수 안 · try 안도 센다(그것이 E0401 이 못 본 자리다)."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return {n for n in names if n not in sys.stdlib_module_names and n not in ("src", "__future__")}


def requirement_roots(text: str) -> list[Root]:
    """요구 파일의 (배포판 이름, 요청한 extra) — 주석 · 빈 줄 · `-r` 류 옵션 줄은 건너뛴다."""
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            req = Requirement(line)
            out.append((canonicalize_name(req.name), frozenset(req.extras)))
    return out


def requirements_closure(roots: list[Root]) -> set[str]:
    """요구에서 출발한 설치 의존 폐포 — 설치되지 않은 배포판이 있으면 예외다(못 재면 red)."""
    closure: set[str] = set()
    seen: set[Root] = set()
    todo = list(roots)
    while todo:
        name, extras = todo.pop()
        if (name, extras) in seen:
            continue
        seen.add((name, extras))
        closure.add(name)
        envs = [{"extra": e} for e in sorted(extras)] or [{"extra": ""}]
        for raw in md.requires(name) or []:  # 설치돼 있지 않으면 PackageNotFoundError — 잡지 않는다
            req = Requirement(raw)
            if req.marker is None or any(req.marker.evaluate(env) for env in envs):
                todo.append((canonicalize_name(req.name), frozenset(req.extras)))
    return closure


def violations(modules: set[str], closure: set[str]) -> dict[str, str]:
    """폐포 밖 모듈 → 사유. 배포판을 못 찾는 것도 위반이다(skip 이 아니다)."""
    dists = md.packages_distributions()
    out = {}
    for mod in sorted(modules - set(_OPTIONAL)):
        found = sorted({canonicalize_name(d) for d in dists.get(mod, [])})
        if not found:
            out[mod] = "설치된 배포판을 못 찾았다 — requirements.txt 에 선언하고 설치했는가"
        elif not any(d in closure for d in found):
            out[mod] = f"배포판 {found} 이 requirements.txt 폐포 밖이다 — 직접 선언이 필요하다"
    return out


def _src_imports() -> dict[str, list[str]]:
    used: dict[str, list[str]] = {}
    for path in sorted((_ROOT / "src").rglob("*.py")):
        for mod in third_party_imports(path.read_text(encoding="utf-8")):
            used.setdefault(mod, []).append(path.relative_to(_ROOT).as_posix())
    return used


def _app_closure() -> set[str]:
    return requirements_closure(requirement_roots((_ROOT / "requirements.txt").read_text(encoding="utf-8")))


def test_every_third_party_import_in_src_is_in_the_requirements_closure():
    """🔴 가드된 지연 import 도 선언된 의존이어야 한다 — 빠지면 운영 이미지에서 조용히 폴백을 탄다(#1857)."""
    used = _src_imports()
    bad = violations(set(used), _app_closure())
    assert not bad, "\n".join(f"{m}: {why} (쓰는 곳 {used[m][:3]})" for m, why in bad.items())


def test_the_measurement_is_not_vacuous():
    """🔴 공허화 방어 — 수집한 import 와 폐포가 비어 있지 않고, 직접 핀이 폐포에 든다."""
    used, closure = _src_imports(), _app_closure()
    assert used and closure
    assert "fastapi" in used and "fastapi" in closure


def test_guarded_and_function_level_imports_are_collected():
    """🔴 E0401 이 못 본 두 자리 — try 안의 import 와 함수 안의 import — 를 수집기가 본다."""
    src = (
        "try:\n    import guarded_mod_x\nexcept ImportError:\n    guarded_mod_x = None\n"
        "def f():\n    from lazy_mod_y.sub import thing\n    return thing\n"
        "import os\nfrom . import sibling\nfrom src.shared import z\n"
    )
    assert third_party_imports(src) == {"guarded_mod_x", "lazy_mod_y"}


def test_an_undeclared_or_uninstalled_module_is_a_violation():
    """🔴 계기 뒤집기 — 설치는 됐지만 선언 안 된 모듈(pytest) · 설치조차 안 된 모듈 모두 위반이다."""
    closure = requirements_closure(requirement_roots("fastapi==0.1\n"))
    assert "pytest" not in closure  # 전제 — fastapi 는 pytest 에 기대지 않는다
    bad = violations({"fastapi", "pytest", "definitely_not_installed_mod_z"}, closure)
    assert set(bad) == {"pytest", "definitely_not_installed_mod_z"}


def test_requested_extras_widen_the_closure():
    """🔴 `uvicorn[standard]` 처럼 요청한 extra 의 의존도 폐포에 든다 — 빼면 그 의존을 쓰는 import 가 거짓 위반이 된다."""
    plain = requirements_closure([("uvicorn", frozenset())])
    standard = requirements_closure([("uvicorn", frozenset({"standard"}))])
    assert plain < standard
