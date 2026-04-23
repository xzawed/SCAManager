"""Julia review guide — Tier 3."""

FULL = """\
## Julia 검토 기준
- **타입 안정성**: 타입 불안정 함수 회피(`@code_warntype`), 추상 타입 컨테이너 지양
- **성능**: 전역 변수 `const` 선언, 루프 내 메모리 할당 최소화, `@view` 슬라이스
- **멀티플 디스패치**: 메서드 명확한 시그니처, 충돌 방지(ambiguity), `!` 변경 함수 컨벤션
- **브로드캐스팅**: `.` 도트 브로드캐스팅 활용, 불필요한 벡터화 회피
- **패키지**: `using` vs `import` 구분, 의존성 `Project.toml` 명시
"""

COMPACT = "## Julia: 타입 안정성, const 전역, @view 슬라이스, 멀티플 디스패치 명확성, Project.toml"
