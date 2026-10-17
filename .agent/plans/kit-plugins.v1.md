# TASK: kit-plugins

<!-- 实现合同。章节标题（英文）由校验器检查，不要改名；Markdown 与 JSON 由校验器逐项比较（contract-guide.md 第九节）。 -->

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: db228add2e1ed72dab694454e0d3fd403d4237ca
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: bb/step-5-preview · thinking high

## Goal
实现 `scripts/kit_plugins.py`：插件管理第一片，子命令 `list`、`show`、`verify` 只读，`enable`、`disable` 只改 `.agent/dispatch.config.json` 的 `plugins` 键，使 oracle `tests/test_kit_plugins_oracle.py` 全部通过；执行端另写自己的测试 `tests/test_kit_plugins.py`。

## Non-goals
- 不接入调度器转发（设计 D8）；不改 README、AGENTS.md、CHANGELOG、权限示例（设计 D9）。
- 不做插件安装、升级、删除，不执行 manifest 里的 `checks`，不联网，不重新生成锁。
- 不支持带 `depends_on` 或 `conflicts` 的插件的启用（本轮一律拒绝并报“本轮不支持”）。
- 不修改任何既有文件；`kit_plugins` 是新模块，`codekit/plugins.py`、`codekit/decisions.py`、`kit_config.py`、`pi_dispatch.py` 只调用其公开函数。

## Repository facts
- 设计：`docs/themis-tally-3.0-r1-日志与插件管理.md` 的 §4.2、§3（D5、D6、D10、D11）、§9 的 P 组。
- `scripts/kit_config.py`：`import pi_dispatch as pd`（约第 44 行），`from codekit import decisions/plugins`；`class ConfigError`（缺省退出码 1）；`PLUGINS_SUBKEYS = ("enabled", "allowed_permissions")`；`KEYS["plugins"]`；`load_config(repo)`；`validate_config(config, repo, *, hints=True)`（plugins 键错误后附“；修复：…”）；`plugins_fix_hint(config, repo)`；`write_checked(repo, config)`（整份校验后原子写，校验不过一个字节都不写）；`main(argv=None, repo=None)`；退出码 `EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2`；`CONFIG_NAME = "dispatch.config.json"`。
- `scripts/pi_dispatch.py`：`EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_BLOCKED, EXIT_DRIFT = 0, 1, 2, 3, 4`；`is_within(path, root)`；模块属性 `KIT_ROOT` 与 `DECISIONS_PLUGIN_DIR`；`is_link_or_junction(path)`；`first_link_component(root, rel)`；`Repo.discover(start)`（不在 Git 仓库抛 `DispatchError(..., EXIT_USAGE)`）；`DispatchError(message, code)`。
- `scripts/codekit/plugins.py`：`PLUGIN_ID`（正则）；`PluginError(ValueError)`（属性 `code`、`path`）；`validate_manifest(manifest)`；`build_lock(manifests, *, compiler_sha256, generation=1)`；`validate_lock(lock, manifests=None)`（`lock_sha256` 不符抛 `E_PLUGIN_LOCK_DRIFT`；锁与 manifest 字节绑定不符或插件集合不符抛 `E_PLUGIN_LOCK_BINDING`）；`check_permission_intersection(manifest, *, allowed_permissions, platform_name=None)`（返回 `missing_permissions` 与 `status` READY/BLOCKED）。
- `scripts/codekit/decisions.py`：`PLUGIN_ID = "decisions"`；`PERMISSION = "network-decisions"`；`DecisionError(RuntimeError)`（属性 `code`、`detail`）；`verify_battery_lock(plugin_dir)`（题库不一致抛 `DecisionError("battery_drift", …)`，只差 CRLF 时在 detail 里直说）；`settings_from_config(config, agent_dir, plugin_dir)`（返回带 `.active` 的 Settings，`active` 即 `mode != "off"`）。
- `scripts/codekit/protocols.py`：`strict_json_loads(raw_bytes)`（重复键即抛 `ProtocolError(ValueError)`）。
- `plugins/` 下 8 个插件目录，`depends_on` 与 `conflicts` 全为空；7 个任务插件要求 `read-candidate`，`decisions` 要求 `network-decisions`。
- 测试约定（本机 Python 3.10+）：pytest 函数写法 + `tmp_path`，不用 unittest 类、不用 `tempfile`/`mkdtemp`，用 `pytest.skip` 代替 `skipTest`；文件名与键名写字面量。

## Scope
- allowed_modified_files: 无
- allowed_new_files:
  - scripts/kit_plugins.py
  - tests/test_kit_plugins.py
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_kit_plugins_oracle.py
  - plugins/**
  - scripts/kit_config.py
  - scripts/kit_install.py
  - scripts/pi_dispatch.py
  - scripts/codekit/**
  - tests/test_kit_config.py
  - tests/test_dispatch.py
  - tests/test_kit_v280.py
  - docs/**
  - README.md
  - CHANGELOG.md
  - AGENTS.md
  - .agent/**
  - .agents/**
  - .claude/**
  - .codex/**
  - .pi/**
  - scripts/dispatch-pi.sh
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
- 模块与导入（D1、D11）：单文件、标准库、Python 3.10+，`main(argv=None, repo=None) -> int`，argparse 子命令，带 `--repo`（与 `kit_config.main` 一致：下游自己的 `--repo` 优先）。导入 `pi_dispatch`、`kit_config`、`codekit` 的写法与 `kit_config.py` 第 40–52 行相同：`import pi_dispatch as pd`、`import kit_config`、`from codekit import decisions/plugins/protocols`。模块暴露 `pd`，使 `kit_plugins.pd is kit_config.pd`。
  - `kit_plugins` 在调用时读取 `pd.KIT_ROOT` 与 `pd.DECISIONS_PLUGIN_DIR`，不把它们复制进模块常量。
  - 调用 codekit 时通过模块属性（如 `decisions.verify_battery_lock`、`plugins.validate_manifest`、`protocols.strict_json_loads`），不从模块 `from-import` 这些名字。
- 正常输入与命令语义（§4.2）：
  - `list [--json]`：每个插件一行——ID、版本、启用（是 / 否 / 不限制）、锁（一致 / 漂移 / 无效 / 本轮不支持）、资源文件（一致 / 不一致）、缺的权限、状态（READY / BLOCKED 与原因）；另列 `enabled` 里有、当前布局没安装的 ID。退出码 0（不在 Git 仓库或参数错误时 2，见 G1），坏插件不拖垮命令。
  - `show <ID> [--json]`：manifest 的版本、api_version、capabilities、permissions、platforms、depends_on、conflicts、checks；每个资源的路径与核对结果；`lock.json` 的 generation 与 lock_sha256（输出字面词 `generation` 后接其值）；配置里的启用与权限状态。退出码 0；ID 不存在 2。
  - `verify [ID] [--json]`：所选插件（缺省全部）的 manifest、锁、资源核对结果与问题清单；不指定 ID 时还核对“列入但未安装”。全部一致 0；有问题 1；ID 不存在 2。
  - `enable <ID> [--allow-permission P …] [--dry-run]`、`disable <ID> [--dry-run]`：变化摘要（例如 `plugins.enabled` 从 `["a", "b"]` 变成 `["a", "b", "c"]`），没有变化时直说。写入或无变化 0；被拒绝 1；用法错误 2。
- 固定词（oracle 逐字断言，实现必须原样输出，不得改写）：
  - 状态词：`一致`、`漂移`、`无效`、`本轮不支持`、`不一致`、`READY`、`BLOCKED`、`是`、`否`、`不限制`、`off`。
  - 字面串：`无效：链接`、`CRLF`、`修复：`、`plugins disable decisions`、`config decisions off`、`决策插件会因此变为 off`、`未安装`（enabled 里未安装的插件所在行）。
  - 文件名：`manifest.json`、`lock.json`、`dispatch.config.json`、`questions`。
  - 键名：`enabled`、`allowed_permissions`、`plugin_id`。
  - `show` 另输出字面词 `generation`（后接 lock.json 里的值）与逐资源核对结果（一致 / 不一致 / `无效：链接`）。
  - oracle 只允许断言上面写出的词、插件 ID、退出码与文件字节，不得断言合同没有写明的词。
- 退出码含义：0 成功/无变化；1 被拒绝、校验不过、写入失败、核对有问题；2 用法错误（含不在 Git 仓库、ID 不存在、参数给多给少）。命令级错误打印一行 `ERROR:` 并返回退出码，不输出堆栈（D10）。
- 用户决定（写死，逐条照做）：
  - G1：不在 Git 仓库里运行任何子命令（list、show、verify、enable、disable）→ 用法错误，退出码 2。
  - G2：enable、disable、show、verify 的插件 ID 不存在 → 用法错误，退出码 2。
  - G3：verify（不论是否指定 ID）把“本轮不支持”的插件计为问题，退出码 1；list 照常列出，锁列显示“本轮不支持”。
  - G4：`--dry-run` 与真正写入走同一套校验（整份校验与决策题库核对）：校验失败时退出码 1，打印原因，配置字节不变；校验通过时退出码 0，不写文件。
  - B3：show、verify、enable、disable 的插件 ID 先按 `plugins.PLUGIN_ID`（正则 `^[a-z][a-z0-9-]{0,63}$`）校验。不合法或不存在时退出码 2，stderr 打印一行 `ERROR:`（含该 ID），不输出堆栈。list 没有 ID 参数。
  - B4：list 的退出码为 0，坏插件不拖垮命令；不在 Git 仓库（G1）与参数错误（argparse）时为 2。
- 枚举与存在性（D5）：插件枚举只取 `plugins/` 根下名字匹配 `PLUGIN_ID` 的直接子目录，链接目录也列出（它们按“无效：链接”核对）。“插件 ID 存在”即“在枚举结果中”。`plugins/` 根本身是链接时枚举为空：list 打印一行 `无效：链接 plugins` 并退出 0；verify（不指定 ID）同样打印该行并退出 1；任何 ID 都不存在（退出 2）。
- 锁状态判定（list、show、verify 的“锁”列），按序：
  1. 目录链接检查（D5）失败 → 记为“无效”，原因写字面串 `无效：链接`，停止该插件的后续读取。
  2. 读取并严格解析 `manifest.json` 与 `lock.json`（`protocols.strict_json_loads`，重复键即失败）；读不出或解析失败 → 无效。
  3. 目录名与 manifest 的 `plugin_id` 不符，或 `validate_manifest` 失败 → 无效。
  4. manifest 的 `depends_on` 或 `conflicts` 非空 → 本轮不支持（不调用 `validate_lock`）。
  5. 调用 `validate_lock(lock, {plugin_id: manifest})`：通过为“一致”；抛 `PluginError` 且 `code` 为 `E_PLUGIN_LOCK_DRIFT` 或 `E_PLUGIN_LOCK_BINDING` 为“漂移”；抛其余错误为“无效”。
  - 资源文件哈希另列一列（一致 / 不一致），不改变锁列；`validate_lock` 不对资源求哈希，哈希由 `kit_plugins` 自己核对，只差 CRLF 时在问题里直说 `CRLF`。
  - 决策插件的题库核对（`verify_battery_lock` 抛出的 `DecisionError`）并入该插件的问题清单，verify 退出码 1，不改变锁列。
- 读前检查（D5）：实际读取的每个文件（`manifest.json`、`lock.json`、每个资源文件，以及决策插件的 `questions/` 目录与其中每个 `*.json`）在读之前都从 `KIT_ROOT` 往下逐级检查链接与 junction，并确认是普通文件（目录则确认是普通目录）；资源路径必须以 `plugins/<id>/` 开头。任何一项失败就停止该插件的后续读取与核对，状态记为“无效：链接”，且不再调用 `verify_battery_lock`。枚举规则（只取 `plugins/` 根下匹配 `PLUGIN_ID` 的直接子目录、链接目录也列出、`plugins/` 根是链接时枚举为空）见“枚举与存在性”。
- enable / disable 语义（D6）：
  - 一次操作只改变 X 的启用成员资格；`disable` 可把“不限制”改成显式列表并提示“之后新增的插件不会自动启用”。不校验其他插件的 manifest、lock 与资源；坏掉的其他插件不挡住操作。
  - 非列表值：`plugins.enabled` 或 `plugins.allowed_permissions` 存在但不是列表（含 `null`）→ 拒绝，不做隐式规范化；修复提示只来自 `kit_config.plugins_fix_hint`，附在 `修复：` 后。
  - `enable X`：X 的 manifest、lock、资源（以及 decisions 的题库）必须全部一致；`depends_on` 或 `conflicts` 非空 → 拒绝。`enabled` 缺省（不限制）时不改 `enabled`，提示“当前不限制，所有插件都算启用”；`enabled` 是列表时加入 X（去重、按 ID 排序）。权限只在 `allowed_permissions` 是列表时检查：所缺权限必须由 `--allow-permission` 一个不多、一个不少地给出，这时一并写入 `allowed_permissions`（整份列表去重、按字符串排序，与 `enabled` 一致）；给多、给少或当前不限制时还给了，都是用法错误（2）。授予权限时列出当前布局下所有因此不再缺这项权限的其他插件（`--dry-run` 同样列出）。
  - `disable X`：只要求 X 存在（按“枚举与存在性”判定）。X 不存在（含 `plugins/` 根是链接）时退出码 2，不写配置。`enabled` 缺省时，把“当前布局下全部插件目录名（匹配 PLUGIN_ID，不是链接目录，不论 manifest 好坏）减去 X”写成显式列表（按 ID 排序）；`enabled` 是列表时移除 X，不在列表里就提示没有变化。不碰 `allowed_permissions`。关掉 `decisions` 时提示决策插件会因此变为 `off`。
- 授予路径（B2）：enable 的 `--allow-permission` 要列出“因此满足权限条件的其他插件”，遍历枚举（含链接目录）。读取其他插件的 `manifest.json` 之前，做同样的读前链接检查（`pd.first_link_component(pd.KIT_ROOT, "plugins/<id>/manifest.json")`）。失败（链接，或读取、解析、`validate_manifest` 失败）计为“该插件的问题”：stdout 输出一行，含该插件 ID；链接时含字面串 `无效：链接`，其他失败时含“无效”与原因。不静默跳过；不影响 enable X 的退出码；该插件不计入“满足权限条件”。
- 题库阶段：除 `DecisionError` 外也收集 `OSError` 与 `ValueError`。核对分析阶段记为该插件的问题（不改变锁列，verify 退出码 1），问题行含该清单的文件名与“不一致”。写入前的决策插件核对拒绝写入时，stderr 打印一行 `ERROR:`（含原因），退出码 1，配置字节不变，不输出堆栈。
- 资源边界：资源路径越出插件目录、资源不是普通文件、资源是链接，按读前检查的规则，锁列记为“无效”，输出含字面串 `无效：链接` 及原因。资源读取失败（OSError）：锁列记“无效”，资源列记“不一致”，输出含“资源读取失败”及原因。
- 不提供 `--version`（设计没有要求）。
- 命令级错误（ID 不合法或不存在、G1、用法错误、写入失败、写入前拒绝）：stderr 一行，以 `ERROR:` 开头，退出码按下面的含义，不输出堆栈。
- 写入（D6、D7）：只经 `kit_config.write_checked`，不得直接写文件；整份校验后原子替换，校验不过或 `os.replace` 抛 `OSError` 时配置一个字节都不写，退出码 1。`--dry-run` 只打印将写入的 `plugins` 段，不写文件。
- 题库不一致时的恢复顺序（D6）：enable 或 disable 因决策插件生效、题库不一致被拒绝时，输出中给出恢复顺序，并含字面命令 `plugins disable decisions` 与 `config decisions off`。这段文字由 `kit_plugins` 自己输出，它不是 kit_config 的配置候选，不属于 `plugins_fix_hint` 的范围。
- 共用规则（D11，逐条照做）：写配置只经 `kit_config.write_checked`，不得直接写文件；修复提示只来自 `kit_config.plugins_fix_hint`，不得自己拼（题库恢复顺序除外）；链接与边界检查只用 `pi_dispatch.is_link_or_junction`、`pi_dispatch.first_link_component` 与 `pi_dispatch.is_within`，不得另写同类实现。
- 错误与重试：逐插件、逐文件收集 `ValueError`（含 `ProtocolError`、`PluginError`）、`DecisionError`（`RuntimeError` 子类）、`OSError`，记为该插件的问题，其余项照常；命令级错误捕获 `pd.DispatchError` 与 `kit_config.ConfigError`，打印 `ERROR:` 一行并返回其退出码；argparse 参数错误退出码 2；不输出堆栈。
- 并发、取消与状态变化：不适用（单进程本地命令，不写后台状态）。
- 兼容性：不修改任何既有文件；`kit_plugins` 是新模块，不接入调度器；同一份配置要在外部运行与安装布局下都合法（只校验格式，不校验是否安装）。
- 测试约定（执行端自己的测试也遵守）：pytest 函数写法；临时目录只用 `tmp_path`，不用 `tempfile` 与 `mkdtemp`；用 `pytest.skip` 代替 `skipTest`；插件树从仓库 `plugins/` 复制到 `tmp_path` 后只改副本；junction 与符号链接的目标只能在 `tmp_path` 之内；不得修改仓库里真实的 `plugins/`；文件名与键名写字面量。

## Steps
1. 读取 Repository facts 中的文件与符号，确认签名与基线一致；不一致就停止并报告。
2. 按 Behavior contract 实现 `scripts/kit_plugins.py`，只调用既有公开函数，不另写同类实现。
3. 编写执行端自己的测试 `tests/test_kit_plugins.py`：命令行解析、`--json`、`--dry-run` 不落盘；只用合成副本，不替代 oracle。
4. 运行 Validation commands 中与改动相关的检查，记录命令与结果。
5. 写执行报告；遇到合同未定义的行为，停止并报告。

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态。需要截短输出时照抄执行说明“机器合同摘要”里每条检查的“自检照抄”写法（bash 以 `set -o pipefail;` 开头）。不要把输出写到固定路径。每个检查都写具体文件名，不运行整个 `tests` 目录（本机 Python 环境里有第三方 `tests` 包会遮住仓库的 tests/）。不做变异检查。

- V01（必要）：`python -m pytest tests/test_kit_plugins_oracle.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配 `[1-9]\d* passed`
- V02（必要）：`python -m pytest tests/test_kit_plugins.py -q` · cwd：仓库根 · 超时：300s · 期望退出码：0 · 输出须匹配 `[1-9]\d* passed`
- V03（必要）：`python -m py_compile scripts/kit_plugins.py` · cwd：仓库根 · 超时：60s · 期望退出码：0
- V04（必要）：`python scripts/kit_plugins.py --help` · cwd：仓库根 · 超时：60s · 期望退出码：0 · 输出须匹配 `usage:`

## Definition of done
- D01：list、show、verify 只读命令按 §4.2 输出状态词与退出码，坏插件不拖垮命令；证据：V01。
- D02：enable、disable 按 D6 改变 plugins.enabled 与 plugins.allowed_permissions，含 --dry-run、--allow-permission 与非列表值拒绝，授予路径的链接检查；证据：V01。
- D03：写入只经 kit_config.write_checked，校验不过或写入失败时配置字节不变，命令级错误打印一行 ERROR 并返回退出码，不输出堆栈；证据：V01。
- D04：读前逐级链接与边界检查只用 pi_dispatch 的公开函数（is_link_or_junction、first_link_component、is_within），不另写同类实现；证据：V01、review。
- D05：所有修改都在允许集合内；证据：scope。
- D06：没有删除、跳过或弱化既有测试，执行端自己的测试只用合成副本、不改真实 plugins/；证据：review、V02。
- D07：scripts/kit_plugins.py 可编译；证据：V03。
- D08：命令行可运行，--help 输出 usage:；证据：V04。
- D09：插件 ID 先按 PLUGIN_ID 校验，枚举与存在性规则（含 plugins 根是链接时枚举为空），G1、G2；证据：V01。
- D10：题库阶段收集 OSError 与 ValueError，show 输出 generation 与逐资源核对，allowed_permissions 去重排序，disable 的显式列表排除链接目录，不提供 --version；证据：V01。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `write_checked`、`first_link_component` 不存在或签名不同）。
- 必须修改允许范围之外的文件才能继续。
- 需要安装依赖、联网、读取凭据或提升权限。
- 合同、设计或概要步骤之间互相冲突，且无法按设计解释。
- 达到单轮时限。

## Budget
- max_attempts_total: 2（按 task-id 汇总，包括所有版本）
- max_wall_seconds_per_attempt: 2700
- max_wall_seconds_total: 5400
- cost_budget: tracking-only（bb/step-5-preview 只报 token，费用记 unknown）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：核实事实约 5 分钟；实现约 20 分钟；执行端测试约 8 分钟；必要检查约 5 分钟；报告约 5 分钟；合计约 43 分钟，不超过单轮 2700 秒。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D10，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置，也不写入 `.agent/` 下任何文件。
- 不删除、跳过或弱化既有测试来获得通过。
- 不提交（authorized_actions 没有 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不用 tempfile 或 mkdtemp 另建目录；测试临时目录只用 pytest 的 tmp_path。
