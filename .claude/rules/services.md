---
description: 서비스 계층 (집계·외부통합·tenant·2nd-LLM verifier·config·cli) 작업 시 적용되는 SCAManager 규칙 (path-scoped)
paths:
  - "src/services/**"
  - "src/verifier/**"
  - "src/config_manager/**"
  - "src/railway_client/**"
  - "src/mcp/**"
  - "src/cli/**"
  # `src/shared/**` 추가 (2026-08-01) — `claude_metrics.py` 는 background 세션 라우팅
  #    규칙의 소비자인데 **로드되는 규칙이 0개**였다(Grok `019fbd1e` 적발).
  - "src/shared/**"
---

# 서비스 계층 규칙

> 서비스 계층 = 라우트/파이프라인과 repository 사이의 비즈니스 로직 (집계 `dashboard_service`/`repo_insight_service`/`analytics_service`·외부 통합 `railway_client`·tenant `saas_service`·2nd-LLM `verifier`·config `config_manager`·cli). 아래는 **서비스 계층 고유 규칙** + cross-cutting 가드의 **타 rule 포인터**(중복 금지·정책 16 단일출처).

## 세션 · 동시성
- **서비스 함수 시그니처**: `fn(db: Session, *, arg1, ...)` keyword-only — 호출자가 연 `Session` 을 주입받는다 (서비스 내부에서 `SessionLocal()` 새로 열지 않음 — lazy-load 금지, 세션 종료 전 필요 값 추출).
- **`asyncio.gather()` 내 Session 공유 금지**: 동시 실행 코루틴은 각각 독립 `with SessionLocal() as db:` (identity map 오염·동시 commit 충돌 차단). cross-ref [`api.md`](api.md)·[`pipeline.md`](pipeline.md) §asyncio.gather.
- **시스템/background 서비스 세션 라우팅**: cron·merge_retry 등 세션 없는 컨텍스트는 `from src.database import WorkerSessionLocal as SessionLocal` alias (BYPASSRLS worker role). cross-ref [`db.md`](db.md) §WorkerSessionLocal.

## RLS · tenant (cross-ref db.md)
- **RLS 1차 안전망 (app-layer)**: `dashboard_service._apply_*_user_filter` + `security_alert_log_repo._apply_owner_filter` — 신규 집계/조회 함수는 동일 owner 필터 적용 의무. legacy(`user_id IS NULL`) 노출 방향은 테이블별 의도적 비대칭(0026 노출 vs 0027 strict). cross-ref [`db.md`](db.md) §RLS legacy 비대칭.
- 🔴 **`saas_service._RLS_MATRIX` bijection 동기화 의무**: alembic `ENABLE ROW LEVEL SECURITY` 테이블 집합 ↔ `_RLS_MATRIX` 양방향 일치 (`tests/unit/test_rls_matrix_completeness.py`). 신규 RLS 테이블 추가 시 매트릭스 동기화. `rls_coverage_summary(db)` = `pg_class.relforcerowsecurity` **실측**(정적 거짓안심 차단). cross-ref [`db.md`](db.md) §_RLS_MATRIX.

## 외부 통합 (cross-ref api.md)
- **외부 SDK timeout/aclose**: GitHub/Railway/OpenAI-verifier 호출은 `timeout` 명시 + sync I/O(PyGithub 등)는 `asyncio.to_thread` wrap + try/finally `aclose`. 신뢰 API = `shared/http_client.py` 싱글톤 / untrusted(discord·slack·n8n·custom) = `notifier/_http.py::build_safe_client`. cross-ref [`api.md`](api.md) §외부 SDK timeout.
- **배치 루프에서 소유권 토큰은 `claim_batch` 반환 직후 **값으로** 스냅샷한다 (2026-07-31 P1 — 실측 재현)**: `sessionmaker` 가 `expire_on_commit` 을 지정하지 않아(기본 True) **첫 행의 write-back commit 이 세션 전체를 만료**시킨다. 그래서 루프 안의 `row.claim_token` 은 rows 2..N 에서 **캡처가 아니라 DB 재조회**이고, 그 사이 다른 워커가 stale(>300s) 재클레임했다면 **남의 토큰**을 자기 것으로 착각한다. 결과: 이 워커가 남의 claim 을 해제 → 정당한 소유자의 `mark_terminal` 이 CAS 0행 매치로 거부 → **종결 결과 소실 + 행이 `pending` 으로 부활**(CAS 가 막으려던 실패 모드가 소유자 쪽으로 뒤집힘). 기본 batch=50 에서 **49/50 행 무방비**였다.
  - **계약**: `claim_tokens = {r.id: r.claim_token for r in claimed}` 를 루프 **진입 전**에 만들고, 모든 CAS write-back 에 그 값을 전달한다(`_process_single_retry(claim_token=...)` 포함 — 그 함수 내부 write-back 도 같은 축이다).
  - 🔴 **회귀 가드는 `SimpleNamespace` row · 단일 행 배치 · `MagicMock` db 로 쓰면 안 된다** — 셋 다 이 축을 **원리적으로 관측 불가**하다(ORM 만료 없음 / commit 경계 미통과 / identity map 없음). 실측: 기존 CAS 배선 테스트 6건이 결함 존재 상태에서 전부 green 이었다. **실 ORM · 2행 이상 배치 · 교차 세션 · 파일 SQLite** + `process_pending_retries` 를 실제로 호출할 것(`test_merge_retry_batch_token_snapshot.py`). 시나리오 재현만 하고 서비스 루프를 안 태우면 서비스 코드를 되돌려도 green 이다(실측).
  - **일반화**: commit 경계를 넘어 살아남아야 하는 값은 **ORM 속성이 아니라 지역 변수**에 담는다. `row.id`(PK)는 불변이라 안전하지만 가변 필드는 전부 재조회 대상이다.
  - **루프의 broad `except Exception` 은 시그니처 불일치도 삼킨다** (2026-07-31 실측): `_process_single_retry` 에 kwarg 를 추가하자, 그 함수를 **더 좁은 시그니처로 대체**하던 기존 테스트 fake 들이 `TypeError` 를 냈고 broad except 가 그것을 잡아 `_recover_and_release` 로 보내 **"행이 pending 으로 갔다"** 는 엉뚱한 실패로 보였다. 원인 진단에 시간이 걸린다. **신규 kwarg 추가 시 `grep -rn "_process_single_retry" tests/` 로 test double 전수 정렬 의무**(정책 16 공유 로직 전수 grep 의 test-double 판 · [[feedback-fixture-model-sync-discipline]]).
- **`merge_retry_service` SHA-bound 검증자 staleness 안전**: retry 경로는 `sha_drift` 검사(`head_sha != row.commit_sha → abandon`) + `merge_pr(expected_sha=row.commit_sha)` 로 검증자가 승인한 정확한 SHA 만 머지. `expected_sha` 바인딩 제거 금지(force-push 미검증 코드 머지 위험). cross-ref [`api.md`](api.md) §검증자 staleness.
- **`issue_registration_service`**: GitHub Issue 를 **먼저 생성**한 뒤 DB INSERT — `IntegrityError`(중복/TOCTOU)=`DUPLICATE:N` / **비-IntegrityError(`SQLAlchemyError`)=orphan ERROR 로깅(repo/number/url/key)+재전파**(services-001 #997). TTL 동기화 `_sync_state_if_stale` 예외는 `(httpx.HTTPError, KeyError, ValueError)` 흡수 — GitHub malformed 응답의 `resp.json()["state"]` 가 `GET /api/issues/*` 500 으로 전파되지 않도록(#1008).
- **`railway_client`**: GitHub payload None-able 키는 `(data.get(k) or {})` 정규화 + 토큰 인증 통과 후 비-dict JSON 바디는 `if not isinstance(body, dict): body = {}` 가드(telegram provider 대칭, #1008).

## verifier · config · 집계
- **`INSIGHT_DISABLED` kill-switch (인사이트 내러티브 비용 제어)**: `dashboard_service.insight_narrative` + `repo_insight_service.repo_insight_narrative` 진입부가 `is_disabled("INSIGHT")` 시 API 호출 없이 `status="disabled"` 응답을 즉시 반환(`feature_kill_switch` 패턴 — 2nd-LLM verifier 와 무관한 별도 kill-switch). AI 코드리뷰 kill-switch(`AI_REVIEW_DISABLED`)와는 대상 모델(Haiku vs Sonnet)·경로 모두 별개. 검증 절차: [`docs/runbooks/cost-controls.md`](../../docs/runbooks/cost-controls.md).
- **2nd-LLM verifier (`src/verifier/`)**: **fail-closed** — `merge_verifier.verifier_blocks_merge` 가드(should_verify + verify_merge_safety + 차단 시 PR 코멘트)는 `gate/engine._run_auto_merge` **단일출처**(자동·반자동 공유). `OPENAI_API_KEY` 미설정=완전 비활성(순수 opt-in·비용 0). 활성화 절차: [`docs/runbooks/merge-verifier.md`](../../docs/runbooks/merge-verifier.md). cross-ref [`api.md`](api.md) §2nd-LLM 검증자 가드.
- **`config_manager` 5-way sync**: RepoConfig 신규 필드 = ORM(`models/repo_config.py`)↔`RepoConfigData`↔`RepoConfigUpdate`↔`settings.html` 폼↔PRESETS 동기화 의무 — 누락 시 REST 업데이트가 해당 필드를 NULL 로 덮어씀. pre-commit `check-config-5way-sync` 훅은 **3-layer(ORM↔Data↔Update) Python 자동 검증만**, 폼·PRESETS 2-layer 는 HTML/JS 파싱 fragile 로 수동 검토(범위 외). cross-ref [`api.md`](api.md) §알림 채널 추가 체크리스트(ORM↔Data↔Update↔폼 4곳) + [`pipeline.md`](pipeline.md) §5-way 동기화(PRESETS 5번째).
- **N+1 배치**: 집계 함수 신규 추가 시 `dashboard_service._fetch_analyses_for_window`/`_group_analyses_by_repo` 배치 패턴 사용 — repo 별 개별 쿼리 루프 금지.
- **`cost_metrics_service`**: Anthropic 비용 집계 진입점(`user_cost_summary`) — `claude_api_cost_repo`(record + 집계) 위임 thin wrapper. `dashboard_kpi` 의 `monthly_cost` 카드(고정 30일 윈도우)가 소비 (C1 Phase 2/4, 0043 `claude_api_calls` 테이블). 검증 절차: [`docs/runbooks/cost-controls.md`](../../docs/runbooks/cost-controls.md).
- **메모리 캐시 상한 의무**: 서비스/클라이언트 모듈 레벨 캐시(dict)는 **상한 + 만료 evict** 패턴(`webhook/_helpers._store_secret`·`add_repo._store_user_repos` 미러). pre-auth 도달 가능 캐시는 특히 필수(무한 증가 DoS). 신규 캐시 도입 시 `tests/conftest.py` autouse 클리어 fixture 동반.

## 발신 메시지 i18n (cross-ref i18n.md)
- 🔴 `cron_service`·`analytics_service` 등 서비스가 알림을 발신/조립할 때 사용자 노출 문자열은 i18n — `tests/unit/notifier/test_no_hardcoded_korean_in_send_modules.py` AST 가드가 `src/services/{merge_retry,cron}` 포함 스캔. logger 메시지는 운영자용(i18n 대상 아님). cross-ref [`i18n.md`](i18n.md) §발신 경로.
