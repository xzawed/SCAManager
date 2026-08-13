#!/usr/bin/env python3
"""문서 변경 다중 에이전트 심의 Hook — PreToolUse (Edit/Write/MultiEdit).
Multi-agent review gate for document changes — PreToolUse hook."""
import anthropic
import asyncio
import json
import os
import re
import sys
from pathlib import Path

# ─── 파일 등급 분류 ──────────────────────────────────────────────────────────
# File grade classification

# 🔴 2026-07-29 스코프 복구 (backlog R9 · Grok 전반 검토) — 2026-07-21 문서 재구성 이후
# **가장 행동에 영향을 주는 규칙 문서들이 전부 `skip` 이었다**:
#   · `AGENTS.md`            = 가드/관측자 3-불변식 SSOT (Claude·Grok dual-consumer)
#   · `.claude/rules/*.md`   = path-scoped 규칙 154KB — 편집 표면에 자동 로드돼 행동을 직접 바꾼다
#   · `.claude/policies/*.md`= 협업 정책 detail 50KB
# 즉 심의 게이트가 **정작 심의해야 할 표면을 통과시키고 있었다**(false coverage). 실측:
# 2026-07-29 세션이 `.claude/rules/pipeline.md` 를 수정했는데 게이트가 발화하지 않았다.
# 🔴 Scope recovery (backlog R9): after the 2026-07-21 doc reorg the highest-behavioral-impact rule
# files all graded `skip` — the review gate was passing exactly the surfaces it exists to review.
_CRITICAL = [
    r"^CLAUDE\.md$",
    r"^AGENTS\.md$",
    r"^docs/STATE\.md$",
    r"^\.claude/settings\.json$",
    r"^\.claude/agents/[^/]+\.md$",
    r"^\.claude/skills/[^/]+\.md$",
    # rules/ 는 편집 표면에 자동 로드되는 **행동 지시문**이라 critical (policies/ 는 detail → important)
    # rules/ are behavioural directives auto-loaded at the edit surface; policies/ are detail.
    r"^\.claude/rules/[^/]+\.md$",
]

# 🔴 2026-08-01 2차 스코프 복구 (문서 감사 91 에이전트 + Grok 시스템 감사 `019fbccf`)
# R9(2026-07-29)가 AGENTS/rules/policies 를 복구했으나 **행동 지시를 담은 표면이 아직 남아
# 있었다**: 추적 비-archive 101개 중 **50개가 `skip`** 이었고 그중 **25개가 에이전트가 따르는
# 지시문**을 담고 있었다. 대표 예:
#   · `docs/runbooks/ai-collaboration.md` — "Grok 은 정책·backlog 를 **저술하지 않는다**",
#     "🔴 **P0/P1 부여 금지**" (정책 19 프로토콜 SSOT 인데 심의 대상이 아니었다)
#   · `docs/runbooks/workflow.md` — "테스트 환경 미구성에서는 **절대 수정하지 않는다**"
#   · `docs/runbooks/owed-verification.md` — "사용자 회신 전까지 **행 삭제 금지**"
#   · `docs/architecture.md` — "신규 파일 추가 시 이 문서 갱신 **의무**"
#   · `docs/reference/env-vars.md` — "운영 절대 설정 금지"(`API_AUTH_DISABLED`)
#   · `.github/PULL_REQUEST_TEMPLATE.md` · `CONTRIBUTING*.md` · `docs/agents-index.md` · `docs/backlog.md`
# 즉 심의 게이트가 **지시를 담은 문서의 편집을 검토 없이 통과**시키고 있었다(false coverage).
# 🔴 `docs/design/**` 이 한 세그먼트만 매칭해 `docs/design/brief/*` 5개가 빠지던 것도 함께 시정.
# 🔴 Second scope recovery: 25 directive-bearing files were graded `skip`, so the gate passed
# edits to the very surfaces that tell agents what to do.
_IMPORTANT = [
    r"^docs/design/.+\.md$",          # `brief/` 등 하위 디렉토리 포함 (이전엔 한 세그먼트만)
    r"^docs/superpowers/.+\.md$",
    r"^README(\.[a-z]{2})?\.md$",     # README.ko.md 등 로케일 변형 포함
    r"^\.claude/policies/[^/]+\.md$",
    # 아래는 2026-08-01 승격분 — 전부 에이전트가 따르는 지시문을 담는다.
    r"^docs/runbooks/[^/]+\.md$",
    r"^docs/architecture\.md$",
    r"^docs/backlog\.md$",
    r"^docs/agents-index\.md$",
    r"^docs/reference/[^/]+\.md$",
    r"^CONTRIBUTING(\.[a-z]{2})?\.md$",
    r"^\.github/PULL_REQUEST_TEMPLATE\.md$",
    # 🔴 2026-08-13 이동: `.claude/plans/` → `docs/_archive/plans/`.
    #    아카이브로 옮겼어도 심의 대상으로 남긴다 — 위험은 위치가 아니라 **완료 표지**에 있고,
    #    그 표지가 지워지면 미래 세션이 출시된 기능을 재구현한다(이 훅이 생긴 이유).
    r"^docs/_archive/plans/[^/]+\.md$",
    r"^SECURITY(\.[a-z]{2})?\.md$",   # 취약점 보고 절차 = 보안 지시문
    r"^scripts/i18n_comments/glossary\.md$",  # "번역 시 아래 용어를 반드시 사용" = 번역 계약
    r"^src/scripts/README\.md$",     # "Production code MUST NOT import from src/scripts/" = 실제 지시문
    # 2026-08-13 승격분 — 3층 분리(프로세스·함정·규칙)로 신설된 지시 표면.
    # 🔴 `docs/process/**` 는 *어떻게 수행하는가* 를 단계로 규정한다 = 지시문이다.
    #    `.claude/traps.md` 는 서술 같지만 각 항목이 "→ 이렇게 하라" 로 끝난다.
    #    둘 다 등재하지 않으면 심의 게이트가 **지시 표면 자체의 편집을 통과**시킨다
    #    (2026-08-01 에 정확히 이 클래스로 25 파일이 false coverage 였다).
    r"^docs/process/[^/]+\.md$",
    r"^\.claude/traps\.md$",
]

# 🔴 의도적으로 `skip` 으로 남긴 것 (판단 기록 — 다음 세션이 재검토를 반복하지 않도록):
#   · `docs/cycle-history.md` — append-only **과거 서사**다. 지시 어휘가 많은 이유는 과거 결정을
#     인용하기 때문이지 지금 지시하기 때문이 아니다. 매 trailing sync 마다 3-에이전트 심의를
#     붙이면 비용만 늘고, 이 파일은 `check_toc_anchors` 가 이미 구조를 지킨다.
#   · `docs/reports/**` — 시점 스냅샷(감사 보고서). 현재 계약이 아니다.
#   · `docs/README.md` — 순수 색인이다(지시문 없음). 🔴 `src/scripts/README.md` 는 여기 있었으나
#     "Production code MUST NOT import from src/scripts/" 라는 **실제 지시문**이 있어 승격했다
#     (2026-08-01 Grok claim-review `019fbd1e` 적발 — "지시 밀도가 낮다" 는 내 판단이 틀렸다).
# Deliberately left `skip`, with the reasoning recorded so it is not re-litigated every session.

_LOW_RISK = [
    r"^docs/reports/artifacts/",
    r"^docs/history/",
    # 🔴 2026-08-13: 구 `docs/integrations/` 가 `docs/runbooks/` 로 합쳐지며 이 자리에
    #    `^docs/runbooks/` 가 들어갔었다. `_IMPORTANT` 가 먼저 매칭돼 실제 강등은 없었지만,
    #    **런북 전체를 low_risk 로 읽히게 하는 죽은 패턴**이라 제거했다.
    #    통합된 문서는 런북과 같은 등급(important)을 받는 것이 맞다.
]


def _project_root() -> str:
    """프로젝트 루트를 런타임 결정 — 훅은 `.claude/hooks/` 에 위치 (WBS P0 회귀 복구, 사이클 160).
    하드코딩 절대경로(commit 7d20dc6 회귀 — `d:/source/scamanager/`) 제거: 드라이브/대소문자/구분자 무관.
    Resolve project root at runtime (hook lives in .claude/hooks/); no hardcoded path."""
    return str(Path(__file__).resolve().parents[2]).replace("\\", "/").rstrip("/").lower() + "/"


def _normalise(path: str) -> str:
    """경로를 슬래시 정규화 + 런타임 프로젝트 루트 접두사 제거 (절대/상대 모두 처리).
    Normalise to forward-slashes and strip the runtime-resolved project root prefix."""
    p = path.replace("\\", "/")
    root = _project_root()
    if p.lower().startswith(root):
        return p[len(root):]
    return p


def classify_file_grade(file_path: str) -> str:
    """Critical / important / low_risk / skip 중 하나를 반환한다.
    Returns one of: critical, important, low_risk, skip."""
    p = _normalise(file_path)

    for pattern in _CRITICAL:
        if re.match(pattern, p, re.IGNORECASE):
            return "critical"

    for pattern in _IMPORTANT:
        if re.match(pattern, p, re.IGNORECASE):
            return "important"

    for pattern in _LOW_RISK:
        if re.match(pattern, p, re.IGNORECASE):
            return "low_risk"

    return "skip"


def gate_disabled() -> bool:
    """DOC_REVIEW_GATE_DISABLED=1 시 True — 문서 리뷰 게이트 비용 kill-switch(로컬 Anthropic 호출 0).
    Return True when DOC_REVIEW_GATE_DISABLED is truthy — cost kill-switch (zero local Anthropic calls)."""
    return os.environ.get("DOC_REVIEW_GATE_DISABLED", "").strip().lower() in ("1", "true", "yes")


# ─── 거부권 매트릭스 ──────────────────────────────────────────────────────────
# Veto matrix


# 게이트가 인정하는 판정값. 이 밖의 값(또는 키 부재)은 **판정이 아니라 부재**다.
# Decisions the gate accepts; anything else (or a missing key) is an absence, not a verdict.
_LEGAL_DECISIONS = ("approve", "warn", "block")


def _inoperative(agent: str, reason: str, detail: str = "") -> dict:
    """심의가 **일어나지 않은** 결과를 만든다 — 승인과 같은 값을 가질 수 없다 (R35/R36).

    🔴 이 저장소의 지배 결함: "아무것도 심의하지 못했다" 와 "심의해서 통과시켰다" 가
    같은 값(`approve`)이었다. `inoperative` 표기가 그 등가를 깬다 — 판정 축(`decision`)은
    `warn` 으로 두어 편집을 차단하지 않되(정책 17 안정성), 관측 축은 분리한다.
    Marks a result as *not reviewed*: warn on the decision axis (never blocks edits) but
    carries a separate observability flag so it can never be read as an approval.
    """
    return {"agent": agent, "decision": "warn", "inoperative": True,
            "reason": reason, "detail": detail}


def apply_veto_matrix(
    grade: str,
    results: list[dict],
) -> tuple[str, list[str]]:
    """에이전트 결과와 파일 등급을 조합해 최종 결정을 반환한다.
    Combines agent results and file grade to return the final decision.

    Returns (decision, reasons):
      decision — "block" | "warn" | "approve"
      reasons  — 사람이 읽을 수 있는 사유 목록 / human-readable reason list
    """
    block_reasons: list[str] = []
    warn_reasons: list[str] = []

    # 🔴 결과가 0건이면 심의가 일어나지 않은 것이다 — approve 로 떨어뜨리지 않는다 (R35).
    # Zero results means no review happened; it must not fall through to approve.
    if not results:
        return "warn", ["[doc-review-gate] 심의 결과 0건 — 아무 에이전트도 판정하지 않았다"]

    for r in results:
        agent = r.get("agent", "unknown")
        decision = r.get("decision")
        reason = r.get("reason", "")

        # 🔴 미심의(`inoperative`) · 판정 키 부재 · 범례 밖 값은 전부 **부재**로 다룬다 (R35).
        #    이전 판의 `r.get("decision", "approve")` 는 스키마 drift 를 조용히 승인으로 바꿨다
        #    (Grok `019fc81b` GROK-6: 키 누락 · `"maybe"` · 빈 결과가 모두 approve).
        # Missing/unknown decisions and inoperative results are absences, never approvals.
        if r.get("inoperative") or decision not in _LEGAL_DECISIONS:
            if decision not in _LEGAL_DECISIONS:
                reason = reason or f"판정값 부재/불명({decision!r}) — 미심의"
            warn_reasons.append(f"[{_agent_label(agent)}] {reason}")
            continue

        if decision not in ("warn", "block"):
            continue

        if decision == "block":
            if agent == "impact":
                # impact-analyzer: 모든 등급 차단 / blocks every grade
                block_reasons.append(f"[impact-analyzer] {reason}")
            elif agent == "consistency" and grade == "critical" and r.get("unable_to_verify") is not True:
                # consistency-reviewer: critical 등급에서만 차단 / blocks only for critical
                # 🔴 단, **근거를 못 봐서 낸 block 은 강등**한다 (R37-b — 회고 2026-08-04).
                #    `important` 경로엔 이미 강등이 있었는데 `critical` 에만 없어서, 6-step ⑤
                #    (STATE 수치 동기화)라는 **의무 절차**가 차단될 수 있었다. "확인 불가" 는
                #    불일치의 증거가 아니다 — 증거 부재를 차단 근거로 쓰면 게이트가 절차를 막는다.
                #    impact-analyzer 는 이 강등 대상이 아니다(행동 변화 위험 = 가드 자살 방지).
                #    🔴 `is True` 만 인정한다 — Grok `019fc878` GROK-2 재현 적발: 진리값
                #    검사(`not r.get(...)`)는 LLM 스키마 drift 로 흔한 **문자열 `"false"`**
                #    를 참으로 읽어 **실제 불일치 block 까지 강등**했다(실측). 부재·False·
                #    비-불리언은 전부 '확인함' 으로 다룬다 (fail-closed 방향).
                # Blocks raised because the reviewer could not see the evidence are demoted:
                # absence of evidence is not evidence of mismatch.
                block_reasons.append(f"[consistency-reviewer] {reason}")
            else:
                # 그 외: 경고로 강등 / demote to warning
                warn_reasons.append(f"[{_agent_label(agent)}] {reason}")
        else:  # warn
            warn_reasons.append(f"[{_agent_label(agent)}] {reason}")

    if block_reasons:
        return "block", block_reasons + warn_reasons
    if warn_reasons:
        return "warn", warn_reasons
    return "approve", []


def _agent_label(agent: str) -> str:
    """에이전트 이름을 표시용 라벨로 변환한다.
    Convert agent name to display label."""
    labels = {
        "impact": "impact-analyzer",
        "consistency": "consistency-reviewer",
        "quality": "quality-reviewer",
    }
    return labels.get(agent, agent)


# ─── Claude API 병렬 호출 ─────────────────────────────────────────────────────
# Parallel Claude API calls

_HOOKS_DIR = Path(__file__).parent
_AGENTS_DIR = _HOOKS_DIR.parent / "agents"
_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_AGENT_NAMES = ("impact", "consistency", "quality")
_AGENT_TIMEOUT = 25  # seconds per agent
_DIFF_BUDGET = 4000  # 프롬프트에 싣는 diff 최대 길이(자) / max diff chars in the prompt


# ─── 자격증명 전제 ───────────────────────────────────────────────────────────
# Credential precondition — the gate cannot review anything without one.

def _dotenv_value(name: str) -> str:
    """리포 `.env` 에서 값을 읽는다 — 없거나 못 읽으면 빈 문자열(fail-soft).

    🔴 훅은 앱과 달리 pydantic `Settings` 를 쓰지 않아 `.env` 를 읽지 않는다.
    파서는 최소한이지만 **실제 `.env` 에서 흔한 형태**는 처리해야 한다. 안 그러면
    "키가 있는데 없다고 말하는" 반대 방향의 거짓말이 된다:
      · `export NAME=v` 접두사 · UTF-8 BOM · 인라인 `# 주석` · 중복 키(셸과 같이 **마지막**이 이김)
    (2026-08-01 Grok claim-review `019fbb2d` 가 4형태 전부 실측 재현.)
    Minimal .env parsing that still handles the shapes real .env files actually use.
    """
    env_file = _HOOKS_DIR.parent.parent / ".env"
    try:
        text = env_file.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        # 부재·권한·디렉토리 — 훅이 죽으면 안 된다(advisory).
        # Missing / permission / is-a-directory: the hook must not die.
        return ""
    found = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        if not sep or key.strip() != name:
            continue
        value = value.strip()
        if value[:1] in ("'", '"') and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]        # 따옴표 안은 주석이 아니다 / quoted value keeps '#'
        else:
            value = value.split("#", 1)[0].strip()
        found = value                  # 마지막 할당이 이긴다 / last assignment wins
    return found


def _lookup_credential(name: str) -> str:
    """환경변수 우선, 없으면 `.env`. / Environment first, then `.env`."""
    return os.environ.get(name, "").strip() or _dotenv_value(name)


def _api_key() -> str:
    """`ANTHROPIC_API_KEY` 해소값. / Resolved API key."""
    return _lookup_credential("ANTHROPIC_API_KEY")


def _credentials() -> dict:
    """Anthropic 클라이언트에 넘길 자격증명 kwargs — 없으면 빈 dict.

    🔴 **선점검과 클라이언트가 같은 원천을 봐야 한다.** 이전 판은 `_api_key()` 로 선점검만
    하고 클라이언트는 `os.environ.get("ANTHROPIC_API_KEY", "")` 를 따로 읽었다. 그래서 키가
    `.env` 에만 있으면 **선점검은 통과(배너 없음) · 클라이언트는 빈 키** → 3 에이전트가
    "에이전트 호출 실패" 로 떨어지는 **원래의 무음 경로**로 되돌아갔다. 이 PR 이 도우려던
    바로 그 사용자 계층에서, 배너까지 사라진 더 나쁜 상태다
    (Grok claim-review `019fbb2d` 적발 — 내가 observer-lie 수정을 쓰면서 observer-lie 를 만듦).
    Preflight and client must read the SAME source; previously they diverged on `.env`.

    `ANTHROPIC_AUTH_TOKEN` 도 인정한다 — SDK 가 받는 자격증명인데 모델에서 빠져 있으면
    올바로 설정된 머신에 INOPERATIVE 오경보를 낸다(가드 자살 방향).
    """
    key = _lookup_credential("ANTHROPIC_API_KEY")
    if key:
        return {"api_key": key}
    token = _lookup_credential("ANTHROPIC_AUTH_TOKEN")
    if token:
        return {"auth_token": token}
    return {}


# 자격증명이 없을 때의 배너 — **일시 오류와 구별되는 문구**여야 한다.
# 🔴 실측 사고 (2026-08-01): 키가 없으면 3 에이전트가 전부
#    `{"decision": "warn", "reason": "에이전트 호출 실패"}` 를 반환하고 veto 가 `warn` 으로
#    떨어져 **exit 0**. 즉 CRITICAL 등급 문서 게이트가 **배선돼 있고 · 실행되고 · 출력도 내면서
#    아무것도 심의하지 않는다.** 그런데 그 문구는 네트워크 blip 과 똑같이 읽힌다 —
#    "이 게이트는 구조적으로 죽어 있다" 는 정보가 어디에도 없었다.
#    가드가 틀린 게 아니라 **실행 전제가 없는** 클래스(`make` 부재와 동형).
# Without a key all three agents fail identically to a transient error, so nothing distinguishes
# "the gate is structurally inoperative" from "one call blipped". This banner does.
_NO_CREDENTIALS_BANNER = (
    "\n"
    "[doc-review-gate] 🔴 INOPERATIVE - no Anthropic credentials\n"
    "  This gate reviewed NOTHING. It is not a transient failure: without a key the\n"
    "  three review agents cannot be called at all, so every document change passes.\n"
    "  Set ANTHROPIC_API_KEY (environment or .env) to arm it; ANTHROPIC_AUTH_TOKEN works too.\n"
    "  Advisory by design - a missing local credential must not block edits.\n"
)


def _emit_advisory(message: str) -> None:
    """차단하지 않는 고지를 **양 채널**로 내보낸다 — Claude(에이전트) + 사용자(터미널).

    🔴 실측 사고 (2026-08-01): 이 훅의 advisory 는 전부 plain `print()` 였다. 공식 훅 계약상
    **PreToolUse 의 plain stdout 은 Claude 에게 전달되지 않는다** — 디버그 로그로만 간다.
    plain stdout 이 Claude 컨텍스트가 되는 이벤트는 `UserPromptSubmit`·`UserPromptExpansion`·
    `SessionStart` **셋뿐**이다. 실측으로도 CRITICAL 문서 3회 편집에서 배너가 한 번도
    에이전트 도구 결과에 나타나지 않았다. 즉 이 고지는 **theatre** 였다.

    올바른 채널 (공식 문서 확인 + Grok claim-review `019fbb65`):
      · `hookSpecificOutput.additionalContext` → **Claude** 가 보는 컨텍스트
      · `systemMessage`                        → **사용자** 터미널에 보이는 경고

    🔴 `permissionDecision` 은 **설정하지 않는다.** `additionalContext` 는 그것과 독립이며,
    `"allow"` 를 넣으면 사용자 권한 확인을 건너뛸 수 있다(advisory 고지에 권한 우회를 얹는
    것은 명백한 안전 결함). 미설정 = 정상 권한 흐름 유지.

    Advisory notices must go through additionalContext (Claude) + systemMessage (user);
    PreToolUse plain stdout never reaches Claude. permissionDecision is deliberately omitted.
    """
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": message.strip(),
        },
        "systemMessage": message.strip(),
    }
    # 🔴 ensure_ascii=True 의무 — Windows cp949 stdout 에서 비-ASCII 가 훅을 죽인다(#1243).
    # ensure_ascii is mandatory: non-ASCII crashes the hook on Windows cp949 stdout.
    print(json.dumps(payload, ensure_ascii=True))


def _read_agent_prompt(agent: str) -> str:
    """에이전트 .md 파일에서 시스템 프롬프트를 읽는다 (YAML frontmatter 제거).
    Reads system prompt from agent .md file, stripping YAML frontmatter."""
    suffix = "analyzer" if agent == "impact" else "reviewer"
    md_file = _AGENTS_DIR / f"doc-{agent}-{suffix}.md"
    if not md_file.exists():
        return f"당신은 문서 {agent} 검토자입니다. JSON {{decision, reason, detail}}으로 응답하세요."
    content = md_file.read_text(encoding="utf-8")
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:].strip()
    return content


def _scrub_surrogates(text: str) -> str:
    """UTF-8 로 인코딩 불가한 lone surrogate 를 제거한다 (R36-b).

    Windows 에서 stdin/파일 경유로 들어온 문자열에 짝 없는 서로게이트(U+D800~U+DFFF)가
    섞이면 `str` 로는 멀쩡해 보이지만 **전송 시점**에 `UnicodeEncodeError` 로 터진다.
    실패가 HTTP 계층에서 나므로 3 에이전트가 동시에 죽고, 그 모양이 "네트워크 blip" 과
    구별되지 않는다 — 이 리포가 2 세션 동안 겪은 무동작의 정체다.

    `errors="replace"` 로 왕복시켜 인코딩 가능한 문자열만 남긴다(정보 손실 < 게이트 사망).
    Round-trips through UTF-8 so only encodable characters survive.
    """
    return text.encode("utf-8", errors="replace").decode("utf-8")


def result_schema(agent: str) -> dict:
    """에이전트 응답의 JSON Schema — 구조화 출력(`output_config.format`)용 (R51).

    🔴 **이 리포가 기록해 온 스키마 drift 의 재발 동인을 API 층에서 닫는다.** 기록된
    실측 사고: 키 누락 · `"maybe"` 같은 범례 밖 값 · 진리값 자리의 문자열 `"false"`
    (Grok `019fc81b` GROK-6 · `019fc878` GROK-2). 프롬프트로 "JSON 만 출력하라" 고
    부탁하는 것과, **스키마를 강제**하는 것은 다르다.

    🔴 **기존 방어를 지우지 않는다** — 구조화 출력이 닫는 것은 *스키마* 축이고,
    응답 절단(`stop_reason=max_tokens`)·호출 실패·빈 결과는 **그대로 열려 있다**(R35/R36).
    이 스키마는 방어를 대체하지 않고 재발 동인 하나를 제거할 뿐이다.
    Structured outputs close the schema-drift axis only; truncation and call failure remain.

    🔴 제약(문서 계약): 모든 object 는 `additionalProperties: false` + `required` 필수.
    `minLength` 같은 수치/문자열 제약은 미지원이라 쓰지 않는다.

    consistency 만 `unable_to_verify` 를 싣는다 — 그 에이전트의 프롬프트 계약이고
    (`.claude/agents/doc-consistency-reviewer.md`), 다른 둘에 강제하면 프롬프트에 없는
    필드를 만들라고 시키는 셈이 된다.
    """
    props: dict = {
        "decision": {"type": "string", "enum": list(_LEGAL_DECISIONS)},
        "reason": {"type": "string"},
        "detail": {"type": "string"},
    }
    if agent == "consistency":
        props["unable_to_verify"] = {"type": "boolean"}
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


def corrupted(text: str) -> bool:
    """디코드 손상 여부 — U+FFFD **또는** lone surrogate.

    🔴 둘 다 봐야 한다. `errors="replace"` 는 잘못된 바이트를 U+FFFD 로 바꾸지만,
    JSON 의 `\\uD800` 형태 이스케이프는 `json.loads` 를 그대로 통과해 **서로게이트로**
    남고, 나중에 `_scrub_surrogates` 가 U+FFFD 로 바꾼다. 즉 U+FFFD 만 검사하면 그
    경로는 검사 시점에 아직 보이지 않아 놓친다 (Grok `019fcd57` 적발).
    Check both: replacement chars, and lone surrogates that only become U+FFFD later.
    """
    return "�" in text or any("\ud800" <= ch <= "\udfff" for ch in text)



def _first_text_block(msg: object) -> str:
    """응답에서 **첫 text 블록**을 꺼낸다 — `content[0].text` 직접 접근 금지 (R61).

    🔴 `content` 는 블록 **배열**이고 thinking·tool_use 가 앞설 수 있다. 첫 블록이 text 라고
    가정하면 그 순간 `AttributeError` 가 나는데, 이 호출은 broad except 안이라 **조용히
    실패**하고 심의가 통째로 죽는다(2026-08-06 회고 P1).

    🔴 `src.shared.anthropic_caching.first_text_block` 과 **의도적 중복**이다 — 훅은
    standalone 실행(`python .claude/hooks/x.py`)이라 `src` 를 import 할 수 없다.
    양쪽이 갈라지지 않도록 `tests/unit/shared/test_anthropic_first_text_block.py` 의
    `test_hook_duplicate_matches_the_src_helper_behaviour` 가 동작 동등성을 고정한다.
    🔴 초판은 존재하지 않는 경로(`tests/unit/hooks/...`)를 가리켰다 — Grok claim-review 적발.
    Deliberate duplicate of the src helper: hooks run standalone and cannot import `src`.
    """
    for block in (getattr(msg, "content", None) or []):
        btype = getattr(block, "type", None)
        text = getattr(block, "text", None)
        # 🔴 판별 순서가 중요하다: **명시적으로 비-text 라고 선언한 블록만** 건너뛰고,
        #    나머지는 `.text` 가 문자열인지로 받는다. `btype is None` 만 허용하면
        #    `MagicMock` 목(`.type` 이 자동 생성돼 None 이 아니다)이 전부 탈락한다 —
        #    실제로 기존 테스트 20건이 이 과엄격을 잡았다.
        # Skip only blocks that explicitly declare a non-text type; otherwise duck-type on
        # `.text` being a str. A `btype is None` check alone would reject MagicMock stubs.
        if isinstance(btype, str) and btype != "text":
            continue
        if isinstance(text, str):
            return text
    raise ValueError("Anthropic 응답에 text 블록이 없다")


def cache_usage(msg) -> dict:
    """응답의 캐시 회계를 뽑는다 — `{"write": n, "read": n}`.

    🔴 이 값이 없으면 캐시가 **조용히 죽어도 아무도 모른다**. 실제 위험 경로:
    `_CONTEXT_SOURCES` 예산을 줄여 프리픽스가 claude-haiku-4-5 의 최소 캐시 길이
    (4096 토큰) 아래로 내려가면, API 는 오류를 내지 않고 그냥 캐시하지 않는다
    (Grok `019fcd10` 지적 — 신규 테스트가 usage 를 전혀 보지 않았다).
    Without this the cache can die silently — the API does not error below the minimum.
    """
    u = getattr(msg, "usage", None)
    return {
        "write": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "read": getattr(u, "cache_read_input_tokens", 0) or 0,
    }


def cache_looks_dead(results: list[dict]) -> bool:
    """캐시 회계를 보고 **한 번도 캐시되지 않았는지** 판정한다.

    쓰기도 읽기도 0 이면 프리픽스가 아예 캐시 대상이 아니었다는 뜻이다(최소 길이 미달
    등). 회계가 하나도 없으면(전건 호출 실패) 판정하지 않는다 — 그 상황은 R36 배너 소관이고,
    여기서 단정하면 **다른 고장을 캐시 고장으로 오진**한다.
    Only claims death when at least one call actually reported usage.
    """
    # 🔴 opt-out 은 고장이 아니다 — `DISABLE_PROMPT_CACHE=1` 이면 마커를 일부러 떼므로
    #    회계가 0/0 인 것이 정상이다. 이 분기가 없으면 **의도한 설정을 사고로 보고**한다
    #    (Grok `019fcd57` verdict-B 적발).
    # Opting out is not a failure: 0/0 is the expected accounting when markers are removed.
    if prompt_cache_disabled():
        return False
    seen = [r["_usage"] for r in results if isinstance(r.get("_usage"), dict)]
    return bool(seen) and all(u["write"] == 0 and u["read"] == 0 for u in seen)


def prompt_cache_disabled() -> bool:
    """DISABLE_PROMPT_CACHE=1 시 True — 앱(`src/shared/anthropic_caching.py`)과 같은 opt-out.
    Same opt-out switch the app uses, so one env var disables caching everywhere."""
    return os.environ.get("DISABLE_PROMPT_CACHE", "").strip().lower() in ("1", "true", "yes")


def build_system_blocks(context: str, agent_prompt: str, volatile_context: str = "") -> list[dict]:
    """system 인자 = [공유 컨텍스트(캐시 breakpoint), 에이전트별 지시].

    🔴 **순서가 절반이다.** 캐시는 프리픽스 매칭이라, 캐시하려는 부분이 **가변 부분보다
    앞**에 있어야 한다. 3 에이전트가 공유하는 것은 컨텍스트뿐이고(에이전트 지시는 서로
    다르다), 매 편집마다 달라지는 것은 diff 다. 그래서:
        system[0]  = 안정 컨텍스트  ← breakpoint 1 (3 에이전트 · 연속 편집이 함께 재사용)
        system[1]  = 가변 컨텍스트  ← breakpoint 2 (`volatile_context` 가 있을 때만 존재)
        system[-1] = 에이전트별 지시 (항상 마지막 — volatile 유무로 index 가 1↔2 로 바뀐다)
        user       = diff (캐시 밖)
    이전 판은 diff 를 user 맨 앞에 두고 컨텍스트를 그 뒤에 뒀다 — 그 배치는
    `cache_control` 을 붙여도 **원리적으로 히트가 불가능**하다.

    Ordering is half the fix: the shared, stable context must precede the per-edit diff.

    🔴 렌더 순서는 `tools → system → messages` 이고 `cache_control` 은 **그 블록까지의
    프리픽스 전체**를 캐시한다. 따라서 breakpoint 를 system[0] 에 걸면 캐시 구간은
    정확히 '컨텍스트' 하나이고, 3 에이전트가 **같은 캐시 항목 하나**를 공유한다.
    (system[1] 에 걸면 에이전트마다 별개 항목이 되어 공유가 깨진다.)

    🔴 최소 캐시 길이 = **4096 토큰**(claude-haiku-4-5 — 전 모델 중 가장 큰 값). 미달이면
    오류 없이 조용히 캐시되지 않는다. 실측 컨텍스트 53,587자로 여유 있게 상회한다 —
    `_CONTEXT_SOURCES` 예산을 줄일 때 이 하한을 함께 확인할 것.

    opt-out: `DISABLE_PROMPT_CACHE=1` (cache_control 미부착).
    """
    cache_on = not prompt_cache_disabled()
    blocks: list[dict] = [{"type": "text", "text": f"## 참조 컨텍스트\n{context}"}]
    if cache_on:
        blocks[0]["cache_control"] = {"type": "ephemeral"}
    # 🔴 가변 원천(STATE.md)은 **별도 블록 + 자체 breakpoint**. 두 번째 breakpoint 덕에
    #    STATE 가 바뀐 편집에서도 앞의 안정 블록은 그대로 히트하고, 재처리 범위가
    #    전체 ≈34.7k 에서 STATE 분(≈10k)으로 줄어든다. 안 바뀐 편집에서는 둘 다 히트해
    #    이전과 동일하다 — 즉 어느 쪽으로도 나빠지지 않는다 (Grok `019fcd10` 잔여 (2)).
    #    breakpoint 는 요청당 최대 4개이고 여기서는 2개를 쓴다.
    # Second breakpoint after the volatile source: a STATE edit no longer invalidates the
    # stable prefix, and a non-STATE edit still hits both. Strictly better in both cases.
    if volatile_context:
        vol: dict = {"type": "text", "text": f"## 참조 컨텍스트 (변동)\n{volatile_context}"}
        if cache_on:
            vol["cache_control"] = {"type": "ephemeral"}
        blocks.append(vol)
    blocks.append({"type": "text", "text": agent_prompt})
    return blocks


async def _call_single_agent(
    client,
    agent: str,
    diff: str,
    context: str,
    volatile_context: str = "",
) -> dict:
    """에이전트 한 개를 호출하고 JSON 결과를 반환한다.
    Calls a single agent and returns a JSON result dict."""
    # 🔴 lone surrogate 정화 — 이것이 게이트를 2 세션 동안 죽여 온 실제 원인이다 (R36-b).
    #    2026-08-04 라이브: R36 이 예외 원문을 노출하자마자 9회+ 반복된 "에이전트 호출 실패" 가
    #    자격증명 축이 아니라 `'utf-8' codec can't encode characters … surrogates not allowed`
    #    였음이 드러났다. httpx 가 요청 본문을 인코딩할 때 터지므로 **3 에이전트가 동시에** 죽고,
    #    원장은 엉뚱하게 "키 만료/크레딧 재확인" 을 요청하고 있었다.
    # Sanitise lone surrogates: this is what actually killed the gate for two sessions.
    system_prompt = _scrub_surrogates(_read_agent_prompt(agent))
    diff = _scrub_surrogates(diff)
    context = _scrub_surrogates(context)
    # 🔴 프롬프트 캐시 — 렌더 순서는 tools → system → messages 이고, cache_control 은
    #    **그 블록까지의 프리픽스 전체**를 캐시한다. 그래서 3 에이전트가 공유하는
    #    컨텍스트를 system 첫 블록에 두고 거기에 breakpoint 를 건다 (R38).
    # Cache the shared context as the first system block: the cached prefix then contains
    # exactly the part all three agents have in common.
    system_blocks = build_system_blocks(context, system_prompt,
                                        _scrub_surrogates(volatile_context))
    # 🔴 `context` 를 여기서 다시 자르지 않는다 — 예산은 `_load_context()` 가 **파일별로**
    #    한 번만 적용하고 라벨에 비율을 적는다. 이중 절단이 CLAUDE.md 를 10.8% 로 깎고
    #    STATE.md 를 통째로 지우면서도 헤더는 둘 다 있다고 말했다(2026-08-01 실측).
    # Do not re-truncate: the budget is applied once, per source, and labelled there.
    # 🔴 컨텍스트는 system 으로 옮겼다 — user 에는 **매번 달라지는 diff 만** 남긴다.
    #    캐시는 프리픽스 매칭이라 가변 부분이 앞에 있으면 그 뒤가 전부 무효화된다.
    # The varying diff must come after the cached prefix, or nothing caches.
    user_msg = (
        f"## 변경 내용 (diff)\n{diff[:_DIFF_BUDGET]}\n\n"
        "위 변경을 검토하고 JSON으로만 응답하세요."
    )
    try:
        msg = await asyncio.wait_for(
            client.messages.create(
                model=_HAIKU_MODEL,
                max_tokens=512,
                system=system_blocks,
                # 🔴 스키마 강제 (R51) — 프롬프트로 부탁하는 대신 API 가 형식을 보장한다.
                #    닫히는 것은 **스키마 축뿐**이고 절단·호출실패는 아래 방어가 계속 맡는다.
                # Enforce the schema at the API layer; truncation/failure axes stay guarded.
                output_config={
                    "format": {"type": "json_schema", "schema": result_schema(agent)}
                },
                messages=[{"role": "user", "content": user_msg}],
            ),
            timeout=_AGENT_TIMEOUT,
        )
        usage = cache_usage(msg)
        text = _first_text_block(msg)
        # 🔴 응답이 출력 예산에서 잘렸으면 그것은 **판정이 아니다** (R35 — 회고 2026-08-04 P0).
        #    이전 판은 `stop_reason` 을 읽지 않고 잘린 JSON 을 파싱 실패로 흘려보낸 뒤
        #    `approve` 로 바꿨다. 출력 예산은 고정인데 리뷰어가 할 말은 위험할수록 길어지므로,
        #    **심각도와 fail-open 확률이 정비례**했다. Grok `019fc81b` GROK-1 이 로컬 재현.
        # A truncated reply is not a verdict: the old code turned it into an approval, so the
        # more a reviewer had to say, the likelier the gate passed it silently.
        if getattr(msg, "stop_reason", None) == "max_tokens":
            return {**_inoperative(agent, "응답 절단(max_tokens) — 미심의", text[:200]),
                    "_usage": usage}
        # 코드 블록 추출 우선, 없으면 전체 텍스트에서 JSON 파싱 시도
        # Prefer code block extraction; fall back to parsing the full text
        code_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        candidate = code_match.group(1).strip() if code_match else text.strip()
        try:
            parsed = json.loads(candidate)
            parsed["agent"] = agent
            parsed["_usage"] = usage
            return parsed
        except (json.JSONDecodeError, ValueError):
            # 🔴 파싱 실패 = 심의 결과를 **받지 못한 것**이다. 승인이 아니다 (R35).
            # Parse failure means no verdict was received — that is not an approval.
            return {**_inoperative(agent, "응답 파싱 실패 — 미심의", text[:200]),
                    "_usage": usage}
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # 🔴 예외 원문(`detail`)을 보존한다 — 세션14 가 8회+ 겪은 전건 실패의 원인을
        #    아무도 몰랐던 이유가 이 문자열이 출력에서 버려졌기 때문이다 (R36).
        # Preserve the exception text: it was dropped from output, which is why 8+ identical
        # failures in session 14 had no diagnosable cause.
        return _inoperative(agent, "에이전트 호출 실패", str(exc))


async def call_agents_parallel(grade: str, diff: str, context: str,
                               volatile_context: str = "") -> list[dict]:
    """3개 에이전트를 병렬로 호출하고 결과 목록을 반환한다.
    Calls all three agents in parallel and returns a list of result dicts."""
    # 🔴 선점검과 **같은 원천**을 쓴다 — 갈라지면 `.env` 전용 키가 조용히 죽는다(위 `_credentials`).
    # Same source as the preflight; divergence silently killed `.env`-only keys.
    client = anthropic.AsyncAnthropic(**_credentials())
    tasks = [_call_single_agent(client, agent, diff, context, volatile_context)
             for agent in _AGENT_NAMES]
    raw = await asyncio.gather(*tasks, return_exceptions=False)
    return list(raw)


# ─── 컨텍스트 로드 ────────────────────────────────────────────────────────────
# Context loading

# 컨텍스트 원천과 **파일별** 예산(자). 규칙을 담은 문서는 전문이 들어가도록 잡는다.
# Per-source budgets, sized so the rule documents fit whole.
_CONTEXT_SOURCES: tuple[tuple[str, int], ...] = (
    ("CLAUDE.md", 40000),     # 27.8k — 전문 (정책 1~19 가 여기 있다)
    ("AGENTS.md", 12000),     # 5.3k  — 전문 (가드 3-불변식 SSOT)
    # 🔴 4000 → 16000 (R37-a, 회고 2026-08-04). 이전 예산은 STATE.md 의 **4%** 만 실어
    #    형식 `**종합 수치**` 블록(offset ~11.1k)과 pylint 값(~11.2k)이 통째로 잘렸다.
    #    그 상태로 consistency 에이전트에게 "STATE 수치와 다르면 block" 을 지시하는 것은
    #    **볼 수 없는 것을 근거로 차단하라**는 모순이다.
    #    ⚠️ 주 카운트(6607·6778)는 원래도 예산 안이었다(offset 3023·3105) — Grok `019fc81b`
    #    GROK-4 가 "심의자가 대조 대상 자체를 못 본다" 는 원 서술을 반증했다. 실제는 **부분 실명**.
    # Raised so the formal aggregate block and pylint value fit; the primary counts always did.
    ("docs/STATE.md", 16000),  # 91k
)


def _load_context() -> str:
    """규칙 문서를 에이전트 컨텍스트로 읽는다 — 잘리면 **얼마나 잘렸는지 적는다**.

    🔴 **이전 판은 심의자를 규칙에 대해 눈멀게 했다** (2026-08-01 근본원인 분석 실측).
    `content[:3000]` 로 파일마다 자른 뒤, 프롬프트가 **합친 문자열을 다시 3000자로**
    잘랐다(이중 절단). 실효 결과:

    - CLAUDE.md **10.8%** 만 도달 — 링크 중간에서 끊겨 **정책 1~19 를 단 한 줄도 못 봤다**
    - docs/STATE.md **0% 도달** — 그런데 프롬프트 헤더는 `(CLAUDE.md / STATE.md)` 라고
      적혀 있었다. 심의자에게 **없는 근거를 있다고 말한** 셈이다(observer-lie).

    "문서가 길어서 규칙이 안 지켜진다" 가 기계 층에서 실제로 발현한 유일한 지점이다.
    사람/Claude 의 읽기가 아니라 **심의 에이전트의 입력**이 길이로 잘려 있었다.

    이제 (a) 규칙 문서는 전문을 넣고 (b) 잘릴 때는 비율을 라벨에 적어 심의자가
    "못 본 부분이 있다" 를 알 수 있게 한다.
    Rule documents are passed whole; any truncation states its own coverage in the label.
    """
    return "\n\n".join(text for _rel, text in load_context_parts())


# 🔴 편집마다 바뀌는 원천 — 캐시 프리픽스에서 **분리**한다 (Grok `019fcd10` 잔여 (2)).
#    STATE.md 는 trailing sync 마다 바뀌므로 한 덩어리에 섞으면 그 한 번의 편집이
#    안정 원천(CLAUDE.md·AGENTS.md ≈24.7k 토큰)까지 통째로 무효화한다.
# Sources that change often; kept out of the stable cache block.
_VOLATILE_SOURCES: frozenset[str] = frozenset({"docs/STATE.md"})


def load_context_parts() -> list[tuple[str, str]]:
    """`(상대경로, 렌더된 텍스트)` 목록 — 호출부가 안정/가변 원천을 나눌 수 있게 한다.

    문자열 하나로 합쳐 돌려주면 호출부가 그 문자열을 **다시 파싱**해야 나눌 수 있고,
    그건 자기 출력 형식에 의존하는 취약한 결합이다. 그래서 나누기 전 형태로 준다.
    Returns parts so callers can split stable/volatile without re-parsing our own output.
    """
    project_root = _HOOKS_DIR.parent.parent
    parts: list[tuple[str, str]] = []
    for rel, budget in _CONTEXT_SOURCES:
        path = project_root / rel
        if not path.exists():
            # 침묵 누락 금지 — 없으면 없다고 말한다 / never drop a source silently
            parts.append((rel, f"=== {rel} — 파일 없음(이 근거 없이 판정됨) ==="))
            continue
        content = path.read_text(encoding="utf-8")
        if len(content) <= budget:
            parts.append((rel, f"=== {rel} (전문 {len(content)}자) ===\n{content}"))
        else:
            pct = budget / len(content)
            parts.append((rel, (
                f"=== {rel} (앞 {budget}자 / 전체 {len(content)}자 = {pct:.0%}만 포함, "
                f"나머지는 못 봄) ===\n{content[:budget]}"
            )))
    return parts


def split_context() -> tuple[str, str]:
    """컨텍스트를 `(안정, 가변)` 으로 나눈다 — 캐시 무효화 범위를 줄이기 위해.

    가변 원천(`_VOLATILE_SOURCES`)이 바뀌어도 안정 블록의 캐시는 살아남는다.
    반대로 가변 원천을 아예 빼면 심의자가 STATE 수치 정합을 못 보게 되므로(R37 이
    되돌린 축) 빼지 않고 **분리만** 한다.
    Split rather than drop: dropping STATE would blind the consistency reviewer.
    """
    parts = load_context_parts()
    stable = "\n\n".join(t for rel, t in parts if rel not in _VOLATILE_SOURCES)
    volatile = "\n\n".join(t for rel, t in parts if rel in _VOLATILE_SOURCES)
    return stable, volatile


# ─── 출력 포맷 ────────────────────────────────────────────────────────────────
# Output formatting

def _format_block(file_path: str, results: list[dict], reasons: list[str]) -> str:
    """차단 시 표시할 메시지를 조립한다.
    Assembles the block message shown when a change is denied."""
    lines = [
        f"[문서 심의] {Path(file_path).name} — 차단",
        "",
    ]
    for r in results:
        if r["decision"] == "block":
            icon = "[X]"
        elif r["decision"] == "warn":
            icon = "[!]"
        else:
            icon = "[OK]"
        lines.append(f"  {icon} {_agent_label(r['agent'])}: {r['reason']}")
    lines += ["", "차단 사유:"]
    for reason in reasons:
        lines.append(f"  • {reason}")
    lines += ["", "수정 방향을 조정한 후 다시 시도하세요."]
    return "\n".join(lines)


def _format_inoperative(file_path: str, results: list[dict]) -> str:
    """🔴 전건 미심의 배너 — '3명이 경고하며 심의함' 과 **문구가 달라야** 한다 (R36).

    세션14 가 8회+ 실제로 앉아 있던 상태다(자격증명은 있고 **호출**이 죽은 축).
    `#1257` 은 자격증명 **부재** 분기만 봉인해서, 정작 발생한 분기는 정상 warn 과
    구별되지 않은 채 남았다 — 그래서 게이트가 무동작이라는 사실이 원장에 오르지 못했다.
    문구는 `_NO_CREDENTIALS_BANNER` 와 같은 계열(`INOPERATIVE` / `REVIEWED NOTHING`)로 맞춘다.
    The all-agents-failed state must not read like a real three-agent verdict.
    """
    dead = [r for r in results if r.get("inoperative")]
    lines = [
        "",
        f"[doc-review-gate] 🔴 INOPERATIVE - REVIEWED NOTHING ({len(dead)}/{len(results)} agents)",
        f"  file: {Path(file_path).name}",
        "  This is NOT a verdict and NOT a transient blip: every review agent failed, so the",
        "  change passed without being reviewed. Fix the call path before trusting this gate.",
    ]
    for r in dead:
        lines.append(f"  [x] {_agent_label(r.get('agent', 'unknown'))}: {r.get('reason', '')}")
        detail = str(r.get("detail") or "").strip()
        if detail:
            # 🔴 실패 원문을 반드시 실어 보낸다 — 이게 없어서 8회+ 반복 실패의 원인을 몰랐다.
            # Carry the failure text: its absence is why 8+ repeats stayed undiagnosed.
            lines.append(f"      detail: {detail[:200]}")
    lines.append("  Advisory by design - a broken review path must not block edits.")
    return "\n".join(lines)


def _format_warn(file_path: str, results: list[dict], reasons: list[str]) -> str:
    """경고 시 표시할 메시지를 조립한다.
    Assembles the warning message shown before proceeding."""
    lines = [
        f"[문서 심의] {Path(file_path).name} — 경고 후 진행",
        "",
    ]
    for r in results:
        icon = "[!]" if r["decision"] == "warn" else "[OK]"
        lines.append(f"  {icon} {_agent_label(r['agent'])}: {r['reason']}")
    return "\n".join(lines)


# ─── Hook 진입점 ─────────────────────────────────────────────────────────────
# Hook entry point

def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지/한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji/Korean print crash on Windows (UTF-8, replace on miss).

    🔴 2026-08-01 정정 — 이 docstring 은 `warn` 분기가 **한글 원문을 그대로 출력**한다고
    적고 있었으나, 그 분기는 이제 `_emit_advisory` 를 거쳐 `ensure_ascii=True` JSON 으로
    나간다. 그래도 이 가드는 유지한다: 훅 진입 직후의 예외 traceback·argparse 오류 등
    **우리가 통제하지 않는 출력**이 여전히 cp949 stdout 을 통과해야 한다.
    훅은 standalone 실행이라 공유 헬퍼를 import 할 수 없어 검증된 관용구를 복제한다
    (scripts/check_dual_import.py 정본). 누락 방지 = test_stdout_encoding_guard.py.
    Retained for output we do not control (tracebacks, argparse), even though the advisory
    paths now emit ensure_ascii JSON.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / captured streams: ignore


def read_payload() -> dict:
    """stdin 을 **바이트로 읽어 UTF-8 로 직접 디코드**한 payload.
    Read stdin as bytes and decode UTF-8 explicitly.

    🔴 `json.load(sys.stdin)` 를 쓰면 안 된다. **실훅 자식 프로세스 계측 (2026-08-04)**:
    `stdin.encoding=cp949` · `stdin.errors=surrogateescape` · `utf8_mode=0` ·
    `PYTHONUTF8`/`PYTHONIOENCODING` 미설정. 즉 UTF-8 한글 payload 가 cp949 로 디코드된다.
    Measured in the real hook child process, not in a shell-spawned python.

    두 가지 결과가 겹친다:
      1. **mojibake** — `'문서 정합 가드'`(8자, U+BB38 U+C11C …) → 훅이 본 것 13자
         U+81FE U+BA84 U+AF4C. 심의 3 에이전트가 줄곧 이걸 읽었고, 결국 *"인코딩 오류로
         판독 불가"* 를 사유로 정당한 `.claude/rules/guards.md` 편집을 **차단**했다
         (가드가 자기 손상을 근거로 필수 절차를 막는 R37 클래스).
      2. 🔴 **lone surrogate 의 발생원** — `errors=surrogateescape` 라 cp949 로 디코드
         불가한 바이트가 U+DC80~U+DCFF 로 escape 된다. 실측: 같은 문자열에서 lone
         surrogate 6개 생성 → `.encode("utf-8")` 이 *"can't encode character '\\udcf0' …
         surrogates not allowed"*. `#1276` 이 2 세션을 죽였다고 기록한 그 예외이고,
         `_scrub_surrogates` 는 **증상**을 지웠다. 원인은 이 디코드였다.

    🔴 왕복 착시 주의: 잘못 디코드된 문자열을 같은 잘못된 인코딩으로 다시 출력하면 원
    바이트가 복원돼 **출력만 보면 정상으로 보인다**. 길이·코드포인트로 단언할 것.
    A wrong-decode → wrong-encode round trip restores the original bytes, so printed
    output looks fine; assert on length/codepoints instead.

    `sys.stdin.buffer` 가 없는 경우(테스트가 StringIO 로 교체)는 텍스트로 읽는다.
    Falls back to text mode when stdin has no binary buffer (tests patch it with StringIO).
    """
    raw = getattr(sys.stdin, "buffer", sys.stdin).read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    return json.loads(raw)


def main() -> None:
    """PreToolUse Hook 진입점 — stdin에서 payload 읽고 심의 결과 출력.
    PreToolUse hook entry point — reads payload from stdin and outputs review result."""
    _make_stdout_safe()
    # 비용 제어 — kill-switch 시 리뷰 없이 즉시 허용(sys.exit(0)=편집 통과, API 호출 0).
    # Cost control — when the kill-switch is on, allow the edit immediately with no review (no API call).
    if gate_disabled():
        sys.exit(0)

    try:
        data = read_payload()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # 🔴 payload 를 못 읽으면 심의는 **일어나지 않는다**. 이전 판은 그것을 조용한
        #    exit 0 으로 처리했다 — 편집은 통과하는데 아무도 그 사실을 몰랐다(R35/R36 클래스).
        #    차단은 하지 않는다(파일 경로조차 모르므로 판정 근거가 없고, 전 편집 차단은
        #    가드 자살이다 — 정책 17). 대신 **말한다**.
        # Never silently allow: we cannot review, so say so instead of exiting mute.
        _emit_advisory("[문서 심의] INOPERATIVE — payload 판독 실패로 심의하지 않음 "
                       f"(detail: {type(exc).__name__}: {exc})")
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = (tool_input.get("file_path", "") or "").replace("\\", "/")

    if not file_path:
        sys.exit(0)

    grade = classify_file_grade(file_path)
    if grade in ("skip", "low_risk"):
        sys.exit(0)

    # diff 구성 — Edit/Write 단일 변경 또는 MultiEdit 배열 모두 처리
    # Build diff — handles both single Edit/Write and MultiEdit edits[] array
    edits = tool_input.get("edits")
    if edits:
        chunks = []
        for i, e in enumerate(edits, 1):
            chunks.append(
                f"[편집 {i}]\n--- 이전 ---\n{e.get('old_string', '')}"
                f"\n+++ 이후 +++\n{e.get('new_string', '')}"
            )
        diff = f"파일: {file_path}\n\n" + "\n\n".join(chunks)
    else:
        old = tool_input.get("old_string", "") or ""
        new = tool_input.get("new_string", "") or tool_input.get("content", "") or ""
        diff = f"파일: {file_path}\n\n--- 이전 ---\n{old}\n\n+++ 이후 +++\n{new}"

    # 🔴 디코드 손상 감지 — `errors="replace"` 는 잘못된 바이트를 U+FFFD 로 바꾸므로
    #    **예외 없이** 손상된 텍스트가 심의에 들어갈 수 있다. 손상된 diff 를 정상 심의로
    #    취급하면 mojibake 사고(R49)의 조용한 재판이 된다 — 차단 대신 고지한다.
    # `errors="replace"` corrupts silently; announce it rather than reviewing garbage as if fine.
    if corrupted(diff):
        _emit_advisory("[문서 심의] DEGRADED — diff 에 디코드 손상(U+FFFD 또는 lone "
                       "surrogate)이 있어 심의자가 원문을 그대로 보지 못한다. "
                       "🔴 차단하지 않고 심의는 계속한다 — 손상 사실을 알린 뒤의 판정이므로 "
                       "판정을 그대로 신뢰하지 말 것")

    # 🔴 자격증명 선점검 — 없으면 심의는 **원리적으로 불가**하므로, 3 에이전트를 호출해
    #    똑같은 실패 3줄을 내는 대신 그 사실 자체를 말한다(위 배너 주석의 사고 참조).
    # Preflight: without credentials no review is possible, so say that instead of three
    # indistinguishable per-agent failures.
    if not _credentials():
        _emit_advisory(_NO_CREDENTIALS_BANNER)
        sys.exit(0)

    stable_context, volatile_context = split_context()
    results = asyncio.run(
        call_agents_parallel(grade, diff, stable_context, volatile_context)
    )
    decision, reasons = apply_veto_matrix(grade, results)

    # 🔴 캐시가 조용히 죽으면 비용이 조용히 10배가 된다 — 그 침묵을 깬다 (R38 잔여 (c)).
    # A silently dead cache is a silent 10x cost; break the silence.
    if cache_looks_dead(results):
        _emit_advisory("[문서 심의] 프롬프트 캐시 미동작 — 쓰기·읽기 모두 0. "
                       "프리픽스가 최소 캐시 길이(claude-haiku-4-5 = 4096 토큰) 아래로 "
                       "내려갔는지 `_CONTEXT_SOURCES` 예산을 확인할 것")

    # 🔴 전건 미심의는 판정 흐름을 타지 않는다 — 고유 배너로 그 사실 자체를 말한다 (R36).
    #    부분 미심의(1~2/3)는 아래 warn 경로가 사유 목록에 그대로 싣는다.
    # All-agents-inoperative gets its own banner instead of masquerading as a warn verdict.
    if results and all(r.get("inoperative") for r in results):
        _emit_advisory(_format_inoperative(file_path, results))
        sys.exit(0)

    if decision == "block":
        hook_output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": _format_block(file_path, results, reasons),
            }
        }
        # 🔴 ensure_ascii=True 의무 — Windows cp949 stdout 에서 한글·em-dash 가 UnicodeEncodeError
        # 로 훅을 죽인다(실측: '—' cp949 illegal multibyte). 형제 훅 check_edit_allowed.py:115
        # 와 동일 관용구.
        # 🔴 ensure_ascii=True is mandatory — non-ASCII crashes the hook on Windows cp949 stdout.
        print(json.dumps(hook_output, ensure_ascii=True))
    elif decision == "warn":
        _emit_advisory(_format_warn(file_path, results, reasons))

    sys.exit(0)


if __name__ == "__main__":
    main()
