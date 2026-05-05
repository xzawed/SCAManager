"""Language-specific review guide registry.

Phase 4 PR-13 (사이클 84) — output_language 인자 추가 (en/ko/ja). Tier1 10 가이드 i18n 적용.
Phase 4 PR-13 (Cycle 84) — output_language arg added (en/ko/ja). Tier1 10 guides i18n.

Usage:
    from src.analyzer.pure.review_guides import get_guide
    guide = get_guide("python")                              # English (default)
    guide = get_guide("python", "full", output_language="ko")  # Korean
    guide = get_guide("go", "compact", output_language="ja")   # Japanese (compact)

Tier 분류 기준 (신규 언어 추가 시 참조):
    Tier 1 — 업계 점유율 상위 (~10개): 상용/오픈소스 정적분석 도구 3+ 지원,
             체크리스트를 full + compact 두 모드로 상세 제공.
             python · javascript · typescript · java · go · rust · c · cpp · csharp · ruby
    Tier 2 — 니치/응용 언어 (~20개): 정적분석 도구 1~2개, 특정 도메인 (모바일·
             백엔드·스크립트) 에서 중요. Tier 1 보다 간결한 가이드.
             php · swift · kotlin · scala · shell · dart · solidity 등
    Tier 3 — 레퍼런스/마이너 언어 (~20개): 도구 1개 미만, 경량 일반 가이드.
             erlang · ocaml · julia · zig · dockerfile 등

다국어 적용 영역:
    - Tier 1 (PR-13): 영어/한국어/일본어 3 언어 — `FULL`/`COMPACT`/`FULL_KO`/`COMPACT_KO`/`FULL_JA`/`COMPACT_JA`
    - Tier 2 (PR-14): 영어/한국어/일본어 3 언어 — 동일 패턴
    - Tier 3 (PR-15): 영어/한국어/일본어 3 언어 — 동일 패턴
    - generic.py (PR-15): 영어/한국어/일본어 3 언어

새 언어 추가 시: `tier{N}/{language}.py` 파일 생성 + `_GUIDE_MAP` 에 1줄 등록.
i18n 적용 시: 동일 파일 안 `FULL`/`COMPACT` (영문 default) + `FULL_KO/JA` + `COMPACT_KO/JA` 추가.
"""
from importlib import import_module

# language → (tier_package, module_name)
_GUIDE_MAP: dict[str, tuple[str, str]] = {
    # Tier 1
    "python": ("tier1", "python"),
    "javascript": ("tier1", "javascript"),
    "typescript": ("tier1", "typescript"),
    "java": ("tier1", "java"),
    "go": ("tier1", "go"),
    "rust": ("tier1", "rust"),
    "c": ("tier1", "c"),
    "cpp": ("tier1", "cpp"),
    "csharp": ("tier1", "csharp"),
    "ruby": ("tier1", "ruby"),
    # Tier 2
    "php": ("tier2", "php"),
    "swift": ("tier2", "swift"),
    "kotlin": ("tier2", "kotlin"),
    "scala": ("tier2", "scala"),
    "shell": ("tier2", "shell"),
    "powershell": ("tier2", "powershell"),
    "sql": ("tier2", "sql"),
    "dart": ("tier2", "dart"),
    "lua": ("tier2", "lua"),
    "perl": ("tier2", "perl"),
    "r": ("tier2", "r"),
    "elixir": ("tier2", "elixir"),
    "haskell": ("tier2", "haskell"),
    "clojure": ("tier2", "clojure"),
    "groovy": ("tier2", "groovy"),
    "html": ("tier2", "html"),
    "css": ("tier2", "css"),
    "solidity": ("tier2", "solidity"),
    "objc": ("tier2", "objc"),
    "fsharp": ("tier2", "fsharp"),
    # Tier 3
    "erlang": ("tier3", "erlang"),
    "ocaml": ("tier3", "ocaml"),
    "julia": ("tier3", "julia"),
    "zig": ("tier3", "zig"),
    "nim": ("tier3", "nim"),
    "crystal": ("tier3", "crystal"),
    "gleam": ("tier3", "gleam"),
    "elm": ("tier3", "elm"),
    "vimscript": ("tier3", "vimscript"),
    "gdscript": ("tier3", "gdscript"),
    "dockerfile": ("tier3", "dockerfile"),
    "makefile": ("tier3", "makefile"),
    "terraform": ("tier3", "terraform"),
    "yaml": ("tier3", "yaml"),
    "toml": ("tier3", "toml"),
    "graphql": ("tier3", "graphql"),
    "protobuf": ("tier3", "protobuf"),
    "xml": ("tier3", "xml"),
    "latex": ("tier3", "latex"),
    "json_schema": ("tier3", "json_schema"),
}

_BASE = "src.analyzer.pure.review_guides"


def get_guide(language: str, mode: str = "full", output_language: str = "en") -> str:
    """언어별 리뷰 가이드 반환 (Phase 4 PR-13 — output_language 인자 추가).

    Return language-specific review guide (Phase 4 PR-13 — output_language arg added).

    Args:
        language: detect_language() 반환값 (예: "python", "go") — 가이드 대상 언어
        mode: "full" (상세) 또는 "compact" (한 줄 요약)
        output_language: "en" / "ko" / "ja" — 가이드 텍스트 출력 언어 (default 'en').
            가이드 모듈에 해당 언어 변형 (FULL_KO / COMPACT_JA 등) 부재 시 영문 fallback.

    Returns:
        가이드 문자열. 알 수 없는 언어는 generic fallback 반환.
        Tier1 (10 언어) 만 i18n 완료 — Tier2/3 은 영문만 (PR-14/15 진행 영역).

    가이드 모듈 컨벤션:
        FULL / COMPACT          — 영문 (default). 모든 모듈 의무.
        FULL_KO / COMPACT_KO    — 한국어 (Tier1 10 모듈 PR-13 적용 / Tier2/3 PR-14/15)
        FULL_JA / COMPACT_JA    — 일본어 (동일)

    출력 언어 fallback chain:
        output_language='ko' → FULL_KO → FULL (영문 fallback)
        output_language='ja' → FULL_JA → FULL (영문 fallback)
        output_language='en' or invalid → FULL (영문)
    """
    entry = _GUIDE_MAP.get(language)
    if entry:
        tier_pkg, mod_name = entry
        mod = import_module(f"{_BASE}.{tier_pkg}.{mod_name}")
    else:
        mod = import_module(f"{_BASE}.generic")

    # Phase 4 PR-13 — output_language 별 attr 검색 + 영문 fallback
    # Phase 4 PR-13 — per-language attr lookup with English fallback
    attr_base = "FULL" if mode == "full" else "COMPACT"
    if output_language in ("ko", "ja"):
        candidate = f"{attr_base}_{output_language.upper()}"
        translated = getattr(mod, candidate, None)
        if translated:
            return translated
    # 영문 default (output_language='en' 또는 번역 부재 시 영문 fallback)
    # English default (output_language='en' or missing translation falls back to English)
    return getattr(mod, attr_base)


def get_tier(language: str) -> int:
    """언어의 Tier 번호 반환 (1/2/3). 알 수 없으면 0."""
    entry = _GUIDE_MAP.get(language)
    if not entry:
        return 0
    tier_pkg, _ = entry
    return int(tier_pkg[-1])


def supported_languages() -> list[str]:
    """가이드가 있는 언어 목록 반환."""
    return list(_GUIDE_MAP.keys())
