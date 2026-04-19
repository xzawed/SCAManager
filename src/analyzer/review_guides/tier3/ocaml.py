"""OCaml review guide — Tier 3."""

FULL = """\
## OCaml 검토 기준
- **타입**: 타입 추론 신뢰하되 공개 함수 시그니처 명시, `option`/`result` 에러 처리
- **패턴 매칭**: 완전한 match(컴파일러 경고), `_` 와일드카드 최소화
- **불변성**: 기본 불변 — `ref`/`mutable` 필드 사용 시 근거 주석
- **모듈**: functor 복잡도 관리, `include` 남용 주의, `mli` 인터페이스 파일 유지
- **예외**: `exception`보다 `result` 타입 선호(함수형 에러 처리), `try/with` 범위 최소화
"""

COMPACT = "## OCaml: option/result, 완전 match, ref 최소화, mli 인터페이스 유지, result > exception"
