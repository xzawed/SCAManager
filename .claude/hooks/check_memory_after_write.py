#!/usr/bin/env python3
"""PostToolUse(Write|Edit|MultiEdit) — 메모리 파일을 고친 «그 순간» 역방향 가드를 돌려 보인다. 막지 않는다.

## 무엇을 닫는가 (#1746 K18 P2-32)

`scripts/check_memory_refs.py` 의 역방향 축(메모리 → 리포)은 세션 시작(조언)과 리포 커밋(pre-commit)에서만
돌았다. 메모리는 리포 밖이라 메모리만 고친 순간에는 아무것도 돌지 않았다 — 결함이 생기는 순간이 유일하게
조용한 순간이었다. 이 훅은 고친 파일이 이 리포의 메모리 디렉토리 안일 때만 그 축을 돌려, 처방 줄의 죽은
좌표 · 복사된 테스트 수 · 없는 머지 커밋을 바로 보인다.

## 🔴 이 훅이 «하지 못하는» 것

**막지 못한다.** PostToolUse 는 쓰기 «뒤» 에 불린다 — 보이게 할 뿐 되돌리지 않는다. Bash 로 쓴 메모리는 보지
않는다(Write|Edit|MultiEdit 만). 정방향 축(리포 문서 → 메모리 슬러그)은 리포 쪽 변경이라 pre-commit 이 본다.

Detection only, after the write: runs the reverse axis when the written file is inside this repo's memory dir.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def _make_stdout_safe() -> None:
    """Windows cp949 stdout 크래시 방지 — 관용구 복제(정책 16 최소 추상화)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure


def written_path(payload: object) -> str:
    """훅 입력에서 쓴 파일 경로 — 없거나 모양이 다르면 빈 문자열."""
    if not isinstance(payload, dict):
        return ""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    path = tool_input.get("file_path")
    return path if isinstance(path, str) else ""


def is_inside(path: str, directory: Path) -> bool:
    """`path` 가 `directory` 안인가 — 경로를 풀지 못하면 아니다(조용히 넘어간다)."""
    try:
        return Path(path).resolve().is_relative_to(directory.resolve())
    except (OSError, ValueError):
        return False


def build_message(found: list[str]) -> str:
    lines = [f"🔴 방금 고친 메모리의 «처방» 이 없는 자리 · 썩는 값을 가리킵니다 ({len(found)}건):"]
    lines += [f"   {line}" for line in found]
    lines += [
        "   살아 있는 좌표로 고치거나(백틱 = 살아 있는 좌표), 테스트 수는 원천을 가리키게 바꾸세요.",
        "   이 훅은 알리기만 합니다 — 쓰기를 막거나 되돌리지 않습니다.",
    ]
    return "\n".join(lines)


def main() -> int:
    _make_stdout_safe()
    try:
        payload = json.load(sys.stdin)
    except (ValueError, RecursionError):
        return 0  # 입력이 없거나 깨지면 무엇을 썼는지 모른다 — 조용히 넘어간다
    path = written_path(payload)
    if not path:
        return 0
    sys.path.insert(0, str(_ROOT))
    import scripts.check_memory_refs as refs  # noqa: PLC0415 — 메모리 경로일 때만 부른다

    memory_dir = refs.resolve_memory_dir(_ROOT)
    if memory_dir is None or not memory_dir.is_dir() or not is_inside(path, memory_dir):
        return 0
    found = refs.reverse_dangling(memory_dir, _ROOT)
    if found:
        message = build_message(found)
        print(json.dumps({"systemMessage": message,
                          "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}},
                         ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
