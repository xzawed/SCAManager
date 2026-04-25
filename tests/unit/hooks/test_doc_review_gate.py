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
        grade = classify_file_grade(
            "f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager/CLAUDE.md"
        )
        assert grade == "critical"

    def test_backslash_path_normalized(self):
        grade = classify_file_grade(
            "f:\\DEVELOPMENT\\SOURCE\\CLAUDE\\SCAManager\\.claude\\agents\\test-writer.md"
        )
        assert grade == "critical"
