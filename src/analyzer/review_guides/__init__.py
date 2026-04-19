"""Language-specific review guide registry.

Usage:
    from src.analyzer.review_guides import get_guide
    guide = get_guide("python")          # full guide (default)
    guide = get_guide("go", "compact")   # compact one-liner
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

_BASE = "src.analyzer.review_guides"


def get_guide(language: str, mode: str = "full") -> str:
    """언어별 리뷰 가이드 반환.

    Args:
        language: detect_language() 반환값 (예: "python", "go")
        mode: "full" (상세) 또는 "compact" (한 줄 요약)

    Returns:
        가이드 문자열. 알 수 없는 언어는 generic fallback 반환.
    """
    entry = _GUIDE_MAP.get(language)
    if entry:
        tier_pkg, mod_name = entry
        mod = import_module(f"{_BASE}.{tier_pkg}.{mod_name}")
    else:
        mod = import_module(f"{_BASE}.generic")

    return mod.COMPACT if mode == "compact" else mod.FULL


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
