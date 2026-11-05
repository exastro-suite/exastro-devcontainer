---
name: mcp-tool-create
description: 指定したAPIのMCPサーバーのtoolsのpython関数を作成する。
---

# Create MCP tools function

APIのパス・メソッドを指定してそれを呼び出す、MCPのtoolsのpython関数を作成します。

## 手順

### STEP 1: APIのパスを確認する
ユーザーにAPIのパスを質問する：
    tool化したいAPIのパスを指定してください。
    例: /api/{organization_id}/workspaces/{workspace_id}/ita/menu/{menu}/info/

### STEP 2: APIのメソッドを確認する
ユーザーにAPIのメソッドを質問する：
    tool化したいAPIのメソッドを指定してください。
    例: POST

### STEP 3: OpenAPIに該当のAPIが存在するか確認する
`exastro-it-automation-dev/ita_root/ita_api_mcp_server/documents/ja/openapi/swagger.yaml`に
指定したパス・メソッドのAPIが存在するか確認する

- 存在しない時は、`指定したAPIは存在しません`とユーザーに伝えて終了します
- 存在する時は、次のステップに進みます

### STEP 4: tools関数の作成先のファイルを確認します
ユーザーに作成先のファイル名を質問する：
    toolの格納先のファイル名を指定してください。
    例: platform_user.py

### STEP 5: tools関数の関数名を確認します
ユーザーに関数名を質問する：
    toolの関数名を指定してください。
    例: tool_create_user (tool_動詞_対象)

### STEP 6: APIの実行に必要な権限を調査します
- APIにmenuのパラメータがある場合は基本的には権限不要
- APIにmenuのパラメータが無い場合は`exastro-it-automation-dev/ita_root/ita_api_organization`配下のAPIの実装を確認し、実行に必要なメニューの権限を確認する

### STEP 7: tools関数を作成します
`tools関数コーディング方法`に記載のルールに従ってtools関数を実装する

## tools関数コーディング方法
- `exastro-it-automation-dev/ita_root/ita_api_mcp_server/tools`配下の指定したファイル名の
  ファイルに、指定した関数名でtools関数を実装すること
- `exastro-it-automation-dev/ita_root/ita_api_mcp_server/tools`の他のツールの構造に倣って実装すること
