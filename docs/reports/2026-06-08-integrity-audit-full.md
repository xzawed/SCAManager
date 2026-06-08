# 정합성 감사 리포트 — scope=full (2026-06-08, Task 9 골든)

> `.claude/workflows/integrity-audit.mjs` scope=full 실행 산출물. read-only — fix 는 사용자 PR 결정.

| 항목 | 값 |
|------|-----|
| scope | full (8 도메인) |
| 라운드 | 3 |
| confirmed (verify real) | 36 (P1 10 / P2 26) |
| 비용(실측) | 358 에이전트 / ~17M 토큰 / ~55분 |
| ⚠️ 검증 한계 | **세션 사용량 한도(2pm Asia/Seoul 리셋)로 다수 verify 에이전트 + completeness critic 실패** → 검증 못 받은 후보 결함 드롭 + 완전성 점검 미실행. 본 36건은 확정(real)이나 **전수 커버리지 미보장** — 한도 리셋 후 resume(resumeFromRunId) 재검증 권장 |

도메인 분포: {'pipeline': 6, 'gate': 2, 'security': 7, 'db': 6, 'ui': 5, 'docs': 5, 'api': 4, 'tests': 1}

## Confirmed 결함 요약표

| # | sev | domain | file:line | 요지 |
|---|-----|--------|-----------|------|
| 1 | P1 | api | `src/webhook/providers/telegram.py:72` | 반자동 Gate Telegram 콜백에 리포 소유권(authorization) 검증 부재 — 임의 사용자가 PR 승인/머지 가능 |
| 2 | P1 | db | `alembic/versions/0026_supabase_rls_policies.py:41` | RLS 정책에 FORCE ROW LEVEL SECURITY 부재 — 앱 연결(테이블 owner)에서 RLS 전면 우회 → '2차 안전망' 무력화 |
| 3 | P1 | docs | `docs/architecture.md:80` | architecture.md src 트리 gate/ 블록에 핵심 실행 서브시스템 src/gate/actions/ 패키지 전체 누락 |
| 4 | P1 | gate | `src/repositories/merge_retry_repo.py:257` | check_suite.completed 즉시 재시도가 백오프 필터에 막혀 무력화 — claim_batch가 only_ids에도 next_retry_at<=now 강제 |
| 5 | P1 | pipeline | `src/api/hook.py:243` | CLI hook 결과 저장이 동시 동일 SHA insert race 미처리 → IntegrityError 500 (멱등성 결함) |
| 6 | P1 | pipeline | `src/github_client/diff.py:39` | GitHub 파일 콘텐츠 fetch 실패(transient 403/5xx)가 incomplete 마커 없이 무분석 만점으로 처리 — auto-merge fail-open |
| 7 | P1 | pipeline | `src/analyzer/io/tools/python.py:57` | 정적분석 도구별 subprocess 타임아웃이 이슈를 무음 폐기 + incomplete 신호 미발생 → 점수 인플레이션 fail-open |
| 8 | P1 | pipeline | `src/scorer/calculator.py:63` | AI 리뷰 실패(api_error/parse_error) 시 중립-고점 기본값이 auto-merge/auto-approve 를 차단하지 않음 (정적분석 incomplete |
| 9 | P1 | security | `src/webhook/validator.py:17` | GitHub webhook HMAC 검증이 비-ASCII 서명 헤더에 TypeError→500 (compare_digest str 비교, 미인증 공개 엔드포인트) |
| 10 | P1 | security | `src/api/hook.py:144` | CLI hook 토큰 검증이 비-ASCII 토큰에 TypeError→500 (verify/result 두 공개 엔드포인트, compare_digest str 비교) |
| 11 | P2 | api | `src/webhook/providers/telegram.py:114` | Gate 콜백 기존 결정/리플레이 가드 부재 — 동일 서명 버튼 재클릭으로 결정 뒤집기 + post_github_review/auto-merge 재실행 |
| 12 | P2 | api | `src/notifier/_http.py:57` | 외부 webhook SSRF 가드의 DNS-rebinding TOCTOU — validate 시점과 connect 시점 DNS 재해석 분리 (docstring 'DNS-r |
| 13 | P2 | api | `src/webhook/providers/telegram.py:211` | Telegram webhook 본문 JSON 파싱 무방비 — secret 통과 후 비정형/비-dict 본문 시 500 (railway provider 와 비대칭) |
| 14 | P2 | db | `src/models/analysis.py:28` | analyses.repo_id FK 에 ondelete 미설정 — repositories→analyses 삭제 사슬에 DB 레벨 안전망 부재(FK CASCADE 매트릭스  |
| 15 | P2 | db | `src/models/merge_attempt.py:32` | merge_attempts.state 인덱스 ORM↔alembic drift — ix_merge_attempts_state_repo 가 마이그레이션 전용(ORM __tab |
| 16 | P2 | db | `src/models/merge_retry.py:116` | 부분 유니크 인덱스 uq_merge_retry_queue_active가 ORM __table_args__에 미선언 — 중복방지 보증이 PG 전용·SQLite 테스트 미검증 |
| 17 | P2 | db | `src/models/insight_narrative_cache.py:47` | insight_narrative_cache.repo_id 중복/유령 인덱스 — ORM index=True가 만든 ix_insight_narrative_cache_repo_ |
| 18 | P2 | db | `tests/unit/migrations/test_0020_round_trip.py:1` | 전역 ORM↔마이그레이션 메타데이터 정합성 가드 부재 — alembic check/compare_metadata 류 회귀 테스트 없음 |
| 19 | P2 | docs | `README.md:497` | README 'full endpoint list' 가 internal cron 4개 중 2개(scan-security, retry-pending-merges) 누락 |
| 20 | P2 | docs | `docs/architecture.md:125` | architecture.md scripts/ 블록에 capture_design_screenshots.py / extract_design_tokens.py 2개 파일 누락 |
| 21 | P2 | docs | `docs/reference/env-vars.md:104` | env-vars.md MERGE_UNKNOWN_RETRY_LIMIT/DELAY line 인용 drift — config.py:60/61 → 실제 63/64 |
| 22 | P2 | docs | `README.md:7` | Python 버전 선언↔현실 불일치 — README/STATE 는 3.14 명시, CI 실제 실행은 3.12 |
| 23 | P2 | gate | `src/gate/retry_policy.py:59` | UNSTABLE_CI + ci_status='passed' 영구 재시도 — 비머지 PR이 max_age(24h)/max_attempts(30) 까지 재시도 예산 소모 +  |
| 24 | P2 | pipeline | `src/analyzer/io/ai_review.py:187` | _parse_response 의 bare int() — AI 점수 필드가 float-string/Infinity 시 리뷰 전체가 parse_error 로 붕괴 (hook. |
| 25 | P2 | pipeline | `src/api/hook.py:231` | CLI hook 의 비숫자/누락 점수 제출 시 parse_error 임에도 89/B 인플레이션 점수가 DB 저장 (대시보드/리더보드 오염) |
| 26 | P2 | security | `src/webhook/validator.py:17` | verify_github_signature: 비-ASCII 서명 헤더 시 uncaught TypeError → 401 대신 500 |
| 27 | P2 | security | `src/webhook/providers/telegram.py:207` | Telegram webhook secret 검증: 비-ASCII 시크릿 토큰 헤더 시 uncaught TypeError → 401 대신 500 |
| 28 | P2 | security | `.claude/rules/security.md:28` | security.md 규칙의 SESSION_SECRET 기본값 문자열 불일치 — 'dev-secret-key' vs 실제 'dev-secret-change-in-produ |
| 29 | P2 | security | `src/webhook/providers/railway.py:47` | Railway/Telegram webhook 토큰 검증이 비-ASCII 입력에 TypeError→500 (compare_digest str 비교) |
| 30 | P2 | security | `src/api/auth.py:26` | Admin API key / Cron API key 검증이 비-ASCII 헤더에 TypeError→500 (compare_digest str 비교) |
| 31 | P2 | tests | `tests/unit/migrations/test_0029_rls_5_missing_tables.py:169` | test_0029 users RLS 검증: dead 'or' fallback + 절대 매칭 불가한 'ON users' in s.lower() sub-branch |
| 32 | P2 | ui | `src/templates/settings.html:1174` | i18n 문자열을 JS 문자열 리터럴에 HTML-escape(autoescape)로 주입 — tojson 미사용 비일관 |
| 33 | P2 | ui | `src/static/js/effects.js:277` | effects.js 죽은 셀렉터(.tabs/.tabs__tab/.nav__link/.nav__links) — 미사용 코드 + preventDefault 잠재 함정 |
| 34 | P2 | ui | `src/i18n/filters.py:43` | i18n_args 필터가 자동이스케이프 컨텍스트에서 str kwarg를 이중 이스케이프 (사용자 표시명 깨짐) |
| 35 | P2 | ui | `src/templates/add_repo.html:215` | add_repo.html: window pagehide 리스너가 hx-boost 재방문마다 누적 (remove-before-add 누락) |
| 36 | P2 | ui | `src/static/js/tweaks.js:83` | tweaks.js: document keydown 리스너가 hx-boost body swap마다 무한 누적 |

## P1 상세 (claim + evidence)

### [P1/api] 반자동 Gate Telegram 콜백에 리포 소유권(authorization) 검증 부재 — 임의 사용자가 PR 승인/머지 가능
- **위치**: `src/webhook/providers/telegram.py:72`
- **3-렌즈**: correctness=real security=real repro=real
- **claim**: handle_gate_callback 는 클릭한 Telegram 사용자(from_data.id)를 decided_by 로 '기록만' 할 뿐, 그 사용자가 해당 repo 의 소유자/연결 사용자인지 검증하지 않는다. callback_data 의 HMAC 토큰은 'gate:{analysis_id}' 만 서명(deterministic)하므로 사용자 신원과 무관하다. 반면 텍스트 명령 경로(telegram_commands.py:219 _handle_stats, :271 _handle_settings)는 `repo.user_id != user.id` 소유권을 엄격히 검증한다 — 대칭이 깨진 authorization 갭.
- **evidence**: grep 실측: telegram.py:75 `decided_by: str`, :109 `body = get_text(..., decided_by=decided_by)`, :114 `save_gate_decision(db, analysis_id, decision, 'manual', decided_by)`, :242-245 `from_data = callback_query.get('from', {}); user_id = from_data.get('id', ...); decided_by = ...` — repo.user_id 대조 코드 없음. 대조군 telegram_commands.py:219 `if repo is None or repo.user_id != user.id:`. 위협 모델 성립 근거: user_re

### [P1/db] RLS 정책에 FORCE ROW LEVEL SECURITY 부재 — 앱 연결(테이블 owner)에서 RLS 전면 우회 → '2차 안전망' 무력화
- **위치**: `alembic/versions/0026_supabase_rls_policies.py:41`
- **3-렌즈**: correctness=real security=real repro=real
- **claim**: 11개 앱 테이블에 RLS policy를 ENABLE하지만 어느 마이그레이션에도 FORCE ROW LEVEL SECURITY가 없다. alembic/env.py:30과 database.py:231이 동일한 settings.database_url을 사용하므로 마이그레이션(테이블 생성=owner)과 런타임 연결이 같은 role(=테이블 owner)이다. PostgreSQL은 테이블 owner에 대해 RLS policy를 기본 우회(FORCE 미설정 시)하므로, 0026 docstring이 표방한 '2차 안전망(DB 레벨 격리 — 앱 버그 시에도 데이터 누출 차단)'이 운영 PG에서 실제로는 전혀 작동하지 않는다. 즉 _apply_*_user_filter 앱 레벨 1차 필터에 버그가 생기면 RLS가 막아주지 못한다. 게다가 saas_service.py:_RLS_MATRIX와 GET /admin/rls-audit는 모든 테이블을 'applied'로 보고해 운영자에게 거짓 보호 안심을 준다. grep 결과 코드베이스/문서 전체에 'FORCE ROW LEVEL'/owner-bypass 언급이 0건이라 이 갭이 인지되지 않은 상태다.
- **evidence**: grep -n 'ENABLE ROW LEVEL SECURITY' alembic/versions/* → 0026:41/56/74, 0027:31, 0028:31, 0029:41/57/77/98/118, 0037:36 (총 11개) / grep -rn 'FORCE ROW LEVEL|FORCE RLS|table owner|BYPASSRLS' → No matches (마이그레이션·소스·docs 전부 부재). alembic/env.py:30 `config.set_main_option("sqlalchemy.url", settings.database_url)` ↔ database.py:231 `SessionLocal = FailoverSessionFactory(settings.database_url, ...)` 동일 U

### [P1/docs] architecture.md src 트리 gate/ 블록에 핵심 실행 서브시스템 src/gate/actions/ 패키지 전체 누락
- **위치**: `docs/architecture.md:80`
- **3-렌즈**: correctness=real security=reject repro=real
- **claim**: docs/architecture.md gate/ 블록(80~89줄)은 9개 파일(_common, engine, github_review, native_automerge, merge_reasons, telegram_gate, merge_failure_advisor, retry_policy, _merge_attempt_states)만 나열하고 `actions/` 서브디렉토리를 누락한다. 실제 src/gate/actions/ 는 GateAction ABC + GateContext + 3개 구체 액션(ApproveAction, AutoMergeAction, ReviewCommentAction)을 담은 게이트 실행 핵심 서브시스템으로, .claude/rules/api.md:27-28 및 STATE.md 사이클 140/162/163/164 서사에서 광범위 참조된다. CLAUDE.md 완료 6-step §⑥(신규 파일 추가 시 architecture.md src 트리 동기화 의무)을 위반한 누락이며, 다음 Claude 세션이 게이트 액션 구조를 architecture.md 단일 출처에서 발견 불가.
- **evidence**: sed -n '80,90p' docs/architecture.md → gate/ 블록이 `_merge_attempt_states.py`(89줄)로 끝나고 곧장 notifier/(90줄)로 이동, actions/ 항목 없음. `grep -n actions docs/architecture.md` → 111줄(src/ui/routes/ actions)만 매치, gate actions 무. 실측: `grep -nE '^class ' src/gate/actions/*.py` → __init__.py:20 GateContext, :33 GateAction(ABC), approve.py:25 ApproveAction, auto_merge.py:27 AutoMergeAction, review_comment.py:19 Re

### [P1/gate] check_suite.completed 즉시 재시도가 백오프 필터에 막혀 무력화 — claim_batch가 only_ids에도 next_retry_at<=now 강제
- **위치**: `src/repositories/merge_retry_repo.py:257`
- **3-렌즈**: correctness=real security=reject repro=real
- **claim**: _trigger_retry_for_sha(check_suite.completed 핸들러)가 find_pending_by_sha로 찾은 행 id를 only_ids로 process_pending_retries에 넘겨 '즉시 재시도'를 의도하지만, claim_batch는 only_ids 분기(266행)와 무관하게 status=='pending' AND next_retry_at <= now(256~257행)를 항상 강제한다. enqueue_or_bump는 신규 행 next_retry_at = now + initial_next_retry_seconds(기본 60초, merge_retry_repo.py:180)로 설정하므로, CI가 60초 미만에 완료되어 check_suite.completed가 도착해도 해당 SHA 행은 아직 next_retry_at가 미래라 claim되지 않는다. 즉 check_suite 웹훅의 핵심 목적(CI 완료 즉시 머지)이 백오프 윈도우 동안 동작하지 않고, 결국 1분 cron sweep을 기다려야 한다. only_ids 트리거 경로는 '이미 due한 행을 우선 처리'만 할 뿐 '강제 due화'를 못 한다.
- **evidence**: merge_retry_repo.py:255-266 claim_batch query = filter(status=='pending', next_retry_at <= _now, claimed_at IS NULL | stale) then `if only_ids: query = query.filter(id.in_(only_ids))` — only_ids는 추가 AND 조건일 뿐 next_retry_at 게이트를 우회하지 않음. enqueue_or_bump merge_retry_repo.py:179-180 `next_retry = _now + timedelta(seconds=initial_next_retry_seconds)`. webhook/providers/github.py:483-492 find_pending_b

### [P1/pipeline] CLI hook 결과 저장이 동시 동일 SHA insert race 미처리 → IntegrityError 500 (멱등성 결함)
- **위치**: `src/api/hook.py:243`
- **3-렌즈**: correctness=real security=reject repro=real
- **claim**: save_hook_result()가 line 197-199에서 find then line 243-244에서 raw db.add(analysis)+db.commit()을 IntegrityError 처리 없이 수행한다. analyses 테이블에는 UniqueConstraint('repo_id','commit_sha', name='uq_analyses_repo_sha')가 있어(src/models/analysis.py:22), 두 개의 동시 pre-push hook이 동일 commit_sha로 POST /api/hook/result 하면 둘 다 existing 체크(line 197)를 통과한 뒤 둘 다 insert를 시도 → 한쪽이 IntegrityError를 던지고 uncaught로 전파되어 FastAPI 500이 반환된다. 이는 pipeline 경로가 명시적으로 방어한 것과 비대칭이다: _save_and_gate는 analysis_repo.save_new(db, Analysis(...))(src/worker/pipeline.py:521)를 통해 IntegrityError를 rollback+재조회로 흡수하고 (analysis, created) 튜플로 race-recovery 신호를 반환한다(src/repositories/analysis_repo.py:34-44). _ensure_repo도 동일 race를 #787에서 명시 수정했다(src
- **evidence**: grep -n 실측: src/api/hook.py:197 `existing = db.query(Analysis).filter_by(` / :243 `db.add(analysis)` / :244 `db.commit()` (IntegrityError 처리 부재 — grep 'IntegrityError|save_new|race' in hook.py 결과 0건). 대조: src/models/analysis.py:22 `UniqueConstraint("repo_id", "commit_sha", name="uq_analyses_repo_sha")`; src/repositories/analysis_repo.py:34 `except IntegrityError:` (race-safe save_new); src/worker/

### [P1/pipeline] GitHub 파일 콘텐츠 fetch 실패(transient 403/5xx)가 incomplete 마커 없이 무분석 만점으로 처리 — auto-merge fail-open
- **위치**: `src/github_client/diff.py:39`
- **3-렌즈**: correctness=real security=real repro=real
- **claim**: _collect_changed_files 가 모든 변경 파일에 대해 repo.get_contents(...) 를 호출하고, GithubException(404 삭제 파일뿐 아니라 rate-limit 403·secondary rate limit·5xx 등 transient 오류 포함) 발생 시 content='' 로 폴백한다(line 41). 빈 content 는 analyze_file 이 예외 없이 빈 StaticAnalysisResult 를 반환(static.py:56-57)하므로 calculate_score 에서 code_quality=25/security=20 만점으로 환산된다. 이 경로는 예외를 raise 하지 않으므로 _run_static_with_timeout 의 incomplete 판정((a)deadline (b)analyze_file 예외 전량 실패)에 걸리지 않아 static_analysis_incomplete 마커가 설정되지 않고 AutoMergeAction/ApproveAction 의 #779/#783 가드를 우회한다. 즉 transient GitHub 오류 시 미분석(수정/추가) 코드가 인플레 만점으로 auto-merge 될 수 있다. #779 가 타임아웃 경로에 적용한 fail-closed 안전망이 upstream content-fetch 실패 경로에는 미적용. ChangedFile(models.py)에 sta
- **evidence**: grep -n 결과: src/github_client/diff.py:38 `content = repo.get_contents(f.filename, ref=ref).decoded_content.decode("utf-8")`, :39 `except (GithubException, UnicodeDecodeError) as exc:`, :41 `content = ""`. static.py:56-57 `if not content.strip(): return StaticAnalysisResult(filename=filename)`. pipeline.py:238 incomplete 안전망은 `failed == len(files)`(analyze_file 예외)만 포착. tests/unit/github_client/tes

### [P1/pipeline] 정적분석 도구별 subprocess 타임아웃이 이슈를 무음 폐기 + incomplete 신호 미발생 → 점수 인플레이션 fail-open
- **위치**: `src/analyzer/io/tools/python.py:57`
- **3-렌즈**: correctness=real security=real repro=real
- **claim**: 개별 분석 도구가 subprocess 타임아웃(STATIC_ANALYSIS_TIMEOUT=30s)에 걸리면 빈 리스트([])를 반환해 이슈를 무음 폐기한다. 이 per-tool 타임아웃은 파일 단위 deadline(PIPELINE_ANALYSIS_TIMEOUT=60s)을 트립하지 않으므로 _run_static_with_timeout 가 incomplete=True 를 설정하지 않는다. 결과적으로 bandit/slither/semgrep(security 카테고리) 등이 타임아웃 시 security 이슈 0건 → 만점(20/20) → static_analysis_incomplete 마커 없음 → AutoMergeAction/ApproveAction 가드를 통과해 미분석 코드가 auto-merge 될 수 있다(fail-open).
- **evidence**: grep -n 결과: python.py:57 `except subprocess.TimeoutExpired:` / :59 `return []` (flake8 104-106, bandit 143-145 동일). 23개 tools 전부 동일 패턴(grep -rln TimeoutExpired = 23 files). constants.py:94 `STATIC_ANALYSIS_TIMEOUT = 30`, pipeline.py:33 `PIPELINE_ANALYSIS_TIMEOUT = 60`. static.py:98-101 analyzer 예외는 analyze_file 내부에서 catch+로그만, pipeline.py:215-222 wait_for 타임아웃/238-243 전량실패만 incomplete 설정 — per-too

### [P1/pipeline] AI 리뷰 실패(api_error/parse_error) 시 중립-고점 기본값이 auto-merge/auto-approve 를 차단하지 않음 (정적분석 incomplete 와 비대칭)
- **위치**: `src/scorer/calculator.py:63`
- **3-렌즈**: correctness=real security=reject repro=real
- **claim**: ai_review.status != 'success'(api_error/parse_error/no_api_key)일 때 calculator 가 AI_DEFAULT_*(commit 13 + direction 21 + test 10 = 44점)를 적용한다. 정적분석이 clean(code_quality 25 + security 20 = 45)이면 총점 89/B 가 되어 approve_threshold/merge_threshold 를 초과할 수 있다. 정적분석 불완전은 static_analysis_incomplete 마커로 auto-merge/auto-approve 가 차단되지만, AI 리뷰 실패에는 동등한 차단 마커가 없다(breakdown['ai_defaults_applied']=True 가 calculator.py:89-90 에 기록되나 gate 가 이를 읽지 않음). 즉 AI 리뷰가 실제로 수행되지 않은 PR 이 자동 승인/머지될 수 있다.
- **evidence**: calculator.py:63 `if ai_review is not None and ai_review.status == "success":` else 분기 72-78 에서 AI_DEFAULT_* 적용 + ai_defaults_applied=True. constants.py:23-25 AI_DEFAULT_COMMIT=13/DIRECTION=21/TEST=10 (합 44). grep -rn 'ai_review_status|ai_defaults_applied|ai_review.status' src/gate/ = 출력 없음(gate 가 AI 상태 미참조). 대조: auto_merge.py:46 / approve.py:55 는 static_analysis_incomplete 만 확인.

### [P1/security] GitHub webhook HMAC 검증이 비-ASCII 서명 헤더에 TypeError→500 (compare_digest str 비교, 미인증 공개 엔드포인트)
- **위치**: `src/webhook/validator.py:17`
- **3-렌즈**: correctness=real security=real repro=real
- **claim**: verify_github_signature 가 expected(str) 와 공격자 제어 signature_header(str) 를 hmac.compare_digest 로 비교한다. compare_digest 는 비-ASCII 문자가 포함된 str 비교 시 TypeError 를 던진다. signature_header 의 'sha256=' prefix 만 검사하므로(L12), 'sha256=ü' 같은 헤더는 prefix 검사를 통과한 뒤 compare_digest(expected, 'sha256=ü') 에서 TypeError 발생. github_webhook(providers/github.py:526)은 verify_github_signature 를 try/except 없이 호출하고 main.py 에 TypeError 전역 핸들러 없음(RateLimitExceeded 만 존재) → 미인증 공격자가 단일 헤더로 반복 500 유발(가용성/로그 노이즈). 수정: 양측 .encode() 후 bytes 비교(비-ASCII 안전) 또는 try/except TypeError→False.
- **evidence**: validator.py:17 `return hmac.compare_digest(expected, signature_header)` (둘 다 str). 실측: `python -c "import hmac; hmac.compare_digest('sha256=abcdef','sha256=ü')"` → `TypeError: comparing strings with non-ASCII characters is not supported`. providers/github.py:526-527 `if not verify_github_signature(payload, x_hub_signature_256, secret): raise HTTPException(401)` (try/except 없음). main.py:203 `add_e

### [P1/security] CLI hook 토큰 검증이 비-ASCII 토큰에 TypeError→500 (verify/result 두 공개 엔드포인트, compare_digest str 비교)
- **위치**: `src/api/hook.py:144`
- **3-렌즈**: correctness=real security=real repro=real
- **claim**: GET /api/hook/verify(L144) 와 POST /api/hook/result(L177) 모두 hmac.compare_digest(config.hook_token or '', <attacker_token>) 로 str-str 비교한다. effective_token 은 ?token= 쿼리 또는 Authorization: Bearer 헤더(L128-131), body.token 은 POST 바디로 전부 공격자 제어. 비-ASCII 토큰(예 ?token=töken) 전송 시 TypeError → 미처리 500. RATE_LIMIT_API 데코레이터가 DoS 를 부분 완화하나 입력 검증 부재로 정상 401/404 대신 500 반환. 수정: 양측 .encode() bytes 비교 또는 try/except.
- **evidence**: hook.py:144 `if config is None or not hmac.compare_digest(config.hook_token or "", effective_token):`, hook.py:177 `... hmac.compare_digest(config.hook_token or "", body.token):` (모두 str). hook.py:128-131 effective_token = Bearer 헤더 또는 query param(공격자 제어). 실측: `hmac.compare_digest('storedtoken','töken')` → TypeError. 두 엔드포인트 모두 토큰 외 인증 없음(공개).

## P2 목록

- **[api]** `src/webhook/providers/telegram.py:114` — Gate 콜백 기존 결정/리플레이 가드 부재 — 동일 서명 버튼 재클릭으로 결정 뒤집기 + post_github_review/auto-merge 재실행
- **[api]** `src/notifier/_http.py:57` — 외부 webhook SSRF 가드의 DNS-rebinding TOCTOU — validate 시점과 connect 시점 DNS 재해석 분리 (docstring 'DNS-rebinding defence' 과대 표현)
- **[api]** `src/webhook/providers/telegram.py:211` — Telegram webhook 본문 JSON 파싱 무방비 — secret 통과 후 비정형/비-dict 본문 시 500 (railway provider 와 비대칭)
- **[db]** `src/models/analysis.py:28` — analyses.repo_id FK 에 ondelete 미설정 — repositories→analyses 삭제 사슬에 DB 레벨 안전망 부재(FK CASCADE 매트릭스 비대칭)
- **[db]** `src/models/merge_attempt.py:32` — merge_attempts.state 인덱스 ORM↔alembic drift — ix_merge_attempts_state_repo 가 마이그레이션 전용(ORM __table_args__ 미선언)
- **[db]** `src/models/merge_retry.py:116` — 부분 유니크 인덱스 uq_merge_retry_queue_active가 ORM __table_args__에 미선언 — 중복방지 보증이 PG 전용·SQLite 테스트 미검증
- **[db]** `src/models/insight_narrative_cache.py:47` — insight_narrative_cache.repo_id 중복/유령 인덱스 — ORM index=True가 만든 ix_insight_narrative_cache_repo_id가 운영 PG에는 존재하지 않음
- **[db]** `tests/unit/migrations/test_0020_round_trip.py:1` — 전역 ORM↔마이그레이션 메타데이터 정합성 가드 부재 — alembic check/compare_metadata 류 회귀 테스트 없음
- **[docs]** `README.md:497` — README 'full endpoint list' 가 internal cron 4개 중 2개(scan-security, retry-pending-merges) 누락
- **[docs]** `docs/architecture.md:125` — architecture.md scripts/ 블록에 capture_design_screenshots.py / extract_design_tokens.py 2개 파일 누락
- **[docs]** `docs/reference/env-vars.md:104` — env-vars.md MERGE_UNKNOWN_RETRY_LIMIT/DELAY line 인용 drift — config.py:60/61 → 실제 63/64
- **[docs]** `README.md:7` — Python 버전 선언↔현실 불일치 — README/STATE 는 3.14 명시, CI 실제 실행은 3.12
- **[gate]** `src/gate/retry_policy.py:59` — UNSTABLE_CI + ci_status='passed' 영구 재시도 — 비머지 PR이 max_age(24h)/max_attempts(30) 까지 재시도 예산 소모 + 터미널 알림 최대 24h 지연
- **[pipeline]** `src/analyzer/io/ai_review.py:187` — _parse_response 의 bare int() — AI 점수 필드가 float-string/Infinity 시 리뷰 전체가 parse_error 로 붕괴 (hook.py _coerce_raw_score 하드닝 미적용 비대칭)
- **[pipeline]** `src/api/hook.py:231` — CLI hook 의 비숫자/누락 점수 제출 시 parse_error 임에도 89/B 인플레이션 점수가 DB 저장 (대시보드/리더보드 오염)
- **[security]** `src/webhook/validator.py:17` — verify_github_signature: 비-ASCII 서명 헤더 시 uncaught TypeError → 401 대신 500
- **[security]** `src/webhook/providers/telegram.py:207` — Telegram webhook secret 검증: 비-ASCII 시크릿 토큰 헤더 시 uncaught TypeError → 401 대신 500
- **[security]** `.claude/rules/security.md:28` — security.md 규칙의 SESSION_SECRET 기본값 문자열 불일치 — 'dev-secret-key' vs 실제 'dev-secret-change-in-production'
- **[security]** `src/webhook/providers/railway.py:47` — Railway/Telegram webhook 토큰 검증이 비-ASCII 입력에 TypeError→500 (compare_digest str 비교)
- **[security]** `src/api/auth.py:26` — Admin API key / Cron API key 검증이 비-ASCII 헤더에 TypeError→500 (compare_digest str 비교)
- **[tests]** `tests/unit/migrations/test_0029_rls_5_missing_tables.py:169` — test_0029 users RLS 검증: dead 'or' fallback + 절대 매칭 불가한 'ON users' in s.lower() sub-branch
- **[ui]** `src/templates/settings.html:1174` — i18n 문자열을 JS 문자열 리터럴에 HTML-escape(autoescape)로 주입 — tojson 미사용 비일관
- **[ui]** `src/static/js/effects.js:277` — effects.js 죽은 셀렉터(.tabs/.tabs__tab/.nav__link/.nav__links) — 미사용 코드 + preventDefault 잠재 함정
- **[ui]** `src/i18n/filters.py:43` — i18n_args 필터가 자동이스케이프 컨텍스트에서 str kwarg를 이중 이스케이프 (사용자 표시명 깨짐)
- **[ui]** `src/templates/add_repo.html:215` — add_repo.html: window pagehide 리스너가 hx-boost 재방문마다 누적 (remove-before-add 누락)
- **[ui]** `src/static/js/tweaks.js:83` — tweaks.js: document keydown 리스너가 hx-boost body swap마다 무한 누적
