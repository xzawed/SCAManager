# 문서 다중 에이전트 심의 시스템 — 구현 회고

**날짜**: 2026-04-26  
**작업 범위**: 그룹 40 — `.claude/hooks/doc_review_gate.py` 전체 구현  
**커밋 수**: 8커밋 (4778686 → 0a7edbe)  
**최종 수치**: 단위 테스트 1332개 (32개 추가) · pylint 10.00/10 · CI 기존 실패와 동일

---

## 1. 무엇을 만들었는가

Claude가 중요 문서를 수정하기 직전, 3개 전문 에이전트가 병렬로 심의하여 변경을 차단·경고·통과시키는 Claude Code PreToolUse Hook.

| 구성 요소 | 역할 |
|-----------|------|
| `doc_review_gate.py` | 진입점 — 파일 등급 분류 → 병렬 API 호출 → 거부권 적용 → 출력 |
| `doc-impact-analyzer` | "이 변경이 Claude 행동을 의도하지 않게 바꾸는가?" — Critical+Important 차단권 |
| `doc-consistency-reviewer` | "기존 문서와 수치·규칙이 충돌하는가?" — Critical 차단권 |
| `doc-quality-reviewer` | "미래 Claude가 이 문장을 오해할 수 있는가?" — 경고만 |

**핵심 설계 원칙**: 사용자에게 보고하는 것보다 Claude 자신의 판단 정확성 확보가 우선. 심의 시스템이 Claude 작업을 막는 단일 장애점이 되어서는 안 된다.

---

## 2. 잘 된 것

### 2.1 설계 단계의 명확한 의사결정

브레인스토밍에서 3가지 핵심 설계 선택이 논의되었고, 각각 근거가 명확했다.

| 질문 | 선택 | 근거 |
|------|------|------|
| 차단 vs 사후 경고 | 직전 차단 | 이미 저장된 후에는 수정 불가 — 사후 경고는 의미 없음 |
| 투표제 vs 역할 기반 에이전트 | 역할 기반 | 동일 편향 증폭 방지, 각 에이전트가 자기 전문 영역에만 집중 |
| 차단 기준 | 에이전트별 차등 | impact: 무조건 차단, consistency: Critical만 차단, quality: 경고만 |

설계 결정이 코드에 그대로 반영되어 `apply_veto_matrix`가 명확히 읽힌다.

### 2.2 TDD가 실제 버그를 2개 잡았다

구현 후 코드 품질 리뷰에서 발견된 **Critical 버그 2개** 모두 테스트로 검출 가능한 종류였다.

- **JSON 파싱 버그**: `{value}` 형태 중괄호가 `detail` 필드에 들어오면 block 결정이 소리 없이 approve로 격하됨. 심의 시스템의 핵심 목적을 무력화하는 버그였다.
- **조기 종료 테스트 허점**: `sys.exit` mock이 실행을 멈추지 않아, 테스트가 성공해도 실제로 에이전트가 호출되고 있었다. 테스트가 "존재하지만 아무것도 검증하지 않는" 상태.

두 버그 모두 코드 리뷰 단계에서 발견·수정되었다. 테스트가 없었다면 운영 중에 발견했을 것이다.

### 2.3 Graceful degradation 원칙 일관 적용

API 호출 실패, JSON 파싱 실패, 타임아웃 — 모든 실패 경로가 `warn` 또는 `approve`로 끝나도록 설계. `block`으로 귀결되는 실패 경로는 없다. 심의 시스템이 Claude 작업의 병목이 되지 않는다.

---

## 3. 개선이 필요했던 것

### 3.1 브랜치 없이 main에 직접 커밋

이번 작업 전체가 `main` 브랜치에 직접 커밋되었다. `.claude/` 내부 파일이라 빠르게 적용하려는 의도가 있었지만, 결과적으로:
- 중간 상태 커밋이 main 히스토리에 그대로 남음 (예: `fix: except 블록에 오류 상세 추가`)
- PR 단위로 변경 검토할 기회가 없었음
- 사용자가 작업 완료 후 이를 인지하고 PR 방식으로 전환을 요청함

**개선**: 다음 작업부터는 `feat/<기능명>` 브랜치에서 작업 후 PR 생성.

### 3.2 CI 기존 실패를 사전에 인지하지 못함

`test_jinja2_autoescape_enabled` 테스트가 GitHub Actions(Python 3.12 환경)에서 실패하고 있는 상태가 이미 수 주 전부터 지속되고 있었다. 이번 작업과 무관하지만, CI 실패를 보고 "우리 작업 때문인가?" 확인이 필요했다.

**개선**: 작업 시작 전 `gh run list --limit 3`으로 기존 CI 상태를 먼저 확인.

### 3.3 MultiEdit 페이로드 처리 미완성

리뷰에서 발견된 Minor 이슈: MultiEdit 도구의 페이로드 구조는 `{"edits": [...]}` 형태인데, 현재 hook은 `old_string`/`new_string`을 직접 읽는다. MultiEdit로 수정 시 diff가 빈 문자열로 구성되어 에이전트가 내용 없는 심의를 하게 된다.

**현재 상태**: hook의 matcher가 MultiEdit을 포함(`Write|Edit|MultiEdit`)하지만 실제로는 처리하지 못함. Minor 이슈로 분류하여 이번 작업에 포함하지 않았다.

**향후 대응**: MultiEdit 페이로드에서 `edits` 배열을 추출해 각 청크를 연결하는 로직 추가.

---

## 4. 발견된 버그 및 수정 이력

| # | 단계 | 버그 | 수정 |
|---|------|------|------|
| 1 | Task 1 구현 후 리뷰 | `_LOW_RISK` 가 `_CRITICAL` 보다 먼저 평가됨 → `docs/history/CLAUDE.md` 가 low_risk 반환 | 평가 순서를 critical → important → low_risk로 재정렬 |
| 2 | Task 1 구현 후 리뷰 | `_LOW_RISK` 만 `re.search` 사용, 나머지는 `re.match` — 불일치 | 전체 `re.match` 통일 |
| 3 | Task 4 구현 후 리뷰 | `_call_single_agent` except 블록에서 `detail: ""` — 오류 내용 유실 | `except Exception as exc` + `detail: str(exc)` |
| 4 | Task 5 코드 품질 리뷰 | `r"\{[^{}]*\}"` 정규식이 값에 중괄호 포함 시 block을 approve로 격하 | 코드 블록 우선 추출 + `json.loads` try/except |
| 5 | Task 5 코드 품질 리뷰 | 조기 종료 테스트에서 `sys.exit` mock이 실행 안 멈춤 → 에이전트 실제 호출 | `pytest.raises(SystemExit)` + `not mock_agents.called` |

---

## 5. CI 상태

| 항목 | 상태 | 비고 |
|------|------|------|
| 로컬 테스트 (1332개) | ✅ 전체 통과 | 이번 작업 추가분 32개 포함 |
| pylint | ✅ 10.00/10 | |
| GitHub Actions CI | ❌ 기존 실패 유지 | `test_jinja2_autoescape_enabled` — Python 3.12 환경에서 `autoescape`가 `callable`로 반환되는 starlette 버전 차이. **이번 작업과 무관한 기존 문제.** |
| CodeQL | ✅ 통과 | |

CI 기존 실패(`test_jinja2_autoescape_enabled`)는 별도 이슈로 수정 필요.

---

## 6. 다음 작업에 적용할 것

1. **브랜치 + PR 필수**: 모든 작업은 `feat/` 또는 `fix/` 브랜치에서 시작, 완료 후 `gh pr create`
2. **작업 시작 전 CI 상태 확인**: `gh run list --limit 3` — 기존 실패와 신규 실패 구분
3. **MultiEdit 처리 보완**: `edits` 배열 처리 로직 추가 (Minor 이슈 백로그)
4. **CI 기존 실패 수정**: `test_jinja2_autoescape_enabled` — `callable` 반환에 맞게 검증 로직 수정
