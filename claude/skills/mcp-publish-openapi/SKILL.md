---
name: mcp-publish-openapi
description: RAG用のopenapiファイル(日本語版)からRAG用のopenapiファイル(英語版)を作成し、RAGに登録します
---

# Publish Openapi

RAG用のopenapiファイル(日本語版)からRAG用のopenapiファイル(英語版)を作成し、RAGに登録します

## 手順

### STEP 1: RAG用のopenapiファイル(日本語版)を翻訳してRAG用のopenapiファイル(英語版)を作成する
- `exastro-it-automation-dev/ita_root/ita_api_mcp_server/documents/ja/openapi`配下のswaggerファイルを読み込み、`exastro-it-automation-dev/ita_root/ita_api_mcp_server/documents/en/openapi`配下に英訳してファイルを作成します
- **重要** 日本語で記載した箇所以外は変更しないこと
- ファイル名は元のファイルと同じ名前とする

### STEP 2: 英語翻訳したファイルをqdrantに登録する
- 次のシェルを実行する
    ```
    sudo docker exec -it exastro-ita-api-mcp-server-1 bash /exastro/documents/tools/import_document.sh {英訳したファイルのパス}
    ```
