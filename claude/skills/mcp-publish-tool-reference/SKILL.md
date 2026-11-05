---
name: mcp-publish-tool-reference
description: RAG用のtool referenceのmarkdownファイル(日本語版)からRAG用のmarkdownファイル(英語版)を作成しRAGに登録します
---

# Publish Tool reference

RAG用のtool-referenceのmarkdownファイル(日本語版)からRAG用のmarkdownファイル(英語版)を作成し、RAGに登録します

## 手順

### STEP 1: ユーザーに作成対象のファイル名を質問する。
ユーザーに作成対象のファイル名を質問する。"*"が指定された時は全件を対象とし、カンマ区切りで複数指定も可とする。
    作成対象のファイル名を指定してください。("*"全件、カンマ区切りで複数指定可)
    例： `*` / `aaa.md,bbb.md`

### STEP 2: RAG用のtool referenceのmarkdownファイル(日本語版)を翻訳してRAG用のmarkdownファイル(英語版)を作成する
- `exastro-it-automation-dev/ita_root/ita_api_mcp_server/documents/ja/tool-reference`配下の日本語のmarkdownファイルを読み込み、`exastro-it-automation-dev/ita_root/ita_api_mcp_server/documents/en/tool-reference`配下に英訳してファイルを作成します
- ファイル名は元のファイルと同じ名前とする

### STEP 3: 英語翻訳したファイルをqdrantに登録する
- 登録対象のファイルが`*`の場合は次のシェルを実行する
    ```
    sudo docker exec -it exastro-ita-api-mcp-server-1 bash /exastro/documents/tools/import_all_documents.sh -y
    ```

- 登録対象のファイルが個別指定の場合は次のシェルを実行する（複数ファイルの時はパラメータに列挙して呼び出すこと）
    ```
    sudo docker exec -it exastro-ita-api-mcp-server-1 bash /exastro/documents/tools/import_document.sh {英訳したファイルのパス}
    ```
