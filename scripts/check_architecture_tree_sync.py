#!/usr/bin/env python3
"""docs/architecture.md 의 src/ 트리가 **실제 src/ 구조와 동기**인지 강제.

## 사고 — "신규 파일 미등재" 3회 재발 (2026-07-20 문서 재구성 진단 P1)

CLAUDE.md 는 `docs/architecture.md` 를 src/ 트리 **단일 출처**로 선언하고, 6-step ⑥ 이 신규
파일 추가 시 동기화를 의무화한다. 그런데 그걸 강제하는 **기계 가드가 0개**라, 신규 파일 미등재가
순전히 인지(사람이 기억)에 의존했다 — 전례 3건(Phase 11 #73 · 2026-05-01 UI cleanup · 사이클
78~82 환경변수 4건). `check_env_vars_sync.py`(config.py↔env-vars.md)와 동형의 가드가 필요하다.

## 판정 = 실제 파일시스템 ↔ 문서 대조 (산문 아님, AGENTS.md 불변식 1)

`src/` 의 패키지(디렉토리)와 최상위 모듈이 architecture.md 트리에 **문자열로 등장**하는지 본다.
의도적 축약(트리에 개별 나열 안 하는 것)은 `_ALLOWLIST` 에 사유와 함께. 그래야 "빠뜨림" 과
"의도적 생략" 이 구별된다.
"""
import sys
from pathlib import Path

# stdout UTF-8 (Windows cp949 크래시 방지 — guards.md 관용구)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

_ROOT = Path(__file__).resolve().parents[1]
_ARCH = _ROOT / "docs" / "architecture.md"
_SRC = _ROOT / "src"

# 🔴 의도적 트리 미나열 — 사유 필수. 신규 추가 시 정당화.
_ALLOWLIST: dict[str, str] = {}


def _tree_text() -> str:
    return _ARCH.read_text(encoding="utf-8")


def _packages() -> list[str]:
    return sorted(p.name for p in _SRC.iterdir() if p.is_dir() and not p.name.startswith("__"))


def _top_modules() -> list[str]:
    return sorted(p.stem for p in _SRC.glob("*.py") if p.stem != "__init__")


def missing_entries() -> list[str]:
    text = _tree_text()
    missing = []
    for pkg in _packages():
        if pkg in _ALLOWLIST:
            continue
        # 패키지는 `pkg/` 또는 `` `pkg` `` 형태로 등장해야 한다
        if f"{pkg}/" not in text and f"`{pkg}`" not in text:
            missing.append(f"src/{pkg}/ (패키지)")
    for mod in _top_modules():
        if mod in _ALLOWLIST:
            continue
        if f"{mod}.py" not in text:
            missing.append(f"src/{mod}.py (최상위 모듈)")
    return missing


def main() -> int:
    if not _ARCH.is_file():
        print(f"ℹ️  {_ARCH} 없음 — skip")
        return 0
    missing = missing_entries()
    if missing:
        print("❌ docs/architecture.md src/ 트리에 미등재된 항목:")
        for m in missing:
            print(f"   - {m}")
        print("→ docs/architecture.md 의 src/ 트리에 추가하거나, 의도적 생략이면")
        print("   scripts/check_architecture_tree_sync.py 의 _ALLOWLIST 에 사유와 함께 등재할 것.")
        print("   (CLAUDE.md 6-step ⑥ — architecture.md 는 src/ 트리 단일 출처)")
        return 1
    print(f"✅ docs/architecture.md src/ 트리 동기 — 패키지 {len(_packages())} + 모듈 {len(_top_modules())} 전 등재")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
