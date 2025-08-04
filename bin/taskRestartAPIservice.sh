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

BASENAME=$(basename $0)
SHELL_DIR=$(realpath $(dirname $0))
REPO_ROOT_DIR=$(realpath ${SHELL_DIR}/..)
ENV_FILE=${REPO_ROOT_DIR}/docker-compose/.env

# パラメータ
CONTAINER_SERVICE=$1
API_PORT=$2
HTTPD_STOP=$3
API_START_PYTHON=$4

# .envの内容を取り込む
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

echo "COMPOSE_PROJECT_NAME = ${COMPOSE_PROJECT_NAME}"

CONTAINER_NAME="${COMPOSE_PROJECT_NAME}-${CONTAINER_SERVICE}-1"
echo "CONTAINER_NAME = ${CONTAINER_NAME}"

# コンテナが存在しているか？
if [ $(sudo docker ps -q -f "name=${CONTAINER_NAME}" | wc -l) -eq 0 ]; then
    # コンテナが存在していない場合
    echo "Not Found Container : ${CONTAINER_NAME}"
    exit 0
fi

# HTTPD(Apache)の停止 or 再起動
if [ "${HTTPD_STOP}" == "stop-httpd" ]; then
    echo "Stop Httpd Service"
    sudo docker exec -it ${CONTAINER_NAME} httpd -k stop
else
    echo "Restart Httpd Service"
    sudo docker exec -it ${CONTAINER_NAME} httpd -k graceful
fi
# 指定portのプロセスを終了
if [ "${API_PORT}" != "0" ]; then
    echo "Stop Process Port ${API_PORT}"
    sudo docker exec -it ${CONTAINER_NAME} fuser -k -n tcp ${API_PORT}
fi

echo "Execute API ${API_START_PYTHON}"
echo "-----------------------------------------------------------------"
sudo docker exec -it ${CONTAINER_NAME} python3 ${API_START_PYTHON}

