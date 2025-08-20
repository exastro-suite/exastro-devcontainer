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

${REPO_ROOT_DIR}/vscode/build.sh

echo "FINISH $(basename $0)"
