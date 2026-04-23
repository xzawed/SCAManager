"""C++ review guide — Tier 1 deep checklist."""

FULL = """\
## C++ 검토 기준
- **스마트 포인터**: raw pointer 대신 `unique_ptr`/`shared_ptr`, `new`/`delete` 직접 사용 최소화
- **RAII**: 리소스 획득=초기화, 소멸자에서 예외 throw 금지, 복사/이동 생성자 `= default`/`= delete`
- **모던 C++**: range-for, `auto`, structured binding, `std::optional`, `std::variant` 활용(C++17+)
- **캐스팅**: C-style cast 금지 → `static_cast`/`dynamic_cast`/`reinterpret_cast` 명시
- **STL**: `std::vector` 선호, 컨테이너 반복 중 수정 금지, `reserve()` 사전 크기 지정
- **const 정확성**: `const` 참조 매개변수, `const` 멤버 함수, `constexpr` 컴파일타임 상수
- **예외**: 예외 명세 제거(C++11+), noexcept 명시, exception-safe 복사 보장
- **보안**: `memcpy`/`memset` 크기 계산 오류, 포맷 문자열 취약점, 버퍼 오버런
"""

COMPACT = "## C++: unique_ptr, RAII, C-style cast 금지, const 정확성, noexcept, 스마트 포인터 선호"
