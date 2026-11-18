"""全量 pytest 的公共设置。

前端的门禁测试把 ``npm ci``、``npm run build``、Vitest 这些慢步骤放在名为 ``pipeline`` 的会话级夹具里：
跑一次十几分钟，还要联网装依赖。全量 pytest 默认跳过用到这个夹具的用例（T002 结项时站主 Q6），
其余用例（读源码、读画布、跑契约检查脚本）照常跑。

下面两种情况照常跑：
- 命令行点名了用例所在的文件：合同的门禁检查（``python -m pytest tests/test_gate_t002_baseline.py -q``）、
  内核的战后白盒测试都是点名运行；
- 设了环境变量 ``TT_FRONTEND_TESTS=1``。

全量回归一次点名几十份门禁时，同一棵树上它们的流水线各自重装依赖、重跑整套 Vitest，结果都一样：``memo_gate_runs`` 让这两样在一个会话里只真跑一次（第 186 轮）。

门禁基准交给 ``re.*`` 的正则字面量，收集时先各编译一遍，编译不过的那份门禁收集失败（``GateModule``，第 193 轮）。
"""

import ast
import hashlib
import inspect
import os
import re
import sys
import warnings
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


#: 第 193 轮（候选 #72）：T054 的门禁把 r"\bxit\(" 写成了 r"\xit\("，编译不过。被扫的新文件在基线上还不存在，那条分支
#: 走不到，基线检查照样算“在断言上失败”；执行端跑完 50 分钟才红在这一处，又搭进一轮热修补。内核收门禁时跑的
#: pytest --collect-only（accept_gate_pre）会把收集失败当场挡回门禁端。认的是 re.* 的第一个参数：字符串常量；名字，
#: 由外层 for、推导式从字面量元组、列表里取出（拆包也认，被遍历的也可以是模块级的字面量），或是模块级的字符串。
#: 名字在所在函数里另有绑定（参数、赋值）的不认；flags 认不得的不编（re.X 改变写法的含义）；f-string、拼接不管。
_RE_FLAG_AT = {"compile": 1, "search": 2, "match": 2, "fullmatch": 2, "findall": 2, "finditer": 2, "split": 3,
               "sub": 4, "subn": 4}
_RE_FLAGS = {"A", "ASCII", "I", "IGNORECASE", "M", "MULTILINE", "S", "DOTALL", "U", "UNICODE", "X", "VERBOSE"}


def regex_literal_problems(source: str) -> list:
    """源码里交给 re.* 却编译不过的正则字面量，按行号排，每处一行：行号、照源码的写法、re 的报错。
    只用 ASCII：内核与调度器起的 pytest 输出是 cp1252，报错里有一个字编不了码，pytest 就把整段转成 \\uXXXX
    （换行、反斜杠一起转），门禁读到的 r"\\xit\\(" 会变成两个反斜杠。"""
    tree = ast.parse(source)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    module = _module_values(tree)
    problems = {}
    for call in ast.walk(tree):
        flags = _re_call_flags(call)
        if flags is None:
            continue
        first = call.args[0]
        if isinstance(first, ast.Name):
            literals = _bound_literals(first.id, call, parents, module)
        else:
            literals = [first] if _is_string(first) else []
        for literal in literals:
            error = _compile_error(literal.value, flags)
            if error:
                written = ast.get_source_segment(source, literal) or repr(literal.value)
                problems[(literal.lineno, literal.col_offset)] = "line %d %s: %s" % (literal.lineno, written, error)
    return [problems[key] for key in sorted(problems)]


def _re_call_flags(node):
    """node 是 re.<函数>(模式, …) 时给 flags 的值；不是这样的调用，或 flags 认不得，给 None。"""
    if not (isinstance(node, ast.Call) and node.args and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "re" and node.func.attr in _RE_FLAG_AT):
        return None
    at = _RE_FLAG_AT[node.func.attr]
    given = [keyword.value for keyword in node.keywords if keyword.arg == "flags"] + node.args[at:at + 1]
    return _flag_value(given[0]) if given else 0


def _flag_value(node):
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "re" \
            and node.attr in _RE_FLAGS:
        return int(getattr(re, node.attr))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left, right = _flag_value(node.left), _flag_value(node.right)
        return None if left is None or right is None else left | right
    return None


def _strings(node, index=None):
    """字面量元组、列表里的字符串常量；给了 index 就取每个内层元组、列表的第 index 项。"""
    items = node.elts if isinstance(node, (ast.Tuple, ast.List)) else []
    if index is not None:
        items = [item.elts[index] for item in items if isinstance(item, (ast.Tuple, ast.List)) and len(item.elts) > index]
    return [item for item in items if _is_string(item)]


def _is_string(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _module_values(tree):
    """模块级的“名字 = 值”。同名的取最后一次：用例跑起来时模块早已导入完。"""
    return {stmt.targets[0].id: stmt.value for stmt in tree.body
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)}


def _bound_literals(name, call, parents, module):
    """名字 name 在 call 处取得到的字符串常量；认不出给空。"""
    node = call
    while node in parents:
        node = parents[node]
        for loop in [node] if isinstance(node, ast.For) else getattr(node, "generators", []):
            found = _loop_literals(name, loop, module)
            if found is not None:
                return found
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and _binds(node, name):
            return []
    value = module.get(name)
    return [value] if _is_string(value) else []


def _loop_literals(name, loop, module):
    """for 或推导式的一层把 name 当循环变量（或拆包的一项）时，它从字面量里取到的字符串常量；不是循环变量给 None。"""
    iterable = module.get(loop.iter.id) if isinstance(loop.iter, ast.Name) else loop.iter
    if isinstance(loop.target, ast.Name):
        return _strings(iterable) if loop.target.id == name else None
    parts = loop.target.elts if isinstance(loop.target, ast.Tuple) else []
    for index, part in enumerate(parts):
        if isinstance(part, ast.Name) and part.id == name:
            return _strings(iterable, index)
    return None


def _binds(function, name):
    """name 是 function 的参数，或在 function 里被赋值过。"""
    args = function.args
    params = args.posonlyargs + args.args + args.kwonlyargs + [arg for arg in (args.vararg, args.kwarg) if arg]
    return any(arg.arg == name for arg in params) or any(
        isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == name for node in ast.walk(function))


def _compile_error(pattern, flags):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # “可能是嵌套集合”之类的 FutureWarning 不算编译不过
        try:
            re.compile(pattern, flags)
        except re.error as exc:
            return str(exc)
    return None


class GateModule(pytest.Module):
    """门禁基准模块：导入之前先把交给 re.* 的正则字面量各编译一遍。"""

    def collect(self):
        try:
            problems = regex_literal_problems(self.path.read_text(encoding="utf-8"))
        except (SyntaxError, ValueError):
            problems = []  # 照常导入，语法、编码错误由 pytest 自己报
        if problems:
            raise self.CollectError("regex literal handed to re.* does not compile (tests/conftest.py compiles them "
                                    "at collection, round 193):\n" + "\n".join(problems))
        return super().collect()


def pytest_pycollect_makemodule(module_path, parent):
    if _GATE_FILE.search(module_path.name):
        return GateModule.from_parent(parent, path=module_path)
    return None
