"""SCAManager UI 일러스트 5장 prompt 정의 (사이클 93 Step 2-A).

SCAManager UI illustration prompts (5 pieces, Cycle 93 Step 2-A).

스타일 = 사용자 결정 2 (★) — Abstract isometric data flows.
Style = User decision 2 (★) — Abstract isometric data flows.

배치 = 사용자 결정 (★) — login / dashboard empty / overview onboarding /
add_repo / repo_detail filter-empty (404 페이지 = 별도 PR).

사용처:
- src/scripts/generate_illustrations.py 가 본 모듈에서 PROMPTS 를 읽어 OpenAI API 호출.
- 사용자가 prompt 검토 후 OK 시 로컬에서 실행 (OPENAI_API_KEY 의무).

DALL-E 3 prompt 가이드라인 (2026-05 기준):
- max 4000 chars
- 명확한 description + style + color palette + composition
- 텍스트/letters/numbers 명시 제외 (한글 글리프 깨짐 방지)
- 4-테마 호환 (warm cream / dark indigo / glass blue / claude-dark warm) — 중성 배경
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IllustrationPrompt:
    """단일 일러스트 prompt 정의.

    Single illustration prompt definition.
    """

    name: str            # 출력 파일명 (확장자 제외)
    placement: str       # 배치 위치 설명 (PR 본문 + 검토용)
    size: str            # DALL-E 3 size: "1024x1024" | "1792x1024" | "1024x1792"
    quality: str         # "standard" (저비용) | "hd" (고품질, 2배 비용)
    prompt: str          # 실제 OpenAI API 전달 prompt


# 4-테마 호환을 위한 공통 톤 가이드 (모든 prompt 에 일관 적용).
# Common tone guide for 4-theme compatibility (applied consistently).
_COMMON_STYLE = (
    "minimalist isometric vector illustration, 30-degree perspective, "
    "soft gradients, clean lines, modern tech aesthetic. "
    "Color palette: muted blue-purple (#5e6ad2), warm orange accents (#D97757), "
    "and sage green (#9CAF88), all on a subtle neutral background that works "
    "across both warm cream and dark indigo theme contexts. "
    "Strictly NO text, NO letters, NO numbers, NO readable code, NO labels."
)


PROMPTS: tuple[IllustrationPrompt, ...] = (
    IllustrationPrompt(
        name="login_hero",
        placement="landing.html — 히어로 섹션 (사이클 117: login.html 삭제, landing.html로 통합)",
        size="1024x1024",
        quality="hd",
        prompt=(
            "A clean isometric vector illustration of an automated code review "
            "flow. Show a stylized terminal/code editor on the left with abstract "
            "floating code-line silhouettes (no actual letters), connected by "
            "glowing data flow paths to a central analysis hub rendered as a "
            "shield-and-gear motif, which then connects to multiple notification "
            "channel icons on the right (envelope, chat bubble, bell). "
            f"Style: {_COMMON_STYLE} "
            "Mood: trustworthy, professional, modern. "
            "Composition: balanced 3-zone (input → process → output), centered "
            "focal point on the analysis hub, minimum 30% negative space."
        ),
    ),
    IllustrationPrompt(
        name="dashboard_empty",
        placement="dashboard.html L210/L678/L700 — 'No data yet' empty state (240×180)",
        size="1024x1024",
        quality="standard",
        prompt=(
            "A clean isometric vector illustration of an empty data dashboard "
            "waiting for content. Show a stylized dashboard frame with "
            "placeholder chart silhouettes (one bar chart and one line chart, "
            "both as light outlines only), and an arrow gently pointing toward "
            "a '+' add indicator with subtle floating particles suggesting "
            "potential data points. "
            f"Style: {_COMMON_STYLE} "
            "Mood: friendly, inviting, anticipatory — never empty-frustrating. "
            "Composition: dashboard frame foreground, particles mid-distance, "
            "warm orange accent only on the '+' add indicator."
        ),
    ),
    IllustrationPrompt(
        name="overview_onboarding",
        placement="overview.html L154-193 — 3-step onboarding tutorial card",
        size="1792x1024",
        quality="hd",
        prompt=(
            "A clean isometric vector illustration of a GitHub repository "
            "connection journey rendered as three left-to-right stages: "
            "(1) a stylized repository folder with branch lines, "
            "(2) a gear/settings cog mid-flow, "
            "(3) an output chart/graph with a generic score badge shape. "
            "Connect the three stages with curved glowing data flow lines. "
            f"Style: {_COMMON_STYLE} "
            "Color hint: stage 1 in blue-purple, stage 2 in sage green, "
            "stage 3 in warm orange — left-to-right gradient progression. "
            "Mood: instructional, approachable, modern. "
            "Composition: horizontal flow, three equal-weight stages, "
            "clear connecting paths."
        ),
    ),
    IllustrationPrompt(
        name="add_repo_hero",
        placement="add_repo.html — form 상단 hero (400×240)",
        size="1792x1024",
        quality="standard",
        prompt=(
            "A clean isometric vector illustration of a repository entering an "
            "analysis pipeline. Show a stylized repository folder/cube with "
            "branch lines on the left flowing into a central funnel containing "
            "subtle gear and filter motifs, exiting on the right as a result "
            "display rendered as an abstract chart or score-badge shape. "
            f"Style: {_COMMON_STYLE} "
            "Mood: welcoming, efficient, technical-but-friendly. "
            "Composition: left-to-right flow with the central funnel as the "
            "primary focal point, repository on left, result on right."
        ),
    ),
    IllustrationPrompt(
        name="filter_empty",
        placement="repo_detail.html L168 — filter-empty state (200×200)",
        size="1024x1024",
        quality="standard",
        prompt=(
            "A clean isometric vector illustration of an empty search/filter "
            "result state. Show a stylized magnifying glass hovering over an "
            "empty document or grid silhouette, with small floating particles "
            "around suggesting 'nothing matched here' without any negative "
            "or sad connotation. "
            f"Style: {_COMMON_STYLE} "
            "Mood: gentle, helpful, non-discouraging — like a librarian's "
            "polite shrug. Warm orange accent only on the magnifying glass "
            "handle. "
            "Composition: centered magnifying glass + document, small "
            "particles for liveliness."
        ),
    ),
)


def get_prompt(name: str) -> IllustrationPrompt:
    """이름으로 단일 prompt 조회 — 부재 시 KeyError.

    Look up a single prompt by name; raises KeyError if missing.
    """
    for p in PROMPTS:
        if p.name == name:
            return p
    raise KeyError(f"unknown prompt name: {name!r} (available: {[p.name for p in PROMPTS]})")
