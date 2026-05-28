# SCAManager Claude Design UI 재설계 — Phase 1: Preparation Package 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude Design이 SCAManager를 완전히 이해하고 Design System을 구축할 수 있도록, 현재 서비스의 Design Brief Package (스크린샷 + 브리프 문서 6종 + 토큰 JSON)를 `docs/design/brief/`에 생성한다.

**Architecture:** 두 개의 Python 유틸리티 스크립트 (`extract_design_tokens.py` — CSS 파싱 + JSON 출력, `capture_design_screenshots.py` — Playwright 12페이지 × 4테마 자동 캡처)와 6개의 마크다운 브리프 문서로 구성된다. 스크립트는 로컬 일회성 도구이며 CI에 포함하지 않는다.

**Tech Stack:** Python 3.x, Playwright (이미 `requirements-dev.txt` 에 설치됨), re (표준 라이브러리), pathlib, json

**⚠️ Phase 3 안내:** 본 계획은 Phase 1만 다룬다. Phase 3 (HTML 템플릿 · tokens.css · themes.css 전면 재작성)은 사용자가 Claude Design에서 Design System + 12페이지 프로토타입을 완성하고 `docs/design/output/`에 결과물을 저장한 후 별도 계획을 작성한다.

---

## 파일 맵

| 상태 | 경로 | 역할 |
|------|------|------|
| 신규 | `scripts/extract_design_tokens.py` | tokens.css + themes.css → JSON 추출기 |
| 신규 | `scripts/capture_design_screenshots.py` | Playwright 12페이지 × 4테마 스크린샷 |
| 신규 | `tests/unit/scripts/test_extract_design_tokens.py` | 토큰 추출기 단위 테스트 |
| 신규 | `docs/design/brief/00-service-overview.md` | 서비스 정체성 + 사용자 페르소나 |
| 신규 | `docs/design/brief/01-current-tokens.json` | 스크립트 실행 결과 (자동 생성) |
| 신규 | `docs/design/brief/02-component-inventory.md` | 전체 UI 컴포넌트 목록 |
| 신규 | `docs/design/brief/03-design-direction.md` | A+B 하이브리드 방향 명세 |
| 신규 | `docs/design/brief/04-theme-roles.md` | 4테마 역할 정의서 |
| 신규 | `docs/design/brief/05-page-inventory.md` | 12페이지 구조 + 정보 계층 |
| 신규 | `docs/design/output/.gitkeep` | Claude Design 결과물 저장소 (빈 디렉토리 추적용) |
| 신규 | `docs/design/brief/screenshots/` | 자동 캡처 스크린샷 (48+장) |

---

## Task 1: 디렉토리 구조 + .gitignore 설정

**Files:**
- Create: `docs/design/brief/screenshots/dark/.gitkeep`
- Create: `docs/design/brief/screenshots/light/.gitkeep`
- Create: `docs/design/brief/screenshots/pastel/.gitkeep`
- Create: `docs/design/brief/screenshots/catppuccin/.gitkeep`
- Create: `docs/design/output/.gitkeep`
- Modify: `.gitignore`

- [ ] **Step 1: 디렉토리 생성 및 .gitkeep 배치**

```bash
mkdir -p docs/design/brief/screenshots/dark
mkdir -p docs/design/brief/screenshots/light
mkdir -p docs/design/brief/screenshots/pastel
mkdir -p docs/design/brief/screenshots/catppuccin
mkdir -p docs/design/output
type nul > docs/design/brief/screenshots/dark/.gitkeep
type nul > docs/design/brief/screenshots/light/.gitkeep
type nul > docs/design/brief/screenshots/pastel/.gitkeep
type nul > docs/design/brief/screenshots/catppuccin/.gitkeep
type nul > docs/design/output/.gitkeep
```

- [ ] **Step 2: .gitignore 에 스크린샷 PNG 제외 추가 (대용량 바이너리 미추적)**

`.gitignore` 파일에서 기존 `# Screenshots` 섹션을 찾거나 없으면 파일 끝에 추가:

```
# Claude Design brief screenshots (large binaries — generated locally)
docs/design/brief/screenshots/**/*.png
docs/design/output/screenshots/
```

- [ ] **Step 3: 커밋**

```bash
git add docs/design/ .gitignore
git commit -m "chore: Claude Design brief 디렉토리 구조 + .gitignore 설정"
```

---

## Task 2: 토큰 추출 스크립트 — TDD

**Files:**
- Create: `scripts/extract_design_tokens.py`
- Create: `tests/unit/scripts/test_extract_design_tokens.py`

- [ ] **Step 1: 테스트 파일 작성 (실패 확인용)**

`tests/unit/scripts/test_extract_design_tokens.py` 생성:

```python
"""
토큰 추출 스크립트 단위 테스트.
Unit tests for the design token extraction script.
"""
import json
import textwrap
from pathlib import Path

import pytest

# 스크립트 임포트 경로 설정 / Script import path setup
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from extract_design_tokens import parse_vars, extract_theme_block, categorize_root_vars


SAMPLE_ROOT_CSS = textwrap.dedent("""
    :root {
      --space-1: 4px;
      --space-2: 8px;
      --fs-xs: 12px;
      --fs-sm: 13px;
      --radius-sm: 6px;
      --elev-0: none;
      --dur-fast: 120ms;
      --blur-sm: 8px;
      --container-lg: 1200px;
      --fs-display-sm: 32px;
      --tracking-tight: -0.02em;
    }
""")

SAMPLE_THEMES_CSS = textwrap.dedent("""
    body[data-theme="dark"], body:not([data-theme]) {
      --bg-base: #07070f;
      --accent: #6366f1;
      --text-1: #f0f0f8;
    }

    body[data-theme="light"] {
      --bg-base: #f6f6fd;
      --accent: #6366f1;
      --text-1: #0f0f1a;
    }
""")


def test_parse_vars_extracts_all_custom_properties():
    css = ":root { --space-1: 4px; --fs-xs: 12px; }"
    result = parse_vars(css)
    assert result == {"--space-1": "4px", "--fs-xs": "12px"}


def test_parse_vars_trims_whitespace():
    css = ":root { --color:   #fff  ; }"
    result = parse_vars(css)
    assert result["--color"] == "#fff"


def test_extract_theme_block_dark():
    result = extract_theme_block(SAMPLE_THEMES_CSS, r'body\[data-theme="dark"\]')
    assert result["--bg-base"] == "#07070f"
    assert result["--accent"] == "#6366f1"


def test_extract_theme_block_light():
    result = extract_theme_block(SAMPLE_THEMES_CSS, r'body\[data-theme="light"\]')
    assert result["--bg-base"] == "#f6f6fd"
    assert result["--text-1"] == "#0f0f1a"


def test_extract_theme_block_missing_returns_empty():
    result = extract_theme_block(SAMPLE_THEMES_CSS, r'body\[data-theme="pastel"\]')
    assert result == {}


def test_categorize_root_vars_spacing():
    root_vars = parse_vars(SAMPLE_ROOT_CSS)
    categories = categorize_root_vars(root_vars)
    assert "--space-1" in categories["spacing"]
    assert "--space-2" in categories["spacing"]


def test_categorize_root_vars_typography():
    root_vars = parse_vars(SAMPLE_ROOT_CSS)
    categories = categorize_root_vars(root_vars)
    assert "--fs-xs" in categories["typography"]
    assert "--fs-sm" in categories["typography"]


def test_categorize_root_vars_display_typography():
    root_vars = parse_vars(SAMPLE_ROOT_CSS)
    categories = categorize_root_vars(root_vars)
    assert "--fs-display-sm" in categories["display_typography"]
    assert "--tracking-tight" in categories["display_typography"]


def test_categorize_root_vars_elevation():
    root_vars = parse_vars(SAMPLE_ROOT_CSS)
    categories = categorize_root_vars(root_vars)
    assert "--elev-0" in categories["elevation"]


def test_categorize_root_vars_motion():
    root_vars = parse_vars(SAMPLE_ROOT_CSS)
    categories = categorize_root_vars(root_vars)
    assert "--dur-fast" in categories["motion"]


def test_categorize_root_vars_radius():
    root_vars = parse_vars(SAMPLE_ROOT_CSS)
    categories = categorize_root_vars(root_vars)
    assert "--radius-sm" in categories["radius"]
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
python -m pytest tests/unit/scripts/test_extract_design_tokens.py -v
```

기댓값: `ImportError: No module named 'extract_design_tokens'`

- [ ] **Step 3: 스크립트 구현**

`scripts/extract_design_tokens.py` 생성:

```python
#!/usr/bin/env python3
"""
tokens.css / themes.css 를 파싱해 Claude Design 입력용 JSON 생성.
Parses tokens.css / themes.css and outputs structured JSON for Claude Design.

사용법 / Usage:
    python scripts/extract_design_tokens.py
출력 / Output:
    docs/design/brief/01-current-tokens.json
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS_CSS = ROOT / "src" / "static" / "css" / "tokens.css"
THEMES_CSS = ROOT / "src" / "static" / "css" / "themes.css"
OUTPUT = ROOT / "docs" / "design" / "brief" / "01-current-tokens.json"

# 테마 선택자 매핑 / Theme selector mapping
THEME_SELECTORS = {
    "dark": r'body\[data-theme="dark"\]',
    "light": r'body\[data-theme="light"\]',
    "pastel": r'body\[data-theme="pastel"\]',
    "catppuccin": r'body\[data-theme="catppuccin"\]',
}

# CSS custom property 파싱 패턴 / CSS custom property parse pattern
_VAR_RE = re.compile(r"--([\w-]+)\s*:\s*([^;]+);")


def parse_vars(css_block: str) -> dict[str, str]:
    """CSS 블록에서 custom property 추출 / Extract custom properties from CSS block."""
    return {f"--{m[0]}": m[1].strip() for m in _VAR_RE.findall(css_block)}


def extract_theme_block(css: str, selector: str) -> dict[str, str]:
    """특정 선택자 블록의 custom property 추출 / Extract vars from a specific selector block."""
    pattern = re.compile(rf"{selector}[^{{]*\{{([^}}]+)\}}", re.DOTALL)
    m = pattern.search(css)
    return parse_vars(m.group(1)) if m else {}


def categorize_root_vars(root_vars: dict[str, str]) -> dict[str, dict[str, str]]:
    """루트 변수를 카테고리별로 분류 / Categorize root variables by domain."""
    def pick(prefix_tuple):
        return {k: v for k, v in root_vars.items() if k.startswith(prefix_tuple)}

    return {
        "spacing": pick("--space-"),
        "typography": pick(("--fs-xs", "--fs-sm", "--fs-md", "--fs-base",
                             "--fs-lg", "--fs-xl", "--fs-2xl", "--fs-3xl")),
        "display_typography": pick(("--fs-display", "--tracking-", "--line-height-display")),
        "radius": pick("--radius-"),
        "elevation": pick("--elev-"),
        "motion": pick(("--dur-", "--ease-", "--anim-")),
        "blur": pick("--blur-"),
        "container": pick("--container-"),
        "grade_colors": pick("--grade-"),
        "claude_brand": pick("--claude-"),
    }


def main() -> None:
    # 실제 CSS 파일 파싱 / Parse actual CSS files
    tokens_text = TOKENS_CSS.read_text(encoding="utf-8")
    themes_text = THEMES_CSS.read_text(encoding="utf-8")

    # :root 블록 추출 / Extract :root block
    root_m = re.search(r":root\s*\{([^}]+)\}", tokens_text, re.DOTALL)
    root_vars = parse_vars(root_m.group(1)) if root_m else {}

    output = {
        "foundation": categorize_root_vars(root_vars),
        "themes": {
            name: extract_theme_block(themes_text, sel)
            for name, sel in THEME_SELECTORS.items()
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅  Tokens extracted → {OUTPUT}")
    print(f"    foundation categories: {list(output['foundation'].keys())}")
    print(f"    themes: {list(output['themes'].keys())}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
python -m pytest tests/unit/scripts/test_extract_design_tokens.py -v
```

기댓값:
```
tests/unit/scripts/test_extract_design_tokens.py::test_parse_vars_extracts_all_custom_properties PASSED
tests/unit/scripts/test_extract_design_tokens.py::test_parse_vars_trims_whitespace PASSED
tests/unit/scripts/test_extract_design_tokens.py::test_extract_theme_block_dark PASSED
tests/unit/scripts/test_extract_design_tokens.py::test_extract_theme_block_light PASSED
tests/unit/scripts/test_extract_design_tokens.py::test_extract_theme_block_missing_returns_empty PASSED
tests/unit/scripts/test_extract_design_tokens.py::test_categorize_root_vars_spacing PASSED
tests/unit/scripts/test_extract_design_tokens.py::test_categorize_root_vars_typography PASSED
tests/unit/scripts/test_extract_design_tokens.py::test_categorize_root_vars_display_typography PASSED
tests/unit/scripts/test_extract_design_tokens.py::test_categorize_root_vars_elevation PASSED
tests/unit/scripts/test_extract_design_tokens.py::test_categorize_root_vars_motion PASSED
tests/unit/scripts/test_extract_design_tokens.py::test_categorize_root_vars_radius PASSED
11 passed in 0.XXs
```

- [ ] **Step 5: 스크립트 실제 실행 + 출력 확인**

```bash
python scripts/extract_design_tokens.py
```

기댓값:
```
✅  Tokens extracted → docs\design\brief\01-current-tokens.json
    foundation categories: ['spacing', 'typography', 'display_typography', 'radius', 'elevation', 'motion', 'blur', 'container', 'grade_colors', 'claude_brand']
    themes: ['dark', 'light', 'pastel', 'catppuccin']
```

그리고 `docs/design/brief/01-current-tokens.json` 파일이 생성됐는지 확인:
```bash
python -c "import json; d=json.load(open('docs/design/brief/01-current-tokens.json')); print('dark accent:', d['themes']['dark'].get('--accent'))"
```
기댓값: `dark accent: #6366f1`

- [ ] **Step 6: pylint 확인**

```bash
python -m pylint scripts/extract_design_tokens.py
```
기댓값: `Your code has been rated at 10.00/10`

- [ ] **Step 7: 커밋**

```bash
git add scripts/extract_design_tokens.py tests/unit/scripts/test_extract_design_tokens.py docs/design/brief/01-current-tokens.json
git commit -m "feat: 디자인 토큰 추출 스크립트 추가 (tokens.css + themes.css → JSON)"
```

---

## Task 3: Playwright 스크린샷 캡처 스크립트

**Files:**
- Create: `scripts/capture_design_screenshots.py`

> ⚠️ 이 스크립트는 로컬 서버(`make run`)가 실행 중인 상태에서만 동작한다.
> 인증이 필요한 페이지는 `--session-cookie` 옵션으로 세션 쿠키를 전달한다.
> (브라우저 개발자도구 → Application → Cookies → `session` 값 복사)

- [ ] **Step 1: 스크립트 작성**

`scripts/capture_design_screenshots.py` 생성:

```python
#!/usr/bin/env python3
"""
현재 서비스 12페이지 × 4테마 스크린샷 자동 캡처 (Claude Design 브리프용).
Auto-captures 12 pages × 4 themes for Claude Design brief package.

사전 조건 / Prerequisites:
  1. make run  (로컬 서버 실행 중 / local server running)
  2. 브라우저에서 로그인 후 session 쿠키 값 복사
     Copy session cookie value from browser DevTools after login

사용법 / Usage:
  python scripts/capture_design_screenshots.py --session-cookie "<value>" --repo-id 1 --analysis-id 1

출력 / Output:
  docs/design/brief/screenshots/{dark,light,pastel,catppuccin}/{page}.png
"""
import argparse
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "design" / "brief" / "screenshots"
BASE_URL = "http://localhost:8000"
THEMES = ["dark", "light", "pastel", "catppuccin"]

# 인증 불필요 페이지 / Public pages (no auth)
PAGES_PUBLIC = [
    ("landing", "/"),
]

# 인증 필요 페이지 / Auth-required pages
PAGES_AUTH = [
    ("overview", "/overview"),
    ("dashboard", "/dashboard"),
    ("add_repo", "/repos/add"),
    ("settings", "/settings"),
]

# 데이터 의존 페이지 (repo_id / analysis_id 필요) / Data-dependent pages
PAGES_DATA = [
    ("repo_detail", "/repos/{repo_id}"),
    ("repo_insights", "/repos/{repo_id}/insights"),
    ("analysis_detail", "/repos/{repo_id}/analysis/{analysis_id}"),
]

# 어드민 페이지 / Admin pages
PAGES_ADMIN = [
    ("admin_operations", "/admin/operations"),
    ("admin_rls_audit", "/admin/rls-audit"),
    ("admin_tenants", "/admin/tenants"),
]

# 모바일 캡처 대상 페이지 / Pages to also capture at mobile width
MOBILE_PAGES = {"dashboard", "analysis_detail", "repo_detail", "settings"}


async def _set_theme(page, theme: str) -> None:
    """JS로 data-theme 속성 변경 후 트랜지션 대기 / Switch theme via JS and wait for transition."""
    await page.evaluate(f"document.body.setAttribute('data-theme', '{theme}')")
    await page.wait_for_timeout(350)  # 테마 트랜지션 안정 대기 / wait for CSS transition


async def _capture(page, name: str, theme: str, suffix: str = "") -> None:
    """스크린샷 저장 / Save screenshot."""
    filename = f"{name}{suffix}.png"
    path = OUTPUT_DIR / theme / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(path), full_page=True)
    print(f"  📸  {theme}/{filename}")


async def _capture_all_themes(page, name: str, suffix: str = "") -> None:
    """현재 페이지를 4테마 모두 캡처 / Capture current page in all 4 themes."""
    # landing 은 always-dark — dark 테마만 캡처
    # landing is always-dark — capture dark theme only
    themes = ["dark"] if name == "landing" else THEMES
    for theme in themes:
        await _set_theme(page, theme)
        await _capture(page, name, theme, suffix)


async def _make_context(browser, viewport: dict, session_cookie: str):
    """세션 쿠키 포함 컨텍스트 생성 / Create browser context with optional session cookie."""
    ctx = await browser.new_context(viewport=viewport)
    if session_cookie:
        await ctx.add_cookies([{
            "name": "session",
            "value": session_cookie,
            "domain": "localhost",
            "path": "/",
            "sameSite": "Lax",
        }])
    return ctx


async def main(args: argparse.Namespace) -> None:
    repo_id = args.repo_id
    analysis_id = args.analysis_id
    session_cookie = args.session_cookie

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # ── 데스크탑 (1440px) 캡처 ──────────────────────────────────────────
        # Desktop (1440px) capture
        desktop_ctx = await _make_context(
            browser, {"width": 1440, "height": 900}, session_cookie
        )
        page = await desktop_ctx.new_page()

        # 공개 페이지
        for name, path in PAGES_PUBLIC:
            await page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
            await _capture_all_themes(page, name)

        # 인증 페이지
        for name, path in PAGES_AUTH:
            resp = await page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
            if resp and resp.url.endswith("/") and name != "overview":
                print(f"  ⚠️  {name}: 인증 실패 — session-cookie 를 확인하세요")
                continue
            await _capture_all_themes(page, name)

        # 데이터 의존 페이지
        for name, path_tmpl in PAGES_DATA:
            path = path_tmpl.format(repo_id=repo_id, analysis_id=analysis_id)
            resp = await page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
            if resp and resp.status == 404:
                print(f"  ⚠️  {name}: 404 — --repo-id / --analysis-id 를 확인하세요")
                continue
            await _capture_all_themes(page, name)

        # 어드민 페이지
        for name, path in PAGES_ADMIN:
            resp = await page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
            if resp and resp.status in (403, 404):
                print(f"  ⚠️  {name}: {resp.status} — 어드민 계정인지 확인하세요")
                continue
            await _capture_all_themes(page, name)

        await desktop_ctx.close()

        # ── 모바일 (390px) 캡처 — 주요 페이지만 ────────────────────────────
        # Mobile (390px) capture — key pages only
        mobile_ctx = await _make_context(
            browser, {"width": 390, "height": 844}, session_cookie
        )
        mobile_page = await mobile_ctx.new_page()

        all_pages = PAGES_PUBLIC + PAGES_AUTH + PAGES_DATA + PAGES_ADMIN
        for name, path_tmpl in all_pages:
            if name not in MOBILE_PAGES:
                continue
            path = path_tmpl.format(repo_id=repo_id, analysis_id=analysis_id)
            await mobile_page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
            await _capture_all_themes(mobile_page, name, suffix="-mobile")

        await mobile_ctx.close()
        await browser.close()

    total = sum(1 for _ in OUTPUT_DIR.rglob("*.png"))
    print(f"\n✅  캡처 완료 — 총 {total}장 → {OUTPUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SCAManager design screenshots")
    parser.add_argument("--session-cookie", default="", help="session cookie value")
    parser.add_argument("--repo-id", type=int, default=1, help="existing repo ID")
    parser.add_argument("--analysis-id", type=int, default=1, help="existing analysis ID")
    asyncio.run(main(parser.parse_args()))
```

- [ ] **Step 2: pylint 확인**

```bash
python -m pylint scripts/capture_design_screenshots.py
```

기댓값: `Your code has been rated at 10.00/10`
(실패 시 inline disable 처리 — `# pylint: disable=<code>`)

- [ ] **Step 3: 스크립트 실행 검증**

로컬 서버가 실행 중인 상태에서:

```bash
# 공개 페이지(landing)만 테스트 — 인증 불필요
python scripts/capture_design_screenshots.py
```

기댓값:
```
  📸  dark/landing.png
```

파일 존재 확인:
```bash
dir docs\design\brief\screenshots\dark\landing.png
```

전체 캡처 (서버 실행 + 브라우저 로그인 후 세션 쿠키 복사):
```bash
python scripts/capture_design_screenshots.py \
  --session-cookie "<DevTools에서 복사한 session 값>" \
  --repo-id <실제 repo ID> \
  --analysis-id <실제 analysis ID>
```

기댓값: `✅  캡처 완료 — 총 XX장 → docs\design\brief\screenshots`

- [ ] **Step 4: 커밋**

```bash
git add scripts/capture_design_screenshots.py
git commit -m "feat: Playwright 12페이지 × 4테마 스크린샷 캡처 스크립트 추가"
```

---

## Task 4: 서비스 개요 문서 (00-service-overview.md)

**Files:**
- Create: `docs/design/brief/00-service-overview.md`

- [ ] **Step 1: 문서 작성**

`docs/design/brief/00-service-overview.md` 생성:

```markdown
# SCAManager — 서비스 개요 (Claude Design 브리프용)

## 한 줄 정의

GitHub Push/PR 이벤트 시 정적 분석 + AI 코드리뷰를 자동 수행하고, 점수 기반 PR 게이트(Approve·Reject·Auto-merge)와 멀티채널 알림을 제공하는 개발자 도구 SaaS.

## 핵심 사용자

| 페르소나 | 설명 | 이 서비스를 쓰는 이유 |
|---------|------|-------------------|
| **개발자 (주 사용자)** | 하루 수십 번 PR을 올리는 백엔드/풀스택 개발자 | 내 코드가 몇 점인지, 어떤 문제가 있는지 빠르게 파악 |
| **팀 리드** | 코드 품질 기준을 설정하고 팀 통계를 모니터링 | 팀 전체 점수 추세, 자주 발생하는 문제 패턴 파악 |
| **DevOps** | PR 게이트 임계값·자동 머지 정책을 관리 | 자동화 파이프라인 신뢰성 확보 |

## 핵심 기능 (페이지별)

| 페이지 | 핵심 기능 |
|--------|---------|
| **Dashboard** | 전체 KPI (평균 점수·분석 건수·보안 이슈·Auto-merge 성공률) + 점수 추세 차트 |
| **Analysis Detail** | 개별 PR 분석 결과 — AI 리뷰 + 정적분석 이슈 목록 + 점수 breakdown + GitHub Issue 등록 |
| **Repo Detail** | 리포지토리별 점수 히스토리 차트 + 분석 목록 필터링 |
| **Repo Insights** | 리포지토리 KPI 심층 분석 (이슈 빈도·스파크라인·등급 분포) |
| **Settings** | PR 게이트 임계값 / 알림 채널 / Auto-merge 정책 설정 |
| **Overview** | 등록된 리포지토리 목록 + 각 리포 최신 점수·등급 |
| **Landing** | 미인증 사용자 진입점 — GitHub OAuth 로그인 유도 |

## 점수 시스템

- 0~100점, A(90+) / B(80+) / C(70+) / D(60+) / F(~60) 5등급
- **등급 색상은 즉시 인지 가능해야 함** — 대시보드와 리스트에서 색상만으로 품질 수준 파악

## 데이터 밀도 특성

- 분석 결과 페이지는 이슈 목록 (10~50건)이 한 화면에 공존
- Dashboard KPI는 5개 지표가 동시 표시
- 점수 히스토리 차트는 30건 이상의 데이터 포인트를 처리

## 기술 스택 (Claude Design이 알아야 할 것)

- **프레임워크**: FastAPI + Jinja2 (서버사이드 렌더링)
- **인터랙션**: HTMX hx-boost (SPA-like 네비게이션), vanilla JS
- **차트**: Chart.js 4.4.0 (로컬 vendoring)
- **폰트**: Pretendard Variable (한국어), Inter (영문 fallback), JetBrains Mono (코드)
- **현재 테마**: 4개 — dark (Polar Aurora) / light (Vercel-inspired) / pastel (Dreamy) / catppuccin (Dev)
```

- [ ] **Step 2: 커밋**

```bash
git add docs/design/brief/00-service-overview.md
git commit -m "docs: Claude Design 브리프 — 서비스 개요 작성"
```

---

## Task 5: 컴포넌트 인벤토리 (02-component-inventory.md)

**Files:**
- Create: `docs/design/brief/02-component-inventory.md`

- [ ] **Step 1: 문서 작성**

`docs/design/brief/02-component-inventory.md` 생성:

```markdown
# SCAManager — UI 컴포넌트 인벤토리 (Claude Design 브리프용)

Claude Design의 Component Library 구성 시 아래 컴포넌트를 모두 포함해야 한다.

## 1순위: 기반 토큰

| 토큰 그룹 | 항목 수 | 비고 |
|---------|--------|------|
| Color (per theme) | ~25개 | bg-base, bg-card, bg-elevated, bg-nav, text-1/2/3, accent, border-subtle/strong, success/warning/danger, grade-a~f |
| Typography scale | 12개 | fs-xs(12) ~ fs-3xl(24) + display-sm(32)/md(44)/lg(60) |
| Spacing scale | 8개 | space-1(4px) ~ space-8(48px) |
| Radius scale | 5개 | xs(4) / sm(6) / md(10) / lg(14) / pill(999) |
| Elevation | 5단계 | elev-0 ~ elev-4 + elev-inset |
| Motion | 6개 | dur-fast(120ms)/base(220ms)/slow(360ms) + ease-out-expo/ease-out/ease-spring |

## 2순위: 원자 컴포넌트

| 컴포넌트 | 변형 | 사용 페이지 |
|---------|------|-----------|
| **Button** | primary / secondary / ghost / danger · size: sm/md/lg | 전체 |
| **Badge / Grade Pill** | A/B/C/D/F 등급 색상 + 점수 숫자 | overview, analysis_detail, repo_detail |
| **Score Bar** | 0~100 progress bar (등급 색 연동) | analysis_detail, repo_detail |
| **Toggle Switch** | on/off 슬라이더 | settings |
| **Input** | text / password / masked (••••) · focus 상태 | settings, add_repo |
| **Icon** | GitHub·Telegram·Discord·Slack·Email + 시스템 아이콘 | settings, nav |
| **Spinner / Loader** | 인라인 로딩 표시 | 전체 |

## 3순위: 분자 컴포넌트

| 컴포넌트 | 설명 | 사용 페이지 |
|---------|------|-----------|
| **KPI Card** | 지표명 + 큰 숫자 + delta(↑↓%) + 서브텍스트 | dashboard |
| **Repo Card** | 리포명 + 최신 등급 배지 + 점수 + 분석 날짜 | overview |
| **Issue Row** | 심각도 아이콘 + 메시지 + 파일:라인 + 카테고리 배지 | analysis_detail |
| **Stat Tile** | 라벨 + 값 + 아이콘 (소형 KPI) | repo_insights |
| **Sparkline Tile** | 미니 라인 차트 + 추세 수치 | repo_insights |
| **Alert Banner** | info / warning / danger 인라인 배너 | 전체 |
| **Empty State** | 아이콘 + 메시지 + CTA 버튼 | overview, dashboard |

## 4순위: 유기체 컴포넌트

| 컴포넌트 | 설명 | 사용 페이지 |
|---------|------|-----------|
| **Nav** | 로고 + 페이지 링크 + 테마 토글 + 사용자 메뉴 / 모바일 햄버거 | base.html (전체) |
| **Data Table** | 헤더 + 정렬 + 행 hover + 페이지네이션 | repo_detail, overview |
| **Chart Frame** | Chart.js 래퍼 — 라인/바/도넛 + 테마 색 동기화 | dashboard, repo_detail, analysis_detail |
| **Modal** | 오버레이 + 헤더 + 내용 + 액션 버튼 | analysis_detail (Issue 등록), repo_detail (삭제 확인) |
| **Settings Card** | 제목 + 설명 + 폼 그룹 + 저장 버튼 | settings |
| **Toast Notification** | 성공/에러 팝업 (우하단, 3초 자동 사라짐) | settings, add_repo |
| **Page Progress Bar** | 페이지 상단 로딩 인디케이터 (hx-boost 연동) | base.html (전체) |

## 특수 케이스

| 항목 | 설명 |
|------|------|
| **Landing Mesh BG** | CSS 애니메이션 그라디언트 배경 — landing.html 전용, always-dark |
| **Grade Color System** | A=green / B=blue / C=yellow / D=orange / F=red — 4테마 모두에서 WCAG AA 기준 충족 의무 |
| **JetBrains Mono 사용처** | 파일 경로, 커밋 SHA, 점수 숫자 (큰 KPI 숫자) — 코드·데이터 영역에 한정 |
```

- [ ] **Step 2: 커밋**

```bash
git add docs/design/brief/02-component-inventory.md
git commit -m "docs: Claude Design 브리프 — 컴포넌트 인벤토리 작성"
```

---

## Task 6: 디자인 방향 브리프 (03-design-direction.md)

**Files:**
- Create: `docs/design/brief/03-design-direction.md`

- [ ] **Step 1: 문서 작성**

`docs/design/brief/03-design-direction.md` 생성:

```markdown
# SCAManager — 디자인 방향 브리프 (Claude Design 브리프용)

## 방향: Developer Tool × Enterprise Analytics 하이브리드

SCAManager는 두 가지 정체성을 동시에 가진다:
1. **개발자가 매일 쓰는 도구** — Linear·Raycast 수준의 예리함과 쾌적함
2. **데이터를 읽는 분석 화면** — Datadog·Grafana 수준의 정보 시각화 깊이

이 두 정체성을 하나의 독창적 시각 언어로 통합하는 것이 목표다.

---

## Developer Tool에서 가져올 요소

### 정보 밀도
- Linear처럼 작은 텍스트와 촘촘한 간격으로 많은 정보를 한 화면에 담는다
- 여백은 "숨을 쉬기 위한 것"이지 "채우지 못해서"가 아니다
- 기본 폰트 크기 14px, 라인 높이 1.6 유지

### 타이포그래피
- 헤딩: Pretendard Variable (한글 최우선)
- 숫자·코드: JetBrains Mono — KPI 큰 숫자, 파일 경로, SHA에만 사용
- 날카로운 letter-spacing (-0.01em ~ -0.02em) 으로 현대적 밀도감

### 마이크로 인터랙션
- hover: 0.12s 이하 elevation 상승 (카드가 살짝 뜨는 효과)
- 버튼 클릭: scale(0.97) → scale(1.0) 피드백
- 페이지 전환: hx-boost 프로그레스 바 상단 thin line

### Accent 시스템
- 단일 색이 아닌 2~3색 그라디언트 체계
- 예: `linear-gradient(135deg, #6366f1, #a855f7)` 방향 유지, 색상은 재정의
- glow 효과는 버튼·배지에만 — 남용 금지

---

## Enterprise Analytics에서 가져올 요소

### 데이터 시각화 계층
```
Level 1 (최상위): KPI 카드 — 가장 크고 즉시 인지
Level 2 (중간): 추세 차트 — 시간축 변화 패턴
Level 3 (상세): 이슈 목록 / 테이블 — 드릴다운
```
이 계층이 Dashboard·Analysis Detail·Repo Detail의 레이아웃 원칙이 된다.

### 등급/점수 색상 시스템
- **A (90+)**: 선명한 초록 — 즉각적인 "안전" 신호
- **B (80+)**: 차분한 파랑 — "양호" 신호
- **C (70+)**: 노랑/황금 — "주의" 신호
- **D (60+)**: 주황 — "경고" 신호
- **F (~60)**: 빨강 — "위험" 신호
- **4테마 모두에서 WCAG AA 기준 (4.5:1 대비) 충족 필수**

### 차트 캔버스
- 차트 영역은 "데이터를 보는 창문" — 배경 노이즈 최소화
- 그리드 라인: 매우 희미하게 (opacity 0.06~0.1)
- 데이터 포인트 색상: accent 그라디언트에서 파생

---

## 금지 패턴

| 패턴 | 이유 |
|------|------|
| 과도한 gradient 배경 | 정보 가독성 저해 |
| 3개 이상 accent 색 동시 사용 | 시각적 혼잡 |
| 큰 여백으로 빈 공간 채우기 | 개발자 도구 밀도감 파괴 |
| 장식용 일러스트레이션 | 분석 도구 신뢰감 저해 |
| 둥근 모서리 과용 (>14px) | 전문성 희석 |

---

## 참고 서비스 (영감, 모방 X)

| 서비스 | 참고할 요소 |
|--------|-----------|
| Linear | 정보 밀도, 키보드 중심 UX, 다크 테마 완성도 |
| Raycast | 타이포그래피 예리함, micro-animation |
| Datadog | KPI 대시보드 레이아웃, 상태 색상 시스템 |
| Grafana Cloud | 차트 캔버스 처리, 다크 배경 데이터 가시성 |
| Vercel Dashboard | 클린한 Light 테마, 카드 elevation |
```

- [ ] **Step 2: 커밋**

```bash
git add docs/design/brief/03-design-direction.md
git commit -m "docs: Claude Design 브리프 — 디자인 방향 A+B 하이브리드 명세 작성"
```

---

## Task 7: 4테마 역할 정의서 (04-theme-roles.md)

**Files:**
- Create: `docs/design/brief/04-theme-roles.md`

- [ ] **Step 1: 문서 작성**

`docs/design/brief/04-theme-roles.md` 생성:

```markdown
# SCAManager — 4테마 역할 정의서 (Claude Design 브리프용)

## 테마 설계 원칙

- **dark** 테마를 기준(ground truth)으로 먼저 완성한다
- 나머지 3테마는 dark에서 정의한 구조와 컴포넌트를 유지하되, 색상 팔레트만 교체한다
- 4테마 모두에서 Grade A~F 색상이 명확히 구분되어야 한다 (색맹 기준 포함)
- 어떤 테마에서도 "2등급 테마"가 없어야 한다 — 완성도 동일

---

## dark — Premium Dark (기준 테마)

**성격**: 고급스럽고 예리한 개발자 도구. 야간 작업 최적화.

**색상 방향**:
- 배경: 거의 순수 검정에 가까운 깊은 어두운 색 (#07070f 계열 유지 또는 개선)
- 카드: 배경 대비 미세하게 밝은 반투명 레이어
- Accent: 인디고~보라 그라디언트 (현재 `#6366f1~#a855f7`) — 재해석 가능
- 텍스트: 따뜻한 흰색 (순수 #fff 보다 약간 따뜻하게)
- 등급 색상: 채도 높고 선명하게 — 어두운 배경에서 빛나는 효과

**무드 키워드**: 우주적(cosmic) · 정밀한(precise) · 몰입적(immersive)

---

## light — Clean Professional

**성격**: 비즈니스 미팅·데모·외부 공유에 적합한 깔끔한 전문가용 테마.

**색상 방향**:
- 배경: 순수 흰색보다 약간 차가운 오프화이트 (#f6f6fd 계열)
- 카드: 흰색 + 미세한 border
- Accent: dark와 동일한 인디고 계열 — 밝은 배경에서도 충분한 대비
- 텍스트: 따뜻한 검정 (순수 #000 보다 약간 부드럽게)
- 등급 색상: 채도를 약간 낮춰 눈부심 방지, WCAG AA 충족

**무드 키워드**: 신뢰적(trustworthy) · 명료한(clear) · 전문적(professional)

---

## pastel — Soft Focus

**성격**: 장시간 모니터 사용 시 눈 피로를 최소화하는 부드러운 테마.

**색상 방향**:
- 배경: 크림·라벤더 계열 따뜻한 오프화이트
- 카드: 배경보다 약간 밝고 따뜻한 흰색
- Accent: 파스텔 톤으로 낮춘 인디고/보라 — 자극 최소화
- 텍스트: 충분한 대비를 유지하면서 부드러운 dark gray
- 등급 색상: 파스텔 톤이되 WCAG AA 기준은 반드시 충족

**무드 키워드**: 부드러운(gentle) · 집중적(focused) · 편안한(comfortable)

---

## catppuccin — Dev Aesthetic

**성격**: IDE 테마와 조화를 이루는 개발자 서브컬처 감성. Catppuccin Mocha 팔레트 영감.

**색상 방향**:
- 배경: 따뜻한 다크 (#1e1e2e 계열 Catppuccin Mocha Base)
- 카드: Catppuccin Surface0 (#313244) 계열
- Accent: Catppuccin Mauve (#cba6f7) 또는 Lavender (#b4befe)
- 텍스트: Catppuccin Text (#cdd6f4)
- 등급 색상: Catppuccin 팔레트의 Green·Blue·Yellow·Peach·Red 대응

**참고 팔레트 (Catppuccin Mocha)**:
- Base: #1e1e2e / Mantle: #181825 / Crust: #11111b
- Surface0: #313244 / Surface1: #45475a
- Text: #cdd6f4 / Subtext0: #a6adc8
- Mauve: #cba6f7 / Lavender: #b4befe / Green: #a6e3a1
- Blue: #89b4fa / Yellow: #f9e2af / Peach: #fab387 / Red: #f38ba8

**무드 키워드**: 미적(aesthetic) · 취향적(opinionated) · 친숙한(familiar to devs)
```

- [ ] **Step 2: 커밋**

```bash
git add docs/design/brief/04-theme-roles.md
git commit -m "docs: Claude Design 브리프 — 4테마 역할 정의서 작성"
```

---

## Task 8: 페이지 인벤토리 (05-page-inventory.md)

**Files:**
- Create: `docs/design/brief/05-page-inventory.md`

- [ ] **Step 1: 문서 작성**

`docs/design/brief/05-page-inventory.md` 생성:

```markdown
# SCAManager — 페이지 인벤토리 (Claude Design 브리프용)

Claude Design에서 12페이지 프로토타입을 생성할 때 아래 순서와 구조를 따른다.

## 프로토타입 생성 순서

```
1순위: landing     — 서비스 첫인상, 브랜드 집약
2순위: dashboard   — 가장 복잡한 KPI+차트 레이아웃
3순위: analysis_detail — 핵심 데이터 표시 페이지
4순위: overview    — 리포 목록 그리드
5순위: repo_detail — 차트+테이블 복합
6순위: settings    — 폼 카드 레이아웃
7순위: repo_insights — 스파크라인+KPI 집약
8순위: add_repo    — 단순 폼
9~12순위: admin 3종 — 어드민 전용
```

---

## 페이지별 상세

### 1. landing (`/`)
- **목적**: 미인증 사용자 → GitHub OAuth 로그인 유도
- **특수사항**: `base.html` 미상속 standalone — always-dark 고정
- **핵심 요소**: 애니메이션 메시 그라디언트 배경, 히어로 CTA 버튼 1개, 서비스 기능 소개
- **주의**: 이 페이지만 단일 다크 테마 — 4테마 적용 불필요

### 2. dashboard (`/dashboard`)
- **목적**: 전체 리포지토리 종합 현황 한눈에 파악
- **핵심 요소**:
  - KPI 카드 5개 (평균점수·분석건수·보안HIGH·활성리포·AutoMerge성공률)
  - 점수 추세 라인 차트 (전체 리포 시계열)
  - 자주 발생 이슈 테이블
  - Auto-merge 실패 사유 목록
- **레이아웃**: 데스크탑 5컬럼 KPI 그리드, 태블릿 3컬럼, 모바일 1컬럼

### 3. analysis_detail (`/repos/{id}/analysis/{id}`)
- **목적**: 개별 PR 분석 결과 상세 보기
- **핵심 요소**:
  - 점수 + 등급 배지 (큰 폰트, 페이지 상단)
  - 점수 breakdown 바 차트 (카테고리별)
  - AI 리뷰 텍스트 (마크다운)
  - 정적분석 이슈 목록 (심각도별 정렬)
  - GitHub Issue 등록 패널 (AI/정적 탭)
  - 이전/다음 분석 네비게이션

### 4. overview (`/overview`)
- **목적**: 사용자가 등록한 리포지토리 목록
- **핵심 요소**: 리포 카드 그리드 (이름·등급·최신점수·분석날짜), 리포 추가 CTA

### 5. repo_detail (`/repos/{id}`)
- **목적**: 특정 리포지토리의 분석 히스토리
- **핵심 요소**:
  - 점수 추세 라인 차트 (해당 리포 시계열)
  - 분석 목록 테이블 (필터·정렬 포함)
  - 일괄 Issue 등록 패널

### 6. settings (`/settings`)
- **목적**: PR 게이트·알림채널·Auto-merge 정책 설정
- **핵심 요소**: 의도 기반 6카드 (빠른설정 / PR게이트 / 이벤트피드백 / 알림채널 / 시스템 / 위험구역)
- **레이아웃**: 카드 스택 단일 컬럼, 저장 바 하단 sticky

### 7. repo_insights (`/repos/{id}/insights`)
- **목적**: 리포지토리 심층 KPI 분석
- **핵심 요소**: Stat tile + Sparkline tile 그리드, 이슈 빈도 분포

### 8. add_repo (`/repos/add`)
- **목적**: 새 리포지토리 등록
- **핵심 요소**: 리포 선택 드롭다운, Webhook URL 표시, 등록 버튼

### 9~11. admin (3종)
- **목적**: 어드민 전용 운영 화면
- **페이지**: `/admin/operations` · `/admin/rls-audit` · `/admin/tenants`
- **특이사항**: 일반 사용자 접근 불가, 테이블 중심 레이아웃
```

- [ ] **Step 2: 커밋**

```bash
git add docs/design/brief/05-page-inventory.md
git commit -m "docs: Claude Design 브리프 — 12페이지 인벤토리 작성"
```

---

## Task 9: PR 생성

- [ ] **Step 1: 전체 파일 상태 확인**

```bash
git status
git log --oneline -8
```

기댓값: 현재 브랜치에 Task 1~8 커밋 8개, 미커밋 변경 없음.

- [ ] **Step 2: 스크린샷 실행 (Phase 1 완성 전 필수)**

`make run` 으로 로컬 서버 실행 후:

```bash
python scripts/extract_design_tokens.py
python scripts/capture_design_screenshots.py \
  --session-cookie "<session 쿠키 값>" \
  --repo-id <실제 ID> \
  --analysis-id <실제 ID>
```

스크린샷 PNG는 .gitignore 에 의해 커밋에서 제외됨.
`01-current-tokens.json` 은 커밋에 포함.

- [ ] **Step 3: tests/unit/scripts/ 디렉토리 확인 및 전체 단위 테스트**

```bash
python -m pytest tests/unit/scripts/test_extract_design_tokens.py -v
```

기댓값: `11 passed`

- [ ] **Step 4: pylint 전체 확인**

```bash
python -m pylint scripts/extract_design_tokens.py scripts/capture_design_screenshots.py
```

기댓값: `Your code has been rated at 10.00/10`

- [ ] **Step 5: PR 생성**

```bash
git push -u origin docs/claude-design-ui-redesign-spec
gh pr create --title "docs: Claude Design UI 재설계 Phase 1 — Preparation Package" --body "$(cat <<'EOF'
## Summary

- Claude Design이 SCAManager를 이해하고 Design System을 구축할 수 있도록 Design Brief Package 완성
- 토큰 추출 스크립트 (`extract_design_tokens.py`) — tokens.css + themes.css → JSON
- Playwright 스크린샷 스크립트 (`capture_design_screenshots.py`) — 12페이지 × 4테마 자동 캡처
- 브리프 문서 6종: 서비스 개요 / 토큰 JSON / 컴포넌트 인벤토리 / 디자인 방향 / 4테마 역할 / 페이지 인벤토리

## Phase 2 안내 (사용자 수행)

본 PR 머지 후 사용자가 Claude Design에서 수행할 작업:
1. `docs/design/brief/` 내용을 Claude Design에 입력
2. Design System 프로젝트 생성 (Color → Typography → Components → Pages 순)
3. 12페이지 프로토타입 생성
4. 결과물을 `docs/design/output/`에 저장 → Phase 3 계획 작성 시작

## 🔍 사용자 검증 필요

- [ ] `python scripts/extract_design_tokens.py` 실행 → `01-current-tokens.json` 생성 확인
- [ ] `python scripts/capture_design_screenshots.py --session-cookie "..." --repo-id N --analysis-id N` 실행 → 스크린샷 캡처 확인
- [ ] `docs/design/brief/` 문서 6종 내용 검토 — Claude Design 입력 전 사실 오류 없는지 확인

## Test plan

- [x] `tests/unit/scripts/test_extract_design_tokens.py` 11개 통과
- [x] pylint 10.00/10
- [x] 전체 기존 테스트 영향 없음 (신규 스크립트 파일만 추가)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Phase 3 계획 안내

Phase 3 구현 계획은 아래 조건 충족 후 별도 작성한다:

```
조건:
1. Claude Design에서 Design System (4테마 토큰 체계) 완성
2. Claude Design에서 12페이지 프로토타입 완성
3. 결과물이 docs/design/output/ 에 저장됨

계획 파일: docs/design/YYYY-MM-DD-phase3-implementation-plan.md
포함 내용: PR-T1(tokens) → PR-T2(base.html) → PR-P1~P6(12페이지) 상세 구현
```
