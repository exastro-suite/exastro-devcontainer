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
import shutil
import subprocess
import sys
import tarfile
import time
import traceback
from typing import Any, cast

import yaml
from flask import g
from requests import Response

from ..agent.libs.exastro_api import Exastro_API
from ..common_libs.ag.util import app_exception, exception
from ..common_libs.ansible_driver.classes.AnscConstClass import AnscConst
from ..common_libs.common.exception import AppException
from ..common_libs.common.util import (
    arrange_stacktrace_format,
    file_read_retry,
    retry_makedirs,
    retry_move,
    retry_rmtree,
)
from .libs.util import (
    arcive_tar_data,
    clear_execution_dir,
    clear_execution_tmpdir,
    delete_status_file,
    get_execution_populated_data,
    get_log_file_path,
    log_merge,
    post_update_execution_status,
    post_upload_execution_files,
)


def agent_child_main():
    """
    agent_childのラッパー
    """
    # コマンドラインから引数を受け取る["自身のファイル名", "organization_id", "workspace_id", …, …]
    args = sys.argv
    organization_id = args[1]
    workspace_id = args[2]
    execution_no = args[3]
    driver_id = args[4]
    runtime_data_del = args[6]

    g.applogger.set_tag("EXECUTION_NO", execution_no)

    # MSG-10720 [処理]プロシージャ開始 (作業No.:{})
    g.applogger.debug(g.appmsg.get_log_message("MSG-10720", [execution_no]))

    try:
        agent_child()
    except AppException as e:
        app_exception(e)
        # 異常時の共通処理
        # 結果データ更新+作業状態通知送信
        status = AnscConst.FAILURE
        status_code, _response, error_code, error_arg = post_upload_file_and_status(
            None, organization_id, workspace_id, execution_no, status, driver_id
        )
        if status_code != 200:
            g.applogger.info(g.appmsg.get_log_message(error_code, error_arg))
    except Exception as e:  # noqa: BLE001
        exception(e)
        # 異常時の共通処理
        # 結果データ更新+作業状態通知送信
        status = AnscConst.FAILURE
        status_code, _response, error_code, error_arg = post_upload_file_and_status(
            None, organization_id, workspace_id, execution_no, status, driver_id
        )
        if status_code != 200:
            g.applogger.info(g.appmsg.get_log_message(error_code, error_arg))
    finally:
        # ステータスファイルの削除
        delete_status_file(organization_id, workspace_id, driver_id, execution_no)
        # /tmpのゴミ掃除
        clear_execution_tmpdir(organization_id, workspace_id, driver_id, execution_no)
        # 作業ディレクトリ削除
        clear_execution_dir(
            organization_id, workspace_id, driver_id, execution_no, runtime_data_del
        )
    return 0


def agent_child():
    # コマンドラインから引数を受け取る["自身のファイル名", "organization_id", "workspace_id", …, …]
    args = sys.argv
    organization_id = args[1]
    workspace_id = args[2]
    execution_no = args[3]
    driver_id = args[4]
    build_type = args[5]
    _runtime_data_del = args[6]
    # 再起動の処理は非提供
    start_mode = args[7]

    # in/out親ディレクトリパス
    storagepath = os.environ.get("STORAGEPATH", "/exastro/storage")
    root_dir_path = pathlib.Path(
        storagepath,
        organization_id,
        workspace_id,
        "driver",
        "ag_ansible_execution",
        driver_id,
        execution_no,
    )

    # ログファイルパス
    (
        exec_log_pass,
        error_log_pass,
        parent_error_log_pass,
        child_exec_log_pass,
        child_error_log_pass,
        runner_exec_log_pass,
        runner_error_log_pass,
    ) = get_log_file_path(organization_id, workspace_id, driver_id, execution_no)

    # builder Runnerのshellで使用する環境変数設定
    project_base_path = f"{storagepath}/{organization_id}/{workspace_id}/driver/ag_ansible_execution/{driver_id}/{execution_no}"
    os.environ["PROJECT_BASE_DIR"] = project_base_path

    base_url = os.environ["EXASTRO_URL"]
    refresh_token = os.environ["EXASTRO_REFRESH_TOKEN"]

    # ITAのAPI呼び出しモジュール
    exastro_api = Exastro_API(base_url=base_url, refresh_token=refresh_token)
    exastro_api.get_access_token(organization_id, refresh_token)

    # 投入資材取得
    _chunk_size = 1024 * 1024
    g.applogger.info(
        g.appmsg.get_log_message("MSG-10992", [workspace_id, execution_no])
    )
    query = {"driver_id": driver_id}
    status_code, response = cast(
        tuple[int, Response],
        get_execution_populated_data(
            organization_id, workspace_id, exastro_api, execution_no, query=query
        ),
    )
    if status_code != 200:
        g.applogger.info(
            g.appmsg.get_log_message(
                "MSG-10993", [workspace_id, execution_no, status_code, response]
            )
        )
        raise AppException(
            "MSG-10993",
            [workspace_id, execution_no, status_code, response],
            [workspace_id, execution_no, status_code, response],
        )

    # tarファイル解凍
    dir_path = (
        pathlib.Path("/tmp")
        / organization_id
        / workspace_id
        / "driver"
        / "ansible"
        / driver_id
        / execution_no
        / execution_no
    )
    retry_rmtree(dir_path)
    retry_makedirs(dir_path)
    file_name = dir_path.with_suffix(".tar.gz")
    with file_name.open("wb") as f:
        for chunk in response.iter_content(chunk_size=_chunk_size):
            if chunk:
                f.write(chunk)
                f.flush()

        # tarファイルの中身のディレクトリ、ファイル移動
        decompress_tar_file(
            organization_id,
            workspace_id,
            driver_id,
            dir_path.parent,
            file_name.name,
            execution_no,
            start_mode,
        )

    response.close()

    # ログファイルの作成
    exec_log_pass.touch(exist_ok=True)

    error_log_pass.touch(exist_ok=True)

    child_exec_log_pass.touch(exist_ok=True)

    child_error_log_pass.touch(exist_ok=True)

    # ITAから配布された資材のコンテナランタイム前提をAEAの設定に合わせる
    container_runtime = get_container_runtime()
    g.applogger.debug(f"container runtime: {container_runtime}")
    container_network = get_container_network()
    g.applogger.debug(f"container network: {container_network}")
    apply_container_runtime(root_dir_path, container_runtime, container_network)
    apply_proxy_envvars(root_dir_path)

    # 実行環境構築方法がITAの場合builder.sh実行
    if build_type == "2":
        builder_result = True
        try:
            g.applogger.debug(
                g.appmsg.get_log_message("MSG-11007", [workspace_id, execution_no])
            )
            cmd: list[str | pathlib.Path] = [
                "sh",
                root_dir_path / "builder_executable_files" / "builder.sh",
            ]

            with child_error_log_pass.open("w") as fp:
                _ = subprocess.run(cmd, check=True, stdout=fp, stderr=subprocess.STDOUT)

        except subprocess.CalledProcessError as e:
            exception(e)
            builder_result = False

        except Exception as e:  # noqa: BLE001
            exception(e)
            builder_result = False

        finally:
            # builder.shの実行に失敗した場合完了(異常)
            if builder_result is False:
                # ansible-builderの実行に失敗しました。(builder_executable_files/builder.sh)
                erro_log = g.appmsg.get_log_message(
                    "MSG-10986",
                    ["ansible-builder", "builder_executable_files/builder.sh"],
                )
                error_log_write(child_error_log_pass, erro_log)

                status = AnscConst.FAILURE
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

                status_code = "MSG-10986"
                msg_args = ["ansible-builder", "builder_executable_files/builder.sh"]
                raise AppException(status_code, msg_args, msg_args)
            else:
                # ログファイルクリア
                with child_error_log_pass.open("w") as f:
                    pass

    def container_running():
        try:
            container_name = f"ansible_runner_{execution_no}"
            # --format jsonの出力形式はdocker(1行1オブジェクト)とpodman(JSON配列)で異なるため、
            # 双方で同じ意味になる--quietを使い、出力の有無だけで判定する
            command = [
                container_runtime,
                "ps",
                "--quiet",
                "--filter",
                f"name={container_name}",
            ]

            cp = subprocess.run(command, check=False, capture_output=True, text=True)
            if cp.returncode != 0:
                return False

            # コンテナIDが返れば起動中
            if cp.stdout.strip():
                return True
        except Exception as e:  # noqa: BLE001
            exception(e)

        return False

    is_container_running = False if start_mode == "start" else container_running()

    # start.sh実行
    if is_container_running is False:
        start_result = True
        try:
            g.applogger.debug(
                g.appmsg.get_log_message("MSG-11008", [workspace_id, execution_no])
            )
            cmd = ["sh", f"{root_dir_path}/runner_executable_files/start.sh"]
            with child_error_log_pass.open("a") as fp:
                _ = subprocess.run(cmd, check=True, stdout=fp, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            exception(e)
            start_result = False

        except Exception as e:  # noqa: BLE001
            exception(e)
            start_result = False
        finally:
            # start.shの実行に失敗した場合完了(異常)
            if start_result is False:
                # ログ更新
                erro_log = g.appmsg.get_log_message(
                    "MSG-10986", ["ansible-runner", "runner_executable_files/start.sh"]
                )
                error_log_write(child_error_log_pass, erro_log)

                status = AnscConst.FAILURE
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

                # agent_child_mainのAppExceptionで異常時の共通処理
                status_code = "MSG-10986"
                msg_args = ["ansible-runner", "runner_executable_files/start.sh"]
                raise AppException(status_code, msg_args, msg_args)

    while True:
        # 5秒スリーブ
        time.sleep(5)

        # alive.sh実行
        try:
            alive_result = True
            cmd = ["sh", f"{root_dir_path}/runner_executable_files/alive.sh"]
            with child_error_log_pass.open("a") as fp:
                _ = subprocess.run(cmd, check=True, stdout=fp, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            # runnerが終るとaliveの戻りが0以外になるので、正常とする。
            # ログをクリアする
            with child_error_log_pass.open("w") as f:
                pass
            alive_result = True
        except Exception as e:  # noqa: BLE001
            exception(e)
            alive_result = False

        # runner作業実行状態判定
        g.applogger.debug(
            g.appmsg.get_log_message(
                "MSG-11009", [workspace_id, execution_no, alive_result]
            )
        )
        if alive_result is True:
            # runner作業中
            file_path = root_dir_path / "out" / "forced.txt"
            # 緊急停止ボタンがクリックされたか判定
            if file_path.is_file():
                # 緊急停止ボタン クリック
                g.applogger.debug(
                    g.appmsg.get_log_message(
                        "MSG-11010", [workspace_id, execution_no, "True"]
                    )
                )
                stop_result = True
                try:
                    cmd = ["sh", f"{root_dir_path}/runner_executable_files/stop.sh"]
                    with child_error_log_pass.open("a") as fp:
                        _ret = subprocess.run(
                            cmd, check=True, stdout=fp, stderr=subprocess.STDOUT
                        )
                except subprocess.CalledProcessError as e:
                    exception(e)
                    stop_result = False

                except Exception as e:  # noqa: BLE001
                    exception(e)
                    stop_result = False
                finally:
                    g.applogger.debug(
                        g.appmsg.get_log_message(
                            "MSG-11011", [workspace_id, execution_no, stop_result]
                        )
                    )
                if stop_result is True:
                    # 緊急停止に成功
                    # runner停止完了
                    # forced_exec作成
                    file_path = root_dir_path / "out" / "forced_exec"
                    file_path.touch()

                    # 結果データ更新 作業状態:緊急停止
                    status = AnscConst.SCRAM
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

                    # 結果データ更新->作業状態通知送信
                    status_code, response, error_code, error_arg = (
                        post_upload_file_and_status(
                            exastro_api,
                            organization_id,
                            workspace_id,
                            execution_no,
                            status,
                            driver_id,
                        )
                    )
                    if status_code != 200:
                        raise AppException(error_code, error_arg)

                    break

                else:
                    # 緊急停止に失敗
                    g.applogger.info(
                        g.appmsg.get_log_message(
                            "MSG-10986",
                            ["ansibe_runner", "runner_executable_files/stop.sh"],
                        )
                    )

                    # rcファイルの中身を確認する
                    rc_data = get_runner_rc_status_file(root_dir_path, execution_no)

                    if rc_data is False:
                        # rcファイルなし
                        # ログを残す
                        runner_rc_status_file_none_log(
                            child_error_log_pass, workspace_id, execution_no, "1"
                        )

                        # 結果データ更新 ステータス:完了(異常)
                        status = AnscConst.FAILURE
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

                        # 結果データ更新->作業状態通知送信
                        status_code, response, error_code, error_arg = (
                            post_upload_file_and_status(
                                exastro_api,
                                organization_id,
                                workspace_id,
                                execution_no,
                                status,
                                driver_id,
                            )
                        )
                        if status_code != 200:
                            raise AppException(error_code, error_arg)

                        break

                    elif rc_data == "0":
                        # 結果データ更新 作業状態:完了
                        status = AnscConst.COMPLETE
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

                        # 結果データ更新->作業状態通知送信
                        status_code, response, error_code, error_arg = (
                            post_upload_file_and_status(
                                exastro_api,
                                organization_id,
                                workspace_id,
                                execution_no,
                                status,
                                driver_id,
                            )
                        )
                        if status_code != 200:
                            raise AppException(error_code, error_arg)

                        break
                    else:
                        # 結果データ更新 作業状態:完了(異常)
                        status = AnscConst.FAILURE
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

                        # 結果データ更新->作業状態通知送信
                        status_code, response, error_code, error_arg = (
                            post_upload_file_and_status(
                                exastro_api,
                                organization_id,
                                workspace_id,
                                execution_no,
                                status,
                                driver_id,
                            )
                        )
                        if status_code != 200:
                            raise AppException(error_code, error_arg)

                        break

            else:
                # 緊急停止ボタンは未クリック
                g.applogger.debug(
                    g.appmsg.get_log_message(
                        "MSG-11010", [workspace_id, execution_no, "False"]
                    )
                )
                rc_data = get_runner_rc_status_file(root_dir_path, execution_no)
                if rc_data is False:
                    # rcファイルなし

                    # 結果データ更新 ステータス:実行中
                    status = AnscConst.PROCESSING
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

                    # 結果データ更新->作業状態通知送信
                    status_code, response, error_code, error_arg = (
                        post_upload_file_and_status(
                            exastro_api,
                            organization_id,
                            workspace_id,
                            execution_no,
                            status,
                            driver_id,
                        )
                    )
                    if status_code != 200:
                        raise AppException(error_code, error_arg)

                    continue

                elif rc_data == "0":
                    # 結果データ更新 ステータス:完了
                    status = AnscConst.COMPLETE
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

                    # 結果データ更新->作業状態通知送信
                    status_code, response, error_code, error_arg = (
                        post_upload_file_and_status(
                            exastro_api,
                            organization_id,
                            workspace_id,
                            execution_no,
                            status,
                            driver_id,
                        )
                    )
                    if status_code != 200:
                        raise AppException(error_code, error_arg)

                    break

                else:
                    # 結果データ更新 ステータス:完了(異常)
                    status = AnscConst.FAILURE
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

                    # 結果データ更新->作業状態通知送信
                    status_code, response, error_code, error_arg = (
                        post_upload_file_and_status(
                            exastro_api,
                            organization_id,
                            workspace_id,
                            execution_no,
                            status,
                            driver_id,
                        )
                    )
                    if status_code != 200:
                        raise AppException(error_code, error_arg)

                    break
        else:
            # runner作業状態取得失敗
            rc_data = get_runner_rc_status_file(root_dir_path, execution_no)
            if rc_data is False:
                # rcファイルなし
                # ログを残す
                erro_log = g.appmsg.get_log_message(
                    "MSG-10986", ["ansible_runner", "runner_executable_files/alive.sh"]
                )
                error_log_write(child_error_log_pass, erro_log)
                g.applogger.info(erro_log)

                runner_rc_status_file_none_log(
                    child_error_log_pass, workspace_id, execution_no, "2"
                )

                # 結果データ更新 ステータス:完了(異常)
                status = AnscConst.FAILURE
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

                # 結果データ更新->作業状態通知送信
                status_code, response, error_code, error_arg = (
                    post_upload_file_and_status(
                        exastro_api,
                        organization_id,
                        workspace_id,
                        execution_no,
                        status,
                        driver_id,
                    )
                )
                if status_code != 200:
                    raise AppException(error_code, error_arg)

                break

            elif rc_data == "0":
                # 結果データ更新 ステータス:完了
                status = AnscConst.COMPLETE
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

                # 結果データ更新->作業状態通知送信
                status_code, response, error_code, error_arg = (
                    post_upload_file_and_status(
                        exastro_api,
                        organization_id,
                        workspace_id,
                        execution_no,
                        status,
                        driver_id,
                    )
                )
                if status_code != 200:
                    raise AppException(error_code, error_arg)

                break

            else:
                # 結果データ更新 ステータス:完了(異常)
                status = AnscConst.FAILURE
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

                # 結果データ更新->作業状態通知送信
                status_code, response, error_code, error_arg = (
                    post_upload_file_and_status(
                        exastro_api,
                        organization_id,
                        workspace_id,
                        execution_no,
                        status,
                        driver_id,
                    )
                )
                if status_code != 200:
                    raise AppException(error_code, error_arg)

                break

    # ステータスファイルの削除
    delete_status_file(organization_id, workspace_id, driver_id, execution_no)


if __name__ == "__main__":
    agent_child_main()


def get_container_runtime() -> str:
    """
    playbook実行コンテナを起動するコンテナランタイムを返す

    Returns:
        "docker"(既定) または "podman"
    """
    return os.environ.get("RUNNER_CONTAINER_RUNTIME", "docker")


def get_container_network() -> str | None:
    """
    playbook実行コンテナを参加させるネットワーク名を返す

    playbookがplatform-auth等のコンテナ名でExastroへ接続するため、AEAと同じネットワークに参加させる。

    Returns:
        RUNNER_NETWORKの値。未設定または空の場合はNone(ランタイム既定のネットワークを使う)
    """
    return os.environ.get("RUNNER_NETWORK") or None


def apply_container_runtime(
    root_dir_path: pathlib.Path, runtime: str, network: str | None = None
):
    """
    ITAから配布された資材のコンテナランタイム前提をAEAの設定に合わせる

    ITA側の資材はpodman固定(ansible-runnerはenv/settings、ansible-builderは引数未指定時の既定値)のため、
    docker(DOoD)で実行する場合は書き換えが必要になる。同一資材で再実行されうるので冪等に処理する。

    ARGS:
        root_dir_path: 資材の展開先ディレクトリ
        runtime: コンテナランタイム("docker" または "podman")
        network: playbook実行コンテナを参加させるネットワーク名(Noneの場合は指定しない)
    """
    # ansible-runner: process_isolation_executable / container_optionsを上書きする
    settings_path = root_dir_path / "env" / "settings"
    if settings_path.is_file():
        keys = ["process_isolation_executable"]
        new_lines = [f"process_isolation_executable: {runtime}"]
        if network:
            # JSONのflow styleはYAMLとして有効。ネットワーク名のクォートも兼ねる
            keys.append("container_options")
            new_lines.append(
                f"container_options: {json.dumps([f'--network={network}'])}"
            )
        lines = [
            line
            for line in settings_path.read_text().splitlines()
            if not line.startswith(tuple(keys))
        ]
        lines.extend(new_lines)
        settings_path.write_text("\n".join(lines) + "\n")

    # ansible-runner: -vを上書きする
    cmdline_path = root_dir_path / "env" / "cmdline"
    if cmdline_path.is_file():
        target_option = "-v"
        options = [
            option if option != target_option else "-vvvv"
            for option in cmdline_path.read_text().split()
        ]
        cmdline_path.write_text(" ".join(options))

    # ansible-builder: --container-runtimeを注入する(未指定時の既定はpodman)
    builder_path = root_dir_path / "builder_executable_files" / "builder.sh"
    if builder_path.is_file():
        builder_sh = builder_path.read_text()
        if "--container-runtime" not in builder_sh:
            builder_path.write_text(
                builder_sh.replace(
                    "ansible-builder build",
                    f"ansible-builder build --container-runtime {runtime}",
                    1,
                )
            )


PROXY_ENV_NAMES = (
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
)


def apply_proxy_envvars(root_dir_path: pathlib.Path):
    """
    AEAのproxy設定をplaybook実行コンテナに引き継ぐ

    ansible-runnerはコンテナ実行時にAEAの環境変数を引き継がず、env/envvarsの内容だけをコンテナに渡す。
    そのためAEAに設定されているproxy関連の環境変数をenv/envvarsに書き出す。
    既存の設定は保持し、同名のキーだけ上書きするので冪等に処理できる。

    ARGS:
        root_dir_path: 資材の展開先ディレクトリ
    """
    proxy_envvars = {
        name: os.environ[name] for name in PROXY_ENV_NAMES if os.environ.get(name)
    }
    if not proxy_envvars:
        return

    envvars_path = root_dir_path / "env" / "envvars"
    envvars: dict[str, Any] = {}
    if envvars_path.is_file():
        # ansible-runnerはenv/envvarsをYAML(JSON含む)として読む
        envvars = yaml.safe_load(envvars_path.read_text()) or {}
    envvars.update(proxy_envvars)
    envvars_path.parent.mkdir(parents=True, exist_ok=True)
    envvars_path.write_text(json.dumps(envvars))


def get_runner_rc_status_file(root_dir_path: pathlib.Path, execution_no: str):
    rc_data = False
    file_path = root_dir_path / "artifacts" / execution_no / "rc"
    if file_path.is_file():
        rc_data = file_path.read_text()
    return rc_data


def runner_rc_status_file_none_log(
    child_error_log_path: pathlib.Path, workspace_id, execution_no, location
):
    # MSG-10953  rcファイルがありません。
    g.applogger.info(
        g.appmsg.get_log_message("MSG-10953", [workspace_id, execution_no, location])
    )
    msg = g.appmsg.get_log_message("MSG-10953", [workspace_id, execution_no, location])
    error_log_write(child_error_log_path, msg)


def error_log_write(log_file: pathlib.Path, msg):
    with log_file.open("a") as f:
        f.write(msg + "\n")


def decompress_tar_file(
    organization_id: str,
    workspace_id: str,
    driver_id: str,
    dir_path: pathlib.Path,
    file_name: str,
    execution_no: str,
    start_mode="start",
):
    """
    tarファイルを解凍してagent用のディレクトリに移動する
    ARGS:
        dir_path: in,outのtarファイルディレクトリ
        conductor_dir_path: conductorのtarファイルディレクトリ
        file_name: in,outのtarファイル名
        conductor_file_name: conductorのtarファイル名
        driver_id: ドライバーID
        execution_no: 作業番号

    Returns:
        stdout row
    """

    # tarファイル解凍先
    tar_path = (
        pathlib.Path("/tmp")
        / organization_id
        / workspace_id
        / "driver"
        / "ansible"
        / driver_id
        / execution_no
        / "tar"
    )

    # in,outのtarファイルを展開
    with tarfile.open(dir_path / file_name, "r:gz") as tar:
        tar.extractall(path=tar_path)

    # 展開したファイルの一覧を取得
    lst = os.listdir(tar_path)

    # in/out親ディレクトリパス
    storagepath = pathlib.Path(os.environ.get("STORAGEPATH", "/exastro/storage"))
    root_dir_path = (
        storagepath
        / organization_id
        / workspace_id
        / "driver"
        / "ag_ansible_execution"
        / driver_id
        / execution_no
    )

    # 移動前に作業用ディレクトリを作成しておく
    retry_makedirs(root_dir_path)

    def _retry_move(src_path: pathlib.Path, dest_path: pathlib.Path):
        if start_mode == "start":
            retry_move(src_path, dest_path)
        else:
            # 再起動のときは、既にディレクトリがある場合は無視する
            @file_read_retry
            def retry_move_on_restart(src_path: pathlib.Path, dest_path: pathlib.Path):
                g.applogger.debug(f"retry_move({src_path, dest_path})")
                try:
                    os.listdir(
                        src_path.parent
                    )  # NFSストレージ対策：属性キャッシュ更新を試みる コピー元のみ(コピー先は無いこともある)
                    shutil.move(src_path, dest_path)
                    return True
                except Exception as e:  # noqa: BLE001
                    # 既にある
                    if str(e).find("already exists") != -1:
                        return True

                    g.applogger.info(
                        f"retry_move failed. src_path={src_path}, dest_path={dest_path}"
                    )
                    t = traceback.format_exc()
                    g.applogger.debug(arrange_stacktrace_format(t))
                    return False

            retry_move_on_restart(src_path, dest_path)

    # 展開したファイルを移動する
    move_dir = ""
    for dir_name in lst:
        if dir_name == execution_no:
            sublst = os.listdir(tar_path / dir_name)
            for dir_name in sublst:
                if dir_name == "in":
                    # inディレクトリの中身取得
                    in_lst = os.listdir(tar_path / execution_no / dir_name)
                    for in_dir_name in in_lst:
                        if in_dir_name in [
                            "inventory",
                            "env",
                            "builder_executable_files",
                            "runner_executable_files",
                        ]:
                            # 1つ上の階層へ移動
                            _retry_move(
                                tar_path / execution_no / dir_name / in_dir_name,
                                tar_path / execution_no,
                            )
                            # inventory,.env.,builder_executable_files,runner_executable_filesディレクトリの移動
                            join_path = tar_path / execution_no / in_dir_name
                            _retry_move(join_path, root_dir_path)
                    # inディレクトリの移動先
                    move_dir = root_dir_path / "project"
                    join_path = tar_path / execution_no / dir_name
                    _retry_move(join_path, move_dir)
                elif dir_name in ["out", ".tmp", "tmp"]:
                    # out,.tmp.,tmpディレクトリの移動
                    join_path = tar_path / execution_no / dir_name
                    _retry_move(join_path, root_dir_path)
        elif dir_name == "conductor":
            # conductorディレクトリの移動先
            join_path = tar_path / dir_name
            _retry_move(join_path, root_dir_path)

    # 作業ディレクトリ削除
    clear_execution_tmpdir(organization_id, workspace_id, driver_id, execution_no)


def post_upload_file_and_status(
    exastro_api, organization_id, workspace_id, execution_no, status, driver_id
):

    status_code, response = (000, {})

    # 各種ファイルをtarファイルにまとめる
    (
        out_gztar_path,
        parameters_gztar_path,
        parameters_file_gztar_path,
        conductor_dir_path,
    ) = arcive_tar_data(organization_id, workspace_id, driver_id, execution_no, status)

    if exastro_api is None:
        # 環境変数の取得
        base_url = os.environ["EXASTRO_URL"]
        refresh_token = os.environ["EXASTRO_REFRESH_TOKEN"]

        # ITAのAPI呼び出しモジュール
        exastro_api = Exastro_API(base_url=base_url, refresh_token=refresh_token)
        exastro_api.get_access_token(organization_id, refresh_token)

    # パラメータ
    body = {"driver_id": driver_id, "status": status}
    form_data: dict[str, Any] = {"json_parameters": json.dumps(body)}

    # form_dataへのtarデータ追加
    if out_gztar_path.is_file():
        form_data["out_tar_data"] = (
            out_gztar_path.name,
            out_gztar_path.open("rb"),
            mimetypes.guess_type(out_gztar_path, False)[0],
        )
    if parameters_gztar_path is not None and parameters_gztar_path.is_file():
        form_data["parameters_tar_data"] = (
            parameters_gztar_path.name,
            parameters_gztar_path.open("rb"),
            mimetypes.guess_type(parameters_gztar_path, False)[0],
        )
    if parameters_file_gztar_path is not None and parameters_file_gztar_path.is_file():
        form_data["parameters_file_tar_data"] = (
            parameters_file_gztar_path.name,
            parameters_file_gztar_path.open("rb"),
            mimetypes.guess_type(parameters_file_gztar_path, False)[0],
        )
    if conductor_dir_path is not None and conductor_dir_path.is_file():
        form_data["conductor_tar_data"] = (
            conductor_dir_path.name,
            conductor_dir_path.open("rb"),
            mimetypes.guess_type(conductor_dir_path, False)[0],
        )

    # 実行中の場合はjson_parameters、out_tar_data以外除外
    if status == AnscConst.PROCESSING:
        accept_key = ["json_parameters", "out_tar_data"]
        for k in tuple(form_data):
            if k not in accept_key:
                del form_data[k]

    # 結果データ更新
    g.applogger.info(
        g.appmsg.get_log_message("MSG-10994", [workspace_id, execution_no])
    )
    status_code, response = post_upload_execution_files(
        organization_id,
        workspace_id,
        exastro_api,
        execution_no,
        body,
        form_data=form_data,
    )
    if status_code != 200:
        return (
            status_code,
            response,
            "MSG-10995",
            [workspace_id, execution_no, status_code, response],
        )

    # 作業状態通知送信
    g.applogger.info(
        g.appmsg.get_log_message("MSG-10990", [workspace_id, execution_no, status])
    )
    status_code, response = post_update_execution_status(
        organization_id, workspace_id, exastro_api, execution_no, body
    )
    if status_code != 200:
        return (
            status_code,
            response,
            "MSG-10991",
            [workspace_id, execution_no, status, status_code, response],
        )

    # 作業状態通知のレスポンスで緊急停止フラグが設定されている場合、forced.txtファイル作成
    chk_emergency_stop(response, organization_id, workspace_id, driver_id, execution_no)
    return status_code, response, "", []


def chk_emergency_stop(
    response, organization_id: str, workspace_id: str, driver_id: str, execution_no: str
):
    storagepath = pathlib.Path(os.environ.get("STORAGEPATH", "/exastro/storage"))
    root_dir_path = (
        storagepath
        / organization_id
        / workspace_id
        / "driver"
        / "ag_ansible_execution"
        / driver_id
        / execution_no
    )
    # 作業状態通知のレスポンスで緊急停止ありの場合
    if response["data"]["SCRAM_STATUS"] == "1":
        g.applogger.debug(
            g.appmsg.get_log_message("MSG-11012", [workspace_id, execution_no])
        )
        p = root_dir_path / "out" / "forced.txt"
        p.touch()
