# 사이클 143 설계 문서 — i18n 완성 + 프로세스 강화

**작성일**: 2026-05-31
**상태**: 승인됨
**범위**: repo_detail.html HTML i18n · analysis_detail.html i18n · GitHub PR 템플릿 · 정책 보강

---

## 1. 배경 및 목표

사이클 142 5+1 회고에서 식별된 잔여 i18n 작업과 프로세스 개선 항목을 구조화하여 완료한다.

### 포함 범위
- `analysis_detail.html` HTML 콘텐츠 하드코딩 한국어 ~3건
- `repo_detail.html` HTML 일반 텍스트 하드코딩 한국어 ~20건
- `repo_detail.html` HTML 이슈 등록 관리 UI 하드코딩 한국어 ~11건
- `.github/pull_request_template.md` 신규 생성 (정책 18 · 11 기본 체크리스트)
- `CLAUDE.md` + `.claude/policies/active.md` 정책 본문 보강

### 제외 범위 (명시적 보류/이월)
- `repo_detail.html` **JS 코드 내** 한국어 ~15건 (보류 — JS i18n 표준 인프라 미확보)
  - L625 `선택 항목 일괄 Issue 등록 (0건) →` 포함 (JS 동적 카운트 연동)
  - L734-736 차트 라벨(평균/최고/최저) 포함
  - L1229-1350 Issue 생성 동적 메시지 포함
- `repo_detail.html` · `analysis_detail.html` 이외 템플릿 i18n (별도 사이클)
- `LimitBodySizeMiddleware` chunked bypass 개선 (이월 — 실질 위험 낮음)

### 설계 결정 근거 (deep-research 검증 결과)
1. **prefix/suffix HTML 속성 분리 방식 채택 불가**: 비표준 패턴 확인. 대신 ICU MessageFormat 방식으로 `{변수}` 플레이스홀더를 문자열 내부에 두는 단일 키 방식 적용.
2. **GitHub 단일 PR 템플릿**: `.github/PULL_REQUEST_TEMPLATE/` 디렉토리 다중 템플릿은 자동 적용 불가 (GitHub 공식 문서 확인). 단일 `.github/pull_request_template.md`만 자동 적용.
3. **chunked bypass 이월 유지**: `content-size-limit-asgi` 라이브러리 유지보수 중단(2020) 확인 — 직접 구현 방식 검토 후 별도 사이클 진행이 안전.

---

## 2. 아키텍처

### i18n 키 네임스페이스 구조

```
src/i18n/translations/{ko,en,ja}.json
└── "analysis_detail"
│   └── "issue_form"        ← Sprint 1-A 신규
│       ├── title
│       ├── body
│       └── labels
└── "repo_detail"
    ├── "cost"              ← Sprint 2 신규 서브 네임스페이스
    │   ├── title
    │   ├── period          ({month} arg)
    │   ├── tokens          ({count} arg)
    │   ├── no_data
    │   ├── disclaimer
    │   ├── model_change
    │   └── settings_link
    ├── recent_score        ← Sprint 2 신규
    ├── analysis_unit       ← Sprint 2 신규
    ├── history_empty       ← Sprint 2 신규
    ├── history_empty_hint  ← Sprint 2 신규
    └── "issue_mgmt"        ← Sprint 3 신규 서브 네임스페이스
        ├── title
        ├── tab_static
        ├── tab_ai
        ├── filter_unregistered
        ├── modal_title
        ├── form_title
        ├── form_body
        ├── form_labels
        ├── btn_cancel
        ├── btn_skip
        └── btn_create_next
```

### PR 템플릿 구조

```
.github/
└── pull_request_template.md   ← 자동 적용 단일 템플릿
    ├── ## Summary
    ├── ## 변경 내용
    ├── ## 테스트
    ├── ## 🔍 사용자 검증 필요
    │   └── [ ] CI 통과 확인
    │   └── [ ] (UI 변경 시) 4테마 × 2뷰포트 8조합 시각 확인
    └── ## 🔍 Codex 검증 의뢰 (push 전, 정책 18)
        └── [ ] Codex OK / Claude 직접 검증 대체 OK
```

---

## 3. Sprint 상세

### Sprint 1 — 소규모 i18n + 프로세스 인프라 (PR 3개)

#### Sprint 1-A: analysis_detail.html i18n

**대상 파일**: `src/templates/analysis_detail.html`

| 라인(추정) | 현재 텍스트 | 신규 키 | 언어 |
|---|---|---|---|
| ~L814 | `제목` | `analysis_detail.issue_form.title` | ko: 제목 / en: Title / ja: タイトル |
| ~L818 | `본문` | `analysis_detail.issue_form.body` | ko: 본문 / en: Body / ja: 本文 |
| ~L822 | `라벨 (쉼표 구분)` | `analysis_detail.issue_form.labels` | ko: 라벨 (쉼표 구분) / en: Labels (comma separated) / ja: ラベル (カンマ区切り) |

**테스트**: `tests/unit/test_i18n_analysis_detail.py` 신규 (~9케이스, 3언어 × 3키 × 존재)

**TDD 순서**: test-writer 에이전트 → 구현 → Green → PR

#### Sprint 1-B: GitHub PR 템플릿

**신규 파일**: `.github/pull_request_template.md`

- 자동 적용 (단일 파일 방식, GitHub 공식 확인)
- Codex 검증 의뢰 섹션 포함 (정책 18)
- UI 변경 8조합 체크리스트 포함 (정책 11) — UI 변경 PR에서 해당 항목만 체크
- 기존 `gh pr create --body "$(cat <<'EOF'..."` 패턴과 병존 가능

**테스트**: 없음 (문서 파일)

#### Sprint 1-C: CLAUDE.md + 정책 보강

**변경 파일**:
- `CLAUDE.md` 완료 6-step: "PR 본문 Codex 검증 의뢰 섹션 포함" 명시 추가
- `.claude/policies/active.md` 정책 11: 8조합 체크리스트 코드블록 표준 형식 구체화

**테스트**: 없음 (정책 문서)

---

### Sprint 2 — repo_detail.html 일반 텍스트 i18n (PR 1개)

**대상 파일**: `src/templates/repo_detail.html`

#### Group A — 점수/통계 영역

| 라인(추정) | 현재 텍스트 | 신규 키 |
|---|---|---|
| ~L449 | `최근 점수:` | `repo_detail.recent_score` |
| ~L451 | `건 분석` | `repo_detail.analysis_unit` |

언어값:
- ko: 최근 점수: / en: Recent Score: / ja: 最近スコア:
- ko: 건 분석 / en: analyses / ja: 件

#### Group B — 분석 이력 빈 상태

| 라인(추정) | 현재 텍스트 | 신규 키 |
|---|---|---|
| ~L495 | `분석 이력이 없습니다` | `repo_detail.history_empty` |
| ~L496 | `Push 또는 PR 이벤트 후 첫 분석이 완료되면 차트가 표시됩니다` | `repo_detail.history_empty_hint` |

#### Group C — AI 비용 섹션

| 라인(추정) | 현재 텍스트 | 신규 키 | 비고 |
|---|---|---|---|
| ~L504 | `이번 달 AI 리뷰 예상 비용` | `repo_detail.cost.title` | — |
| ~L505 | `({{ month }} 01일 ~ 말일, Webhook 기준)` | `repo_detail.cost.period` | `{month}` arg |
| ~L511 | `(입력+출력 {{ token_count }} 토큰)` | `repo_detail.cost.tokens` | `{count}` arg |
| ~L514 | `데이터 없음 — 이번 달 토큰 추적 분석이 아직 없습니다.` | `repo_detail.cost.no_data` | — |
| ~L518 | `※ Anthropic 공식 요금 기준 추정값입니다...` | `repo_detail.cost.disclaimer` | — |
| ~L519a | `모델 변경:` | `repo_detail.cost.model_change` | — |
| ~L519b | `설정 페이지` (링크 텍스트) | `repo_detail.cost.settings_link` | — |

**총 신규 키**: ~13개 (ko/en/ja)

**테스트**: `tests/unit/test_i18n_repo_detail.py` 신규 (~60케이스)

**TDD 순서**: test-writer → 구현 → Green → PR

---

### Sprint 3 — repo_detail.html 이슈 등록 관리 UI i18n (PR 1개)

**대상 파일**: `src/templates/repo_detail.html`

#### Group A — 섹션 헤더 + 필터 탭

| 라인(추정) | 현재 텍스트 | 신규 키 |
|---|---|---|
| ~L609 | `🔁 반복 이슈 — Issue 등록 관리` | `repo_detail.issue_mgmt.title` |
| ~L613a | `🔴 정적 분석 이슈` | `repo_detail.issue_mgmt.tab_static` |
| ~L613b | `🔵 AI 제안사항` | `repo_detail.issue_mgmt.tab_ai` |
| ~L622 | `미등록만 보기` | `repo_detail.issue_mgmt.filter_unregistered` |

#### Group B — 이슈 생성 모달

| 라인(추정) | 현재 텍스트 | 신규 키 |
|---|---|---|
| ~L641 | `📝 GitHub Issue 생성` | `repo_detail.issue_mgmt.modal_title` |
| ~L643 | `제목` | `repo_detail.issue_mgmt.form_title` |
| ~L648 | `본문` | `repo_detail.issue_mgmt.form_body` |
| ~L650 | `라벨 (쉼표 구분)` | `repo_detail.issue_mgmt.form_labels` |
| ~L654 | `취소` | `repo_detail.issue_mgmt.btn_cancel` |
| ~L655 | `이 항목 건너뜀` | `repo_detail.issue_mgmt.btn_skip` |
| ~L656 | `생성 후 다음 →` | `repo_detail.issue_mgmt.btn_create_next` |

> **주의**: `analysis_detail.issue_form.*` 와 **별도 네임스페이스** 유지 — 두 페이지의 모달은 독립 컴포넌트.
> **제외**: L625 `선택 항목 일괄 Issue 등록 (0건) →` — JS 동적 카운트 연동, JS 보류 목록으로 이동.

**총 신규 키**: ~11개 (ko/en/ja)

**테스트**: `tests/unit/test_i18n_repo_detail.py` 에 Sprint 3 키 추가 (~42케이스)
**통합 smoke**: `tests/integration/test_i18n_smoke.py` — `/repos/` 엔드포인트 EN/JA locale 확인 1건 추가

**TDD 순서**: test-writer → 구현 → Green → PR

---

## 4. 테스트 전략

| 레이어 | 도구 | 검증 내용 |
|---|---|---|
| 단위 | `test_i18n_analysis_detail.py` (신규) | analysis_detail 신규 키 존재 + 비공백 |
| 단위 | `test_i18n_repo_detail.py` (신규) | repo_detail 신규 키 존재 + 비공백 (Sprint 2+3 누적) |
| 통합 | `test_i18n_smoke.py` (기존 + 1건 추가) | `/repos/` 엔드포인트 locale 응답 |
| CI | pytest + CodeQL + SonarCloud | 전체 통과 의무 |

**TDD 원칙**: 모든 Sprint의 구현 코드 작성 전 test-writer 에이전트로 테스트 먼저 작성.

---

## 5. 완료 기준

| Sprint | 완료 조건 |
|---|---|
| 1-A | `test_i18n_analysis_detail.py` 9케이스 Green + PR 머지 |
| 1-B | `.github/pull_request_template.md` GitHub UI 자동 적용 확인 |
| 1-C | CLAUDE.md + active.md 정책 본문 보강 + PR 머지 |
| 2 | `test_i18n_repo_detail.py` 60케이스 Green + PR 머지 |
| 3 | `test_i18n_repo_detail.py` 102케이스 누적 Green + smoke +1 + PR 머지 |
| **전체** | 전체 테스트 3480 → **3591** (+111) / Code Scanning 0건 유지 |

---

## 6. 보류 / 이월 항목 (다음 사이클 참고)

| 항목 | 이유 | 재검토 조건 |
|---|---|---|
| repo_detail.html JS 내 한국어 ~15건 | JS i18n 표준 인프라 미확보, prefix/suffix 비표준 | JS i18n 전용 라이브러리(i18next 등) 도입 결정 시 |
| LimitBodySizeMiddleware chunked bypass | 실질 위험 낮음, content-size-limit-asgi 유지보수 중단 | ASGI receive() 직접 래퍼 구현 방식 검토 후 |
| repo_detail/analysis_detail 이외 템플릿 i18n | 범위 집중 | 별도 사이클 |
