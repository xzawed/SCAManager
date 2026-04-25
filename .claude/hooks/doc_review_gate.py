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

_PROJECT_PREFIXES = (
    "f:/development/source/claude/scamanager/",
    "f:\\development\\source\\claude\\scamanager\\",
)

_CRITICAL = [
    r"^CLAUDE\.md$",
    r"^docs/STATE\.md$",
    r"^\.claude/settings\.json$",
    r"^\.claude/agents/[^/]+\.md$",
    r"^\.claude/skills/[^/]+\.md$",
]

_IMPORTANT = [
    r"^docs/design/[^/]+\.md$",
    r"^docs/guides/[^/]+\.md$",
    r"^docs/superpowers/.+\.md$",
    r"^README\.md$",
]

_LOW_RISK = [
    r"^docs/reports/artifacts/",
    r"^docs/history/",
    r"^docs/integrations/",
]


def _normalise(path: str) -> str:
    """경로를 슬래시로 정규화하고 프로젝트 루트 접두사를 제거한다.
    Normalise path to forward-slashes and strip project root prefix."""
    p = path.replace("\\", "/")
    lower = p.lower()
    for prefix in _PROJECT_PREFIXES:
        if lower.startswith(prefix.lower()):
            p = p[len(prefix):]
            break
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
    user_msg = (
        f"## 변경 내용 (diff)\n{diff[:4000]}\n\n"
        f"## 참조 컨텍스트 (CLAUDE.md / STATE.md)\n{context[:3000]}\n\n"
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
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            parsed["agent"] = agent
            return parsed
        return {"agent": agent, "decision": "approve", "reason": "JSON 파싱 실패 — 통과", "detail": text[:200]}
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return {"agent": agent, "decision": "warn", "reason": "에이전트 호출 실패", "detail": str(exc)}


async def call_agents_parallel(grade: str, diff: str, context: str) -> list[dict]:
    """3개 에이전트를 병렬로 호출하고 결과 목록을 반환한다.
    Calls all three agents in parallel and returns a list of result dicts."""
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    tasks = [_call_single_agent(client, agent, diff, context) for agent in _AGENT_NAMES]
    raw = await asyncio.gather(*tasks, return_exceptions=True)
    results = []
    for agent, r in zip(_AGENT_NAMES, raw):
        if isinstance(r, Exception):
            results.append({"agent": agent, "decision": "warn", "reason": f"오류: {r}", "detail": ""})
        else:
            results.append(r)
    return results


# ─── 컨텍스트 로드 ────────────────────────────────────────────────────────────
# Context loading

def _load_context() -> str:
    """CLAUDE.md 와 STATE.md 앞부분을 에이전트 컨텍스트로 읽는다.
    Loads the front portion of CLAUDE.md and STATE.md as agent context."""
    project_root = _HOOKS_DIR.parent.parent
    parts = []
    for rel in ("CLAUDE.md", "docs/STATE.md"):
        path = project_root / rel
        if path.exists():
            content = path.read_text(encoding="utf-8")
            parts.append(f"=== {rel} (앞 3000자) ===\n{content[:3000]}")
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

def main() -> None:
    """PreToolUse Hook 진입점 — stdin에서 payload 읽고 심의 결과 출력.
    PreToolUse hook entry point — reads payload from stdin and outputs review result."""
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

    # diff 구성 / Build diff
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
        print(json.dumps(hook_output, ensure_ascii=False))
    elif decision == "warn":
        print(_format_warn(file_path, results, reasons))

    sys.exit(0)


if __name__ == "__main__":
    main()
