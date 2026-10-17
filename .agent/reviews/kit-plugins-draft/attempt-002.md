# REVIEW：kit-plugins-draft v2 · attempt-002

Verdict: REVISE

<!-- review-draft 生成（2026-10-17T12:30:42Z，调度工具 2.10.0）：事实取自 .agent/runs/kit-plugins-draft/attempt-002；标着“待填”的地方是复审判断，全部填完 verdict 才收。
     Verdict 行只能写一个结论，并与 verdict 命令的 --verdict 一致。 -->

## 基本信息
- 基线：`c1c2e196e7766207927f28f6218cf470cb556343`
- 候选树：`84c4f819ab6bf1d297c228e297bdaf53f11e4fbe`（补丁往返校验通过；4 files changed, 528 insertions(+), 87 deletions(-)）
- 要求的执行模型：bb/step-5-preview · thinking high
- 实际模型：bb/step-5-preview；providerThinkingLevel：未回报
- 运行：退出码 0 · 用时 1122.61 s / 上限 3200 s · 正常结束 · 工具错误 3
- token：输入 206884 · 输出 71897 · 缓存读 5867008 · 缓存写 0；费用 unknown（unknown）
- 复审者：B 组规划审核端——Claude Code 子代理（general-purpose，`claude-haiku-5-5`，只读，在 scratchpad 副本里跑变异与探针），结论 APPROVED_WITH_EDITS；主会话（Opus 5.5）在临时 worktree 里复核：按 E1–E7 修改后 oracle 54 passed、4 skipped，B2c 变异被新用例抓住，去掉参考实现时 54 项逐例失败。

## 门禁

| 门禁 | 结果 | 说明 |
|---|---|---|
| G0 输入一致 | passed | 工具：通过 |
| G1 执行完整 | passed | 工具：通过；提供商未回报思考级别：只能确认请求的级别（high） |
| G2 范围合规 | passed | 工具：通过 |
| G3 行为正确 | 未通过（审核） | 工具：通过；第一轮的 B1–B4、M1–M3、m1–m5 都已落实，G1、G2、G4、B3 与 B2 的两类变异都被抓住；但起草合同 Steps 第 14 步要求的 manifest 层链接用例没有写成：`test_b2_grant_path_other_manifest_link_not_read_and_reported` 实际把整个 docs-change 目录做成 junction，参考实现第 567 行改成只查插件目录时 oracle 仍 53 passed（F1） |
| G4 回归检查 | passed | 工具：通过；检查记录：checks/01（fresh，4/4 通过）；检查在干净副本（基线 + 候选补丁 + setup）上运行 |
| G5 质量复审 | 通过（附审核端修改） | 4 个 skip 只限文件链接变体（本机建不了文件符号链接），目录 junction 用例都真实运行；oracle 不调用私有函数，没有参考实现时逐例失败；删除的 5 行含断言的代码全是替换（审核端核对）。内层合同小错：D01–D03 的证据误写 V04（F2）、时间分配算术（F3）、oracle 断言了合同没写明的文件名（F4）、资源读取失败的状态没写进合同（F5）、“规划端 oracle”用语（F6） |
| G6 可集成 | passed | 工具：通过 |

## DoD 映射

| DoD | 结果 | 证据 | 说明 |
|---|---|---|---|
| D01 | 部分满足（内层合同的证据映射、时间分配与措辞，F2、F3、F6；coverage 与 scope 已修正） | V02 passed、scope（越界 0） | 三个交付物修正：合同草稿符合 v2 要求，JSON 必需键齐全，coverage 与 scope 已修正；目的：草稿可以被审核端直接改写成正式合同 |
| D02 | 满足（执行报告逐条列出改动位置与用例名） | 复审 | 复审记录 B1–B4、M1–M3、m1–m5 逐条有对应修改，执行报告逐条列出改动位置 |
| D03 | 部分满足（B2 的 manifest 层用例缺失，F1；其余写死用例齐全并通过） | V01 passed、复审 | oracle 补齐写死的用例（G1、G2、G4、B2、B3、M1、M2、m1、m2、m3、m5 对应的用例名）且全部通过；目的：oracle 能区分正确实现与错误实现，而不是只能证明“能跑” |
| D04 | 满足（参考实现只用公开函数；它不发布） | V01 passed、V03 passed、复审 | 参考实现修正后通过 oracle，只调用既有公开函数，不另写同类实现 |
| D05 | 满足（越界 0） | scope（越界 0） | 所有修改都在允许集合内 |
| D06 | 满足（删除的 5 行都是替换） | 复审 | 没有删除、跳过或弱化既有测试，既有用例只允许加强断言 |
| D07 | 满足（基线上 pytest 退出码 5，修改后 5 passed） | V04 passed | 探针 V04 在基线上失败（pytest 退出码 5，没有用例被选中），修完后通过；目的：证明这五个用例确实针对本轮的修改，而不是空跑 |

## 范围与质量
- 越界与警告：越界 0、警告 0
- 测试可信度：oracle 53 项（加 E7 后 54 项）、4 skip（文件链接变体）；没有参考实现时 54 项逐例失败（导入失败，按设计 4.7 只算弱证据）；审核端变异：G1、G2、G4、B2a、B2b、B3 全部抓住，B2c 漏掉 → E7 补上后抓住（主会话复核）。
- 变异检查：没有记录（中高风险任务要做一轮，见 review-pi/mutation-check.md）
- 兼容性与残余风险：起草产物不集成（参考实现不发布）；发布的是修改后的内层合同与 oracle。残余：导入失败式的基线证据偏弱（设计 4.7），由实现任务的变异检查补足。
- 执行器自述与证据是否一致：interpretations 9 条都在合同范围内；资源读取失败的处理（事件流第 6116 行的推理）没有写进 interpretations（F5）；Steps 第 14 步的 manifest 层用例名不副实而报告称已完成；过程：事件流第 332 行一条检查命令的退出码被 `| tail -n 30` 掩盖（其余 12 条 pytest 管道都带 `set -o pipefail;`），没有临时目录用法（第一轮的 `tempfile.mkdtemp()` 已改正）。
  - 执行报告：json_ok（executor_status completed）
  - 合同矛盾：无
  - 自定解读（9，原文）：
    - {"quote": "T1：--json 的键名与结构。oracle 只断言输出可解析为 JSON 对象，不断言键名。", "adopted": "沿用 v1 键名，仅在 show --json 的 lock.json 里补 generation、顶层补 resources", "reason": "合同不约束键名；最小改动并让 JSON 与文字输出承载同样信息"}
    - {"quote": "T2：文字输出的格式、列宽与提示语措辞。oracle 只断言本合同写明的固定词、插件 ID、退出码与文件字节。", "adopted": "沿用 v1 列格式；只改 lock.json：generation <值>，lock_sha256 <值>、逐资源行、plugins 根是链接时直接打印 无效：链接 plugins（去掉 ERROR 前缀）", "reason": "合同只锁定固定词、ID、退出码与字节；去掉 ERROR 前缀避免“错误前缀 + 0 退出码”并存"}
    - {"quote": "T3：授予权限时受影响插件清单的排序与格式", "adopted": "sorted() 按 ID 字典序；格式沿用 v1 的“授予 <权限> 后，以下插件也满足权限条件：…”一行；问题行另起一行打到 stdout", "reason": "§4.2 只要求列出，按 ID 排序稳定可断言"}
    - {"quote": "T4：写入失败（OSError）时的提示文字自定；退出码记为 1", "adopted": "沿用 v1 的 ERROR: 写入 dispatch.config.json 失败：<原因>，退出码 1；_decisions_gate 解析失败用 ERROR: 决策插件配置无法解析，拒绝写入（配置未改）：<原因>", "reason": "合同只定退出码"}
    - {"quote": "读前检查（D5）：…以及决策插件的 questions/ 目录与其中每个 *.json 在读之前都…检查链接与 junction", "adopted": "新增 _questions_link()，调用 verify_battery_lock 前对 questions/ 与其中每个 *.json 各做一次 first_link_component", "reason": "资源段只在 manifest 把它们列为资源时才覆盖，而 verify_battery_lock 自己会读取它们"}
    - {"quote": "任何一项失败…锁列记为“无效”", "adopted": "_questions_link 命中时把 info[\"lock\"] 置为“无效”", "reason": "与资源段读前失败的处理保持一致"}
    - {"quote": "m3：decisions.mode 为 on，patch 抛 ValueError，enable code-change 退出码 1…配置字节不变", "adopted": "该用例配置写 {\"decisions\": {\"mode\": \"on\"}, \"plugins\": {\"enabled\": [\"decisions\"]}}", "reason": "必须让 enabled 真的变化才会走到 _apply→_decisions_gate；否则 enable 因“没有变化”提前返回 0，触发不了写入前核对"}
    - {"quote": "oracle 只断言本合同写明的固定词、插件 ID、退出码与文件字节", "adopted": "用 _impact_lines()/_resource_rows() 按行筛选后再断言“不一致”在/不在行内", "reason": "T2 允许措辞自定，不能逐字比较整行"}
    - {"quote": "命令级错误（…用法错误…）：stderr 一行，以 ERROR: 开头；argparse 参数错误退出码 2；命令级错误捕获 pd.DispatchError 与 kit_config.ConfigError", "adopted": "程序自己检测到的错误打印一行 ERROR:；argparse 自己的用法错误沿用 argparse 的 usage+error 输出，退出码 2，oracle 不断言其 stderr 格式", "reason": "合同把 argparse 单列且 D10 只要求捕获两类异常；v1 行为未变"}
  - 限制与取舍（5，原文）：
    - tests/test_kit_config.py::test_init_show_set_unset_validate 在本机失败（decisions secret source 为 env 而非 none，因本机设了 API key 环境变量）；与本次改动无关，kit_config.py 未被修改，也不属于 V01–V04
    - 4 个文件符号链接 oracle 用例在 Windows 非特权进程下按合同 pytest.skip；目录 junction 变体全部真实运行
    - 内层合同的 S8/V02（tests/test_kit_plugins.py，执行端自己的测试）不在本轮 Scope 内，未创建
    - 未做变异反测（合同规定由验收端在固定候选上执行）
    - 未提交、未推送、未派遣，未写 .agent/ 下任何文件
  - 未决问题：无
  - 事件流里的解读线索（逐条核对是否都在上面的自定解读、合同矛盾或未决问题里）：
    - 第 20557 行（thinking）：g the ERROR: format, and v1 behaves this way. The oracle doesn't assert ERROR: for argparse errors. I'll note it as an interpretation rather than a conflict... Actually, let me be careful: it IS arguably an internal contradiction in the outer contract (行为说明 vs
    - 第 20557 行（thinking）：stderr format, and the contract's 失败判定 for test_m5_no_version_option only says "`--version` 退出码 2", I'll treat it as an interpretation (argparse errors keep argparse's own message; the `ERROR:` one-liner applies to errors the program detects). I'll document it
- 摘要里的“复审需要关注”（原文）：
  - 新增被 Git 忽略的路径：`.pytest_cache/`
  - 新增被 Git 忽略的路径：`.pytest_cache/.gitignore`
  - 新增被 Git 忽略的路径：`.pytest_cache/CACHEDIR.TAG`
  - 新增被 Git 忽略的路径：`.pytest_cache/README.md`
  - 新增被 Git 忽略的路径：`.pytest_cache/v/`
  - 新增被 Git 忽略的路径：`scripts/__pycache__/`
  - 新增跳过/聚焦标记：`pytest.skip("本机无法创建文件符号链接（需要权限）")`
  - 删除了 5 行含断言的代码（新增 87 行）
  - 测试或检查命令的退出码被管道掩盖（1 条，例如事件流第 332 行 `timeout 600 python -m pytest tests/test_kit_plugins_oracle.py -q 2>&1 | tail -n 30`；另有 12 条探索命令也如此）：执行器没有看到被检查程序的退出码，报告里的 reported_exit_code 是推断值，以 check 的结果为准（2.10.0 起执行说明给了每条检查的自检照抄写法）

## 结论理由
第二稿把第一轮审核的 B1–B4、M1–M3、m1–m5 逐条落实，fresh 检查 4/4，写死行为的变异大都能被抓住；内层合同可以发布。但 oracle 仍漏了起草合同点名的一个用例（B2 的 manifest 层），内层合同还有证据映射与算术等小错，按起草合同的 DoD 判 REVISE（EXECUTION_ERROR）。起草预算已用完（2/2），剩余部分小而明确：由规划审核端在发布前按 E1–E7 补齐（只改证据映射、算术、措辞，补一个用例与一处断言依据，不改行为），主会话在临时 worktree 里复核通过后发布为 kit-plugins.v1，本 attempt 标 SUPERSEDED。

## 后续动作
- 需要修正的具体差异（REVISE）：由规划审核端在发布时补齐，不再派遣（预算 2/2）：
  - E1、E2：内层 D01–D03 的证据只写 V01（V04 是 `--help`，证明不了行为）。
  - E3：时间分配改为 5 + 20 + 8 + 5 + 5 = 43 分钟。
  - E4：题库问题行含该清单的文件名与“不一致”（oracle 已断言，合同补上依据）。
  - E5：资源读取失败（OSError）时锁列“无效”、资源列“不一致”、输出含“资源读取失败”（记录参考实现现行做法）。
  - E6：Goal 去掉“规划端”三字。
  - E7：oracle 新增 `test_b2_grant_path_other_manifest_junction_not_read_and_reported`（manifest.json 位置是目录 junction），原用例改名为 `…_other_plugin_dir_link_…`。
- 待决的业务或环境问题（BLOCKED / ESCALATE）：无
- 已授权且可以继续的集成动作：合同没有授权集成动作：交付候选，等待决定
- 人工介入：0（审核由 B 组规划审核端完成，主会话复核与发布，用户未介入）
