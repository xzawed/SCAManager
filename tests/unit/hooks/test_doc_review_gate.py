"""doc_review_gate.py 단위 테스트."""
import io
import json
import sys
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_absolute_path_from_runtime_root_is_critical(self):
        # 런타임 프로젝트 루트 기반 절대경로 — 하드코딩 경로 회귀 차단 (WBS P0, 사이클 160).
        # 기존 'd:/Source/SCAManager' 하드코딩 테스트는 버그 prefix 와 동일해 결함을 은폐했음.
        # Absolute path from the real repo root must classify regardless of drive/case/separator.
        root = Path(__file__).resolve().parents[3]  # repo root (test: tests/unit/hooks/)
        assert classify_file_grade(str(root / "CLAUDE.md")) == "critical"

    def test_absolute_path_uppercase_drive_backslash_is_critical(self):
        # 대문자 드라이브 + 백슬래시 변형도 critical (Windows 경로 회귀 가드).
        root = Path(__file__).resolve().parents[3]
        p = str(root / ".claude" / "agents" / "test-writer.md").replace("/", "\\")
        assert classify_file_grade(p) == "critical"

    def test_non_runtime_root_absolute_path_is_skip(self):
        # 실 런타임 루트가 아닌 절대경로는 strip 되지 않아 'skip' 이 정상 (상대 doc 경로만 분류).
        # 루트에 접미사를 붙인 형제 경로 — 어떤 머신에서도 런타임 루트와 불일치 보장.
        # An absolute path NOT under the runtime root stays unstripped → 'skip' (only relative doc paths classify).
        # Use a sibling of the real root (root + suffix) so it never equals the root on any machine.
        #
        # 🔴 기존 하드코딩 'd:/source/scamanager/' 는 본 리포 실제 루트와 우연히 일치 →
        # 루트가 d:\Source\SCAManager 인 머신에서만 strip 되어 'critical' 로 분류, 머신 의존 실패 유발
        # (CI Linux 루트는 불일치해 통과 → 결함 은폐). 런타임 루트 파생으로 머신 독립 보장.
        # The old hardcoded 'd:/source/scamanager/' collided with this repo's real root —
        # it failed only on machines rooted at d:\Source\SCAManager (CI Linux root differed → passed, hiding the flaw).
        root = str(Path(__file__).resolve().parents[3]).replace("\\", "/")
        assert classify_file_grade(f"{root}_external/CLAUDE.md") == "skip"


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
        decision, _ = apply_veto_matrix("important", results)
        assert decision == "block"

    # consistency-reviewer는 critical에서만 차단
    def test_consistency_blocks_critical(self):
        results = [self._r("consistency", "block", "수치 불일치")]
        decision, _ = apply_veto_matrix("critical", results)
        assert decision == "block"

    def test_consistency_warns_important(self):
        results = [self._r("consistency", "block", "수치 불일치")]
        decision, _ = apply_veto_matrix("important", results)
        assert decision == "warn"

    # quality-reviewer는 항상 경고만
    def test_quality_warns_critical(self):
        results = [self._r("quality", "block", "모호한 표현")]
        decision, _ = apply_veto_matrix("critical", results)
        assert decision == "warn"

    def test_quality_warns_important(self):
        results = [self._r("quality", "block", "모호한 표현")]
        decision, _ = apply_veto_matrix("important", results)
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
        decision, _ = apply_veto_matrix("critical", results)
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

    async def test_malformed_json_is_inoperative_not_approve(self):
        """🔴 JSON 파싱 실패는 **미심의**다 — approve 로 통과시키지 않는다 (R35, 회고 2026-08-04 P0).

        이 테스트의 이전 판은 정반대 극성을 고정하고 있었다:
        `\"\"\"JSON 파싱 실패 시 approve로 fallback — 작업 차단하지 않음.\"\"\"`
        즉 **스위트가 fail-open 을 정상 동작으로 지키고 있었다**(Grok `019fc81b` GROK-7).
        심의하지 못한 것과 심의해서 통과시킨 것은 같은 값을 가질 수 없다.

        The previous revision of this test froze the opposite polarity: it blessed the
        approve-on-parse-failure fail-open. Not-reviewed must never equal reviewed-and-approved.
        """
        from doc_review_gate import call_agents_parallel

        responses = ["JSON 아님", "JSON 아님", "JSON 아님"]
        mock_client = self._make_mock_client(responses)

        with patch("doc_review_gate.anthropic.AsyncAnthropic", return_value=mock_client):
            results = await call_agents_parallel("critical", "diff", "ctx")

        for r in results:
            assert r["decision"] == "warn", f"파싱 실패가 approve 로 샜다: {r}"
            assert r["inoperative"] is True, f"미심의 표기가 없다: {r}"

    async def test_truncated_response_is_inoperative(self):
        """🔴 `stop_reason == max_tokens` 는 잘린 응답이다 — 판정으로 읽지 않는다 (R35).

        기전: 출력 예산이 고정이라 **리뷰어가 할 말이 많을수록** 잘린다. 잘린 JSON 은
        파싱 실패로 떨어지고, 이전 구현은 그것을 approve 로 바꿨다 — 즉 심각도와
        fail-open 확률이 정비례했다. `stop_reason` 을 읽으면 그 자체가 신호다.
        """
        from doc_review_gate import call_agents_parallel

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=MagicMock(
            content=[MagicMock(text='{"decision": "block", "reason": "말이 길어서 잘림')],
            stop_reason="max_tokens",
        ))

        with patch("doc_review_gate.anthropic.AsyncAnthropic", return_value=mock_client):
            results = await call_agents_parallel("critical", "diff", "ctx")

        for r in results:
            assert r["inoperative"] is True, f"절단이 미심의로 표기되지 않았다: {r}"
            assert r["decision"] == "warn"
            assert "절단" in r["reason"], f"절단 고유 문구가 없다: {r['reason']}"

    async def test_call_failure_carries_the_exception_text(self):
        """🔴 실패 원문(`detail`)을 버리지 않는다 (R36).

        세션14 가 8회+ 겪은 전건 실패의 원인을 아무도 몰랐던 이유가 이것이다 —
        예외 원문이 출력에서 통째로 사라졌다.
        """
        from doc_review_gate import call_agents_parallel

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("보이는-원인-문구"))

        with patch("doc_review_gate.anthropic.AsyncAnthropic", return_value=mock_client):
            results = await call_agents_parallel("critical", "diff", "ctx")

        for r in results:
            assert r["inoperative"] is True
            assert "보이는-원인-문구" in r.get("detail", ""), f"예외 원문이 버려졌다: {r}"


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

    def test_low_risk_file_exits_zero_immediately(self):
        from doc_review_gate import main
        payload = self._stdin_payload("docs/reports/artifacts/foo.log")
        with patch("sys.stdin", io.StringIO(payload)):
            with patch("doc_review_gate.call_agents_parallel") as mock_agents:
                with pytest.raises(SystemExit) as exc:
                    main()
        assert exc.value.code == 0
        assert not mock_agents.called  # 에이전트 호출 없이 조기 종료 / exits before calling agents

    def test_python_file_skipped(self):
        from doc_review_gate import main
        payload = self._stdin_payload("src/main.py")
        with patch("sys.stdin", io.StringIO(payload)):
            with patch("doc_review_gate.call_agents_parallel") as mock_agents:
                with pytest.raises(SystemExit) as exc:
                    main()
        assert exc.value.code == 0
        assert not mock_agents.called  # 에이전트 호출 없이 조기 종료 / exits before calling agents

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
        # 🔴 텍스트 포함이 아니라 **전달 채널 형태**를 본다 — plain print 로 되돌려도
        #    "[문서 심의]" 는 여전히 stdout 에 있으므로 텍스트 단언은 theatre 에서도 통과한다.
        #    PreToolUse 의 plain stdout 은 Claude 에게 전달되지 않는다(공식 계약).
        # Assert the delivery shape, not substring presence: plain print keeps the text in
        # stdout while never reaching Claude.
        payload_out = json.loads(capsys.readouterr().out)
        ctx = payload_out["hookSpecificOutput"]["additionalContext"]
        assert "[문서 심의]" in ctx
        assert "quality" in ctx
        assert payload_out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert "permissionDecision" not in payload_out["hookSpecificOutput"], (
            "advisory 경고에 권한 결정을 얹으면 안 된다 — `allow` 는 사용자 확인을 건너뛴다"
        )
        assert "[문서 심의]" in payload_out["systemMessage"], "사용자 채널에도 실려야 한다"
        mock_exit.assert_called_with(0)


class TestGateKillSwitch:
    """DOC_REVIEW_GATE_DISABLED env kill-switch (로컬 Anthropic 비용 제어)."""

    def test_disabled_when_env_truthy(self, monkeypatch):
        from doc_review_gate import gate_disabled
        for v in ("1", "true", "TRUE", "yes"):
            monkeypatch.setenv("DOC_REVIEW_GATE_DISABLED", v)
            assert gate_disabled() is True

    def test_enabled_when_env_unset_or_falsy(self, monkeypatch):
        from doc_review_gate import gate_disabled
        monkeypatch.delenv("DOC_REVIEW_GATE_DISABLED", raising=False)
        assert gate_disabled() is False
        monkeypatch.setenv("DOC_REVIEW_GATE_DISABLED", "0")
        assert gate_disabled() is False


# ──────────────────────────────────────────────────────────────────────────────
# 🔴 심의 스코프 회귀 가드 (backlog R9 · 2026-07-29)
#
# 2026-07-21 문서 재구성 이후 **가장 행동에 영향을 주는 규칙 문서들이 전부 `skip`** 이었다 —
# 심의 게이트가 정작 심의해야 할 표면을 통과시키는 false coverage. 실측: 2026-07-29 세션이
# `.claude/rules/pipeline.md` 를 수정했는데 게이트가 발화하지 않았다.
#
# 🔴 여기서 대조하는 대상은 **디스크의 실제 파일**이다 — 하드코딩 목록끼리 비교하면 파일이
# 새로 생겨도(예: `.claude/rules/newarea.md`) 영원히 안 걸린다(공허화).
# ──────────────────────────────────────────────────────────────────────────────

def test_behavioural_rule_docs_are_never_skipped():
    """`AGENTS.md` · `.claude/rules/**` · `.claude/policies/**` 는 `skip` 이면 안 된다.

    디스크를 스캔하므로 신규 rules/policies 파일이 추가돼도 자동으로 검사 대상이 된다.
    """
    root = Path(__file__).resolve().parents[3]
    targets = [root / "AGENTS.md"]
    targets += sorted((root / ".claude" / "rules").glob("*.md"))
    targets += sorted((root / ".claude" / "policies").glob("*.md"))

    assert len(targets) > 5, "대조 집합이 비었다 — 스캐너가 고장났거나 경로가 바뀌었다"

    skipped = [
        p.relative_to(root).as_posix()
        for p in targets
        if classify_file_grade(p.relative_to(root).as_posix()) == "skip"
    ]
    assert not skipped, (
        "행동 지시 문서가 심의 대상에서 빠졌다(false coverage): "
        f"{skipped}\n→ doc_review_gate.py 의 _CRITICAL/_IMPORTANT 패턴을 확인할 것."
    )


def test_rules_are_critical_and_policies_are_important():
    """등급 구분 고정 — rules/ 는 편집 표면 자동 로드라 critical, policies/ 는 detail 이라 important.

    등급이 뒤바뀌면 consistency-reviewer 의 차단 범위가 달라진다(`apply_veto_matrix` 참조).
    """
    assert classify_file_grade("AGENTS.md") == "critical"
    assert classify_file_grade(".claude/rules/pipeline.md") == "critical"
    assert classify_file_grade(".claude/policies/active.md") == "important"


# ──────────────────────────────────────────────────────────────────────────────
# 심의자가 **규칙을 실제로 보는가** — 컨텍스트 절단 회귀 차단
#
# 🔴 2026-08-01 근본원인 분석 실측: `_load_context()` 가 파일마다 3000자로 자른 뒤
#    프롬프트가 **합친 문자열을 다시 3000자로** 잘랐다(이중 절단). 결과는
#    CLAUDE.md 10.8% 도달(정책 1~19 **0줄**) + STATE.md **0% 도달** —
#    그런데 프롬프트 헤더는 `(CLAUDE.md / STATE.md)` 라고 적혀 있었다.
#    "규칙을 집행하는 심의자가 규칙을 못 본다" 는 이 저장소 지배적 결함(observer-lie)의
#    가장 조용한 형태다: 심의는 계속 돌고, 결과는 계속 초록이다.
# ──────────────────────────────────────────────────────────────────────────────

# 🔴 **기대값은 `_CONTEXT_SOURCES` 에서 유도하지 않는다.** 유도하면 원천을 **삭제**했을 때
#    루프가 그냥 안 돌아 초록이 된다(실측: AGENTS.md 원천 제거 뮤테이션 M-C 가 GREEN).
#    가드가 자기 설정을 기대값으로 읽으면, 설정을 지우는 것이 곧 가드를 지우는 것이 된다.
# Pinned here, NOT derived from the module: deriving makes source *removal* silently green.
_REQUIRED_CONTEXT_SOURCES = ("CLAUDE.md", "AGENTS.md", "docs/STATE.md")

# 각 원천에만 있는 문구 — 다른 원천에도 있는 문구를 쓰면 그 원천을 지워도 통과한다.
# 실측: 초판은 "3-불변식" 을 썼는데 CLAUDE.md 에도 2회 나와 AGENTS.md 제거가 GREEN 이었다.
_SOURCE_FINGERPRINTS = (
    ("CLAUDE.md", "#### 정책 7", "PR 단위 의무 — 문서 변경 심의의 핵심 판정 근거"),
    ("CLAUDE.md", "#### 정책 19", "Grok claim-review — 파일 끝쪽이라 절단에 가장 먼저 사라진다"),
    ("AGENTS.md", "### 불변식 1 — fail-closed", "가드 저술 규율 — 별도 파일이라 통째로 빠져 있었다"),
    ("AGENTS.md", "### 불변식 2 — 실경로 뮤테이션", "합성 픽스처 금지 규율"),
)


@pytest.mark.parametrize(("rel", "needle", "why"), _SOURCE_FINGERPRINTS)
def test_review_context_contains_the_rules_it_enforces(rel, needle, why):
    """🔴 심의자 컨텍스트에 **실제 규칙 본문**이 들어 있어야 한다."""
    from doc_review_gate import _load_context

    disk = (Path(__file__).resolve().parents[3] / rel).read_text(encoding="utf-8")
    assert needle in disk, f"지문이 {rel} 에서 사라졌다 — 이 테스트가 공허해졌다: {needle!r}"
    assert needle in _load_context(), f"심의자가 못 보는 규칙: {needle} ({rel}) — {why}"


@pytest.mark.parametrize("rel", _REQUIRED_CONTEXT_SOURCES)
def test_review_context_labels_declare_what_was_actually_included(rel):
    """🔴 라벨이 **실제 포함분과 일치**해야 한다 — 없는 근거를 있다고 말하지 않는다.

    구판의 헤더 `## 참조 컨텍스트 (CLAUDE.md / STATE.md)` 는 STATE.md 가 0자 실린
    상태에서도 그대로 출력됐다. 라벨은 심의자가 자기 시야의 한계를 아는 유일한 수단이다.
    """
    from doc_review_gate import _load_context

    context = _load_context()
    header = f"=== {rel} "
    assert header in context, f"원천 {rel} 이 심의자 컨텍스트에서 빠졌다"

    body = context.split(header, 1)[1]
    # 라벨이 '전문' 이라 주장하면 파일 끝 문장이 실제로 있어야 한다
    if body.lstrip().startswith("(전문"):
        disk = (Path(__file__).resolve().parents[3] / rel).read_text(encoding="utf-8")
        assert disk.rstrip()[-40:] in context, f"{rel} 이 '전문' 이라면서 끝이 잘렸다"


def test_prompt_does_not_re_truncate_the_context():
    """🔴 프롬프트가 컨텍스트를 **다시 자르면** 파일별 예산이 무의미해진다(구판의 실제 기전).

    `_call_single_agent` 이 만드는 user 메시지를 가로채, 넘긴 컨텍스트가 **온전히**
    실렸는지 본다. 산문 검사가 아니라 실제 조립 결과를 관측한다.
    """
    import asyncio

    from doc_review_gate import _call_single_agent

    context = "X" * 9000 + "TAIL_SENTINEL"
    captured = {}

    async def _fake_create(**kwargs):
        captured["user"] = kwargs["messages"][0]["content"]
        raise RuntimeError("stop — 조립만 관측한다")

    client = MagicMock()
    client.messages.create = _fake_create

    # 🔴 string-path 패치 — `import X as mod` 를 들이면 이 파일의 `from X import ...` 와
    #    이중 import 가 되어 CodeQL `py/import-and-import-from` 을 자초한다(testing.md).
    # String-path patching avoids the dual-import form this file's top-level import would create.
    with patch("doc_review_gate._read_agent_prompt", return_value="sys"):
        asyncio.run(_call_single_agent(client, "impact", "diff", context))

    assert "TAIL_SENTINEL" in captured["user"], (
        "컨텍스트 꼬리가 프롬프트에서 잘렸다 — 이중 절단 회귀"
    )


# ──────────────────────────────────────────────────────────────────────────────
# 자격증명 전제 — **게이트가 아무것도 심의하지 않는 상태**를 관측한다
#
# 🔴 실측 (2026-08-01): 이 머신에 `ANTHROPIC_API_KEY` 가 없어 3 에이전트가 전부
#    `{"decision": "warn", "reason": "에이전트 호출 실패"}` 를 반환했고 veto 가 `warn` 으로
#    떨어져 exit 0. CRITICAL 등급 문서 게이트가 **배선돼 있고 · 실행되고 · 출력도 내면서
#    아무것도 심의하지 않았다.** 게다가 그 문구는 네트워크 blip 과 구별되지 않는다.
#
# 🔴 왜 6188건 스위트가 이걸 못 잡았나 — `tests/conftest.py:17` 이
#    `os.environ["ANTHROPIC_API_KEY"] = "sk-test-key"` 로 **모든 테스트에 키를 주입**한다.
#    즉 테스트 환경은 **운영의 실패 조건을 재현할 수 없도록 구성**돼 있었다.
#    아래 테스트는 그래서 `monkeypatch.delenv` 로 그 조건을 **명시적으로 복원**한다.
#    (같은 함정: 테스트가 항상 통과하는 이유가 '코드가 옳아서' 가 아닐 수 있다.)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def no_credentials(monkeypatch, tmp_path):
    """운영의 실제 조건 — 환경변수도 `.env` 도 없는 상태로 되돌린다.

    🔴 여기에 `import doc_review_gate as mod` 를 두지 말 것 — 이 파일 상단이 이미
    `from doc_review_gate import ...` 라 **이중 import**(CodeQL `py/import-and-import-from`)가
    되고 CI `Block new dual-import` 가 차단한다. 이 세션에서 **두 번** 걸린 자리다.
    monkeypatch 는 string-path 로 충분하다(testing.md).
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    # `.env` 탐색이 리포 실파일을 보지 않도록 훅 디렉토리를 임시 트리로 돌린다.
    monkeypatch.setattr("doc_review_gate._HOOKS_DIR", tmp_path / "repo" / ".claude" / "hooks")
    return tmp_path / "repo"


def test_api_key_is_empty_without_env_or_dotenv(no_credentials):
    """🔴 전제 확인 — 이 조건에서 자격증명은 없다(테스트가 공허하지 않음을 보장)."""
    from doc_review_gate import _api_key

    assert _api_key() == ""


def test_api_key_falls_back_to_dotenv(no_credentials, monkeypatch):
    """🔴 훅은 pydantic Settings 를 안 거치므로 `.env` 를 직접 읽어야 한다.

    이 fallback 이 없으면 키를 `.env` 에만 넣어 둔 사용자에게 게이트가 영영 죽어 있는다.
    """
    from doc_review_gate import _api_key

    repo = no_credentials
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".env").write_text(
        "OTHER=1\nANTHROPIC_API_KEY='sk-from-dotenv'\n", encoding="utf-8"
    )
    assert _api_key() == "sk-from-dotenv"


def test_env_var_wins_over_dotenv(no_credentials, monkeypatch):
    from doc_review_gate import _api_key

    repo = no_credentials
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".env").write_text("ANTHROPIC_API_KEY=sk-from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
    assert _api_key() == "sk-from-env"


def test_gate_without_credentials_announces_it_is_inoperative(no_credentials, capsys):
    """🔴 배선 테스트(불변식 3) — 자격증명이 없으면 **에이전트를 부르지 않고** 그 사실을 말한다.

    이전 동작: 3 에이전트를 호출 → 전부 동일한 "에이전트 호출 실패" → veto `warn` → exit 0.
    리뷰어에게 "일시 오류" 로 읽히고, 게이트가 죽었다는 정보는 어디에도 없었다.
    """
    from doc_review_gate import main

    payload = json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": "CLAUDE.md", "old_string": "a", "new_string": "b"},
    })
    with patch("sys.stdin", io.StringIO(payload)):
        with patch("doc_review_gate.call_agents_parallel") as mock_agents:
            with pytest.raises(SystemExit) as exc:
                main()

    assert exc.value.code == 0, "자격증명 부재는 차단이 아니다(advisory — 정책 17)"
    assert not mock_agents.called, (
        "자격증명이 없는데 에이전트를 호출했다 — 실패 3줄이 '일시 오류' 로 위장된다"
    )
    # 🔴 **채널까지** 단언한다 — `"INOPERATIVE" in out` 만 보면 plain print 로 되돌려도
    #    통과한다(실측: 이 파일의 초판이 정확히 그랬다). 공식 계약상 PreToolUse 의
    #    plain stdout 은 Claude 에게 도달하지 않으므로, 텍스트만 보는 단언은 theatre 를
    #    봉인하지 못한다(Grok claim-review `019fbb65`).
    # Assert the channel, not just the text: plain print would keep this green while never
    # reaching Claude.
    emitted = json.loads(capsys.readouterr().out)
    ctx = emitted["hookSpecificOutput"]["additionalContext"]
    assert "INOPERATIVE" in ctx, f"게이트 무동작이 Claude 채널에 실리지 않았다: {ctx!r}"
    assert "reviewed NOTHING" in ctx
    assert "INOPERATIVE" in emitted["systemMessage"], "사용자 채널 누락"
    assert "permissionDecision" not in emitted["hookSpecificOutput"], (
        "고지에 권한 결정을 얹으면 안 된다 — `allow` 는 사용자 확인을 건너뛸 수 있다"
    )


def test_inoperative_banner_is_distinguishable_from_a_transient_failure():
    """🔴 이 사고의 핵심 — 두 문구가 **구별 가능**해야 한다.

    구판은 자격증명 부재와 네트워크 blip 이 **같은 문자열**("에이전트 호출 실패")을 냈다.
    구별 불가능한 신호는 신호가 아니다.
    """
    from doc_review_gate import _NO_CREDENTIALS_BANNER

    transient = "에이전트 호출 실패"
    assert transient not in _NO_CREDENTIALS_BANNER
    assert "INOPERATIVE" in _NO_CREDENTIALS_BANNER
    assert "ANTHROPIC_API_KEY" in _NO_CREDENTIALS_BANNER, "복구 방법이 없으면 배너가 무용하다"


def test_conftest_injects_a_key_so_the_default_suite_cannot_see_this(no_credentials):
    """🔴 메타 — 왜 6188건이 이 결함을 못 봤는지 **파일로 고정**한다.

    `tests/conftest.py` 가 모든 테스트에 `ANTHROPIC_API_KEY` 를 주입하므로, 위 fixture 로
    명시적으로 지우지 않는 한 어떤 테스트도 운영의 실제 조건에 도달하지 못한다.
    이 단언이 깨지면(주입이 사라지면) 그 자체가 알아야 할 변화다.
    """
    conftest = (Path(__file__).resolve().parents[2] / "conftest.py").read_text(encoding="utf-8")
    assert 'os.environ["ANTHROPIC_API_KEY"]' in conftest, (
        "conftest 의 키 주입이 사라졌다 — 이 파일의 경고 주석과 격리 fixture 를 재검토할 것"
    )


# ──────────────────────────────────────────────────────────────────────────────
# 🔴 Grok claim-review `019fbb2d` 적발 — **선점검과 클라이언트가 갈라져 있었다**
#
# 초판은 `_api_key()` 로 선점검만 하고, 클라이언트는 `os.environ.get(...)` 를 **따로** 읽었다.
# 그래서 키가 `.env` 에만 있으면:
#   선점검 통과(배너 없음) → 클라이언트 빈 키 → 3 에이전트 "에이전트 호출 실패" → warn → exit 0
# 즉 **이 수정이 도우려던 사용자 계층에서, 배너까지 사라진 더 나쁜 무음 경로**가 됐다.
# observer-lie 를 고치는 코드가 observer-lie 를 만든 것 — 이 세션 3번째 재생산.
# ──────────────────────────────────────────────────────────────────────────────

def test_client_uses_the_same_credential_source_as_the_preflight(no_credentials, monkeypatch):
    """🔴 배선 테스트(불변식 3) — `.env` 전용 키가 **클라이언트까지** 도달해야 한다.

    이 단언이 없으면 `_api_key()` 가 아무리 옳아도 게이트는 여전히 인증 실패한다.
    """
    import asyncio

    from doc_review_gate import call_agents_parallel

    repo = no_credentials
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".env").write_text("ANTHROPIC_API_KEY=sk-only-in-dotenv\n", encoding="utf-8")

    seen = {}

    class _FakeClient:
        def __init__(self, **kwargs):
            seen.update(kwargs)
            self.messages = MagicMock()

    with patch("anthropic.AsyncAnthropic", _FakeClient):
        with patch("doc_review_gate._call_single_agent", new=AsyncMock(return_value={})):
            asyncio.run(call_agents_parallel("critical", "diff", "ctx"))

    assert seen.get("api_key") == "sk-only-in-dotenv", (
        f"클라이언트가 선점검과 다른 원천을 읽는다 — `.env` 전용 키가 조용히 죽는다: {seen!r}"
    )


def test_auth_token_counts_as_a_credential(no_credentials, monkeypatch):
    """🔴 오경보 방지 — `ANTHROPIC_AUTH_TOKEN` 만 있는 머신을 INOPERATIVE 로 부르면 안 된다.

    올바로 설정된 환경에 거짓 경보를 내는 것은 fail-open 의 반대 방향이지만 똑같이 해롭다
    (실배선 거부 = 가드 자살, 정책 17 안정성 우선).
    """
    from doc_review_gate import _credentials

    assert _credentials() == {}, "전제 붕괴 — 이 상태에서는 자격증명이 없어야 한다"
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "at-valid")
    assert _credentials() == {"auth_token": "at-valid"}


def test_api_key_wins_over_auth_token(no_credentials, monkeypatch):
    from doc_review_gate import _credentials

    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "at-valid")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-valid")
    assert _credentials() == {"api_key": "sk-valid"}


@pytest.mark.parametrize(("content", "expected", "shape"), [
    ("export ANTHROPIC_API_KEY=sk-exported\n", "sk-exported", "export 접두사"),
    ("\ufeffANTHROPIC_API_KEY=sk-bom\n", "sk-bom", "UTF-8 BOM"),
    ("ANTHROPIC_API_KEY=sk-plain # 설명\n", "sk-plain", "인라인 주석"),
    ("ANTHROPIC_API_KEY='sk-with#hash'\n", "sk-with#hash", "따옴표 안의 #(주석 아님)"),
    ("ANTHROPIC_API_KEY=sk-first\nANTHROPIC_API_KEY=sk-last\n", "sk-last", "중복 키 = 마지막이 이김"),
    ("ANTHROPIC_API_KEY_OLD=sk-other\n", "", "접두사 충돌은 매칭 금지"),
    ("ANTHROPIC_API_KEY=   \n", "", "공백만 = 값 없음"),
])
def test_dotenv_parser_handles_real_world_shapes(no_credentials, content, expected, shape):
    """🔴 "키가 있는데 없다고 말하는" 반대 방향 거짓말 차단 — 4형태 전부 실측 재현됐다."""
    from doc_review_gate import _dotenv_value

    repo = no_credentials
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".env").write_text(content, encoding="utf-8")
    assert _dotenv_value("ANTHROPIC_API_KEY") == expected, f"형태: {shape}"


def test_dotenv_read_failure_does_not_kill_the_hook(no_credentials):
    """🔴 `.env` 가 디렉토리면 `read_text` 가 던진다 — 훅은 advisory 라 죽으면 안 된다."""
    from doc_review_gate import _dotenv_value

    repo = no_credentials
    (repo / ".env").mkdir(parents=True, exist_ok=True)
    assert _dotenv_value("ANTHROPIC_API_KEY") == ""


def test_kill_switch_precedes_the_banner(no_credentials, monkeypatch, capsys):
    """🔴 kill-switch 가 켜져 있으면 배너도 내지 않는다 — 의도적 비활성에 스팸 금지."""
    from doc_review_gate import main

    monkeypatch.setenv("DOC_REVIEW_GATE_DISABLED", "1")
    payload = json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": "CLAUDE.md", "old_string": "a", "new_string": "b"},
    })
    with patch("sys.stdin", io.StringIO(payload)):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == "", "비활성 상태에서 배너를 냈다"


# ──────────────────────────────────────────────────────────────────────────────
# 🔴 훅 출력 **채널** 계약 (2026-08-01 — Grok claim-review `019fbb65` + 공식 문서 확인)
#
# 이 훅의 advisory 는 전부 plain `print()` 였고, 그건 **Claude 에게 도달하지 않는다**:
#   공식 계약 — "exit 0 의 stdout 은 디버그 로그로만 간다. 예외는 UserPromptSubmit ·
#   UserPromptExpansion · SessionStart 셋뿐" (PreToolUse 는 목록에 없다).
# 실측도 일치했다: 배너 도입 후 CRITICAL 문서 3회 편집에서 에이전트 도구 결과에 **0회** 출현.
#
# 🔴 내가 처음 내놓은 시정안(SessionStart 로 이관)은 **기각됐다** — SessionStart 는 세션당
#    1회라 세션 중간에 키가 만료/취소되면 **stale-green** 이 된다. "안 보이지만 live" 가
#    "보이지만 stale" 보다 낫다. 올바른 채널은 PreToolUse 의 `additionalContext` 다.
# ──────────────────────────────────────────────────────────────────────────────

_ADVISORY_PATHS = (
    ("CLAUDE.md", "critical"),
    ("docs/design/foo.md", "important"),
)


def _emit(monkeypatch, capsys, message="TEST_ADVISORY_MARKER"):
    from doc_review_gate import _emit_advisory

    _emit_advisory(message)
    return json.loads(capsys.readouterr().out)


def test_advisory_goes_to_the_claude_channel(monkeypatch, capsys):
    """🔴 `additionalContext` = Claude 가 실제로 보는 유일한 PreToolUse 채널."""
    emitted = _emit(monkeypatch, capsys)
    assert emitted["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert emitted["hookSpecificOutput"]["additionalContext"] == "TEST_ADVISORY_MARKER"


def test_advisory_goes_to_the_user_channel(monkeypatch, capsys):
    """🔴 `systemMessage` = 사용자 터미널 채널. Claude 채널과 **다른 대상**이다."""
    emitted = _emit(monkeypatch, capsys)
    assert emitted["systemMessage"] == "TEST_ADVISORY_MARKER"


def test_advisory_never_carries_a_permission_decision(monkeypatch, capsys):
    """🔴 안전 — 고지에 `permissionDecision` 을 얹지 않는다.

    `"allow"` 는 사용자 권한 확인을 **건너뛸 수 있다**. 단순 고지를 전달하려고 권한 흐름을
    바꾸는 것은 명백한 결함이라, 이 훅이 그 방향으로 진화하는 것을 여기서 막는다.
    """
    emitted = _emit(monkeypatch, capsys)
    assert "permissionDecision" not in emitted["hookSpecificOutput"]
    assert "permissionDecisionReason" not in emitted["hookSpecificOutput"]


def test_advisory_output_is_ascii_safe(monkeypatch, capsys):
    """🔴 Windows cp949 stdout — 비-ASCII 가 훅을 죽인 전례(#1243)."""
    from doc_review_gate import _emit_advisory

    _emit_advisory("한글 — em-dash 🔴")
    raw = capsys.readouterr().out
    assert raw.isascii(), "ensure_ascii 누락 — cp949 에서 훅이 죽는다"
    assert json.loads(raw)["systemMessage"] == "한글 — em-dash 🔴"


@pytest.mark.parametrize(("path", "grade"), _ADVISORY_PATHS)
def test_no_advisory_path_uses_bare_print(path, grade):
    """🔴 소스 감사 — advisory 경로가 다시 bare `print(...)` 로 돌아가지 않게 한다.

    `_emit_advisory` 를 정의만 하고 호출부를 되돌리면 위 단언들은 **여전히 통과**한다
    (그 함수를 직접 부르는 테스트이므로). 그래서 `main()` 이 실제로 그것을 쓰는지 본다 —
    정의 ≠ 배선(불변식 3).
    """
    source = (Path(__file__).resolve().parents[3] / ".claude" / "hooks"
              / "doc_review_gate.py").read_text(encoding="utf-8")
    assert grade in ("critical", "important")   # 파라미터가 공허하지 않음을 표시
    assert "print(_NO_CREDENTIALS_BANNER)" not in source, "자격증명 배너가 bare print 로 회귀"
    assert "print(_format_warn(" not in source, "warn 경로가 bare print 로 회귀"
    assert source.count("_emit_advisory(") >= 3, "정의 1 + 호출 2 이상이어야 한다"


# ──────────────────────────────────────────────────────────────────────────────
# 🔴 2차 스코프 복구 회귀 가드 (2026-08-01 문서 감사)
#
# R9(2026-07-29)가 AGENTS/rules/policies 를 복구한 뒤에도 **행동 지시를 담은 표면 25개**가
# `skip` 으로 남아 있었다 — 추적 비-archive 101개 중 50개가 skip 이었다. 대표:
# `docs/runbooks/ai-collaboration.md`(정책 19 프로토콜 SSOT · "P0/P1 부여 금지"),
# `docs/architecture.md`("갱신 의무"), `docs/reference/env-vars.md`("운영 절대 설정 금지"),
# PR 템플릿 · CONTRIBUTING · backlog · agents-index.
#
# 🔴 위 `test_behavioural_rule_docs_are_never_skipped` 는 AGENTS/rules/policies 만 스캔해
#    이 25개를 **한 번도 보지 않았다**. 스캔 범위가 좁은 가드는 "있는데 안 보는" 형태다.
# ──────────────────────────────────────────────────────────────────────────────

def test_directive_bearing_surfaces_are_reviewed():
    """🔴 에이전트가 따르는 지시문을 담은 문서는 `skip` 이면 안 된다.

    디스크를 스캔하므로 신규 런북/가이드가 추가돼도 자동으로 검사 대상이 된다.
    """
    root = Path(__file__).resolve().parents[3]
    targets = sorted((root / "docs" / "runbooks").glob("*.md"))
    targets += sorted((root / "docs" / "reference").glob("*.md"))
    targets += sorted((root / ".claude" / "plans").glob("*.md"))
    targets += [
        root / "docs" / "architecture.md",
        root / "docs" / "backlog.md",
        root / "docs" / "agents-index.md",
        root / ".github" / "PULL_REQUEST_TEMPLATE.md",
        root / "CONTRIBUTING.md",
        root / "CONTRIBUTING.ko.md",
        root / "SECURITY.md",
    ]
    targets = [t for t in targets if t.exists()]
    assert len(targets) > 25, f"대조 집합이 {len(targets)}개 — 스캐너 고장 또는 경로 변경"

    skipped = [
        t.relative_to(root).as_posix() for t in targets
        if classify_file_grade(t.relative_to(root).as_posix()) == "skip"
    ]
    assert not skipped, (
        "지시문을 담은 문서가 심의 대상에서 빠졌다(false coverage): "
        f"{skipped}\n→ doc_review_gate.py 의 _IMPORTANT 패턴을 확인할 것."
    )


def test_nested_design_docs_are_not_skipped():
    """🔴 `docs/design/brief/*` 5개가 한 세그먼트 패턴 때문에 빠져 있었다."""
    root = Path(__file__).resolve().parents[3]
    nested = sorted((root / "docs" / "design").rglob("*/*.md"))
    assert nested, "중첩 design 문서를 못 찾았다 — 이 단언이 공허하다"
    for p in nested:
        rel = p.relative_to(root).as_posix()
        assert classify_file_grade(rel) != "skip", f"{rel} 이 skip 이다 — 중첩 경로 패턴 확인"


def test_skip_set_is_small_and_deliberate():
    """🔴 skip 이 다시 불어나면 **아무도 모르게** false coverage 가 돌아온다.

    남겨 둔 skip 은 색인·과거 서사·시점 스냅샷뿐이어야 한다(소스에 사유가 기록돼 있다).
    """
    import subprocess  # nosec B404 — 리포 자신의 파일 목록만 읽는다

    root = Path(__file__).resolve().parents[3]
    files = [
        f for f in subprocess.run(  # nosec B603 B607
            ["git", "ls-files", "*.md"], cwd=str(root), capture_output=True,
            text=True, encoding="utf-8", errors="replace", check=True,
        ).stdout.split()
        if "_archive" not in f
    ]
    assert len(files) > 80, f"추적 문서를 {len(files)}개만 찾았다 — 스캐너 확인"
    skipped = sorted(f for f in files if classify_file_grade(f) == "skip")
    assert len(skipped) <= 8, (
        f"skip 이 {len(skipped)}개로 늘었다 — false coverage 재발 위험:\n  {skipped}\n"
        "→ 새로 추가된 문서가 지시문을 담는다면 _IMPORTANT 에 등재할 것."
    )


# ── R35/R36 — 미심의(inoperative)는 승인이 아니다 / not-reviewed is never approve ──
#
# 회고 2026-08-04 확정 P0 + Grok claim-review `019fc81b`(GROK-1·2·6·7).
# 지배 결함: 게이트가 **아무것도 심의하지 못한 상태**와 **심의해서 통과시킨 상태**가
# 같은 값을 갖는다. 아래는 그 등가를 깨는 단언들이다.
# The gate could not distinguish "reviewed nothing" from "reviewed and approved".


def test_missing_decision_key_is_not_a_silent_approve():
    """🔴 스키마 drift(= `decision` 키 없음)가 조용히 approve 가 되면 안 된다 (R35, GROK-6).

    `r.get("decision", "approve")` 기본값이 **판정 부재를 판정으로 바꾼다**. 에이전트가
    스키마를 바꾸거나 부분 응답을 내면 게이트 전체가 무음 통과한다.
    """
    decision, reasons = apply_veto_matrix("critical", [{"agent": "impact", "reason": "키 없음"}])
    assert decision != "approve", "판정 키가 없는데 승인으로 처리됐다"
    assert reasons, "사유가 비어 있으면 사용자에게 아무것도 도달하지 않는다"


def test_unknown_decision_value_is_not_a_silent_approve():
    """🔴 범례 밖 판정값(`maybe` 등)도 마찬가지다 (R35, GROK-6)."""
    decision, _ = apply_veto_matrix(
        "critical", [{"agent": "impact", "decision": "maybe", "reason": "??"}]
    )
    assert decision != "approve", "알 수 없는 판정값이 승인으로 처리됐다"


def test_empty_results_is_not_approve():
    """🔴 결과가 0건이면 심의가 일어나지 않은 것이다 — approve 가 아니다 (R35, GROK-6)."""
    decision, _ = apply_veto_matrix("critical", [])
    assert decision != "approve", "빈 결과가 승인으로 처리됐다"


def test_inoperative_result_never_reaches_approve():
    """🔴 `inoperative` 표기가 붙은 결과가 하나라도 있으면 approve 로 끝나지 않는다 (R36)."""
    results = [
        {"agent": "impact", "decision": "approve", "reason": "OK"},
        {"agent": "consistency", "decision": "warn", "reason": "응답 파싱 실패 — 미심의",
         "inoperative": True, "detail": "원문"},
        {"agent": "quality", "decision": "approve", "reason": "OK"},
    ]
    decision, _ = apply_veto_matrix("critical", results)
    assert decision != "approve", "3 중 1이 미심의인데 전건 승인으로 보고됐다"


def test_all_agents_inoperative_says_it_reviewed_nothing(monkeypatch, capsys):
    """🔴 3/3 전건 미심의는 '3명이 경고하며 심의함' 과 **문구가 달라야** 한다 (R36).

    세션14 가 8회+ 실제로 앉아 있던 상태다. 그때 출력은 정상 warn 과 구별되지 않았고,
    그래서 게이트가 무동작이라는 사실이 원장에 오르지 못한 채 다음 세션까지 갔다.
    단언은 결과(=warn)가 아니라 **분기 고유 문구**를 고정한다 — 그래야 죽은 분기를 잡는다.
    """
    # 🔴 `import doc_review_gate as mod` 금지 — 상단이 이미 `from doc_review_gate import ...`
    #    라 이중 import(CodeQL `py/import-and-import-from`)가 된다. string-path 로 패치한다
    #    (.claude/rules/testing.md §모듈 패치 시 이중 import 회피 · `check_dual_import.py` 강제).
    from doc_review_gate import main

    monkeypatch.setattr("doc_review_gate._credentials", lambda: {"api_key": "x"})
    monkeypatch.setattr("doc_review_gate._load_context", lambda: "ctx")
    monkeypatch.setattr("doc_review_gate.classify_file_grade", lambda _p: "critical")
    monkeypatch.setattr("doc_review_gate.call_agents_parallel", AsyncMock(return_value=[
        {"agent": a, "decision": "warn", "reason": "에이전트 호출 실패",
         "inoperative": True, "detail": "보이는-원인-문구"}
        for a in ("impact", "consistency", "quality")
    ]))
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps({"tool_input": {
            "file_path": "CLAUDE.md", "old_string": "a", "new_string": "b"}})),
    )

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0, "advisory 는 편집을 차단하지 않는다(정책 17 안정성)"

    out = capsys.readouterr().out
    assert out.strip(), "전건 미심의인데 출력이 비었다 — 관측면 0"

    # 🔴 텍스트 substring 이 아니라 **JSON 형태를 파싱**해 단언한다 (guards.md §훅 출력 채널):
    #    `assert "MARKER" in out` 은 bare print 로 되돌려도 통과해 채널 회귀를 못 잡는다.
    #    또 출력은 ensure_ascii=True JSON 이라 한글이 \uXXXX 로 escape 된다 — 파싱이 필수다.
    payload = json.loads(out)
    hook_out = payload["hookSpecificOutput"]
    assert hook_out["hookEventName"] == "PreToolUse"
    assert "permissionDecision" not in hook_out, "advisory 에 권한 결정을 얹으면 안 된다"
    banner = hook_out["additionalContext"]
    assert banner == payload["systemMessage"], "Claude 채널과 사용자 채널이 갈라졌다"

    assert "REVIEWED NOTHING" in banner.upper(), (
        f"'아무것도 심의하지 않았다' 를 말하는 고유 문구가 없다:\n{banner}"
    )
    assert "3/3" in banner, f"몇 개가 죽었는지 숫자가 없다:\n{banner}"
    assert "보이는-원인-문구" in banner, f"예외 원문이 사용자에게 도달하지 않는다:\n{banner}"


# ── R37 — "확인 불가" 는 차단 사유가 아니다 / inability to verify is not a block reason ──
#
# 회고 2026-08-04 P1 + Grok `019fc81b` GROK-4·5.
# 🔴 원 finding 의 기전 서술("종합수치 라인이 char 11132 라 심의자가 못 본다")은 **반증됐다** —
#    `6607`@3023 · `6778`@3105 로 주 카운트는 4000자 예산 **안**에 있었다(부분 실명).
#    실재하는 결함은 두 개다: (a) 예산 밖인 pylint·커버리지 (b) `critical` 등급에서
#    consistency 의 block 이 **"확인 불가 ⇒ block 아님" 강등 없이** 곧장 deny 로 간다.


def test_state_context_budget_reaches_the_aggregate_numbers():
    """🔴 심의자에게 대조 대상을 **실제로** 보여준다 (R37-a).

    이전 예산(4000자)은 STATE.md 의 4%만 실어, 형식 `**종합 수치**` 블록과 pylint 값이
    통째로 잘렸다. 그 상태로 consistency 에이전트에게 "STATE 수치와 다르면 block" 을
    지시하는 것은 **볼 수 없는 것을 근거로 차단하라**는 모순이다.
    기대 지문은 테스트 쪽에 고정한다 — 피검사 모듈에서 유도하면 원천 삭제 시 공허해진다
    (guards.md §기대값을 피검사 모듈에서 유도하지 말 것).

    🔴 이 테스트의 초판은 **공허했다**: 컨텍스트 전문에 대해 `"pylint" in ctx` 를 봤는데
    그 문자열은 CLAUDE.md 구간에도 있어, STATE 예산을 4000 으로 되돌려도 GREEN 이었다.
    단언은 반드시 **STATE 구간으로 한정**해야 예산 축을 관측한다.
    The first revision asserted over the whole context, so the fingerprints matched other
    sources and the STATE budget axis was never observed.
    """
    from doc_review_gate import _load_context

    ctx = _load_context()
    marker = "=== docs/STATE.md"
    assert marker in ctx, "STATE 원천이 컨텍스트에서 사라졌다"

    # STATE 헤더부터 다음 원천 헤더(또는 끝)까지가 실제로 실린 STATE 구간이다.
    # Slice the STATE section only — from its header to the next source header.
    state_section = ctx[ctx.index(marker):]
    nxt = state_section.find("\n=== ", len(marker))
    if nxt != -1:
        state_section = state_section[:nxt]

    assert "종합 수치" in state_section, "형식 종합수치 블록이 예산 밖이다 — 대조 대상을 못 본다"
    assert "pylint" in state_section, "pylint 값이 예산 밖이다 — 대조 대상을 못 본다"


def test_unable_to_verify_block_is_demoted_to_warn():
    """🔴 근거를 못 봐서 낸 block 은 deny 가 아니라 warn 이다 (R37-b, GROK-5).

    `critical` 등급에서 consistency 의 block 은 곧장 `deny` 로 간다 — `important` 경로에는
    이미 강등이 있는데(`_agent_label` 아래 else 분기) `critical` 에만 없었다.
    그 결과 6-step ⑤(STATE 수치 동기화)라는 **의무 절차**가 차단될 수 있다.
    """
    results = [{"agent": "consistency", "decision": "block",
                "reason": "STATE.md 를 볼 수 없어 확인 불가", "unable_to_verify": True}]
    decision, reasons = apply_veto_matrix("critical", results)
    assert decision == "warn", "확인 불가가 deny 로 승격됐다 — 의무 절차가 막힌다"
    assert reasons, "강등해도 사유는 사용자에게 도달해야 한다"


def test_unable_to_verify_does_not_soften_a_real_block():
    """🔴 대조군 — 근거를 보고 낸 block 은 그대로 차단이다 (강등이 게이트를 죽이면 안 된다)."""
    results = [{"agent": "consistency", "decision": "block",
                "reason": "STATE 6607 인데 본문은 6600 — 실제 불일치"}]
    decision, _ = apply_veto_matrix("critical", results)
    assert decision == "block", "실 불일치까지 강등되면 게이트가 무의미해진다"


def test_unable_to_verify_never_softens_impact_analyzer():
    """🔴 impact-analyzer 의 block 은 모든 등급에서 차단이다 — 행동 변화 위험은 강등 대상이 아니다."""
    results = [{"agent": "impact", "decision": "block",
                "reason": "규칙 삭제", "unable_to_verify": True}]
    decision, _ = apply_veto_matrix("critical", results)
    assert decision == "block", "impact 차단이 강등됐다 — 가드 자살"


# ── R36-b — lone surrogate 가 게이트를 통째로 죽인다 / lone surrogates killed the gate ──
#
# 🔴 **라이브 발견 (2026-08-04)**: R36 의 `detail` 노출이 만들어지자마자, 세션14 이후
#    9회+ 반복된 "에이전트 호출 실패" 의 진짜 원인이 처음으로 보였다:
#        'utf-8' codec can't encode characters in position 196-198: surrogates not allowed
#    자격증명 축이 아니었다. 훅이 조립한 프롬프트에 **lone surrogate** 가 섞여 있어
#    httpx 가 요청 본문을 UTF-8 로 인코딩할 때 터졌고, 3 에이전트가 동일하게 죽었다.
#    원장이 "키 만료/크레딧 재확인" 을 요청하고 있던 것은 **틀린 가설**이었다.
#    Exactly the class R36 exists for: the cause was in the discarded exception text.


def test_lone_surrogate_in_diff_does_not_kill_the_call():
    """🔴 서로게이트가 섞인 입력으로도 호출이 조립돼야 한다 (R36-b).

    뮤테이션 관점: 정화를 제거하면 `client.messages.create` 에 도달하기도 전에
    UnicodeEncodeError 가 나거나, 도달해도 전송 단계에서 죽는다.
    """
    import asyncio

    from doc_review_gate import _call_single_agent

    dirty = "정상 텍스트 " + "\ud83d" + " 뒤쪽"   # lone high surrogate
    captured = {}

    async def _fake_create(**kwargs):
        captured["user"] = kwargs["messages"][0]["content"]
        captured["system"] = kwargs["system"]
        raise RuntimeError("stop — 조립만 관측한다")

    client = MagicMock()
    client.messages.create = _fake_create

    with patch("doc_review_gate._read_agent_prompt", return_value="sys " + "\udcff"):
        asyncio.run(_call_single_agent(client, "impact", dirty, "ctx " + "\ud800"))

    for key in ("user", "system"):
        payload = captured[key]
        # 🔴 결과가 아니라 **전송 가능성**을 단언한다 — 이 인코딩이 실제 실패 지점이었다.
        payload.encode("utf-8")   # 서로게이트가 남아 있으면 여기서 UnicodeEncodeError
        assert not any("\ud800" <= ch <= "\udfff" for ch in payload), (
            f"{key} 에 lone surrogate 가 남았다 — 전송 시 3 에이전트가 동시에 죽는다"
        )
