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

_IMPORTANT = [
    r"^docs/design/[^/]+\.md$",
    r"^docs/guides/[^/]+\.md$",
    r"^docs/superpowers/.+\.md$",
    r"^README\.md$",
    r"^\.claude/policies/[^/]+\.md$",
]

_LOW_RISK = [
    r"^docs/reports/artifacts/",
    r"^docs/history/",
    r"^docs/integrations/",
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

    for r in results:
        agent = r.get("agent", "unknown")
        decision = r.get("decision", "approve")
        reason = r.get("reason", "")

        if decision not in ("warn", "block"):
            continue

        if decision == "block":
            if agent == "impact":
                # impact-analyzer: 모든 등급 차단 / blocks every grade
                block_reasons.append(f"[impact-analyzer] {reason}")
            elif agent == "consistency" and grade == "critical":
                # consistency-reviewer: critical 등급에서만 차단 / blocks only for critical
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


async def _call_single_agent(
    client,
    agent: str,
    diff: str,
    context: str,
) -> dict:
    """에이전트 한 개를 호출하고 JSON 결과를 반환한다.
    Calls a single agent and returns a JSON result dict."""
    system_prompt = _read_agent_prompt(agent)
    # 🔴 `context` 를 여기서 다시 자르지 않는다 — 예산은 `_load_context()` 가 **파일별로**
    #    한 번만 적용하고 라벨에 비율을 적는다. 이중 절단이 CLAUDE.md 를 10.8% 로 깎고
    #    STATE.md 를 통째로 지우면서도 헤더는 둘 다 있다고 말했다(2026-08-01 실측).
    # Do not re-truncate: the budget is applied once, per source, and labelled there.
    user_msg = (
        f"## 변경 내용 (diff)\n{diff[:_DIFF_BUDGET]}\n\n"
        f"## 참조 컨텍스트\n{context}\n\n"
        "위 변경을 검토하고 JSON으로만 응답하세요."
    )
    try:
        msg = await asyncio.wait_for(
            client.messages.create(
                model=_HAIKU_MODEL,
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            ),
            timeout=_AGENT_TIMEOUT,
        )
        text = msg.content[0].text
        # 코드 블록 추출 우선, 없으면 전체 텍스트에서 JSON 파싱 시도
        # Prefer code block extraction; fall back to parsing the full text
        code_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        candidate = code_match.group(1).strip() if code_match else text.strip()
        try:
            parsed = json.loads(candidate)
            parsed["agent"] = agent
            return parsed
        except (json.JSONDecodeError, ValueError):
            return {"agent": agent, "decision": "approve", "reason": "JSON 파싱 실패 — 통과", "detail": text[:200]}
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return {"agent": agent, "decision": "warn", "reason": "에이전트 호출 실패", "detail": str(exc)}


async def call_agents_parallel(grade: str, diff: str, context: str) -> list[dict]:
    """3개 에이전트를 병렬로 호출하고 결과 목록을 반환한다.
    Calls all three agents in parallel and returns a list of result dicts."""
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    tasks = [_call_single_agent(client, agent, diff, context) for agent in _AGENT_NAMES]
    raw = await asyncio.gather(*tasks, return_exceptions=False)
    return list(raw)


# ─── 컨텍스트 로드 ────────────────────────────────────────────────────────────
# Context loading

# 컨텍스트 원천과 **파일별** 예산(자). 규칙을 담은 문서는 전문이 들어가도록 잡는다.
# Per-source budgets, sized so the rule documents fit whole.
_CONTEXT_SOURCES: tuple[tuple[str, int], ...] = (
    ("CLAUDE.md", 40000),     # 27.8k — 전문 (정책 1~19 가 여기 있다)
    ("AGENTS.md", 12000),     # 5.3k  — 전문 (가드 3-불변식 SSOT)
    ("docs/STATE.md", 4000),  # 88k   — 수치만 필요하므로 머리만
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
    project_root = _HOOKS_DIR.parent.parent
    parts = []
    for rel, budget in _CONTEXT_SOURCES:
        path = project_root / rel
        if not path.exists():
            # 침묵 누락 금지 — 없으면 없다고 말한다 / never drop a source silently
            parts.append(f"=== {rel} — 파일 없음(이 근거 없이 판정됨) ===")
            continue
        content = path.read_text(encoding="utf-8")
        if len(content) <= budget:
            parts.append(f"=== {rel} (전문 {len(content)}자) ===\n{content}")
        else:
            pct = budget / len(content)
            parts.append(
                f"=== {rel} (앞 {budget}자 / 전체 {len(content)}자 = {pct:.0%}만 포함, "
                f"나머지는 못 봄) ===\n{content[:budget]}"
            )
    return "\n\n".join(parts)


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

    🔴 `warn` 분기(`print(_format_warn(...))`)는 한글 원문을 그대로 출력하므로 ensure_ascii
    만으로는 부족하다. 훅은 standalone 실행이라 공유 헬퍼를 import 할 수 없어 검증된 관용구를
    복제한다(scripts/check_dual_import.py 정본). 누락 방지 = test_stdout_encoding_guard.py.
    The warn branch prints raw Korean, so ensure_ascii alone is not enough; hooks run standalone
    so the verified idiom is duplicated rather than imported.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / captured streams: ignore


def main() -> None:
    """PreToolUse Hook 진입점 — stdin에서 payload 읽고 심의 결과 출력.
    PreToolUse hook entry point — reads payload from stdin and outputs review result."""
    _make_stdout_safe()
    # 비용 제어 — kill-switch 시 리뷰 없이 즉시 허용(sys.exit(0)=편집 통과, API 호출 0).
    # Cost control — when the kill-switch is on, allow the edit immediately with no review (no API call).
    if gate_disabled():
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except Exception:  # pylint: disable=broad-exception-caught
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

    context = _load_context()
    results = asyncio.run(call_agents_parallel(grade, diff, context))
    decision, reasons = apply_veto_matrix(grade, results)

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
        print(_format_warn(file_path, results, reasons))

    sys.exit(0)


if __name__ == "__main__":
    main()
