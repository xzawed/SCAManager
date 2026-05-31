## Summary

<!-- 변경 내용을 1-3줄로 요약 -->

## 변경 내용

<!-- 구체적인 변경 사항 -->

## 테스트

<!-- 테스트 방법 및 결과 -->

## 체크리스트

### 기본
- [ ] `make test` 통과 (0 failed)
- [ ] `make lint` 통과 (pylint 10.00 · bandit HIGH 0)

### 신규 파일 추가 시 (없으면 이 섹션 전체 삭제)
- [ ] `docs/architecture.md` `src/` 트리 블록에 신규 파일 항목 추가
- [ ] `docs/architecture.md` `templates/` · `repositories/` · `services/` 카운트·목록 갱신 (해당 시)
- [ ] `docs/STATE.md` 그룹 이력에 신규 파일 표 추가

### ORM 컬럼 추가 시 (없으면 이 섹션 전체 삭제)
- [ ] `alembic/versions/` 마이그레이션 파일 생성 (`make revision m="설명"`)
- [ ] `server_default` 포함 여부 확인 (`nullable=False` 컬럼은 필수)
- [ ] `make migrate` 왕복 검증 (`downgrade -1` → `upgrade head`)
- [ ] `test_migration_completeness` CI 통과 확인

### 수치 변경 시 (없으면 이 섹션 전체 삭제)
- [ ] `docs/STATE.md` 헤더 수치 갱신
- [ ] `README.md` + `README.ko.md` 배지 갱신

## 🔍 사용자 검증 필요

- [ ] CI 통과 확인
- [ ] (UI 변경 시) 4테마(dark/light/pastel/catppuccin) × 2뷰포트(데스크탑/모바일) 8조합 시각 확인

<!-- UI/CSS/HTML 변경 PR은 아래 8조합 체크리스트를 작성해 주세요 (정책 11) -->
<!--
| 테마 | 데스크탑 | 모바일 |
|------|---------|--------|
| dark | [ ] | [ ] |
| light | [ ] | [ ] |
| pastel | [ ] | [ ] |
| catppuccin | [ ] | [ ] |
-->

## ⚠️ 자율 판단 보고 (정책 3, 해당 시)

<!-- Claude가 위임받은 작업 중 자율 판단한 항목 명시 (없으면 이 섹션 삭제) -->

## 🔍 Codex 검증 의뢰 (push 전, 정책 18)

- [ ] Codex 검증 의뢰 완료 — push 전 Codex OK 회신 대기 중
- [ ] (예외) Codex 샌드박스 오류 시 Claude 직접 검증 대체 — 사유 명시

🤖 Generated with [Claude Code](https://claude.com/claude-code)
