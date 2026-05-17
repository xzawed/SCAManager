# DB 마이그레이션 가이드

> 이 문서는 SCAManager의 DB 마이그레이션 절차를 설명한다. Alembic 기반이며
> Supabase, 온프레미스 PostgreSQL, Railway PostgreSQL, SQLite(테스트)를 모두 지원한다.

---

## 환경별 DATABASE_URL 형식

| 환경 | DATABASE_URL 예시 |
|------|-----------------|
| Railway PostgreSQL | `postgresql://user:pass@host:5432/db` (플러그인 자동 주입) |
| Supabase | `postgresql://postgres:[pass]@db.[project].supabase.co:5432/postgres?sslmode=require` |
| 온프레미스 PostgreSQL | `postgresql://user:pass@localhost:5432/scamanager` |
| 로컬 개발 (SQLite) | `sqlite:///./scamanager.db` |
| 테스트 | `sqlite:///:memory:` (conftest.py 자동 주입 — `.env` 파일 불필요) |

> **주의**: `postgres://` 스킴은 `src/config.py`의 `fix_postgres_url` validator가
> 자동으로 `postgresql://`로 변환한다. Supabase URL에는 `sslmode=require`도 자동 추가된다.
> 직접 수정은 불필요하다.

---

## 기본 마이그레이션 명령

```bash
# DB 마이그레이션 적용 (alembic upgrade head)
make migrate

# 새 마이그레이션 파일 생성 (ORM 변경 후 반드시 실행)
make revision m="변경 내용 한 줄 설명"

# 현재 revision 상태 확인
alembic current

# revision 이력 확인
alembic history --verbose
```

---

## 신규 스키마 변경 절차 (개발 흐름)

1. `src/models/*.py`에서 ORM 모델 변경 (Column 추가/수정/삭제)
2. `make revision m="변경 설명"` — `alembic/versions/NNNN_*.py` 마이그레이션 파일 자동 생성
3. 생성된 파일의 `upgrade()` / `downgrade()` 함수 검토:
   - PostgreSQL 전용 DDL(인덱스, RLS 등)은 `is_postgresql(op.get_bind())` 분기 추가 (`src/shared/alembic_dialect.py` 참조)
   - SQLite에서는 `batch_alter_table` 패턴 사용 금지 (신규 파일 기준) — 상세: `.claude/rules/db.md`
4. `make migrate` — 로컬 DB에 적용
5. `make test` — 전체 테스트 통과 확인
6. PR 머지 후 운영 환경 자동 적용 (아래 "Railway 운영 환경" 절 참조)

> **🔴 주의**: ORM 컬럼 추가 후 `make revision` 없이 배포하면 운영 500 에러 발생.
> 단위 테스트는 in-memory SQLite(`Base.metadata.create_all`)로 ORM 정의 그대로 테이블을
> 만들기 때문에 마이그레이션 파일이 없어도 테스트가 통과한다.
> 전례: `leaderboard_opt_in` 컬럼 (PR #72·#74, 2026-04-26).

---

## Railway 운영 환경 마이그레이션

Railway에서는 앱 시작 시 `src/main.py`의 `lifespan` 함수가 자동으로
`_run_migrations()` → `alembic upgrade head`를 실행한다 (timeout: 30초).

**PR 머지 → Railway 자동 재배포 → lifespan 시작 → 마이그레이션 자동 적용** 흐름.

수동 실행이 필요한 경우:

```bash
railway run alembic upgrade head
```

> **헬스체크**: `GET /health` → `{"status":"ok"}`. 마이그레이션 실패 시 앱은 시작되지만
> Railway 로그에 오류가 기록된다. 배포 후 헬스체크가 200을 반환하더라도 Railway 빌드 로그에서
> alembic 오류를 직접 확인할 것.

---

## Supabase → 온프레미스 PostgreSQL 전환

`src/database.py`와 `src/config.py`는 URL 기반 자동 분기로 두 환경을 모두 지원한다.
아래 절차로 전환한다.

### 1. 신규 PostgreSQL DB 접속 확인

```bash
psql "postgresql://user:pass@new-host:5432/scamanager" -c "SELECT version();"
```

### 2. Supabase 데이터 덤프

```bash
pg_dump "postgresql://postgres:[pass]@db.[project].supabase.co:5432/postgres" \
  --no-owner --no-acl \
  -f dump.sql
```

### 3. 신규 DB에 복원 (두 가지 방법)

**방법 A — 마이그레이션으로 스키마 생성 후 데이터만 별도 복원**

```bash
# 스키마만 생성
DATABASE_URL="postgresql://user:pass@new-host:5432/scamanager" alembic upgrade head

# 데이터만 복원 (--data-only)
pg_dump "postgresql://postgres:[pass]@db.[project].supabase.co:5432/postgres" \
  --no-owner --no-acl --data-only -f data_only.sql
psql "postgresql://user:pass@new-host:5432/scamanager" < data_only.sql
```

**방법 B — 전체 dump 복원 (스키마 + 데이터)**

```bash
psql "postgresql://user:pass@new-host:5432/scamanager" < dump.sql
# 복원 후 alembic revision 상태 동기화
DATABASE_URL="postgresql://user:pass@new-host:5432/scamanager" alembic stamp head
```

### 4. 검증

```bash
# alembic revision 확인
DATABASE_URL="postgresql://user:pass@new-host:5432/scamanager" alembic current

# DB 연결 및 테이블 확인
psql "postgresql://user:pass@new-host:5432/scamanager" \
  -c "\dt" \
  -c "SELECT count(*) FROM repositories;"
```

### 5. .env 업데이트 및 재시작

```bash
# .env 수정
DATABASE_URL=postgresql://user:pass@new-host:5432/scamanager

# DB_FORCE_IPV4, DB_SSLMODE 환경에 맞게 조정
DB_FORCE_IPV4=false   # 온프레미스 로컬 → false, Railway 환경 → true
DB_SSLMODE=           # 미설정 시 PostgreSQL 기본값 (연결 암호화 없음)

# 서버 재시작
make run
```

---

## DB Failover (Primary → Fallback 자동 전환)

`DATABASE_URL_FALLBACK` 설정 시 `src/database.py`의 `FailoverSessionFactory`가
Primary `OperationalError` 발생 시 Fallback DB로 자동 전환한다.

```bash
# .env 설정 예시 — Supabase를 Fallback으로 사용
DATABASE_URL=postgresql://user:pass@on-premise-host:5432/scamanager
DATABASE_URL_FALLBACK=postgresql://postgres:[pass]@db.[project].supabase.co:5432/postgres
DB_FAILOVER_PROBE_INTERVAL=30  # Primary 복구 확인 주기 (초)
```

- `DATABASE_URL_FALLBACK` 미설정(빈 값)이면 단일 엔진 모드 — Failover 비활성
- Primary 복구 시 `_probe_primary_loop` daemon 스레드가 자동 감지 후 복귀
- 현재 활성 DB 확인: `SessionLocal.active_db` → `"primary"` 또는 `"fallback"`

---

## 롤백 절차

```bash
# 한 단계 롤백
alembic downgrade -1

# 특정 revision으로 롤백
alembic downgrade <revision_id>

# 현재 revision 확인
alembic current

# 전체 이력 확인
alembic history --verbose
```

> **🔴 주의**: `alembic/versions/` 파일은 수정 금지. 롤백 후 재적용이 필요하면
> 새 마이그레이션 파일로 작성한다 (append-only 원칙).
> `alembic/versions/0005_add_users_and_user_id.py`,
> `0006_phase8b_github_oauth.py`는 이미 프로덕션에 적용된 이력 마이그레이션이므로 수정 금지.

---

## 마이그레이션 파일 목록 (`alembic/versions/`)

| 파일명 | 내용 |
|--------|------|
| `3b8216565fed_create_repositories_and_analyses_tables.py` | 초기 테이블 생성 |
| `0002_phase3_add_repo_config_gate_decision.py` | RepoConfig, GateDecision 테이블 |
| `0003_drop_analysis_rules.py` | analysis_rules 컬럼 제거 |
| `0004_add_auto_merge.py` | auto_merge 필드 추가 |
| `0005_add_users_and_user_id.py` | User 모델, user_id FK |
| `0006_phase8b_github_oauth.py` | GitHub OAuth 전환 |
| `0007_add_notification_channels.py` | 알림 채널 설정 필드 |
| `0008_add_commit_message.py` | commit_message 컬럼 |
| `0009_add_hook_token.py` | hook_token 컬럼 |
| `0010_pr_gate_three_options.py` | Gate 3-option 확장 |
| `0011_add_commit_comment_and_create_issue.py` | commit comment, issue 생성 옵션 |
| `0012_add_railway_fields.py` | Railway 배포 관련 필드 |
| `0013_add_analysis_feedbacks.py` | AnalysisFeedback 테이블 |
| `0014_add_merge_attempts.py` | MergeAttempt 테이블 |
| `0015_add_auto_merge_issue_on_failure.py` | 실패 시 issue 자동 생성 옵션 |
| `0016_add_unique_constraint_analyses_repo_sha.py` | analyses 유니크 제약 |
| `0017_add_user_telegram_id.py` | telegram_id 컬럼 |
| `0018_add_analysis_author.py` | author_login 컬럼 |
| `0019_add_repo_config_leaderboard_opt_in.py` | leaderboard_opt_in 컬럼 |
| `0020_add_merge_retry_queue.py` | MergeRetryQueue 테이블 |
| `0021_add_analyses_created_at_index.py` | created_at 인덱스 |
| `0022_add_merge_attempt_lifecycle.py` | MergeAttempt lifecycle 필드 |
| `0023_add_composite_indexes.py` | 복합 인덱스 추가 |
| `0024_gate_decisions_cascade.py` | GateDecision FK ondelete CASCADE |
| `0025_drop_repo_config_leaderboard_opt_in.py` | leaderboard_opt_in 제거 |
| `0026_supabase_rls_policies.py` | Supabase RLS 정책 (PG 전용) |
| `0027_add_security_alert_process_log.py` | 보안 알림 처리 로그 |
| `0028_add_insight_narrative_cache.py` | Insight narrative 캐시 |
| `0029_rls_5_missing_tables.py` | RLS 누락 테이블 5개 추가 |
| `0030_add_i18n_columns.py` | 다국어 지원 컬럼 |
| `0031_repo_insights_cache.py` | Repo insights 캐시 |

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 서버 시작 시 `OperationalError: no such column` | ORM 변경 후 마이그레이션 미실행 | `make migrate` |
| `Target database is not up to date` | alembic revision 충돌 (브랜치 병합 등) | `alembic merge heads` 후 새 merge revision 생성 |
| `postgres://` URL 연결 실패 | 일부 라이브러리가 `postgres://` 미지원 | `src/config.py`가 자동 변환 — 직접 수정 불필요 |
| Railway 배포 후 500 에러 | 마이그레이션 실패 (timeout 30초 초과 등) | Railway 빌드 로그에서 alembic 오류 확인 |
| Supabase 연결 시 SSL 오류 | `sslmode=require` 미설정 | `src/config.py`가 자동 추가 — URL에 `supabase.co` 포함 확인 |
| `batch_alter_table` 관련 오류 (PG) | SQLite 전용 패턴 잘못 사용 | 신규 마이그레이션에서 `op.create_unique_constraint(...)` 직접 사용 |
| IPv6 연결 hang (Railway) | Railway 컨테이너 IPv6 아웃바운드 차단 | `.env`에 `DB_FORCE_IPV4=true` 설정 |
| `SMTP_PORT=""` 설정 시 ValidationError | pydantic이 빈 문자열을 int로 변환 실패 | Railway Variables에서 SMTP_PORT 삭제 또는 숫자로 설정 |

---

## 관련 문서

- [Railway 운영 가이드](railway.md)
- [환경변수 전체 목록](../reference/env-vars.md)
- [DB/마이그레이션 규칙](.claude/rules/db.md) — ORM 변경 시 체크리스트
- [운영 smoke check](operational-smoke-checks.md)
