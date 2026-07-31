# 5+1 회고 — 2026-07-31 (범위 #1221~#1247 + 본 세션 자기 산출물)

> 정책 8 다중 에이전트 회고. 실행 = `.claude/workflows/retrospective.mjs` (run `wf_d58ff24d-f4d`).
> 이 파일의 존재가 **회고 카덴스 카운터를 리셋**한다(`check_retro_cadence.py` 는 `_archive/reports/`
> 최신 `*retrospective*.md` 이후 머지 PR 을 셈).
>
> 🔴 **직전 회고(2026-07-26)의 R1 이 "회고 보고서 아카이브 미이행 3회차" 였다.** 이번 세션은
> 회고 산출 직후 이 파일을 먼저 기록해 4회차를 만들지 않았다. 다만 이것은 여전히 **인간/에이전트
> 규율**이고 기계 집행이 아니다 — R1 의 근본(워크플로가 보고서를 쓰지 않음)은 미해결이다.

## 실행 지표

| 지표 | 값 |
|------|-----|
| 범위 | 22 PR (#1221~#1247), 경계 `67e2ed7..9b37c1e` (기계 산출 `scripts/retro_scope.py`) + 본 세션 산출물 |
| 관점 | 5종(process·code·docs·decision·tooling) + completeness critic (+1) |
| 라운드 | 3 (loop-until-dry: 신규 37 → 37 → 41) + completeness gap **8건** 표적 라운드 |
| 에이전트 | **188** (0 error · 0 skipped · 0 empty) · 16.9M 토큰 · 4145 tool calls · 225분 |
| findings_total | **164** |
| **verdict_coverage** | **1.0** (전건 검증 — UNVERIFIED **0**) |
| ROI | 확정 **156** (P0 **8** · P1 **72** · P2 **76**) · severity_adjust **42** · **false-positive 차단 8** |
| 인용 검증 | `citation_verified` **154/156** |

> P1 72·P2 76 은 **관점 중복 포함** 수치다. 루트로 묶으면 P1 은 약 **13 클러스터**.

### 병행 실행한 Grok claim-review (정책 19)

같은 세션에서 ops-불변식 단축 패스를 별도로 돌렸다 — 회고 카덴스에 full-pass 를 겹치지 않는다는
프로토콜 규칙을 지키기 위해 **주장 트리거 + 통제면**으로 범위를 좁혔다.

| 항목 | 값 |
|------|-----|
| Grok session | `019fb7fd-a005-7c21-9ee8-11ffde668d54` (owner-interrupt: claim-review) |
| CLAIM A | CLAUDE.md 의 "배선 가드는 실행 기전을 단언한다" → **BROKEN** |
| CLAIM B | 창의 신규 seal 2종이 3-불변식 충족 → **HOLDS with caveat** |
| 뮤테이션 검증 | `wf_30d60394-312` — 24 에이전트 · 12 뮤테이션 **전건 적용 증명** · 적대검증 **0건 뒤집힘** |
| 결과 | **11 GREEN(fail-open 확정)** / 1 RED |

🔴 **회고와 Grok 이 독립적으로 같은 뿌리에 도달했다** — 회고 P0-5·P0-7(훅 회귀 가드 0)과
Grok CLAIM A(배선 판정 substring)는 같은 관측자 결함의 서로 다른 축이다. 교차 검증으로 본다.

---

## 지배 주제

### 1. 지배 서사가 **그 서사를 고친 PR 자신에게서** 재생산됐다

창의 헤드라인은 "가드가 초록인데 아무것도 검증하지 않았다"(eslint/tsc 런타임 무동작 #1228,
훅 6종 무동작 #1243)였다. 회고가 확인한 것은 그 시정들이 **같은 결함을 자기 안에서 반복**했다는 것이다.

| 시정 | 무엇을 고쳤나 | 무엇이 재생산됐나 |
|------|--------------|------------------|
| `#1243` 훅 6종 부활 | `python` → `PY=$(...)` 폴백 | **회귀 가드 0건** — bare `python` 으로 되돌려도 전 스위트 green (뮤테이션 실증). 정책 4 정면 위반 |
| `#1244` 원자적 claim | `with_for_update()` 행 잠금 | **잠금이 무동작** — `populate_existing()` 부재로 identity map 이 stale 값 반환. 게다가 테스트가 SQLite 라 `FOR UPDATE` 자체가 발행되지 않아 삭제 뮤테이션도 green |
| `#1230` 정책 19 집행면 | seal 주장에 claim-review 흔적 강제 | **면제 마커가 계량되지 않음** — 생성 66분 만에 자기 적용, 창의 post-guard seal PR 10건 중 **5건이 면제로 통과**. HTML 주석 안의 흔적도 인정 |
| `#1229` 공허화 차단 | lint-js 검사 범위가 비면 fail | 개념이 **eslint 에만** 적용되고 가드 스크립트 자신에는 일반화되지 않음 — B8 은 스캔 범위를 비우면 "fail-open 0" 을 출력하며 초록 |

### 2. **관측자가 자기 범위를 관측하지 않는다** (신규 명명)

이번 회고가 새로 이름 붙인 클래스다. 기존 3-불변식은 "가드의 **판정**이 산문으로 충족되는가"를 묻는데,
여기서 드러난 것은 한 단계 위다 — **가드가 무엇을 보고 있는지(범위) 자체에 관측자가 없다.**

- `check_memory_refs.py` 는 `MEMORY_DIR` 이 **구 PC 슬러그**(`d--Source-SCAManager`)에 하드코딩돼
  이 머신에서 **한 번도 실행된 적이 없다**. graceful-skip 분기가 항상 타서 exit 0. 실경로로 돌리면
  **exit 1, dangling 4~5건**(그중 하나는 CLAUDE.md 가 자기 정책 근거로 인용하는 메모리).
- `check_guard_fail_open.py`(B8) 는 스캔 범위를 비워도 "check 가드 N개 — fail-open 0" 을 출력한다.
  범위가 0이어도 성공 문구가 나온다.
- `check_docs_sync.py` 는 **문서 사본끼리만** 대조한다. 4지점이 **함께 틀리면** 원리적으로 초록이다
  (뮤테이션 실증). 실제로 HEAD 에서 4지점이 전부 거짓인데 초록이었다.

세 사례 모두 "판정 로직"은 멀쩡하다. **입력이 비어 있거나 틀린 곳을 가리키는데 아무도 세지 않는다.**

### 3. 로컬 보호 계층이 통째로 내려가 있다

`pre-commit` 미설치를 관측하는 면이 리포 전체에 없다. 결과로 **시크릿 훅 5종이 창 22 커밋 내내
0회 실행**됐다. CI 의 TruffleHog `--only-verified` 는 이 클래스를 대체하지 못한다(검증된 시크릿만 본다).

---

## P0 (확정 8건 → 4 뿌리)

### A. CLI supersede 의 '원자적 claim' 이 무동작 — 패자도 gate·notify 실행 (P0-1·3·4)

`src/worker/pipeline.py:678`

`_claim_and_supersede_cli` 는 `db.query(Analysis).filter(id==...).with_for_update().one_or_none()`
로 행을 다시 읽고 `not _is_cli_only(locked)` 로 패배를 판정한다. 그러나 `analysis` 객체가 이미 같은
Session 의 identity map 에 **만료되지 않은 상태로** 존재하므로, SQLAlchemy 는 `populate_existing()`
없이는 SELECT 결과를 **버리고 캐시된 인스턴스를 반환**한다.

→ 승자가 이미 `source` 를 pr/push 로 바꿔 commit 한 뒤에도 **패자에게는 여전히 `source == "cli"`**
로 보인다 → 패자도 supersede 를 수행하고 `created=True` 가 되어 **gate(auto-merge 시도) + notify
(Telegram/PR 코멘트)가 2회** 실행된다. Postgres 에서도 동일하다(FOR UPDATE 는 SQL 잠금만 하고
ORM 속성 갱신은 별개).

🔴 **이 봉인을 '증명'하는 테스트는 in-memory SQLite 를 쓴다.** SQLAlchemy 의 SQLite 방언은
`FOR UPDATE` 를 **조용히 버리므로**, `.with_for_update()` 삭제 뮤테이션조차 red 를 만들지 못한다.
즉 guards.md 3-불변식 ②(실경로 뮤테이션 red) 미충족 상태로 '원자적' 이 주장됐다.

**처방**: `populate_existing()` 추가(또는 `db.refresh(locked)`) + 회귀 가드를 **두 개의 독립
Session**으로 재작성(승자 commit → 패자 claim 순서에서 `None` 단언) + PG 전용 경합 테스트를
`ci.yml` `pg-concurrency` job 에 등재(`threading.Barrier` 동반 — testing.md 규칙).

### B. #1243 '훅 6종 부활' 에 회귀 가드 0 (P0-5·7)

창의 최대 P0(보안 훅 `block_credential_dump` 포함 6종이 Windows Store 스텁 exit 49 로 한 번도
실행된 적 없음)를 `#1243` 이 고쳤으나 **그 결함 클래스를 탐지하는 테스트를 한 건도 추가하지 않았다.**
배선 가드 3종은 전부 **명령 문자열의 텍스트**만 관측하고 그 명령이 **실제로 실행되는가**는 보지 않는다.

실측: `settings.json` 을 bare `python` 으로 되돌리는 뮤테이션에서 **16/16 green**, 61 테스트 전부 green.

**처방**: settings.json 의 각 훅 command 를 **문자열 그대로 subprocess 실행**해 exit code 계약을
단언(`returncode != 49`). 최소형은 `test_credential_dump_hook._run_hook` 이 `sys.executable` 대신
settings.json 의 command 를 쓰도록 바꾸는 것.

🔴 **본 세션 PR #1248 은 이 축을 절반만 닫았다** — `echo` 데코이는 거부하지만 `python` 은
allowlist 에 있어 bare `python` 회귀는 **여전히 통과**한다. 정직하게 미해결로 남긴다.

### C. `check_memory_refs` 가 이 PC 에서 한 번도 검사한 적 없음 (P0-6·8)

`scripts/check_memory_refs.py:22` 의 `MEMORY_DIR` = `~/.claude/projects/d--Source-SCAManager/memory`
(구 PC `D:\Source\SCAManager` 슬러그). 실경로는 `f--DEVELOPMENT-SOURCE-CLAUDE-SCAManager`.
→ graceful-skip 이 **항상** 타서 `⏭️ 메모리 디렉토리 없음` + exit 0.

같은 죽은 경로가 `tests/unit/scripts/test_lint_gate_wiring.py` 에도 있어
`test_no_dangling_memory_references_in_repo` 가 **모든 환경에서 skip** 된다(CI 는 메모리 디렉토리가
원래 없어 skip 이 설계, 로컬은 경로가 틀려 skip).

🔴 **이 창이 만든 `#1225` 새 PC 셋업 런북이 그 잘못된 경로를 정본으로 인쇄했다** — "이식용 런북"이
이식으로 깨진 경로를 3회차 왕복시켰다.

### D. STATE/README 테스트 수치 4지점이 전부 거짓 (P0-2)

문서 `전체 6205(단위 6040 + 통합 165)` vs HEAD 실측 `전체 6213(단위 6043 + 통합 170)`.
창의 마지막 PR `#1247` 이 테스트 8건을 추가하고도 6-step ⑤("예외 없음")를 수행하지 않았다.

🔴 **4지점이 똑같이 틀린 값으로 합의**하고 있어 문서만 보면 반증이 불가능하다.
`check_docs_sync` 는 문서 사본끼리만 대조하므로 이 실패 모드를 **원리적으로 못 본다**(뮤테이션 실증).

**근본 처방**: CI test job 에서 `pytest --collect-only -q` 의 collected 수를 STATE 정규식 값과
대조(로컬 pre-commit 은 속도 때문에 현행 doc-to-doc 유지).

---

## P1 루트 클러스터 (72건 → ~13)

| # | 클러스터 | 건수 | 핵심 |
|---|---------|-----:|------|
| 1 | 6-step ⑤ 미이행 · STATE drift | 11 | P0-D 의 파생. `/docs-sync` 스킬이 통합 카운트를 상수 154 로 하드코딩 · trailing sync 이월 규칙에 종결 조건 없음 |
| 2 | 정책 19 집행면 결함 | 9 | 면제 마커 미계량(5/10 사용) · HTML 주석 안 흔적 인정 · 세션 id 재사용 무탐지 · seal 어휘가 이 리포 관용구('뮤테이션 N건 red')를 못 잡음 · 집행면이 정책 SSOT 4곳 어디에도 없음 |
| 3 | 메모리 경로 stale | 8 | P0-C 의 파생. CLAUDE.md '매 작업마다 메모리 grep' 단계가 두 축 모두 틀려 항상 빈 결과 |
| 4 | `#1244` 커버리지 승격 부작용 | 7 | 🔴 **조달 불가 언어(css/scss·dart·powershell·protobuf)의 auto-merge 영구 차단** — `#1245` 가 스스로 "해서는 안 된다"고 적은 동작 · 가시화가 6채널 중 GitHub 코멘트 1곳에만 구현 |
| 5 | 훅 인터프리터 회귀 가드 0 | 6 | P0-B 의 파생 |
| 6 | backlog 원장 정확성 | 6 | R9 는 해소됐는데 🟡 유지 · R2-b 반증수단이 원리적으로 측정 불가(404) · 요약표 🔴 1건인데 실제 3건 |
| 7 | eslint fail-closed 오탐 | 4 | 🔴 `ruleId:null` 을 전부 '미린트' 로 오판 → **흔한 `eslint-disable` 주석 하나로 PR 전체가 오판** · 미설정 룰 참조가 severity=ERROR 오탐으로 집계돼 **점수를 깎음**(실측 재현) |
| 8 | 로컬 보호 계층 부재 | 2 | 🔴 pre-commit 미설치 관측면 0 → **시크릿 훅 5종 22 커밋 내내 0회 실행** |
| 9 | B8 스캔 범위 무관측 | 2 | 범위를 비워도 "fail-open 0" 성공 문구 출력 |
| 10 | architecture.md stale | 2 | 창에서 P0 로 정정한 `claude -p` 서술이 이 문서에만 생존 |
| 11 | 작업트리/grep 오염 | 2 | 🔴 **루트 grep 결과 100% 인플레** — 리포 루트 아래 worktree. 정책 6(line 인용 실측)·정책 16(공유 로직 전수 grep)의 **입력이 구조적으로 파괴** |
| 12 | owed 원장 0행 | 2 | 22 PR·2 세션 종료 동안 0행. 창의 헤드라인 봉인들의 라이브 검증이 추적면 밖 |
| 13 | 기타 (문서 약속·규칙 sync) | 11 | CONTRIBUTING 이 존재하지 않는 기계 강제를 약속 · path-scoped rules sync 의무가 코드 PR 7건 중 6건 미이행 |

---

## 🔴 회고가 본 세션 자신을 잡은 것 (정책 8 진화 5)

범위에 "세션 자신의 산출물" 을 포함한 default 가 실제로 작동했다.

- **클러스터 11 (루트 grep 100% 인플레)** = 본 세션이 만든 뮤테이션 worktree 24개가 리포 루트 아래
  `.claude/worktrees/` 에 생성된 결과. 회고 도중 에이전트가 `git worktree list` 로 직접 관측했다.
- 실측: `.claude/worktrees/` 는 **gitignore 되지 않는다**(`git check-ignore` exit 1) → 메인 트리에서
  `git add -A` 시 worktree 전체가 스테이징되는 실제 위험이 있었다.
- 조치: 회고 종료 직후 worktree 3개 회수 + `.gitignore` 등재(본 PR).

---

## false-positive 차단 8건 · severity 조정 42건

cross-verify 가 실제로 걸러낸 것들이다. 대표 사례:

- **P0 → P1 강등**: `#1243` 의 "fail-closed" 주장 거짓 건. 사실은 전부 확인됐으나
  (`dev-secret-change-in-production` = **31자**라 길이 검사로 통과 불가, `config.py:222` 의 하드코딩
  예외 분기가 통과시킴), **시정 자체는 작동**하고(`cp .env.example .env` 경로는 차단됨) 잔여 노출은
  선재 항목이며 다층 완화가 있어 P1 로 조정. 검증관이 4개 경로를 직접 실행해 판정했다.

---

## 다음 세션 인수인계

**이번 세션 처리**: P0 4뿌리 전량 이행(사용자 결정) + P1/P2 backlog 등재.
**미해결 잔여**: [`docs/backlog.md`](../../backlog.md) R16 이후 참조.

🔴 **R1(회고 보고서 아카이브 기계화)은 여전히 미해결이다.** 이번 파일은 규율로 썼을 뿐,
`retrospective.mjs` 는 지금도 보고서를 쓰지 않는다. 4회차를 막은 것은 기계가 아니다.
