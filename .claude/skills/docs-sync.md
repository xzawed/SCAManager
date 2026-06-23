---
name: docs-sync
description: PR 작업 후 docs 수치·서사 동기화 — STATE.md 최신/종합/추적셀 + cycle-history TOC·섹션 + README 배지 쌍 갱신 가이드 (check_docs_sync·check_toc_anchors 페어)
---

PR 작업 완료/머지 시 테스트 수치·작업 서사를 STATE.md·cycle-history.md·README 배지에 일관 반영하는 절차.
`scripts/check_docs_sync.py`(commit-time 검증)·`scripts/check_toc_anchors.py`(TOC 앵커 검증)와 **페어** —
스킬이 생성하고 훅이 차단한다 (turn-0 drift 방지).

## 입력
- PR 번호(들) + 작업 1줄 요약 + 상세 서사
- 단위/전체 카운트 — **실측 의무**: `pytest tests/unit --collect-only -q | tail -1` + 통합(154) 합산.
  (정책 8 진화: 추정 카운트 금지)

## 갱신 지점

🔴 **`check_docs_sync.py` 가 카운트 정합을 강제하는 4 검사 지점** = ① STATE 종합 수치(전체+단위) · ② STATE 추적셀 시작 헤더(전체+단위) · ⑤ README.md 배지 · ⑤ README.ko.md 배지. 이 4 곳 카운트가 어긋나면 commit 차단. **③ 추적셀 trail · ④ 최신 블록 = 절차적 수동 갱신(훅 미검증)**, ⑥ cycle-history 는 `check_toc_anchors` 가 **앵커만** 검증(카운트 X).

1. **STATE.md 종합 수치** (header) 🔒훅: `전체 **N** 수집 (단위 **M** + 통합 154)`
2. **STATE.md 추적셀 시작 헤더** 🔒훅: `**N 수집**` + `단위 M + 통합 154 (현재)`
3. **STATE.md 추적셀 trail** (절차·훅 미검증): 말미에 `+ **<날짜> <작업> +Δ** (...상세...). (\`pytest --co\` 단위 M + 통합 154 = N 수집).` 추가
4. **STATE.md 최신 블록** (절차·훅 미검증): 새 작업으로 **교체** (직전 서사는 cycle-history 최신순 맨 앞으로 이관 — 헤더 "직전" 체인 누적 금지)
5. **README.md + README.ko.md 배지** 🔒훅: `Tests-N%2B_total_(M_unit_%2B_154_integration)` (**양쪽 동일**·`%2B` 인코딩 유지)
6. **cycle-history.md** (앵커만 🔒`check_toc_anchors`): TOC 엔트리(앵커 = 헤더 slug) + body 섹션(최신순 맨 앞)

## slug 계산 (cycle-history TOC 앵커 — 추정 금지·함수 실측)
```bash
python -c "import sys; sys.path.insert(0,'scripts'); import check_toc_anchors as t; print(t.github_slug('<헤더 텍스트>', {}))"
```
em-dash(`—`)/`+`/`()`/`.` 가 더블하이픈·제거를 유발하므로 반드시 실측 (#958 사고 패턴).

## 검증 (커밋 전 의무)
- `python scripts/check_docs_sync.py` → ✅ (4 지점 카운트 일치)
- `python scripts/check_toc_anchors.py docs/cycle-history.md` → ✅ (앵커 정합)
- 카운트 실측 대조: `pytest tests/unit --collect-only -q | tail -1` 이 M 인지

## 주의
- README.md ↔ README.ko.md 배지 쌍 **동시 갱신 의무** (과거 Codex 적발 drift — `feedback-docs-sync-codeql-gotchas`).
- **카운트 무변경 PR**(docs-only·`.mjs`·스킬)은 1~3·5 갱신 불필요, 4(최신)·6(cycle-history)만 갱신.
- 신규 `src/` 파일 추가 시 `docs/architecture.md` 동기화(6-step ⑥)는 본 스킬 범위 밖 — 별도 수행.
