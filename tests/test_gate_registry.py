"""gate.registry — GateAction Protocol + REGISTRY 등록 검증 (스캐폴딩).

src/gate/registry.py 와 src/gate/actions/ 는 향후 확장 대비 인프라이며
현재 engine.py 는 기존 직접 구현을 유지한다. 본 테스트는 구조적 정합성
검증용.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from src.gate.registry import REGISTRY, GateContext, GateAction, register  # noqa: E402
import src.gate.actions  # noqa: E402, F401 — auto-register


def test_gate_registry_contains_three_actions():
    """import 시 review_comment / approve / auto_merge 3개가 등록된다."""
    names = [a.name for a in REGISTRY]
    assert "review_comment" in names
    assert "approve" in names
    assert "auto_merge" in names


def test_gate_registry_action_order_preserved():
    """등록 순서 = review_comment → approve → auto_merge (실행 순서 보장)."""
    names = [a.name for a in REGISTRY]
    # 전체 순서 유지
    i_rc = names.index("review_comment")
    i_ap = names.index("approve")
    i_am = names.index("auto_merge")
    assert i_rc < i_ap < i_am


def test_gate_action_protocol_runtime_checkable():
    """GateAction 이 runtime_checkable Protocol 이다."""
    for action in REGISTRY:
        assert isinstance(action, GateAction), f"{action.name} 이 GateAction 을 준수하지 않음"


def test_gate_register_rejects_duplicate_name():
    """동일 name 으로 등록 시 REGISTRY 크기가 증가하지 않아야 한다."""
    before = len(REGISTRY)
    existing = REGISTRY[0]
    register(existing)  # 동일 name 재등록
    assert len(REGISTRY) == before


def test_gate_context_dataclass_fields():
    """GateContext 가 필요한 7개 필드를 가진다."""
    from dataclasses import fields
    names = {f.name for f in fields(GateContext)}
    assert names == {
        "repo_name", "pr_number", "analysis_id", "result",
        "github_token", "db", "config",
    }
