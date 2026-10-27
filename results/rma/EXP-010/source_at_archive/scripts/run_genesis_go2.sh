#!/usr/bin/env bash
set -euo pipefail
export LD_LIBRARY_PATH="/usr/lib/wsl/lib"
exec /home/abc/.venvs/genesis-go2/bin/python /home/abc/my_unilab/scripts/sim2sim_genesis_go2.py "$@"
