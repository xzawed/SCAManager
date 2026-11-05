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
워크트리 세션은 메모리 디렉토리를 그 체크아웃 경로로 유도하므로(`CLAUDE_PROJECT_MEMORY_DIR` 가 없으면) 조용하다.

Detection only, after the write: runs the reverse axis when the written file is inside this repo's memory dir.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PROJECTS_ROOT = Path.home() / ".claude" / "projects"


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


def read_payload() -> object:
    """stdin 을 **바이트로 읽어 UTF-8 로 직접 디코드**한다 — `doc_review_gate.read_payload` 와 같은 관용구.

    🔴 `json.load(sys.stdin)` 를 쓰면 안 된다 — 실훅 자식 프로세스의 stdin 은 cp949 라, 한글이 든 메모리 경로가
    깨져 «메모리 밖» 으로 읽히고 이 훅이 조용히 죽었다(적대 패스 실측). 깨진 입력이면 None.
    """
    try:
        raw = getattr(sys.stdin, "buffer", sys.stdin).read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        return json.loads(raw)
    except (ValueError, RecursionError):
        return None


def may_be_memory(path: str) -> bool:
    """메모리일 수 있는 경로인가 — 아니면 검사 모듈을 아예 불러오지 않는다(모듈이 깨져 있어도 다른 쓰기는 조용하다)."""
    env = os.environ.get("CLAUDE_PROJECT_MEMORY_DIR")
    return is_inside(path, Path(env)) if env else is_inside(path, _PROJECTS_ROOT)


def build_message(found: list[str]) -> str:
    lines = [f"🔴 메모리의 «처방» 이 없는 자리 · 썩는 값을 가리킵니다 (메모리 전체 기준 {len(found)}건):"]
    lines += [f"   {line}" for line in found]
    lines += [
        "   살아 있는 좌표로 고치거나(백틱 = 살아 있는 좌표), 테스트 수는 원천을 가리키게 바꾸세요.",
        "   이 훅은 알리기만 합니다 — 쓰기를 막거나 되돌리지 않습니다.",
    ]
    return "\n".join(lines)


def _emit(message: str) -> None:
    print(json.dumps({"systemMessage": message,
                      "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": message}},
                     ensure_ascii=True))


def main() -> int:
    _make_stdout_safe()
    path = written_path(read_payload())
    if not path or not may_be_memory(path):
        return 0
    # 🔴 검사가 무엇으로 넘어져도 이 훅은 exit 0 이다 — 대신 못 잰 것을 한 줄로 보인다(조용해지지 않는다).
    #    Whatever the checker raises, exit 0 and say it could not check.
    try:
        sys.path.insert(0, str(_ROOT))
        import scripts.check_memory_refs as refs  # noqa: PLC0415 — 메모리일 수 있는 경로일 때만 부른다

        memory_dir = refs.resolve_memory_dir(_ROOT)
        if memory_dir is None or not memory_dir.is_dir() or not is_inside(path, memory_dir):
            return 0
        found = refs.reverse_dangling(memory_dir, _ROOT)
    except Exception as exc:  # noqa: BLE001 — 조언 훅은 어떤 실패로도 쓰기 흐름을 시끄럽게 깨지 않는다
        _emit(f"⚠️ 메모리 역방향 가드를 돌리지 못했다 — {type(exc).__name__}: {str(exc)[:200]}")
        return 0
    if found:
        _emit(build_message(found))
    return 0


if __name__ == "__main__":
    sys.exit(main())
