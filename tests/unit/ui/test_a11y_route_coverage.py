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


# ── 화면 «상태» — 한 라우트가 여러 UI 인 경우 ─────────────────────────────────

def dashboard_modes() -> set[str]:
    """`?mode=` 분기를 **라우터의 SSOT** 에서 파생한다.

    🔴 처음에는 템플릿을 `mode == '<x>'` 로 grep 했다. 그건 SSOT 가 아니다 —
    따옴표 종류·`mode in (...)`·파이썬 쪽에서만 갈리는 분기를 놓치고, 낱말 경계가 없어
    `foo_mode == 'x'` 같은 것도 주워 담는다(Grok `01a08b4a`).
    유효 모드의 정본은 `src/ui/routes/dashboard.py::_VALID_MODES` 다.
    """
    src = (_ROOT / "src" / "ui" / "routes" / "dashboard.py").read_text(encoding="utf-8")
    m = re.search(r"_VALID_MODES\s*=\s*\(([^)]*)\)", src)
    assert m, "`_VALID_MODES` 를 찾지 못했다 — 모드 SSOT 가 옮겨졌다"
    return set(re.findall(r"[\"']([a-z_]+)[\"']", m.group(1)))


def _contrast_sweep_paths() -> set[str]:
    """대비 감사가 «실제로» 여는 경로 — `_TOKEN_TEXT_PATHS` 만 본다.

    🔴 `_swept_paths()` 처럼 파일 안 모든 리터럴을 합치면 안 된다. 그 함수는 «타깃 크기»
    축이 넣은 `?mode=` 문자열까지 세어, 대비 축이 그 화면을 여는 것처럼 보이게 만든다
    (Grok `01a08aa1`). 축마다 자기 목록을 본다.
    """
    src = _SWEEP.read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if not (isinstance(node, ast.Assign) and isinstance(node.value, (ast.List, ast.Tuple))):
            continue
        if any(isinstance(t, ast.Name) and t.id == "_TOKEN_TEXT_PATHS" for t in node.targets):
            return {e.value for e in node.value.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    raise AssertionError("`_TOKEN_TEXT_PATHS` 를 찾지 못했다 — 시험이 늙었다")


def test_the_contrast_sweep_opens_every_dashboard_mode():
    """🔴 대시보드는 «한 화면» 이 아니다 — `?mode=` 마다 다른 DOM 이다.

    실측(2026-09-09 400조합): 대비 스윕은 `/dashboard` 하나만 열어 기본 모드 외 4개는
    한 번도 관측되지 않았다. 그런데 라우트 커버리지 가드는 **초록**이었다 — `/dashboard`
    가 라우트로는 덮였고, 타깃 크기 축이 넣은 `?mode=` 리터럴까지 합쳐 세기 때문이다.
    「초록 = 쟀다」가 되지 않도록 축마다 따로 요구한다.

    The dashboard renders five different UIs; the contrast sweep opened only the default.
    """
    modes = dashboard_modes()
    assert len(modes) >= 2, f"대시보드 mode 분기를 {len(modes)}개 찾았다 — 파생이 죽었다"
    # 🔴 목록을 읽는 것만으로는 부족하다 — 대비 시험이 «그 목록» 을 parametrize 해야
    #    의미가 있다. 데코레이터를 `_FOCUS_PATHS` 로 바꾸면 이 가드는 초록인 채
    #    모드가 다시 안 재진다(Grok `01a08b4a`).
    src = _SWEEP.read_text(encoding="utf-8")
    assert re.search(
        r'@pytest\.mark\.parametrize\(\s*"path",\s*_TOKEN_TEXT_PATHS\s*\)\s*\n'
        r"def test_token_text_meets_aa_against_painted_background", src), (
        "대비 시험이 `_TOKEN_TEXT_PATHS` 를 parametrize 하지 않는다 — "
        "이 가드가 읽는 목록과 실제로 여는 목록이 갈렸다")
    swept = _contrast_sweep_paths()
    missing = sorted(m for m in modes
                     if not any(f"mode={m}" in p for p in swept)
                     # 기본 모드는 `?mode=` 없이도 열린다 — `/dashboard` 로 충분하다.
                     and not (m == "overview" and "/dashboard" in swept))
    assert not missing, (
        "대비 스윕이 열지 않는 대시보드 모드가 있다 — 그 화면의 글자 대비는 "
        f"어떤 조합에서도 관측되지 않는다: {missing}\n  여는 경로: {sorted(swept)}")


# ── 상호작용 «상태» — 클릭해야 나타나는 표면 ──────────────────────────────────

def interactive_states() -> dict[str, str]:
    """{셀렉터: 어디} — 클릭·입력으로만 나타나는 상태를 **소스에서 파생**한다.

    판정 근거는 두 가지다:
      - `aria-haspopup="true"` 를 가진 버튼이 여는 대상(드롭다운·메뉴)
      - 기본이 숨김(`.hidden`)이거나 «보임» 상태 클래스(`.visible`)로만 드러나는 오버레이

    🔴 손으로 목록을 적으면 새 상태가 조용히 빠진다 — 이 리포는 설정 `advanced`
    (`.adv-only` 22요소)와 모바일 nav 오버레이를 그렇게 놓친 적이 있다.

    값에 «어느 규칙이 찾았는지» 를 붙인다 — 규칙이 죽으면 파생이 줄고, 「파생 ⊆ 스윕」만
    보는 가드는 그때 **조용히 초록**이다(실증: 규칙 (c) 를 통째로 지워도 통과).
    """
    out: dict[str, str] = {}
    for path in sorted((_ROOT / "src" / "templates").glob("*.html")):
        raw = path.read_text(encoding="utf-8")
        # 🔴 Jinja 를 먼저 걷어낸다. `class="{% if … %}is-hidden{% endif %}"` 는
        #    «데이터 조건» 분기(#1639 W12)이지 클릭으로 여는 상태가 아니다 — 섞으면 이
        #    가드가 시드 문제까지 떠안아 영영 red 다. 태그를 지우면 그 class 는 빈다.
        src = re.sub(r"\{%.*?%\}|\{\{.*?\}\}", "", raw, flags=re.S)
        where = path.name
        # 🔴 속성 «순서» 를 가정하지 않는다 — 이슈 모달은 `class=... id=...` 순서라
        #    `id="…"[^>]*class=` 정규식이 통째로 놓쳤다. 태그를 통으로 잡고 안을 본다.
        for m in re.finditer(r"<[a-z]+\b[^>]*>", src):
            tag = m.group(0)
            mid = re.search(r'id="([\w-]+)"', tag)
            if not mid:
                continue
            cls = re.search(r'class="([^"]*)"', tag)
            classes = cls.group(1).split() if cls else []
            # (a) 열리는 메뉴  (b) 기본이 숨김인 오버레이 — «단독 토큰» hidden
            #     🔴 `\bhidden\b` 로 보면 `is-hidden` 도 걸린다(하이픈이 낱말 경계다).
            if 'role="menu"' in tag:
                out[f"#{mid.group(1)}"] = f"{where} (a:menu)"
            elif "hidden" in classes:
                out[f"#{mid.group(1)}"] = f"{where} (b:hidden)"
            # (d) 인라인 `style="display:none"` — CSS 를 아무리 봐도 안 보이는 축이다.
            #     🔴 (a)~(c) 는 모두 «클래스» 를 본다. `#telegramOtpDisplay` 는 클래스가
            #        없고 JS 가 `style.display=''` 로 열어, 세 규칙 어디에도 안 걸렸다
            #        (Grok `01a08bda`). 숨기는 방법이 하나가 아니다.
            elif re.search(r'style="[^"]*display\s*:\s*none', tag):
                out[f"#{mid.group(1)}"] = f"{where} (d:inline-none)"
        # (c) 상태 클래스로만 «드러나는» 면.
        #     🔴 클래스 «이름» 을 추측하지 않는다. 첫 판은 `.visible` 만 봐서
        #        `add_repo.html` 의 `.toast.show` 를 놓쳤고(Grok `01a08bb5`), 이름 목록을
        #        `show|open|active` 로 넓히자 이번엔 `.filter-btn.active` 처럼 «항상 보이는
        #        컨트롤의 선택 상태» 까지 8건 딸려 왔다 — 그건 이미 관측되는 면이다.
        #        판정 근거는 이름이 아니라 성질이다: **그 클래스가 없으면 안 보이는가.**
        base_hidden = {m.group(1) for m in re.finditer(
            r"\.([\w-]+)\s*\{([^}]*)\}", src)
            if re.search(r"(?<![-\w])(?:display\s*:\s*none|opacity\s*:\s*0(?!\.)|"
                         r"visibility\s*:\s*hidden)", m.group(2))}
        for m in re.finditer(r"\.([\w-]+)\.([\w-]+)\s*\{", src):
            if m.group(1) in base_hidden:
                out[f".{m.group(1)}"] = f"{where} (c:state-class)"
    return out


# 열 수는 있으나 «잴 것이 없는» 상태 — 사유와 함께 두고, 사라지면 red 다(역방향).
_STATE_EXEMPT = {
    "#reinstall_hook_form":
        "글자가 없는 POST 껍데기다(`<form>` 안이 비었다) — 사람에게 «보이는» 적이 없다.",
    "#reinstall_webhook_form":
        "글자가 없는 POST 껍데기다(`<form>` 안이 비었다) — 사람에게 «보이는» 적이 없다.",
}


def _sweep_state_openers() -> set[str]:
    """스윕이 «직접 여는» 상태 — e2e 의 `_STATE_OPENERS` 키를 AST 로 꺼낸다.

    🔴 `sel not in src` 로 보면 안 된다 — 부분문자열이다. `.save-bar` 를
    `.save-bar-GONE` 으로 바꾸는 뮤테이션이 green 으로 통과했다(앞 글자가 그대로 들어
    있으므로). 딕셔너리 «키» 로 정확히 본다.
    """
    for node in ast.walk(ast.parse(_SWEEP.read_text(encoding="utf-8"))):
        if (isinstance(node, ast.Assign)
                and any(getattr(t, "id", None) == "_STATE_OPENERS" for t in node.targets)
                and isinstance(node.value, ast.Dict)):
            return {k.value for k in node.value.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    raise AssertionError("e2e 스윕에서 `_STATE_OPENERS` 를 찾지 못했다 — 이름이 바뀌었다")


# `_STATE_OPENERS` 밖에서 열리는 면 — 여는 «곳» 을 사유로 적는다.
_OPENED_ELSEWHERE = {
    ".nav-links": "모바일 nav 오버레이 — 햄버거를 눌러 여는 전용 시험이 이미 있다(#1637).",
    ".reveal": "스크롤로 드러난다 — 모든 픽셀 감사 앞의 `_reveal_all` 이 연다.",
}


def test_interactive_states_and_what_the_sweep_opens_are_the_same_set():
    """🔴 클릭해야 나타나는 상태는 «열지 않으면» 어떤 픽셀 감사도 그 면을 보지 못한다.

    실측(400조합 프로브): 테마·언어 드롭다운, `.save-bar`, 이슈 모달은 어떤 스윕에도
    없었다. 모바일 nav 오버레이(#1637)와 설정 advanced(#1641)가 같은 부류였고, 둘 다
    열자마자 진짜 미달이 나왔다 — 「목록에 못 적는 상태」가 이 스윕의 구조적 구멍이다.

    🔴 **부분집합으로 보면 안 된다.** 「파생 ⊆ 스윕」만 걸면 파생을 «줄이는» 변경이
    전부 초록이다 — 못 찾은 면은 없는 면과 구별되지 않으므로. 규칙마다 「≥1」 바닥을
    걸어도 마찬가지다(Grok `01a08bd2` 가 규칙 (b)·(c) 각각에 대해 실증: 이름을
    `.visible` 로 되돌리면 `.toast`·`.nav-links` 가 조용히 빠지는데 (c) 는 여전히 3을
    찾아 바닥을 넘는다). 그래서 **양방향 등식**이다 — 한쪽이 줄어도 red 다.

    The derived surfaces and the surfaces the sweep opens must be the SAME set:
    a subset guard goes green whenever the derivation itself shrinks.
    """
    states = interactive_states()
    claimed = _sweep_state_openers() | set(_STATE_EXEMPT) | set(_OPENED_ELSEWHERE)

    unopened = sorted(f"{sel}  ({states[sel]})" for sel in states.keys() - claimed)
    assert not unopened, (
        "스윕이 열지 않는 상호작용 상태가 있다 — 그 면의 대비·크기는 관측되지 않는다:\n  "
        + "\n  ".join(unopened))

    # 이 축이 «죽은 면제» 도 잡는다 — 면제가 실재하지 않는 면을 가리키면 여기서 red.
    vanished = sorted(claimed - states.keys())
    assert not vanished, (
        "스윕·면제가 가리키는 면을 파생이 더는 찾지 못한다 — 소스에서 사라졌거나 "
        "**파생 규칙이 약해졌다**(후자면 다른 면들도 같이 빠진 것이다):\n  "
        + "\n  ".join(vanished))
