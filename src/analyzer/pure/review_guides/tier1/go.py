"""Go review guide — Tier 1 deep checklist."""

FULL = """\
## Go 검토 기준
- **에러 처리**: `err != nil` 체크 누락 금지, `_` 무시 금지, `fmt.Errorf("...: %w", err)` 감싸기
- **인터페이스**: 작은 인터페이스 선호(1~2 메서드), 구현 side에서 정의 — 소비 side에서 선언
- **고루틴**: 고루틴 leak 방지(context.Context 전파, done channel, WaitGroup), goroutine 내 패닉 recover
- **채널**: 채널 방향 타입 명시(`chan<-`, `<-chan`), 버퍼 크기 근거 명시
- **포인터**: 값 vs 포인터 리시버 일관성, 불필요한 포인터화 지양
- **패키지**: 패키지명 소문자 단수, import cycle 금지, internal 패키지 활용
- **테스트**: `_test.go` 파일, `t.Helper()`, 테이블 드리븐 테스트 패턴
- **보안**: `os/exec` 입력 검증, `crypto/rand` vs `math/rand` 구분, SQL injection
"""

COMPACT = "## Go: err 체크 누락 금지, 고루틴 leak, context 전파, 포인터 리시버 일관성, crypto/rand"
