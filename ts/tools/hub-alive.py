"""hub 停没停（迁移计划第 ⑤ 步 E2：翻选择文件之前机械地查，不靠人记）。只读：不拿锁、不写信箱。

用法：python ts/tools/hub-alive.py [--repo 仓库]（缺省当前目录）。退出码：0 没有活的 hub 进程；1 有，逐个列出来源、pid 与进程名；
2 不是 Windows（判活要 Win32）。

查这些地方记的 pid（写它的都是 hub 的进程本身：串行 hub、supervisor、主任务 runner、owner-sweep、站主命令；切换之前是 python.exe，
之后是 bun.exe）：
- 信箱下以“.”开头的锁目录里的 owner.json（DirLock：.runner、.lock、.land、.sweep、.owner-sweep……），以及 .runners/<主任务>/owner.json；
- ledger/exec-active/*.json：执行端从 prepare 到 check、后台回归期间，跑它的 hub 进程挂的标记；
- .pause/<主任务>：站主命令等主任务 runner 让出锁时挂的标记。
判活只按 pid 与进程名：进程还没退出、映像文件名是 python.exe、pythonw.exe 或 bun.exe 才算“活的 hub”。不读命令行。pid 被别的同名
进程复用时会误报“还活着”，只会偏保守；拿不到进程信息（权限不够）的也按活的报。记录读不出（不是 JSON、没有整数 pid）的照样列出、
退出 1，留给人看。
"""
import argparse
import ctypes
import json
import sys
from ctypes import wintypes
from pathlib import Path

HUB_IMAGES = {"python.exe", "pythonw.exe", "bun.exe"}
STILL_ACTIVE = 259


def records(root: Path):
    """（来源，pid 或 None）：信箱下记了 pid 的地方，按路径排序。"""
    paths = sorted(root.glob(".*/owner.json")) + sorted(root.glob(".runners/*/owner.json"))
    paths += sorted((root / "ledger" / "exec-active").glob("*.json")) + sorted(p for p in (root / ".pause").glob("*") if p.is_file())
    for path in paths:
        try:
            pid = json.loads(path.read_text(encoding="utf-8")).get("pid")
        except (OSError, ValueError, AttributeError):
            pid = None
        yield path.relative_to(root).as_posix(), pid if type(pid) is int and pid > 0 else None


def image_of(pid: int):
    """进程还活着时交回映像文件名（小写），已经退出或不存在时交回 None；打不开（权限不够）交回 "?"。"""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None if ctypes.get_last_error() == 87 else "?"  # 87：参数错误，即没有这个 pid
    try:
        code = wintypes.DWORD()
        if k32.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value != STILL_ACTIVE:
            return None
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not k32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return "?"
        return buffer.value.replace(chr(92), "/").rsplit("/", 1)[-1].lower()
    finally:
        k32.CloseHandle(handle)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="hub-alive.py")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        print("只在 Windows 上：判活要 Win32 的进程查询", file=sys.stderr)
        return 2
    root = Path(args.repo).resolve() / ".agent" / "mailbox"
    alive = []
    for source, pid in records(root):
        if pid is None:
            alive.append("%s：读不出 pid" % source)
            continue
        image = image_of(pid)
        if image == "?" or image in HUB_IMAGES:
            alive.append("%s：pid %d，%s" % (source, pid, "拿不到进程信息" if image == "?" else image))
    for line in alive:
        print(line)
    print("有活的 hub 进程：%d 处" % len(alive) if alive else "没有活的 hub 进程")
    return 1 if alive else 0


if __name__ == "__main__":
    sys.exit(main())
