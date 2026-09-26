## 离线边界核实

**P0.2，对应文档 6.1。** 核实方式为静态核实，没有运行测试，也没有修改任何文件。只做了几项只读探查：
- 用 shutil.which 定位工具；
- 查询几项 Git 配置，但不列出全部配置；
- 检查文件是否存在；
- 读取 pyc 文件头。

基线：HEAD `a4fa199b0e5bdc658215765ee7558b9fe6723940`。

### 结论

**`python tests/test_dispatch.py` 不会启动真实的 pi。** 但按原样运行，还不满足“真正离线、只用桩”的严格判据，所以 `safe_to_run = false`。原因有两条，都只需在运行时调整环境变量就能消除，不必改文件：
1. `doctor` 会在 PATH 上找到并运行真实的 `claude --version` 和 `codex --version`，共 6 次 doctor，12 次调用。
2. `run` 与 `doctor` 会读取真实的 `~/.pi/agent/settings.json`。本机存在这个文件，代码只记录其中的键名。

按下文“受控运行方式”运行后，可以视为满足判据。

### pi 命令如何解析

- `tests/test_dispatch.py:29` 设置 `BASE_ENV["PI_DISPATCH_PI_CMD"] = [sys.executable, tests/stub_pi.py]`，全文只有这一处。
  - 没有任何测试删除、置空或覆盖它。
  - `tool()` 只能在 BASE_ENV 上新增或覆盖键，不能删除。
  - 1732-1756 行的 `bare`、`named` 环境只去掉 Git 身份变量。
- `resolve_pi_command()`（`pi_dispatch.py:1760-1786`）在变量非空时直接返回它；只有变量缺失或为空时，才用 `shutil.which("pi")` 在 PATH 上查找。
  - 本机这一步会找到 `<HOME>\AppData\Roaming\npm\pi.CMD`，即真实 pi。
  - 测试中走不到这个分支。
- 全文只有三处调用 `resolve_pi_command`：
  - `cmd_run:3277`；
  - `cmd_doctor:4682`；
  - `cmd_smoke:4767`。
- `dispatch.config.json` 没有能覆盖 pi 命令的键。

| 测试中的入口 | 实际走到 | pi 来源 |
|---|---|---|
| `run_ok` 与 `tool(...,"run")`：430、498、501、505、508、1694、1722 行 | 桩预检（--help、--version、--list-models、auth check），然后 run_supervised | 桩 |
| 484 行（已领取）、503 行（PI_EXEC_MODEL 冲突） | 在解析 pi 之前就被拒绝 | 不启动 |
| 337 行（并发预算）、448 行（杀调度器）的 `Popen` | `dict(BASE_ENV, ...)` 保留了变量 | 桩 |
| doctor：715、721、731、737、743、1734 行 | 桩 --version、--help、--list-models、`auth check --no-refresh`，**另有真实 claude/codex --version** | 桩 + 真实 claude/codex |
| 591 行 `doctor --out` 指向证据目录 | `safe_output_path` 先拒绝，不运行任何外部命令 | 不启动 |
| 748 行 smoke | 桩 --version，再在 `pi-smoke-*` 中运行两步 | 桩 |
| 713 行 Git Bash 包装脚本 `validate` | validate 与 derive-json 不解析 pi | 不启动 |
| 656-698 行（唯一改写 PATH 的测试） | Windows 上在 658 行直接 return | 不执行 |
| 测试进程内的 `pd.*` 调用 | 都是纯函数、git 或文件读写，不涉及 pi | 不启动 |

### 网络

- 测试、桩与调度器源码都不导入网络模块。
- git 只用本地子命令，没有 clone、fetch、push、remote。调度器的 git 调用固定 `core.fsmonitor=false`。测试仓库没有 remote。
- 桩中出现的 `git push`、`/tmp`、`mktemp` 命令只是写出的事件字符串，不会执行。
- **疑点**：真实的 claude、codex `--version` 是否联网，无法从本仓库证明。

### 凭据

- 不读取 `auth.json`、`models.json`、`~/.ssh` 等凭据文件；测试中出现的令牌都是合成值。
- 会读取 `~/.pi/agent/settings.json`，只记录顶层键名。
- 会探测 `~/.pi/agent` 下的 AGENTS.md、SYSTEM.md，以及 `bin/rg`、`bin/fd` 是否存在。本机只有 settings.json、`bin/rg.exe`、`bin/fd.exe` 存在；worktree 的各级上级目录中没有 AGENTS.md 或 CLAUDE.md。
- `BASE_ENV` 把运行者的全部环境变量传给所有子进程，但没有找到任何打印或写出变量值的路径。

### 写入位置

- 写入本仓库的只有 `scripts/__pycache__/pi_dispatch.cpython-312.pyc`。
  - 由测试进程内的 `import pi_dispatch` 产生；
  - 当前 pyc 与源码的 mtime、size 一致，按现状不会重写；
  - 该目录已被 .gitignore 忽略。
- 其余写入都在 `%TEMP%\pi-dispatch-e2e-*`（即 WORK）内，结束时删除：
  - worktree、fresh、baseline、mutate 的工作区都在 `WORK/worktrees` 下；
  - 链接与 junction 都指向 WORK 内部。
- 例外是 smoke 的 `%TEMP%\pi-smoke-*`：它在 WORK 之外，失败时会残留。
- Git 只改临时仓库的本地配置。

### 后台进程与残余风险

- test_timeout 与 test_dispatcher_killed 的 hang 场景各会产生一个 `python sleep(600)` 的孙进程，由 Job Object 回收。
- `test_dispatcher_killed`（471-472 行）与 `test_timeout`（440 行）会对**已经结束**的 PID 无条件执行 `taskkill /PID <pid> /F /T`。PID 被复用时可能误杀无关的进程树。概率低，不列为阻断项。
- 如果 30 秒内等不到 pid 文件，这个调度器会留在后台，最长 600 秒。

### 所需工具

- Python 3.12.10，只用标准库；
- git；
- `C:\Program Files\Git\bin\bash.exe`；
- tasklist 与 taskkill。

不需要 node、真实 pi 或网络。

### 受控运行方式（规划端取证时使用）

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PI_CODING_AGENT_DIR = (New-Item -ItemType Directory -Force (Join-Path $env:TEMP 'pi-e2e-empty-agent')).FullName
$env:Path = ($env:Path -split ';' | Where-Object { $_ -notmatch '\\AppData\\Roaming\\npm\\?$' -and $_ -notmatch '\\\.local\\bin\\?$' }) -join ';'
python -c "import shutil; print([shutil.which(n) for n in ('pi','claude','codex')], shutil.which('git'))"   # 期望 [None, None, None] 与 git 路径
python -B tests/test_dispatch.py
```

去掉 PATH 中的两个目录后，doctor 只会多出“PATH 中没有 claude 或 codex”“未找到 rg/fd”之类的 notes，没有任何断言依赖它们。另一个好处是：万一 `PI_DISPATCH_PI_CMD` 丢失，调度器会报“PATH 中找不到 pi”并失败，而不会启动真实 pi。