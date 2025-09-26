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

echo "START $(basename $0)"

SHELL_DIR=$(realpath $(dirname $0))
REPO_ROOT_DIR=$(realpath ${SHELL_DIR}/..)

DOCKER_COMMAND=$(which docker)

# 初期化時に停止するコンテナ
STOP_CONTAINERS=(keycloak platform-db platform-db-mysql ita-mariadb ita-mysql ita-mongodb)

# .envファイル読み込み
ENV_FILE=${REPO_ROOT_DIR}/docker-compose/.env
if [ -e "${ENV_FILE}" ]; then
    echo "LOAD .env"
    grep '^COMPOSE_PROJECT_NAME=' "${ENV_FILE}" > /tmp/${BASENAME}.env.$$
    source /tmp/${BASENAME}.env.$$
    rm /tmp/${BASENAME}.env.$$
fi
if [ -z "${COMPOSE_PROJECT_NAME}" ]; then
    echo "COMPOSE_PROJECT_NAME NOT DEFINED"
    COMPOSE_PROJECT_NAME=docker-compose
fi

# コンテナの停止
STOP_CONTAINERS=()
for RESTART_CONTAINER in ${RESTART_CONTAINERS[@]}
do
    COMPOSE_DOCKER_NAME=${COMPOSE_PROJECT_NAME}-${RESTART_CONTAINER}-1
    if [ "$(sudo ${DOCKER_COMMAND} ps -f name=${COMPOSE_DOCKER_NAME} -q | wc -l)" -eq 1 ]; then
        echo "STOP CONTAINER ${RESTART_CONTAINER}"
        STOP_CONTAINERS+=("${RESTART_CONTAINER}")
        sudo ${DOCKER_COMMAND} stop "${COMPOSE_DOCKER_NAME}"
    fi
done

# ファイルクリア
echo "CLEAN VOLUMES"
sudo find "${REPO_ROOT_DIR}/.volumes" -type f -delete

if [ -d "${REPO_ROOT_DIR}/.volumes/ita-mariadb/data" ]; then
    sudo find "${REPO_ROOT_DIR}/.volumes/ita-mariadb/data" -mindepth 1 -delete
fi
if [ -d "${REPO_ROOT_DIR}/.volumes/ita-mysql/data" ]; then
    sudo find "${REPO_ROOT_DIR}/.volumes/ita-mysql/data" -mindepth 1 -delete
fi
if [ -d "${REPO_ROOT_DIR}/.volumes/ita-mongodb/data" ]; then
    sudo find "${REPO_ROOT_DIR}/.volumes/ita-mongodb/data" -mindepth 1 -delete
fi
if [ -d "${REPO_ROOT_DIR}/.volumes/platform-db/data" ]; then
    sudo find "${REPO_ROOT_DIR}/.volumes/platform-db/data" -mindepth 1 -delete
fi
if [ -d "${REPO_ROOT_DIR}/.volumes/platform-db-mysql/data" ]; then
    sudo find "${REPO_ROOT_DIR}/.volumes/platform-db-mysql/data" -mindepth 1 -delete
fi
if [ -d "${REPO_ROOT_DIR}/.volumes/storage" ]; then
    sudo find "${REPO_ROOT_DIR}/.volumes/storage" -mindepth 1 -delete
fi

# コンテナを停止（削除します）
sudo docker rm -f $(sudo docker ps -a -q --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}")
