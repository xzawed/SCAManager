"""tests/unit 공용 fixture — 전역 logging 상태 격리.
Shared fixtures for tests/unit — global logging state isolation.

🔴 왜 필요한가: `logging` 은 프로세스 전역 싱글톤이다. `logging.config.fileConfig()` 는
기본값 `disable_existing_loggers=True` 로 **이미 존재하는 모든 로거를 disable** 하고,
`_clearExistingHandlers()` 로 root 핸들러와 전역 핸들러 레지스트리(`logging._handlerList`,
`logging._handlers`)까지 비운다. 이 부작용이 테스트 밖으로 새면 pytest 의 caplog 핸들러가
사라지고 `src.*` 로거가 disabled 인 채 남아 **뒤따르는 수천 건이 비결정적으로 깨진다**.
🔴 Why: logging is a process-wide singleton. fileConfig() defaults to disable_existing_loggers=True
and also wipes root handlers plus the global handler registries. Leaking that state would strip
pytest's caplog handler and leave src.* loggers disabled, breaking thousands of later tests.

이 fixture 는 non-autouse (opt-in) — 요청한 테스트에만 비용이 든다.
Non-autouse by design: only the tests that request it pay the cost.
"""
import logging
import logging.config

import pytest

# 로거 1개의 복원 대상 가변 상태 / the mutable per-logger state we restore
_PRISTINE = (logging.NOTSET, [], [], True, False)


def _snapshot_logger(lg: logging.Logger) -> tuple:
    """로거의 가변 상태를 캡처 — handlers/filters 는 리스트 복사(참조 공유 금지).
    Capture a logger's mutable state; copy the handler/filter lists rather than aliasing them.
    """
    return (lg.level, list(lg.handlers), list(lg.filters), lg.propagate, lg.disabled)


def _restore_logger(lg: logging.Logger, snap: tuple) -> None:
    """캡처한 상태로 로거를 되돌린다.
    Restore a logger from a captured snapshot.

    🔴 `setLevel()` 사용 의무 — `lg.level = N` 직접 대입은 `Logger._cache`(isEnabledFor 결과
    캐시)를 무효화하지 않아, 복원 후에도 낡은 판정이 남는다.
    🔴 Must use setLevel(): assigning .level directly leaves Logger._cache stale, so isEnabledFor
    would keep returning the pre-restore verdict.
    """
    level, handlers, filters, propagate, disabled = snap
    lg.setLevel(level)
    lg.handlers[:] = handlers
    lg.filters[:] = filters
    lg.propagate = propagate
    lg.disabled = disabled


@pytest.fixture
def logging_isolation():
    """전역 logging 상태를 스냅샷 → yield → 원상 복구.
    Snapshot global logging state, yield, then restore it exactly.

    복구 범위 / restored surface:
      1. root 로거 (level·handlers·filters·propagate·disabled)
      2. 스냅샷 시점에 존재하던 **모든** 로거의 동일 5종 상태 (fileConfig 가 전부 disable 한다)
      3. 테스트 중 새로 생성된 로거 → 기본 상태(NOTSET·핸들러 없음·propagate)로 리셋
      4. 전역 핸들러 레지스트리 `logging._handlerList` / `logging._handlers`
         — `_clearExistingHandlers()` 가 이 둘을 비우므로 복구하지 않으면 pytest caplog
           핸들러가 레지스트리에서 영구 소실된다
      5. `logging.disable()` 전역 임계값 (`manager.disable`)
      6. `manager._clear_cache()` — isEnabledFor 캐시 무효화 (레벨 변경이 반영되도록)
    """
    manager = logging.Logger.manager
    root = logging.getLogger()

    saved_root = _snapshot_logger(root)
    saved_loggers = {
        name: _snapshot_logger(obj)
        for name, obj in list(manager.loggerDict.items())
        if isinstance(obj, logging.Logger)  # PlaceHolder 는 대상 아님 / skip PlaceHolder entries
    }
    saved_names = set(manager.loggerDict)
    saved_disable = manager.disable
    # 🔴 private 레지스트리 — `dict(...)` 는 WeakValueDictionary 에서 강참조를 떠 테스트 도중
    # 핸들러가 GC 되는 것도 함께 막는다.
    # 🔴 Private registries; dict(...) also pins strong refs so handlers survive the test body.
    saved_handler_list = list(getattr(logging, "_handlerList", []))
    saved_handlers = dict(getattr(logging, "_handlers", {}))

    try:
        yield
    finally:
        _restore_logger(root, saved_root)
        for name, snap in saved_loggers.items():
            obj = manager.loggerDict.get(name)
            if isinstance(obj, logging.Logger):
                _restore_logger(obj, snap)
        # 테스트가 새로 만든 로거는 삭제 대신 초기 상태로 리셋 — 외부에 남은 참조를 깨지 않는다.
        # Reset (not delete) loggers created during the test so outside references stay valid.
        for name in set(manager.loggerDict) - saved_names:
            obj = manager.loggerDict.get(name)
            if isinstance(obj, logging.Logger):
                _restore_logger(obj, _PRISTINE)
        if hasattr(logging, "_handlerList"):
            logging._handlerList[:] = saved_handler_list
        if hasattr(logging, "_handlers"):
            logging._handlers.clear()
            logging._handlers.update(saved_handlers)
        manager.disable = saved_disable
        clear_cache = getattr(manager, "_clear_cache", None)
        if callable(clear_cache):
            clear_cache()
