"""alembic 0027 RLS policy — 의도적 divergence 가드 (정합성 감사 U1 종결).
alembic 0027 RLS policy — intentional-divergence guard (integrity-audit U1 closure).

0027 `security_alert_process_logs` RLS policy 는 0026 형제 정책(analyses/merge_attempts)과
달리 `OR user_id IS NULL` 절을 **의도적으로 생략**한다 — legacy(user_id NULL) repo 의
보안알림 로그를 전역 노출하지 않는 더 엄격한 격리(strict multi-tenancy 방향 정합).
0027 intentionally omits the `OR user_id IS NULL` clause that the 0026 sibling policies
(analyses/merge_attempts) carry — stricter isolation that does NOT expose a legacy
(user_id NULL) repo's security-alert logs globally.

U1 재검증(2026-06-13, 운영 legacy repo=0): integrity-audit 가 "0026 대비 절 누락"을 결함으로
flag 했으나 0027 작성자의 의도된 설계임을 확인 → false-positive 종결. 본 가드는 미래 감사/
리팩터가 무심코 `user_id IS NULL` 을 추가(= legacy 보안알림 cross-tenant 노출 = 보안 완화)
하지 못하도록 잠근다.
U1 re-verification (2026-06-13, operational legacy repos = 0): the audit flagged the missing
clause as a defect, but it is the original author's deliberate design → closed as a false
positive. This guard locks the divergence so a future audit/refactor cannot silently add
`user_id IS NULL` (which would expose legacy security-alert logs cross-tenant = weaker security).

🔴 의도적으로 0026식 "legacy=전역 노출"로 통일하려면(옵션 ⓒ) 본 테스트를 함께 갱신할 것.
🔴 If you ever decide to unify on the 0026 "legacy=globally visible" model, update this test too.
"""
# pylint: disable=wrong-import-position
import importlib.util
import os
import pathlib

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")


def _load_0027():
    """alembic/versions/0027_*.py 모듈을 동적 로드한다."""
    versions_dir = pathlib.Path(__file__).resolve().parents[3] / "alembic" / "versions"
    candidates = sorted(versions_dir.glob("0027_*.py"))
    assert len(candidates) == 1, f"0027 마이그레이션 파일 1개 기대, 실제: {candidates}"
    spec = importlib.util.spec_from_file_location(f"alembic_0027_{candidates[0].stem}", candidates[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_0027_policy_has_owner_isolation():
    """0027 정책은 owner 격리(user_id = current app user)를 포함한다."""
    module = _load_0027()
    sql = module._RLS_SECURITY_ALERT_LOGS  # pylint: disable=protected-access
    assert "current_setting('app.user_id'" in sql, "app.user_id 세션 격리 누락"
    assert "security_alert_logs_isolation" in sql, "정책명 누락"


def test_0027_intentionally_omits_user_id_is_null():
    """🔴 U1: 0027 정책은 `user_id IS NULL`(legacy 전역 노출 절)을 의도적으로 생략한다.

    이 단언이 깨지면 (a) 누군가 0026 parity 를 위해 절을 추가했거나 (b) SQL 이 바뀐 것.
    추가가 의도적(legacy=전역 노출 모델 채택)이라면 본 테스트를 함께 갱신할 것 —
    무심코 추가 시 legacy repo 보안알림이 cross-tenant 로 노출된다(보안 완화).
    """
    module = _load_0027()
    sql = module._RLS_SECURITY_ALERT_LOGS.upper()  # pylint: disable=protected-access
    assert "IS NULL" not in sql, (
        "0027 RLS 정책에 `user_id IS NULL`(0026식 legacy 전역 노출 절)이 추가됨 — "
        "의도적 divergence 위반. legacy 보안알림 cross-tenant 노출 위험. "
        "의도적 통일이면 본 가드를 갱신할 것 (정합성 감사 U1 노트 참조)."
    )
