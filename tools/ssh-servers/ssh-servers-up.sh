#!/bin/bash

BASEDIR=$(dirname $0)

. ${BASEDIR}/.env

cd ${BASEDIR}
echo ${DOCKER_COMPOSE_COMMAND}

${DOCKER_COMPOSE_COMMAND} down
${DOCKER_COMPOSE_COMMAND} up -d
