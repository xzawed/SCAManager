"""개요 카드 — 검증 여부와 상관없이 «기록된 점수» 로 등급·막대를 그린다 (2026-10-17 사용자 결정).

## 무엇이 바뀌었나

운영(2026-10-17 읽기 전용 집계): 7개 리포 전부 AI 리뷰를 끈 뒤의 분석이 미검증(`score_unreliable`)
이다. 개요 평균이 검증된 점수만 모아서, AI 를 끈 뒤 추가한 리포 3개(분석 196·590·5회)는 등급·막대가
없었고 나머지 4개는 AI 를 끄기 전 분석만으로 등급을 냈다. 사용자 결정: «자동 점수 채점 여부와
상관없이 기록된 내용을 토대로 메인화면에는 등급과 그래프가 같이 노출».

## 이 시험이 지키는 것

- 평균 = 점수가 저장된 분석 전부(검증·미검증). 점수 NULL(진짜 AI 실패)만 빠진다.
- 미검증 점수가 들었으면 «미검증 포함», 그 리포의 AI 리뷰가 지금 꺼져 있으면(리포 토글
  `ai_review_enabled=False` 또는 전역 `AI_REVIEW_DISABLED`) «AI 리뷰 꺼짐» 을 덧붙인다 — 알리기만 하고
  등급·막대는 막지 않는다.
- 분석은 있는데 저장된 점수가 하나도 없으면 중립 «—» 칩 · 빈 막대 · «기록된 점수 없음».
- 대조군: 검증 점수만 있는 리포(평균 0 포함)와 분석 0건 리포는 종전 그대로.

판정은 카드 HTML 의 부분문자열이 아니라 **카드 안 요소의 클래스·글자**로 한다.

Overview cards grade and fill the bar from every recorded score, verified or not; an «includes
unverified» marker (+ «AI review off») tells the reader, and only a repo with no stored score at
all keeps the neutral «—» card.
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
from src.scorer.calculator import calculate_grade
from src.scorer.reliability import score_is_unreliable

# 리포별 분석 시드 — (점수, result). 신뢰도 캐시는 프로덕션 쓰기 경로와 같은 함수로 채운다.
# 점수 None = 진짜 AI 실패(api_error)라 점수가 저장되지 않은 분석이다.
# Per-repo seeds; the reliability cache is filled with the production write-path predicate.
_SEEDS = {
    "o/verified": [(92, {"ai_review_status": "success"}), (88, {"ai_review_status": "success"})],
    "o/aioff": [(70, {"ai_review_status": "disabled"})] * 3,
    "o/uncovered": [(80, {"ai_review_status": "success", "static_uncovered_languages": ["lua"]})] * 2,
    "o/mixed": [(90, {"ai_review_status": "success"}), (50, {"ai_review_status": "disabled"})],
    "o/zero": [(0, {"ai_review_status": "success"})],
    "o/failed": [(None, {"ai_review_status": "api_error"})] * 2,
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


def _texts(els: list[dict], cls: str) -> list[str]:
    return [e["text"].strip() for e in _with(els, cls)]


def _chips(els: list[dict]) -> list[tuple[set, str]]:
    return [(e["cls"], e["text"].strip()) for e in _with(els, "grade")]


def _graded(score: int) -> tuple[set, set, str]:
    """점수 하나에서 나와야 할 (칩 클래스, 막대 클래스, 등급 글자)."""
    grade = calculate_grade(score)
    return {"grade", f"grade--{grade.lower()}"}, {"score-bar", f"score-bar--{grade.lower()}"}, grade


def _bar_pct(bar: dict) -> str:
    style = bar["attrs"].get("style") or ""
    for decl in style.split(";"):
        key, _, value = decl.partition(":")
        if key.strip() == "--sb-pct":
            return value.strip()
    raise AssertionError(f"막대에 --sb-pct 가 없다: {style!r}")


def test_a_repo_with_only_unverified_analyses_shows_its_recorded_grade_and_bar(render):
    """🔴 분석 3회가 전부 AI 리뷰 꺼짐(미검증) — 기록된 점수 70 으로 칩·막대·점수를 그리고 표식을 단다."""
    els = _card(render(), "o/aioff")
    chip_cls, bar_cls, grade = _graded(70)
    assert _chips(els) == [(chip_cls, grade)], "기록된 점수가 있는데 등급 칩이 그 점수의 등급이 아니다"
    bars = _with(els, "score-bar")
    assert [b["cls"] for b in bars] == [bar_cls], [b["cls"] for b in bars]
    assert [_bar_pct(b) for b in bars] == ["70%"], "막대가 기록된 평균만큼 차지 않았다"
    assert _texts(els, "repo-card__score") == ["70"]
    assert _texts(els, "repo-card__unverified") == ["미검증 포함"]
    assert _texts(els, "repo-card__ai-off") == ["AI 리뷰 꺼짐"]
    assert not _with(els, "repo-card__no-score"), "점수가 있는데 «기록된 점수 없음» 이 붙었다"
    assert "3회" in _texts(els, "repo-card__meta")


def test_the_average_counts_every_recorded_score(render):
    """🔴 검증 90 + 미검증 50 → 평균 70 이다(검증된 것만 모으면 90). 표식은 붙고 등급은 70 의 것."""
    els = _card(render(), "o/mixed")
    chip_cls, _bar_cls, grade = _graded(70)
    assert _texts(els, "repo-card__score") == ["70"], "미검증 점수가 평균에서 빠졌다"
    assert _chips(els) == [(chip_cls, grade)]
    assert _texts(els, "repo-card__unverified") == ["미검증 포함"]
    assert not _with(els, "repo-card__ai-off"), "설정 행이 없는(기본 켜짐) 리포에 «AI 리뷰 꺼짐»"


def test_unverified_for_another_reason_does_not_claim_ai_is_off(render):
    """AI 는 켜져 있는데 미검증(미지원 언어) — 등급·막대와 «미검증 포함» 만, «AI 리뷰 꺼짐» 은 없다.

    🔴 거짓 초록 미끼: 표식의 안내 문구(title)에는 «AI 리뷰 꺼짐» 이라는 글자가 들어 있다. 카드 원문
    부분문자열로 판정하면 이 카드도 «꺼짐» 으로 읽힌다 — 그래서 표시 «요소» 로만 판정한다.
    Decoy: the hint tooltip contains the words, so a substring scan would misread this card.
    """
    html = render()
    els = _card(html, "o/uncovered")
    chip_cls, _bar_cls, grade = _graded(80)
    assert _chips(els) == [(chip_cls, grade)]
    assert _texts(els, "repo-card__unverified") == ["미검증 포함"]
    assert not _with(els, "repo-card__ai-off"), "AI 리뷰가 켜진 리포에 «AI 리뷰 꺼짐» 이 붙었다"
    assert "AI 리뷰 꺼짐" in _raw_card(html, "o/uncovered"), (
        "미끼가 사라졌다 — 안내 문구가 바뀌었다면 이 시험의 미끼를 새로 심을 것")


def test_the_global_kill_switch_also_counts_as_ai_off(render, monkeypatch):
    """전역 `AI_REVIEW_DISABLED` 도 파이프라인처럼 AI 를 끈다 — 리포 토글이 켜져 있어도."""
    monkeypatch.setenv("AI_REVIEW_DISABLED", "1")
    els = _card(render(), "o/uncovered")
    assert _texts(els, "repo-card__unverified") == ["미검증 포함"]
    assert _texts(els, "repo-card__ai-off") == ["AI 리뷰 꺼짐"]


def test_a_repo_whose_analyses_have_no_stored_score_stays_neutral(render):
    """분석 2회가 전부 진짜 AI 실패(점수 NULL) — 그릴 점수가 없으니 중립 «—» · 빈 막대 · 사유."""
    els = _card(render(), "o/failed")
    assert _chips(els) == [({"grade"}, "—")], "점수가 없는데 등급 색이 붙었다(F 처럼 보인다)"
    bars = _with(els, "score-bar")
    assert [b["cls"] for b in bars] == [{"score-bar"}], [b["cls"] for b in bars]
    assert _bar_pct(bars[0]) == "0%"
    assert not _with(els, "repo-card__score"), "점수가 없는데 점수 숫자가 그려졌다"
    assert _texts(els, "repo-card__no-score") == ["기록된 점수 없음"]
    assert not _with(els, "repo-card__unverified") and not _with(els, "repo-card__ai-off")
    assert "2회" in _texts(els, "repo-card__meta")


def test_verified_zero_and_empty_cards_are_unchanged(render):
    """대조군 — 검증 점수만 있는 카드(평균 0 포함)와 분석 0건 카드는 종전 그대로, 표식 없음."""
    html = render()
    verified = _card(html, "o/verified")
    assert _chips(verified) == [({"grade", "grade--a"}, "A")]
    assert _texts(verified, "repo-card__score") == ["90"]
    assert [_bar_pct(b) for b in _with(verified, "score-bar")] == ["90%"]
    assert not _with(verified, "repo-card__unverified") and not _with(verified, "repo-card__no-score")

    # 🔴 평균 0 은 «없음» 이 아니다 — F 칩 옆에 점수 0 과 F 막대가 있어야 한다.
    # An average of 0 is a real score, not «missing».
    zero = _card(html, "o/zero")
    assert _chips(zero) == [({"grade", "grade--f"}, "F")]
    assert _texts(zero, "repo-card__score") == ["0"]
    assert [b["cls"] for b in _with(zero, "score-bar")] == [{"score-bar", "score-bar--f"}]
    assert not _with(zero, "repo-card__unverified")

    empty = _card(html, "o/empty")
    assert not _with(empty, "grade") and not _with(empty, "score-bar")
    assert not _with(empty, "repo-card__unverified") and not _with(empty, "repo-card__no-score")
    assert "0회" in _texts(empty, "repo-card__meta")


@pytest.mark.parametrize(("lang", "marker", "ai_off", "no_score"), [
    ("en-US", "Includes unverified", "AI review off", "No recorded score"),
    ("ja-JP", "未検証を含む", "AIレビューオフ", "記録されたスコアなし"),
])
def test_the_labels_follow_the_viewer_language(render, lang, marker, ai_off, no_score):
    """문구는 요청 언어를 따른다."""
    html = render(lang)
    aioff = _card(html, "o/aioff")
    assert _texts(aioff, "repo-card__unverified") == [marker]
    assert _texts(aioff, "repo-card__ai-off") == [ai_off]
    assert _texts(_card(html, "o/failed"), "repo-card__no-score") == [no_score]
