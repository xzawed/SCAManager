"""Perl review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Perl review checklist
- **Strict mode**: `use strict; use warnings;` required; `use utf8;` for encoding
- **Error handling**: `die` / `eval` / `$@` pattern; use `Carp` module (`croak` / `confess`); `or die` chains
- **Regex**: Use `/x` flag for comments; capture `$1` immediately; watch `/g` infinite loops
- **File handling**: `open(my $fh, '<', $file) or die`; 3-argument `open` required
- **Security**: Use list form for `system()` / `exec()` (prevents shell injection); `taint mode` (`-T`)
- **Modules**: `use Moo` / `Moose` for OOP; use `local $_` to prevent scope pollution
"""

COMPACT = "## Perl: use strict/warnings, 3-arg open, system() list form, taint mode, Carp"

FULL_KO = """\
## Perl 검토 기준
- **엄격 모드**: `use strict; use warnings;` 필수, `use utf8;` 인코딩
- **에러 처리**: `die`/`eval`/`$@` 패턴, `Carp` 모듈 사용(croak/confess), `or die` 체인
- **정규식**: `/x` 플래그로 주석 추가, `$1` 캡처 변수 즉시 저장, `/g` 무한 루프 주의
- **파일 처리**: `open(my $fh, '<', $file) or die`, 3인수 open 필수
- **보안**: `system()`/`exec()` 리스트 형식 사용(셸 주입 방지), `taint mode`(`-T`)
- **모듈**: `use Moo`/`Moose` OOP, `local $_` 스코프 오염 방지
"""

COMPACT_KO = "## Perl: use strict/warnings, 3인수 open, system() 리스트 형식, taint mode, Carp 사용"

FULL_JA = """\
## Perl レビュー基準
- **strict モード**: `use strict; use warnings;` 必須、エンコーディングに `use utf8;`
- **エラー処理**: `die` / `eval` / `$@` パターン、`Carp` モジュール (`croak` / `confess`)、`or die` チェーン
- **正規表現**: `/x` フラグでコメント追加、`$1` キャプチャ変数を即時保存、`/g` 無限ループ注意
- **ファイル処理**: `open(my $fh, '<', $file) or die`、3 引数 `open` 必須
- **セキュリティ**: `system()` / `exec()` はリスト形式 (シェル注入防止)、`taint mode` (`-T`)
- **モジュール**: `use Moo` / `Moose` OOP、`local $_` でスコープ汚染防止
"""

COMPACT_JA = "## Perl: use strict/warnings、3 引数 open、system() リスト形式、taint mode、Carp"
