> ⚠️ **ARCHIVED — 2026-04-27**: 이 문서는 해당 시점에 완료된 작업을 기록한 것으로, 현재 코드베이스와 일치하지 않을 수 있습니다. 현재 상태는 [docs/STATE.md](../STATE.md)를 참조하세요.

# Railway 배포 실패 → GitHub Issue 자동 등록 (Design Spec)

**작성일**: 2026-04-20
**상태**: ✅ 완료 (2026-04-20) — STATE.md 그룹 7 참조

## 1. Context

SCAManager 에 등록된 사용자 리포들이 각자 Railway 에 배포될 때 빌드가 실패해도, 개발자는 Railway 대시보드를 직접 열어야 실패 사실을 알 수 있다. 빌드 실패는 보통 커밋 직후에 발생하는데, Git 플랫폼(이 경우 GitHub)에서 알림·추적이 되지 않으면 이슈 발견과 대응이 지연된다.

현재 SCAManager 는 이미 "저점 분석 결과 → GitHub Issue 자동 생성"(`src/notifier/github_issue.py`) 인프라를 갖추고 있다. 동일 패턴을 Railway 빌드 실패 이벤트로 확장해 다음을 달성한다:

- Railway 빌드 실패 즉시, 해당 리포의 GitHub Issue 가 자동 생성된다
- Issue 본문에 커밋 정보 + 실패 로그(마지막 200줄)가 포함돼 개발자가 바로 원인 파악 가능
- 기존 `create_low_score_issue` 와 같이 리포 owner 권한의 GitHub 토큰으로 생성 → 팀 권한 체계 준수

## 2. 범위 결정 사항 (브레인스토밍 결과)

| 항목 | 결정 |
|------|------|
| 대상 | 등록된 모든 Repo (SCAManager 자체 + 사용자 리포 무관하게 `railway_deploy_alerts=True` 인 모든 Repo) |
| 이벤트 수신 | Railway Project Webhook (POST 수신) |
| 로그 본문 포함 | Railway GraphQL API 호출로 전체 로그 가져오기 |
| URL 스키마 | `POST /webhooks/railway/{token}` — per-repo 고유 토큰 기반 인증·매칭 |
| 대상 실패 유형 | Build 실패만 (`FAILED` / `BUILD_FAILED`) — Runtime Crash 미포함 |
| 프리셋 통합 | `railway_deploy_alerts` 필드를 3개 프리셋(🌱 최소·⚙️ 표준·🛡️ 엄격)에 반영 |

## 3. 데이터 모델 변경

### 3-1. `src/models/repo_config.py` 신규 필드 3개

| 필드 | 타입 | 기본값 | 용도 |
|------|------|-------|------|
| `railway_deploy_alerts` | `Boolean` | `False` | 기능 opt-in 스위치 (프리셋이 제어) |
| `railway_webhook_token` | `String(64)` | `None` | `/webhooks/railway/{token}` 경로 매칭 키. `secrets.token_hex(32)` 로 **신규 리포 등록 시** 자동 발급 (기존 `hook_token` 과 동일 타이밍). 기능 추가 이전에 등록된 구 리포는 settings 저장 시 자동 발급 |
| `railway_api_token` | `String` (Fernet 암호화) | `None` | GraphQL deploymentLogs 조회용. `src/crypto.py` 의 `encrypt_token/decrypt_token` 재사용 |

### 3-2. Alembic 마이그레이션

`alembic/versions/xxxx_add_railway_fields_to_repo_config.py` 신설:
- 3개 컬럼 추가 (모두 nullable 또는 기본값 포함 → 기존 데이터 호환)
- `create_unique_constraint('uq_repo_config_railway_webhook_token', 'repo_config', ['railway_webhook_token'])` — 토큰 고유성 보장

**주의**: `batch_alter_table` 금지 (CLAUDE.md 규약). PostgreSQL 전용 `op.add_column` + `op.create_unique_constraint` 직접 호출.

### 3-3. 중복 방지 전략

신규 테이블 없이 **GitHub Issue 본문의 HTML 주석 마커**로 dedup:

```html
<!-- scamanager-railway-deployment-id:{deployment_id} -->
```

Issue 생성 전 GitHub Search API (`/search/issues?q=repo:{repo}+"{marker}"`) 로 동일 deployment_id 마커가 있는 Issue 존재 여부 확인. 있으면 생성 건너뛰기.

근거: Railway 는 같은 deployment 를 여러 번 알림하지는 않지만, 네트워크 재시도·수동 redeploy 로 같은 deployment_id 이벤트가 중복 도달할 가능성 존재. 별도 테이블 대신 기존 Issue 를 진실 소스로 삼아 단순성 유지.

## 4. 신규 모듈 구조

```
src/railway_client/
    __init__.py
    models.py         # RailwayDeployEvent dataclass
    webhook.py        # parse_railway_payload(body) → RailwayDeployEvent | None
    logs.py           # async fetch_deployment_logs(api_token, deployment_id) → str
src/notifier/
    railway_issue.py  # async create_deploy_failure_issue(...) + _build_issue_body()
src/webhook/router.py (수정)
    POST /webhooks/railway/{token}
```

### 4-1. `src/railway_client/models.py`

```python
@dataclass(frozen=True)
class RailwayDeployEvent:
    deployment_id: str
    project_id: str
    project_name: str
    environment_name: str
    status: str                 # "FAILED" | "BUILD_FAILED" | 기타
    commit_sha: str | None
    commit_message: str | None
    repo_full_name: str | None  # Railway payload 가 제공하는 GitHub repo (검증용)
    timestamp: str
```

### 4-2. `src/railway_client/webhook.py`

```python
def parse_railway_payload(body: dict) -> RailwayDeployEvent | None:
    """Railway webhook JSON 을 RailwayDeployEvent 로 파싱. 필수 필드 없으면 None."""
    # 최소 필수: body["type"]=="DEPLOY", body["status"] in {FAILED, BUILD_FAILED},
    # body["deployment"]["id"] 존재
```

**판단 로직**:
- `type != "DEPLOY"` → `None`
- `status == "SUCCESS"` → `None` (빌드 성공은 무시)
- `status not in {"FAILED", "BUILD_FAILED"}` → `None`
- 필수 필드 누락 → `None` + WARN 로그

### 4-3. `src/railway_client/logs.py`

```python
async def fetch_deployment_logs(
    api_token: str,
    deployment_id: str,
    tail_lines: int = 200,
) -> str:
    """Railway GraphQL `deploymentLogs` 조회 → 마지막 N줄 반환."""
    # endpoint: https://backboard.railway.app/graphql/v2
    # Authorization: Bearer {api_token}
    # 타임아웃: HTTP_CLIENT_TIMEOUT (constants.py 재사용)
    # 실패 시 RailwayLogFetchError (모듈 내부 정의) raise
    #   호출처에서 잡아 "log fetch failed" 문자열로 대체
```

### 4-4. `src/notifier/railway_issue.py`

```python
async def create_deploy_failure_issue(
    *,
    github_token: str,
    repo_full_name: str,
    event: RailwayDeployEvent,
    logs_tail: str | None,
) -> int | None:
    """Issue 중복 체크 후 생성. 이미 존재하면 None, 생성 성공 시 Issue number."""
```

본문 구조 (`_build_issue_body`):
```markdown
<!-- scamanager-railway-deployment-id:{deployment_id} -->

## 🚨 Railway Build Failed

- **Project**: {project_name} (`{project_id}`)
- **Environment**: {environment_name}
- **Status**: {status}
- **Commit**: [`{sha[:7]}`]({commit_url}) — {commit_message_first_line}
- **Time**: {timestamp}

### Build Log (last 200 lines)
```
{logs_tail or '로그를 가져오지 못했습니다. Railway 대시보드에서 확인해주세요.'}
```

---
<sub>Auto-generated by SCAManager · [Railway 대시보드 열기](https://railway.app/project/{project_id})</sub>
```

Labels: `["scamanager", "deploy-failure", "railway"]`

## 5. Webhook 라우트

### 5-1. `src/webhook/router.py` 추가

```python
@router.post("/webhooks/railway/{token}", status_code=202)
async def railway_webhook(
    token: str,
    request: Request,
    background_tasks: BackgroundTasks,
):
    # 1. token 조회 (HMAC compare_digest 타이밍 공격 방지)
    # 2. RepoConfig/Repository 조회, 없거나 alerts=False 면 silent 200
    # 3. payload 파싱, 빌드 실패 아니면 silent 200
    # 4. BackgroundTasks 에 _handle_railway_deploy_failure 등록
    # 5. return {"status": "accepted"}
```

보안 패턴:
- `hmac.compare_digest(config.railway_webhook_token or "", token)` — 상수 시간 비교
- 실패 시 404 로 응답 (존재 여부 노출 방지)

### 5-2. 백그라운드 핸들러

```python
async def _handle_railway_deploy_failure(
    repo_config: RepoConfigSnapshot,  # 세션 종료 후 안전한 dataclass
    event: RailwayDeployEvent,
):
    # 1. api_token 존재 시 fetch_deployment_logs, 실패/부재 시 logs_tail=None
    # 2. github_token 결정: repo.owner.plaintext_token or settings.github_token
    # 3. create_deploy_failure_issue 호출
    # 4. 모든 단계 try/except 로 감싸 파이프라인 무중단
```

## 6. UI 변경 (`settings.html`)

### 6-1. 신규 카드 ⑤ "Railway 알림" (시스템 카드 아래)

```
┌─ ⑤ Railway 배포 알림 ──────────────┐
│ ☐ 빌드 실패 시 자동 Issue 생성     │
│                                      │
│ API 토큰 (로그 조회용)              │
│ [**********]                         │
│                                      │
│ Webhook URL (Railway Project에 등록) │
│ {APP_BASE_URL}/webhooks/railway/xxx  │
│ [📋 복사]                            │
│                                      │
│ ℹ️ Railway Project Settings →       │
│   Webhooks 에 위 URL 을 추가하세요  │
└──────────────────────────────────────┘
```

### 6-2. JS 수정

`PRESETS` 3개 블록에 `railway_deploy_alerts` 추가:

| 프리셋 | `railway_deploy_alerts` |
|-------|------------------------|
| `minimal` | `false` |
| `standard` | `true` |
| `strict` | `true` |

`applyPreset()` 에 한 줄:
```javascript
const railwayAlertInput = document.querySelector('input[name="railway_deploy_alerts"]');
if (railwayAlertInput) railwayAlertInput.checked = p.railway_deploy_alerts;
```

**프리셋이 건드리지 않는 필드**: `railway_webhook_token`, `railway_api_token` — 알림 채널 URL 규약(CLAUDE.md) 준수.

### 6-3. 5-way 동기화 체크리스트 (신규 설정 추가 규약 확장)

| 계층 | 변경 |
|------|------|
| 1. `RepoConfig` ORM | 3개 필드 추가 + 마이그레이션 |
| 2. `RepoConfigData` dataclass | 동일 필드 |
| 3. `RepoConfigUpdate` API body | 동일 필드 (`/api/repos/{repo}/config` PUT) |
| 4. `settings.html` 폼 | 체크박스 + 2개 입력란 |
| 5. `settings.html` PRESETS | `railway_deploy_alerts` 3개 블록 + `applyPreset()` |

## 7. 에러 처리 전략

| 상황 | 응답·동작 |
|------|----------|
| 토큰 경로 매칭 실패 | HTTP 404, 본문 `{"detail":"Not Found"}` — repo 존재 여부 노출 방지 |
| `alerts=False` | HTTP 200 `{"status":"ignored"}` — 즉시 반환 |
| payload 파싱 실패 | HTTP 200 `{"status":"ignored"}` + WARN 로그 |
| 빌드 실패 아닌 이벤트 (SUCCESS 등) | HTTP 200 `{"status":"ignored"}` |
| Railway API 호출 실패 | Issue 는 **생성**, logs 섹션에 에러 메시지 삽입 |
| Issue 중복 (dedup 매칭) | HTTP 202 + 로그만 기록, 재생성 안 함 |
| GitHub Issue 생성 실패 | `logger.error` + 파이프라인 무중단 (알림 채널 독립성 원칙 준수) |

## 8. 테스트 전략

### 8-1. 신규 테스트 파일

`tests/test_railway_webhook.py` — 라우트 + 백그라운드 핸들러
`tests/test_railway_client.py` — payload 파싱 + 로그 조회
`tests/test_railway_issue_notifier.py` — Issue 생성·중복 체크

### 8-2. 주요 케이스 (최소 12개)

| # | 케이스 | 검증 대상 |
|---|-------|---------|
| 1 | 잘못된 토큰 | 404 |
| 2 | `alerts=False` + 유효 payload | 200, Issue 미생성 |
| 3 | `status=SUCCESS` | 200, Issue 미생성 |
| 4 | `status=BUILD_FAILED` + api_token 있음 | Issue 생성 + 로그 포함 |
| 5 | `status=FAILED` + api_token 없음 | Issue 생성 + "log fetch failed" 대체 문자열 |
| 6 | `status=BUILD_FAILED` + Railway API 타임아웃 | Issue 생성 + 에러 메시지 로그 |
| 7 | 동일 deployment_id 재수신 | 중복 Issue 미생성 |
| 8 | payload 필수 필드 누락 | 200 + WARN |
| 9 | `type != "DEPLOY"` | 200, 무시 |
| 10 | GitHub Issue 생성 실패 (403) | 파이프라인 무중단, 에러 로그 |
| 11 | 프리셋 `minimal` → `railway_deploy_alerts=false` | UI JS 테스트 또는 E2E |
| 12 | 프리셋 `standard/strict` → `railway_deploy_alerts=true` | 동일 |

### 8-3. 기대 테스트 증분

- 단위: **+12 ~ +15** → 1076 + 15 = **~1091**
- 기존 테스트 영향 없음 (기능 확장)

## 9. 보안 고려

| 항목 | 조치 |
|------|------|
| Railway webhook 는 HMAC 미지원 | token 경로 기반 인증 + `hmac.compare_digest` |
| `railway_api_token` 평문 저장 시 DB 유출 리스크 | `src/crypto.py` Fernet 암호화 |
| API 토큰 반환 시 UI 노출 | `RepoConfigData` 에서 `****` 마스킹 반환 |
| 타이밍 공격 | 모든 토큰 비교에 `hmac.compare_digest` 사용 |
| 내부 DB 존재 여부 노출 | 잘못된 토큰은 404 일관 |

## 10. 비-목표 (향후 Phase)

- Runtime Crash (`CRASHED`) 감지 — 일시 럭스 오탐 위험
- 배포 성공 알림 — 정상 동작은 알림 불필요
- SCAManager 가 Railway API 로 webhook 자동 등록 — Railway API 호출 권한 관리 복잡도
- Environment(staging/production) 별 다른 알림 채널 — payload `environment_name` 은 Issue body 에만 포함
- 슬랙·Telegram 으로 Railway 실패 알림 확장 — GitHub Issue 우선, 다음 Phase

## 11. 마이그레이션 / 롤아웃

1. **마이그레이션 자동 적용** — `main.py` lifespan 에서 alembic 자동 실행 (기존 패턴)
2. **기본값 False** — 기존 리포는 영향 없음 (기능 비활성 상태로 안전)
3. **리포 등록 플로우 변경 없음** — 토큰은 "최초 save 시 자동 발급" 로직으로 지연 처리
4. **구 리포 업그레이드** — settings 페이지 최초 방문 시 `railway_webhook_token` 자동 발급 + save

## 12. Critical Files (구현 대상)

| 파일 | 변경 유형 |
|------|---------|
| `src/models/repo_config.py` | 필드 3개 추가 |
| `alembic/versions/xxxx_add_railway_fields_to_repo_config.py` | 신규 |
| `src/config_manager/manager.py` | `RepoConfigData` 확장 + save 시 token 자동 발급 |
| `src/api/repos.py` | `RepoConfigUpdate` body 확장 |
| `src/crypto.py` | 변경 없음 (재사용) |
| `src/railway_client/__init__.py` | 신규 |
| `src/railway_client/models.py` | 신규 |
| `src/railway_client/webhook.py` | 신규 |
| `src/railway_client/logs.py` | 신규 |
| `src/notifier/railway_issue.py` | 신규 |
| `src/webhook/router.py` | 신규 엔드포인트 1개 |
| `src/templates/settings.html` | 카드 ⑤ + PRESETS 3곳 수정 |
| `tests/test_railway_webhook.py` | 신규 |
| `tests/test_railway_client.py` | 신규 |
| `tests/test_railway_issue_notifier.py` | 신규 |
| `CLAUDE.md` | 주의사항 섹션 — "Railway Webhook 토큰 경로 인증", "5-way 동기화 규약" |
| `docs/STATE.md` | 그룹 7 이력 추가, 테스트 수치 갱신 |

## 13. Verification

```bash
# 단위 테스트
make test                          # 1076 → ~1091 기대

# 린트
make lint                          # pylint 10.00 + flake8 0건 + bandit HIGH 0

# 수동 E2E
make run
# 1. Settings 페이지 접속
# 2. 각 프리셋 클릭 → Railway 알림 체크박스 상태 확인
# 3. API 토큰 입력 + 저장
# 4. Webhook URL 복사 → 테스트용 Railway 프로젝트에 등록
# 5. 의도적으로 빌드 실패 커밋 push → GitHub Issue 자동 생성 확인

# 중복 방지 확인
# 6. 같은 실패 이벤트 재발송 → 두 번째 Issue 생성되지 않는지 확인
```

## 14. 재사용 기존 자산

| 자산 | 경로 | 재사용 지점 |
|------|------|-----------|
| Fernet 토큰 암호화 | `src/crypto.py` encrypt_token/decrypt_token | `railway_api_token` 저장 |
| Issue 본문 조립 패턴 | `src/notifier/github_issue.py` `_build_issue_body` | `railway_issue._build_issue_body` 템플릿 참고 |
| GitHub API 헤더 | `src/github_client/helpers.py` `github_api_headers` | Issue POST 호출 |
| HTTP 타임아웃 상수 | `src/constants.py` `HTTP_CLIENT_TIMEOUT` | Railway GraphQL 클라이언트 |
| HMAC 상수시간 비교 | 표준 라이브러리 `hmac.compare_digest` | 토큰 경로 매칭 |
| BackgroundTasks 비동기 | FastAPI `BackgroundTasks` | Railway 이벤트 처리 |
| 프리셋 JS 헬퍼 | `applyPreset()`, `_setPair()` | `railway_deploy_alerts` 체크박스 토글 |
