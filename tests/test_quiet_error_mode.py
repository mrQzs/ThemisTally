"""第 123 轮：入口进程设上不弹系统错误框的错误模式（pi_dispatch.QUIET_ERROR_MODE），子进程继承。

控制台进程还在初始化时就收到 CTRL_BREAK，DLL 初始化失败（0xC0000142）；进程的错误模式缺这几位时，系统弹出
“python.exe - Application Error”硬错误框（系统日志 System、来源 Application Popup、事件 26），进程卡到有人点确定。

用例都从 CREATE_DEFAULT_ERROR_MODE 起的进程出发（不继承 conftest 给本进程设的模式），只测“设了模式”这一边：
修坏了也只是等到超时，超时就结束进程树，不会故意弹框。
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import pi_dispatch as pd  # noqa: E402

pytestmark = pytest.mark.skipif(os.name != "nt", reason="错误模式只在 Windows 上有")

STATUS_DLL_INIT_FAILED = 0xC0000142
NEWLINE = chr(10)
#: 子进程把自己继承到的错误模式写进文件（只写文件：TS 入口与辅助进程退出时未必来得及刷新 stdout）
REPORT = "import ctypes, sys; open(sys.argv[1], 'w').write(str(ctypes.windll.kernel32.GetErrorMode()))"


def run_fresh(args, tmp_path, **kwargs):
    """以默认错误模式起一个进程（不继承本进程的），等它结束。"""
    return subprocess.run(args, cwd=str(tmp_path), capture_output=True, timeout=180,
                          creationflags=subprocess.CREATE_DEFAULT_ERROR_MODE, **kwargs)


def inherited_mode(setup: str, tmp_path) -> int:
    """全新的 Python 进程先执行 setup，再起一个子进程：子进程继承到的错误模式。"""
    out = tmp_path / "mode.txt"
    code = "\n".join([
        "import subprocess, sys",
        "sys.path.insert(0, %r)" % str(SCRIPTS),
        setup,
        "subprocess.run([sys.executable, '-c', %r, %r], check=True)" % (REPORT, str(out)),
    ])
    result = run_fresh([sys.executable, "-c", code], tmp_path)
    assert out.exists(), result.stderr.decode("utf-8", "replace")[-2000:]
    return int(out.read_text())


def quiet(mode: int) -> bool:
    # 写死数值，不读 pd.QUIET_ERROR_MODE：常数本身改坏了也要抓得住
    return mode & 0x8003 == 0x8003


def test_the_test_run_itself_has_the_mode():
    # conftest 一导入就设上：全量 pytest 与门禁起的子进程都继承（站主桌面上的弹窗都出在跑测试的时候）
    import ctypes

    assert quiet(ctypes.windll.kernel32.GetErrorMode())


def test_a_process_started_with_the_default_mode_lacks_the_bits(tmp_path):
    # 对照：不经任何入口时缺这几位，下面几条用例才有意义
    assert not quiet(inherited_mode("pass", tmp_path))


@pytest.mark.parametrize("module", ["pi_dispatch", "kit_hub"])
def test_python_entry_points_set_the_mode_for_their_children(tmp_path, module):
    setup = "\n".join([
        "import %s" % module,
        "try:",
        "    %s.main(['--help'])" % module,
        "except SystemExit:",
        "    pass",
    ])
    assert quiet(inherited_mode(setup, tmp_path))


def runtime_or_skip(name: str) -> Path:
    found = pd.find_bun() if name == "bun" else shutil.which(name)
    if found is None or not (ROOT / "ts" / "node_modules").is_dir():
        pytest.skip("本机没有 %s 或 ts/ 没装依赖" % name)
    return Path(found)


@pytest.mark.parametrize("runtime, entry", [
    ("bun", "packages/cli/src/main.ts"),
    ("bun", "packages/base/src/native-helper.ts"),
    ("node", "node_modules/vitest/package.json"),
])
def test_bun_and_node_already_start_with_the_mode(tmp_path, runtime, entry):
    """TS 一侧不用另设：Bun 与 Node 的 libuv 启动时就设了 SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX |
    SEM_NOOPENFILEERRORBOX。TS 的入口（桌面端可能直接用 Bun 起）、Node 后备的辅助进程与跑 vitest 的 Node 起的子进程
    都继承。这条钉住这个前提：哪天运行时不再这么做，就要在 TS 的入口自己设。"""
    executable = runtime_or_skip(runtime)
    out = tmp_path / "mode.txt"
    script = tmp_path / "probe.mjs"
    script.write_text(NEWLINE.join([
        'import { spawnSync } from "node:child_process";',
        'import { pathToFileURL } from "node:url";',
        'if (process.env.THEMIS_ENTRY.endsWith(".ts")) await import(pathToFileURL(process.env.THEMIS_ENTRY).href);',
        'spawnSync(process.env.THEMIS_PY, ["-c", process.env.THEMIS_REPORT, process.env.THEMIS_OUT]);',
        "process.exit(0);",
    ]), encoding="utf-8")
    env = dict(os.environ, THEMIS_ENTRY=str(ROOT / "ts" / entry), THEMIS_PY=sys.executable, THEMIS_REPORT=REPORT,
               THEMIS_OUT=str(out))
    result = run_fresh([str(executable), str(script)], tmp_path, env=env, stdin=subprocess.DEVNULL)
    assert out.exists(), result.stderr.decode("utf-8", "replace")[-2000:]
    assert quiet(int(out.read_text()))

def popup_count():
    """系统日志里“Application Popup”事件 26 的条数；查不了为 None。"""
    query = ("@(Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Application Popup'; Id=26} "
             "-ErrorAction SilentlyContinue).Count")
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", query],
                                capture_output=True, text=True, timeout=120)
        return int(result.stdout.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def test_ctrl_break_during_child_startup_exits_at_once_without_a_popup(tmp_path):
    """站主桌面上的弹窗（themistally-15 的实验）：起子进程后立即给它的进程组发 CTRL_BREAK。设了模式的父进程起的子进程
    当场以 0xC0000142 退出，不卡住，系统日志里没有新的事件 26。"""
    code = "\n".join([
        "import json, os, signal, subprocess, sys",
        "sys.path.insert(0, %r)" % str(SCRIPTS),
        "import pi_dispatch",
        "pi_dispatch.quiet_error_mode()",
        "codes = []",
        "for _ in range(5):",
        "    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'],",
        "                             creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)",
        "    try:",
        "        os.kill(child.pid, signal.CTRL_BREAK_EVENT)",
        "    except OSError:",
        "        child.kill()",
        "        child.wait()",
        "        print('NO_CONSOLE')",
        "        sys.exit(0)",
        "    try:",
        "        codes.append(child.wait(timeout=20) & 0xFFFFFFFF)",
        "    except subprocess.TimeoutExpired:",
        "        subprocess.run(['taskkill', '/F', '/T', '/PID', str(child.pid)], capture_output=True)",
        "        codes.append(None)",
        "print(json.dumps(codes))",
    ])
    before = popup_count()
    result = run_fresh([sys.executable, "-c", code], tmp_path)
    output = result.stdout.decode("utf-8", "replace").strip()
    if output == "NO_CONSOLE":
        pytest.skip("本进程没有控制台，发不出 CTRL_BREAK")
    codes = json.loads(output)
    assert None not in codes, codes  # 没有一个卡到超时
    assert STATUS_DLL_INIT_FAILED in codes, [hex(c) for c in codes]  # 确实撞上了初始化中的窗口
    after = popup_count()
    if before is not None and after is not None:
        assert after == before
