"""C review guide — Tier 1 deep checklist."""

FULL = """\
## C 검토 기준
- **메모리**: `malloc`/`free` 쌍 확인, double-free·use-after-free, `NULL` 반환 체크
- **버퍼**: `strcpy`/`sprintf`/`gets` 금지 → `strncpy`/`snprintf`/`fgets`, 배열 경계 검사
- **포인터**: 초기화되지 않은 포인터 사용, 포인터 산술 경계 초과, void* 캐스팅 안전성
- **정수**: 부호 있는/없는 정수 혼용(unsigned underflow), 정수 오버플로우, 타입 프로모션 주의
- **문자열**: null-terminator 보장, 멀티바이트 문자열 처리 함수 적합성
- **에러 처리**: 시스템 콜 반환값(`errno`) 체크 누락, 파일 디스크립터 누수
- **컴파일러**: `-Wall -Wextra` 경고 0건 목표, `__attribute__((warn_unused_result))` 활용
- **보안**: format string 취약점(`printf(user_input)`), `system()` 호출 입력 검증
"""

COMPACT = "## C: malloc/free 쌍, gets/strcpy 금지, 버퍼 경계, 정수 오버플로, format string 취약점"
