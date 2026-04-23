/* P4-Gate cppcheck 실증 샘플 — 외부 테스트 리포 PR 에 포함해 분석 결과 검증.
 * 의도적 결함 3건:
 *   1) strcpy 버퍼 오버플로우 — cppcheck error "bufferAccessOutOfBounds"
 *   2) scanf %s 포맷 — cppcheck warning "invalidscanf"
 *   3) 초기화 안 된 지역 변수 — cppcheck warning "uninitvar"
 */
#include <string.h>
#include <stdio.h>

int vulnerable_copy(const char *long_str) {
    char buf[10];
    strcpy(buf, long_str);
    return 0;
}

int unsafe_input(void) {
    char name[32];
    scanf("%s", name);
    return 0;
}

int uninitialized(void) {
    int x;
    return x + 1;
}

int main(void) {
    vulnerable_copy("AAAAAAAAAAAAAAAAAAAAA");
    unsafe_input();
    return uninitialized();
}
