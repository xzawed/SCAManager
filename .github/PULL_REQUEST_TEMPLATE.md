## 요약

<!-- 변경 내용 1~3줄 -->

## 체크리스트

- [ ] `py -3 scripts/pre_push_gate.py` 통과 (CI 강제 가드 — 목록 정본은 그 파일)
- [ ] `py -3 -m pytest tests/unit` 전체 통과 (영역 서브셋 대체 금지)
- [ ] 신규 파일: `docs/architecture.md` `src/` 트리·핵심 데이터 흐름 + `.claude/rules/<area>.md`
- [ ] ORM 컬럼: `alembic/versions/` 마이그레이션 · `server_default` · downgrade→upgrade 왕복
- [ ] 수치 변경: `docs/STATE.md` 추적 불릿 → `py -3 scripts/check_docs_sync.py --fix`
- [ ] UI 변경: 4테마(dark/light/pastel/catppuccin) × 데스크탑/모바일 8조합 시각 확인

## 🔍 사용자 검증 필요

<!-- "CI/테스트 통과" 금지. 테스트가 증명할 수 없는 것 1~3개 -->
- [ ] {수기 확인 항목}

## ⚠️ 자율 판단 보고 (해당 시)

<!-- 해당 시 작성 · 없으면 삭제
## MCP 자율 실행
- 도구 + 영향 범위 / SELECT-only 자율 · 변경·PII = 사전 승인 여부:

## Grok claim-review
- session: <Grok sessionId>
- claim: <한 줄 요약>
- verdict: <SURVIVES 또는 BROKEN + 근거>
-->

🤖 Generated with [Claude Code](https://claude.com/claude-code)
