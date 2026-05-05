"""YAML review guide — Tier 3.

Phase 4 PR-15 (사이클 84) — i18n: en (default) / ko / ja.
"""

FULL = """\
## YAML review checklist
- **Indentation**: Spaces only (no tabs); consistent indentation (2 spaces recommended)
- **Type gotchas**: `yes` / `no` / `on` / `off` parse as bool — quote strings
- **Anchors/aliases**: Clear `&anchor` / `*alias` reuse; deep nesting hurts readability
- **Secrets**: No hardcoded secrets in YAML — reference env vars or external secret stores
- **GitHub Actions**: Least-privilege `permissions`; understand `pull_request_target` risks
- **Kubernetes**: Set resource limits; no `latest` image tags; least-privilege RBAC
- **Validation**: Validate with `yamllint` / `kustomize build` / `helm lint`
"""

COMPACT = "## YAML: no tabs, yes/no bool gotcha, no secrets, GitHub Actions perms, K8s limits"

FULL_KO = """\
## YAML 검토 기준
- **들여쓰기**: 스페이스만 사용(탭 금지), 일관된 들여쓰기(2칸 권장)
- **타입 주의**: `yes`/`no`/`on`/`off`는 bool로 파싱됨 — 문자열은 따옴표로 감싸기
- **앵커/별칭**: `&anchor`/`*alias` 재사용 명확성, 과도한 중첩 앵커 가독성 저하
- **시크릿**: YAML에 시크릿 하드코딩 금지 — 환경변수 참조 또는 외부 secret store
- **GitHub Actions**: `permissions` 최소 권한, `pull_request_target` 위험성 이해
- **Kubernetes**: resource limits 설정, `latest` 이미지 태그 금지, RBAC 최소 권한
- **검증**: `yamllint` / `kustomize build` / `helm lint` 도구 검증
"""

COMPACT_KO = "## YAML: 탭 금지, yes/no bool 주의, 시크릿 하드코딩 금지, GitHub Actions permissions, K8s limits"

FULL_JA = """\
## YAML レビュー基準
- **インデント**: スペースのみ (タブ禁止)、一貫したインデント (2 スペース推奨)
- **型注意**: `yes` / `no` / `on` / `off` は bool としてパース — 文字列はクォートで囲む
- **アンカー/エイリアス**: `&anchor` / `*alias` の再利用を明確化、深いネストで可読性低下
- **シークレット**: YAML へのシークレットハードコード禁止 — 環境変数参照または外部シークレットストア
- **GitHub Actions**: `permissions` 最小権限、`pull_request_target` のリスクを理解
- **Kubernetes**: リソースリミット設定、`latest` イメージタグ禁止、RBAC 最小権限
- **検証**: `yamllint` / `kustomize build` / `helm lint` で検証
"""

COMPACT_JA = "## YAML: タブ禁止、yes/no bool 注意、シークレット禁止、GitHub Actions permissions、K8s limits"
