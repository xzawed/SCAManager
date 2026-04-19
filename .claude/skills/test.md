---
description: SCAManager 테스트 실행 — 전체 또는 특정 모듈
---

프로젝트 루트에서 pytest를 실행한다.

## 인자 없이 호출 (`/test`)

전체 테스트 스위트 실행:

```bash
cd D:/Source/SCAManager && pytest -v
```

결과 요약을 출력하고, 실패한 테스트가 있으면 오류 내용과 수정 방향을 제시한다.

## 인자와 함께 호출 (`/test pipeline`, `/test webhook` 등)

인자를 모듈명으로 해석하여 해당 테스트 파일만 실행:

```bash
cd D:/Source/SCAManager && pytest tests/test_<인자>.py -v
```

예: `/test pipeline` → `pytest tests/test_pipeline.py -v`

## 커버리지 포함 (`/test coverage`)

```bash
cd D:/Source/SCAManager && pytest --cov=src --cov-report=term-missing
```

## 테스트 실행 후

- 통과: "✅ X/X 테스트 통과" 요약
- 실패: 실패한 테스트명, 오류 메시지, 원인 분석, 수정 제안 제공
