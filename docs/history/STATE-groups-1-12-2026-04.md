# STATE.md 초기 이력 아카이브 (그룹 1~12, 2026-04-05 ~ 04-22)

> [docs/STATE.md](../STATE.md) 에서 분리된 초기 Phase 이력 (2026-04-24 축약).
> 원본 그대로 보존 — 내용 변경 없음. STATE.md 의 축약 표가 본 파일로 링크합니다.

---

## 작업 이력 (최신 → 과거)

### 그룹 12 — RailwayDeployEvent sub-dataclass 리팩토링 (2026-04-22)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| models.py 재구조화 | `RailwayProjectInfo`(3) + `RailwayCommitInfo`(3) + top-level(3) nested dataclass — pylint R0902 informational (9/7) 제거 | — |
| parser 내부 변경 | `parse_railway_payload` 시그니처 불변, sub-dataclass 생성자 호출로 내부만 전환 | — |
| notifier 접근 체인 | `railway_issue.py` 11곳 nested 접근(`event.project.*`/`event.commit.*`)으로 업데이트 (출력 문자열 불변) | — |
| 테스트 fixture 재작성 | `test_railway_client.py`(2곳) + `test_railway_issue_notifier.py`(`_EVENT` fixture nested 재작성) | — |
| 외부 API 불변 | `parse_railway_payload` · `create_deploy_failure_issue` 시그니처 · Webhook payload 스키마 · DB 전부 그대로 | — |

### 그룹 11 — 5라운드 다중 에이전트 합의 품질 감사 (2026-04-21)

| 라운드 | 렌즈 | 점수 | 비고 |
|-------|------|------|------|
| R1 | 정상성 | 20/20 | 1126 passed, 0 failed, 326.88s |
| R2 | 커버리지 | 15/20 | pytest-cov 설치 불가(DNS 제약), STATE.md 96.2% 참조. 절차적 페널티 -5 |
| R3 | 결정성·격리성 | 20/20 | 3회 반복 + 역순 모두 1126 passed. CoV 3.5%. Agent B·C 합의 |
| R4 | 보안·Lint | 20/20 | pylint 10.00 / flake8 0 / bandit HIGH 0. LOW 7건 전부 false positive |
| R5 | 통합·E2E | 20/20 | 49 passed, 38.72s. Settings 재설계 E2E 커버리지 실효적 검증 |
| **합계** | **A 등급** | **95/100** | 3 에이전트 합의, ±3 초과 편차 0건 |

주요 권고 (차기 Phase 반영): `requirements-dev.txt` 에 pytest-cov 추가, `test_db_result_stores_source_pr` 14.57s 조사, `RailwayDeployEvent` sub-dataclass 분리, PyGithub `auth=` 마이그레이션.

**후속 해소 (동일일 2026-04-21)** — 3 에이전트(P/Q/R) 병렬 회귀 조사 → 근본 원인 확정 + 테스트 3파일 수정:
- `_run_static_analysis` mock 누락 (pipeline 7건 +200% 회귀 공통 원인) — `mock_deps` fixture + `test_pipeline_pr_regate.py` 시나리오 3개 모두 mock 추가
- `patch("src.notifier.n8n.notify_n8n_issue")` 경로 오류 (webhook_issues BackgroundTask DNS 블로킹) — `src.webhook.router.notify_n8n_issue` 로 변경
- Quick Win 2건 동시 반영: `pytest-cov>=5.0.0` 추가, `asyncio_default_fixture_loop_scope = function` 설정

**측정 효과**: 전체 pytest 시간 **326.88s → 70.81s (78% 단축)**. 1126 passed 유지, Production 코드 변경 0.

상세: [docs/reports/2026-04-21-quality-audit-round5.md](reports/2026-04-21-quality-audit-round5.md) 의 `Follow-up` 섹션

**잔여 권고 해소 (동일일 2026-04-21, 3건 연속)**:
- **#8** `e2e/conftest.py` `_ALEMBIC_HEAD` 자동 추출 — DAG 파싱으로 교체, 신규 마이그레이션 추가 시 수동 수정 불필요
- **#9** `tests/test_static_analyzer.py` → `tests/integration/` 이동 + `pytest.ini markers.slow` 선언 + `integration/conftest.py` 자동 마킹 (37 slow / 1089 fast / 총 1126)
- **#6** PyGithub `login_or_token` → `Auth.Token` 마이그레이션 (src/github_client/diff.py) — E2E warnings **41 → 4** (37건 제거)

**후속 해소 (2026-04-22)**:
- **#5** `RailwayDeployEvent` sub-dataclass 분리 — 그룹 12 참조. 3-그룹 nested(`RailwayProjectInfo`/`RailwayCommitInfo`/top-level) 로 재구조화 완료. pylint R0902 informational 제거, 외부 API 불변.

### 그룹 10 — Phase D.1 cppcheck 도구 추가 (2026-04-21)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| 단위 테스트 선작성 (TDD Red) | supports(c/cpp/other)·is_enabled binary·XML 파싱 엣지케이스·subprocess timeout/OSError/ParseError | +14 |
| `_CppCheckAnalyzer` 구현 | Analyzer Protocol · XML v2 stderr 파싱 · `--enable=warning,style,performance,portability` · category='code_quality' · `_parse_cppcheck_xml` 분리(mock 없이 검증 가능) | — |
| Registry 등록 검증 | `_register_cppcheck_analyzers()` 명시 호출 후 REGISTRY 확인 + 속성(name/category/SUPPORTED_LANGUAGES) | +2 |
| nixpacks.toml aptPkgs | cppcheck 바이너리를 Railway 배포 이미지에 포함 (+30MB, Docker 전환 불필요) | — |
| 백엔드 불변 | Analyzer Protocol · REGISTRY · `analyze_file()` 로직 · `AnalysisIssue` · `calculator.py` · `language.py` 전부 그대로 | — |

### 그룹 9 — Settings 페이지 재설계 (2026-04-21)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| 스모크 테스트 3종 (TDD Red) | form 필드 16개 보존 · railway_deploy_alerts toggle-switch · 프리셋 `<details>` + 신규 JS 헬퍼 3종 | +3 |
| PR 카드 재편 (①) | 헤더 '⚡ PR 동작' → '📋 PR 들어왔을 때', auto_merge + merge_threshold 를 Push 카드에서 이동 | — |
| 이벤트 후 피드백 카드 통합 (②) | commit_comment / create_issue / railway_deploy_alerts 3종을 트리거별 소제목(Push 이후 / 점수 미달 시 / Railway 빌드 실패 시) 그룹핑 + raw checkbox → toggle-switch 통일 | — |
| 시스템 & 토큰 카드 통합 (⑤) | CLI Hook + Webhook 재등록 + Railway API 토큰(.masked-field + 👁️) + Railway Webhook URL 통합. 메인 `<form id="settingsForm">` + `form="settingsForm"` 바깥 필드 바인딩 | — |
| 위험 구역 카드 ⑥ 분리 | 리포 삭제 `<details>` 를 독립 카드(빨간 그라디언트)로 최하단 분리 | — |
| 프리셋 P1 diff 미리보기 | onPresetToggle 재정의 + renderPresetDiff(name) 신규 — 현재값 vs 프리셋값 9 필드 diff 테이블, 변경 필드는 var(--accent) 색상 · 불변 필드는 opacity:.45 | — |
| 프리셋 P2 적용 하이라이트 | flashPresetChanges(changedFields) 신규 + @keyframes preset-flash 2.5s 애니메이션 (box-shadow glow + background fade) | — |
| 저장 오류 UX | ?save_error=1 쿼리 감지 시 .advanced-details.open = true 자동 펼침 (문제 필드 접근성) | — |
| 백엔드 불변 | ORM·RepoConfigData·POST 핸들러·PRESETS 9개 필드·JS 헬퍼 5종 시그니처 전부 불변 | — |
| E2E 자동 검증 | 8단계 Verification 자동화 — 6카드·P1 diff·P2 하이라이트·mask-toggle·save_error 아코디언·auto_merge 위치·위험구역 분리 + 기존 3개 preset 적용 방식 업데이트 | E2E +11 (38→49) |

### 그룹 8 — 5-Round 감사 후속 테스트 보강 (2026-04-21)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| _notify_merge_failure 커버리지 | Telegram HTTPError 예외·skip 경로 고정 + caplog.at_level 안정화 | +2 |
| save_gate_decision UPDATE 분기 | upsert 재사용 경로 + SQLAlchemy 2.x 호환 + 교차 세션 count | +1 |
| _regate_pr_if_needed rollback | SQLAlchemyError 시 rollback + gate skip + 오류 로그 | +1 |
| _save_and_gate TOCTOU 감지 | 동시 삽입 감지 경로 고정 (신규 test_pipeline_save_and_gate.py) | +1 |
| CLAUDE.md HMAC 주석 정정 | [:16] → [:32] (128-bit) 문서 오기 수정 | — |

### 그룹 7 — Railway 배포 실패 → GitHub Issue 자동 등록 (2026-04-20)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| ORM 필드 추가 | `RepoConfig`에 `railway_deploy_alerts`/`railway_webhook_token`/`railway_api_token` + Alembic 0012 | +2 |
| railway_client 패키지 | `RailwayDeployEvent` dataclass + `parse_railway_payload()` + `fetch_deployment_logs()` | +9 |
| railway_issue notifier | `create_deploy_failure_issue()` — Search API dedup + Issue 생성 | +7 |
| Webhook 엔드포인트 | `POST /webhooks/railway/{token}` + BackgroundTask 핸들러 | +5 |
| Settings UI | 카드 ⑤ Railway 알림 + PRESETS 3개 블록 + GET/POST 핸들러 | +3 (RepoConfigData/API) |

### 그룹 6 — UI 개선 (2026-04-19)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| overview 최근 점수 제거 | "최근 점수" 컬럼 제거 → `리포지토리\|분석\|평균 점수\|등급` 4컬럼 | +2 |
| 등급 평균 기반 전환 | `calculate_grade(avg_score)` — 최신 분석 grade 아닌 평균 점수 기반 | — |
| `_grade` 공개화 | `calculate_grade(score)` 공개 함수 (ui/router.py 재사용) | — |
| DB 쿼리 최적화 | `latest_id_subq`/`latest_map` 배치 조회 제거 (쿼리 1개 감소) | — |

### 그룹 5 — 구조적 코드품질 전면 개선 (2026-04-19)

| 작업 | 주요 내용 |
|------|----------|
| 순환 import 해소 | AnalysisIssue를 registry.py로 이동 — static.py↔tools/*.py 순환 제거 |
| pylint 10.00 달성 | dispatch dict(language.py), _AnalysisSaveParams, _select_guide_modes 추출 |
| 하드코딩 제거 | constants.py에 16개 상수 추가 (AI 점수 범위·알림 한도·캐시 TTL·타임아웃) |
| notifier 공통화 | _common.py 신설 — 6개 알림 모듈의 이슈 수집·절단 로직 통합 |
| GateDecision upsert | save_gate_decision() — 재시도 시 중복 INSERT 방지 |
| webhook secret 캐시 | _get_webhook_secret() — DB 조회 5분 TTL 캐시 |
| 테스트 격리 | conftest.py autouse fixture — _webhook_secret_cache 테스트 간 클리어 |

### 그룹 4 — 다언어 AI 리뷰 + 정적분석 확장 (Phase 0~C, 2026-04-19)

| Phase | 주요 내용 | 테스트 누계 |
|-------|----------|-----------|
| Phase 0 | language.py(50언어) + review_guides(Tier1×10/Tier2×20/Tier3×20) + review_prompt.py(토큰 예산) | 896 |
| Phase A | registry.py + tools/python.py(Analyzer Protocol) + CQ_WARNING_CAP 단일 cap | 943 |
| Phase B | tools/semgrep.py — 23개 언어, security 자동 분류, graceful degradation | 1004 |
| Phase C | tools/eslint.py(JS/TS) + tools/shellcheck.py(shell) + nixpacks 빌드 수정 | **1074** |

> Phase 0~C 통합 회고: [docs/reports/2026-04-19-multilang-expansion-retrospective.md](reports/2026-04-19-multilang-expansion-retrospective.md)

### 그룹 3 — 코드 품질 / 아키텍처 리팩터 (2026-04-19)

| 작업 | 주요 내용 | 테스트 증분 |
|------|----------|-----------|
| 리포지토리 계층 신설 | repository_repo/analysis_repo — pipeline·router db.query 직접 사용 교체 | — |
| Notifier 레지스트리 | NotifyContext + Notifier Protocol + REGISTRY + 루프 축약 | — |
| RepoConfig 동기화 해소 | dataclass fields 루프 + model_dump() — 채널 추가 시 7곳→4곳 | — |
| private→public 리네임 | _build_result_dict→build_analysis_result_dict 등 3개 함수 공개 | — |
| DB/커버리지 보강 | database.py FailoverSessionFactory 예외경로 (+16, 75%→100%) | +16 |
| UI 커버리지 보강 | ui/router.py 분기 (+11, 83.9%→99.4%) | +11 |
| 통합 테스트 | webhook→gate end-to-end 3 시나리오 | +3 |
| 테스트 엣지케이스 | gate/engine.py·auth/github.py·github_client/repos.py·알림·보안 | +28 |
| 품질 감사 7라운드 | 정상성·커버리지·결정성·격리성·pylint·flake8·bandit+E2E | — |

### 그룹 2 — n8n 자동화 (2026-04-17 ~ 04-19)

| 작업 | 주요 내용 |
|------|----------|
| n8n Phase 1 | 저점 Issue 감지 → claude_fix.sh 실행 → PR 자동 생성 |
| n8n Phase 2 | 봇 PR auto_merge 누락 수정 (re-gate + `claude-fix/` 무한루프 가드) |
| n8n Phase 3 | PR merge 시 `Closes #N` 키워드 파싱 → GitHub Issues API 자동 close |
| auto_merge 견고성 | merge_pr tuple 반환 + mergeable_state 재시도 + Telegram 실패 알림 (+12 테스트) |

### 그룹 1 — 핵심 기능 구축 (2026-04-05 ~ 04-12)

| 작업 | 주요 내용 |
|------|----------|
| 초기 설계 | FastAPI + PostgreSQL + GitHub OAuth + Webhook + 점수 체계 + Telegram 알림 |
| Gate 시스템 | 3-옵션(PR 댓글·Auto Approve·Telegram 반자동) 완전 독립 처리 |
| 웹 대시보드 | 리포 현황·점수 차트·분석 상세·설정 UI |
| CLI Hook | pre-push hook → AI 리뷰 → 대시보드 반영 |
| 스코어 버그 수정 | 89점 고정 문제 해소 (SHA 이동 + AI status 필드) |

