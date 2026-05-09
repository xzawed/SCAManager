"""사이클 93 Step 2-A fix-up — generate_illustrations.py 단위 테스트 (mock).

Cycle 93 Step 2-A fix-up — generate_illustrations.py unit tests (mocked).

CI patch coverage 20.51% → 80%+ 회복 영역. 메모리 `feedback-ci-fixup-patch-coverage.md`
페어 (사이클 73 #244 학습) — 신규 service/repo/endpoint PR push 직전 80% 사전 검증 의무.

mock 패턴 = OpenAI client 전체 mock + tmp_path 출력 디렉토리 격리 + monkeypatch sys.argv.
production 의존성 X (src/scripts/ 영역) — 본 테스트만이 코드 회귀 가드 단일 source.
"""
from __future__ import annotations

import base64
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.scripts import generate_illustrations as gi


# 1×1 투명 PNG b64 (mock 응답용 — 실 이미지 없이 b64 → PNG 흐름 검증)
# 1×1 transparent PNG b64 (for mock responses — verifies b64 → PNG flow without real image)
_DUMMY_PNG_B64 = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d49444154789c63000100000005000100"
        "0d0a2db40000000049454e44ae426082"
    )
).decode("ascii")


def _build_mock_openai_client() -> MagicMock:
    """OpenAI client mock — images.generate(...) 호출 시 b64_json 응답 반환."""
    client = MagicMock()
    response = MagicMock()
    response.data = [MagicMock(b64_json=_DUMMY_PNG_B64)]
    client.images.generate.return_value = response
    return client


# ───────────────────────────── generate_one() ─────────────────────────────


def test_generate_one_dry_run_returns_none(capsys):
    """dry_run=True 시 API 호출 X + None 반환 + prompt stdout 출력."""
    result = gi.generate_one(client=None, name="login_hero", dry_run=True)
    assert result is None
    captured = capsys.readouterr()
    assert "login_hero" in captured.out
    assert "[dry-run]" in captured.out
    assert "isometric" in captured.out  # prompt 본문 포함 검증


def test_generate_one_calls_openai_with_prompt_args(tmp_path, monkeypatch):
    """API 호출 시 prompt/size/quality 정확 전달 검증."""
    monkeypatch.setattr(gi, "_OUTPUT_DIR", tmp_path)
    client = _build_mock_openai_client()
    gi.generate_one(client=client, name="login_hero", dry_run=False)
    client.images.generate.assert_called_once()
    call_kwargs = client.images.generate.call_args.kwargs
    assert call_kwargs["model"] == "dall-e-3"
    assert call_kwargs["size"] == "1024x1024"
    assert call_kwargs["quality"] == "hd"
    assert call_kwargs["n"] == 1
    assert call_kwargs["response_format"] == "b64_json"
    assert "isometric" in call_kwargs["prompt"]


def test_generate_one_writes_b64_to_disk(tmp_path, monkeypatch):
    """API 응답 b64_json → PNG 파일 저장 검증."""
    monkeypatch.setattr(gi, "_OUTPUT_DIR", tmp_path)
    client = _build_mock_openai_client()
    out_path = gi.generate_one(client=client, name="filter_empty", dry_run=False)
    assert out_path is not None
    assert out_path == tmp_path / "filter_empty.png"
    assert out_path.exists()
    assert out_path.read_bytes().startswith(b"\x89PNG")  # PNG magic header


def test_generate_one_handles_empty_b64_response(tmp_path, monkeypatch, capsys):
    """API 응답에 b64_json 부재 시 None 반환 + 에러 메시지 stdout."""
    monkeypatch.setattr(gi, "_OUTPUT_DIR", tmp_path)
    client = MagicMock()
    response = MagicMock()
    response.data = [MagicMock(b64_json=None)]
    client.images.generate.return_value = response
    result = gi.generate_one(client=client, name="add_repo_hero", dry_run=False)
    assert result is None
    assert "이미지 데이터 없음" in capsys.readouterr().out


# ───────────────────────────── main() ─────────────────────────────


def test_main_dry_run_skips_openai_check(monkeypatch, capsys):
    """dry-run 시 openai 미설치 + API key 부재도 통과 (검토 흐름 보장)."""
    monkeypatch.setattr(sys, "argv", ["generate_illustrations", "--all", "--dry-run"])
    monkeypatch.setattr(gi, "_OPENAI_AVAILABLE", False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = gi.main()
    assert result == 0
    captured = capsys.readouterr()
    assert "대상" in captured.out
    assert "5장" in captured.out  # PROMPTS 5장 모두 출력


def test_main_no_openai_returns_1(monkeypatch, capsys):
    """production mode + openai 부재 → exit 1 + 설치 안내."""
    monkeypatch.setattr(sys, "argv", ["generate_illustrations", "--name", "login_hero"])
    monkeypatch.setattr(gi, "_OPENAI_AVAILABLE", False)
    result = gi.main()
    assert result == 1
    assert "openai 패키지 미설치" in capsys.readouterr().err


def test_main_no_api_key_returns_1(monkeypatch, capsys):
    """openai 있고 + API key 부재 → exit 1 + key 안내."""
    monkeypatch.setattr(sys, "argv", ["generate_illustrations", "--name", "login_hero"])
    monkeypatch.setattr(gi, "_OPENAI_AVAILABLE", True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = gi.main()
    assert result == 1
    assert "OPENAI_API_KEY" in capsys.readouterr().err


def test_main_all_iterates_5_prompts(tmp_path, monkeypatch):
    """--all 시 PROMPTS 5장 모두 generate_one 호출."""
    monkeypatch.setattr(sys, "argv", ["generate_illustrations", "--all"])
    monkeypatch.setattr(gi, "_OPENAI_AVAILABLE", True)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(gi, "_OUTPUT_DIR", tmp_path)
    mock_client = _build_mock_openai_client()
    with patch.object(gi, "OpenAI", return_value=mock_client):
        result = gi.main()
    assert result == 0
    assert mock_client.images.generate.call_count == 5
    # 5장 모두 PNG 저장 검증
    assert len(list(tmp_path.glob("*.png"))) == 5


def test_main_single_name_runs_once(tmp_path, monkeypatch):
    """--name <single> 시 1회만 호출."""
    monkeypatch.setattr(
        sys, "argv", ["generate_illustrations", "--name", "dashboard_empty"]
    )
    monkeypatch.setattr(gi, "_OPENAI_AVAILABLE", True)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(gi, "_OUTPUT_DIR", tmp_path)
    mock_client = _build_mock_openai_client()
    with patch.object(gi, "OpenAI", return_value=mock_client):
        result = gi.main()
    assert result == 0
    assert mock_client.images.generate.call_count == 1
    assert (tmp_path / "dashboard_empty.png").exists()


def test_main_handles_api_error_returns_2(tmp_path, monkeypatch, capsys):
    """OpenAI API exception → exit 2 + 에러 메시지 stderr."""
    monkeypatch.setattr(sys, "argv", ["generate_illustrations", "--name", "login_hero"])
    monkeypatch.setattr(gi, "_OPENAI_AVAILABLE", True)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(gi, "_OUTPUT_DIR", tmp_path)
    mock_client = MagicMock()
    mock_client.images.generate.side_effect = RuntimeError("rate limit exceeded")
    with patch.object(gi, "OpenAI", return_value=mock_client):
        result = gi.main()
    assert result == 2
    assert "rate limit" in capsys.readouterr().err


def test_main_argparse_rejects_unknown_name(monkeypatch):
    """--name 에 PROMPTS 외 이름 → argparse SystemExit (choices 검증)."""
    monkeypatch.setattr(
        sys, "argv", ["generate_illustrations", "--name", "nonexistent"]
    )
    with pytest.raises(SystemExit):
        gi.main()


def test_main_argparse_requires_name_or_all(monkeypatch):
    """--name / --all 둘 다 부재 시 argparse SystemExit (mutually_exclusive_group required)."""
    monkeypatch.setattr(sys, "argv", ["generate_illustrations"])
    with pytest.raises(SystemExit):
        gi.main()
