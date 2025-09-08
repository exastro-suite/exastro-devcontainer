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
DOCKER_COMMAND=$(which docker)

# devcontainerのメインコンテナ起動時以外は処理を中断する
if [ -z "${DEVCONTAINER_MAIN_SERVICE}" ]; then
    # 環境変数未指定時のデフォルトの起動devcontainerを設定
    # --------------------------------------------------------------------------------------
    # なお、環境変数未指定時のデフォルトの起動devcontainerを修正する際は以下の内容と
    # .devcontainer.jsonの.nameおよび.serviceに記載しているコンテナ名も同じ値に修正すること
    # --------------------------------------------------------------------------------------
    DEVCONTAINER_MAIN_SERVICE="ita-api-organization"
fi

echo "DEVCONTAINER_MAIN_SERVICE = ${DEVCONTAINER_MAIN_SERVICE}"
echo "CONTAINER_NAME = ${CONTAINER_NAME}"

if [ "${DEVCONTAINER_MAIN_SERVICE}" != "${CONTAINER_NAME}" -o -z "${CONTAINER_NAME}" ]; then
    echo "※ サブコンテナのため、API serviceの起動はこのWindowでは行いません"
    echo "※ 以下でエラー表示に関しては想定通りなので、ターミナルは閉じて頂いて構いません"
    exit 9
fi

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

# ita-migrationが完了するまで待つ
while true; do
    if [ $(sudo ${DOCKER_COMMAND} ps -q -f "name=${COMPOSE_PROJECT_NAME}-ita-migration-1" | wc -l) -ne 1 ]; then
        break;
    fi
    if [ $(sudo ${DOCKER_COMMAND} "inspect ${COMPOSE_PROJECT_NAME}-ita-migration-1" | jq -r '.[0].State.Status') == 'exited' ]; then
        break;
    fi

    echo "Wait until ${COMPOSE_PROJECT_NAME}-ita-migration-1 is exited ...";
    sleep 5;
done;

echo "FINISH $(basename $0)"

exit 0
