# syntax=docker/dockerfile:1
# BASE_IMAGE で ubi-init(既定) / ubi-minimal を切り替える。パッケージマネージャは存在するほうを自動で選ぶ
# 既定は ITA の各コンテナと同じ ubi-init:9.4。ベースのレイヤーを共有してホストのディスク消費を抑える
ARG BASE_IMAGE=registry.access.redhat.com/ubi9/ubi-init
ARG BASE_VERSION=9.4
ARG UV_VERSION=latest
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM ${BASE_IMAGE}:${BASE_VERSION}
ARG CONTAINER_RUNTIME=docker
ARG INSTALL_DEV=false
ARG USERNAME=exastro \
  GROUPNAME=exastro \
  USER_UID=1000 \
  USER_GID=1000

# playbook実行コンテナはコンテナ外のランタイムに投げるためCLIのみを入れる
# 実行時に使うのはdocker(DOoD) / podmanのどちらか一方のため、ビルド引数で切り替える
# podman-dockerは/usr/bin/dockerがdocker-ce-cliと競合するため導入しない
RUN if [ "${CONTAINER_RUNTIME}" = "docker" ]; then \
  curl -fsSL -o /etc/yum.repos.d/docker-ce.repo https://download.docker.com/linux/centos/docker-ce.repo \
  && RUNTIME_PKG=docker-ce-cli; \
  elif [ "${CONTAINER_RUNTIME}" = "podman" ]; then \
  RUNTIME_PKG=podman; \
  else \
  echo "CONTAINER_RUNTIME must be docker or podman" >&2; exit 1; \
  fi \
  && PKG=$(command -v microdnf || command -v dnf) \
  && $PKG install -y --setopt=install_weak_deps=0 --nodocs glibc-langpack-en ${RUNTIME_PKG} \
  && $PKG clean all && rm -rf /var/cache/dnf /var/cache/yum \
  && groupadd -g ${USER_GID} ${GROUPNAME} \
  && useradd -m -s /bin/bash -g ${GROUPNAME} -u ${USER_UID} ${USERNAME} \
  && usermod -aG wheel ${USERNAME}
COPY --from=uv /uv /uvx /bin/

USER ${USERNAME}
WORKDIR /exastro
# エージェントは /exastro から python -m ansible-execution-agent.entrypoint で起動するため、
# ディレクトリ名 ansible-execution-agent はモジュール名の一部として固定である
COPY --chown=${USERNAME}:${GROUPNAME} uv.lock pyproject.toml /exastro/ansible-execution-agent/
# INSTALL_DEV=true のときだけ dev グループ(debugpy)を入れる
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
RUN --mount=type=cache,target=/home/${USERNAME}/.cache/uv,uid=${USER_UID},gid=${USER_GID} \
  uv python install --directory /exastro/ansible-execution-agent \
  && uv sync --frozen $([ "${INSTALL_DEV}" = "true" ] || echo --no-dev) --directory /exastro/ansible-execution-agent
COPY --chown=${USERNAME}:${GROUPNAME} --exclude=messages . /exastro/ansible-execution-agent/
# common/message_class.py の読み込み先は /exastro/messages 固定
COPY --chown=${USERNAME}:${GROUPNAME} messages/ /exastro/messages/
ENTRYPOINT ["ansible-execution-agent/entrypoint.sh"]
