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

    async def test_malformed_json_returns_approve(self):
        """JSON 파싱 실패 시 approve로 fallback — 작업 차단하지 않음."""
        from doc_review_gate import call_agents_parallel

        responses = ["JSON 아님", "JSON 아님", "JSON 아님"]
        mock_client = self._make_mock_client(responses)

        with patch("doc_review_gate.anthropic.AsyncAnthropic", return_value=mock_client):
            results = await call_agents_parallel("critical", "diff", "ctx")

        for r in results:
            assert r["decision"] in ("approve", "warn")


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
        output = capsys.readouterr().out
        assert "[문서 심의]" in output
        assert "quality" in output
        mock_exit.assert_called_with(0)
