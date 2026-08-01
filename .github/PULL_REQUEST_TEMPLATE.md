## Summary

<!-- 변경 내용을 1-3줄로 요약 -->

## 변경 내용

<!-- 구체적인 변경 사항 -->

## 테스트

<!-- 테스트 방법 및 결과 -->

## 체크리스트

### 기본
<!-- 🔴 `make lint` 는 게이트가 아닙니다 — 세 린터를 `|| true` 로 삼켜 항상 exit 0 이라 근거가 될 수
     없습니다(위반 열람 전용). 로컬 검증 기준은 `py -3 scripts/pre_push_gate.py --full` 이고,
     최종 근거는 CI job 결과입니다. `make gate` 는 편의용이며 13 가드를 돌리지 않습니다. -->
- [ ] `py -3 scripts/pre_push_gate.py` 통과 (CI 강제 가드 13종 — repo-integrity 9 + PR-diff 4)
- [ ] `py -3 -m pytest tests/unit` 전체 통과 (영역 서브셋 대체 금지)

### 신규 파일 추가 시 (없으면 이 섹션 전체 삭제)
- [ ] `docs/architecture.md` `src/` 트리 + `핵심 데이터 흐름`에 신규 파일·경로 반영
- [ ] `docs/architecture.md` `templates/` · `repositories/` · `services/` · `models/` · `analyzer/io/tools/` 카운트·목록 갱신 (해당 시)
- [ ] 해당 영역 `.claude/rules/<area>.md` 본문 갱신 (CLAUDE.md 영역 매트릭스 참조)

### ORM 컬럼 추가 시 (없으면 이 섹션 전체 삭제)
- [ ] `alembic/versions/` 마이그레이션 파일 생성 (`make revision m="설명"`)
- [ ] `server_default` 포함 여부 확인 (`nullable=False` 컬럼은 필수)
- [ ] 왕복 검증 (`alembic downgrade -1` → `alembic upgrade head` — `make migrate` 는 upgrade 만 한다)
- [ ] `test_migration_completeness` CI 통과 확인

### 수치 변경 시 (없으면 이 섹션 전체 삭제)
- [ ] `docs/STATE.md` 종합 수치 + 추적셀 시작 헤더 (훅이 대조하는 지점 2곳)
- [ ] `README.md` + `README.ko.md` 배지 갱신

## 🔍 사용자 검증 필요

<!-- 🔴 "CI/테스트 통과" 금지 (정책 2) — 위 §기본이 이미 담당합니다. 테스트가 증명할 수 없는 것만
     1~3개 (예: Railway 배포 후 /health · Telegram 실제 발송 도달 · OAuth 로그인 왕복) -->
- [ ] {수기 확인 항목}
- [ ] (UI 변경 시) 4테마(dark/light/pastel/catppuccin) × 2뷰포트(데스크탑/모바일) 8조합 시각 확인

<!-- MCP 자율 실행이 있었으면 아래 섹션을 작성하세요 (정책 12/3). 없으면 삭제. -->
<!--
## MCP 자율 실행 결과 (정책 12)

- 호출 도구 + 영향 범위: {예: Supabase execute_sql SELECT — RLS 실측, PII 0건}
- SELECT-only 자율 / 변경·PII SELECT = 사용자 사전 승인 여부: {}
-->

<!-- "무엇을 닫았다"는 단언이 제목·본문·PR 범위 커밋에 있으면 CI `repo-integrity` 가 아래 3줄의
     **값**을 요구하고, 없으면 PR 을 실패시킵니다 (정책 19). 해당 없으면 삭제. -->
<!--
## Grok claim-review

- session: <Grok sessionId>
- claim: <한 줄 요약>
- verdict: <SURVIVES 또는 BROKEN + 근거>
-->

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

🤖 Generated with [Claude Code](https://claude.com/claude-code)
