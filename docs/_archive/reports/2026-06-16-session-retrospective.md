# 2026-06-16 세션 회고 — Railway follow-up (#906~#910 + RLS Phase 4 step 0)

> 정책 8(5+1 다중 에이전트 깊은 회고) + 정책 9(Claude 자유 발언). 본 문서는 시점 스냅샷 — 실시간 상태는 [STATE.md](../../STATE.md).

## 1. 회고 대상

2026-06-15 Railway↔Supabase prod 다운(pooler host aws-0→aws-1) RESOLVED 후의 **follow-up 실행 세션**. 머지된 5 PR:

| PR | commit | 내용 |
|----|--------|------|
| #906 | 36bc72c | fix(deploy): Railway pre-deploy = `alembic upgrade head` (railway.toml preDeployCommand) |
| #907 | dffd0aa | docs: Railway↔Supabase 연결 invariants + RLS Phase 4 마이그레이션 credential 게이트 문서화 |
| #908 | 6d97cef | feat(db): `MIGRATION_DATABASE_URL` (owner role) — RLS Phase 4 "두 번째 벽" |
| #909 | 8f4aa55 | docs: sync — STATE/cycle-history/README 배지 + 게이트 "✅ #908 구현" flip |
| #910 | 7cf7ff3 | docs: sync — RLS Phase 4 step 0 운영 완료 반영 |

운영 milestone: RLS Phase 4 step 0 운영 완료 (alembic 0038→0041, RLS FORCE 11/11, MCP read-only 실측). 접속 role 여전히 postgres/BYPASSRLS = step 1/2 미전환(예상·안전).

## 2. 방법

workflow `wf_74404088` — 6 에이전트 = **5 도메인 병렬(코드/문서/프로세스/운영/테스트) + 1 cross-verify(적대 교차검증 + completeness critic)**. 각 에이전트 강제 조건: read-only · self-contained · `file:line` grep 실측 인용(정책 6) · P0/P1/P2 분류 · false-positive 회피 사례 명시.

- 13 finding(11 distinct, #518 은 3 도메인 수렴 보고).
- cross-verify: **8 TRUE · 5 SEVERITY_ADJUST(전부 P1→P2) · 0 FALSE_POSITIVE**.
- 카운트 실측(정책 8 사이클 92): `pytest --collect-only` = 5106 total / 4952 unit / 154 integration — STATE/README 배지와 일치.

## 3. 확정 결함 — P0 0 · P1 1 · P2 10

| ID | 등급 | 결함 | 근거 | 처리 |
|----|------|------|------|------|
| DOC-1 | **P1** | architecture.md:27 config.py 설명이 #908 `effective_migration_url`/`MIGRATION_DATABASE_URL` 미반영 (6-step ⑥ 누락) | `git show --stat 6d97cef` = architecture.md 미변경 | **#914** |
| #518 | P2 | CodeQL `py/mixed-returns` open alert — #908 테스트 헬퍼 self-inflicted (#516/#517 계열) | `test_alembic_env_migration_url.py:47-48` | **#912** |
| CODE-2 | P2 | `_normalize_pg_url` supabase SSL이 `'supabase.co'` substring 의존 (pooler `.supabase.com` 우연 매칭) | config.py:153 | 백로그 |
| CODE-3 | P2 | online 마이그레이션 connect_args(IPv4/SSL) 행동 테스트 부재 | env.py:77-90 | 백로그 |
| PROC-1 | P2 | codex 입력 전달 + `git add -A` 임시파일 default 미codify | active.md narrative만 | **#913** |
| PROC-3 | P2 | `.gitignore` codex 임시파일(`.codex_*`) 가드 부재 | .gitignore:22-28 | **#913** |
| ops-DOC1 | P2 | railway.toml preDeployCommand는 config-as-code이나 대시보드 override drift 경로 잔존 | railway.toml:13-15 | 백로그(사용자 운영 closure) |
| DOC-2 | P2 | lifespan 마이그레이션은 #908 게이트 적용에도 silent-fail (Phase 4 재발방지 pre-deploy 단독 의존) | main.py:91-94,156-164 | 백로그(runbook 하드닝) |
| DOC-3 | P2 | MIGRATION_DATABASE_URL pooler 모드 caveat 미문서화 (DDL은 session 5432 > transaction 6543) | runbook §6:167 | 백로그(사용자 결정) |
| PROC-2 | P2 | 정책 9: 직전 wf3sn621a 회고 질문 2 사이클째 미회신 | outage memory:27 | 자유발언서 회신 수령("모두 OK") |
| TEST-2 | P2 | config 5 테스트는 effective_migration_url 정규화를 transitive로만 커버 (결함 아님, 선택 강화) | test_config.py:124-172 | 백로그(선택) |

**cross-verify completeness critic 신규 6건**: 단위 카운트 machine-verify 누락(→ 본 회고서 collect-only 실측 확정), 회고 후보 (b) 게이트 도입부 stale 은 이미 #908/#909 해소(캐리포워드 방지·FALSE_POSITIVE), #911(js-yaml) ↔ #518 트리거 commit 경계, Phase 4 cross-layer(hybrid session routing) 비간섭 미검증 등.

## 4. 잘된 점 (default 유지·강화)

- **#908 게이트 설계 정합** — `effective_migration_url = migration_database_url or database_url` 단일 결정점(env.py:38), offline/online/pre-deploy/lifespan 4경로 일관, 미설정 시 발효 0(비파괴), online 경로가 migration URL 자체에 IPv4/SSL 파생.
- **Codex mutual 2-layer ROI 실증** — 내부 5+1/3-agent(0 findings) 통과 후 Codex가 기술오류 6건 적발(DB_FORCE_IPV4 IPv6-only 무효·ENOTFOUND↔Supavisor 계층 ×4). 정책 18 §5 격리 가치 유지.
- **문서 정합** — README↔README.ko 5 배지 쌍 STATE 일치(`%2B` 통일)·STATE 4곳 sync·.codex/rules 미러 동기화.
- **PR 본문 무결성 100%** — 5 PR 본문 `@-` 소실 0 (2026-06-09 #838~845 사고 이후 `--body-file` 정착).
- **운영 규율** — PW 교체 비-AI 채널 보류 일관·MCP 테이블명 오타 자가교정(per-table breakdown authoritative).

## 5. Claude 자유 발언 (정책 9)

- **§1 바라는 점** — RLS Phase 4 step 1(PW 교체)~3 진입 시점/OAuth 전략 결정(High tier) 사용자 입력 필요. railway.toml ↔ 대시보드 drift closure(대시보드 Pre-deploy Command 비웠는지) 확인 요청.
- **§2 자성** — DOC-1(P1) 6-step ⑥ 누락(#908에서 db.md/env-vars/runbook은 갱신했으나 architecture.md만 빠뜨림). CodeQL #518 = self-inflicted 4번째 계열 — 신규 가드 헬퍼 작성 시 머지 전 로컬 CodeQL 룰 자가점검 default 미정착.
- **§3 필요** — Phase 4 step 1 OAuth 전략 결정 + secret rotate(F12) 우선순위.
- **§4 수정 제안** — (1) config.py 변경 시 architecture.md를 db.md/env-vars와 동일 묶음으로 (2) codex mutual 도구 codify(PROC-1/3) (3) py/mixed-returns 회피 패턴 메모리화.
- **🔍 회고 질문 회신** — 직전 wf3sn621a + 이번 세션 "다르게 결정했을 항목" → 사용자 **"모두 OK"**.

## 6. Option A follow-up 결과 (#912~#914)

사용자 결정 = Option A(의무+저위험). 전 PR Codex mutual 검증 후 push(정책 18).

- **#912** CodeQL #518 해소 — `pytest.fail`→`raise AssertionError` + `import pytest` 제거(`py/unused-import` #517 cascade 선제). Codex OK.
- **#913** codex mutual 운용 도구 default codify — active.md 정책 18 §codex 운용 + `.gitignore` `.codex_*` 가드. Codex **NG 1[POSIX-shell 한정 누락]→정정→OK**(정책 18 §3b 단일정답 — codify PR 자체에서 mutual 가치 실증).
- **#914** architecture.md(P1, DOC-1) + 본 회고 아카이브 + STATE/cycle-history sync.

카운트 불변(단위 4952·전체 5106·E2E 115·pylint 10.00).

## 7. 잔여 (사용자 운영 영역)

- #2 RLS Phase 4: step 1 PW 교체(SQL Editor 직접·Claude/MCP 금지) → step 2 URL 전환(`MIGRATION_DATABASE_URL`/`DATABASE_URL`/`DATABASE_URL_WORKER`) → step 3 검증. step 1 전 OAuth 전략 결정 의무(전원 로그인 장애 위험) + §6 pre-flight 로컬 secret-safe probe.
- secret rotate (F12, 낮은 긴급도).
- P2 백로그 7건(CODE-2/3·ops-DOC1·DOC-2/3·TEST-2) — 다음 사이클 우선순위 사용자 결정.
