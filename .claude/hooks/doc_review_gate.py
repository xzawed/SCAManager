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
    """경로를 소문자 슬래시로 정규화하고 프로젝트 루트 접두사를 제거한다.
    Normalise path to lowercase forward-slashes and strip project root prefix."""
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

    for pattern in _LOW_RISK:
        if re.search(pattern, p, re.IGNORECASE):
            return "low_risk"

    for pattern in _CRITICAL:
        if re.match(pattern, p, re.IGNORECASE):
            return "critical"

    for pattern in _IMPORTANT:
        if re.match(pattern, p, re.IGNORECASE):
            return "important"

    return "skip"


# apply_veto_matrix placeholder — Task 2에서 구현됨
# Placeholder — implemented in Task 2
def apply_veto_matrix(grade: str, results: list) -> tuple:
    raise NotImplementedError("Task 2에서 구현")
