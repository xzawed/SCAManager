## 스키마 변경 절차

1. 모델을 쓴다 — `src/models/<name>.py`, `Base` 상속, `__tablename__` 명시. 부분 인덱스는 `postgresql_where` 로 선언한다.
2. 신규 모델 파일이면 `alembic/env.py::from src.models.repository import Repository` 의 import 목록에 추가한다. 빠지면 autogenerate 가 그 테이블에 `drop_table` 을 만든다.
3. 초안을 만든다 — `alembic revision --autogenerate -m "설명"` (`make revision m="..."`).
4. 생성 파일을 `alembic/versions/NNNN_<slug>.py` 로 옮기고 `revision = "NNNN"`, `down_revision` = 직전 번호로 고친다(현재 head `0045`).
4-1. 기존 테이블에 `nullable=False` 컬럼을 넣으면 `server_default` 를 함께 준다 —
   행이 있는 운영 테이블에서 pre-deploy 의 `alembic upgrade head` 가 실패한다.
   SQLite 단위 테스트는 `create_all` 이라 `add_column` 을 안 돌리고 CI PG 는 빈 DB 라
   **이 실패는 운영에서만 난다**.
5. PG 전용 DDL 은 `if not is_postgresql(op.get_bind()): return` 뒤에 둔다 (`from src.shared.alembic_dialect import is_postgresql`) — SQLite 단위 테스트가 같은 파일을 실행한다.
6. 신규 테이블이면 아래 RLS 3종을 같은 마이그레이션에 넣고 `src/services/saas_service.py::_RLS_MATRIX:` `_RLS_MATRIX` 에 등재한다.
7. `downgrade()` 를 역순으로 쓴다 — 정책 DROP → 제약 → 인덱스 → 테이블.
8. 신규 모델이면 모델 목록 개수 상수 2곳을 함께 올린다 — `tests/unit/test_migration_completeness.py::_REGISTERED_MODELS =` · `tests/unit/migrations/test_orm_alembic_parity.py::_REGISTERED_MODEL_MODULES =`.

## 신규 테이블 RLS

```python
op.execute("ALTER TABLE t ENABLE ROW LEVEL SECURITY;")
op.execute("ALTER TABLE t FORCE ROW LEVEL SECURITY;")
op.execute("""
CREATE POLICY t_user_isolation ON t FOR ALL
USING (repo_id IN (SELECT id FROM repositories
  WHERE user_id IS NULL
     OR user_id = NULLIF(current_setting('app.user_id', true), '')::integer));
""")
```

`user_id IS NULL` 절을 빼면 legacy 행이 조회에서 사라진다. FORCE 를 빼면 bijection 가드가 fail 한다. downgrade 는 `DROP POLICY IF EXISTS`.

## 저장소 계층

`src/repositories/<name>_repo.py` 에 모듈 함수로 쓴다 — 클래스 없음, 첫 인자 `db: Session`. `__init__.py` 는 빈 파일로 둔다. 세션은 `src/database.py` — 웹 `get_db()`, 백그라운드 `WorkerSessionLocal`. 웹 경로만 쿼리마다 `SET LOCAL app.user_id` 를 발화한다.

## 검증

```
py -3 -m pytest tests/unit/migrations tests/unit/test_migration_completeness.py tests/unit/test_rls_matrix_completeness.py
```

`DATABASE_URL_FALLBACK` 이 설정돼 있으면 그 DB 에도 같은 `alembic upgrade head` 를
손으로 돌린다 — pre-deploy 는 primary 만 올리는데 `FailoverSessionFactory` 가 장애 시
그쪽으로 전환한다.

실 PG upgrade→downgrade 왕복과 ORM↔스키마 대조는 CI `pg-concurrency` job 만 돈다. PG 전용 테스트를 추가하면 그 job 의 실행 목록에 등재해야 수집된다 — 빠뜨리면 `tests/unit/scripts/test_ci_wires_every_pg_gated_test.py` 가 red 로 잡는다. 로컬에서 돌리려면 `DATABASE_URL_TEST_POSTGRES` 를 설정한다(`DATABASE_URL` 은 conftest 가 sqlite 로 덮는다).

## 적용

- 수동 — `alembic upgrade head` (`make migrate`)
- 배포 — `railway.toml::preDeployCommand =` `preDeployCommand`
- 기동 — `src/main.py::def _run_migrations` lifespan 이 30초 타임아웃으로 실행. 실패해도 기본은 기동, `STRICT_MIGRATION=true` 면 기동 거부.
- 대상 URL — `MIGRATION_DATABASE_URL` 우선, 없으면 `DATABASE_URL` (`src/config.py::def effective_migration_url`).

## 롤백

```bash
py -3 -m alembic downgrade -1          # 한 단계
py -3 -m alembic downgrade <revision>  # 특정 revision
```

`alembic/versions/` 의 기존 파일은 수정하지 않는다 — 되돌릴 일은 **새 revision 으로 전진**한다.
운영에서 pre-deploy 의 `alembic upgrade head` 가 실패하면 Railway 에서 **이전 배포를 재배포**해
서비스를 되돌린 뒤 downgrade 를 판단한다(실패한 배포는 트래픽을 받지 않는다).
