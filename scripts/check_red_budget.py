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

import hashlib
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
#
# ## 2026-08-14 확대 — 분모가 규칙보다 좁으면 '이주' 가 우회로가 된다
#
# 회고(`wf_2b615d5e-8c5`) P0-A 실측: `#1345` 가 *"무집행 0건 · 집행률 100%"* 를 선언한
# **바로 그 커밋**에서 `docs/process/**`(마커 22)와 `.claude/traps.md`(8)를 만들었는데,
# 두 표면 모두 이 목록 밖이라 카운터가 한 번도 읽지 않았다 — 그중 **무집행 27건**.
#
# 🔴 **가장 값싼 우회로는 기호 치환이 아니라 경로 이동이었다.** 🔴 줄을 `docs/process/`
# 로 옮겨 적으면 규칙은 독자에게 그대로 작동하는데 delta 축은 무집행 *감소*를 개선으로
# 채점한다. `deleted_not_renamed()` 분모 축도 같은 glob 만 보므로 두 층을 통째로
# 삭제해도 발화하지 않았다(뮤테이션 실증: 6파일 삭제 → EXIT 0).
#
# ⚠️ **이 확대로도 전수는 아니다.** 활성 문서 전체로 재면 계수 밖 마커가 여전히
# 약 475건 남는다(`docs/backlog.md` 92 · `docs/STATE.md` 41 · `docs/runbooks/**` 등).
# 그 표면들은 **원장·시점 기록**이라 규칙 층과 성격이 다르다 — 편입하면 이력 한 줄이
# 규칙으로 둔갑한다. 그래서 넓힌 것은 *"이 세션이 지시문으로 저술한 두 층"* 까지이고,
# 남은 범위 한계는 `CLAUDE.md` §3층 분리가 명시한다(숨기지 않는다).
#
# The denominator must cover every surface that *authors rules*; otherwise relocating a
# rule out of scope is the cheapest way to score an improvement.
SURFACE_GLOBS = (
    "CLAUDE.md",
    "AGENTS.md",
    ".claude/rules/*.md",
    ".claude/policies/*.md",
    ".claude/traps.md",       # 2026-08-14 편입 — 실패 클래스 층(지시문)
    "docs/process/*.md",      # 2026-08-14 편입 — 프로세스 층(지시문)
)

# **필수 규칙 마커 집합** — 독자에게 "빨강 = 반드시" 로 읽히는 표기 전부.
# 리터럴 집합으로 못박는다: 유도(예: 이모지 카테고리 조회)하면 원천을 비워도 초록이다.
# `has_marker()` docstring 에 이 집합이 왜 단일 문자가 아닌지와 무엇이 열려 있는지 적었다.
# ⚠️ ⚠/❌ 는 의도적으로 **제외** — 이 리포에서 각각 '한계 고지'·'나쁜 예시' 로 이미
#    자리잡은 표기라 필수 규칙으로 읽히지 않는다(실측 20/13 occurrence).
_RED_MARKERS = ("🔴", "🛑", "🟥", "⛔", "🚨", "🚫", "🔺", "‼", "🆘")

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

    ## 🔴 이 축이 닫지 **못하는** 것 (Grok claim-review `019ffadc` — 봉인 주장 금지)

    이 축은 **파일 경로**만 본다. 아래는 여전히 통과한다:

    | 우회 | 이 축 | delta 축 |
    |---|---|---|
    | 파일 삭제 · `git mv` · glob 밖 이동 | **차단** | 통과 |
    | **파일을 남기고 🔴 줄만 제거** | 통과 | 통과(줄어드니까) |
    | 파일을 0바이트로 비우기 | 통과 | 통과 |
    | 같은 PR 에서 `SURFACE_GLOBS` 축소 | 통과 | 통과 |

    🔴 **가장 값싼 잔여 우회는 "🔴 토큰을 지우고 파일은 남기는 것"** 이다 — 삭제와 경제적
    효과가 같은데 두 축 다 발화하지 않는다. 0바이트 비우기는
    `tests/unit/scripts/test_rules_and_index_coverage.py` 의 `paths:` 요구가 잡지만,
    `paths:` 를 남긴 껍데기는 잡지 못한다. `SURFACE_GLOBS` 축소는
    `test_surface_list_covers_every_rule_home` 이 glob 문자열을 pin 해 **리뷰에 노출**되지만
    기계 차단은 아니다.

    **그러므로 이 함수는 봉인을 주장하지 않는다** — 닫은 것은 *삭제* 한 클래스뿐이다.
    Path-only. Stripping the 🔴 tokens while keeping the file is the cheapest remaining bypass.
    """
    return missing_surfaces_from(surface_names(base_root), head_root)


def missing_surfaces_from(base_names: set[str], head_root: Path) -> list[str]:
    """`missing_surfaces` 의 집합-입력판 — base 를 이미 스냅숏으로 들고 있을 때 쓴다.

    base worktree 는 판정 전에 제거되므로(`baseline_unenforced` 의 finally), main() 은
    경로가 아니라 **집합**을 넘긴다. 두 함수가 같은 뺄셈을 쓰도록 여기 한 곳에 둔다.
    """
    return sorted(base_names - surface_names(head_root))


def base_blob(base_sha: str, name: str, root: Path) -> str:
    """base 시점 파일 내용. 못 읽으면 빈 문자열.

    rename 판정 전용이라 **실패가 곧 '삭제로 본다'** 가 된다(fail-closed) — 내용을
    확인하지 못하면 rename 이라고 우기지 못한다.
    """
    out = _run(["git", "show", f"{base_sha}:{name}"], root)
    return out.stdout if out.returncode == 0 else ""


def _digest(text: str) -> str:
    """줄바꿈 정규화 후 해시 — CRLF/LF 왕복이 rename 을 삭제로 오판하지 않게."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def deleted_not_renamed(
    missing: list[str], base_sha: str, head_root: Path, root: Path,
) -> list[str]:
    """사라진 표면 중 **rename 이 아닌 것**만 — 내용이 같은 파일이 남아 있으면 rename.

    🔴 왜 필요한가 (Grok claim-review `019ffadc` C2): 초판은 파일 **경로**만 뺐다.
    그래서 `git mv .claude/rules/services.md …` 같은 정상 rename 이 면제 경로 없이
    hard-block 됐고, docstring 이 처방한 *"같은 PR 에서 SURFACE_GLOBS 를 고쳐라"* 는
    **fiction** 이었다 — 그 상수는 glob 튜플이고 단위 테스트가 그 문자열을 pin 한다.
    실측: `git log --diff-filter=R -- .claude/rules/` 는 비어 있어 rename 이 아직
    없었지만, 없다는 것이 앞으로도 없다는 뜻은 아니다(가드 자살 예방 — 정책 17).

    A path-only diff would hard-block a legitimate `git mv`. Content hashing lets a
    rename through while a real deletion still fails.
    """
    if not missing:
        return []
    head_digests = {_digest(p.read_text(encoding="utf-8", errors="replace"))
                    for p in surfaces(head_root)}
    return [name for name in missing
            if _digest(base_blob(base_sha, name, root)) not in head_digests]


def has_marker(line: str) -> bool:
    """이 줄이 **필수 규칙 마커**를 달고 있는가 — 🔴 만이 아니다.

    ## 왜 집합인가 (2026-08-13 Grok claim-review `019ffb93` 반례 (e))

    초판은 `"🔴" in line` 이었다. 적대 검토가 `.claude/rules/` 에 **🛑** 로 표시한
    집행자 없는 필수 규칙 1줄을 넣었고 스위트는 **25 passed** 였다 — 독자에게는
    빨간 필수 마커로 보이는데 카운터에는 존재하지 않는다. *"무집행 🔴 = 0"* 이
    참인 채로 무집행 필수 규칙을 얼마든지 쌓을 수 있었다.

    반례 하나를 막는 것으로 끝내지 않는다(AGENTS.md §불변식 2-b) — **클래스는
    '빨강 계열 필수 마커 위장'** 이므로 그 클래스를 집합으로 닫는다.

    ⚠️ **여전히 열려 있는 것**: 이 집합 밖의 임의 기호(예: `**[필수]**`, `<!-- red -->`,
    새 이모지)는 통과한다. 열거는 원리적으로 완결되지 않는다 — 이 축이 끝내는 것은
    *"현행 리포에서 빨강으로 읽히는 표기"* 뿐이다.

    Look-alike red markers used to be invisible to the counter; the class is closed
    as a set, not as a single-instance patch. Arbitrary new notations remain open.
    """
    return any(m in line for m in _RED_MARKERS)


_FENCE = re.compile(r"^\s*(```|~~~)")
_CODE_SPAN = re.compile(r"`[^`]*`")


def _strip_code(text: str) -> str:
    """코드 스팬·펜스 안의 마커는 **인용**이지 규칙 표시가 아니다 — 계수에서 뺀다.

    ## 왜 (2026-08-14 회고 P0-A 정리 중 실측)

    `SURFACE_GLOBS` 를 넓히자 무집행 27건이 드러났는데, 그중 다수가 **마커를 설명하는
    문장**이었다: `"무집행 🔴 이 늘었는가"` · `| 🔴 규칙 | 307건 |` ·
    ```py 블록 안의 `# 🔴 예외 없음` 주석```. 이것들을 규칙으로 세면 저자가
    **마커 제도 자체를 문서로 설명하지 못하게** 된다 — traps B5(산문 가드는 양방향으로
    틀린다)와 메모리 `feedback-prose-guard-both-ways` 의 *"인용 면제 필수(정정 기록이
    막힌다)"* 가 정확히 이 형태다. 같은 취지의 선례가 이미 있다: `_EXEMPT` 정규식의
    `(?![\\`'\"])` 인용 배제.

    ⚠️ **대가**: 규칙을 코드 펜스 안에 숨기면 계수를 피한다. 다만 펜스 안은 **코드로
    렌더링**되므로 독자에게 빨간 필수 규칙으로 보이지 않는다 — 이 게이트가 재는 것은
    *"독자에게 필수로 보이는데 기계가 안 지키는 것"* 이고, 그 축은 유지된다.

    Markers inside code spans/fences are mentions, not marks; counting them would stop
    authors from documenting the marker system itself.
    """
    out, in_fence = [], False
    for line in text.split("\n"):
        if _FENCE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else _CODE_SPAN.sub("", line))
    return "\n".join(out)


def rule_blocks(text: str) -> list[str]:
    """필수 마커 줄 + 뒤따르는 연속 줄 = 규칙 블록.

    🔴 **인용 배제는 마커 탐지에만 적용하고 블록 본문은 원문을 돌려준다.**
    집행자 이름은 관례상 백틱 안에 적힌다(`` `scripts/check_x.py` ``) — 스트립한
    텍스트를 그대로 돌려주면 `has_enforcer()` 가 **모든 집행자를 못 보게** 된다
    (2026-08-14 자초 실측: 무집행 0 → 118). 탐지용 사본과 반환용 원문을 분리한다.
    """
    raw = text.split("\n")
    probe = _strip_code(text).split("\n")   # 마커 탐지 전용 — 인용/코드 제거본
    out: list[str] = []
    for i, line in enumerate(probe):
        if not has_marker(line):
            continue
        buf = [raw[i]]
        for j in range(i + 1, len(probe)):
            if not probe[j].strip() or has_marker(probe[j]):
                break
            buf.append(raw[j])
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
        # 🔴 **비율을 인쇄하지 않는다** (2026-08-14 사용자 결정 — 회고 P0-A 후속).
        #    이 리포는 «28% → 100%» 에 두 번 당했고 두 번 다 **분자가 아니라 분모가
        #    움직인 것**이었다: 한 번은 무집행 221개의 마커를 떼서(분모 307→92),
        #    한 번은 규칙을 계측 표면 밖으로 옮겨서. 비율은 그 이동을 **개선처럼**
        #    보이게 하는 성질이 있다 — 절대값과 분모를 함께 적으면 그 성질이 사라진다.
        #    Ratios hide denominator moves; print absolutes and name the surfaces.
        print(f"현재: 무집행 **{current}건** · 집행자 동반 {total - current}건 "
              f"(계측 표면 {len(surfaces(_ROOT))}개 위 마커 {total}건)")
        # 🔴 **이 exit 0 은 "통과" 가 아니라 "안 쟀음" 이다** (2026-08-13 Grok 반례 (d)).
        #    적대 검토가 `.claude/rules/i18n.md`(🔴 표면 하나)를 통째로 삭제한 뒤 이 스크립트를
        #    env 없이 돌렸고, 출력은 `100.0% · 무집행 0건` + EXIT 0 이었다 — 분모가 88→85 로
        #    줄어든 것이 **개선으로 읽혔다**. 분모 축(`deleted_not_renamed`)은 PR_BASE_SHA
        #    분기에만 살고, 로컬 실행은 그 축을 **한 번도 돌리지 않는다**.
        #    배너가 봉인처럼 읽히지 않게 하는 것이 로컬에서 할 수 있는 전부다.
        #    Local runs never evaluate the denominator axis; say so instead of printing green.
        print("\n⏭️  PR 환경변수(PR_BASE_SHA)가 없다 — **두 축을 안 쟀다**:")
        print("     · 증감 판정 (무집행 🔴 이 늘었는가)")
        print("     · 🔴 **분모 축** (🔴 표면 파일이 사라졌는가) — 표면을 지우면 위 무집행 수는")
        print("       줄어든다. 이 실행은 그것을 구별하지 못한다. 판정은 CI 몫이다.")
        return 0

    current, total = unenforced_count(_ROOT)
    snapshot = baseline_unenforced(base_sha, _ROOT)
    if snapshot is None:
        print("🔴 base 시점을 산출하지 못했다 — **판정 불가**(fail-closed).", file=sys.stderr)
        return 1
    base, base_surfaces = snapshot

    delta = current - base
    print(f"무집행 🔴 — base {base} → head {current} (Δ {delta:+d})")
    # 비율 미인쇄 — 위 로컬 분기와 같은 이유(분모 이동을 개선으로 보이게 한다).
    print(f"집행자 동반 {total - current}건 · 계측 표면 {len(surfaces(_ROOT))}개 위 마커 {total}건")

    # 🔴 **분모 축 — delta 보다 먼저 본다** (2026-08-13 회고 P0).
    #    표면 파일이 사라지면 무집행 🔴 이 줄어 delta 가 음수가 되고, delta 만 보는
    #    판정은 그것을 '개선' 으로 인쇄한다(실측: guards.md+docs.md 삭제 → Δ −50 · EXIT 0).
    #    🔴 `red-budget-exempt:` 로 면제하지 **않는다** — 그 마커는 *증가*를 명시화하는
    #    장치이고, 삭제까지 덮으면 "가드를 지우고 한 줄 적으면 끝" 이 되어 축이 무의미해진다.
    #    표면을 정말로 없애야 한다면 SURFACE_GLOBS 를 같은 PR 에서 고쳐 **리뷰에 노출**한다.
    #    Deletion is checked before delta and is deliberately not exemptible.
    gone = deleted_not_renamed(
        missing_surfaces_from(base_surfaces, _ROOT), base_sha, _ROOT, _ROOT)
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
        # 🔴 **실패 메시지에도 비율을 쓰지 않는다** (2026-08-14 Grok `019fffde` CLAIM 2 BROKEN).
        #    stdout 두 분기만 고치고 이 stderr 를 남겨 뒀더니 `23.1%`·`100%`·`0%` 가 그대로
        #    인쇄됐다 — 그리고 **사람이 읽는 자리는 실패 로그**다. 절대값이 더 강한 근거다.
        "   이 저장소의 실측(2026-08-08): 🔴 290건 중 집행자 동반은 **67건뿐**이었다.\n"
        "   42회 발화에 준수 0회인 정책이 있고, 발화만 있고 이행 기록이 없는 의무가 있다.\n"
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
