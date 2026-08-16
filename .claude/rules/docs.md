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

> 이 파일이 자동 로드된다 = **처방 문서 표면**을 만지고 있다. `.claude/rules` path 패턴이 이 파일을 매칭한다.
>
> 문서를 **압축·삭제·이동**한다면 [`docs/process/doc-compression.md`](../../docs/process/doc-compression.md) 가 순서 정본이고, 실패 클래스는 [`.claude/traps.md`](../traps.md) §C 다.
>
> 새 항목은 실제 사고 뒤에만 추가한다. 추측성 지침을 넣지 않는다.

## 수치는 손으로 여러 곳에 적지 않는다 — SSOT 는 현재 불릿 한 줄

테스트 수를 STATE 종합 · 추적셀 머리 · SSOT 불릿 · README 배지 · README.ko 배지에 복제하지 않는다. N지점 손동기화는 N-1번의 실패 기회다.

- **손으로 고치는 곳**: `docs/STATE.md` §테스트 수 추적 이력 **현재 불릿 한 줄**뿐.
  (절 제목은 가드가 키로 쓰므로 유지한다.)
- **나머지 4지점**: `py -3 scripts/check_docs_sync.py --fix` 가 그 한 줄에서 파생한다.
- 형식이 계약: `… (A→**B** 단위 … = **C** 수집)` 처럼 **단위와 누계를 모두** 담는다.
  수치 없는 항목이 꼬리에 오면 가드가 red (`scripts/check_docs_sync.py` · `scripts/check_test_count_sync.py`).
- **표 셀에 다시 적지 말 것** — 머리와 꼬리가 한 줄에서 수만 자 떨어진다.

## 원장에 "해당 없음" 을 적으면 기계가 "해당 있음" 으로 센다

원장은 행의 **존재**로 판정한다. 부정·유보·주석은 **행을 만들지 말고** 산문 단락에 적는다. 산문이 부정해도 기계는 행만 본다.

적용 대상 파일 원장은 현재 없다. 열린 일감·미결 운영 검증은 GitHub Issues.

## 파생 집계는 손으로 유지하지 않는다

열린 일감은 GitHub Issues. 파생 숫자는 `docs/STATE.md` 현재 불릿 한 줄 + `check_docs_sync.py --fix` 만.

## 문서를 **옮기면** 관측자가 조용히 죽는다

경로를 하드코딩한 소비자가 있다 — 이름 변경·이동 전에 grep 한다:

| 문서 | 소비자 |
|---|---|
| `docs/STATE.md` | `check_docs_sync.py` · `check_test_count_sync.py` · `doc_review_gate.py` |
| `docs/architecture.md` | 아키텍처 트리 sync 가드 |
| `docs/reference/env-vars.md` | env 인용 sync 가드 |
| `CLAUDE.md` · `AGENTS.md` | `doc_review_gate` 컨텍스트 · `check_memory_refs` |

내용 재구조화는 해도 **경로는 두는 것**이 기본값이다.

## 인용한 `file:line` 은 `grep -n` 실측값이어야 한다

정책 6. 추정 라인은 drift 로 거짓이 된다. 가능하면 커밋 해시를 병기한다 (`ai_review.py:89` 형태). PR 번호는 근거가 아니다.
