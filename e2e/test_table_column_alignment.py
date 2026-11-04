"""표 머리글과 본문 열이 같은 x 에서 시작한다 — 표가 있는 모든 화면 · 넓은 화면과 폰 폭 (#1639 · #1711 후속).

#1711 에서 행 가상요소(`tr::before`)를 Chromium 이 열 하나로 세어 본문 전체가 머리글보다 한 칸 오른쪽에
그려졌다. 400조합 스윕은 색·대비·포커스·타깃 크기를 쟀고 th↔td 정렬은 재지 않아, 4테마 × 2폭 전부에서
어긋난 채 초록이었다. 정적 가드(`tests/unit/ui/test_table_row_pseudo_element.py`)는 그 원인 하나만 막는다 —
이 시험은 원인과 무관하게 «그려진» 위치를 잰다(colspan·숨김 열 불일치도 같은 증상이다).

🔴 화면 목록은 손으로 적되 닫는다 — 표가 있는 템플릿 집합(소스 파생)과 이 목록 + 사유 있는 면제가 같아야 한다.
🔴 폰 폭에서 머리글이 안 그려지는 표(카드형으로 바뀌는 표)는 그 폭에서만 건너뛴다. 넓은 화면에서는 모든 표를
   재야 하고, 잰 행이 0 이면 «재지 못한 것» 이라 red 다.

Header and body columns start at the same x on every screen that has a table.
"""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

import pytest

from e2e.conftest import admin_session_cookie
from e2e.test_theme_mobile_guards import _reveal_all

_TEMPLATES = Path(__file__).resolve().parents[1] / "src" / "templates"

# 설정 프리셋 표는 아코디언이라 한 번에 하나만 열린다 — 상태 하나 = 프리셋 하나. 본문 행은 열 때 JS 가 그린다.
_OPEN_PRESET = """async (name) => {
    document.getElementById('preset-' + name).open = true;
    const t0 = performance.now();
    while (!document.querySelector('#preset-diff-' + name + ' tr') && performance.now() - t0 < 3000) {
        await new Promise(r => requestAnimationFrame(() => r()));
    }
}"""

# {템플릿: (주소, 잴 상태들)} — 상태 None = 연 그대로, 문자열 = 그 설정 프리셋을 열고 그 안의 표만.
_TABLE_SURFACES = {
    "admin_rls_audit.html": ("/admin/rls-audit", [None]),
    "admin_tenants.html": ("/admin/tenants", [None]),
    "overview.html": ("/", [None]),
    "repo_detail.html": ("/repos/owner%2Ftestrepo", [None]),
    "repo_insights.html": ("/repos/owner%2Ftestrepo/insights", [None]),
    "settings.html": ("/repos/owner%2Ftestrepo/settings", ["minimal", "standard", "strict"]),
}
# 눈에 보이는 머리글이 없는 표 — 맞출 열 머리가 없다. {템플릿: 그 사유를 이루는 원문}.
# 원문이 사라지면(머리글이 보이게 되면) 닫힘 시험이 red — 그때 위 목록으로 옮긴다.
_HEADERLESS = {"analysis_detail.html": '<thead class="sr-only">'}

# 표마다: 마지막 머리글 행의 칸 시작 x(colspan 반영)와, 칸 수가 같은 본문 행의 칸 시작 x 를 맞댄다.
_TABLE_JS = r"""(rootSel) => {
  const root = document.querySelector(rootSel);
  const out = [];
  for (const [ti, t] of Array.from(root.querySelectorAll('table')).entries()) {
    const head = t.tHead ? Array.from(t.tHead.rows) : [];
    const hrow = head[head.length - 1];
    const cls = t.className || '(class 없음)';
    if (!hrow) { out.push({ti, cls, skip: 'thead 없음'}); continue; }
    const cols = [];
    let n = 0;
    for (const th of Array.from(hrow.cells)) {
      const r = th.getBoundingClientRect();
      cols.push({col: n, x: r.left, painted: r.width > 1 && r.height > 1});
      n += th.colSpan || 1;
    }
    if (!cols.every(c => c.painted)) { out.push({ti, cls, skip: '머리글이 안 그려졌다'}); continue; }
    const bad = [];
    let rows = 0;
    for (const body of Array.from(t.tBodies)) {
      for (const tr of Array.from(body.rows)) {
        const rr = tr.getBoundingClientRect();
        if (rr.width < 1 || rr.height < 1) continue;
        let c = 0;
        const starts = [];
        for (const td of Array.from(tr.cells)) {
          starts.push({col: c, x: td.getBoundingClientRect().left});
          c += td.colSpan || 1;
        }
        if (c !== n) continue;            // 빈 상태 줄(colspan 한 칸) 등 — 열 구조가 다른 행
        rows++;
        for (const s of starts) {
          const h = cols.find(k => k.col === s.col);
          if (h && Math.abs(h.x - s.x) > 1) bad.push({row: rows, col: s.col,
                                                       th: Math.round(h.x), td: Math.round(s.x)});
        }
      }
    }
    out.push({ti, cls, cols: n, rows, bad});
  }
  return out;
}"""


class _Tables(HTMLParser):
    """템플릿 원문에서 `<table>` 시작 태그를 센다 — HTML 주석·`<script>` 안의 글자는 태그가 아니다."""

    def __init__(self):
        super().__init__()
        self.count = 0

    def handle_starttag(self, tag, attrs):  # noqa: ARG002 — HTMLParser 서명
        if tag == "table":
            self.count += 1


def _templates_with_tables() -> set[str]:
    out = set()
    for path in sorted(_TEMPLATES.rglob("*.html")):
        parser = _Tables()
        parser.feed(path.read_text(encoding="utf-8"))
        if parser.count:
            out.add(path.relative_to(_TEMPLATES).as_posix())
    return out


def test_every_template_with_a_table_is_measured_or_says_why():
    """표가 있는 템플릿은 전부 재거나(`_TABLE_SURFACES`) 사유를 댄다(`_HEADERLESS`) — 새 표가 조용히 빠지지 않게."""
    found = _templates_with_tables()
    assert found, f"{_TEMPLATES} 에서 표를 하나도 못 찾았다 — 경로가 바뀌었거나 파서가 고장났다"
    listed = set(_TABLE_SURFACES) | set(_HEADERLESS)
    assert found == listed, (
        f"표가 있는 템플릿 ↔ 이 시험의 목록이 다르다 — 목록에 없음 {sorted(found - listed)} · "
        f"표가 없는데 목록에 있음 {sorted(listed - found)}")
    for name, marker in _HEADERLESS.items():
        assert marker in (_TEMPLATES / name).read_text(encoding="utf-8"), (
            f"{name}: 면제 사유(`{marker}`)가 원문에서 사라졌다 — 머리글이 보이면 `_TABLE_SURFACES` 로 옮긴다")


@pytest.mark.parametrize("template", sorted(_TABLE_SURFACES))
def test_table_header_and_body_columns_line_up(seeded_page, base_url, seeded_analysis,
                                               paginated_history, calibration_feedback, template):
    """머리글 칸과 본문 칸이 같은 x 에서 시작한다(허용 1px) — 넓은 화면(1440)과 폰 폭(375)."""
    path, states = _TABLE_SURFACES[template]
    page = seeded_page
    if path.startswith("/admin/"):
        page.context.add_cookies([admin_session_cookie()])
    bad, unmeasured, rows_wide = [], [], {}
    for width in (1440, 375):
        for state in states:
            page.set_viewport_size({"width": width, "height": 900})
            page.goto(f"{base_url}{path}")
            assert "localhost" in page.url, f"{page.url[:60]} 로 나갔다 — 남의 페이지를 잰다"
            page.add_style_tag(content="*,*::before,*::after{transition:none !important}")
            root = "body"
            if state:
                page.evaluate(_OPEN_PRESET, state)
                root = f"#preset-{state}"
            page.wait_for_timeout(200)
            _reveal_all(page)
            where = f"{width}px{' · ' + state if state else ''}"
            for t in page.evaluate(_TABLE_JS, root):
                if "skip" in t:
                    # 폰 폭의 카드형 표는 머리글을 숨긴다 — 넓은 화면에서만 «못 잼» 을 red 로 본다.
                    if width == 1440:
                        unmeasured.append(f"{where} 표{t['ti']} {t['cls']}: {t['skip']}")
                    continue
                if width == 1440:
                    rows_wide[state] = rows_wide.get(state, 0) + t["rows"]
                bad += [f"{where} 표{t['ti']} {t['cls']} 열{b['col']}: th x={b['th']} · td x={b['td']} "
                        f"(행 {b['row']})" for b in t["bad"]]
    assert not unmeasured, f"{template}: 넓은 화면에서 재지 못한 표 — " + " / ".join(unmeasured)
    empty = [s or "(기본)" for s in states if rows_wide.get(s, 0) == 0]
    assert not empty, (
        f"{template}: 넓은 화면에서 잰 본문 행이 0 인 상태 {empty} — 표가 비었거나 안 그려졌다"
        "(재지 못한 것이지 통과한 것이 아니다)")
    assert not bad, f"{template}: 머리글과 본문 열이 어긋났다 —\n  " + "\n  ".join(bad[:12])
