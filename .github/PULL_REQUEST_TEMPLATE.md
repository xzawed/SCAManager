## 변경 요약
<!-- 무엇을, 왜 변경했는지 1~3줄로 -->


## 체크리스트

### 기본
- [ ] `make test` 통과 (0 failed)
- [ ] `make lint` 통과 (pylint 10.00 · bandit HIGH 0)

### 신규 파일 추가 시 (없으면 이 섹션 전체 삭제)
- [ ] `CLAUDE.md` `src/` 트리 블록에 신규 파일 항목 추가
- [ ] `CLAUDE.md` `templates/` · `repositories/` · `services/` 카운트·목록 갱신 (해당 시)
- [ ] `docs/STATE.md` 그룹 이력에 신규 파일 표 추가

### ORM 컬럼 추가 시 (없으면 이 섹션 전체 삭제)
- [ ] `alembic/versions/` 마이그레이션 파일 생성 (`make revision m="설명"`)
- [ ] `server_default` 포함 여부 확인 (`nullable=False` 컬럼은 필수)
- [ ] `make migrate` 왕복 검증 (`downgrade -1` → `upgrade head`)
- [ ] `test_migration_completeness` CI 통과 확인

### 수치 변경 시 (없으면 이 섹션 전체 삭제)
- [ ] `docs/STATE.md` 헤더 수치 갱신
- [ ] `README.md` + `README.ko.md` 배지 갱신
