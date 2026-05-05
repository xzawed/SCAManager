"""Dart/Flutter review guide — Tier 2.

Phase 4 PR-14 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## Dart review checklist
- **Null safety**: Enable sound null safety; minimize `!` force-non-null; use `??` / `?.`
- **Async**: `async` / `await`; handle Future errors (`.catchError` vs try/catch); cancel Stream subscriptions
- **Flutter**: Use `const` widgets (avoid rebuilds); don't reuse `BuildContext` after async gaps
- **State management**: Minimize `setState` scope; consistent Provider / Riverpod / Bloc pattern
- **Memory**: Call `dispose()` for controllers/stream subscriptions; avoid GlobalKey overuse
- **Types**: Minimize `dynamic`; distinguish `Object?` vs `dynamic`; explicit generics
"""

COMPACT = "## Dart: null safety, minimize !, const widgets, no BuildContext after async, dispose()"

FULL_KO = """\
## Dart 검토 기준
- **null 안전**: sound null safety 활성화, `!` 강제 non-null 최소화, `??`/`?.` 활용
- **비동기**: `async`/`await`, Future 에러 처리(`.catchError` vs try/catch), Stream 구독 해제
- **Flutter**: `const` 위젯 활용(재빌드 방지), `BuildContext` 비동기 후 사용 금지
- **상태 관리**: `setState` 최소 범위, Provider/Riverpod/Bloc 패턴 일관성
- **메모리**: `dispose()` 컨트롤러·스트림 구독 해제, GlobalKey 남용 주의
- **타입**: `dynamic` 최소화, `Object?` vs `dynamic` 구분, 제네릭 명시
"""

COMPACT_KO = "## Dart: null safety, ! 최소화, const 위젯, BuildContext 비동기 금지, dispose() 필수"

FULL_JA = """\
## Dart レビュー基準
- **null 安全**: sound null safety を有効化、`!` 強制 non-null を最小化、`??` / `?.` を活用
- **非同期**: `async` / `await`、Future エラー処理 (`.catchError` vs try/catch)、Stream 購読解除
- **Flutter**: `const` ウィジェット活用 (リビルド防止)、非同期後の `BuildContext` 使用禁止
- **状態管理**: `setState` スコープを最小化、Provider / Riverpod / Bloc パターンの一貫性
- **メモリ**: コントローラ・ストリーム購読の `dispose()`、GlobalKey の濫用注意
- **型**: `dynamic` を最小化、`Object?` vs `dynamic` 区別、ジェネリクスを明示
"""

COMPACT_JA = "## Dart: null safety、! 最小化、const ウィジェット、BuildContext 非同期後禁止、dispose() 必須"
