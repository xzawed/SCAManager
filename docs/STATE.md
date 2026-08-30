# SCAManager 프로젝트 상태

현재 수치와 재측정 명령만 둔다. 서사는 git, 열린 일감은 GitHub Issues 가 갖는다.

## 현재 수치

**최신 (현재 코드 기준)**
- 손으로 고치는 곳은 파일 끝 SSOT 불릿 한 줄뿐. 나머지 4지점은 `--fix` 가 파생한다.

**종합 수치**: 전체 **8038** 수집 (단위 **7843** + 통합 195) / E2E **121** (`#1291` 기준) / pylint **9.99/10** (`src/`).

| 지표 | 값 | 재측정 |
|---|---|---|
| 전체 테스트 | **8038 수집** | `py -3 -m pytest --collect-only -q tests/unit` + `tests/integration` — 단위 7843 + 통합 195 (현재) |
| E2E 테스트 | **121개** | `make test-e2e` — = 121 collected (110 표준 + 11 perf). 대조 `scripts/check_e2e_scope.py` |
| pylint | **9.99/10** | `py -3 -m pylint src/`. CI `--fail-under` 는 README 배지에서 파생 |
| 커버리지 | Python 97% | `py -3 -m pytest tests/unit --cov=src` |
| bandit HIGH | 0 | `py -3 -m bandit -r src/` |
| 지원 언어 | AI 49 / 정적 27 | `src/analyzer/pure/language.py` · 등록 분석기 25종 |

## 수치 갱신 절차

1) `py -3 -m pytest --collect-only -q tests/unit` 과 `tests/integration` 으로 실측한다.
2) 아래 §테스트 수 추적 이력의 **마지막 불릿 한 줄**만 그 값으로 고친다.
3) `py -3 scripts/check_docs_sync.py --fix` — 종합 수치·추적셀·README 2배지가 파생된다.
4) `py -3 scripts/check_test_count_sync.py` 로 실측과 대조한다.
5) 2) 외의 지점은 직접 편집하지 않는다. E2E 가 바뀌면 `e2e/EXPECTED_COUNT` 를 같은 PR 에서 맞춘다.

## 테스트 수 추적 이력

- **현재** (7242→**7843** 단위; 통합 195 = **8038** 수집)
