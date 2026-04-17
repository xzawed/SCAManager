"""Phase 3-B Red — src/analyzer/regression.py 의 detect_regression 순수 함수 테스트.

detect_regression(current_score, previous_scores, current_grade, drop_threshold) -> dict | None
반환 dict 형태: {"type": "drop"|"f_entry", "delta": int, "baseline": float, "secondary"?: "f_entry"}
현재 src/analyzer/regression.py 파일이 존재하지 않으므로 import 단계에서 모든 테스트가 실패(Red)한다.
"""
import os

# conftest와 동일한 env setdefault (신규 파일도 동일 env 필요)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")


def test_detect_regression_no_previous_returns_none():
    # previous_scores가 비어있고 A 등급이면 회귀 없음 → None
    from src.analyzer.regression import detect_regression

    result = detect_regression(
        current_score=92,
        previous_scores=[],
        current_grade="A",
        drop_threshold=15,
    )
    assert result is None


def test_detect_regression_stable_score():
    # 점수가 baseline 근처에서 안정적이면 None
    from src.analyzer.regression import detect_regression

    result = detect_regression(
        current_score=81,
        previous_scores=[80, 82, 78],
        current_grade="B",
        drop_threshold=15,
    )
    assert result is None


def test_detect_regression_small_drop_below_threshold():
    # baseline(80) - current(75) = 5점 하락은 drop_threshold(15) 미만 → None
    from src.analyzer.regression import detect_regression

    result = detect_regression(
        current_score=75,
        previous_scores=[80, 82, 78],
        current_grade="B",
        drop_threshold=15,
    )
    assert result is None


def test_detect_regression_drop_exceeds_threshold():
    # baseline(85) - current(65) = 20점 하락 > 15 → drop 감지, delta·baseline 확인
    from src.analyzer.regression import detect_regression

    result = detect_regression(
        current_score=65,
        previous_scores=[85, 88, 82],
        current_grade="D",
        drop_threshold=15,
    )
    assert result is not None
    assert result["type"] == "drop"
    # baseline = (85+88+82)/3 = 85.0
    assert result["baseline"] == 85.0
    # delta = 85.0 - 65 = 20
    assert result["delta"] == 20


def test_detect_regression_drop_exact_threshold():
    # 경계값: baseline(80) - current(65) = 15 → <= 이면 감지
    from src.analyzer.regression import detect_regression

    result = detect_regression(
        current_score=65,
        previous_scores=[80],
        current_grade="D",
        drop_threshold=15,
    )
    assert result is not None
    assert result["type"] == "drop"
    assert result["baseline"] == 80.0
    assert result["delta"] == 15


def test_detect_regression_f_entry_from_higher_grade():
    # drop(40점 하락)과 F진입 조건 둘 다 만족 → type=drop 우선, secondary=f_entry 포함
    from src.analyzer.regression import detect_regression

    result = detect_regression(
        current_score=40,
        previous_scores=[85, 80, 75],
        current_grade="F",
        drop_threshold=15,
    )
    assert result is not None
    assert result["type"] == "drop"
    assert result.get("secondary") == "f_entry"
    # baseline = 80.0
    assert result["baseline"] == 80.0
    assert result["delta"] == 40


def test_detect_regression_f_entry_small_drop():
    # baseline(51) - current(44) = 7점, drop 미달이지만 F 진입(직전이 F 아님) → type=f_entry
    from src.analyzer.regression import detect_regression

    result = detect_regression(
        current_score=44,
        previous_scores=[50, 52, 51],
        current_grade="F",
        drop_threshold=15,
    )
    assert result is not None
    assert result["type"] == "f_entry"


def test_detect_regression_first_analysis_f_no_baseline():
    # previous_scores가 비어 있으면 baseline 없음 → F 등급이어도 None (사양대로)
    from src.analyzer.regression import detect_regression

    result = detect_regression(
        current_score=40,
        previous_scores=[],
        current_grade="F",
        drop_threshold=15,
    )
    assert result is None


def test_detect_regression_returns_positive_delta():
    # delta는 항상 baseline - current_score 값이며 감지될 때 양수여야 한다
    from src.analyzer.regression import detect_regression

    result = detect_regression(
        current_score=60,
        previous_scores=[90, 90, 90],
        current_grade="C",
        drop_threshold=15,
    )
    assert result is not None
    assert result["delta"] > 0
    # 구체값: 90.0 - 60 = 30
    assert result["delta"] == 30
    assert result["baseline"] == 90.0
