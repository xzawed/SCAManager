"""점수 없는 분석의 등급 표시 · 높이가 자유로운 차트의 틀 (2026-10-16 화면별 렌더링 검수).

## 무엇이 문제였나

1. AI 리뷰가 진짜로 실패하면 파이프라인이 점수·등급을 둘 다 NULL 로 저장한다
   (`src/worker/pipeline.py::_null_persist`). 그런데 분석 상세 머리는 `analysis.grade or 'F'`
   로 빨간 **F 배지**를 그리고, 등급 문구는 `str.format(grade=None)` 이라 **«등급 None»** 이 찍혔다.
   리포 상세 머리도 최신 분석이 그 상태면 F 배지였다. 개요·대시보드는 같은 상태에서 배지를 숨긴다.
2. 대시보드 repos 모드의 `#repoTrendChart` 만 고정 높이 틀 없이 `maintainAspectRatio: false` 였다
   — Chart.js 가 캔버스 높이를 «캔버스가 정하는» 부모 높이에서 가져와 **끝없이 자랐다**
   (실측 12초에 데스크톱 4,738px · 모바일 15,482px).

## 행동 판정은 e2e

실제 화면의 캔버스 높이 추이·표 행은 `e2e/test_page_render_defects.py` 가 잰다. 여기는 템플릿
수준에서 되돌림을 빠르게 잡는다.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.i18n.filters import register_i18n_filters

_TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "templates"


def _render(template_name: str, **context) -> str:
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES)),
                      autoescape=select_autoescape(["html", "xml"]))
    register_i18n_filters(env)
    return env.get_template(template_name).render(**context)


class _FakeUser:
    github_login = "alice"
    display_name = "Alice"


class _Region(HTMLParser):
    """class 에 `root` 가 든 요소 «안» 의 등급 배지(class·글자) · 점수 바 class · 글자 전부.

    배지 = class 에 `badge` 가 든 요소다(분석 머리는 `grade--hero` — 같은 머리의 PR 링크도
    `grade grade--b` 칩이라 `grade` 만으로 고르면 그 칩을 등급으로 오독한다).
    """

    def __init__(self, root: str, badge: str = "grade") -> None:
        super().__init__(convert_charrefs=True)
        self.root, self.badge_cls, self.depth = root, badge, 0
        self._badge_tag: str | None = None
        self.badges: list[tuple[list[str], str]] = []
        self.bars: list[list[str]] = []
        self.text: list[str] = []
        self._badge: list[str] | None = None
        self._badge_text = ""

    def handle_starttag(self, tag, attrs):
        cls = (dict(attrs).get("class") or "").split()
        if self.depth == 0 and self.root in cls:
            self.depth = 1
            return
        if self.depth == 0:
            return
        if tag not in ("br", "img", "input", "meta", "link"):
            self.depth += 1
        if self.badge_cls in cls and self._badge is None:
            self._badge, self._badge_text, self._badge_tag = cls, "", tag
        if "score-bar" in cls:
            self.bars.append(cls)

    def handle_endtag(self, tag):
        if self.depth == 0:
            return
        if self._badge is not None and tag == self._badge_tag:
            self.badges.append((self._badge, self._badge_text.strip()))
            self._badge = None
        self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.text.append(data)
            if self._badge is not None:
                self._badge_text += data


def _region(html: str, root: str, badge: str = "grade") -> _Region:
    r = _Region(root, badge)
    r.feed(html)
    assert r.text, f"`.{root}` 를 렌더 결과에서 찾지 못했다 — 스캐너가 늙었다"
    return r


def _analysis(score, grade) -> dict:
    return {
        "id": 42, "commit_sha": "abc1234", "commit_message": "fix: bug", "pr_number": 7,
        "score": score, "grade": grade,
        "result": {"ai_review_status": "parse_error", "breakdown": {}, "issues": []},
        "source": "pr", "created_at": "2026-05-01T10:00:00",
    }


def _analysis_ctx(score, grade, locale) -> dict:
    return {"current_user": _FakeUser(), "repo_name": "owner/repo", "analysis": _analysis(score, grade),
            "trend_data": [], "prev_id": None, "next_id": None,
            "user_feedback": {"thumbs": None, "comment": None, "updated_at": None}, "locale": locale}


def test_unscored_analysis_hero_shows_no_grade_and_no_none():
    """🔴 점수·등급 NULL 분석 — 머리에 F 배지도 «None» 도 없다. 배지는 중립 «—», 점수 바는 색 없음.

    An unscored analysis (score and grade NULL) shows a neutral «—» badge, no «None», no F.
    """
    for locale in ("ko", "en", "ja"):
        hero = _region(_render("analysis_detail.html", **_analysis_ctx(None, None, locale)),
                       "analysis-hero", badge="grade--hero")
        text = " ".join("".join(hero.text).split())
        assert "None" not in text, f"[{locale}] 머리 글자에 파이썬 None 이 찍혔다: {text[:160]!r}"
        assert hero.badges, f"[{locale}] 머리 등급 배지를 못 찾았다(스캐너가 늙었다)"
        for cls, label in hero.badges:
            assert not any(c.startswith("grade--") and c != "grade--hero" for c in cls), (
                f"[{locale}] 등급 없는 분석에 등급 색 배지 {cls} ({label!r})")
            assert label == "—", f"[{locale}] 등급 없는 배지 글자가 «—» 가 아니다: {label!r}"
        assert all(not any(c.startswith("score-bar--") for c in bar) for bar in hero.bars), (
            f"[{locale}] 점수 없는 막대에 등급 색 {hero.bars}")


def test_scored_analysis_hero_keeps_its_grade():
    """대조군 — 등급이 있으면 그 색 배지·문구가 그대로다(위 시험이 배지를 «못 찾아» 초록이 되지 않게)."""
    hero = _region(_render("analysis_detail.html", **_analysis_ctx(82, "B", "ko")), "analysis-hero",
                   badge="grade--hero")
    assert any("grade--b" in cls and label == "B" for cls, label in hero.badges), hero.badges
    assert "등급 B" in " ".join("".join(hero.text).split())
    assert any("score-bar--b" in bar for bar in hero.bars), hero.bars


def _repo_ctx(analyses: list[dict]) -> dict:
    return {"current_user": _FakeUser(), "repo_name": "owner/repo", "analyses": analyses,
            "chart_labels": [], "chart_scores": [], "hook_installed": False,
            "monthly_cost_usd": 0.0, "monthly_token_count": 0, "monthly_cost_month": "2026-05",
            "locale": "ko"}


def _row(score, grade, created_at) -> dict:
    return {"id": 1, "score": score, "grade": grade, "commit_sha": "abc1234", "pr_number": None,
            "commit_message": "msg", "source": "push", "created_at": created_at}


def test_repo_header_has_no_f_badge_for_an_unscored_latest_analysis():
    """🔴 리포 상세 머리 — 최신 분석이 점수·등급 NULL 이면 F 배지를 그리지 않는다(개요 카드와 같은 규칙)."""
    html = _render("repo_detail.html", **_repo_ctx([
        _row(None, None, "2026-05-02T10:00:00"), _row(80, "B", "2026-05-01T10:00:00")]))
    meta = _region(html, "repo-hero__meta")
    assert not any("grade--f" in cls for cls, _ in meta.badges), f"점수 없는 최신 분석에 F 배지: {meta.badges}"
    graded = _region(_render("repo_detail.html", **_repo_ctx([_row(80, "B", "2026-05-02T10:00:00")])),
                     "repo-hero__meta")
    assert any("grade--b" in cls for cls, _ in graded.badges), (
        f"대조군 — 등급 있는 최신 분석의 배지를 못 찾았다(스캐너가 늙었다): {graded.badges}")


# ── 높이가 자유로운 차트의 틀 ─────────────────────────────────────────────────────

# 높이를 CSS 로 고정하는 감싸개 클래스 — 사유와 함께.
_SIZED_WRAPPERS = {
    "chart-wrap-inner": "repo_detail.html · analysis_detail.html 의 `.chart-wrap-inner { height: … }`",
}


class _CanvasParents(HTMLParser):
    """각 `<canvas>` 의 바로 위 부모 (태그, attrs)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, dict]] = []
        self.found: list[tuple[str, tuple[str, dict]]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "canvas":
            self.found.append((a.get("id", "?"), self.stack[-1] if self.stack else ("(root)", {})))
            return
        if tag not in ("br", "img", "input", "meta", "link", "hr", "source"):
            self.stack.append((tag, a))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def unsized_canvases(src: str) -> list[str]:
    """`maintainAspectRatio: false` 를 쓰는 템플릿에서, 높이를 고정한 틀 안에 없는 캔버스 id."""
    if not re.search(r"maintainAspectRatio\s*:\s*false", src):
        return []
    p = _CanvasParents()
    p.feed(src)
    bad = []
    for cid, (_tag, attrs) in p.found:
        style = attrs.get("style") or ""
        classes = set((attrs.get("class") or "").split())
        if re.search(r"(?<![\w-])height\s*:", style) or classes & set(_SIZED_WRAPPERS):
            continue
        bad.append(cid)
    return bad


def test_free_height_charts_sit_in_a_fixed_height_box():
    """🔴 `maintainAspectRatio: false` 차트의 캔버스는 높이를 고정한 부모 안에 있다 — 없으면 끝없이 자란다.

    Chart.js 문서의 전제다: 그 옵션은 «부모» 높이를 쓰므로, 부모 높이가 캔버스에 달려 있으면
    리사이즈 관찰이 서로를 키운다(실측: repos 리포트 12초에 4,738px).
    """
    bad = {}
    for path in sorted(_TEMPLATES.glob("*.html")):
        ids = unsized_canvases(path.read_text(encoding="utf-8"))
        if ids:
            bad[path.name] = ids
    assert not bad, f"높이 틀 없는 자유 높이 차트: {bad} — `<div style=\"position:relative;height:…\">` 로 감싼다"


def test_the_canvas_scan_tells_boxes_apart():
    """🔴 스캐너 자기검증 — 틀 없는 캔버스는 잡고, 높이 style·등재된 감싸개는 놓아준다."""
    src = """<script>new Chart(c, {options: {maintainAspectRatio: false}})</script>
      <section class="x"><h3>t</h3><canvas id="bare" height="80"></canvas></section>
      <div style="position: relative; height: 220px;"><canvas id="styled"></canvas></div>
      <div class="chart-wrap-inner"><canvas id="wrapped"></canvas></div>
      <div style="max-height: 200px"><canvas id="maxonly"></canvas></div>"""
    assert unsized_canvases(src) == ["bare", "maxonly"]
    assert unsized_canvases(src.replace("maintainAspectRatio: false", "responsive: true")) == []
