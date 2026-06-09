"""`i18n_args(...) | safe` 호출 계약 가드 (#34 Option A 방어선).

`i18n_args(...) | safe` caller contract guard (#34 Option A defence line).

#34 Option A 로 i18n_args 필터의 수동 escape 를 제거(이중 이스케이프 해소)한 뒤,
autoescape 가 꺼진 `| safe` 컨텍스트에서 kwarg 는 더 이상 필터에서 escape 되지 않는다.
따라서 `i18n_args(...kwargs...) | safe` 호출처에 **사용자 제어 문자열 kwarg** 가 추가되면
XSS 우회가 된다. 본 가드는 그런 호출처를 vetted allowlist 로 고정해, 신규 위험 호출처가
추가되면 CI fail 로 사람 검토를 강제한다.

After #34 Option A removed the filter-level manual escape, a `| safe` caller passing a kwarg
bypasses Jinja2 autoescape. This guard pins such callers to a vetted allowlist so a future
user-data kwarg in a `| safe` context fails CI and forces review.
"""
import pathlib
import re

_TEMPLATES = pathlib.Path(__file__).resolve().parents[3] / "src" / "templates"

# kwargs(=) + | safe 를 동반하는 i18n_args 호출의 검증된 안전 키.
# Vetted-safe keys for i18n_args calls that carry kwargs AND | safe.
#   - range_summary: approve/reject = config 정수(Field 검증) — 사용자 자유문자열 아님
#   - telegram_otp_expires: remaining = 개발자 작성 Markup <span> — 의도적 HTML
_SAFE_KWARG_ALLOWLIST = {
    "settings_page.pr_rules.range_summary",
    "settings_page.notify.telegram_otp_expires",
}

_KEY_RE = re.compile(r"'([^']+)'\s*\|\s*i18n_args")
# i18n_args(...) 인자 안의 kwarg 패턴 (`, name=` 형태) — `default('ko')` 등 위치 인자 제외
# kwarg pattern inside i18n_args(...) (`, name=`); excludes positional like default('ko')
_KWARG_RE = re.compile(r",\s*\w+\s*=")


def test_safe_i18n_args_callers_pass_only_vetted_kwargs():
    """`i18n_args(...kwargs...) | safe` 호출처는 vetted allowlist 키만 허용 (#34 방어선)."""
    offenders: dict[str, set[str]] = {}
    for path in _TEMPLATES.rglob("*.html"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if "i18n_args(" not in line or "| safe" not in line:
                continue
            seg = line[line.index("i18n_args("):]
            if not _KWARG_RE.search(seg):
                continue  # kwargs 없는 호출은 XSS 우회 위험 없음 (번역문은 신뢰)
            match = _KEY_RE.search(line)
            key = match.group(1) if match else line.strip()
            if key not in _SAFE_KWARG_ALLOWLIST:
                offenders.setdefault(path.name, set()).add(key)
    assert not offenders, (
        "i18n_args(...kwargs...) | safe 신규 호출처 발견 — autoescape 우회로 사용자 입력 XSS 위험. "
        "kwarg 가 config 상수/Markup 등 안전값임을 확인 후 _SAFE_KWARG_ALLOWLIST 에 등재하라. "
        f"미등재 호출처: {offenders}"
    )
