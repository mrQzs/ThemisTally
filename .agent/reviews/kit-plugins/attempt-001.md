# REVIEW：kit-plugins v1 · attempt-001

Verdict: REVISE

<!-- review-draft 生成（2026-10-17T13:50:19Z，调度工具 2.10.0）：事实取自 .agent/runs/kit-plugins/attempt-001；标着“待填”的地方是复审判断，全部填完 verdict 才收。
     Verdict 行只能写一个结论，并与 verdict 命令的 --verdict 一致。 -->

## 基本信息
- 基线：`db228add2e1ed72dab694454e0d3fd403d4237ca`
- 候选树：`41b94300ee0ae6eb0b4bfecb7db37568ff5582d7`（补丁往返校验通过；1 file changed, 692 insertions(+)）
- 要求的执行模型：bb/step-5-preview · thinking high
- 实际模型：bb/step-5-preview；providerThinkingLevel：未回报
- 运行：退出码 3221225786 · 用时 2700.031 s / 上限 2700 s · 超时 · 工具错误 1
- token：输入 360767 · 输出 167743 · 缓存读 2619136 · 缓存写 0；费用 unknown（unknown）
- 复审者：Claude Code 规划端会话（Opus 5.5）；独立复审：pi-reviewer 子代理（`claude-opus-5-5`，只读）。规划端用探针复现了独立复审标为“推理”的 H2、H3、H4。

## 门禁

| 门禁 | 结果 | 说明 |
|---|---|---|
| G0 输入一致 | passed | 工具：通过 |
| G1 执行完整 | failed | 工具：不通过；运行超时；Pi 退出码为 3221225786；没有 agent_settled：该 pi 版本应以它结束，事件流可能被截断或运行被中断；最终 assistant stopReason=toolUse；提供商未回报思考级别：只能确认请求的级别（high）；执行报告状态：missing |
| G2 范围合规 | passed | 工具：通过 |
| G3 行为正确 | 未通过 | 工具：不通过（V01 53/54：授予路径静默跳过链接插件目录）；复审另有 oracle 测不出的偏差：锁列出现第五个值“无效：链接”（合同第 88 与 95 行自相矛盾）、资源读取失败时锁列仍“一致”、“未安装”排除了链接目录、状态判定没有用设计 D5 要求的 `check_permission_intersection`、show 在锁不一致时不输出 generation、没有变化摘要（合同第 70 行）；三条会冒出堆栈的路径（H2 题库读不出、H3 plugins 不是对象、M5 列表元素不可哈希）与一条给出执行不了的修复提示（H4） |
| G4 回归检查 | failed | 工具：不通过；检查记录：checks/01（fresh，2/4 通过）；必要检查 V01：failed；必要检查 V02：failed；检查在干净副本（基线 + 候选补丁 + setup）上运行 |
| G5 质量复审 | 未通过 | 执行端自己的测试没有写出（V02 失败）；没有执行报告（超时） |
| G6 可集成 | passed | 工具：通过 |

## DoD 映射

| DoD | 结果 | 证据 | 说明 |
|---|---|---|---|
| D01 | 未满足（锁列取值、资源读取失败、未安装、状态判定、show 的锁信息） | V01 failed | list、show、verify 只读命令按 §4.2 输出状态词（一致/漂移/无效/本轮不支持/不一致、READY/BLOCKED、是/否/不限制）与退出码（0/1/2），坏插件不拖垮命令 |
| D02 | 未满足（B2 链接目录、H3、H4、变化摘要） | V01 failed | enable、disable 按 D6 改变 plugins.enabled 与 plugins.allowed_permissions，含 --dry-run、--allow-permission 与非列表值拒绝，授予路径对其他插件 manifest 的读前链接检查 |
| D03 | 部分满足（写入只经 write_checked；但 H2、H3、M5 可冒堆栈） | V01 failed | 写入只经 kit_config.write_checked，校验不过或写入失败时配置字节不变；命令级错误打印一行 ERROR 并返回退出码，不输出堆栈 |
| D04 | 部分满足（只用 pd 的公开函数；文件链接变体在本机 skip） | V01 failed、复审 | 读前逐级链接与边界检查只用 pi_dispatch.is_link_or_junction、first_link_component 与 is_within，不另写同类实现 |
| D05 | 满足（只新增 scripts/kit_plugins.py，越界 0） | scope（越界 0） | 所有修改都在允许集合内 |
| D06 | 未满足（没有 tests/test_kit_plugins.py） | 复审、V02 failed | 没有删除、跳过或弱化既有测试，执行端自己的测试只用合成副本、不改真实 plugins/ |
| D07 | 满足 | V03 passed | scripts/kit_plugins.py 可编译 |
| D08 | 满足 | V04 passed | 命令行可运行，--help 输出 usage: |
| D09 | 部分满足（verify 先读配置再校验 ID；悬空链接） | V01 failed | 插件 ID 先按 PLUGIN_ID 校验，枚举与存在性规则（含 plugins 根是链接时枚举为空、链接目录也列出），G1、G2 |
| D10 | 部分满足（无变化路径的题库异常；show 的 generation） | V01 failed | 题库阶段收集 OSError 与 ValueError；show 输出 generation 与逐资源核对；allowed_permissions 去重排序；disable 的显式列表排除链接目录；不提供 --version |

## 范围与质量
- 越界与警告：越界 0、警告 0
- 测试可信度：oracle 54 项（4 个文件链接变体 skip），候选 53 过；没有执行端测试。规划端变异 22 个抓住 18：M10、M20 为等价变异，M05、M14 是 oracle 缺口（规划审核端在 v2 前补测）。
- 变异检查：
  - mutations/01：22 条
    - 抓住 18，漏掉 4（意外 4：M05 M10 M14 M20），跳过 0，出错 0
    - `M05 K05 enabled 缺省显示为“是”` → 归因：合同遗漏（oracle 没有断言 list 在不限制时的启用列） → 处理：规划端补测（v2 基线的 oracle 增补）
    - `M10 K10 不校验插件 ID 格式` → 归因：等价变异（`_require_exists` 只认枚举里按 PLUGIN_ID 过滤的名字，不合法的 ID 同样退出 2 并打一行 ERROR） → 处理：注明
    - `M14 K14 verify --json 恒为 0` → 归因：合同遗漏（oracle 没有测 `verify --json` 在有问题时的退出码） → 处理：规划端补测（v2 基线的 oracle 增补）
    - `M20 K20 题库文件不查链接` → 归因：等价变异（第 203 行再判一次链接，中间各级目录第 188 行已查） → 处理：注明；文件级链接改用替身补测（本机建不了文件符号链接，4 个变体 skip）
- 兼容性与残余风险：只新增模块，不接入调度器；H2 的根因在 `decisions.verify_battery_lock`（读不出的清单冒 OSError，调用方都只捕获 DecisionError），规划端已在 `ca59fd9` 修正并公开 `kit_config.plugins_section_error` 供 v2 使用。
- 执行器自述与证据是否一致：超时，没有执行报告；事件流 57 次工具调用，其间有几段数万行事件的连续思考，模块在第 56088 行（共 56665 行）一次写出；事件流第 23230、53821 行的解读线索（状态判定、链接目录算不算存在、恢复顺序放哪）都没有报告。
  - 执行报告：missing（executor_status None）
  - 合同矛盾：无
  - 自定解读：无
  - 限制与取舍：无
  - 未决问题：无
  - 事件流里的解读线索：无
- 摘要里的“复审需要关注”（原文）：
  - 新增被 Git 忽略的路径：`.pytest_cache/`
  - 新增被 Git 忽略的路径：`.pytest_cache/.gitignore`
  - 新增被 Git 忽略的路径：`.pytest_cache/CACHEDIR.TAG`
  - 新增被 Git 忽略的路径：`.pytest_cache/README.md`
  - 新增被 Git 忽略的路径：`.pytest_cache/v/`
  - 新增被 Git 忽略的路径：`scripts/__pycache__/`
  - 测试或检查命令的退出码被管道掩盖（2 条，例如事件流第 56201 行 `cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" && python -m pytest tests/test_kit_plugins_oracle.py -q 2>&1 | tail -40`；另有 5 条探索命令也如此）：执行器没有看到被检查程序的退出码，报告里的 reported_exit_code 是推断值，以 check 的结果为准（2.10.0 起执行说明给了每条检查的自检照抄写法）
  - 执行过程中有 5 处提到合同的歧义、矛盾或一致性，可能只是在检查，需要核实（例如事件流第 23230 行：“Reasons for BLOCKED: - Missing permissions (权限不足). - Lock not consistent (漂移/无效/本轮不支持)? - Resource inconsistent? Let me re-read the contract for list: "状态（READY”）；报告的 interpretations、contract_conflicts 与 unresolved_questions 都为空：核对执行器是否自行选定了某种解释（全部摘录见 events-summary.json 的 ambiguity_mentions）

## 结论理由
跑满 2700 秒超时（TIMEOUT）：候选只有实现，没有执行端测试与执行报告；实现大体可用（oracle 53/54、变异 18/22，漏掉的两个是 oracle 缺口、两个是等价变异），但有一处 oracle 抓到的 B2 缺口、六处 oracle 测不出的合同或设计偏差、三条可冒堆栈的路径与一条执行不了的修复提示。合同本身在锁列的取值上前后不一致（第 88 与 95 行），属规划问题，v2 写死裁定。分类 TIMEOUT。在本候选上继续（v2，最后一次，2700 秒）；规划端先补共用代码（ca59fd9），规划审核端补 oracle 与 v2 合同。

## 后续动作
- 需要修正的具体差异（REVISE）：v2 按以下顺序（先写最小的执行端测试，防止再次超时没有测试）：
  0. 先写最小的 `tests/test_kit_plugins.py`（至少 1 个用例能通过），再改实现。
  1. B2：授予路径对链接插件目录输出问题行（含该 ID 与 `无效：链接`），不计入受影响清单。
  2. 锁列只取四值：读前检查失败时锁列“无效”，原因或问题文字含 `无效：链接`（list 的原因、verify/show 的问题行、JSON 的字符串值）；plugins 根是链接时 JSON 也含 `无效：链接`。
  3. 资源读取失败：锁列“无效”、资源列“不一致”、问题含新固定词“资源读取失败”。
  4. 先查原配置：读配置后调用 `kit_config.plugins_section_error(config)`，不为 None 时 stderr 一行 `ERROR: <错误>；修复：<kit_config.plugins_fix_hint(config, repo)>`（提示为 None 不附），退出 1，不写；五个子命令都如此。
  5. 无变化路径与写入走同一条路：题库门禁（收集 ValueError、OSError、DecisionError，附恢复顺序）→ 整份校验，不冒堆栈。
  6. 状态与缺的权限用 `plugins.check_permission_intersection(manifest, allowed_permissions=<列表>, platform_name=None)`（设计 D5）；allowed_permissions 不限制时不调用、缺的权限为空；READY 当且仅当锁一致、资源一致、权限 READY。
  7. “未安装”= enabled 里不在枚举结果（含链接目录）中的 ID。
  8. show：lock.json 通过读前检查且解析成对象时，就输出 generation 与 lock_sha256 的原值。
  9. 检查顺序：G1 → ID 格式 → ID 存在 → 读配置 → plugins 段检查 → …；verify 也先校验 ID。
  10. 变化摘要：dry-run 与真写入都输出每个变化子键一行 `plugins.<键>: <旧> → <新>`；受影响清单只在成功时输出；“没有变化”只说一次；decisions 本不在列表里时不提示变为 off。
  11. plugins 根与插件目录先用 `pd.is_link_or_junction` 判断，悬空链接也算链接。
  12. 逐插件核对（含授予路径读其他插件）整体收集 ValueError、OSError、DecisionError，记“无效”加原因。
  13. verify 的标题行在资源不一致时不打印“一致”。
  14. 执行报告（interpretations、contract_conflicts）。
  接受现状、写进合同的：缺失文件的归类保持现状；资源边界用前缀判断（resource_ref 已拒绝 `..` 与绝对路径）；“因此满足权限条件”= 补上后不再缺任何权限，重复的 `--allow-permission` 按集合处理；argparse 自身的错误只要求退出 2、不冒堆栈。
- 待决的业务或环境问题（BLOCKED / ESCALATE）：无
- 已授权且可以继续的集成动作：本 attempt 不集成（REVISE）；`branch --rework` 作 v2 的基线，挑到 themis-3.0 上（在 ca59fd9 之后），再加规划审核端的 oracle 增补。
- 人工介入：0（复审由规划端会话与子代理完成，用户未介入）
