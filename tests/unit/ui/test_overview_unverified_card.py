"""개요 카드 — 분석은 있는데 «검증된 점수» 가 없는 리포 (2026-10-17 사용자 신고).

## 무엇이 문제였나

운영(2026-10-17 읽기 전용 집계): `Sillok`(196회)·`Mathless`(590회)·`keycloak-sdk-php`(5회) 의
분석은 전부 점수가 있지만 `ai_review_status = "disabled"`(리포의 AI 리뷰 토글이 꺼짐)라
`score_unreliable` 이다. 개요 평균은 검증된 점수만 모으므로(R46) 평균이 없고, 카드는 등급
칩도 점수 막대도 그리지 않아 «N회» 한 줄만 남았다 — 왜 비었는지 아무 말이 없었다.
`{% if item.avg_score %}` 는 평균 0 도 «없음» 으로 읽어 F 칩 옆에서 막대를 지웠다.

## 이 시험이 지키는 것

- 검증 점수가 없는 리포 = 중립 «—» 칩(등급 색 없음) · 빈 막대 · «검증된 점수 없음».
  AI 리뷰가 꺼져 있으면(리포 토글 `ai_review_enabled=False` 또는 전역 `AI_REVIEW_DISABLED`)
  «AI 리뷰 꺼짐» 을 덧붙인다 — 파이프라인이 AI 를 끄는 두 기준과 같다.
- 대조군: 검증 점수가 있는 리포(평균 0 포함)는 칩·점수·막대, 분석 0건 리포는 개수만 — 그대로.

판정은 카드 HTML 의 부분문자열이 아니라 **카드 안 요소의 클래스·글자**로 한다.

Overview card for a repo whose analyses exist but none is verified: a neutral «—» chip, an empty
bar and a «no verified score» label (+ «AI review off» when AI review is disabled) instead of a
silently blank card.
"""
from __future__ import annotations

from html.parser import HTMLParser
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.auth.session import CurrentUser, get_current_user
from src.database import Base
from src.main import app
from src.models.analysis import Analysis
from src.models.repo_config import RepoConfig
from src.models.repository import Repository
from src.models.user import User
from src.scorer.reliability import score_is_unreliable

# 리포별 분석 시드 — (점수, result). 신뢰도 캐시는 프로덕션 쓰기 경로와 같은 함수로 채운다.
# Per-repo seeds; the reliability cache is filled with the production write-path predicate.
_SEEDS = {
    "o/verified": [(92, {"ai_review_status": "success"}), (88, {"ai_review_status": "success"})],
    "o/aioff": [(70, {"ai_review_status": "disabled"})] * 3,
    "o/uncovered": [(80, {"ai_review_status": "success", "static_uncovered_languages": ["lua"]})] * 2,
    "o/zero": [(0, {"ai_review_status": "success"})],
    "o/empty": [],
}
# 리포 AI 리뷰 토글을 끈 리포 — 나머지는 설정 행이 없다(기본값 = 켜짐).
# Repos whose AI-review toggle is off; the rest have no config row (default = on).
_AI_OFF = {"o/aioff"}

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}


@pytest.fixture(name="render")
def _render_overview(monkeypatch):
    """시드한 리포들로 `GET /` 을 그리는 함수를 준다."""
    # 🔴 개발 PC `.env` 가 kill-switch 를 켜 두면 «AI 켜짐» 대조군이 거짓 red 가 된다.
    # A kill-switch leaking from the dev `.env` would flip the AI-on controls.
    monkeypatch.delenv("AI_REVIEW_DISABLED", raising=False)
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(User(id=1, github_id="1", github_login="o", email="o@x.com", display_name="O"))
    for i, (name, rows) in enumerate(_SEEDS.items(), start=1):
        session.add(Repository(id=i, full_name=name, user_id=1))
        session.flush()
        for j, (score, result) in enumerate(rows):
            session.add(Analysis(repo_id=i, commit_sha=f"{i:02d}{j:038d}", score=score,
                                 result=result, score_unreliable=score_is_unreliable(result)))
        if name in _AI_OFF:
            session.add(RepoConfig(repo_full_name=name, ai_review_enabled=False))
    session.commit()

    class _Ctx:
        def __enter__(self):
            return session

        def __exit__(self, *_a):
            return False

    def render(lang: str = "ko-KR") -> str:
        resp = TestClient(app).get("/", headers={"Accept-Language": lang})
        assert resp.status_code == 200, resp.status_code
        return resp.text

    with (
        patch("src.ui.routes.overview.SessionLocal", return_value=_Ctx()),
        patch.object(app, "dependency_overrides", {
            get_current_user: lambda: CurrentUser(
                id=1, github_login="o", email="o@x.com", display_name="O", plaintext_token="t"),
        }),
    ):
        yield render
    session.close()
    engine.dispose()


class _Cards(HTMLParser):
    """`.repo-card` 마다 그 안의 요소(태그·클래스 집합·속성·직계 글자)를 모은다."""

    def __init__(self):
        super().__init__()
        self.cards: dict[str, list[dict]] = {}
        self._href: str | None = None
        self._depth = 0
        self._stack: list[dict] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = set((a.get("class") or "").split())
        if self._href is None:
            # 클래스 «토큰» 비교다 — `repo-card__row` 같은 하위 요소는 맞지 않는다.
            # A class-token match: `repo-card__row` does not match.
            if tag == "a" and "repo-card" in cls:
                self._href, self._depth = a.get("href"), 1
                self.cards[self._href] = []
            return
        el = {"tag": tag, "cls": cls, "attrs": a, "text": ""}
        self.cards[self._href].append(el)
        if tag not in _VOID:
            self._depth += 1
            self._stack.append(el)

    def handle_endtag(self, tag):
        if self._href is None:
            return
        self._depth -= 1
        if self._depth == 0:
            self._href, self._stack = None, []
        elif self._stack:
            self._stack.pop()

    def handle_data(self, data):
        if self._href is not None and self._stack:
            self._stack[-1]["text"] += data


def _cards(html: str) -> dict[str, list[dict]]:
    parser = _Cards()
    parser.feed(html)
    return parser.cards


def _card(html: str, name: str) -> list[dict]:
    """한 리포 카드의 요소들. 못 찾으면 red — «안 쟀음» 을 통과로 두지 않는다."""
    cards = _cards(html)
    href = f"/repos/{name}"
    assert href in cards, f"{name} 카드를 못 찾았다 — 찾은 카드 {sorted(cards)}"
    return cards[href]


def _raw_card(html: str, name: str) -> str:
    """카드 원문(미끼 확인용) — `<a … href="/repos/name">` 부터 첫 `</a>` 까지."""
    start = html.index(f'href="/repos/{name}"')
    return html[start:html.index("</a>", start)]


def _with(els: list[dict], cls: str) -> list[dict]:
    return [e for e in els if cls in e["cls"]]


def _bar_pct(bar: dict) -> str:
    style = bar["attrs"].get("style") or ""
    for decl in style.split(";"):
        key, _, value = decl.partition(":")
        if key.strip() == "--sb-pct":
            return value.strip()
    raise AssertionError(f"막대에 --sb-pct 가 없다: {style!r}")


def test_a_repo_with_only_unverified_analyses_shows_a_neutral_chip_and_says_why(render):
    """🔴 분석 3회가 전부 AI 리뷰 꺼짐(미검증) — 빈 카드가 아니라 «—» · 빈 막대 · 사유다."""
    els = _card(render(), "o/aioff")
    chips = _with(els, "grade")
    assert len(chips) == 1, f"등급 칩이 {len(chips)}개다 — 검증 점수가 없으면 중립 칩 하나여야 한다"
    assert chips[0]["cls"] == {"grade"}, f"등급 색이 붙었다(F 처럼 보인다): {chips[0]['cls']}"
    assert chips[0]["text"].strip() == "—"
    bars = _with(els, "score-bar")
    assert len(bars) == 1 and bars[0]["cls"] == {"score-bar"}, [b["cls"] for b in bars]
    assert _bar_pct(bars[0]) == "0%", "빈 막대여야 한다 — 미검증 점수를 채워 그리지 않는다"
    assert not _with(els, "repo-card__score"), "검증 점수가 없는데 점수 숫자가 그려졌다"
    labels = _with(els, "repo-card__unverified")
    assert [e["text"].strip() for e in labels] == ["검증된 점수 없음"]
    assert [e["text"].strip() for e in _with(els, "repo-card__ai-off")] == ["AI 리뷰 꺼짐"]
    assert "3회" in [e["text"].strip() for e in _with(els, "repo-card__meta")]


def test_unverified_for_another_reason_does_not_claim_ai_is_off(render):
    """AI 는 켜져 있는데 미검증(미지원 언어) — «검증된 점수 없음» 만, «AI 리뷰 꺼짐» 은 없다.

    🔴 거짓 초록 미끼: 안내 문구(title)에는 «AI 리뷰 꺼짐» 이라는 글자가 들어 있다. 카드 원문
    부분문자열로 판정하면 이 카드도 «꺼짐» 으로 읽힌다 — 그래서 표시 «요소» 로만 판정한다.
    Decoy: the hint tooltip contains the words, so a substring scan would misread this card.
    """
    html = render()
    els = _card(html, "o/uncovered")
    assert [e["text"].strip() for e in _with(els, "repo-card__unverified")] == ["검증된 점수 없음"]
    assert not _with(els, "repo-card__ai-off"), "AI 리뷰가 켜진 리포에 «AI 리뷰 꺼짐» 이 붙었다"
    assert "AI 리뷰 꺼짐" in _raw_card(html, "o/uncovered"), (
        "미끼가 사라졌다 — 안내 문구가 바뀌었다면 이 시험의 미끼를 새로 심을 것")


def test_the_global_kill_switch_also_counts_as_ai_off(render, monkeypatch):
    """전역 `AI_REVIEW_DISABLED` 도 파이프라인처럼 AI 를 끈다 — 리포 토글이 켜져 있어도."""
    monkeypatch.setenv("AI_REVIEW_DISABLED", "1")
    els = _card(render(), "o/uncovered")
    assert [e["text"].strip() for e in _with(els, "repo-card__ai-off")] == ["AI 리뷰 꺼짐"]


def test_verified_and_empty_cards_are_unchanged(render):
    """대조군 — 검증 점수가 있는 카드(평균 0 포함)와 분석 0건 카드는 종전 그대로다."""
    html = render()
    verified = _card(html, "o/verified")
    assert [(e["cls"], e["text"].strip()) for e in _with(verified, "grade")] == [({"grade", "grade--a"}, "A")]
    assert [e["text"].strip()[:2] for e in _with(verified, "repo-card__score")] == ["90"]
    assert [_bar_pct(b) for b in _with(verified, "score-bar")] == ["90%"]
    assert not _with(verified, "repo-card__unverified")

    # 🔴 검증된 평균 0 은 «없음» 이 아니다 — F 칩 옆에 점수 0 과 막대가 있어야 한다.
    # A verified average of 0 is a real score, not «missing».
    zero = _card(html, "o/zero")
    assert [(e["cls"], e["text"].strip()) for e in _with(zero, "grade")] == [({"grade", "grade--f"}, "F")]
    assert [e["text"].strip()[:1] for e in _with(zero, "repo-card__score")] == ["0"]
    assert [b["cls"] for b in _with(zero, "score-bar")] == [{"score-bar", "score-bar--f"}]

    empty = _card(html, "o/empty")
    assert not _with(empty, "grade") and not _with(empty, "score-bar")
    assert not _with(empty, "repo-card__unverified")
    assert "0회" in [e["text"].strip() for e in _with(empty, "repo-card__meta")]


@pytest.mark.parametrize(("lang", "label", "ai_off"), [
    ("en-US", "No verified score", "AI review off"),
    ("ja-JP", "検証済みスコアなし", "AIレビューオフ"),
])
def test_the_labels_follow_the_viewer_language(render, lang, label, ai_off):
    """문구는 요청 언어를 따른다."""
    els = _card(render(lang), "o/aioff")
    assert [e["text"].strip() for e in _with(els, "repo-card__unverified")] == [label]
    assert [e["text"].strip() for e in _with(els, "repo-card__ai-off")] == [ai_off]
