#!/bin/bash
#   Copyright 2026 NEC Corporation
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

# .envがある場合は読込み
if [ -e "${SHELL_DIR}/.env" ]; then
    source "${SHELL_DIR}/.env"
fi

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


#
# 各backyardコンテナのentrypoint.shとその子プロセスをkillする
#

echo "** ita-by-ansible-execute 停止"
sudo ${DOCKER_COMMAND} exec -it \
   ${COMPOSE_PROJECT_NAME}-ita-by-ansible-execute-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-ansible-legacy-role-vars-listup 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-ansible-legacy-role-vars-listup-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-ansible-legacy-vars-listup 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-ansible-legacy-vars-listup-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-ansible-pioneer-vars-listup 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-ansible-pioneer-vars-listup-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-ansible-towermaster-sync 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-ansible-towermaster-sync-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-cicd-for-iac 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-cicd-for-iac-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-collector 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-collector-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-conductor-regularly 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-conductor-regularly-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-conductor-synchronize 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-conductor-synchronize-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-excel-export-import 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-excel-export-import-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-hostgroup-split 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-hostgroup-split-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-menu-create 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-menu-create-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-menu-export-import 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-menu-export-import-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-oase-conclusion 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-oase-conclusion-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-terraform-cli-execute 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-terraform-cli-execute-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-terraform-cli-vars-listup 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-terraform-cli-vars-listup-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-terraform-cloud-ep-execute 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-terraform-cloud-ep-execute-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1

echo "** ita-by-terraform-cloud-ep-vars-listup 停止"
sudo ${DOCKER_COMMAND} exec -it \
    ${COMPOSE_PROJECT_NAME}-ita-by-terraform-cloud-ep-vars-listup-1 \
    bash -c 'pid=$(ps -ef | awk "/\/[e]xastro\/backyard\/entrypoint\.sh/{print \$2}"); [ -n "$pid" ] && kill $(pgrep -P "$pid") "$pid"'

sleep 1
