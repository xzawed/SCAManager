"""픽셀 접근성 스윕이 «모든 화면» 을 여는지 닫는다 (회고 2026-09-07 P1-37).

## 무엇이 문제였나

접근성 e2e 는 화면 경로를 **손으로 적은 상수 목록**으로 돈다. 목록에 없는 화면은 원리적으로
관측되지 않고, 그 사실은 어디에도 나타나지 않는다 — 초록이 「전부 쟀다」로 읽힌다.

실측으로 두 화면이 밖에 있었다:

- `/repos/add`
- `/repos/{repo}/analyses/{id}` — 경로에 **id 가 들어가** parametrize 상수로 적을 수 없어서
  빠졌다. 그리고 바로 그 화면에서 심각도 칩이 리터럴 hex 라 24조합 중 16건이 AA 미달인
  채로 있었다(#1633). 「목록에 못 적는 화면」이 조용히 빠지는 것이 이 스윕의 구조적 구멍이다.

## 🔴 이 가드가 «화면» 을 정하는 방법

`@router.get` 중 **RedirectResponse 를 돌려주는 것은 화면이 아니다**. `/insights`·
`/insights/me` 는 301 이라 여기서 제외한다 — 넣으면 리다이렉트 대상만 두 번 재고
「10화면 중 8」 같은 거짓 결손을 만든다.

파생이 앱과 어긋나지 않도록, 파생한 경로가 실제 등록 경로 집합에 있는지도 함께 본다.
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SWEEP = _ROOT / "e2e" / "test_theme_mobile_guards.py"
_ROUTES_DIR = _ROOT / "src" / "ui" / "routes"


def _screen_routes() -> dict[str, str]:
    """{전체 경로: 정의 파일} — 화면을 렌더하는 GET 라우트만."""
    out: dict[str, str] = {}
    for path in sorted(_ROUTES_DIR.rglob("*.py")):
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        prefix = ""
        m = re.search(r'APIRouter\([^)]*prefix\s*=\s*"([^"]*)"', src, re.S)
        if m:
            prefix = m.group(1)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            route = None
            for dec in node.decorator_list:
                if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr == "get" and dec.args
                        and isinstance(dec.args[0], ast.Constant)):
                    route = dec.args[0].value
            if route is None:
                continue
            # 🔴 화면 판정은 «렌더하는가» 하나로 한다. 리다이렉트(`/insights`·
            #    `/insights/me` — 301)는 이 검사에서 자연히 빠진다.
            #    반환 애노테이션으로 한 번 더 거르는 분기를 두었다가 걷어냈다: 실측상
            #    `ann=RedirectResponse` 2건 모두 본문에 `TemplateResponse` 가 없고
            #    둘을 «함께» 가진 함수는 0건이라 그 분기는 어떤 뮤테이션으로도 죽지 않는
            #    중복이었다. 그리고 앞으로 「조건부 리다이렉트 + 렌더」 라우트가 생기면
            #    그것은 «화면이 맞으므로», 애노테이션으로 빼면 오히려 틀린다.
            if "TemplateResponse" not in ast.unparse(node):
                continue
            out[prefix + route] = path.relative_to(_ROOT).as_posix()
    return out


def _swept_paths() -> set[str]:
    """접근성 스윕이 여는 경로 — 상수 목록 + 파일 안의 리터럴 경로 전부."""
    src = _SWEEP.read_text(encoding="utf-8")
    found: set[str] = set()
    tree = ast.parse(src)
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and isinstance(node.value, (ast.List, ast.Tuple))):
            continue
        for elt in node.value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str) \
                    and elt.value.startswith("/"):
                found.add(elt.value)
    # 🔴 f-string 경로(예: 분석 상세 `f".../analyses/{id}"`)는 접두 리터럴만 남는다.
    #    그대로 두면 `/…/analyses/` 로 끝나 라우트의 `{analysis_id}` 조각과 대조되지 않고
    #    「안 연다」로 오판한다. 동적 조각을 placeholder 로 되살린다.
    for m in re.finditer(r'f"(/[^"{]*)\{', src):
        prefix = m.group(1)
        found.add(prefix + "__dynamic__" if prefix.endswith("/") else prefix)
    return found


def _route_to_regex(route: str) -> re.Pattern:
    """라우트 패턴 → 스윕 경로와 대조할 정규식.

    🔴 `{repo_name:path}` 를 `.+` 로 두면 안 된다 — 그러면 `/repos/{repo}` 가
    `/repos/owner/testrepo/settings` 에도 맞아, 실제로는 안 여는 화면을 «열었다» 고
    판정한다. e2e 리포 이름은 `owner/testrepo`(또는 `owner%2Ftestrepo`) 두 조각이므로
    거기까지만 먹게 좁힌다.
    """
    pat = re.escape(route)
    pat = pat.replace(re.escape("{repo_name:path}"), r"[^/]+(?:/|%2F)[^/]+")
    pat = re.sub(r"\\\{[^}]*\\\}", r"[^/]+", pat)
    return re.compile("^" + pat + "$")


def test_every_screen_route_is_opened_by_the_accessibility_sweep():
    """🔴 화면 라우트 하나가 스윕 목록 밖이면 그 화면은 «한 번도» 관측되지 않는다.

    가드가 자기 목록 밖을 못 보는 것과 같은 부류다. 목록을 손으로 유지하는 한 새 화면은
    조용히 빠지고, 초록은 「전부 쟀다」로 읽힌다.

    Every screen route must be opened by the sweep; a hand list silently drops new screens.
    """
    screens = _screen_routes()
    swept = _swept_paths()
    assert screens, "화면 라우트를 0개 찾았다 — 스캔이 죽었다(공허한 초록)"
    assert swept, "스윕 경로를 0개 찾았다 — 스캔이 죽었다(공허한 초록)"

    uncovered = []
    for route, where in sorted(screens.items()):
        rx = _route_to_regex(route)
        if not any(rx.match(p) for p in swept):
            uncovered.append(f"{route}  ({where})")
    assert not uncovered, (
        "접근성 스윕이 열지 않는 화면이 있다 — 그 화면의 대비·포커스는 아무도 재지 않는다:\n  "
        + "\n  ".join(uncovered))


def test_derived_screen_routes_are_actually_registered():
    """🔴 계기 자기검증 — 소스에서 파생한 경로가 앱에 실제로 등록돼 있어야 한다.

    파생이 앱과 어긋나면 위 시험은 «존재하지 않는 화면» 을 요구하거나(거짓 red),
    실재하는 화면을 빼먹는다(거짓 초록). 등록 경로 집합과 교차 확인한다.
    """
    for key, val in {
        "DATABASE_URL": "sqlite:///:memory:", "GITHUB_WEBHOOK_SECRET": "s",
        "GITHUB_TOKEN": "g", "TELEGRAM_BOT_TOKEN": "1:a", "TELEGRAM_CHAT_ID": "-1",
        "SESSION_SECRET": "x" * 32,
    }.items():
        os.environ.setdefault(key, val)
    import sys
    sys.path.insert(0, str(_ROOT / "tests" / "unit"))
    from _route_helpers import registered_paths  # noqa: PLC0415
    from src.main import app  # noqa: PLC0415

    registered = registered_paths(app)
    assert registered, "등록 경로를 0개 얻었다 — 헬퍼가 죽었다(공허한 초록)"
    missing = sorted(r for r in _screen_routes() if r not in registered)
    assert not missing, (
        "소스에서 파생한 화면 경로가 앱에 등록돼 있지 않다 — 파생이 앱과 어긋났다:\n  "
        + "\n  ".join(missing))
