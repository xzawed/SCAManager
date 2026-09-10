"""픽셀 감사가 «스크롤한 뒤» 재는지 — 배선을 잰다.

## 무엇이 문제였나

`base.html::_revealIO` 가 `.card`·`.s-card`·`.kpi-card`·`.reveal` 에 `.reveal` 을 붙이고
`.visible` 은 **뷰포트에 들어올 때만** 붙인다. `.reveal { opacity: 0 }` 이므로 스크롤하지
않으면 첫 화면 아래 글자는 전부 `opacity:0` 이고, 대비 감사는 그것을 「보이지 않음」으로
건너뛴다 — 초록이 「전부 쟀다」로 읽힌다.

실측(2026-09-09): 스크롤 전 `/repos/{repo}/settings` 는 `.reveal` 7개 중 **4개**,
`/dashboard` 는 2개 중 **1개** 가 `opacity<0.99` 였다. 스크롤을 넣자 관측 글자가 늘고
결론이 «양방향» 으로 바뀌었다 — 페이드 도중에 재던 거짓 미달이 사라지고, 첫 화면 아래
있던 진짜 미달이 드러났다.

## 🔴 이 가드가 «e2e 시험» 이 아니라 여기 있는 이유

e2e 쪽 시험(`test_the_aa_sweep_measures_below_the_fold_too`)은 `_reveal_all` 을 **직접**
부른다. 그래서 누군가 네 스윕에서 `_reveal_all` 호출을 «떼어내도» 그 시험은 초록으로
남는다 — 함수가 비어야만 red 다. 정의와 배선은 다른 축이고, 그 어긋남은 조용하다
(Grok 반증 `01a081c4`). 배선은 구조로 잰다.

## 🔴 이 가드가 «하지 못하는» 것

- 내부 스크롤 컨테이너(`overflow-y:auto`)는 `window.scrollTo` 로 안 움직인다. 현재
  스윕 대상 화면은 문서 스크롤이지만, 열린 모달처럼 내부에서 스크롤하는 표면이
  스윕에 들어오면 이 축은 다시 열린다.
- 「스크롤했는가」만 본다. 스크롤 «폭» 이 충분한지는 e2e 쪽 잔여 카운트가 잰다.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SWEEP = _ROOT / "e2e" / "test_theme_mobile_guards.py"

# 픽셀 감사를 «돌리는» 표식 — 이 상수를 evaluate 하면 그 함수는 화면을 재는 스윕이다.
# 목록을 손으로 적지 않으려고 이름 규칙(`*_AUDIT_JS`/`*_BASE_JS`)에서 파생한다.
_AUDIT_SUFFIXES = ("_AUDIT_JS", "_BASE_JS")

# 스크롤을 «자기 방식으로» 하는 함수의 면제 — 사유와 함께 두고, 사라지면 red 다.
# 🔴 지금은 비어 있다. 판정식이 `_reveal_all(` «또는» `scrollTo(` 를 받으므로, 자체
#    스크롤 루프를 가진 랜딩 스윕은 면제 없이 그대로 통과한다. 면제를 남겨뒀더니
#    역방향 검사가 곧바로 「죽은 면제」로 잡았다 — 필요 없는 면제는 두지 않는다.
_EXEMPT: dict[str, str] = {}


def _audit_constants() -> set[str]:
    """`*_AUDIT_JS`·`*_BASE_JS` 로 끝나는 모듈 상수 이름."""
    tree = ast.parse(_SWEEP.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in tree.body:
        for target in getattr(node, "targets", []):
            if isinstance(target, ast.Name) and target.id.endswith(_AUDIT_SUFFIXES):
                out.add(target.id)
    return out


def sweep_functions() -> dict[str, bool]:
    """{픽셀 감사를 돌리는 함수 이름: 스크롤을 태우는가}."""
    src = _SWEEP.read_text(encoding="utf-8")
    tree = ast.parse(src)
    audits = _audit_constants()
    out: dict[str, bool] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # 🔴 `evaluate(_TOKEN_TEXT_AUDIT_JS)` 문자열로 찾으면 안 된다. admin·랜딩 스윕은
        #    상수를 **루프 변수**에 담아 `evaluate(js)` 로 부른다(`for js in (…):`).
        #    문자열 매칭은 그 둘을 통째로 놓쳤다 — 탐지 밖이면 가드가 없는 것과 같다.
        #    이름을 «참조하는가» 로 본다.
        names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        if not (names & audits):
            continue
        body = ast.unparse(node)
        out[node.name] = ("_reveal_all(" in body) or ("scrollTo(" in body)
    return out


def test_every_pixel_audit_scrolls_before_measuring():
    """🔴 픽셀 감사를 돌리면서 스크롤하지 않는 함수가 있으면 그 화면은 첫 화면만 재진다.

    Any function that runs a pixel audit without scrolling only ever sees the first viewport.
    """
    sweeps = sweep_functions()
    assert sweeps, "픽셀 감사를 돌리는 함수를 0개 찾았다 — 스캔이 죽었다(공허한 초록)"
    missing = sorted(n for n, ok in sweeps.items() if not ok and n not in _EXEMPT)
    assert not missing, (
        "픽셀 감사를 돌리면서 스크롤하지 않는다 — 첫 화면 아래는 관측되지 않는다:\n  "
        + "\n  ".join(missing))


def test_the_scroll_helper_actually_scrolls():
    """🔴 `_reveal_all` 이 껍데기면 위 시험은 「배선됐다」만 보고 아무것도 못 잰다."""
    src = _SWEEP.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_reveal_all"), None)
    assert fn is not None, "`_reveal_all` 이 없다 — 스크롤 관용구가 사라졌다"
    body = ast.unparse(fn)
    # 🔴 `"scrollTo(" in body` 로는 부족하다 — 헬퍼 끝의 «맨 위로 복귀»(`scrollTo(0, 0)`)가
    #    그 조건을 혼자 만족시켜, 실제 훑기 루프를 지워도 초록이었다(뮤테이션 실증).
    #
    # 🔴 그 다음 판이던 `scrollTo\(\s*0\s*,\s*(?!0\s*\))` 도 통과했다. `\s*` 가 0글자로
    #    «되물러» 부정 선읽기가 공백 위치에서 성립해 버린다 — 이 세션에서 이미 한 번 겪은
    #    백트래킹 구멍과 같은 부류다. 선읽기로 부류를 판정하지 말고 «인자를 꺼내» 본다.
    offsets = [a.strip() for a in re.findall(r"scrollTo\(\s*0\s*,([^)]*)\)", body)]
    assert offsets, "`_reveal_all` 에 `scrollTo` 호출이 없다(껍데기)"
    assert any(o != "0" for o in offsets), (
        f"`_reveal_all` 이 «맨 위로» 만 스크롤한다({offsets}) — "
        "훑기 루프가 없으면 아무것도 드러나지 않는다")
    assert "scrollHeight" in body, "문서 끝까지 훑지 않는다 — 일부만 드러난다"
    assert "_settle_animations(" in body, (
        "드러낸 뒤 애니메이션을 정착시키지 않는다 — 페이드 «도중» 값을 재게 된다")


def test_exemptions_still_point_at_a_real_sweep():
    """🔴 죽은 면제는 「이미 따져봤다」로 읽히면서 아무것도 가리지 않는다."""
    sweeps = sweep_functions()
    stale = sorted(n for n in _EXEMPT if n not in sweeps)
    assert not stale, (
        "면제 목록이 실재하지 않는 함수를 가리킨다 — 지우거나 갱신한다:\n  "
        + "\n  ".join(stale))


def test_the_mobile_target_threshold_is_the_wcag_value():
    """🔴 가드는 «자기 자신이 꺼지는 것» 을 못 잡는다 — 임계값을 밖에서 고정한다.

    실측: e2e 판정식을 `< 1` 로 낮추는 뮤테이션이 **green 으로 통과**했다.
    판정 기준은 한 곳(`_TARGET_MIN`)에서 오고, 그 값이 규범값인지는 여기서 잰다.
    SC 2.5.8 Target Size (Minimum) = 24 CSS px (2.5.5 의 AAA 44 가 아니다).
    """
    src = _SWEEP.read_text(encoding="utf-8")
    m = re.search(r"^_TARGET_MIN\s*=\s*(\d+)", src, re.M)
    assert m, "`_TARGET_MIN` 이 없다 — 임계값이 다시 JS 안으로 숨었다"
    assert int(m.group(1)) == 24, (
        f"타깃 크기 임계값이 {m.group(1)} 이다 — SC 2.5.8 은 24 CSS px 다")
    assert "_TARGET_AUDIT_JS, _TARGET_MIN" in src, (
        "감사 JS 가 임계값을 «인자로» 받지 않는다 — JS 안에 숫자를 박으면 "
        "그 숫자만 조용히 낮출 수 있다")
    # 🔴 `r.width < 1` 은 «빈 상자 걸러내기» 라 정당하다 — 처음엔 그것까지 금지해
    #    스스로 red 를 냈다. 금지 대상은 «임계값» 이므로 두 자리 리터럴만 막는다.
    assert not re.search(r"r\.(width|height)\s*<\s*\d{2,}", src), (
        "감사 JS 가 임계값을 리터럴과 견준다 — 인자(MIN)로 견줘야 한 곳만 고칠 수 있다")


# ── admin 도달 관용구가 «공용» 인지 (#1639 W10) ───────────────────────────────

def _e2e_files() -> list:
    return sorted((_ROOT / "e2e").glob("test_*.py"))


def test_admin_screens_are_only_opened_through_the_shared_fixture():
    """🔴 `/admin/*` 을 여는 시험은 «관용구» 를 써야 한다 — 안 쓰면 남의 페이지를 잰다.

    실측: 세션 쿠키 없이 `/admin/*` 을 연 프로브가 **github.com 을 72조합 측정**하고,
    GitHub 로그인 페이지의 결함(이름 없는 아이콘 버튼 30·작은 타깃 37·중복 id 4)을
    이 앱의 결함으로 집계했다. 남의 DOM 을 우리 것으로 적는 것이 가장 나쁜 오측이다.

    `require_admin` 은 `require_login` 을 «평범한 함수» 로 부르므로 conftest 의
    `dependency_overrides` 가 그 경로에는 적용되지 않는다 — 진짜 세션 쿠키만이 유일한 길이다.

    Tests that open /admin/* must use the shared fixture, or they measure GitHub's page.
    """
    # 🔴 «파일» 단위로 보면 안 된다 — 같은 파일의 다른 시험이 관용구를 쓰면 통과한다.
    #    실측: admin 시험의 픽스처를 `seeded_page` 로 되돌리는 뮤테이션이 green 이었다.
    #    시험 «함수» 단위로 본다.
    offenders = []
    for path in _e2e_files():
        src = path.read_text(encoding="utf-8")
        if "/admin/" not in src:
            continue
        tree = ast.parse(src)
        admin_consts = {}
        for n in tree.body:
            for t in getattr(n, "targets", []):
                if isinstance(t, ast.Name):
                    admin_consts[t.id] = ast.unparse(n.value)
        for node in ast.walk(tree):
            if not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name.startswith("test_")):
                continue
            body = ast.unparse(node)
            # 🔴 경로가 «모듈 상수» 에 있으면 본문에 `/admin/` 문자열이 없다 —
            #    admin 시험이 `_ADMIN_PATHS` 를 쓰는 형태였고, 첫 판은 그래서 건너뛰었다.
            #    참조하는 이름의 모듈 상수 값까지 따라간다.
            refs = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            touches_admin = "/admin/" in body or any(
                "/admin/" in v for k, v in admin_consts.items() if k in refs)
            if not touches_admin:
                continue
            params = {a.arg for a in node.args.args}
            if "admin_page" in params or "admin_session_cookie" in body:
                continue
            offenders.append(f"{path.name}::{node.name}")
    assert not offenders, (
        "`/admin/*` 을 열면서 공용 admin 관용구(`admin_page` 픽스처)를 쓰지 않는다 — "
        "세션 없이 열면 GitHub 로그인 페이지를 재게 된다:\n  " + "\n  ".join(offenders))


def test_the_shared_admin_idiom_lives_in_conftest():
    """🔴 관용구가 한 시험 파일에만 있으면 다음 프로브가 같은 실수를 반복한다.

    정의가 «공용 위치» 에 있어야 새 파일이 자연히 집어 쓴다.
    """
    conftest = (_ROOT / "e2e" / "conftest.py").read_text(encoding="utf-8")
    assert "def admin_session_cookie(" in conftest, (
        "`admin_session_cookie` 가 conftest 에 없다 — 시험 파일 안에 갇히면 공용이 아니다")
    assert "def admin_page(" in conftest, (
        "`admin_page` 픽스처가 conftest 에 없다 — 쿠키를 손으로 붙이게 되면 빠뜨릴 수 있다")
    assert "def _assert_still_on_our_app(" in conftest, (
        "외부 이동 검사가 conftest 에 없다 — 그 검사가 없으면 «남의 페이지» 를 재고도 초록이다")
    # 🔴 정의만으로는 부족하다 — 실제로 «쓰여야» 한다. 첫 판은 conftest 에 두기만 하고
    #    시험은 인라인 단언을 계속 써서, 헬퍼가 죽은 채 남아 있었다(Grok `01a08b4a`).
    # 🔴 «언급» 이 아니라 «호출» 을 요구한다 — 시그니처에 픽스처 이름만 남겨도 언급은
    #    참이라, 호출을 지우는 뮤테이션이 green 이었다.
    users = [p.name for p in _e2e_files()
             if re.search(r"assert_still_on_our_app\s*\(", p.read_text(encoding="utf-8"))]
    assert users, (
        "`assert_still_on_our_app` 을 쓰는 e2e 시험이 없다 — 정의만 있고 배선이 없는 "
        "헬퍼는 다음 사람에게 «이미 지켜진다» 로 읽힌다")
