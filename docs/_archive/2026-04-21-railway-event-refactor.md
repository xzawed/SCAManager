> ⚠️ **ARCHIVED — 2026-04-27**: 이 문서는 해당 시점에 완료된 작업을 기록한 것으로, 현재 코드베이스와 일치하지 않을 수 있습니다. 현재 상태는 [docs/STATE.md](../STATE.md)를 참조하세요.

# RailwayDeployEvent sub-dataclass 분리 Implementation Plan

> **Status:** ✅ **완료** (2026-04-22). STATE.md 그룹 12 참조.
>
> **실행 환경**: `make test` 정상 실행 환경. pytest 호출 시 `.env` stash + env unset 래퍼 사용.

**Goal:** `RailwayDeployEvent` 평면 9-필드 구조를 3-그룹 nested(project·commit·top-level) 로 재구조화해 pylint R0902 informational 경고를 선제 제거. 외부 API(`parse_railway_payload`, `create_deploy_failure_issue`) 시그니처 불변, DB·점수 계산·Gate 엔진 무관.

**Architecture:** `src/railway_client/models.py` 에 `RailwayProjectInfo` + `RailwayCommitInfo` sub-dataclass 추가 후 `RailwayDeployEvent` 를 nested 구조로 재작성. `src/railway_client/webhook.py::parse_railway_payload` 는 sub-dataclass 생성자 호출로 내부만 변경. `src/notifier/railway_issue.py` 는 `event.project_id` → `event.project.project_id` 등 접근 체인 11곳 업데이트. 테스트 2 파일 fixture 재작성.

---

## File Map

| 상태 | 파일 | 역할 |
|------|------|------|
| 수정 | `src/railway_client/models.py` | `RailwayProjectInfo` + `RailwayCommitInfo` 신규 + `RailwayDeployEvent` nested 재작성 |
| 수정 | `src/railway_client/webhook.py` | `parse_railway_payload` 내부를 sub-dataclass 생성자로 변경 |
| 수정 | `src/notifier/railway_issue.py` | `_build_issue_body` + `create_deploy_failure_issue` 의 접근 체인 11곳 업데이트 |
| 수정 | `tests/test_railway_client.py` | 평면 assertion → nested 접근 (4곳) |
| 수정 | `tests/test_railway_issue_notifier.py` | `_EVENT` fixture 재작성 (nested 생성자) |
| (불변) | `src/webhook/router.py` | `event.deployment_id` 만 사용 — 접근 변경 없음 |
| (불변) | `tests/test_railway_webhook.py` | parser 가 자동 처리 — payload 구조 불변 |
| (불변) | `alembic/versions/0012_add_railway_fields.py` | DB 스키마 무관 |
| 수정 | `CLAUDE.md` | "파이프라인 / 비즈니스 로직" 섹션에 nested 구조 1줄 주석 |
| 수정 | `docs/STATE.md` | 그룹 12 항목 추가 |

---

## Task 1: 테스트 선작성 (TDD Red)

**Files:**
- Modify: `tests/test_railway_client.py`
- Modify: `tests/test_railway_issue_notifier.py`

백엔드 불변 강조 — `parse_railway_payload` 시그니처 · POST 핸들러 · Alembic 마이그레이션 · Gate 엔진 전부 그대로.

- [ ] **Step 1: `tests/test_railway_client.py` — nested 접근 assertion 으로 교체**

기존 `test_parse_valid_build_failed` 를 아래로 교체:

```python
def test_parse_valid_build_failed():
    """BUILD_FAILED 이벤트는 nested RailwayDeployEvent 를 반환해야 한다."""
    event = parse_railway_payload(_VALID_PAYLOAD)
    assert event is not None
    assert event.deployment_id == "deploy-abc123"
    assert event.status == "BUILD_FAILED"
    assert event.project.project_id == "proj-123"
    assert event.project.project_name == "my-project"
    assert event.project.environment_name == "production"
    assert event.commit.commit_sha == "deadbeef1234567890abcdef"
    assert event.commit.repo_full_name == "owner/repo"
```

`test_parse_missing_optional_fields` 를 아래로 교체:

```python
def test_parse_missing_optional_fields():
    """project/commit 정보 없어도 파싱은 성공해야 한다."""
    payload = {
        "type": "DEPLOY",
        "status": "FAILED",
        "timestamp": "2026-04-20T10:00:00Z",
        "deployment": {"id": "deploy-xyz"},
    }
    event = parse_railway_payload(payload)
    assert event is not None
    assert event.project.project_name == ""
    assert event.commit.commit_sha is None
```

- [ ] **Step 2: `tests/test_railway_issue_notifier.py` — `_EVENT` fixture 재작성**

파일 상단 import 에 추가:

```python
from src.railway_client.models import (
    RailwayDeployEvent,
    RailwayProjectInfo,
    RailwayCommitInfo,
)
```

기존 `_EVENT = RailwayDeployEvent(...)` 블록을 교체:

```python
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

- [ ] **Step 3: Red 확인 — ImportError (RailwayProjectInfo 미존재)**

```bash
run_pytest tests/test_railway_client.py tests/test_railway_issue_notifier.py -v --tb=line
```

기대: `ImportError: cannot import name 'RailwayProjectInfo'` 다수 실패.

- [ ] **Step 4: 커밋**

```bash
git add tests/test_railway_client.py tests/test_railway_issue_notifier.py
git commit -m "test(railway): RailwayDeployEvent nested 구조로 테스트 선작성 (Red)

RailwayProjectInfo + RailwayCommitInfo sub-dataclass import 가정한
nested 접근 assertion. 모듈 미존재로 ImportError (Red)."
```

---

## Task 2: `models.py` nested 재구조화

**Files:**
- Modify: `src/railway_client/models.py`

기존 9-필드 평면 dataclass 를 3-그룹 nested 로 재작성.

- [ ] **Step 1: `src/railway_client/models.py` 전면 교체**

```python
"""Railway webhook 이벤트 데이터 모델 (3-그룹 nested)."""
from dataclasses import dataclass

RAILWAY_FAILURE_STATUSES: frozenset = frozenset({"FAILED", "BUILD_FAILED"})


@dataclass(frozen=True)
class RailwayProjectInfo:
    """Railway 프로젝트 식별 정보 (어디서 실패했나)."""
    project_id: str
    project_name: str
    environment_name: str


@dataclass(frozen=True)
class RailwayCommitInfo:
    """배포 대상 커밋 정보 (무엇을 배포하려 했나). 모두 Optional."""
    commit_sha: str | None
    commit_message: str | None
    repo_full_name: str | None


@dataclass(frozen=True)
class RailwayDeployEvent:
    """Railway deployment webhook 이벤트 (3-그룹 nested).

    Top-level(3): deployment_id · status · timestamp — 이벤트 본질
    project(3):   project_id · project_name · environment_name
    commit(3):    commit_sha · commit_message · repo_full_name
    """
    deployment_id: str
    status: str
    timestamp: str
    project: RailwayProjectInfo
    commit: RailwayCommitInfo
```

- [ ] **Step 2: Task 1 테스트 일부 GREEN 확인 (_EVENT fixture 생성은 통과)**

```bash
run_pytest tests/test_railway_issue_notifier.py::test_build_issue_body_contains_marker -v
```

기대: PASS (단 `_build_issue_body` 가 `event.project_name` 접근 시 AttributeError — Task 3 에서 해소).

- [ ] **Step 3: 커밋**

```bash
git add src/railway_client/models.py
git commit -m "refactor(railway): RailwayDeployEvent 를 3-그룹 nested dataclass 로 재구조화

RailwayProjectInfo(3) + RailwayCommitInfo(3) + top-level(3) 분리.
pylint R0902 informational (9/7) 제거. 외부 import 경로는 모두
models.py 유지."
```

---

## Task 3: `webhook.py` parser 업데이트

**Files:**
- Modify: `src/railway_client/webhook.py`

`parse_railway_payload` 시그니처 불변, 내부만 sub-dataclass 생성자 호출로 변경.

- [ ] **Step 1: `src/railway_client/webhook.py` 전면 교체**

```python
"""Railway webhook payload 파싱."""
import logging
from src.railway_client.models import (
    RAILWAY_FAILURE_STATUSES,
    RailwayCommitInfo,
    RailwayDeployEvent,
    RailwayProjectInfo,
)

logger = logging.getLogger(__name__)


def parse_railway_payload(body: dict) -> RailwayDeployEvent | None:
    """Railway webhook JSON 을 RailwayDeployEvent 로 파싱.

    Returns:
        RailwayDeployEvent — 빌드 실패 이벤트인 경우 (nested 구조).
        None — 빌드 성공, 비DEPLOY 타입, 필수 필드 누락인 경우.
    """
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

    return RailwayDeployEvent(
        deployment_id=deployment_id,
        status=status,
        timestamp=body.get("timestamp", ""),
        project=RailwayProjectInfo(
            project_id=project_raw.get("id", ""),
            project_name=project_raw.get("name", ""),
            environment_name=environment.get("name", ""),
        ),
        commit=RailwayCommitInfo(
            commit_sha=commit_raw.get("commitSha") or None,
            commit_message=commit_raw.get("commitMessage") or None,
            repo_full_name=commit_raw.get("repo") or None,
        ),
    )
```

- [ ] **Step 2: `test_railway_client.py` 전체 PASS 확인**

```bash
run_pytest tests/test_railway_client.py -v
```

기대: 파싱 관련 6개 테스트 전부 PASS.

- [ ] **Step 3: 커밋**

```bash
git add src/railway_client/webhook.py
git commit -m "refactor(railway): parse_railway_payload 를 nested 생성자로 전환

시그니처 불변. sub-dataclass RailwayProjectInfo/RailwayCommitInfo
를 명시 생성해 RailwayDeployEvent 에 주입."
```

---

## Task 4: `notifier/railway_issue.py` 접근 체인 업데이트

**Files:**
- Modify: `src/notifier/railway_issue.py`

11곳 접근 경로 변경. 출력 문자열(Issue 본문) 은 불변 — 기존 테스트 assertion 통과.

- [ ] **Step 1: `_build_issue_body` 내부 접근 변경**

| 기존 | 신규 |
|------|------|
| `event.commit_sha[:7]` | `event.commit.commit_sha[:7]` |
| `event.repo_full_name` | `event.commit.repo_full_name` |
| `event.commit_sha` | `event.commit.commit_sha` |
| `event.commit_message` | `event.commit.commit_message` |
| `event.project_name` | `event.project.project_name` |
| `event.project_id` | `event.project.project_id` |
| `event.environment_name` | `event.project.environment_name` |
| `event.status` | 불변 |
| `event.timestamp` | 불변 |
| `event.deployment_id` | 불변 |

코드 예시 (일부):
```python
sha_short = event.commit.commit_sha[:7] if event.commit.commit_sha else "unknown"
commit_url = (
    f"https://github.com/{event.commit.repo_full_name}/commit/{event.commit.commit_sha}"
    if event.commit.repo_full_name and event.commit.commit_sha
    else "#"
)
commit_line = event.commit.commit_message.splitlines()[0] if event.commit.commit_message else ""
...
f"- **Project**: {event.project.project_name} (`{event.project.project_id}`)",
f"- **Environment**: {event.project.environment_name}",
f"- **Status**: {event.status}",
...
f'<a href="https://railway.app/project/{event.project.project_id}">Railway 대시보드 열기</a></sub>',
```

- [ ] **Step 2: `create_deploy_failure_issue` 내부 접근 변경**

```python
title = f"[SCAManager] Railway 빌드 실패: {event.project.project_name} ({event.status})"
```

`event.deployment_id` 사용 3곳(marker/search query/log) 은 불변.

- [ ] **Step 3: 테스트 전체 PASS 확인**

```bash
run_pytest tests/test_railway_issue_notifier.py -v
```

기대: 7개 PASS (기존 fixture 재작성이 이미 적용됐으므로).

- [ ] **Step 4: 커밋**

```bash
git add src/notifier/railway_issue.py
git commit -m "refactor(notifier): railway_issue 접근 체인을 nested 로 업데이트 (11곳)

event.{project_id,project_name,environment_name} → event.project.*
event.{commit_sha,commit_message,repo_full_name} → event.commit.*
event.{deployment_id,status,timestamp} 불변. Issue 본문 출력 문자열
및 GitHub Issue 생성 로직 모두 동일."
```

---

## Task 5: 전체 회귀 + lint

**Files:** (검사만)

- [ ] **Step 1: 전체 테스트 회귀**

```bash
run_pytest tests/ -q
```

기대: 1126 passed, 0 failed.

- [ ] **Step 2: lint 게이트**

```bash
python -m pylint src/railway_client/ src/notifier/railway_issue.py
python -m flake8 src/
python -m bandit -r src/ -ll -q
```

기대:
- pylint: R0902 경고 **0건** (기존 `too-many-instance-attributes 9/7` 제거 확인)
- pylint 전체 점수 10.00/10 유지
- flake8: 0건
- bandit HIGH: 0건

- [ ] **Step 3: E2E 스모크**

```bash
run_pytest e2e/test_settings.py::test_settings_page_loads -q
```

기대: 1 passed (Railway 경로와 무관하지만 import 체인 검증).

---

## Task 6: 문서 갱신

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/STATE.md`

- [ ] **Step 1: `CLAUDE.md` 의 "파이프라인 / 비즈니스 로직" 섹션에 주석 추가**

기존 항목 중 Railway 관련 위치에 1줄 추가:

```markdown
- **RailwayDeployEvent nested 구조**: `RailwayDeployEvent` 는 3-그룹 nested dataclass — `event.project.project_id`, `event.commit.commit_sha` 등 sub-dataclass 경로로 접근. 평면(`event.project_id`) 접근은 2026-04-21 이후 제거됨. 신규 필드 추가 시 `RailwayProjectInfo` 또는 `RailwayCommitInfo` 에 삽입.
```

- [ ] **Step 2: `docs/STATE.md` 그룹 12 추가**

그룹 11 블록 아래에 추가:

```markdown
### 그룹 12 — RailwayDeployEvent sub-dataclass 리팩토링 (2026-04-21)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| models.py 재구조화 | RailwayProjectInfo(3) + RailwayCommitInfo(3) + top-level(3) nested dataclass | — |
| parser 내부 변경 | parse_railway_payload 시그니처 불변, sub-dataclass 생성자 호출로 내부만 전환 | — |
| notifier 접근 체인 | railway_issue.py 11곳 nested 접근으로 업데이트 (출력 문자열 불변) | — |
| 테스트 fixture 재작성 | test_railway_client.py(4곳) + test_railway_issue_notifier.py(_EVENT fixture) | — |
| pylint R0902 제거 | 9/7 informational 경고 제거 → sub-dataclass 각 ≤3 attrs | — |
| 외부 API 불변 | parse_railway_payload · create_deploy_failure_issue 시그니처 · Webhook payload 스키마 · DB 전부 그대로 | — |
```

- [ ] **Step 3: 커밋**

```bash
git add CLAUDE.md docs/STATE.md
git commit -m "docs: RailwayDeployEvent nested 리팩토링 — CLAUDE.md + STATE.md 갱신

CLAUDE.md 에 nested 접근 규약 1줄 추가. STATE.md 그룹 12 항목
추가. 테스트 수치 1126 유지 (신규 테스트 증가 없음)."
```

---

## Task 7: push + 최종 검증

**Files:** (push + 검증만)

- [ ] **Step 1: git push**

```bash
git push origin main
```

- [ ] **Step 2: Railway 배포 로그 확인** (선택)

Railway 대시보드에서 새 배포가 트리거됐는지 + `src/railway_client/models.py` import 체인 에러 없는지. 실제 Railway webhook 수신 시 기존 payload 스키마 유지로 파싱 정상 동작 기대.

- [ ] **Step 3: 최종 수치 확인**

```bash
run_pytest tests/ -q                # 1126 passed
python -m pylint src/               # 10.00/10 유지
python -m pytest e2e/ -q            # 49 passed, 4 warnings
```

---

## Verification (통합 체크리스트)

1. `RailwayProjectInfo` / `RailwayCommitInfo` / `RailwayDeployEvent` 3개 dataclass 전부 `@dataclass(frozen=True)` 유지
2. `parse_railway_payload` 시그니처 `(body: dict) -> RailwayDeployEvent | None` 불변
3. `create_deploy_failure_issue` 시그니처 keyword-only 불변
4. `pylint src/railway_client/` 출력에 `R0902` 0건
5. Railway webhook 외부 payload 예시 그대로 파싱 가능 (기존 테스트 6개 PASS)
6. Issue 본문 출력(`_build_issue_body`) 이 기존 테스트 4개 assertion 과 완전 일치

---

## Out of Scope

스펙 §6 에서 제외한 항목:

| 항목 | 제외 사유 |
|------|----------|
| `RailwayLogInfo` 별도 dataclass | 로그는 파이프라인 외부 문자열로 전달 |
| Pydantic 전환 | 런타임 검증 비용 + 사용처 많음. 별도 Phase |
| DB 테이블 신설 | `RailwayDeployEvent` 는 메모리 dataclass, 영속화 대상 아님 |

이 플랜은 단일 기술부채 해소(pylint R0902 선제 제거) + 가독성 향상 목적이며, **외부 API·DB·점수·Gate 엔진·웹훅 payload 모두 불변**. 예상 Task 7개, 예상 소요 1.5~2 시간.
