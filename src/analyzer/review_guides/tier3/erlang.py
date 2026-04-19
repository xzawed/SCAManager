"""Erlang review guide — Tier 3."""

FULL = """\
## Erlang 검토 기준
- **프로세스**: "let it crash" 철학 — supervisor 트리 설계, gen_server 상태 최소화
- **패턴 매칭**: 함수 절 완전성, 변수 재바인딩 금지(단일 할당)
- **에러**: `{ok, Val}`/`{error, Reason}` 튜플, `catch`/`try` 적절성
- **메시지**: 메시지 큐 오버플로 방지, 선택적 receive 패턴 최소화
- **OTP**: behaviour(`gen_server`/`supervisor`/`gen_statem`) 콜백 완성도
"""

COMPACT = "## Erlang: let it crash + supervisor, 단일 할당, {ok/error} 튜플, 메시지 큐 관리, OTP behaviour"
