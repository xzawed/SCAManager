"""Go review guide — Tier 1 deep checklist.

Phase 4 PR-13 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Go review checklist
- **Error handling**: Don't skip `err != nil` checks, don't discard with `_`; wrap via `fmt.Errorf("...: %w", err)`
- **Interfaces**: Prefer small interfaces (1-2 methods); define on the consumer side, not the implementation side
- **Goroutines**: Prevent leaks (propagate `context.Context`, use done channels, WaitGroup);
  recover from panics inside goroutines
- **Channels**: Explicit channel direction types (`chan<-`, `<-chan`); justify buffer size
- **Pointers**: Consistent value vs pointer receivers; avoid unnecessary pointer conversion
- **Packages**: Lowercase singular package names; no import cycles; leverage `internal` packages
- **Tests**: `_test.go` files, `t.Helper()`, table-driven test pattern
- **Security**: Validate `os/exec` input; distinguish `crypto/rand` vs `math/rand`; SQL injection
"""

COMPACT = "## Go: err checks required, goroutine leaks, context propagation, receiver consistency, crypto/rand"

FULL_KO = """\
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

COMPACT_KO = "## Go: err 체크 누락 금지, 고루틴 leak, context 전파, 포인터 리시버 일관성, crypto/rand"

FULL_JA = """\
## Go レビュー基準
- **エラー処理**: `err != nil` チェック漏れ禁止、`_` 無視禁止、`fmt.Errorf("...: %w", err)` でラップ
- **インターフェース**: 小さなインターフェース推奨 (1〜2 メソッド)、消費側で定義 — 実装側ではない
- **ゴルーチン**: ゴルーチンリーク防止 (context.Context 伝播、done channel、WaitGroup)、ゴルーチン内 panic recover
- **チャネル**: チャネル方向型を明示 (`chan<-`, `<-chan`)、バッファサイズの根拠を明示
- **ポインタ**: 値 vs ポインタレシーバの一貫性、不要なポインタ化回避
- **パッケージ**: パッケージ名は小文字単数、import cycle 禁止、internal パッケージ活用
- **テスト**: `_test.go` ファイル、`t.Helper()`、テーブルドリブンテストパターン
- **セキュリティ**: `os/exec` 入力検証、`crypto/rand` vs `math/rand` 区別、SQL injection
"""

COMPACT_JA = "## Go: err チェック必須、ゴルーチンリーク、context 伝播、レシーバ一貫性、crypto/rand"
