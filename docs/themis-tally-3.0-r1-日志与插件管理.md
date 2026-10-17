# Themis Tally 3.0 第一轮设计：日志管理与插件管理的第一片

状态：2gate 闸一第 3 轮零 Blocking（2026-10-17）后进入实现；实现中发现 D4 的去重前提在子代理会话记录上不成立，按 2gate 改设计并补送闸一第 4 轮（只审 D4 的改动，见 §0 的 impl-3），第 4 轮零 Blocking。第 3 轮的 Should-fix 与 Nit 在过闸后直接采纳（见 §0 的 r3 各行），由闸二一并核对。

- 分支：`themis-3.0`（本地，不推送）。起点 `8fb12ed`（master），之上是设计说明提交 `0f4879c` 与本文的历次提交。
- 上位设计：`docs/themis-tally-3.0-四端分层解耦架构.md` 第 8.2 节（日志管理）、8.3 节（插件管理）、13 节（首轮实战）。
- 下文 `file:line` 都在 `8fb12ed` 上核对过。

## 0. 审核变更对照表

| 编号 | 结论 | 本稿处置 |
|---|---|---|
| r4-S1 | 第 4 轮 Should-fix：L1、L2 测不出“取最后一条”“只认 `tool_use` / `end_turn`”“只比较中间记录的 model”三种错误实现；原有的固定夹具若不带 `stop_reason` 会全部变成“未完成” | 采纳：L1 对流式夹具做全排列（最终记录不在最后）并把同一 id 拆到不同文件；`stop_reason` 为 `max_tokens` 的记录也是最终记录；L2 补“中间记录 `isSidechain` 与最终记录不同”；L2 的 A、A、B 与五类固定输入都带最终标记 |
| r4-N1 | 第 4 轮 Nit：D4 第 7 步的允许读取字段漏了 `message.stop_reason` | 采纳：第 7 步加上 |
| g2r1-B1 | 闸二第 1 轮 Blocking：plugins 的写入门禁与修复提示的模拟经 `verify_battery_lock` 直接读题库、不查链接；questions/ 是 junction 时 dry-run 与写入都放行，而 verify 判“无效：链接”（规划端探针复现） | `kit_config.battery_link_problem()` 在读之前从 KIT_ROOT 逐级查 questions/ 与其中每个 `*.json`；`_check_decisions`（整份校验与提示模拟）与 plugins 的门禁都先过它，经过链接就不读。调度器运行时的 `load_locked_batteries` 仍不查链接，但读到的字节必须等于锁里的（2.8 的内容锁），列为残余 |
| g2r1-B2 | 闸二第 1 轮 Blocking：plugins 根列不出来（OSError）被当作“没有插件”，`verify --json` 报 ok、退出 0（探针复现） | `_root_problem()`：根是链接或列不出来都作为一条问题；list 输出它（退出 0），verify 计为问题（退出 1），带 ID 的命令退出 2 并说明原因 |
| g2r1-B3 | 闸二第 1 轮 Blocking：两条堆栈路径——`--repo` 指向文件时所有命令冒 NotADirectoryError（`Repo.discover` 直接以它为 git 的工作目录）；配置是嵌套过深的 JSON 时 `load_config` 冒 RecursionError（探针复现） | `Repo.discover` 先确认是目录，否则一行 ERROR、退出 2；`load_config` 收集 RecursionError 为 ConfigError。遗留行为的刻画用例 LB-EXIT-029（原来分平台钉住“Windows 堆栈退出 1”“POSIX 误报找不到 git 退出 3”）改为跨平台的新行为 |
| g2r1-S1 | 闸二第 1 轮 Should-fix：修复提示用单引号包 JSON，值里有单引号（如 `don't`）时提示没法原样执行 | 采纳：JSON 里的单引号写成 `\u0027`（合法的 JSON 转义），整段放进单引号在 bash 与 PowerShell 下都能执行 |
| g2r1-S2 | 闸二第 1 轮 Should-fix：`PLUGIN_ID.match` 放过末尾的换行（`"decisions\n"` 能写进配置） | 采纳：kit_config 的格式校验与枚举、kit_plugins 的 ID 校验与枚举都用 `fullmatch` |
| g2r1-S3 | 闸二第 1 轮 Should-fix：`logs usage` 的文本输出没有写明规划端统计是“部分” | 采纳：文本的规划端标题行在 partial 时写明 |
| g2r1-N1 | 闸二第 1 轮 Nit：L4 用固定种子的 30 次随机排列，不是全部置换 | 知情接受：记录数一多全部置换就不可行，固定种子的随机排列可复现、覆盖了文件顺序与文件内顺序两个维度；不改 |
| g2r1-测试 | 闸二第 1 轮覆盖意见：P8 只断言三个 ID、P9 受影响清单不是完整集合、P10 不查拒绝前后字节、P14 比较解析后的对象、W2 只查 ID | 采纳：P8 断言完整列表；P9 从副本的 manifest 算出期望集合后逐个比对；P10、P14 改为字节不变；W2 断言装好的决策插件“锁:一致”且 READY。P1、P2 的逐插件精确断言由 v2 增补的用例覆盖，不另改 |
| impl-5 | 实现中发现（T1 attempt-001 复审时用含 NUL 的目标做探针）：`pi_dispatch.is_link_or_junction` 在 Windows 上对含 NUL 的路径抛 `ValueError`——`os.path.islink` 对这类路径返回假，但随后的 `os.lstat` 抛 `ValueError`，而函数只捕获 `OSError`。它是 D11 的公共谓词，调用方都按“是不是链接”使用 | 捕获 `(OSError, ValueError)` 并返回假，与 `os.path.islink` 一致；`tests/test_kit_v300.py` 的 `LinkPredicateInputs` 覆盖（含 NUL、孤立代理字符，以及 `first_link_component` 经过它的路径） |
| impl-4 | 实现中发现：§7.1 把 W1、W2 放在 `tests/test_dispatch.py`，但那里的场景用 `check()` 记录结果、不抛异常，用 pytest 跑全量时失败的检查也显示为通过（只有以脚本方式运行才汇总失败） | W1、W2 改放新的 unittest 模块 `tests/test_kit_v300.py`（§7.1 相应改写）；`test_dispatch.py` 这一既有问题不在本轮范围，记入第 6 节 |
| impl-3 | 实现中发现（T1 规划子代理完成后核对它的会话记录）：子代理的会话记录在 `<会话目录>/subagents/agent-<id>.jsonl`，同一回复先写若干条 `message.stop_reason` 为 null、`output_tokens` 未到终值的中间记录，最后一条才带最终用量与 `stop_reason`；40 个 `message.id` 里 33 个各条用量不同。按原 D4，这些 id 全被判为冲突、不计入。主会话记录里每条都是最终记录（145 个 id 全部一致），所以第 2 轮的实测没有暴露这一点 | D4 第 3 步改为：组内只比较最终记录（`stop_reason` 为非空字符串）；中间记录不参与计数，但其模型与 `isSidechain` 必须与最终记录一致；没有最终记录的 id 记为未完成、不计入、结果标“部分”。§2.2 补事实；计数与 id 分类相应增加；L1、L2 补流式用例。送闸一第 4 轮 |
| impl-2 | 实现记录：修复提示原定三个候选，其中“换成语义等价的合法对象”与“删掉非法子键”得到的配置完全相同，永远不会被选中；第三个候选若无条件取“全部插件减去 decisions”，会把用户已有的显式列表扩大 | D6 的候选改为两个；第二个候选保持已有的合法 `enabled` 列表、只去掉 `decisions`（`tests/test_kit_config.py` 的 `PluginsKey` 覆盖） |
| impl-1 | 实现前自查（过闸后，闸二核对）：D6 与 D7 共用的修复提示生成函数、`logs` 与 `plugins` 共用的链接检查，若不先定下位置，两个 Pi 任务会各自手抄一份（2gate 第 ③ 步禁止） | 新增 D11：两者都由规划端先实现，执行端只调用。`kit_config.plugins_fix_hint`；`validate_config` 加 `hints` 参数，模拟候选时传 `hints=False`，避免重入。`pi_dispatch.py` 把现有的 `_is_link_or_junction`（`pi_dispatch.py:5203-5220`）公开为 `is_link_or_junction`，新增 `first_link_component`。写进 §7.1 |
| r3-S1 | 第 3 轮 Should-fix：D8 的“找第一个非选项词”会把 `--version plugins …`、`-h plugins …`、`--unknown plugins …`、`-- plugins list` 也截获 | 过闸后采纳：截获只消费完整合法的 `--repo <值>` / `--repo=<值>`；遇到其他任何以 `-` 开头的词（含 `--`、`-h`、`--version`、未知选项）或 `--repo` 缺值，立即把完整原始 argv 交给 argparse，不再寻找。W1 补对应用例，并断言这些输入下游调用次数为零 |
| r3-S2 | 第 3 轮 Should-fix：决策插件生效且题库损坏、同时两个子键都是 `null` 时，三种修复提示全部写不进去 | 过闸后采纳：修复提示在给出之前，先用同一整份校验模拟“执行该命令后的配置”，模拟通过才给出；候选依次是：删掉非法子键；把 `plugins` 换成等价的合法对象；决策插件生效且题库不一致时，换成“`enabled` = 当前布局全部插件减去 `decisions`”的合法对象（一次替换同时修好非法值并关掉决策插件）。都不通过时只报告错误、不给提示。D6 的“可以落盘”加前提：其余配置与环境校验通过（`kill_grace_seconds`、`worktree_root` 等仍可能挡住写入，这是既有行为）。P13、C2 补这个组合 |
| r3-S3 | 第 3 轮 Should-fix：P5 只断言报错，测不出“先读取、后检查”的错误实现 | 过闸后采纳：P5 用读取替身断言被拒绝的路径从未被读取，并断言检查失败后没有调用 `verify_battery_lock` |
| r3-N1 | 第 3 轮 Nit：`non_integer_fields` 的单位与各计数是否互斥没有说明 | 过闸后采纳：D4 第 7 步写明每个 id 恰好落入“冲突、无可用时间、窗口外、计入”四类之一；按行或按记录的计数与 id 分类可以重叠；`non_integer_fields` 按“去重后的消息 × 字段”统计，只统计计入的消息。L2 补一组固定预期 |
| r2-B1 | 第 2 轮 Blocking：r1-B2 没有闭环。写入走 `write_checked` 的整份校验，决策插件生效时会核对它的题库（`kit_config.py:151-160`、`220-224`），题库坏了就连 `disable code-change` 也写不进去 | 保留整份校验（2.8 起的现有规则，任何配置写入都受它约束，不只是 `plugins`），收窄 D6 的承诺：不校验其他插件的 manifest、lock 与资源文件，但写入仍受整份校验约束。D6 写明这种情况的判断与恢复顺序：先 `plugins disable decisions` 或 `config decisions off`（写入后决策插件不再生效，不再触发题库核对，所以能落盘），修好题库再启用。补 P12 的“决策插件生效且题库损坏”用例 |
| r2-S1 | 第 2 轮 Should-fix：记录里可解析但不带时区的时间无法与带时区的时间比较 | D4：记录的时间也必须带时区，统一换算到 UTC 再取最小值；不带时区的记录时间不可用并计数。补 L5 |
| r2-S2 | 第 2 轮 Should-fix：两个子键都非法时，按提示逐个 `unset` 都写不进去（`cmd_unset` 每次整份校验，`kit_config.py:348-366`） | D6、D7 的修复提示按情况给出：只有一个非法时 `config unset plugins.<子键>`；两个都非法时 `config unset plugins`（两者在决策插件的读法里都等于不限制，删掉整个键语义不变），或用 `config set plugins '<完整 JSON>'` 一次替换。C2、P13 断言提示的命令确实能成功 |
| r2-S3 | 第 2 轮 Should-fix：`verify_battery_lock` 抛的 `DecisionError` 是 `RuntimeError` 子类（`decisions.py:74`），D10 收集不到 | D5、D10 把 `DecisionError` 纳入逐插件收集。P2 断言没有堆栈、`verify` 退出码 1、`list` 继续列出其他插件 |
| r2-S4 | 第 2 轮 Should-fix：`add_help=False` 加 `REMAINDER` 时，以 `-` 开头的第一个参数（`--help`、`--repo`）不会被收进 `REMAINDER`，`parse_args` 报未识别参数（已在本机 Python 3.10.19 复现，退出码 2） | D8 改为在 `pi_dispatch.main` 调用 argparse 之前截获：跳过全局选项后，第一个词是 `logs` 或 `plugins` 就把其后全部参数原样交给下游。W1 覆盖 `plugins --help`、`logs --repo <路径> list` 与全局 `--repo` |
| r2-S5 | 第 2 轮 Should-fix：manifest.json、lock.json 本身是链接时仍会被读取；`verify_battery_lock` 还会再读一次（`decisions.py:322-323`） | D5：实际读取的每个文件（manifest、lock、资源、决策插件的 `questions/` 目录及其中每个清单）读之前都过逐级链接检查，任一失败就停止该插件的后续读取。补 P5 |
| r2-S6 | 第 2 轮 Should-fix：`--allow-permission` 写入的是共享权限列表，会让其他需要同一权限的插件也从 BLOCKED 变成 READY（`read-candidate` 被 7 个任务插件共用） | D6 收窄承诺：不改变其他插件的启用成员资格；授予权限时列出所有因此满足权限条件的插件（`--dry-run` 同样列出）。P9、P10 断言这份清单 |
| r2-N1 | 第 2 轮 Nit：冲突组是否计重复、跳过计数按行还是按消息没有定义 | D4 第 7 步定义每个计数；L2 断言具体数字 |
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
- 链接检查的现成做法：`kit_install._is_link` 同时识别符号链接与 Windows 重解析点（junction），`_link_level` 从根往下逐级查（`scripts/kit_install.py:92-112`）。

### 2.2 宿主会话记录（Claude Code，2026-10-17 在本机核对）

- 位置：`~/.claude/projects/<项目目录转写>/<会话 ID>.jsonl`，每行一个 JSON 对象。
- 带用量的记录：`message` 是对象，里面有字符串 `id`、`model` 与 `usage` 对象。`usage` 含 `input_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`、`output_tokens`（另有 `server_tool_use` 等字段）。记录顶层有 `timestamp`（ISO 8601，带 `Z`）、`requestId`、`sessionId`、`isSidechain`。
- **同一次回复会写成多条记录**：每个内容块一条，每条都带同一个 `message.id` 和同一份 `usage`。本会话核对结果：174 条 usage 记录只对应 57 个 `message.id`，同一 id 的 usage 完全一致，`requestId` 与 `message.id` 一一对应。直接求和会多算两倍多。
- 本会话里调用过的 advisor 没有出现在这些 usage 记录里：174 条记录的 `message.model` 全是主模型。
- **子代理的会话记录不同**（2026-10-17 核对 T1 规划子代理的记录）：
  - 位置是 `<会话目录>/subagents/agent-<id>.jsonl`，记录的 `isSidechain` 全为真；
  - 同一回复在流式生成时先写若干条中间记录：`message.stop_reason` 为 null，`output_tokens` 还没到终值（例如 8），输入与缓存两项已经是终值；最后一条是最终记录，`stop_reason` 为 `tool_use` 或 `end_turn`，带最终的 `output_tokens`（例如 800）；
  - 该记录 40 个 `message.id` 里，33 个的各条用量不同，全部是这种“中间记录 + 最终记录”；每个 id 都有且只有一条最终记录；
  - 主会话记录（同日 145 个 id）每条都带 `stop_reason`，同一 id 的各条完全一致，没有中间记录；
  - 这个子代理的 `message.model` 是 `claude-haiku-5-5`，不是主会话的模型：本环境的子代理缺省模型不同于主会话。
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
- 决策插件另有专用核对 `verify_battery_lock`（`scripts/codekit/decisions.py:312-357`）：
  - `questions/` 下多出锁里没有的清单、锁里有而缺失的清单、字节不符都算不一致，只差 CRLF 时直说（`decisions.py:339-350`），不一致时抛 `DecisionError("battery_drift", …)`（`decisions.py:353`）；
  - 它自己用 `read_text` 读 `manifest.json` 与 `lock.json`（`decisions.py:322-323`），会跟随链接；
  - `DecisionError` 是 `RuntimeError` 的子类（`decisions.py:74`）。
- 配置的整份校验对每个已知键都跑一遍校验函数（`kit_config.py:220-224`）。其中 `_check_decisions` 在决策插件生效时调用 `verify_battery_lock`，题库不一致就报错（`kit_config.py:151-160`）。生效的判定是 `mode != "off"`（`decisions.py:423-424`），而 `plugins.enabled` 不含 `decisions`、`allowed_permissions` 缺 `network-decisions` 或有 `.agent/DECISIONS_OFF` 时 mode 会被置为 off（`decisions.py:509-521`）。所以决策插件生效且题库不一致时，**任何**配置写入都会被拒绝；把决策插件关掉的那次写入除外，因为写入后它不再生效。
- `config unset` 每次都走整份校验（`kit_config.py:348-366`）。
- 权限：`check_permission_intersection(manifest, allowed_permissions=..., platform_name=...)` 返回缺的权限与 `READY` / `BLOCKED`（`plugins.py:377-404`）。权限列表是所有插件共用的：`read-candidate` 被 7 个任务插件同时要求。
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
- `REMAINDER` 收不进以 `-` 开头的第一个参数：本机 Python 3.10.19 复现，`plugins --help`（`add_help=False` 时）与 `plugins --repo x list`（两种写法都）由 `parse_args` 报“unrecognized arguments”，退出码 2。调度器入口直接用 `parse_args`（`pi_dispatch.py:7572`）；顶层只有 `--repo` 与 `--version` 两个选项（`pi_dispatch.py:7394-7395`）。
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
  3. **全局去重**：把所有给定文件的候选记录按 `message.id` 分组（与读取顺序无关）。组内 `message.stop_reason` 是非空字符串的记录是**最终记录**，其余是流式生成时的**中间记录**（2.2）。
     - 中间记录不参与计数，但它们的 `message.model` 与 `isSidechain` 必须与最终记录相同，否则这个 id 记为冲突；
     - 有最终记录时：所有最终记录的四个计数字段（`input_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`、`output_tokens`）、`message.model` 与 `isSidechain` 必须全部相同，相同就只算一次；有任何不同就记为冲突。冲突的 id 整个不计入，结果标为“部分”；
     - 没有最终记录（流被中断）：这个 id 记为未完成，不计入，结果标为“部分”。
  4. **代表时间**：记录的 `timestamp` 必须是带时区（`Z` 或偏移）的 ISO 8601 时间，统一换算到 UTC；不带时区或无法解析的记录时间不可用，计数。代表时间是同一组里所有可用时间的最小值；一个可用时间都没有的 id 计数后跳过。
  5. **窗口**：去重之后再按代表时间过滤，`--since` 含、`--until` 不含；命令行的时间必须带时区（`Z` 或偏移），否则用法错误。
  6. **计数字段**：某个字段不是整数时，这条消息的该字段记 unknown 并计数，其余字段照常计入。
  7. **输出**：按模型、主线与子代理（`isSidechain`）分组的四项 token，以及下面这些计数。只读用量、时间、模型、`isSidechain` 与 `message.stop_reason`，不读也不输出 `content` 或其他字段。
     - `skipped_lines`：按原因分开（`bad_json`、`not_object`、`not_candidate`），单位是行；
     - `intermediate_records`：所有组里中间记录的条数；
     - `duplicate_records`：只在既不冲突也非未完成的组里统计，等于组内最终记录数减 1 的总和；
     - `conflict_ids` 与 `conflict_records`：冲突组的个数与这些组里的记录总数（冲突组不计入 `duplicate_records`）；
     - `incomplete_ids`：没有最终记录的组的个数；
     - `unusable_timestamps`：不带时区或无法解析的记录时间，单位是记录；
     - `ids_without_time`：一个可用时间都没有、因而跳过的 id；
     - `outside_window_ids`：去重后因窗口被排除的 id；
     - `non_integer_fields`：计数字段不是整数的次数。
     所有计数都在全局分组之后得出，与读取顺序无关。每个 id 恰好落入五类之一：冲突、未完成、无可用时间、窗口外、计入；判定顺序是先冲突，再未完成，再无可用时间，再窗口。按行或按记录的计数（`skipped_lines`、`intermediate_records`、`duplicate_records`、`conflict_records`、`unusable_timestamps`）与 id 分类可以重叠，不要相加当作互斥分类。结果在 `conflict_ids` 或 `incomplete_ids` 大于 0、或有给定的会话文件读不出来时标为“部分”。`non_integer_fields` 按“去重后的消息 × 字段”统计，只统计计入的消息。
  8. **覆盖范围**：只统计会话记录里有的调用。advisor 等不写进会话记录的调用不在其中（2.2），所以规划端用量是下界，输出里注明。
  理由：2.2 的实测；结果必须与文件顺序、记录顺序无关；不读对话内容；不越出用户指定的范围。
- **D5 `plugins` 的只读部分复用 `codekit/plugins.py`，逐插件独立核对**：
  - 插件目录：`KIT_ROOT/plugins/` 下名字匹配 `PLUGIN_ID`（`plugins.py:19`）的直接子目录；`plugins` 目录本身与每个插件目录都不能是链接或 junction。
  - **读前检查**：实际读取的每个文件（`manifest.json`、`lock.json`、每个资源文件，以及决策插件的 `questions/` 目录和其中每个 `*.json`）在读之前都要从 `KIT_ROOT` 往下逐级检查链接与 junction，并确认是普通文件（目录则确认是普通目录）。任何一项失败就停止这个插件的后续读取与核对，状态记为“无效：链接”。
  - manifest 与 lock 用 `codekit.protocols.strict_json_loads` 解析（重复键等直接拒绝）。
  - 每个插件单独核对：`validate_manifest`，目录名必须等于 `plugin_id`；`depends_on` 或 `conflicts` 非空 → 记为“本轮不支持”，不再调用 `validate_lock`（2.3：单插件注册表在有依赖时必然失败）；否则 `validate_lock(lock, {plugin_id: manifest})`。
  - 资源文件：用 `validate_lock` 返回的规范化路径。从 `KIT_ROOT` 往下逐级检查链接与 junction（插件根、中间目录、文件本身）；路径必须以 `plugins/<id>/` 开头；文件必须是普通文件；原始字节 SHA-256 必须等于锁里的值，只差 CRLF 时直说。
  - `decisions` 在读前检查通过后另调用 `verify_battery_lock`（2.3），把它抛出的 `DecisionError` 并入该插件的问题（包括多出的题库文件）。
  - 权限与启用状态：用 `check_permission_intersection` 与配置里的列表判定；`enabled` 里列了、但当前布局没有安装的 ID，单独报告。
  - 不执行 manifest 里 `checks` 的命令。
- **D6 `enable` / `disable` 的语义与决策插件的读法一致（`decisions.py:513-521`）**。承诺的范围：
  - 一次操作只改变 X 的启用成员资格（`enabled` 里有没有 X），外加一种会明确提示的形式变化：`disable` 把“不限制”改成显式列表；
  - 不校验其他插件的 manifest、lock 与资源文件，坏掉的其他插件不会挡住操作；
  - `--allow-permission` 写入的是共享的权限列表，会让其他需要同一权限的插件也满足权限条件，影响范围在输出里列出；
  - 写入仍受 `kit_config` 的整份校验约束，见下面的“写入”；所以“可以落盘”的前提是其余配置与环境的校验也通过（例如 `kill_grace_seconds`、`worktree_root` 仍可能挡住写入，这是既有行为）。

  具体规则：
  - **非列表值**：`plugins.enabled` 或 `plugins.allowed_permissions` 存在但不是列表（例如 `null`）→ 拒绝，不做隐式规范化。
  - **修复提示**（D6 与 D7 共用一个生成函数）：给出之前，先用同一整份校验模拟“执行该命令之后的配置”，模拟通过才给出。候选依次是：
    1. 删掉非法的子键：只有一个非法时 `config unset plugins.<子键>`，两个都非法（或 `plugins` 本身不是对象）时 `config unset plugins`（两者在决策插件的读法里都等于不限制）；
    2. 用 `config set plugins '<JSON>'` 一次替换成合法对象，其中 `enabled` 去掉 `decisions`：原来有合法的 `enabled` 列表就保持原样、只去掉 `decisions`；原来缺省或非法（都等于不限制）就取当前布局全部插件减去 `decisions`。合法的 `allowed_permissions` 与下划线说明保留。这一条用于决策插件生效且题库不一致的情况：一次替换同时修好非法值并关掉决策插件。
    都模拟不过时只报告错误，不给出执行不了的提示。（实现时发现，“换成语义等价的合法对象”与第 1 条得到的配置完全相同，永远不会被选中，所以去掉了，见 §0 的 impl-2。）
  - **`enable X`**：
    - X 的 manifest、lock、资源文件（以及 `decisions` 的题库核对）必须全部一致；`depends_on` 或 `conflicts` 非空 → 拒绝（本轮不支持）。不校验其他插件的 manifest、lock 与资源文件。
    - `enabled` 缺省（不限制）时不改 `enabled`，提示“当前不限制，所有插件都算启用”；`enabled` 是列表时加入 X（去重、按 ID 排序）。
    - 权限只在 `allowed_permissions` 是列表时检查：缺的权限必须由 `--allow-permission <名>` 一个不多、一个不少地给出，这时一并写入 `allowed_permissions`；给多、给少或当前不限制时还给了，都是用法错误。
    - 授予权限时，列出当前布局下所有因此不再缺这项权限的其他插件（`--dry-run` 同样列出）。
  - **`disable X`**：
    - 只要求 `KIT_ROOT/plugins/X/` 存在（允许关掉坏掉的插件），不校验其他插件的 manifest、lock 与资源文件。
    - `enabled` 缺省时，把“当前布局下全部插件目录名（匹配 `PLUGIN_ID`，不论 manifest 好坏）减去 X”写成显式列表（按 ID 排序），并打印这一变化：之后新增的插件不会自动启用。
    - `enabled` 是列表时移除 X；不在列表里就提示没有变化。
    - 不碰 `allowed_permissions`。
    - 关掉 `decisions` 时提示：决策插件会因此变为 off（`decisions.py:515-518`）。
  - **写入**：用 `kit_config.write_checked`（D7），整份校验后原子替换，校验不过一个字节都不写。`--dry-run` 只打印将写入的 `plugins` 段，不写文件。
  - **决策插件生效且题库不一致时**（2.3）：写入前先用新配置判断决策插件是否仍然生效（`settings_from_config(...).active`），生效就先跑 `verify_battery_lock`。不一致 → 拒绝，配置不变，并提示恢复顺序：先 `plugins disable decisions` 或 `config decisions off`，这两种写入都会让决策插件不再生效，因而不再触发题库核对、可以落盘；修好题库（或经复审后重新生成锁）再启用。这条规则来自现有的整份校验，本轮不放宽。
- **D7 `kit_config` 增加 `plugins` 键与公开的 `write_checked`**：
  - `KEYS["plugins"]`，校验函数 `_check_plugins`：缺省合法；必须是对象；子键只允许 `enabled`、`allowed_permissions` 与下划线开头的说明。
  - `enabled`：字符串列表，每项匹配 `PLUGIN_ID`，不重复。**不检查是否已安装**：同一份配置要在两种布局下都合法（2.3）；列入但未安装由 `plugins list` / `verify` 报告。
  - `allowed_permissions`：非空字符串列表，不重复。
  - 任一子键不是列表（包括 `null`）→ 错误，修复提示用 D6 的同一个生成函数（先模拟整份校验，通过才给出）。
  - `write_checked(repo, config)` 是现有 `_write_checked` 的公开名字，旧名保留。
  - 这样 `config show` 会列出 `plugins`，`config set plugins.enabled '[…]'` 也能用（`split_path` 只认已知键）。
  理由：2.3 的缺口；`plugins` 已经被决策插件读取，配置管理器却不认识它。
- **D8 接入沿用 `config` 的转发方式**：
  - `cmd_logs`、`cmd_plugins` 与 `cmd_config`（`pi_dispatch.py:7118-7124`）同形：从调度器所在目录导入模块，导入失败报 `DispatchError(EXIT_USAGE)`，下游退出码原样返回。
  - **在 argparse 之前截获**（2.4：`REMAINDER` 收不进以 `-` 开头的第一个参数）：`pi_dispatch.main` 从头扫描 argv：
    - 只消费完整合法的全局 `--repo <值>` 或 `--repo=<值>`（值不能为空，也不能以 `-` 开头）；
    - 遇到其他任何以 `-` 开头的词（包括 `--`、`-h`、`--help`、`--version`、未知选项）或 `--repo` 缺值，立即把**完整原始 argv** 交给 argparse，不再寻找；
    - 遇到的第一个不以 `-` 开头的词是 `logs` 或 `plugins` 时，把它之后的全部参数原样交给对应模块的 `main(args, repo=<全局 --repo>)`，不经过 argparse；是其他词（例如 `doctor --out plugins` 里的 `doctor`）就交给 argparse。
    - 下游参数里自己的 `--repo` 优先（与 `kit_config.main` 的做法一致，`kit_config.py:634-635`）。
  - 解析器里仍登记 `logs`、`plugins` 两个子命令，只用于 `pi_dispatch.py --help` 的命令列表。
  - `config` 的转发不在本轮改动之列（第 6 节）。
  - `KIT_LOADED_FILES` 加两个文件。
  - `tests/test_kit_v280.py` 的 import 扫描改为同时跟随 `import kit_<名>` 形式的导入（只在 `scripts/kit_<名>.py` 存在时），让清单与实际加载一致。
- **D9 文档与权限**：README 命令表加 `logs`、`plugins`，并写明安装布局下只有决策插件；AGENTS.md“Codex 的沙箱”一节把 `logs` 与 `plugins list/show/verify` 列为只读，`plugins enable/disable` 列为只写工作区；`.claude/settings.example.json` 放行 `logs` 与 `plugins list|show|verify`；CHANGELOG 加“未发布（themis-3.0 分支）”一节。
- **D11 共用代码由规划端先实现，执行端只调用**（2gate：会被抄散的谓词统一收口）：
  - `kit_config.plugins_fix_hint(config, repo) -> Optional[str]`：D6、D7 的修复提示生成函数，规则见 D6。它用 `validate_config(candidate, repo, hints=False)` 模拟候选。
  - `kit_config.validate_config(config, repo, *, hints=True)`：`plugins` 键的校验出错、并且 `hints` 为真时，在这条错误后面附上 `plugins_fix_hint` 的结果；`_check_plugins` 自己只报不带提示的错误。所以模拟候选时不会再次生成提示，不会重入。
  - `pi_dispatch.is_link_or_junction(path)`：把现有的 `_is_link_or_junction`（`pi_dispatch.py:5203-5220`，含 Python 3.12 的 `isjunction` 与 Windows 重解析点属性）公开，旧名保留。
  - `pi_dispatch.first_link_component(root, rel) -> Optional[str]`：从 `root` 往下逐级检查 `rel` 的每一级，返回第一个是链接或 junction 的那一级（相对 `root` 的 POSIX 路径），没有则 `None`；与 `kit_install._link_level`（`kit_install.py:104-112`）同义。`kit_install` 里那份既有的副本本轮不动。
  - 边界判断用现有的 `pi_dispatch.is_within`（`pi_dispatch.py:558-560`）。
  - `kit_logs` 与 `kit_plugins` 只能调用这些函数，不得另写同类实现。
- **D10 错误处理**：
  - `plugins`：逐插件收集 `ValueError`（含 `ProtocolError`、`PluginError`）、`DecisionError`（`RuntimeError` 的子类，2.3）与 `OSError`，记为该插件的问题，其余插件照常列出与核对。
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
- 规划端的合同、oracle、概要步骤与审核在新的子代理里做（与本会话同一模型），用量取子代理结果里报告的数字；取不到时按上位设计 13.3 的弱信号口径记录。第一次启动子代理时先核实三件事：它的用量记在哪里（单独的文件，还是主会话记录里 `isSidechain` 为真的记录）、`message.model` 是什么、Agent 结果里有没有 token 合计。
- 两组的规划端子代理依次运行，不让时间窗口重叠（D4 只按模型与 `isSidechain` 分组，重叠的子代理分不开）；Pi 的派遣可以并行。
- 测量的含义要写清楚：2gate 已经为两组都产出了经审核的详细设计，所以本轮比较的是“谁把一份已批准的设计展开成合同与 oracle”，不是“从概要步骤到合同”。B 组的规划端成本 = 写起草派遣的 `TASK:` 合同 + 审核起草结果；合同端成本 = 起草那次 Pi 运行，按 task-id 与执行端的运行分开记。
- B 组起草派遣的参考实现放在草稿 worktree 里的真实路径 `scripts/kit_plugins.py`，oracle 正常导入它；发布时只取合同与 oracle。起草的 attempt 给出 verdict 后用 `mark SUPERSEDED --ref <发布提交>` 收尾，永不 `integrate`。起草运行内只检查草稿 JSON 能否解析；正式的 `validate` 在发布进 `.agent/plans/` 时做。
- B 组起草派遣的 `TASK:` 合同写明：合同里哪些取舍交给它在本文 4.2 与 D5、D6 的范围内决定，每一项都要写进执行报告的 `interpretations`。

## 6. 刻意不做

- `logs`：导出、归档、封存清单校验、实时跟随、占用统计、费用计算、Codex 会话记录的导入、自动发现会话文件、读取对话内容。
- `plugins`：安装、升级、删除、执行插件的 `checks`、联网、generic 适配器插件、重新生成锁；**带 `depends_on` 或 `conflicts` 的插件的启用**（依赖语义与锁的布局留到插件安装那一轮统一定义，现有 8 个插件都没有依赖）。
- 不改派遣流程的语义（prepare / run / check / verdict / integrate 不动）。
- 不改 `config` 的转发：`config --help` 现在由外层 argparse 处理，属既有行为。
- **调度器 `resolve_run_dir` 的边界缺口**（2.1）：本轮的 `logs` 自己守边界，不依赖它；调度器本身的修复会影响 `status`、`check` 等多个命令，另立任务（第 10 节第 5 项）。
- 不引入配置 v3、角色绑定或方案（下一轮）。
- 不改 `scripts/codekit/plugins.py` 与 `scripts/codekit/decisions.py`（受保护；本轮只调用它们的公开函数）。
- 不改任何证据文件；不给 `pricing` 加 `bb/step-5-preview`（用户决定）。
- 多个进程同时改配置的竞争：`write_config` 用固定的临时文件名（`kit_config.py:228-235`），本轮沿用，不另加锁（第 10 节第 3 项）。
- `tests/test_dispatch.py` 的场景在 pytest 下不会失败（`check()` 只记录结果，impl-4）：既有问题，影响所有版本的端到端场景，另立任务；本轮的新场景放在 unittest 模块里。

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
| `scripts/kit_config.py` | `KEYS`（`165-185`）、新增 `_check_plugins`、`_write_checked`（`322-326`）旁加公开名、`validate_config`（`212-225`）加 `hints` 参数、新增 `plugins_fix_hint` | D7、D11 | 规划端 |
| `scripts/pi_dispatch.py`（先行） | `_is_link_or_junction`（`5203-5220`）旁加公开名 `is_link_or_junction`；新增 `first_link_component` | D11 | 规划端，先于 T1、T2 |
| `tests/test_kit_config.py` | 新增用例 | 第 9 节 C 组与 D11 的链接检查 | 规划端 |
| `scripts/pi_dispatch.py` | `KIT_LOADED_FILES`（`94-98`）；文档串命令表（`28` 附近）；`cmd_config` 旁新增 `cmd_logs`、`cmd_plugins`（`7118-7124`）；解析器（`7502-7504` 附近） | D8 | 规划端 |
| `tests/test_kit_v280.py` | import 扫描（`120-144`） | D8 | 规划端 |
| `tests/test_kit_v300.py` | 新文件：转发与安装布局场景（impl-4），以及公共链接谓词的输入（impl-5） | 第 9 节 W 组 | 规划端 |
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
| L1 | 同一 `message.id` 写三条、usage 相同且都带 `stop_reason`（主会话写法）；另一 id 先写三条 `stop_reason` 为 null、`output_tokens` 为 8 的中间记录，再写一条 `stop_reason` 为 `tool_use`、`output_tokens` 为 800 的最终记录（子代理写法）。对子代理写法的记录做全排列（最终记录不一定在最后），并把同一 id 拆到两个文件；另有一个 id 的最终记录 `stop_reason` 为 `max_tokens` | 按三次计数；把子代理写法判为冲突；取到中间记录的 8 而不是最终的 800；“取最后一条”；只认 `tool_use` / `end_turn` 为最终 |
| L2 | 同一 `message.id` 两条最终记录：四项计数不同；或 `model` 不同；或 `isSidechain` 不同；中间记录的 `model` 与最终记录不同；中间记录的 `model` 相同但 `isSidechain` 不同；只有中间记录、没有最终记录（断言 `incomplete_ids` 为 1、结果标“部分”）。下面的固定输入都带 `stop_reason` 最终标记。另有一组三条，usage 依次为 A、A、B：断言 `conflict_ids` 为 1、`conflict_records` 为 3、`duplicate_records` 为 0。再加一组固定输入：一个冲突 id、一个无可用时间的 id、一个窗口外的 id、一个计入且两条记录都带 `output_tokens: null` 的 id，断言四类 id 各为 1、`non_integer_fields` 为 1 | 随意取一条；冲突不报；结果不标“部分”；计数口径漂移 |
| L3 | 坏 JSON 行、非对象行、没有 usage 的记录、`message.id` 不是字符串、计数字段不是整数 | 崩溃，或悄悄算进去 |
| L4 | 同一 `message.id` 分在两个文件里、时间分别在窗口边界两侧；记录恰好落在 `--since` 与 `--until` 上。对文件参数顺序、文件内记录顺序做全部置换，结果必须完全相同 | 结果随读取顺序变化；窗口边界错位；跨文件重复计数 |
| L5 | 命令行时间不带时区；记录的 `timestamp` 无法解析；记录的 `timestamp` 可解析但不带时区（与同 id 另一条带 `Z` 的记录并存） | 把不带时区的时间当本地时间；把无时间的记录算进窗口；代表时间随运行环境的时区变化 |
| L6 | `isSidechain` 为真的记录 | 与主线混在一起 |
| L7 | attempt 没有 `events-summary.json`；`usage` 不是对象；摘要的 `complete` 为假、`truncated` 为真或 `parse_error_lines` 非空 | 把缺失当 0；把不完整的数当成准确值 |
| L8 | `.agent/runs` 不存在或为空；有 `_tmp` 这类非 task 目录；有不匹配 `attempt-NNN` 的目录 | 崩溃或误列 |
| L9 | 所有子命令跑一遍前后，逐字节比较 `.agent/` | 工具写了证据 |
| L10 | 证据里有很长的行和大量匹配 | 输出整份大文件或超过上限 |
| L11 | 会话记录的 `content` 里有形似密钥的文字 | 把对话内容打印出来 |
| L12 | task 目录、attempt 目录、证据文件或其中间目录是符号链接或 junction（Windows 上用 junction，其他平台用符号链接） | 跟随链接读到 runs 之外 |
| L13 | `logs show` 的目标分别用 task-id、task-id.vN、task-id/attempt-NNN、显式路径给出，且指向链接或 runs 之外；目标不存在。同时断言合法的写法能成功：大小写不同的同一路径（Windows）、含 `..` 但解析后仍在 runs 之内的路径 | 读 runs 之外的文件；崩溃而不是退出码 2；“一律拒绝”也能通过测试 |

**P 组：`plugins`**

| 编号 | 场景 | 防止的失败 |
|---|---|---|
| P1 | 现有 8 个插件 | 把一致的插件报成不一致 |
| P2 | 资源文件改一个字节；只把 LF 改成 CRLF；`decisions/questions/` 下多出一个锁里没有的清单。多出清单时断言：没有堆栈、`verify` 退出码 1、`list` 继续列出其他插件 | 漏报漂移；CRLF 时不给提示；漏报多出的题库；`DecisionError` 冒出去中断命令 |
| P3 | `lock_sha256` 被改 | 漏报锁漂移 |
| P4 | manifest 被改（与锁绑定不符） | 漏报绑定不一致 |
| P5 | `plugins` 目录、插件目录、中间目录或资源文件是符号链接或 junction；`manifest.json` 或 `lock.json` 本身是链接（内容与原文件相同）；决策插件的 `questions/` 目录或其中某个清单是链接；资源路径解析后不在插件目录内。用读取替身断言被拒绝的路径从未被读取，且检查失败后没有调用 `verify_battery_lock` | 读到插件目录之外；“先读取、后检查”；检查失败后仍继续读取 |
| P6 | 目录名与 `plugin_id` 不同；manifest 有重复键；manifest 不是合法 JSON | 接受不一致的插件；一个坏插件让 `list` 整体失败 |
| P7 | `enabled` 缺省时 `enable X` | 写出只含 X 的列表，把其他插件全关掉 |
| P8 | `enabled` 缺省时 `disable X`，当前布局里另有一个 manifest 坏掉的插件 | 写出的列表漏掉坏插件或其他插件；不提示语义变化 |
| P9 | `allowed_permissions` 是列表、X 缺权限、没给 `--allow-permission`；给了之后，输出列出因此满足权限条件的其他插件（例如授予 `read-candidate` 时列出其余任务插件） | 悄悄加权限或写入了部分改动；不说明共享权限的影响范围 |
| P10 | 给出的 `--allow-permission` 多于、少于所缺的权限；当前不限制时给了 | 授予无关权限 |
| P11 | `enable` 一个 `depends_on` 或 `conflicts` 非空的插件；`list` / `verify` 遇到这样的插件 | 启用依赖语义未定义的插件；因单插件注册表缺依赖而误报“锁无效” |
| P12 | 两个插件的 manifest 坏掉时 `disable` 其中一个，以及 `disable decisions`。另：`decisions.mode` 为 on、`enabled` 缺省、决策插件题库多出一个清单时 `disable code-change` → 被拒绝、配置不变、给出恢复顺序；按提示 `disable decisions` → 成功；再 `disable code-change` → 成功 | 因为无关的坏插件拒绝关闭；决策插件题库坏时没有可行的恢复路径 |
| P13 | `plugins.enabled` 或 `allowed_permissions` 为 `null` 时 `enable` / `disable`；两个同时为 `null`；两个同时为 `null` 并且 `decisions.mode` 为 on、题库不一致。断言给出的修复命令执行后确实成功 | 隐式改写旧值；不给修复提示；提示的命令本身写不进去 |
| P14 | `enable` 一个锁不一致的插件；配置里另有一个无效键时 `enable` | 启用坏插件；绕过整份校验写入 |
| P15 | 写入中途失败（`os.replace` 抛错） | 留下半份配置 |
| P16 | 关掉 `decisions`；`--dry-run` | 不提示决策插件会变为 off；实际写了文件 |
| P17 | `enabled` 为 `["decisons"]`（拼错） | `verify` 不报（必须退出码 1）；`list` 崩溃 |

**C 组：`kit_config`**

| 编号 | 场景 | 防止的失败 |
|---|---|---|
| C1 | 合法的 `plugins` 段；`config show` | 新键不显示或被报未知 |
| C2 | `enabled` 不是列表（含 `null`）、有重复、ID 格式错；`allowed_permissions` 有空串或重复；未知子键；两个子键同时非法；两个子键同时非法并且决策插件生效、题库不一致。断言提示的命令执行后能通过整份校验 | 接受会让插件悄悄失效的值；错误提示里没有修复办法，或提示的命令写不进去 |
| C3 | `config set plugins.enabled '[…]'`；`enabled` 里有当前布局没安装的 ID | `split_path` 仍拒绝；同一份配置在安装布局下被判无效 |
| C4 | 现有决策插件测试 | `plugins` 语义被改动 |

**W 组：接入**

| 编号 | 场景 | 防止的失败 |
|---|---|---|
| W1 | 通过 `pi_dispatch.main` 调用 `plugins --help`、`plugins list --json`、`logs --repo <路径> list`、`--repo <路径> plugins list`、全局与下游给出不同的 `--repo`，用替身记录下游 `main` 收到的参数与 `repo`，并让替身返回非零退出码。另：`--version plugins …`、`-h plugins …`、`--unknown plugins …`、`-- plugins list`、`--repo`（缺值）、`--repo --version`、`doctor --out plugins`，断言下游调用次数为零 | 转发失效；`--help` 或以 `-` 开头的参数被外层截走；全局与下游的 `--repo` 优先级错误；下游退出码被吞；误截获版本、帮助或其他子命令 |
| W2 | `KIT_LOADED_FILES` 含两个新文件；import 扫描一致；用 `kit_install install` 装进临时目标仓库，在目标里运行装好的 `plugins list` 与 `logs list` | 新文件不受保护或不被发放；安装布局下命令不能用 |
| W3 | 全量 `python -m pytest tests` | 回归 |

## 10. 待用户拍板

1. **版本标注**：本轮在 CHANGELOG 记为“未发布（themis-3.0 分支）”，合并到 master 时再定版本号（推荐）；或现在就记为 2.11.0。
2. **会话文件的读取范围**：只读命令行显式给出的路径（推荐）；或允许自动到 `~/.claude/projects/` 下找本仓库的会话文件。
3. **配置并发写**：沿用 `kit_config` 现有的“固定临时文件名 + 原子替换”，不加锁（推荐，本轮不扩大范围）；或本轮就给配置写入加锁。
4. **合并到 master**：闸二通过后由你决定，不自动合并。
5. **调度器 `resolve_run_dir` 的边界缺口**：另立一个小任务修（推荐，修法是 task-id 分支同样检查链接与边界）；或本轮顺带修。
