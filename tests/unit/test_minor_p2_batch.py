"""품질감사 minor P2 묶음 회귀 가드 (2026-06-25).

Audit minor-P2 batch regression guards: grade order-independence, PR payload KeyError defence,
user-repos cache bound.
"""


def test_calculate_grade_independent_of_threshold_dict_order(monkeypatch):
    """worker-core-001: GRADE_THRESHOLDS 삽입 순서를 뒤집어도(오름차순) 정답이어야 한다."""
    # 오름차순(D 먼저) — sorted() 없으면 score>=45 가 먼저 매칭돼 모두 D 로 오분류
    # Ascending order (D first) — without sorting, score>=45 matches first → mis-grades everything as D.
    reordered = {"D": 45, "C": 60, "B": 75, "A": 90}
    monkeypatch.setattr("src.scorer.calculator.GRADE_THRESHOLDS", reordered)
    from src.scorer.calculator import calculate_grade
    assert calculate_grade(95) == "A"
    assert calculate_grade(80) == "B"
    assert calculate_grade(65) == "C"
    assert calculate_grade(50) == "D"
    assert calculate_grade(30) == "F"


def test_extract_event_metadata_pr_missing_number_returns_none():
    """worker-core-003: PR 페이로드에 'number' 키 부재 시 KeyError 없이 pr_number=None."""
    from src.worker.pipeline import _extract_event_metadata
    data = {"repository": {"full_name": "owner/r"}, "pull_request": {"head": {"sha": "abc"}}}
    repo_name, commit_sha, _msg, pr_number = _extract_event_metadata("pull_request", data)
    assert pr_number is None  # data.get("number") → None (이전 data["number"] 는 KeyError)
    assert repo_name == "owner/r"
    assert commit_sha == "abc"


def test_store_user_repos_bounds_cache_size():
    """api-ui-001: _user_repos_cache 가 상한(_USER_REPOS_CACHE_MAX)을 초과 성장하지 않는다."""
    import src.ui.routes.add_repo as mod
    mod._user_repos_cache.clear()
    try:
        now = 1000.0
        # 상한만큼 미래-만료 엔트리로 채움
        for i in range(mod._USER_REPOS_CACHE_MAX):
            mod._user_repos_cache[i] = ([], now + mod._USER_REPOS_CACHE_TTL)
        # 신규 user 저장 → 상한 초과 → evict 후 크기 ≤ 상한 + 신규 user 존재
        mod._store_user_repos(10_000_000, [{"x": 1}], now)
        assert len(mod._user_repos_cache) <= mod._USER_REPOS_CACHE_MAX
        assert 10_000_000 in mod._user_repos_cache
    finally:
        mod._user_repos_cache.clear()


def test_store_user_repos_purges_expired_first():
    """상한 초과 시 만료 엔트리를 먼저 정리한다 (만료분 우선 evict)."""
    import src.ui.routes.add_repo as mod
    mod._user_repos_cache.clear()
    try:
        now = 1000.0
        # 만료된 엔트리로 상한만큼 채움 (expiry < now)
        for i in range(mod._USER_REPOS_CACHE_MAX):
            mod._user_repos_cache[i] = ([], now - 1)
        mod._store_user_repos(10_000_000, [{"x": 1}], now)
        # 만료분 정리로 신규 포함 크기가 상한 이하
        assert len(mod._user_repos_cache) <= mod._USER_REPOS_CACHE_MAX
        assert 10_000_000 in mod._user_repos_cache
    finally:
        mod._user_repos_cache.clear()
