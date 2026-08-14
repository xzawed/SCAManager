# 흐름 — 커밋부터 머지까지

> **언제 여는가**: 작업을 마치고 올릴 때. 정책 7(PR 단위)·6-step 의 **실행 순서**를 담는다.
> 규정의 정본은 [`CLAUDE.md`](../../CLAUDE.md) 다 — 여기는 **어디서 막히고 어떻게 뚫는가**.

---

## 1. 착수 — 브랜치부터

```bash
git checkout main && git pull
git checkout -b <type>/<scope>          # feat/ fix/ chore/ docs/
gh pr list --state open                 # 같은 파일 건드리는 미머지 PR 확인
```

**마지막 줄이 6-step ⑤ 분기를 가른다 — STATE·README 배지를 건드리는 미머지 PR 이 있으면
수치 갱신을 **trailing sync 로 이월**한다.

---

## 2. 커밋 전 — 전체 스위트

```bash
py -3 -m pytest tests/unit -q      # 🔴 예외 없음 — 문서 전용 PR 도
py -3 scripts/pre_push_gate.py     # 게이트 전건
```

**문서만 바꿨으니 생략해도 된다는 판단은 틀렸다** — 2026-08-13 에 그렇게 판단했고
본문 수치 축이 red 로 반증했다. 6-step ② 에 예외가 없다고 적혀 있다.

---

## 3. 커밋 — 훅이 파일을 고치면 다시 stage

pre-commit 이 `end-of-file-fixer` 등으로 파일을 고치면 **커밋은 실패한다**.
`git add -A` 후 재시도한다. 실패를 못 보고 push 하면 브랜치가 옛 상태로 올라간다.

---

## 4. PR 본문 — 막히는 3지점

### 4-a. 수치 축

본문에 `pytest tests/unit … N passed / M skipped` 를 적으면 **실측과 대조된다**.
🔴 리베이스했으면 **다시 재고 적는다** — base 가 앞서가면 직전 수치가 그 순간 stale 이다.
(집행: `scripts/check_test_count_sync.py` 본문 수치 축)

### 4-b. 정책 19 흔적

*봉인·완결·fail-closed* 어휘가 있으면 claim-review 흔적 3필드가 필요하다.

```
- session: <id>
- claim: <무엇을 주장하는가>
- verdict: WEAKENED (축별 부연은 괄호로)
```

🔴 **`verdict:` 뒤 첫 토큰이 enum 이어야 한다.** `**C1 WEAKENED …` 처럼 쓰면 매칭 실패다.
(집행: `scripts/check_claim_review_trace.py`)
흔적은 **벤더 무관** — 회고 cross-verify 패스도 유효하다.
**정정 기록이 가장 걸리기 쉽다** — *"내 봉인 주장은 거짓이었다"* 도 어휘 탐지에 걸린다.

**push 전 로컬 검증으로 CI 왕복을 아낀다**:

```bash
PR_TITLE="$(gh pr view N --json title --jq .title)" \
PR_BODY="$(gh pr view N --json body --jq .body)" \
PR_BASE_SHA="$(gh pr view N --json baseRefOid --jq .baseRefOid)" \
PR_HEAD_SHA="$(gh pr view N --json headRefOid --jq .headRefOid)" \
py -3 scripts/check_claim_review_trace.py
```

### 4-c. 본문 편집은 required check 를 갱신하지 못한다

`gh pr edit --body-file` 만으로는 CI 가 **옛 본문**을 읽는다.
→ **빈 커밋을 하나 더 민다.** 실측 4회(backlog R34).

---

## 5. 머지 후 — 확인까지가 한 단위

```bash
git checkout main && git pull
gh run list --branch main --limit 2       # main 이 초록인지
git merge-base --is-ancestor <sha> origin/main   # 내 커밋이 실제로 들어갔는지
```

**머지된 브랜치에 커밋을 얹지 마라.** push 출력의 `* [new branch]` 는
브랜치가 삭제됐다가 재생성됐다는 신호다 — 그 커밋은 고아가 된다(2026-08-13 실사고).

**PR 컨텍스트에서 관측 불가한 축이 있다** — 이월 마커가 push 이벤트에서도 인식되는지는
**머지 후에만** 확인된다.

---

## 6. 이월했으면 종결까지

`STATE-sync-deferred:` 를 썼다면 그 세션 안에 **trailing sync PR** 로 닫는다.
🔴 마커는 **PR 본문이 아니라 커밋 메시지**에 — 본문은 push 이벤트에 전달되지 않는다.
(집행: `scripts/check_test_count_sync.py`)

⚠️ 이월의 비용: 여러 PR 이 배치로 미루면 **per-PR 귀속이 사후에 재구성되지 않는다**.
종결 PR 에 per-PR 실측을 남기는 편이 낫다.

---

## 이 흐름이 막지 못하는 것

- **CI 가 보지 못하는 축** — CodeQL·Sonar·Codecov·TruffleHog·pip-audit·lint-js·PG job·통합테스트.
  `pre_push_gate` 가 매 실행 인쇄한다.
- **로컬 3.14 ↔ CI 3.12 이원** — 버전 의존 회귀는 로컬이 못 잡는다(backlog R30).
