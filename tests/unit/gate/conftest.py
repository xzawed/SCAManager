"""gate 테스트 공통 시드 — 민감 경로 가드의 **네트워크 조회**만 무해화한다.

## 왜 필요한가 / Why this seed exists

`_run_auto_merge` 는 진입부에서 민감 경로 가드(`sensitive_paths_block_merge`, B6-a)를 호출하고,
그 가드는 GitHub 에서 PR 변경 파일 목록을 받아온다. 가드는 **fail-closed** 라 조회가 실패하면
머지를 보류한다 — 의도된 동작이다(무엇이 바뀌었는지 모르는 채 인증 코드를 머지할 수는 없다).

그 결과 이 조회를 모킹하지 않은 기존 auto-merge 테스트 29건이 "머지 보류" 로 떨어졌다.
**가드가 옳고 테스트에 시드가 없었던 것**이므로, 여기서 조회만 기본값(민감 파일 없음)으로 채운다.

## 🔴 이 fixture 가 가드를 무력화하지 않는다

패치 대상은 **네트워크 호출 한 곳**(`get_pr_filenames`)뿐이고, 판정 로직·fail-closed 분기·
배선은 그대로 실행된다. 가드 자체의 동작은 `test_sensitive_path_guard.py` 가 이 fixture 를
덮어써서(자체 `patch`) 차단·fail-closed·kill-switch·배선을 전부 검증한다.
This seeds only the network lookup; the guard's logic, fail-closed branch, and wiring still run.
"""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _seed_pr_filenames():
    """PR 변경 파일 목록 기본값 = 민감하지 않은 파일 1건.

    빈 리스트가 아니라 실제 파일명을 준다 — 빈 목록은 '판정 불가' 와 혼동될 수 있고,
    테스트가 '조회는 됐고 민감 파일이 없었다' 는 정상 경로를 타야 하기 때문이다.
    """
    with patch("src.github_client.diff.get_pr_filenames", return_value=["README.md"]):
        yield
