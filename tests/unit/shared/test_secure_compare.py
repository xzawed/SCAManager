"""secure_str_compare 단위 테스트 (Task 9 P1 #9/#10 — 비-ASCII compare_digest TypeError class 수정)."""
from src.shared.secure_compare import secure_str_compare


def test_equal_strings_true():
    assert secure_str_compare("token-abc", "token-abc") is True


def test_unequal_strings_false():
    assert secure_str_compare("token-abc", "token-xyz") is False


def test_non_ascii_input_returns_false_not_typeerror():
    """핵심: 비-ASCII 입력이 TypeError 가 아닌 False 를 반환해야 한다 (500 차단).

    hmac.compare_digest(str, str) 는 비-ASCII str 에 TypeError 를 던진다 — 공개 인증
    엔드포인트에서 401/403 대신 500 을 유발하던 결함. UTF-8 bytes 비교로 차단.
    """
    # 비교 대상이 ASCII 이고 입력이 비-ASCII — TypeError 없이 False
    assert secure_str_compare("정상아님", "expected-ascii") is False
    # 양쪽 비-ASCII 동일 — True (인코딩 후 동등)
    assert secure_str_compare("한글토큰", "한글토큰") is True
    # 이모지 등 비-BMP 문자도 안전
    assert secure_str_compare("🔑key", "expected") is False


def test_none_inputs_treated_as_empty():
    assert secure_str_compare(None, "x") is False
    assert secure_str_compare("x", None) is False
    assert secure_str_compare(None, None) is True   # "" == ""
    assert secure_str_compare("", "") is True
