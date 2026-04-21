"""Integration test 자동 마킹.

이 디렉토리의 모든 테스트는 실제 subprocess/DB/외부 I/O 를 검증하므로
기본적으로 `@pytest.mark.slow` 가 자동 부여된다. 빠른 유닛 실행만 원하면
`pytest tests/ -m "not slow"` 로 격리할 수 있다.
"""
import pytest


def pytest_collection_modifyitems(config, items):  # pylint: disable=unused-argument
    """tests/integration/ 하위 모든 수집 항목에 slow 마커를 자동 부여한다."""
    for item in items:
        if "tests/integration/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.slow)
