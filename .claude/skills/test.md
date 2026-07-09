---
name: test
description: SCAManager 테스트 실행 — 전체 또는 특정 모듈
---

프로젝트 루트(`pwd`) 에서 pytest 를 실행한다. **Linux/devcontainer/Windows 환경 모두 호환** — `cd` 절대경로 하드코딩 금지.

## 인자 없이 호출 (`/test`)

환경변수 격리 + 전체 테스트 스위트 실행 (권장):

```bash
make test-isolated
```

`.env` 파일이 stash 되어 단위 테스트가 깨끗한 환경변수로 실행. 🔴 **신규 실패 판정 = 하드코딩 수치 아닌 baseline 실측 대비** — 로컬 환경/경로 차이로 false failure 가능하나, 판정 기준은 `pytest tests/unit` **baseline 출력의 실패집합**(현 main CI green = 0; 수치 출처 `docs/STATE.md` SSOT). 고정 카운트 인용 금지 — 자연 drift(정책 6).

빠른 단위 테스트만 (통합 제외):

```bash
make test-fast
```

또는 직접 pytest 호출:

```bash
python -m pytest tests/ -q
```

결과 요약을 출력하고, 실패한 테스트가 있으면 오류 내용과 수정 방향을 제시한다.

## 인자와 함께 호출 (`/test pipeline`, `/test webhook` 등)

Phase 4 이후 테스트 파일은 `tests/unit/<영역>/test_<모듈>.py` 계층 구조. 인자 해석:

```bash
# 영역 단위 — 모든 단위 테스트 실행
python -m pytest tests/unit/<영역>/ -q

# 특정 모듈 — 단일 파일 실행
python -m pytest tests/unit/<영역>/test_<모듈>.py -q
```

예:
- `/test pipeline` → `pytest tests/unit/worker/ -q`
- `/test webhook` → `pytest tests/unit/webhook/ -q`
- `/test gate` → `pytest tests/unit/gate/ -q`
- `/test integration` → `pytest tests/integration/ -q` (slow tests, `make test-slow` 와 동일)

## 커버리지 포함 (`/test coverage`)

```bash
make test-cov
```

## 테스트 실행 후

- 통과: "✅ X/X 테스트 통과" 요약 + 사전 실패 (baseline 실측 집합 — 현 main CI green = 0) 와 신규 실패 명확히 분리 (하드코딩 카운트 금지)
- 실패: 실패한 테스트명, 오류 메시지, 원인 분석, 수정 제안 제공
