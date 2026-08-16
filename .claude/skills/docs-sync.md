---
name: docs-sync
description: PR 작업 후 docs 수치·서사 동기화 — STATE.md 최신/종합/추적셀 + README 배지 쌍 갱신 가이드 (check_docs_sync 페어). TOC 앵커는 check_toc_anchors 가 활성 `## 목차` 문서를 본다.
---

PR 작업 완료/머지 시 테스트 수치·작업 서사를 STATE.md·README 배지에 일관 반영하는 절차.
`scripts/check_docs_sync.py`(commit-time 검증)·`scripts/check_toc_anchors.py`(TOC 앵커 검증)와 **페어** —
스킬이 생성하고 훅이 차단한다 (turn-0 drift 방지).

## 입력
- PR 번호(들) + 작업 1줄 요약 + 상세 서사
- 단위/통합 카운트 — **실측 의무** (정책 8 진화: 추정 카운트 금지). 두 값 모두 아래 명령으로 얻는다:

  ```bash
  py -3 -m pytest tests/unit --collect-only -q | tail -1         # 단위
  py -3 -m pytest tests/integration --collect-only -q | tail -1  # 통합
  ```

  🔴 이 스킬 본문에 통합 수를 **숫자로 고정해 두지 않는다** — 이전 판이 `154` 를 5곳에
  박아 두었다가 실제 값이 늘어난 뒤 5주간 stale 이었다(문서 감사 적발). 현재 값은
  `docs/STATE.md` 종합 수치가 정본이고, 매번 위 명령으로 재확인한다.

## 갱신 지점

🔴 **손으로 고치는 곳은 한 곳뿐이다.**
같은 정수가 5지점에 손으로 복제돼 있었고(**N지점 동기화는 N-1번의 실패 기회**), 실제로
그중 하나를 빠뜨려 가드가 red 를 냈다. 지금은 **§테스트 수 추적 이력의 현재 불릿 한 줄이 SSOT** 이고 나머지는 파생이다.
(절은 이력이 아니다. 과거 항목은 git 에 있다. 새 줄을 덧붙이지 말고 그 한 줄을 고친다.)

```bash
# ① docs/STATE.md §테스트 수 추적 이력의 **현재 불릿** 을 실측값으로 고친다.
#    형식이 곧 계약 — 단위와 누계를 **모두** 담아야 한다:
#      - **현재** (A→**B** 단위; 통합 K = **C** 수집)
#
# ② 파생 3지점(STATE 종합·추적셀 머리·README 2배지)을 자동 갱신
py -3 scripts/check_docs_sync.py --fix
```

**실측 의무** (정책 8 진화 — 추정 카운트 금지):

```bash
py -3 -m pytest tests/unit --collect-only -q | tail -1      # 단위
py -3 -m pytest tests/integration --collect-only -q | tail -1  # 통합 (리터럴로 적지 말 것)
```

🔴 **통합 수를 문서에 리터럴로 적지 않는다** — 이 스킬 자신이 `154` 를 5곳에 박아 두었다가
실제 값이 **171** 이 되도록 5주간 방치했다(문서 감사 적발). 항상 위 명령으로 실측한다.

### 손으로 갱신하는 나머지 (수치 아님 — 서사)

- **STATE.md 최신 블록**: 새 작업으로 **교체** (직전 서사는 세션 기록으로 이관)
- TOC 앵커(`check_toc_anchors.TARGETS`): 활성 `## 목차` 문서를 고치면 slug 을 함수로 실측

## slug 계산 (TOC 앵커 — 추정 금지·함수 실측)
```bash
python -c "import sys; sys.path.insert(0,'scripts'); import check_toc_anchors as t; print(t.github_slug('<헤더 텍스트>', {}))"
```
em-dash(`—`)/`+`/`()`/`.` 가 더블하이픈·제거를 유발하므로 반드시 실측.

## 검증 (커밋 전 의무)
- `python scripts/check_docs_sync.py` → ✅ (4 지점 카운트 일치)
- `python scripts/check_toc_anchors.py` → ✅ (TARGETS 의 `## 목차` 앵커 정합)
- 카운트 실측 대조: `pytest tests/unit --collect-only -q | tail -1` 이 M 인지

## 주의
- README.md ↔ README.ko.md 배지 쌍 **동시 갱신 의무** (과거 Codex 적발 drift — `feedback-docs-sync-codeql-gotchas`).
- **카운트 무변경 PR**(docs-only·`.mjs`·스킬)은 수치 불릿·배지 갱신 불필요, STATE.md 최신 블록만 교체.
- 신규 `src/` 파일 추가 시 `docs/architecture.md` 동기화(6-step ⑥)는 본 스킬 범위 밖 — 별도 수행.
