"""i18n 패키지 — 다국어 지원 인프라 (Phase 1 PR-1b).

i18n package — multilingual support infrastructure (Phase 1 PR-1b).
"""
from src.i18n.loader import get_text, load_translations
from src.i18n.filters import register_i18n_filters

__all__ = ["get_text", "load_translations", "register_i18n_filters"]
