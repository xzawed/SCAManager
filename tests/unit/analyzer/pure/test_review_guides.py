"""Tests for review guide loading (Phase 0.2-0.4) and review_prompt builder (Phase 0.5)."""
import pytest

from src.analyzer.pure.review_guides import get_guide, get_tier, supported_languages
from src.analyzer.pure.review_prompt import (
    build_review_prompt,
    detect_languages_from_patches,
    has_test_files,
)


class TestGuideLoading:
    """모든 가이드 모듈이 로드 가능하고 FULL/COMPACT 문자열을 반환하는지 검증."""

    @pytest.mark.parametrize("lang", [
        "python", "javascript", "typescript", "java", "go",
        "rust", "c", "cpp", "csharp", "ruby",
    ])
    def test_tier1_guides_load(self, lang):
        full = get_guide(lang, "full")
        compact = get_guide(lang, "compact")
        assert isinstance(full, str) and len(full) > 50
        assert isinstance(compact, str) and len(compact) > 10
        assert get_tier(lang) == 1

    @pytest.mark.parametrize("lang", [
        "php", "swift", "kotlin", "scala", "shell", "powershell",
        "sql", "dart", "lua", "perl", "r", "elixir", "haskell",
        "clojure", "groovy", "html", "css", "solidity", "objc", "fsharp",
    ])
    def test_tier2_guides_load(self, lang):
        full = get_guide(lang, "full")
        compact = get_guide(lang, "compact")
        assert isinstance(full, str) and len(full) > 30
        assert isinstance(compact, str) and len(compact) > 10
        assert get_tier(lang) == 2

    @pytest.mark.parametrize("lang", [
        "erlang", "ocaml", "julia", "zig", "nim", "crystal", "gleam",
        "elm", "vimscript", "gdscript", "dockerfile", "makefile",
        "terraform", "yaml", "toml", "graphql", "protobuf", "xml",
        "latex", "json_schema",
    ])
    def test_tier3_guides_load(self, lang):
        full = get_guide(lang, "full")
        compact = get_guide(lang, "compact")
        assert isinstance(full, str) and len(full) > 30
        assert isinstance(compact, str) and len(compact) > 10
        assert get_tier(lang) == 3

    def test_generic_fallback_for_unknown(self):
        guide = get_guide("unknown_lang_xyz")
        assert isinstance(guide, str) and len(guide) > 10

    def test_tier_unknown_returns_zero(self):
        assert get_tier("nonexistent") == 0

    def test_supported_languages_count(self):
        langs = supported_languages()
        assert len(langs) == 50

    def test_all_50_languages_have_guides(self):
        for lang in supported_languages():
            assert get_guide(lang, "full"), f"Missing full guide for {lang}"
            assert get_guide(lang, "compact"), f"Missing compact guide for {lang}"


class TestDetectLanguagesFromPatches:
    def test_single_language(self):
        patches = [("foo.py", "diff"), ("bar.py", "diff")]
        langs = detect_languages_from_patches(patches)
        assert langs == ["python"]

    def test_multi_language_by_frequency(self):
        patches = [
            ("a.py", "diff"), ("b.py", "diff"),  # python x2
            ("c.go", "diff"),                      # go x1
        ]
        langs = detect_languages_from_patches(patches)
        assert langs[0] == "python"
        assert "go" in langs

    def test_unknown_files_excluded(self):
        patches = [("readme.xyz", "diff"), ("main.py", "diff")]
        langs = detect_languages_from_patches(patches)
        assert "unknown" not in langs
        assert "python" in langs

    def test_empty_patches(self):
        assert detect_languages_from_patches([]) == []


class TestBuildReviewPrompt:
    def test_returns_prompt_and_languages(self):
        patches = [("main.py", "def foo(): pass")]
        prompt, langs = build_review_prompt("feat: add foo", patches)
        assert isinstance(prompt, str) and len(prompt) > 100
        assert "python" in langs

    def test_language_guide_included(self):
        patches = [("app.go", "func main() {}")]
        prompt, langs = build_review_prompt("feat: add main", patches)
        assert "Go" in prompt or "go" in prompt.lower()
        assert "go" in langs

    def test_single_language_uses_full_guide(self):
        patches = [("script.py", "x = 1")]
        prompt, _ = build_review_prompt("chore: update", patches)
        assert "Python" in prompt

    def test_many_languages_compact_mode(self):
        """11개 이상 언어 시 compact 모드 적용 — 프롬프트 과대 성장 방지."""
        patches = [
            ("a.py", "x"), ("b.js", "x"), ("c.go", "x"),
            ("d.rs", "x"), ("e.ts", "x"), ("f.java", "x"),
            ("g.rb", "x"), ("h.sh", "x"), ("i.php", "x"),
            ("j.kt", "x"), ("k.sql", "x"), ("l.dart", "x"),
        ]
        prompt, langs = build_review_prompt("chore: multi", patches)
        assert len(langs) >= 10
        # 프롬프트가 과도하게 길지 않아야 함 (8000 토큰 * 4 chars = 32000자 이하)
        assert len(prompt) < 40000

    def test_empty_diff_fallback(self):
        patches = [("foo.py", "")]
        prompt, langs = build_review_prompt("empty", patches)
        assert isinstance(prompt, str)

    def test_no_patches(self):
        prompt, langs = build_review_prompt("empty", [])
        assert isinstance(prompt, str)
        assert langs == []

    def test_detected_langs_section_in_prompt(self):
        patches = [("main.rs", "fn main() {}")]
        prompt, _ = build_review_prompt("feat: add main", patches)
        assert "rust" in prompt.lower() or "감지" in prompt


class TestHasTestFiles:
    def test_python_test_file(self):
        assert has_test_files([("test_foo.py", "def test_x(): pass")])

    def test_non_test_file(self):
        assert not has_test_files([("app.py", "x = 1")])

    def test_go_test_file(self):
        assert has_test_files([("foo_test.go", "func TestFoo(t *testing.T) {}")])

    def test_js_test_file(self):
        assert has_test_files([("foo.test.ts", "test('x', () => {})")])

    def test_empty_patches(self):
        assert not has_test_files([])
