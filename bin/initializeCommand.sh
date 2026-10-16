#!/bin/bash
#   Copyright 2025 NEC Corporation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

echo "START $(basename "$0")"

SHELL_DIR=$(realpath "$(dirname "$0")")
REPO_ROOT_DIR=$(realpath "${SHELL_DIR}/..")

# ディレクトリ作成・パーミッション設定
mkdir -p "${REPO_ROOT_DIR}/.private"
chmod 777 "${REPO_ROOT_DIR}/.private"

mkdir -p "${REPO_ROOT_DIR}/.vscode_extensions/vscode-server/extensions"
chmod 777 "${REPO_ROOT_DIR}/.vscode_extensions/vscode-server/extensions"

mkdir -p "${REPO_ROOT_DIR}/.vscode_extensions/vscode-server-insiders/extensions"
chmod 777 "${REPO_ROOT_DIR}/.vscode_extensions/vscode-server-insiders/extensions"

mkdir -p "${REPO_ROOT_DIR}/.volumes/storage"
chmod 777 "${REPO_ROOT_DIR}/.volumes/storage"

mkdir -p "${REPO_ROOT_DIR}/.volumes/exastro/log"
chmod 777 "${REPO_ROOT_DIR}/.volumes/exastro/log"

mkdir -p "${REPO_ROOT_DIR}/.volumes/exastro/ssl"
chmod 777 "${REPO_ROOT_DIR}/.volumes/exastro/ssl"

mkdir -p ~/.aws
mkdir -p ~/.claude

# devcontainerが使うコンテナランタイムを決定する
# 既定はDOoD(ホストのdockerd)。podmanに切り替える場合は${REPO_ROOT_DIR}/docker-compose/.envのDEVCONTAINER_RUNTIME=podmanを指定する
ENV_FILE="${REPO_ROOT_DIR}/docker-compose/.env"
CONTAINER_RUNTIME=$(grep -E '^DEVCONTAINER_RUNTIME=' "$ENV_FILE" 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '"'"'"'\r ')
CONTAINER_RUNTIME=${CONTAINER_RUNTIME:-docker}
if [ "$CONTAINER_RUNTIME" = "podman" ]; then
    # ホストのrootless podmanのソケット。AEAのコンテナユーザー(exastro)はuid 1000なので所有者がそのまま一致する
    CONTAINER_RUNTIME_SOCK_SRC=${CONTAINER_RUNTIME_SOCK_SRC:-/run/user/$(id -u)/podman/podman.sock}
    CONTAINER_RUNTIME_SOCK_DST=/run/podman/podman.sock
    CONTAINER_RUNTIME_GID=$(id -g)
else
    CONTAINER_RUNTIME_SOCK_SRC=/var/run/docker.sock
    CONTAINER_RUNTIME_SOCK_DST=/var/run/docker.sock
    CONTAINER_RUNTIME_GID=$(grep docker /etc/group | cut -d: -f3)
fi
if [ ! -S "$CONTAINER_RUNTIME_SOCK_SRC" ]; then
    echo "Error: container runtime socket not found: $CONTAINER_RUNTIME_SOCK_SRC (DEVCONTAINER_RUNTIME=$CONTAINER_RUNTIME)"
    exit 1
fi

# コンテナランタイムの情報を.envに設定する(既存の行は置換、なければ追記)
set_env_value() {
    local key="$1" value="$2"
    if grep -qE "^${key}=" "$ENV_FILE"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    else
        echo "${key}=${value}" >> "$ENV_FILE"
    fi
}
set_env_value DEVCONTAINER_RUNTIME_GID "$CONTAINER_RUNTIME_GID"
set_env_value DEVCONTAINER_RUNTIME_SOCK_SRC "$CONTAINER_RUNTIME_SOCK_SRC"
set_env_value DEVCONTAINER_RUNTIME_SOCK_DST "$CONTAINER_RUNTIME_SOCK_DST"

set_env_value AG_ANSIBLE_HOST_STORAGEPATH "${REPO_ROOT_DIR}/.volumes/storage"

which aws && {
    echo "** Check AWS session **"
    export AWS_CA_BUNDLE=/etc/pki/tls/certs/ca-bundle.crt
    aws sts get-caller-identity
}

"${REPO_ROOT_DIR}/vscode/build.sh"

echo "FINISH $(basename "$0")"
