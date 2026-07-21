# Claude ↔ Grok 협업 프로토콜

> 🔴 **Grok/Codex 등 auto-load 없는 에이전트의 진입점 = [`AGENTS.md`](../../AGENTS.md)**
> (dual-consumer SSOT — 3-불변식·트리거 inline). 이 파일은 그 프로토콜의 상세다.

> **성립 근거**: 2026-07-19 사용자 승인 + Claude·Grok 2라운드 상호 회고·협의.
> **한 줄 헌장**: *Claude 는 구현과 라이브 배포 진실을 소유하고, Grok 은 명시된 주장에 대한
> 경로 증명과 observer-lie 사냥을 소유한다. 회고 카덴스에 full-pass 를 걸지 않는다.
> 사용자에게는 `HOLDS` 만 보고한다.*

---

## 왜 하는가 (측정된 근거만)

| 근거 | 실측 |
|------|------|
| cross-vendor 다양성이 실효 | 2026-06-29 Codex 가 Claude 8-에이전트가 놓친 **P1 2건** 단독 발견 |
| Grok 자체 성과 | 2026-07-17 전체 리뷰 → **확정 P1 4건** (auto-merge SHA 결속 · SMTP 587 100% 실패 · pip-audit 게이트) |
| 🔴 Grok 의 알려진 편향 | 같은 리뷰의 **P0 정밀도 0/4** — 허위가 아니라 **심각도 과대평가** |
| 무가치 확인된 것 | `grok_build_plan` = 산출 0. `grok_build_delegate` + 외부 `.md` 기록만 실효 |

**따라서**: 상시 페어링 ❌ / 조건부 인터럽트 ✅. Grok 은 **파이프라인 단계가 아니라 인터럽트**다.

---

## 🔴 사냥 대상 1순위 — observer-lie

Grok 이 Claude 자기평가에 **추가로 지목한 실패 클래스**다(협의 중 도출, 본 프로토콜의 핵심):

> **"코드의 버그는 고쳤는데 관측자는 여전히 거짓말을 하고 있다."**

2026-07-19 세션의 결함이 전부 이 형태였다:

| 사례 | 관측자가 한 거짓말 |
|------|-------------------|
| tflint 미설치 | `\|\| echo WARNING` 이 실패를 삼켜 **빌드는 성공** — analyzer 만 조용히 죽음 |
| `[[deploy.cronJobs]]` | Railway 가 무시하는 키인데 저장소엔 "cron 설정함" 흔적 |
| `[deploy] numReplicas` | 백로그가 지시한 해법 자체가 무효 키 → "핀했다" 거짓 흔적 |
| Claude 의 배포 폴링 | 커밋 해시가 JSON 어딘가에 있으면 매칭 → **WAITING 을 "활성"으로 보고** |

**핵심 질문**: *보호 장치를 삭제해도 여전히 참으로 보이는 것은 무엇인가?*
Claude 는 **통제의 존재를 발명**하는 경향이 있다 — 배선·집행·관측 없이 산문이나 무효 설정만 남긴다.

---

## 호출 트리거

### 호출한다

| 트리거 | 사유 |
|--------|------|
| 🔴 **"봉인/완결/fail-closed/유출 0" 주장** | Claude 최악의 실패 모드 직격. **심각도 판단 불필요**한 이진 질문이라 Grok 편향을 우회 |
| auto-merge · gate · analyzed SHA · claim_decision · 반자동 telegram 머지 변경 | 최대 성과 영역 (SHA 결속 P1 전례) |
| 뮤테이션 테스트 없는 **신규 가드·kill-switch** | 2026-07-18 신규 가드 4종 전부 결함 전례 |
| 점수 무결성 (incomplete · AI 실패 · 절단 · NULL-persist 파리티) | fail-open → 머지 이력 |
| 시크릿 / 로깅 / webhook URL / 인증 fail-closed | 주장 vs 기전 대조 |
| 배포·공급망 (railway.toml · buildCommand · 의존성 핀 · audit CI) | silent-disable 클래스 |
| 사용자가 "이 영역은 못 믿겠다" | 소유자 직감은 유효 트리거 |

### 🔴 ops-invariants 단축 패스 (협의 중 Grok 이 Claude 안을 반박해 채택)

Claude 는 "카덴스 트리거를 없애고 회고 **산출 주장**에만 걸자"고 제안했다.
Grok 의 반박이 옳아 수용했다:

> **주장-트리거만으로는 "아무도 주장하지 않은 통제면(control plane)"을 영영 못 본다.**
> 한 번도 실행되지 않은 cron 에는 "봉인했다"는 주장이 없었다 — **주장의 부재**가 있었다.

따라서 **짧은 ops 불변식 체크리스트**를 별도로 둔다 (전체 재감사 ❌):

- 실행되지 않는 설정 (무효 Railway 키 · `JOBS` 미등록 cron · 미배선 SessionStart 훅)
- 라이브 role/env drift (`BYPASSRLS` · `MIGRATION_DATABASE_URL` 부재)
- **통과 조건이 "문자열이 어딘가 있으면"인 검사**

**빈도**: 달력 기반 ❌. 배포/설정/RLS/cron 이 변경된 창에서, 또는 그 영역을 "봉인" 주장할 때만.

### 호출하지 않는다

문서·STATE·i18n 키 추가·CSS / 재현 명확한 로컬 버그픽스 / 구현 중간("이 함수 짜줘") /
계획·백로그 정리·정책 문구 / 5+1 이 이미 같은 파일을 덮었고 신규 "봉인" 주장이 없을 때 /
triage 예산 초과 시(반쪽 패스 금지).

🔴 **회고 카덴스(정책 8 진화 4 — ≥3 세션/≥15 PR)에 Grok full-pass 를 겹치지 않는다** —
3중 파일업이 되어 Codex 시절 피로를 재생산한다.

---

## 역할 분담

| 영역 | 주담 | Grok |
|------|------|------|
| 기능 구현 · 버그픽스 | **Claude** | ❌ |
| 테스트 설계 | **Claude** | Claude 가 green 선언 **후** 뮤테이션만 |
| auto-merge / gate / SHA 결속 | Claude 구현 | **경로 그래프 검토** |
| 인증 / 시크릿 / SSRF | Claude 구현 | **봉인 주장 적대 검증** |
| 점수 무결성 | Claude | fail-open 경로 |
| 배포 / 공급망 | Claude | silent-disable 클래스 |
| DB 마이그레이션 · RLS | Claude | FORCE/ENABLE/앱필터 **bijection 감사**만 |
| 문서 · STATE · 정책 진화 | **Claude 전담** (저술) | 🔴 **소유 금지 / claim-review 허용** — 아래 참조 |
| 계획 · WBS | **Claude 전담** | 🔴 **호출 금지** (`grok_build_plan` 실측 무가치) |

**Grok 이 실제로 나은 지점**: cross-cutting 불변식(그래프 전체에서 나쁜 결과가 여전히 가능한가) ·
**"테스트가 버그를 고정한 경우"** 탐지. 후자는 Claude 가 그 테스트를 쓴 당사자라 구조적으로 못 본다.

---

## 🔴 v2 개정 (2026-07-19 — 첫 실사용 회고 결과)

프로토콜을 만든 세션 안에서 곧바로 실사용(추출기 리뷰)하고 양측이 회고했다. 그 결과 드러난
**구멍 4건**을 규칙으로 승격한다.

| # | 개정 | 왜 |
|---|------|-----|
| **A1** | **`freeze test` 의 의미를 고정** — "테스트 파일이 있다"가 아니라 **봉인한 버그를 되살렸을 때 red 가 되는 테스트**. 되살려도 green 이면 브리프 필드는 `BROKEN freeze: <이름>` 이며 개수 보고가 아니다 | 추출기는 테스트 13건이 **전부 green 인 채로** 174 중 35만 뽑고 있었다. "테스트 있음"은 아무것도 보장하지 않았다 |
| **A2** | **신규 관측자에는 뮤테이션 없이 HOLDS 금지** — 새 seal(완전성 검사·가드·kill-switch)을 만들면 그 seal 자체를 최소 1회 깨뜨려 실패를 확인해야 HOLDS. 실행 주체는 Claude 든 Grok 이든 무방하나 **누군가는 실행**해야 한다.<br>🔴 **A2-b 보강 (2026-07-19 회고 P1 — A2 가 명목상 충족된 채 무동작이었다)**: 뮤테이션 대상은 그 seal 이 **보호한다고 주장하는 실제 운영 경로**(해당 파일/심볼 또는 그 실 의존)여야 한다. **합성 문자열·픽스처만 바꾸는 것으로는 A2 를 충족하지 않는다.** 근거: `#1121` 이 `_scale_without_lock_violation(scaled, "no lock here")` 같은 합성 입력으로 "뮤테이션 실증" 을 PR 본문에 적었으나, **실제 `scheduler.py` 를 넣으면 docstring 이 마커를 만족시켜 축이 죽어 있었다**(replica 5 로 올려도 8 passed). | 이번에 `assert X or True` 와 "folding 을 못 잡는 folding 테스트" 2건이 뮤테이션으로만 드러났다. 관측자를 만들며 관측자-거짓말을 재생산했다 |
| **A3** | **브리프 무결성 자가 점검** — `freeze test: none` 이라 쓰려는데 해당 주제의 `tests/**` 가 존재하면 자동 이의 대상. 쓰기 전에 `ls`/`grep` 로 확인 | Claude 가 "freeze test 없음"이라 썼으나 13건이 있었다. 브리프의 사실 오류는 리뷰 방향을 통째로 틀어놓는다 |
| **A4** | **배포 주장 인터럽트는 기계적 선행 조건** — `배포·활성·RUNNING·봉인` 이 들어간 사용자 대상 문장은 deploy reality 블록 **없이는 작성 자체가 프로토콜 위반**. Grok 호출 여부와 무관하게 먼저 적용된다 | 2-phase 게이트는 옳지만, 거짓 보고는 Grok 이 호출되기 **전에** 일어났다. 게이트가 늦게 걸리면 소용없다 |

### 회고가 새로 명명한 실패 클래스 4종

1. 🔴 **green 스위트가 부패를 인증한다** (SMTP 587 과 동일, 저장소 **2회차**) — 테스트가
   *어제의 세계*를 인코딩한 채 오늘의 고장을 승인한다. 스크립트 버그가 아니라 **재발 클래스**다.
   실제 CSS 대상 완전성 단언이 freeze oracle 이 되기 전까지 스위트는 계속 거짓말한다.
2. 🔴 **backlog 처방문은 검증되지 않은 코드다** — B2 의 처방(`[deploy] numReplicas = 1`)이
   그 자체로 P0 재현이었다. 무효 Railway 키와 **같은 silent-ignore 클래스**인데, 이번엔
   PR 이 아니라 **티켓 형태로** 유입됐다. 처방문도 대조 대상이다.
3. 🔴 **통제면 결함의 인터럽트 지연** — silent-disable 계열(#1119·#1121)은 세션 시작 시
   ops 불변식 패스가 아니라 **머지 작업 중 우연히** 발견됐다. 프로토콜에 패스가 있어도
   실행하지 않으면 없는 것과 같다.
4. **Grok 의 미완 마무리** — 신규 seal 에 대한 뮤테이션을 끝내지 않고 분석에서 멈췄다.
   공동 원장에 기록한다(Claude 단독 항목 아님).

## 🔴 경계 개정 — '호출 금지' 가 아니라 '소유 금지' (2026-07-19 회고 P1)

v1 은 문서·STATE·정책 영역에 **호출 자체를 금지**했다. 그런데 같은 세션에 그 경계를 **두 번**
넘었고(사용자 지시), **두 번 다 Claude 가 놓친 실제 오류를 찾아냈다**:

| 위반 | 결과 |
|------|------|
| backlog 처방문 전수 점검(#1128) | 처방문 **3건이 틀렸음**을 확인 — B2 지시대로 했으면 cron P0 재현 |
| 회고 결과 기반 정책 개정 협의 | 카덴스 트리거 충돌·score-lie 라우팅 등 **내 안 2건이 반박돼 수정** |

즉 규칙이 **유일하게 실효 있는 용도를 막고 있었다**. 경계를 다시 긋는다:

- ❌ **소유 금지 (authoring)** — Grok 은 backlog 처방문·정책 문구를 **저술하지 않는다**.
  제안 문안을 그대로 SSOT 에 넣지 않는다(rule drift 위험은 여기 있다).
- ✅ **claim-review 허용** — 그 문서의 **주장을 공격**하는 것은 허용한다. 조건 =
  사용자 요청이 있거나, CLAIM 이 **seal / HOLDS / 완전성** 부류일 때.
- 📝 **기록 의무** — 그 경우 브리프에 `owner-interrupt: claim-review` 를 명시한다.
  경계를 넘은 사실이 기록되지 않으면 다음 사람이 경계를 오해한다(v1 위반 2건이 미기록이었다).

🔴 **여전히 호출 금지**: 계획·WBS(`grok_build_plan` 실측 무가치) · 구현 중간.

## 브리프 계약 (Claude → Grok)

🔴 **거대 컨텍스트 덤프 금지** — Grok 회고 R3: *"과잉 컨텍스트는 리뷰어를 구조적 논평으로 민다."*
좁은 입력이 예의가 아니라 **경로 증명을 유지하는 수단**이다.

| 필드 | 필수 | 비고 |
|------|------|------|
| **CLAIM** | ✅ | 🔴 **평결이 아니라 공격받을 가설로** 제시 (Grok R1 — 사전 프레이밍이 다양성을 죽인다) |
| **BAD OUTCOME 한 줄** | ✅ | "틀리면 X 가 머지된다 / 시크릿이 남는다 / analyzer 가 꺼진다" |
| **freeze test 이름** | ✅ | 버그 재발 시 **green 이면 안 되는** 테스트. 없으면 `none` 명시 |
| **DIFF** | ✅ | 전체 파일 ❌ |
| **already-mutated 목록** | ✅ | 불릿. `mutated: X 제거 → fail` / `did not mutate: Y` |
| **deploy reality 블록** | 배포·RLS·cron 주장 시 ✅ | 아래 고정 필드 |
| **non-goals** | ✅ | "재설계 금지 · 헬퍼 제안 금지 · i18n 재감사 금지" |

### deploy reality 고정 필드

Grok 은 MCP 가 없어 **Claude 의 배포 진실을 상속**한다 (Grok R5 — *"당신의 거짓 green 이 곧 내 거짓 green"*).

```
service            : SCAManager
deployment status  : SUCCESS | BUILDING | DEPLOYING | WAITING | FAILED
RUNNING commit     : <sha>          ← 🔴 "JSON 어딘가에 언급됨" 이 아니라 실제 RUNNING
replicas (live)    : <n>
last cron fire     : <job> @ <ts>   (해당 시)
rolbypassrls       : app=<bool> worker=<bool>  (RLS 주장 시)
```

---

## findings 계약 (Grok → Claude)

- 🔴 **P0/P1 부여 금지.** 심각도는 Claude/사용자가 매긴다 (P0 정밀도 0/4 근거)
- 대신 **영향 계층 라벨** 필수: `wrong-merge` · `secret` · `fail-open` · `silent-disable` · `score-lie`
- **1회 최대 12건** — 40건 덤프는 사람에 대한 DoS
- **`HOLDS` / `HOLDS with caveat` / `BROKEN`** 명시 — 🔴 **확인도 반증만큼 가치 있다**.
  없으면 Claude 는 "검증됨"과 "아직 아무도 안 봄"을 구별 못 한다
- **`static-only, not reproduced`** 기본 표기 — 실제 실행했을 때만 뗀다
- **신규 추상화 제안 금지** (정책 16). "A·B 에 중복 가드 존재" 서술은 허용, "추출하라"는 ❌
- 조건부 나쁜 결과는 유효: *"tflint 설치 실패 시 Terraform 분석이 조용히 미실행"*

### findings 스키마 (~15줄/건)

```
ID:         GROK-YYYYMMDD-N
CLAIM:      나쁜 결과 한 문장 ("검사 누락" ❌)
PATH:       file → function → next hop (3~6홉)
PRECONDITION: 무엇이 참이어야 하는가
EVIDENCE:   line refs + 기존 테스트가 놓치는 이유
MUTATION:   "X 를 지우거나 뒤집으면 테스트가 여전히 green 인가?" 한 줄
IMPACT:     wrong-merge | secret | fail-open | silent-disable | score-lie
STATUS:     static-only | reproduced
```

---

## 라우팅 (기존 체계 재사용 — 세 번째 taxonomy 금지)

영향 계층은 **라벨로만** 남고, 실제 라우팅은 기존 2체계를 쓴다.

| 영향 계층 | 라우팅 |
|-----------|--------|
| `wrong-merge` · `secret` · `fail-open` | [`owed-verification.md`](owed-verification.md) **안전등급** (SessionStart 훅 집행) |
| `silent-disable` | [`../backlog.md`](../backlog.md) — 단 **사용자 가시 효과 명시 의무** ("언어 X 가 영영 미분석") 없으면 잡무로 죽는다 |
| `score-lie` | 🔴 **merge/gate 에 영향하면 안전등급**. 순수 대시보드 표시 오류만 backlog |

> `score-lie` 분기는 협의 중 Grok 이 Claude 안(전량 backlog)을 반박해 수정된 것이다 —
> 부풀린 점수가 auto-merge 를 유발하면 그것은 대시보드 문제가 아니다.

**처리 흐름**: Grok → 외부 `.md` 기록 → Claude **1회 triage**(확인/강등/기각+사유, 재구현 ❌)
→ **영향 계층 클러스터당 1 PR** (findings 당 1 PR ❌) → 필요 시 Grok 이 **diff 한정** 재확인.

---

## 🔴 2-phase 사용자 보고 게이트

협의 중 **신규 도출**된 규칙. 2026-07-19 Claude 가 배포 미완료 상태를 "활성화됐습니다"로
보고한 사고의 직접 대책이다 — 문제는 "리뷰 부재"가 아니라 **주장이 공격 등급이 되기 전에
사용자 채널을 쓴 것**이었다.

1. **Phase 1 (내부)**: Claude 가 CLAIM + freeze test + deploy reality 제시 →
   Grok 또는 자체 뮤테이션이 `HOLDS` / `BROKEN` / `STATIC-ONLY-UNVERIFIED` 반환
2. **Phase 2 (사용자)**: **`HOLDS` 또는 `HOLDS with caveat` 만** 사용자에게 간다.
   배포·RLS·cron 주장의 `STATIC-ONLY-UNVERIFIED` 는 **보고 불가**

**마이크로 규칙**: `배포 | 활성 | 봉인 | 운영 | cron 실행됨` 이 포함된 문장은
라이브 deploy reality 필드를 동반하거나 **`UNVERIFIED:` 접두사**를 붙인다.

---

## 안티패턴

1. Grok 을 동일 브랜치 **공동 구현자**로 (편집 경합 · 컨벤션 파괴)
2. `grok_build_plan` / 위원회식 공동 설계 (실측 0)
3. **Grok 심각도를 우선순위로** 채택 (정밀도 0/4)
4. **매 PR 마다** Grok (비용 + 지연 + triage 세금)
5. 확정 버그 없이 Grok 이 테스트를 "개선"하기 (스위트 컨벤션과 충돌 + 거짓 확신)
6. Claude 가 **서사로 방어**하기 ("가드 있습니다") — Grok 이 제시한 뮤테이션을 **실행하지 않고**
7. 작은 변경에 3중 파일업 (5+1 + whole-branch + Grok + 사용자)
8. Grok 이 **문서·정책 진화** 소유
9. 같은 P1 을 **양쪽이 병렬 수정** (중복 PR)
10. 협업을 **공정성 목표**로 취급 — 새 경로를 못 더하면 턴을 강제하지 않는다

---

## 양측 자기 한계 (본인 진술)

**Grok**: 지속적 정책 캐시 없음 → "늘 하던 방식"을 놓침 / 불확실 시 **심각도 과대평가**(성격 아닌
알려진 편향) / 라이브 운영 사실(BYPASSRLS · 무효 Railway 키)은 probe 없이는 못 봄 /
다중 파일 컨벤션 보존 구현은 Claude 보다 약함 / **정교한 busywork** 생성 가능 —
*"우아함이 아니라 나쁜 결과로 필터링하라"*.

**Claude**: 자기 가드를 뮤테이션 없이 신뢰 / 저장소가 이미 문서화한 함정을 반복 /
그럴듯한 거짓 주장 작성(`#1104` "2계층 봉인") / **통과가 주장하는 의미가 아닌 검사를 작성** /
🔴 **관측자를 거짓말하게 둔 채 코드만 수정**(observer-lie).
