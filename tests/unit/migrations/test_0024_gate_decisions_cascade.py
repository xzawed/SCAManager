"""Phase H — gate_decisions.analysis_id ON DELETE CASCADE 회귀 가드 (Critical C7).

12-에이전트 감사 (2026-04-30) Critical C7 — `gate_decisions.analysis_id` FK 가
ondelete 미설정 → Repository/Analysis 삭제 시 FK violation 잠재.

본 테스트는 ORM 정의 측 `ondelete="CASCADE"` 가 유지되는지 검증.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position
from src.models.gate_decision import GateDecision


def test_gate_decision_analysis_id_fk_has_cascade_delete():
    """GateDecision.analysis_id FK 의 ondelete 가 CASCADE 인지 검증.

    Repository → Analysis CASCADE 사슬과 일관성 유지. 미설정 시 Analysis
    삭제 → FK violation → 운영 사고 가능.
    """
    fk_columns = list(GateDecision.__table__.c.analysis_id.foreign_keys)
    assert len(fk_columns) == 1, "analysis_id 에 FK 가 정확히 1개 있어야 함"
    fk = fk_columns[0]
    assert fk.ondelete == "CASCADE", (
        f"gate_decisions.analysis_id FK ondelete='{fk.ondelete}' — "
        "'CASCADE' 이어야 함 (Critical C7 회귀)"
    )
