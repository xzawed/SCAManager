# 문서·가드 정리 — 진행 상태 (정본)

> **이 파일이 정본이다.** 계획 전문은 [`docs-consolidation-plan.md`](docs-consolidation-plan.md),
> 근거가 된 감사는 [`_archive/reports/2026-08-10-docs-system-audit.md`](../_archive/reports/2026-08-10-docs-system-audit.md)
> 와 [`2026-08-11-docs-scoring-report.md`](../_archive/reports/2026-08-11-docs-scoring-report.md) 다.
>
> 🔴 **착수 전 반드시 이 파일부터 읽는다** — 이미 완료된 묶음을 다시 하면 순손실이다.

## 지금 어디까지 왔나

| PR | 묶음 | AR | 상태 | 산출 |
|----|------|----|------|------|
| **1** | B 실행 오인 어휘 전역화 | 9 | ✅ **완료** (`#1328`) | `fix/plan-execution-cue-global` — 표지 11 + 가드 6축 |
| **2** | J 처분 지시 철회 + 원장 등재 | 6 | ✅ **완료** (`#1329`) | backlog **R78** = 등재 3건 전량 (아래 §PR-2) |
| **3** | E SESSION_SECRET 3분기 정정 | 6 | ✅ **완료** (`#1330`) | `fix/session-secret-doc-parity` — 문서 3지점 + 실행 가드 6 |
| 4 | A pylint 진리값 (10.00→9.99) | 4 | 🟡 **PR-5 선행** | 배지 5지점 + 집행자 |
| 5 | C 게이트 예산 거짓 집행자 교체 | 3 | ⏸️ PR-4 대기 | 🔴 순서 역전 시 거짓 봉인 |
| 6 | D 가드 개수 산문 파생화 | 4 | 🟡 | 문서 9지점 |
| 7 | F 배선·인벤토리 파생화 | 4 | 🟡 | PR-6 이후 |
| 8 | G architecture = 가드 배선 SSOT | 4 | 🟡 | `.claude` 등재 0건 해소 |
| 9 | H 라우트↔문서 동기 가드 | 2 | 🟡 | PR-8 이후 |
| 10 | I 봉인 함정·주석 drift | 2 | 🟡 | PR-7 이후 |
| 11 | trailing sync | — | 🟡 | PR-4 이후 브랜치 컷 |
| 12 | K 데이터셋 v2 | — | ⏸️ **보류** | red 불가 (사용자 승인 시에만) |

**다음 착수** = PR-4 → PR-5 (🔴 **순서 강제** — 역순이면 pylint 거짓값 10.00 이 기계로 봉인된다).
그 다음 PR-6 → PR-7 → PR-8 → PR-9/10, 마지막에 PR-11(trailing sync).

> 🔴 **PR 번호와 backlog ID 는 다른 축이다 (2026-08-11 실사고)**: 계획서 §PR-2 는 신규 등재를
> `R75`·`R76`·`R77` 로 적었는데, 그 세 ID 는 계획 작성과 **같은 창에** 2026-08-04 회고 findings
> 가 이미 가져갔다(`R75` api_error 원인 부재 · `R76` 본문 수치 축 · `R77` import 시점 자격증명
> 인쇄). 실제 등재는 `#1329` 가 **`R78` 한 행에 (a)(b)(c) 로 통합**했다. 계획서의 ID 는 읽지 말고
> **backlog 현재 MAX+1** 을 쓸 것 — 원장 ID 를 계획서가 예약할 수 없다.

## 다른 PC 에서 이어가는 절차

```bash
git checkout main && git pull
py -3 scripts/check_memory_refs.py          # 메모리 경로 유도 (슬러그 하드코딩 금지)
py -3 scripts/pre_push_gate.py              # 현재 상태 확인
cat docs/runbooks/docs-consolidation-status.md   # 이 파일
```

🔴 **메모리는 리포와 함께 이동하지 않는다** — `~/.claude/projects/<슬러그>/memory/` 는 PC 로컬이다.
과거에 PC 이전으로 메모리 6건이 유실된 전례가 있다(MEMORY.md 하단 복원 기록). 새 PC 에서
메모리가 비어 있으면 그 사실 자체를 먼저 사용자에게 보고할 것.

🔴 **`make` 이 없는 머신이 있다.** push 전 게이트는 `py -3 scripts/pre_push_gate.py` 다.

## PR-2 — 처분 지시 철회 + 원장 등재 (✅ `#1329` 완료)

🔴 **가드는 기각됐다** — 리포 내 실제 처분 지시가 0건이라 red 를 만들 수 없다. 그래서 산출물은
backlog 등재뿐이었고, 그 등재는 `#1329` 가 **`R78` 한 행**으로 이미 내보냈다. 등재 대상 3건이
그 행의 (a)(b)(c) 에 1:1 로 들어 있다:

1. (a) RRS 순위 발행 금지 — 채점 체계는 계측기로만 보존
2. (b) `glossary.md` 처분 철회 근거 — 실행 시 `scripts/i18n_comments/translate_comments.py:48` 런타임 파손
3. (c) 소비자 수집 4모드 미구현 (경로 조립 · 정규식/glob · bare-basename · 디렉토리 glob)

그 결과 *"증명 없는 이동 금지"* 에는 **집행자가 없다**(발행 규칙으로만 존속) — R78 본문이 그
공백을 명시한다. **이 묶음에 남은 작업은 없다.** 확인 방법: `grep -n '^| \*\*R78\*\*' docs/backlog.md`.

## 🔴 이 계획이 서 있는 전제 (뒤집지 말 것)

1. **총량은 비용 문제가 아니다** — 게이트는 세션 비용의 0.48%, 리포 전체 통독도 2.6%.
   문서를 0자로 줄여도 97%가 남는다. **용량 절감을 근거로 한 정리안은 기각**된다.
2. **문서 삭제·경로 이동 0건** — 이동 시뮬 9/9 가 근거 자체를 소멸시켰고,
   `translate_comments.py:48` 은 실제 런타임 파손이다. 소비자 grep 증명 없는 이동은 금지.
3. **채점 체계(RRS)는 순위를 발행하지 않는다** — 검증 2라운드에서 BROKEN 판정.
   편집 불변성 없음(공백 커밋 1회로 처분 26건 소멸) · 관측자 오염(감사 세션이 분모 안) ·
   접근축 93%가 부수 등장.
4. **정책 17** — 외부 권장 규격은 가이드라인이고 안정성과 충돌하면 거부한다.
   `CLAUDE.md`·`AGENTS.md` 축소는 `#1296` 에서 순손실이 실증됐다.

## 검증이 닿지 않은 범위 (정직 표기)

`.claude/agents|skills` 본문 ↔ 코드 · `docs/runbooks/**`(구 `guides`·`integrations` 통합분) ·
`docs/runbooks/**`(1건 외) · ko 번역쌍 원본 대조 · `docs/_archive/**` 62건.
3라운드 검증 어디에서도 대조되지 않았다 — 여기서 나온 주장은 근거가 없다고 보아야 한다.

## 재현 — 측정 데이터셋

[`_archive/reports/2026-08-11-doc-metrics.json`](../_archive/reports/2026-08-11-doc-metrics.json)
(199 문서 × 9축: 세션 접근 · 툴 읽기/편집 · 6개월 커밋 · 최종수정 · 인바운드 링크 ·
코드 소비자 · 자동로드 멤버십 · 크기).

🔴 **이 데이터셋은 무결하지 않다** — 검증이 지목한 결함을 그대로 적는다:
- `code_consumers` 는 **경로 리터럴 grep** 이라 위음성 4종(경로 조립·정규식/glob·bare-basename·디렉토리 glob)
- `consumer_files` 는 **정렬 후 앞 8개 절단** (CLAUDE.md 43→8)
- `days_since_edit` 의 65.8% 가 **일괄 스윕 커밋** 타임스탬프
- `sessions_touched` 는 **부수 등장 포함**(실제 Read/Edit 대상은 9건뿐) + 감사 세션 자신이 분모 안

재수집하려면 위 4개 결함을 먼저 고칠 것. 고치지 않은 채 순위를 발행하면 같은 오탐이 재생산된다.
