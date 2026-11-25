# Copyright 2022 NEC Corporation#
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

"""
共通関数 module
"""

import collections.abc
import datetime
import inspect
import os
import pathlib
import shutil
import time
import traceback

import pytz
from flask import g


def get_iso_datetime(is_utc=True):
    """
    get timestamp for api response format

    Args:
        is_utc (bool):

    Returns:
        2022-08-02T10:26:18.809Z
    """
    return datetime_to_str(datetime.datetime.now(datetime.UTC))


def datetime_to_str(p_datetime):
    """datetime to string (ISO format)
    Args:
        p_datetime (datetime): datetime
    Returns:
        str: datetime formated string (UTC)
    """
    if p_datetime is None:
        return None

    if p_datetime.tzinfo is None:
        aware_datetime = pytz.timezone(os.environ.get("TZ", "UTC")).localize(p_datetime)
    else:
        aware_datetime = p_datetime

    utc_datetime = aware_datetime.astimezone(datetime.UTC)
    return utc_datetime.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def arrange_stacktrace_format(t):
    """
    stacktrace

    Arguments:
        t: return traceback.format_exc()
    Returns:
        (str)
    """
    return t
    # retStr = ""

    # exception_block_arr = t.split('Traceback (most recent call last):\n')
    # # exception_block = exception_block_arr[1]  # most deep exception called
    # exception_block_index = 0
    # for exception_block in exception_block_arr:
    #     exception_block = re.sub(r'\n\nDuring handling of the above exception, another exception occurred:\n\n', '', exception_block.strip())
    #     if exception_block[0:4] != 'File':
    #         continue

    #     retStr = retStr + "\n{} : exception block".format(exception_block_index)
    #     exception_block_index = exception_block_index + 1

    #     trace_block_arr = re.split('File ', exception_block)
    #     for trace_block in trace_block_arr:
    #         row_arr = re.split('\n', str(trace_block.strip()))
    #         row_index = 0
    #         row_str = ""
    #         length = len(row_arr) - 1
    #         if length == 0:
    #             continue

    #         for row in row_arr:

    #             if row_index == 0:
    #                 row_str = "\n -> " + row
    #             elif row_index == 1:
    #                 row_str = row_str + ", " + row.strip()
    #                 retStr = retStr + row_str
    #             elif row_index == 2:
    #                 retStr = retStr + "\n " + row.strip()

    #             row_index = row_index + 1

    # return retStr


file_read_retry_limit = int(
    os.environ.get("FILE_READ_RETRY_LIMIT", "3")
)  # ファイルストレージへの読み書きのリトライ回数の上限
file_read_retry_delay_time = float(
    os.environ.get("FILE_READ_RETRY_DELAY_TIME", "0.1")
)  # ファイルストレージへの読み書きのリトライのインターバル


def file_read_retry(func: collections.abc.Callable[..., bool]):
    """
    file_read_retry
        ファイルストレージへの書き込み直後の読み込みが遅い場合向けの対策
        Measures to take when reading is slow immediately after writing to file storage

        「FileNotFoundError: [Errno 2] No such file or directory」が出るため、リトライを行う
        "FileNotFoundError: [Errno 2] No such file or directory" appears, so retry.

        デコレーター関数 / decorator function
        ・file_encodeの中に例をあげています
    """

    def wrapper(*args, **kwargs):
        retBool = False
        i = 1
        # logger_class: コンテキスト外等でg.apploggerが使用できない時の対処
        logger = kwargs.get("logger_class") or g.applogger
        while True:
            try:
                retBool = func(*args, **kwargs)
                if retBool is True:
                    break
            except Exception as e:
                # raiseしたくない場合は、funcの中でログを出力し、（エラーを抑止して）Falseを返却してください
                if i == file_read_retry_limit:
                    # 最後のログ出力のみ、stacktraceを出力
                    # Output stacktrace only the last log output
                    t = traceback.format_exc()
                    logger.info(arrange_stacktrace_format(t))
                    raise
                else:
                    # retry分は、メッセージのみを出力
                    # For retry minutes, only the message is output
                    print_exception_msg(e, logger_class=logger)

            if i == file_read_retry_limit:
                break
            time.sleep(file_read_retry_delay_time)
            i = i + 1

    return wrapper


lasttime_get_maintenance_mode = None
last_maintenance_mode_setting = None
interval_get_maintenance_mode = int(
    os.environ.get("INTERVAL_GET_MAINTENANCE_MODE", "30")
)


def print_exception_msg(e, logger_class=None):
    """
    例外メッセージを、infoログに出力する
    logger_class: コンテキスト外等でg.apploggerが使用できない時の対処
    """
    logger = logger_class or g.applogger
    # 例外と、発生したファイ名と行番号を出力
    info = inspect.getouterframes(inspect.currentframe())[1]
    msg_line = f"({pathlib.Path(info.filename).name}:{info.lineno})"
    exception_msg = f"exception_msg='{e}'"
    logger.info(f"[timestamp={get_iso_datetime()}] {exception_msg} {msg_line}")


# 低速ストレージ対応: @file_read_retry デコレータでリトライ処理を付与
# ディレクトリ作成
@file_read_retry
def retry_makedirs(dir_path: pathlib.Path, raise_error=True):
    """
    `os.makedirs(dir_path, exist_ok=True)` 相当(親ディレクトリも作成)を`@file_read_retry`付きで実行する
    Args:
        dir_path: 作成するディレクトリパス
        raise_error: リトライを実施してもエラーが発生した際に例外スローするか (True: 例外スロー&ログ出力/ False: ログ出力のみ)
    """
    g.applogger.debug(f"retry_makedirs({dir_path})")
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        g.applogger.info(f"retry_makedirs failed. {dir_path=}")
        t = traceback.format_exc()
        g.applogger.debug(arrange_stacktrace_format(t))
        if raise_error is True:
            raise
        else:
            return False


# パーミッション設定
@file_read_retry
def retry_chmod(path: pathlib.Path, mode, raise_error=True):
    """
    `os.chmod(path, mode)` を`@file_read_retry`付きで実行する
    Args:
        path: 対象のパス
        mode: 設定するパーミッションモード(0o777形式)
        raise_error: リトライを実施してもエラーが発生した際に例外スローするか (True: 例外スロー&ログ出力/ False: ログ出力のみ)
    """
    g.applogger.debug(f"retry_chmod({path, mode})")
    try:
        os.listdir(path.parent)  # NFSストレージ対策：属性キャッシュ更新を試みる
        path.chmod(mode)
        return True
    except Exception:
        g.applogger.info(f"retry_chmod failed. path={path}, mode={mode}")
        t = traceback.format_exc()
        g.applogger.debug(arrange_stacktrace_format(t))
        if raise_error is True:
            raise
        else:
            return False


# ディレクトリコピー(shutil.copytree)
@file_read_retry
def retry_copytree(src_path: pathlib.Path, dest_path: pathlib.Path, raise_error=True):
    """
    `shutil.copytree(src_path, dest_path, exist_ok=True)` を`@file_read_retry`付きで実行する
    Args:
        src_path: コピー元のディレクトリパス
        dest_path: コピー先のディレクトリパス
        raise_error: リトライを実施してもエラーが発生した際に例外スローするか (True: 例外スロー&ログ出力/ False: ログ出力のみ)
    """
    g.applogger.debug(f"retry_copytree({src_path, dest_path})")
    try:
        os.listdir(
            src_path.parent
        )  # NFSストレージ対策：属性キャッシュ更新を試みる コピー元のみ(コピー先は無いこともある)
        shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
        return True
    except Exception:
        g.applogger.info(
            f"retry_copytree failed. src_path={src_path}, dest_path={dest_path}"
        )
        t = traceback.format_exc()
        g.applogger.debug(arrange_stacktrace_format(t))
        if raise_error is True:
            raise
        else:
            return False


# ファイルコピー(shutil.copy)
@file_read_retry
def retry_copy(src_path: pathlib.Path, dest_path: pathlib.Path, raise_error=True):
    """
    `shutil.copy(src_path, dest_path)` を`@file_read_retry`付きで実行する
    Args:
        src_path: コピー元のファイルパス
        dest_path: コピー先のファイルパス
        raise_error: リトライを実施してもエラーが発生した際に例外スローするか (True: 例外スロー&ログ出力/ False: ログ出力のみ)
    """
    g.applogger.debug(f"retry_copy({src_path, dest_path})")
    try:
        os.listdir(src_path.parent)  # NFSストレージ対策：属性キャッシュ更新を試みる
        os.listdir(dest_path.parent)  # NFSストレージ対策：属性キャッシュ更新を試みる
        shutil.copy(src_path, dest_path)
        return True
    except Exception:
        g.applogger.info(
            f"retry_copy failed. src_path={src_path}, dest_path={dest_path}"
        )
        t = traceback.format_exc()
        g.applogger.debug(arrange_stacktrace_format(t))
        if raise_error is True:
            raise
        else:
            return False


# ディレクトリ移動(shutil.move)
@file_read_retry
def retry_move(src_path: pathlib.Path, dest_path: pathlib.Path, raise_error=True):
    """
    `shutil.move(src_path, dest_path)` を`@file_read_retry`付きで実行する
    Args:
        src_path: コピー元のディレクトリパス
        dest_path: コピー先のディレクトリパス
        raise_error: リトライを実施してもエラーが発生した際に例外スローするか (True: 例外スロー&ログ出力/ False: ログ出力のみ)
    """
    g.applogger.debug(f"retry_move({src_path, dest_path})")
    try:
        os.listdir(
            src_path.parent
        )  # NFSストレージ対策：属性キャッシュ更新を試みる コピー元のみ(コピー先は無いこともある)
        shutil.move(src_path, dest_path)
        return True
    except Exception:
        g.applogger.info(
            f"retry_move failed. src_path={src_path}, dest_path={dest_path}"
        )
        t = traceback.format_exc()
        g.applogger.debug(arrange_stacktrace_format(t))
        if raise_error is True:
            raise
        else:
            return False


# ディレクトリ削除(shutil.rmtree)
@file_read_retry
def retry_rmtree(dir_path: pathlib.Path, raise_error=True):
    """
    `shutil.rmtree(dir_path)` を`@file_read_retry`付きで実行する
    Args:
        dir_path: 削除するディレクトリパス
        raise_error: リトライを実施してもエラーが発生した際に例外スローするか (True: 例外スロー&ログ出力/ False: ログ出力のみ)
    """
    g.applogger.debug(f"retry_rmtree({dir_path})")
    try:
        # 低速ストレージ（読み書きが不安定なストレージ）対応:
        # - 存在しないケースがあるディレクトリに対してもos.path.isdirで存在確認をせずに削除するため
        # - 作成することでキャッシュをクリアできる可能性もあるため
        # 一旦作成してから削除する
        dir_path.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(dir_path)
        return True
    except Exception:
        g.applogger.info(f"retry_rmtree failed. dir_path={dir_path}")
        t = traceback.format_exc()
        g.applogger.debug(arrange_stacktrace_format(t))
        if raise_error is True:
            raise
        else:
            return False


# ファイル削除(os.remove)
@file_read_retry
def retry_remove(file_path: pathlib.Path, raise_error=True, logger_class=None):
    """
    `os.remove(file_path)` を`@file_read_retry`付きで実行する
    Args:
        file_path: 削除するファイルパス
        raise_error: リトライを実施してもエラーが発生した際に例外スローするか (True: 例外スロー&ログ出力/ False: ログ出力のみ)
        logger_class: コンテキスト外等でg.apploggerが使用できない時の対処
    """
    logger = logger_class or g.applogger
    logger.debug(f"os.remove({file_path})")
    try:
        os.listdir(file_path.parent)  # NFSストレージ対策：属性キャッシュ更新を試みる
        file_path.unlink()
        return True
    except Exception:
        logger.info(f"retry_remove failed. file_path={file_path}")
        t = traceback.format_exc()
        logger.debug(arrange_stacktrace_format(t))
        if raise_error is True:
            raise
        else:
            return False
