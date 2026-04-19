"""Language detection for 50 programming/configuration languages.

Priority:
1. Special filename patterns (Dockerfile, Makefile, Rakefile, Gemfile, ...)
2. Extension mapping (50+ extensions)
3. Shebang parsing (#!/usr/bin/env python3, #!/bin/bash, ...)
4. Fallback: "unknown"
"""
import os
import re
from pathlib import PurePosixPath

# Extension → language mapping (lowercase extension)
_EXTENSION_MAP: dict[str, str] = {
    # Tier 1
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hxx": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    # Tier 2
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin", ".kts": "kotlin",
    ".scala": "scala", ".sc": "scala",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".ps1": "powershell", ".psm1": "powershell",
    ".sql": "sql",
    ".dart": "dart",
    ".lua": "lua",
    ".pl": "perl", ".pm": "perl",
    ".r": "r",
    ".ex": "elixir", ".exs": "elixir",
    ".hs": "haskell",
    ".clj": "clojure", ".cljs": "clojure",
    ".groovy": "groovy", ".gradle": "groovy",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "css", ".sass": "css", ".less": "css",
    ".sol": "solidity",
    ".m": "objc", ".mm": "objc",
    ".fs": "fsharp", ".fsi": "fsharp",
    # Tier 3
    ".erl": "erlang", ".hrl": "erlang",
    ".ml": "ocaml", ".mli": "ocaml",
    ".jl": "julia",
    ".zig": "zig",
    ".nim": "nim",
    ".cr": "crystal",
    ".gleam": "gleam",
    ".elm": "elm",
    ".vim": "vimscript",
    ".gd": "gdscript",
    ".tf": "terraform", ".hcl": "terraform",
    ".yml": "yaml", ".yaml": "yaml",
    ".toml": "toml",
    ".graphql": "graphql", ".gql": "graphql",
    ".proto": "protobuf",
    ".xml": "xml",
    ".tex": "latex",
}

# Full-filename patterns (case-insensitive match against basename)
_FILENAME_MAP: dict[str, str] = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
    "gnumakefile": "makefile",
    "rakefile": "ruby",
    "gemfile": "ruby",
}

# Dockerfile.dev / Dockerfile.prod style prefixes
_FILENAME_PREFIX_MAP: dict[str, str] = {
    "dockerfile.": "dockerfile",
}

# Shebang interpreter basename → language
_SHEBANG_MAP: dict[str, str] = {
    "python": "python", "python2": "python", "python3": "python",
    "node": "javascript", "deno": "typescript", "bun": "typescript",
    "bash": "shell", "sh": "shell", "zsh": "shell", "fish": "shell",
    "ruby": "ruby",
    "perl": "perl",
    "php": "php",
    "lua": "lua",
    "pwsh": "powershell", "powershell": "powershell",
}

_SHEBANG_RE = re.compile(r"^#!\s*(\S+)(?:\s+(\S+))?")


def _parse_shebang(content: str) -> str:
    """첫 줄의 shebang에서 인터프리터 basename을 추출해 언어를 반환. 실패 시 empty string."""
    if not content:
        return ""
    first_line = content.splitlines()[0] if "\n" in content else content
    match = _SHEBANG_RE.match(first_line)
    if not match:
        return ""
    interpreter, arg = match.group(1), match.group(2)
    # `#!/usr/bin/env python3` → arg = "python3"
    # `#!/bin/bash` → interpreter = "/bin/bash"
    candidate = arg if interpreter.endswith("env") and arg else interpreter
    basename = os.path.basename(candidate).lower()
    return _SHEBANG_MAP.get(basename, "")


def _match_filename(basename: str) -> str:
    """파일명 특수 매핑. 대소문자 무시. 실패 시 empty string."""
    lower = basename.lower()
    if lower in _FILENAME_MAP:
        return _FILENAME_MAP[lower]
    for prefix, lang in _FILENAME_PREFIX_MAP.items():
        if lower.startswith(prefix):
            return lang
    return ""


def _match_extension(basename: str) -> str:
    """확장자 매핑. `.R` 같은 대소문자 구분 케이스 우선 조회 후 lowercase 조회. 실패 시 empty string."""
    _, ext = os.path.splitext(basename)
    if not ext:
        return ""
    # Check exact-case first (preserves `.R` vs `.r` if needed — both map to "r" here)
    return _EXTENSION_MAP.get(ext) or _EXTENSION_MAP.get(ext.lower(), "")


def detect_language(filename: str, content: str | None = None) -> str:
    """파일명(+ optional content)에서 언어 감지.

    우선순위: 특수 파일명 > 확장자 > shebang > "unknown"
    """
    basename = os.path.basename(filename)

    lang = _match_filename(basename)
    if lang:
        return lang

    lang = _match_extension(basename)
    if lang:
        return lang

    if content:
        lang = _parse_shebang(content)
        if lang:
            return lang

    return "unknown"


def _normalize_path(filename: str) -> PurePosixPath:
    """Windows/Posix 경로를 PurePosixPath로 정규화하여 디렉토리 판단을 일관되게."""
    return PurePosixPath(filename.replace("\\", "/"))


def is_test_file(filename: str, language: str) -> bool:
    """언어별 테스트 파일 규칙."""
    path = _normalize_path(filename)
    basename = path.name
    parts = path.parts

    if language == "python":
        if basename.startswith("test_") and basename.endswith(".py"):
            return True
        if basename.endswith("_test.py"):
            return True
        if "tests" in parts:
            return True
        return False

    if language in ("javascript", "typescript"):
        stem = basename.rsplit(".", 1)[0]  # strip final extension
        # foo.test.ts, foo.spec.tsx — stem ends with .test or .spec
        if stem.endswith(".test") or stem.endswith(".spec"):
            return True
        if "__tests__" in parts:
            return True
        return False

    if language == "go":
        return basename.endswith("_test.go")

    if language == "java":
        if not basename.endswith(".java"):
            return False
        name = basename[:-5]  # strip ".java"
        if name.endswith("Test") or name.endswith("Tests"):
            return True
        if "test" in parts:  # src/test/java/...
            return True
        return False

    if language == "ruby":
        if basename.endswith("_spec.rb") or basename.endswith("_test.rb"):
            return True
        if "spec" in parts:
            return True
        return False

    if language == "shell":
        stem = basename.rsplit(".", 1)[0]
        if stem.endswith(".test"):
            return True
        if "tests" in parts:
            return True
        return False

    # Generic / unknown languages — no reliable test convention
    return False
