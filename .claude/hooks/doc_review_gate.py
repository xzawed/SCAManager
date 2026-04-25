#!/usr/bin/env python3
"""문서 변경 다중 에이전트 심의 Hook — PreToolUse (Edit/Write/MultiEdit).
Multi-agent review gate for document changes — PreToolUse hook."""
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
