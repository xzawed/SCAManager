#!/usr/bin/env python3
"""🔴 예산제 — **집행자 없는 🔴 규칙이 늘어나면 실패** (P4).

## 왜 (2026-08-08 진단)

사용자 관찰 *"규칙이 반복 발화되는데 지켜지지 않는다"* 는 실측으로 옳았다.
그런데 원인은 **총량이 아니라 집행 비율**이다:

| 축 | 값 |
|---|---|
| 🔴 규칙(줄 기준) | **290** |
| 그중 집행자 동반 | **67 (23.1%)** |
| **무집행** | **223** |
| 30커밋당 🔴 증가율 | **+17%** |

실측 준수율이 **0/42**(정책 13) · **발화율 100% / 이행률 0%**(R43)인 규칙이 있다.
규칙이 도달해도 지켜지지 않는다 — 그러니 규칙을 더 쓰는 것은 처방이 아니다.

🔴 **그렇다고 문서를 줄이는 것도 아니다.** 두 번 시도해 두 번 다 순손실이었다
(`#1296` CLAUDE.md 424→196줄 → Grok BROKEN: 행동 규칙 8건 소실 /
R54 "5지점 → 1줄 파생" → 틀린 값 하나가 4지점 자동 전파 → 이 세션의 사고 그 자체).

그래서 이 게이트는 **바이트를 재지 않는다.** 재는 것은 하나다:
> **집행자 없는 🔴 이 이 PR 에서 늘었는가?**

늘리는 것 자체는 막지 않는다 — `red-budget-exempt:` 로 **명시**하면 통과하되 계수된다.
조용한 증가만 막는다.

## 산식 (결정론적 — 재현 가능해야 한다)

- 대상 표면: `CLAUDE.md` · `AGENTS.md` · `.claude/rules/*.md` · `.claude/policies/*.md`
- **🔴 규칙 1건 = 🔴 를 포함한 줄 1개** (문단이 아니라 줄 — 재현 가능한 최소 단위)
- 규칙 블록 = 그 줄 + 뒤따르는 연속 줄(빈 줄 또는 다음 🔴 줄 전까지)
- 블록 안에 `tests/**/test_*.py` · `scripts/check_*.py` · `.claude/hooks/*.py` 형태의
  이름이 있고 **그 파일이 실재**하면 '집행자 동반'
- 🔴 파일명이 있는데 실재하지 않으면 **집행자로 치지 않는다**(dangling)

⚠️ **이것은 프록시다.** 규칙 블록에 가드 이름을 적는 것과 그 가드가 그 규칙을 실제로
집행하는 것은 다르다. 이 게이트가 재는 것은 *"저자가 집행자를 함께 만들었는가"* 라는
**습관**이지 집행의 정확성이 아니다. 그 한계를 숨기지 않는다.

Red-budget gate: fails when a PR increases the number of 🔴 rules that have no machine enforcer.
Adding them is allowed — but only explicitly, via a counted marker.
"""
from __future__ import annotations

import os
import re
import subprocess  # nosec B404
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[1]

# 🔴 PR 본문은 **단일 리더**를 통해서만 읽는다 — 원문을 정규식에 넘기면 HTML 주석 안
# 마커가 "리뷰어 비가시 + 게이트 통과" 를 성립시킨다(회고 N-P0-1 · backlog R20 결함 1).
# 스크립트 간 공유 관용구는 `retro_scope.py:34` 선례를 따른다(standalone 실행이라
# sys.path 조작이 필요하다). 단일성 강제: `tests/unit/scripts/test_pr_body_single_reader.py`.
# Read the PR body only through the single hardened reader; see the guard test.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_claim_review_trace import (  # noqa: E402  # pylint: disable=wrong-import-position
    read_pr_body,
)


# 🔴 규칙이 사는 표면 — 리터럴로 못박는다(유도하면 비워도 초록이다).
SURFACE_GLOBS = ("CLAUDE.md", "AGENTS.md", ".claude/rules/*.md", ".claude/policies/*.md")

# 집행자로 인정하는 이름 형태.
_ENFORCER = re.compile(
    r"(?:tests/[\w/]*test_\w+\.py|scripts/check_\w+\.py|\.claude/hooks/\w+\.py"
    r"|test_\w+\.py|check_\w+\.py)"
)

_EXEMPT = re.compile(
    r"^[ \t]*(?![`'\"])red-budget-exempt\s*:\s*\S.{15,}", re.MULTILINE)
_LINE_BREAKS = re.compile(r"\s+")


def surfaces(root: Path) -> list[Path]:
    out: list[Path] = []
    for g in SURFACE_GLOBS:
        out.extend(sorted(root.glob(g)))
    return [p for p in out if p.is_file()]


def surface_names(root: Path) -> set[str]:
    """표면 파일의 **루트 상대 경로** 집합.

    🔴 절대 경로면 base(임시 worktree)와 head(리포)가 영원히 다른 집합이 되어
    대조가 *"전부 사라졌다"* 로 오작동한다. POSIX 구분자로 정규화한다.
    Relative, POSIX-normalized — absolute paths would never compare across worktrees.
    """
    return {p.relative_to(root).as_posix() for p in surfaces(root)}


def missing_surfaces(base_root: Path, head_root: Path) -> list[str]:
    """base 에 있었는데 head 에서 사라진 표면 — 신규 추가는 결함이 아니다.

    ## 왜 이 축이 따로 필요한가 (2026-08-13 회고 P0, 실경로 재현)

    이 게이트의 판정은 *"무집행 🔴 이 늘었는가"* 라는 **delta** 하나였다. 그런데 delta 는
    **분모가 사라지는 경우를 원리적으로 못 본다** — `.claude/rules/guards.md`(49 🔴)와
    `docs.md` 를 삭제하면 무집행 🔴 이 **221 → 171 (Δ −50)** 이 되고 게이트는
    `✅ 무집행 🔴 이 늘지 않았다` 로 **EXIT 0** 을 냈다.

    즉 **가드 저술 규칙을 통째로 지우는 것이 이 리포에서 가장 값싼 '집행률 개선' 수단**
    이었다. 규칙을 없애 비율을 올리는 것은 이 게이트가 재려던 것의 정반대다.

    Deleting the rules that author guards *lowered* the unenforced count, so a delta-only
    verdict scored it as an improvement. This axis watches the denominator itself.
    """
    return missing_surfaces_from(surface_names(base_root), head_root)


def missing_surfaces_from(base_names: set[str], head_root: Path) -> list[str]:
    """`missing_surfaces` 의 집합-입력판 — base 를 이미 스냅숏으로 들고 있을 때 쓴다.

    base worktree 는 판정 전에 제거되므로(`baseline_unenforced` 의 finally), main() 은
    경로가 아니라 **집합**을 넘긴다. 두 함수가 같은 뺄셈을 쓰도록 여기 한 곳에 둔다.
    """
    return sorted(base_names - surface_names(head_root))


def rule_blocks(text: str) -> list[str]:
    """🔴 줄 + 뒤따르는 연속 줄 = 규칙 블록."""
    lines = text.split("\n")
    out: list[str] = []
    for i, line in enumerate(lines):
        if "🔴" not in line:
            continue
        buf = [line]
        for j in range(i + 1, len(lines)):
            nxt = lines[j]
            if not nxt.strip() or "🔴" in nxt:
                break
            buf.append(nxt)
        out.append("\n".join(buf))
    return out


def has_enforcer(block: str, root: Path) -> bool:
    """블록이 **실재하는** 가드 파일을 가리키는가. dangling 은 집행자가 아니다."""
    for name in set(_ENFORCER.findall(block)):
        if "/" in name:
            if (root / name).exists():
                return True
        elif any(root.rglob(name)):
            return True
    return False


def unenforced_count(root: Path) -> tuple[int, int]:
    """(무집행 🔴 수, 전체 🔴 수)."""
    total = enforced = 0
    for path in surfaces(root):
        for blk in rule_blocks(path.read_text(encoding="utf-8", errors="replace")):
            total += 1
            if has_enforcer(blk, root):
                enforced += 1
    return total - enforced, total


def _run(args: list[str], cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(  # nosec B603
        args, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout, check=False,
    )


def _append_step_summary(markdown: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(markdown)
    except OSError:
        pass  # 기록 실패가 판정을 바꾸면 안 된다 / logging must never change the verdict


def baseline_unenforced(base_sha: str, root: Path) -> tuple[int, set[str]] | None:
    """base 시점의 `(무집행 🔴 수, 표면 파일 집합)`. 판정 불가면 None.

    🔴 base 를 **worktree 로 꺼내서** 센다 — `git show` 로 파일만 읽으면
    `has_enforcer` 의 '파일 실재' 판정이 **현재 트리**를 보게 되어, 이 PR 이 추가한
    가드가 base 계산에도 반영된다(base 를 과대평가 → 증가를 놓친다).
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        wt = Path(tmp) / "base"
        add = _run(["git", "worktree", "add", "--detach", str(wt), base_sha], root, timeout=600)
        if add.returncode != 0:
            return None
        try:
            count, _total = unenforced_count(wt)
            # 🔴 표면 삭제 축도 **같은 worktree 에서** 얻는다 — base 를 두 번 꺼내면
            #    두 스냅숏이 갈릴 수 있고, worktree 생성 비용도 두 배가 된다.
            #    Same worktree serves both axes; two checkouts could diverge.
            return count, surface_names(wt)
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt)], root, timeout=600)


def main() -> int:
    print("=== 🔴 예산제 / Red-Budget Gate ===\n")
    base_sha = os.environ.get("PR_BASE_SHA", "")
    if not base_sha:
        current, total = unenforced_count(_ROOT)
        print(f"현재: 🔴 {total}건 · 집행자 동반 {total - current}건 "
              f"({(total - current) / total * 100:.1f}%) · **무집행 {current}건**")
        print("⏭️  PR 환경변수(PR_BASE_SHA)가 없다 — 증감 판정은 CI 몫이다.")
        return 0

    current, total = unenforced_count(_ROOT)
    snapshot = baseline_unenforced(base_sha, _ROOT)
    if snapshot is None:
        print("🔴 base 시점을 산출하지 못했다 — **판정 불가**(fail-closed).", file=sys.stderr)
        return 1
    base, base_surfaces = snapshot

    delta = current - base
    print(f"무집행 🔴 — base {base} → head {current} (Δ {delta:+d})")
    print(f"전체 🔴 {total}건 · 집행자 동반 {total - current}건 "
          f"({(total - current) / total * 100:.1f}%)")

    # 🔴 **분모 축 — delta 보다 먼저 본다** (2026-08-13 회고 P0).
    #    표면 파일이 사라지면 무집행 🔴 이 줄어 delta 가 음수가 되고, delta 만 보는
    #    판정은 그것을 '개선' 으로 인쇄한다(실측: guards.md+docs.md 삭제 → Δ −50 · EXIT 0).
    #    🔴 `red-budget-exempt:` 로 면제하지 **않는다** — 그 마커는 *증가*를 명시화하는
    #    장치이고, 삭제까지 덮으면 "가드를 지우고 한 줄 적으면 끝" 이 되어 축이 무의미해진다.
    #    표면을 정말로 없애야 한다면 SURFACE_GLOBS 를 같은 PR 에서 고쳐 **리뷰에 노출**한다.
    #    Deletion is checked before delta and is deliberately not exemptible.
    gone = missing_surfaces_from(base_surfaces, _ROOT)
    if gone:
        print(f"\n🔴 **🔴 규칙이 사는 표면이 {len(gone)}개 사라졌다** — 삭제는 개선이 아니다.")
        for name in gone:
            print(f"   · {name}")
        print("\n   무집행 🔴 이 줄어든 것은 규칙을 지켰기 때문이 아니라 **규칙을 지웠기 때문**이다.")
        print("   의도한 삭제라면 같은 PR 에서 SURFACE_GLOBS 를 고쳐 리뷰에 노출할 것.")
        _append_step_summary(
            f"- 🔴 **표면 삭제 {len(gone)}건** — {', '.join(gone)}\n")
        return 1

    if delta <= 0:
        print("\n✅ 무집행 🔴 이 늘지 않았다.")
        return 0

    exemption = _EXEMPT.search(read_pr_body())
    if exemption:
        reason = _LINE_BREAKS.sub(" ", exemption.group(0).strip())[:200]
        print(f"::notice title=red-budget exempted::{reason}")
        _append_step_summary(
            f"- ⏭️ **🔴 예산 면제** — 무집행 🔴 {delta:+d}\n  - 사유: {reason}\n")
        print(f"\n⏭️  면제 마커 확인 — 무집행 🔴 {delta:+d} 통과")
        return 0

    print(
        f"\n🔴 **집행자 없는 🔴 규칙이 {delta}건 늘었다.**\n"
        "   이 저장소의 실측: 🔴 290건 중 집행자 동반은 23.1% 뿐이고,\n"
        "   실측 준수율 0/42 인 정책과 '발화율 100% / 이행률 0%' 인 의무가 존재한다.\n"
        "   규칙을 더 쓰는 것은 처방이 아니다 — **같은 PR 에서 그것을 집행하는 가드를 만들 것.**\n"
        "\n   해결 / Fix:\n"
        "     · 규칙 블록에 그 규칙을 집행하는 테스트/스크립트 이름을 적고 그 파일을 만든다\n"
        "       (예: `tests/unit/scripts/test_x.py` · `scripts/check_x.py`)\n"
        "     · 지금은 집행할 수 없는 규칙이면 PR 본문에 적는다:\n"
        "         red-budget-exempt: <왜 지금 집행할 수 없는가 — 16자 이상>\n"
        "       🔴 그 사용은 job summary 에 계수된다.\n"
        "\n   ⚠️ 이 게이트는 **프록시**다 — 블록에 가드 이름이 있는지를 볼 뿐,\n"
        "      그 가드가 그 규칙을 실제로 집행하는지는 판정하지 않는다.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
