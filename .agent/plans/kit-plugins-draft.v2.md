# TASK: kit-plugins-draft

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: c1c2e196e7766207927f28f6218cf470cb556343
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: none
- executor: bb/step-5-preview · thinking high

## Goal
在返工基线上修改 attempt-001 留下的起草产物，使之达到发布标准：(a) 实现合同草稿 `drafts/kit-plugins/contract.md` 与 `contract.json`；(b) oracle 测试 `tests/test_kit_plugins_oracle.py`；(c) 参考实现 `scripts/kit_plugins.py`，只用来证明 oracle 有效，不发布。本次是本任务的最后一次尝试，不集成。

## Non-goals
- 不重写三个文件：保留 v1 中已经正确的部分，只改下面 Steps 列出的内容。
- 不修改 `plugins/`、`scripts/kit_config.py`、`scripts/pi_dispatch.py`、`scripts/codekit/`、既有测试（`tests/test_kit_config.py` 等）与文档。既有 oracle 用例只能加强断言，不能删除或弱化。
- 不接入调度器转发（设计 D8）；不改 README、AGENTS.md、CHANGELOG（设计 D9）。
- 不做插件安装、升级、删除，不执行插件 checks，不联网，不重新生成锁。
- 不提交、不推送、不派遣，不写 `.agent/` 下任何文件。

## Repository facts
- 基线 `c1c2e19` 是返工基线：父提交 `ce04541`，它包含 attempt-001 的候选：`drafts/kit-plugins/contract.md`、`drafts/kit-plugins/contract.json`、`tests/test_kit_plugins_oracle.py`、`scripts/kit_plugins.py`。这四个文件在基线里已经存在，所以本轮对它们的改动是“修改”，列在 allowed_modified_files。
- 规划端的复审记录是 `.agent/reviews/kit-plugins-draft/attempt-001.md`，只在规划端的主仓库里，执行器的 worktree 里没有，不要去主仓库读。下面 Steps 已把其中要改的内容全部写出，执行器不需要它。
- 设计：`docs/themis-tally-3.0-r1-日志与插件管理.md` 的 §2.3、§2.4、§3（D1、D5–D7、D10、D11）、§4.2、§4.3、§9 的 P 组；上位设计 `docs/themis-tally-3.0-四端分层解耦架构.md` 的 §4.2、§4.7、§6.7、§6.8。
- `scripts/kit_config.py`：导入 `pi_dispatch as pd` 与 codekit 的写法在第 40–52 行；`class ConfigError` 在第 63 行，缺省退出码 1；`_check_plugins` 在第 169 行；KEYS 中的 `plugins` 项在第 216–217 行；`load_config(repo)` 在第 236 行；`validate_config(config, repo, *, hints=True)` 在第 249 行，plugins 键的错误后附加“；修复：…”（第 266–269 行）；`plugins_fix_hint(config, repo)` 在第 283 行；`write_checked(repo, config)` 在第 421 行，校验不过抛 `ConfigError` 且一个字节都不写；`main(argv=None, repo=None)` 在第 729 行；`decisions` 子命令（第 713–715 行）接受 off、shadow、on、marker。`_check_decisions` 在调用时读取 `pd.DECISIONS_PLUGIN_DIR`（第 156、161 行）。
- `scripts/pi_dispatch.py`：`EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_BLOCKED, EXIT_DRIFT = 0, 1, 2, 3, 4`（第 57 行）；`is_within(path, root)`（第 558 行）；模块属性 `KIT_ROOT`（第 3672 行）与 `DECISIONS_PLUGIN_DIR`（第 3673 行）；`is_link_or_junction(path)`（第 5203 行）；`first_link_component(root, rel)`（第 5227 行）；`DispatchError(message, code)`（第 480 行，`Repo.discover` 不在 Git 仓库时抛它，退出码 2）。
- `scripts/codekit/plugins.py`：`PLUGIN_ID`（第 19 行，正则 `^[a-z][a-z0-9-]{0,63}$`）；`PluginError(ValueError)`（第 30–32 行，属性 `code`、`path`）；`validate_manifest(manifest)`（第 173 行）；`build_lock(manifests, *, compiler_sha256, generation=1)`（第 288 行）；`validate_lock(lock, manifests=None)`（第 307 行；lock_sha256 不符抛 `E_PLUGIN_LOCK_DRIFT`，锁与 manifest 字节绑定或插件集合不符抛 `E_PLUGIN_LOCK_BINDING`）；`check_permission_intersection(...)`（第 377 行）。
- `scripts/codekit/decisions.py`：`PLUGIN_ID = "decisions"`（第 48 行）；`PERMISSION = "network-decisions"`（第 49 行）；`DecisionError(RuntimeError)`（第 74 行，属性 `code`、`detail`）；`verify_battery_lock(plugin_dir)`（第 312 行）；`settings_from_config(config, agent_dir, plugin_dir)`（第 452 行）。
- `scripts/codekit/protocols.py`：`strict_json_loads(raw_bytes)`，重复键即抛 `ProtocolError(ValueError)`。
- `plugins/` 下有 8 个插件目录：code-change、decisions、docs-change、docs-checks、mutation-review、python-checks、regression-tests、repo-analysis。
- `tests/test_kit_config.py`：把 `scripts/` 插入 sys.path 并用裸名导入的写法在第 22–26 行；`class PluginsKey`（第 282 行）用 `mock.patch.object(kit_config.pd, "KIT_ROOT", …)` 与 `DECISIONS_PLUGIN_DIR` 在临时插件副本上测试（第 359–360 行）。
- 参考实现 `scripts/kit_plugins.py` 的函数，基线行号仅供定位：`_installed_ids` 65–74、`_listed_ids` 77–83、`_is_plugin` 86–87、`_analyze_plugin` 119–243、`_newly_satisfied` 500–513、`cmd_list` 299–324、`cmd_show` 345–379、`cmd_verify` 382–415、`_decisions_gate` 448–464、`_apply` 467–492、`cmd_enable` 516–581、`cmd_disable` 584–621、`build_parser` 628–662、`main` 665–689。
- 写法与测试约定：AGENTS.md 只允许执行器使用测试框架自己管理的临时目录（例如 pytest 的 `tmp_path`），不允许用 `tempfile` 等方式另建目录。这是对设计 §2.5（描述现状的 unittest 写法）的有意偏离，已由用户接受。

## Scope
- allowed_modified_files:
  - drafts/kit-plugins/contract.md
  - drafts/kit-plugins/contract.json
  - tests/test_kit_plugins_oracle.py
  - scripts/kit_plugins.py
- allowed_new_files: 无
- allowed_deleted_files: 无
- forbidden_paths:
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
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
- 正常输入（交付状态）：
  - 合同草稿：`drafts/kit-plugins/contract.md` 与 `contract.json` 是实现任务 `kit-plugins` 的正式合同草稿，符合下面“内层合同的要求”。
  - oracle：`tests/test_kit_plugins_oracle.py` 覆盖 §9 的 P1–P17，并补齐 Steps 中列出的用例；全部通过。
  - 参考实现：`scripts/kit_plugins.py` 修正到 oracle 全部通过。它只用来证明 oracle 有效，不发布。
- 写死的行为（用户与规划端已裁定。内层合同必须逐条写明，不得改动；合同端若认为不合适，只能写进 contract_conflicts，不得改动实现）：
  - G1：不在 Git 仓库里运行任何子命令（list、show、verify、enable、disable），用法错误，退出码 2。
  - G2：enable、disable、show、verify 的插件 ID 不存在，退出码 2。
  - G3：verify（不论是否指定 ID）把“本轮不支持”的插件计为问题，退出码 1；list 照常列出，锁列显示“本轮不支持”。
  - G4：`--dry-run` 与真正写入走同一套校验（整份校验与决策题库核对）。校验失败：退出码 1，打印原因，配置字节不变。校验通过：退出码 0，不写文件。
  - B3：show、verify、enable、disable 的插件 ID 先按 `PLUGIN_ID`（正则 `^[a-z][a-z0-9-]{0,63}$`）校验。不合法或不存在时退出码 2，stderr 打印一行 `ERROR:`（含该 ID），不输出堆栈。list 没有 ID 参数。
  - B4：list 的退出码为 0，坏插件不拖垮命令；不在 Git 仓库（G1）与参数错误（argparse）时为 2。
  - 枚举与存在性（D5）：插件枚举只取 `plugins/` 根下名字匹配 `PLUGIN_ID` 的直接子目录，链接目录也列出（它们按“无效：链接”核对）。“插件 ID 存在”即“在枚举结果中”。`plugins/` 根本身是链接时枚举为空：list 打印一行 `无效：链接 plugins` 并退出 0；verify（不指定 ID）同样打印该行并退出 1；任何 ID 都不存在（退出 2）。
  - 读前检查（D5）：实际读取的每个文件（manifest.json、lock.json、每个资源文件，以及决策插件的 questions/ 目录与其中每个 *.json）在读之前，都从 KIT_ROOT 往下逐级检查链接与 junction，并确认是普通文件（目录则确认是普通目录）；资源路径必须以 `plugins/<id>/` 开头。任何一项失败，停止该插件的后续读取与核对，锁列记为“无效”，输出含“无效：链接”及具体组件或路径，且不调用 `verify_battery_lock`。
  - 授予路径（B2）：enable 的 `--allow-permission` 要列出“因此满足权限条件的其他插件”，遍历枚举（含链接目录）。读取其他插件的 manifest.json 之前，做同样的读前链接检查（`pd.first_link_component(pd.KIT_ROOT, "plugins/<id>/manifest.json")`）。失败（链接，或读取、解析、validate_manifest 失败）计为“该插件的问题”：stdout 输出一行，含该插件 ID；链接时含字面串“无效：链接”，其他失败时含“无效”与原因。不静默跳过；不影响 enable X 的退出码；该插件不计入“满足权限条件”。
  - disable 写显式列表（enabled 缺省时）：列表 = 枚举中的非链接目录减去 X，按 ID 排序；链接目录不列入。
  - disable 的 X 不存在（含 `plugins/` 根是链接）：退出码 2，不写配置。
  - allowed_permissions 写入：整份列表去重，并按字符串排序（与 enabled 一致）。
  - 题库阶段：除 `DecisionError` 外也收集 `OSError` 与 `ValueError`。核对分析阶段记为该插件的问题（不改变锁列，verify 退出码 1）。写入前的决策插件核对拒绝写入时，stderr 打印一行 `ERROR:`（含原因），退出码 1，配置字节不变，不输出堆栈。
  - show：输出 lock.json 的 `generation`（字面词 `generation` 后接其值）与 lock_sha256；每个资源一行，行内含资源路径与核对结果（一致 / 不一致；D5 读前检查失败时为“无效：链接”）。
  - 资源路径越出插件目录、资源不是普通文件、资源是链接：按读前检查的规则，锁列记为“无效”，输出含字面串“无效：链接”及原因。
  - 不提供 `--version`（设计没有要求）。
  - 命令级错误（ID 不合法或不存在、G1、用法错误、写入失败、写入前拒绝）：stderr 一行，以 `ERROR:` 开头，退出码按下面的含义。
- 锁状态（list、show、verify 的“锁”列）判定顺序，与 v1 相同：(1) 读前链接检查失败 → 无效；(2) 读取并严格解析 manifest.json 与 lock.json（`protocols.strict_json_loads`）失败 → 无效；(3) 目录名与 manifest 的 plugin_id 不符，或 validate_manifest 失败 → 无效；(4) manifest 的 depends_on 或 conflicts 非空 → 本轮不支持（不调用 validate_lock）；(5) validate_lock 通过 → 一致；抛 PluginError 且 `code` 为 E_PLUGIN_LOCK_DRIFT 或 E_PLUGIN_LOCK_BINDING → 漂移；抛其余错误 → 无效。资源哈希另列一列（一致 / 不一致），不改变锁列；只差 CRLF 时问题行含 `CRLF`。
- 固定词（oracle 逐字断言；实现原样输出，不得改写）：
  - 状态词：`一致`、`漂移`、`无效`、`本轮不支持`、`不一致`、`READY`、`BLOCKED`、`是`、`否`、`不限制`、`off`。
  - 字面串：`无效：链接`、`CRLF`、`修复：`、`plugins disable decisions`、`config decisions off`、`决策插件会因此变为 off`、`未安装`（enabled 里未安装的插件所在行）、`generation`。
  - 文件名与键名：`manifest.json`、`lock.json`、`dispatch.config.json`、`questions`、`enabled`、`allowed_permissions`、`plugin_id`。
- 退出码含义：0 成功或无变化（list 恒为 0）；1 被拒绝、校验不过、写入失败、核对有问题；2 用法错误（含不在 Git 仓库、插件 ID 不合法或不存在、参数给多给少）。
- 与 v1 相同、保持不变：D6 的 enable、disable 语义；`--allow-permission` 一个不多一个不少；非列表值拒绝并附“修复：”（提示只来自 `kit_config.plugins_fix_hint`）；写入只经 `kit_config.write_checked`；D10 的收集与不输出堆栈；D11 只调用既有公开函数（pi_dispatch 的 `is_link_or_junction`、`first_link_component`、`is_within`，kit_config 与 codekit 的公开函数）。题库不一致时的恢复顺序由 kit_plugins 自己输出，不经 plugins_fix_hint。
- 允许合同端自行决定的取舍（限于设计 §4.2、D5、D6 的范围；每一项写进执行报告的 interpretations，写明合同原文、采用的做法与理由）：
  - T1：`--json` 的键名与结构。oracle 只断言输出可解析为 JSON 对象，不断言键名。
  - T2：文字输出的格式、列宽与提示语措辞。oracle 只断言本合同写明的固定词、插件 ID、退出码与文件字节。
  - T3：授予权限时受影响插件清单的排序与格式（§4.2 要求列出）。
  - T4：写入失败（OSError）时的提示文字自定；退出码记为 1。
- 错误与重试：合同、设计或仓库事实互相冲突时，停止该部分，写进 contract_conflicts，不自行选定一种解释当作完成。
- 并发、取消与状态变化：不适用（单进程本地命令，不写后台状态）。
- 兼容性：不修改任何既有文件；`kit_plugins` 是新模块，不接入调度器。

## 内层合同的要求
写进 `drafts/kit-plugins/contract.md` 与 `contract.json`。执行器修改基线里已有的这两个文件，不重写。
1. Identity：`plan_version` 1；`repository` ThemisTally；`base_sha` 用全零占位 `0000000000000000000000000000000000000000`，发布时由审核端替换；`risk_level` medium；`authorized_actions` local_edit, local_test；`integration_actions` local_branch, merge；`executor` bb/step-5-preview · thinking high。
2. JSON 字段：同 v1（`outline_ref` 的 sha256 为 e2885dd535bca98b04d0582bca398790942056acffbd67a2fcfb028732fda728，budget 为 2700 / 5400（规划端裁定：v1 草稿的 1800 / 3600 对这个规模偏紧），不写 `contract_family` 与 `execution_profile`）。coverage：每个条目的 `scope` 写成数组；给 D07 落点（挂在 S7，检查 V03）；S7 的 dod 补上 D01–D03 的 CLI 部分（即 D01、D02、D03、D07、D08）；`deviations` 为空数组。
3. Scope：同 v1 的内层 Scope（允许新建 `scripts/kit_plugins.py` 与 `tests/test_kit_plugins.py`；禁止 `tests/test_kit_plugins_oracle.py` 等）。
4. 检查：V01 `python -m pytest tests/test_kit_plugins_oracle.py -q`，输出须匹配 `[1-9]\d* passed`；V02 `python -m pytest tests/test_kit_plugins.py -q`，输出须匹配 `[1-9]\d* passed`；V03 `python -m py_compile scripts/kit_plugins.py`；V04 `python scripts/kit_plugins.py --help`，输出须匹配 `usage:`。V01 至 V04 全部为 required。每个检查都写具体文件名，不得运行整个 `tests` 目录。
5. DoD：D01 list、show、verify 只读命令按 §4.2 输出状态词与退出码，坏插件不拖垮命令；D02 enable、disable 按 D6 改变 plugins.enabled 与 plugins.allowed_permissions，含 --dry-run、--allow-permission 与非列表值拒绝，授予路径的链接检查；D03 写入只经 write_checked，校验不过或写入失败时配置字节不变，命令级错误打印一行 ERROR 并返回退出码，不输出堆栈；D04 读前逐级链接与边界检查只用 pi_dispatch 的公开函数；D05 范围；D06 没有删除、跳过或弱化既有测试；D07 scripts/kit_plugins.py 可编译；D08 命令行可运行，--help 输出 usage:；D09 插件 ID 先按 PLUGIN_ID 校验，枚举与存在性规则（含 plugins 根是链接），G1、G2；D10 题库阶段收集 OSError 与 ValueError，show 输出 generation 与逐资源核对，allowed_permissions 去重排序，disable 排除链接目录，不提供 --version。每条写证据，每个检查至少被一条 DoD 引用。
6. 行为说明（Behavior contract）：以设计 §4.2、D5、D6、D10、D11 为准，并逐条写明上面“写死的行为”、锁状态判定、固定词与退出码含义（逐字，与 oracle 断言的词一致）。另外写明：`kit_plugins` 在调用时读取 `pd.KIT_ROOT` 与 `pd.DECISIONS_PLUGIN_DIR`，不把它们复制进模块常量；调用 codekit 时通过模块属性（如 `decisions.verify_battery_lock`），不从模块 from-import 这些名字；导入 `pi_dispatch`、`kit_config`、`codekit` 的写法与 `kit_config.py` 第 40–52 行相同；模块暴露 `pd`，使 `kit_plugins.pd is kit_config.pd`。oracle 不得断言合同没有写明的词。
7. 测试约定（写进内层 Behavior contract，执行端自己的测试也遵守）：pytest 函数写法；临时目录只用 `tmp_path`，不用 `tempfile` 与 `mkdtemp`；用 `pytest.skip` 代替 `skipTest`；插件树从仓库 `plugins/` 复制到 `tmp_path` 后只改副本；junction 与符号链接的目标只能在 `tmp_path` 之内；不得修改仓库里真实的 `plugins/`；文件名与键名写字面量。
8. 内层合同不得提及参考实现、草稿 worktree 或起草过程。
9. 占位规则：两份内层文件里不得残留模板的填写标记（方括号包住的说明性字样），也不得残留模板里的大写替换标记；全零的 `base_sha` 是唯一允许的占位。
10. 事实表（Repository facts）删去 `_installed_plugin_ids()` 及任何 kit_config 私有函数；读前检查补上 D5 的枚举规则（plugins 根或插件目录为链接时的处理，与上面的“枚举与存在性”一致）。第 67 行的 list 退出码改为“0（不在 Git 仓库或参数错误时 2，见 G1）”。

## oracle 用例（Steps 中指定；新增用例的名字以 `test_<编号>_` 开头，既有用例名保持不变）
- 保留并加强的既有用例：test_pd_identity_and_bare_import、test_p01_eight_plugins_all_consistent、test_p02a/b/c、test_p03_lock_sha_drift、test_p04_manifest_binding_drift、test_p05_* 既有用例、test_p06_*、test_p07_*、test_p08_*、test_p09_*、test_p10a/b/c、test_p11_*、test_p12a/b、test_p13_*、test_p14a/b、test_p15_*、test_p16a/b、test_p17_*、test_json_outputs_parse_to_objects。
- 新增：见 Steps 第 6、9、11–14、15 步。选择器 `test_g1_ or test_g2_ or test_g4_ or test_b3_` 只选这五个用例：test_g1_outside_git_repo_all_subcommands_exit_2、test_g2_unknown_id_exit_2、test_g4_dry_run_validation_failure_exit_1_bytes_unchanged、test_g4_dry_run_success_exit_0_no_write、test_b3_plugin_id_not_matching_exit_2_no_traceback。
- 失败判定：每个用例的断言都要能在参考实现被改坏时失败；文件链接变体用 `pytest.skip`（理由写“本机无法创建文件符号链接（需要权限）”）；目录 junction 能建时必须真的运行。

## Steps
每一步对应规划端复审记录（attempt-001）的编号。只做这里写出的内容。
1. [B4、m4] 内层合同：第 67 行改为 list 退出码 0（不在 Git 仓库或参数错误时 2，见 G1）；第 25 行事实表删去 `_installed_plugin_ids()`；第 90 行读前检查补枚举规则。
2. [B3、G2] 参考实现：新增插件 ID 校验（`plugins.PLUGIN_ID`）与存在性判断（枚举结果）。`cmd_show`、`cmd_verify`（有 ID 时）、`cmd_enable`、`cmd_disable` 入口先校验，不合法或不存在时 stderr 打印一行 `ERROR: 插件 ID 不合法或不存在：<id>`，退出码 2。`_is_plugin` 改为枚举判断。内层第 6 项同步写明。
3. [m3、B3] 参考实现枚举规则：`_listed_ids`（77–83）与 `_installed_ids`（65–74）在 `plugins/` 根是链接时返回空；`cmd_list` 在根是链接时打印 `无效：链接 plugins` 并退出 0（基线已有，确认）；`cmd_verify` 无 ID 且根是链接时加入该问题并退出 1；`_not_installed` 用枚举（含链接目录）判定未安装。
4. [B2] 参考实现 `_newly_satisfied`（500–513）：改为遍历 `_listed_ids()`；每个其他插件先做 `pd.first_link_component(pd.KIT_ROOT, "plugins/<id>/manifest.json")`；失败，或读取、解析、validate_manifest 失败，都返回问题行，不再 `continue` 静默跳过。`cmd_enable` 把问题行打印到 stdout（每插件一行，含插件 ID；链接时含“无效：链接”）。问题不影响退出码，该插件不计入“满足权限条件”。
5. [m3] 题库阶段：`_analyze_plugin` 的题库段（约 234–240 行）捕获 `(decisions.DecisionError, OSError, ValueError)`，记为该插件的问题，锁列不变；`_decisions_gate`（448–464）捕获同一组异常，stderr 打印一行 `ERROR:`，退出码 1，配置不变。
6. [m5] `cmd_disable`（584–621）unrestricted 分支的显式列表用 `_installed_ids()`（非链接目录）减去 X；`build_parser`（628–662）删除 `--version`。
7. [m1] `cmd_enable` 写入 allowed_permissions 时整份列表去重并按字符串排序（约 555 行，检查所有写入路径都满足）。
8. [m1] 参考实现资源段（188–229）中“资源路径越出插件目录”（196–197 行）与“资源不是普通文件”（209–210 行）的输出改为含字面串“无效：链接”，原因写在其后。
9. [m2] 参考实现：`_analyze_plugin` 记录 `lock_raw["generation"]` 与每个资源的核对结果；`cmd_show`（345–379）输出 `lock.json：generation <值>，lock_sha256 <值>`，每个资源一行 `资源 <路径>：<一致|不一致|无效：链接>`。
10. [M2] oracle P1：期望插件列表取字面 8 个 ID，并断言复制副本里的目录名与之相同；不再调用 `kit_plugins._installed_ids()` 或任何被测模块的函数。
11. [m5、M2] oracle 结构：删除模块顶层的 `import kit_plugins`；每个用例内 `import kit_plugins`（helper 函数），`run()` 与 `run_hint()` 通过 helper 调用；没有参考实现时每个用例逐例失败，不是收集错误。
12. [B1] oracle 补：test_g1_outside_git_repo_all_subcommands_exit_2（list、show decisions、verify、enable code-change、disable code-change 在非 Git 目录下都退出 2，stderr 有 `ERROR:`，无 Traceback）；test_g2_unknown_id_exit_2（enable、disable、show、verify 对 `no-such-plugin` 都退出 2，enable、disable 的配置字节不变）；test_g4_dry_run_validation_failure_exit_1_bytes_unchanged（配置含非法键 surprise_key，`enable code-change --dry-run` 退出 1，字节不变）；test_g4_dry_run_success_exit_0_no_write（合法配置，`disable docs-change --dry-run` 退出 0，字节不变，输出含 plugins 段）。
13. [M1] oracle P5 子情形：新增 test_p05_plugins_root_is_junction（`plugins/` 根为 junction，verify 退出 1，输出含“无效：链接”，读取替身无 KIT 内插件 manifest 的读取）；test_p05_intermediate_dir_is_junction（合成插件 zz-mid，资源路径 `plugins/zz-mid/sub/data.txt`，`sub` 为目录 junction）；test_p05_resource_path_is_junction（合成插件 zz-res，资源 `plugins/zz-res/res.bin` 为目录 junction）；文件链接变体 test_p05_manifest_file_symlink_identical_content、test_p05_lock_file_symlink_identical_content、test_p05_questions_json_file_symlink、test_p05_resource_file_symlink，先尝试 `os.symlink`，失败则 `pytest.skip`。既有的目录 junction 用例保留，并在名字或注释里写明它是“目录链接变体”。合成清单与锁用 codekit 的公开函数生成。
14. [B2] oracle 补：test_b2_grant_path_other_manifest_link_not_read_and_reported（docs-change/manifest.json 为目录 junction，`enable python-checks --allow-permission read-candidate` 退出 0；读取替身无 docs-change/manifest.json 的读取；输出含 docs-change 与“无效：链接”；docs-change 不在“满足权限条件”的清单里）；test_b2_grant_path_broken_manifest_reported_not_silent（docs-change/manifest.json 为非法 JSON，退出 0，输出含 docs-change 与“无效”）。
15. [B3] oracle 补 test_b3_plugin_id_not_matching_exit_2_no_traceback：对 show、verify、enable、disable 与 ID `../plugins/code-change`、`a/b`、空串，退出码 2，输出含 `ERROR:`，无 Traceback；enable、disable 的配置字节不变。
16. [m1] 加强弱断言：P2c（题库问题行含该清单的文件名与“不一致”）；P6（目录名不符的行含 `plugin_id`；重复键的行含 `manifest.json`）；P7（输出含“不限制”）；P9（allowed_permissions 精确等于排序后的 `["network-decisions", "read-candidate"]`）；P16a（输出含“决策插件会因此变为 off”）；P17（输出含“未安装”与 `decisons`）；P5 资源越界（输出含“无效：链接”）。新增 test_m1_allowed_permissions_written_sorted_unique（配置 allowed_permissions 为 `["zeta-perm", "network-decisions"]`，enable python-checks --allow-permission read-candidate 后为 `["network-decisions", "read-candidate", "zeta-perm"]`）。
17. [m2] oracle 补 test_m2_show_generation_and_resource_hash：show code-change 输出含 `generation`；README 一行含“一致”；改 README 字节后该行含“不一致”。
18. [m3] oracle 补：test_m3_plugins_root_link_enumeration_empty（`plugins/` 根为 junction：list 退出 0 且含 `无效：链接 plugins`；verify 退出 1；`disable code-change` 退出 2，配置字节不变）；test_m3_battery_oserror_collected_in_verify（patch `codekit.decisions.verify_battery_lock` 抛 OSError，verify decisions 退出 1，无 Traceback，输出含 decisions）；test_m3_battery_valueerror_refuses_enable（decisions.mode 为 on，patch 抛 ValueError，enable code-change 退出 1，stderr 含 `ERROR:`，无 Traceback，配置字节不变）。
19. [m5] oracle 补 test_m5_disable_unrestricted_excludes_linked_plugin_dir（`docs-checks` 为目录 junction，`disable code-change` 在无限制配置下，enabled 不含 docs-checks 与 code-change，含 decisions）；test_m5_no_version_option（`--version` 退出码 2）。
20. 设计 §9 能写的都写（小量）：test_p09b_dry_run_lists_impact_no_write（`enable python-checks --allow-permission read-candidate --dry-run` 输出列出其他插件，退出 0，字节不变）；test_p11b_conflicts_unsupported（conflicts 非空，enable 退出 1，verify 退出 1 且含“本轮不支持”）；test_p12c_two_broken_manifests_disable_one（两个插件 manifest 坏掉，disable 其中一个，退出 0）。
21. [M3] 内层 contract.json：coverage 给 D07 落点（挂 S7、V03）；每个 `scope` 改为数组；S7 的 dod 补 D01–D03；新增 D09、D10 并给落点；`deviations` 为空数组。内层 contract.md 的 DoD 列表与 JSON 一致。
22. [过程] 临时目录只用 `tmp_path`，或 `T=$(mktemp -d) … rm -rf "$T"`（rm 是该命令的最后一步），不用 `tempfile.mkdtemp()`。合同前后矛盾写进 `contract_conflicts`；自定做法写进 `interpretations`（每条写合同原文、做法与理由）。
23. [检查] 运行 V01–V04。在执行报告里逐条列出复审记录 B1–B4、M1–M3、m1–m5 的改动位置与对应用例名，以及 V01–V04 的结果。基线由主会话运行，执行器不要运行基线。

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态。需要截短输出时照抄执行说明“机器合同摘要”里每条检查的“自检照抄”写法（bash 以 `set -o pipefail;` 开头）。不要把输出写到固定路径。V01–V04 只跑具体文件，不跑整个 `tests` 目录（本机 Python 环境里有第三方 `tests` 包会遮住仓库的 tests/）。不做变异检查。

- V01（必要）：`python -m pytest tests/test_kit_plugins_oracle.py -q` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配 `[1-9]\d* passed`
- V02（必要）：`python -c "import json; d = json.load(open('drafts/kit-plugins/contract.json', encoding='utf-8')); missing = [k for k in ('task_id', 'scope', 'checks', 'definition_of_done') if k not in d]; assert not missing, missing; print('JSON_OK')"` · cwd：仓库根 · 超时：60s · 期望退出码：0 · 输出须匹配 `JSON_OK`
- V03（必要）：`python -m py_compile scripts/kit_plugins.py` · cwd：仓库根 · 超时：60s · 期望退出码：0
- V04（必要，基线应失败）：`python -m pytest tests/test_kit_plugins_oracle.py -q -k "test_g1_ or test_g2_ or test_g4_ or test_b3_"` · cwd：仓库根 · 超时：300s · 期望退出码：0 · 输出须匹配 `[1-9]\d* passed`

## Definition of done
- D01：三个交付物修正：合同草稿符合 v2 要求，JSON 必需键齐全，coverage 与 scope 已修正；证据：V02、scope；目的：草稿可以被审核端直接改写成正式合同。
- D02：复审记录 B1–B4、M1–M3、m1–m5 逐条有对应修改，执行报告逐条列出改动位置；证据：review。
- D03：oracle 补齐写死的用例（G1、G2、G4、B2、B3、M1、M2、m1、m2、m3、m5 对应的用例名）且全部通过；证据：V01、review；目的：oracle 能区分正确实现与错误实现，而不是只能证明“能跑”。
- D04：参考实现修正后通过 oracle，只调用既有公开函数，不另写同类实现；证据：V01、V03、review。
- D05：所有修改都在允许集合内；证据：scope。
- D06：没有删除、跳过或弱化既有测试，既有用例只允许加强断言；证据：review。
- D07：探针 V04 在基线上失败（pytest 退出码 5，没有用例被选中），修完后通过；证据：V04；目的：证明这五个用例确实针对本轮的修改，而不是空跑。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符，例如 `write_checked`、`first_link_component`、`plugins.PLUGIN_ID` 不存在或签名不同。
- 必须修改允许范围之外的文件才能继续。
- 需要安装依赖、联网、读取凭据或提升权限。
- 合同、设计与复审要求之间互相冲突，且无法按设计解释。
- 达到单轮时限。

## Budget
- max_attempts_total: 2（按 task-id 汇总，包括所有版本；attempt-001 已用 1 次、2136 秒，本次是最后一次）
- max_wall_seconds_per_attempt: 3200（规划端裁定：最后一次，取剩余额度 3264 秒以内）
- max_wall_seconds_total: 5400
- cost_budget: tracking-only（bb/step-5-preview 只报 token，费用记 unknown）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读基线与复审要求约 5 分钟；参考实现修正约 12 分钟；oracle 补用例约 15 分钟；内层合同修正约 4 分钟；检查与报告约 4 分钟；合计约 40 分钟，不超过单轮 3200 秒。

## Report back
- 最后一条消息必须是执行报告：逐条列出复审记录 B1–B4、M1–M3、m1–m5 的改动位置与对应用例名；列出 V01–V04 的结果（V04 只报修改后的结果）；遗留问题与阻塞原因；末尾附上执行说明规定的 JSON 代码块。
- interpretations 必须包含 T1–T4 的每一项，每条写合同原文、采用的做法与理由；其他自定做法也写进 interpretations。
- 与合同前后矛盾的地方写进 contract_conflicts，并把相关 DoD 标为 blocked。
- 自检结果是自述；最终是否通过由审核端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置，不写入 `.agent/` 下任何文件（包括复审记录）。
- 不删除、跳过或弱化既有测试来获得通过；不改写 G1–G4 与 B3 的行为。
- 不提交（authorized_actions 没有 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不用 `tempfile` 或 `mkdtemp` 另建目录；测试临时目录只用 pytest 的 `tmp_path`，命令里需要临时目录时只用 `T=$(mktemp -d) … rm -rf "$T"`。
