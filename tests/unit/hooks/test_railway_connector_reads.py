"""운영 접근 훅 — claude.ai Railway 커넥터의 읽기 도구 (원장 #1940 이관 #1917-6).
Production-access hook: read tools of the claude.ai Railway connector.

운영 MCP 읽기 허용 목록은 로컬 railway MCP 의 밑줄 이름(`list_deployments`)만 알아, 커넥터의 하이픈 이름 읽기
(`list-deployments` · `get-logs`)를 «운영 실행 · 변경» 으로 막았다. 사용자 결정(11-28 · 권장안): CLI 로 이미 자율인
읽기와 같은 것(배포 목록 · 로그 · 상태 · 지표 · 문서 · 목록)만 넣고, 설정 · 변수가 섞일 수 있는 도구
(`describe-service` · `get-service-config` 등)는 값이 없음을 확인하기 전까지 넣지 않는다.
판정 표는 판정 함수를 부르고, 배선은 훅을 배선된 방식대로 subprocess 로 돌려 확인한다.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_HOOK = _ROOT / ".claude" / "hooks" / "block_credential_dump.py"
_CONNECTOR = "mcp__claude_ai_Railway__"


def _load_hook():
    spec = importlib.util.spec_from_file_location("block_credential_dump_for_connector_tests", _HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MOD = _load_hook()


def _run(tool_name):
    payload = {"tool_name": tool_name, "tool_input": {}}
    proc = subprocess.run([sys.executable, str(_HOOK)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, timeout=20, check=False, cwd=str(_ROOT))
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    text = proc.stdout.decode("utf-8", "replace").strip()
    if not text:
        return None, ""
    out = json.loads(text)["hookSpecificOutput"]
    return out["permissionDecision"], out["permissionDecisionReason"]


# 커넥터의 읽기 — CLI 의 자율 읽기(status · whoami · list · logs · metrics · docs · deployment/domain list)와 같은 것
# connector reads matching the CLI reads that are already autonomous
_CONNECTOR_READS = ["list-deployments", "get-logs", "get-status", "environment-status", "whoami", "list-projects",
                    "list-workspaces", "list-services", "get-service-metrics", "http-error-rate", "http-requests",
                    "http-response-time", "search-docs", "fetch-docs", "list-domains", "domain-status"]


@pytest.mark.parametrize("tool", _CONNECTOR_READS)
def test_a_connector_read_is_allowed(tool):
    """커넥터의 배포 목록 · 로그 · 상태 · 지표 · 문서 · 목록 읽기는 통과한다."""
    assert _MOD.decide_mcp_production_access(_CONNECTOR + tool) is None, tool


@pytest.mark.parametrize("tool", ["list-deployments", "get-logs"])
def test_a_connector_read_passes_the_wired_hook(tool):
    """배선된 훅도 통과시킨다 — 판정 함수만 재면 main() 이 다른 길로 막아도 초록이다."""
    assert _run(_CONNECTOR + tool) == (None, ""), tool


def test_a_connector_read_leaves_an_audit_record(tmp_path, monkeypatch):
    """허용된 운영 읽기는 감사 기록 한 줄을 남긴다 — 커넥터 읽기도 로컬 MCP 읽기처럼 채널 이름으로 적힌다."""
    audit = tmp_path / "allows.jsonl"
    monkeypatch.setenv("SCAMANAGER_HOOK_AUDIT_LOG", str(audit))
    assert _run(_CONNECTOR + "get-logs") == (None, "")
    records = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert [record["channels"] for record in records] == [["Railway MCP get-logs"]]


# witness-corpus: 설정 · 변수 · 비밀이 섞이거나 운영을 바꾸는 커넥터 도구 — 읽기 목록에 넣지 않았다(사용자 결정)
_CONNECTOR_NOT_READS = ["describe-service", "get-service-config", "describe-environment", "get-bucket-credentials",
                        "get-staged-changes", "railway-agent", "redeploy", "accept-deploy", "set-variables"]


@pytest.mark.parametrize("tool", _CONNECTOR_NOT_READS)
def test_a_connector_tool_outside_the_reads_is_denied(tool):
    """🔴 값이 없음을 확인하지 않은 도구 · 운영을 바꾸는 도구는 그대로 막는다(허용 목록 밖은 모두)."""
    assert _MOD.decide_mcp_production_access(_CONNECTOR + tool), tool


def test_the_connector_variable_listing_is_a_value_dump():
    """🔴 커넥터의 `list-variables` 도 값 덤프로 막는다 — 덤프 이름 검사가 밑줄 · 소문자 서버 이름만 알았다."""
    decision, reason = _run(_CONNECTOR + "list-variables")
    assert decision == "deny"
    assert "KEY=VALUE" in reason, reason


def test_a_hyphen_read_name_is_not_read_through_underscores():
    """🔴 대조군 — 로컬 MCP 의 밑줄 읽기 이름과 섞지 않는다: 커넥터의 `get-service-config` 는 로컬의 `get_service_config`
    가 허용이어도 막는다(값 확인 전)."""
    assert _MOD.decide_mcp_production_access("mcp__railway__get_service_config") is None
    assert _MOD.decide_mcp_production_access(_CONNECTOR + "get-service-config")
