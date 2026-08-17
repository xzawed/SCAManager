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

> **`make` 이 없는 머신** — 이 리포의 개발 PC 포함(`make --version` → `command not found` 실측).
> `make migrate` = `alembic upgrade head` (`Makefile:126`) ·
> `make revision m="설명"` = `alembic revision --autogenerate -m "설명"` (`Makefile:146`).

---

## 신규 스키마 변경 절차 (개발 흐름)

1. `src/models/*.py`에서 ORM 모델 변경 (Column 추가/수정/삭제)
2. `make revision m="변경 설명"` — `alembic/versions/NNNN_*.py` 마이그레이션 파일 자동 생성
3. 생성된 파일의 `upgrade()` / `downgrade()` 함수 검토:
   - PostgreSQL 전용 DDL(인덱스, RLS 등)은 `is_postgresql(op.get_bind())` 분기 추가 (`src/shared/alembic_dialect.py` 참조)
   - SQLite에서는 `batch_alter_table` 패턴 사용 금지 (신규 파일 기준) — 상세: `.claude/rules/db.md`
4. `make migrate` — 로컬 DB에 적용
5. `py -3 -m pytest tests/unit` — 단위 테스트 **전체** 통과 확인 (6-step ②).
   `make test` 는 `python -m pytest tests/ -q` 라 `tests/integration` 까지 돈다 (`Makefile:26`).
6. PR 머지 후 운영 환경 자동 적용 (아래 "Railway 운영 환경" 절 참조)

> **🔴 주의**: ORM 컬럼 추가 후 `make revision` 없이 배포하면 운영 500 에러 발생.
> 단위 테스트는 in-memory SQLite(`Base.metadata.create_all`)로 ORM 정의 그대로 테이블을
> 만들기 때문에 마이그레이션 파일이 없어도 테스트가 통과한다.
> 전례: `leaderboard_opt_in` 컬럼.

---

## Railway 운영 환경 마이그레이션

Railway 마이그레이션 게이트는 **2층**이다.

1. **1차 = 실게이트** — `railway.toml` 의 `preDeployCommand = "alembic upgrade head"`.
   새 컨테이너가 트래픽을 받기 전에 돌고 **실패하면 배포가 중단**된다(loud-fail).
   🔴 Railway 대시보드 Settings→Deploy→Pre-deploy Command 는 **빈 값**으로 둔다
   (단일 출처 = `railway.toml`. 사유와 2026-06-15 전례는 그 파일 `[deploy]` 주석).
2. **2차 = 멱등 중복** — `src/main.py:221` 의 `lifespan` 이 `_run_migrations()` →
   `alembic upgrade head` 를 실행한다 (`src/main.py:225` · timeout 30초).

**PR 머지 → 자동 재배포 → pre-deploy 마이그레이션 → 컨테이너 기동 → lifespan 재확인** 흐름.

수동 실행이 필요한 경우:

```bash
railway run alembic upgrade head
```

> **헬스체크**: `GET /health` → `{"status":"ok"}` (`src/main.py:378`).
> 🔴 **lifespan 마이그레이션 실패는 기본값에서 앱을 막지 않는다** — `STRICT_MIGRATION=false`(기본,
> `src/config.py:87`)면 오류를 로그에 남기고 그대로 기동하고, `true` 면 실패·timeout 시 기동을
> 거부한다 (`src/main.py:231` · `:243`). Railway 는 1차 pre-deploy 가 막아 주지만
> **온프레미스·비-Railway 는 lifespan 이 유일 게이트**다 (`docs/reference/env-vars.md` §STRICT_MIGRATION).
> 헬스체크가 200을 반환하더라도 배포 로그에서 alembic 오류를 직접 확인할 것.

---

## Supabase → 온프레미스 PostgreSQL 전환

`src/database.py`와 `src/config.py`는 URL 기반 자동 분기로 두 환경을 모두 지원한다.
아래 절차로 전환한다.

> **주의**: 같은 이전을 [`onpremise-migration-guide.md`](onpremise-migration-guide.md) §4 가
> `pg_dump --format=custom` + `pg_restore` 조합으로도 서술한다(이 문서는 plain SQL + `psql`).
> **두 문서의 절차를 섞지 말고 한 쪽을 끝까지 따를 것.**

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

## 마이그레이션 파일 확인 (`alembic/versions/`)

```bash
# 현재 head revision
py -3 -m alembic heads

# 전체 파일 목록 (파일명 접두 숫자 = 적용 순서)
ls alembic/versions/

# 각 파일의 목적 — 파일 최상단 docstring 이 정본이다
head -3 alembic/versions/0045_analysis_attempts.py
```

> 🔴 **여기에 손유지 목록을 두지 않는다.** 2026-05-17 ~ 2026-08-17 이 자리에는 41행짜리
> `파일명 | 내용` 표가 있었다. 그 표가 중간 revision 에서 끝나 head 를 오인하게 만든 것이
> 적발돼 「이 표는 정본이 아니다」라는 경고가 덧붙었고, 결국 표 자체를 퇴역시켰다.
> 2026-08-17 실측: 표에 개별 등재된 41개 파일명은 디스크와 100% 일치했으나(45개 중 0042~0045 는
> 이미 와일드카드 한 행으로 뭉뚱그려져 있었다), 각 행의 설명은 해당 파일 docstring 의 축약본이라
> **고유 계약이 0** 이었다(45개 전 파일이 실질 docstring 첫 줄 보유). 손유지 표는 drift 표면만 남긴다.

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| 서버 시작 시 `OperationalError: no such column` | ORM 변경 후 마이그레이션 미실행 | `alembic upgrade head` (= `make migrate`) |
| `Target database is not up to date.` (`revision --autogenerate` 시) | DB 의 현재 revision 이 script head 와 다름 | `alembic upgrade head` 후 재실행 |
| `Multiple head revisions are present` | 브랜치 병합으로 head 가 2개 이상 | `alembic merge heads` 로 merge revision 생성 |
| `postgres://` URL 연결 실패 | 일부 라이브러리가 `postgres://` 미지원 | `src/config.py`가 자동 변환 — 직접 수정 불필요 |
| Railway 배포 후 500 에러 | pre-deploy 마이그레이션 실패 또는 lifespan timeout(30초) | Railway 배포 로그의 **pre-deploy 단계**부터 alembic 오류 확인 |
| Supabase 연결 시 SSL 오류 | `sslmode=require` 미설정 | `src/config.py:212` 는 **hostname 이 `.supabase.co` / `.supabase.com`(pooler) 로 끝날 때만** 자동 부착한다 — 호스트명 확인. URL query 에 `sslmode` 가 이미 있으면 덮어쓰지 않는다 |
| `batch_alter_table` 관련 오류 (PG) | SQLite 전용 패턴 잘못 사용 | 신규 마이그레이션에서 `op.create_unique_constraint(...)` 직접 사용 |
| IPv6 연결 hang (Railway) | Railway 컨테이너 IPv6 아웃바운드 차단 | `.env`에 `DB_FORCE_IPV4=true` 설정 |

> **정정 (2026-08-17 실측)** — 이 표에 있던 두 행이 틀렸다.
> ① `` `SMTP_PORT=""` 설정 시 ValidationError → Railway Variables 에서 삭제 `` 행을 제거했다.
> 그 방어는 문서 신설(2026-05-17)보다 39일 앞선 `fccffd6c`(2026-04-08)에 이미 들어와 있었다 —
> `src/config.py:283` `coerce_smtp_port` 가 빈 문자열을 587 로 대체한다
> (`SMTP_PORT=""` 로 `Settings()` 기동 → `smtp_port == 587` 실측). **태어날 때부터 거짓이었다.**
> ② `Target database is not up to date` 행은 원인·해결이 뒤바뀌어 있었다(원인 「revision 충돌」,
> 해결 「`alembic merge heads`」). 그 문자열은 `alembic/autogenerate/api.py:591` 이
> **autogenerate 경로에서만** 던지며 multiple-head 와 무관하다 — multiple-head 는
> `alembic/script/base.py:270` 의 별개 메시지다. 두 증상을 각각 한 행으로 분리했다.

---

## 관련 문서

- [Railway 운영 가이드](railway.md)
- [환경변수 전체 목록](../reference/env-vars.md)
- [DB/마이그레이션 규칙](../../.claude/rules/db.md) — ORM 변경 시 체크리스트
- [운영 smoke check](operational-smoke-checks.md)
- [온프레미스 마이그레이션 가이드](onpremise-migration-guide.md) — §4 가 같은 Supabase→온프레미스
  이전을 `pg_dump --format=custom` + `pg_restore` 로 서술한다(이 문서는 plain SQL + `psql`)
