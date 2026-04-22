# RailwayDeployEvent sub-dataclass 분리 — 설계 스펙 (기술부채 해소)

**작성일**: 2026-04-21
**상태**: ✅ 완료 (2026-04-22) — STATE.md 그룹 12 참조
**우선순위**: P3 (점수 영향 없음, 선제적 리팩토링)
**리스크**: 🟡 중간 (6 파일 / 25+ 참조 변경)

## 1. Context

2026-04-20 Phase D.1 cppcheck 이후 Phase-N+1 백로그에 추가됐던 권고 사항:

> `RailwayDeployEvent` 를 sub-dataclass 로 분리하는 리팩토링을 검토 권장 — pylint R0902 경고(`too-many-instance-attributes 9/7`)가 향후 설계 변경(Railway 모델 필드 추가)에서 R0914(too-many-locals)로 번질 위험.

현재 `src/railway_client/models.py` 의 `RailwayDeployEvent` 는 **9개 필드 평면 구조**:

```python
@dataclass(frozen=True)
class RailwayDeployEvent:
    deployment_id: str
    project_id: str
    project_name: str
    environment_name: str
    status: str
    commit_sha: str | None
    commit_message: str | None
    repo_full_name: str | None
    timestamp: str
```

**pylint 평가**: R0902 informational (9/7) — 점수 영향 없이 **warning 만 누적**. 2026-04-21 감사에서 현재 상태 유지 시 pylint 10.00/10 을 위협하진 않지만, Railway webhook payload 가 추가 필드(예: `build_duration_ms`, `branch_name`) 를 요구할 때 리팩토링 필요성 가중.

**이번 리팩토링의 목적**:
- pylint R0902 warning 제거 (informational → clean)
- 개념적 그룹화(`project` / `deployment` / `commit`) 로 가독성 향상
- 필드 추가 시 sub-dataclass 에만 영향 (Open/Closed Principle)

## 2. 범위 결정 사항

| 항목 | 결정 |
|------|------|
| 분리 전략 | 3-group flat → nested (project / deployment + commit) |
| 기존 API 시그니처 | `parse_railway_payload(body: dict) -> RailwayDeployEvent \| None` 불변 (반환 타입 구조만 변경) |
| 점수 스코어러 영향 | **없음** (Railway 이벤트는 `calculate_score` 진입점 아님) |
| 프로덕션 webhook 경로 | `POST /webhooks/railway/{token}` 외부 payload 구조 불변 |
| 마이그레이션 | 불필요 (dataclass 는 순수 메모리 객체, DB 컬럼 매핑 없음) |
| 테스트 영향 | 3 파일 (`test_railway_client.py`·`test_railway_issue_notifier.py`·`test_railway_webhook.py`) + 모든 `event.commit_sha` 같은 평면 접근을 `event.commit.commit_sha` 로 변경 |

## 3. 아키텍처 — Nested Dataclass 구조

### 3-1. 신규 구조 (`src/railway_client/models.py`)

```python
"""Railway webhook 이벤트 데이터 모델 (nested dataclass 구조)."""
from dataclasses import dataclass

RAILWAY_FAILURE_STATUSES: frozenset = frozenset({"FAILED", "BUILD_FAILED"})


@dataclass(frozen=True)
class RailwayProjectInfo:
    """Railway 프로젝트 식별 정보."""
    project_id: str
    project_name: str
    environment_name: str


@dataclass(frozen=True)
class RailwayCommitInfo:
    """배포 대상 커밋 정보 (모두 Optional — Railway payload 가 누락 가능)."""
    commit_sha: str | None
    commit_message: str | None
    repo_full_name: str | None


@dataclass(frozen=True)
class RailwayDeployEvent:
    """Railway deployment webhook 에서 파싱된 이벤트 (3-group nested)."""
    deployment_id: str
    status: str          # "FAILED" | "BUILD_FAILED"
    timestamp: str
    project: RailwayProjectInfo
    commit: RailwayCommitInfo
```

**필드 배분**:
- **Top-level (3 attrs)**: `deployment_id`, `status`, `timestamp` — 이벤트 본질
- **`project` (3 attrs)**: `project_id`, `project_name`, `environment_name` — 어디서 실패했나
- **`commit` (3 attrs)**: `commit_sha`, `commit_message`, `repo_full_name` — 무엇을 배포하려 했나

**pylint R0902 결과 예측**: 각 dataclass 모두 attrs ≤ 3 또는 ≤ 5 로 limit 7 이내 → **R0902 완전 제거**.

### 3-2. Parser 변경 (`src/railway_client/webhook.py`)

```python
def parse_railway_payload(body: dict) -> RailwayDeployEvent | None:
    if body.get("type") != "DEPLOY":
        return None
    status = body.get("status", "")
    if status not in RAILWAY_FAILURE_STATUSES:
        return None

    deployment = body.get("deployment") or {}
    deployment_id = deployment.get("id")
    if not deployment_id:
        logger.warning("parse_railway_payload: deployment.id 누락 — payload 무시")
        return None

    project_raw = body.get("project") or {}
    environment = body.get("environment") or {}
    commit_raw = deployment.get("meta") or {}

    project = RailwayProjectInfo(
        project_id=project_raw.get("id", ""),
        project_name=project_raw.get("name", ""),
        environment_name=environment.get("name", ""),
    )
    commit = RailwayCommitInfo(
        commit_sha=commit_raw.get("commitSha") or None,
        commit_message=commit_raw.get("commitMessage") or None,
        repo_full_name=commit_raw.get("repo") or None,
    )
    return RailwayDeployEvent(
        deployment_id=deployment_id,
        status=status,
        timestamp=body.get("timestamp", ""),
        project=project,
        commit=commit,
    )
```

**외부 API 불변**: 함수 시그니처 `parse_railway_payload(body: dict) -> RailwayDeployEvent | None` 그대로.

### 3-3. 접근 체인 변경 영향

| 기존 | 신규 | 파일 |
|------|------|------|
| `event.project_id` | `event.project.project_id` | `src/notifier/railway_issue.py` (2곳) |
| `event.project_name` | `event.project.project_name` | `src/notifier/railway_issue.py` (2곳) |
| `event.environment_name` | `event.project.environment_name` | `src/notifier/railway_issue.py` (1곳) |
| `event.commit_sha` | `event.commit.commit_sha` | `src/notifier/railway_issue.py` (3곳) |
| `event.commit_message` | `event.commit.commit_message` | `src/notifier/railway_issue.py` (1곳) |
| `event.repo_full_name` | `event.commit.repo_full_name` | `src/notifier/railway_issue.py` (1곳) |
| `event.deployment_id` | 변경 없음 | 4 파일 |
| `event.status` | 변경 없음 | 2 파일 |
| `event.timestamp` | 변경 없음 | 1 파일 |

`src/webhook/router.py:378, 380` 은 `event.deployment_id` 만 사용 → **수정 불필요**.

## 4. 불변 제약

- `parse_railway_payload(body: dict) -> RailwayDeployEvent | None` 시그니처 불변
- `create_deploy_failure_issue(*, github_token, repo_full_name, event, logs_tail)` 시그니처 불변
- Railway webhook 외부 payload 스키마 불변 (수신만 바뀜)
- DB 스키마 불변 (`RailwayDeployEvent` 는 메모리 dataclass, 영속화 대상 아님)
- REGISTRY / 점수 계산 / Gate engine 전부 무관

## 5. 테스트 영향 범위

### 5-1. `tests/test_railway_client.py`
- `test_parse_valid_build_failed`: `event.commit_sha` → `event.commit.commit_sha`, `event.repo_full_name` → `event.commit.repo_full_name`
- `test_parse_missing_optional_fields`: `event.project_name` → `event.project.project_name`, `event.commit_sha` → `event.commit.commit_sha`

### 5-2. `tests/test_railway_issue_notifier.py`
- `_EVENT` fixture 생성자 호출 전면 재작성 (평면 kwargs → nested dataclass)

```python
# BEFORE
_EVENT = RailwayDeployEvent(
    deployment_id="deploy-abc",
    project_id="proj-123",
    project_name="my-project",
    ...
)

# AFTER
_EVENT = RailwayDeployEvent(
    deployment_id="deploy-abc",
    status="BUILD_FAILED",
    timestamp="2026-04-20T10:00:00Z",
    project=RailwayProjectInfo(
        project_id="proj-123",
        project_name="my-project",
        environment_name="production",
    ),
    commit=RailwayCommitInfo(
        commit_sha="deadbeef1234567890abcdef",
        commit_message="feat: add feature",
        repo_full_name="owner/repo",
    ),
)
```

- `_build_issue_body` 테스트 4개는 본문 assertion 은 유지 (output 문자열 불변)
- `create_deploy_failure_issue` 테스트 3개는 `_EVENT` 재사용으로 자동 반영

### 5-3. `tests/test_railway_webhook.py`
- payload 구조 불변이라 **수정 불필요** (parser 가 자동 처리)

## 6. 범위 밖 (의도적 제외)

| 항목 | 제외 사유 | 권고 |
|------|----------|------|
| `RailwayLogInfo` 같은 별도 dataclass 분리 | 현재 로그는 파이프라인 외부에서 별도 문자열로 처리 (fetch_deployment_logs 반환값) | 현재 구조 유지 |
| Pydantic 모델 전환 | 런타임 검증 비용 증가 + 기존 dataclass 사용처 많음 | 별도 Phase (webhook 외 입력 검증 통합 시) |
| 마이그레이션 전용 변환 함수 추가 | 외부 API 시그니처 불변이므로 불필요 | 불필요 |

## 7. 자가 리뷰 체크리스트

- [x] Placeholder 없음 — 전체 섹션 완결
- [x] 내부 일관성 — parser 변경이 접근 체인 섹션과 일치
- [x] Scope 적절 — 5 파일 수정, 외부 API 불변
- [x] 모호성 없음 — 필드 배분 3+3+3 명시, pylint R0902 제거 목표 명확
- [x] 기존 Railway 플랜과의 관계 — 플랜 아카이브(2026-04-20) 는 그대로 유지, 본 리팩토링은 추가 Phase
- [x] 현재 pylint 10.00/10 유지 여부 — parser 함수 길이 증가로 pylint C0200 주의, 현재 37줄 → 50줄 내외 예상 (limit 50 이내)

## 8. 승인 요청

Phase-N+1 리팩토링 착수 GO/NO-GO:

1. ✅ 3-group nested 구조 (project / commit / top-level) 수용
2. ✅ `parse_railway_payload` 시그니처 불변 보장
3. ✅ 외부 webhook payload 스키마 불변 보장
4. ✅ 테스트 2 파일 (`test_railway_client.py`, `test_railway_issue_notifier.py`) fixture 재작성 수용

승인 후 본 스펙을 Task-by-Task 플랜(`docs/superpowers/plans/2026-04-21-railway-event-refactor.md`) 으로 변환해 TDD 순서로 구현한다. 예상 Task 7개 / ~1.5~2 시간.
