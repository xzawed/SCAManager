"""YAML review guide — Tier 3."""

FULL = """\
## YAML 검토 기준
- **들여쓰기**: 스페이스만 사용(탭 금지), 일관된 들여쓰기(2칸 권장)
- **타입 주의**: `yes`/`no`/`on`/`off`는 bool로 파싱됨 — 문자열은 따옴표로 감싸기
- **앵커/별칭**: `&anchor`/`*alias` 재사용 명확성, 과도한 중첩 앵커 가독성 저하
- **시크릿**: YAML에 시크릿 하드코딩 금지 — 환경변수 참조 또는 외부 secret store
- **GitHub Actions**: `permissions` 최소 권한, `pull_request_target` 위험성 이해
- **Kubernetes**: resource limits 설정, `latest` 이미지 태그 금지, RBAC 최소 권한
- **검증**: `yamllint` / `kustomize build` / `helm lint` 도구 검증
"""

COMPACT = "## YAML: 탭 금지, yes/no bool 주의, 시크릿 하드코딩 금지, GitHub Actions permissions, K8s limits"
