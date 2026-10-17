# 05 三平台命令与入口

状态：拟议实施说明，尚未实现；不是已审核合同，不授权安装依赖、修改 CI 或启动模型。
总纲：[完整设计](../themis-tally-v2-design.md)；导航：[实施索引](README.md)。
对应总设计：第 5、9 节及 P2。

## 1. 目标与非目标

让同一调度核心在 Linux、macOS、Windows 原生环境执行明确的平台命令。
将操作系统、用户 shell、CLI 工具能力分别探测，保留可追溯的环境锁和退出语义。
无 shell 需求的命令直接运行 argv，确有需求时显式声明 shell 和平台实现。
不自动翻译 Bash/PowerShell 脚本，不把 WSL 与原生 Windows 混为同一个运行环境。
不承诺 POSIX 平台在调度器被强杀后清掉所有后代；首期提供检测及恢复说明。
不通过 `shell=True` 普遍兼容不安全字符串，也不把模型输出当可展开的命令模板。

## 2. 依赖与输入输出

前置依赖：[04 CLI 适配器](04-cli-adapters-and-pi.md)，复用 01 协议及 02 配置结果。
输入：Invocation 或合同检查定义、目标平台、工作目录、过滤后的环境、时限与取消信号。
输出：已解析的命令/工具信息、执行日志、退出码、超时/取消/启动错误及进程清理证据。
平台枚举固定为 `linux`、`macos`、`windows`，shell 名称与版本是单独字段。
环境锁记录实际入口、版本、路径和工具能力；机器路径不计入配置语义锁。
命令渲染文本供审核阅读，执行源仍是机器合同中已审核并锁定的结构。

## 3. 现状与复用点

`run_supervised` 已提供执行监督，`_WinJob`、`_terminate_tree` 分别涉及 Windows/POSIX 清理。
`_run_command_item` 和 `_resolve_argv` 已处理 argv、工作目录、日志、超时和退出码。
`scripts/dispatch-pi.sh` 已转发参数、探测 Python，并考虑 macOS Bash 3.2 空数组行为。
当前缺少中立 Python/PowerShell 入口、合同平台变体和显式 shell 结构。
现有 Windows npm shim 的特殊字符检查应保留，优先使用已核验的 native/node 入口。
现有进程管理是复用起点；Linux/macOS/Windows 的真实运行验证不能由单平台 mock 替代。

## 4. 接口和行为约束

### 4.1 合同命令模型

共同字段包括 `id`、`required`、`cwd`、`timeout_seconds`、`expected_exit_code` 及输出断言。
执行载体必须是非空 `argv`，或成对的 `{shell, script}`，两者互斥。
可用 `by_platform` 提供完整执行载体；不得把 `required` 等共同语义藏进变体覆盖。
通用命令或目标平台变体必须恰好选出一份，缺实现或选择冲突就阻塞。
所有声明支持的平台都须在检查集合锁定前验证覆盖，缺平台不能记为跳过后通过。
下面是拟议形状，实际测试路径和 Python 入口在实施合同时确定：

```json
{
  "id": "V01",
  "required": true,
  "cwd": ".",
  "timeout_seconds": 300,
  "expected_exit_code": 0,
  "by_platform": {
    "linux": {"argv": ["python3", "-m", "pytest", "tests"]},
    "macos": {"argv": ["python3", "-m", "pytest", "tests"]},
    "windows": {"argv": ["py", "-3", "-m", "pytest", "tests"]}
  }
}
```

路径读写与简单文件操作优先采用 Python/pathlib，不因平台不同生成易错的删除命令串。
`cwd` 必须解析后位于对应工作副本内；相对路径、链接及大小写规则使用平台真实语义核验。
环境增量通过既有白名单/过滤逻辑传递，日志不打印完整环境变量或凭据。
平台命令展示由同一机器定义生成，MD/JSON 不得各维护一份可漂移的命令。

### 4.2 Shell 与入口

| 环境 | 调度入口 | 声明和核验重点 |
|---|---|---|
| Linux | `python3 scripts/dispatch.py`；可选 `.sh` | Bash/zsh 的真实路径和版本、信号与进程组 |
| macOS | 同上；`.sh` 兼容旧 Bash 场景 | 默认 zsh 不等于执行所有脚本用 zsh；系统工具差异 |
| Windows | `py -3 scripts/dispatch.py` 或 Python；`.ps1` | PowerShell 7/Windows PowerShell 区分，cmd 显式选择 |

新增 `.sh/.ps1` 只探测所需解释器、转发参数和退出码，不重复业务逻辑。
PowerShell wrapper 原样传播外部程序 `$LASTEXITCODE`，包括 `wait` 的退出码 3。
shell 脚本作为受控文件或明确参数交给指定解释器，不经过另一层未经声明的 shell。
指定 shell 缺失或版本不符时明确阻塞，不静默替换为另一种语法。
`.cmd/.bat` 保持参数限制，优先解析到安全 native/node 入口；拒绝无法可靠传递的参数。
CLI 内部工具可能仍要求 Bash；原生调度器可运行不等于该 CLI 在无 Bash 环境可执行所有任务。
WSL 作为独立 Linux 环境预检，不能在同一个 attempt 自动混用两套 Git、Python 和路径。

### 4.3 参数和进程监督

argv 逐项保留边界；空字符串、空格、中文、引号和特殊字符必须通过专门子进程回显验证。
shell 脚本测试分开覆盖语法错误与其中程序非零退出，不混淆为同一种成功/失败。
日志记录调用形式、解析的入口、目标平台和所用 shell 版本，区分原始退出码与调度状态。
启动失败、自然非零退出、超时和用户取消分别记录，不能统一填一个“失败”而丢失原因。
正常超时/取消沿用 Windows Job Object 与 POSIX 进程组清理，并核对后代进程状态。
调度器强杀是另一个故障类别：Windows Job 行为单测/实测，POSIX 残留检测单独验收。
Linux 父死亡信号不等于所有后代回收；需要更强保证时另行设计外部 supervisor。
重启恢复不自动对未知 PID 杀进程，须校验运行标识与进程身份，避免 PID 复用误伤。

## 5. 预计文件范围

- 新增 `scripts/dispatch.py`、`scripts/dispatch.sh`、`scripts/dispatch.ps1` 中立入口。
- 提取 `scripts/codekit/process.py`、`platforms.py`，复用现有进程监督和 argv 逻辑。
- 保留 `scripts/pi_dispatch.py`、`scripts/dispatch-pi.sh` 兼容入口。
- 扩展命令 schema、合同 Markdown 渲染及平台相关离线/原生测试。
- 更新环境文档、入口说明和源技能；需要 CI 变更时另列获准范围。

当前 AGENTS 对执行器仍含 POSIX 临时目录写法，规则迁移需同步提供明确平台行为。
规则、源技能与受保护核心的改动由主模型在后续实施授权下直接处理，不能令执行器自行突破。

## 6. 实施步骤

1. 保留现有进程/argv 回归，确定新命令模型和三平台覆盖规则。
2. 先实现中立 Python 入口和薄 wrapper，再加入显式 shell、平台选择及一致渲染。
3. 接入 04 Invocation，区分调度 shell 与 CLI 工具 shell 的预检结果。
4. 用无网络子进程测试引号、Unicode、退出码、超时/取消和恢复标识。
5. 在三平台原生环境执行同套核心场景，记录真实平台/工具版本与未覆盖项目。
6. 后续获准真实调用后验证 CLI/平台组合；未测组合保留“未验证”而非推定支持。

## 7. 验收标准

- **05-A01**：原生 Windows 无 Bash 可跑中立入口、argv 检查和 stub 调度流程。
- **05-A02**：Linux/macOS 原生跑通同套核心场景；缺机器时明确标为未验收。
- **05-A03**：argv 与 shell 互斥、平台缺失、变体覆盖共同语义均在运行前拒绝。
- **05-A04**：空格、中文、引号、空参数、特殊字符往返一致；不安全 shim 参数被拒绝。
- **05-A05**：wrapper 保持程序非零退出和 `wait=3`；语法错误与程序失败留下准确记录。
- **05-A06**：正常超时/取消回收受监督进程树，保留超时、取消和清理状态证据。
- **05-A07**：调度器强杀单独验证；POSIX 潜在残留有检测/恢复说明，无全回收虚假承诺。
- **05-A08**：Windows/WSL 混合路径与环境被拒绝；切换环境需要新锁和预检。
- **05-A09**：机器合同与 Markdown 命令展示同源，CRLF/Unicode 不改变 argv 参数边界。
- **05-A10**：缺 CLI 内部必需 shell 时明确阻塞该用途，不因调度器可运行就报告完整支持。

## 8. 兼容与恢复

旧 argv 合同保持语义，新 shell/平台结构仅由新版 schema 解释。
保留旧包装入口参数和退出码，不要求用户一次性替换所有脚本路径。
执行中断保留证据与工作目录，恢复先确认进程状态，再由明确的新动作重跑检查。
平台变更或路径解析漂移后重新预检，不使用另一平台的通过记录冒充本次验证。
回退入口不自动改合同版本、清理旧证据或安装所缺 shell。

## 9. 后续合同拆分建议

1. **入口与 argv**：Python/PowerShell/Bash 薄入口、退出码和参数边界。
2. **命令模型**：平台变体、显式 shell、共同语义限制与同源渲染。
3. **进程与恢复**：超时/取消、强杀证据、残留识别和三平台原生矩阵。
4. **规则与文档迁移**：平台操作说明、临时目录规则、技能入口及兼容说明。

每包正式实施前需明确基线、范围、授权和可用平台；离线测试不能替代原生验收。
