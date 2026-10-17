# REVIEW：kit-plugins v2 · attempt-002

Verdict: REVISE

<!-- review-draft 生成（2026-10-17T15:09:31Z，调度工具 2.10.0）：事实取自 .agent/runs/kit-plugins/attempt-002；标着“待填”的地方是复审判断，全部填完 verdict 才收。
     Verdict 行只能写一个结论，并与 verdict 命令的 --verdict 一致。 -->

## 基本信息
- 基线：`355d94389eef46e449149b75095b5d0bccc447cc`
- 候选树：`934e12fe1854fd0c62b6abc7b7afe9bbcaa00d51`（补丁往返校验通过；2 files changed, 515 insertions(+), 142 deletions(-)）
- 要求的执行模型：bb/step-5-preview · thinking high
- 实际模型：bb/step-5-preview；providerThinkingLevel：未回报
- 运行：退出码 0 · 用时 1718.812 s / 上限 2700 s · 正常结束 · 工具错误 3
- token：输入 236666 · 输出 109075 · 缓存读 4261376 · 缓存写 0；费用 unknown（unknown）
- 复审者：Claude Code 规划端会话（Opus 5.5）；独立复审：pi-reviewer 子代理（`claude-opus-5-5`，只读，静态核对）。

## 门禁

| 门禁 | 结果 | 说明 |
|---|---|---|
| G0 输入一致 | passed | 工具：通过 |
| G1 执行完整 | passed | 工具：通过；提供商未回报思考级别：只能确认请求的级别（high） |
| G2 范围合规 | passed | 工具：通过 |
| G3 行为正确 | 未通过（复审） | 工具：通过；第 1、4–7、9–13 项落实，变异 25 个抓住 24。合同明文要求而 oracle 没有把守的输出缺口：show 不输出“问题：”行、正常路径不打印问题（F1）；list 的原因对清单、资源、题库的链接类失败不含 `无效：链接`（F2，执行器在事件流第 32633 行自定、未报告）；plugins 根是链接时 JSON 没有 `无效：链接 plugins`（F3）；show 的早退路径不输出锁信息、状态行格式不符（F4）；权限核对出错按满足放行（F5） |
| G4 回归检查 | passed | 工具：通过；检查记录：checks/01（fresh，4/4 通过）；检查在干净副本（基线 + 候选补丁 + setup）上运行 |
| G5 质量复审 | 通过（附规划端补测） | 执行端测试 8 项只用合成副本、覆盖第 1–5 项；`test_d11_04` 对 list/show/verify 没有断言“修复：”（偏弱）。M19（逐插件兜底）没有 oracle 用例 |
| G6 可集成 | passed | 工具：通过 |

## DoD 映射

| DoD | 结果 | 证据 | 说明 |
|---|---|---|---|
| D01 | 部分满足（F1–F4） | V01 passed | list、show、verify 按第二节与第八节输出锁列四值（一致/漂移/无效/本轮不支持）、资源列、状态词（READY/BLOCKED、是/否/不限制）与退出码，坏插件不拖垮命令 |
| D02 | 满足 | V01 passed | enable、disable 按第十节改变 plugins.enabled 与 plugins.allowed_permissions，含 --dry-run、--allow-permission 与非列表值拒绝，授予路径的读前链接检查 |
| D03 | 满足（写入只经 write_checked；无新的堆栈路径） | V01 passed | 写入只经 kit_config.write_checked，校验不过或写入失败时配置字节不变；命令级错误打印一行 ERROR 并返回退出码，不输出堆栈 |
| D04 | 满足（只用 pd 的公开函数；资源越界改用 is_within） | V01 passed、复审 | 读前逐级链接与边界检查只用 pi_dispatch 的 is_link_or_junction、first_link_component、is_within，不另写同类实现 |
| D05 | 满足（越界 0） | scope（越界 0） | 所有修改都在允许集合内（scripts/kit_plugins.py 修改，tests/test_kit_plugins.py 新增） |
| D06 | 满足（没有删除或弱化测试） | 复审、V02 passed | 没有删除、跳过或弱化既有测试（含 oracle），执行端自己的测试只用合成副本、不改真实 plugins/ |
| D07 | 满足 | V03 passed | scripts/kit_plugins.py 可编译 |
| D08 | 满足 | V04 passed | 命令行可运行，--help 输出 usage: |
| D09 | 满足 | V01 passed | 插件 ID 先按 PLUGIN_ID 校验（B3），枚举与存在性（链接目录列出，悬空链接算链接，plugins 根是链接时枚举为空），G1、G2，检查顺序 |
| D10 | 满足 | V01 passed | 题库门禁（无变化路径与写入共用）、show 的 generation 与 lock_sha256 原值、变化摘要、allowed_permissions 去重排序、disable 的显式列表排除链接目录、不提供 --version |
| D11 | 满足（test_d11_04 偏弱） | V02 passed | 执行端测试 tests/test_kit_plugins.py 覆盖 review 第 1–5 项（授予路径的链接目录问题行、锁列四值、资源读取失败、plugins 段不合法的五个子命令、无变化路径的题库门禁） |
| D12 | 部分满足（F1、F4 是第 8 项 show 的格式部分） | V01 passed | review 第 6–13 项的实现（权限状态与调用条件、未安装口径、show、检查顺序、变化摘要、逐插件收集、verify 标题、悬空链接）由 V01 的增补用例覆盖 |

## 范围与质量
- 越界与警告：越界 0、警告 0
- 测试可信度：oracle 102 passed、4 skipped（文件符号链接变体），执行端 8 项；变异 25 个：all 抓住 24（M19 漏掉），executor 抓住 7（M03 意外漏掉——执行端测试只覆盖插件目录链接，资源链接由 oracle 抓住，属规划端的预期写错）。
- 变异检查：
  - mutations/01：25 条，命令 all、executor
    - all：抓住 24，漏掉 1（意外 1：M19），跳过 0，出错 0
    - executor：抓住 7，漏掉 18（意外 1：M03），跳过 0，出错 0
    - `M03 N03 资源链接时锁列写成 无效：链接`（executor 意外漏掉） → 归因：执行器少写（执行端测试只测了插件目录链接；oracle 抓住） → 处理：注明
    - `M19 N19 逐插件兜底不收集异常`（all 意外漏掉） → 归因：合同遗漏（没有用例让 `_check_plugin` 内部抛出；Python 3.10 的 `Path.is_file()` 遇 EACCES 会抛 PermissionError，路径真实存在） → 处理：规划端补测（补齐提交）
    - 预期内的漏掉（expect_missed：合同交给其他命令覆盖的规则）：M09 M10 M11 M12 M13 M14 M15 M16 M17 M18 M20 M21 M22 M23 M24 M25 → 处理：注明
- 兼容性与残余风险：只改 `scripts/kit_plugins.py` 与执行端测试；v1 已正确的行为（G1–G4、B2、B3、D6、只经 write_checked 写入）保持。残余：`_enumerate_entries` 的 `child.is_dir()` 遇 EACCES 理论上可抛（不在逐插件包裹内，Windows 上基本到不了）；授予路径不比对其他插件的 plugin_id 与目录名（不符时按目录名计入受影响清单）。
- 执行器自述与证据是否一致：检查结果与 fresh 一致；3 条 interpretations 都在合同范围内，但 list 原因只写锁列词（F2）这一自定解读没有报告；过程偏差：事件流第 31536、31719 行两条临时目录命令先 `cd "$T"` 再运行、手写了 worktree 绝对路径，用途是排查与任务无关的 test_kit_config 失败（扩大到无关测试）；都以 `rm -rf "$T"` 收尾，没有留下文件。
  - 执行报告：json_ok（executor_status completed）
  - 合同矛盾：无
  - 自定解读（3，原文）：
    - {"quote": "第十三节：disable decisions …之前是生效的", "adopted": "“生效”= 在 enabled 集合中（不限制即算启用），非决策模式 active", "reason": "oracle test_p16a 要求 mode off 但在 enabled 中仍输出 off 提示"}
    - {"quote": "第八节表第 13 行与第 18 行组合", "adopted": "资源读取失败（锁无效）后又遇题库内容不符时保留锁“无效”", "reason": "表未覆盖该组合，取更保守读法，无对应测试"}
    - {"quote": "第九节：缺的权限与权限状态来自 check_permission_intersection", "adopted": "allowed 为列表时对每个 manifest 合法插件都调用，紧随 manifest 校验后", "reason": "满足 test_v2_12a/b 的调用条件，权限状态仅在锁、资源都一致时影响 READY/BLOCKED"}
  - 限制与取舍（2，原文）：
    - 本机 4 个 oracle 文件符号链接用例 skip（无创建文件符号链接权限），环境相关，非实现缺陷
    - tests/test_kit_config.py 的 test_init_show_set_unset_validate 在本机因决策 API key 环境变量命中 secret.source=env 而失败，先于本次改动存在、与 kit_plugins 无关，不在 V01–V04 内
  - 未决问题：无
  - 事件流里的解读线索（逐条核对是否都在上面的自定解读、合同矛盾或未决问题里）：
    - 第 17403 行（thinking）：t). So the decision plugin is NOT active (mode off). But the test expects "决策插件会因此变为 off"! Hmm. So my interpretation of "生效" (active) must be wrong, OR the off message condition is different. Let me re-read section 13: "disable decisions 时，只有决策插件由生效变为不生效（
    - 第 25239 行（thinking）：ure). Since the combination isn't specified, and my choice (keep the more severe 无效) is reasonable, I'll note it as an interpretation if needed. Actually, it's such an edge case that I'll just handle it and mention in interpretations if relevant. Let me not ov
    - 第 32696 行（thinking）：decisions 不再在 enabled 中，且之前是生效的" — "生效的" here, combined with "不再在 enabled 中", reads as membership), I'll treat it as an interpretation: "生效" = in the enabled set (unrestricted ⇒ enabled). Actually, re-reading section 13: "disable decisions 时，只有决策插件由生效变为不生效（即 d
- 摘要里的“复审需要关注”（原文）：
  - 可疑命令（递归或强制删除）：命令第 1 / 1 行 `…onfig.py" init >/dev/null 2>&1; python -c "import json;print(json.load(open('.agent/dispatch.config.json'))['allowed_executors'])"; cd - >/dev/null; rm -rf "$T"`（事件流第 31536 行）
  - 可疑命令（递归或强制删除）：命令第 1 / 1 行 `… -c "import json;print('allowed_executors=',json.load(open('.agent/dispatch.config.json',encoding='utf-8'))['allowed_executors'])"; cd - >/dev/null; rm -rf "$T"`（事件流第 31719 行）
  - 系统临时路径线索（2 个命中片段）：逐项按 AGENTS.md 核对写法、用途和工具结果。这些是事后扫描线索，不是命令阻断或违规裁定；清理输出或路径当前不存在，不能证明此前未覆盖既有内容
  - 临时路径：事件流第 31536 行，命令第 1 行 `…- what init produces for allowed_executors ---"; T=$(mktemp -d); cd "$T" && git init -q && mkdir -p .agent && python "<worktree>/scripts/kit_config.py" init >/d…`
  - 临时路径：事件流第 31719 行，命令第 1 行 `T=$(mktemp -d); cd "$T" && git init -q && mkdir -p .agent && python "<worktree>/scripts/kit_config.py" init >/dev/null 2>&1; python -c "import json;print('allow…`
  - 新增被 Git 忽略的路径：`.pytest_cache/`
  - 新增被 Git 忽略的路径：`.pytest_cache/.gitignore`
  - 新增被 Git 忽略的路径：`.pytest_cache/CACHEDIR.TAG`
  - 新增被 Git 忽略的路径：`.pytest_cache/README.md`
  - 新增被 Git 忽略的路径：`.pytest_cache/v/`
  - 新增被 Git 忽略的路径：`scripts/__pycache__/`

## 结论理由
最后一次返工把复审第 1–13 条的绝大部分落实：fresh 检查 4/4、oracle 102 项、变异 24/25，写入路径、题库门禁顺序、原配置检查、权限核对的调用条件、逐插件兜底都对，没有新的堆栈路径。剩下的是合同明文要求、oracle 没有把守的输出格式缺口（F1–F5），以及一个没有用例的兜底分支（M19）。分类 EXECUTION_ERROR。预算已用完（2/2），剩余部分小而明确：按 rework.md 第四节由规划端在返工提交上补齐，作为单独的提交，并按同样的标准验收（V01–V04、补测、补齐部分的变异检查、全量测试），之后 `mark SUPERSEDED`。

## 后续动作
- 需要修正的具体差异（REVISE）：由规划端补齐，不再派遣：
  - F1：show 两条路径都逐条输出 `问题：<问题>`（正常路径在状态行之后）。
  - F2：list 的原因在锁列不是“一致”时写成 `<锁列值>：<首条问题>`，链接类失败因此含 `无效：链接`，“漂移”“本轮不支持”照旧可见。
  - F3：plugins 根是链接时，list --json 与 verify --json 加一个含 `无效：链接 plugins` 的字符串值。
  - F4：show 的早退路径在 lock.json 解析为对象时也输出两行锁信息，状态行改为 `状态 <锁列值>`，并输出“启用”“权限”两行。
  - F5：权限核对抛 ValueError 时记问题“权限核对失败：…”，按不满足处理。
  - F6（顺带）：清单内容是 JSON null 时原因写“不是对象”；lock.json 不是对象时先判“无效”（表第 6 行先于第 7 行）；授予路径的兜底文字加“核对失败：”前缀。
  - 补测：F1–F5 与 M19 各一例写进 oracle；`test_d11_04` 对 list/show/verify 也断言“修复：”。
- 待决的业务或环境问题（BLOCKED / ESCALATE）：无；另向用户报告一条环境观察：执行器进程能看到决策模型的 key 环境变量（`TYPESAFE_API_KEY` 不在 `env_remove` 中），是否加入过滤需要用户同意。
- 已授权且可以继续的集成动作：local_branch、merge：本 attempt 判 REVISE，不用 integrate；`branch --rework` 建返工提交，挑到 themis-3.0，再加规划端的补齐提交，验收后 `mark SUPERSEDED`。
- 人工介入：0（复审与补齐由规划端会话完成，用户未介入）
