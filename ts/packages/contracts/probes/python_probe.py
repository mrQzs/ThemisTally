"""契约探针（Python 实现）：stdin 读一个 JSON 请求，stdout 写一个 JSON 结果。

只 import 仓库里的 scripts/，不改它。请求与结果的形状见 test/harness.ts；
TS 实现的探针（ts_probe.ts）收发同样的 JSON，契约测试与对照测试对两边一视同仁。
"""
import base64
import errno
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # ts/packages/contracts/probes → 仓库根
sys.path.insert(0, str(ROOT / "scripts"))

import pi_dispatch  # noqa: E402


def wait_for(barrier: str) -> None:
    """并发用例：先报“就绪”，等测试建好起跑文件再一起动手。"""
    sys.stderr.write("ready\n")
    sys.stderr.flush()
    while not os.path.exists(barrier):
        time.sleep(0.001)


def main() -> int:
    request = json.loads(sys.stdin.read())
    if request.get("barrier"):
        wait_for(request["barrier"])
    if request["op"] != "publish_new":
        sys.stdout.write(json.dumps({"ok": False, "error": "UNKNOWN_OP"}))
        return 2
    try:
        published = pi_dispatch.publish_new(Path(request["path"]), base64.b64decode(request["data_b64"]))
        result = {"ok": True, "published": published}
    except OSError as exc:
        result = {"ok": False, "error": errno.errorcode.get(exc.errno or 0, "EUNKNOWN")}
    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
