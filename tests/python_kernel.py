"""起真调度器子进程、只测 Python 实现的测试用（TS 迁移计划 D5）。

选择文件（scripts/kernel-impl.json）选了 ts 的命令，子进程里的 scripts/pi_dispatch.py 会转交 TS；没装 TS 依赖的工作树
（执行端的 worktree、check --fresh 的干净副本、门禁的 pre/post 工作区、新建的临时 worktree）里只会报“TS 实现没装好”。
script() 写一个不带选择文件的 kit：只有一个 pi_dispatch.py，加载真的 scripts/pi_dispatch.py，把选择文件指向自己旁边
（不放就不存在，等于全部 python）。不加内核开关；TS 那一侧由 ts/ 的契约测试与装了依赖的全量运行覆盖。

包装把 sys.path[0] 换成 scripts/：与直接运行 scripts/pi_dispatch.py 时一样，自己所在的目录不参与 import。
"""
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

WRAPPER = """import sys
sys.path[0] = {scripts!r}
import pi_dispatch as pd
pd.KERNEL_IMPL_PATH = pd.Path(__file__).resolve().with_name("kernel-impl.json")
sys.exit(pd.main())
"""


def script(directory: Path) -> Path:
    """directory/pi_dispatch.py：经它起的调度器读 directory/kernel-impl.json。"""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "pi_dispatch.py"
    path.write_text(WRAPPER.format(scripts=str(SCRIPTS)), encoding="utf-8")
    return path
