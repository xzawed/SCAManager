"""본문 크기 제한이 `Content-Length` 헤더에만 의존한다 — 헤더가 없으면 무제한 (감사 A4, #1519).

🔴 실측. `src/main.py::LimitBodySizeMiddleware` 의 docstring 은
「요청 본문 크기를 제한한다 (DoS 방어) / Limits request body size to prevent DoS via
oversized payloads」라고 적는다. 구현은:

    content_length = request.headers.get("content-length")
    if content_length:
        ...  # 여기서만 검사
    return await call_next(request)   # 헤더가 없으면 그냥 통과

HTTP/1.1 은 `Transfer-Encoding: chunked` 를 쓰면 `Content-Length` 를 **보내지 않는다**
(RFC 9112 §6.1 — 둘을 동시에 보내면 안 된다). 즉 chunked 요청은 이 제한을 통째로
지나간다. 그리고 이것이 리포의 **유일한** 본문 크기 가드다
(`grep -rn "content-length\|MAX_BODY" src/` 히트는 `src/main.py` 뿐).

이 파일이 봉인하는 것:
1. 헤더가 **없는** 요청도 제한을 받는다.
2. 헤더가 **거짓** 인 요청 — 작다고 적고 실제로는 큰 본문 — 도 제한을 받는다.
   신뢰할 수 없는 값을 그대로 믿는 것 자체가 결함이다.
3. 정상 요청은 그대로 통과한다(과잉 차단 방지).

The only body-size guard reads a header that chunked requests never send.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.responses import PlainTextResponse  # noqa: E402
from starlette.routing import Route  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from src.main import LimitBodySizeMiddleware  # noqa: E402

_LIMIT = LimitBodySizeMiddleware._MAX_BODY  # noqa: SLF001


async def _echo(request):
    body = await request.body()
    return PlainTextResponse(str(len(body)))


@pytest.fixture()
def client() -> TestClient:
    """미들웨어만 단 최소 앱 — 앱 전체 라우팅과 무관하게 이 축만 잰다."""
    app = Starlette(routes=[Route("/echo", _echo, methods=["POST"])])
    app.add_middleware(LimitBodySizeMiddleware)
    return TestClient(app)


def _chunks(total: int, size: int = 64 * 1024):
    """제너레이터 본문 — httpx 가 이것을 보면 chunked 로 보내고 Content-Length 를 안 붙인다."""
    sent = 0
    while sent < total:
        n = min(size, total - sent)
        sent += n
        yield b"a" * n


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_a_generator_body_really_omits_content_length(client: TestClient):
    """🔴 전제 — 제너레이터 본문이 정말 `Content-Length` 없이 나가는가.

    붙어서 나간다면 이 파일의 나머지가 **다른 것**을 재는 것이 된다.
    """
    seen: dict[str, str | None] = {}

    async def _peek(request):
        seen["cl"] = request.headers.get("content-length")
        seen["te"] = request.headers.get("transfer-encoding")
        await request.body()
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/peek", _peek, methods=["POST"])])
    TestClient(app).post("/peek", content=_chunks(4096))

    assert seen.get("cl") is None, (
        f"제너레이터 본문에 Content-Length 가 붙었다({seen['cl']!r}) — 전제가 바뀌었다"
    )
    assert seen.get("te") == "chunked", f"chunked 로 나가지 않는다: {seen.get('te')!r}"


def test_normal_small_request_still_passes(client: TestClient):
    """대조군 — 정상 크기 요청은 그대로 통과한다."""
    r = client.post("/echo", content=b"x" * 1024)
    assert r.status_code == 200, f"정상 요청이 막혔다: {r.status_code}"
    assert r.text == "1024"


# ─── 결함 ────────────────────────────────────────────────────────────────────


def test_oversized_chunked_body_is_rejected(client: TestClient):
    """🔴 `Content-Length` 가 없어도 한도를 넘는 본문은 거부된다.

    막지 않으면 이 미들웨어의 docstring(「DoS 방어」)이 거짓이고,
    리포에 다른 본문 크기 가드가 없다.
    """
    r = client.post("/echo", content=_chunks(_LIMIT + 4096))
    assert r.status_code == 413, (
        f"헤더 없는 초과 본문이 {r.status_code} 로 통과했다 — chunked 로 제한을 우회한다. "
        f"수신 바이트={r.text}"
    )


def test_lying_content_length_does_not_grant_passage(client: TestClient):
    """🔴 「작다」고 적은 헤더를 믿고 큰 본문을 통과시키지 않는다.

    헤더는 클라이언트가 정하는 값이다. 그것만 보는 가드는 정직한 클라이언트만 막는다.
    """
    payload = b"a" * (_LIMIT + 4096)
    r = client.post("/echo", content=payload, headers={"Content-Length": "10"})
    assert r.status_code == 413, (
        f"거짓 Content-Length 로 초과 본문이 {r.status_code} 로 통과했다"
    )


def test_the_limit_is_the_only_body_guard_in_the_repo():
    """🔴 이 미들웨어가 유일한 가드라는 전제를 고정한다.

    다른 가드가 생기면 이 테스트가 red 가 되고, 그때 이 파일의 서술을 고쳐야 한다.
    다중 가드를 «있다» 고 착각하면 여기 구멍이 나도 안심하게 된다.
    """
    import re  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    pat = re.compile(r"content-length|MAX_BODY", re.IGNORECASE)
    hits = {
        p.as_posix()
        for p in Path("src").rglob("*.py")
        if "__pycache__" not in p.as_posix() and pat.search(p.read_text(encoding="utf-8"))
    }
    assert hits == {"src/main.py"}, (
        f"본문 크기를 다루는 곳이 바뀌었다: {sorted(hits)} — 이 파일의 전제를 다시 확인하라"
    )


# ─── 연결 종료 — 읽지 않은 chunk 가 다음 요청을 오염시킨다 ─────────────────────


def test_413_closes_the_connection(client: TestClient):
    """🔴 413 응답이 연결을 닫는다 — 남은 chunk 를 읽지 않고 끊기 때문이다.

    keep-alive 를 유지하면 다음 요청이 그 잔여 바이트를 **자기 본문의 일부로** 읽는다
    (요청 desync). Grok 이 이 축을 짚었고(session 01a03cd1), 헤더 하나로 막는다.
    """
    r = client.post("/echo", content=_chunks(_LIMIT + 4096))
    assert r.status_code == 413
    assert r.headers.get("connection", "").lower() == "close", (
        f"413 이 연결을 닫지 않는다 — 읽지 않은 본문이 다음 요청으로 흘러간다: "
        f"{dict(r.headers)}"
    )


def test_the_header_only_path_is_still_an_early_reject(client: TestClient):
    """대조군 — `Content-Length` 가 한도를 넘으면 **본문을 읽기 전에** 거부한다.

    스트리밍 계수만 남기고 헤더 검사를 없애면 10MB 를 전부 수신한 뒤에야 끊게 된다.
    """
    r = client.post("/echo", content=b"x", headers={"Content-Length": str(_LIMIT + 1)})
    assert r.status_code == 413
