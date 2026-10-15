# REVIEW：kit-install v1 · attempt-001

Verdict: PASS

<!-- review-draft 生成（2026-10-15T20:38:54Z，调度工具 2.8.0）：事实取自 .agent/runs/kit-install/attempt-001；标着待填的地方是复审判断，全部填完 verdict 才收。
     Verdict 行只能写一个结论，并与 verdict 命令的 --verdict 一致。 -->

## 基本信息
- 基线：`b0f762544d792f69169080750cd42577a0c7ad58`
- 候选树：`7c5d0b89a7c52ad23b2c9fca4478ae088baa546e`（补丁往返校验通过；2 files changed, 617 insertions(+)）
- 要求的执行模型：step/step-5-preview · thinking high
- 实际模型：step/step-5-preview；providerThinkingLevel：未回报
- 运行：退出码 0 · 用时 600.203 s / 上限 1800 s · 正常结束 · 工具错误 0
- token：输入 131428 · 输出 36987 · 缓存读 1643008 · 缓存写 0；费用 unknown（unknown）
- 复审者：规划/验收会话（Claude Opus 5.5）；独立复审：Claude Code 的 general-purpose 子代理，按 `review-brief.md` 与 independent-review.md 只读复审（同一厂商，不是换一家审查）

## 门禁

| 门禁 | 结果 | 说明 |
|---|---|---|
| G0 输入一致 | passed | 工具：通过 |
| G1 执行完整 | passed | 工具：通过；提供商未回报思考级别：只能确认请求的级别（high） |
| G2 范围合规 | passed | 工具：通过 |
| G3 行为正确 | passed | 工具：通过；执行过程中提到合同的歧义、矛盾或一致性，报告没有列出：复审时核对（见 summary.md） |
| G4 回归检查 | passed | 工具：通过；检查记录：checks/01（fresh，7/7 通过）；检查在干净副本（基线 + 候选补丁 + setup）上运行 |
| G5 质量复审 | passed | 工具：通过；质量复审（测试是否弱化、兼容性、残余风险）由复审报告负责，工具不做机械判断 |
| G6 可集成 | passed | 工具：通过 |

## DoD 映射

| DoD | 结果 | 证据 | 说明 |
|---|---|---|---|
| D01 | met | V01 passed、V02 passed | 发放内容与每个发放文件的状态（第 1–2 条）；目的：装进目标仓库的 kit 与 kit 本身逐字节一致，kit 一升级就能分清哪些文件过期、哪些被本地改过 |
| D02 | met（R3 由规划端补全） | V01 passed、V02 passed | AGENTS.md、两个规则文件与 dispatch 配置（第 3 条）；目的：目标仓库自己的规则与配置一个字节都不被改写，缺什么都说清楚 |
| D03 | met | V01 passed、V02 passed | 三个命令与 `--force`（第 4–5 条）；目的：本地改过的东西不会在更新时悄悄丢失，覆盖之前一定有备份 |
| D04 | met as contracted；目的的缺口 R1 是合同疏漏，规划端补全 | V01 passed、V02 passed | 拒绝（第 6 条）；目的：链接与仓库之外的路径一个字节都不写，拒绝时目标原封不动 |
| D05 | met | V01 passed、V02 passed、V07 passed | 安装记录、输出与退出码（第 7–8 条）；目的：被脚本调用时最后一行就能读到结果，记录足以支撑下一次 update 与 doctor |
| D06 | met（R4、R6 记录与补全） | V03 passed、V04 passed、V05 passed、V06 passed、scope（越界 0）、复审 | 其它模块与测试不受影响，文档串与导入按第 9 条，Step 4 的测试齐全，不自行做变异检查，所有修改在允许集合内，无依赖变更 |

## 范围与质量
- 越界与警告：越界 0、警告 0
- 测试可信度：oracle 16 个用例在基线上全部失败、在候选上全部通过；执行器测试 5 个，正是合同 Step 4 的五组，没有 skip、没有弱化，断言是全等比较（字节、行、计数）。拒绝那一组的断言落在别的目录上，也没有先验证合法基线（R6）。
- 变异检查：
  - mutations/01：38 条，命令 all、executor
    - all：抓住 38，漏掉 0（意外 0），跳过 0，出错 0
    - executor：抓住 9，漏掉 29（意外 0），跳过 0，出错 0
    - 预期内的漏掉（expect_missed：合同交给其他命令覆盖的规则）：M03 M04 M05 M06 M07 M08 M09 M10 M11 M12 M13 M14 M18 M19 M20 M21 M22 M23 M24 M25 M26 M27 M28 M29 M30 M31 M33 M34 M35 → 处理：注明
- 兼容性与残余风险：新文件，独立脚本，不改任何已有模块（V03、V04 与 scope 证明）。junction 的识别只在 Windows 上实测过；POSIX 的符号链接路径只读过代码（kit 没有 CI）。没有 `install` 的调度器转发，从 kit 目录直接运行脚本。
- 执行器自述与证据是否一致：一致。三条 limitations 属实（467 行比估计的 250 行长、用法错误统一走 `ERROR:`、没跑 V04 是遵照合同）。kit 提交号只在 kit 根就是 Git 根时记录，这个取舍合理，但没有写进 `unresolved_questions`（R4）。12 条测试命令经 `| tail` 掩盖了退出码，合同的检查说明明确禁止（过程偏差）；两条临时目录探针以 `mktemp -d` 开头、`rm -rf "$T"` 收尾，只在临时仓库里安装，合规。
  - 执行报告：json_ok（executor_status completed）
  - 合同矛盾：无
  - 限制与取舍（3，原文）：
    - 实现 467 行，长于合同估计的约 250 行（文档串、类型注解与 helper 拆分）；功能范围未扩大
    - 用法错误统一输出一行 ERROR: 并退出 2；记录校验对 check 同样生效
    - V04 全量未运行（合同要求由验收端执行）
  - 未决问题：无
- 摘要里的“复审需要关注”（原文）：
  - 可疑命令（递归或强制删除）：命令第 1 / 1 行 `…)); print(d['kit_version'], d['kit_commit'][:8] if d['kit_commit'] else None, d['kit_dirty'], d['installed_at']==d['updated_at'], len(d['files']))"; rm -rf "$T"`（事件流第 11548 行）
  - 可疑命令（递归或强制删除）：命令第 1 / 1 行 `…ersion'], d['schema_version'], d['record_type'], (d['kit_commit'] or '')[:8], d['kit_dirty'], d['installed_at']==d['updated_at'], len(d['files']))"; rm -rf "$T"`（事件流第 11654 行）
  - 系统临时路径线索（2 个命中片段）：逐项按 AGENTS.md 核对写法、用途和工具结果。这些是事后扫描线索，不是命令阻断或违规裁定；清理输出或路径当前不存在，不能证明此前未覆盖既有内容
  - 临时路径：事件流第 11548 行，命令第 1 行 `T=$(mktemp -d); git init -q "$T/t"; python scripts/kit_install.py install "$T/t" > "$T/out" 2>&1; echo "exit=$?"; tail -1 "$T/out"; python -c "import json,sys; …`
  - 临时路径：事件流第 11654 行，命令第 1 行 `T=$(mktemp -d); git init -q "$T/t"; python scripts/kit_install.py install "$T/t" > "$T/out" 2>&1; echo "exit=$?"; KI_TARGET="$T/t" python -c "import json,os; d=…`
  - 新增被 Git 忽略的路径：`scripts/__pycache__/`
  - 新增被 Git 忽略的路径：`scripts/codekit/__pycache__/`
  - 新增被 Git 忽略的路径：`scripts/codekit/adapters/__pycache__/`
  - 新增被 Git 忽略的路径：`tests/__pycache__/`
  - 测试或检查命令的退出码被管道掩盖（12 条，例如事件流第 7843 行 `python -m pytest -q -p no:cacheprovider tests/test_kit_install_oracle.py 2>&1 | tail -40`；另有 8 条探索命令也如此）：执行器没有看到被检查程序的退出码，报告里的 reported_exit_code 是推断值，以 check 的结果为准
  - 执行器自行宣布了 1 处解读（例如事件流第 6100 行：“a repo? Then kit_commit would be null. Contract says "kit 根目录是 Git 工作区时" — root dir of a worktree. I'll go with toplevel check. Actually wait — careful: is REPO”）；报告的 contract_conflicts 与 unresolved_questions 都为空：这些解读没有被报告（全部摘录见 events-summary.json 的 interpretation_mentions）
  - 执行过程中有 2 处提到合同的歧义、矛盾或一致性，可能只是在检查，需要核实（例如事件流第 11960 行：“_conflicts stays empty. Hmm, actually let me reconsider whether any of these is a genuine contract ambiguity worth 'unresolved_questions'. The contract says "ch”）；报告的 contract_conflicts 与 unresolved_questions 都为空：核对执行器是否自行选定了某种解释（全部摘录见 events-summary.json 的 ambiguity_mentions）

## 结论理由
以 `check --fresh` 7/7（全量 1471 passed / 7 skipped）、两条命令的变异（oracle 加执行器测试 38/38；只用执行器测试 9/38，漏掉的 29 条全是事先标好的“合同留给 oracle”，意外 0 条）、逐条代码核对与独立复审为据，候选按合同第 1–9 条的字面实现，所有拒绝检查都在第一次写入之前完成。独立复审（子代理）建议 REVISE，依据是下面的 R1；R1 是合同与 oracle 的疏漏（规划问题，不算执行错误，见 review-pi 第 5 步“合同本身有疏漏时”），规划端已在补全里修正并加 oracle 用例，所以结论为 PASS、由规划端补全，不另派 v2。

- R1（中，规划问题）：每次写入先写 `<路径>.kit-install.tmp` 再 `os.replace`，写前检查没有覆盖这个临时文件名，`open(tmp, "wb")` 会跟随链接。规划端实测：目标里放一个指向仓库外文件的同名符号链接，install 退出 0，仓库外的文件被写成 kit 的 `pi_dispatch.py`，目标里的 `scripts/pi_dispatch.py` 变成指向仓库外的链接——D04 的目的没有保住。合同规定了“先写同一目录里的临时文件再 `os.replace`”，却没把临时文件名列进第 6 条要检查的路径；规划端草稿与 oracle 一样漏了。补全：写前核对每个要写路径的临时文件名不存在（`lexists`），临时文件以 `O_CREAT | O_EXCL`（有 `O_NOFOLLOW` 时带上）新建；备份目录选名改用 `lexists`。oracle 补用例：临时文件名是目录、是指向仓库外的链接时都拒绝，一个字节都不写。
- R2（低）：git 不在 PATH 时抛 `FileNotFoundError`，记录嵌套过深时抛 `RecursionError`，kit 缺 AGENTS.md 或规则片段时抛 `FileNotFoundError`：都以堆栈退出 1（1 在合同里专指仍有 KEEP / CONFLICT），而第 6 条要求拒绝。都发生在第一次写入之前，目标不受损。补全：三处 git 调用接 `OSError`，记录接 `RecursionError`，kit 的 AGENTS.md 与两个片段先核对，`main` 把其余 `OSError` 也写成一行 `ERROR:`。oracle 补“git 不在 PATH”与五种坏记录。
- R3（低）：第 3 条要求 AGENTS.md 的章节两边去掉首尾空白后比较整行，候选只取目标里行首 `## ` 的标题文字：五个标题都在、只是缩进两格时报告五个全缺（规划端实测）；反过来 `##  标题`（两个空格）候选判在、合同判缺。只影响报告行。补全按合同比较，oracle 补缩进的用例。
- R4（低，报告纪律）：`kit_commit` 只在 kit 根就是 Git 工作区根时记录。取舍合理：宽松读法会把外层无关仓库的 HEAD 记给一个未跟踪的 kit，`kit_dirty` 还会因为看不到未跟踪文件而错报 false。但执行器只在思考里决定（事件流第 6100 行附近），没有写进 `unresolved_questions`；“用法错误统一 `ERROR:`”“check 也校验记录”两处取舍只写在 limitations。两条安装探针用了 `mktemp -d`（AGENTS.md 允许的写法、已清理），但合同 Forbidden 写了“命令与探针里不另建临时目录”——这一句与合同自己的检查说明（允许 `T=$(mktemp -d)` 截短输出）矛盾，是规划端的措辞问题。
- R5（低）：模块文档串与 argparse 说明把 kit 写成“PI-Kit”（AGENTS.md 开头的旧名）；状态说明里 ADD / UPDATE 写“本次写入”，check 其实不写。补全改正。
- R6（低）：执行器的拒绝用例检查的目录不是被拒绝的那个，断言是空的，也没有先验证合法基线；`.gitattributes` 用例没有先验证合法基线。补全给拒绝用例加了合法基线与“不存在的目标没被创建”的断言。oracle 原先没有守住的规则（记录校验的拒绝、update 保留 `installed_at`、记录的键集合）补全一并加了用例；`kit_dirty` 的含义、备份目录的 `-2` 后缀与 `.agent/kit-backup` 是链接的情形只核对了代码，没有回归测试。

## 后续动作
- 需要修正的具体差异（REVISE）：无；R1、R2、R3、R5、R6 由规划端补全（集成之后的单独提交）
- 待决的业务或环境问题（BLOCKED / ESCALATE）：无
- 已授权且可以继续的集成动作：local_branch、merge：`bash scripts/dispatch-pi.sh integrate .agent/runs/kit-install/attempt-001`（当前末端上验证后落地）
- 人工介入：约 90 分钟（规划端：设计说明、草稿与 oracle、草稿变异、合同、复审与探针）
