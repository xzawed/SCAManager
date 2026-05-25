# AI 분석 결과 GitHub Issue 등록 기능 — 설계 스펙

> 작성일: 2026-05-24 | 상태: 승인됨

## 개요

Repo별 대시보드에서 AI 분석(AI 제안사항 + 정적 분석 이슈)을 사용자가 확인·판단하여 GitHub Issue로 등록하는 기능. 등록 이력을 DB에 저장하고 GitHub Issue 상태(open/closed)를 실시간 동기화하여 처리 현황을 한눈에 파악할 수 있게 한다.

---

## 결정 사항

| 항목 | 결정 |
|------|------|
| 진입점 | analysis_detail (개별 등록) + repo_detail (일괄 등록) — 양쪽 모두 |
| 등록 대상 | AI 제안사항(`ai_suggestions`) + 정적 분석 이슈(`AnalysisIssue`) — 탭으로 구분 |
| 등록 흐름 | 편집 가능 모달(제목·본문·라벨 수정 가능) → GitHub Issue 생성 |
| 중복 처리 | DB 등록 이력 저장 + GitHub API 상태 실시간 동기화 (TTL 5분 캐시) |
| 구현 방식 | 2단계 분할 — Phase 1: analysis_detail / Phase 2: repo_detail + 실시간 sync |

---

## 아키텍처

### 신규 파일

| 파일 | 역할 |
|------|------|
| `src/models/issue_registration.py` | IssueRegistration ORM 모델 |
| `src/repositories/issue_registration_repo.py` | DB CRUD + issue_key 중복 조회 |
| `src/services/issue_registration_service.py` | 등록 로직 + GitHub 상태 동기화 |
| `src/api/issue_registration.py` | REST 엔드포인트 3개 |
| `alembic/versions/0034_issue_registration.py` | DB 마이그레이션 |

### 기존 파일 수정

| 파일 | 변경 내용 |
|------|----------|
| `src/templates/analysis_detail.html` | Issue 등록 패널(탭 + 버튼 + 모달) 추가 |
| `src/templates/repo_detail.html` | 반복 이슈 일괄 등록 패널 추가 (Phase 2) |
| `src/github_client/issues.py` | `create_issue()` 함수 추가 |
| `src/main.py` | issue_registration 라우터 include |

---

## 데이터 모델

### `issue_registration` 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | int PK | |
| `analysis_id` | int FK → analyses | 출처 분석 |
| `repo_id` | int FK → repositories | 대상 리포 |
| `issue_type` | enum | `ai_suggestion` / `static_issue` |
| `issue_key` | varchar(64) | 중복 판별 키 — AI: `SHA256(suggestion_text[:500])` / 정적: `SHA256(f"{tool}:{category}:{message[:200]}")` (라인 번호 제외 — 커밋 간 line drift로 인한 중복 등록 방지) |

> **복합 유니크 제약**: `UniqueConstraint('repo_id', 'issue_key')` — 동일 리포 내 중복 방지, 다른 리포 동일 이슈는 허용.
| `github_issue_number` | int | 생성된 GitHub Issue 번호 |
| `github_issue_state` | enum | `open` / `closed` |
| `github_issue_synced_at` | datetime | 마지막 상태 동기화 시각 |
| `created_at` | datetime | 등록 시각 |

---

## Phase 1 — analysis_detail 개별 등록

### UI 흐름

1. analysis_detail 페이지 하단에 **"📋 GitHub Issue 등록"** 패널 추가
2. **AI 제안사항 탭** / **정적 분석 이슈 탭** 구분
3. 각 항목 우측에 상태별 표시:
   - 미등록: **"Issue 등록"** 버튼
   - 진행중: **"🔵 #N 진행중"** 뱃지 (GitHub Issue URL 링크)
   - 해결됨: **"✅ #N 해결됨"** 뱃지 + 항목 취소선 처리

### 편집 모달

- **제목**: 자동 채워짐 — `💡 [AI 제안] {내용 요약} — {SHA}` / `🔴 [{카테고리}] {tool} {rule} — {SHA}`
- **본문**: 마크다운 자동 생성 — `## 📌 분석 정보` + `## 내용` + 편집 가능 영역
- **라벨**: 자동 제안 (ai-suggestion·enhancement / security·critical 등) + 추가/삭제 가능. GitHub API는 존재하지 않는 라벨을 자동 생성하므로 별도 라벨 사전 검증 불필요.
- **버튼**: 취소 / "GitHub에 Issue 생성 →"
- 생성 완료 후: 모달 닫힘 + 버튼이 "🔵 #N 진행중" 뱃지로 즉시 전환 + 성공 토스트

---

## Phase 2 — repo_detail 반복 이슈 일괄 등록

### UI 흐름

1. repo_detail 페이지에 **"🔁 반복 이슈 — Issue 등록 관리"** 패널 추가
2. **정적 분석 이슈 탭** / **AI 제안사항 탭** 구분
3. 필터: critical / warning / 전체 + "미등록만 보기" 토글
4. 항목별 체크박스 선택 → 하단 **"선택 항목 일괄 Issue 등록 (N건) →"** 버튼
5. 일괄 등록 모달: 항목을 순서대로 편집 — **"생성 후 다음 →"** / **"이 항목 건너뜀"** 버튼

### GitHub 상태 동기화

- **트리거**: 페이지 로드 시 등록된 이슈 상태 일괄 조회
- **캐시**: `github_issue_synced_at` 기준 TTL 5분 — 중복 API 호출 방지
- **방식**: `asyncio.gather` 병렬 처리 — 페이지 로드 블로킹 없음

---

## REST API

### `POST /api/issues/register`

**요청**
```json
{
  "analysis_id": 123,
  "issue_type": "ai_suggestion",
  "issue_key": "sha256-hash",
  "title": "💡 [AI 제안] 캐시 TTL 조정",
  "body": "## 📌 분석 정보\n커밋: abc1234...",
  "labels": ["ai-suggestion", "enhancement"]
}
```

**응답**
```json
{
  "github_issue_number": 44,
  "github_issue_url": "https://github.com/owner/repo/issues/44",
  "state": "open"
}
```

### `GET /api/issues/status?analysis_id=` (Phase 1)

analysis_detail용 — 해당 분석의 등록 이력 조회 + TTL 만료 항목 GitHub 상태 동기화 후 반환. `analysis_id` 단독 사용.

### `GET /api/issues/repo-summary?repo_id=` (Phase 2)

repo_detail용 반복 이슈 목록 + 각 항목의 등록 상태 반환.

---

## 에러 처리

| 상황 | 처리 |
|------|------|
| 같은 `issue_key` 이미 존재 | `409 Conflict` + 기존 Issue 번호 반환 — 모달에 "이미 등록된 이슈입니다 (#N)" 표시 |
| GitHub API 5xx | DB 저장 안 함 — "GitHub 연결 오류, 다시 시도해 주세요" 토스트 |
| GitHub 토큰 권한 부족 | `403` → "Issues 쓰기 권한이 없습니다. 토큰을 확인해 주세요" |
| 상태 동기화 실패 | 기존 캐시 상태 유지 — 조용히 실패, 사용자에게 오류 미노출 |
| 일괄 등록 중 일부 실패 | 성공 N건 / 실패 M건 요약 토스트 표시 |

---

## 테스트 계획

### 단위 테스트
- `issue_registration_repo`: `issue_key` 중복 감지, DB CRUD
- `issue_registration_service`: GitHub API mock → 생성 성공/실패 분기
- `github_client/issues.py`: `create_issue()` 요청 형식 검증

### 통합 테스트
- `POST /api/issues/register` → DB 저장 + GitHub API 호출 순서 검증
- `GET /api/issues/status` → TTL 캐시 hit/miss 동작

### 회귀 가드
- 중복 `issue_key` 409 응답 보장
- GitHub API 실패 시 DB 미저장 보장
- 일괄 등록 중 1건 실패해도 나머지 계속 진행 보장

---

## 구현 순서 (Phase 1 → Phase 2)

**Phase 1**
1. `alembic/versions/0034_issue_registration.py` — 마이그레이션
2. `src/models/issue_registration.py` — ORM
3. `src/repositories/issue_registration_repo.py` — DB CRUD
4. `src/github_client/issues.py` — `create_issue()` 추가
5. `src/services/issue_registration_service.py` — 등록 + 동기화 로직
6. `src/api/issue_registration.py` — REST 엔드포인트
7. `src/templates/analysis_detail.html` — UI 패널 + 모달
8. 테스트 작성

**Phase 2**
1. `src/services/issue_registration_service.py` — repo 반복 이슈 집계 + 상태 일괄 동기화
2. `src/api/issue_registration.py` — `repo-summary` 엔드포인트 추가
3. `src/templates/repo_detail.html` — 일괄 등록 패널
4. 테스트 추가
