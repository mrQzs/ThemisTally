"""契约用的启动器：把本进程令牌的备份与还原特权（SeBackupPrivilege、SeRestorePrivilege）设成启用（on）或停用（off），再起后面的命令。
子进程继承令牌，标准输入输出照旧接着。

libuv 打开文件总带 FILE_FLAG_BACKUP_SEMANTICS：备份特权启用时，Node 与 Bun 的读不受别的进程 dwShareMode=0 的占用限制，
停用时与 Python 一样撞上共享冲突（libuv 报 EBUSY）。Git Bash 起的进程树里这两个特权是启用的，PowerShell 起的是停用的
（hub 的 supervisor 经 PowerShell 的 Start-Process 起）。第 ⑤b 片的 C4 两种状态都跑，结果不随测试从哪里起而变。
用法：python backup_privilege.py on|off 命令 参数……
"""
import ctypes
import json
import subprocess
import sys
from ctypes import wintypes

PRIVILEGES = ("SeBackupPrivilege", "SeRestorePrivilege")
SE_PRIVILEGE_ENABLED = 0x2
TOKEN_ADJUST_PRIVILEGES = 0x20
TOKEN_QUERY = 0x8
ERROR_NOT_ALL_ASSIGNED = 1300


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wintypes.DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * len(PRIVILEGES))]


def set_privileges(enable: bool) -> bool:
    """设好之后交回 True；要启用而令牌里没有这两个特权（不是管理员）时交回 False。停用时没有就算停用了。"""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi32.LookupPrivilegeValueW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(LUID)]
    advapi32.AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
                                               ctypes.c_void_p]
    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(token)):
        return False
    entries = []
    for name in PRIVILEGES:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
            return False
        entries.append(LUID_AND_ATTRIBUTES(luid, SE_PRIVILEGE_ENABLED if enable else 0))
    request = TOKEN_PRIVILEGES(len(entries), (LUID_AND_ATTRIBUTES * len(PRIVILEGES))(*entries))
    if not advapi32.AdjustTokenPrivileges(token, False, ctypes.byref(request), 0, None, None):
        return False
    return not enable or ctypes.get_last_error() != ERROR_NOT_ALL_ASSIGNED


def main() -> int:
    state, argv = sys.argv[1], sys.argv[2:]
    if not set_privileges(state == "on"):
        print(json.dumps({"ok": False, "error": "PRIVILEGE_UNAVAILABLE"}))
        return 0
    return subprocess.run(argv).returncode


if __name__ == "__main__":
    sys.exit(main())
