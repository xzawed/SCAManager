---
description: 문서·원장 편집 시 적용되는 SCAManager 규칙 (path-scoped)
paths:
  - "docs/**"
  - "README.md"
  - "README.ko.md"
  - "CLAUDE.md"
  - "AGENTS.md"
---

# 문서·원장 편집 규칙

> 🔴 이 파일이 자동 로드된다 = 당신은 지금 **이 리포에서 가장 자주 편집되는 표면**을 만지고 있다
> (실측: 최근 1개월 docs/README touch **388회** vs src **233회**). 그런데 2026-08-05 이전까지
> 이 표면에는 **로드 시점 규칙이 하나도 없었다**(`.claude/rules` 56개 path 패턴 중 docs 매칭 0).
>
> 🔴 **여기 적힌 것은 새 규범이 아니라 이미 사고로 확인된 것뿐이다.** 문서 감사가
> *"규칙 파일을 늘리면 stale 문서가 하나 더 생긴다"*(backlog R43: rules sync 이행률 0%)고
> 경고했으므로, 추측성 지침은 넣지 않는다. 새 항목은 **실제 사고 뒤에만** 추가한다.

## 🔴 수치는 손으로 여러 곳에 적지 않는다 — SSOT 는 이력 꼬리 한 줄

테스트 수는 5지점에 복제돼 있었다(STATE 종합 · STATE 추적셀 머리 · 이력 꼬리 ·
README 배지 · README.ko 배지). **N지점 동기화 의무는 N-1번의 실패 기회**다.

- **손으로 고치는 곳**: `docs/STATE.md` §테스트 수 추적 이력 **맨 아래 한 줄**뿐.
- **나머지 4지점**: `py -3 scripts/check_docs_sync.py --fix` 가 그 한 줄에서 **파생**한다.
- 형식이 곧 계약: 항목은 `… (A→**B** 단위 … = **C** 수집)` 처럼 **단위와 누계를 모두** 담는다.
  수치 없는 항목이 꼬리에 오면 가드가 **red** 다(형식 미준수 자체가 실패).
- 🔴 **표 셀에 다시 적지 말 것** — 이력이 표 셀 안에 있던 시절 그 줄은 **30,806자**였고,
  머리와 꼬리가 30,752자 떨어져 있어 한쪽만 고치는 사고가 실제로 났다.

## 🔴 원장(ledger)에 "해당 없음" 을 적으면 기계가 "해당 있음" 으로 센다

`docs/runbooks/retro-cadence-deferrals.md` 에 *"승인 아님"* 이라고 **산문으로 적은 행**을
넣었더니, 파서가 셀이 비어있지 않다는 이유로 **"이월 승인 기록됨"** 을 인쇄했다(2026-08-05).

**계약**: 원장은 행의 **존재**로 판정된다. 부정·유보·주석은 **행을 만들지 말고** 산문 단락에
적는다. 산문이 부정해도 기계는 행만 본다 — 이 리포가 반복해 온 observer-lie 의 원장 판이다.

같은 규칙이 `docs/runbooks/owed-verification.md`(append-only, 행 삭제 금지)에도 적용된다.

## 🔴 파생 집계는 손으로 유지하지 않는다

`docs/backlog.md` 의 상태 요약(`🔴 N · 🟡 M · ✅ K`)은 표에서 파생되는 값인데 손으로 적혀 있고,
`test_backlog_shape.py` 가 bijection 을 강제한다. 상태 하나를 바꾸면 **요약도 함께** 고쳐야 한다
(실제로 이번 세션에 빠뜨려 red 가 났다). 요약을 고칠 때는 눈대중 대신:

```bash
py -3 -c "import re,pathlib,collections; c=collections.Counter(
 m.group(1) for m in re.finditer(r'^\| \*\*R\d+\*\* \| (.)', pathlib.Path('docs/backlog.md').read_text(encoding='utf-8'), re.M)); print(c)"
```

## 🔴 문서를 **옮기면** 관측자가 조용히 죽는다

경로를 하드코딩한 소비자가 실재한다 — 이름 변경·이동 전에 반드시 grep 한다:

| 문서 | 소비자 |
|---|---|
| `docs/STATE.md` | `check_docs_sync.py` · `check_test_count_sync.py` · `doc_review_gate.py` |
| `docs/architecture.md` | 아키텍처 트리 sync 가드 |
| `docs/backlog.md` | `test_backlog_shape.py` |
| `docs/runbooks/owed-verification.md` | SessionStart `check_owed_verification.py` |
| `docs/runbooks/retro-cadence-deferrals.md` | SessionStart `check_retro_cadence.py` |
| `docs/reference/env-vars.md` | env 인용 sync 가드 |
| `CLAUDE.md` · `AGENTS.md` | `doc_review_gate` 컨텍스트 · `check_memory_refs` |

**내용 재구조화는 해도 되지만 경로는 두는 것**이 기본값이다(2026-08-05 STATE 분해가 그 형태).

## 🔴 인용한 `file:line` 은 `grep -n` 실측값이어야 한다

정책 6. 추정 라인은 자연 drift 로 조용히 거짓이 된다(실제 drift 5건 시정 이력).
가능하면 커밋 해시를 병기한다 — `ai_review.py:89 (#218)` 형태.

## 아카이브 표기

`docs/_archive/**` 는 **그 시점의 사실 기록**이다. 나중에 반증된 내용이라도 **재작성하지 않는다**
(정책 18 폐기 항목의 "Codex 적발" 주석이 그 예). 현재 사실을 고치려면 활성 문서를 고친다.
