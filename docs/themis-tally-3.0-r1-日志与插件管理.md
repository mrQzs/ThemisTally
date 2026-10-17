# Themis Tally 3.0 第一轮设计：日志管理与插件管理的第一片

状态：2gate 闸一审核中（第 2 轮送审稿）。本文是第一轮的实现设计，审到零 Blocking 才进入实现。

- 分支：`themis-3.0`（本地，不推送）。起点 `8fb12ed`（master），之上是设计说明提交 `0f4879c` 与本文的历次提交。
- 上位设计：`docs/themis-tally-3.0-四端分层解耦架构.md` 第 8.2 节（日志管理）、8.3 节（插件管理）、13 节（首轮实战）。
- 下文 `file:line` 都在 `8fb12ed` 上核对过。

## 0. 审核变更对照表

| 编号 | 第 1 轮结论 | 本稿处置 |
|---|---|---|
| r1-B1 | Blocking：D4 的“第一条”在多文件、乱序输入下不确定，窗口结果随读取顺序变化；同 id 的 `model`、`isSidechain` 不一致没有规则 | D4 改为“先全局去重与判冲突，再按窗口过滤”；代表时间取同 id 所有有效时间的最小值；同 id 的四项计数、`model`、`isSidechain` 必须全部相同，否则算冲突；L4、L5 合并为置换测试 L4 |
| r1-B2 | Blocking：D6 对全集合跑 `resolve_plugins`，任何一个坏插件都会让 `disable`（包括 `disable decisions`）失败；`resolve_plugins` 校验传入注册表里的每个 manifest（`plugins.py:242`） | D6 不再调用 `resolve_plugins`；`disable` 不校验任何其他插件，只要求目录存在；`enable` 只校验 X 自己；带 `depends_on` 或 `conflicts` 的插件本轮一律不能启用（现有 8 个插件全部为空）。补 P11、P12 |
| r1-B3 | Blocking：§2.1 说 `resolve_run_dir` 保证结果在 runs 之内，不实：task-id 分支直接返回 `attempts[-1].resolve()`（`pi_dispatch.py:3224`），`task_attempts` 用 `is_dir()` 跟随链接（`pi_dispatch.py:3137`） | 更正 §2.1；`logs` 不再复用 `resolve_run_dir` 与 `task_attempts`，改为自己逐级检查链接与 junction（沿用 `kit_install.py:92-112` 的做法）并检查边界；L12、L13 覆盖 task-id、版本 ID、显式路径与 junction。调度器自身的这个缺口记入 §6，另立任务 |
| r1-S1 | Should-fix：单插件 `validate_lock` 在有依赖时因注册表缺依赖而失败（`plugins.py:365-366`），与 D6 的依赖支持不兼容 | 采纳：本轮不支持带依赖或互斥的插件（D5、D6），`list` / `verify` 把它们报为“本轮不支持”，不调用会失败的组合 |
| r1-S2 | Should-fix：D5 只核对锁里的资源，`decisions/questions/` 下多出的题库文件会被报成一致，运行时却是 `battery_drift`（`decisions.py:339-340`） | 采纳：对 `decisions` 另调用 `verify_battery_lock`（D5）；补 P2 的“多出题库文件”用例 |
| r1-S3 | Should-fix：解析出错或流被截断时，摘要仍写出全零 usage（`pi_dispatch.py:2713`、`2742-2745`），D3 会当成已知的零 | 采纳：`complete` 为假、`truncated` 为真或 `parse_error_lines` 非空时，这个 attempt 记为“部分”，计入下界并单独计数（D3）；补 L7 |
| r1-S4 | Should-fix：`enabled: null` 这类非列表旧值的处理没闭合 | 采纳：D7 拒绝非列表值并给出修复提示（`config unset plugins.enabled` 表示不限制）；D6 遇到非列表值同样拒绝并给同一提示，不做隐式规范化；补 C2、P13 |
| r1-S5 | Should-fix：外部运行（README 方式一）有 8 个插件，装进目标仓库后只发放 `plugins/decisions/**`（`pi_dispatch.py:94-98`、`kit_install.py:196`），D7 的“必须已安装”会让同一份配置在安装后失效 | 采纳：D7 只校验格式，不校验是否安装；“列入但未安装”由 `plugins list` / `verify` 报告（verify 退出码 1）；§2.3 写明两种布局的插件差异；W2 改为在真正安装出来的目标仓库里运行插件命令 |
| r1-S6 | Should-fix：只查资源文件本身不够，插件根目录或中间目录是 junction 时 `resolve()` 后仍会“落在插件目录内” | 采纳：从 `KIT_ROOT/plugins` 往下每一级都查链接与 junction，并使用 `validate_lock` 返回的规范化路径（D5）；补 P5 |
| r1-S7 | Should-fix：D10 漏掉 `ProtocolError`、`PluginError`（都是 `ValueError` 子类，`protocols.py:228`、`plugins.py:30`）与 `OSError` | 采纳：逐插件、逐文件收集 `ValueError` 与 `OSError`，不中断其余项；`verify` 有问题时退出码 1；不输出堆栈（D10） |
| r1-S8 | Should-fix：转发的子解析器默认带帮助，`plugins --help` 被外层 argparse 截走（`pi_dispatch.py:7502-7503`），W1 测不出转发是否生效 | 采纳：两个子解析器 `add_help=False`（D8）；W1 改为真实转发调用，断言下游收到的参数、`repo` 与退出码 |
| 自查 | 本会话调用的 advisor 没有出现在会话记录的 usage 里（全部 174 条 usage 记录的模型都是主模型） | D4 写明：规划端用量只覆盖会话记录里有的调用，是下界 |

## 1. 范围

### 1.1 本轮交付

1. **`logs` 第一片**：新文件 `scripts/kit_logs.py`，子命令 `list`、`show`、`search`、`usage`，全部只读。`usage` 第一次把规划端用量（宿主会话记录）与执行端用量（Pi 运行证据）放在一起按 token 汇总。
2. **`plugins` 第一片**：新文件 `scripts/kit_plugins.py`，子命令 `list`、`show`、`verify`、`enable`、`disable`。前三个只读；后两个只改 `.agent/dispatch.config.json` 的 `plugins` 键。
3. **`kit_config` 补上 `plugins` 键**：现在 `plugins` 被 `codekit/decisions.py` 读取，却不在配置管理器的已知键里（2.3）。
4. **接入**：调度器转发 `logs`、`plugins` 两个子命令，两个新文件加入 `KIT_LOADED_FILES` 受保护；同步测试、README、AGENTS.md、权限示例与 CHANGELOG。
5. **首轮实测**：`logs` 按 A 组（规划端直接写合同与 oracle）做，`plugins` 按 B 组（合同端起草）做，测量记录写进 `.agent/design/3.0-首轮实测.md`（上位设计 13 节）。

### 1.2 不在本轮

- 配置中心（CC Switch 式的 runtime / profile / 方案切换）依赖角色绑定底座（上位设计 P1、M1），下一轮单独走 2gate。
- 管理台网页、日志导出与归档、插件安装与升级、插件依赖语义，见第 6 节。

### 1.3 用户决定（2026-10-17）

- 以 3.0 自身改进作为真实任务推进；走 2gate；在本地分支 `themis-3.0` 上提交，不推送。
- `bb/step-5-preview` 只报 token，费用记 unknown。
- 交互式宿主的模型不由 Themis 切换。

## 2. 现状（承重事实）

### 2.1 运行证据

- 证据根目录是 `Repo.runs_dir = agent_dir / "runs"`（`scripts/pi_dispatch.py:1128`）。attempt 目录名必须匹配 `^attempt-(?P<n>\d{3,})$`（`pi_dispatch.py:66`）。task 目录名的格式是 `TASK_ID_RE = ^[a-z0-9][a-z0-9-]{0,63}$`（`pi_dispatch.py:60`），所以 `.agent/runs/_tmp` 这类目录不是 task。
- `task_attempts` 用 `is_dir()` 筛选，会跟随符号链接与 junction（`pi_dispatch.py:3133-3138`）。
- `resolve_run_dir`（`pi_dispatch.py:3207-3225`）接受 attempt 路径、`task-id/attempt-NNN`、`task-id`、`task-id.vN`：
  - 只有“候选目录里有 `meta.json`”的分支检查结果在 `runs_dir` 之内（`pi_dispatch.py:3213-3217`）；
  - task-id 与 task-id.vN 分支直接返回 `attempts[-1].resolve()`，**不检查边界**（`pi_dispatch.py:3218-3224`）。runs 下某个 attempt 若是指向外部的链接，结果会落到 runs 之外。
- 状态：`set_state` 写 `state.json`（`{"state", "at", ...}`）并追加 `history.jsonl`（`pi_dispatch.py:3114-3119`）；`get_state` 在缺文件时返回 `UNKNOWN`（`pi_dispatch.py:3129-3130`）。
- 用量：
  - `events-summary.json` 的 `usage` 只有 `USAGE_KEYS = ("input", "output", "cacheRead", "cacheWrite", "totalTokens")`（`pi_dispatch.py:2603`，写入在 `2957`）；同一文件有 `requested_model`（`2943`）与 `cost`（未知时 `total` 为 null，`2959-2961`）。
  - 汇总时各项从 0 开始累加（`pi_dispatch.py:2713`），解析不了的行只记行号后跳过（`pi_dispatch.py:2742-2745`）。所以流被截断或有坏行时，`usage` 可能是不完整的数，甚至全零。
  - 同一份摘要有 `parse_error_lines`、`truncated`、`complete`（`pi_dispatch.py:2933-2940`）。
- `metrics` 读同一个 `usage`（`pi_dispatch.py:6783`），并在输出里写明“规划与复审（规划端）费用不在此表”（`pi_dispatch.py:6867`）。
- AGENTS.md：证据只读，不提交、不删除、不编辑；读取时先看 `summary.md`，大文件按需截取。
- 链接检查的现成做法：`kit_install._is_link` 同时识别符号链接与 Windows 重解析点（junction），`_link_level` 从根往下逐级查（`scripts/kit_install.py:92-110`）。

### 2.2 宿主会话记录（Claude Code，2026-10-17 在本机核对）

- 位置：`~/.claude/projects/<项目目录转写>/<会话 ID>.jsonl`，每行一个 JSON 对象。
- 带用量的记录：`message` 是对象，里面有字符串 `id`、`model` 与 `usage` 对象。`usage` 含 `input_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`、`output_tokens`（另有 `server_tool_use` 等字段）。记录顶层有 `timestamp`（ISO 8601，带 `Z`）、`requestId`、`sessionId`、`isSidechain`。
- **同一次回复会写成多条记录**：每个内容块一条，每条都带同一个 `message.id` 和同一份 `usage`。本会话核对结果：174 条 usage 记录只对应 57 个 `message.id`，同一 id 的 usage 完全一致，`requestId` 与 `message.id` 一一对应。直接求和会多算两倍多。
- 本会话里调用过的 advisor 没有出现在这些 usage 记录里：174 条记录的 `message.model` 全是主模型。
- 这不是公开文档化的接口，字段与写法可能随版本变化。

### 2.3 插件与配置

- 8 个插件目录 `plugins/<id>/`，各有 `manifest.json`、`lock.json`、`README.md`；8 个 manifest 的 `depends_on` 与 `conflicts` 全部为空。
- `validate_manifest`（`scripts/codekit/plugins.py:173-237`）：封闭字段集，`record_type` 必须是 `builtin-task-plugin-manifest`，`schema_version` 为 1；`permissions`、`platforms`、`depends_on`、`conflicts` 是字符串列表；`resources` 是 ResourceRef；`checks` 是 `{id, command, deterministic}`。
- `resource_ref`（`plugins.py:129-149`）：封闭的 `{kind, id, path, sha256}`，把反斜杠换成 `/` 并做 NFC 规范化，拒绝绝对路径与 `..`，返回规范化后的值（`plugins.py:142-149`）。
- `resolve_plugins(manifests, enabled)`（`plugins.py:238`）：先对注册表里**每一个** manifest 跑 `validate_manifest`（`plugins.py:242`），任何一个坏掉整个调用失败；再按 `depends_on` 递归，缺依赖报 `E_PLUGIN_DEPENDENCY`（`plugins.py:260-261`）。
- `validate_lock(lock, manifests)`（`plugins.py:307-376`）：
  - 校验锁的结构、规范顺序、`lock_sha256`（不符时 `E_PLUGIN_LOCK_DRIFT`）；
  - 给了 manifests 时，先对注册表跑 `resolve_plugins`（`plugins.py:365`），再要求锁里的插件集合与注册表完全相同（`plugins.py:366-367`），最后核对锁与 manifest 字节的绑定（不符时 `E_PLUGIN_LOCK_BINDING`）；
  - 返回的行里资源路径是规范化后的（`plugins.py:372-374`）；
  - **它不对磁盘上的资源文件求哈希**。
- 资源哈希是文件原始字节的 SHA-256：本次对 8 个插件共 11 个资源逐个求哈希，全部与锁一致。`.gitattributes:25,29` 把 `plugins/decisions/**` 与 `plugins/*/README.md` 设为 `-text`，避免检出时换行转换改变哈希。
- 决策插件另有专用核对 `verify_battery_lock`（`scripts/codekit/decisions.py:312-357`）：`questions/` 下多出锁里没有的清单、锁里有而缺失的清单、字节不符都算不一致，只差 CRLF 时直说（`decisions.py:339-350`）。决策生效时 `kit_config` 的整份校验也调用它（`scripts/kit_config.py:157`）。
- 权限：`check_permission_intersection(manifest, allowed_permissions=..., platform_name=...)` 返回缺的权限与 `READY` / `BLOCKED`（`plugins.py:377-404`）。
- 异常：`strict_json_loads` 抛 `ProtocolError`，`codekit` 的插件函数抛 `PluginError`，两者都是 `ValueError` 的子类（`scripts/codekit/protocols.py:228`、`plugins.py:30`）。
- 配置语义：`plugins.enabled` 与 `plugins.allowed_permissions` 现在只有决策插件读（`decisions.py:513-521`）。值是列表时按列表判定，**缺省或不是列表时等于不限制**。
- **缺口**：`kit_config.KEYS`（`kit_config.py:165-185`）没有 `plugins`。所以：
  - `validate_config` 把手写的 `plugins` 键报成“未知键”（`kit_config.py:212-225`）；
  - `split_path` 拒绝 `config set plugins.enabled …`（`kit_config.py:245-249`）；
  - `_write_checked` 先整份校验再写，有错一个字节都不写（`kit_config.py:322-326`）。
- **两种布局的插件不同**：插件文件所在的根是 `KIT_ROOT = Path(__file__).resolve().parent.parent`（`pi_dispatch.py:3672`）。
  - 从 ThemisTally 目录运行（README 方式一）时，`KIT_ROOT/plugins/` 有全部 8 个插件；
  - 装进目标仓库（方式二）时，`kit_install` 只发放 `KIT_LOADED_FILES` 列出的 `plugins/decisions/**`（`pi_dispatch.py:94-98`、`kit_install.py:192-197`），其余 7 个任务插件是 v2 的离线参考，不发放。

### 2.4 调度器转发与保护

- `config` 的转发：`cmd_config` 从调度器所在目录导入 `kit_config` 并调用 `kit_config.main(args, repo=…)`，导入失败时报 `DispatchError(EXIT_USAGE)`（`pi_dispatch.py:7118-7124`）。解析器用 `argparse.REMAINDER` 原样传参，但子解析器带默认的帮助选项（`pi_dispatch.py:7502-7504`），所以 `config --help` 由外层 argparse 处理，不会转发。
- `KIT_LOADED_FILES`（`pi_dispatch.py:94-98`）并入 `PROTECTED_PATTERNS`（`pi_dispatch.py:100-104`），执行器改了就是 G2 越界。它还决定：
  - `kit_install` 发放哪些文件（`scripts/kit_install.py:192-197`）；
  - doctor 的 kit 检查要求哪些文件存在（`pi_dispatch.py:7032`）；
  - `tests/test_kit_v280.py` 用 import 扫描核对这份清单（`tests/test_kit_v280.py:120-144`）。扫描只从 `pi_dispatch.py` 与 `kit_config.py` 出发，只跟随 `from codekit import …`、相对导入与 `import pi_dispatch`，不跟随 `import kit_config` 这类导入。
- 退出码：调度器 `EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_BLOCKED, EXIT_DRIFT = 0, 1, 2, 3, 4`（`pi_dispatch.py:57`）；配置管理器 `EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2`（`kit_config.py:54`），`ConfigError` 缺省退出码为 1（`kit_config.py:61-63`），`main` 捕获后打印 `ERROR:` 并返回该码（`kit_config.py:642-645`）。
- `kit_config` 在模块顶层 `import pi_dispatch as pd`（`kit_config.py:44`）。
- `.claude/settings.example.json` 只放行只读的调度命令，并禁止编辑 `.agent/runs/**`。AGENTS.md 的“Codex 的沙箱”一节逐个列出哪些子命令只读、哪些要在沙箱外运行。

### 2.5 测试约定

- `unittest` 写法，用 pytest 运行；测试把 `scripts/` 插进 `sys.path` 后直接导入模块（`tests/test_kit_config.py:22-28`）。
- 用临时 Git 仓库，并在清理时删除（`tests/test_kit_config.py:42-55`）；凭据库用 `CODEKIT_SECRET_STORE=file` 加临时 `XDG_CONFIG_HOME`，不碰真实凭据库。
- 本机 `python` 为 3.10.19（Git Bash）；README 写明配置子命令需要 Python 3.10。

## 3. 决策与理由

不新造口径：用量字段沿用 `events-summary.json` 的 `USAGE_KEYS`；插件校验沿用 `codekit/plugins.py` 与 `decisions.verify_battery_lock`；配置写入沿用 `kit_config` 的整份校验与原子替换；退出码沿用 `kit_config` 的常量；链接检查沿用 `kit_install` 的做法。

- **D1 两个新文件，照 `kit_config` 的结构写**：单文件、标准库、Python 3.10+，`main(argv=None, repo=None) -> int`，argparse 子命令，带 `--repo`。新文件不在保护路径内，可以委派给执行端；接入时才加进 `KIT_LOADED_FILES`（2.4）。
- **D2 `logs` 只读，并且自己守边界**：
  - 不写 `.agent/` 下任何文件。
  - 不复用 `resolve_run_dir` 与 `task_attempts`（2.1 的边界缺口）。自己枚举 `runs_dir` 下的 task 目录与 attempt 目录；从 `runs_dir` 往下，每一级（task 目录、attempt 目录、证据文件及其中间目录）都用 `kit_install` 同样的办法检查符号链接与 junction（2.1），是链接就跳过并计数，不跟随。
  - `logs show <目标>` 接受 `task-id`（取编号最大的 attempt）、`task-id.vN`（取 `meta.json` 的 `plan_version` 等于 N 的编号最大的 attempt）、`task-id/attempt-NNN` 与 attempt 目录路径。任何形式都要求：路径的每一级都不是链接，并且解析后的路径在 `runs_dir` 之内；否则用法错误（退出码 2）。
  理由：AGENTS.md 规定证据只读；2.1 的实测缺口。
- **D3 执行端用量只取 `events-summary.json` 的 `usage`**：
  - 与 `metrics` 同一来源、同一字段（2.1）。
  - 文件缺失、`usage` 缺失或不是对象 → 这个 attempt 记为 unknown，不当 0。
  - `complete` 为假、`truncated` 为真、或 `parse_error_lines` 非空 → 记为“部分”：数字计入合计的下界，单独计数并在输出里标明（2.1：解析错误被跳过时摘要仍会写出数字）。
  - `logs usage` 只报 token，费用仍由 `metrics` 负责（用户决定 bb 的费用记 unknown）。
- **D4 规划端用量来自宿主会话记录，先全局去重、再按窗口过滤**：
  1. **读取**：只读命令行显式给出的 `--transcript` 路径（文件，或目录下直接一层的 `*.jsonl`），不自动到用户目录里找。
  2. **候选记录**：顶层是对象、`message` 是对象、`message.id` 是非空字符串、`message.usage` 是对象。不看 `type` 字段。坏 JSON 行、非对象行计数后跳过。
  3. **全局去重**：把所有给定文件的候选记录按 `message.id` 分组（与读取顺序无关）。同一组里，四个计数字段（`input_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`、`output_tokens`）、`message.model` 与 `isSidechain` 必须全部相同，相同就只算一次（记重复条数）；有任何不同就记为冲突，这个 id 整个不计入，结果标为“部分”。
  4. **代表时间**：同一组里所有能解析的 `timestamp` 的最小值。没有任何能解析的时间时，这个 id 计数后跳过。
  5. **窗口**：去重之后再按代表时间过滤，`--since` 含、`--until` 不含；命令行的时间必须带时区（`Z` 或偏移），否则用法错误。
  6. **计数字段**：某个字段不是整数时，这条消息的该字段记 unknown 并计数，其余字段照常计入。
  7. **输出**：按模型、主线与子代理（`isSidechain`）分组的四项 token，以及重复、冲突、跳过的计数。只读用量、时间、模型与 `isSidechain`，不读也不输出 `content` 或其他字段。
  8. **覆盖范围**：只统计会话记录里有的调用。advisor 等不写进会话记录的调用不在其中（2.2），所以规划端用量是下界，输出里注明。
  理由：2.2 的实测；结果必须与文件顺序、记录顺序无关；不读对话内容；不越出用户指定的范围。
- **D5 `plugins` 的只读部分复用 `codekit/plugins.py`，逐插件独立核对**：
  - 插件目录：`KIT_ROOT/plugins/` 下名字匹配 `PLUGIN_ID`（`plugins.py:19`）的直接子目录；`plugins` 目录本身与每个插件目录都不能是链接或 junction。
  - manifest 与 lock 用 `codekit.protocols.strict_json_loads` 解析（重复键等直接拒绝）。
  - 每个插件单独核对：`validate_manifest`，目录名必须等于 `plugin_id`；`depends_on` 或 `conflicts` 非空 → 记为“本轮不支持”，不再调用 `validate_lock`（2.3：单插件注册表在有依赖时必然失败）；否则 `validate_lock(lock, {plugin_id: manifest})`。
  - 资源文件：用 `validate_lock` 返回的规范化路径。从 `KIT_ROOT` 往下逐级检查链接与 junction（插件根、中间目录、文件本身）；路径必须以 `plugins/<id>/` 开头；文件必须是普通文件；原始字节 SHA-256 必须等于锁里的值，只差 CRLF 时直说。
  - `decisions` 另调用 `verify_battery_lock`（2.3），把它报的问题并入（包括多出的题库文件）。
  - 权限与启用状态：用 `check_permission_intersection` 与配置里的列表判定；`enabled` 里列了、但当前布局没有安装的 ID，单独报告。
  - 不执行 manifest 里 `checks` 的命令。
- **D6 `enable` / `disable` 的语义与决策插件的读法一致（`decisions.py:513-521`），不让一个操作隐性改变其他插件的状态**：
  - **非列表值**：`plugins.enabled` 或 `plugins.allowed_permissions` 存在但不是列表（例如 `null`）→ 拒绝，提示用 `config unset plugins.enabled`（或 `allowed_permissions`）删除它来表示不限制。不做隐式规范化。
  - **`enable X`**：
    - X 的 manifest、lock、资源文件（以及 `decisions` 的题库核对）必须全部一致；`depends_on` 或 `conflicts` 非空 → 拒绝（本轮不支持）。不校验其他插件。
    - `enabled` 缺省（不限制）时不改 `enabled`，提示“当前不限制，所有插件都算启用”；`enabled` 是列表时加入 X（去重、按 ID 排序）。
    - 权限只在 `allowed_permissions` 是列表时检查：缺的权限必须由 `--allow-permission <名>` 一个不多、一个不少地给出，这时一并写入 `allowed_permissions`；给多、给少或当前不限制时还给了，都是用法错误。
  - **`disable X`**：
    - 只要求 `KIT_ROOT/plugins/X/` 存在（允许关掉坏掉的插件），不校验任何其他插件。
    - `enabled` 缺省时，把“当前布局下全部插件目录名（匹配 `PLUGIN_ID`，不论 manifest 好坏）减去 X”写成显式列表（按 ID 排序），并打印这一变化：之后新增的插件不会自动启用。
    - `enabled` 是列表时移除 X；不在列表里就提示没有变化。
    - 不碰 `allowed_permissions`。
    - 关掉 `decisions` 时提示：决策插件会因此变为 off（`decisions.py:515-518`）。
  - **写入**：用 `kit_config.write_checked`（D7），整份校验后原子替换，校验不过一个字节都不写。`--dry-run` 只打印将写入的 `plugins` 段，不写文件。
- **D7 `kit_config` 增加 `plugins` 键与公开的 `write_checked`**：
  - `KEYS["plugins"]`，校验函数 `_check_plugins`：缺省合法；必须是对象；子键只允许 `enabled`、`allowed_permissions` 与下划线开头的说明。
  - `enabled`：字符串列表，每项匹配 `PLUGIN_ID`，不重复。**不检查是否已安装**：同一份配置要在两种布局下都合法（2.3）；列入但未安装由 `plugins list` / `verify` 报告。
  - `allowed_permissions`：非空字符串列表，不重复。
  - 任一子键不是列表（包括 `null`）→ 错误，提示用 `config unset plugins.<子键>` 表示不限制。
  - `write_checked(repo, config)` 是现有 `_write_checked` 的公开名字，旧名保留。
  - 这样 `config show` 会列出 `plugins`，`config set plugins.enabled '[…]'` 也能用（`split_path` 只认已知键）。
  理由：2.3 的缺口；`plugins` 已经被决策插件读取，配置管理器却不认识它。
- **D8 接入沿用 `config` 的转发方式**：
  - `cmd_logs`、`cmd_plugins` 与 `cmd_config`（`pi_dispatch.py:7118-7124`）同形；解析器用 `REMAINDER`，子解析器 `add_help=False`，让 `logs --help`、`plugins --help` 转发给下游（2.4）。
  - `KIT_LOADED_FILES` 加两个文件。
  - `tests/test_kit_v280.py` 的 import 扫描改为同时跟随 `import kit_<名>` 形式的导入（只在 `scripts/kit_<名>.py` 存在时），让清单与实际加载一致。
- **D9 文档与权限**：README 命令表加 `logs`、`plugins`，并写明安装布局下只有决策插件；AGENTS.md“Codex 的沙箱”一节把 `logs` 与 `plugins list/show/verify` 列为只读，`plugins enable/disable` 列为只写工作区；`.claude/settings.example.json` 放行 `logs` 与 `plugins list|show|verify`；CHANGELOG 加“未发布（themis-3.0 分支）”一节。
- **D10 错误处理**：
  - `plugins`：逐插件收集 `ValueError`（含 `ProtocolError`、`PluginError`）与 `OSError`，记为该插件的问题，其余插件照常列出与核对。
  - `logs`：逐文件收集 `OSError` 与解码问题，计数后继续。
  - 命令级错误（目标找不到、参数错误）捕获 `pd.DispatchError` 与 `kit_config.ConfigError`，打印 `ERROR:` 一行并返回其退出码；argparse 的参数错误退出码 2。
  - 不输出堆栈。

## 4. 接口

### 4.1 `logs`

| 命令 | 输出 | 退出码 |
|---|---|---|
| `logs list [--task ID] [--state S] [--json]` | 每个 attempt 一行：`task/attempt`、状态、状态时间、证据文件数、总字节、有没有 `summary.md`；另报跳过的链接数。按 task 名、attempt 编号排序。没有时打印“没有 attempt” | 0；参数错误 2 |
| `logs show <目标> [--json]` | 目标按 D2 解析。打印 attempt 路径与状态；`summary.md` 的内容（超过 64 KiB 截断并注明）；证据文件清单（相对路径与大小）。不打印其他文件的内容 | 0；找不到或越界 2 |
| `logs search <正则> [--task ID] [--max N]` | 在后缀为 `.md`、`.txt`、`.log`、`.json`、`.jsonl` 的证据文件里逐行搜，输出 `相对路径:行号: 内容`，内容截到 200 个字符；`--max` 缺省 50，达到上限时注明 | 0（含没有匹配）；正则无效 2 |
| `logs usage [--task ID] [--transcript 路径 …] [--since 时间] [--until 时间] [--json]` | 两段：执行端（每个 attempt 的 `usage`，合计、unknown 与“部分”的计数，按 `requested_model` 分组）；规划端（D4 的分组与计数，注明是下界）。`--since` / `--until` 只作用于规划端 | 0；路径不存在或时间格式错 2 |

`--json` 的输出是一个对象，键名固定写在模块里，测试按键名断言。

### 4.2 `plugins`

| 命令 | 输出 | 退出码 |
|---|---|---|
| `plugins list [--json]` | 每个插件一行：ID、版本、启用（是 / 否 / 不限制）、锁（一致 / 漂移 / 无效 / 本轮不支持）、资源文件（一致 / 不一致）、缺的权限、状态（READY / BLOCKED 与原因）；另列 `enabled` 里有、当前布局没安装的 ID | 0 |
| `plugins show <ID> [--json]` | manifest 的版本、api_version、capabilities、permissions、platforms、depends_on、conflicts、checks；每个资源的路径与哈希核对；锁的 generation 与 lock_sha256；配置里的启用与权限状态 | 0；ID 不存在 2 |
| `plugins verify [ID] [--json]` | 所选插件（缺省全部）的 manifest、锁、资源文件核对结果与问题清单；不指定 ID 时还核对“列入但未安装” | 全部一致 0；有问题 1；ID 不存在 2 |
| `plugins enable <ID> [--allow-permission P …] [--dry-run]` | 变化摘要，例如 `plugins.enabled: [a, b] → [a, b, c]`；没有变化时直说 | 写入或无变化 0；被拒绝 1；用法错误 2 |
| `plugins disable <ID> [--dry-run]` | 同上；从“不限制”改成显式列表时单独提示 | 同上 |

### 4.3 `kit_config` 的 `plugins` 键

```json
{
  "plugins": {
    "enabled": ["code-change", "decisions"],
    "allowed_permissions": ["network-decisions", "read-candidate"]
  }
}
```

两个子键都可以缺省；缺省就是不限制（与 `decisions.py:513-521` 一致）。子键存在时必须是列表。

### 4.4 调度器转发

`python scripts/pi_dispatch.py logs …` 与 `python scripts/pi_dispatch.py plugins …` 原样转发给两个模块的 `main(args, repo=…)`，包括 `--help`；`--repo` 一并传过去；下游的退出码原样返回。

## 5. 执行方式

| 项 | 谁做 | 方式 |
|---|---|---|
| D7 `kit_config` 的 `plugins` 键与 `write_checked`，及其测试 | 规划端（受保护文件） | 直接改，先于 T2 提交，作为 T2 的基线 |
| T1 `kit_logs.py` | Pi 执行 | A 组：规划端按本文写合同与 oracle，oracle 提交到基线后派遣 |
| T2 `kit_plugins.py` | Pi 执行 | B 组：规划端按本文写概要步骤；Pi 作为合同端起草合同、oracle 与参考实现（一次普通派遣，交付物在 `drafts/kit-plugins/` 与 `tests/test_kit_plugins_oracle.py`）；规划端审核后发布，再派 Pi 实现 |
| D8、D9 接入、文档与权限 | 规划端（受保护文件） | T1、T2 集成之后直接改 |
| 实测记录 | 规划端 | `.agent/design/3.0-首轮实测.md`：各阶段起止时间、子代理用量、Pi 用量、审核意见、修订轮数、verdict、变异抓住率 |

- 执行端与合同端都用 Pi + `bb/step-5-preview`，思考级别 high。每次派遣最多 2 个 attempt，每个 attempt 不超过 1800 秒。
- 规划端的合同、oracle、概要步骤与审核在新的子代理里做（与本会话同一模型），用量取子代理结果里报告的数字；取不到时按上位设计 13.3 的弱信号口径记录。
- B 组起草派遣的 `TASK:` 合同写明：合同里哪些取舍交给它在本文 4.2 与 D5、D6 的范围内决定，每一项都要写进执行报告的 `interpretations`。

## 6. 刻意不做

- `logs`：导出、归档、封存清单校验、实时跟随、占用统计、费用计算、Codex 会话记录的导入、自动发现会话文件、读取对话内容。
- `plugins`：安装、升级、删除、执行插件的 `checks`、联网、generic 适配器插件、重新生成锁；**带 `depends_on` 或 `conflicts` 的插件的启用**（依赖语义与锁的布局留到插件安装那一轮统一定义，现有 8 个插件都没有依赖）。
- 不改派遣流程的语义（prepare / run / check / verdict / integrate 不动）。
- **调度器 `resolve_run_dir` 的边界缺口**（2.1）：本轮的 `logs` 自己守边界，不依赖它；调度器本身的修复会影响 `status`、`check` 等多个命令，另立任务（第 10 节第 5 项）。
- 不引入配置 v3、角色绑定或方案（下一轮）。
- 不改 `scripts/codekit/plugins.py` 与 `scripts/codekit/decisions.py`（受保护；本轮只调用它们的公开函数）。
- 不改任何证据文件；不给 `pricing` 加 `bb/step-5-preview`（用户决定）。
- 多个进程同时改配置的竞争：`write_config` 用固定的临时文件名（`kit_config.py:228-235`），本轮沿用，不另加锁（第 10 节第 3 项）。

## 7. 影响面清单

### 7.1 要改的

| 文件 | 位置 | 内容 | 谁 |
|---|---|---|---|
| `scripts/kit_logs.py` | 新文件 | 4.1 | T1（Pi） |
| `tests/test_kit_logs_oracle.py` | 新文件 | 规划端 oracle，覆盖第 9 节 L 组的关键场景 | 规划端（A 组） |
| `tests/test_kit_logs.py` | 新文件 | 执行端自己的测试 | T1（Pi） |
| `scripts/kit_plugins.py` | 新文件 | 4.2 | T2（Pi） |
| `tests/test_kit_plugins_oracle.py` | 新文件 | 合同端起草、规划端审核的 oracle，覆盖第 9 节 P 组 | B 组合同端 |
| `tests/test_kit_plugins.py` | 新文件 | 执行端自己的测试 | T2（Pi） |
| `scripts/kit_config.py` | `KEYS`（`165-185`）、新增 `_check_plugins`、`_write_checked`（`322-326`）旁加公开名 | D7 | 规划端 |
| `tests/test_kit_config.py` | 新增用例 | 第 9 节 C 组 | 规划端 |
| `scripts/pi_dispatch.py` | `KIT_LOADED_FILES`（`94-98`）；文档串命令表（`28` 附近）；`cmd_config` 旁新增 `cmd_logs`、`cmd_plugins`（`7118-7124`）；解析器（`7502-7504` 附近） | D8 | 规划端 |
| `tests/test_kit_v280.py` | import 扫描（`120-144`） | D8 | 规划端 |
| `tests/test_dispatch.py` | 新增转发与安装布局场景 | 第 9 节 W 组 | 规划端 |
| `README.md`、`AGENTS.md`、`.claude/settings.example.json`、`CHANGELOG.md` | 命令表、Codex 沙箱一节、放行规则、未发布一节 | D9 | 规划端 |
| `.agent/design/3.0-首轮实测.md` | 新文件 | 实测记录 | 规划端 |
| `.agent/plans/kit-logs.v1.*`、`.agent/plans/kit-plugins.v1.*`、`.agent/reviews/…` | 新文件 | 合同与复审记录 | 规划端 |

### 7.2 刻意不改的

| 文件 | 理由 |
|---|---|
| `scripts/codekit/plugins.py`、`scripts/codekit/decisions.py` | 受保护；本轮只调用公开函数，语义不变 |
| `scripts/pi_dispatch.py` 的 `resolve_run_dir`、`task_attempts` | 边界缺口另立任务（第 6 节）；`logs` 不依赖它们 |
| `scripts/kit_install.py` | 发放清单取自 `KIT_LOADED_FILES`（`kit_install.py:192-197`），加进清单就会自动发放；由测试 W2 在真实安装出来的目标里核对 |
| `.agent/dispatch.config.json` | 本轮不需要改；用户决定不加 bb 的单价 |
| `.agent/runs/**` | 证据只读 |
| `schemas/**` | 本轮没有新的记录类型落盘 |

## 8. 上线顺序与回滚

1. 闸一：本文送 Codex 对抗审核，修到零 Blocking。
2. D7：`kit_config` 改动与测试，提交。
3. T1 与 T2 可以并行：
   - T1：写合同与 oracle → oracle 提交 → 派遣 → 复审 → 集成到 `themis-3.0`；
   - T2：写概要步骤 → 起草派遣 → 审核（最多修订 2 轮）→ 发布并提交 oracle → 派遣 → 复审 → 集成。
4. D8、D9：接入、文档、权限示例，跑全量测试，提交。
5. 闸二：分支相对 `8fb12ed` 的改动送 Codex 审核，修到零 Blocking。
6. 向用户汇报；合并到 master 由用户决定。

回滚：所有改动都在 `themis-3.0` 分支上、按步骤分开提交，master 不动。任一步出问题可以 `git revert` 该提交，或整个放弃分支。本轮不改仓库配置、不改证据，没有数据迁移。

## 9. 测试计划

每条对应一个具体的失败场景。

**L 组：`logs`**

| 编号 | 场景 | 防止的失败 |
|---|---|---|
| L1 | 同一 `message.id` 写三条、usage 相同 | 按三次计数 |
| L2 | 同一 `message.id` 两条：四项计数不同；或 `model` 不同；或 `isSidechain` 不同 | 随意取一条；冲突不报；结果不标“部分” |
| L3 | 坏 JSON 行、非对象行、没有 usage 的记录、`message.id` 不是字符串、计数字段不是整数 | 崩溃，或悄悄算进去 |
| L4 | 同一 `message.id` 分在两个文件里、时间分别在窗口边界两侧；记录恰好落在 `--since` 与 `--until` 上。对文件参数顺序、文件内记录顺序做全部置换，结果必须完全相同 | 结果随读取顺序变化；窗口边界错位；跨文件重复计数 |
| L5 | 命令行时间不带时区；记录的 `timestamp` 无法解析 | 把不带时区的时间当本地时间；把无时间的记录算进窗口 |
| L6 | `isSidechain` 为真的记录 | 与主线混在一起 |
| L7 | attempt 没有 `events-summary.json`；`usage` 不是对象；摘要的 `complete` 为假、`truncated` 为真或 `parse_error_lines` 非空 | 把缺失当 0；把不完整的数当成准确值 |
| L8 | `.agent/runs` 不存在或为空；有 `_tmp` 这类非 task 目录；有不匹配 `attempt-NNN` 的目录 | 崩溃或误列 |
| L9 | 所有子命令跑一遍前后，逐字节比较 `.agent/` | 工具写了证据 |
| L10 | 证据里有很长的行和大量匹配 | 输出整份大文件或超过上限 |
| L11 | 会话记录的 `content` 里有形似密钥的文字 | 把对话内容打印出来 |
| L12 | task 目录、attempt 目录、证据文件或其中间目录是符号链接或 junction（Windows 上用 junction，其他平台用符号链接） | 跟随链接读到 runs 之外 |
| L13 | `logs show` 的目标分别用 task-id、task-id.vN、task-id/attempt-NNN、显式路径给出，且指向链接或 runs 之外；目标不存在 | 读 runs 之外的文件；崩溃而不是退出码 2 |

**P 组：`plugins`**

| 编号 | 场景 | 防止的失败 |
|---|---|---|
| P1 | 现有 8 个插件 | 把一致的插件报成不一致 |
| P2 | 资源文件改一个字节；只把 LF 改成 CRLF；`decisions/questions/` 下多出一个锁里没有的清单 | 漏报漂移；CRLF 时不给提示；漏报多出的题库 |
| P3 | `lock_sha256` 被改 | 漏报锁漂移 |
| P4 | manifest 被改（与锁绑定不符） | 漏报绑定不一致 |
| P5 | `plugins` 目录、插件目录、中间目录或资源文件是符号链接或 junction；资源路径解析后不在插件目录内 | 读到插件目录之外 |
| P6 | 目录名与 `plugin_id` 不同；manifest 有重复键；manifest 不是合法 JSON | 接受不一致的插件；一个坏插件让 `list` 整体失败 |
| P7 | `enabled` 缺省时 `enable X` | 写出只含 X 的列表，把其他插件全关掉 |
| P8 | `enabled` 缺省时 `disable X`，当前布局里另有一个 manifest 坏掉的插件 | 写出的列表漏掉坏插件或其他插件；不提示语义变化 |
| P9 | `allowed_permissions` 是列表、X 缺权限、没给 `--allow-permission` | 悄悄加权限或写入了部分改动 |
| P10 | 给出的 `--allow-permission` 多于、少于所缺的权限；当前不限制时给了 | 授予无关权限 |
| P11 | `enable` 一个 `depends_on` 或 `conflicts` 非空的插件；`list` / `verify` 遇到这样的插件 | 启用依赖语义未定义的插件；因单插件注册表缺依赖而误报“锁无效” |
| P12 | 两个插件的 manifest 坏掉时 `disable` 其中一个；同时 `disable decisions` | 因为无关的坏插件拒绝关闭 |
| P13 | `plugins.enabled` 或 `allowed_permissions` 为 `null` 时 `enable` / `disable` | 隐式改写旧值；不给修复提示 |
| P14 | `enable` 一个锁不一致的插件；配置里另有一个无效键时 `enable` | 启用坏插件；绕过整份校验写入 |
| P15 | 写入中途失败（`os.replace` 抛错） | 留下半份配置 |
| P16 | 关掉 `decisions`；`--dry-run` | 不提示决策插件会变为 off；实际写了文件 |
| P17 | `enabled` 里有当前布局没安装的 ID | `verify` 不报；`list` 崩溃 |

**C 组：`kit_config`**

| 编号 | 场景 | 防止的失败 |
|---|---|---|
| C1 | 合法的 `plugins` 段；`config show` | 新键不显示或被报未知 |
| C2 | `enabled` 不是列表（含 `null`）、有重复、ID 格式错；`allowed_permissions` 有空串或重复；未知子键 | 接受会让插件悄悄失效的值；错误提示里没有修复办法 |
| C3 | `config set plugins.enabled '[…]'`；`enabled` 里有当前布局没安装的 ID | `split_path` 仍拒绝；同一份配置在安装布局下被判无效 |
| C4 | 现有决策插件测试 | `plugins` 语义被改动 |

**W 组：接入**

| 编号 | 场景 | 防止的失败 |
|---|---|---|
| W1 | 通过 `pi_dispatch.main` 调用 `logs …`、`plugins …`、`plugins --help`，用替身记录下游 `main` 收到的参数与 `repo`，并让替身返回非零退出码 | 转发失效；`--help` 被外层截走；下游退出码被吞 |
| W2 | `KIT_LOADED_FILES` 含两个新文件；import 扫描一致；用 `kit_install install` 装进临时目标仓库，在目标里运行装好的 `plugins list` 与 `logs list` | 新文件不受保护或不被发放；安装布局下命令不能用 |
| W3 | 全量 `python -m pytest tests` | 回归 |

## 10. 待用户拍板

1. **版本标注**：本轮在 CHANGELOG 记为“未发布（themis-3.0 分支）”，合并到 master 时再定版本号（推荐）；或现在就记为 2.11.0。
2. **会话文件的读取范围**：只读命令行显式给出的路径（推荐）；或允许自动到 `~/.claude/projects/` 下找本仓库的会话文件。
3. **配置并发写**：沿用 `kit_config` 现有的“固定临时文件名 + 原子替换”，不加锁（推荐，本轮不扩大范围）；或本轮就给配置写入加锁。
4. **合并到 master**：闸二通过后由你决定，不自动合并。
5. **调度器 `resolve_run_dir` 的边界缺口**：另立一个小任务修（推荐，修法是 task-id 分支同样检查链接与边界）；或本轮顺带修。
