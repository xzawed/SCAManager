"""민감 경로 hold 목록이 **드리프트했는지** 잰다 — 손유지 리스트의 유일한 강제자 (#1543).

`src/gate/sensitive_paths.py::_SENSITIVE_PATTERNS` 는 무검토 auto-merge 를 막는 **유일한
경로 인지 홀드**다. 점수 게이트는 경로 민감도를 모른다 — 60점만 넘으면 인증 변경도 그냥
머지된다(그 파일의 주석이 `#1102~#1107` 6건 전부 `reviews=0`, 그중 `#1104` 는 토큰 유출
P0 였다고 기록한다).

목록 안의 SCAManager 고유 파일은 손으로 적는다. 대조 대상이던 `.claude/rules/security.md`
가 삭제돼 **drift 를 강제하는 것이 없었다.** 이 스크립트가 그 자리를 메운다.

## 오라클 — 사람의 판단이 아니라 import

「보안 파일인가」를 판단이나 키워드 세기로 정하면 그 판정이 곧 드리프트한다.
`import hmac` 은 **기계 사실**이다: 서명을 검증하거나 시크릿을 만들거나 토큰을 암호화하려면
그 이름을 적어야 한다.

넓은 신호(`subprocess` · `log_safety` · `auth.session`)는 일부러 뺐다 — 실측 60파일이라
그것으로 막으면 정상 PR 이 막히고 사용자가 가드를 끈다(가드의 자살). 강한 넷만 본다.

## 런타임과 분리한다

이 검사는 **CI 전용**이다. 런타임 가드는 고객 리포 PR 에도 돌고, 그쪽 파일 내용을 읽지
않는다 — 경로만 본다. 그래서 여기서 잰 결과를 런타임이 import 하지 않는다. 우리 트리의
목록이 완전한지만 강제한다.

Enforce that every file using a strong security primitive is covered by the merge hold.
CI-only: the runtime guard is path-based and also runs on customer repos.
"""
from __future__ import annotations

import ast
import io
import pathlib
import re
import sys


def _make_stdout_safe() -> None:
    """Windows(cp949) 콘솔에서 한국어 출력이 UnicodeEncodeError 로 죽는 것을 막는다.

    🔴 **이미 UTF-8 이면 손대지 않는다.** 무조건 감싸면 pytest 의 캡처 스트림을
    새 wrapper 가 물고 있다가 닫아 버려, 이 스크립트를 import 하는 테스트 전부가
    `ValueError: I/O operation on closed file` 로 죽는다(내 첫 판이 그랬다).

    Repo convention: re-wrap stdout as UTF-8 only when it is not already UTF-8.
    """
    encoding = str(getattr(sys.stdout, "encoding", "") or "")
    if encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


_make_stdout_safe()

# 🔴 강한 보안 원시요소 — 이 이름을 적었다면 서명·시크릿·암호화를 다룬다는 뜻이다.
#   넓히지 마라: `subprocess`·`log_safety`·`auth.session` 을 넣으면 60파일이 되고,
#   그러면 정상 PR 이 막혀 사용자가 가드를 끈다(실측 2026-08-27).
# Strong primitives only; broadening this list disables the guard in practice.
_STRONG_MODULES: frozenset[str] = frozenset({
    # 표준 라이브러리 / stdlib
    "hmac", "secrets",
    # 🔴 서드파티 암호·인증 — 처음엔 stdlib 두 개만 봤고, 그래서 `src/crypto.py`
    #   (`cryptography.fernet`) 와 그 복제본을 **오라클이 아예 못 봤다**(Grok 01a04342 Q1).
    #   지금 hold 인 것은 손으로 적혀 있어서지 오라클이 본 것이 아니었다.
    # Third-party crypto/authz: the four-name oracle could not see `cryptography.fernet`.
    "cryptography", "jwt", "itsdangerous", "passlib", "authlib", "nacl",
    "bcrypt", "argon2",
})
# 우리 보안 모듈 — **접두 일치**다. `src.shared.ssrf` 를 경유하는 아웃바운드 호출부는
# 그 방어를 무력화할 수 있으므로 같이 본다(실측: 2파일).
_STRONG_FROM: tuple[str, ...] = (
    "src.crypto", "src.shared.secure_compare", "src.shared.ssrf",
)

# 🔴 강한 원시요소를 쓰지만 머지 hold 대상이 **아닌** 것 — 사유를 적어야 한다.
#   사유 없이 면제되면 이 목록이 다시 손유지 리스트가 된다.
# Exemptions must carry a reason, or this becomes another hand-maintained list.
REVIEWED_NOT_SENSITIVE: dict[str, str] = {}

# 면제 사유 최소 길이 — 테스트에만 두면 스크립트는 아무 사유나 받는다(Grok MISSED 1).
_MIN_REASON = 16

# 🔴 「스캔이 눈멀었는가」를 **개수**로 재지 않는다.
#
#   첫 판은 `_MIN_EXPECTED = 10` 이었다. 그러면 파일 5개를 정당하게 지우는 순간 red 가
#   되고, 그 처방은 「상수를 낮춰라」다 — 그게 곧 무장 해제다(Grok 01a04342 Q4).
#   개수 하한은 정당한 삭제를 벌하는 모양이다.
#
#   대신 **계기를 알려진 양성으로 자기검증**한다. 이 두 파일은 각각의 원시요소를 확실히
#   쓰고, 지워질 이유가 없다(둘 다 그 원시요소의 정의 자리이거나 유일 소비자다).
#   스캐너가 이것을 못 보면 개수와 무관하게 계기가 깨진 것이다.
# Self-test the scanner against known positives instead of a population floor:
# a count floor punishes legitimate deletion and its fix is the disarm itself.
_SCANNER_SELF_TEST: dict[str, str] = {
    "src/shared/secure_compare.py": "hmac",
    "src/crypto.py": "cryptography",
}


def _classify(module: str) -> str | None:
    """모듈 이름 하나를 강한 원시요소로 분류한다 — 없으면 None."""
    if module.split(".")[0] in _STRONG_MODULES:
        return module.split(".")[0]
    for own in _STRONG_FROM:
        if module == own or module.startswith(own + "."):
            return own
    return None


def _module_names(node: ast.AST, rel: str) -> list[str]:
    """🔴 import 한 줄에서 **모듈 이름 전부**를 뽑는다 — 형태가 셋이다.

        import src.crypto                 -> Import,     alias.name 이 점 표기
        from src.crypto import decrypt    -> ImportFrom,  node.module
        from ..crypto import decrypt      -> ImportFrom,  node.level > 0 (상대)

    첫 판은 `Import` 의 **루트만** 봐서 `import src.crypto` 를 놓쳤고(루트는 `src`),
    상대 import 는 아예 몰랐다(Grok 01a04342 MISSED 2). 이 리포는 실제로
    `import src.gate.actions.approve` 형태를 쓴다.

    Three import shapes; the first version only looked at the root of a dotted Import.
    """
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if not isinstance(node, ast.ImportFrom):
        return []
    if not node.level:
        return [node.module] if node.module else []
    # 상대 import — 이 파일의 패키지를 기준으로 절대 경로로 되돌린다.
    parts = rel.split("/")[:-1]
    base = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
    return [".".join([*base, node.module]) if node.module else ".".join(base)]


def _imports_strong_primitive(path: pathlib.Path, rel: str) -> set[str]:
    """파일이 강한 보안 원시요소를 import 하는지 — AST 로 본다(문자열 검색이 아니라)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return set()
    hits: set[str] = set()
    for node in ast.walk(tree):
        for module in _module_names(node, rel):
            found = _classify(module)
            if found:
                hits.add(found)
    return hits


def scan_strong_primitive_files(root: pathlib.Path) -> dict[str, list[str]]:
    """`src/**/*.py` 중 강한 보안 원시요소를 쓰는 파일 -> 쓴 이름들."""
    found: dict[str, list[str]] = {}
    for path in sorted((root / "src").rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        hits = _imports_strong_primitive(path, rel)
        if hits:
            found[rel] = sorted(hits)
    return found


def _hold_patterns(root: pathlib.Path) -> list[re.Pattern]:
    """런타임 가드의 패턴을 **AST 로** 읽는다 — import 하면 앱 설정이 딸려 온다.

    🔴 정규식으로 소스를 긁지 않는다. 목록 안에 두 줄로 나뉜 패턴이 있고
    (`(auth|...|secrets|` + `credential|...)` 로 이어 붙는 그 패턴),
    문자열 리터럴을 따로 뽑으면 **반토막 난 정규식**이 되어 컴파일이 터진다.
    파서는 인접 리터럴을 하나로 합쳐 주므로 AST 가 정본이다.

    Read via AST: adjacent string literals are one Constant, a regex scrape splits them.
    """
    source = (root / "src" / "gate" / "sensitive_paths.py").read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    raws: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign | ast.Assign):
            continue
        targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
        if not any(isinstance(t, ast.Name) and t.id == "_SENSITIVE_PATTERNS"
                   for t in targets):
            continue
        raws = [n.value for n in ast.walk(node)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return [re.compile(raw, re.IGNORECASE) for raw in raws]


def main() -> int:
    """드리프트가 있으면 1, 없으면 0. 아무것도 못 재도 1 — 「안 쟀음」은 통과가 아니다."""
    root = pathlib.Path.cwd()
    found = scan_strong_primitive_files(root)
    patterns = _hold_patterns(root)

    if not patterns:
        print("🔴 hold 패턴을 읽지 못했다 — `_SENSITIVE_PATTERNS` 의 형태가 바뀌었다.")
        print("   Could not read the hold patterns; the guard is measuring nothing.")
        return 1

    # 🔴 계기 자기검증 — 알려진 양성을 못 보면 개수와 무관하게 스캐너가 깨진 것이다.
    #    자기검증 파일이 트리에 없으면(테스트용 tmp 트리) 그 항목은 건너뛴다.
    blind = [
        f"{path} ({prim})" for path, prim in _SCANNER_SELF_TEST.items()
        if (root / path).exists() and prim not in found.get(path, [])
    ]
    if blind:
        print("🔴 스캐너가 **알려진 양성**을 못 봤다 — 계기가 깨졌다:")
        print("   The scanner missed a known positive; it is measuring nothing.")
        for item in blind:
            print(f"   - {item}")
        print("   초록이 아니라 '안 쟀음' 이다.")
        return 1

    # 면제는 **사유**를 요구한다 — 사유 없이 면제되면 다시 손유지 리스트가 된다.
    # An exemption without a reason turns this back into a hand-maintained list.
    thin = {p: r for p, r in REVIEWED_NOT_SENSITIVE.items() if len(r) < _MIN_REASON}
    if thin:
        print(f"🔴 면제 사유가 {_MIN_REASON}자 미만이다:")
        for path, reason in sorted(thin.items()):
            print(f"   - {path}: {reason!r}")
        return 1

    drift = {
        path: names for path, names in found.items()
        if not any(p.search(path) for p in patterns) and path not in REVIEWED_NOT_SENSITIVE
    }

    if drift:
        print("🔴 강한 보안 원시요소를 쓰는데 **무검토 auto-merge hold 밖**인 파일:")
        print("   Files using a strong security primitive that the merge hold does not cover:")
        for path, names in sorted(drift.items()):
            print(f"   - {path}  ({', '.join(names)})")
        print()
        print("해결 / Fix: `src/gate/sensitive_paths.py::_SENSITIVE_PATTERNS` 에 등재하거나,")
        print("   민감하지 않다면 이 스크립트의 `REVIEWED_NOT_SENSITIVE` 에 **사유와 함께** 적으세요.")
        print("   점수 게이트는 경로 민감도를 모릅니다 — 60점만 넘으면 그대로 머지됩니다.")
        return 1

    exempt = f" · 면제 {len(REVIEWED_NOT_SENSITIVE)}" if REVIEWED_NOT_SENSITIVE else ""
    print(f"✅ 강한 보안 원시요소 파일 {len(found)}개 전부 머지 hold 안{exempt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
