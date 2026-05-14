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
- 🔴 **RailwayDeployEvent nested 구조**: `src/railway_client/models.py` 의 `RailwayDeployEvent` 는 3-그룹 nested dataclass — `event.project.project_id`, `event.commit.commit_sha` 등 sub-dataclass 경로로 접근. 평면 접근 (`event.project_id`) 은 2026-04-22 이후 제거됨.
- **golangci-lint go.mod 자동생성**: `_GolangciLintAnalyzer.run()` 은 tmp_path 에 `go.mod` 가 없으면 `_ensure_go_mod()` 로 최소 모듈 정의 (`module tempmod\n\ngo 1.21\n`) 를 자동 생성.
- 🔴 **race-recovery 시그널 컨벤션**: 파이프라인 내 race recovery 분기는 `result_dict is None` 을 시그널로 사용. 호출자는 `if result_dict is None: skip notify` 로 명시적 처리.
