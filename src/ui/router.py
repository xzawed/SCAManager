"""UI router aggregator — `src/ui/routes/` 의 sub-routers 를 순서대로 include.

외부 API: `from src.ui.router import router` (main.py 용).
실제 endpoint 구현은 `src/ui/routes/` 의 각 도메인 파일 참조.

**include 순서 주의**: FastAPI 라우팅은 등록 순서에 영향 — `/repos/{name}` 은
catch-all 이므로 `/repos/add`, `/repos/{name}/settings` 등 구체 경로 이후에
와야 한다.
"""
from fastapi import APIRouter

from src.ui.routes import (
    actions,
    add_repo,
    detail,
    insights,
    overview,
    settings,
)

router = APIRouter()

# 구체 경로 → 일반 경로 순
# Specific routes first, catch-all route last.
router.include_router(overview.router)       # GET /
router.include_router(insights.router)       # GET /insights, /insights/me
router.include_router(add_repo.router)       # GET/POST /repos/add, /api/github/repos
router.include_router(settings.router)       # /repos/{name}/settings, reinstall-*
router.include_router(actions.router)        # /repos/{name}/delete
router.include_router(detail.router)         # /repos/{name}/analyses/{id}, /repos/{name}  (catch-all 마지막)
