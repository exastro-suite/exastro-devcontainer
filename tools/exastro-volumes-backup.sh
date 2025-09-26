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

# バックアップ時に停止するコンテナ
RESTART_CONTAINERS=(keycloak platform-db platform-db-mysql ita-mariadb ita-mysql ita-mongodb)

# ファイル名決定
BACKUP_PATH="${SHELL_DIR}/.backup"
if [ $# -eq 0 ]; then
    BACKUP_FILE="${BACKUP_PATH}/exastro_volumes.$(date '+%Y%m%d-%H%M').tgz"
elif [ $# -eq 1 ]; then
    BACKUP_FILE="${BACKUP_PATH}/exastro_volumes.$(date '+%Y%m%d-%H%M')-${1}.tgz"
else
    echo "Usage: $(basename $0) [backup filename part]"
    exit 1
fi
echo "BACKUP_FILE: ${BACKUP_FILE}"


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

# backup先ディレクトリ作成
mkdir -p "${BACKUP_PATH}"

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
    while [ "$(sudo ${DOCKER_COMMAND} ps -f name=${COMPOSE_DOCKER_NAME} -q | wc -l)" -eq 1 ]; do
        sleep ;1
        echo "STOPPING CONTAINER ${RESTART_CONTAINER}"
    done;
    echo "STOPPED CONTAINER ${RESTART_CONTAINER}"
done
sleep 3

# バックアップ
echo "START BACKUP volumes"
sudo tar cfz "${BACKUP_FILE}" -C "${REPO_ROOT_DIR}" ".volumes"

# コンテナの再開
for RESTART_CONTAINER in ${STOP_CONTAINERS[@]}
do
    COMPOSE_DOCKER_NAME=${COMPOSE_PROJECT_NAME}-${RESTART_CONTAINER}-1
    echo "RESTART CONTAINER ${RESTART_CONTAINER}"
    sudo ${DOCKER_COMMAND} start "${COMPOSE_DOCKER_NAME}"
done

exit 0
