# src/scripts — 로컬 1회 실행 도구

production 의존성 X. Production code MUST NOT import from `src/scripts/`.

## 일러스트 생성 — `py -3 -m src.scripts.generate_illustrations`

1) `OPENAI_API_KEY` 설정 · `pip install -r requirements-dev.txt`
2) `--all --dry-run` 으로 prompt 검토 — 빼면 즉시 과금된다.
3) `--name <PROMPTS 이름>` 또는 `--all` → PNG 는 `src/static/illustrations/`.
4) PNG 를 commit. 재실행 X (결과가 매번 다르다).

정본: prompt 정의 = `illustration_prompts.py`, 단가 = 스크립트 docstring.
참조: `grep -rn static/illustrations/ src/templates/ src/static/css/`
가드: `tests/unit/scripts/test_{illustration_prompts,generate_illustrations}.py`
