"""라우트 등록 검증 헬퍼 — fastapi 0.137 `_IncludedRouter`(지연 include) 대응.
Route-registration helpers — handle fastapi 0.137's `_IncludedRouter` (lazy include wrapper).

fastapi 0.137 부터 `include_router` 가 라우트를 즉시 평탄화하지 않고 `_IncludedRouter` 래퍼로
지연 포함한다. 그 결과 `[r.path for r in app.routes]` 직접 순회는 `_IncludedRouter.path`
AttributeError 를 낸다. 아래 헬퍼는 원본 라우터(+ include prefix)·중첩 include·`Mount` 하위까지
재귀 평탄화하여 실제 등록 경로를 재구성한다.

fastapi 0.137 no longer flattens `include_router` eagerly — it wraps sub-routers in a lazy
`_IncludedRouter`, so `[r.path for r in app.routes]` raises AttributeError on `_IncludedRouter.path`.
These helpers recursively reconstruct the registered full paths through the original router
(+ include prefix), nested includes, and `Mount` sub-apps.
"""
from starlette.routing import Mount


def _walk(routes, prefix, paths, names):
    for route in routes:
        # _IncludedRouter (지연 include) — 원본 APIRouter 로 하강.
        # APIRouter(prefix=...) 의 prefix 는 leaf .path 에 이미 반영되고,
        # include_router(prefix=...) 의 prefix 는 include_context.prefix 에만 있어 별도 누적.
        included = getattr(route, "original_router", None)
        if included is not None:
            ctx = getattr(route, "include_context", None)
            inc_prefix = getattr(ctx, "prefix", "") if ctx is not None else ""
            _walk(getattr(included, "routes", []) or [], prefix + inc_prefix, paths, names)
            continue
        # Mount(sub-app) — 마운트 경로를 prefix 로 두고 하위 라우트 하강.
        if isinstance(route, Mount):
            _walk(getattr(route, "routes", None) or [], prefix + route.path, paths, names)
            continue
        path = getattr(route, "path", None)
        if path is not None:
            paths.add(prefix + path)
        name = getattr(route, "name", None)
        if name is not None:
            names.append(name)


def registered_paths(app):
    """앱에 등록된 모든 라우트의 풀 경로 집합 (prefix·중첩 include·Mount 평탄화).
    Full set of registered route paths (prefix / nested include / Mount flattened).
    """
    paths, names = set(), []
    _walk(app.routes, "", paths, names)
    return paths


def route_name_count(app, name):
    """주어진 name 으로 등록된 라우트 개수 — 중복 name(또는 부재) 탐지용.
    Count of routes registered under `name` — detects duplicate (or missing) names.
    """
    paths, names = set(), []
    _walk(app.routes, "", paths, names)
    return names.count(name)
