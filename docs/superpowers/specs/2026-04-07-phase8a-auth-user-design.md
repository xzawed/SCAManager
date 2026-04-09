# Phase 8A: Google OAuth 로그인 + User 모델 + 사용자별 대시보드

**날짜:** 2026-04-07  
**상태:** 승인됨  
**다음 Phase:** 8B (리포 추가 UI + 사용자별 GitHub 토큰 + Webhook 자동 생성)

---

## 배경 및 목적

SCAManager는 현재 인증 없는 단일 관리자 도구다. Webhook으로 등록된 리포가 전역으로 공유되며, 누구나 대시보드에 접근할 수 있다.

이번 Phase는 SaaS 전환의 첫 단계로, 다음을 달성한다:

- Google OAuth로 사용자 인증
- `User` 모델로 사용자 데이터 분리
- 각 사용자가 본인 리포만 볼 수 있는 대시보드
- Phase 8B(리포 추가), 8C(PR 관리)의 기반 구조 확립

**전체 로드맵:**

| Phase | 내용 |
|---|---|
| **8A (현재)** | Google OAuth + User 모델 + 사용자별 대시보드 |
| 8B | 리포 추가 UI + 사용자별 GitHub 토큰 + Webhook 자동 생성 |
| 8C | PR 관리 UI (오픈 PR 목록 + Approve/Reject) |

---

## 아키텍처

### 신규 파일

```
src/auth/
├── google.py        # Google OAuth2 플로우 (authlib)
└── session.py       # get_current_user() 헬퍼 + require_login 의존성

src/models/
└── user.py          # User ORM

src/templates/
└── login.html       # 로그인 페이지

alembic/versions/
└── 0005_add_users_and_user_id.py
```

### 변경 파일

```
src/main.py              # SessionMiddleware 추가, /auth/* 라우터 등록
src/ui/router.py         # require_login 의존성, user_id 필터링
src/models/repository.py # user_id FK 추가 (nullable)
src/config.py            # GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SESSION_SECRET 추가
requirements.txt         # authlib>=1.3.0, httpx>=0.27.0
```

---

## 데이터 모델

### 신규: `users` 테이블

```python
class User(Base):
    __tablename__ = "users"

    id           = Column(Integer, primary_key=True, index=True)
    google_id    = Column(String, unique=True, nullable=False, index=True)
    email        = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    created_at   = Column(DateTime, default=datetime.utcnow)

    repositories = relationship("Repository", back_populates="owner")
```

### 변경: `repositories` 테이블

```python
# 기존 필드 유지, 아래 컬럼 추가
user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
owner   = relationship("User", back_populates="repositories")
```

`nullable=True`: 기존 Webhook으로 등록된 레코드의 하위 호환성 보장. 소유자 없는 레코드는 대시보드에서 숨김 처리.

---

## 인증 흐름

```
GET / (세션 없음)
    → 302 /login

GET /login
    → login.html ("Google로 로그인" 버튼)

GET /auth/google
    → authlib로 Google OAuth 동의 URL 생성
    → 302 accounts.google.com/o/oauth2/...

GET /auth/callback?code=...&state=...
    → code를 access_token으로 교환 (Google API)
    → userinfo 엔드포인트로 google_id, email, name 조회
    → users 테이블 upsert
      - 없으면 → 신규 User 생성 (자동 회원가입)
      - 있으면 → 기존 User 조회
    → session["user_id"] = user.id 저장
    → 302 /

POST /auth/logout
    → session.clear()
    → 302 /login
```

### 세션 방식

`starlette.middleware.sessions.SessionMiddleware` 사용. 서명된 쿠키로 추가 DB/Redis 불필요.

```python
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
```

---

## 환경변수

| 변수 | 필수 | 설명 |
|---|---|---|
| `GOOGLE_CLIENT_ID` | ✅ | Google Cloud Console → OAuth 2.0 클라이언트 ID |
| `GOOGLE_CLIENT_SECRET` | ✅ | Google Cloud Console → OAuth 2.0 클라이언트 시크릿 |
| `SESSION_SECRET` | ✅ | 세션 쿠키 서명 키 (32자 이상 랜덤 문자열 권장) |

**Google Cloud Console 설정:**
- OAuth 동의 화면 → 외부 사용자 타입
- 승인된 리다이렉션 URI: `http://localhost:8000/auth/callback` (로컬), `https://your-domain/auth/callback` (프로덕션)

---

## UI 라우트

### 신규

| Method | URL | 설명 |
|---|---|---|
| GET | `/login` | 로그인 페이지 (세션 있으면 / 리다이렉트) |
| GET | `/auth/google` | Google OAuth 시작 |
| GET | `/auth/callback` | Google 콜백 처리 |
| POST | `/auth/logout` | 로그아웃 |

### 변경

| URL | 변경 내용 |
|---|---|
| `GET /` | `require_login` 의존성 추가, `user_id` 필터링 |
| `GET /repos/{repo}` | `require_login` + 본인 소유 확인 (타인 → 404) |
| `GET /repos/{repo}/settings` | `require_login` + 본인 소유 확인 |
| `POST /repos/{repo}/settings` | `require_login` + 본인 소유 확인 |

### 변경 없음

`/webhooks/github`, `/api/webhook/telegram`, `/api/*`, `/health`

Webhook 엔드포인트는 GitHub에서 직접 호출하므로 세션 인증 불가. Phase 8B에서 per-repo 시크릿으로 보안 강화.

---

## 핵심 구현 상세

### `src/auth/session.py`

```python
from fastapi import Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from src.database import SessionLocal
from src.models.user import User

def get_current_user(request: Request) -> User | None:
    """세션에서 현재 사용자를 반환. 없으면 None."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    with SessionLocal() as db:
        return db.query(User).filter(User.id == user_id).first()

def require_login(request: Request) -> User:
    """로그인 필수 의존성. 비로그인 시 /login 리다이렉트."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user
```

### `src/ui/router.py` 변경 예시

```python
@router.get("/", response_class=HTMLResponse)
def overview(request: Request, current_user: User = Depends(require_login)):
    with SessionLocal() as db:
        repos = db.query(Repository).filter(
            Repository.user_id == current_user.id  # 필터 추가
        ).order_by(Repository.created_at.desc()).all()
    ...
```

---

## 마이그레이션

`alembic/versions/0005_add_users_and_user_id.py`:

1. `users` 테이블 생성
2. `repositories.user_id` 컬럼 추가 (nullable=True, FK → users.id)
3. 기존 데이터 변경 없음 (고아 레코드는 user_id=NULL 상태 유지)

---

## 테스트 계획

| 파일 | 테스트 내용 |
|---|---|
| `tests/test_user_model.py` | User CRUD, google_id unique 제약 |
| `tests/test_auth_session.py` | `get_current_user()` — 세션 있음/없음/잘못된 ID |
| `tests/test_auth_session.py` | `require_login()` — 비로그인 시 302 확인 |
| `tests/test_ui_router.py` | 비로그인 → `/login` 리다이렉트 |
| `tests/test_ui_router.py` | 로그인 후 본인 리포만 반환 |
| `tests/test_ui_router.py` | 타인 리포 접근 시 404 |

Google OAuth 실제 호출은 `unittest.mock.patch`로 mock 처리.  
기존 146개 단위 테스트는 `require_login` 우회를 위해 test client에 세션 주입 방식으로 수정.

---

## 검증

```bash
# 1. 단위 테스트 전체 통과
make test

# 2. 코드 품질
make lint

# 3. 수동 E2E 검증
# - /login 접근 → 로그인 페이지 표시
# - Google 로그인 → 대시보드 리다이렉트
# - 본인 리포만 표시 확인
# - /auth/logout → 로그인 페이지로 이동
# - 로그아웃 후 / 접근 → /login 리다이렉트
```
