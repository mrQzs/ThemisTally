#!/usr/bin/env bash
# 兼容 方案.md 附录 A 的入口名：所有逻辑在跨平台的 pi_dispatch.py 中。
# 用法与 pi_dispatch.py 相同，例如：bash scripts/dispatch-pi.sh prepare normalize-query.v1
set -euo pipefail

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)

# Windows 的 python3 可能是应用商店占位程序，所以逐个试运行，而不只检查命令是否存在。
for candidate in python3 python py; do
  if command -v "$candidate" >/dev/null 2>&1; then
    # Bash 3.2 在 set -u 下展开空数组会报 unbound variable。
    # 把解释器也放进数组，python3/python 与 py -3 两条路径都保持非空。
    python_cmd=("$candidate")
    [[ "$candidate" == py ]] && python_cmd+=(-3)
    if "${python_cmd[@]}" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
      exec "${python_cmd[@]}" "$here/pi_dispatch.py" "$@"
    fi
  fi
done

echo 'ERROR: 需要 Python 3.8+（python3、python 或 py -3）' >&2
exit 2
