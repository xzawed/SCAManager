"""분석 상세의 「등록됨」 배지가 **새로고침하면 사라진다** — 키 두 종류가 섞여 있었다.

`stateMap` 은 서버가 준 SHA256 `issue_key` 로 채워지는데(`analysis_detail.html::stateMap[reg.issue_key]`)
조회는 클라이언트가 만든 평문 키로 했다(`stateMap[item.key]`). 두 값은 변환 없이 다르므로
**로드 시 채운 항목은 한 번도 읽히지 않는다**. 같은 세션 안에서는 등록 직후 평문 키로
직접 넣어 주므로 배지가 보이고, 새로고침하면 사라진다.

## 실측 (node 로 함수를 떼어 실행)

    클라이언트 키   "st:ruff:F401:unused:src/a.py"
    서버 키         sha256(json.dumps([...]))[:64]  ->  "9ec027fce4ad875c..."

`repo_detail.html` 은 영향 없다 — 그쪽 `_allItems` 는 `key: reg.issue_key` 로 서버 키를
그대로 쓴다.

## 왜 서버가 키를 실어 보내나 (Grok 01a042d4)

키 알고리즘은 **서버 계약**이다. JS 에서 SHA256 을 다시 구현하면 `json.dumps` 의 구분자,
`ensure_ascii=False` 의 한글 처리, `[:200]` 절단이 조용히 어긋나고 — 그 어긋남은 화면에서
「등록 안 됨」과 똑같이 보인다. 그래서 클라이언트는 계산하지 않고 **서버가 준 문자열을
비교만** 한다.

🔴 파이프라인이 아니라 **렌더 시점**에 붙인다. `analyses.result` 에 해시를 굳히면 키
알고리즘이 바뀔 때마다 저장된 값이 낡는다(오늘 하루에만 두 번 바뀌었다).
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import copy  # noqa: E402
import json  # noqa: E402
import pathlib  # noqa: E402
import re  # noqa: E402

import pytest  # noqa: E402

from src.services.issue_registration_service import (  # noqa: E402
    make_ai_issue_key,
    make_static_issue_key,
)
from src.ui.routes.detail import annotate_issue_keys  # noqa: E402

_TEMPLATE = (pathlib.Path(__file__).parents[3] / "src" / "templates"
             / "analysis_detail.html")

_RESULT = {
    "score": 80,
    "issues": [
        {"tool": "ruff", "category": "F401", "message": "unused import",
         "file": "src/auth/login.py", "line": 3, "severity": "warning"},
        {"tool": "ruff", "category": "F401", "message": "unused import",
         "file": "src/api/hook.py", "line": 9, "severity": "warning"},
        {"tool": "bandit", "category": "B105", "message": "hardcoded password",
         "line": 12, "severity": "error"},  # file 없음 — 전환 이전 분석
    ],
    "ai_suggestions": ["첫 번째 제안", "두 번째 제안"],
}


# ─── 서버가 키를 실어 보낸다 ────────────────────────────────────────────────


def test_every_static_issue_carries_the_server_key():
    """🔴 각 정적 이슈에 서버가 계산한 `issue_key` 가 붙는다."""
    out = annotate_issue_keys(_RESULT)
    for src_issue, got in zip(_RESULT["issues"], out["issues"]):
        expected = make_static_issue_key(
            src_issue.get("tool") or "", src_issue.get("category") or "",
            src_issue.get("message") or "", file=src_issue.get("file"))
        assert got["issue_key"] == expected, f"키가 서버 계산과 다르다: {got}"


def test_two_files_get_two_keys_after_annotation():
    """같은 메시지·다른 파일이 **다른 키**로 나간다 — #1499 가 서버에서 고친 것이 화면까지 온다."""
    out = annotate_issue_keys(_RESULT)
    assert out["issues"][0]["issue_key"] != out["issues"][1]["issue_key"]


def test_ai_suggestion_keys_are_parallel_and_aligned():
    """🔴 AI 제안은 **문자열 리스트**라 키를 얹을 수 없다 — 나란한 배열로 준다.

    길이가 어긋나면 인덱스가 밀려 엉뚱한 제안에 배지가 붙는다. 길이를 함께 잰다.
    """
    out = annotate_issue_keys(_RESULT)
    keys = out["ai_issue_keys"]
    assert len(keys) == len(_RESULT["ai_suggestions"]), "나란한 배열의 길이가 어긋났다"
    for text, key in zip(_RESULT["ai_suggestions"], keys):
        assert key == make_ai_issue_key(text)


def test_the_ai_suggestions_stay_strings():
    """AI 제안 자체는 문자열로 남는다 — 템플릿이 `{{ s }}` 로 직접 렌더한다."""
    out = annotate_issue_keys(_RESULT)
    assert out["ai_suggestions"] == _RESULT["ai_suggestions"]
    assert all(isinstance(s, str) for s in out["ai_suggestions"])


def test_an_issue_without_a_file_still_gets_a_key():
    """전환 이전 분석에는 `file` 이 없다 — 그래도 키가 나와야 화면이 죽지 않는다."""
    out = annotate_issue_keys(_RESULT)
    assert out["issues"][2]["issue_key"]
    assert out["issues"][2]["issue_key"] == make_static_issue_key(
        "bandit", "B105", "hardcoded password", file=None)


# ─── 저장된 값을 건드리지 않는다 ────────────────────────────────────────────


def test_the_stored_result_is_not_mutated():
    """🔴 주입은 **렌더 시점**이다 — 저장된 `analyses.result` 를 바꾸면 안 된다.

    ORM 이 들고 있는 dict 를 그 자리에서 고치면 해시가 DB 에 굳고, 키 알고리즘이
    바뀌는 순간 저장된 값이 조용히 낡는다(오늘 하루에만 두 번 바뀌었다).
    """
    before = copy.deepcopy(_RESULT)
    annotate_issue_keys(_RESULT)
    assert _RESULT == before, "입력 dict 를 제자리에서 고쳤다"
    assert "issue_key" not in _RESULT["issues"][0]


def test_an_empty_result_stays_empty():
    """🔴 없는 키를 **발명하지 않는다** — 내 첫 판이 여기서 빈 상태 화면을 지웠다.

    빈 결과에 `issues`/`ai_issue_keys` 를 얹으면 dict 가 truthy 가 되고, 템플릿 바깥의
    if-r 가드가 통과해 「분석 결과 데이터가 없습니다」 화면이 통째로 사라진다.
    `tests/unit/ui/test_router.py::test_analysis_detail_result_none_shows_fallback` 가
    그것을 잡았다 — 배지 하나 고치려다 빈 상태 화면을 지우는 셈이었다.
    """
    assert annotate_issue_keys({}) == {}, "빈 결과에 키를 발명했다"
    assert not annotate_issue_keys({}), "빈 결과가 truthy 가 되면 빈 상태 화면이 사라진다"


def test_only_the_present_keys_are_annotated():
    """한쪽만 있는 결과도 그대로다 — 없는 쪽을 만들어 내지 않는다."""
    only_issues = annotate_issue_keys({"issues": [{"tool": "ruff"}]})
    assert "ai_issue_keys" not in only_issues
    assert only_issues["issues"][0]["issue_key"]

    only_ai = annotate_issue_keys({"ai_suggestions": ["x"]})
    assert "issues" not in only_ai
    assert len(only_ai["ai_issue_keys"]) == 1


def test_a_malformed_issue_entry_is_tolerated():
    """도구가 필드를 빠뜨려도 렌더는 계속된다 — 배지 하나 때문에 페이지를 죽이지 않는다."""
    out = annotate_issue_keys({"issues": [{}, {"tool": "x"}]})
    assert all(i["issue_key"] for i in out["issues"])


# ─── 화면이 그 키를 실제로 쓴다 ────────────────────────────────────────────


def test_the_template_uses_the_server_key_not_a_plaintext_one():
    """🔴 서버가 키를 보내도 **템플릿이 안 쓰면** 배지는 여전히 안 뜬다.

    평문 접두사(`'st:'` / `'ai:'`)로 키를 조립하던 자리가 남아 있으면 조회는 계속 miss 다.
    """
    body = _TEMPLATE.read_text(encoding="utf-8")
    code = [ln for ln in body.splitlines() if not ln.lstrip().startswith(("//", "/*", "*"))]
    plaintext = [ln.strip() for ln in code if re.search(r"key:\s*'(?:st|ai):'", ln)]
    assert not plaintext, f"평문 키 조립이 남아 있다: {plaintext}"
    assert re.search(r"key:\s*issue\.issue_key", body), "정적 항목이 서버 키를 안 쓴다"


def test_the_state_map_is_written_and_read_with_the_same_kind_of_key():
    """🔴 쓰기와 읽기가 다른 종류의 키를 쓰면 조회는 **언제나** miss 다.

    이 파일이 존재하는 이유 자체다 — 로드 시 채운 항목이 한 번도 읽히지 않았다.
    """
    body = _TEMPLATE.read_text(encoding="utf-8")
    writes = set(re.findall(r"stateMap\[([^\]]+)\]\s*=", body))
    reads = set(re.findall(r"=\s*stateMap\[([^\]]+)\]", body))
    assert writes and reads, "stateMap 사용부를 못 찾았다 — 이 테스트가 늙었다"
    # 서버 키(`reg.issue_key`)로 쓰는 이상, 읽기도 같은 값을 담은 항목이어야 한다.
    assert any("issue_key" in w for w in writes), f"서버 키로 쓰지 않는다: {writes}"
    for r in reads:
        assert ".key" in r, f"읽기 키가 항목 키가 아니다: {r}"


@pytest.mark.parametrize("attr", ["data-static-issues", "data-ai-issue-keys"])
def test_the_panel_ships_the_keys_to_the_browser(attr):
    """주입한 키가 실제로 data 속성으로 나가는지 — 서버만 알고 있으면 소용없다."""
    body = _TEMPLATE.read_text(encoding="utf-8")
    assert attr in body, f"{attr} 가 패널에 없다"


def test_an_undefined_key_is_never_written_to_the_state_map():
    """🔴 `stateMap[undefined]` 는 문자열 키 `"undefined"` 가 된다.

    나란한 배열 길이 가드가 발동하면 AI 항목의 키가 전부 `undefined` 다. 그 상태로
    등록에 성공하면 **모든 AI 행이 배지 하나를 공유**한다(Grok 01a042e5 Q3).
    """
    body = _TEMPLATE.read_text(encoding="utf-8")
    assert re.search(r"if \(_currentItem\.key\)\s*stateMap\[_currentItem\.key\]", body), (
        "키가 없을 때도 stateMap 에 쓴다"
    )


# ─── 렌더된 HTML 까지 간다 ──────────────────────────────────────────────────
#
# 🔴 함수가 키를 돌려주는 것과 **브라우저가 그 키를 받는 것**은 다른 축이다.
# 그 사이에 Jinja 의 `tojson`, data 속성 인용부호, 그리고 내가 새로 추가한
# `data-ai-issue-keys` 가 있다. 여기서만 그 축이 측정된다.


def _rendered_page():
    """분석 상세를 실제로 렌더해 HTML 을 돌려준다.

    인증 의존성을 override 하지 않으면 404 다 — 렌더까지 못 가서 이 테스트가
    「속성이 없다」로 조용히 초록이 될 수도 있었다(첫 판이 실제로 404 였다).
    """
    from unittest.mock import MagicMock, patch  # noqa: PLC0415

    from fastapi.testclient import TestClient  # noqa: PLC0415

    from src.auth.session import CurrentUser, get_current_user, require_login  # noqa: PLC0415
    from src.main import app  # noqa: PLC0415
    from src.models.user import User as UserModel  # noqa: PLC0415

    user = UserModel(id=1, github_id="12345", github_login="testuser",
                     github_access_token="gho_test", email="t@e.com",
                     display_name="T")
    # 🔴 전역 dict 다. 남기면 다른 파일의 테스트가 내 로그인 상태를 물려받는다 —
    #    첫 판이 그랬고, 순서 의존 실패 6건을 「고치고」 다른 3건을 깨뜨렸다.
    #    무엇이 초록인지가 내 테스트의 부작용으로 정해지면 그 초록은 증거가 아니다.
    # dependency_overrides is global state; leaking it decides other files' results.
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[require_login] = lambda: user
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=1, github_login="testuser", display_name="T", avatar_url=None)

    mock_db = MagicMock()
    mock_analysis = MagicMock(
        id=10, commit_sha="aaa1111", commit_message="c", pr_number=None,
        score=80, grade="B", result=_RESULT,
        created_at=MagicMock(isoformat=MagicMock(return_value="2026-08-27T00:00:00")),
    )
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        MagicMock(id=1, full_name="owner/repo", user_id=None),
        mock_analysis,
    ]
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit \
        .return_value.all.return_value = []

    class _Ctx:
        def __enter__(self):
            return mock_db

        def __exit__(self, *a):
            return False

    try:
        with patch("src.ui.routes.detail.SessionLocal", return_value=_Ctx()):
            return TestClient(app).get("/repos/owner%2Frepo/analyses/10")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


def test_the_rendered_page_carries_the_static_keys():
    """🔴 서버가 계산한 정적 키가 **HTML 까지** 나온다."""
    resp = _rendered_page()
    assert resp.status_code == 200, f"렌더가 실패했다: {resp.status_code}"
    expected = make_static_issue_key("ruff", "F401", "unused import",
                                     file="src/auth/login.py")
    assert expected in resp.text, "정적 이슈 키가 HTML 에 없다"


def test_the_rendered_page_carries_the_ai_key_array():
    """🔴 내가 새로 추가한 data 속성이 실제로 렌더되는지 — 여기서만 잰다."""
    resp = _rendered_page()
    m = re.search(r"data-ai-issue-keys='([^']*)'", resp.text)
    assert m, "data-ai-issue-keys 속성이 렌더되지 않았다"
    keys = json.loads(m.group(1))
    assert keys == [make_ai_issue_key(s) for s in _RESULT["ai_suggestions"]], (
        f"렌더된 AI 키가 서버 계산과 다르다: {keys}"
    )


def test_the_rendered_static_issues_are_still_usable_json():
    """`tojson` 이 키를 넣고도 파싱 가능한 JSON 을 내는지 — 인용부호 사고가 잦다."""
    resp = _rendered_page()
    m = re.search(r"data-static-issues='([^']*)'", resp.text)
    assert m, "data-static-issues 속성이 없다"
    issues = json.loads(m.group(1))
    assert len(issues) == len(_RESULT["issues"])
    assert all(i["issue_key"] for i in issues), "렌더된 이슈에 키가 없다"
