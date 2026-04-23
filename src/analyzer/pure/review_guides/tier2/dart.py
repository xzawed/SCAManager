"""Dart/Flutter review guide — Tier 2."""

FULL = """\
## Dart 검토 기준
- **null 안전**: sound null safety 활성화, `!` 강제 non-null 최소화, `??`/`?.` 활용
- **비동기**: `async`/`await`, Future 에러 처리(`.catchError` vs try/catch), Stream 구독 해제
- **Flutter**: `const` 위젯 활용(재빌드 방지), `BuildContext` 비동기 후 사용 금지
- **상태 관리**: `setState` 최소 범위, Provider/Riverpod/Bloc 패턴 일관성
- **메모리**: `dispose()` 컨트롤러·스트림 구독 해제, GlobalKey 남용 주의
- **타입**: `dynamic` 최소화, `Object?` vs `dynamic` 구분, 제네릭 명시
"""

COMPACT = "## Dart: null safety, ! 최소화, const 위젯, BuildContext 비동기 금지, dispose() 필수"
