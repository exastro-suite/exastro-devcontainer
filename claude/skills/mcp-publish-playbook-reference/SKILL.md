---
name: mcp-publish-playbook-reference
description: ExastroのPlaybook CollectionのRAG用ドキュメントファイルを作成し、RAGに登録する
---

# Publish Playbook Reference

Exastro IT AutomationのAnsible Legacy Playbook素材集を取得し、RAG登録用のファイルを作成し、RAGに登録する

## 手順

### STEP 1: 接続先Exastroのユーザーを確認する。
ユーザーに接続先Exastroのユーザーを質問する。
    Playbook Collectionを読み込む接続先Exastroのユーザーを指定してください。
    例： `admin`

### STEP 2: 接続先Exastroのパスワードを確認する。
ユーザーに接続先Exastroのパスワードを質問する。
    Playbook Collectionを読み込む接続先Exastroのパスワードを指定してください。
    例： `password`

### STEP 3: AnsibleLegacyPlaybookのダウンロードURLを確認する。
ユーザーにAnsibleLegacyPlaybookのダウンロードURLを質問する。
    Ansible Legacy PlaybookのダウンロードURLを指定してください。
    例： `http://platform-auth:8000/api/org1/workspaces/ws1/ita/menu/playbook_files/filter/?file=yes`

### STEP 4: ユーザーに作成対象のAnsibleLegacyPlaybookの項番(item_no)を質問する。
ユーザーに作成対象のAnsibleLegacyPlaybookの項番(item_no)を質問する。"*"が指定された時は全件を対象とし、カンマ区切りで複数指定も可とする。
    markdownファイルの格納先を指定してください。("*"全件、カンマ区切りで複数指定可)
    例： `*` / `80,160`

### STEP 5: curlコマンドでAnsible Legacy Playbookの内容を取得する。
Ansible Legacy PlaybookのダウンロードURLからcurlコマンドでAnsible Legacy Playbookの内容を取得する。
- ベーシック認証で接続先Exastroのユーザー、パスワードを指定
- メソッドは`POST`を指定
- リクエストBODYは`{discard: {NORMAL: "0"}}`を指定
- `content-type`は`application/json`
- curlは`-s`オプションを付けて実行する

### STEP 6: Ansible Legacy Playbookの内容からmarkdownファイルを作成する。
- `STEP 5`で取得したAnsible Legacy Playbookの内容から、`STEP 4`で指定したitem_noを対象にmarkdownファイルを作成する
- markdownファイルの作成先は`exastro-it-automation-dev/ita_root/ita_api_mcp_server/documents/en/playbooks-reference`配下とする
- 作成するmarkdownファイルの内容については`markdownファイルの作成方法`記述のルールに従って作成する

### STEP 7: markdownファイルの内容確認
- 変換後のmarkdownファイル全てが`markdownファイルの作成方法`に沿っているか確認し、沿っていない場合はmarkdownファイルを修正する
- **重要**: PlaybookセクションのPlaybookとOverview、Descriptionの内容がマッチしているか再確認する（あってないことが往々にしてあるため）

### STEP 8: 作成したファイルをqdrantに登録する
- 作成対象のitem_noが`*`の場合は次のシェルを実行する
    ```
    sudo docker exec -it exastro-ita-api-mcp-server-1 bash /exastro/documents/tools/import_all_documents.sh -y
    ```

- 作成対象のitem_noが個別指定の場合は次のシェルを実行する（複数ファイルの時はパラメータに列挙して呼び出すこと）
    ```
    sudo docker exec -it exastro-ita-api-mcp-server-1 bash /exastro/documents/tools/import_documents.sh {作成したファイルのパス}
    ```

## markdownファイルの作成方法
- `.data`のリスト１件毎に`itemno`(固定) + `.item_no` + `-`(固定) + `.playbook_file` + `.md`(固定) の名前でmarkdownファイルを作成する
- playbookは`.file.playbook_file`をbase64デコードして取り出す

- 処理概要:
    - 取り出したplaybookの処理を解析して200文字以内で処理を要約するした内容を出力する
    - **重要**: API取り出した`.parameter.description_en`や`.parameter.description_ja`の内容は参照しないで、playbookの処理内容を解析して出力すること
- 説明: 
    - `.parameter.description_en`が空以外の時、`.parameter.description_en`を出力する
    - `.parameter.description_en`が空の時、playbookの処理内容を解析して`{{ 変数名 }}`で記載しているパラメータの説明を出力する。※変数名の前後にスペースが入っているもののみ対象とすること
- 追加説明
    - `exastro-it-automation-dev/ita_root/ita_api_mcp_server/documents/ja/playbooks-reference-add`配下に作成対象のmarkdownファイルと同名のファイルが存在した場合、その内容を出力する

- 検索用キーワード
    - このplaybookの処理を検索する際に使われるかもしれないと推測される検索ワードで、処理概要や説明に出てきてないキーワードがあれば5件以内で出力する
    - キーワードの項目として`with_together`、`with_items`などのAnsible Playbookの命令文などは出力しないこと

- markdownの形式は以下のとおりとする
    ```markdown
    # Ansible Legacy Default Playbook - playbookファイル名
    `This playbook describes the playbooks initially registered in Exastro's playbook_list.`の固定文言を入れる
    ## Exastro Registration Info
    - **item_no**: `.parameter.item_no`の値
    - **playbook_name**: `.parameter.playbook_name`の値
    - **playbook_file**: `.parameter.playbook_file`の値
    ## Overview
    処理概要を英語で記載
    ## Description
    説明を英語で記載

    追加説明を英語で記載

    ## Keyword
    検索用キーワードを英語で列挙
    ## Playbook
    playbookをcode-blockで出力
    ```

