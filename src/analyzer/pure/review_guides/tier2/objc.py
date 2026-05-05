"""Objective-C review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Objective-C review checklist
- **Memory**: Confirm ARC; pick `strong` / `weak` / `unsafe_unretained`; retain cycles (`__weak`)
- **nil handling**: Sending messages to nil is safe (Obj-C feature); nil-return vs NSError dual pattern
- **Blocks**: Capture `self` → `__weak typeof(self) weakSelf`; copy block properties
- **Threading**: Correct `@synchronized` / `dispatch_async`; UI updates on the main thread
- **API mixing**: Swift ↔ Obj-C bridging nullability annotations (`_Nullable`, `_Nonnull`)
- **Protocols**: Mark `@optional` / `@required`; delegate properties as `weak`
"""

COMPACT = "## Objective-C: __weak retain cycle, nil dual pattern, block weakSelf, main thread UI, nullability"

FULL_KO = """\
## Objective-C 검토 기준
- **메모리**: ARC 환경 확인, `strong`/`weak`/`unsafe_unretained` 선택, retain cycle(`__weak`)
- **nil 처리**: nil 메시지 전송 안전(Obj-C 특성), nil 반환 vs NSError 이중 패턴
- **블록**: 블록 내 `self` 캡처 → `__weak typeof(self) weakSelf`, 블록 복사(`copy` property)
- **스레드**: `@synchronized`/`dispatch_async` 적절성, UI 업데이트 main thread 보장
- **API 혼합**: Swift ↔ Obj-C 브릿징 nullability 어노테이션(`_Nullable`, `_Nonnull`)
- **프로토콜**: `@optional`/`@required` 명시, delegate `weak` property
"""

COMPACT_KO = "## Objective-C: __weak retain cycle, nil 이중 패턴, 블록 weakSelf, main thread UI, nullability"

FULL_JA = """\
## Objective-C レビュー基準
- **メモリ**: ARC 環境確認、`strong` / `weak` / `unsafe_unretained` の選択、retain cycle (`__weak`)
- **nil 処理**: nil メッセージ送信は安全 (Obj-C 特性)、nil 戻り値 vs NSError 二重パターン
- **ブロック**: ブロック内 `self` キャプチャ → `__weak typeof(self) weakSelf`、ブロックコピー (`copy` property)
- **スレッド**: `@synchronized` / `dispatch_async` の適切性、UI 更新は main thread
- **API ミックス**: Swift ↔ Obj-C ブリッジングの nullability アノテーション (`_Nullable`、`_Nonnull`)
- **プロトコル**: `@optional` / `@required` 明示、delegate は `weak` property
"""

COMPACT_JA = "## Objective-C: __weak retain cycle、nil 二重パターン、ブロック weakSelf、main thread UI、nullability"
