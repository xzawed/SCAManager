"""Perl review guide — Tier 2."""

FULL = """\
## Perl 검토 기준
- **엄격 모드**: `use strict; use warnings;` 필수, `use utf8;` 인코딩
- **에러 처리**: `die`/`eval`/`$@` 패턴, `Carp` 모듈 사용(croak/confess), `or die` 체인
- **정규식**: `/x` 플래그로 주석 추가, `$1` 캡처 변수 즉시 저장, `/g` 무한 루프 주의
- **파일 처리**: `open(my $fh, '<', $file) or die`, 3인수 open 필수
- **보안**: `system()`/`exec()` 리스트 형식 사용(셸 주입 방지), `taint mode`(`-T`)
- **모듈**: `use Moo`/`Moose` OOP, `local $_` 스코프 오염 방지
"""

COMPACT = "## Perl: use strict/warnings, 3인수 open, system() 리스트 형식, taint mode, Carp 사용"
