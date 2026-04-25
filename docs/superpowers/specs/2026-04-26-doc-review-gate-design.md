# 문서 변경 다중 에이전트 심의 시스템 설계

**날짜**: 2026-04-26  
**목적**: Claude가 중요 문서를 수정할 때 판단의 정확성과 타당성을 다중 에이전트 심의로 검증한다  
**상태**: 설계 완료, 구현 대기

---

## 1. 핵심 목적

Claude는 단일 관점으로 문서를 수정할 때 맹점이 생길 수 있다.

- CLAUDE.md 규칙 수정 → 이후 모든 세션에서 행동 변화 유발
- STATE.md 수치 수정 → 다른 문서와 불일치 발생
- 에이전트 정의 수정 → 해당 에이전트의 판단 기준 붕괴

이 시스템은 Claude가 중요 문서를 수정하기 **직전**에, 3개의 전문 에이전트가 각자의 관점에서 해당 변경을 검증하여 Claude 스스로 판단을 교정할 수 있게 한다.

**보고 여부보다 Claude의 판단 정확성이 우선이다.** 사용자에게 보이는 출력은 부수 효과이며 핵심이 아니다.

---

## 2. 문서 등급 분류

### Critical (impact-analyzer 또는 consistency-reviewer 반대 시 차단)

| 파일/경로 | 차단 이유 |
|-----------|----------|
| `CLAUDE.md` | Claude의 행동 규칙 정의 — 변경 즉시 이후 모든 세션에 영향 |
| `docs/STATE.md` | 프로젝트 수치 단일 출처 — 오류 시 다른 문서 전체 불일치 |
| `.claude/settings.json` | Hook·권한 설정 — 변경 즉시 자동화 시스템 행동 변화 |
| `.claude/agents/*.md` | 에이전트 판단 기준 정의 — 변경 시 에이전트 행동 변화 |
| `.claude/skills/*.md` | Claude 작업 방식 정의 — 변경 시 Claude 행동 변화 |

### Important (impact-analyzer 반대 시만 차단, 나머지는 경고)

| 파일/경로 | 경고 이유 |
|-----------|----------|
| `docs/design/*.md` | 구현 기준이 되는 설계 문서 |
| `docs/guides/*.md` | 운영 가이드 — 오류 시 잘못된 절차 실행 |
| `docs/superpowers/**/*.md` | 계획·스펙 문서 |
| `README.md` | 외부 공개 문서 |

### Low-risk (심의 없음)

| 파일/경로 | 이유 |
|-----------|------|
| `docs/reports/artifacts/` | 로그·측정 결과 — 변경해도 동작에 영향 없음 |
| `docs/history/` | 히스토리 아카이브 |
| `docs/integrations/` | 참조용 외부 연동 문서 |

---

## 3. 에이전트 역할 및 거부권

### 3.1 에이전트 구성

**병렬 실행** — 3개 에이전트가 동시에 검토하여 단일 에이전트 시간(목표: 20초 이내)으로 완료한다.

#### `doc-impact-analyzer`
- **핵심 질문**: 이 변경이 Claude의 행동을 의도하지 않게 바꾸는가?
- **검토 방법**: 변경 전후 diff를 기준으로 Claude가 이 문서를 따랐을 때의 행동을 시뮬레이션
- **특히 주의**: 규칙 삭제, 조건 변경, 예외 추가
- **거부권**: Critical + Important 모두에서 **무조건 차단**

#### `doc-consistency-reviewer`
- **핵심 질문**: 기존 CLAUDE.md 규칙, STATE.md 수치, 다른 문서와 충돌하는가?
- **검토 방법**: 변경 내용의 주요 사실·수치·규칙을 기존 문서와 교차 검증
- **특히 주의**: 수치 불일치, 모순 규칙, 이미 삭제된 개념 참조
- **거부권**: Critical에서 **차단**, Important에서 **경고**

#### `doc-quality-reviewer`
- **핵심 질문**: 미래 세션의 Claude가 이 문장을 오해할 수 있는가?
- **검토 방법**: 모호한 표현, 이중 해석 가능한 문장, 불완전한 예시 식별
- **특히 주의**: "가능하면", "적절히", "경우에 따라" 같은 애매한 부사
- **거부권**: Critical + Important 모두에서 **경고만** (차단 없음)

### 3.2 거부권 매트릭스

| 에이전트 | Critical | Important | 근거 |
|----------|----------|----------|------|
| `doc-impact-analyzer` | **차단** | **차단** | 행동 변화는 등급 무관하게 최우선 위험 |
| `doc-consistency-reviewer` | **차단** | 경고 | 사실 충돌은 Critical에서만 즉각 위험 |
| `doc-quality-reviewer` | 경고 | 경고 | 품질은 주관적 — Claude 작업을 막을 수 없음 |

---

## 4. 기술 구현 구조

### 4.1 파일 구조

```
.claude/
├── hooks/
│   ├── check_edit_allowed.py        # 기존 — 고위험 파일 차단
│   └── doc_review_gate.py           # 신규 — 문서 심의 진입점
└── agents/
    ├── pipeline-reviewer.md         # 기존
    ├── test-writer.md               # 기존
    ├── doc-impact-analyzer.md       # 신규
    ├── doc-consistency-reviewer.md  # 신규
    └── doc-quality-reviewer.md      # 신규
```

### 4.2 Hook 설정 (settings.json)

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/check_edit_allowed.py",
            "timeout": 10
          },
          {
            "type": "command",
            "command": "python .claude/hooks/doc_review_gate.py",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

### 4.3 doc_review_gate.py 핵심 로직

```
1. stdin에서 tool_input 읽기 (file_path, old_string, new_string)
2. file_path 기준으로 등급 판별
   - Low-risk → exit 0 (즉시 통과)
3. diff 구성 (old → new 변경 내용)
4. Claude API (Haiku 4.5) 병렬 호출
   - asyncio.gather()로 3개 에이전트 동시 실행
   - 각 에이전트: 역할 system prompt + diff + 관련 컨텍스트(CLAUDE.md 등)
5. 결과 수집 → 거부권 매트릭스 적용
6. 차단 결정 시:
   - hookSpecificOutput에 차단 사유 상세 기술
   - exit 0 (permissionDecision: "deny")
7. 경고 결정 시:
   - 경고 내용을 stdout에 출력
   - exit 0 (진행 허용)
```

### 4.4 에이전트 프롬프트 설계 원칙

각 에이전트는 다음 형식의 JSON을 반환한다:

```json
{
  "decision": "approve | warn | block",
  "reason": "구체적 사유 (한 문장)",
  "detail": "Claude가 이해해야 할 맥락 (2-3문장)"
}
```

- 에이전트는 **"괜찮아 보인다"** 같은 모호한 승인을 하지 않는다
- 승인 시에도 "어떤 관점에서 문제없음"을 명시한다
- 차단 시 **"무엇을 어떻게 바꿔야 통과할 수 있는가"** 를 반드시 포함한다

---

## 5. 성능 목표

| 지표 | 목표 |
|------|------|
| Critical 파일 심의 시간 | 20초 이내 (병렬 Haiku 4.5) |
| Important 파일 심의 시간 | 15초 이내 |
| 오탐률 (정상 변경 차단) | 5% 미만 |
| 누락률 (문제 변경 통과) | 2% 미만 |

---

## 6. 범위 제외 (Out of Scope)

- `.py` 소스 코드 변경 심의 — 기존 pytest Hook이 담당
- `alembic/versions/` — 기존 `check_edit_allowed.py`가 담당
- 사용자 대시보드·리포트 생성 — 이 시스템의 목적이 아님
- 외부 PR 자동 리뷰 — SCAManager의 GitHub 연동 기능과 별개

---

## 7. 위험 및 완화

| 위험 | 완화 |
|------|------|
| Haiku API 호출 실패 | 타임아웃 30초, 실패 시 경고만 출력하고 통과 (차단 금지) |
| 오탐으로 작업 완전 차단 | `doc-quality-reviewer`는 차단 권한 없음. impact/consistency만 차단 |
| 너무 느린 심의로 흐름 방해 | 20초 초과 시 타임아웃 처리, 결과 없는 에이전트는 경고 생략 |
| 에이전트 프롬프트 drift | 각 에이전트 `.md` 파일을 단일 출처로 관리, 변경 시 이 시스템 자체도 심의 대상 |
