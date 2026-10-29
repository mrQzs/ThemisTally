"""调度器命令的耗时：同一批只读命令，钉成全部 Python 与全部 TS（经真的启动器）各跑若干次，取中位数（迁移计划第 9 节的计时）。

用法：python ts/tools/dispatch-timing.py [--repo 仓库] [--runs 10] [--plan 合同版本] [--task 任务]
内核是本文件所在的仓库；--repo 缺省也是它。只读命令，不改仓库；选择文件写在临时目录里，不碰提交的那一份。
"""
import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KERNEL = Path(__file__).resolve().parents[2]


def selectors(directory: Path) -> dict:
    ts = directory / "ts.json"
    ts.write_text(json.dumps({"schema_version": 1, "readonly": "ts", "config": "ts", "dispatcher": "ts", "hub": "python"}),
                  encoding="utf-8")
    return {"python": directory / "absent.json", "ts": ts}


def median_seconds(selector: Path, repo: Path, argv: list, runs: int) -> tuple:
    program = ("import sys; sys.path.insert(0, %r); import pi_dispatch as pd; pd.KERNEL_IMPL_PATH = pd.Path(sys.argv[1]); "
               "sys.exit(pd.main(sys.argv[2:]))" % str(KERNEL / "scripts"))
    times = []
    code = None
    for _ in range(runs):
        start = time.perf_counter()
        done = subprocess.run([sys.executable, "-c", program, str(selector), "--repo", str(repo)] + argv, cwd=str(repo),
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        times.append(time.perf_counter() - start)
        code = done.returncode
    return statistics.median(times), code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=str(KERNEL))
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--plan", default="t023-desktop-ui-writes-b.v1")
    parser.add_argument("--task", default="t023-desktop-ui-writes-b")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    commands = [
        ["validate", args.plan],
        ["metrics"],
        ["wait", args.task, "--timeout", "1"],
        ["sync-adapters", "--check"],
        ["release-check"],
        ["status", "--json"],
        ["config", "show", "--json"],
    ]
    with tempfile.TemporaryDirectory(prefix="dispatch-timing-") as directory:
        chosen = selectors(Path(directory))
        for argv in commands:
            py, py_code = median_seconds(chosen["python"], repo, argv, args.runs)
            ts, ts_code = median_seconds(chosen["ts"], repo, argv, args.runs)
            print("%-28s python %6.2f s  ts %6.2f s  (+%.2f s)  exit %s/%s" % (" ".join(argv[:2]), py, ts, ts - py, py_code, ts_code))
    return 0


if __name__ == "__main__":
    sys.exit(main())
