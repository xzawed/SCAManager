#!/usr/bin/env python3
"""회고 범위를 **기계 산출**한다 — 손으로 적지 않는다.

## 왜 필요한가 (2026-07-19 회고 P0)

정책 8 진화 (5)는 회고 범위를 *"직전 정식 회고 이후 머지 PR **+ 본 세션 산출물 전체**"* 로
규정한다(`CLAUDE.md`). 그런데 그 정책을 신설한 세션이 **첫 적용에서 자기 산출물 2건을
누락**했다 — 범위를 손으로 `#1108~#1129` 라 적었고, 회고 착수 직전에 머지된 `#1130`·`#1131`
이 빠졌다. 정책이 명명한 시나리오("가장 검증이 덜 된 코드가 회고를 피해간다")가 정책 신설
당일 그대로 발생했다.

🔴 **손으로 적는 한 항상 '진입 직전 머지분'이 빠진다.** 사람이 범위를 적는 시점과 회고가
시작되는 시점 사이에 머지가 일어나기 때문이고, 이건 주의력으로 못 막는다.

The retro scope must be computed, not typed: whatever is merged between writing the scope and
starting the run is silently excluded — exactly the case the policy exists to prevent.

## 사용법 / Usage

    python scripts/retro_scope.py            # 사람이 읽는 요약
    python scripts/retro_scope.py --json     # 워크플로 args 에 넣을 JSON

경계는 `check_retro_cadence` 와 **같은 함수**로 판정한다(`newest_retro` · `_boundary_commit`)
— 두 곳이 다른 회고를 최신으로 고르면 카운터와 회고 범위가 어긋난다.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# 🔴 카덴스 카운터와 **동일 판정 로직 공유** — 각자 구현하면 최신 회고가 갈린다.
# Share the counter's selection logic; duplicating it would let the two disagree.
from check_retro_cadence import (  # noqa: E402  # pylint: disable=wrong-import-position
    _RETRO_NAME,
    newest_retro,
)

_ROOT = Path(__file__).resolve().parents[1]
_REPORTS = _ROOT / "docs" / "_archive" / "reports"


def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지/한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji/Korean print crash on Windows (UTF-8, replace on miss).

    🔴 standalone 실행이라 공유 헬퍼를 import 하지 않고 관용구를 복제한다(정책 16 최소 추상화).
    누락 방지는 `tests/unit/scripts/test_stdout_encoding_guard.py` 가 담당.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure


def _git(args: list[str]) -> str:
    """git 호출 — 실패 시 빈 문자열(호출자가 판단). encoding 명시 의무(cp949 오디코딩 방지)."""
    try:
        r = subprocess.run(
            ["git", *args], cwd=_ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", check=False,
        )
        return r.stdout if r.returncode == 0 else ""
    except OSError:
        return ""


def boundary_commit(retro_filename: str) -> str | None:
    """회고 리포트가 **추가된** 커밋 = 범위 경계. 없으면 None.
    The commit that ADDED the retro report is the range boundary."""
    path = f"docs/_archive/reports/{retro_filename}"
    sha = _git(["log", "--diff-filter=A", "--format=%H", "-1", "--", path]).strip()
    return sha or None


def merged_prs(boundary: str) -> list[int]:
    """경계 이후 HEAD 까지의 squash-merge PR 번호 — **오름차순**.

    🔴 `HEAD` 를 그 자리에서 읽는 것이 핵심이다. 사람이 적은 목록은 작성 시점에 고정되지만
    이 함수는 **호출 시점**의 HEAD 를 본다.
    Reads HEAD at call time — a hand-written list freezes at authoring time.
    """
    out = _git(["log", "--format=%s", f"{boundary}..HEAD"])
    nums = []
    for line in out.splitlines():
        # squash 머지 제목 끝의 (#NNNN)
        if (i := line.rfind("(#")) != -1 and line.rstrip().endswith(")"):
            tail = line[i + 2:].rstrip(")").strip()
            if tail.isdigit():
                nums.append(int(tail))
    return sorted(set(nums))


def compute() -> dict:
    """범위 산출 결과 dict — 리포트 부재 등 실패도 사유와 함께 담는다."""
    if not _REPORTS.is_dir():
        return {"ok": False, "reason": "reports dir 없음 / no reports dir"}
    newest = newest_retro([p.name for p in _REPORTS.glob("*.md") if _RETRO_NAME.match(p.name)])
    if not newest:
        return {"ok": False, "reason": "정식 회고 리포트 없음 / no formal retro report"}
    boundary = boundary_commit(newest)
    if not boundary:
        return {"ok": False, "reason": f"경계 커밋 판정 실패 / no add-commit for {newest}"}
    prs = merged_prs(boundary)
    head = _git(["rev-parse", "--short", "HEAD"]).strip()
    return {
        "ok": True,
        "prev_retro": newest,
        "boundary": boundary[:7],
        "head": head,
        "pr_count": len(prs),
        "prs": prs,
        "range": f"#{prs[0]}~#{prs[-1]}" if prs else "(없음)",
    }


def main() -> int:
    """CLI 진입점 — 사람이 읽는 요약 또는 `--json` 출력."""
    _make_stdout_safe()
    ap = argparse.ArgumentParser(description="회고 범위 기계 산출 / compute retro scope")
    ap.add_argument("--json", action="store_true", help="JSON 출력 (워크플로 args 용)")
    args = ap.parse_args()

    r = compute()
    if args.json:
        print(json.dumps(r, ensure_ascii=False))
        return 0 if r["ok"] else 1

    if not r["ok"]:
        print(f"❌ 범위 산출 실패: {r['reason']}")
        return 1
    print("회고 범위 (기계 산출 — 손으로 적지 말 것)")
    print(f"  직전 정식 회고 : {r['prev_retro']}")
    print(f"  경계 커밋      : {r['boundary']}  → HEAD {r['head']}")
    print(f"  머지 PR        : {r['pr_count']}건  {r['range']}")
    print(f"  전체           : {', '.join('#' + str(n) for n in r['prs'])}")
    print()
    print("🔴 회고 착수 **직전에** 다시 실행할 것 — 그 사이 머지분이 빠지는 것이 P0 의 기전이었다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
