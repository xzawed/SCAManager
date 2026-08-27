"""dedup 키가 **파일 경로를 빼서** 서로 다른 파일의 findings 를 한 슬롯으로 붕괴시킨다 (#1499).

`make_static_issue_key` 는 `tool:category:message[:200]` 만 해싱했다. 라인 번호를 뺀 것은
의도적이고 타당하다(커밋 간 drift 방지) — 그런데 **파일까지 빠져서** 서로 다른 파일의
동일 메시지 이슈가 하나의 키로 붕괴한다. `register()` 는 dedup 슬롯 스쿼팅을 되돌릴 수
없으므로, A파일의 이슈가 먼저 등록되면 B파일의 진짜 finding 은 **영구히 등록 불가**다.

## 운영 실측 (2026-08-27, Supabase)

이 결함이 가설이 아니라는 근거. `analyses.result->'issues'` 를 `#1494` 의 파일 키 도입
시점(2026-08-25, 그 전 0% → 그 후 100%) 이후로 잘라 `(repo, tool, category, message[:200])`
로 묶었다:

    현재 키              630
    file 을 넣으면       1,149   (+82%)
    2개 이상 파일을 삼킨 키  200   (31.7%)
    최악의 키 하나        파일 35개
    등록 불가가 될 findings  519  (error 303 + warning 216)

전환 후 10,229건에 `file` 이 null·빈문자열 **0건**이라, 새 등록은 항상 재료를 갖는다.

## 왜 `file` 은 넣고 `line` 은 안 넣나

`line` 은 커밋마다 흔들려 같은 결함이 매번 새 키가 된다(원 docstring 의 판단). 파일
이름 변경은 그보다 훨씬 드물고, 결과도 다르다 — 중복 이슈가 하나 더 생길 뿐 **차단은
아니다**. 차단이 되돌릴 수 없는 쪽이므로 그 위험만 닫는다.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pathlib  # noqa: E402
import re  # noqa: E402

import pytest  # noqa: E402

from src.services.issue_registration_service import make_static_issue_key  # noqa: E402

_TEMPLATES = pathlib.Path(__file__).parents[3] / "src" / "templates"
_POSTING_TEMPLATES = ("analysis_detail.html", "repo_detail.html")
# payload 의 `file:` 만 — 주석 안의 같은 글자를 세지 않기 위해 값까지 요구한다.
_FILE_PAYLOAD = re.compile(r"^\s*file:\s*\S")


# ─── 키가 파일을 가른다 ──────────────────────────────────────────────────────


def test_the_same_finding_in_two_files_gets_two_keys():
    """🔴 서로 다른 파일의 같은 메시지는 **다른 키**여야 한다.

    운영 실측에서 키 하나가 파일 35개를 삼켰다. 첫 등록이 나머지 34개를 영구히 막는다.
    """
    a = make_static_issue_key("ruff", "F401", "`os` imported but unused",
                              file="src/auth/login.py")
    b = make_static_issue_key("ruff", "F401", "`os` imported but unused",
                              file="src/api/hook.py")
    assert a != b, "서로 다른 파일이 한 dedup 슬롯으로 붕괴했다"


def test_the_same_finding_in_the_same_file_keeps_one_key():
    """반대쪽 — 같은 파일의 같은 결함은 여전히 **하나**다. 그게 dedup 의 존재 이유다."""
    a = make_static_issue_key("bandit", "B105", "hardcoded password",
                              file="src/auth/token.py")
    b = make_static_issue_key("bandit", "B105", "hardcoded password",
                              file="src/auth/token.py")
    assert a == b


def test_the_production_collision_shape_is_resolved():
    """🔴 운영에서 실제로 붕괴한 모양을 그대로 재현한다.

    이 배열은 「같은 tool·category·message 가 여러 파일에 흩어진다」는 실측 형태다.
    수정 전에는 findings 5 -> keys 2 였다.
    """
    rows = [
        ("ruff", "F401", "`os` imported but unused", "src/auth/login.py"),
        ("ruff", "F401", "`os` imported but unused", "src/api/hook.py"),
        ("ruff", "F401", "`os` imported but unused", "src/worker/pipeline.py"),
        ("bandit", "B105", "Possible hardcoded password", "src/auth/token.py"),
        ("bandit", "B105", "Possible hardcoded password", "tests/fixtures/sample.py"),
    ]
    keys = {make_static_issue_key(t, c, m, file=f) for t, c, m, f in rows}
    assert len(keys) == len(rows), (
        f"findings {len(rows)} -> keys {len(keys)} — 아직 붕괴한다"
    )


def test_a_missing_file_is_not_the_same_as_an_empty_one():
    """전환 이전 분석에는 `file` 이 없다 — `None` 이어도 키가 만들어져야 한다.

    그 경우는 예전과 같은 동작(파일 없는 버킷)으로 **완만히 낮아질** 뿐, 예외로 죽거나
    전환 이후 분석의 슬롯을 뺏지 않는다.
    """
    legacy = make_static_issue_key("ruff", "F401", "msg", file=None)
    modern = make_static_issue_key("ruff", "F401", "msg", file="src/a.py")
    assert legacy != modern, "파일 없는 구 분석이 신 분석의 슬롯을 먹는다"
    assert legacy == make_static_issue_key("ruff", "F401", "msg", file=None)


def test_file_must_be_passed_explicitly():
    """🔴 `file` 은 keyword-only **필수**다 — 빠뜨리면 조용히 옛 키로 돌아간다.

    Grok(01a0425c)이 짚은 지점: 해시만 고치고 호출부가 전달을 잊으면 「영원히 빈 file」이
    되어 실측한 31.7% 붕괴가 그대로 남는다. 기본값을 주지 않아 그 경로를 없앤다.
    """
    with pytest.raises(TypeError):
        make_static_issue_key("ruff", "F401", "msg")  # type: ignore[call-arg]


def test_the_key_still_ignores_the_line_number():
    """`line` 은 여전히 키에 없다 — 커밋마다 흔들려 같은 결함이 매번 새 키가 된다.

    이 PR 이 넣은 것은 `file` 뿐이다. 서명에 `line` 이 생기면 이 계약이 조용히 뒤집힌다.
    """
    import inspect  # noqa: PLC0415

    params = inspect.signature(make_static_issue_key).parameters
    assert "line" not in params, f"line 이 키 재료로 들어왔다: {list(params)}"
    assert "file" in params


# ─── 재료가 실제로 서버까지 온다 ────────────────────────────────────────────


def test_the_request_model_accepts_a_file():
    """🔴 키가 파일을 받아도 **요청이 안 실어 보내면** 아무것도 달라지지 않는다."""
    from src.api.issue_registration import RegisterRequest  # noqa: PLC0415

    assert "file" in RegisterRequest.model_fields, (
        f"RegisterRequest 에 file 이 없다: {list(RegisterRequest.model_fields)}"
    )


def test_the_api_feeds_the_file_into_the_key():
    """🔴 요청의 `file` 이 실제로 키 계산에 쓰이는지 — 필드만 있고 안 쓰면 공허하다."""
    from src.api.issue_registration import RegisterRequest, _make_issue_key  # noqa: PLC0415

    def _req(file):
        return RegisterRequest(analysis_id=1, issue_type="static_issue", tool="ruff",
                               category="F401", message="unused", title="t", body="b",
                               labels=[], file=file)

    assert _make_issue_key(_req("src/a.py")) != _make_issue_key(_req("src/b.py")), (
        "API 가 file 을 받고도 키에 넣지 않는다"
    )


@pytest.mark.parametrize("template", _POSTING_TEMPLATES)
def test_the_posting_template_sends_the_file(template):
    """🔴 브라우저가 `file` 을 안 보내면 서버는 언제나 `None` 을 본다.

    등록은 자동 파이프라인이 아니라 이 두 화면의 버튼이 전부다(실측: 운영 등록 0건,
    경로는 `POST /api/issues/register`). payload 에 없으면 이 PR 은 아무것도 못 고친다.
    """
    body = (_TEMPLATES / template).read_text(encoding="utf-8")
    assert "/api/issues/register" in body, f"{template} 이 등록 호출부가 아니다 — 테스트가 늙었다"
    # 🔴 주석에도 "file:" 은 쓸 수 있다 — payload 로 **가는** 줄만 센다(Grok 01a0426a).
    #    코드 줄 = 주석(//, /*)이 아니고 `file` 뒤에 콜론과 값이 오는 줄.
    payload_lines = [
        ln for ln in body.splitlines()
        if _FILE_PAYLOAD.search(ln) and not ln.lstrip().startswith(("//", "/*", "*"))
    ]
    assert payload_lines, f"{template} 의 payload 가 file 을 안 보낸다"


# ─── 필드 경계는 위조할 수 없다 (Grok 01a0426a 가 뚫은 축) ──────────────────


def test_a_colon_inside_a_field_cannot_forge_a_boundary():
    """🔴 콜론으로 이어붙이면 필드 안의 콜론이 **경계를 위조**한다.

    Grok 이 준 반례 그대로다 — 두 튜플이 같은 문자열이 됐다:

        ("ruff","F401","msg:src/b.py","src/a.py")
        ("ruff","F401","msg","src/b.py:src/a.py")
    """
    a = make_static_issue_key("ruff", "F401", "msg:src/b.py", file="src/a.py")
    b = make_static_issue_key("ruff", "F401", "msg", file="src/b.py:src/a.py")
    assert a != b, "필드 안의 콜론이 경계를 위조했다"


def test_a_quote_inside_a_field_cannot_forge_a_boundary():
    """JSON 으로 바꿨으니 이번엔 **따옴표**로 같은 시도를 한다 — 이스케이프되어야 한다."""
    a = make_static_issue_key("t", "c", 'm","x', file="y")
    b = make_static_issue_key("t", "c", "m", file='x","y')
    assert a != b, "따옴표가 JSON 경계를 위조했다"


def test_an_absent_file_and_an_empty_one_are_the_same_slot():
    """🔴 「없음」의 표기가 두 가지면 **두 호출부가 갈린다** — 실측으로 갈렸다.

    한때는 `None` 과 `""` 를 가르는 것이 정직해 보였다. 그런데 브라우저는 빈 file 을
    `null` 로 보내고(`issue.file || null`) 저장된 분석은 `""` 를 그대로 들고 있어서,
    등록 경로와 렌더 경로가 **같은 finding 에 다른 키**를 만들었다(Grok 01a042e5 Q4).

    빈 경로는 경로가 아니다. 「없음」을 하나로 정하고 그 정규화를 키 함수 안에서만
    하면, 호출부가 몇 개든 갈릴 수 없다. 운영 실측으로 전환 후 빈 문자열 file 은
    **0건**이라 이 통합이 실제로 잃는 것도 없다.
    """
    assert make_static_issue_key("t", "c", "m", file=None) == \
        make_static_issue_key("t", "c", "m", file=""), "「없음」이 두 값으로 갈렸다"
    assert make_static_issue_key("t", "c", "m", file=None) != \
        make_static_issue_key("t", "c", "m", file="src/a.py")


def test_the_key_normalizes_inside_not_at_the_call_site():
    """🔴 정규화가 키 함수 **안**에 있어야 한다 — 밖에 있으면 호출부마다 달라진다."""
    assert make_static_issue_key(None, None, None, file=None) == \
        make_static_issue_key("", "", "", file=""), "날것과 정규화된 값이 다른 키다"


# ─── 방어는 HTTP 경계까지 간다 ──────────────────────────────────────────────


def test_a_static_request_that_omits_the_file_is_rejected():
    """🔴 keyword-only 필수는 **Python 호출부만** 막는다 — 진짜 호출자는 브라우저다.

    요청 모델의 기본값 `None` 이 그대로 「조용히 빈 file」 구멍이었다(Grok 01a0426a).
    필드를 **빠뜨린** 요청은 낡은 클라이언트이므로 거절한다.
    """
    import pydantic  # noqa: PLC0415

    from src.api.issue_registration import RegisterRequest  # noqa: PLC0415

    with pytest.raises(pydantic.ValidationError):
        RegisterRequest(analysis_id=1, issue_type="static_issue", tool="t",
                        category="c", message="m", title="T", body="B", labels=[])


def test_an_explicit_null_file_is_accepted():
    """명시적 `null` 은 받는다 — 2026-08-25 이전 분석에는 파일 키가 없다.

    누락과 null 을 같이 거절하면 구 분석에서 등록이 통째로 막힌다.
    """
    from src.api.issue_registration import RegisterRequest  # noqa: PLC0415

    req = RegisterRequest(analysis_id=1, issue_type="static_issue", tool="t",
                          category="c", message="m", title="T", body="B",
                          labels=[], file=None)
    assert req.file is None


def test_an_ai_suggestion_does_not_need_a_file():
    """AI 제안은 파일 단위 finding 이 아니다 — 같은 요구를 걸면 그 경로가 죽는다."""
    from src.api.issue_registration import RegisterRequest  # noqa: PLC0415

    req = RegisterRequest(analysis_id=1, issue_type="ai_suggestion",
                          suggestion_text="x", title="T", body="B", labels=[])
    assert req.issue_type == "ai_suggestion"


# ─── 등록 경로와 렌더 경로는 같은 키를 만들어야 한다 ────────────────────────
#
# 🔴 이 절이 없었기 때문에 두 경로가 각자 정규화했고, 같은 finding 이 서로 다른
# 슬롯을 잡았다. 배지는 「등록 안 됨」으로 보이고, 다시 누르면 서버가 중복이라고 거절한다.


def _paths_agree(stored, posted):
    """저장된 이슈에서 뽑은 키 == 등록 요청에서 뽑은 키."""
    from src.api.issue_registration import RegisterRequest, _make_issue_key  # noqa: PLC0415
    from src.ui.routes.detail import annotate_issue_keys  # noqa: PLC0415

    render_key = annotate_issue_keys({"issues": [stored]})["issues"][0]["issue_key"]
    req = RegisterRequest(analysis_id=1, issue_type="static_issue", body="B", labels=[],
                          **posted)
    return render_key == _make_issue_key(req)


def test_the_render_path_and_the_register_path_agree():
    """정상 경로 — 대조군. 여기서 어긋나면 아래 엣지 단언이 공허하다."""
    assert _paths_agree(
        {"tool": "ruff", "category": "F401", "message": "unused", "file": "src/a.py"},
        {"tool": "ruff", "category": "F401", "message": "unused", "file": "src/a.py",
          "title": "T"})


def test_the_two_paths_agree_when_the_message_is_empty():
    """🔴 브라우저는 빈 message 를 null 로 보낸다 — 예전엔 서버가 title 로 대체했다."""
    assert _paths_agree(
        {"tool": "ruff", "category": "F401", "message": "", "file": "src/a.py"},
        {"tool": "ruff", "category": "F401", "message": None, "file": "src/a.py",
          "title": "사용자가 고친 제목"})


def test_the_two_paths_agree_when_the_file_is_empty():
    """🔴 저장된 분석은 `""` 를 들고 있는데 브라우저는 `null` 을 보낸다."""
    assert _paths_agree(
        {"tool": "ruff", "category": "F401", "message": "unused", "file": ""},
        {"tool": "ruff", "category": "F401", "message": "unused", "file": None,
          "title": "T"})


def test_a_non_mapping_issue_entry_does_not_kill_the_page():
    """🔴 항목이 dict 가 아니면 `{**issue}` 가 TypeError 였다 — 상세 페이지가 500 이다."""
    from src.ui.routes.detail import annotate_issue_keys  # noqa: PLC0415

    out = annotate_issue_keys({"issues": ["문자열", None, {"tool": "ruff"}]})
    assert len(out["issues"]) == 1, "mapping 아닌 항목을 걸러내지 않았다"
    assert out["issues"][0]["issue_key"]
