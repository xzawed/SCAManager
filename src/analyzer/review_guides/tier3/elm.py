"""Elm review guide — Tier 3."""

FULL = """\
## Elm 검토 기준
- **아키텍처**: Model-Update-View 패턴 명확성, Msg 유니온 타입 완전 처리
- **타입**: 모든 `Maybe`/`Result` 처리 누락 금지(컴파일러 강제), 타입 별칭 명확성
- **부작용**: Cmd/Sub 통해서만 부작용, JS 상호운용은 Port 경유
- **성능**: 불필요한 `Html.Lazy.lazy` 없는 재렌더링 최소화, `Html.Keyed`
- **패키지**: `elm.json` 의존성 버전 제약, `elm-review` 규칙 준수
"""

COMPACT = "## Elm: MVU 패턴, Maybe/Result 완전 처리, Cmd/Sub 부작용, Port JS 상호운용, elm-review"
