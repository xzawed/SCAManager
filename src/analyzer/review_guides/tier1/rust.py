"""Rust review guide — Tier 1 deep checklist."""

FULL = """\
## Rust 검토 기준
- **소유권**: 불필요한 `clone()` 남용 확인, 참조 수명(`'a`) 명시 필요 여부
- **에러 처리**: `unwrap()`/`expect()` — panic 가능 지점 리뷰 필수, `?` 연산자 전파 패턴
- **타입**: `Result<T, E>` / `Option<T>` 일관 사용, `Box<dyn Error>` vs 구체 타입
- **unsafe**: `unsafe` 블록 최소화·문서화, raw pointer 사용 근거 주석
- **동시성**: `Mutex`/`RwLock` 데드락 위험, `Arc` 남용 vs `Rc` 단일 스레드
- **성능**: 불필요한 힙 할당(`Box`, `Vec` 과다), `&str` vs `String` 선택
- **패턴 매칭**: `match` 완전성, if let vs match 적절성, 중첩 `Option` 처리
- **의존성**: `Cargo.lock` 커밋(바이너리), `cargo audit` 취약점 여부
"""

COMPACT = "## Rust: unwrap 금지→?, clone 남용, unsafe 최소화·문서화, Arc/Mutex 데드락, cargo audit"
