#!/bin/bash

BASEDIR=$(dirname $0)

. ${BASEDIR}/.env


DEVICE_LIST_REGISTERS='[
    {
        "parameter": {
            "discard": "0",
            "hw_device_type": "SV",
            "host_name": "ssh-server-1",
            "ip_address": "'"${HOST_SERVER_IP}"'",
            "login_user": "'"${SSH_SERVER_1_USER_NAME}"'",
            "login_password":"'"${SSH_SERVER_1_USER_PASSWORD}"'",
            "authentication_method":"'"${AUTHENTICATION_METHOD}"'",
            "connection_options": "-p '"${SSH_SERVER_1_SSH_PORT}"'",
            "connection_type": "machine",
            "remarks": ""
        },
        "type": "Register"
    },
    {
        "parameter": {
            "discard": "0",
            "hw_device_type": "SV",
            "host_name": "ssh-server-2",
            "ip_address": "'"${HOST_SERVER_IP}"'",
            "login_user": "'"${SSH_SERVER_2_USER_NAME}"'",
            "login_password":"'"${SSH_SERVER_2_USER_PASSWORD}"'",
            "authentication_method":"'"${AUTHENTICATION_METHOD}"'",
            "connection_options": "-p '"${SSH_SERVER_2_SSH_PORT}"'",
            "connection_type": "machine",
            "remarks": ""
        },
        "type": "Register"
    },
    {
        "parameter": {
            "discard": "0",
            "hw_device_type": "SV",
            "host_name": "ssh-server-3",
            "ip_address": "'"${HOST_SERVER_IP}"'",
            "login_user": "'"${SSH_SERVER_3_USER_NAME}"'",
            "login_password":"'"${SSH_SERVER_3_USER_PASSWORD}"'",
            "authentication_method":"'"${AUTHENTICATION_METHOD}"'",
            "connection_options": "-p '"${SSH_SERVER_3_SSH_PORT}"'",
            "connection_type": "machine",
            "remarks": ""
        },
        "type": "Register"
    }
]'

curl -s -X POST \
    -u "$EXASTRO_USER_NAME:$EXASTRO_USER_PASSWORD" \
    -H "Content-Type: application/json" \
    -d "$DEVICE_LIST_REGISTERS" \
    "$EXASTRO_BASE_URL/api/$EXASTRO_ORG_ID/workspaces/$EXASTRO_WS_ID/ita/menu/device_list/maintenance/all/" | jq
