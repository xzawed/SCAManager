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
