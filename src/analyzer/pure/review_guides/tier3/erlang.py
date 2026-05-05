"""Erlang review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Erlang review checklist
- **Processes**: "Let it crash" philosophy — design supervisor trees; minimize gen_server state
- **Pattern matching**: Exhaustive function clauses; no variable rebinding (single assignment)
- **Errors**: `{ok, Val}` / `{error, Reason}` tuples; appropriate `catch` / `try`
- **Messages**: Prevent message queue overflow; minimize selective receive patterns
- **OTP**: Complete behaviour callbacks (`gen_server` / `supervisor` / `gen_statem`)
"""

COMPACT = "## Erlang: let it crash + supervisor, single assignment, {ok/error} tuples, OTP behaviour"

FULL_KO = """\
## Erlang 검토 기준
- **프로세스**: "let it crash" 철학 — supervisor 트리 설계, gen_server 상태 최소화
- **패턴 매칭**: 함수 절 완전성, 변수 재바인딩 금지(단일 할당)
- **에러**: `{ok, Val}`/`{error, Reason}` 튜플, `catch`/`try` 적절성
- **메시지**: 메시지 큐 오버플로 방지, 선택적 receive 패턴 최소화
- **OTP**: behaviour(`gen_server`/`supervisor`/`gen_statem`) 콜백 완성도
"""

COMPACT_KO = "## Erlang: let it crash + supervisor, 단일 할당, {ok/error} 튜플, 메시지 큐 관리, OTP behaviour"

FULL_JA = """\
## Erlang レビュー基準
- **プロセス**: "let it crash" 哲学 — supervisor ツリー設計、gen_server 状態を最小化
- **パターンマッチ**: 関数節の網羅性、変数再バインド禁止 (単一代入)
- **エラー**: `{ok, Val}` / `{error, Reason}` タプル、`catch` / `try` の適切性
- **メッセージ**: メッセージキューオーバーフロー防止、選択的 receive パターンを最小化
- **OTP**: behaviour (`gen_server` / `supervisor` / `gen_statem`) コールバック完成度
"""

COMPACT_JA = "## Erlang: let it crash + supervisor、単一代入、{ok/error} タプル、メッセージキュー管理、OTP"
