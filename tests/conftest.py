"""全量 pytest 的公共设置。

前端的门禁测试把 ``npm ci``、``npm run build``、Vitest 这些慢步骤放在名为 ``pipeline`` 的会话级夹具里：
跑一次十几分钟，还要联网装依赖。全量 pytest 默认跳过用到这个夹具的用例（T002 结项时站主 Q6），
其余用例（读源码、读画布、跑契约检查脚本）照常跑。

下面两种情况照常跑：
- 命令行点名了用例所在的文件：合同的门禁检查（``python -m pytest tests/test_gate_t002_baseline.py -q``）、
  内核的战后白盒测试都是点名运行；
- 设了环境变量 ``TT_FRONTEND_TESTS=1``。
"""

import os
import sys
from pathlib import Path

import pytest

SLOW_FIXTURE = "pipeline"


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
    if os.environ.get("TT_FRONTEND_TESTS") == "1":
        return
    named = named_files(config)
    skip = pytest.mark.skip(reason="前端流水线（npm ci、build、Vitest）在全量 pytest 里默认跳过："
                                   "点名运行这个文件，或设 TT_FRONTEND_TESTS=1")
    for item in items:
        if SLOW_FIXTURE in getattr(item, "fixturenames", ()) and Path(str(item.path)).resolve() not in named:
            item.add_marker(skip)
