---
name: mcp-publish-manual
description: マニュアルの文書からRAG用のmarkdownファイル(日本語・英語)を作成し、RAGに登録します
---

# Publish Manual
マニュアルの文書ファイル(rst)ファイルを読み込み、要約・Markdown化し、RAG登録用のドキュメントを作成し、RAGに登録する

## 手順

### STEP 1: マニュアルのリポジトリのcloneコマンドを確認する
ユーザーにマニュアルのリポジトリのcloneコマンドを質問する：
    マニュアルのリポジトリのcloneコマンドを指定してください
    例: git clone -b current --depth 1 https://github.com/exastro-suite/exastro-it-automation-docs-dev.git exastro-it-automation-docs.$$

### STEP 2: マニュアルのリポジトリをcloneする
- /tmpに移動し、`STEP 1`で指定したマニュアルのリポジトリのcloneコマンドを実行する
- コマンド実行する時はPROXYの設定を引き継ぐこと

### STEP 3: 処理対象のマニュアルのバージョンを確認する
ユーザーにマニュアルのバージョンを確認する：
    RAG用のmarkdownに変換を行いたいバージョンを指定してください。
    例: `2.10`

### STEP 4: マニュアルの文書ファイル(rst)の格納ディレクトリの存在を確認する
`STEP 2`でcloneしたディレクトリ配下に`src/ja/<STEP 3で指定したバージョン>`のディレクトリ（処理対象のディレクトリ）が存在することを確認する

### STEP 5: 処理対象のマニュアルの文書ファイル(rst)を確認する
ユーザーに処理対象のマニュアルの文書ファイル(rst)を質問する：
    マニュアルの文書ファイル(rst)を指定してください。全ての場合は`*`を指定してください。
    例: `manuals/ansible-driver/ansible_common.rst`, `*`

### STEP 6: マニュアルの文書ファイル(rst)から削除されたmarkdownファイルの削除
- `exastro-it-automation-dev/ita_root/ita_api_mcp_server/documents/ja/manual`配下に存在するmarkdownファイルに対応する
  `STEP 4`で確認した処理対象のディレクトリのrstファイルが存在しなmarkdownファイルを削除する
- `exastro-it-automation-dev/ita_root/ita_api_mcp_server/documents/en/manual`配下に存在するmarkdownファイルに対応する
  `STEP 4`で確認した処理対象のディレクトリのrstファイルが存在しなmarkdownファイルを削除する
- また`作成対象外のファイルおよびディレクトリ`に該当するmarkdownファイルが存在する場合も削除する

### STEP 7: rstファイルをmarkdownファイルに変換します
- `markdownの生成方法`に記載のルールに従ってmarkdownを作成します
- markdownの作成対象は`STEP 4`で確認した処理対象のディレクトリ配下の`STEP 5`で処理対象のマニュアルの文書ファイル(rst)とする
  ただし、`作成対象外のファイルおよびディレクトリ`に該当するファイル・ディレクトリは対象外とする
- markdownの作成先は`exastro-it-automation-dev/ita_root/ita_api_mcp_server/documents/ja/manual`とする
- ディレクトリ・ファイルの構成はマニュアルの文書ファイル(rst)の格納ディレクトリと同じとする（拡張子のみrstからmdに変更する）

### STEP 8: 作成したmarkdownをチェックする
- 作成したmarkdownファイルを１つ１つ読み込み、無駄な記載や意味が分からない記載が無いか確認し修正する

### STEP 9: 日本語マニュアルを英訳する
- `exastro-it-automation-dev/ita_root/ita_api_mcp_server/documents/ja/manual`配下に存在するmarkdownファイルを英訳する
- 英訳したファイルは`exastro-it-automation-dev/ita_root/ita_api_mcp_server/documents/en/manual`配下に出力する
- ディレクトリ・ファイルの構成は同じにすること

### STEP 10: 英語翻訳したファイルをqdrantに登録する
- 次のシェルを実行し、英語翻訳したファイルをqdrantに登録する
    ```
    sudo docker exec -it exastro-ita-api-mcp-server-1 bash /exastro/documents/tools/import_all_documents.sh -y
    ```

### STEP 11: cloneしたマニュアルのリポジトリを削除する
`STEP 2`でcloneしたディレクトリを削除します


## markdownの生成方法
- 画面説明や画面操作に関わる記載は不要なのでmarkdownからは削除します
- ファイルの１行目にはレベル１のタイトルで、そのmarkdownファイルの全体の内容に沿ったタイトルを付けてください
- 設定が必要なメニューや設定順序や設定の意味に関する記載はmarkdownに出力する
- 画面操作に関する記載はmarkdownの出力対象外とする
- 表形式や段組みなどの必要以上の空白は削除してファイルサイズを小さくすること
- 元のマニュアルの文書ファイル(rst)の5分の1くらいに全体を要約すること

## 作成対象外のファイルおよびディレクトリ
- 対象外のファイル
    - index.rst
- 対象外のディレクトリ
    - include
    - release_notes
    - terms
    - installation
    - configuration
    - contribute
    - kb
    - learn
    - reference
    - templates
    - kb/availability
    - manuals/organization_management
    - manuals/platform_management
    - manuals/maintenance
