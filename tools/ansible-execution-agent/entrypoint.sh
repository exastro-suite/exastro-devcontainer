#!/bin/bash
cd $(dirname $0)
source .venv/bin/activate
cd ..
# exec で python をコンテナの PID 1 にする。
# sh の子プロセスのままだと docker stop の SIGTERM が python まで届かず、
# python が死んでも PID 1 が生き残ってコンテナが "Up" のまま無処理になる。
exec python -m ansible-execution-agent.entrypoint
