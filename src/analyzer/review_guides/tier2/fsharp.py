"""F# review guide — Tier 2."""

FULL = """\
## F# 검토 기준
- **불변성**: `let` 불변 바인딩 선호, `mutable` 최소화, 레코드 `with` 업데이트
- **타입**: 판별 유니온(DU) 도메인 모델링, `Option<T>`/`Result<T,E>` 에러 처리, `unit` 반환 주의
- **파이프라인**: `|>` 체인 가독성, 함수 합성(`>>`) 적절성
- **비동기**: `async { }` 컴퓨테이션 표현식, `Async.RunSynchronously` 남용 금지
- **패턴 매칭**: `match` 완전성(컴파일러 경고), 액티브 패턴 복잡도 경계
- **.NET 상호운용**: `null` 방어적 처리, `Option.ofObj`, `try/with` 예외 캐치
"""

COMPACT = "## F#: 불변 let, DU 도메인 모델, Option/Result, |> 파이프, async 컴퓨테이션, null 방어"
