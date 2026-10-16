# Copyright 2024 NEC Corporation#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import json
import mimetypes
import os
import pathlib
import subprocess
import time
import traceback
from typing import Any, cast

from flask import g

from ..agent.libs.exastro_api import Exastro_API
from ..common_libs.ag.util import app_exception, exception
from ..common_libs.ansible_driver.classes.AnscConstClass import AnscConst
from ..common_libs.common.exception import AppException
from ..common_libs.common.util import (
    arrange_stacktrace_format,
    file_read_retry,
    retry_makedirs,
)
from .libs.util import (
    arcive_tar_data,
    clear_execution_dir,
    clear_execution_tmpdir,
    create_execution_parameters_file,
    create_execution_restart_status_file,
    create_execution_status_file,
    delete_status_file,
    get_execution_parameters_file,
    get_execution_status_file_path,
    get_log_file_path,
    log_merge,
    post_agent_version,
    post_notification_execution,
    post_unexecuted_instance,
    post_update_execution_status,
    post_upload_execution_files,
)

# バージョン通知の連続失敗回数。この回数以上連続して失敗したら error に昇格させる。
# バージョン通知が通らない間は未実行作業を一切取得しない（作業実行が止まる）ため、
# INFO に埋もれて気付けない状態を避ける。
VERSION_NOTIFICATION_ERROR_THRESHOLD = 3

# バージョン通知の連続失敗回数（プロセス内で保持する）
_version_notification_failure_count = 0

# 子プロの起動モジュール。
# 死活監視はps出力との突き合わせで行うため、起動側と監視側で文字列が食い違うと
# 「起動直後の子プロを停止扱いにして作業を異常終了させる」という致命的な誤判定になる。
# 食い違いを防ぐため定数として一元管理する。
CHILD_PROCESS_MODULE = "ansible-execution-agent.entrypoint_child"

# 起動した子プロのPopenハンドル {execution_no: Popen}
# poll()で終了検知とゾンビ回収を兼ねる。親プロセスがwait()しない限り終了した子プロは
# <defunct>のまま残り続け、PID 1のtiniでも（親が生きているため）回収されない。
_child_processes = {}


def agent_main(organization_id, workspace_id, loop_count, interval):
    global _version_notification_failure_count

    # 環境変数の取得
    base_url = os.environ["EXASTRO_URL"]
    refresh_token = os.environ["EXASTRO_REFRESH_TOKEN"]

    # 作業実行可能ステータス
    #   1: Not compatible (old)→古い: 作業実行不可
    #   2: Compatible (newest)→最新:  作業実行可
    #   3: Compatible→最新ではない:   作業実行可
    execute_status_list = ["2", "3"]

    # ITAのAPI呼び出しモジュール
    exastro_api = Exastro_API(base_url=base_url, refresh_token=refresh_token)
    exastro_api.get_access_token(organization_id, refresh_token)

    main_logic_execute = False
    version_diff = None
    # バージョン通知API実行
    g.applogger.info(g.appmsg.get_log_message("MSG-10996", [workspace_id]))
    status_code, response = cast(
        tuple[int, dict], post_agent_version(organization_id, workspace_id, exastro_api)
    )
    if status_code != 200:
        _version_notification_failure_count += 1
        failure_message = g.appmsg.get_log_message(
            "MSG-10997", [workspace_id, status_code, response]
        )
        if _version_notification_failure_count >= VERSION_NOTIFICATION_ERROR_THRESHOLD:
            # 連続失敗が続いている間は作業実行が完全に止まるため、error で通知する
            g.applogger.error(
                f"{failure_message} Version notification has failed"
                f" {_version_notification_failure_count} times in a row."
                " No execution will be started until it succeeds."
            )
        else:
            g.applogger.info(failure_message)
    else:
        _version_notification_failure_count = 0
        target_data = response["data"] if isinstance(response["data"], dict) else {}
        version_diff = target_data.get("version_diff")
        # 作業実行可否
        main_logic_execute = bool(
            version_diff and str(version_diff) in execute_status_list
        )
    g.applogger.info(
        f"{'Execute main_logic' if main_logic_execute else 'Skip main_logic'}({main_logic_execute=} {version_diff=})"
    )

    count = 1
    max = int(loop_count)

    while True:
        try:
            if main_logic_execute:
                main_logic(organization_id, workspace_id, exastro_api)
        except AppException as e:
            app_exception(e)
        except Exception as e:  # noqa: BLE001
            # catch - other all error
            exception(e)

        # インターバルを置いて、max数までループする
        time.sleep(interval)
        if count >= max:
            break
        else:
            count = count + 1


def main_logic(organization_id, workspace_id, exastro_api):

    # 終了済みの子プロを回収する（ゾンビ対策）
    reap_child_processes()

    # 起動した未実行インスタンス
    start_up_list = []

    # 未実行作業取得数
    execution_limit = None

    # 同時実行数の上限値取得
    _execution_limit = getenv_int("EXECUTION_LIMIT", 1)

    # 未実行作業取得の上限値取得
    _movement_limit = getenv_int("MOVEMENT_LIMIT", 1)

    # 実行中のプロセス数をカウントする
    ps_exec_count, ps_error_count, working_ps_list, error_ps_list = (
        get_working_child_process(organization_id, workspace_id)
    )

    g.applogger.debug("ps_exec_count:" + str(ps_exec_count))
    g.applogger.debug("ps_error_count:" + str(ps_error_count))
    g.applogger.debug("working_ps_list: " + str(working_ps_list))
    g.applogger.debug("error_ps_list: " + str(error_ps_list))
    # 実行可能な作業数: 同時実行数の上限値 - 実行中のプロセス数
    allow_execution_limit = _execution_limit - ps_exec_count
    g.applogger.info(
        f"Process: {allow_execution_limit=} ({ps_exec_count}/{_execution_limit}) API: {_movement_limit=}"
    )

    # 作業実行可能な場合
    if allow_execution_limit > 0:
        # 未実行作業取得数を設定
        execution_limit = min(allow_execution_limit, _movement_limit)
        body = {}
        str_een = os.getenv("EXECUTION_ENVIRONMENT_NAMES", None)
        # パラメータの追加
        body.setdefault(
            "execution_environment_names", str_een.split(",")
        ) if str_een else None
        body.setdefault("execution_limit", execution_limit) if execution_limit else None
        # 未実行インスタンス取得
        g.applogger.info(g.appmsg.get_log_message("MSG-10988", [workspace_id]))
        g.applogger.debug(
            f"post_unexecuted_instance: {organization_id=} {workspace_id=} {body=}"
        )
        status_code, response = cast(
            tuple[int, dict],
            post_unexecuted_instance(
                organization_id, workspace_id, exastro_api, body=body
            ),
        )
        if status_code == 200:
            target_executions = (
                response["data"] if isinstance(response["data"], dict) else {}
            )
            for execution_no, value in target_executions.items():
                g.applogger.debug(
                    f"{execution_no=}: \n {json.dumps(value, indent=4) if value else {}}"
                )
                # 子プロ起動時の引数対応: None -> ""
                runtime_data_del = value["anstwr_del_runtime_data"] or "0"

                # 子プロ起動
                g.applogger.info(
                    g.appmsg.get_log_message("MSG-11006", [workspace_id, execution_no])
                )

                command = [
                    "python",
                    "-m",
                    CHILD_PROCESS_MODULE,
                    organization_id,
                    workspace_id,
                    execution_no,
                    value["driver_id"],
                    value["build_type"],
                    runtime_data_del,
                    "start",
                ]

                _child_processes[execution_no] = subprocess.Popen(command)

                # 子プロ起動状態ファイル生成
                create_execution_status_file(
                    organization_id, workspace_id, value["driver_id"], execution_no
                )

                # 子プロ起動パラメータ退避
                create_execution_parameters_file(
                    organization_id,
                    workspace_id,
                    value["driver_id"],
                    execution_no,
                    value["build_type"],
                    runtime_data_del,
                )

                # 子プロ再起動状態ファイル生成
                create_execution_restart_status_file(
                    organization_id, workspace_id, value["driver_id"], execution_no
                )

                # 起動した子プロの作業番号を退避
                # なんらかの理由で子プロの起動に失敗した場合の。子プロ死活監視の為
                start_up_list.append(execution_no)

        else:
            g.applogger.info(
                g.appmsg.get_log_message(
                    "MSG-10989", [workspace_id, status_code, response]
                )
            )
    else:
        # 同時実行数制御で未実行作業取得をSKIP
        g.applogger.info(
            f"Skipped acquiring unexecuted tasks due to the concurrent task limit. Processes in progress: {ps_exec_count}"
        )

    g.applogger.debug("ps_exec_count:" + str(ps_exec_count))
    g.applogger.debug("ps_error_count:" + str(ps_error_count))
    g.applogger.debug("working_ps_list: " + str(working_ps_list))
    g.applogger.debug("error_ps_list: " + str(error_ps_list))

    # 作業中の作業がある場合、作業中通知
    if ps_exec_count != 0:
        g.applogger.info(
            g.appmsg.get_log_message("MSG-10998", [workspace_id, str(working_ps_list)])
        )
        status_code, response = post_notification_execution(
            organization_id, workspace_id, exastro_api, working_ps_list
        )
        if status_code != 200:
            g.applogger.info(
                g.appmsg.get_log_message(
                    "MSG-10999",
                    [workspace_id, str(working_ps_list), status_code, response],
                )
            )

    # 子プロセスが存在しない作業がある場合、作業中通知
    if ps_error_count != 0:
        # 指定リトライ回数以上のステータス更新、ステータスファイルファイルの削除
        update_error_executions(
            organization_id, workspace_id, exastro_api, error_ps_list
        )


def reap_child_processes():
    """終了済みの子プロをwait()して回収する（ゾンビ対策）"""
    for execution_no, proc in list(_child_processes.items()):
        if proc.poll() is not None:
            del _child_processes[execution_no]


def child_process_exist_check(organization_id, workspace_id, execution_no, driver_id):
    """
    実行中の子プロの起動確認

    Returns:
        bool
    """
    # 自身が起動した子プロはPopenハンドルで判定する（ps出力の突き合わせより確実）
    proc = _child_processes.get(execution_no)
    if proc is not None and proc.poll() is None:
        return True

    # ハンドルを持たない子プロ（親プロセス再起動前に起動された子プロ）はps出力で判定する
    # psコマンドがマレに起動プロセスリストを取りこぼすことがあるので3回分を作成
    child_process_1 = child_process_exist_check_ps()
    time.sleep(0.05)
    child_process_2 = child_process_exist_check_ps()
    time.sleep(0.05)
    child_process_3 = child_process_exist_check_ps()

    # 子プロ起動確認
    # 子プロの起動コマンド: python -m {CHILD_PROCESS_MODULE} {organization_id} {workspace_id} {execution_no} {driver_id} ...
    command_args = (
        f"{CHILD_PROCESS_MODULE} {organization_id} {workspace_id} {execution_no}"
    )

    for child_process in (child_process_1, child_process_2, child_process_3):
        for r_child_process in child_process.split("\n"):
            if command_args in r_child_process:
                return True

    return False


def child_process_exist_check_ps():
    """
    実行中の子プロのpsコマンド取得結果

    Returns:
        stdout row
    """
    # ps -efww | grep {CHILD_PROCESS_MODULE}
    # 引数が長い子プロの行が途中で切り詰められないよう、wは2つ指定する
    # psの失敗時は空文字（＝子プロ無し）を返さない。
    # 子プロが動いていても停止扱いになり、作業が異常終了してしまうため例外を起こす
    cp = subprocess.run(["ps", "-efww"], capture_output=True, text=True, check=True)

    return "\n".join(
        line for line in cp.stdout.splitlines() if CHILD_PROCESS_MODULE in line
    )


def get_working_child_process(organization_id: str, workspace_id: str):
    """ステータスファイルから作業一覧取得
    Args:
        organization_id (_type_): organization_id
        workspace_id (_type_): workspace_id

    Returns:
        ps_exec_count: Num
        ps_error_count: Num
        working_ps_list: { driver_id : []}
        error_ps_list: { driver_id : []}
    """
    driver_id_list = [
        "legacy",
        "pioneer",
        "legacy_role",
    ]
    ps_exec_count = 0
    ps_error_count = 0
    working_ps_list = {}
    error_ps_list = {}
    storagepath = pathlib.Path(os.environ.get("STORAGEPATH", "/exastro/storage"))
    status_file_dir_path = (
        storagepath / organization_id / workspace_id / "ag_ansible_execution" / "status"
    )

    # プロセス再起動上限値
    # 子プロ再起動は行わない
    # プロセス再起動上限値は0とする
    child_process_retry_limit = int(os.getenv("CHILD_PROCESS_RETRY_LIMIT", "0"))

    # ドライバ毎の空リスト作成
    for _d in driver_id_list:
        working_ps_list.setdefault(_d, [])
        error_ps_list.setdefault(_d, [])

    for driver_id in driver_id_list:
        for _file in (status_file_dir_path / driver_id).glob("*"):
            if len(_file.name) > 36:
                # ステータスファイル以外もあるのでファイル名が36文字以上はスキップ
                continue

            if _file.is_file():
                continue

            execution_no = _file.name

            # 実行中の子プロの起動確認
            ret = child_process_exist_check(
                organization_id, workspace_id, execution_no, driver_id
            )
            if ret is True:
                # 子プロ実行中
                g.applogger.debug(
                    g.appmsg.get_log_message("MSG-11002", [workspace_id, execution_no])
                )
                working_ps_list[driver_id].append(execution_no)
                ps_exec_count += 1
            else:
                # 子プロが存在しない
                # 再起動判定および再起動（ステータスファイルが読めないなどで再起動自体に失敗した場合は、リトライ回数を保持できない可能性もあるため、リトライは諦める）
                ret = reboot_child_process(
                    organization_id,
                    workspace_id,
                    driver_id,
                    execution_no,
                    child_process_retry_limit,
                )
                if ret is True:
                    working_ps_list[driver_id].append(execution_no)
                    ps_exec_count += 1
                else:
                    g.applogger.debug(
                        g.appmsg.get_log_message(
                            "MSG-11003", [workspace_id, execution_no]
                        )
                    )
                    error_ps_list[driver_id].append(execution_no)
                    ps_error_count += 1

    g.applogger.debug(
        f"working_ps_list: \n {json.dumps(working_ps_list, indent=4) if working_ps_list else {}}"
    )
    g.applogger.debug(
        f"error_ps_list: \n {json.dumps(error_ps_list, indent=4) if error_ps_list else {}}"
    )

    return ps_exec_count, ps_error_count, working_ps_list, error_ps_list


def reboot_child_process(
    organization_id: str,
    workspace_id: str,
    driver_id: str,
    execution_no: str,
    child_process_retry_limit: int,
):
    # ステータスファイルのパスを取得
    status_file_dir_path, status_file_path = get_execution_status_file_path(
        organization_id, workspace_id, driver_id, execution_no
    )

    # ステータスファイルに書き込まれている再起動回数取得
    reboot_cnt_str: str = ""

    @file_read_retry
    def read_reboot_cnt():
        nonlocal reboot_cnt_str

        os.listdir(
            status_file_dir_path.parent
        )  # NFSストレージ対策：属性キャッシュ更新を試みる
        reboot_cnt_str = status_file_path.read_text()
        if len(reboot_cnt_str) == 0:
            reboot_cnt_str = "0"
        return True

    try:
        read_reboot_cnt()
    except Exception:  # noqa: BLE001
        g.applogger.info(f"read_reboot_cnt. file_path={status_file_path}")
        return False

    reboot_cnt = int(reboot_cnt_str)

    # 再起動回数制限内で再起動を行う
    if reboot_cnt < child_process_retry_limit:
        # 子プロ起動パラメータ退避ファイルから起動パラメータ取得
        try:
            build_type, runtime_data_del = get_execution_parameters_file(
                organization_id, workspace_id, driver_id, execution_no
            )
        except Exception:  # noqa: BLE001
            # 不正な子プロ起動パラメータファイルのため、再起動処理を行わない
            g.applogger.info(
                f"invalid execution_parameters_file execution_no={execution_no}"
            )
            return False

        @file_read_retry
        def write_status_file():
            nonlocal reboot_cnt

            # ステータスファイルに再起動回数書き込み
            reboot_cnt = int(reboot_cnt) + 1
            status_file_path.write_text(str(reboot_cnt))
            return True

        try:
            write_status_file()
        except Exception:  # noqa: BLE001
            g.applogger.info(f"write_status_file failed. file_path={status_file_path}")
            return False

        # 子プロ再起動 Restarted child process. (workspace id:{} execution no:{} count:{})
        g.applogger.info(
            g.appmsg.get_log_message(
                "MSG-11005", [workspace_id, execution_no, str(reboot_cnt)]
            )
        )
        command = [
            "python",
            "-m",
            CHILD_PROCESS_MODULE,
            organization_id,
            workspace_id,
            execution_no,
            driver_id,
            build_type,
            runtime_data_del,
            "restart",
        ]
        _child_processes[execution_no] = subprocess.Popen(command)
        return True
    else:
        # Child process restart count has been exceeded. (workspace id:{} execution no:{})
        g.applogger.info(
            g.appmsg.get_log_message("MSG-11004", [workspace_id, execution_no])
        )
        return False


def update_error_executions(organization_id, workspace_id, exastro_api, error_ps_list):
    """エラー対象の作業状態通知送信
        結果ファイル更新＋ステータス更新
    Args:
        organization_id (_type_): organization_id
        workspace_id (_type_): workspace_id
        exastro_api: Exastro_API()
        error_ps_list: : { driver_id : []}
    """

    status_id = AnscConst.FAILURE  # 完了(異常)
    runtime_data_del = 2  # 実行時削除フラグは最初の処理対象の作業実行Noのものを共通利用する（0 or 1 or Noneなので、2は未取得）
    for driver_id, del_execution_list in error_ps_list.items():
        for del_execution in del_execution_list:
            try:
                status_update = True
                # 作業状態通知送信: 異常時

                # ステータスファイル有りで、作業中の実行プロセス停止時、エラーログに追記して通知
                # enomoto /ag_parent_error.logパス確認
                storagepath = pathlib.Path(
                    os.environ.get("STORAGEPATH", "/exastro/storage")
                )
                _base_dir = (
                    storagepath
                    / organization_id
                    / workspace_id
                    / "driver"
                    / "ag_ansible_execution"
                    / driver_id
                    / del_execution
                )
                retry_makedirs(_base_dir / "out")
                # ログファイルのパス取得
                (
                    exec_log_pass,
                    error_log_pass,
                    parent_error_log_pass,
                    child_exec_log_pass,
                    child_error_log_pass,
                    runner_exec_log_pass,
                    runner_error_log_pass,
                ) = get_log_file_path(
                    organization_id, workspace_id, driver_id, del_execution
                )

                @file_read_retry
                def write_parent_error_log(parent_error_log_pass, del_execution):
                    try:
                        with parent_error_log_pass.open("w") as f:
                            # Ansible実行エージェントで作業中の実行プロセスが停止した為、終了します。(Execution no:{})
                            f.write(
                                g.appmsg.get_log_message("MSG-10985", [del_execution])
                            )
                        return True
                    except Exception:
                        g.applogger.info(
                            f"write_parent_error_log failed. file_path={parent_error_log_pass}"
                        )
                        t = traceback.format_exc()
                        g.applogger.info(arrange_stacktrace_format(t))
                        raise

                write_parent_error_log(parent_error_log_pass, del_execution)

                # ansibleのログファイルとアプリのログをマージする
                log_merge(
                    exec_log_pass,
                    error_log_pass,
                    parent_error_log_pass,
                    child_exec_log_pass,
                    child_error_log_pass,
                    runner_exec_log_pass,
                    runner_error_log_pass,
                    driver_id,
                )

                # 各種tar＋ファイルパス取得
                (
                    out_gztar_path,
                    parameters_gztar_path,
                    parameters_file_gztar_path,
                    conductor_gztar_path,
                ) = arcive_tar_data(
                    organization_id,
                    workspace_id,
                    driver_id,
                    del_execution,
                    status_id,
                    mode="parent",
                )

                g.applogger.debug(
                    f"{out_gztar_path=}, {parameters_gztar_path=}, {parameters_file_gztar_path=}, {conductor_gztar_path=}"
                )

                body = {
                    "driver_id": driver_id,
                    "status": status_id,
                }

                form_data: dict[str, Any] = {"json_parameters": json.dumps(body)}

                # form_dataへのtarデータ追加
                if out_gztar_path is not None and out_gztar_path.is_file():
                    form_data["out_tar_data"] = (
                        out_gztar_path.name,
                        out_gztar_path.open("rb"),
                        mimetypes.guess_type(out_gztar_path, False)[0],
                    )
                if (
                    parameters_gztar_path is not None
                    and parameters_gztar_path.is_file()
                ):
                    form_data["parameters_tar_data"] = (
                        parameters_gztar_path.name,
                        parameters_gztar_path.open("rb"),
                        mimetypes.guess_type(parameters_gztar_path, False)[0],
                    )
                if (
                    parameters_file_gztar_path is not None
                    and parameters_file_gztar_path.is_file()
                ):
                    form_data["parameters_file_tar_data"] = (
                        parameters_file_gztar_path.name,
                        parameters_file_gztar_path.open("rb"),
                        mimetypes.guess_type(parameters_file_gztar_path, False)[0],
                    )
                if conductor_gztar_path is not None and conductor_gztar_path.is_file():
                    form_data["conductor_tar_data"] = (
                        conductor_gztar_path.name,
                        conductor_gztar_path.open("rb"),
                        mimetypes.guess_type(conductor_gztar_path, False)[0],
                    )

                # 結果データ更新
                g.applogger.info(
                    g.appmsg.get_log_message("MSG-10994", [workspace_id, del_execution])
                )
                status_code, response = post_upload_execution_files(
                    organization_id,
                    workspace_id,
                    exastro_api,
                    del_execution,
                    body,
                    form_data=form_data,
                )
                if status_code != 200:
                    g.applogger.info(
                        g.appmsg.get_log_message(
                            "MSG-10995",
                            [workspace_id, del_execution, status_code, response],
                        )
                    )
                    status_update = False

                # 作業状態通知
                if status_update:
                    g.applogger.info(
                        g.appmsg.get_log_message(
                            "MSG-10990", [workspace_id, del_execution, status_id]
                        )
                    )
                    status_code, response = post_update_execution_status(
                        organization_id, workspace_id, exastro_api, del_execution, body
                    )
                    if status_code != 200:
                        g.applogger.info(
                            g.appmsg.get_log_message(
                                "MSG-10991",
                                [
                                    workspace_id,
                                    del_execution,
                                    status_id,
                                    status_code,
                                    response,
                                ],
                            )
                        )
                        status_update = False

            finally:
                # 実行時削除フラグを取得しておく
                try:
                    _, runtime_data_del = get_execution_parameters_file(
                        organization_id, workspace_id, driver_id, del_execution
                    )
                except Exception:  # noqa: BLE001
                    # パラメータファイルが読めなかった場合、実行時削除はTrue扱いとする
                    runtime_data_del = 1
                    g.applogger.info(
                        f"read execution_parameters_file failed. execution_no={del_execution}"
                    )
                # ステータスファイルの削除
                delete_status_file(
                    organization_id, workspace_id, driver_id, del_execution
                )
                # /tmpのゴミ掃除
                clear_execution_tmpdir(
                    organization_id, workspace_id, driver_id, del_execution
                )
                # 作業ディレクトリ削除(実行時データ削除フラグは削除対象の最初の作業Noのものを共通利用する)
                clear_execution_dir(
                    organization_id,
                    workspace_id,
                    driver_id,
                    del_execution,
                    runtime_data_del,
                )


def getenv_int(key, default):
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        g.applogger.info(f"The environment variable is not a number. {key=}")
        return default
