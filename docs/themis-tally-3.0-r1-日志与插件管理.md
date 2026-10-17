# Themis Tally 3.0 第一轮设计：日志管理与插件管理的第一片

状态：2gate 闸一审核中。本文是第一轮的实现设计，审到零 Blocking 才进入实现。

- 分支：`themis-3.0`（本地，不推送）。起点 `8fb12ed`（master），之上是设计说明提交 `0f4879c`。
- 上位设计：`docs/themis-tally-3.0-四端分层解耦架构.md` 第 8.2 节（日志管理）、8.3 节（插件管理）、13 节（首轮实战）。
- 下文 `file:line` 都在 `8fb12ed` 上核对过。

## 0. 审核变更对照表

| 编号 | 第 N 轮结论 | 本稿处置 |
|---|---|---|
| （无） | 尚未送审 | 第 1 轮送审稿 |

## 1. 范围

### 1.1 本轮交付

1. **`logs` 第一片**：新文件 `scripts/kit_logs.py`，子命令 `list`、`show`、`search`、`usage`。全部只读。`usage` 第一次把规划端用量（宿主会话记录）与执行端用量（Pi 运行证据）放在一起按 token 汇总。
2. **`plugins` 第一片**：新文件 `scripts/kit_plugins.py`，子命令 `list`、`show`、`verify`、`enable`、`disable`。前三个只读；后两个只改 `.agent/dispatch.config.json` 的 `plugins` 键。
3. **`kit_config` 补上 `plugins` 键**：现在 `plugins` 被 `codekit/decisions.py` 读取，却不在配置管理器的已知键里（2.3）。
4. **接入**：调度器转发 `logs`、`plugins` 两个子命令，两个新文件加入 `KIT_LOADED_FILES` 受保护；同步测试、README、AGENTS.md、权限示例与 CHANGELOG。
5. **首轮实测**：`logs` 按 A 组（规划端直接写合同与 oracle）做，`plugins` 按 B 组（合同端起草）做，测量记录写进 `.agent/design/3.0-首轮实测.md`（上位设计 13 节）。

### 1.2 不在本轮

- 配置中心（CC Switch 式的 runtime / profile / 方案切换）依赖角色绑定底座（上位设计 P1、M1），下一轮单独走 2gate。
- 管理台网页、日志导出与归档、插件安装与升级，见第 6 节。

### 1.3 用户决定（2026-10-17）

- 以 3.0 自身改进作为真实任务推进；走 2gate；在本地分支 `themis-3.0` 上提交，不推送。
- `bb/step-5-preview` 只报 token，费用记 unknown。
- 交互式宿主的模型不由 Themis 切换。

## 2. 现状（承重事实）

### 2.1 运行证据

- 证据根目录是 `Repo.runs_dir = agent_dir / "runs"`（`scripts/pi_dispatch.py:1128`）。attempt 目录名必须匹配 `^attempt-(?P<n>\d{3,})$`（`pi_dispatch.py:66`）；`task_attempts` 按编号排序列出（`pi_dispatch.py:3133-3138`）。task 目录名的格式是 `TASK_ID_RE = ^[a-z0-9][a-z0-9-]{0,63}$`（`pi_dispatch.py:60`），所以 `.agent/runs/_tmp` 这类目录不是 task。
- 状态：`set_state` 写 `state.json`（`{"state", "at", ...}`）并追加 `history.jsonl`（`pi_dispatch.py:3114-3119`）；`get_state` 在缺文件时返回 `UNKNOWN`（`pi_dispatch.py:3129-3130`）。
- 用量：`events-summary.json` 的 `usage` 字段只有 `USAGE_KEYS = ("input", "output", "cacheRead", "cacheWrite", "totalTokens")`（`pi_dispatch.py:2603`，写入在 `2957`）；同一文件有 `requested_model`（`2943`）与 `cost`（未知时 `total` 为 null，`2958-2961`）。
- `metrics` 读同一个 `usage`（`pi_dispatch.py:6783`），并在输出里写明“规划与复审（规划端）费用不在此表”（`pi_dispatch.py:6867`）。
- attempt 定位：`resolve_run_dir` 接受 attempt 路径、`task-id/attempt-NNN`、`task-id`、`task-id.vN`，并要求结果在 `runs_dir` 之内，否则抛 `DispatchError(EXIT_USAGE)`（`pi_dispatch.py:3207-3225`）。
- AGENTS.md：证据只读，不提交、不删除、不编辑；读取时先看 `summary.md`，大文件按需截取。

### 2.2 宿主会话记录（Claude Code，2026-10-17 在本机核对）

- 位置：`~/.claude/projects/<项目目录转写>/<会话 ID>.jsonl`，每行一个 JSON 对象。
- 带用量的记录：`message` 是对象，里面有字符串 `id`、`model` 与 `usage` 对象。`usage` 含 `input_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`、`output_tokens`（另有 `server_tool_use` 等字段）。记录顶层有 `timestamp`（ISO 8601，带 `Z`）、`requestId`、`sessionId`、`isSidechain`。
- **同一次回复会写成多条记录**：每个内容块一条，每条都带同一个 `message.id` 和同一份 `usage`。本会话核对结果：174 条 usage 记录只对应 57 个 `message.id`，同一 id 的 usage 完全一致，`requestId` 与 `message.id` 一一对应。直接求和会多算两倍多。
- 这不是公开文档化的接口，字段与写法可能随版本变化。

### 2.3 插件与配置

- 8 个插件目录 `plugins/<id>/`，各有 `manifest.json`、`lock.json`、`README.md`。
- `validate_manifest`（`scripts/codekit/plugins.py:173-237`）：封闭字段集，`record_type` 必须是 `builtin-task-plugin-manifest`，`schema_version` 为 1；`permissions`、`platforms`、`depends_on`、`conflicts` 是字符串列表；`resources` 是 ResourceRef；`checks` 是 `{id, command, deterministic}`。
- `resource_ref`（`plugins.py:129-149`）：封闭的 `{kind, id, path, sha256}`，拒绝绝对路径与 `..`。
- `validate_lock(lock, manifests)`（`plugins.py:307-376`）：校验锁的结构、规范顺序、`lock_sha256`（不符时 `E_PLUGIN_LOCK_DRIFT`），以及锁与 manifest 字节的绑定（不符时 `E_PLUGIN_LOCK_BINDING`）。**它不对磁盘上的资源文件求哈希。**
- 资源哈希是文件原始字节的 SHA-256：本次对 8 个插件共 11 个资源逐个求哈希，全部与锁一致。`.gitattributes:25,29` 把 `plugins/decisions/**` 与 `plugins/*/README.md` 设为 `-text`，避免检出时换行转换改变哈希。决策插件对问题清单另有一份逐字节核对，并在“只差 CRLF”时直说（`verify_battery_lock`，`scripts/codekit/decisions.py:308-357`）。
- 依赖与冲突：`resolve_plugins(manifests, enabled)`（`plugins.py:238`）。权限：`check_permission_intersection(manifest, allowed_permissions=..., platform_name=...)` 返回缺的权限与 `READY` / `BLOCKED`（`plugins.py:377-404`）。
- 配置语义：`plugins.enabled` 与 `plugins.allowed_permissions` 现在只有决策插件读（`decisions.py:513-521`）。值是列表时按列表判定，**缺省或不是列表时等于不限制**。
- **缺口**：`kit_config.KEYS`（`scripts/kit_config.py:165-185`）没有 `plugins`。所以：
  - `validate_config` 把手写的 `plugins` 键报成“未知键”（`kit_config.py:212-225`）；
  - `split_path` 拒绝 `config set plugins.enabled …`（`kit_config.py:245-249`）；
  - `_write_checked` 先整份校验再写，有错一个字节都不写（`kit_config.py:322-326`）。
- 插件文件所在的根是 `KIT_ROOT = Path(__file__).resolve().parent.parent`（`pi_dispatch.py:3672`），决策插件目录由它拼出（`pi_dispatch.py:3673`）。kit 从外部目录运行时，插件在 kit 里，配置在目标仓库里。

### 2.4 调度器转发与保护

- `config` 的转发：`cmd_config` 从调度器所在目录导入 `kit_config` 并调用 `kit_config.main(args, repo=…)`，导入失败时报 `DispatchError(EXIT_USAGE)`（`pi_dispatch.py:7118-7124`）；解析器用 `argparse.REMAINDER` 原样传参（`pi_dispatch.py:7502-7504`）。
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

不新造口径：用量字段沿用 `events-summary.json` 的 `USAGE_KEYS`；插件校验沿用 `codekit/plugins.py`；配置写入沿用 `kit_config` 的整份校验与原子替换；退出码沿用 `kit_config` 的常量；attempt 定位沿用 `resolve_run_dir`。

- **D1 两个新文件，照 `kit_config` 的结构写**：单文件、标准库、Python 3.10+，`main(argv=None, repo=None) -> int`，argparse 子命令，带 `--repo`。新文件不在保护路径内，可以委派给执行端；接入时才加进 `KIT_LOADED_FILES`（2.4）。
- **D2 `logs` 只读**：不写 `.agent/` 下任何文件，不跟随符号链接（遇到就跳过并计数）。理由：AGENTS.md 规定证据只读（2.1）。
- **D3 执行端用量只取 `events-summary.json` 的 `usage`**：与 `metrics` 同一来源、同一字段（2.1）。文件缺失、`usage` 缺失或不是对象时，这个 attempt 记为 unknown，不当 0。`logs usage` 只报 token，费用仍由 `metrics` 负责（用户决定 bb 的费用记 unknown）。
- **D4 规划端用量来自宿主会话记录，按 `message.id` 去重**：
  - 带用量的记录 = 顶层是对象、`message` 是对象、`message.id` 是非空字符串、`message.usage` 是对象。不看 `type` 字段。
  - 同一 `message.id` 的多条记录：四个计数字段都相同 → 只算一次（记重复条数）；有任何不同 → 记为冲突，这个 id 整个不计入，结果标为部分。
  - 去重跨所有给定的会话文件。
  - 时间：取同一 id 第一条记录的 `timestamp`。`--since` 含、`--until` 不含；时间必须带时区（`Z` 或偏移），否则用法错误。没有可解析 `timestamp` 的记录计数后跳过。
  - 只读用量、时间、模型与 `isSidechain`，不读也不输出 `content` 或其他字段。按模型、主线与子代理（`isSidechain`）分组。
  - 某个计数字段不是整数时，这条消息的该字段记 unknown，并计数。
  - 会话文件只从命令行显式给出的 `--transcript` 路径读取（文件，或目录下直接一层的 `*.jsonl`），不自动到用户目录里找。
  理由：2.2 的实测；不读对话内容；不越出用户指定的范围。
- **D5 `plugins` 的只读部分全部复用 `codekit/plugins.py`**：
  - manifest 与 lock 用 `codekit.protocols.strict_json_loads` 解析（重复键等直接拒绝），再交给 `validate_manifest`、`validate_lock(lock, {plugin_id: manifest})`；
  - 另对锁里的每个资源文件求原始字节 SHA-256：不存在、不是普通文件、是符号链接、解析后不在 `KIT_ROOT/plugins/<id>/` 之内、或哈希不符，都算不一致；只差 CRLF 时直说（与决策插件一致，2.3）；
  - 目录名必须等于 `plugin_id`；
  - 权限与启用状态用 `check_permission_intersection` 与配置里的列表判定；
  - 不执行 manifest 里 `checks` 的命令。
- **D6 `enable` / `disable` 的语义与决策插件的读法一致（`decisions.py:513-521`），并且不让“启用一个插件”隐性关掉其他插件**：
  - `plugins.enabled` 缺省（不限制）时：
    - `enable X` 不改 `enabled`，提示“当前不限制，所有插件都算启用”；
    - `disable X` 把“已安装的全部插件减去 X”写成显式列表（按 ID 排序），并打印这一变化：之后新增的插件不会自动启用。
  - `enabled` 是列表时：`enable X` 加入（去重、排序）；`disable X` 移除。
  - 权限：只有 `allowed_permissions` 是列表时才检查。`enable X` 缺的权限必须由 `--allow-permission <名>` 一个不多、一个不少地给出，这时一并写入 `allowed_permissions`；给多、给少或当前不限制时还给了，都是用法错误。`disable` 不碰 `allowed_permissions`。
  - 依赖与冲突：对启用之后的有效集合（`enabled` 缺省时就是全部已安装插件）跑 `resolve_plugins`，有错就拒绝。`disable X` 时，有效集合里还有插件 `depends_on` X 就拒绝。
  - `enable` 要求 X 的 manifest、lock、资源文件全部一致；`disable` 只要求 X 已安装（允许关掉坏掉的插件）。
  - 写入用 `kit_config.write_checked`（D7）：整份校验后原子替换，校验不过一个字节都不写。`--dry-run` 只打印将写入的 `plugins` 段。
  - 关掉 `decisions` 时提示：决策插件会因此变为 off（`decisions.py:515-518`）。
- **D7 `kit_config` 增加 `plugins` 键与公开的 `write_checked`**：
  - `KEYS["plugins"]`，校验函数 `_check_plugins`：缺省合法；必须是对象；子键只允许 `enabled`、`allowed_permissions` 与下划线开头的说明；`enabled` 是字符串列表，每项匹配 `PLUGIN_ID`（`plugins.py:19`）、不重复、并且在 `KIT_ROOT/plugins/` 下有同名目录与 `manifest.json`；`allowed_permissions` 是非空字符串列表、不重复。
  - `write_checked(repo, config)` 是现有 `_write_checked` 的公开名字，旧名保留。
  - 这样 `config show` 会列出 `plugins`，`config set plugins.enabled '[…]'` 也能用（`split_path` 只认已知键）。
  理由：2.3 的缺口；`plugins` 已经被决策插件读取，配置管理器却不认识它。
- **D8 接入沿用 `config` 的转发方式**：`cmd_logs`、`cmd_plugins` 与 `cmd_config`（`pi_dispatch.py:7118-7124`）同形；解析器同样用 `REMAINDER`。`KIT_LOADED_FILES` 加两个文件；`tests/test_kit_v280.py` 的 import 扫描改为同时跟随 `import kit_<名>` 形式的导入，让清单与实际加载一致。
- **D9 文档与权限**：README 命令表加 `logs`、`plugins`；AGENTS.md“Codex 的沙箱”一节把 `logs` 与 `plugins list/show/verify` 列为只读，`plugins enable/disable` 列为只写工作区；`.claude/settings.example.json` 放行 `logs` 与 `plugins list|show|verify`；CHANGELOG 加“未发布（themis-3.0 分支）”一节。
- **D10 错误处理**：两个新模块捕获 `pd.DispatchError` 与 `kit_config.ConfigError`，打印 `ERROR:` 一行并返回其退出码；参数错误由 argparse 处理（退出码 2）。不输出堆栈。

## 4. 接口

### 4.1 `logs`

| 命令 | 输出 | 退出码 |
|---|---|---|
| `logs list [--task ID] [--state S] [--json]` | 每个 attempt 一行：`task/attempt`、状态、状态时间、证据文件数、总字节、有没有 `summary.md`。按 task 名、attempt 编号排序。没有时打印“没有 attempt” | 0；参数错误 2 |
| `logs show <目标> [--json]` | 目标用 `resolve_run_dir` 解析。打印 attempt 路径与状态；`summary.md` 的内容（超过 64 KiB 截断并注明）；证据文件清单（相对路径与大小）。不打印其他文件的内容 | 0；找不到 2 |
| `logs search <正则> [--task ID] [--max N]` | 在后缀为 `.md`、`.txt`、`.log`、`.json`、`.jsonl` 的证据文件里逐行搜，输出 `相对路径:行号: 内容`，内容截到 200 个字符；`--max` 缺省 50，达到上限时注明 | 0（含没有匹配）；正则无效 2 |
| `logs usage [--task ID] [--transcript 路径 …] [--since 时间] [--until 时间] [--json]` | 两段：执行端（每个 attempt 的 `usage` 与合计，unknown 单独计数，按 `requested_model` 分组）；规划端（按模型与主线 / 子代理分组的四项 token，及去重、冲突、跳过的计数）。`--since` / `--until` 只作用于规划端 | 0；路径不存在或时间格式错 2 |

`--json` 的输出是一个对象，键名固定写在模块里，测试按键名断言。

### 4.2 `plugins`

| 命令 | 输出 | 退出码 |
|---|---|---|
| `plugins list [--json]` | 每个插件一行：ID、版本、启用（是 / 否 / 不限制）、锁（一致 / 漂移 / 无效）、资源文件（一致 / 不一致）、缺的权限、状态（READY / BLOCKED 与原因） | 0 |
| `plugins show <ID> [--json]` | manifest 的版本、api_version、capabilities、permissions、platforms、depends_on、conflicts、checks；每个资源的路径与哈希核对；锁的 generation 与 lock_sha256；配置里的启用与权限状态 | 0；ID 不存在 2 |
| `plugins verify [ID] [--json]` | 所选插件（缺省全部）的 manifest、锁、资源文件核对结果与问题清单 | 全部一致 0；有不一致 1；ID 不存在 2 |
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

两个子键都可以缺省；缺省就是不限制（与 `decisions.py:513-521` 一致）。

### 4.4 调度器转发

`python scripts/pi_dispatch.py logs …` 与 `python scripts/pi_dispatch.py plugins …` 原样转发给两个模块的 `main(args, repo=…)`；`--repo` 一并传过去。

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
- `plugins`：安装、升级、删除、执行插件的 `checks`、联网、generic 适配器插件、重新生成锁。
- 不改派遣流程的语义（prepare / run / check / verdict / integrate 不动）。
- 不引入配置 v3、角色绑定或方案（下一轮）。
- 不改 `scripts/codekit/plugins.py` 与 `scripts/codekit/decisions.py`（受保护；本轮只调用它们的公开函数）。
- 不改任何证据文件；不给 `pricing` 加 `bb/step-5-preview`（用户决定）。
- 多个进程同时改配置的竞争：`write_config` 用固定的临时文件名（`kit_config.py:228-235`），本轮沿用，不另加锁；见第 10 节。

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
| `tests/test_dispatch.py` | 新增转发场景 | 第 9 节 W 组 | 规划端 |
| `README.md`、`AGENTS.md`、`.claude/settings.example.json`、`CHANGELOG.md` | 命令表、Codex 沙箱一节、放行规则、未发布一节 | D9 | 规划端 |
| `.agent/design/3.0-首轮实测.md` | 新文件 | 实测记录 | 规划端 |
| `.agent/plans/kit-logs.v1.*`、`.agent/plans/kit-plugins.v1.*`、`.agent/reviews/…` | 新文件 | 合同与复审记录 | 规划端 |

### 7.2 刻意不改的

| 文件 | 理由 |
|---|---|
| `scripts/codekit/plugins.py`、`scripts/codekit/decisions.py` | 受保护；本轮只调用公开函数，语义不变 |
| `scripts/kit_install.py` | 发放清单取自 `KIT_LOADED_FILES`（`kit_install.py:192-197`），加进清单就会自动发放；由测试 W2 核对 |
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
| L2 | 同一 `message.id` 两条 usage 不同 | 随意取一条；冲突不报 |
| L3 | 坏 JSON 行、非对象行、没有 usage 的记录、`message.id` 不是字符串 | 崩溃，或悄悄算进去 |
| L4 | 记录恰好落在 `--since` 与 `--until` 上；时间不带时区 | 窗口边界错位；把不带时区的时间当本地时间 |
| L5 | 同一 `message.id` 出现在两个会话文件里 | 跨文件重复计数 |
| L6 | `isSidechain` 为真的记录 | 与主线混在一起 |
| L7 | attempt 没有 `events-summary.json`，或 `usage` 不是对象 | 把缺失当 0 |
| L8 | `.agent/runs` 不存在或为空；有 `_tmp` 这类非 task 目录；有不匹配 `attempt-NNN` 的目录 | 崩溃或误列 |
| L9 | 所有子命令跑一遍前后，逐字节比较 `.agent/` | 工具写了证据 |
| L10 | 证据里有很长的行和大量匹配 | 输出整份大文件或超过上限 |
| L11 | 会话记录的 `content` 里有形似密钥的文字 | 把对话内容打印出来 |
| L12 | 证据目录里有符号链接 | 跟随链接读到 runs 之外 |
| L13 | `logs show` 的目标在 runs 之外、或找不到 | 读 runs 之外的文件；崩溃而不是退出码 2 |

**P 组：`plugins`**

| 编号 | 场景 | 防止的失败 |
|---|---|---|
| P1 | 现有 8 个插件 | 把一致的插件报成不一致 |
| P2 | 资源文件改一个字节；只把 LF 改成 CRLF | 漏报漂移；CRLF 时不给提示 |
| P3 | `lock_sha256` 被改 | 漏报锁漂移 |
| P4 | manifest 被改（与锁绑定不符） | 漏报绑定不一致 |
| P5 | 资源路径是符号链接，或解析后不在插件目录内 | 读到插件目录之外 |
| P6 | 目录名与 `plugin_id` 不同；manifest 有重复键 | 接受不一致的插件 |
| P7 | `enabled` 缺省时 `enable X` | 写出只含 X 的列表，把其他插件全关掉 |
| P8 | `enabled` 缺省时 `disable X` | 写出空列表或漏掉其他插件；不提示语义变化 |
| P9 | `allowed_permissions` 是列表、X 缺权限、没给 `--allow-permission` | 悄悄加权限或写入了部分改动 |
| P10 | 给出的 `--allow-permission` 多于、少于所缺的权限；当前不限制时给了 | 授予无关权限 |
| P11 | `disable X`，而有效集合里另有插件 `depends_on` X | 关掉被依赖的插件 |
| P12 | `enable` 一个锁不一致的插件 | 启用坏掉的插件 |
| P13 | 配置里另有一个无效键时 `enable` | 绕过整份校验写入 |
| P14 | 写入中途失败（`os.replace` 抛错） | 留下半份配置 |
| P15 | 关掉 `decisions` | 不提示决策插件会变为 off |
| P16 | `--dry-run` | 实际写了文件 |

**C 组：`kit_config`**

| 编号 | 场景 | 防止的失败 |
|---|---|---|
| C1 | 合法的 `plugins` 段；`config show` | 新键不显示或被报未知 |
| C2 | `enabled` 不是列表、有重复、有未安装的 ID、ID 格式错；未知子键 | 接受会让插件悄悄失效的拼写错误 |
| C3 | `config set plugins.enabled '[…]'` | `split_path` 仍拒绝 |
| C4 | 现有决策插件测试 | `plugins` 语义被改动 |

**W 组：接入**

| 编号 | 场景 | 防止的失败 |
|---|---|---|
| W1 | `pi_dispatch.py logs --help`、`plugins --help` | 转发失效 |
| W2 | `KIT_LOADED_FILES` 含两个新文件；import 扫描一致；`kit_install check` 列出它们 | 新文件不受保护或不被发放 |
| W3 | 全量 `python -m pytest tests` | 回归 |

## 10. 待用户拍板

1. **版本标注**：本轮在 CHANGELOG 记为“未发布（themis-3.0 分支）”，合并到 master 时再定版本号（推荐）；或现在就记为 2.11.0。
2. **会话文件的读取范围**：只读命令行显式给出的路径（推荐）；或允许自动到 `~/.claude/projects/` 下找本仓库的会话文件。
3. **配置并发写**：沿用 `kit_config` 现有的“固定临时文件名 + 原子替换”，不加锁（推荐，本轮不扩大范围）；或本轮就给配置写入加锁。
4. **合并到 master**：闸二通过后由你决定，不自动合并。
