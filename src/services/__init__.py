"""Service layer — use case 오케스트레이션 전용 패키지.

**배치 규약**: 신규 use case 는 본 패키지에 `*_service.py` 로 추가한다.

**기존 3개 서비스급 모듈은 현 위치 유지** (Phase S.3 결정):
- `src/worker/pipeline.py` — 분석 오케스트레이션 (11곳 import)
- `src/gate/engine.py` — PR Gate 3-옵션 처리 (3곳 import)
- `src/config_manager/manager.py` — Repo 설정 CRUD + `RepoConfigData` 변환 (11곳 import)

이들은 각 도메인 패키지의 안정적 인터페이스. `src/services/` 로 이관 시
94곳 import + 19 파일 변경이 필요해 이득보다 비용이 크다. 신규 use case
만 본 패키지에 추가해 장기적으로 아키텍처를 수렴시킨다.

**네이밍 규약**: `<domain>_service.py` (예: `notification_service.py`,
`scoring_service.py`).

**계층 의존성**: services/ 는 repositories/ · analyzer/ · notifier/ 등
하위 패키지를 import 해도 되지만, api/·ui/·webhook/ 같은 상위 어댑터
계층을 import 하면 안 된다 (clean architecture 역방향 금지).
"""
