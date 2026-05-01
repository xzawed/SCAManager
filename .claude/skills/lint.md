---
description: SCAManager 코드 품질 검사 — pylint, flake8, bandit 실행
---

`src/` 디렉토리에 대해 정적 분석 도구 3종을 실행하고 결과를 요약한다.

## 실행 순서

```bash
# 1. pylint (코드 품질, 오류)
pylint src/ --output-format=text

# 2. flake8 (스타일, PEP8)
flake8 src/

# 3. bandit (보안 취약점)
bandit -r src/ -ll
```

## 결과 해석

각 도구 결과를 다음 형식으로 요약:

| 도구 | 점수/이슈 수 | 주요 문제 |
|------|------------|----------|
| pylint | X.XX/10 | ... |
| flake8 | X개 경고 | ... |
| bandit | HIGH:X, MED:X | ... |

SCAManager 자체 점수 체계 기준으로 환산 (Phase E 이후 — `src/constants.py` 단일 출처):
- pylint + flake8 (code_quality) → 25점 만점 (`CODE_QUALITY_MAX`). error -3, warning -1 (cap `CQ_WARNING_CAP=25`)
- bandit + semgrep(security) → 20점 만점 (`SECURITY_MAX`). HIGH -7, LOW/MED -2
- 합산 정적분석 만점: 45점 (총점 100 중)
- AI 항목: 커밋 15 + 방향 25 + 테스트 15 = 55점 (Claude API)
- 등급: A (≥90) / B (≥75) / C (≥60) / D (≥45) / F (<45) — `GRADE_THRESHOLDS`

## 인자

- `/lint` — 전체 src/ 검사
- `/lint src/analyzer` — 특정 서브모듈만 검사
