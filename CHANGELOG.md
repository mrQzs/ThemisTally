# 变更记录

## 2.3.0：调度器按 KitExperiment 实机反馈修正（2026-10-06）

`scripts/pi_dispatch.py` 此前锁定在 a4fa199（2.2.2），用户同意解锁后修正以下四处。旧实现的锁定预期仍由 a4fa199 的 Git 对象生成，不受影响。

- **附件不再暴露主仓库路径**。合同与执行说明原来以运行目录的绝对路径附上，附件名会原样出现在发给执行器的消息里；KitExperiment 的两次运行中，执行器据此读取主仓库，第二次时合同已明文禁止。现在两份副本放在中性的临时目录里附上，内容与运行目录中的文件逐字节相同，运行结束后删除；`run.json` 记录副本的路径与 SHA-256。
- **访问主仓库判为 G2 不通过**。工具参数落在主仓库里，或 shell 命令里出现主仓库路径（例如 `cd "<主仓库>"`），`events-summary.json` 的记录带 `main_repo: true`，summary 标明“位于主仓库”，verdict 的 G2 判为不通过，只能显式豁免。本 attempt 的运行目录与附件目录仍记为自己的路径。主仓库以外的工作副本外路径仍只作提示。
- **扫描 shell 命令里的主仓库路径**。原来只看工具调用的路径参数，`cd <绝对路径>` 一类的访问漏报。
- **`mutate` 不再把 pytest 会话中断记为抓住**。变异让 KeyboardInterrupt 冒出测试时，pytest 以退出码 2 结束，后面的用例都没有运行；退出码 2 且日志里有 `!!! KeyboardInterrupt !!!` 横幅时，记为出错并写明原因。
- 测试：`tests/test_dispatch.py` 新增 9 项检查（共 271 项）；两处旧测试改为不依赖工作区版本号：fixture 表头的 `tool_version` 固定写旧实现的 2.2.2，`--version` 的用例核对格式与工作区声明的版本。全量 unittest 1410 项通过，跳过 39 项。

## 未发布：KitExperiment 迁移到 macOS 后的自测反馈

两个仓库从 Windows 拷到 macOS 15.7.9（x86_64）后，第一次在 POSIX 上跑全量自测：Python 3.9.6 下 1408 项中 4 项失败、66 项报错。

逐任务记录、有效做法与待改进项（含因调度器锁定暂未修改的扫描与执行说明问题）见 [KitExperiment 实机反馈](docs/KitExperiment实机反馈.md)。

- **产品缺陷：POSIX 上路径静态审阅不可用**。
  - 现象：`protocols._link_target_text` 直接引用 `stat.IO_REPARSE_TAG_MOUNT_POINT`，这个常量只在 Windows 上定义。macOS/Linux 上每个非链接分段都抛 AttributeError，`resolve_existing_path_for_review`、`seal_bytes` 与 `read_sealed` 因此无法使用。
  - 修复：改为模块常量（getattr，缺省 0xA0000003）。POSIX 的 lstat 没有 `st_reparse_tag`，标签按 0 处理。
- **产品缺陷：macOS 自带 Python 3.9.6 上导入有副作用（违反 01-A14）**。
  - 现象：导入 `codekit.sealing` 与 `codekit.baseline` 时会打开 `/dev/urandom`。原因是 secrets 与 tempfile 都导入 random，random 一导入就取熵播种。这正是 `dispatch-pi.sh` 首选的 `python3`；Python 3.12 不受影响。
  - 修复：sealing 改用首次使用才导入的代理，保留可被测试替换的模块属性 `secrets`；baseline 改为在函数内导入。
- **测试的平台假设：符号链接用例**。
  - 现象：PhysicalPathTests 与 SealingTests 用未解析的临时目录写绝对链接目标。macOS 上 `/var → /private/var` 是根外的系统链接，逐跳核对按设计判为 `E_PATH_ESCAPE`，用例测到的就不再是它要测的规则。
  - 修复：POSIX 上改用 resolve 后的临时目录，Windows 不变。
  - 产品行为不变：目标路径经过根外系统链接的绝对链接，仍按设计失败关闭。
- **测试的平台假设：legacy CLI 用例**。
  - Markdown 检查行按解释器文件名生成（macOS 上是 `python3`），三个用例却写死了 `python`。其中 LB-CONTRACT-018 因替换落空而空转通过，现补上替换前的计数断言。
  - LB-EXIT-026 用 PY 所在目录模拟“没有 git”，但 Xcode 的 `usr/bin` 里同时有 git。POSIX 上改为空目录，Windows 不变。
- **新增两项静态检查**：上面两处产品缺陷只在 POSIX 上，或只在 macOS 自带的 Python 3.9 上暴露，在 Windows 上跑自测发现不了。所以补了两项在所有平台都会运行的源码检查：
  - codekit 源码不得直接引用 `stat.IO_REPARSE_TAG_*` 与 `stat.FILE_ATTRIBUTE_*`；
  - F049 导入的模块在模块级不导入 random、secrets 与 tempfile。

  两项检查都能在修复前的源码上命中对应缺陷。
- **实测结果**：
  - Python 3.9.6 与 3.12.14 的全量 unittest 都是 1408 项全部通过，跳过 39 项：Windows/NTFS 特性、大小写不敏感的 APFS、未安装 jsonschema，以及归属其他模块的用例。
  - 两项静态检查是在全量运行之后补的，单独运行通过（ImportSideEffectTests 5 项）。
  - `tests/test_dispatch.py` 在两个解释器上都是 262 项全部通过。
- **规划指南（KitExperiment runtime 移植的实机反馈）**：
  - plan-task 新增三条：
    - 要求与现有实现逐项一致时，把参考源码与参考测试放进基线，并由规划端提交 oracle 测试（逐字移植的参考测试、失败关闭用例、与参考逐项比较的差分测试）作为验收标准，不在合同里意译接口；
    - 草稿验证统计失败用例时把 pytest 的 `SUBFAILED` 算进去；
    - 列出要改掉的旧断言时写明“下列旧断言是错的”，不要只写“至少包括”的列表。
  - 实测结果：
    - 前四份只给意译接口的合同，候选都与参考不同；
    - 按新做法写的 v2 一次完成，canonical 层与参考逐个定义的 AST 相同，27 个变异全部被抓住。
- **执行器的临时文件写法**：
  - 问题：执行器为了“保留真实退出码”把检查输出写到固定的 `/tmp/v01.txt` 等路径再 `rm -f`，KitExperiment 已出现两次。
  - 改进：合同模板 Validation 一节与 AGENTS.md 执行器一节补上合规写法——直接运行检查命令，确要截短就用 `T=$(mktemp -d)` … `rm -rf "$T"`。
  - 未改动：`pi_dispatch.py` 的执行说明属于锁定的旧实现（a4fa199），本次没有修改。
- **跨机复审**：在 macOS 上复审了 Windows 上派遣的 attempt。
  - in_place 检查因 worktree 不在本机而拒绝运行；`check --fresh` 按 prepare 时记录的 `core.autocrlf=true` 快照，与候选树一致。
  - `verdict` 在 worktree 不存在时跳过重新快照，以候选补丁的往返校验为准。

## 未发布：Fiction-Wiki 的 macOS 执行反馈

- 离线适配器现在要求 `run_started` 恰好出现一次且位于序号 0，拒绝拼接或重放前缀被误结算为成功；新增对应回归测试。

- 修复Bash3.2在`set -u`下展开空数组导致包装器无法启动的问题；保持Python版本检查、解释器回退、参数与退出码传递。
- 增加包装器回归场景，覆盖python3、python、py -3、全部不可用及带空格/字面量参数。
- 新增`plan-task/test-design.md`：合法基线与独立反例、非空/partial分支、类型边界、逐字段摘要与真实模型链。
- 委派清单和合同模板加入按实机反馈控制任务大小与时间分配；已开始任务不能改名重置预算。
- 执行说明加入反例隔离指引，以及检查完成后转报告、时间不足明确未运行项的要求。
- 复审指南区分机械caught和有效行为捕获；记录P1-01/P1-02各两轮的成果、剩余测试缺口与执行范围问题。详见[实机反馈](docs/Fiction-Wiki实机反馈.md)。
- 独立复审说明禁止通过环境工具隐式写入，或借用其他检查正在清理的临时环境；需要复现时由主验收端提供稳定解释器或执行探针。
- P1-03再次出现固定临时路径读写/删除后，临时路径扫描改为保留每个不同的命中片段，摘要逐条展示事件号、命令行号与摘录；超过50条时明确标出未展示数量及原始证据位置。这是事后取证改进，不是命令阻断或沙箱。
- 明确故意改坏实现的变异默认由验收端执行，local_test不自动授权额外变异；补充真实旧版本标识与跨集合唯一性的合同设计提醒。
- 根据legacy适配验收补充同码守卫的独立反例、必要检查真实退出码与验收侧错误变异纠正案例；区分实现正确、测试遗漏和规划补充。
- 根据决定记录验收补充required-nullable精确错误、关联条件同码遮蔽、非空投影与DB/DTO默认值分层；必需字段测试使用独立预期清单，避免随实现缺陷一起漏测。
- 明确实际JSON入口须有合法正例及反例，子DTO的缺字段测试不能替代顶层协议证明；独立复审按候选树汇总追加变异，不能只看最新的小清单。
- 区分可独立违反的规则与被其他约束蕴含的边界；无法构造单一语义错误时，分别核验接受集合、字段错误协议及Schema，不把等价变异算成产品漏洞。
- 独立复审先核对worktree与仓库相对路径；错误glob和截断目录列表不能证明基线已删除，也不能据此自行换到主工作区验收。
- 测试返工逐项核对原缺口；保留有效覆盖允许修正旧输入与弱断言，不能以纯追加行数或零删除代替验收。
- 与 2.2.0–2.2.2（WoMovieTest netperf 反馈）合并：执行说明第 7 条用本节的写法；第 8 条（变异检查由验收端做、临时改坏时备份放工作目录内）与第 9 条（反例隔离、摘要逐字段验证）并存。

## 2.2.2（2026-09-24）：Repository facts 的路径也按检查 cwd 找

| 反馈 | 改进 |
|---|---|
| 2.2.1 的「Repository facts 文件不在基线」核对把一份合同里相对项目子目录（检查的 cwd `UITest/`）写的 8 个路径全报成不存在：合同习惯按检查的 cwd 写相对路径 | 除仓库根外，也按合同 `checks` / `setup` 里每个 `cwd` 各找一遍，任一命中即算存在 |

**自测**：`test_v22_netperf_feedback` 增至 17 项断言；全套自测通过。

## 2.2.1（2026-09-24）：同一项目 P3 阶段的两条反馈

| 反馈 | 改进 |
|---|---|
| `netperf-diff` 与 `netperf-report` 并行派遣，diff 合同的 Repository facts 写着 `report.ts` 的类型「基线已含」，其实那是同批另一份合同才会产出的文件。执行器正确地按停止条件 BLOCKED（149 s，零改动），但一轮 attempt 与一次验收就此花掉 | `validate`（prepare、baseline 同样经过它）核对 Repository facts 里用反引号点名的仓库相对文件（至少一个 `/`、有扩展名、不含通配符、不在 `allowed_new_files` 里）是否存在于基线：缺失即 WARN「Repository facts 提到的文件在基线 … 中不存在——若它由同批的另一份合同产出，等那份集成后再以新 HEAD 为基线」。自测里示例合同点名的虚构文件现在先放进测试仓库的基线 |
| `branch` 的输出用「→」连接分支名与提交，规划端在 cp1252 控制台里用 grep 抓提交 ID 时得到乱码 | `branch` 另打印一行纯 ASCII 的 `commit=<sha> branch=<name>` |

**自测**：`test_v22_netperf_feedback` 增至 16 项断言；全套自测通过。

## 2.2.0（2026-09-24）：WoMovieTest netperf 项目的反馈

在 WoMovieTest（TypeScript + Playwright 的 UI 回归仓库）上由 Claude Code 2.1.281 担任规划端，把「网络性能压榨点探查」拆成 13 份合同交给 `step/step-5-preview`（thinking high）。规划端在 `.agent/reviews/pi-kit-feedback.md` 里记录了 11 条反馈，逐条处理如下（#5 核实不成立：`doctor --out` 本来就会创建 `_env/`）。

| 反馈 | 改进 |
|---|---|
| `contract-guide.md` 说 setup 要手工补进 JSON，其实 `derive-json` 会解析 Markdown 的 `## Setup` 节，模板与指南都没提 | contract-template.md 增加可选的 `## Setup` 节；contract-guide 第六节写明 Markdown 也能写 setup 行，validate 不比较它 |
| 按「先提交合同再派遣」的流程，HEAD 必然比 base_sha 多一个合同提交，13 份合同 13 次 WARN「base_sha 不是当前 HEAD」，真正该看的警告被淹没 | validate / prepare / baseline：base 与 HEAD 的差异只在规划路径（`planner_paths`，缺省 `.agent/plans/**` 等）时降为 `NOTE`，并列出差异文件；差异碰到代码时仍是 WARN。`_print_messages` 认识 `NOTE：` 前缀 |
| Windows 上 `core.autocrlf=true` 时每次 `git add .agent/**` 都刷一屏「LF will be replaced by CRLF」 | `gitattributes.append.txt` 追加 `.agent/** text eol=lf` |
| 目标仓库已有 AGENTS.md 时，README 只说「合并内容」；实际还要给执行器加项目禁区（不打生产站、不读凭据目录） | AGENTS.md 执行器一节新增「本仓库额外的禁区」占位；README 安装步骤写明合并时的三个决定 |
| `baseline` 对只新增测试文件的合同，V03 在基线上必然 failed，输出「基线上未通过（修复后应通过）」读起来像修复类任务 | 检查没有 `expect_on_base`、日志显示找不到文件或用例（`Could not find`、`ENOENT`、`no tests found`、`collected 0 items`、`找不到`…）时，说明改为「只新增测试文件的合同在基线上本就如此，属正常；有效性改用变异检查证明」 |
| dispatch-pi / review-pi 写「第一个候选 ff-only」，前提是 HEAD 仍是基线；按上面的流程 ff-only 必然失败 | 两个技能改为「HEAD 仍是基线才 ff-only，否则 cherry-pick」；`branch` 按当前 HEAD 直接打印合适的集成命令 |
| 漏掉的变异由规划端补测试，这一步没有痕迹 | review-template 的变异一行改为固定格式：`<变异名> → 归因 → 处理`，便于从复审记录统计 |
| **collect-cdp 的 verdict 被 G6 拒绝**：列出的「被修改的候选文件」全是 `.agent/**` 等基线文件。根因是系统级 gitconfig 在运行期间被外部重写（`core.autocrlf` 由 true 变 false），autocrlf=true 检出的 CRLF 工作副本在重新快照时不再归一 | prepare 在 meta.json 记录生效的 `core.autocrlf`（`git_autocrlf`）；`snapshot_tree` 与 `tree_from_patch` 一律 `git -c core.autocrlf=<记录值>` 执行（候选、check 前后、fresh 副本、mutate、verdict、branch、cleanup 全部沿用），证据不再随后来的全局配置变化漂移。G6 仍有差异时，用 `git diff --ignore-cr-at-eol` 判断是否只差行尾，是就提示「core.autocrlf 在运行后被改动（记录 X，现在 Y）」而不是「候选被修改」。doctor 记录 `repository.git_autocrlf` |
| 三个执行器都自发做突变反测，写法都是 `T=$(mktemp -d)` 暂存原文件、改坏、跑测试、cp 回来、rm -rf，每次触发「可疑命令 + 临时目录」两类提示 | AGENTS.md 与执行说明写明：验收端会用 `mutate` 做变异检查，执行器不必自做；确要临时改坏，备份放工作目录内并在同一条命令里删除 |
| 执行器自述「S01 未执行」，其实 prepare 已经跑过 setup；执行器看不到 prepare 的日志 | 执行说明新增「准备阶段已经做过的事（prepare）」：列出每条 setup 的命令、cwd、退出码，注明不必重跑 |

**实机结果**（截至 2.2.0 发布时）：P1 采集层 4 份合同已派遣，3 份 PASS 集成（url-headers 186 s、collect-perf 384 s、collect-cdp 873 s），变异检查分别 10 抓 9、8 抓 6、10 抓 10；漏掉的都归因为合同测试清单遗漏，由规划端补测。中风险的 collect-cdp 用 `pi-reviewer` 做了独立复审，8 条发现均不阻断。

**自测**：新增 `test_v22_netperf_feedback`（13 项断言），全套自测通过；每处修正都有对应断言。

## 2.1.0（2026-09-23）：Codex 规划端试跑的反馈

在 WoMovieSubCheck 上第一次由 Codex CLI 0.156.0 担任规划端，完成一个子任务的规划、派遣与验收（a001 REVISE → a002 PASS）。Codex 在该仓库的 `.agent/reviews/export-relative-output/tooling-notes.md` 中记录了 10 条工具问题，逐条核实后处理如下。

| 反馈 | 改进 |
|---|---|
| a001 的执行器用 `tempfile.mkdtemp()` 在工作目录外建目录并 `os.chdir` 进去，留下两个空目录。自动范围检查没有发现（越界 0），是 Codex 复审时人工发现的，判 SCOPE_VIOLATION | 事件摘要新增 `temp_path_uses` 与 `temp_path_use_count`：命令中出现 tempfile、mktemp、`/tmp`、`/var/tmp`、`$TMPDIR` / `$TEMP` / `$TMP`、`%TEMP%`、`AppData\Local\Temp` 等写法时，记下行号，一律列入“复审需要关注”。<br>扫描前先把工作目录与本 attempt 运行目录换成 `<worktree>`，因为默认的 worktree 就建在系统临时目录下。只屏蔽认得准的完整参数：左右边界、引号与空格都按完整参数判断。同名前缀的兄弟目录、引号前后的拼接、转义的引号、反斜杠转义的空白、含变量的路径、用 `..` 跳出去的路径，认不准就不屏蔽，照常计入。`<worktree>` 里名叫 tmp 的子目录不算临时路径，`>/tmp/x` 这样不带空格的重定向照常计入。<br>AGENTS.md 与执行说明写明：临时文件是“不访问工作目录以外的路径”唯一的例外，用途只限中间产物，只能用测试框架管理的目录，或在同一条命令里用 `T=$(mktemp -d)` 新建、以 `rm -rf "$T"` 作为最后一步。<br>1.2.4 的“删除本条命令用 mktemp 新建的临时路径不算可疑命令”取消：这类删除照常列为可疑命令，由复审核对。原因见下文的 Codex 审查 |
| “contract_conflicts: none found. Let me double check for inconsistencies …”被提示为“提到合同有歧义或矛盾” | 提示改为“提到合同的歧义、矛盾或一致性，可能只是在检查，需要核实”，这正是 Codex 在原始反馈里建议的两种做法之一。<br>排除规则只新增一类：关键词后面直接跟着独立的否定答案，例如 “inconsistencies: none found.”“矛盾：无。”，或报告标题“### 合同矛盾”下一行的“未发现。”。“矛盾：未发现解决办法”这类答案后面还有别的内容的，仍然计入。<br>只是在检查的句子不排除，试跑的那一处仍会提示。单独的 no 不算答案；答案之后必须是句末标点、文本结尾，或换行后接空行、标题、列表。<br>1.2.0 的否定前缀收紧为必须紧挨关键词，中间只允许 any、real、seem、internal、任何、发现这类固定的填充词：“no fix for this inconsistency”“不可调和的矛盾”“not merely inconsistent”“不仅矛盾”都仍然计入。双重否定（cannot … without、isn't without、not un-、并非没有）照常计入；句点后面紧跟标识符时（如 `None.__class__`）不算句末 |
| 沙箱内 doctor 报“执行模型不在可用模型列表中”，沙箱外正常 | doctor 记录 `executor_model_list`：退出码、行数、没有表格时的原因、脱敏后的 stderr 末尾。<br>- `pi --list-models` 本身失败时单独报告，建议在沙箱外运行，`executor_model_listed` 记为 null；<br>- 模型表格只解析表头之后的行。pi 0.87 没有可用或匹配的模型时，输出的是一句说明而不是表格。现在分别报告“pi 没有任何可用模型”（多半读不到 `~/.pi/agent`）与“没有与该模型匹配的”；<br>- doctor、预检与 smoke 的结果写出之前统一脱敏，因为 pi 转述 models.json 的解析错误时可能带出其中的凭据。<br>&nbsp;&nbsp;- 先去掉 ANSI 样式；文本里嵌着的 JSON 对象或数组按键名处理，包括日志前缀后面跨行的对象与嵌套在字符串里的 JSON：只遮敏感键下的字符串，计数与布尔值保留；这些 JSON 一律按脱敏后的结构重新写出，不照抄原文，因为重复的键解码后只剩最后一个值，原文里前面的值可能就是凭据；<br>&nbsp;&nbsp;- 其余按文本处理：PEM 私钥整块遮蔽；疑似凭据的键（含 Authorization、API key，键名可以带任意层转义的引号）后面的值一律遮到行尾，连同后面缩进的续行；值在本行确定不了结束时（空值、以 `{` `[` 开头、以逗号或反斜杠结尾、YAML 块标量（`|` `>` `|2-` 等，可以带 # 注释）、引号没在本行闭合），遮蔽这条输出的其余部分，所以每行带前缀的多行日志、隔着空行的对象也不会漏；常见的令牌前缀也会遮蔽；<br>&nbsp;&nbsp;- 事件摘要中的错误信息先脱敏再截断，`final_error` 同样脱敏。<br>原始记录不改动：派遣的事件流与 stderr 在本机被 Git 忽略的 `.agent/runs/` 中；smoke 的原始日志在系统临时目录的 `pi-smoke-*` 中，成功且没有 `--keep` 时删除 |
| branch 到最后一步才报 Git 身份缺失 | 用 `git var GIT_AUTHOR_IDENT` 与 `GIT_COMMITTER_IDENT` 判定，与 commit-tree 同一套规则。<br>- doctor 提前给出备注，并记录 `repository.git_identity`；<br>- branch 在按补丁重建候选树、写任何 Git 对象之前拒绝，并列出可用的环境变量 |
| 候选提交自动附上配置中的 Claude 署名，与 Codex 规划端不符 | branch 新增两个参数：<br>- `--trailer "Key: value"`：可重复，追加在配置的尾注之后；<br>- `--no-config-trailers`：去掉 dispatch.config.json 的固定尾注。<br>尾注含回车、换行等控制字符时报用法错误，配置中的尾注同样校验；标题中的换行合并成空格，主题行始终是一行 |
| 提权命令列表漏了 `verdict` | `verdict` 会重新快照候选，要写 Git 对象。AGENTS.md、dispatch-pi、README、`.codex/config.example.toml` 的列表都补上 `verdict`，并补上 `smoke`：它在系统临时目录中运行，并联网调用模型。只改 `.agent/runs/` 中状态的 `mark` 列入可以在沙箱内运行的命令 |
| PowerShell 把 `wait` 的退出码 3 显示成 1 | 文档写明在 PowerShell 中用 `…; exit $LASTEXITCODE`，并说明 `python scripts/pi_dispatch.py` 与 bash 入口等价 |
| 沙箱内 pytest 访问共享临时目录，报 WinError 5 | AGENTS.md 写明两种做法：把测试临时目录放进工作区，或在沙箱外运行。前者先 `mkdir -p .agent/runs/_tmp`，再用 `--basetemp=.agent/runs/_tmp/pytest`：<br>- pytest 不会创建上级目录；<br>- `.agent/runs/` 被 Git 忽略，不会改变主工作区的指纹；<br>- pytest 每次运行前会清空 basetemp，只能指向专门的目录 |
| 只补测试的任务，baseline 只能说明“缺用例”，不能证明测试有效 | plan-task 按检查的形态写：<br>- 只选中新增测试节点的检查写“基线应失败”，并写明原因是缺用例；<br>- 运行已有测试文件或整个套件的检查照常通过，按回归保护写；<br>- 测试的有效性一律用变异证明：在 DoD 中列出必须抓住的最小变异，验收时用 `mutate` 核对 |
| prepare 提示“在 worktree 中按项目规则准备依赖”，与 dispatch-pi 的要求不一致 | 提示改为与技能一致：出新版本合同补上 setup，再重新 prepare；不在 worktree 里手工准备，否则 `check --fresh` 无法复现 |

**用真实历史回放**：用 WoMovieSubCheck 的 50 个历史 attempt，对比 2.0.0 与 2.1.0 的事件摘要。
- 工作目录外的临时路径用法有 67 处，分布在 19 个 attempt 中。多数是执行器在 `python -c` 检查里用 `tempfile.mkdtemp()` 建了目录却没有删除，这正是新规则要提示的。
- 屏蔽工作目录之前，这个数字是 270 处：执行器用绝对路径 cd 进自己的 worktree，也被当成了临时目录。
- 可疑命令从 1 条变为 2 条，多出的是原来被豁免的 mktemp 删除。
- 歧义提示从 48 处变为 49 处：否定前缀收紧后，“These aren't strictly contradictory”这类带保留的说法会提示。

**自测中发现的既有缺陷**：在 Windows 上，`branch` 生成的提交说明是 CRLF 换行。
- 原因：说明文件用文本模式写入，commit-tree 原样写进提交对象。
- 修正：改为按字节写入，并加了回归测试。
- 影响：WoMovieSubCheck 的 94 个可达提交里没有 CRLF 的提交说明。

**Codex 审查**：用本机 Codex CLI 0.156.0（只读沙箱）审查，原文与逐条处理见 [docs/Codex审查-2.1.md](docs/Codex审查-2.1.md)。
- 第一轮结论为 REVISE，提出 12 条发现，全部核实成立。两条高严重度：
  - 歧义过滤会漏掉明确发现的矛盾；
  - 临时目录的“已清理”判定会被不执行的删除骗过。更严重的是，`T=$(mktemp -d >/dev/null; printf %s src); rm -rf "$T"` 这种删源码的命令，也会被当成清理临时目录。这个漏洞从 1.2.4 起就存在。
- 第二轮复核：12 条中 8 条已修正、4 条部分修正，另有 6 条新发现。
- 第三轮复核：第二轮的 10 项中 3 项已修正、7 项部分修正，另有 8 条新发现。当时换成了白名单式的 bash 语句切分。
- 第四轮复核：15 项中 4 项已修正、11 项部分修正，另有 10 条新发现（8 条中、2 条低）。例如：
  - 赋值后面接管道或 `&`，其实是在子 shell 里执行；
  - `printf -v "T"` 与 `command exit` 能绕过检查；
  - heredoc 的结束词只匹配了前缀；
  - 相邻句子的否定其实在说别的。
- 第五轮复核：减法去掉的各项都判为“已不适用”，Codex 另核对了 25 条历史反例，确认没有因此漏掉提示。剩下的三处另有 5 条中、1 条低的发现，都改成了最保守的写法：
  - 路径屏蔽的左边界、引号拼接与带空格的参数；
  - 否定前缀跨越任意字符；
  - “no. 4”这类编号与换行续写被当成否定答案；
  - 多层转义的 Authorization 与含反斜杠的值漏遮。
- 第六轮复核：标出两条阻止发布的问题，一并修正：
  - 常见日志格式下的脱敏缺口：日志前缀后的多行 JSON、`API key` 的写法、键名后的 ANSI 样式、折行的 Digest；
  - 上一轮引入的回归：`>/tmp/x` 这样不带空格的重定向漏提示。
  另有两条不阻止发布的低严重度问题，也已修正：路径屏蔽的少见写法（引号前的拼接、转义的引号、变量），以及双重否定与 `None.__class__` 这样的句点。
- 第七轮复核：只剩一条阻止发布的问题：每行带前缀的多行日志、不缩进的 PEM 私钥、隔着空行的续行仍会漏遮。改为值在本行确定不了结束时遮蔽输出的其余部分，PEM 整块遮蔽。另有四条不阻止发布的低严重度问题，也已修正：
  - JSON 扫描的平方级耗时：只在像 JSON 开头的位置尝试解析，占位符一次还原；
  - 反斜杠转义的空白；
  - 两种双重否定；
  - NUL 与占位符的碰撞。
- 第八轮复核：结论为 PASS。Codex 认为“遮蔽其余部分”损失的诊断细节可以接受：退出码、模型行数、认证结果等独立记录仍然保留。另有三条不阻止发布的低风险残余，提交前一并修正，并请 Codex 针对这三处做了第九轮确认：
  - YAML 块标量（`password: |-`）的值在下一行；
  - `[2026-09-23 12:34:56]` 这样的时间戳被当成 JSON 数组候选，长日志变慢；
  - 深度过大的完整 JSON 在按结构脱敏时仍会抛出 RecursionError。
- 第九轮确认：指出第八轮收尾时顺带加入的“没有需要遮蔽的 JSON 照抄原文”引入了回归：重复的键解码后只剩最后一个值，原文里前面的凭据会原样保留。已撤回这一改动；YAML 块标量补上带注释与数字在前的写法。随后请 Codex 做了第十轮确认。
- 第十轮确认：结论为 PASS。另指出一条不阻止发布的低风险问题：重新写出 JSON 时，原文里转义的孤立代理码点会变成按 UTF-8 写不出去的字符，让预检的写出步骤异常退出。已改为恢复成 JSON 的 Unicode 转义，并补回归测试。
- 各轮发现全部核实成立。

**结论是做减法**：四轮下来，这几处检测总能被构造的写法绕过。它们只是给验收端的提示，想在提示阶段替复审判断“已清理”“只是在检查”，得不偿失。历史回放也显示，被删掉的豁免几乎没有省下提示：mktemp 删除豁免只起过一次作用，“已清理”降为备注在真实数据里也只有一处。所以：
- 去掉“已清理”判定与 1.2.4 的删除豁免，连同为它写的 bash 语句切分；
- 去掉“只是在检查”的排除；
- 保留确定性高的部分：路径屏蔽、紧跟在关键词后面的独立否定答案、脱敏。

每处修正都有回归测试。在副本上逐个退回修正做变异验证，48 个变异全部被测试抓住。自测从 199 项增加到 235 项。

## 2.0.0（2026-09-23）：规划端通用化，同时支持 Claude Code 与 Codex；规则统一到 AGENTS.md

| 变动 | 说明 |
|---|---|
| **AGENTS.md 成为唯一的规则文件，删除 CLAUDE.md** | 原 CLAUDE.md 的规划端规则、`.claude/rules/agent-files.md` 的 `.agent/` 目录规则都并入 AGENTS.md。开头新增“角色判定”：收到 `TASK:` 合同的是 Pi 执行器，只适用执行器一节；其余情况是规划端。<br>- Codex 与 Pi 原生读取 AGENTS.md；<br>- Claude Code 2.1.277 起在没有 CLAUDE.md 时原生读取；<br>- 仓库另有 CLAUDE.md，或 Claude Code 不能原生读取时，用一行 `@AGENTS.md` 导入。<br>AGENTS.md 约 8.5 KB，低于 Codex 默认的 32 KiB 读取上限 |
| **技能的唯一来源改为 `.agents/skills/`** | Codex 原生读取这里的技能，Claude Code 只读 `.claude/skills/`，所以新增 `sync-adapters [--check]`：<br>- 把四个 PI-Kit 技能整目录复制过去；<br>- `--check` 只比较，不一致时退出 1；<br>- 不碰仓库自己的其他技能。<br>Pi 也会发现 `.agents/skills`，但调度器启动执行器时本来就带 `--no-skills`，执行器看不到规划端技能。用 `codex debug prompt-input` 实测（Codex 0.156.0）：四个技能与 AGENTS.md 全文都被读入 |
| **技能正文不再绑定 Claude Code** | 技能之间按名称引用；两个工具的调用写法写在 AGENTS.md 与 README 中（Claude Code `/名称`，Codex `$名称`）。`$ARGUMENTS` 后加了一句说明：它在 Codex 中不会被替换，参数就是用户调用技能时附带的文字。check-pi-env 与环境模板同时记录两种规划端的事实（版本、模型与推理强度、规则文件、技能、Codex 的沙箱 / 审批 / 项目信任） |
| **独立复审要求与工具无关** | 复审要求移到 `review-pi/independent-review.md`，并补充“合同列出的每条规则是否都有测试把守”以及读取变异检查记录。<br>- Claude Code：`pi-reviewer` 子代理改为薄适配层，读取这份要求；<br>- Codex：用 `codex exec --sandbox read-only` 另开会话 |
| **新增 `wait <run-dir> [--timeout 秒]`** | Codex 没有后台完成通知。`wait` 阻塞等待 attempt 结束（缺省最多 540 秒）：结束时退出 0，仍在运行时退出 3 并打印进度；刚在后台启动、还没开始的 attempt 最多再等 60 秒 |
| **Codex 的沙箱与配置** | `prepare`、`run`、`check`、`baseline`、`mutate`、`branch`、`cleanup`、`collect` 会写 Git 元数据（`.git` 下的 objects、worktrees、refs）或仓库之外的 worktree，`run` 还要联网。`workspace-write` 沙箱中 `.git` 是只读的，所以这些命令要批准在沙箱外运行。`validate`、`derive-json`、`status`、`metrics`、`wait`、`doctor`、`sync-adapters` 可以在沙箱内运行。新增的 `.codex/config.example.toml` 只设置推理强度与审批策略的项目默认值 |
| **调度器** | 受保护路径加入 `.codex/**`，执行说明与机器合同摘要同步列出 `.agents/`、`.claude/`、`.codex/`。doctor 同时记录 `claude` 与 `codex` 的版本，并提示以下情况：<br>- 有 CLAUDE.md 却没有 `@AGENTS.md`；<br>- AGENTS.md 超过 32 KiB；<br>- Claude Code 技能副本不一致；<br>- 仍是 1.x 布局。 |
| **升级说明** | README 新增“从 1.x 升级”：移动技能目录、合并规则、删除 CLAUDE.md、运行 `sync-adapters`。合同格式、证据目录与状态没有变化，已派遣的合同与证据不受影响 |

**Codex 审查**：用本机 Codex CLI 0.156.0（gpt-6-astra，只读沙箱）做了六轮审查，原文与逐条处理见 [docs/Codex审查-2.0.md](docs/Codex审查-2.0.md)。
- 第一轮全面审查，提出 8 条发现；
- 第二至第五轮复核上一轮的修正，各发现一处遗漏；
- 第六轮结论为 PASS。

全部发现都已核实成立并修正：
- `sync-adapters` 删除旧副本前，校验解析后的路径确实在仓库内；`.claude`、`.claude/skills` 或技能目录是链接时拒绝，以免删到仓库外或删掉 `.agents/skills` 中的源；读取时也不跟随链接；
- 升级步骤补上 `mkdir -p .agents/skills`，并要求先把 CLAUDE.md 与 `agent-files.md` 中项目自己的规则迁进 AGENTS.md，再删旧文件；
- 不再说项目配置能免去审批：`workspace-write` 沙箱中 `.git` 只读，写 Git 元数据的调度命令都要批准在沙箱外运行；
- `wait` 遇到 state.json 缺失或损坏时退出 1，不再报“已结束”；
- `sync-adapters --check` 在部分技能缺少源文件时也判为失败；
- 只用 Codex、没有装 Claude Code 副本时，doctor 不再报“副本不一致”；
- review-pi 中遗留的 `/dispatch-pi` 写法改为技能名加链接；
- 遍历技能目录时跳过 Windows junction 与其他重解析点：Python 3.12 之前 `islink` 认不出 junction；
- 读取源目录、读取副本、写入与删除副本，一律先确认路径与其上级都不是指向仓库之外的链接；
- doctor 的规则文件检查：CLAUDE.md 链接到本仓库的 AGENTS.md 属于合法做法，不提示；指向仓库之外时只提示，不读取。

每处修正都有回归测试：链接类的测试用真实的 junction 与符号链接，并做了变异验证，退回旧写法时测试失败。自测从 164 项增加到 199 项。

## 独立为 PI-Kit 仓库（2026-09-23，工具版本仍为 1.3.0）

| 变动 | 说明 |
|---|---|
| 套件从 `claude-pi-kit/` 目录移植为独立的 git 仓库 PI-Kit | 调度工具、Skill、模板与自测原样保留，与 1.3.0 逐字节一致 |
| 新增 `docs/` | 收入《方案.md》（设计来源）、《审阅意见.md》（审阅与改动理由）和《Codex审查报告.md》（原文；原文中指向审查时本机文件的链接改成了纯文本路径）。README 与本记录中原来指向“上一级目录”的引用，改为指向 `docs/` |
| 新增 `gitattributes.append.txt`，安装步骤补一条 | 实机反馈：Windows 上开启 `core.autocrlf` 时，`dispatch-pi.sh` 检出后是 CRLF 换行，bash 无法执行。WoMovieSubCheck 用 `*.sh text eol=lf` 解决了这个问题。本仓库自己的 `.gitattributes` 也这样设置 |
| 新增 `.gitignore` | 忽略 Python 缓存 |

## 1.3.0（2026-09-23）：mutate 子命令（变异检查）

| 反馈 | 改进 |
|---|---|
| 连续三批复审，规划器都手写一次性脚本做变异检查：把实现改坏一点，看新增测试会不会失败。export-command 的 11 个变异漏掉 1 个（测试只用了绝对路径），negation-coverage 的 9 个变异漏掉 1 个（合同写了去重，测试清单却没有重复词的用例）。这两处缺口 fresh 检查都看不出来。手写脚本还要自己处理 CRLF、恢复文件、记录结果，Bash heredoc 又会吞掉反斜杠 | 新增 `mutate <run-dir> --spec <清单.json>`：<br>- 在干净副本（与 `check --fresh` 相同）上先运行一次不变异的 command，必须通过；<br>- 再逐个套用变异，失败记为抓住、通过记为漏掉，锚点出现次数不符记为跳过；<br>- 每次运行后恢复原文件，记录写到 `mutations/NN/`，执行 worktree 与候选都不受影响；<br>- 清单用 JSON 写，按 LF 书写即可，CRLF 文件自动处理 |
| 漏掉的变异该怎么处理，原来没有写下来 | review-pi 新增 mutation-check.md：怎样为每条规则选最小变异，以及漏掉的四种原因（合同遗漏、执行器少写、等价变异、输入观察不到）各自的处理。复审模板加一行“变异检查”；plan-task 要求测试清单覆盖每一条规则（含去重、排序、边界） |

## 1.2.7（2026-09-23）：分支主题行不重复 task-id；过长标题的提示；重新标定“长时间没有工具调用”

| 反馈 | 改进 |
|---|---|
| apply-patch 的集成提交主题是 `apply-patch: apply-patch：补丁校验……`：合同标题本身以 task-id 开头，`branch` 又加了一次前缀 | `branch` 的主题行：标题已以 task-id 加冒号（半角或全角）或空格开头时原样使用，否则仍写 `<task-id>: <标题>` |
| export-command 开跑两分多钟、19 次工具调用后，`status` 就提示“长时间没有工具调用（3160 个增量）”，其实执行器只是在正常地规划实现。用 45 次实机运行的事件流标定：两次工具调用之间的长段几乎全是思考增量；正常运行中最长的一段在 4200 个以内；超过 1 万的 4 次都是用时最长的运行（1200 秒以上），其中 2 次超时 | 阈值从 2000 改为 6000，dispatch-pi 的说明同步写明标定依据 |
| export-command 的合同第一次 derive-json 时忘了 `--title`，标题取了 Goal 的整个第一段（约 100 字），要到查看 JSON 时才发现，只好加 `--title … --force` 重新生成 | 没给 `--title`、取自 Goal 的标题超过 60 字时，derive-json 打印 NOTE，提示标题会成为提交主题行并给出改法；不影响退出码。plan-task 与合同指南写明标题的用途 |

## 1.2.6（2026-09-23）：删除缓存目录不再列为可疑命令

| 反馈 | 改进 |
|---|---|
| job-cli 的执行器在收尾时运行 `rm -rf subtitle_qa/__pycache__ tests/__pycache__`，被列为“递归或强制删除”。1.2.4 起摘要会显示命中的那一行，一眼就能看出删的只是被 Git 忽略的缓存目录，但复审者每次仍要专门说明一遍 | 每个 rm 目标都是工作副本内的缓存目录时，改记在“备注”：<br>- 目录名为 `__pycache__`、`.pytest_cache`、`.mypy_cache`、`.ruff_cache`、`.hypothesis`；<br>- 路径是相对路径，不含 `..`、`~` 或变量。<br>混有任何其他目标时仍列为可疑命令。用这次的真实命令回放，识别正确 |

## 1.2.5（2026-09-23）：长时间没有工具调用的提示，超时但候选完整时的收尾

| 反馈 | 改进 |
|---|---|
| 规划器把需要用户拍板的设计说明写进了 `.agent/designs/`（复数）。调度器缺省的规划路径是 `.agent/design/**`，dispatch-pi 的说明却没有列出这一项，于是无从知道应当放在哪里 | dispatch-pi 的说明列全缺省规划路径；plan-task 第 3 节写明设计说明放在 `.agent/design/<主题>.md`，逐条列出需要用户决定的问题与建议 |
| 对齐 DP 的性能改写（F5）：cProfile 显示候选枚举占七成时间，分阶段计时却显示它只要 0.07 秒；真正的瓶颈是精确分数沿路径累加后，分母变成上千位的大整数 | plan-task：改写算法、又要求结果不变时，先在副本上完成新算法，在测试里保留原实现的逐字副本作为标准答案，用大量带平局的随机用例与接近真实的数据逐项比对；性能问题先分阶段计时，Windows 上的 cProfile 会严重放大调用多的函数 |
| 稀疏 DP 的合同已经给出完整算法与取舍规则，执行器仍用约 950 秒、十几万字符从头推导等价性，中途几次推翻合同里正确的规则。写完代码与测试后来不及写报告就超时了。规划器是从 `status` 的 `live:6t 945s`（工具调用次数长时间不动）才察觉的 | `status` 对运行中的 attempt 统计上次工具调用之后的消息增量，达到 2000 个时提示“长时间没有工具调用（N 个增量）”。plan-task：规划器已有验证过的实现时，合同写明“不需要重新证明，以比对测试为准”，必要时直接写进实现；时限按实现、测试与运行估算 |
| 这次超时的候选其实已经完整（fresh 检查全部通过），缺的只是执行报告。排障表原来只建议出一个只收尾的 vN+1 | 排障表与 review-pi 增加第二条路径：候选完整时，由规划器逐项复审代替报告，直接集成返工提交并标 SUPERSEDED，不必为一份报告再派一轮 |

## 1.2.4（2026-09-23）：可疑命令写明命中的那一行

| 反馈 | 改进 |
|---|---|
| 摘要把一条“递归或强制删除”列入复审需要关注，但只显示命令的前 300 个字符：那是一段写配置文件的 heredoc，真正的 `rm -rf` 在第 50 行（最后一行），摘要里看不到。复审者只好到 events.jsonl 里找出完整命令 | 可疑命令记下命中所在的行（过长时截取命中附近）、它是命令的第几行、事件流行号；摘要写成“命令第 50 / 50 行 `rm -rf …`（事件流第 N 行）” |
| 找到后发现删除的是这条命令开头用 `TMPD="$(mktemp -d)"` 新建的临时目录，完全无害；执行器常这样清理临时目录 | 删除本条命令用 mktemp 新建的临时路径时，改记在“备注”，不列为可疑命令。判断从严：<br>- 变量只有这一次赋值，也没有 `read` / `for` / `printf -v` 这类按名字改写它的写法；命令含 `eval` 或 nameref 时一律不算；<br>- 每个 rm 目标都恰好是变量本身。<br>带子路径（`"$TMPD"/x`）、结尾斜杠或额外目标都仍按可疑命令处理：mktemp 失败时变量为空，子路径会落到根目录。<br>用这次的真实命令回放：其中嵌的 python 代码以字符串形式提到变量名，不影响判断，识别为临时目录清理 |

## 1.2.3（2026-09-23）：单值字段可以带括号说明

| 反馈 | 改进 |
|---|---|
| 合同写了 `- dependency_changes: forbidden（只加命令入口，不增删依赖）`，想告诉执行器：给 pyproject.toml 加命令入口不算依赖变更。derive-json 把整段文字都当成了取值，校验报“必须是 forbidden 或 allowed”，还报 Markdown 与 JSON 不一致，而 JSON 正是从这份 Markdown 生成的。列表字段写“无（…）”一直可以正常解析，单值字段却不行 | Identity 各项与 `dependency_changes` 只取括号前的值，全角、半角括号都可以；说明文字保留在 Markdown 中给执行器看。合同指南补充这条写法 |

## 1.2.2（2026-09-23）：记录“候选已并入后续提交”

| 反馈 | 改进 |
|---|---|
| 某任务第二次 attempt 判了 REVISE 且预算用尽，剩余测试由规划器补齐后集成。调度工具仍把它当作“待集成”，为其他任务 prepare 时一直提示范围重叠；`mark INTEGRATED` 又只接受通过验收的候选 | `mark` 新增 `SUPERSEDED`：<br>- 用于已结束、尚未集成、但候选已经并入后续提交的 attempt；<br>- 必须带 `--ref`（包含该候选的提交）与 `--reason`（由谁、怎样收尾）。<br>SUPERSEDED 不算待集成。review-pi 的“后续动作”写明规划器直接补齐时的做法 |
| 合同检查行写着“（必要，基线应失败）”，执行器在推理中反复斟酌这是否与“期望退出码 0”矛盾，最后写进 limitations | 执行说明的机器合同摘要把基线期望写成完成后的要求：“基线上预期失败（用来证明修复），你完成后它必须通过” |

## 1.2.1（2026-09-23）：范围重叠只看最新 attempt

| 反馈 | 改进 |
|---|---|
| 某任务的 attempt-001 判了 REVISE，返工后 attempt-002 已经集成；为其他任务 prepare 时，仍提示“与未集成的 attempt-001（REVISE）改动范围重叠” | 每个任务只看最新的 attempt：返工后的新 attempt 代表这个任务的现状，旧 attempt 的候选已经并入返工基线；最新 attempt 已集成或放弃时不再提示 |
| 执行器在第 230 秒把一次 edit 写成了正文里的 `<tool_call><function=edit>…`，Pi 没有执行它，回合随之结束。事件流完整、stopReason=stop，摘要只显示“执行报告：no_json”，看起来像是执行器忘了写报告 | 最终 assistant 消息的正文含有工具调用标记时，记为执行完整性问题，G1 不通过，并说明“模型把工具调用写成了文本，Pi 没有执行，运行没有做完”。排障文档说明怎样处理 |

另外补充了一条对齐任务的实机经验（写在 plan-task 中）：用来证明“不会揉大组”的测试若都用等长的对子，恰好掩盖了代价公式在时长不等时的问题。设计代价或阈值时，要用参差的真实形态数据做一次模拟。

## 1.2.0（2026-09-23）：合同矛盾的声明与核对

| 反馈 | 改进 |
|---|---|
| 执行器在推理中发现合同的行为说明（“按 finding_id 去重”）与步骤（“该 cue 只有一条”）互相矛盾，写下 “This is ambiguous” 后自行选了前者，把测试写成断言两条，并把 DoD 标为 done。报告只在 limitations 里写了一句“按合同不去重”，独立复审代理通读事件流才发现 | 执行说明第 6 条写明：合同内部前后矛盾也属于需求冲突，不要自行选定一种解释当作完成。<br>- 报告新增 `contract_conflicts` 字段：两处原文、暂时采用的做法、理由；相关 DoD 标为 blocked；<br>- AGENTS.md 模板同步这一条 |
| 验收端只能靠通读事件流发现这类情况 | 调度器扫描执行器的推理与回复，把提到“歧义 / 矛盾”的摘录记入 `events-summary.json` 的 `ambiguity_mentions`：<br>- 报告没有声明时列入“复审需要关注”，已声明时记为备注；<br>- `verdict` 打印 G3 提示，报告列出的矛盾要逐条裁定。<br>以下情况不计入：否定说法（no ambiguity、没有矛盾），附近没有提到合同、规范或步骤的领域用语，以及合同正文自己反复使用的词（如对齐状态 ambiguous） |
| 回看已有的 21 个 attempt：超时的 rule-source-conflict v1 有 13 处提及，它正是在一句含义不明的合同上推演了约 10 分钟 | 同上；排障文档说明两类提示的处理方式 |
| 探针在基线上失败，只说明第一条断言有效；后面的断言在基线上根本没运行到，写错了也看不出来 | plan-task 与合同指南：<br>- 多段探针派遣前在草稿修复上跑一次；<br>- “某条 finding 由哪些模块产生”要实测；<br>- 同一行为只在 Behavior contract 写一次 |
| 返工期间，同批的其他任务已经合入集成分支 | plan-task 的返工一节：可以把返工提交重放到当前 HEAD，再作为新版本的 base_sha；通过后集成分支快进即可 |

实机验证：pipeline-core v2 按上述做法出合同（返工提交重放到当前 HEAD；探针先在草稿修复上验证），一次通过。

其他：
- `TOOL_VERSION` 升为 1.2.0。
- 自测从 124 项增加到 136 项。

## 1.1.2（2026-09-22）：超时收尾

| 反馈 | 改进 |
|---|---|
| 执行器在一轮推理里推演了约 10 分钟才开始改文件，写完代码与测试时已到 1200 秒时限，被终止前没有自检，也没有执行报告（候选本身在干净副本上全部通过） | 执行说明的“运行事实”写明：<br>- 执行器看不到已用时间，开始时用 shell 记下时间并定期对比；<br>- 用时过半前应开始修改文件；<br>- 剩余不到五分之一时停止扩展，先运行检查并写报告 |
| 超时但候选完整时，怎样收尾没有说明 | 排障文档补充：先 `check --fresh` 验证并复审；判 REVISE（TIMEOUT）；用 `branch --rework` 取得返工基线，出只收尾的新版本合同 |

## 1.1.1（2026-09-22）：第二轮实机反馈

| 反馈 | 改进 |
|---|---|
| 执行器为了对比基线行为，用 `git stash push` 暂存自己的改动，跑完探针再 `git stash pop`。这次恢复成功了，但一旦失败，候选就会丢失 | 执行说明第 4 条与 AGENTS.md 模板写明：不要用 git stash / checkout -- / reset 临时撤掉自己的改动；需要对比时在报告中说明，由验收端用 `baseline` 在基线副本上运行 |
| 规划器的设计说明放在 `.agent/design/`，运行期间写入会被报成“规划路径之外的变化” | `planner_paths` 缺省值加入 `.agent/design/**` |
| `baseline` 对 `expect_on_base` 为 any 的回归测试套件提示“基线上已通过”，在每个合同上都出现 | 提示改为“基线上已通过（回归保护属正常；若用来证明修复，标注 expect_on_base: fail 并改写）” |

实机验证：1.1.0 的规划路径分类在第四批中按预期生效。规划器在运行期间写入的合同只出现在“备注”，没有进入“复审需要关注”。`derive-json`、`baseline`、prepare 的运行提醒都在真实合同上用过。

## 1.1.0（2026-09-22）：根据实机反馈改进

来源：在 `WoMovieSubCheck` 上用真实模型 `step/step-5-preview`（thinking high）执行审核报告拆出的子任务，其中有 3–4 个任务的并行批次。下表每一项都对应一次实际遇到的问题。

| 反馈（实际发生的情况） | 改进 |
|---|---|
| 规划器在运行期间往 `.agent/plans/` 写下一个合同，摘要只会说“主工作区的 HEAD 或状态发生变化”，无法判断是谁改了什么 | 运行结束时比较前后两次内容树，在 `observations.json` 的 `main_repo_changes` 中列出变化的路径与 HEAD 前后值。<br>- 规划路径（`planner_paths`，缺省 `.agent/plans/**`、`.agent/reviews/**`、`.agent/*.md`）的变化只记为“备注”；<br>- 其他路径与 HEAD 的变化列入“复审需要关注”，并写进 G2 的门禁备注 |
| 执行器 4 次把 worktree 绝对路径中的 `pi-worktrees` 拼成 `pi-worktres`，edit / read 失败，摘要只显示“工作副本外路径” | 执行说明要求用相对于工作目录的路径，不要手写绝对路径。越界访问记录 `failed`（调用是否失败）与 `exists`（路径是否存在），摘要写成“调用失败，路径不存在，可能是手写绝对路径时拼错” |
| 执行器重新读取随消息附上的 plan.md（位于 attempt 运行目录），被报为越界访问 | 本 attempt 运行目录中的文件记入 `own_run_paths`，只在“备注”中提及；执行说明也说明两份文件已随消息附上 |
| `git stash list` 被报为“可疑命令（git 写操作）” | `git stash list/show` 与 `git tag -l/--list` 不再计入 |
| 用 Write 工具写合同时，`\u200e` 转义被写成了实际的 U+200E。Markdown 看起来与 JSON 一致，校验却报命令不一致，执行器也会读到不可见字符 | validate 对 Markdown 与 JSON 中的不可见格式字符（Unicode 类别 Cf）给出警告，写明行号与码点；文档建议探针里用 `chr(0x200E)` |
| 每个修复任务都要手工确认探针在基线上会失败，否则探针区分不了修复前后 | 新增 `baseline <plan-key>`：在基线副本上运行合同检查，不创建 attempt，也不计入预算，结果写入 `.agent/runs/<task-id>/baseline/NN/`。检查项可以声明 `expect_on_base: fail / pass`（Markdown 写“基线应失败 / 基线应通过”），不符时退出码为 1 |
| JSON 合同需要手工与 Markdown 同步，命令、正则里的反斜杠与转义很容易出错 | 新增 `derive-json <plan-key> [--title] [--force] [--print]`：按模板格式从 Markdown 生成 JSON，写完立即校验 |
| `validate .agent/plans/x.v1.md` 报“计划标识不合法”；`status <attempt 路径>` 显示“没有 attempt 记录” | `validate` / `prepare` / `baseline` / `derive-json` 接受 `.agent/plans/` 下合同文件的路径；`status` 接受 task-id.vN、task-id/attempt-NNN 或 attempt 路径，运行中的 attempt 显示工具调用次数与已用时间 |
| 并行批次需要人工保证各任务改动范围不重叠 | prepare 检查其他任务中尚未集成的 attempt，改动范围重叠时给出警告；有 attempt 正在运行时提醒不要改动主工作区 |
| 并行批次的集成方式（第一个快进，其余 cherry-pick）、复审时范围重叠的 `sed` 输出造成的误读、执行器漏掉合同列出的别名写法 | 写进 dispatch-pi 的“并行批次”与 review-pi 的复审经验 |

其他：
- `TOOL_VERSION` 升为 1.1.0。
- 自测从 97 项增加到 124 项。

## 1.0.0（2026-09-22）

- 从《方案.md》（见 `docs/`）提取并扩充的首个版本。
- Codex 审查的 18 条发现全部修正。
- 用模拟 Pi 完成端到端自测，97 项。
