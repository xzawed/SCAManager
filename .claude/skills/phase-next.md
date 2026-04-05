---
description: 다음 Phase 구현 브레인스토밍 및 계획 수립 시작
---

현재 Phase 완료 상태를 확인하고, 다음 Phase 구현을 위한 브레인스토밍과 계획 수립을 시작한다.

## Phase 현황 확인

| Phase | 내용 | 상태 |
|-------|------|------|
| Phase 1 | Webhook → 정적 분석 → Telegram 알림 | ✅ 완료 |
| Phase 2 | Claude AI 리뷰 + 커밋 메시지 점수 + GitHub PR Comment | 🔜 다음 |
| Phase 3 | PR Gate Engine (자동/반자동) + Config Manager | 예정 |
| Phase 4 | Dashboard API + Web UI | 예정 |
| Phase 5 | n8n 연동 + 통계 고도화 | 예정 |

## Phase 2 주요 작업 (다음 단계)

설계 문서: `docs/superpowers/specs/2026-04-05-scamanager-design.md`

구현 대상:
1. **Claude AI 리뷰어** (`src/analyzer/ai_review.py`)
   - Anthropic SDK로 diff + 커밋 메시지 전달
   - 구조화된 JSON 응답 파싱 (점수, 개선사항, 방향성)

2. **커밋 메시지 점수** (`src/scorer/calculator.py` 수정)
   - 커밋 메시지 품질 20점 항목 실제 구현

3. **GitHub PR Comment** (`src/notifier/github_comment.py`)
   - PyGithub로 PR에 상세 분석 결과 마크다운 코멘트

4. **병렬 실행** (`src/worker/pipeline.py` 수정)
   - `asyncio.gather`로 정적분석 + AI 리뷰 병렬 처리

## 실행

이 스킬을 호출하면 `superpowers:brainstorming` 스킬을 이용해 Phase 2 구현을 시작한다.
설계 문서와 Phase 1 코드를 참고하여 Phase 2 구현 계획을 수립한다.
