# TASK: kit-plugins-draft

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: ce04541889a5b6cfbc34ce603a65b42afd08c241
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: none
- executor: bb/step-5-preview · thinking high

## Goal
在执行 worktree 里为实现任务 `kit-plugins` 起草并交付三样东西，本次起草不集成：(a) 正式实现合同的草稿 `drafts/kit-plugins/contract.md` 与 `drafts/kit-plugins/contract.json`；(b) oracle 测试 `tests/test_kit_plugins_oracle.py`，覆盖 3.0 第一轮设计 §9 的 P1–P17；(c) 参考实现 `scripts/kit_plugins.py`，只用来证明 oracle 有效，不发布。

## Non-goals
- 不修改 `plugins/`、`scripts/kit_config.py`、`scripts/pi_dispatch.py`、`scripts/codekit/`、既有测试与文档。
- 不接入调度器转发（设计 D8）；不改 README、AGENTS.md、CHANGELOG（设计 D9）。
- 不做插件安装、升级、删除、执行插件 checks、联网、重新生成锁。
- 不提交、不推送、不派遣，不写 `.agent/` 下任何文件。

## Repository facts
以下事实在基线 ce04541 上核对过（自 32f801d 起，该提交只新增了 tests/test_kit_logs_oracle.py，与这里引用的文件无关）。行号是该提交的行号，起草时仍须逐条核实：
- 设计：`docs/themis-tally-3.0-r1-日志与插件管理.md` 的 §2.3、§2.4、§3（D1、D5–D7、D10、D11）、§4.2、§4.3、§9 的 P 组；上位设计 `docs/themis-tally-3.0-四端分层解耦架构.md` 的 §4.2、§4.7、§6.7、§6.8。
- `scripts/kit_config.py`：导入 `pi_dispatch as pd` 与 codekit 的写法在第 40–52 行；`class ConfigError` 在第 63 行，缺省退出码 1；`_check_plugins` 在第 169 行；KEYS 中的 `plugins` 项在第 216–217 行；`load_config(repo)` 在第 236 行；`validate_config(config, repo, *, hints=True)` 在第 249 行，plugins 键的错误后附加“；修复：…”（第 266–269 行）；`_installed_plugin_ids()` 在第 274 行，读取 `pd.KIT_ROOT / "plugins"`；`plugins_fix_hint(config, repo)` 在第 283 行；`write_checked(repo, config)` 在第 421 行，校验不过抛 `ConfigError` 且一个字节都不写；`main(argv=None, repo=None)` 在第 729 行；`decisions` 子命令（第 713–715 行）接受 off、shadow、on、marker。`_check_decisions` 在调用时读取 `pd.DECISIONS_PLUGIN_DIR`（第 156、161 行）。
- `scripts/pi_dispatch.py`：`EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_BLOCKED, EXIT_DRIFT = 0, 1, 2, 3, 4`（第 57 行）；`is_within(path, root)`（第 558 行）；模块属性 `KIT_ROOT`（第 3672 行）与 `DECISIONS_PLUGIN_DIR`（第 3673 行）；`is_link_or_junction(path)`（第 5203 行）；`first_link_component(root, rel)`（第 5227 行）。
- `scripts/codekit/plugins.py`：`PLUGIN_ID`（第 19 行）；`PluginError`（`ValueError` 子类，第 30–32 行，属性 `code` 与 `path`）；`_fail`（第 36 行）；`resource_ref`（第 129 行）；`validate_manifest`（第 173 行）；`build_lock`（第 288 行）；`validate_lock(lock, manifests)`（第 307 行），其中 lock_sha256 不符抛 E_PLUGIN_LOCK_DRIFT（第 360 行），锁与 manifest 字节绑定不符或插件集合不符抛 E_PLUGIN_LOCK_BINDING（第 363、367、371 行）；`check_permission_intersection`（第 377 行）。`resolve_plugins` 不用（设计 D6）。
- `scripts/codekit/decisions.py`：`PLUGIN_ID = "decisions"`（第 48 行）；`PERMISSION = "network-decisions"`（第 49 行）；`DecisionError(RuntimeError)`（第 74 行）；`verify_battery_lock(plugin_dir)`（第 312 行）；`settings_from_config(config, agent_dir, plugin_dir)`（第 452 行）。
- `plugins/` 下有 8 个插件目录：code-change、decisions、docs-change、docs-checks、mutation-review、python-checks、regression-tests、repo-analysis。
- `tests/test_kit_config.py`：把 `scripts/` 插入 sys.path 并用裸名导入的写法在第 22–26 行；`class PluginsKey`（第 282 行）用 `mock.patch.object(kit_config.pd, "KIT_ROOT", …)` 与 `DECISIONS_PLUGIN_DIR` 在临时插件副本上测试（第 359–360 行）；`class LinkHelpers`（第 381 行）测试链接检查。
- 格式与写法的来源（均已纳入基线）：`.agents/skills/plan-task/contract-template.md`、`.agents/skills/plan-task/contract-template.json`、`.agents/skills/plan-task/contract-guide.md`（第九节规定检查行、DoD 行的写法，以及 Markdown 与 JSON 的一致性）、`.agents/skills/plan-task/test-design.md`。
- 测试写法（有意偏离设计 §2.5）：AGENTS.md 只允许执行器使用测试框架自己管理的临时目录（例如 pytest 的 `tmp_path`），不允许用 `tempfile` 等方式另建目录。因此本合同的测试用 pytest 函数写法、`tmp_path` 与 `pytest.skip`，不用 unittest 类与 `skipTest`，也不用 `tempfile`。设计 §2.5 描述的是现状的 unittest 写法；这里的偏离已由用户决定接受。

## Scope
- allowed_modified_files: 无
- allowed_new_files:
  - drafts/kit-plugins/contract.md
  - drafts/kit-plugins/contract.json
  - tests/test_kit_plugins_oracle.py
  - scripts/kit_plugins.py
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
- 正常输入：
  - 合同草稿：`drafts/kit-plugins/contract.md` 与 `contract.json` 是实现任务 `kit-plugins` 的正式合同草稿，内容符合下面“内层合同的要求”。
  - oracle：`tests/test_kit_plugins_oracle.py` 对 §9 的 P1–P17 逐条写用例。用例函数名以 `test_p01_` 至 `test_p17_` 开头，一个编号可以有多个用例。断言只针对：退出码、本合同写明的固定词（见“内层合同的要求”第 6 项）、插件 ID、文件字节，以及“被拒绝的路径从未被读取”。写法要求如下：
    - 只用合成夹具。每个用例把仓库的 `plugins/` 复制到 `tmp_path` 下，只修改副本，用 `mock.patch.object(pi_dispatch, "KIT_ROOT", …)` 与 `mock.patch.object(pi_dispatch, "DECISIONS_PLUGIN_DIR", …)` 替换；绝不修改仓库里真实的 `plugins/`（测试模块前后比较其文件快照）。
    - 用 pytest 函数写法，不用 unittest 类，以便使用 `tmp_path`。这与设计 §2.5 的 unittest 约定不同，已由用户决定接受（见 Repository facts）。
    - Windows 上用 `cmd /c mklink /J` 建 junction，目标只能在 `tmp_path` 之内；建不了时用 `pytest.skip` 跳过，并在执行报告里写明跳过数与原因。其他平台用符号链接。
    - P5：用读取替身（包装 `open`、`pathlib.Path.read_bytes`、`pathlib.Path.read_text`）断言被拒绝的路径从未被读取；并用替身断言检查失败后没有调用 `codekit.decisions.verify_battery_lock`。
    - 文件名与键名（manifest.json、lock.json、dispatch.config.json、questions、enabled、allowed_permissions）写字面量，不从被测模块导入。
    - 需要合成清单或锁时，用 codekit 的公开函数（`validate_manifest`、`build_lock`）生成一致的内容，不手写哈希。
    - 导入：把 `scripts/` 插入 `sys.path`，用裸名导入（`import pi_dispatch`、`import kit_config`、`import kit_plugins`），不用 `scripts.xxx` 形式；两种导入会得到两个模块对象，补丁只打到一个上。补丁统一打在 `kit_config.pd` 上（与 `PluginsKey` 第 359 行相同），并断言一次 `kit_plugins.pd is kit_config.pd`。
  - 参考实现：`scripts/kit_plugins.py` 实现 §4.2、D5、D6、D10、D11，使 oracle 全部通过。
- 用户决定（已接受，合同写死。内层合同逐条重述，不得改动；合同端若认为不合适，只能写进 contract_conflicts，不得改动实现）：
  - G1 不在 Git 仓库里运行任何子命令（list、show、verify、enable、disable）：用法错误，退出码 2。
  - G2 enable 或 disable 的插件 ID 在 `KIT_ROOT/plugins/` 下没有目录：用法错误，退出码 2。show、verify 的 ID 不存在同为 2（§4.2 已写）。
  - G3 verify（不论是否指定 ID）把“本轮不支持”的插件计为问题，退出码 1；list 照常列出，锁列显示“本轮不支持”。
  - G4 `--dry-run` 与真正写入走同一套校验（整份校验与决策题库核对）：校验失败时 dry-run 同样退出码 1 并打印原因；校验通过时 dry-run 退出码 0，不写文件。
  - 锁状态（list、show、verify 的“锁”列）按下列顺序判定：
    1. 目录链接检查（D5）失败：记为“无效”，原因写字面串“无效：链接”，停止该插件的后续读取。
    2. 读取并严格解析 manifest.json 与 lock.json（`codekit.protocols.strict_json_loads`，重复键即失败）；读不出或解析失败：无效。
    3. 目录名与 manifest 的 plugin_id 不符，或 validate_manifest 失败：无效。
    4. manifest 的 depends_on 或 conflicts 非空：本轮不支持（不调用 validate_lock）。
    5. 调用 `validate_lock(lock, {plugin_id: manifest})`：通过为“一致”；抛 PluginError 且 `code` 为 E_PLUGIN_LOCK_DRIFT（lock_sha256 不符）或 E_PLUGIN_LOCK_BINDING（锁与 manifest 字节绑定不符、插件集合不符）为“漂移”；抛其余错误为“无效”。
    - 资源文件哈希另列一列（一致 / 不一致），不改变锁列。validate_lock 不对资源求哈希，哈希由 kit_plugins 自己核对。
    - 决策插件的题库核对（`verify_battery_lock` 抛出的 DecisionError）并入该插件的问题清单，verify 退出码 1，不改变锁列。
  - 题库不一致时的恢复顺序（D6）：enable 或 disable 因决策插件生效、题库不一致被拒绝时，输出中给出恢复顺序，并含字面命令 `plugins disable decisions` 与 `config decisions off`。这段文字由 kit_plugins 自己输出，它不是 kit_config 的配置候选，不属于 plugins_fix_hint 的范围。
- 允许合同端自行决定的取舍（限于设计 §4.2、D5、D6 的范围；每一项写进执行报告的 interpretations，写明合同原文、采用的做法与理由）：
  - T1 `--json` 的键名与结构。oracle 只断言输出可解析为 JSON 对象，不断言键名。
  - T2 文字输出的格式、列宽与提示语措辞。oracle 只断言本合同写明的固定词、插件 ID、退出码与文件字节。
  - T3 授予权限时受影响插件清单的排序与格式（§4.2 要求列出）。
  - T4 写入失败（OSError）时的提示文字自定；退出码记为 1（沿用 §4.2 的“被拒绝 1”）。
- 错误与重试：合同、设计或仓库事实互相冲突，或 Repository facts 里的函数不存在、签名不同时，停止，写进 contract_conflicts，不自行选定一种解释当作完成。
- 并发、取消与状态变化：不适用（单进程本地命令，不写后台状态）。
- 兼容性：不修改任何既有文件；`kit_plugins` 是新模块，不接入调度器。
- 内层合同的要求（写进 `drafts/kit-plugins/contract.md` 与 `.json`）：
  1. Identity：`plan_version` 1；`repository` ThemisTally；`base_sha` 用全零占位 `0000000000000000000000000000000000000000`，发布时由审核端替换为 oracle 基线提交；`risk_level` medium；`authorized_actions` local_edit, local_test；`integration_actions` local_branch, merge；`executor` bb/step-5-preview · thinking high。
  2. JSON 字段：`task_id` kit-plugins；`plan_version` 1；`authorization.executor` [local_edit, local_test]；`authorization.integration` [local_branch, merge]；`executor` 为 {provider bb, model step-5-preview, thinking high, tools 用模板缺省, context_files project}；`budget` 为 2 次、单轮 1800 秒、合计 3600 秒、`cost_budget` null。不写 `contract_family` 与 `execution_profile`。另加 `outline_ref`（kind execution-outline，id ol-kit-plugins，path `.agent/requests/r1-kit-plugins/outline.r1.json`，sha256 e2885dd535bca98b04d0582bca398790942056acffbd67a2fcfb028732fda728）、`coverage`（列出 S1–S8 各落到哪些 scope、DoD 与检查）与 `deviations`（没有偏离时为空数组）。这三个新增字段不参与 validate 校验，只供审核。
  3. Scope：`allowed_modified_files` 为空；`allowed_new_files` 恰为 `scripts/kit_plugins.py` 与 `tests/test_kit_plugins.py`；`forbidden_paths` 必须包含 `tests/test_kit_plugins_oracle.py`，并包含本合同 Scope 中列出的其他禁止路径，且不得与允许集合重叠。
  4. 检查：V01 `python -m pytest tests/test_kit_plugins_oracle.py -q`，输出须匹配 `[1-9]\d* passed`；V02 `python -m pytest tests/test_kit_plugins.py -q`，输出须匹配 `[1-9]\d* passed`；V03 `python -m py_compile scripts/kit_plugins.py`；V04 `python scripts/kit_plugins.py --help`，输出须匹配 `usage:`。V01 至 V04 全部为 required。每个检查都写具体文件名，不得运行整个 `tests` 目录（本机 Python 环境里有第三方 `tests` 包会遮住仓库的 tests/）。
  5. DoD：覆盖 list、show、verify，enable、disable，写入与拒绝，退出码与错误输出，链接检查复用，范围与不改既有测试；另有两条分别引用 V03（可编译）与 V04（命令行可运行）。每条写证据，每个检查至少被一条 DoD 引用。
  6. Behavior contract：以设计 §4.2、D5、D6、D10、D11 为准，并逐字写出 oracle 会断言的每一个固定词：状态词“一致”“漂移”“无效”“本轮不支持”“不一致”“READY”“BLOCKED”“是”“否”“不限制”“off”；字面串“无效：链接”“CRLF”“修复：”“plugins disable decisions”“config decisions off”；退出码的含义；文件名 manifest.json、lock.json、dispatch.config.json、questions；键名 enabled、allowed_permissions。oracle 不得断言合同没有写明的词。另外写明：`kit_plugins` 在调用时读取 `pd.KIT_ROOT` 与 `pd.DECISIONS_PLUGIN_DIR`，不把它们复制进模块常量；调用 codekit 时通过模块属性（如 `decisions.verify_battery_lock`），不从模块 from-import 这些名字；导入 `pi_dispatch`、`kit_config`、`codekit` 的写法与 `kit_config.py` 第 40–52 行相同；模块暴露 `pd`，使 `kit_plugins.pd is kit_config.pd`。
  7. 测试约定（写进内层 Behavior contract，执行端自己的测试也遵守）：pytest 函数写法；临时目录只用 `tmp_path`，不用 `tempfile` 与 `mkdtemp`；用 `pytest.skip` 代替 `skipTest`；插件树从仓库 `plugins/` 复制到 `tmp_path` 后只改副本；junction 与符号链接的目标只能在 `tmp_path` 之内；不得修改仓库里的真实 `plugins/`；文件名与键名写字面量。
  8. 内层合同不得提及参考实现、草稿 worktree 或起草过程。
  9. 设计与用户决定的固定行为：设计 §4.2、D5、D6、D10、D11 写明的命令、退出码与语义照写，不得改动。上面“用户决定”中的 G1–G4、锁状态判定与题库恢复顺序照写进内层 Behavior contract，逐条重述，不得改动。D11 的共用规则逐条重述：写配置只经 `kit_config.write_checked`，不得直接写文件；修复提示只来自 `kit_config.plugins_fix_hint`，不得自己拼（题库恢复顺序除外）；链接与边界检查只用 `pi_dispatch.is_link_or_junction`、`pi_dispatch.first_link_component` 与 `pi_dispatch.is_within`，不得另写同类实现。
  10. 格式与占位：内层 Markdown 与 JSON 按 `.agents/skills/plan-task/contract-template.md`、`contract-template.json` 与 `contract-guide.md` 第九节书写，检查行与 DoD 行的写法保证审核端可以校验。两份内层文件里不得残留模板的填写标记（方括号包住的说明性字样），也不得残留模板里的大写替换标记；全零的 `base_sha` 是唯一允许的占位。

## Steps
1. 核实 Repository facts 中的每一项（读文件与符号），与基线不符就停止并报告。
2. 读设计：`docs/themis-tally-3.0-r1-日志与插件管理.md` 的 §2.3、§2.4、§3（D1、D5、D6、D7、D10、D11）、§4.2、§4.3、§9 的 P 组；上位设计 `docs/themis-tally-3.0-四端分层解耦架构.md` 的 §6.7、§6.8。
3. 写 oracle `tests/test_kit_plugins_oracle.py`，覆盖 §9 的 P1–P17。用例设计按 `.agents/skills/plan-task/test-design.md`：合法基线、唯一变化、精确的退出码或字节结果，不只断言“非零”。
4. 写参考实现 `scripts/kit_plugins.py`，直到 V01 全部通过。它只用来证明 oracle 有效，报告里说明它不发布。
5. 写 `drafts/kit-plugins/contract.md` 与 `contract.json`，按“内层合同的要求”第 1–10 项。
6. 运行外层检查 V01–V03，写执行报告。

概要步骤（ExecutionOutline 原文，修订 1，`.agent/requests/r1-kit-plugins/outline.r1.json`，文件字节的 sha256 为 e2885dd535bca98b04d0582bca398790942056acffbd67a2fcfb028732fda728）。内层合同要覆盖这些步骤，覆盖结果写进 coverage。开放问题 Q1–Q3 的默认与 G1–G3 一致，已由用户决定；Q4 中的锁状态映射已由用户决定（见上文“锁状态”），--json 键名属于 T1：
- S1｜枚举插件；每次读取清单、锁、资源或题库前从 KIT_ROOT 逐级检查链接与 junction，失败即停止后续读取｜范围 kit_plugins｜验收意图：被拒绝的路径从未被读取｜风险 medium｜坑：DecisionError 是 RuntimeError 子类｜依赖：无
- S2｜list、show、verify 只读：锁与资源状态、缺的权限、READY 或 BLOCKED、未安装的启用 ID；坏插件不拖垮命令｜范围 kit_plugins｜验收意图：状态词与退出码按 4.2 固定｜风险 low｜依赖：S1
- S3｜配置经 load_config 读取；列表类子键非列表则拒绝并给修复提示；写入只经 write_checked｜范围 kit_plugins｜验收意图：校验不过时配置字节不变｜风险 medium｜依赖：S1
- S4｜enable：X 的清单、锁、资源与题库须一致；enabled 缺省时不改；列表时加入 X；--allow-permission 不多不少｜范围 kit_plugins｜验收意图：enable 不写出只含 X 的列表｜风险 medium｜坑：depends_on 或 conflicts 非空一律拒绝｜依赖：S1、S3
- S5｜disable：enabled 缺省时写成全部插件减 X 的显式列表并提示；不碰 allowed_permissions；关 decisions 时提示变 off｜范围 kit_plugins｜验收意图：其他坏插件不挡住关闭｜风险 medium｜依赖：S3
- S6｜逐插件收集 ValueError、DecisionError、OSError；命令级错误打印一行 ERROR 并返回退出码，不输出堆栈；--dry-run 不落盘｜范围 kit_plugins｜验收意图：写入中途失败时配置字节不变｜风险 medium｜坑：漏掉 DecisionError 会冒出堆栈｜依赖：S2、S4、S5
- S7｜main(argv=None, repo=None) 返回整数；子命令 list、show、verify、enable、disable；--repo、--json；用法错误退出码 2｜范围 kit_plugins｜验收意图：--json 输出可解析为对象｜风险 low｜依赖：S2、S4、S5、S6
- S8｜执行端自己的测试：命令行解析、--json、--dry-run 不落盘；不替代 oracle｜范围 tests/test_kit_plugins.py｜验收意图：只用临时副本，不改真实插件目录｜风险 low｜依赖：S7

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态。不要把输出写到固定的 /tmp 路径。不要自己做变异检查，验收端会在固定候选上做。V01–V03 只跑具体文件，不跑整个 tests 目录（本机 python 环境里有第三方 tests 包会遮住仓库的 tests/）。

- V01（必要）：`python -m pytest tests/test_kit_plugins_oracle.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配 `[1-9]\d* passed`
- V02（必要）：`python -c "import json; d = json.load(open('drafts/kit-plugins/contract.json', encoding='utf-8')); missing = [k for k in ('task_id', 'scope', 'checks', 'definition_of_done') if k not in d]; assert not missing, missing; print('JSON_OK')"` · cwd：仓库根 · 超时：60s · 期望退出码：0 · 输出须匹配 `JSON_OK`
- V03（必要）：`python -m py_compile scripts/kit_plugins.py` · cwd：仓库根 · 超时：60s · 期望退出码：0

## Definition of done
- D01：三个交付物就位，合同草稿按模板并通过 JSON 必需键检查；证据：V02、scope；目的：草稿可以被审核端直接改写成正式合同。
- D02：oracle 覆盖 §9 的 P1–P17（能写的都写），在本机真正运行（执行报告写明跳过的用例数与原因，若有），只用合成副本，从不修改仓库里的真实 plugins/；证据：V01、review；目的：oracle 能区分正确实现与错误实现，而不是只能证明“能跑”。
- D03：参考实现让 oracle 全部通过，只调用既有公开函数（kit_config 与 pi_dispatch 中列出的函数，codekit 只调用公开函数），不另写同类实现；证据：V01、V03、review；目的：证明 oracle 在正确实现上可以通过（上位设计 4.7 第 2 步）。
- D04：所有修改都在允许集合内；证据：scope。
- D05：没有修改既有文件，没有删除、跳过或弱化既有测试；证据：review。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符，例如 `write_checked`、`first_link_component` 不存在或签名不同。
- 必须修改允许范围之外的文件才能继续。
- 需要安装依赖、联网、读取凭据或提升权限。
- 合同、设计或概要步骤之间互相冲突，且无法按设计解释。
- 达到单轮时限。

## Budget
- max_attempts_total: 2（按 task-id 汇总，包括返工版本）
- max_wall_seconds_per_attempt: 2700
- max_wall_seconds_total: 5400
- cost_budget: tracking-only（bb/step-5-preview 没有带来源的单价，费用记 unknown，只报 token）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：核实事实约 5 分钟；oracle 约 15 分钟；参考实现约 12 分钟；合同草稿约 5 分钟；运行检查与报告约 5 分钟；合计约 42 分钟，不超过单轮 2700 秒。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D05；列出自检命令与结果；列出 oracle 的用例数与跳过数（若有）及原因；遗留问题与阻塞原因；末尾附上执行说明规定的 JSON 代码块。
- interpretations 必须包含 T1–T4 的每一项，每条写合同原文、采用的做法与理由。
- “用户决定”中的 G1–G4、锁状态判定与题库恢复顺序是合同写死的，实现必须照做。若认为它们与设计或事实冲突，写进 contract_conflicts，不得改动实现。
- 自检结果是自述；最终是否通过由审核端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置，也不写入 `.agent/` 下任何文件。
- 不删除、跳过或弱化既有测试来获得通过。
- 不提交（authorized_actions 没有 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不用 tempfile 或 mkdtemp 另建目录；测试临时目录只用 pytest 的 tmp_path。
