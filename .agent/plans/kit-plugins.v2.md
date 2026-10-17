# TASK: kit-plugins

<!-- 实现合同（第 2 版，最后一次派遣）。章节标题（英文）由校验器检查，不要改名；Markdown 与 JSON 由校验器逐项比较（contract-guide.md 第九节）。
     本版在 kit-plugins.v1 的基础上：修正 review attempt-001 的第 0–14 项，写死“v2 裁定”，补充 oracle 的 v2 增补用例。 -->

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: 355d94389eef46e449149b75095b5d0bccc447cc
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: bb/step-5-preview · thinking high

## Goal
返工 `scripts/kit_plugins.py`（基线中已有的候选，692 行）：按 review attempt-001 的第 0–14 项修正，使基线中的 oracle `tests/test_kit_plugins_oracle.py`（含 v2 增补的 48 个用例）与执行端自己的 `tests/test_kit_plugins.py` 全部通过。子命令 `list`、`show`、`verify` 只读，`enable`、`disable` 只改 `.agent/dispatch.config.json` 的 `plugins` 键。

## Non-goals
- 不接入调度器转发（设计 D8）；不改 README、AGENTS.md、CHANGELOG、权限示例（设计 D9）。
- 不做插件安装、升级、删除，不执行 manifest 里的 `checks`，不联网，不重新生成锁。
- 不支持带 `depends_on` 或 `conflicts` 的插件的启用（本轮一律拒绝并报“本轮不支持”）。
- 不修改其它既有文件：`codekit/plugins.py`、`codekit/decisions.py`、`kit_config.py`、`pi_dispatch.py` 只调用其公开函数，不改。
- 不提供 `--version`。

## Repository facts
- 基线 `355d943` = `411dada`（attempt-001 的候选，位于规划端提交 `ca59fd9` 之上）+ oracle 的 v2 增补。`ca59fd9` 的改动：`scripts/codekit/decisions.py` 的 `verify_battery_lock` 把读不出的题库清单与列举失败转为 `DecisionError("battery_drift", …)`（此前冒出 OSError）；`scripts/kit_config.py` 公开 `plugins_section_error(config)`（plugins 段的格式错误，不带修复提示）。
- 基线 `411dada` 的 `scripts/kit_plugins.py` 是 review attempt-001 的候选（692 行），函数位置（`grep -n "^def " scripts/kit_plugins.py` 核对）：`_plugins_root`(63)、`_root_is_link`(67)、`_enumerate_entries`(74)、`_installed_ids`(94)、`_require_exists`(98)、`_link_level`(104)、`_read_json_file`(112)、`_check_resources`(138)、`_check_battery`(185)、`_check_plugin`(212)、`_is_consistent`(271)、`_plugins_view`(279)、`_enabled_label`(290)、`_missing_permissions`(297)、`_not_installed`(304)、`_list_row`(317)、`_format_list_row`(337)、`cmd_list`(344)、`cmd_show`(371)、`cmd_verify`(427)、`_permission_impact`(468)、`_battery_gate`(492)、`_finish_mutation`(508)、`cmd_enable`(543)、`cmd_disable`(582)、`_reject_reason`(608)、`_discover`(622)、`_validate_id`(626)、`build_parser`(632)、`main`(665)。可以沿用这些函数名，也可以拆分，但行为以本合同为准。
- 基线中的 `tests/test_kit_plugins_oracle.py` 已含 v2 增补（`test_v2_*`，规划端提交 `355d943`）；若基线里没有这些用例，按停止条件处理。
- `scripts/kit_config.py`：`import pi_dispatch as pd`；`class ConfigError`(63，缺省退出码 1)；`EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2`(56)；`CONFIG_NAME = "dispatch.config.json"`(57)；`PLUGINS_SUBKEYS = ("enabled", "allowed_permissions")`(166)；`_check_plugins(config, _repo)`(169)；`plugins_section_error(config) -> Optional[str]`(199，只查 plugins 段，不带修复提示)；`config_path(repo)`(245)；`load_config(repo)`(249)；`validate_config(config, repo, *, hints=True)`(262，整份校验，返回错误列表)；`plugins_fix_hint(config, repo) -> Optional[str]`(296)；`write_checked(repo, config)`(434，整份校验后原子写，校验不过一个字节都不写)；`main(argv=None, repo=None)`(742)。
- `scripts/pi_dispatch.py`：`EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_BLOCKED, EXIT_DRIFT = 0, 1, 2, 3, 4`(57)；`class DispatchError`(480，`(message, code)`)；`is_within(path, root)`(558)；`Repo.discover(start)`(1132，不在 Git 仓库时抛 `DispatchError` 且退出码 2)；`KIT_ROOT`(3672)；`DECISIONS_PLUGIN_DIR`(3673)；`is_link_or_junction(path)`(5203，悬空链接与 junction 也返回真)；`first_link_component(root, rel)`(5227，返回 rel 从 root 往下第一个链接级，没有返回 None，rel 含 `..` 时抛 ValueError)。
- `scripts/codekit/plugins.py`：`PLUGIN_ID`(19，正则 `^[a-z][a-z0-9-]{0,63}$`)；`PluginError(ValueError)`(30，属性 `code`、`path`)；`validate_manifest(manifest)`(173)；`build_lock(manifests, *, compiler_sha256, generation=1)`(288)；`validate_lock(lock, manifests=None)`(307，`lock_sha256` 不符抛 `E_PLUGIN_LOCK_DRIFT`，锁与 manifest 绑定不符或插件集合不符抛 `E_PLUGIN_LOCK_BINDING`)；`check_permission_intersection(manifest, *, allowed_permissions, platform_name=None)`(377，返回含 `missing_permissions` 与 `status`（READY/BLOCKED）的字典)。
- `scripts/codekit/decisions.py`：`PLUGIN_ID = "decisions"`(48)；`PERMISSION = "network-decisions"`(49)；`DecisionError(RuntimeError)`(74，属性 `code`、`detail`)；`verify_battery_lock(plugin_dir)`(312，题库与锁不符抛 `DecisionError("battery_drift", …)`，读不出的清单也是这一种；detail 里有文件名)；`settings_from_config(config, agent_dir, plugin_dir)`(459，返回带 `.active` 的 Settings；`plugins.enabled` 存在却没有 decisions，或 `allowed_permissions` 存在却没有 network-decisions，则不生效)。
- `scripts/codekit/protocols.py`：`strict_json_loads(raw_bytes)`(420，重复键即抛 `ProtocolError(ValueError)`，228)。
- `plugins/` 下 8 个插件目录：code-change、decisions、docs-change、docs-checks、mutation-review、python-checks、regression-tests、repo-analysis。`depends_on` 与 `conflicts` 全为空；7 个任务插件要求 `read-candidate`，`decisions` 要求 `network-decisions`；`decisions` 的题库是 `plugins/decisions/questions/` 下的 `mutation-equivalence.json`、`report-screen.json`、`run-health.json`。
- 测试约定（本机 Python 3.10+）：pytest 函数写法 + `tmp_path`，不用 unittest 类、不用 `tempfile`/`mkdtemp`，用 `pytest.skip` 代替 `skipTest`；文件名与键名写字面量。

## Scope
- allowed_modified_files:
  - scripts/kit_plugins.py
- allowed_new_files:
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

### 一、模块与导入（D1、D11）
- 单文件、标准库、Python 3.10+；`main(argv=None, repo=None) -> int`；argparse 子命令；带 `--repo`（下游自己的 `--repo` 优先）。
- 导入写法与 `kit_config.py` 第 40–52 行相同：`import pi_dispatch as pd`、`import kit_config`、`from codekit import decisions/plugins/protocols`（经模块属性调用，如 `decisions.verify_battery_lock`、`plugins.validate_manifest`、`protocols.strict_json_loads`，不从模块 from-import 这些名字）。模块暴露 `pd`，使 `kit_plugins.pd is kit_config.pd`。
- `KIT_ROOT` 与 `DECISIONS_PLUGIN_DIR` 在调用时从 `pd` 读取，不复制进模块常量。

### 二、命令与输出（§4.2）
- `list [--json]`：每个插件一行，行首是插件 ID（空白分隔的第一个词），其后依次为版本、启用（是 / 否 / 不限制）、锁（一致 / 漂移 / 无效 / 本轮不支持，锁列只取这四个值）、资源（一致 / 不一致；未核对时为 `-`）、缺的权限、状态（READY，或 BLOCKED 加原因）。另列 `enabled` 里有、当前布局没安装的 ID，行为 `<ID> 未安装`。退出码 0；G1 与参数错误为 2；plugins 段不合法为 1（见第七节）。坏插件不拖垮命令。根是链接时打印一行 `无效：链接 plugins`。
- `show <ID> [--json]`：版本、api_version、capabilities、permissions、platforms、depends_on、conflicts、checks；每个资源一行，行以“资源”开头，行内含路径与核对结果（一致 / 不一致 / 无效：链接）；`lock.json` 通过读前检查且解析为对象时，输出 `锁 generation <原值>` 与 `锁 lock_sha256 <原值>`（字面词 generation 与 lock_sha256 后接 lock.json 里的原值）；`启用 …`、`权限 …（缺 X 或无缺失）`、`状态 <锁列值>`；问题行以“问题：”开头。退出码 0；ID 不合法或不存在 2。
- `verify [ID] [--json]`：所选插件（缺省全部）的标题行与问题行。标题行为 `<ID> <词>`：锁列不是一致时词为锁列值；锁一致而资源不一致时为 `<ID> 资源不一致`；都一致时为 `<ID> 一致`。问题行缩进两个空格。不指定 ID 时另列“未安装”。全部一致 0；有问题 1；ID 不合法或不存在 2。
- `enable <ID> [--allow-permission P …] [--dry-run]`、`disable <ID> [--dry-run]`：见第九、十、十二、十三节。写入或无变化 0；被拒绝 1；用法错误 2。
- `--json`：输出一个 JSON 对象。键名不固定，验收只看字符串值（递归遍历所有字符串）与退出码。

### 三、固定词（oracle 逐字断言；实现必须原样输出，不得改写）
- 状态词：`一致`、`漂移`、`无效`、`本轮不支持`、`不一致`、`READY`、`BLOCKED`、`是`、`否`、`不限制`、`off`。
- 字面串：`无效：链接`、`无效：链接 plugins`（根是链接时的行）、`CRLF`、`修复：`、`plugins disable decisions`、`config decisions off`、`决策插件会因此变为 off`、`未安装`（行为 `<ID> 未安装`）、`资源读取失败`、`满足权限条件`、`没有变化`、`generation`、`lock_sha256`、`→`、`ERROR:`。
- 行前缀：list 行首是插件 ID；show 的资源行以“资源”开头；show 的问题行以“问题：”开头；verify 的标题行首是 `<ID> `。
- 文件名：`manifest.json`、`lock.json`、`dispatch.config.json`、`questions`。
- 键名：`enabled`、`allowed_permissions`、`plugin_id`；变化摘要的键名写作 `plugins.enabled`、`plugins.allowed_permissions`。
- oracle 只允许断言上面写出的词、插件 ID、退出码与文件字节，不得断言合同没有写明的词。

### 四、退出码（写死）
- 0：成功、无变化、写入成功、dry-run 成功、只读命令在全部一致时。
- 1：被拒绝（启用时资源或锁不一致、决策题库门禁拒绝、整份校验不过）、写入失败、核对有问题（verify）、plugins 段不合法（第七节）、配置读不出。
- 2：用法错误：不在 Git 仓库（G1）、插件 ID 不合法或不存在（B3、G2）、argparse 的参数错误（给多给少、未知选项）、`--allow-permission` 用法不符（第九节）。
- 命令级错误（以上 1 与 2 的情形）：stderr 打印一行，以 `ERROR:` 开头，不输出堆栈（D10）。argparse 自身的错误只要求退出 2、不冒堆栈。

### 五、用户决定（写死，逐条照做）
- G1：不在 Git 仓库里运行任何子命令（list、show、verify、enable、disable）→ 退出 2。
- G2：enable、disable、show、verify 的插件 ID 不存在 → 退出 2。
- G3：verify（不论是否指定 ID）把“本轮不支持”的插件计为问题，退出 1；list 照常列出，锁列显示“本轮不支持”。
- G4：`--dry-run` 与真正写入走同一套校验（题库门禁、整份校验）：校验失败时退出 1，打印原因，配置字节不变；校验通过时退出 0，不写文件。
- B3：show、verify、enable、disable 的插件 ID 先按 `plugins.PLUGIN_ID` 校验。不合法或不存在时退出 2，stderr 一行 `ERROR:`（含该 ID），不输出堆栈。list 没有 ID 参数。
- B4：list 的退出码为 0（配置段不合法除外，见第七节），坏插件不拖垮命令。

### 六、枚举与存在性（D5、D9）
- 插件枚举只取 `plugins/` 根下名字匹配 `PLUGIN_ID` 的直接子目录；链接目录（含悬空链接）也列出，它们按“无效：链接”核对；普通文件不列出。“插件 ID 存在”即“在枚举结果中”。
- `plugins/` 根是链接（含悬空链接，即 `is_link_or_junction` 为真）时：枚举为空；list 打印一行 `无效：链接 plugins` 并退出 0；verify（不指定 ID）同样打印该行并退出 1；任何 ID 都不存在（退出 2）。
- “未安装”= enabled 里不在枚举结果（含链接目录）中的 ID。

### 七、配置段校验（review 第 4 项）
- 五个子命令读到配置后，先调用 `kit_config.plugins_section_error(config)`。返回 None 则继续；否则 stderr 打印一行 `ERROR: <错误>；修复：<hint>`，其中 `<hint>` 来自 `kit_config.plugins_fix_hint(config, repo)`（返回 None 时不附“；修复：”），退出 1，不写配置。
- 修复提示只来自 `plugins_fix_hint`，且只根据原配置计算，不得自己拼（题库恢复顺序除外，见第十二节）。
- 检查顺序见第十五节（这一步在 ID 检查之后）。

### 八、读前检查与锁列（D5）— 裁定表（权威，逐行执行）
读前检查的每个文件（`manifest.json`、`lock.json`、每个资源、决策插件的 `questions/` 目录及其中每个 `*.json`）在读之前都从 `KIT_ROOT` 往下逐级检查链接与 junction，并确认是普通文件（目录则确认是普通目录）。资源路径必须以 `plugins/<id>/` 开头。下表每行是一个失败点：

| # | 失败点 | 锁列 | 资源列 | 必须出现的字面串 | 之后是否停止该插件的读取 | 是否调用 verify_battery_lock |
|---|---|---|---|---|---|---|
| 1 | `plugins/` 根是链接（含悬空） | —（整体） | — | `无效：链接 plugins` | 不枚举 | 否 |
| 2 | 插件目录是链接（含悬空） | 无效 | - | `无效：链接 plugins/<id>` | 是 | 否 |
| 3 | `manifest.json` 路径上任一级是链接或 junction（含悬空） | 无效 | - | `无效：链接` | 是 | 否 |
| 4 | `manifest.json` 缺失、不是普通文件（非链接）、读取失败、严格解析失败、不是对象、`plugin_id` 与目录名不符、`validate_manifest` 失败 | 无效 | - | 无（原因写具体情况，如“不是普通文件”“解析失败：…”“目录名与 plugin_id 不一致”） | 是 | 否 |
| 5 | `lock.json` 路径上任一级是链接或 junction（含悬空） | 无效 | - | `无效：链接` | 是 | 否 |
| 6 | `lock.json` 缺失、不是普通文件、读取失败、解析失败、不是对象 | 无效 | - | 无（原因写具体情况） | 是 | 否 |
| 7 | manifest 的 `depends_on` 或 `conflicts` 非空 | 本轮不支持 | - | `本轮不支持` | 是（不调用 validate_lock） | 否 |
| 8 | `validate_lock` 抛 `E_PLUGIN_LOCK_DRIFT` 或 `E_PLUGIN_LOCK_BINDING` | 漂移 | - | `漂移` | 是 | 否 |
| 9 | `validate_lock` 抛其它 ValueError | 无效 | - | 无（原因写异常文字） | 是 | 否 |
| 10 | 资源路径不以 `plugins/<id>/` 开头（越出插件目录） | 无效 | - | `无效：链接`（原因：路径越出插件目录） | 是（本资源及之后的资源不再读） | 否 |
| 11 | 资源路径上任一级是链接或 junction（含悬空） | 无效 | - | `无效：链接` | 是 | 否 |
| 12 | 资源缺失，或存在但不是普通文件（含目录）（沿用 v1 第 103 行的链接类归类） | 无效 | - | `无效：链接`（原因：不是普通文件） | 是 | 否 |
| 13 | 资源是普通文件，但读取抛 OSError（资源读取失败） | 无效 | 不一致 | `资源读取失败` | 否（其余资源照常核对，题库照常核对） | 是 |
| 14 | 资源哈希与锁不符 | 一致（不改锁列） | 不一致 | 无（只差 CRLF 时写 `CRLF`） | 否 | 是 |
| 15 | 决策插件：`questions/` 路径上任一级是链接，或 `questions/` 缺失、不是普通目录 | 无效 | 保持资源核对的结果 | `无效：链接` | 是 | 否 |
| 16 | 决策插件：`questions/` 下某个 `*.json`（含名字是目录的）是链接，或不是普通文件 | 无效 | 保持资源核对的结果 | `无效：链接`（原因写文件名） | 是 | 否 |
| 17 | 决策插件：`questions/` 列举抛 OSError | 一致 | 不一致 | `题库与内容锁不一致` | 是 | 否 |
| 18 | 决策插件：`verify_battery_lock` 抛 ValueError、OSError 或 DecisionError | 一致 | 不一致 | `题库与内容锁不一致`，原因含文件名（来自 detail） | 是 | 是（已调用） |

- 第 1 行只影响 list 与 verify 的输出，不属于某个插件的锁列。
- 锁列只取四个值（一致 / 漂移 / 无效 / 本轮不支持）。“无效：链接”只出现在原因或问题文字里，从不作为锁列的值。list --json 与 verify --json 的字符串值中也不出现恰为“无效：链接”的值（show 的资源行状态可以是“无效：链接”）。
- 缺失文件的归类保持现状：清单（manifest、lock）缺失或不是普通文件，是第 4、6 行（无效，不带链接字样）；资源与题库缺失或不是普通文件，是第 12、15、16 行（无效，带链接字样）。
- 资源读取失败（第 13 行）的问题文字格式：`资源读取失败：资源 <路径>：<原因>`。
- 资源路径检查（第 10–12 行）在读取之前完成；被拒绝的路径从未被读取。

### 九、锁状态判定、状态与权限（review 第 6 项）
- 锁状态按第八节表的顺序判定：读前检查（第 1–6 行）→ 目录名与 manifest 校验 → depends_on/conflicts（第 7 行）→ validate_lock（第 8、9 行）→ 资源（第 10–14 行）→ 决策题库（第 15–18 行）。遇到“停止”即结束该插件的后续核对。
- `allowed_permissions` 是列表时，缺的权限与权限状态来自 `plugins.check_permission_intersection(manifest, allowed_permissions=<列表>, platform_name=None)`（manifest 为已校验的对象）；`allowed_permissions` 不限制（不存在）或不是列表时，不调用该函数，缺的权限为空，权限状态视为 READY。
- 状态：READY 当且仅当锁一致、资源一致、权限 READY（与是否启用无关）。BLOCKED 时原因：锁不一致则写锁列的原因文字；资源不一致则写“资源不一致”；否则写“缺 <权限名>”。权限名在行内列出。
- 资源列：一致 / 不一致。读前检查失败、没有进入资源核对的（第 2–6 行与第 10–12 行）资源列为 `-`；资源已核对的（第 13–16 行）资源列是资源核对的结果，不因题库失败而改动。

### 十、enable / disable 语义（D6）
- 一次操作只改变 X 的启用成员资格。不校验其他插件的 manifest、lock 与资源；坏掉的其他插件不挡住操作（B2 的授予路径除外，见第十一节）。
- 非列表值：`plugins.enabled` 或 `plugins.allowed_permissions` 存在但不是列表（含 `null`）→ 拒绝（第七节的 ERROR 行，退出 1）。
- `enable X`：X 的 manifest、锁、资源（以及 decisions 的题库）必须全部一致（第八节表与第九节的“一致”）；否则拒绝（退出 1）。`depends_on` 或 `conflicts` 非空 → 拒绝（退出 1）。`enabled` 缺省（不限制）时不改 `enabled`，提示“当前不限制，所有插件都算启用”；`enabled` 是列表时加入 X（去重、按 ID 排序）。
- 权限只在 `allowed_permissions` 是列表时检查：所缺权限必须由 `--allow-permission` 一个不多、一个不少地给出（重复的 `--allow-permission` 按集合处理），这时一并写入 `allowed_permissions`（整份列表去重、按字符串排序）。给多、给少，或当前不限制时还给了，都是用法错误（退出 2）。“因此满足权限条件”= 补上后不再缺任何权限。
- `disable X`：只要求 X 存在（第六节）。`enabled` 缺省时，把“当前布局下全部插件目录名（匹配 PLUGIN_ID，不是链接目录，不论 manifest 好坏）减去 X”写成显式列表（按 ID 排序），并提示“从不限制改为显式列表，之后新增的插件不会自动启用”。`enabled` 是列表时移除 X；不在列表里则无变化。不碰 `allowed_permissions`。
- 写入时 `plugins.enabled` 与 `plugins.allowed_permissions` 只按上述规则改动，其它键与其它子键不动。

### 十一、授予路径（B2，review 第 1 项）
- enable 的 `--allow-permission` 要列出“因此满足权限条件的其他插件”。遍历枚举结果（含链接目录）。读取其他插件的 `manifest.json` 之前，做与第八节同样的读前检查（`pd.first_link_component(pd.KIT_ROOT, "plugins/<id>/manifest.json")` 等）。
- 链接类失败（第 3 行）输出一行问题：`<ID> 无效：链接 …`，含该插件 ID 与字面串 `无效：链接`。其它失败（第 4 行的清单失败、读取失败、解析失败、validate_manifest 失败）输出一行 `<ID> 无效：<原因>`。这些插件不计入“满足权限条件”的清单，不静默跳过，不影响 enable X 的退出码。
- 受影响清单行：`以下插件也将满足权限条件：<ID>、…`（含字面串 `满足权限条件`）；只在成功写入或 dry-run 成功时输出，被拒绝时不输出（第十三节）。

### 十二、题库门禁（review 第 5 项）与恢复顺序
- 无变化路径与写入路径走同一条路：先题库门禁，再整份校验。
- 题库门禁：新配置里决策插件生效（`settings_from_config(...).active`）时调用 `verify_battery_lock`；它抛出的 ValueError、OSError、DecisionError 都拒绝（退出 1）。拒绝时 stderr 打印一行 `ERROR:`，含原因与恢复顺序，其中必须有字面串 `plugins disable decisions` 与 `config decisions off`。配置字节不变。
- 恢复顺序文字由 `kit_plugins` 自己输出（它不是 kit_config 的配置候选，不属于 `plugins_fix_hint` 的范围）。
- 写入前的整份校验（`kit_config.validate_config`）错误：拒绝（退出 1），字节不变。
- 题库阶段在核对分析中收集 ValueError、OSError、DecisionError：记为该插件的问题（第八节第 17、18 行），不改变锁列，verify 退出 1，问题行含文件名与“不一致”。

### 十三、变化摘要（review 第 10 项）
- enable 与 disable 的写入与 `--dry-run` 都先输出每个变化的子键一行：`plugins.<键>: <旧值> → <新值>`（旧值不存在时写“未设置”；值写 JSON 文本）。
- 无变化时输出“没有变化”，且只输出一次（其它提示照常输出，但不再重复“没有变化”）。
- 授予路径的问题行与受影响清单（第十一节）只在成功（写入或 dry-run 成功）时输出，被拒绝时不输出。
- `disable decisions` 时，只有决策插件由生效变为不生效（即 disable 使 `decisions` 不再在 enabled 中，且之前是生效的）才输出“决策插件会因此变为 off”。decisions 本不在列表里（无变化）时不输出；disable 其它插件时不输出。
- 写入成功输出 `已写入 <配置路径>`；dry-run 成功输出 `plugins 段（dry-run，未写入）：` 加该段的 JSON。

### 十四、show 的输出（review 第 8 项）
- 见第二节。`锁 generation`、`锁 lock_sha256` 在 lock.json 通过读前检查并解析为对象时输出，与锁是否一致无关（锁漂移时仍输出原值）。
- 资源行与问题行的前缀见第三节。

### 十五、检查顺序（review 第 9 项）
- 固定顺序：G1（不在 Git 仓库）→ 插件 ID 格式（B3）→ 插件 ID 存在（G2）→ 读配置（格式错误为退出 1）→ plugins 段（第七节）→ 其余步骤。
- verify 不指定 ID 时跳过前两步的 ID 检查，其余同上。
- 配置读不出（JSON 不合法）时，ID 错误仍按前两步退出 2。

### 十六、逐插件收集（review 第 12 项）
- 每个插件的核对（含授予路径读取其他插件）整体收集 ValueError、OSError、DecisionError：该插件的锁列记“无效”，原因写“核对失败：<异常文字>”，其余插件照常。命令本身不因此退出。

### 十七、共用规则（D11，逐条照做）
- 写配置只经 `kit_config.write_checked`，不得直接写文件。
- 修复提示只来自 `kit_config.plugins_fix_hint`（题库恢复顺序除外）。
- 链接与边界检查只用 `pi_dispatch.is_link_or_junction`、`pi_dispatch.first_link_component` 与 `pi_dispatch.is_within`，不得另写同类实现。
- 写入失败（OSError）或整份校验不过时，配置字节不变，退出 1。

### 十八、兼容性与边界
- 不修改任何既有文件；`kit_plugins` 是新模块，不接入调度器；同一份配置在外部运行与安装布局下都合法（只校验格式，不校验是否安装）。
- 并发、取消与状态变化：不适用（单进程本地命令，不写后台状态）。
- 不提供 `--version`（`--version` 是 argparse 的未知选项，退出 2）。

### 十九、测试约定（执行端自己的测试也遵守）
- pytest 函数写法；临时目录只用 `tmp_path`，不用 `tempfile` 与 `mkdtemp`；用 `pytest.skip` 代替 `skipTest`。
- 插件树从仓库 `plugins/` 复制到 `tmp_path` 后只改副本；junction 与符号链接的目标只能在 `tmp_path` 之内；不得修改仓库里真实的 `plugins/`。
- 文件名与键名写字面量。

## Steps
前置（核实）：读取 Repository facts 中的文件与符号，确认签名与基线一致（`grep -n "^def " scripts/kit_plugins.py` 等）。不一致就停止并报告。

以下步骤按 review attempt-001 的第 0–14 项顺序，每步在一个函数层面完成；每步结束时运行与之相关的检查（不必跑全量）。

0. 先写最小的 `tests/test_kit_plugins.py`，至少 1 个用例能通过（pytest 函数写法、`tmp_path`，只用合成副本）。之后的每一步都可以往这个文件里补用例（D11 的用例见下）。
1. B2（第十一节）：`_permission_impact` 不再跳过链接目录；链接类失败输出 `<ID> 无效：链接 …` 问题行；不计入受影响清单。
2. 锁列只取四值（第八节）：`_read_json_file`、`_check_plugin`、`_check_resources`、`_check_battery` 的链接类失败设为锁列“无效”，原因文字含字面串 `无效：链接`；`cmd_list`（链接目录行）与 `cmd_verify` 的标题行按第二节输出；list --json 与 verify --json 的字符串值中不出现恰为“无效：链接”的值（show 的资源状态除外）。
3. 资源读取失败（第八节第 13 行）：`_check_resources` 读取抛 OSError 时，资源列“不一致”、锁列“无效”、问题含 `资源读取失败`；继续核对其余资源与题库。
4. 配置段校验（第七节）：`cmd_list`、`cmd_show`、`cmd_verify`、`cmd_enable`、`cmd_disable` 读到配置后调用 `kit_config.plugins_section_error(config)`，不为 None 时按第七节打印 ERROR 行、退出 1、不写。
5. 题库门禁与无变化路径（第十二节）：`_finish_mutation` 先调 `_battery_gate`，再整份校验；无变化路径与写入路径相同。
6. 权限与状态（第九节）：`_list_row`、`cmd_show` 的缺权限与状态改用 `plugins.check_permission_intersection`；不限制时不调用；READY 只看锁、资源、权限三项。
7. 未安装（第六节）：`_not_installed` 用枚举结果（含链接目录），不再只用 `_installed_ids()`。
8. show（第十四节）：`cmd_show` 在 lock.json 通过读前检查且解析为对象时，输出 `锁 generation` 与 `锁 lock_sha256` 的原值（锁漂移时也输出）。
9. 检查顺序（第十五节）：`cmd_verify` 先校验 ID（如给出）与存在性，再读配置。
10. 变化摘要（第十三节）：`_finish_mutation` 与 `cmd_disable` 输出 `plugins.<键>: 旧 → 新` 行；“没有变化”只一次；受影响清单只在成功时输出；“决策插件会因此变为 off”只在 decisions 真正被关掉时输出。
11. 悬空链接（第六节、第八节第 1–2 行）：`_root_is_link` 与 `_enumerate_entries` 对悬空链接也判为链接（用 `pd.is_link_or_junction`，不要求目标存在）；根是链接时枚举为空。
12. 逐插件收集（第十六节）：`_check_plugin_safe` 或等价的包裹收集 ValueError、OSError、DecisionError，记“无效”加原因；授予路径的其他插件同样。
13. verify 标题（第二节）：锁一致而资源不一致时标题为 `<ID> 资源不一致`，绝不为 `<ID> 一致`。
14. 执行报告（最后）：写 interpretations 与 contract_conflicts；未完成的 DoD 标 blocked 并写明原因。

D11 的执行端用例（写在 `tests/test_kit_plugins.py`，每例用合成副本，断言只用第三节的词、退出码与文件字节）至少覆盖：第 1 项（授予路径的链接目录问题行，不在清单中）、第 2 项（锁列四值，list --json 的字符串值）、第 3 项（资源读取失败的锁列与资源列）、第 4 项（plugins 段不合法时五个子命令退出 1、带修复提示、不写）、第 5 项（无变化路径上的题库门禁给出恢复字样，配置字节不变）。

### 时间限制的收尾
- 单轮时限 2700 秒由调度器强制，到点直接终止，来不及写的报告就丢了。所以第一条命令先记下 `date +%s`，每完成一步再看一次；累计超过 2100 秒（35 分钟）就停止新的改动，先写执行报告（未完成的步骤与 DoD 标 blocked，写明未完成的原因）。不得以未运行的检查声称通过。

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态。需要截短输出时照抄执行说明“机器合同摘要”里每条检查的“自检照抄”写法（bash 以 `set -o pipefail;` 开头）。不要把输出写到固定路径。每个检查都写具体文件名，不运行整个 `tests` 目录（本机 Python 环境里有第三方 `tests` 包会遮住仓库的 tests/）。不做变异检查。

- V01（必要）：`python -m pytest tests/test_kit_plugins_oracle.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配 `[1-9]\d* passed` · 基线应失败
- V02（必要）：`python -m pytest tests/test_kit_plugins.py -q` · cwd：仓库根 · 超时：300s · 期望退出码：0 · 输出须匹配 `[1-9]\d* passed`
- V03（必要）：`python -m py_compile scripts/kit_plugins.py` · cwd：仓库根 · 超时：60s · 期望退出码：0
- V04（必要）：`python scripts/kit_plugins.py --help` · cwd：仓库根 · 超时：60s · 期望退出码：0 · 输出须匹配 `usage:`

## Definition of done
- D01：list、show、verify 按第二节与第八节输出锁列四值、资源列、状态与退出码，坏插件不拖垮命令；证据：V01。
- D02：enable、disable 按第十节改变 plugins.enabled 与 plugins.allowed_permissions，含 --dry-run、--allow-permission、非列表值拒绝，授予路径的读前链接检查；证据：V01。
- D03：写入只经 kit_config.write_checked，校验不过或写入失败时配置字节不变，命令级错误打印一行 ERROR 并返回退出码，不输出堆栈；证据：V01。
- D04：读前逐级链接与边界检查只用 pi_dispatch 的 is_link_or_junction、first_link_component、is_within，不另写同类实现；证据：V01、review。
- D05：所有修改都在允许集合内（scripts/kit_plugins.py 修改，tests/test_kit_plugins.py 新增）；证据：scope。
- D06：没有删除、跳过或弱化既有测试（含 oracle），执行端自己的测试只用合成副本、不改真实 plugins/；证据：review、V02。
- D07：scripts/kit_plugins.py 可编译；证据：V03。
- D08：命令行可运行，--help 输出 usage:；证据：V04。
- D09：插件 ID 先按 PLUGIN_ID 校验（B3），枚举与存在性（链接目录列出，悬空链接算链接，plugins 根是链接时枚举为空），G1、G2，检查顺序；证据：V01。
- D10：题库门禁（无变化路径与写入共用）、show 的 generation 与 lock_sha256 原值、变化摘要、allowed_permissions 去重排序、disable 的显式列表排除链接目录、不提供 --version；证据：V01。
- D11：执行端测试 tests/test_kit_plugins.py 覆盖 review 第 1–5 项（授予路径的链接目录问题行、锁列四值、资源读取失败、plugins 段不合法的五个子命令、无变化路径的题库门禁）；证据：V02。
- D12：review 第 6–13 项的实现（权限状态与调用条件、未安装口径、show、检查顺序、变化摘要、逐插件收集、verify 标题、悬空链接）由 V01 中的增补用例覆盖；证据：V01。

## Budget
- max_attempts_total: 2（按 task-id 汇总，包括 v1 的 attempt-001；本版是最后一次派遣）
- max_wall_seconds_per_attempt: 2700
- max_wall_seconds_total: 5400（v1 的 attempt-001 已用 2700.031 秒，本版剩余约 2699.97 秒；调度器按剩余时间截短单轮上限）
- cost_budget: tracking-only（bb/step-5-preview 只报 token，费用记 unknown）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配（合计约 31 分钟，不超过单轮 2700 秒的 70%）：
  - 核实事实：约 2 分钟
  - 实现（步骤 0–13）：约 19 分钟
  - 执行端测试（覆盖 D11 的第 1–5 项）：约 4 分钟
  - 必要检查（V01–V04）：约 3 分钟
  - 执行报告：约 3 分钟

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D12，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `write_checked`、`first_link_component`、`plugins_section_error` 不存在或签名不同，或基线中没有 `tests/test_kit_plugins_oracle.py`）。
- 必须修改允许范围之外的文件才能继续。
- 需要安装依赖、联网、读取凭据或提升权限。
- 合同、设计或概要步骤之间互相冲突，且无法按第八节的裁定表解释。
- 达到单轮时限（见“时间限制的收尾”）。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置，也不写入 `.agent/` 下任何文件。
- 不修改 `tests/test_kit_plugins_oracle.py`、`kit_config.py`、`codekit/**`、`pi_dispatch.py`。
- 不删除、跳过或弱化既有测试来获得通过。
- 不提交（authorized_actions 没有 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不用 tempfile 或 mkdtemp 另建目录；测试临时目录只用 pytest 的 tmp_path；需要在命令里新建临时目录时只能写成 `T=$(mktemp -d)`，并以 `rm -rf "$T"` 作为这条命令的最后一步。不把输出写到固定路径。
