#!/usr/bin/env python3
"""
env-vars 싱크 점검 — src/config.py Settings 필드 ↔ docs/reference/env-vars.md 등재 정합.
env-vars sync checker — Settings env fields ↔ env-vars.md table entries.

신규 환경변수 env-vars.md 미등재(사이클 82/119 Codex 반복 적발)를 turn-0 차단.
내부 전용/파생 필드는 _INTERNAL_FIELDS allowlist 제외. stdlib 전용. 미등재 0건이면 exit 0.
Block newly added env vars missing from env-vars.md (cycle 82/119 repeated findings).
Internal/derived-only fields are excluded via _INTERNAL_FIELDS allowlist. stdlib only. Exit 0 if none missing.
"""
import io
import re
import sys
from pathlib import Path

# Windows cp949 출력 보호 — 한글 출력 깨짐 방지
# Windows cp949 stdout protection — prevent garbled Korean output
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# config.py Settings 의 비-env 내부/파생 필드 (env-vars.md 등재 면제). 사유는 주석.
# Non-env internal/derived Settings fields exempt from env-vars.md (reason inline).
# Step 1 사전 조사(2026-06-23) 결과: 56개 전 필드 env-vars.md 등재 확인 — 내부 전용 없음.
# Step 1 pre-survey (2026-06-23): all 56 fields confirmed in env-vars.md — no internal-only fields.
_INTERNAL_FIELDS: frozenset[str] = frozenset()

# Settings 클래스 본문의 4칸 들여쓰기 필드 패턴 (pydantic BaseSettings 규칙)
# 4-space indented field pattern inside Settings class body (pydantic BaseSettings convention)
_FIELD_RE = re.compile(r"^    ([a-z][a-z0-9_]*)\s*:", re.MULTILINE)

# env-vars.md 테이블 등재 패턴: | `ENV_NAME` | ... |
# env-vars.md table entry pattern: | `ENV_NAME` | ... |
_DOCUMENTED_RE = re.compile(r"\|\s*`([A-Z][A-Z0-9_]*)`")


def check_sync(project_root: Path) -> tuple[bool, list[str]]:
    """config.py Settings env 필드가 env-vars.md 에 전부 등재됐는지 검사.
    Check that all Settings env fields in config.py are listed in env-vars.md.

    Returns:
        (ok, messages) — ok=True 이면 전부 등재, False 이면 messages 에 미등재 목록.
        (ok, messages) — ok=True means all documented, False means messages lists missing entries.
    """
    # 설정 파일과 문서 파일 읽기 / Read config and docs files
    cfg = (project_root / "src" / "config.py").read_text(encoding="utf-8")
    ev = (project_root / "docs" / "reference" / "env-vars.md").read_text(encoding="utf-8")

    # Settings 필드 추출 / Extract Settings fields
    fields = _FIELD_RE.findall(cfg)

    # env-vars.md 등재 항목 집합 / Set of documented env var names
    documented = set(_DOCUMENTED_RE.findall(ev))

    # 미등재 필드 목록 (allowlist 제외, 대문자 비교) / Missing fields (excluding allowlist, uppercase compare)
    missing = [
        f for f in fields
        if f not in _INTERNAL_FIELDS and f.upper() not in documented
    ]

    if not missing:
        return True, []

    # 미등재 항목별 오류 메시지 생성 / Build error message per missing entry
    return False, [
        f"❌ env-vars.md 미등재: {f} (→ `{f.upper()}`) — 등재 또는 _INTERNAL_FIELDS allowlist"
        for f in missing
    ]


def main() -> int:
    """CLI 진입점 — 통과 0 / 위반 1.
    CLI entry point — exit 0 on pass, exit 1 on violation.
    """
    project_root = Path(__file__).resolve().parents[1]
    ok, msgs = check_sync(project_root)
    print("=== env-vars 싱크 점검 / Env-Vars Sync Check ===\n")
    if ok:
        print("✅ config.py Settings 의 모든 env 필드가 env-vars.md 에 등재됨")
        print("✅ All Settings env fields are documented in env-vars.md")
        return 0
    for m in msgs:
        print(m)
    print("\n해결: docs/reference/env-vars.md 테이블에 등재하거나, 비-env 내부 필드면 _INTERNAL_FIELDS 추가.")
    print("Fix: add to docs/reference/env-vars.md table, or add to _INTERNAL_FIELDS if internal-only.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
