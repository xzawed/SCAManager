# SCAManager 프로젝트 상태

현재 수치와 재측정 명령만 둔다. 서사는 git, 열린 일감은 GitHub Issues 가 갖는다.
테스트 수는 적지 않는다 — 원천은 실행 결과다(PR 본문 첫 줄 ↔ CI junit · E2E 기준 `e2e/EXPECTED_COUNT`).

## 현재 수치

| 지표 | 값 | 재측정 |
|---|---|---|
| 단위 · 통합 테스트 | 실행 결과 | `py -3 -m pytest --collect-only -q tests/unit` · `tests/integration` |
| E2E 테스트 | `e2e/EXPECTED_COUNT`(바닥) | `py -3 -m pytest e2e/ -p no:asyncio --collect-only -q`. 대조 `scripts/check_e2e_scope.py` |
| pylint | **9.99/10** | `py -3 -m pylint src/`. CI `--fail-under` 는 README 배지에서 파생 |
| 커버리지 | Python 97% | `py -3 -m pytest tests/unit --cov=src` |
| bandit HIGH | 0 | `py -3 -m bandit -r src/` |
| 지원 언어 | AI 49 / 정적 25 | `src/analyzer/pure/language.py` · 등록 분석기 24종 |
