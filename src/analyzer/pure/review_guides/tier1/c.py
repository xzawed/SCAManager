"""C review guide — Tier 1 deep checklist.

Phase 4 PR-13 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## C review checklist
- **Memory**: Verify `malloc` / `free` pairing; watch for double-free / use-after-free; check `NULL` returns
- **Buffers**: Avoid `strcpy` / `sprintf` / `gets` → use `strncpy` / `snprintf` / `fgets`; bounds-check arrays
- **Pointers**: Watch uninitialized pointers, out-of-range pointer arithmetic, `void*` cast safety
- **Integers**: Mixed signed/unsigned (unsigned underflow), integer overflow, type promotion gotchas
- **Strings**: Ensure null-terminator; pick appropriate multibyte string functions
- **Error handling**: Check syscall return values (`errno`); avoid file descriptor leaks
- **Compiler**: Aim for zero warnings under `-Wall -Wextra`; leverage `__attribute__((warn_unused_result))`
- **Security**: Format string vulnerabilities (`printf(user_input)`); validate `system()` inputs
"""

COMPACT = "## C: malloc/free pairs, no gets/strcpy, buffer bounds, integer overflow, format-string vulns"

FULL_KO = """\
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

COMPACT_KO = "## C: malloc/free 쌍, gets/strcpy 금지, 버퍼 경계, 정수 오버플로, format string 취약점"

FULL_JA = """\
## C レビュー基準
- **メモリ**: `malloc` / `free` のペア確認、double-free · use-after-free、`NULL` 戻り値チェック
- **バッファ**: `strcpy` / `sprintf` / `gets` 禁止 → `strncpy` / `snprintf` / `fgets`、配列境界チェック
- **ポインタ**: 初期化されていないポインタ使用、ポインタ算術の境界超過、void* キャスト安全性
- **整数**: 符号あり/なしの混用 (unsigned underflow)、整数オーバーフロー、型プロモーション注意
- **文字列**: null-terminator 保証、マルチバイト文字列処理関数の適合性
- **エラー処理**: システムコール戻り値 (`errno`) チェック漏れ、ファイルディスクリプタ漏れ
- **コンパイラ**: `-Wall -Wextra` 警告ゼロを目標、`__attribute__((warn_unused_result))` 活用
- **セキュリティ**: format string 脆弱性 (`printf(user_input)`)、`system()` 呼び出し入力検証
"""

COMPACT_JA = "## C: malloc/free ペア、gets/strcpy 禁止、バッファ境界、整数オーバーフロー、format string 脆弱性"
