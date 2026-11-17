"""全量 pytest 的公共设置。

前端的门禁测试把 ``npm ci``、``npm run build``、Vitest 这些慢步骤放在名为 ``pipeline`` 的会话级夹具里：
跑一次十几分钟，还要联网装依赖。全量 pytest 默认跳过用到这个夹具的用例（T002 结项时站主 Q6），
其余用例（读源码、读画布、跑契约检查脚本）照常跑。

下面两种情况照常跑：
- 命令行点名了用例所在的文件：合同的门禁检查（``python -m pytest tests/test_gate_t002_baseline.py -q``）、
  内核的战后白盒测试都是点名运行；
- 设了环境变量 ``TT_FRONTEND_TESTS=1``。

全量回归一次点名几十份门禁时，同一棵树上它们的流水线各自重装依赖、重跑整套 Vitest，结果都一样：``memo_gate_runs`` 让这两样在一个会话里只真跑一次（第 186 轮）。
"""

import hashlib
import inspect
import os
import re
import sys
from pathlib import Path

import pytest

SLOW_FIXTURE = "pipeline"

if os.name == "nt":
    # 跑测试时起的子进程都继承这个错误模式（与 pi_dispatch.QUIET_ERROR_MODE 相同，第 123 轮）：还在初始化时就收到
    # CTRL_BREAK 的子进程当场以 0xC0000142 退出，不弹“Application Error”硬错误框、不卡到有人点确定
    import ctypes

    ctypes.windll.kernel32.SetErrorMode(ctypes.windll.kernel32.GetErrorMode() | 0x8003)


@pytest.fixture(autouse=True)
def python_kernel_impl(request, monkeypatch, tmp_path_factory):
    """进程内调 ``pd.main`` 的用例测的是 Python 实现：选择文件（scripts/kernel-impl.json）钉成“不存在”，等于全部
    python，不随提交的选择文件把 status、logs 转交给 TS。TS 子进程的输出不经 redirect_stdout，没装依赖的临时
    worktree（门禁回归、落地预演）里也起不来。TS 与 Python 的对等由 ts/ 的契约测试与 tests/test_kernel_impl.py 的
    端到端覆盖；test_kernel_impl.py 自己管选择文件，不钉。子进程里跑的 ``scripts/pi_dispatch.py`` 读真的选择文件。"""
    module = sys.modules.get("pi_dispatch")
    if module is None or request.path.name == "test_kernel_impl.py":
        return
    monkeypatch.setattr(module, "KERNEL_IMPL_PATH", tmp_path_factory.getbasetemp() / "no-kernel-impl.json")


@pytest.fixture(autouse=True)
def no_ambient_quizs(monkeypatch):
    """测试不看这台机器上线用的 QUIZS_*（协调人走 quizs 之后设在用户级环境变量里，第 145 轮）：要用的用例自己设。
    不清掉的话，名册里的协调人在测试里会真的去找 Quizs 与证书，结果随机器、随证书到没到期而变（第 148 轮在设了
    这些变量的新会话里跑才发现）。子进程继承的也是清过的环境。"""
    for name in ("QUIZS_CMD", "QUIZS_LIVE_PLAN", "QUIZS_PROVIDER_PROFILE", "QUIZS_QUALIFICATION"):
        monkeypatch.delenv(name, raising=False)


#: 第 186 轮：全量回归（R01）一次点名四十多份门禁（T048 的 47 份 1748 秒，每份约 37 秒），同一棵树上 31 份各跑一遍整套
#: `npm test`（约 20 秒）、18 份老门禁不看 node_modules 在不在就 `npm ci`（删掉重装），结果都一样。门禁文件冻着，这里给
#: 门禁模块的 run_capture 包一层（签名是 argv、cwd、timeout、env 的那 31 份），同一会话里：
#: - `npm ci`：上一遍成功，package.json、锁文件与 node_modules/.package-lock.json 都还是那一遍之后的样子，照它的结果、不重装；
#: - 整套 `npm test`（argv 只有 npm 与 test，探针带着文件名不算）：cwd、环境与 cwd 下的文件（node_modules、dist 除外，
#:   被 git 忽略的探针目录照算）都和上一遍开跑时一样，照它的结果；上一遍用时超过这一份的时限照旧真跑。
#: 超时的不记。`npm run build` 会重写 dist，照旧每份真跑。设 TT_GATE_MEMO=0 关掉，设 TT_GATE_MEMO_LOG=<文件> 记下每次判定。
_GATE_MEMO = {}
_GATE_FILE = re.compile(r"test_gate_t\d+_baseline\.py$")
_MEMO_SKIP_DIRS = {"node_modules", "dist", ".vite", "coverage"}


def _file_digest(path: Path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _install_stamp(cwd) -> tuple:
    try:
        stat = (Path(cwd) / "node_modules" / ".package-lock.json").stat()
    except OSError:
        return ()
    return (stat.st_size, stat.st_mtime_ns)


def _tree_state(cwd) -> str:
    """cwd 下每个文件的相对路径、大小与修改时刻（node_modules、dist 这类产物目录除外）。"""
    digest = hashlib.sha256()
    for folder, dirs, files in os.walk(cwd):
        dirs[:] = sorted(name for name in dirs if name not in _MEMO_SKIP_DIRS)
        for name in sorted(files):
            full = os.path.join(folder, name)
            try:
                stat = os.stat(full)
            except OSError:
                continue
            digest.update(("%s|%d|%d\n" % (os.path.relpath(full, cwd), stat.st_size, stat.st_mtime_ns))
                          .encode("utf-8", "surrogateescape"))
    return digest.hexdigest()


def _memo_log(reuse: bool, key: tuple, timeout) -> None:
    """设了 TT_GATE_MEMO_LOG（一个文件）时追加这一次的判定与键（环境只记哈希）：省不下时间时看是键的哪一样对不上。
    第一遍实测就是靠它查出 PYTEST_CURRENT_TEST 让环境永远对不上。"""
    target = os.environ.get("TT_GATE_MEMO_LOG")
    if target:
        with open(target, "a", encoding="utf-8") as log:
            log.write("%s %s timeout=%s %s\n" % ("hit" if reuse else "miss", key[0], timeout,
                                                 " ".join(str(part)[:16] for part in key[2:])))


def _memoized(original):
    def run_capture(argv, cwd, timeout, env=None):
        words = [str(item) for item in argv[1:]]
        if not argv or Path(str(argv[0])).stem.lower() != "npm" or words not in (["ci"], ["test"]):
            return original(argv, cwd, timeout, env)
        # pytest 每条用例都改写 PYTEST_CURRENT_TEST，门禁传的环境是 os.environ 的副本，带着它就永远对不上
        # （第一遍实测开没开一样：48 份 1558 秒对 1548 秒）
        environment = {name: value for name, value in (env if env is not None else os.environ).items()
                       if name != "PYTEST_CURRENT_TEST"}
        key = (words[0], str(Path(cwd).resolve()),
               hashlib.sha256(repr(sorted(environment.items())).encode("utf-8", "surrogateescape")).hexdigest())
        if words == ["ci"]:
            key += (_file_digest(Path(cwd) / "package.json"), _file_digest(Path(cwd) / "package-lock.json"))
            hit = _GATE_MEMO.get(key)
            reuse = bool(hit and hit["stamp"] and hit["stamp"] == _install_stamp(cwd))
            _memo_log(reuse, key, timeout)
            if reuse:
                return hit["result"]
            result = original(argv, cwd, timeout, env)
            if result[0] == 0 and not result[1]:
                _GATE_MEMO[key] = {"stamp": _install_stamp(cwd), "result": result}
            return result
        key += (_tree_state(cwd), _install_stamp(cwd))
        hit = _GATE_MEMO.get(key)
        reuse = bool(hit and hit["result"][3] <= timeout)
        _memo_log(reuse, key, timeout)
        if reuse:
            return hit["result"]
        result = original(argv, cwd, timeout, env)
        if not result[1]:
            _GATE_MEMO[key] = {"result": result}
        return result

    run_capture.__wrapped__ = original
    return run_capture


def memo_gate_runs() -> int:
    """给已经导入的门禁模块的 run_capture 包上 _memoized，返回包了几份。签名不是 argv、cwd、timeout、env 的不动。"""
    wrapped = 0
    for module in list(sys.modules.values()):
        source = getattr(module, "__file__", None) or ""
        function = getattr(module, "run_capture", None)
        if not _GATE_FILE.search(source.replace("\\", "/")) or not callable(function) or hasattr(function, "__wrapped__"):
            continue
        if list(inspect.signature(function).parameters) != ["argv", "cwd", "timeout", "env"]:
            continue
        module.run_capture = _memoized(function)
        wrapped += 1
    return wrapped


def named_files(config: pytest.Config) -> set:
    """命令行里点名的测试文件（去掉 ``::用例`` 部分；目录不算点名）。"""
    files = set()
    for arg in config.args:
        path = Path(str(arg).split("::", 1)[0])
        if not path.is_absolute():
            path = Path(config.invocation_params.dir) / path
        if path.is_file():
            files.add(path.resolve())
    return files


def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:
    if os.environ.get("TT_GATE_MEMO") != "0":
        memo_gate_runs()
    if os.environ.get("TT_FRONTEND_TESTS") == "1":
        return
    named = named_files(config)
    skip = pytest.mark.skip(reason="前端流水线（npm ci、build、Vitest）在全量 pytest 里默认跳过："
                                   "点名运行这个文件，或设 TT_FRONTEND_TESTS=1")
    for item in items:
        if SLOW_FIXTURE in getattr(item, "fixturenames", ()) and Path(str(item.path)).resolve() not in named:
            item.add_marker(skip)
