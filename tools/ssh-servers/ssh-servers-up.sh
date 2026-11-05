#!/bin/bash

BASEDIR=$(dirname $0)

. ${BASEDIR}/.env

cd ${BASEDIR}
echo ${DOCKER_COMPOSE_COMMAND}

CERT_FILE=${HOST_CERTIFICATE_FILE:-/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem}

${DOCKER_COMPOSE_COMMAND} down

BUILD_LOG=$(mktemp)
${DOCKER_COMPOSE_COMMAND} build 2>&1 | tee "${BUILD_LOG}"
BUILD_STATUS=${PIPESTATUS[0]}

if [ ${BUILD_STATUS} -ne 0 ] && grep -q "additional privileges requested" "${BUILD_LOG}"; then
    # 新しいdocker composeは内部でbuildx bakeを使うが --allow を公開していないため、
    # bake定義を直接 buildx bake に渡し、ホスト証明書ファイルの読み取りを許可する
    echo "BuildKitの追加権限が必要なため、docker buildx bake --allow で再ビルドします"
    ${DOCKER_COMPOSE_COMMAND} build --print | sudo docker buildx bake -f - --allow=fs.read=${CERT_FILE} --load
fi
rm -f "${BUILD_LOG}"

${DOCKER_COMPOSE_COMMAND} up -d --no-build
