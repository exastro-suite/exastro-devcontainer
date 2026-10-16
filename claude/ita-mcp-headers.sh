#!/bin/bash
# ITA MCP サーバー(ita-mcp)用の Authorization ヘッダーを JSON で出力する
# Claude Code の headersHelper から接続のたびに呼ばれる(トークンの有効期限切れ対策)
#
# 認証情報(ITA_MCP_USER / ITA_MCP_PASS)は、環境変数が設定済みならそれを優先し、
# 未設定のものだけを/workspace/exastro-devcontainer/docker-compose/.env(gitignore済み)から補う
# 組織IDは.mcp.jsonのURL(環境変数CLAUDE_CODE_MCP_SERVER_URL)から取り出す。取れなければITA_MCP_ORG、それも無ければorg1

ENV_FILE=/workspace/exastro-devcontainer/docker-compose/.env
if [ -r "$ENV_FILE" ]; then
    # .envをsourceするとシェルとして実行されるため、KEY=VALUEとして読むだけにする
    # (最終行に改行が無くても読めるように|| [ -n "$key" ]を付ける)
    while IFS='=' read -r key value || [ -n "$key" ]; do
        case "$key" in
            ITA_MCP_USER|ITA_MCP_PASS) ;;
            *) continue ;;
        esac
        # 行末のCRと、値全体を囲む引用符を取り除く
        value=${value%$'\r'}
        case "$value" in
            \"*\") value=${value#\"}; value=${value%\"} ;;
            \'*\') value=${value#\'}; value=${value%\'} ;;
        esac
        case "$key" in
            ITA_MCP_USER) : "${ITA_MCP_USER:=$value}" ;;
            ITA_MCP_PASS) : "${ITA_MCP_PASS:=$value}" ;;
        esac
    done < "$ENV_FILE"
fi

ORG=$(printf '%s' "$CLAUDE_CODE_MCP_SERVER_URL" | sed -n 's|.*/api/\([^/]*\)/workspaces/.*|\1|p')
ORG=${ORG:-${ITA_MCP_ORG:-org1}}
AUTH_BASE=http://platform-auth:8000

if [ -z "$ITA_MCP_USER" ] || [ -z "$ITA_MCP_PASS" ]; then
    echo "ita-mcp-headers: ITA_MCP_USER / ITA_MCP_PASS is not set (see exastro-devcontainer/docker-compose/.env)" >&2
    exit 1
fi

# scopeにoffline_accessを含めるとplatform-api経由で1年有効のオフラインセッションが毎回作られるため、openidのみにする
# (scopeを省略するとplatform-auth側でエラーになるので省略はしない)
TOKEN=$(curl -s -m 10 --noproxy '*' -X POST "$AUTH_BASE/auth/realms/$ORG/protocol/openid-connect/token" \
    -d "client_id=_${ORG}-api" \
    -d grant_type=password \
    -d "scope=openid" \
    --data-urlencode "username=$ITA_MCP_USER" \
    --data-urlencode "password=$ITA_MCP_PASS" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])' 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "ita-mcp-headers: failed to get access token from platform-auth" >&2
    exit 1
fi

printf '{"Authorization": "Bearer %s"}\n' "$TOKEN"
