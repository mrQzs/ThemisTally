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
from pathlib import Path

import pytest

SLOW_FIXTURE = "pipeline"


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
