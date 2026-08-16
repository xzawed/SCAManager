# SCAManager 사용자 협업 정책 본문 detail

> CLAUDE.md 정책 표의 detail. 현재 계약만 적는다. 과거 진화 서사는 git 이력에 있다.

<a id="정책-1"></a>
<a id="정책-1-진화"></a>

## 정책 1: 일괄 결정 · 빠른 진행 시 검토 깊이 자가 보고

옵션을 제시할 때는 **장단점 표**(옵션·장점·단점·위험·권장시점) + ★ 권장 + "고려했으나 제시 안 한 안" 1줄.

**검토 깊이 1줄 자가 보고 요청** 이 붙는 경우:

- 사용자가 "전부다" / "모두 진행" / "모두 OK" 처럼 **일괄 결정** 할 때
- 또는 단일 작업일 **빠른 진행 신호**(`머지 했습니다 다음 작업 진행` / `다음 진행해주세요` 등)가 **≥ 10회** 일 때

요청 형식: 검토 시간 ≥ N분 항목 vs 직관 판단 항목(또는 line-level 검토 PR vs commit body 만 검증 PR)을 나눠 달라고 한다.

**예외** (이 의무 없음):

- 단순 머지 보고 ("머지 했습니다")
- Q1 형식 옵션 표 결정 (옵션 🅐/🅑/🅒)
- 사용자가 "바로 진행" / "검토 OK 진행" / "오늘 종결까지 진행" 을 **명시**한 경우

**누락 시 회복** (다음 응답에서, 건너뛰지 말 것):

1. 자성 1줄: 이전 응답에서 자가 보고 요청을 누락했다.
2. 검토 깊이 사후 요청 (위와 같은 분류).
3. 회복 자체를 누락하면 다음 회고 §자성에 기록.

적용 영역 = 다중 영역(≥ 3) 일괄 결정, 또는 사용자 검토 시간을 추정하기 어려운 빠른 진행.

---

<a id="정책-2"></a>

## 정책 2: PR 본문 "🔍 사용자 검증 필요" 섹션 의무

시각/운영 확인 항목 1~3개를 명시한다. "tests pass" 만 적지 않는다.

```markdown
## 🔍 사용자 검증 필요
- [ ] Railway 배포 후 `/repos/{owner}/{repo}/settings` 데스크탑 + 모바일 확인
- [ ] claude-dark 테마 토글 시 카드 헤더 정상 표시
- [ ] (있다면) 운영 사고 보고
```

**Phase 종료 시**: 개별 PR 체크리스트는 참고용으로 남기고, 누적 검증 항목을 **단일 회신 표**로 묶는다. 사용자는 OK / NG / 미수행 중 하나를 명시한다. 권장 표기: `[x] 확인 OK` / `[!] 미수행` / `[ ] 후속`.

**sync PR commit body** 에는 산식이 아니라 실측 1줄:

```
## 검증
- 단위 = `pytest tests/unit --collect-only -q` → N collected
- 통합 = `pytest tests/integration --collect-only -q` → N collected
- E2E = `pytest e2e --collect-only -q` → N collected
```

---

<a id="정책-3"></a>

## 정책 3: 자율 판단 보고는 PR 본문 Summary 직후

위임받은 작업 중 에이전트가 판단한 항목은 **PR 본문 Summary 바로 아래**(최상단)에 둔다. 본문 중간에 묻히면 검토 신호가 사라진다.

다음 중 **하나라도** 해당하면 `⚠️ 이의 시 알려주세요` 마커를 붙인다 (자가 감이 아니라 이 목록):

- 자율 판단 보고 ≥ 5건
- architecture 영향 (파일 위치 / 모듈 분리 / API 시그니처)
- 데이터 모델 변경 (DB 스키마 / 함수 시그니처 / KPI 정의)
- 사용자 인지 영향 (라벨 / 텍스트 / 동작 순서 / URL 변경)
- destructive 작업 (브랜치 삭제 / DROP / DELETE — 정책 9 완화 미적용)

MCP 직접 실행 결과는 별도 섹션 **§"MCP 자율 실행 결과"** — 도구·SQL + 결과 요약 + 해석 + acknowledge 요청. 정책 12와 페어.

---

<a id="정책-10"></a>

## 정책 10: PR 직접 생성 (URL 안내 금지)

흐름: `git checkout main && pull` → `checkout -b <type>/<scope>` → 작업+commit → `push -u origin` → **`gh pr create`**. 사용자에게 URL 만 주고 생성을 맡기지 않는다.

**본문 전달**: 임시 파일 작성 후 `--body-file <경로>` 만 쓴다. `--body @-` 와 PowerShell `--body-file -` stdin 은 금지 — `gh` 가 리터럴 `@-` 를 본문으로 저장한다.

**생성·수정 직후**: `gh pr view <n> --json body --jq '.body | length'`. 길이 < 50 이거나 본문이 `@-` 이면 `--body-file` 로 다시 보낸다.

기본 본문: §Summary + §🔍 사용자 검증 필요 (정책 2) + §자율 판단 보고 (정책 3). 구 Codex 검증 섹션은 넣지 않는다 (정책 18 폐기).

**fix-up**: 머지 전 CI 실패·회귀는 **같은 PR 브랜치에 추가 commit** (`fix(<feature>-ci):`). 머지 후 발견은 별도 `fix/<feature>-<bug>` PR.
**PR 본문 §자율 판단 보고에 사유 명시 의무** — 기계 집행자가 없어 이 문서 계약이 전부다(빠뜨리면 커밋 한 줄만 남고 왜 고쳤는지가 사라진다).

---

<a id="정책-7"></a>

## 정책 7: main 직접 작업 금지 · 응집 단위 · 위반 회복

모든 작업은 브랜치 + PR. `git push origin main` · main 에 commit 후 방치 · "docs 라서 main" 은 없다.

**PR 단위 = 응집 단위** ("작게 자르기"가 아님). 신규 기능은 (a) URL/route (b) 화면/template (c) 데이터/service 를 **같은 PR** 에 묶는다. 하나라도 빠지면 사용자 진입 경로가 깨진다.

같은 PR 의무 예:

- 신규 라우트 + 기존 URL redirect
- 신규 라우트 + nav 링크 갱신
- 라우트 폐기 + 그 URL 을 가리키는 외부 링크 정리

**단일 PR > 1500 LOC** 이면 응집에 맞아도 사용자 사전 확인. architecture / migration / RLS 는 사용자가 모아서 하자고 **명시한 경우** 단일 PR 이 기본이다.

실수로 main 에 commit 했을 때:

```bash
git branch <type>/<scope>-<desc>
git reset --hard origin/main
git checkout <type>/<scope>-<desc>
git push -u origin <branch>
```

---

<a id="정책-11"></a>

## 정책 11: 시각 변경 PR 8조합 체크리스트

적용: `src/templates/*.html` / `src/static/**/*.css` / `base.html` `<style>` / 신규 시각 컴포넌트.

본문 최상단:

```markdown
## Claude 시각 검증 불가 — 사용자 의무 (정책 11)

본 PR 은 UI/시각 변경 포함. 정적 코드만 검증 가능 — 다음 8 조합은 사용자 직접 확인:

- [ ] dark 테마 데스크탑 (1440px+)
- [ ] light 테마 데스크탑
- [ ] pastel 테마 데스크탑
- [ ] catppuccin 테마 데스크탑
- [ ] dark 테마 모바일 (375px ~ 767px)
- [ ] light 테마 모바일
- [ ] pastel 테마 모바일
- [ ] catppuccin 테마 모바일

특히 검증 필요 (변경 영역 한정):
- {변경 영역 설명}
```

표 형식:

```
| 테마 | 데스크탑 | 모바일 |
|------|---------|--------|
| dark | [ ] | [ ] |
| light | [ ] | [ ] |
| pastel | [ ] | [ ] |
| catppuccin | [ ] | [ ] |
```

**인증·외부 통합을 건드린 PR** 은 8조합에 더해 종단 확인 (기대값 SSOT = [`operational-smoke-checks.md`](../../docs/runbooks/operational-smoke-checks.md)):

- `GET /login` → **301** `/auth/github` (`src/auth/github.py:39-44`)
- `GET /auth/github` → 302 + GitHub 동의 화면
- GitHub 동의 후 `/auth/callback` → `/` + 세션 (`src/auth/github.py:123`)
- `POST /auth/logout` → `/` (랜딩). HTMX 는 200 + `HX-Redirect: /`. GET 은 **405** 가 정상 (`src/auth/github.py:136-158`)

외부 통합 변경 시: Telegram OTP 연결, GitHub webhook → pipeline → 알림.

---

<a id="정책-12"></a>

## 정책 12: MCP 범위

- **SELECT-only** 자율 실행 OK (통계·검증·조회)
- **INSERT / UPDATE / DELETE / DROP / ALTER** 는 사용자 사전 승인
- **PII / credential** 이 나올 수 있는 SELECT 도 사전 승인 (`users.email`, `users.github_access_token`, `repo_configs.*_token` 등)
- 호출했으면 PR 본문 §"MCP 자율 실행 결과"에 도구 + 영향 범위 (정책 3)

SQL 본문을 사용자에게 보여주지 않은 채 INSERT/DELETE 하지 않는다.

---

<a id="정책-13"></a>

## 정책 13: 운영 endpoint smoke check

사이클·Phase 종료 시 최소 3-endpoint. 기대값 SSOT = [`docs/runbooks/operational-smoke-checks.md`](../../docs/runbooks/operational-smoke-checks.md). 여기 숫자를 복제하지 않는다.

현재 코드가 내는 응답:

- `GET /health` → 200 `{"status": "ok"}` (`src/main.py:382`)
- `GET /auth/github` → 302, `Location` 의 `redirect_uri=` 가 `APP_BASE_URL` 과 맞는지
- `GET /login` → **301** `/auth/github` (`src/auth/github.py:39-44`)

인증/외부 통합 변경 PR 추가:

- `GET /auth/callback` (state 없이 직접 호출 → 의도된 거부 또는 302)
- `POST /webhooks/github` (서명 헤더 없음 → 401)

실행: curl 또는 사용자 운영 URL. PR 본문 §"운영 smoke check 결과" 필수. 빌드 성공을 운영 정상으로 보지 않는다.

자동화는 보조이지 대체가 아니다:

- `tests/integration/test_oauth_flow_smoke.py` — 3-endpoint + 인증 flow
- `e2e/test_dashboard.py` · `e2e/test_theme_mobile_guards.py`

외부 의존(GitHub OAuth App callback URL)은 자동화가 못 본다.

---

<a id="정책-14"></a>

## 정책 14: GitHub Code Scanning 운영 체크

SCAManager lint(pylint / flake8 / bandit) 통과 ≠ Security 탭 open 0. CodeQL 등 별도 룰셋이다.

- 작업 시작 전: open alert 카운트 1줄
- 사이클·Phase 종료: Security 탭을 **직접** 본다 (Issue 추적으로 대체 금지)
- 신규 alert: (a) 실제 위반 → fix PR (b) false-positive → dismiss + 사유 (c) 의도된 패턴 → suppress + 회고 사유

```bash
gh api repos/<owner>/<repo>/code-scanning/alerts --jq '[.[] | select(.state=="open")] | length'
```

gh 없으면 사용자가 Security 탭 카운트·제목을 공유한다. 룰 본문을 안 읽고 dismiss 하지 않는다.

절차 상세: `docs/runbooks/operational-smoke-checks.md` §9.

---

<a id="정책-15"></a>

## 정책 15: 코드 작업 직전 사전 사고

Edit / Write / destructive / MCP 변경 SQL **직전**에 도구를 치지 않고 세 가지를 자문한다.

1. 이 변경의 **목적**이 사용자 의도와 맞는가?
2. 영향 범위(다른 파일 / 운영 / 테스트)를 **알고** 있는가?
3. 변경 후 **검증 방법**이 있는가?

이해 부족이면 중단: 의도 모호 → 1줄 확인. 영향 불명 → 조사 후 보고. 검증 방법 없음 → 가드를 추가하거나 사용자에게 검증을 요청.

누락 후 진행이 드러나면: 사과 + 영향 분석 + revert 여부 회신.

**3-tier** (`feedback-architecture-decision-pre-confirm.md`):

- **High** (스키마 / API / 권한 / 데이터 모델) — 옵션 표 + 사용자 1줄
- **Medium** (헬퍼 / 정책 본문) — 사고 후 자율 + PR 자율 판단 보고
- **Low** (회귀 가드 / docstring / typo) — 즉시 가능. (2)(3) 자문은 남는다

---

<a id="정책-16"></a>

## 정책 16: 단순화 우선순위

1. **정확성** — 동작·회귀를 바꾸면 단순화하지 않는다
2. **성능** — hot-path latency / memory 가 늘면 실측 없이 단순화하지 않는다
3. **가독성** — 위 둘이 충족될 때
4. **최소 추상화** — 사용처 ≥ 3 일 때만 베이스/Protocol/Generic
5. **토큰 비용** — 운영 토큰 ↓, caching. **AI 리뷰 품질을 깎는 단순화는 금지**

**명시 제외** (사용자 결정, 사전 확인 없이 축소하지 말 것):

- `build_review_prompt` 토큰 예산 축소
- `review_guides/` 언어별 가이드 압축

현재 코드 위치 (줄 번호는 쓰지 않는다 — drift):

- prompt cache 조립 = `src/shared/anthropic_caching.py::build_cached_system_param`
- cache 통계 = `src/shared/claude_metrics.py::get_cache_stats`
- 동일 SHA 재사용 = `src/repositories/analysis_repo.py::find_by_sha` (`src/worker/pipeline.py` 가 호출)

새 토큰 절약 수단은 High tier 사전 확인 (정책 15).

적용 패턴: 의도 드러나는 이름, 인자 ≤ 5, 단일 책임, public 타입 힌트, 중첩 ≤ 3. 표준 라이브러리(functools/contextlib) 밖 메타클래스·데코레이터 체인 금지. "다음 확장 대비" 분기 금지.

PR 자가 검토: 더 짧게 쓸 수 있나 / 같은 결과 분기를 합칠 수 있나 / 한 번만 쓰는 임시 변수를 인라인할 수 있나 / itertools·collections·functools·dataclasses 로 충분한가.

CI lint (pylint R0911~R0917) 가 1차, PR §자율 판단 보고가 2차.

<a id="정책-16-공유-로직-grep-전수"></a>

### 공유 로직은 수정 직전 `grep -rn` 전수

같은 값·로직이 2곳 이상이면 **고치기 전에** `grep -rn <심볼>` 로 호출처를 모두 적고, diff/PR 에 "전수 확인 N곳" 1줄.

API + HTML 양쪽이 같은 서비스를 부르는 곳(`operations_kpi`·가격·KPI)은 High-tier 사전 grep (정책 15).

가능하면 회귀 가드도 같이 (`tests/unit` 가격 parity 등). 사후 리뷰(5+1·whole-branch·외부 검증자)를 이 규율의 대체로 쓰지 않는다.

---

<a id="정책-17-why-how"></a>

## 정책 17: 문서 정리 — 안정성 우선

CLAUDE.md 는 운영 의무 문서다. Anthropic 200줄 같은 **외부 권장**은 가이드라인이다. 안정성과 충돌하면 거부한다.

cleanup PR 자가 검토:

- (a) default rule + 진화 1~2줄이 본문에 남는가?
- (b) 행동 영향 0 을 검증할 수 있는가?
- (c) 단계 분할 + 단계별 검증을 하는가?
- (d) 분리 위험 영역은 사용자 사전 확인을 받았는가?

하나라도 아니면 보류하거나 옵션 표를 낸다.

정책 8·11·5·9 의무 영역은 **본문 보존이 기본**. 분리하려면 High tier.

<a id="정책-17-5번째-default"></a>

## 정책 17: 누적 결함 정기 검증

트리거 (둘 중 하나, 사용자 결정 없이 진입):

- 단일 작업일 ≥ 18 PR 규모 영역 도입 후 **≥ 5 사이클** 경과
- 또는 직전 정기 검증 이후 누적 ≥ 50 PR

검증 범위: 단위 + 통합 + E2E + lint + 기능 + 보안. Round 2 는 단위 분포를 실측하고 (정책 8 cross-verify), Round 3 은 Tier A/B + 옵션 표.

정책 8 회고 cross-verify(사이클마다)와 **시점이 다르다**. 둘을 한 번에 돌리면 토큰만 는다.

---

<a id="정책-18"></a>

## 정책 18: Codex mutual 검증 — 폐기, 현재 계약

`codex exec` 실패는 **정상**이다. 이상 징후로 보고하거나 사용자에게 확인을 요청하지 않는다.

대체는 Claude 단독 2-layer: (a) 정책 8 5+1 cross-verify (b) `pipeline-reviewer` / whole-branch 적대 리뷰. whole-branch 를 비용 때문에 빼지 않는다 (`form=` 데이터손실처럼 파일 단위가 못 보는 결함).

사이클 종료 조건에서 Codex OK 는 없다. push 전 `pytest tests/unit` 전체는 CLAUDE.md 6-step ② 로 남는다.

코드·문서의 "Codex 적발/발견" 주석은 **당시 기록**이므로 고치지 않는다.

---

<a id="정책-8-doc-audit-agent-domain"></a>

## 정책 8: 문서 감사 5+1 도메인 분리

문서 감사 dispatch 때 아래 도메인을 겹치지 않게 배정한다. 프롬프트에 "담당 도메인 밖 파일 언급 금지", `self-contained`, `line:span`(`grep -n` 실측), P0/P1/P2.

| 에이전트 | 담당 | 주요 파일 |
|---|---|---|
| Agent-1 | 핵심 정책 | `CLAUDE.md` / `.claude/` (skills, rules 제외) |
| Agent-2 | 활성 정책 | `.claude/policies/active.md` |
| Agent-3 | 아키텍처 + 상태 | `docs/architecture.md` / `docs/STATE.md` |
| Agent-4 | Path-scoped rules | `.claude/rules/*.md` |
| Agent-5 | 참조 + 운영 | `docs/reference/*.md` / `docs/runbooks/*.md` |
| Agent-6 (cross-verify) | 합성 | 1~5 종합, false-positive 제거, P0/P1/P2 정렬 |

작업이 한 영역에 몰리면 수를 조정할 수 있다. 비중복은 유지한다.

<a id="정책-8-회고-카덴스"></a>

## 정책 8: 5+1 · cross-verify · 카덴스

**6번째 에이전트**: 1차 5명 결과를 받은 뒤 별도 cross-verify 1건. `doc-consistency-reviewer` 를 회고 cross-verify 로 쓰지 않는다 (`general-purpose` 또는 해당 specialist). 문서 diff 일관성 **단독** 호출은 허용.

**생략** — 아래 3조건을 **모두** 충족할 때만. 자가 판단으로 생략하지 않는다. 생략 시 PR 본문에 3조건 대조 표.

1. 1차 5 에이전트 P0 합계 ≥ 8
2. 관점 5종이 모두 P0 ≥ 1
3. 사용자 빠른 진행 신호 명시

**개별 PR** 에 5+1 을 돌렸으면 commit/PR 본문 §"cross-verify 결과"에 false-positive N / 신규 N / Tier A 정정 N 을 숫자로 적는다.

**단일 작업일 dispatch 상한** (인지 규율, 기계 집행 없음):

- dispatch = 한 메시지 안의 Agent 호출 그룹 (5+1 = 1 dispatch)
- invocation = 개별 Agent 호출 합 (5+1 = 6)
- 임계: dispatch ≥ 5 **또는** 누적 invocation ≥ 30 → 사용자 사전 확인. "여러 에이전트 + 깊게" 명시 시 면제.

**카덴스**: 직전 정식 회고 이후 **≥ 3 세션 또는 ≥ 15 PR** 이면 5+1 회고가 강제다.

- 기계 신호: `scripts/check_retro_cadence.py` (`RETRO_PR_THRESHOLD = 15`, SessionStart, advisory exit 0)
- 범위 산출: `scripts/retro_scope.py` (직전 회고 이후 머지 PR + 본 세션 산출물)
- 이월: `docs/runbooks/retro-cadence-deferrals.md` 에 사용자 승인 인용 + 목표 세션. 빈 칸이 아닌 **행의 존재**가 승인이다 (`.claude/rules/docs.md`)
- 자기회고 갈음은 사용자 **명시 승인** 만. "규모가 작아서"는 사유가 아니다
- 감사/수정만 한 세션도 종료 시 회고 대상이다

---

<a id="정책-5-phase-종료-cross-reference"></a>

## 정책 5: Phase 종료 때 같이 볼 4 정책

한 정책만 적용하고 끝내지 않는다.

- **정책 2**: Phase 종료 일괄 회신 + sync 실측 1줄
- **정책 5**: 단계별 진행/종료 신호를 나눈다. 잔여 단계가 있으면 진행 신호를 회신한다. NEW-P0-N(운영 사고 차단)은 매 사이클 회신 — 보류·정책 9 완화 없음
- **정책 8**: 회고+sync / sync 단독 / 회고 단독 분기
- **정책 11**: 시각 변경이 누적됐으면 8조합을 Phase 종료 회신에 묶는다

---

## 정책 19: Claude ↔ Grok 협업 — detail

> SSOT = [`AGENTS.md`](../../AGENTS.md) + [`docs/runbooks/ai-collaboration.md`](../../docs/runbooks/ai-collaboration.md).
> CLAUDE.md 에는 default rule 만 남긴다.

Grok 은 파이프라인 단계가 아니라 **claim-review / 인터럽트**. 별도 지시가 없으면 실질 작업마다 CLAIM-REVIEW. 건너뛰려면 사용자가 명시한다. 상세: [[feedback-grok-collaboration-default]].

- **트리거**: "봉인/완결/fail-closed/유출 0" **주장** → 그 주장 하나로 뮤테이션 패스. 1순위 = observer-lie (*보호 장치를 지워도 참으로 보이는가?*)
- **2-phase 사용자 보고**: `배포|활성|봉인|운영|cron 실행됨` 이 들어간 문장은 라이브 근거 또는 **`UNVERIFIED:`** 접두사. `STATIC-ONLY-UNVERIFIED` 는 사용자에게 보고하지 않는다
- **A2**: 새 관측자는 실경로 뮤테이션 red 없이 HOLDS 하지 않는다. 합성 픽스처 불가. 본문 = [`AGENTS.md`](../../AGENTS.md)
- 🔴 **A2-b (반례 일반화 + 봉인 선언 금지)** — 반례 하나를 red 로 만들고 끝내지 않는다.
  **(A)** 그 반례의 **클래스를 이름 붙이고**, 클래스 안 **다른 인스턴스를 스스로 만들어** red 를 본 뒤에야 "닫았다"고 말한다.
  **(B)** 뮤테이션 red 는 *"이 뮤테이션을 막았다"* 로만 보고한다. 클래스 전체를 닫았다는 말은 **외부 적대 검증 1회를 더** 거친 뒤에만.
  집행: `tests/unit/scripts/test_agents_md_invariant_survival.py` — **어휘 생존만** 고정한다. 어휘를 남기고 뜻을 뒤집으면 통과한다. 실질 집행은 review-time claim-review. 기계가 A 를 판정한다고 쓰지 않는다. 본문 = [`AGENTS.md`](../../AGENTS.md) §불변식 2-b.
- **소유 금지**: Grok 은 정책·backlog 를 **저술하지 않는다**. claim-review 는 허용 (`owner-interrupt: claim-review`). 계획·WBS·구현 중간에는 부르지 않는다
- 회고 카덴스에 Grok full-pass 를 겹치지 않는다. 주장 트리거 + ops 불변식 단축만
- 🔴 **CI 집행면**: seal 어휘가 있는 PR 은 `scripts/check_claim_review_trace.py` 가 session/claim/verdict 값 흔적을 요구한다. 흔적·면제는 HTML 주석을 벗긴 **리뷰어 가시 영역**만. 면제는 `::notice` 로 센다.
  가드 표면 PR 은 면제 불가 — `tests/unit/scripts/test_claim_review_mandatory_on_guards.py`. 경로 집합은 `scripts/check_claim_review_trace.py` 의 `_GUARD_SURFACES` 가 정본.
