# Code-Kit 2.9 设计说明：安装与更新（第一轮实战）

状态：2.9.0 已做完（2026-10-15）。

## 1. 为什么做

2026-10-15 用户决定让 Code-Kit 先在自己身上实战：PLan 里除了 Code-Kit 与 KitExperiment，其余仓库都是别人项目的克隆。第一件选的是评估里列过的“安装与更新”。

- **安装步骤丢了**：Code-Kit 的 README 从第一个提交起没有安装步骤。PI-Kit 1.x 的 README 有手工步骤（复制文件、合并 AGENTS.md 时的三个决定、追加 `gitignore.append.txt` 与 `gitattributes.append.txt`），迁过来时没带上；CHANGELOG 与 dispatch-pi 的 troubleshooting 还在引用它。
- **调度器不再是单文件**：2.6 起还要 `scripts/kit_config.py`、`scripts/codekit/` 下 7 个模块、`plugins/decisions/`。只复制 `pi_dispatch.py` 的仓库会悄悄失去决策与配置管理器，调度器只在 doctor 里说一句“不可用”。
- **两种布局都没写**：技能里的命令都是 `bash scripts/dispatch-pi.sh …`，默认 kit 装在目标仓库的 `scripts/` 里；KitExperiment 则是从 kit 目录运行，规划端每条命令手写绝对路径。哪种都没有说明，也没有工具核对。
- **更新没有依据**：kit 升级时，不知道目标里哪些文件过期、哪些被本地改过。
- **实战的意义**：主体由 Pi 执行器实现（新脚本加测试），规划端写 oracle、合同与复审，并第一次实机使用 2.8 的多命令变异、`review-draft` 与 `integrate`。

## 2. 现状（2026-10-15 核对）

- **kit 的发放内容**（目标仓库需要的文件）：
  - 运行时：`scripts/pi_dispatch.py`、`scripts/dispatch-pi.sh`，以及 `KIT_LOADED_FILES`（`scripts/kit_config.py`；`scripts/codekit/` 下的 `__init__`、`decisions`、`secrets`、`plugins`、`planner`、`planner_protocol`、`protocols`；`plugins/decisions/**`）。
  - 技能：`.agents/skills/` 下的 check-pi-env、plan-task、dispatch-pi、review-pi；Claude Code 副本 `.claude/skills/…`（`sync-adapters` 生成）与 `.claude/agents/pi-reviewer.md`。
  - 规则与目录说明：`AGENTS.md`（带“按需补充”占位的模板；目标已有 AGENTS.md 时要合并）、`.agent/README.md`、`.agent/dispatch.config.example.json`。
  - 片段：`gitignore.append.txt`（`.agent/runs/`）、`gitattributes.append.txt`（`*.sh text eol=lf`、`.agent/** text eol=lf`）。
  - 可选：`.codex/config.example.toml`、`.claude/settings.example.json`。
- **调度器已有的核对**：`prepare` 要求 `.agent/runs/` 被忽略；doctor 能区分 Claude 适配层“没装”与“装了但漂移”（`claude_adapters_installed`、`planner_file_notes`）；决策模块缺失时说“不可用”。不核对整个 kit 是否齐全、是否过期。
- **执行器的只读范围**：Code-Kit 自己的 `dispatch.config.json` 把 `scripts/codekit/**`、`schemas/**` 等 v2 文件列为执行器只读，2.8 起 `KIT_LOADED_FILES` 也是内置只读。新脚本放 `scripts/kit_install.py`，不受影响。

## 3. 方案草图

新文件 `scripts/kit_install.py`：标准库、单文件，从 kit 目录运行，`python <kit>/scripts/kit_install.py <命令> <目标仓库>`。

1. **`check`**（只读）：列出每个发放文件在目标里的状态：
   - `ADD`：目标没有；
   - `SAME`：与 kit 相同；
   - `UPDATE`：目标是上次安装时的原样，kit 已经更新；
   - `KEEP`：目标与上次安装记录不同，是本地改过的；
   - `CONFLICT`：目标已有同名文件，但没有安装记录可以对照。
2. **`install`**：首次安装。
   - 目标没有的文件直接复制（按字节，`.sh` 保持 LF）。
   - 已有同名文件按第 6 节问题 2 处理；AGENTS.md 按问题 1；`.gitignore` 与 `.gitattributes` 按问题 4 追加片段（已有就跳过）。
   - `.agent/dispatch.config.json` 只在没有时从示例生成；最后写安装记录（问题 3）。
3. **`update`**：按安装记录逐个比较。过期的覆盖；本地改过的按问题 2 处理；kit 新增的补上；kit 删掉的只报告，不删。
4. **输出与退出码**：每个文件一行 `ADD|SAME|UPDATE|KEEP|CONFLICT <路径>`，最后一行是 JSON 汇总。退出码 0 完成，1 有没处理的冲突，2 用法错误。
5. **边界**：
   - 目标路径必须是 Git 仓库的工作区根目录；源与目标都不跟随符号链接或 junction，写入路径必须落在目标仓库内。
   - 不碰目标的 `.agent/plans`、`reviews`、`runs` 与凭据；不运行 Git 命令以外的程序；不提交、不联网。
6. **调度器一侧**（规划端改 `pi_dispatch.py`）：`doctor` 读安装记录，报告 kit 是否齐全、哪些过期、哪些本地改过；从 kit 目录运行时（KitExperiment 那种）报告“kit 在目标仓库之外，不需要安装”。技能与 README 写清两种布局。

## 4. 这一轮怎么跑

- **一份合同**：Pi 写 `scripts/kit_install.py` 与 `tests/test_kit_install.py`。规划端先写 oracle `tests/test_kit_install_oracle.py`，在草稿实现上用 `mutate --tree` 验证它分得开，再只提交 oracle 作为基线。doctor 的完整性检查、技能、README 与 CHANGELOG 由规划端在集成后补。
- **授权**：执行器 `local_edit, local_test`；集成 `local_branch, merge`（用户 2026-09-23 的长期授权：Code-Kit 的提交与合并到 master 不必再问；推送等用户说）。
- **检查**：oracle、执行器测试、回归（`tests/test_kit_v280.py`、`tests/test_kit_config.py`）、`compileall`、`git diff --check`。全量 pytest 约 7 分钟，放进合同检查，由 `integrate` 在落地前跑一次。
- **预算**：最多 2 轮，每轮 1800 秒；step/step-5-preview，thinking high。按 KitExperiment 的均值，一轮约 ¥2.6。
- **实机用一遍 2.8**：多命令变异清单（oracle 加执行器测试、只用执行器测试）、`review-draft`、`integrate`。回流写进新开的 `docs/ThemisTally实机反馈.md`。

## 5. 不做

- 不做 pip 或 npm 包，不从网络下载 kit：目标从本机的 kit 目录安装。
- 不自动改写目标已有的 AGENTS.md 正文（见问题 1）；不删除目标里的任何文件。
- CI、v2 去留、第二种执行 CLI：另立方向。

## 6. 用户决定（2026-10-15，均选推荐项）

1. **AGENTS.md**：目标没有时放 kit 模板；已有时不动，输出列出目标里缺少的 kit 章节，由人手工合并。
2. **目标里已有、与 kit 不同的文件**：不覆盖，列为 `CONFLICT` / `KEEP` 并退出 1；加 `--force` 才覆盖，覆盖前把原文件备份到 `.agent/kit-backup/<时间>/`。
3. **安装记录**：目标写 `.agent/kit-install.json`（kit 版本、kit 提交、每个文件的 sha256），`update` 与 `doctor` 据此分辨“过期”和“本地改过”。
4. **忽略与行尾规则**：追加到目标的 `.gitignore` 与 `.gitattributes`，提交由用户决定。

## 7. 进度与遗留

- 2026-10-15：核对现状，写成本说明；用户决定第 6 节四项（均选推荐项）。
- 2026-10-15：合同 kit-install.v1，attempt-001 一次通过（600 秒）；集成 `9cc19ef`，规划端补全 `1b905bc`。实机记录见 `docs/ThemisTally实机反馈.md`。
- 遗留：调度器没有 `install` 转发子命令（从 kit 目录运行 `kit_install.py` 即可）；装进目标仓库的布局还没在真实项目上用过。
