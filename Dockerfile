# SCAManager 운영 이미지 — Railway 가 저장소 루트의 이 파일을 자동 감지해 빌드한다.
# 분석기 버전의 정본은 여기다. CI(.github/workflows/ci.yml)는 같은 버전을 설치해야 한다
# — tests/unit/scripts/test_ci_provisions_the_contract.py 가 대조한다.
# Production image, auto-detected by Railway. Analyzer pins live here; CI must match them.

# Ubuntu 24.04 = 옛 Nixpacks 이미지와 CI 러너(ubuntu-latest)의 OS 다.
# shellcheck·cppcheck·ruby·go 가 운영·CI 와 같은 apt 버전으로 온다.
# Same OS as the former Nixpacks image and the CI runner, so apt analyzers match both.
FROM ubuntu:24.04

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# PATH 앞의 venv — pre-deploy `alembic upgrade head` 는 exec 형이라 PATH 로만 풀린다.
# VIRTUAL_ENV 는 solc-select 가 컴파일러를 venv 아래(/opt/venv/.solc-select)에 두게 한다
# — root 가 빌드 때 깔고 비-root 런타임이 읽는다.
# The venv leads PATH so the exec-form pre-deploy resolves alembic. VIRTUAL_ENV makes
# solc-select keep compilers under the venv, where the non-root runtime can read them.
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# 시스템 패키지 — 옛 nixpacks.toml aptPkgs 전량 + python·curl·gnupg(NodeSource 키).
# apt 버전은 핀하지 않는다: 배포판(noble)이 고정이고, 핀은 보안 갱신을 막는다.
# 런타임 사용자(uid 10001)도 여기서 만든다 — 홈은 semgrep·rubocop·go 캐시용.
# System packages: the former aptPkgs plus python/curl/gnupg. The release pins the versions.
# The runtime user is created here too; its home holds the tools' caches.
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg unzip \
      python3.12 python3.12-venv python3.12-dev \
      shellcheck cppcheck ruby-full golang-go build-essential libyaml-dev \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 app

# Node 20 — NodeSource 공식 저장소(서명 키 검증). CI 의 setup-node 와 같은 major.
# Node 20 from the official NodeSource repo (signed); same major as CI.
# hadolint ignore=DL3008
RUN mkdir -p /etc/apt/keyrings \
 && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
 && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*

# 분석기 바이너리 — 전부 정확한 버전 하나로 핀(범위 · 메이저만 · 버전 없음은
# tests/unit/scripts/test_ci_provisions_the_contract.py 가 막는다). 🔴 실패를 `|| echo` 로 삼키지 않는다:
# 삼킨 실패는 이 레이어에 **캐시돼** 이후 빌드마다 도구 없는 이미지가 나온다. 빌드가 실패하면 Railway 는
# 이전 배포를 그대로 서비스한다.
# eslint 는 엔진만 여기서 온다 — 분석기 설정이 import 하는 파서(@typescript-eslint/parser)와 그 typescript 는
# 아래 `npm ci`(package-lock)에서 온다. package.json 의 eslint 는 이 리포 템플릿 린트(`lint:js`)용이다.
# Analyzers pinned to one exact version each (the contract test rejects ranges, bare majors and bare names).
# Failures are not swallowed: a swallowed failure would be cached in this layer and every later
# build would ship without the tool. A failed build keeps the old deploy. Only the eslint engine
# comes from here; the parser its config imports comes from `npm ci` below.
# GitHub 릴리스 내려받기는 몇 분 흔들려도 버티게 재시도하고(모든 오류 · 연결 20 초 · 한 번 180 초 · 15 초 간격 20번 —
# 빠른 실패면 약 5 분 · 새 시도는 300 초까지) 받은 파일마다
# sha256 을 대조한다 — 11-09 GitHub 504 동안 배포 빌드 3건이 이 단계에서 실패했다(회고 원장 R-7). 체크섬 = 각 릴리스의
# 공식 체크섬 파일(ktlint 는 서명만 있어 공식 주소에서 받은 파일의 값). 버전을 올리면 체크섬도 같은 커밋에서 바꾼다 —
# `.github/workflows/ci.yml` 조달 step 과 같은 값이어야 한다(`tests/unit/scripts/test_ci_provisions_the_contract.py`).
# golangci-lint 는 설치 스크립트를 쓰지 않는다 — 그 안의 내려받기는 이 재시도 · 대조를 받지 않는다.
# Release downloads retry for minutes and are sha256-checked; bump the checksum with the version.
RUN gem install rubocop-ast -v 1.36.2 --no-document --bindir /usr/bin \
 && gem install rubocop -v 1.57.2 --no-document --bindir /usr/bin \
 && curl -sSfL --connect-timeout 20 --max-time 180 --retry 20 --retry-all-errors --retry-delay 15 --retry-max-time 300 \
    https://github.com/golangci/golangci-lint/releases/download/v1.55.2/golangci-lint-1.55.2-linux-amd64.tar.gz \
    -o /tmp/golangci-lint.tar.gz \
 && echo "ca21c961a33be3bc15e4292dc40c98c8dcc5463a7b6768a3afc123761630c09c  /tmp/golangci-lint.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/golangci-lint.tar.gz -C /tmp \
 && install -m 0755 /tmp/golangci-lint-1.55.2-linux-amd64/golangci-lint /usr/bin/golangci-lint \
 && rm -rf /tmp/golangci-lint.tar.gz /tmp/golangci-lint-1.55.2-linux-amd64 \
 && curl -sSfL --connect-timeout 20 --max-time 180 --retry 20 --retry-all-errors --retry-delay 15 --retry-max-time 300 \
    https://github.com/hadolint/hadolint/releases/download/v2.15.1/hadolint-linux-x86_64 \
    -o /usr/bin/hadolint \
 && echo "c7187db94eeeeca956519a6af171adc31453941a1e777961f6e680f697c8c507  /usr/bin/hadolint" | sha256sum -c - \
 && chmod +x /usr/bin/hadolint \
 && curl -sSfL --connect-timeout 20 --max-time 180 --retry 20 --retry-all-errors --retry-delay 15 --retry-max-time 300 \
    https://github.com/pinterest/ktlint/releases/download/1.8.0/ktlint \
    -o /usr/bin/ktlint \
 && echo "a3fd620207d5c40da6ca789b95e7f823c54e854b7fade7f613e91096a3706d75  /usr/bin/ktlint" | sha256sum -c - \
 && chmod +x /usr/bin/ktlint \
 && curl -sSfL --connect-timeout 20 --max-time 180 --retry 20 --retry-all-errors --retry-delay 15 --retry-max-time 300 \
    https://github.com/terraform-linters/tflint/releases/download/v0.64.0/tflint_linux_amd64.zip \
    -o /tmp/tflint.zip \
 && echo "cca9d13e2e1d7a2c627af60ff899a3c9b74212899416aeb96ec764d2ef954537  /tmp/tflint.zip" | sha256sum -c - \
 && unzip -o /tmp/tflint.zip -d /usr/bin/ \
 && chmod +x /usr/bin/tflint \
 && rm /tmp/tflint.zip \
 && npm install -g eslint@10.14.0 typescript@6.0.3 \
 && npm cache clean --force

WORKDIR /app

# Python 의존성 — requirements.txt 만 먼저 복사해 코드 변경이 이 레이어를 깨지 않게 한다.
# Python deps first, so code-only changes reuse this layer.
COPY requirements.txt ./
RUN python3.12 -m venv /opt/venv \
 && pip install --retries 5 --timeout 60 -r requirements.txt

# semgrep — 앱과 **다른 venv**. 앱은 CLI 로만 부르므로 `semgrep` 하나만 PATH 에 링크한다(venv 의 bin 을 PATH 에
# 올리면 그 venv 의 python 이 앱 python 을 가린다). 그 정확 전이 핀이 앱 의존성과 섞이지 않는다(requirements-semgrep.txt).
# semgrep in its own venv; only its CLI is linked onto PATH so the app's python and pins stay its own.
COPY requirements-semgrep.txt ./
RUN python3.12 -m venv /opt/semgrep \
 && /opt/semgrep/bin/pip install --retries 5 --timeout 60 -r requirements-semgrep.txt \
 && ln -s /opt/semgrep/bin/semgrep /usr/local/bin/semgrep

# slither 가 Solidity 를 컴파일할 solc — solc-select 는 slither-analyzer 의 전이 의존이다.
# The solc compiler slither needs; solc-select arrives transitively with slither-analyzer.
RUN solc-select install 0.8.20 \
 && solc-select use 0.8.20

# npm 의존성 — Tailwind 빌드 + 런타임 eslint 분석기 설정이 리포 node_modules 를 읽는다.
# `--ignore-scripts` = 설치 스크립트 미실행(공급망 hardening, CI 와 같다).
# Tailwind build + the runtime eslint config both read the repo node_modules.
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts \
 && npm cache clean --force

# Tailwind 빌드 뒤 🔴 조달 계약 확인 — `PROVISIONED_ANALYZERS` 의 바이너리가 없으면 빌드 실패다.
# 목록을 여기 옮겨 적지 않고 코드에서 읽는다(런타임 판정 `_binary_is_absent` 와 같은 함수).
# Build the CSS, then fail the build if any contracted analyzer binary is missing (runtime's check).
COPY . .
RUN npm run build \
 && python -c "import sys; from src.analyzer.io.static import PROVISIONED_ANALYZERS as P, _binary_is_absent as absent; missing = sorted(t for t in P if absent(t)); print('provisioned analyzers missing:', missing or 'none', '/', len(P)); sys.exit(1 if missing else 0)"

# 🔴 런타임 사용자의 HOME 을 못박는다 — 런타임이 /etc/passwd 로 채워 주지 않으면 golangci-lint 가
#   빌드 캐시를 못 만들어 Go 파일이 조용히 「문제 없음」이 된다(리뷰 실측). 모든 RUN 뒤에 둬야
#   root 로 도는 빌드 단계의 캐시가 이 디렉터리에 root 소유로 쌓이지 않는다.
# Pin HOME for the runtime user (golangci-lint's build cache). After every RUN so root caches never land there.
ENV HOME=/home/app

# 비-root 실행 — 분석기는 PR 의 신뢰할 수 없는 코드를 돈다.
# Run as non-root: analyzers process untrusted PR code.
USER 10001:10001

EXPOSE 8000

# 🔴 `sh -c` 로 감싼다 — `$PORT` 는 셸만 확장한다(exec 형 단독은 글자 그대로 넘긴다). `exec` 로
# uvicorn 이 PID 1 이 되어 SIGTERM 을 직접 받는다. PORT 가 없으면(로컬 실행) 8000.
# Wrapped in `sh -c` because only a shell expands $PORT; `exec` makes uvicorn PID 1.
CMD ["/bin/sh", "-c", "exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
