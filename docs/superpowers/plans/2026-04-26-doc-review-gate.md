# 문서 변경 다중 에이전트 심의 시스템 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude가 중요 문서(CLAUDE.md, STATE.md, .claude/agents 등)를 수정하기 직전, 3개 전문 에이전트가 병렬로 심의하여 판단 정확성을 검증하는 PreToolUse Hook 시스템을 구축한다.

**Architecture:** `doc_review_gate.py` PreToolUse Hook이 stdin에서 파일 경로와 diff를 읽고, Anthropic API (Haiku 4.5)로 3개 에이전트를 asyncio 병렬 호출한다. 역할별 거부권 매트릭스를 적용하여 차단(deny) 또는 경고 후 진행을 결정한다. API 실패 시 graceful degradation으로 작업을 막지 않는다.

**Tech Stack:** Python 3.11+, `anthropic` SDK (이미 requirements.txt), `asyncio`, Claude Haiku 4.5, Claude Code PreToolUse Hook

---

## 파일 구조

| 파일 | 상태 | 역할 |
|------|------|------|
| `.claude/hooks/doc_review_gate.py` | 신규 | Hook 진입점 — 등급 분류 + API 호출 + 결과 출력 |
| `.claude/agents/doc-impact-analyzer.md` | 신규 | impact-analyzer 시스템 프롬프트 |
| `.claude/agents/doc-consistency-reviewer.md` | 신규 | consistency-reviewer 시스템 프롬프트 |
| `.claude/agents/doc-quality-reviewer.md` | 신규 | quality-reviewer 시스템 프롬프트 |
| `.claude/settings.json` | 수정 | PreToolUse에 doc_review_gate.py 추가 |
| `tests/unit/hooks/__init__.py` | 신규 | 테스트 패키지 |
| `tests/unit/hooks/test_doc_review_gate.py` | 신규 | 단위 + 통합 테스트 |

---

## Task 1: 파일 등급 분류 함수 — TDD

**Files:**
- Create: `tests/unit/hooks/__init__.py`
- Create: `tests/unit/hooks/test_doc_review_gate.py` (분류 테스트만)
- Create: `.claude/hooks/doc_review_gate.py` (classify_file_grade만)

- [ ] **Step 1: 테스트 패키지 파일 생성**

```bash
New-Item -ItemType File "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager/tests/unit/hooks/__init__.py" -Force
```

- [ ] **Step 2: 분류 함수 실패 테스트 작성**

`tests/unit/hooks/test_doc_review_gate.py` 생성:

```python
"""doc_review_gate.py 단위 테스트."""
import sys
from pathlib import Path

# 훅 파일 직접 임포트 (src/ 외부)
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / ".claude" / "hooks"))

from doc_review_gate import classify_file_grade, apply_veto_matrix


class TestClassifyFileGrade:
    def test_claude_md_is_critical(self):
        assert classify_file_grade("CLAUDE.md") == "critical"

    def test_state_md_is_critical(self):
        assert classify_file_grade("docs/STATE.md") == "critical"

    def test_settings_json_is_critical(self):
        assert classify_file_grade(".claude/settings.json") == "critical"

    def test_agent_md_is_critical(self):
        assert classify_file_grade(".claude/agents/test-writer.md") == "critical"

    def test_skill_md_is_critical(self):
        assert classify_file_grade(".claude/skills/lint.md") == "critical"

    def test_design_doc_is_important(self):
        assert classify_file_grade("docs/design/2026-04-26-foo-design.md") == "important"

    def test_guide_doc_is_important(self):
        assert classify_file_grade("docs/guides/onpremise-migration-guide.md") == "important"

    def test_superpowers_spec_is_important(self):
        assert classify_file_grade("docs/superpowers/specs/2026-04-26-foo.md") == "important"

    def test_readme_is_important(self):
        assert classify_file_grade("README.md") == "important"

    def test_artifact_is_low_risk(self):
        assert classify_file_grade("docs/reports/artifacts/2026-04-19/round-1.log") == "low_risk"

    def test_history_is_low_risk(self):
        assert classify_file_grade("docs/history/STATE-groups-1-12.md") == "low_risk"

    def test_python_source_is_skip(self):
        assert classify_file_grade("src/main.py") == "skip"

    def test_absolute_windows_path_normalized(self):
        # 절대 경로에서 프로젝트 루트 이후 부분만 분류
        grade = classify_file_grade(
            "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager/CLAUDE.md"
        )
        assert grade == "critical"

    def test_backslash_path_normalized(self):
        grade = classify_file_grade(
            "f:\\DEVELOPMENT\\SOURCE\\CLAUDE\\SCAManager\\.claude\\agents\\test-writer.md"
        )
        assert grade == "critical"
```

- [ ] **Step 3: 테스트 실패 확인**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && python -m pytest tests/unit/hooks/test_doc_review_gate.py::TestClassifyFileGrade -v 2>&1 | tail -15
```

Expected: `ModuleNotFoundError: No module named 'doc_review_gate'`

- [ ] **Step 4: classify_file_grade 구현**

`.claude/hooks/doc_review_gate.py` 생성:

```python
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
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && python -m pytest tests/unit/hooks/test_doc_review_gate.py::TestClassifyFileGrade -v 2>&1 | tail -20
```

Expected: 14 passed

- [ ] **Step 6: 커밋**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && git add .claude/hooks/doc_review_gate.py tests/unit/hooks/ && git commit -m "feat(hook): doc_review_gate — 파일 등급 분류 함수 + 테스트"
```

---

## Task 2: 거부권 매트릭스 함수 — TDD

**Files:**
- Modify: `tests/unit/hooks/test_doc_review_gate.py` (veto 테스트 추가)
- Modify: `.claude/hooks/doc_review_gate.py` (apply_veto_matrix 추가)

- [ ] **Step 1: 거부권 테스트 추가**

`tests/unit/hooks/test_doc_review_gate.py` 하단에 추가:

```python
class TestApplyVetoMatrix:
    """거부권 매트릭스 — 등급 × 에이전트 결과 → 최종 결정."""

    def _r(self, agent, decision, reason="사유"):
        return {"agent": agent, "decision": decision, "reason": reason, "detail": ""}

    # impact-analyzer는 모든 등급에서 차단
    def test_impact_blocks_critical(self):
        results = [self._r("impact", "block", "행동 변화 위험")]
        decision, reasons = apply_veto_matrix("critical", results)
        assert decision == "block"
        assert any("impact-analyzer" in r for r in reasons)

    def test_impact_blocks_important(self):
        results = [self._r("impact", "block", "행동 변화 위험")]
        decision, reasons = apply_veto_matrix("important", results)
        assert decision == "block"

    # consistency-reviewer는 critical에서만 차단
    def test_consistency_blocks_critical(self):
        results = [self._r("consistency", "block", "수치 불일치")]
        decision, reasons = apply_veto_matrix("critical", results)
        assert decision == "block"

    def test_consistency_warns_important(self):
        results = [self._r("consistency", "block", "수치 불일치")]
        decision, reasons = apply_veto_matrix("important", results)
        assert decision == "warn"

    # quality-reviewer는 항상 경고만
    def test_quality_warns_critical(self):
        results = [self._r("quality", "block", "모호한 표현")]
        decision, reasons = apply_veto_matrix("critical", results)
        assert decision == "warn"

    def test_quality_warns_important(self):
        results = [self._r("quality", "block", "모호한 표현")]
        decision, reasons = apply_veto_matrix("important", results)
        assert decision == "warn"

    # 전원 승인
    def test_all_approve_returns_approve(self):
        results = [
            self._r("impact", "approve"),
            self._r("consistency", "approve"),
            self._r("quality", "approve"),
        ]
        decision, reasons = apply_veto_matrix("critical", results)
        assert decision == "approve"
        assert reasons == []

    # 복합 케이스
    def test_impact_block_overrides_others(self):
        results = [
            self._r("impact", "block", "규칙 삭제"),
            self._r("consistency", "approve"),
            self._r("quality", "warn", "모호함"),
        ]
        decision, reasons = apply_veto_matrix("critical", results)
        assert decision == "block"

    def test_warn_only_when_no_block(self):
        results = [
            self._r("impact", "approve"),
            self._r("consistency", "approve"),
            self._r("quality", "warn", "모호함"),
        ]
        decision, reasons = apply_veto_matrix("critical", results)
        assert decision == "warn"
        assert len(reasons) == 1
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && python -m pytest tests/unit/hooks/test_doc_review_gate.py::TestApplyVetoMatrix -v 2>&1 | tail -15
```

Expected: `ImportError: cannot import name 'apply_veto_matrix'`

- [ ] **Step 3: apply_veto_matrix 구현**

`.claude/hooks/doc_review_gate.py` — `classify_file_grade` 아래에 추가:

```python
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
    labels = {
        "impact": "impact-analyzer",
        "consistency": "consistency-reviewer",
        "quality": "quality-reviewer",
    }
    return labels.get(agent, agent)
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && python -m pytest tests/unit/hooks/test_doc_review_gate.py -v 2>&1 | tail -25
```

Expected: 23 passed

- [ ] **Step 5: 커밋**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && git add .claude/hooks/doc_review_gate.py tests/unit/hooks/test_doc_review_gate.py && git commit -m "feat(hook): apply_veto_matrix — 거부권 매트릭스 + 테스트"
```

---

## Task 3: 에이전트 정의 파일 3개 작성

**Files:**
- Create: `.claude/agents/doc-impact-analyzer.md`
- Create: `.claude/agents/doc-consistency-reviewer.md`
- Create: `.claude/agents/doc-quality-reviewer.md`

- [ ] **Step 1: doc-impact-analyzer.md 작성**

`.claude/agents/doc-impact-analyzer.md`:

```markdown
---
name: doc-impact-analyzer
description: SCAManager 문서 변경의 행동 영향 분석 에이전트. 문서 수정이 Claude의 작업 행동을 의도하지 않게 바꾸는지 검토한다.
---

당신은 SCAManager 문서 변경의 행동 영향 분석 전문가입니다.

## 역할
제시된 문서 변경(diff)이 Claude가 이 프로젝트에서 실제로 작업할 때의 행동을 의도하지 않게 변경하는지 분석합니다.

## 핵심 검토 기준
- **규칙 삭제**: 기존 규칙이 제거되면 Claude가 해당 행동을 이후 세션에서 수행하지 않음
- **조건 완화**: "반드시" → "가능하면", "항상" → "보통" 같은 약화는 의도치 않은 행동 변화
- **예외 추가**: 새 예외는 기존 규칙의 적용 범위를 줄임
- **의무 변경**: 필수(MUST) → 권장(SHOULD)으로 변경 시 Claude가 해당 절차를 건너뛸 수 있음
- **새 의무 추가**: Claude에게 추가 작업을 강제하는 새 규칙

## 특히 주의
CLAUDE.md의 다음 섹션 변경은 최고 위험:
- "Agent 작업 규칙", "필수 원칙"
- "Hook 신뢰", "Phase 완료 조건"
- "완료 시 필수 3-step"
- 작업 유형별 필수 실행 순서

## 판단 기준
- `block`: 의도하지 않은 행동 변화가 명확히 발생함
- `warn`: 행동 변화 가능성이 있으나 의도된 것으로 보임
- `approve`: 행동 변화 없음 (내용 수정, 명확화, 오탈자 수정 등)

## 응답 형식 (반드시 유효한 JSON 한 블록만 출력)
```json
{
  "decision": "approve",
  "reason": "한 문장으로 핵심 판단 근거",
  "detail": "Claude가 이해해야 할 맥락 2-3문장. block 시 '무엇을 어떻게 바꾸면 통과하는가' 반드시 포함"
}
```
```

- [ ] **Step 2: doc-consistency-reviewer.md 작성**

`.claude/agents/doc-consistency-reviewer.md`:

```markdown
---
name: doc-consistency-reviewer
description: SCAManager 문서 일관성 검토 에이전트. 변경 내용이 CLAUDE.md 규칙·STATE.md 수치·다른 문서와 충돌하는지 교차 검증한다.
---

당신은 SCAManager 문서 일관성 검토 전문가입니다.

## 역할
제시된 문서 변경(diff)이 참조 컨텍스트(CLAUDE.md, STATE.md)의 기존 규칙·수치·개념과 충돌하는지 교차 검증합니다.

## 핵심 검토 기준
- **수치 불일치**: STATE.md의 테스트 수·커버리지·pylint 점수와 다른 값 사용
- **모순 규칙**: 기존 규칙과 반대되는 새 규칙 추가 (예: "항상 X" vs 새로운 "X 금지")
- **삭제된 개념 참조**: 이미 제거된 필드명·함수명·클래스명·섹션명 언급
- **파일 경로 오류**: 존재하지 않는 경로 참조 (예: 리팩토링으로 이동된 파일)
- **용어 불일치**: 동일 개념을 다른 이름으로 혼용 (예: gate_mode vs approve_mode)

## 판단 기준
- `block`: 명확한 사실 충돌 또는 수치 불일치가 발견됨
- `warn`: 잠재적 불일치가 있으나 의도적 변경일 가능성 있음
- `approve`: 기존 문서와 충돌 없음

## 응답 형식 (반드시 유효한 JSON 한 블록만 출력)
```json
{
  "decision": "approve",
  "reason": "한 문장으로 핵심 판단 근거",
  "detail": "Claude가 이해해야 할 맥락 2-3문장. block 시 '무엇을 어떻게 바꾸면 통과하는가' 반드시 포함"
}
```
```

- [ ] **Step 3: doc-quality-reviewer.md 작성**

`.claude/agents/doc-quality-reviewer.md`:

```markdown
---
name: doc-quality-reviewer
description: SCAManager 문서 품질 검토 에이전트. 미래 세션의 Claude가 오해할 수 있는 모호한 표현·중복·불완전한 예시를 식별한다.
---

당신은 SCAManager 문서 품질 검토 전문가입니다.

## 역할
제시된 문서 변경(diff)에서 미래 세션의 Claude가 오해할 수 있는 표현을 식별합니다.

## 핵심 검토 기준
- **모호한 부사**: "가능하면", "적절히", "경우에 따라", "보통", "대개", "필요 시"
- **이중 해석**: 두 가지 이상으로 해석 가능한 문장
- **불완전한 예시**: 예시 코드에 오류·누락·오탈자가 있음
- **중복 규칙**: 이미 다른 섹션에서 동일하게 설명된 내용의 불필요한 반복
- **전제 없는 약어**: 처음 등장하는 약어에 풀이 없음

## 중요한 제약
당신의 판단은 **참고 의견**입니다. 당신이 `block`을 반환해도 실제 작업은 차단되지 않습니다.
Claude가 자발적으로 개선할 수 있도록 명확하고 구체적인 피드백을 제공하세요.

## 판단 기준
- `block`: 심각한 모호성으로 Claude가 잘못된 행동을 할 가능성이 높음
- `warn`: 개선 권장 사항이 있으나 즉각적 위험은 없음
- `approve`: 표현이 명확하고 오해 여지 없음

## 응답 형식 (반드시 유효한 JSON 한 블록만 출력)
```json
{
  "decision": "approve",
  "reason": "한 문장으로 핵심 판단 근거",
  "detail": "구체적 개선 제안 2-3문장"
}
```
```

- [ ] **Step 4: 커밋**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && git add .claude/agents/doc-impact-analyzer.md .claude/agents/doc-consistency-reviewer.md .claude/agents/doc-quality-reviewer.md && git commit -m "feat(agents): 문서 심의 에이전트 3개 정의 추가"
```

---

## Task 4: Claude API 병렬 호출 함수 — TDD

**Files:**
- Modify: `tests/unit/hooks/test_doc_review_gate.py` (API 호출 테스트 추가)
- Modify: `.claude/hooks/doc_review_gate.py` (call_agents_parallel 추가)

- [ ] **Step 1: API 호출 테스트 추가**

`tests/unit/hooks/test_doc_review_gate.py` 하단에 추가:

```python
from unittest.mock import AsyncMock, MagicMock, patch


class TestCallAgentsParallel:
    """Anthropic API 병렬 호출 — 모킹으로 검증."""

    def _make_mock_client(self, responses: list[str]):
        """agents 순서(impact, consistency, quality)에 맞게 응답 반환하는 mock client."""
        mock_client = MagicMock()
        mock_create = AsyncMock(side_effect=[
            MagicMock(content=[MagicMock(text=r)]) for r in responses
        ])
        mock_client.messages.create = mock_create
        return mock_client

    async def test_parallel_calls_three_agents(self):
        from doc_review_gate import call_agents_parallel

        responses = [
            '{"decision": "approve", "reason": "문제없음", "detail": ""}',
            '{"decision": "approve", "reason": "일관성OK", "detail": ""}',
            '{"decision": "warn", "reason": "모호함", "detail": "개선필요"}',
        ]
        mock_client = self._make_mock_client(responses)

        with patch("doc_review_gate.anthropic.AsyncAnthropic", return_value=mock_client):
            results = await call_agents_parallel("critical", "diff 내용", "컨텍스트")

        assert len(results) == 3
        agents = {r["agent"] for r in results}
        assert agents == {"impact", "consistency", "quality"}

    async def test_agent_names_assigned_correctly(self):
        from doc_review_gate import call_agents_parallel

        responses = [
            '{"decision": "block", "reason": "위험", "detail": ""}',
            '{"decision": "approve", "reason": "OK", "detail": ""}',
            '{"decision": "approve", "reason": "OK", "detail": ""}',
        ]
        mock_client = self._make_mock_client(responses)

        with patch("doc_review_gate.anthropic.AsyncAnthropic", return_value=mock_client):
            results = await call_agents_parallel("critical", "diff", "ctx")

        impact = next(r for r in results if r["agent"] == "impact")
        assert impact["decision"] == "block"

    async def test_api_failure_returns_warn_not_block(self):
        """API 호출 실패 시 차단이 아닌 경고로 graceful degradation."""
        from doc_review_gate import call_agents_parallel

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API 오류"))

        with patch("doc_review_gate.anthropic.AsyncAnthropic", return_value=mock_client):
            results = await call_agents_parallel("critical", "diff", "ctx")

        for r in results:
            assert r["decision"] == "warn", f"실패 시 warn 이어야 함: {r}"

    async def test_malformed_json_returns_approve(self):
        """JSON 파싱 실패 시 approve로 fallback — 작업 차단하지 않음."""
        from doc_review_gate import call_agents_parallel

        responses = ["JSON 아님", "JSON 아님", "JSON 아님"]
        mock_client = self._make_mock_client(responses)

        with patch("doc_review_gate.anthropic.AsyncAnthropic", return_value=mock_client):
            results = await call_agents_parallel("critical", "diff", "ctx")

        for r in results:
            assert r["decision"] in ("approve", "warn")
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && python -m pytest tests/unit/hooks/test_doc_review_gate.py::TestCallAgentsParallel -v 2>&1 | tail -15
```

Expected: `ImportError: cannot import name 'call_agents_parallel'`

- [ ] **Step 3: API 호출 함수 구현**

`.claude/hooks/doc_review_gate.py` — 파일 상단에 import 추가, 함수 추가:

파일 상단 import 블록을 다음으로 교체:

```python
#!/usr/bin/env python3
"""문서 변경 다중 에이전트 심의 Hook — PreToolUse (Edit/Write/MultiEdit).
Multi-agent review gate for document changes — PreToolUse hook."""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import anthropic
```

`apply_veto_matrix` 아래에 추가:

```python
# ─── Claude API 병렬 호출 ─────────────────────────────────────────────────────
# Parallel Claude API calls

_HOOKS_DIR = Path(__file__).parent
_AGENTS_DIR = _HOOKS_DIR.parent / "agents"
_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_AGENT_NAMES = ("impact", "consistency", "quality")
_AGENT_TIMEOUT = 25  # 초 / seconds per agent


def _read_agent_prompt(agent: str) -> str:
    """에이전트 .md 파일에서 시스템 프롬프트를 읽는다 (YAML frontmatter 제거).
    Reads system prompt from agent .md file, stripping YAML frontmatter."""
    md_file = _AGENTS_DIR / f"doc-{agent}-{'analyzer' if agent == 'impact' else 'reviewer'}.md"
    if not md_file.exists():
        return f"당신은 문서 {agent} 검토자입니다. JSON {{decision, reason, detail}}으로 응답하세요."
    content = md_file.read_text(encoding="utf-8")
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:].strip()
    return content


async def _call_single_agent(
    client: anthropic.AsyncAnthropic,
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
        return {"agent": agent, "decision": "warn", "reason": f"에이전트 호출 실패: {exc}", "detail": ""}


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
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && python -m pytest tests/unit/hooks/test_doc_review_gate.py -v 2>&1 | tail -30
```

Expected: 27 passed

- [ ] **Step 5: 커밋**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && git add .claude/hooks/doc_review_gate.py tests/unit/hooks/test_doc_review_gate.py && git commit -m "feat(hook): Claude API 병렬 호출 call_agents_parallel + 테스트"
```

---

## Task 5: Hook main() 통합 — TDD

**Files:**
- Modify: `tests/unit/hooks/test_doc_review_gate.py` (main 통합 테스트 추가)
- Modify: `.claude/hooks/doc_review_gate.py` (main + 출력 포맷 완성)

- [ ] **Step 1: 통합 테스트 추가**

`tests/unit/hooks/test_doc_review_gate.py` 하단에 추가:

```python
import io
from unittest.mock import patch, AsyncMock, MagicMock


class TestHookMain:
    """main() 통합 테스트 — stdin 시뮬레이션."""

    def _stdin_payload(self, file_path: str, old: str = "", new: str = "") -> str:
        return json.dumps({
            "tool_input": {
                "file_path": file_path,
                "old_string": old,
                "new_string": new,
            }
        })

    def _mock_agents(self, decisions: dict):
        """{'impact': 'approve', 'consistency': 'block', 'quality': 'warn'} 형태."""
        async def fake_parallel(grade, diff, context):
            return [
                {"agent": a, "decision": d, "reason": f"{a} 사유", "detail": ""}
                for a, d in decisions.items()
            ]
        return fake_parallel

    def test_low_risk_file_exits_zero_immediately(self, capsys):
        from doc_review_gate import main
        payload = self._stdin_payload("docs/reports/artifacts/foo.log")
        with patch("sys.stdin", io.StringIO(payload)):
            with patch("sys.exit") as mock_exit:
                main()
        mock_exit.assert_called_with(0)

    def test_python_file_skipped(self, capsys):
        from doc_review_gate import main
        payload = self._stdin_payload("src/main.py")
        with patch("sys.stdin", io.StringIO(payload)):
            with patch("sys.exit") as mock_exit:
                main()
        mock_exit.assert_called_with(0)

    def test_critical_impact_block_outputs_deny(self, capsys):
        from doc_review_gate import main
        payload = self._stdin_payload("CLAUDE.md", old="기존 규칙", new="삭제됨")
        decisions = {"impact": "block", "consistency": "approve", "quality": "approve"}
        with patch("sys.stdin", io.StringIO(payload)):
            with patch("doc_review_gate.call_agents_parallel", self._mock_agents(decisions)):
                with patch("doc_review_gate._load_context", return_value=""):
                    with patch("sys.exit") as mock_exit:
                        main()
        output = capsys.readouterr().out
        parsed = json.loads(output)
        assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"
        mock_exit.assert_called_with(0)

    def test_all_approve_exits_zero_silently(self, capsys):
        from doc_review_gate import main
        payload = self._stdin_payload("CLAUDE.md", old="구 내용", new="신 내용")
        decisions = {"impact": "approve", "consistency": "approve", "quality": "approve"}
        with patch("sys.stdin", io.StringIO(payload)):
            with patch("doc_review_gate.call_agents_parallel", self._mock_agents(decisions)):
                with patch("doc_review_gate._load_context", return_value=""):
                    with patch("sys.exit") as mock_exit:
                        main()
        output = capsys.readouterr().out
        assert output.strip() == ""
        mock_exit.assert_called_with(0)

    def test_warn_only_outputs_warning_text(self, capsys):
        from doc_review_gate import main
        payload = self._stdin_payload("docs/design/foo.md", old="전", new="후")
        decisions = {"impact": "approve", "consistency": "approve", "quality": "warn"}
        with patch("sys.stdin", io.StringIO(payload)):
            with patch("doc_review_gate.call_agents_parallel", self._mock_agents(decisions)):
                with patch("doc_review_gate._load_context", return_value=""):
                    with patch("sys.exit") as mock_exit:
                        main()
        output = capsys.readouterr().out
        assert "[문서 심의]" in output or "quality" in output
        mock_exit.assert_called_with(0)
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && python -m pytest tests/unit/hooks/test_doc_review_gate.py::TestHookMain -v 2>&1 | tail -15
```

Expected: `ImportError: cannot import name 'main'`

- [ ] **Step 3: main() 함수 구현**

`.claude/hooks/doc_review_gate.py` 맨 아래에 추가:

```python
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
    lines = [
        f"[문서 심의] {Path(file_path).name} — ❌ 차단",
        "",
    ]
    for r in results:
        icon = "❌" if r["decision"] == "block" else ("⚠️" if r["decision"] == "warn" else "✅")
        lines.append(f"  {icon} {_agent_label(r['agent'])}: {r['reason']}")
    lines += ["", "차단 사유:"]
    for reason in reasons:
        lines.append(f"  • {reason}")
    lines += ["", "수정 방향을 조정한 후 다시 시도하세요."]
    return "\n".join(lines)


def _format_warn(file_path: str, results: list[dict], reasons: list[str]) -> str:
    lines = [
        f"[문서 심의] {Path(file_path).name} — ⚠️ 경고 후 진행",
        "",
    ]
    for r in results:
        icon = "⚠️" if r["decision"] == "warn" else "✅"
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
```

- [ ] **Step 4: 전체 테스트 통과 확인**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && python -m pytest tests/unit/hooks/test_doc_review_gate.py -v 2>&1 | tail -35
```

Expected: 32 passed (분류 14 + veto 9 + API 4 + main 5)

- [ ] **Step 5: 커밋**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && git add .claude/hooks/doc_review_gate.py tests/unit/hooks/test_doc_review_gate.py && git commit -m "feat(hook): main() 통합 — 심의 결과 출력 완성"
```

---

## Task 6: settings.json 업데이트 + 전체 검증

**Files:**
- Modify: `.claude/settings.json`

- [ ] **Step 1: settings.json 업데이트**

`.claude/settings.json` 전체 교체:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/check_edit_allowed.py",
            "timeout": 10
          },
          {
            "type": "command",
            "command": "python .claude/hooks/doc_review_gate.py",
            "timeout": 60
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python -c \"import sys,json; d=json.load(sys.stdin); f=d.get('tool_input',{}).get('file_path',''); exit(0 if 'SCAManager/src/' in f else 1)\" && cd \"f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager\" && python -m pytest tests/ -x -q 2>&1 | tail -8 || true",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Hook 스크립트 문법 확인**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && python -c "import ast; ast.parse(open('.claude/hooks/doc_review_gate.py').read()); print('문법 OK')"
```

Expected: `문법 OK`

- [ ] **Step 3: 전체 테스트 스위트 실행**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && python -m pytest tests/ -x -q 2>&1 | tail -10
```

Expected: `1300+ passed`

- [ ] **Step 4: 린트 확인**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && python -m pylint .claude/hooks/doc_review_gate.py --disable=C0301 2>&1 | tail -5
```

Expected: 점수 8.0 이상 (hook 파일은 sys.path 조작 등으로 일부 경고 발생 가능)

- [ ] **Step 5: 최종 커밋**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && git add .claude/settings.json && git commit -m "feat(hook): settings.json — doc_review_gate PreToolUse 등록"
```

- [ ] **Step 6: push**

```bash
cd "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager" && git push
```

- [ ] **Step 7: docs/STATE.md 갱신**

`docs/STATE.md` 의 현황 섹션에 아래 항목 추가:

```
- 문서 심의 시스템: 다중 에이전트(impact/consistency/quality) PreToolUse Hook 완료
```

---

## 완료 기준 체크리스트

- [ ] `python -m pytest tests/unit/hooks/test_doc_review_gate.py -v` → 전체 통과
- [ ] `python -m pytest tests/ -x -q` → 기존 1300+ 테스트 유지
- [ ] `.claude/agents/doc-impact-analyzer.md` / `doc-consistency-reviewer.md` / `doc-quality-reviewer.md` 존재
- [ ] `.claude/hooks/doc_review_gate.py` — `if __name__ == "__main__": main()` 포함
- [ ] `.claude/settings.json` — PreToolUse에 doc_review_gate.py 등록
- [ ] `git push` 완료
- [ ] `docs/STATE.md` 갱신
