# Codex 审查记录：2.0.0（规划端通用化）

- **审查工具**：OpenAI Codex CLI 0.156.0，模型 gpt-6-astra，本机默认推理强度，只读沙箱（`codex exec --sandbox read-only`），2026-09-23。
- **审查对象**：2.0.0 的改动（提交前的工作区）。
- **原文说明**：以下各轮为原文。其中指向本机文件的链接改成了纯文本路径；行号对应当轮的工作区，之后的修正会让行号漂移。
- **轮次**：共六轮。
  - 第一轮全面审查；
  - 第二至第五轮复核上一轮的修正，各发现一处遗漏；
  - 第六轮结论为 PASS。
- **处理**：所有发现都由规划端逐条核实后修正，见文末的“处理结果”。

## 第一轮：全面审查

结论：建议修正后再提交 2.0.0；四个技能已被 Codex 发现，但升级指引、同步边界和状态检查仍有缺陷。

发现列表，按严重度排序：

1. **高｜同步删除未校验真实路径边界**  
   **位置**：`scripts/pi_dispatch.py:3385`  
   **问题**：固定四个目录名不能保证删除发生在仓库内。  
   **证据**：如果 `.claude` 或 `.claude/skills` 是指向外部目录的符号链接／junction，`shutil.rmtree(target_dir)` 会沿父目录链接删除外部同名技能目录；这里没有解析真实路径或拒绝链接的检查。当前测试只覆盖普通目录。  
   **建议**：修改前校验源、目标及其父目录的真实路径，拒绝越界链接，并补充链接边界测试。  
   **把握**：较确定，依据静态分析，未创建链接复现。

2. **高｜升级步骤可能丢失项目自定义规则**  
   **位置**：`README.md:123`  
   **问题**：要求删除 CLAUDE.md，却没有要求先迁移其中的项目自定义内容。  
   **证据**：1.x 安装说明明确要求把 kit 规则合并进已有 CLAUDE.md；新升级步骤只处理协作规则，随后删除整个文件。下一步直接删除 `agent-files.md` 也有类似问题。  
   **建议**：明确先将仍适用的项目规则合并到 AGENTS.md，核对无内容遗漏后，才删除旧文件或保留导入行。  
   **把握**：确定。

3. **中｜示例配置不足以保证调度命令免审批运行**  
   **位置**：`README.md:98`、`.codex/config.example.toml:17`  
   **问题**：仅开放网络和外部 worktree 目录，不能解决所有沙箱写权限。  
   **证据**：Codex 的 `workspace-write` 对 Git 元数据有额外保护；`prepare` 在脚本第 2858 行执行 `git worktree add`，还需要修改主仓库 `.git/worktrees`。项目信任负责加载配置，不会取消这些保护。  
   **建议**：保留当前有效键名，但删除“配置后即可省去逐次批准”的保证，明确 Git 元数据操作仍可能需要沙箱外执行。  
   **把握**：较确定；未实际执行沙箱内 worktree 操作。

4. **中｜`wait` 把未知状态报告为已经结束**  
   **位置**：`scripts/pi_dispatch.py:3487`  
   **问题**：无法读取有效状态时仍返回成功。  
   **证据**：`get_state()` 在状态文件缺失或 JSON 无效时返回 `UNKNOWN`；内存探针得到退出码 **0** 和 `已结束：… · UNKNOWN`。  
   **建议**：仅对明确的结束状态返回 0；未知、损坏或不可读状态返回非零并说明原因。补充相应测试。  
   **把握**：确定。

5. **中｜缺少部分技能源文件时，漂移检查仍通过**  
   **位置**：`scripts/pi_dispatch.py:3438`  
   **问题**：`sync-adapters --check` 可能放行不完整的安装。  
   **证据**：内存探针隐藏 `review-pi` 源目录后，检查先打印缺失警告，随后宣称副本“一致”并返回 **0**；旧副本仍存在。新增测试只覆盖所有源都缺失的情况。  
   **建议**：检查模式在 `missing` 或 `drift` 任一非空时失败；补充单个源缺失的用例。  
   **把握**：确定。

6. **中｜升级移动命令缺少目标父目录准备**  
   **位置**：`README.md:122`  
   **问题**：典型 1.x 仓库不能直接照抄该命令完成移动。  
   **证据**：1.x 布局没有 `.agents/skills/`，本仓库 HEAD 也没有；`git mv` 不会自动创建目标的缺失父目录。  
   **建议**：移动前增加 `mkdir -p .agents/skills`，并给出四个技能的完整迁移命令。  
   **把握**：确定。

7. **低｜仅使用 Codex 的合法安装会被 doctor 报为漂移**  
   **位置**：`scripts/pi_dispatch.py:3425`  
   **问题**：与 README 中“.claude/ 只用 Codex 时不必复制”的说明矛盾。  
   **证据**：模拟未安装 Claude 副本时，`planner_file_notes()` 报告 19 处不一致并要求同步。  
   **建议**：区分“未安装 Claude 适配层”和“已安装但漂移”，增加仅 Codex 安装测试。  
   **把握**：确定。

8. **低｜共用技能正文仍残留 Claude 调用写法**  
   **位置**：`.agents/skills/review-pi/SKILL.md:83`  
   **问题与证据**：仍写着“见 `/dispatch-pi` 排障表”。  
   **建议**：改为“见 dispatch-pi 技能的排障表”，最好直接链接对应文档，再同步副本。  
   **把握**：确定。

本会话技能清单中，来自本仓库 `.agents/skills/` 的名称是：

- `check-pi-env`
- `plan-task`
- `dispatch-pi`
- `review-pi`

核对范围与限制：

- **已通过**：当前副本的 `sync-adapters --check`、Python 语法解析、示例 TOML 解析、`git diff --check HEAD`。AGENTS.md 为 **8,479 字节**。四技能实际被发现，说明现有 frontmatter 的 `argument-hint` 未阻止加载。
- **已核对**：本机 Codex **0.156.0** 的帮助支持 `exec --sandbox read-only -o`；本机 Claude Code **2.1.280** 内置说明支持“无 CLAUDE.md 时读取 AGENTS.md”的默认行为。角色判定及 `$ARGUMENTS` 的补充说明未发现直接冲突。
- **内存验证**：正常状态转换、PREPARED 默认 60 秒宽限及运行超时符合预期；这些探针没有写文件。
- **未运行**：`test_v2_planner_adapters` 和完整测试，因为当前沙箱只读，而测试会创建临时仓库。新增测试也未覆盖真实链接边界、autocrlf 检出循环和上述异常场景。
- **无法完成**：`codex debug prompt-input` 报 `Could not find home directory`；因此本次未取得新的 CLI 提示输入证据。
- 未执行真实派遣、独立模型复审或后台运行闭环；未验证 Claude 各提供商及遥测开关组合。全程未联网、未安装软件，也未修改、创建或删除文件。

## 第二轮：复核第一轮的 8 条修正

上一轮 8 条原始问题均已修复；另发现 1 项中等严重度遗漏。

| # | 结论 | 依据 |
|---|---|---|
| 1 | 已修复 | `scripts/pi_dispatch.py:3371` 比较真实路径与预期路径；`3413 行` 在删除前统一校验全部目标，阻止顶层链接导致越界删除。 |
| 2 | 已修复 | `README.md:128` 要求先迁移、核对 CLAUDE.md 中的定制规则；132 行同样保护 `agent-files.md` 的定制内容。 |
| 3 | 已修复 | `AGENTS.md:56`、`config.example.toml:5` 明确 `.git` 只读及越出沙箱所需审批；README 与 dispatch-pi 技能说明一致。 |
| 4 | 已修复 | `scripts/pi_dispatch.py:3528` 对非明确结束状态返回 1，UNKNOWN 不再报告“已结束”。 |
| 5 | 已修复 | `scripts/pi_dispatch.py:3480` 使用 `drift or missing`，部分技能源缺失也返回失败。 |
| 6 | 已修复 | `README.md:124` 已在移动技能前加入 `mkdir -p .agents/skills`。 |
| 7 | 已修复 | `scripts/pi_dispatch.py:3449` 判断是否安装副本，仅在已安装时报告不一致。 |
| 8 | 已修复 | `review-pi/SKILL.md:79`、83 行已改为技能名称及文档链接；生成副本也一致。 |

另有一项遗漏：

**中：目录遍历仍会跟随 Windows junction。**

- **位置**：`scripts/pi_dispatch.py:3351`、3355 行。
- **问题**：`is_symlink()`、`os.path.islink()` 不识别 junction，`os.walk(..., followlinks=False)` 仍会进入它。源技能目录中的 junction 因而可以把目录外的内容带入复制集合。
- **证据**：本机现有 junction 的元数据确认 `is_symlink=False`、`is_junction=True`；内存模拟中，junction 子目录里的 `refs/outside.md` 被 `_tree_files` 收录，随后会由 `3424 行` 的复制循环写出。现有 `测试:1229` 只覆盖顶层目标链接，未覆盖这种情况。
- **建议**：在遍历前显式拒绝或跳过 junction，保持 Python 3.8 兼容，并补充源目录、嵌套 junction 的回归测试。
- **把握**：高。

本轮全程只读，未重跑会创建文件的 189 项自测；已完成源码与测试审阅、19 种 `wait` 状态的内存检查及全部技能副本逐字节比对，`git diff --check HEAD` 通过。

结论：暂不建议提交，先修复 junction 遍历遗漏并补齐回归测试。

## 第三轮：确认 junction 修正

1. **完整性：仍有中等遗漏。** 根、子目录和文件中的 junction 已过滤，但未检查根的祖先。若 `.agents/skills` 本身是外部 junction，技能目录仍会被视为普通目录，外部内容进入 `adapter_drift`、`sync_adapters` 的读取集合；内存模拟收录了 `outside.md`。依据：`pi_dispatch.py:3376`、`3418`、`3441`。建议读取前校验源路径及祖先的解析位置，并补回归。`claude_skill_target` 已保护写入目标及其祖先，但不保护源：`3396`。

2. **兼容性与误判：未发现新增问题。** Python 3.8–3.11 的属性回退、3.12+ 的 `isjunction`、POSIX 的 `islink` 分支合理；普通目录不会因目录属性被误判。依据：`pi_dispatch.py:3355`、`3362`。

3. **提交结论：REVISE，建议补齐祖先入口后提交。** 新测试有效，但只覆盖技能内部 junction：`test_dispatch.py:1257`、`1265`。

本轮仅做源码审查和只读内存探针，未重跑会写文件的全量或变异测试。

## 第四轮：确认源目录上级的修正

1. **修正尚不完整。** 源侧已校验，但 ``scripts/pi_dispatch.py:3436`` 仍直接读取副本。`.claude` 或 `.claude/skills` 指向外部时，doctor 和 `sync-adapters --check` 仍读取外部内容；内存探针复现了内容相同时检查返回成功。此处应调用 `claude_skill_target`。

2. **未发现所列路径误报。** ``scripts/pi_dispatch.py:3395`` 对仓库根和实际路径分别解析，再用 `normcase` 比较。只读实测大小写、8.3 短名均通过；仓库根链接的内存模拟也通过。

3. **结论：REVISE，暂不建议提交。** 现有目标链接测试仅检查拒绝同步及未写入外部目录，不能发现上述提前读取问题（``tests/test_dispatch.py:1243``）。补齐副本读取校验及“拒绝前未读取外部内容”的回归测试后再提交。

本轮未改动文件、未联网、未调用模型，也未重跑会落盘的自测。

## 第五轮：逐一列出文件系统入口

**暂不建议提交（REVISE）**。第四轮修复有效，但 doctor 仍有未经链接校验的内容读取入口。

以下逐项列出文件系统入口；“已校验”指当前路径检查，不代表能抵御并发换链。

| 入口 | 链接校验与风险 | 依据 |
|---|---|---|
| 仓库发现：`resolve`、Git 元数据读取 | 规范化仓库根，作为后续校验基准；不写入 | `pi_dispatch.py:868` |
| 路径解析：`resolve` | 校验本身，比较真实位置与预期位置 | `pi_dispatch.py:3396` |
| 链接探测：`islink/isjunction/lstat` | 校验本身；只读取元数据 | `pi_dispatch.py:3355` |
| 技能源读取 | 经 `skill_source` 校验自身及父路径；未见静态越界 | `pi_dispatch.py:3433`、`3456` |
| 技能副本读取 | 漂移检查现经 `claude_skill_target`；同步读取前也已校验全部目标 | `pi_dispatch.py:3437`、`3453` |
| 目录判断、遍历：`is_dir/os.walk` | 调用前根路径已校验；递归前过滤子目录链接及 junction | `pi_dispatch.py:3376` |
| 文件判断、读取：`is_file/read_bytes` | 先检查文件链接，再判断和读取；链接被跳过 | `pi_dispatch.py:3383` |
| 删除前判断：`target_dir.exists` | 使用预先校验的目标路径 | `pi_dispatch.py:3462` |
| 删除：`rmtree` | 删除根已校验；内部链接依赖标准库处理，未见静态越界删除 | `pi_dispatch.py:3463` |
| 建目录：`mkdir` | 使用已校验目标及遍历生成的相对路径；旧目录先删除 | `pi_dispatch.py:3466` |
| 写文件：`write_bytes` | 同上；未见静态越界写入 | `pi_dispatch.py:3467` |
| doctor：`AGENTS.md.is_file/stat` | **未校验**；可跟随链接读取外部元数据，不读取正文 | `pi_dispatch.py:3476` |
| doctor：`CLAUDE.md.is_file/read_text` | **未校验，有内容越界读取风险**；外部文件链接会直接被读取 | `pi_dispatch.py:3485` |
| doctor：安装状态 `exists` | **未独立校验**；源缺失时漂移检查跳过对应目标，可能跟随链接探测并漏报 | `pi_dispatch.py:3421`、`3434` |
| doctor：旧布局 `SKILL.md.is_file` | **未校验**；源全部缺失时可能把外部链接目标识别为旧布局，仅读取元数据 | `pi_dispatch.py:3499` |

`--check` 在进入同步写入前返回，本身没有写入或删除入口。`pi_dispatch.py:3522`

建议先补齐 doctor 的规则文件校验及两个存在性探测，并将拒绝原因转为提示。新增回归断言覆盖了本轮副本链接问题，但没有覆盖上述入口；本轮未复跑测试或变异验证。`test_dispatch.py:1261`、`1271`

## 第六轮：确认 doctor 入口的修正

**PASS，可以提交；未发现本轮新增的阻塞问题。**

1. **五处均已按约定处理**：
   - AGENTS 外链提示，保留大小检查：`pi_dispatch.py:3479`。
   - CLAUDE 外链不读取，链接本仓库 AGENTS 时放行：`pi_dispatch.py:3491`。
   - 安装状态、旧布局判断经过目标目录校验：`pi_dispatch.py:3421`、`pi_dispatch.py:3511`。
   - 源缺失判断前先校验副本目录：`pi_dispatch.py:3434`。

2. **新增测试与修正对应**：缺源加链接副本、合法 CLAUDE 链接、仓库外 CLAUDE 链接均有真实链接用例：`test_dispatch.py:1320`、`test_dispatch.py:1334`、`test_dispatch.py:1342`。本轮语法检查及当前仓库只读函数检查通过，未重跑会写盘的测试。

3. **剩余问题不阻塞提交**：校验后换链需要攻击者并发替换链接；既有 `context_evidence` 跟随规则文件计算哈希的行为与 HEAD 相同，不属于本次修改：`pi_dispatch.py:3497`、`pi_dispatch.py:1668`。

## 处理结果

| 轮次 | 发现 | 严重度 | 处理 |
|---|---|---|---|
| 1 | `sync-adapters` 删除旧副本前未校验真实路径 | 高 | 解析后的路径必须就是仓库内的预期位置，`.claude`、`.claude/skills` 或技能目录是链接时拒绝；先校验全部目标再改动 |
| 1 | 升级步骤可能丢失项目自定义规则 | 高 | 先把 CLAUDE.md 与 `agent-files.md` 中项目自己的内容迁进 AGENTS.md，核对后再删除 |
| 1 | 示例配置不能免去 Codex 沙箱的审批 | 中 | 写明 `workspace-write` 中 `.git` 只读，写 Git 元数据或仓库外 worktree 的调度命令都要批准在沙箱外运行；示例配置只保留推理强度与审批策略 |
| 1 | `wait` 把未知状态报告为已结束 | 中 | 只有明确的结束状态才退出 0；state.json 缺失或损坏时退出 1 |
| 1 | 部分技能源缺失时 `--check` 仍通过 | 中 | `--check` 在缺少源文件时也失败；同步模式跳过缺失的技能并退出 1 |
| 1 | 升级命令缺少 `mkdir -p .agents/skills` | 中 | 升级步骤给出完整命令 |
| 1 | 只用 Codex 时 doctor 报“副本不一致” | 低 | 区分“未安装 Claude Code 副本”与“已安装但不一致”，前者不提示 |
| 1 | review-pi 残留 `/dispatch-pi` 写法 | 低 | 改为技能名加 troubleshooting.md 链接 |
| 2 | 目录遍历仍会跟随 Windows junction | 中 | 新增 `_is_link_or_junction`：依次检查 islink、Python 3.12+ 的 isjunction、Windows 的重解析点属性；`_tree_files` 用它过滤 |
| 3 | 未检查源目录的上级是否为链接 | 中 | 新增 `_repo_local_path` 与 `skill_source`，读取源与写入目标共用同一校验 |
| 4 | 读取副本时未经链接校验 | 中 | `adapter_drift` 从 `claude_skill_target` 读取副本；外部内容与源相同时，`--check` 也不会误报“一致” |
| 5 | doctor 的规则文件读取与存在性判断未校验；源缺失时跳过副本 | 中 | AGENTS.md 或 CLAUDE.md 指向仓库之外时只提示、不读取；CLAUDE.md 链接到本仓库 AGENTS.md 时放行；存在性判断与旧布局判断走校验过的路径；源缺失时也先校验副本目录 |
| 6 | PASS；剩余两点不阻塞提交：校验后被并发换链；`context_evidence` 的既有行为 | —— | 并发换链需要攻击者能在本机并发操作，不在本工具的防护范围（README 已写明“不是沙箱”）；`context_evidence` 与本次改动无关 |

第 1 轮第 1 条，以及第 2–5 轮的修正，都有用真实链接的回归测试，并做了变异验证：退回旧写法时，对应测试失败。
