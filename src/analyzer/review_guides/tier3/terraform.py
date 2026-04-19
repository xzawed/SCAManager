"""Terraform/HCL review guide — Tier 3."""

FULL = """\
## Terraform 검토 기준
- **보안**: 시크릿 하드코딩 금지 → `var.`/환경변수/Vault, S3 버킷 퍼블릭 접근 차단
- **상태**: remote state backend 필수(로컬 tfstate 금지), state locking(DynamoDB)
- **모듈**: 모듈 버전 고정(`source = "... version = ..."`), 재사용 가능한 최소 인터페이스
- **변수**: `variable` 타입 제약(`type = string`), `sensitive = true` 민감 변수
- **명명**: 리소스 명 규칙(`{env}_{service}_{resource}`), `tags` 공통 태그
- **멱등성**: `plan` 결과 검토 — 의도치 않은 삭제/교체(force new resource) 확인
- **보안 그룹**: 최소 권한 원칙, `0.0.0.0/0` ingress 최소화
"""

COMPACT = "## Terraform: 시크릿 하드코딩 금지, remote state+locking, 모듈 버전 고정, sensitive 변수, plan 검토"
