# Phase 8B: GitHub OAuth + 리포 추가 UI + Webhook 자동 생성

**날짜:** 2026-04-07
**상태:** 승인됨
**이전 Phase:** 8A (Google OAuth + User 모델 + 사용자별 대시보드)
**다음 Phase:** 8C (PR 관리 UI)

---

## 배경 및 목적

Phase 8A에서 Google OAuth로 로그인 및 사용자별 대시보드를 구현했다. Phase 8B는 다음을 달성한다:

- Google OAuth → **GitHub OAuth** 교체 (`repo` 스코프 포함)
- 사용자별 GitHub access_token DB 저장 → 리포 목록 브라우징, Webhook 생성, PR 리뷰에 활용
- **리포 추가 UI**: GitHub 리포 목록 드롭다운 → 선택 후 Webhook 자동 생성
- **리포별 Webhook 시크릿**: `secrets.token_hex(32)` 자동 생성, DB 저장, 검증

**SaaS 전환 로드맵:**

| Phase | 내용 |
|-------|------|
| 8A | Google OAuth + User 모델 + 사용자별 대시보드 ✅ |
| **8B (현재)** | GitHub OAuth + 리포 추가 UI + Webhook 자동 생성 |
| 8C | PR 관리 UI (오픈 PR 목록 + Approve/Reject) |

---

## 아키텍처

### 신규 파일

```
src/auth/
└── github.py            # GitHub OAuth 플로우 (authlib)
                         # GET /login, GET /auth/github, GET /auth/callback, POST /auth/logout

src/github_client/
└── repos.py             # list_user_repos(), create_webhook(), delete_webhook()

src/templates/
└── add_repo.html        # 리포 추가 페이지 (드롭다운)
```

### 변경 파일

```
src/auth/google.py           → 삭제 (github.py로 교체)
src/models/user.py           # google_id → github_id, github_login, github_access_token 추가
src/models/repository.py     # webhook_secret, webhook_id 컬럼 추가
src/config.py                # google_* 제거, github_client_* 추가
src/main.py                  # auth_router → github auth router로 교체
src/webhook/router.py        # 리포별 시크릿 조회 → 검증 로직 변경
src/worker/pipeline.py       # settings.github_token → owner.github_access_token
src/ui/router.py             # /repos/add 라우트 추가, /api/github/repos 추가
src/templates/login.html     # "GitHub로 로그인" 버튼으로 교체
src/templates/overview.html  # "리포 추가" 버튼 추가
alembic/versions/0006_phase8b_github_oauth.py  # DB 마이그레이션
```

---

## 데이터 모델

### 변경: `users` 테이블

```python
class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    github_id       = Column(String, unique=True, nullable=False, index=True)  # google_id → github_id
    github_login    = Column(String, nullable=False)   # GitHub username (e.g. "octocat")
    github_access_token = Column(String, nullable=True)  # OAuth access token (repo scope)
    email           = Column(String, unique=True, nullable=False)
    display_name    = Column(String, nullable=False)
    created_at      = Column(DateTime, default=datetime.utcnow)

    repositories    = relationship("Repository", back_populates="owner")
```

### 변경: `repositories` 테이블

```python
# 기존 필드 유지, 아래 컬럼 추가
webhook_secret = Column(String, nullable=True)   # 리포별 랜덤 시크릿
webhook_id     = Column(Integer, nullable=True)  # GitHub Webhook ID
```

`nullable=True`: 레거시 수동 등록 리포(user_id=NULL) 하위 호환 보장.

### 마이그레이션 `0006_phase8b_github_oauth.py`

1. `users.google_id` → `github_id` 컬럼명 변경 (ALTER COLUMN)
2. `users`에 `github_login` 컬럼 추가 (String, NOT NULL DEFAULT '')
3. `users`에 `github_access_token` 컬럼 추가 (String, nullable)
4. `repositories`에 `webhook_secret` 컬럼 추가 (String, nullable)
5. `repositories`에 `webhook_id` 컬럼 추가 (Integer, nullable)

---

## 인증 플로우 (GitHub OAuth)

### `src/auth/github.py`

```
GET /login
  → 세션 있으면 / 리다이렉트
  → login.html 렌더링

GET /auth/github
  → authlib로 GitHub OAuth 동의 URL 생성
    scope: "repo user:email"
  → 302 github.com/login/oauth/authorize?...

GET /auth/callback?code=...&state=...
  → code → access_token 교환 (GitHub API)
  → GET https://api.github.com/user
      → id (github_id), login (github_login), name (display_name)
  → GET https://api.github.com/user/emails
      → primary verified email
  → users 테이블 upsert (github_id 기준):
      없으면 → 신규 User 생성
      있으면 → github_access_token, github_login, display_name 갱신
  → session["user_id"] = user.id
  → 302 /

POST /auth/logout
  → session.clear()
  → 302 /login
```

### 환경변수

| 변수 | 변경 | 설명 |
|------|------|------|
| `GOOGLE_CLIENT_ID` | **제거** | — |
| `GOOGLE_CLIENT_SECRET` | **제거** | — |
| `GITHUB_CLIENT_ID` | **신규** | GitHub OAuth 앱 Client ID |
| `GITHUB_CLIENT_SECRET` | **신규** | GitHub OAuth 앱 Client Secret |
| `GITHUB_TOKEN` | 유지 (optional) | 레거시 리포 fallback용 |
| `GITHUB_WEBHOOK_SECRET` | 유지 (optional) | 레거시 리포 Webhook 검증 fallback |
| `SESSION_SECRET` | 유지 | 세션 쿠키 서명 키 |

### GitHub OAuth 앱 설정 (수동 작업)

1. github.com → Settings → Developer settings → OAuth Apps → New OAuth App
2. Homepage URL: `http://localhost:8000` (로컬) 또는 프로덕션 URL
3. Authorization callback URL: `http://localhost:8000/auth/callback`
4. Client ID/Secret 복사 → `.env`에 `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` 설정

---

## 리포 추가 UI

### `src/github_client/repos.py`

```python
async def list_user_repos(token: str) -> list[dict]:
    """사용자가 접근 가능한 리포 목록 반환 (public + private, per_page=100, sort=updated)"""
    # GET https://api.github.com/user/repos?per_page=100&sort=updated
    # Authorization: Bearer {token}
    # 반환: [{"full_name": "owner/repo", "private": bool, "description": str}, ...]

async def create_webhook(
    token: str,
    repo_full_name: str,
    webhook_url: str,
    secret: str,
) -> int:
    """GitHub Webhook 생성 → webhook_id 반환"""
    # POST https://api.github.com/repos/{owner}/{repo}/hooks
    # body: {"name": "web", "active": true,
    #        "events": ["push", "pull_request"],
    #        "config": {"url": webhook_url, "content_type": "json", "secret": secret}}
    # 반환: webhook_id (int)

async def delete_webhook(token: str, repo_full_name: str, webhook_id: int) -> bool:
    """GitHub Webhook 삭제"""
    # DELETE https://api.github.com/repos/{owner}/{repo}/hooks/{id}
```

### 신규 라우트 (`src/ui/router.py`)

| Method | URL | 설명 |
|--------|-----|------|
| `GET` | `/repos/add` | 리포 추가 페이지 |
| `POST` | `/repos/add` | 리포 등록 + Webhook 자동 생성 |
| `GET` | `/api/github/repos` | 사용자 리포 목록 JSON |

### 리포 추가 흐름

```
GET /repos/add
  → require_login
  → /api/github/repos 는 JS fetch로 호출 (비동기 드롭다운)
  → add_repo.html 렌더링

GET /api/github/repos
  → require_login
  → list_user_repos(current_user.github_access_token)
  → 이미 DB에 등록된 리포 제외
  → JSON 반환: [{"full_name": "...", "private": bool}, ...]

POST /repos/add (form: repo_full_name)
  → require_login
  → 중복 체크: 이미 등록된 리포면 에러 반환
  → webhook_secret = secrets.token_hex(32)
  → webhook_url = str(request.base_url) + "webhooks/github"
      (FastAPI Request.base_url 사용 — 별도 환경변수 불필요)
  → webhook_id = await create_webhook(token, repo_full_name, webhook_url, webhook_secret)
  → Repository DB 저장:
      full_name=repo_full_name, user_id=current_user.id,
      webhook_secret=webhook_secret, webhook_id=webhook_id
  → 302 /repos/{repo_full_name}
```

### `src/templates/add_repo.html`

- 드롭다운(select): JS로 `/api/github/repos` 호출 후 옵션 채움
- 로딩 스피너 (GitHub API 응답 대기)
- 이미 등록된 리포는 목록에서 제외
- 제출 버튼: "리포 추가 + Webhook 생성"

### `src/templates/overview.html` 변경

- 헤더 영역에 "리포 추가" 버튼 → `/repos/add` 링크

---

## Webhook 검증 변경

### `src/webhook/router.py`

```
POST /webhooks/github 수신
  → payload 파싱: repository.full_name 추출
  → DB에서 Repository 조회 (full_name 기준)
  → repo.webhook_secret 있으면 → 리포별 시크릿으로 서명 검증
  → repo.webhook_secret 없으면 (레거시) → settings.github_webhook_secret fallback
  → 서명 불일치 → 401
  → 이후 기존 파이프라인 흐름 동일
```

`src/webhook/validator.py`는 변경 없음 (함수 signature 동일).

**주의:** 서명 검증 전 payload body를 먼저 읽어야 함. full_name 파싱은 서명 검증 후 JSON 파싱 시 함께 처리.

실제 구현 순서:
1. payload body 읽기
2. JSON 파싱 → full_name 추출
3. DB에서 시크릿 조회
4. 시크릿으로 서명 검증

---

## 파이프라인 변경

### `src/worker/pipeline.py`

```python
async def run_analysis_pipeline(event: str, data: dict):
    repo_full_name = ...  # data에서 추출 (기존 로직)

    # 토큰 결정
    with SessionLocal() as db:
        repo = db.query(Repository).filter_by(full_name=repo_full_name).first()
        token = (
            repo.owner.github_access_token
            if repo and repo.owner and repo.owner.github_access_token
            else settings.github_token  # 레거시 fallback
        )

    # 이후 token을 GitHub API 호출에 사용 (기존 settings.github_token 대체)
    files = await get_pr_files(token, repo_full_name, pr_number)
    ...
    await post_pr_comment(token, repo_full_name, pr_number, body)
    await post_github_review(token, repo_full_name, pr_number, decision, body)
    await merge_pr(token, repo_full_name, pr_number)
```

---

## 테스트 계획

| 파일 | 테스트 내용 |
|------|-------------|
| `tests/test_github_repos.py` | `list_user_repos()`, `create_webhook()`, `delete_webhook()` — httpx mock |
| `tests/test_auth_github.py` | OAuth 라우트 — GitHub API mock (기존 test_auth_google.py 교체) |
| `tests/test_user_model.py` | github_id, github_login, github_access_token 필드 (기존 수정) |
| `tests/test_ui_router.py` | `/repos/add` GET/POST, `/api/github/repos` — mock 추가 |
| `tests/test_webhook_router.py` | 리포별 시크릿 검증, 레거시 fallback 검증 |
| `tests/test_pipeline.py` | owner 토큰 사용, settings.github_token fallback |

Google OAuth 관련 테스트 파일(`tests/test_auth_google.py`) → `tests/test_auth_github.py`로 교체.

---

## 검증

```bash
# 1. 단위 테스트 전체 통과
make test

# 2. 코드 품질
make lint

# 3. 수동 E2E 검증
# - / 접근 → /login 리다이렉트 확인
# - "GitHub로 로그인" 클릭 → GitHub OAuth 동의 → 대시보드 리다이렉트
# - /repos/add 접근 → 드롭다운에 리포 목록 표시 확인
# - 리포 선택 → 추가 → /repos/{repo} 리다이렉트 확인
# - GitHub 리포 Settings → Webhooks → 자동 생성된 Webhook 확인
# - GitHub에 push → Webhook 수신 → 분석 파이프라인 정상 동작 확인
```

---

## 알려진 제약사항

- **GitHub OAuth token 만료 없음**: GitHub OAuth App 토큰은 기본적으로 만료되지 않음 (사용자가 revoke하지 않는 한). Phase 8C 이후 필요 시 token refresh 고려.
- **리포 100개 제한**: `per_page=100`으로 첫 페이지만 조회. 리포 수가 많으면 페이지네이션 필요 (Phase 8C 이후 개선).
- **Webhook 삭제 UI 없음**: Phase 8B에서는 리포 추가만 구현. 리포 삭제/Webhook 제거 UI는 Phase 8C 이후 추가.
- **레거시 리포**: `user_id=NULL`, `webhook_secret=NULL` 리포는 설정 화면 접근 가능하나 대시보드 미표시 (Phase 8A 동일).
