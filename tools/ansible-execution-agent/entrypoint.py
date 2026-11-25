import os
import sys
import time
import traceback

from .agent.agent_init import main

if __name__ == "__main__":
    # main()内で捕捉できなかった例外でループを止めないためのインターバル
    retry_interval = max(3, int(os.environ.get("EXECUTE_INTERVAL", "5")))

    while True:
        try:
            main()
        except Exception:  # noqa: BLE001
            # main()のtry/exceptの外側（ロガー生成前など）で発生した例外
            # プロセスを落とさず、インターバルを置いてループを継続する
            sys.stderr.write(traceback.format_exc())
            sys.stderr.flush()
            time.sleep(retry_interval)
