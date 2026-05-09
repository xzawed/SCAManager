---
description: 파이프라인 / 비즈니스 로직 작업 시 적용되는 SCAManager 코딩 규칙 (Codex용 — path-scoped)
paths:
  - "src/worker/pipeline.py"
  - "src/analyzer/**"
  - "src/scorer/**"
  - "src/webhook/**"
  - "src/gate/**"
---

# 파이프라인 / 비즈니스 로직 규칙 (Codex)

- **멱등성**: `run_analysis_pipeline` 은 commit SHA 로 중복 체크 — 같은 SHA 는 재분석 건너뜀.
- **PR action 필터링**: `pull_request` 이벤트 중 `opened`/`synchronize`/`reopened` 만 처리.
- **None-able 키 정규화**: `(data.get("head_commit") or {}).get(...)` 패턴 필수 (브랜치 삭제 push 대응).
- **Analyzer Registry**: 신규 도구 추가 시 3단계 — ① `tools/` 클래스 + `register()` ② `analyze_file()` import ③ `SUPPORTED_LANGUAGES` 선언.
- **category 기반 점수**: `AnalysisIssue.category` ("code_quality"|"security") 기준. tool 이름 무관.
- **봇 PR 루프 방지**: `pr_head_ref` 가 `_BOT_PR_PREFIXES` (`claude-fix/`, `bot/`, `renovate/`, `dependabot/`) 시작 시 `create_issue` 건너뜀.
- **AI 리뷰 JSON 파싱**: `re.search` 로 코드 블록 내 JSON 만 추출 (설명 텍스트 앞에 붙을 수 있음).
- **GateDecision upsert**: `save_gate_decision()` 은 동일 `analysis_id` 존재 시 UPDATE, 없으면 INSERT.
- **build_analysis_result_dict**: `src/worker/pipeline.py` 모듈 레벨 함수 — `score`·`grade` 필드 포함. pipeline 과 hook.py 양쪽에서 사용.
