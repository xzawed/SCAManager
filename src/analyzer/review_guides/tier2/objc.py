"""Objective-C review guide — Tier 2."""

FULL = """\
## Objective-C 검토 기준
- **메모리**: ARC 환경 확인, `strong`/`weak`/`unsafe_unretained` 선택, retain cycle(`__weak`)
- **nil 처리**: nil 메시지 전송 안전(Obj-C 특성), nil 반환 vs NSError 이중 패턴
- **블록**: 블록 내 `self` 캡처 → `__weak typeof(self) weakSelf`, 블록 복사(`copy` property)
- **스레드**: `@synchronized`/`dispatch_async` 적절성, UI 업데이트 main thread 보장
- **API 혼합**: Swift ↔ Obj-C 브릿징 nullability 어노테이션(`_Nullable`, `_Nonnull`)
- **프로토콜**: `@optional`/`@required` 명시, delegate `weak` property
"""

COMPACT = "## Objective-C: __weak retain cycle, nil 이중 패턴, 블록 weakSelf, main thread UI, nullability"
