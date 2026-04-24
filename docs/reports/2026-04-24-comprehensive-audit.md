# SCAManager 전면 감사 보고서 (2026-04-24)

14개 에이전트 × 3 Round 독립 검증 (Round 1: 5 · Round 2: 5 · Round 3: 4). 모든 P1 이상 이슈는 Round 3 에서 재검증 완료.

## 최종 결론 — 전반 건강도: B+ (양호, 정리 필요)

아키텍처·보안 설계 골격은 **견고**하다. Gate 3-옵션 독립, SSRF 방어 (`_http.py::build_safe_client`), HMAC `compare_digest`, 5-way sync 규약, Analyzer Registry, FailoverSessionFactory — 모두 문서가 주장하는 대로 구현됨. 그러나 **운영 지표의 정확성**(issue_count 오기록, 테스트 수 3-way 불일치)과 **성능 인프라의 방치된 설계**(http_client 싱글톤 미사용, 정적분석 파일-병렬성 부재)에서 체계적 결함이 발견되었다.

## P0 — 긴급 (없음)

데이터 손실·보안 유출 경로 확인되지 않음.

## P1 — 높음 (7건, Round 3 재검증 완료)

### P1-1. `issue_count` 가 파일 수를 기록 — 메트릭 왜곡 [True]

`src/worker/pipeline.py:327`: `ctx["issue_count"] = len(analysis_results)` — `analysis_results` 는 파일당 1개 `StaticAnalysisResult`. 실제 이슈 합계 아님.

소비처 조사 결과: **로그 필드 하나뿐** (stage_timer extra_fields). DB·API·UI 어디에도 없음. 회귀 위험 극소. → **Phase G.1 에서 수정**.

### P1-2. 정적분석 파일-병렬성 부재 [Partially True]

`src/worker/pipeline.py:96-100`: `asyncio.to_thread(lambda: [analyze_file(f) for f in files])` — 이벤트 루프만 비차단, 파일 간 병렬성 없음. 메모리·TIMEOUT·race 재검토 필요. → **Phase G.6 (별도 Phase) 으로 연기**.

### P1-3. httpx 싱글톤 미사용 — 10 파일 / 16 호출 사이트 [True]

5개 디렉토리(gate/github_client/railway_client/notifier/telegram) 에서 0회 싱글톤 사용. 매 요청마다 `async with httpx.AsyncClient()` 신규 생성 — TCP/TLS/DNS 반복 비용. → **Phase G.5 에서 3개 PR 로 분할 수정**.

### P1-4. Telegram webhook secret 실패 시 HTTP 200 반환 [True]

`src/webhook/providers/telegram.py:111-115`: 서명 실패 시 `return {"status": "ok"}` — HTTP 200 반환. GitHub provider 는 401 반환으로 일관성 파괴. → **Phase G.3 에서 수정**.

### P1-5. `decrypt_token` 평문 fallback 3중 [True]

`src/crypto.py:31-58`: 키 미설정·오타 시 조용히 평문 저장. prod 환경에서 감지 장치 없음. → **Phase G.4 에서 startup 경고 추가**.

### P1-6. 문서 3-way 테스트 수 불일치 [True]

CI 실측 1293 vs STATE.md 1247 vs CLAUDE.md 1247 vs README 1275. → **Phase G.2 에서 1293 으로 통일**.

### P1-7. `.env.example` SMTP 블록 부재 [True]

Email notifier 지원 변수 5종이 .env.example 에 없음. docs/reference/env-vars.md 에는 존재. → **Phase G.2 에서 추가**.

## P2 — 중간

- Alembic 0005/0006: `batch_alter_table` (SQLite 전용 패턴, PG 무해) — 기존 마이그레이션이므로 수정 불가·무해
- ~~PyGithub 블로킹: `src/github_client/diff.py` 타임아웃 미설정~~ → **✅ 그룹 36 수정** (`_make_github_client` + `timeout=HTTP_CLIENT_TIMEOUT`)
- ~~DB 유니크 제약 부재: `(analyses.repo_id, commit_sha)` race window~~ → **✅ 그룹 36 수정** (Migration 0016 + IntegrityError 안전망)
- `src/database.py:160-172` SELECT 1 — `pool_pre_ping` 과 다른 Failover 전용 역할, 의도적 유지
- ~~settings.html ④ 번호 라벨 누락~~ → **✅ 그룹 36 수정**
- ~~Phase F.2 반자동 merge 콜백 관측 미구현~~ → **✅ 그룹 37 수정** (`handle_gate_callback` + `log_merge_attempt` nested try/except)

## P3 — 낮음

주요 규약 전부 준수 확인:
- Gate 3-옵션 독립성 (`_run_review_comment`·`_run_approve_decision`·`_run_auto_merge`)
- merge_reasons 11 태그 전부 advisor 매핑 완료 (F.3)
- GRADE 상수 단일 출처
- keyword-only 강제 (`*`)
- Jinja2 autoescape + `html.escape()` 규약
- HMAC `compare_digest` 사용

## CI 로그에서 추가 발견 (Phase H 후보)

SonarCloud 가 Jinja2 템플릿을 JS 로 파싱 시도 → 파싱 에러:
- `src/templates/repo_detail.html:369:30` "Unexpected token"
- `src/templates/analysis_detail.html:538:23` "Unexpected token"

`sonar-project.properties` 에서 `sonar.javascript.exclusions` 로 템플릿 경로 제외 필요.

## 수정 우선순위 (Phase G 실행 순서)

1. G.0: 이 보고서 아카이브 (완료)
2. G.1: P1-1 issue_count 1줄 정정
3. G.2: P1-6/P1-7 문서 수치·템플릿 동기화
4. G.3: P1-4 Telegram 401 반환
5. G.4: P1-5 crypto prod 경고
6. G.5: P1-3 http_client 싱글톤 치환 (3 PR 분할)
7. G.6: P1-2 정적분석 병렬화 (별도 Phase)

## 감사 메타데이터

- **에이전트 수:** 14 (Round 1·2·3 각 5·5·4)
- **감사 날짜:** 2026-04-24
- **CI 실측 수치:** 1293 passed (run #24889251990)
- **후속 Phase:** G (즉시 실행), H (P2 이슈, SonarCloud 템플릿 파싱)
