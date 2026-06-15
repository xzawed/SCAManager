"""`tests/unit/_route_helpers.py` 견고성 가드.
Robustness guard for the route-introspection helpers.

fastapi 0.137 `_IncludedRouter`(지연 include) / `APIRouter(prefix=)` / `include_router(prefix=)` /
중첩 include / `Mount` 전 케이스에서 풀 경로를 정확히 재구성하는지 검증한다.
Verifies full-path reconstruction across lazy includes, router prefixes, nested includes, and mounts.
"""
from fastapi import APIRouter, FastAPI

from tests.unit._route_helpers import registered_paths, route_name_count


def _build_app():
    app = FastAPI()

    @app.get("/health")
    def _health():
        return {}

    # 무-prefix 라우터 (절대경로) — 프로젝트 컨벤션
    auth = APIRouter()

    @auth.get("/auth/callback", name="auth_callback")
    def _cb():
        return {}

    app.include_router(auth)

    # 중첩 include (parent → child)
    parent, child = APIRouter(), APIRouter()

    @child.post("/webhooks/github")
    def _wh():
        return {}

    parent.include_router(child)
    app.include_router(parent)

    # APIRouter(prefix=) — prefix 가 leaf .path 에 반영
    apir = APIRouter(prefix="/api/admin")

    @apir.get("/settings")
    def _settings():
        return {}

    app.include_router(apir)

    # include_router(prefix=) — prefix 가 include_context 에만 존재
    flat = APIRouter()

    @flat.get("/ping")
    def _ping():
        return {}

    app.include_router(flat, prefix="/v2")

    # Mount sub-app
    sub = FastAPI()

    @sub.get("/inner")
    def _inner():
        return {}

    app.mount("/mounted", sub)
    return app


def test_registered_paths_handles_includes_prefix_and_mount():
    paths = registered_paths(_build_app())
    for expected in [
        "/health",               # 직접 라우트 / direct route
        "/auth/callback",        # 무-prefix include
        "/webhooks/github",      # 중첩 include / nested include
        "/api/admin/settings",   # APIRouter(prefix=)
        "/v2/ping",              # include_router(prefix=)
        "/mounted/inner",        # Mount 하위 / under Mount
    ]:
        assert expected in paths, f"{expected} 누락 — registered_paths: {sorted(paths)}"


def test_route_name_count_detects_unique_missing_and_duplicate():
    app = _build_app()
    assert route_name_count(app, "auth_callback") == 1   # 정확히 1개 / exactly one
    assert route_name_count(app, "nonexistent_route") == 0  # 부재 / missing

    # 중복 name 탐지 / duplicate-name detection
    dup = APIRouter()

    @dup.get("/dup", name="auth_callback")
    def _dup():
        return {}

    app.include_router(dup)
    assert route_name_count(app, "auth_callback") == 2
