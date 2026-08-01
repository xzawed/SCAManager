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
_REQUIRED_FIELDS: tuple[tuple[str, str], ...] = (
    # 🔴 백틱/따옴표 허용 (2026-07-31) — 아래 안내문 예시가 백틱 형태(`019fadf6-...`)인데
    #    정규식은 백틱을 거부해, **가드가 자기 안내대로 적은 본문을 차단**했다. 실측: 이 가드를
    #    고치는 PR 자신이 그 이유로 exit 1. 마크다운에서 ID 를 코드 표기하는 것은 자연스럽다.
    # 🔴 Allow backticks/quotes: the help text below demonstrates a backticked example the regex
    #    rejected, so the guard blocked bodies written exactly as it instructed.
    (r"^[-*|\s]*session\s*[:|]\s*[`'\"]?[0-9a-f]{8}-[0-9a-f]{4}",
     "session — Grok sessionId (예: `019fadf6-523e-...`)"),
    (r"^[-*|\s]*verdict\s*[:|]\s*(SURVIVES|BROKEN|CONFIRMED|REFUTED|HOLDS)\b",
     "verdict — SURVIVES | BROKEN | CONFIRMED | REFUTED | HOLDS 중 하나"),
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


def _strip_html_comments(text: str) -> str:  # pylint: disable=too-many-branches
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
    body = _strip_html_comments(os.environ.get("PR_BODY", ""))
    base_sha = os.environ.get("PR_BASE_SHA", "")
    head_sha = os.environ.get("PR_HEAD_SHA", "")

    commits = commit_messages(base_sha, head_sha) if base_sha and head_sha else ""
    haystack = "\n".join([title, body, commits])

    claims = find_seal_claims(haystack)
    if not claims:
        print("✅ seal 주장 없음 — claim-review 요구 대상 아님 / no seal claim")
        return 0

    # 🔴 면제는 **본문에서만** 유효하다 — haystack(제목·커밋 포함)에서 찾으면 커밋 메시지 한 줄로
    # 자기면제가 가능하다(Grok 적발). 면제는 리뷰어가 보는 자리에 있어야 한다.
    # 🔴 Exemption is body-only: searching the whole haystack would let a commit line self-exempt.
    exemption = _EXEMPT.search(body)
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
        print(f"⏭️  면제 마커(claim-review-not-required) 확인 — seal 주장 {len(claims)}건 통과")
        return 0

    missing = missing_trace_fields(body)
    if not missing:
        print(f"✅ seal 주장 {len(claims)}건 + claim-review 흔적 확인")
        return 0

    print("🔴 seal 주장이 있는데 claim-review 흔적이 없습니다 (정책 19).", file=sys.stderr)
    print("   This PR asserts a seal without a claim-review trace.\n", file=sys.stderr)
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
        "     - verdict: SURVIVES | BROKEN (근거 요약)\n"
        "   인용·회고 서술이라 검증 대상이 아니면 `claim-review-not-required: <사유>` 를 적으세요.\n"
        "   🔴 이 검사는 흔적의 **존재**만 봅니다 — 위조·판정의 진위는 잡지 못합니다(설계상 한계).",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
