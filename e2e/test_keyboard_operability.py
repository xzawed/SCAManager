"""E2E 가드 — 마우스 없이 «조작» 이 되는가 (WCAG 2.1.1 키보드 · 2.4.3 포커스 순서).

포커스 «표시» 스윕(`test_theme_mobile_guards.py`)은 CDP 로 `:focus` 를 «강제» 해 칠해진 모양만
잰다 — 포커스가 실제로 그 자리에 «도달» 하는지, 키가 무엇을 하는지는 재지 않는다. 그래서 두
메뉴의 `keydown` 처리기를 통째로 지워도 스위트가 초록이었다(#1746 K15 P1-60). 여기서는 실제
키를 누르고 `document.activeElement` 와 화면 상태를 본다.

실측(수정 전):

| 자리 | 수정 전 |
|---|---|
| 테마·언어 메뉴(`role="menu"`) | ↓/↑ 로 열리지 않고 항목 사이를 오갈 수 없다 · Escape 무반응 (P2-67) |
| 키보드로 언어 변경 | body 가 통째로 바뀌며 포커스가 문서 처음으로 떨어진다 — 테마 팔만 버튼으로 돌려줬다 (P2-68) |
| 리포 상세 분석 표 | 행에 `onclick` 만 있고 정렬 머리글은 `th` 의 click 뿐 — Tab 으로 하나도 닿지 않는다 (P1-59) |
"""
import os
import re

from sqlalchemy import create_engine, text

_ACTIVE_JS = """() => { const a = document.activeElement || document.body;
    return {id: a.id || '', tag: a.tagName.toLowerCase(), role: a.getAttribute('role') || '',
            theme: (a.dataset && a.dataset.themeTarget) || '', lang: (a.dataset && a.dataset.lang) || '',
            inMenu: !!a.closest('[role="menu"]'), href: a.getAttribute('href') || ''}; }"""


def _active(page) -> dict:
    return page.evaluate(_ACTIVE_JS)


def _menu_open(page, switcher_id: str) -> bool:
    return page.evaluate("(id) => document.getElementById(id).classList.contains('open')", switcher_id)


def _order(page, menu_id: str, key: str) -> list[str]:
    return page.evaluate(
        "([id, key]) => [...document.querySelectorAll('#' + id + ' [role=\"menuitemradio\"]')]"
        ".map(e => e.dataset[key])", [menu_id, key])


def test_theme_menu_keeps_the_menu_button_keyboard_contract(seeded_page, base_url):
    """🔴 `role="menu"` 는 키보드 계약을 약속한다(WAI-ARIA APG «메뉴 버튼»).

    버튼: ↓ 는 열고 첫 항목 · ↑ 는 열고 마지막 항목 · Enter(클릭)로 열어도 첫 항목.
    항목: ↑↓ 순환 · Home/End 양끝 · Escape 는 닫고 버튼으로 · Tab 은 닫고 지나간다 ·
    Enter 는 고르고 닫은 뒤 버튼으로.
    """
    p = seeded_page
    p.goto(f"{base_url}/dashboard")
    order = _order(p, "themeDropdown", "themeTarget")
    assert len(order) >= 3, f"테마 항목이 {order} — 재지 못한 것이지 통과가 아니다"

    p.focus("#themeToggle")
    p.keyboard.press("ArrowDown")
    assert _menu_open(p, "themeSwitcher"), "↓ 로 메뉴가 열리지 않았다"
    assert p.get_attribute("#themeToggle", "aria-expanded") == "true"
    assert _active(p)["theme"] == order[0], f"↓ 로 연 뒤 포커스 = {_active(p)} — 첫 항목이어야 한다"
    p.keyboard.press("ArrowDown")
    assert _active(p)["theme"] == order[1], "↓ 가 다음 항목으로 옮기지 않는다"
    p.keyboard.press("End")
    assert _active(p)["theme"] == order[-1], "End 가 마지막 항목으로 가지 않는다"
    p.keyboard.press("ArrowDown")
    assert _active(p)["theme"] == order[0], "마지막에서 ↓ 가 처음으로 돌지 않는다"
    p.keyboard.press("ArrowUp")
    assert _active(p)["theme"] == order[-1], "처음에서 ↑ 가 마지막으로 돌지 않는다"
    p.keyboard.press("Home")
    assert _active(p)["theme"] == order[0], "Home 이 첫 항목으로 가지 않는다"

    p.keyboard.press("Escape")
    assert not _menu_open(p, "themeSwitcher"), "Escape 로 메뉴가 닫히지 않았다"
    assert p.get_attribute("#themeToggle", "aria-expanded") == "false"
    assert _active(p)["id"] == "themeToggle", f"Escape 뒤 포커스 = {_active(p)} — 버튼으로 돌아와야 한다"

    p.keyboard.press("ArrowUp")
    assert _active(p)["theme"] == order[-1], "↑ 로 열면 마지막 항목이어야 한다"
    p.keyboard.press("Tab")
    assert not _menu_open(p, "themeSwitcher"), "Tab 으로 메뉴를 떠났는데 열린 채로 남았다"
    assert not _active(p)["inMenu"], f"Tab 뒤에도 포커스가 메뉴 안이다: {_active(p)}"

    p.focus("#themeToggle")
    p.keyboard.press("Enter")
    assert _menu_open(p, "themeSwitcher"), "Enter 로 메뉴가 열리지 않았다"
    assert _active(p)["theme"] == order[0], f"Enter 로 연 뒤 포커스 = {_active(p)} — 첫 항목이어야 한다"
    pick = order[1]
    p.keyboard.press("ArrowDown")
    p.keyboard.press("Enter")
    assert p.evaluate("() => document.documentElement.getAttribute('data-theme')") == pick, (
        "Enter 로 고른 테마가 적용되지 않았다")
    assert not _menu_open(p, "themeSwitcher")
    assert _active(p)["id"] == "themeToggle", f"고른 뒤 포커스 = {_active(p)} — 버튼으로 돌아와야 한다"


def test_mouse_open_leaves_focus_on_the_menu_button(seeded_page, base_url):
    """마우스로 열면 포커스를 옮기지 않는다 — 키보드 계약이 마우스 사용자의 포커스를 빼앗지 않게.

    대조군: 위 시험의 «Enter 로 열면 첫 항목» 이 진짜로 «키보드에서만» 일어나는지 본다.
    """
    p = seeded_page
    p.goto(f"{base_url}/dashboard")
    p.click("#themeToggle")
    assert _menu_open(p, "themeSwitcher"), "클릭으로 메뉴가 열리지 않았다"
    assert not _active(p)["inMenu"], f"마우스로 열었는데 포커스가 항목으로 옮겨졌다: {_active(p)}"


def test_language_change_by_keyboard_returns_focus_to_the_language_button(seeded_page, base_url):
    """🔴 키보드로 언어를 바꾸면 body 가 통째로 바뀐 뒤에도 포커스가 언어 버튼에 있다.

    수정 전: 전환이 body 를 `outerHTML` 로 갈아 끼워, 포커스가 사라진 항목과 함께 문서 처음으로
    떨어졌다 — 같은 파일의 테마 팔은 `toggleBtn.focus()` 로 돌려줬는데 언어 팔만 열려 있었다.

    🔴 전환은 사용자 행(`users.preferred_language`)도 바꾼다 — 뒤 시험이 다른 언어 분포를 보지
       않게 원래 값으로 되돌린다(쿠키는 이 시험의 컨텍스트와 함께 사라진다).
    """
    p = seeded_page
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        original = conn.execute(text("SELECT preferred_language FROM users WHERE id = 1")).scalar()
    try:
        p.goto(f"{base_url}/dashboard")
        before = p.evaluate("() => document.documentElement.lang")
        target = "ja" if before != "ja" else "en"
        order = _order(p, "langDropdown", "lang")
        assert target in order, f"언어 항목 {order} 에 {target} 이 없다"

        p.focus("#langToggle")
        p.keyboard.press("ArrowDown")
        assert _active(p)["lang"] == order[0], f"↓ 로 연 뒤 포커스 = {_active(p)}"
        for _ in range(order.index(target)):
            p.keyboard.press("ArrowDown")
        assert _active(p)["lang"] == target, f"{target} 항목에 닿지 못했다: {_active(p)}"
        with p.expect_response(lambda r: "preferred-language" in r.url) as resp:
            p.keyboard.press("Enter")
        assert resp.value.ok, f"언어 저장 응답 {resp.value.status} — 전환 자체가 안 됐다"
        label = {"ja": "ダッシュボード", "en": "Dashboard"}[target]
        # body 교체가 끝났다는 신호 = 서버가 새 언어로 그린 nav 글자(`<html lang>` 은 교체 «전» 에 바뀐다).
        p.wait_for_function(
            "(t) => { const a = document.querySelector('nav a.nav-link[href=\"/dashboard\"]');"
            " return !!a && a.textContent.trim() === t; }", arg=label, timeout=10000)
        p.wait_for_timeout(300)
        focused = _active(p)
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE users SET preferred_language = :v WHERE id = 1"), {"v": original})
        engine.dispose()
    assert focused["id"] == "langToggle", (
        f"키보드로 언어를 바꾼 뒤 포커스 = {focused} — 언어 버튼으로 돌아와야 한다")


def test_analysis_history_is_operable_without_a_mouse(seeded_page, base_url, seeded_analysis):
    """🔴 리포 상세의 분석 이력 — 정렬과 «행 열기» 를 키보드만으로 할 수 있다.

    수정 전: 행은 `<tr onclick>`, 정렬은 `th` 의 click 처리기뿐이라 Tab 으로 하나도 닿지 않았다.
    «포커스 표시» 작업이 여기에 원리적으로 도달하지 못한 이유다 — 포커스를 받는 요소가 없었다.
    """
    p = seeded_page
    p.goto(f"{base_url}/repos/owner%2Ftestrepo")
    p.wait_for_selector("#analysisTable tr.analysis-row", state="attached")

    # 정렬: 머리글 안의 «버튼» 이 받고, 상태는 그대로 `th[aria-sort]` 가 나른다.
    p.focus("#searchInput")
    reached = None
    for _ in range(40):
        p.keyboard.press("Tab")
        reached = p.evaluate("() => { const t = document.activeElement.closest('th.sortable-th');"
                             " return t ? t.dataset.sort : null; }")
        if reached:
            break
    assert reached, "Tab 으로 정렬 머리글에 닿지 못했다 — 머리글이 포커스를 받지 않는다"
    before = p.get_attribute(f"th.sortable-th[data-sort='{reached}']", "aria-sort")
    p.keyboard.press("Enter")
    after = p.get_attribute(f"th.sortable-th[data-sort='{reached}']", "aria-sort")
    assert after in ("ascending", "descending") and after != before, (
        f"Enter 로 정렬되지 않았다(aria-sort {before!r} → {after!r})")

    # 행 열기: 첫 칸의 진짜 링크(좁은 화면에서도 남는 열).
    hit = None
    for _ in range(40):
        p.keyboard.press("Tab")
        hit = p.evaluate("() => { const a = document.activeElement;"
                         " return a.closest('#analysisTable') ? (a.getAttribute('href') || a.tagName) : null; }")
        if hit:
            break
    assert hit and re.search(r"/analyses/\d+$", hit), (
        f"Tab 으로 분석 행의 링크에 닿지 못했다(도달 = {hit!r}) — 행이 마우스 전용이다")
    p.keyboard.press("Enter")
    p.wait_for_function("() => /\\/analyses\\/\\d+$/.test(location.pathname)", timeout=10000)
