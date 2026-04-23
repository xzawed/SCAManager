"""Elixir review guide — Tier 2."""

FULL = """\
## Elixir 검토 기준
- **패턴 매칭**: `case`/`cond`/`with` 완전 매칭, `_` 와일드카드 명시적 의도
- **파이프라인**: `|>` 체인 가독성, 첫 인수 데이터 흐름 패턴 준수
- **프로세스**: GenServer `handle_call`/`handle_cast` 반환 튜플 정확성, 프로세스 누수
- **에러**: `{:ok, result}`/`{:error, reason}` 튜플 패턴, `with` 체인 에러 전파
- **불변성**: 데이터 변환 체인 명확성, ETS 공유 상태 접근 직렬화
- **테스트**: ExUnit `describe`/`test`, `Mox` 목킹, `ExUnit.Case async: true`
- **보안**: 외부 입력 `Ecto.Changeset` 검증, SQL injection Ecto 파라미터화
"""

COMPACT = "## Elixir: {:ok/:error} 튜플, with 에러 전파, GenServer 반환 튜플, Ecto Changeset 검증"
