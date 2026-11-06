"""리포 상세의 분석 이력 표가 폰 폭에서 카드 안에 다 들어간다 (#1639).

480px 이하에서는 커밋 · 출처 열을 숨겨 네 열(날짜 · PR · 점수 · 등급)만 남는다. 그래도 셀 좌우 여백
16px 과 70px 점수 막대 때문에 표가 카드보다 넓었다. `.table-wrap` 이 가로 스크롤을 품고 있어 페이지는
넘치지 않으므로, 페이지 넘침 검사로는 보이지 않았다. 수정 전 375px 에서는 등급 열이 한국어 60px ·
영어 83px 가려졌고, 날짜가 하이픈에서 두 줄로 접혔다.

🔴 가장 긴 값으로 잰다 — 점수 100 · 다섯 자리 PR · 영어 머리글(대문자 + 자간). 짧은 값이나 한국어로만
   재면 «다 보임» 이 거짓 초록이다.
🔴 한계 — 320px 에서는 등급 열이 아직 가려진다(영어 28px · 일본어 3px — 그 CSS 규칙 옆 주석). 날짜 한
   줄은 375px 부터 시험한다(한국어는 360px 부터 한 줄이다).

The repo-detail history table fits inside its card at phone widths, measured with the widest values.
"""
from __future__ import annotations

import contextlib
import os

import pytest

# 가장 넓은 행 — 점수 100(등급 A) · 다섯 자리 PR. 화면이 이 값을 내려면 DB 를 거쳐야 한다.
# The widest row: score 100 and a five-digit PR; the screen can only show it through the DB.
_WIDEST_SHA = "phone-fit-widest"
_WIDEST_SCORE = 100
_WIDEST_PR = 12345
_LANGS = ("ko", "en", "ja")
_FIT_WIDTHS = (360, 375, 390, 414, 480)
_ONE_LINE_DATE_WIDTHS = (375, 390, 414, 480)
# 480px 규칙 밖 — 점수 막대가 그대로 보여야 하는 폭(규칙이 폰 폭에만 걸렸는가).
# Outside the 480px rule: the score bar must still show here.
_BAR_WIDTHS = (481, 1440)

# 🔴 0.5px 이하의 넘침은 세지 않는다 — `scrollWidth` 는 정수로 반올림되고 `cutCols` 는 0.5px 여유를 둔다.
#    반 픽셀 미만은 칠할 때 반올림돼 글자를 자르지 않는다(Grok claim-review H1 이 짚은 허용 폭).
# Overflow of 0.5px or less is not counted: scrollWidth is rounded and cutCols allows 0.5px.
_MEASURE_JS = r"""widestPr => {
  const wrap = document.querySelector('.history-card .table-wrap');
  if (!wrap) return null;
  const wr = wrap.getBoundingClientRect();
  const r1 = v => Math.round(v * 10) / 10;
  const lines = el => {
    if (!el) return 0;
    const range = document.createRange();
    range.selectNodeContents(el);
    return new Set(Array.from(range.getClientRects()).filter(x => x.width > 0)
                        .map(x => Math.round(x.top))).size;
  };
  const ths = Array.from(wrap.querySelectorAll('thead th')).filter(th => th.checkVisibility());
  const rows = Array.from(wrap.querySelectorAll('#analysisTable tr.analysis-row'));
  const widest = rows.find(tr => (tr.querySelector('.pr-badge')?.textContent || '').trim() === widestPr);
  const bars = Array.from(wrap.querySelectorAll('.score-bar'));
  const val = widest && widest.querySelector('.score-val');
  const bar = widest && widest.querySelector('.score-bar');
  return {
    hiddenPx: wrap.scrollWidth - wrap.clientWidth,
    pageOverflowPx: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    cols: ths.map(th => th.textContent.trim()),
    cutCols: ths.filter(th => th.getBoundingClientRect().right > wr.right + 0.5)
                .map(th => [th.textContent.trim(), r1(th.getBoundingClientRect().right - wr.right)]),
    rows: rows.length,
    dateLines: rows.length ? Math.max(...rows.map(tr => lines(tr.querySelector('td.date-cell a')))) : 0,
    bars: bars.length,
    visibleBars: bars.filter(b => b.checkVisibility()).length,
    widest: widest ? {score: val ? val.textContent.trim() : null, scoreShown: !!(val && val.checkVisibility()),
                      barShown: !!(bar && bar.checkVisibility()),
                      barWidth: bar ? r1(bar.getBoundingClientRect().width) : 0} : null,
  };
}"""


@contextlib.contextmanager
def _widest_history_rows(full_name: str = "owner/testrepo"):
    """가장 넓은 값의 분석 1건을 잠시 더한다 — 맨 위 행(최신)이라 첫 쪽에 나온다.

    🔴 ORM 으로 넣고 `score_unreliable` 은 쓰기 경로와 같은 판정 함수로 채운다(원시 SQL 의 기본값은
       «신뢰 불가» 라 집계에서 빠진다). 다른 시험이 보는 행 수가 바뀌지 않게 창이 끝나면 지운다.
    Temporarily adds the widest analysis; it is the newest row, so it lands on the first page.
    """
    from datetime import datetime, timezone  # noqa: PLC0415

    from sqlalchemy import create_engine  # noqa: PLC0415
    from sqlalchemy.orm import sessionmaker  # noqa: PLC0415

    from src.models.analysis import Analysis  # noqa: PLC0415
    from src.models.repository import Repository  # noqa: PLC0415
    from src.scorer.calculator import calculate_grade  # noqa: PLC0415
    from src.scorer.reliability import score_is_unreliable  # noqa: PLC0415

    db_path = os.environ.get("DATABASE_URL", "").replace("sqlite:///", "")
    engine = create_engine(f"sqlite:///{db_path}")
    make_session = sessionmaker(bind=engine)
    result = {"summary": "e2e: 가장 넓은 이력 행 / widest history row", "issues": []}
    try:
        with make_session() as session:
            repo = session.query(Repository).filter_by(full_name=full_name).one()
            assert session.query(Analysis).filter_by(commit_sha=_WIDEST_SHA).first() is None, (
                f"{_WIDEST_SHA} 가 이미 있다 — 앞선 창이 지우지 못했다")
            session.add(Analysis(repo_id=repo.id, commit_sha=_WIDEST_SHA, score=_WIDEST_SCORE,
                                 grade=calculate_grade(_WIDEST_SCORE), pr_number=_WIDEST_PR,
                                 commit_message="e2e: 가장 넓은 이력 행", result=result,
                                 author_login="e2e-tester",
                                 created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                                 score_unreliable=score_is_unreliable(result)))
            session.commit()
        yield
    finally:
        with make_session() as session:
            session.query(Analysis).filter_by(commit_sha=_WIDEST_SHA).delete()
            session.commit()
        engine.dispose()


def _open_history(page, base_url: str, language: str, width: int) -> None:
    page.context.add_cookies([{"name": "preferred_language", "value": language, "url": base_url}])
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(f"{base_url}/repos/owner%2Ftestrepo")
    assert "localhost" in page.url, f"{page.url[:60]} 로 나갔다 — 남의 페이지를 잰다"
    lang = page.evaluate("() => document.documentElement.lang")
    assert lang == language, f"<html lang={lang!r}> — {language} 화면을 열지 못했다"
    page.wait_for_selector("#analysisTable tr.analysis-row", state="attached")


def _measure(page) -> dict:
    """표를 잰다 — 못 재면(표 · 행 · 가장 넓은 행이 없으면) 초록이 아니라 red."""
    m = page.evaluate(_MEASURE_JS, f"#{_WIDEST_PR}")
    assert m is not None, "이력 표(.history-card .table-wrap)가 없다 — 잴 대상이 없다"
    assert m["rows"] > 0, "이력 표에 행이 없다 — 잴 대상이 없다"
    assert m["widest"] is not None, (
        f"가장 넓은 행(PR #{_WIDEST_PR})이 표에 없다 — 짧은 값으로 재면 «다 보임» 이 거짓 초록이다")
    assert m["widest"]["score"] == str(_WIDEST_SCORE), f"가장 넓은 행의 점수가 {m['widest']} 다"
    return m


@pytest.mark.parametrize("language", _LANGS)
def test_history_table_fits_inside_the_card_at_phone_widths(seeded_page, base_url, language):
    """🔴 폰 폭 다섯(360~480px) — 네 열이 모두 카드 안에 들어가고, 점수는 막대 없이 숫자로 보인다.

    375px 부터는 날짜도 한 줄이다(하이픈에서 접히지 않는다).
    All four columns fit at five phone widths; the score shows as a number without its bar.
    """
    failures, measured = [], 0
    with _widest_history_rows():
        for width in _FIT_WIDTHS:
            _open_history(seeded_page, base_url, language, width)
            m = _measure(seeded_page)
            measured += 1
            if m["hiddenPx"] > 0 or m["cutCols"]:
                failures.append(f"{width}px: 표가 카드보다 {m['hiddenPx']}px 넓다 — 잘린 열 {m['cutCols']}")
            if len(m["cols"]) != 4:
                failures.append(f"{width}px: 보이는 열이 네 개가 아니다 {m['cols']}")
            if width in _ONE_LINE_DATE_WIDTHS and m["dateLines"] != 1:
                failures.append(f"{width}px: 날짜가 {m['dateLines']}줄로 접혔다")
            if m["bars"] == 0:
                failures.append(f"{width}px: 점수 막대 요소가 0개 — «막대 숨김» 을 잴 수 없다")
            if m["visibleBars"]:
                failures.append(f"{width}px: 점수 막대 {m['visibleBars']}개가 보인다 — 폭을 먹는다")
            if not m["widest"]["scoreShown"]:
                failures.append(f"{width}px: 점수 숫자가 보이지 않는다")
    assert measured == len(_FIT_WIDTHS)
    assert not failures, f"이력 표({language}):\n  " + "\n  ".join(failures)


def test_history_table_keeps_the_score_bar_above_the_phone_breakpoint(seeded_page, base_url):
    """🔴 대조군 — 480px 위에서는 점수 막대가 그대로 보인다(숨김 규칙이 폰 폭에만 걸렸는가)."""
    failures = []
    with _widest_history_rows():
        for width in _BAR_WIDTHS:
            _open_history(seeded_page, base_url, "ko", width)
            m = _measure(seeded_page)
            if not m["widest"]["barShown"] or m["widest"]["barWidth"] < 60:
                failures.append(f"{width}px: 점수 막대가 안 보이거나 줄었다 {m['widest']}")
    assert not failures, "480px 위 이력 표:\n  " + "\n  ".join(failures)


def test_history_table_instrument_sees_hidden_overflow_and_counts_lines(seeded_page, base_url):
    """🔴 계기 뒤집기 — 이 계기가 «표 안에 숨은 넘침» 과 «접힌 줄» 을 실제로 재는가.

    잡혀야 할 것: 표 안에서만 넘치는 폭(페이지는 안 넘친다 — 페이지 넘침 검사는 못 본다) · 접힌 날짜.
    무시해야 할 것: 표 밖 요소의 페이지 넘침 · 줄 수는 그대로인 키 큰 날짜 칸.
    제품 상태와 무관하게(수정 전에도) 통과해야 한다 — 기준값에 대한 변화만 본다.
    Plants on both sides: overflow hidden inside the wrap must be caught, page overflow outside the
    table must be ignored; a wrapped date must be counted, a taller one-line cell must not.
    """
    with _widest_history_rows():
        _open_history(seeded_page, base_url, "en", 375)
        base = _measure(seeded_page)

        pad = seeded_page.add_style_tag(
            content=".history-card .tbl th, .history-card .tbl td { padding-inline: 40px !important; }")
        grown = _measure(seeded_page)
        pad.evaluate("el => el.remove()")
        assert grown["hiddenPx"] > base["hiddenPx"] and grown["pageOverflowPx"] <= 0, (
            f"표 안의 넘침을 못 본다 — 기준 {base['hiddenPx']}px → 여백 40px {grown['hiddenPx']}px"
            f"(페이지 넘침 {grown['pageOverflowPx']}px)")

        seeded_page.evaluate("""() => { const d = document.createElement('div'); d.id = 'phoneFitWide';
            d.style.cssText = 'width:2000px;height:1px'; document.querySelector('.repo-hero').appendChild(d); }""")
        wide = _measure(seeded_page)
        seeded_page.evaluate("() => document.getElementById('phoneFitWide').remove()")
        assert wide["pageOverflowPx"] > 0 and wide["hiddenPx"] == base["hiddenPx"], (
            f"표 밖의 넘침을 표의 넘침으로 읽는다 — 페이지 {wide['pageOverflowPx']}px · "
            f"표 {base['hiddenPx']}px → {wide['hiddenPx']}px")

        narrow = seeded_page.add_style_tag(
            content=".history-card td.date-cell a { width: 4ch !important; }")
        folded = _measure(seeded_page)
        narrow.evaluate("el => el.remove()")
        assert folded["dateLines"] >= 2, f"접힌 날짜를 못 센다 — 4ch 폭에서 {folded['dateLines']}줄"

        tall = seeded_page.add_style_tag(
            content=".history-card td.date-cell a { min-height: 64px !important; }")
        tall_m = _measure(seeded_page)
        tall.evaluate("el => el.remove()")
        assert tall_m["dateLines"] == base["dateLines"], (
            f"칸 높이를 줄 수로 읽는다 — 기준 {base['dateLines']}줄 → 키 큰 칸 {tall_m['dateLines']}줄")
