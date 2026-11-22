"""설정 화면은 카탈로그에서 내린 모델 고정값을 보여 주고, 저장해도 지우지 않는다 (회고 2026-09-16 K10 — P1-29 · P1-44).

## 사고

`review_model` 선택 상자는 「전역 기본값」 + 현행 카탈로그만 그렸다. 리포가 카탈로그에서 내린
모델(`claude-opus-4-7`)에 고정돼 있으면 어떤 선택지도 `selected` 가 아니어서 브라우저가 첫 선택지
(전역 기본값, 값 "")를 골랐다. 그 상태로 **다른 설정을 저장하기만 해도** `review_model` 이 None 이
되어 고정이 조용히 사라졌다. 화면은 그 사실을 보여 주지도 않았다.

## 어떻게 재는가

서버가 그린 HTML 에서 «브라우저가 제출할 값» 을 뽑는다 — `selected` 선택지가 있으면 그 값,
없으면 첫 선택지의 값. 그 값을 저장 경로(`build_repo_config_from_form`)에 넣어 고정이 남는지 본다.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from html.parser import HTMLParser
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.session import CurrentUser, require_login
from src.config_manager.manager import RepoConfigData
from src.main import app
from src.shared import model_catalog as mc
from src.shared.claude_metrics import headline_rate
from src.ui.routes.settings import build_repo_config_from_form

_USER = CurrentUser(id=1, github_login="testuser", email="t@example.com",
                    display_name="Test User", plaintext_token="")
_REPO = "owner/repo"


@contextmanager
def _ctx(db):
    yield db


@pytest.fixture(autouse=True)
def _override_login():
    prev = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: _USER
    yield
    if prev is not None:
        app.dependency_overrides[require_login] = prev
    else:
        app.dependency_overrides.pop(require_login, None)


class _ReviewModelOptions(HTMLParser):
    """`<select name="review_model">` 안의 선택지 (value, selected, 글자, 묶음) 를 모은다."""

    def __init__(self):
        super().__init__()
        self.inside = False
        self.group = None
        self.options: list[list] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "select" and a.get("name") == "review_model":
            self.inside = True
        elif tag == "optgroup" and self.inside:
            self.group = a.get("label")
        elif tag == "option" and self.inside:
            self.options.append([a.get("value", ""), "selected" in a, "", self.group])

    def handle_endtag(self, tag):
        if tag == "select":
            self.inside = False
        elif tag == "optgroup":
            self.group = None

    def handle_data(self, data):
        if self.inside and self.options:
            self.options[-1][2] += data.strip()


def _render(review_model, lang="ko"):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name=_REPO, user_id=1)
    cfg = RepoConfigData(repo_full_name=_REPO, review_model=review_model)
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)), \
         patch("src.ui.routes.settings.get_repo_config", return_value=cfg), \
         patch("src.ui.routes.settings._detect_stale_webhook",
               new_callable=AsyncMock, return_value=False):
        r = TestClient(app).get("/repos/owner%2Frepo/settings", headers={"Accept-Language": lang})
    assert r.status_code == 200
    parser = _ReviewModelOptions()
    parser.feed(r.text)
    assert parser.options, "review_model 선택지를 하나도 못 찾았다 — 이 시험은 아무것도 재지 못했다"
    return parser.options


def _submitted(options) -> str:
    """브라우저가 보낼 값 — `selected` 가 여럿이면 마지막, 없으면 첫 선택지."""
    chosen = [value for value, selected, _text, _group in options if selected]
    return chosen[-1] if chosen else options[0][0]


def _offered() -> int:
    """화면이 그릴 선택지 수 — 전역 기본값 + 계열 넷 + 판 고정 / global default + four lines + pinned models."""
    auto, pinned = mc.catalog_choices()
    return 1 + len(auto) + len(pinned)


@pytest.mark.parametrize("lang, label", [
    ("ko", "목록에서 내린 모델"),
    ("en", "retired from the list"),
    ("ja", "一覧から外したモデル"),
])
def test_a_retired_pin_is_shown_selected_and_labelled(lang, label):
    """🔴 내린 모델 고정값이 선택된 채로 보이고, 세 언어 모두 내린 모델이라고 적혀 있다."""
    options = _render("claude-opus-4-7", lang)
    selected = [o for o in options if o[1]]
    assert [o[0] for o in selected] == ["claude-opus-4-7"], options
    assert "claude-opus-4-7" in selected[0][2] and label in selected[0][2], selected


def test_a_retired_pin_survives_a_save_round_trip():
    """🔴 화면이 제출할 값으로 저장하면 고정이 남는다 — 예전엔 None 이 되어 조용히 지워졌다."""
    submitted = _submitted(_render("claude-opus-4-7"))
    assert submitted == "claude-opus-4-7", f"브라우저가 {submitted!r} 를 보낸다 — 고정이 지워진다"
    with patch("src.ui.routes.settings.get_repo_config",
               return_value=RepoConfigData(repo_full_name=_REPO, review_model="claude-opus-4-7")):
        saved = build_repo_config_from_form(MagicMock(), _REPO, {"review_model": submitted})
    assert saved.review_model == "claude-opus-4-7"


def test_a_catalog_pin_adds_no_extra_option():
    """대조군 — 카탈로그 모델 고정은 그 선택지가 선택되고, 내린 모델 선택지는 생기지 않는다."""
    options = _render("claude-opus-5")
    assert _submitted(options) == "claude-opus-5"
    assert len(options) == _offered(), [o[0] for o in options]


def test_no_pin_submits_the_global_default():
    """대조군 — 고정이 없으면 아무것도 선택되지 않아 첫 선택지(전역 기본값 "")가 제출된다."""
    options = _render(None)
    assert _submitted(options) == ""
    assert len(options) == _offered(), [o[0] for o in options]


@pytest.mark.parametrize("lang, auto_group, pinned_group", [
    ("ko", "최신 모델 자동 따라가기", "모델 고정"),
    ("en", "Follow the latest model", "Pin a model"),
    ("ja", "最新モデルに自動追従", "モデルを固定"),
])
def test_the_selector_offers_the_four_lines_then_the_pinned_models(lang, auto_group, pinned_group):
    """전역 기본값 · «최신 계열» 묶음 4줄(계열 순) · «판 고정» 묶음(카탈로그 순) — 세 언어 묶음 이름."""
    options = _render(None, lang)
    auto, pinned = mc.catalog_choices()
    assert options[0][0] == "" and options[0][3] is None
    assert [(o[0], o[3]) for o in options[1:5]] == [(c.value, auto_group) for c in auto]
    assert [(o[0], o[3]) for o in options[5:]] == [(c.value, pinned_group) for c in pinned]


def test_an_auto_value_selects_its_line():
    options = _render("auto:sonnet")
    assert _submitted(options) == "auto:sonnet"
    assert len(options) == _offered()


def test_a_dated_value_selects_the_option_of_its_model():
    """🔴 날짜 붙은 저장값은 그 판의 선택지(별칭)로 선택된다 — 목록에 없는 판 줄이 생기지 않는다."""
    mc.install_snapshot([mc.ModelEntry(
        id="claude-haiku-4-5-20251001", line="haiku", display_name="Claude Haiku 4.5",
        created_at=mc.FALLBACK_CATALOG[0].created_at, deprecated_at=None, retires_at=None,
        supports_structured_outputs=True, supports_effort=False)], source="api")
    options = _render("claude-haiku-4-5-20251001")
    assert _submitted(options) == "claude-haiku-4-5"
    assert len(options) == _offered(), [o[0] for o in options]


def test_every_option_shows_the_rate_table_price():
    """선택지 가격 = 요율표(입력 / 출력, 100만 토큰당) — 계열 줄은 지금 부르는 판의 요율."""
    options = {o[0]: o[2] for o in _render(None, "en")}
    auto, pinned = mc.catalog_choices()
    for value, model in [(c.value, c.current_id) for c in auto] + [(c.value, c.value) for c in pinned]:
        price_in, price_out, _estimated = headline_rate(model)
        shown = re.search(r"\$(\d+(?:\.\d+)?) / \$(\d+(?:\.\d+)?)", options[value])
        assert shown, (value, options[value])
        assert (float(shown.group(1)), float(shown.group(2))) == (price_in, price_out), (value, options[value])


def test_prices_below_a_dollar_show_cents():
    """$0.10 — $0.1 이 아니다 / below a dollar the price shows cents."""
    from src.ui.routes.settings import _money  # pylint: disable=import-outside-toplevel

    assert [_money(v) for v in (0.1, 0.5, 2.0, 10.0, 2.5)] == ["0.10", "0.50", "2", "10", "2.50"]


class _EffortOptions(HTMLParser):
    """`<select name="review_effort">` 안의 선택지 (value, selected, 글자) 를 모은다."""

    def __init__(self):
        super().__init__()
        self.inside = False
        self.options: list[list] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "select" and a.get("name") == "review_effort":
            self.inside = True
        elif tag == "option" and self.inside:
            self.options.append([a.get("value", ""), "selected" in a, ""])

    def handle_endtag(self, tag):
        if tag == "select":
            self.inside = False

    def handle_data(self, data):
        if self.inside and self.options:
            self.options[-1][2] += data.strip()


def _render_effort(review_effort, lang="ko"):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name=_REPO, user_id=1)
    cfg = RepoConfigData(repo_full_name=_REPO, review_effort=review_effort)
    with patch("src.ui.routes.settings.SessionLocal", return_value=_ctx(db)), \
         patch("src.ui.routes.settings.get_repo_config", return_value=cfg), \
         patch("src.ui.routes.settings._detect_stale_webhook",
               new_callable=AsyncMock, return_value=False):
        r = TestClient(app).get("/repos/owner%2Frepo/settings", headers={"Accept-Language": lang})
    assert r.status_code == 200
    parser = _EffortOptions()
    parser.feed(r.text)
    assert parser.options, "review_effort 선택지를 하나도 못 찾았다 — 이 시험은 아무것도 재지 못했다"
    return parser.options


@pytest.mark.parametrize("lang, labels", [
    ("ko", ["전역 기본값 사용", "낮음", "보통", "높음"]),
    ("en", ["Use global default", "Low", "Medium", "High"]),
    ("ja", ["グローバルデフォルトを使用", "低", "中", "高"]),
])
def test_the_effort_field_offers_the_global_default_and_three_levels(lang, labels):
    """사용자 11-22 결정 — 전역 기본값 · 낮음 · 보통 · 높음(xhigh · max 는 처음엔 뺀다)."""
    options = _render_effort(None, lang)
    assert [o[0] for o in options] == ["", "low", "medium", "high"]
    assert all(text.startswith(label) for (_v, _s, text), label in zip(options, labels)), options


def test_the_stored_effort_is_selected_and_posted_back():
    """🔴 저장된 단계가 선택된 채로 그려져, 다른 설정을 저장해도 그 값이 다시 제출된다."""
    options = _render_effort("medium")
    assert [o[0] for o in options if o[1]] == ["medium"]
    with patch("src.ui.routes.settings.get_repo_config",
               return_value=RepoConfigData(repo_full_name=_REPO, review_effort="medium")):
        saved = build_repo_config_from_form(MagicMock(), _REPO, {"review_effort": _submitted_effort(options)})
    assert saved.review_effort == "medium"


def _submitted_effort(options) -> str:
    chosen = [value for value, selected, _text in options if selected]
    return chosen[-1] if chosen else options[0][0]
