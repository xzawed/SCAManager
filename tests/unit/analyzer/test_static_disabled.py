"""disabled_tools 인프라 테스트 — repo_config.disabled_tools에 등록된 도구는 스킵된다.
Infrastructure tests for disabled_tools — analyzers listed in repo_config.disabled_tools are skipped.
"""
import pytest
from src.analyzer.io.static import analyze_file


class FakeRepoConfig:
    """disabled_tools 필드만 가진 최소 stub.
    Minimal stub with only the disabled_tools field.
    """
    def __init__(self, disabled: list):
        self.disabled_tools = disabled


class TestDisabledTools:
    def test_disabled_tool_is_skipped(self):
        """disabled_tools에 등록된 도구는 analyze_file 결과에서 이슈를 반환하지 않아야 한다.
        A tool listed in disabled_tools must not appear in analyze_file results.
        """
        # pylint는 unused variable을 반드시 경고함 — 비활성화 시 이슈 0이어야 함
        # pylint reliably warns on unused variable — must produce 0 issues when disabled
        code = "def foo():\n    unused_var = 42\n    return 0\n"
        enabled_result = analyze_file("app.py", code, repo_config=None)
        pylint_enabled = [i for i in enabled_result.issues if i.tool == "pylint"]

        repo_cfg = FakeRepoConfig(disabled=["pylint"])
        disabled_result = analyze_file("app.py", code, repo_config=repo_cfg)
        pylint_disabled = [i for i in disabled_result.issues if i.tool == "pylint"]

        assert pylint_disabled == [], f"pylint should be skipped but got {pylint_disabled}"
        # 비활성화 전에는 이슈가 있어야 함 (vacuous pass 방지)
        # Issues must exist before disabling (prevents vacuous pass)
        assert len(pylint_enabled) > len(pylint_disabled), (
            "pylint must produce issues on unused variable to validate the disable logic"
        )

    def test_non_disabled_tool_still_runs(self):
        """disabled_tools에 없는 도구는 정상적으로 실행되어야 한다.
        Tools absent from disabled_tools must still run normally.
        """
        repo_cfg = FakeRepoConfig(disabled=["semgrep"])
        # bandit은 비활성화되지 않음 — pickle.loads 보안 이슈를 감지해야 한다
        # bandit is not disabled — should detect pickle.loads security issue
        code = "import pickle\npickle.loads(b'data')\n"
        result = analyze_file("app.py", code, repo_config=repo_cfg)
        bandit_issues = [i for i in result.issues if i.tool == "bandit"]
        assert len(bandit_issues) >= 1

    def test_no_repo_config_runs_all_tools(self):
        """repo_config=None이면 disabled_tools 체크 없이 모든 도구가 실행된다.
        When repo_config=None, all tools run without disabled_tools filtering.
        """
        code = "import pickle\npickle.loads(b'data')\n"

        result_none = analyze_file("app.py", code, repo_config=None)
        result_empty = analyze_file("app.py", code, repo_config=FakeRepoConfig(disabled=[]))

        # None과 빈 리스트 모두 동일하게 모든 도구를 실행해야 함
        # None and empty list must both run all tools identically
        assert len(result_none.issues) == len(result_empty.issues)
        assert isinstance(result_none.issues, list)
