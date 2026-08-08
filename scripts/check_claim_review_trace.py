"""정책 19 집행면 — **seal 주장에 claim-review 흔적을 강제**한다.

## 왜 만드나 (2026-07-29 실측 사고)

정책 19("실질 작업마다 Grok CLAIM-REVIEW")는 **산문 의무뿐이었다.** 그 결과:

- `docs/backlog.md` **R2**: 창 42 커밋 중 **26건이 "봉인/fail-closed" 주장인데 Grok 흔적 0**.
  직전 회고 P1 의 즉시 재발.
- 2026-07-29 세션: Claude 가 분석 단계에 claim-review 를 1회 돌린 뒤, **정작 자기가 만든 가드**를
  "봉인 · 양방향 강제 · 뮤테이션 8/8 red" 로 단언하며 PR 2건을 냈다. 뒤늦게 돌린 claim-review 가
  그 두 주장을 **모두 BROKEN** 으로 판정했다(설정 파싱이 손실 투영이라 우회 4종 통과).

🔴 **핵심**: 트리거 단어를 **자기가 타이핑하고도** 호출하지 않았다. 즉 "규칙을 못 찾음"(문서량)이
아니라 **집행면이 없어 자기보고로 끝나는 구조**가 원인이다. 정책 8(회고 카덴스)·owed 원장은 이미
같은 이유로 산문 → SessionStart 훅으로 승격됐다. 이 스크립트는 정책 19 의 같은 승격이다.

## 무엇을 강제하나

PR 제목·본문·PR 범위 커밋 메시지에 **seal 주장**(봉인·fail-closed·완결·유출 0·뮤테이션 N/N red
등)이 있으면, 같은 텍스트에 **구조화된 claim-review 흔적**을 요구한다. 없으면 **exit 1**.

## 🔴 이 가드가 잡지 못하는 것 (정직 기준 — Grok 이 명시한 한계)

정적 검사는 **흔적의 존재/형태**만 볼 수 있다. 아래는 **원리적으로 못 잡는다**:

1. **위조** — 저자가 Grok 을 돌리지 않고 섹션만 손으로 채우는 것. 실행 여부·판정의 진위는
   정적으로 검증 불가하다.
2. **주장의 의미적 진실** — HOLDS 라 적힌 판정이 실제로 참인지. (저장소는 이미 "fail-open 은
   semantic 이라 완전 자동 탐지 불가" 를 `AGENTS.md` 에 확정해 두었다.)
3. **우회 어휘** — "강화했다 · 틈을 막았다" 처럼 트리거 어휘를 피한 표현.
4. **PR 밖 주장** — 대화에서만 한 주장은 이 표면에 오지 않는다.

즉 이 가드는 **"주장 + 흔적 0 + CI 초록" 이라는 무임승차를 끝낼 뿐**, claim-review 의 품질이나
진위를 보증하지 않는다. 그 이상을 주장하면 이 파일 자체가 새 observer-lie 가 된다.

Policy-19 enforcement: PRs asserting a seal must carry a structured claim-review trace. It cannot
detect forged traces, semantic truth, reworded claims, or claims made outside the PR — it only ends
the "assert a seal, show no trace, stay green" free ride.
"""
from __future__ import annotations

import os
import re
import subprocess  # nosec B404
import sys

# seal 주장 어휘 — "이 변경이 어떤 실패 가능성을 닫았다" 고 단언하는 표현.
# 🔴 어휘 목록은 완전하지 않다(위 §한계 3). 넓히면 오탐이 늘고 좁히면 우회가 는다.
# seal-claim lexicon; deliberately incomplete (see limitation 3 above).
_SEAL_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"봉인", "봉인"),
    (r"완결", "완결"),
    (r"fail[-\s]?closed", "fail-closed"),
    (r"\bseal(ed|ing)?\b", "seal"),
    (r"유출\s*(0|없)", "유출 0"),
    # N/N · N of N · "전부 red" 등 변형 포함 (Grok 적발: `mutation 7 of 7 red` 가 통과했다)
    (r"(뮤테이션|mutation)\s*\d+\s*(/|of|중)\s*\d+\s*red", "뮤테이션 N/N red"),
    (r"(뮤테이션|mutation)\s*(전부|모두|all)\s*red", "뮤테이션 전부 red"),
    # 단수형 카운트 관용구 — `뮤테이션 6건 red`·`뮤테이션 5종 red` (backlog R20: STATE 세션13
    # 서사가 실제로 쓴 자기 관용구인데 위 두 패턴 어디에도 안 잡혔다). red 동반이 판정선 —
    # `뮤테이션 6건 추가` 같은 평범한 개수 서술은 트리거하지 않는다(오탐 방지, 정책 17).
    # Singular-count idiom this repo actually writes; `red` is required so plain counts
    # ("added 6 mutations") never trigger.
    (r"(뮤테이션|mutation)\s*\d+\s*(건|종)\s*(전부|모두)?\s*red", "뮤테이션 N건 red"),
    (r"\bHOLDS\b", "HOLDS"),
    (r"재발\s*(불가|차단|봉쇄)", "재발 불가"),
    (r"구조적으로\s*(불가능|막)", "구조적으로 불가능"),
)

# claim-review 흔적 — 헤딩 + 필수 필드. 🔴 **값까지** 요구한다.
# Grok 적발(2026-07-29): 초판은 키만 봐서 `session:` `claim:` `verdict:` **빈 3줄**로 통과했다
# = "구조는 있는데 내용이 없는" 초록. 그래서 session 은 Grok sessionId 형태, verdict 는 닫힌
# 집합, claim 은 최소 길이를 요구한다. 위조 비용을 올릴 뿐 **위조를 막지는 못한다**(§한계 1).
# 🔴 Values are required, not just keys: the first version passed on three EMPTY fields — structure
# without substance. This raises the forgery cost; it does not prevent forgery.
_TRACE_HEADING = re.compile(r"^#{1,4}[^\n]*claim-?review", re.IGNORECASE | re.MULTILINE)
# 🔴 `WEAKENED` 추가 (2026-08-06) — Grok 이 실제로 내는 판정인데 합법 토큰이 아니었다.
#    `docs/cycle-history.md:223` 이 이미 그 판정을 서사로 기록하고 있는데 가드는 거부했다.
#    '부분적으로 성립' 을 표현할 수단이 없으면 저자는 SURVIVES 로 반올림하게 된다 —
#    즉 어휘 부족이 **판정을 낙관 쪽으로 왜곡**한다.
# Grok really emits WEAKENED; without it authors round up to SURVIVES.
_REQUIRED_FIELDS: tuple[tuple[str, str], ...] = (
    # 🔴 백틱/따옴표 허용 (2026-07-31) — 아래 안내문 예시가 백틱 형태(`019fadf6-...`)인데
    #    정규식은 백틱을 거부해, **가드가 자기 안내대로 적은 본문을 차단**했다. 실측: 이 가드를
    #    고치는 PR 자신이 그 이유로 exit 1. 마크다운에서 ID 를 코드 표기하는 것은 자연스럽다.
    # 🔴 Allow backticks/quotes: the help text below demonstrates a backticked example the regex
    #    rejected, so the guard blocked bodies written exactly as it instructed.
    # 🔴 **벤더 중립화 (2026-08-08 — 면제 필수 승격의 짝)**: 가드 표면 PR 에서 면제를 닫는
    #    순간, 이 필드가 Grok sessionId **형식만** 받으면 그 서비스가 죽는 날 가드 작업이
    #    영구 차단된다. 그건 봉인이 아니라 가용성 사고다(정책 17 — 안정성 > 권장 규격).
    #    그렇다고 아무 문자열이나 받으면 자기 인증이 되므로, **되짚을 수 있는 식별자**만 받는다:
    #      · Grok sessionId  — `019fadf6-523e-...`
    #      · 워크플로 run id — `wf_a3ad73e1-eca` (transcript 가 디스크에 남는다)
    #    둘 다 사후에 원문을 열 수 있다는 것이 요점이다 — 그게 "흔적" 의 정의다.
    # Vendor-neutral but still retrievable: a Grok sessionId or a Workflow run id, both of
    # which point at a transcript someone can reopen. A free-form string would be self-certification.
    (r"^[-*|\s]*session\s*[:|]\s*[`'\"]?(?:[0-9a-f]{8}-[0-9a-f]{4}|wf_[a-z0-9-]{6,})",
     "session — Grok sessionId (`019fadf6-523e-...`) 또는 워크플로 run id (`wf_a3ad73e1-eca`)"),
    (r"^[-*|\s]*verdict\s*[:|]\s*(SURVIVES|WEAKENED|BROKEN|CONFIRMED|REFUTED|HOLDS)\b",
     "verdict — SURVIVES | WEAKENED | BROKEN | CONFIRMED | REFUTED | HOLDS 중 하나"),
    (r"^[-*|\s]*claim\s*[:|]\s*\S.{15,}",
     "claim — 검증한 주장 (16자 이상)"),
)

# 면제 마커 — seal 어휘가 **인용/회고 서술**일 때만. 🔴 본문에서만 유효하고 사유 16자 이상.
# Grok 적발: 초판은 haystack 전체(제목·커밋 포함)에서 `\S+` 한 글자만 있으면 통과해
# `claim-review-not-required: x` 로 자기면제가 가능했다.
# Exemption is body-only and needs a real reason; the first version accepted a single character
# anywhere in title/body/commits.
# 🔴 **줄 맨 앞**에서만, 그리고 백틱/인용부호로 감싸이지 않은 것만 마커로 인정한다.
# 자기 적용 실측(2026-07-29): 이 가드의 **사용법을 설명하는 문장** — 예: 인용·회고면
# `claim-review-not-required: <사유>` 를 적으세요 — 가 마커로 오인돼 **가드를 문서화하는 PR 이
# 스스로 면제**됐다(seal 주장 13건이 통과). 설명은 문장 중간이나 코드 표기 안에 오므로 앵커로
# 분리한다.
# 🔴 Only at line start and not wrapped in backticks/quotes. Measured on this very PR: prose
# *explaining* the marker exempted the PR that documents the guard.
_EXEMPT = re.compile(
    r"^[ \t]*(?![`'\"])claim-review-not-required\s*:\s*\S.{15,}",
    re.IGNORECASE | re.MULTILINE,
)


# 🔴 HTML 주석은 GitHub 렌더링에서 **리뷰어에게 보이지 않는다** — 주석 안 흔적/면제를
#    인정하면 "가드 통과 + 리뷰어 비가시" 조합이 성립한다(backlog R20 결함 1). 미종결
#    `<!--` 이후도 전부 제거한다 — GitHub 는 닫히지 않은 주석 뒤를 렌더하지 않는다.
# 🔴 단, 마크다운 인지가 필수다 (Grok `019fbe32` GROK-20260802-1/2 재현 적발): 코드펜스·
#    인라인 코드 안의 `<!--` 는 GitHub 에서 **가시**(주석 아님)인데, 초판 정규식은 그 이후를
#    전부 지워 — 가시 seal 주장이 탐지를 벗어나고(fail-open) 가시 흔적이 지워졌다(false red).
#    "가드가 보는 텍스트 = 리뷰어가 보는 텍스트" 는 렌더 규칙을 따라야만 참이다.
# HTML comments are reviewer-invisible, but `<!--` inside fenced/inline code is VISIBLE on
# GitHub — the first regex version stripped past it, hiding visible seals from enforcement
# (fail-open) and visible traces from credit (false red). The stripper must be markdown-aware.
_FENCE_LINE = re.compile(r"^[ \t]{0,3}(?:```|~~~)")
_INLINE_CODE = re.compile(r"`[^`\n]+`")

# 개행류 제어문자 전부 — Actions 워크플로 커맨드는 라인 지향이라 이 중 하나라도 남으면
# 본문이 ::error 등을 위조 주입할 수 있다 (Grok `019fbe32` GROK-20260802-3 — 종전엔 \n 만 중화).
# Every line-break control char; any survivor lets the body forge workflow commands
# into the line-oriented Actions log (only \n was neutralized before).
_LINE_BREAKS = re.compile("[" + "".join(chr(c) for c in (10, 11, 12, 13, 0x85, 0x2028, 0x2029)) + "]+")


def strip_html_comments(text: str) -> str:  # pylint: disable=too-many-branches
    """리뷰어 비가시 영역(진짜 HTML 주석)만 제거하는 라인 상태기계.

    규칙 (GitHub 렌더 동작 대응 — branch 수는 상태 전이 그대로라 분해하면 오히려 흐려진다):
      · 펜스(```/~~~) 내부와 인라인 코드 스팬 안의 `<!--` 는 주석 시작이 아니다(가시 보존).
      · HTML 주석 내부에서는 펜스 토글·인라인 보호가 없다 — `-->` 만 찾는다(GitHub 동작).
      · 미종결 주석은 문서 끝까지 비가시다.
    A line state machine that strips only genuinely reviewer-invisible regions, honoring
    fenced/inline code (visible), comment-interior rules, and unterminated comments.
    """
    out: list[str] = []
    in_comment = False
    in_fence = False
    for line in text.split("\n"):
        if in_comment:
            close = line.find("-->")
            if close == -1:
                continue  # 줄 전체 비가시 / whole line invisible
            in_comment = False
            line = line[close + 3:]
            # 닫힌 뒤 남은 부분은 아래 일반 경로로 계속 처리한다.
            # The remainder after the close falls through to the normal path below.
        if in_fence:
            if _FENCE_LINE.match(line):
                in_fence = False
            out.append(line)
            continue
        if _FENCE_LINE.match(line):
            in_fence = True
            out.append(line)
            continue
        # 인라인 코드 스팬을 마스킹해 그 안의 마커가 주석을 열지 못하게 한다(원문은 보존).
        # Mask inline code spans so their markers cannot open a comment; text is preserved.
        masked = _INLINE_CODE.sub(lambda m: "\x00" * len(m.group(0)), line)
        kept: list[str] = []
        pos = 0
        while pos < len(line):
            if in_comment:
                close = line.find("-->", pos)
                if close == -1:
                    break
                in_comment = False
                pos = close + 3
                continue
            start = masked.find("<!--", pos)
            if start == -1:
                kept.append(line[pos:])
                break
            kept.append(line[pos:start])
            pos = start + 4
            in_comment = True
        out.append("".join(kept))
    return "\n".join(out)


def read_pr_body() -> str:
    """🔴 **PR 본문을 읽는 유일한 지점** — 리뷰어 비가시 영역을 제거한 뒤 돌려준다.

    ## 왜 함수 하나로 모았나 (2026-08-08 회고 N-P0-1)

    이 모듈이 `strip_html_comments` 로 닫아 둔 축(backlog R20 결함 1 · Grok `019fbe32`)이
    **세 게이트에서 한꺼번에 재발**했다. `check_reverse_mutation` · `check_test_count_sync` ·
    `check_red_budget` 이 면제 마커 관용구는 복제하면서 **하드닝은 복제하지 않아**,
    `os.environ["PR_BODY"]` 원문을 정규식에 그대로 넘겼다. 결과는 리포가 이미 한 번
    값을 치른 fail-open 그대로다 — 멀티라인 `<!-- … -->` 안에 마커를 적으면
    **리뷰어에게는 안 보이는데 required check 는 통과**한다.

    🔴 교훈은 "복제하지 말라" 가 아니라 **"읽는 지점을 하나로 두라"** 다. 관용구는 앞으로도
    복제되겠지만, 그 관용구가 `read_pr_body()` 를 부르는 한 하드닝이 함께 따라온다.
    `tests/unit/scripts/test_pr_body_single_reader.py` 가 이 단일성을 기계로 강제한다.

    The single place any gate reads the PR body; strips reviewer-invisible regions so a
    marker hidden in an HTML comment can never satisfy a gate.
    """
    return strip_html_comments(os.environ.get("PR_BODY", "") or "")


def find_seal_claims(text: str) -> list[tuple[int, str, str]]:
    """seal 주장이 나타난 (줄번호, 어휘, 줄내용) 목록."""
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern, label in _SEAL_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                hits.append((lineno, label, line.strip()[:120]))
                break
    return hits


def missing_trace_fields(text: str) -> list[str]:
    """claim-review 흔적에서 빠진 요소 목록 (빈 리스트 = 흔적 충족)."""
    missing = []
    if not _TRACE_HEADING.search(text):
        missing.append("`## Grok claim-review` 형태의 섹션 헤딩")
    for pattern, label in _REQUIRED_FIELDS:
        if not re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            missing.append(label)
    return missing


# ── 정책 트리거 ≠ 가드 트리거 (backlog R57) ─────────────────────────────
#
# 정책 19 는 *"실질 작업마다 CLAIM-REVIEW 기본 포함"* 이다(사용자 명시 지시). 그런데 이
# 가드는 **seal 어휘가 있을 때만** 흔적을 요구했다. 그래서 어휘가 없는 PR 은 아무것도 없이
# 통과했고, Claude 는 그 **가드 트리거를 정책 트리거로 오인**해 seal 어휘가 없는 PR 에
# `claim-review-not-required` 를 자기발급했다(최근 25 PR 중 6건).
#
# 🔴 실측 (2026-08-06, 최근 30 머지 PR):
#   · 코드 표면 변경 23건 / 문서 전용 7건
#   · 새 기준에서 흔적도 면제도 없는 것 = **3건(10%)** — 오탐이 진탐을 넘지 않는다.
# 그 3건은 e2e drift 30건 해소·CodeQL 수정 등 **실질 코드 변경**이라 red 가 옳다.
#
# 목록에 `docs/runbooks/owed-verification.md` 가 있는 이유: 그 파일은 R0-2 이후
# **기계 판정 입력**이다. 행을 지우는 PR 이 '문서' 로 분류돼 무검증 통과하면 안 된다.
# `tests/unit/{scripts,hooks}/` 는 가드가 저술되는 표면이라 같은 이유로 포함한다.
#
# The guard fired only on seal vocabulary while the policy applies to substantive work; that
# gap is what the self-issued exemptions filled. Measured FP rate with this list: 3/30.
_CODE_SURFACES = (
    "src/",
    "scripts/",
    "alembic/",
    "e2e/",
    ".claude/hooks/",
    ".claude/workflows/",
    ".claude/settings.json",
    ".github/workflows/",
    ".pre-commit-config.yaml",
    "tests/unit/scripts/",
    "tests/unit/hooks/",
    "docs/runbooks/owed-verification.md",
)


# 🔴 **가드 표면** — 여기를 건드리는 PR 은 면제 마커로 빠져나갈 수 없다 (사용자 결정 2026-08-08).
#
# 왜 코드 표면 전체가 아니라 부분집합인가: 면제를 전면 폐지하면 일상 리팩터까지 외부 검증을
# 기다리게 되어 **오탐이 진탐을 넘는다**(정책 17 — 가드 자살). 반면 *관측자를 저술하는 표면*
# 에서는 결함이 조용하다 — 가드가 틀리면 그 가드가 지키는 축 전체가 무증상으로 열린다.
#
# 🔴 근거 (2026-08-08 세션 실측): 이 창이 만든 게이트 **4개 중 3개가 같은 형태로 결함**이었다
#    (면제 마커 관용구는 복제하고 하드닝은 복제하지 않음 → HTML 주석 은닉 면제 3중 재발).
#    11 에이전트 5+1 회고는 그중 하나를 **못 찾았고**, Grok claim-review `019fe026` 가
#    "이월 마커 봉인" 을 BROKEN 으로 반증했다. *"게이트가 작동하는가"* 와
#    *"이 봉인을 어떻게 깨는가"* 는 다른 질문이고, 후자만 그 결함을 찾았다.
#
# ⚠️ **흔적은 Grok 전용이 아니다** — 요구하는 것은 (session · claim · verdict) 세 필드이지
#    특정 벤더가 아니다. 외부 서비스가 죽어도 독립 적대 검증(워크플로 적대 패스 등)으로
#    흔적을 채울 수 있다. 그래야 서비스 장애가 가드 작업을 영구 차단하지 않는다.
# Guard-authoring surfaces cannot self-exempt; the trace is reviewer-agnostic (three fields),
# so an outage of any one reviewer never hard-blocks the repo.
_GUARD_SURFACES = (
    "scripts/",
    ".claude/hooks/",
    ".claude/workflows/",
    ".claude/settings.json",
    ".github/workflows/",
    ".pre-commit-config.yaml",
    "tests/unit/scripts/",
    "tests/unit/hooks/",
    "docs/runbooks/owed-verification.md",
)


def guard_surfaces(paths: list[str] | None) -> list[str]:
    """변경 경로 중 **가드 표면**만. 판정 불가(None)면 빈 리스트 — 이 축은 쉰다.

    🔴 `None` 에서 빈 리스트를 돌려주는 것이 fail-open 처럼 보이지만 아니다: 그 경우
    `changed_code_surfaces` 도 `None` 이라 **seal 축만** 남고, 그 축은 그대로 흔적을 요구한다.
    여기서 fail-closed 로 두면 base/head SHA 가 없는 **모든 로컬 실행**이 영구 red 가 된다
    (정책 17 — 로컬 게이트가 못 쓰게 되면 아무도 안 돌린다).
    """
    return [p for p in (paths or []) if p.startswith(_GUARD_SURFACES)]


def changed_code_surfaces(base_sha: str, head_sha: str) -> list[str] | None:
    """PR 이 건드린 코드 표면 경로. **판정 불가면 None**(빈 리스트와 구별한다).

    🔴 `base...head`(three-dot, merge-base 기준)를 쓴다 — `base..head` 는 base 브랜치가
    앞서간 만큼을 함께 세어 남의 변경을 이 PR 의 것으로 오판한다.
    """
    try:
        proc = subprocess.run(  # nosec B603 B607
            ["git", "diff", "--name-only", f"{base_sha}...{head_sha}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return [
        line.strip() for line in (proc.stdout or "").splitlines()
        if line.strip().startswith(_CODE_SURFACES)
    ]


def commit_messages(base_sha: str, head_sha: str) -> str:
    """PR 범위 커밋 메시지 전문 (실패 시 빈 문자열 — 이 축은 보조)."""
    try:
        proc = subprocess.run(  # nosec B603 B607
            ["git", "log", "--format=%B", f"{base_sha}..{head_sha}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, check=False,
        )
    except OSError:
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def _append_step_summary(markdown: str) -> None:
    """GitHub Actions job summary 에 한 줄 추가 (없으면 조용히 무시 — 로컬 실행).

    🔴 `::notice` 는 Actions **로그 안쪽**이라 실질적으로 아무도 보지 않는다. 면제 남용은
    한 건씩 보면 정상이고 **추세로만** 드러나므로, 사람이 실제로 여는 자리(run summary)에
    누적돼야 한다. 이 리포가 반복해 고쳐 온 "관측은 하는데 아무도 안 보는" 클래스다.
    """
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(markdown)
    except OSError:
        pass  # 요약 기록 실패가 판정을 바꾸면 안 된다 / never let logging change the verdict


def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지·한글 출력 크래시 방지 — UTF-8 재구성(errors=replace)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시


def main() -> int:
    """seal 주장이 있으면 claim-review 흔적을 요구한다 (blocking — exit 1)."""
    _make_stdout_safe()
    # 🔴 PR 본문은 **임의 사용자 입력**이라 셸 보간이 아니라 env 로 받는다(명령 인젝션 차단).
    # 🔴 The PR body is untrusted input: read it from env, never interpolate it into a shell line.
    title = os.environ.get("PR_TITLE", "")
    # 🔴 body 는 HTML 주석 스트리핑 후 판정한다 (backlog R20 결함 1) — 주석 안에 숨긴
    #    흔적/면제가 exit 0 을 만들면 리뷰어 비가시 무임승차가 된다. 제목·커밋 메시지는
    #    plain text 로 렌더되므로 스트리핑하지 않는다(기존 동작 보존).
    # The body is judged after comment stripping; titles/commits render as plain text.
    body = read_pr_body()
    base_sha = os.environ.get("PR_BASE_SHA", "")
    head_sha = os.environ.get("PR_HEAD_SHA", "")

    commits = commit_messages(base_sha, head_sha) if base_sha and head_sha else ""
    haystack = "\n".join([title, body, commits])

    claims = find_seal_claims(haystack)

    # 🔴 두 번째 트리거 — **코드 표면을 건드리면** seal 어휘가 없어도 흔적을 요구한다 (R57).
    #    정책 19 의 트리거는 '실질 작업' 인데 가드는 '어휘' 만 봤고, 그 간극을 자기발급
    #    면제가 메웠다. PR env 가 없으면(로컬 `pre_push_gate`) `None` 이라 이 축은 쉰다 —
    #    거기서 fail-closed 로 두면 모든 로컬 push 가 영구 red 가 된다(정책 17).
    # Second trigger: touching code surfaces requires a trace even without seal vocabulary.
    surfaces = changed_code_surfaces(base_sha, head_sha) if base_sha and head_sha else None

    if not claims and not surfaces:
        # 🔴 `None`(판정 불가)과 `[]`(변경 없음)은 같은 분기로 오지만 **같은 말을 하면 안 된다**
        #    (Grok claim-review `019fd786` 적발). 이전 문구는 경로를 못 구한 상태에서도
        #    "코드 표면 변경 없음" 이라고 단언해, 모른다는 사실을 안다는 말로 덮었다.
        # None (undecidable) and [] (nothing changed) land in the same branch but must not
        # say the same thing: claiming "no code surfaces changed" when we could not tell is a lie.
        if surfaces is None and base_sha and head_sha:
            print(
                "⚠️ 변경 경로를 산출하지 못했다 — **코드 표면 축 판정 불가**(seal 축만 적용).\n"
                "   '변경 없음' 이 아니라 '모른다' 다. base/head SHA 와 저장소 히스토리를 확인할 것."
            )
            print("✅ seal 주장 없음 — 이 축에서는 요구 대상 아님")
        else:
            print("✅ seal 주장 없음 · 코드 표면 변경 없음 — claim-review 요구 대상 아님")
        return 0

    # 🔴 면제는 **본문에서만** 유효하다 — haystack(제목·커밋 포함)에서 찾으면 커밋 메시지 한 줄로
    # 자기면제가 가능하다(Grok 적발). 면제는 리뷰어가 보는 자리에 있어야 한다.
    # 🔴 Exemption is body-only: searching the whole haystack would let a commit line self-exempt.
    exemption = _EXEMPT.search(body)

    # 🔴 **면제가 통하지 않는 경우** (사용자 결정 2026-08-08 — "필수로 승격").
    #    (a) 가드 표면을 건드렸다 — 관측자를 저술하는 PR 은 자기 승인으로 통과할 수 없다.
    #    (b) seal 주장 + 코드 표면 — "봉인했다" 는 주장은 코드가 걸려 있을 때 검증이 필요하다.
    #    문서 전용 PR 이 과거 사고를 **인용**하며 seal 어휘를 쓰는 것은 그대로 면제 가능하다
    #    (회고 기록·원장 서술이 막히면 이 리포가 가장 중요하게 여기는 "무엇이 왜 틀렸는지
    #    남기기" 가 불가능해진다 — 인용은 주장이 아니다).
    # Self-exemption is unavailable when the PR authors a guard, or claims a seal over code.
    guarded = guard_surfaces(surfaces)
    exemption_blocked = bool(guarded) or bool(claims and surfaces)

    if exemption and exemption_blocked:
        why = (
            f"가드 표면 {len(guarded)}개 파일 변경" if guarded
            else f"seal 주장 {len(claims)}건 + 코드 표면 {len(surfaces or [])}개 파일"
        )
        reason = _LINE_BREAKS.sub(" ", exemption.group(0).strip())[:200]
        print(f"::error title=claim-review exemption not allowed::{why}")
        _append_step_summary(
            f"- 🔴 **claim-review 면제 거부** — {why}\n  - 시도한 사유: {reason}\n"
        )
        print(
            f"🔴 이 PR 에서는 `claim-review-not-required` 가 **유효하지 않다** — {why}.\n"
            f"   시도한 사유: {reason}\n\n"
            "   근거: 2026-08-08 창이 만든 게이트 4개 중 3개가 같은 형태로 결함이었고,\n"
            "   11 에이전트 회고가 그중 하나를 못 찾았다. Grok claim-review 가 '봉인' 주장을\n"
            "   BROKEN 으로 반증했다 — *'작동하는가'* 와 *'어떻게 깨는가'* 는 다른 질문이다.\n\n"
            "   → 독립 적대 검증을 수행하고 본문에 흔적을 남기세요:\n"
            "     ## Grok claim-review\n"
            "     - session: <sessionId>\n"
            "     - claim: <검증한 주장 한 줄>\n"
            "     - verdict: SURVIVES | WEAKENED | BROKEN (근거 요약)\n"
            "   ⚠️ 흔적은 **벤더 중립**이다 — 요구하는 것은 세 필드이지 특정 도구가 아니다.\n"
            "      외부 서비스가 죽었으면 독립 적대 패스(워크플로 등)로 검증하고 그 결과를 적으세요.",
            file=sys.stderr,
        )
        return 1

    if exemption:
        # 🔴 면제 사용은 계량 대상 (backlog R20-a) — 조용한 exit 0 이면 남용 추세가 관측되지
        #    않는다(창의 post-guard seal PR 10건 중 5건이 면제 통과). Actions UI annotation 으로
        #    매 사용을 가시화한다. 계량 집계는 회고 시 `gh pr list --search` 로 수행.
        # Every exemption use is annotated so the trend is observable in the Actions UI.
        # 🔴 개행류 제어문자 전부 중화 (Grok `019fbe32` GROK-20260802-3) — `\r` 가 남으면
        #    워크플로 커맨드 라인이 갈라져 본문이 `::error` 등을 위조 주입할 수 있다.
        # Neutralize every line-break control char; a surviving `\r` would let the body forge
        # additional workflow commands into the Actions log.
        reason = _LINE_BREAKS.sub(" ", exemption.group(0).strip())[:200]
        print(f"::notice title=claim-review exemption used::{reason}")
        # 🔴 job summary 에도 남긴다 (R57) — `::notice` 는 Actions 로그 안쪽이라 아무도 안 본다.
        #    면제 남용은 **추세**로만 보이므로 사람이 보는 자리에 축적돼야 한다.
        # Also record in the job summary: `::notice` is buried in the log where nobody looks.
        _append_step_summary(
            f"- ⏭️ **claim-review 면제 사용** — seal 주장 {len(claims)}건 · "
            f"코드 표면 {len(surfaces or [])}개 파일\n  - 사유: {reason}\n"
        )
        print(
            f"⏭️  면제 마커(claim-review-not-required) 확인 — "
            f"seal 주장 {len(claims)}건 · 코드 표면 {len(surfaces or [])}개 통과"
        )
        return 0

    missing = missing_trace_fields(body)
    if not missing:
        print(
            f"✅ claim-review 흔적 확인 — seal 주장 {len(claims)}건 · "
            f"코드 표면 {len(surfaces or [])}개"
        )
        return 0

    if claims:
        print("🔴 seal 주장이 있는데 claim-review 흔적이 없습니다 (정책 19).", file=sys.stderr)
    else:
        print(
            "🔴 코드 표면을 바꾸는데 claim-review 흔적이 없습니다 (정책 19 default).",
            file=sys.stderr,
        )
        print(
            "   정책 19 는 *실질 작업마다* CLAIM-REVIEW 를 기본 포함하라고 합니다 —\n"
            "   seal 어휘가 없다는 것은 면제 사유가 아닙니다(그 오인이 backlog R57 입니다).\n"
            f"   변경된 표면 {len(surfaces or [])}개: {', '.join((surfaces or [])[:6])}"
            + (" …" if len(surfaces or []) > 6 else ""),
            file=sys.stderr,
        )
    print("   This PR changes code/guard surfaces without a claim-review trace.\n", file=sys.stderr)
    for lineno, label, line in claims[:8]:
        print(f"   - [{label}] line {lineno}: {line}", file=sys.stderr)
    if len(claims) > 8:
        print(f"   ... 외 {len(claims) - 8}건", file=sys.stderr)
    print("\n   빠진 요소 / missing:", file=sys.stderr)
    for item in missing:
        print(f"   - {item}", file=sys.stderr)
    print(
        "\n   해결 / Fix: Grok claim-review 를 실행하고 PR 본문에 아래 형태로 결과를 남기세요.\n"
        "     ## Grok claim-review\n"
        "     - session: <grok sessionId>\n"
        "     - claim: <검증한 주장 한 줄>\n"
        "     - verdict: SURVIVES | WEAKENED | BROKEN (근거 요약)\n"
        "   인용·회고 서술이라 검증 대상이 아니면 `claim-review-not-required: <사유>` 를 적으세요.\n"
        "   🔴 이 검사는 흔적의 **존재**만 봅니다 — 위조·판정의 진위는 잡지 못합니다(설계상 한계).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
