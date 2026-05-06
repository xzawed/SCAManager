# SCAManager 점수 체계

> CLAUDE.md 분리본 (사이클 85 정리, 2026-05-06). 점수 영역 작업 시 reference.

## 점수 배점 + 도구

| 항목 | 배점 | 도구 | 감점 규칙 |
|------|------|------|----------|
| 코드 품질 | 25점 | pylint + flake8 + semgrep(code_quality) | error -3, warning -1 (CQ_WARNING_CAP=25 통합 cap) |
| 보안 | 20점 | bandit + semgrep(security) | HIGH -7, LOW/MED -2 |
| 커밋 메시지 품질 | 15점 | Claude AI (0-20 → 0-15 스케일링) | — |
| 구현 방향성 | 25점 | Claude AI (0-20 → 0-25 스케일링) | — |
| 테스트 | 15점 | Claude AI (0-10 → 0-15 스케일링, 비-코드 파일 면제) | — |

## 등급

A(90+), B(75+), C(60+), D(45+), F(44-)

> `ANTHROPIC_API_KEY` 미설정 시 AI 항목은 중립적 기본값(커밋13 + 방향21 + 테스트10 = 44/55)으로 fallback, AI 없이도 최대 89점(B등급) 가능.

## 관련 모듈

- 단일 출처: [`src/constants.py`](../../src/constants.py) (배점 / 감점 / 등급 임계)
- 점수 계산: [`src/scorer/calculator.py`](../../src/scorer/calculator.py)
- 등급 판정: `calculate_grade(avg_score)` (`src/scorer/calculator.py`)

## AI 점수 스케일링

- Claude 는 commit 0-20, direction 0-20, test 0-10으로 반환
- calculator 가 commit 0-15, direction 0-25, test 0-15로 스케일링
- `round()` 사용으로 banker's rounding 적용
- 비-코드 파일만 변경 시 테스트 점수 면제 (test_score=10 → 15/15)
