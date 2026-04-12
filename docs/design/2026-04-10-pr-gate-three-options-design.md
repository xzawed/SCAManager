# PR Gate 3-옵션 분리 재설계 — 설계 문서

**날짜:** 2026-04-10  
**상태:** 구현 완료  
**관련 마이그레이션:** `0010_pr_gate_three_options.py`

---

## 배경 및 동기

기존 `gate_mode` (disabled/auto/semi-auto) 하나에 세 가지 책임이 뭉쳐 있었다:

- PR에 코드리뷰 댓글 발송 여부
- GitHub APPROVE / REQUEST_CHANGES 판정 여부
- 자동 Merge 실행 여부

이 결합로 인해 "코드리뷰 댓글은 달되 자동 Approve는 하지 않겠다"거나, "Approve 없이 점수만으로 자동 Merge 하겠다"는 조합이 불가능했다.

---

## 설계 결정: 3-옵션 완전 독립

| 옵션 | 필드 | 타입 | 기본값 | 역할 |
|------|------|------|--------|------|
| **Review Comment** | `pr_review_comment` | bool | `True` | 분석 완료 시 PR에 AI 코드리뷰 댓글 발송 |
| **Approve** | `approve_mode` | str | `"disabled"` | 점수 기반 GitHub APPROVE / REQUEST_CHANGES |
| **Auto Merge** | `auto_merge` + `merge_threshold` | bool + int | `False` + `75` | 점수 ≥ 임계값이면 squash merge |

세 옵션은 완전히 독립적이므로 어떤 조합이든 가능하다. 예:
- `pr_review_comment=True`, `approve_mode="disabled"`, `auto_merge=False` → 댓글만
- `pr_review_comment=False`, `approve_mode="auto"`, `auto_merge=True` → Approve + Merge만
- `pr_review_comment=True`, `approve_mode="semi-auto"`, `auto_merge=True` → 전체 활성화

---

## 아키텍처 변경

### DB 마이그레이션 (`0010`)

```sql
-- rename
ALTER COLUMN gate_mode RENAME TO approve_mode;
ALTER COLUMN auto_approve_threshold RENAME TO approve_threshold;
ALTER COLUMN auto_reject_threshold RENAME TO reject_threshold;
-- add
ADD COLUMN pr_review_comment BOOLEAN NOT NULL DEFAULT TRUE;
ADD COLUMN merge_threshold INTEGER NOT NULL DEFAULT 75;
```

### `run_gate_check()` 시그니처 변경

```python
# 이전
async def run_gate_check(event, data, result, db)

# 이후
async def run_gate_check(
    repo_name: str,
    pr_number: int | None,
    analysis_id: int,
    result: dict,          # score·grade 포함
    github_token: str,
    db: Session,
) -> None
```

- `telegram_bot_token` 파라미터 제거 → `settings.telegram_bot_token` 직접 사용
- `score_result` 파라미터 제거 → `result["score"]`에서 추출
- `pr_number=None`이면 모든 PR 액션 즉시 스킵

### `_build_result_dict()` 확장

`src/worker/pipeline.py`의 `_build_result_dict()`가 이제 `score`·`grade` 필드를 포함한다.  
gate engine과 telegram callback 양쪽에서 저장된 result dict만으로 점수를 추출한다.

### `post_pr_comment_from_result()` 신규 함수

`src/notifier/github_comment.py`에 추가:

```python
async def post_pr_comment_from_result(
    github_token: str,
    repo_name: str,
    pr_number: int,
    result: dict,
) -> None
```

`AiReviewResult` 객체 없이 저장된 result dict만으로 PR 코드리뷰 댓글을 게시한다.  
gate engine이 이 함수를 사용하므로 pipeline에서 `post_pr_comment` 제거가 가능해졌다.

---

## 데이터 흐름

```
run_analysis_pipeline()
  → _build_result_dict()  ← score·grade 포함
  → DB 저장
  → run_gate_check(repo_name, pr_number, analysis_id, result, github_token, db)
      ┌─ [pr_review_comment=True]  → post_pr_comment_from_result()
      ├─ [approve_mode="auto"]     → score 비교 → APPROVE or REQUEST_CHANGES
      ├─ [approve_mode="semi-auto"]→ send_gate_request() (Telegram 인라인 키보드)
      └─ [auto_merge=True, score ≥ merge_threshold] → merge_pr() (approve_mode 무관)

POST /api/webhook/telegram (semi-auto 콜백)
  → post_github_review() + GateDecision 저장
  → result["score"] ≥ merge_threshold → merge_pr()  (approve_mode 무관)
```

---

## 영향 파일 목록

| 파일 | 변경 내용 |
|------|----------|
| `alembic/versions/0010_pr_gate_three_options.py` | 신규 마이그레이션 |
| `src/models/repo_config.py` | 필드 rename + 2개 신규 컬럼 |
| `src/config_manager/manager.py` | `RepoConfigData` 동기화 |
| `src/gate/engine.py` | 전면 재작성 (3-섹션 독립 로직) |
| `src/notifier/github_comment.py` | `post_pr_comment_from_result()` 추가 |
| `src/worker/pipeline.py` | `post_pr_comment` 제거, result dict에 score·grade 추가 |
| `src/webhook/router.py` | `handle_gate_callback` auto_merge 독립 처리 |
| `src/api/repos.py` | `RepoConfigUpdate` 필드 동기화 |
| `src/ui/router.py` | 설정 저장 필드명 업데이트 |
| `src/templates/settings.html` | 4-카드 레이아웃으로 재구성 |
| `tests/test_gate_engine.py` | 전면 재작성 (16개 테스트) |
| `tests/test_pipeline.py` | mock_deps 업데이트, 2개 신규 테스트 |
| `tests/test_config_manager.py` | 신규 필드 반영 |
| `tests/test_api_repos.py` | 필드명 업데이트 |
| `tests/test_repo_config_model.py` | 필드명 업데이트 |
| `tests/test_webhook_telegram.py` | result dict + merge_threshold 반영 |

---

## 테스트 커버리지

구현 완료 기준: 전체 단위 테스트 321개 통과.

신규 테스트 케이스 (test_gate_engine.py):
- `pr_review_comment=True` → `post_pr_comment` 호출
- `pr_review_comment=False` → `post_pr_comment` 미호출
- `approve_mode="auto"`, 고점수 → APPROVE
- `approve_mode="auto"`, 저점수 → REQUEST_CHANGES
- `approve_mode="auto"`, 중간점수 → skip (neither)
- `approve_mode="semi-auto"` → `send_gate_request` 호출
- `approve_mode="disabled"` → review comment 없음
- `auto_merge=True`, `score ≥ threshold` → `merge_pr` 호출 (approve_mode=disabled에서도)
- `auto_merge=True`, `score < threshold` → `merge_pr` 미호출
- `pr_number=None` → 모든 액션 스킵
