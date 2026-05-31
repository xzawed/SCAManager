"""사이클 147 Sprint 2 — landing.html render-parity 가드 (회고 P1-4).

Cycle 147 Sprint 2 — landing.html render-parity guards (retro P1-4).

배경 (Background):
사이클 146 신규 테스트(test_i18n_common_landing.py)는 JSON 키 존재만 검증.
landing.html 이 오타 키를 호출하면 raw 'landing.<key>' 가 노출되나 키 존재 테스트는
통과하는 사각 존재. 사이클 144 #696 render-parity 패턴을 사이클 146 키에 적용.

landing.html 은 standalone (base.html 미상속, always-dark 디자인). context 는
locale 만 필요 (+ 선택적 error → OAuth 오류 배너). 3 언어(en/ko/ja) 검증 +
데모 리뷰 HTML(<strong>) 보존 확인.
"""
from __future__ import annotations

import re

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.i18n.filters import register_i18n_filters


def _render(template_name: str, **context) -> str:
    env = Environment(
        loader=FileSystemLoader("src/templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    register_i18n_filters(env)
    return env.get_template(template_name).render(**context)


# ── 한국어 render ────────────────────────────────────────────────────────────


def test_landing_renders_korean_hero_and_features():
    """hero + feature 카드 4종 한국어 렌더 (오타 키면 raw 키 노출 → 실패)."""
    out = _render("landing.html", locale="ko")
    assert "AI 코드 리뷰 자동화" in out  # badge / page_title
    assert "완벽한 코드 리뷰" in out  # hero_gradient
    assert "지금 시작" in out  # cta_start
    assert "왜 SCAManager인가?" in out  # features_heading
    assert "자동 코드 리뷰" in out  # feature_auto_title
    assert "스마트 Gate" in out  # feature_gate_title
    assert "점수 시스템" in out  # feature_score_title
    assert "멀티 채널 알림" in out  # feature_notify_title


def test_landing_renders_korean_demo_review_html_preserved():
    """데모 리뷰 4종 + <strong> HTML 태그 보존 (| safe 필터 — escape 안 됨)."""
    out = _render("landing.html", locale="ko")
    # safe 필터로 <strong> 가 raw HTML 로 보존되어야 함 (escape 된 &lt;strong&gt; 아님)
    assert "<strong>보안:</strong>" in out  # demo_review_1
    assert "<strong>성능:</strong>" in out  # demo_review_2
    assert "<strong>코드 품질:</strong>" in out  # demo_review_4
    assert "&lt;strong&gt;" not in out  # escape 회귀 가드 / escape regression guard


# ── 영어 render ──────────────────────────────────────────────────────────────


def test_landing_renders_english():
    out = _render("landing.html", locale="en")
    assert "Flawless Code Review" in out  # hero_gradient
    assert "Automatic Code Review" in out  # feature_auto_title
    assert "<strong>Security:</strong>" in out  # demo_review_1 (safe HTML)


# ── 일본어 render ────────────────────────────────────────────────────────────


def test_landing_renders_japanese():
    out = _render("landing.html", locale="ja")
    assert "完璧なコードレビュー" in out  # hero_gradient
    assert "自動コードレビュー" in out  # feature_auto_title


# ── error 배너 조건부 블록 ───────────────────────────────────────────────────


def test_landing_renders_error_banner_korean():
    """error='oauth_failed' 시 OAuth 오류 배너 렌더 (조건부 블록 활성화)."""
    out = _render("landing.html", locale="ko", error="oauth_failed")
    assert "로그인 중 문제가 발생했습니다" in out  # error_oauth_failed


def test_landing_renders_generic_error_banner_korean():
    """error='other' 시 generic 오류 배너 렌더."""
    out = _render("landing.html", locale="ko", error="something_else")
    assert "일시적인 오류가 발생했습니다" in out  # error_generic


# ── raw 키 누출 회귀 가드 ────────────────────────────────────────────────────


def test_landing_no_raw_key_leak():
    """렌더 출력에 raw 'landing.<key>' 미노출 회귀 가드 (오타 키 탐지)."""
    out = _render("landing.html", locale="ko", error="oauth_failed")
    leaks = re.findall(r"landing\.[a-z_]+", out)
    assert not leaks, f"raw landing 키 노출: {leaks}"
