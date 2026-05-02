"""Integration test 자동 마킹 + webhook secret 환경 의존성 격리.

이 디렉토리의 모든 테스트는 실제 subprocess/DB/외부 I/O 를 검증하므로
기본적으로 `@pytest.mark.slow` 가 자동 부여된다. 빠른 유닛 실행만 원하면
`pytest tests/ -m "not slow"` 로 격리할 수 있다.

[2026-05-02 그룹 61 — pre-existing 24 fail 정리]
근본 원인: 그룹 60 PR B-1/B-2 와 동일 패턴 — devcontainer 등 일부 환경에서
`GITHUB_WEBHOOK_SECRET=dev_secret` (또는 다른 값) 가 export 되어 conftest 의
`os.environ.setdefault('test_secret')` 무효 → settings.github_webhook_secret =
"dev_secret" → test 가 보낸 HMAC ("test_secret" 기반) 과 불일치 → 401.

fix: integration test 의 모든 webhook 호출이 사용하는 `get_webhook_secret`
함수를 autouse fixture 로 일괄 mock. 신규 webhook integration test 도 자동
적용 → 환경 의존성 영구 격리.
"""
from unittest.mock import patch

import pytest

# tests/integration/test_e2e_pipeline_scenarios.py:33 + test_webhook_to_gate.py 와 동일 값.
# tests/conftest.py L7 의 GITHUB_WEBHOOK_SECRET=test_secret default 와도 일치.
_INTEGRATION_TEST_SECRET = "test_secret"


def pytest_collection_modifyitems(config, items):  # pylint: disable=unused-argument
    """tests/integration/ 하위 모든 수집 항목에 slow 마커를 자동 부여한다."""
    for item in items:
        if "tests/integration/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.slow)


@pytest.fixture(autouse=True)
def _mock_webhook_secret_for_integration():
    """integration test 에서 webhook secret 환경 의존성 격리.

    `src.webhook.providers.github.get_webhook_secret` 을 일괄 mock 으로 대체 →
    devcontainer 등 환경의 export 된 GITHUB_WEBHOOK_SECRET 영향 차단.
    fix 범위: 24 pre-existing fail (test_e2e_pipeline_scenarios 20 + test_webhook_to_gate 4).
    신규 webhook integration test 도 자동 적용.
    """
    with patch(
        "src.webhook.providers.github.get_webhook_secret",
        return_value=_INTEGRATION_TEST_SECRET,
    ):
        yield
