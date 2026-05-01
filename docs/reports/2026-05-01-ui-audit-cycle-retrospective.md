# UI 감사 사이클 회고 — 2026-05-01

> **범위**: STATE.md 그룹 55~57 (UI/UX 개편 + 4-에이전트 감사 + 5-에이전트 정합성 cleanup) 단일 작업일 + 후속 메타 sync 시리즈.
>
> **목적**: 향후 동일 패턴 재사용 시 참조 — 다중 에이전트 감사 사이클 운영 + Step 시리즈 분할 + cleanup PR 분할 + 환각 토큰 발견 모델.

---

## 사이클 전체 요약 (PR 매트릭스)

| 단계 | PR | 핵심 |
|------|-----|------|
| Phase 1A | #149 | Claude × Linear 디자인 토큰 정의 |
| Phase 1B | #150 | 폰트 로딩 + claude-dark 토글 + 마이크로카피 |
| Phase 1C | #151 | claude-dark 등급 색 alias |
| Phase 2A Step A | #152 | Settings 6→5 카드 (③+④ 통합) |
| Phase 2A Progressive | #153 | `<details>` 아코디언 제거 + W2 분리 + 단순/고급 모드 + ●○ 점 |
| Settings P0 핫픽스 | #156 | 4-에이전트 감사 P0 5건 |
| Settings P1·P2 polish | #159, #160 | P1 8건 + P2 7건 |
| 7-페이지 4-에이전트 감사 → Step A~E | #163~#168 | 환각 토큰 alias / safe-area / WCAG / Chart.js vendoring / 색 의미 통일 / nav 가드 등 65건 |
| 5-에이전트 정합성 cleanup PR-1 | #169 | claude-dark 누락 토큰 8종 + 환각 alias 2종 + Step B/D 누락 4건 |
| cleanup PR-2 (docs sync) | #170 | STATE 그룹 57 + CLAUDE.md 트리/주의사항 7건/현재상태 + 기획서 진화 |
| cleanup PR-3 (P1 polish) | #171, #172 (중복 머지) | chart-wrap clamp + .btn:disabled 확장 + tooltip 토큰화 |
| cleanup PR-4 (회귀 가드) | #173 | StaticFiles + 환각 토큰 / claude-dark / nav guard / chip a11y / chart aspect / safe-area / iOS 줌인 12건 |
| 메타 sync PR-D1~D5 (후속) | (push 진행 중) | 5-에이전트 재감사 — 깨진 링크 / 트리 누락 / 운영 사고 위험 / 회귀 가드 갭 |

**총 작업 PR 수**: 약 25건 (단일 작업일 + 후속 메타).

---

## 잘된 것 (재사용 권장)

### 1. 다중 에이전트 감사 패턴

본 사이클에서 사용된 두 가지 감사 변형:

**(a) 4-에이전트 화면 감사** (Step A~E 도출)
- Agent 1: Playwright 캡처 + 시각 분석 (실제 스크린샷)
- Agent 2: 데스크탑 레이아웃 코드 분석
- Agent 3: 모바일 레이아웃 코드 분석
- Agent 4: 컴포넌트 시각 일관성

→ **결함 65건 식별 (P0 32 + P1 18 + P2 15)**.

**(b) 5-에이전트 정합성 감사** (cleanup PR-D1~D5 도출)
- Agent 1: CLAUDE.md 전체 정합성 (트리 / 주의사항 / 현재상태)
- Agent 2: STATE.md 전체 정합성 (그룹 / 수치 / PR 매핑)
- Agent 3: docs/ 디렉토리 전체 (runbook / guide / report / design / reference / archive)
- Agent 4: 코드 트리 vs 문서 등재 매트릭스
- Agent 5: 테스트 + 회귀 가드 매트릭스

→ **추가 27 결함 식별** (P0 8 + P1 12 + P2 7).

**핵심 성공 요인**:
- 각 에이전트는 **독립된 self-contained 프롬프트** — 다른 에이전트 결과 의존 0
- **병렬 디스패치** — 단일 메시지에 5 Agent tool_use 동시 실행 → 200초 내 모든 결과 수집
- 각 보고서가 **line:span 인용 의무** — 추측 없는 사실 기반

### 2. Step 시리즈 분할 (root cause 우선)

4-에이전트 감사 65 결함을 모두 단일 PR 처리하지 않고 다음 5단계로 분할:

| Step | 우선순위 | 내용 |
|------|---------|------|
| A | root cause | 환각 토큰 alias + safe-area + WCAG + login 모바일 |
| B | 모바일 전용 | iOS 줌인 + 신규 미디어쿼리 + 테이블 |
| C | 차트 인프라 | Chart.js vendoring + claude-dark 색 호환 |
| D | 색 의미 토큰 | --warning 신규 + 시맨틱 통일 |
| E | 페이지별 polish | nav 가드 + chart aspect + a11y |

**효과**: 각 PR 의 변경 영향 범위 명확 + 회귀 추적 용이 + 사용자 검토 부담 분산.

**핵심 원칙**: **root cause Step (A) 가 가장 큰 ROI** — base.html 한 곳 fix 로 7 페이지 ~60% 결함 동시 해소.

### 3. cleanup PR 분할 모델 (4 갈래)

Step E 머지 후 5-에이전트 정합성 감사가 발견한 27 결함을 다음 4 PR 로 분할:

| PR | 책임 |
|----|------|
| PR-1 | 코드 결함 (사고 위험 차단 우선) |
| PR-2 | 문서 동기화 (수치/트리/현재상태) |
| PR-3 | P1 polish (Step E 후속) |
| PR-4 | 회귀 가드 (가드 12건 추가) |

**효과**: 코드/문서/polish/가드 4 영역이 명확히 분리 → 각 PR 의 회귀 위험 + 검토 시간 + 머지 우선순위 차별화.

**후속 PR-D1~D5 (메타 sync)** 는 이 모델을 한 번 더 적용 — 5-에이전트 재감사 결과를 5 PR 로 분할.

### 4. 회귀 가드 source-grep 패턴

PR-4 (#173) + PR-D2 가 추가한 가드 17건 모두 **template/CSS/JS source 를 grep** 하는 단순 패턴:

```python
def test_phantom_token_aliases_in_root():
    base = _read_template("base.html")
    for token in ("--bg-hover:", "--card-bg:", "--text:", ...):
        assert token in base, f"{token} alias 누락"
```

**장점**:
- 빠른 실행 (외부 의존성 0)
- 명확한 실패 메시지 — 어느 토큰 / 어느 파일 / 어느 패턴 회귀했는지 즉시 알 수 있음
- 디자인 결정 변경 시 가드도 동시 수정 → CLAUDE.md 의 "신규 추가 시 규칙" 패턴과 정합

**단점/주의**:
- false-positive 위험 (예: `clamp(200px` 정확 매칭 → 정상적으로 180px 변경 시 깨짐)
- 디자인 의도 변경 시 maintenance burden — 회고 시 중요한 디자인 변경이면 가드도 동시 갱신 필수

### 5. 환각 토큰 발견 패턴

**환각(phantom) 토큰** 발견 사례:
- CSS 가 `var(--bg-hover)` 참조 → base.html 미정의 → 다크 테마 시각 깨짐
- 5-에이전트 감사 단계까지 발견 못 함 (단위 테스트 통과)
- 발견 후 **alias 패턴** 으로 해결: `:root { --bg-hover: var(--table-row-hover); }` — consumer 코드 변경 0

**향후 신규 디자인 토큰 추가 시 점검 절차**:
1. CSS grep 으로 `var(--*)` 참조 모두 추출
2. base.html `:root` + 4 테마 블록에서 정의된 토큰과 매트릭스 비교
3. 미정의 토큰 발견 시 alias 추가 (consumer 코드 변경 X)

---

## 어려웠던 것 (회피/개선)

### 1. PR 중복 머지 (#171, #172)

PR-3 (P1 polish) 가 두 번 머지됨 — `#171` 과 `#172` 가 동일 메시지/내용. 무해하지만 git log 가 어수선.

**원인 추정**: 동일 작업이 두 번 push 됐거나, 사용자가 PR 두 개 모두 squash merge.

**예방**: PR push 전 `git log --oneline -5` 확인 + 동일 메시지 commit 발견 시 PR 닫고 재push.

### 2. PR-5 머지 전 후속 PR 진행 (PR-D1~D3)

PR-5 (1968→1980 docs sync) push 후 사용자 머지 전에 PR-D1/D2/D3 진행. 변경 line 이 다른 영역이라 conflict 0 이었지만, 일반적으로 위험.

**예방**: 동일 영역 (특히 STATE.md / CLAUDE.md) docs PR 은 머지 후 다음 진행 권장. 또는 명시적으로 PR base 를 이전 PR 로 변경 (`gh pr create --base <prev-branch>`).

### 3. 미매핑 PR 17건

5-에이전트 감사가 식별한 미매핑 PR (#91/#93/#95~#97/#109~#115/#127/#145~#148) — 이미 머지된 PR 들이 어느 그룹에도 포함 안 된 상태.

**원인 추정**: 단일 작업일에 다수 PR 머지 + 그룹 정리 시점에 일부 누락.

**예방**: STATE.md 그룹 작성 시 `git log --oneline --since "<date>"` 로 시간 범위 PR 모두 매핑 의무. 또는 매주 정기 sync (CLAUDE.md "완료 5-step" 의 ④ STATE 갱신 강화).

### 4. 환각 토큰 8종 (claude-dark 테마)

PR #169 cleanup PR-1 에서 식별 — claude-dark 테마가 `--grad-gate/merge/notify/hook` 등 8종 토큰 미정의로 settings 페이지 시각 깨짐. Phase 1B 도입 시점 (PR #150) 에서 이미 누락된 상태였으나 6 PR 후에야 발견.

**원인**: claude-dark 가 default 테마 아니라 명시 선택 시만 활성 → 일상 작업 중 시각 검증 부재.

**예방**:
- 신규 테마 추가 시 (a) 모든 페이지 visual smoke test 의무 (e2e/test_theme.py 확장), (b) 4-테마 토큰 매트릭스 회귀 가드 (PR-4 G2 의 `test_claude_dark_settings_tokens_defined` 같은 패턴)

### 5. 5-way sync 5번째 layer (PRESETS / JS 헬퍼) 가드 부재

PR-4 가 추가한 12 가드는 디자인 토큰/HTML 구조 회귀에 집중 — PRESETS 9 키 / JS 헬퍼 12종 / themechange 페어링 가드 부재. PR-D2 가 보완.

**원인**: 가드 추가 시 "코드/마크업 회귀" 우선, "5-way sync 의 마지막 layer (JS 정책 객체)" 누락.

**예방**: 5-way sync 체크리스트에 "가드 5종" 명시 — ORM / dataclass / API body / HTML form / **PRESETS + JS 헬퍼** 까지 회귀 가드 의무.

---

## 학습된 패턴 (CLAUDE.md "주의사항" 신규 항목)

본 사이클에서 CLAUDE.md UI/템플릿 카테고리에 추가된 신규 규칙:

1. 🔴 **환각(phantom) 토큰 alias 패턴** — 미정의 토큰 발견 시 base.html `:root` 흡수, consumer 코드 변경 0
2. 🔴 **WCAG 2.5.5 모바일 클릭 영역 ≥44px 의무** — 모든 인터랙티브 요소 모바일 분기에 `min-height: 44px`
3. 🔴 **safe-area-inset 적용 의무** — sticky/fixed 요소는 `env(safe-area-inset-*)` 페어
4. **Chart.js vendoring + StaticFiles mount** — CDN 차단 환경 호환 위해 `src/static/vendor/` 로컬 호스팅
5. **claude-dark 테마 차트 색 동기화** — `getComputedStyle` + `themechange` 동적 read
6. **색 의미(semantic) 토큰 통일** — `--success / --warning / --danger` 만 사용, hex 직접 사용 금지
7. **claude-dark 테마 토큰 매트릭스** — settings 페이지 토큰 8종 4-테마 정의 의무

---

## 향후 적용 권장

### 1. UI 변경 시

- 변경 후 4-에이전트 감사 (Playwright + 데스크탑/모바일/일관성) 자동 디스패치
- root cause 우선 Step 분할 → cleanup PR 4 갈래 (코드/문서/polish/가드) 모델

### 2. 디자인 토큰 추가 시

- **5-step**: 정의 → 4-테마 alias → 사용처 grep → 회귀 가드 → STATE 갱신
- 환각 토큰 식별 패턴 — CSS `var(--*)` grep vs base.html 정의 매트릭스

### 3. 신규 vendor 자원 추가 시

- `docs/runbooks/static-assets.md` 절차 따름
- 회귀 가드 (`test_static_*_returns_200`) 동시 추가

### 4. 정기 정합성 감사

- 월 1회 5-에이전트 정합성 감사 권장 — STATE/CLAUDE/docs/src/ 트리/테스트 가드 매트릭스 검증
- 단일 작업일 다수 PR 머지 후 STATE 그룹 정리 의무

---

## 관련 문서

- `docs/STATE.md` 그룹 55, 56, 57 — 작업 이력
- `docs/design/2026-05-01-ui-redesign-claude-linear-hybrid.md` — 기획서 + 진화 기록
- `docs/runbooks/static-assets.md` — Chart.js vendoring 운영 절차
- `CLAUDE.md` UI/템플릿 카테고리 — 신규 7건 규칙
- `tests/unit/ui/test_router.py` 끝 부분 — PR-4 회귀 가드 12건 + PR-D2 가드 5건
