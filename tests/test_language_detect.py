"""Phase 0.1 tests for src/analyzer/language.py — language detection covering 50 languages."""
import pytest

from src.analyzer.pure.language import detect_language, is_test_file


class TestExtensionMappingTier1:
    """Tier 1 (10 languages): python, javascript, typescript, java, go, rust, c, cpp, csharp, ruby."""

    @pytest.mark.parametrize("filename,expected", [
        ("foo.py", "python"),
        ("foo.pyi", "python"),
        ("app.js", "javascript"),
        ("app.mjs", "javascript"),
        ("app.cjs", "javascript"),
        ("component.jsx", "javascript"),
        ("component.ts", "typescript"),
        ("component.tsx", "typescript"),
        ("Main.java", "java"),
        ("main.go", "go"),
        ("lib.rs", "rust"),
        ("impl.c", "c"),
        ("impl.h", "c"),
        ("impl.cpp", "cpp"),
        ("impl.cc", "cpp"),
        ("impl.cxx", "cpp"),
        ("impl.hpp", "cpp"),
        ("impl.hxx", "cpp"),
        ("Program.cs", "csharp"),
        ("foo.rb", "ruby"),
    ])
    def test_tier1_extensions(self, filename, expected):
        assert detect_language(filename) == expected


class TestExtensionMappingTier2:
    """Tier 2 (20 languages)."""

    @pytest.mark.parametrize("filename,expected", [
        ("index.php", "php"),
        ("View.swift", "swift"),
        ("Main.kt", "kotlin"),
        ("Build.kts", "kotlin"),
        ("Main.scala", "scala"),
        ("Main.sc", "scala"),
        ("build.sh", "shell"),
        ("run.bash", "shell"),
        ("run.zsh", "shell"),
        ("script.ps1", "powershell"),
        ("module.psm1", "powershell"),
        ("query.sql", "sql"),
        ("widget.dart", "dart"),
        ("script.lua", "lua"),
        ("run.pl", "perl"),
        ("Module.pm", "perl"),
        ("analysis.r", "r"),
        ("ANALYSIS.R", "r"),
        ("app.ex", "elixir"),
        ("app.exs", "elixir"),
        ("Main.hs", "haskell"),
        ("core.clj", "clojure"),
        ("core.cljs", "clojure"),
        ("Jenkinsfile.groovy", "groovy"),
        ("build.gradle", "groovy"),
        ("index.html", "html"),
        ("page.htm", "html"),
        ("style.css", "css"),
        ("style.scss", "css"),
        ("style.sass", "css"),
        ("style.less", "css"),
        ("Token.sol", "solidity"),
        ("AppDelegate.m", "objc"),
        ("AppDelegate.mm", "objc"),
        ("Program.fs", "fsharp"),
        ("Types.fsi", "fsharp"),
    ])
    def test_tier2_extensions(self, filename, expected):
        assert detect_language(filename) == expected


class TestExtensionMappingTier3:
    """Tier 3 (20 languages)."""

    @pytest.mark.parametrize("filename,expected", [
        ("server.erl", "erlang"),
        ("records.hrl", "erlang"),
        ("parser.ml", "ocaml"),
        ("parser.mli", "ocaml"),
        ("model.jl", "julia"),
        ("main.zig", "zig"),
        ("main.nim", "nim"),
        ("app.cr", "crystal"),
        ("app.gleam", "gleam"),
        ("Main.elm", "elm"),
        ("plugin.vim", "vimscript"),
        ("player.gd", "gdscript"),
        ("main.tf", "terraform"),
        ("variables.hcl", "terraform"),
        ("config.yml", "yaml"),
        ("config.yaml", "yaml"),
        ("pyproject.toml", "toml"),
        ("schema.graphql", "graphql"),
        ("schema.gql", "graphql"),
        ("message.proto", "protobuf"),
        ("config.xml", "xml"),
        ("paper.tex", "latex"),
    ])
    def test_tier3_extensions(self, filename, expected):
        assert detect_language(filename) == expected


class TestFilenamePatterns:
    """파일명 특수 매핑 — 확장자 없는 파일들."""

    @pytest.mark.parametrize("filename,expected", [
        ("Dockerfile", "dockerfile"),
        ("Dockerfile.dev", "dockerfile"),
        ("Dockerfile.prod", "dockerfile"),
        ("Makefile", "makefile"),
        ("GNUmakefile", "makefile"),
        ("makefile", "makefile"),
        ("Rakefile", "ruby"),
        ("Gemfile", "ruby"),
    ])
    def test_filename_patterns(self, filename, expected):
        assert detect_language(filename) == expected

    def test_path_prefix_ignored(self):
        """경로 접두사는 무시 — 파일명 기반 판단."""
        assert detect_language("src/deep/nested/foo.py") == "python"
        assert detect_language("infra/docker/Dockerfile") == "dockerfile"


class TestShebangDetection:
    """확장자가 없거나 미지인 파일에 shebang이 있으면 언어 감지."""

    @pytest.mark.parametrize("content,expected", [
        ("#!/usr/bin/env python3\nprint(1)\n", "python"),
        ("#!/usr/bin/env python\n", "python"),
        ("#!/usr/bin/python2\n", "python"),
        ("#!/bin/bash\n", "shell"),
        ("#!/bin/sh\n", "shell"),
        ("#!/usr/bin/env zsh\n", "shell"),
        ("#!/usr/bin/env node\n", "javascript"),
        ("#!/usr/bin/env ruby\n", "ruby"),
        ("#!/usr/bin/env perl\n", "perl"),
        ("#!/usr/bin/env lua\n", "lua"),
        ("#!/usr/bin/env pwsh\n", "powershell"),
    ])
    def test_shebang(self, content, expected):
        assert detect_language("script", content=content) == expected


class TestUnknownFallback:
    """감지 실패 시 'unknown' 반환."""

    def test_unknown_extension(self):
        assert detect_language("mystery.xyz") == "unknown"

    def test_no_extension_no_content(self):
        assert detect_language("README") == "unknown"

    def test_empty_content_no_extension(self):
        assert detect_language("script", content="") == "unknown"


class TestPriority:
    """우선순위: 파일명 특수 매핑 > 확장자 > shebang."""

    def test_extension_beats_shebang(self):
        """확장자가 있으면 shebang을 무시한다."""
        result = detect_language("build.sh", content="#!/usr/bin/env python3\n")
        assert result == "shell"

    def test_filename_beats_shebang(self):
        """Dockerfile 같은 특수 파일명은 shebang보다 우선."""
        result = detect_language("Dockerfile", content="#!/bin/bash\n")
        assert result == "dockerfile"

    def test_shebang_only_when_no_extension(self):
        """확장자가 없을 때만 shebang 사용."""
        result = detect_language("script", content="#!/usr/bin/env python3\n")
        assert result == "python"


class TestCaseInsensitive:
    """일부 파일명은 대소문자 혼용 허용."""

    def test_dockerfile_uppercase(self):
        assert detect_language("DOCKERFILE") == "dockerfile"

    def test_makefile_lowercase(self):
        assert detect_language("makefile") == "makefile"


class TestContentNone:
    """content=None일 때 확장자/파일명만으로 판단."""

    def test_content_none_with_extension(self):
        assert detect_language("foo.py", content=None) == "python"

    def test_content_none_unknown(self):
        assert detect_language("mystery.xyz", content=None) == "unknown"


class TestIsTestFilePython:
    @pytest.mark.parametrize("filename,expected", [
        ("test_foo.py", True),
        ("foo_test.py", True),
        ("tests/test_api.py", True),
        ("src/tests/test_api.py", True),
        ("foo.py", False),
        ("src/app.py", False),
    ])
    def test_python_test_files(self, filename, expected):
        assert is_test_file(filename, "python") is expected


class TestIsTestFileJsTs:
    @pytest.mark.parametrize("filename,expected", [
        ("foo.test.ts", True),
        ("foo.spec.tsx", True),
        ("foo.test.js", True),
        ("foo.spec.jsx", True),
        ("__tests__/foo.ts", True),
        ("src/__tests__/api.js", True),
        ("foo.ts", False),
        ("app.tsx", False),
    ])
    def test_js_ts_test_files(self, filename, expected):
        lang = "typescript" if filename.endswith((".ts", ".tsx")) else "javascript"
        assert is_test_file(filename, lang) is expected


class TestIsTestFileGo:
    @pytest.mark.parametrize("filename,expected", [
        ("foo_test.go", True),
        ("pkg/handler_test.go", True),
        ("foo.go", False),
    ])
    def test_go_test_files(self, filename, expected):
        assert is_test_file(filename, "go") is expected


class TestIsTestFileJava:
    @pytest.mark.parametrize("filename,expected", [
        ("FooTest.java", True),
        ("FooTests.java", True),
        ("src/test/java/com/x/FooTest.java", True),
        ("Foo.java", False),
    ])
    def test_java_test_files(self, filename, expected):
        assert is_test_file(filename, "java") is expected


class TestIsTestFileRuby:
    @pytest.mark.parametrize("filename,expected", [
        ("foo_spec.rb", True),
        ("foo_test.rb", True),
        ("spec/foo_spec.rb", True),
        ("foo.rb", False),
    ])
    def test_ruby_test_files(self, filename, expected):
        assert is_test_file(filename, "ruby") is expected


class TestIsTestFileShell:
    @pytest.mark.parametrize("filename,expected", [
        ("foo.test.sh", True),
        ("tests/run.sh", True),
        ("build.sh", False),
    ])
    def test_shell_test_files(self, filename, expected):
        assert is_test_file(filename, "shell") is expected


class TestIsTestFileUnknownLanguage:
    """알 수 없는 언어에 대해서는 일반적 규칙(test_/tests/) 적용."""

    def test_unknown_language_defaults_false(self):
        assert is_test_file("foo.xyz", "unknown") is False
