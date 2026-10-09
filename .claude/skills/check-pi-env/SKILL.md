---
name: check-pi-env
description: 核验规划端（Claude Code 或 Codex）与 Pi 执行端的运行环境（CLI 版本、执行模型与 high 思考级别、凭据就绪、规则与上下文文件、项目工具链），生成或更新 .agent/environment.md。用于首次接入 Pi 协作流程、升级 pi / 规划端工具 / 模型之后，或派遣预检失败时。
argument-hint: "[provider/model] [--smoke]"
---

# 核验执行环境

参数：$ARGUMENTS

（上一行在 Claude Code 中会替换为调用参数；在 Codex 中保持原样，此时参数就是用户调用本技能时附带的文字。）

目标是留下可复核的环境事实，不做安装或升级。安装、升级 pi 或项目工具链，按项目既有规则由用户决定。
**不要**把 API key、令牌或完整的环境变量写进任何文件或回复。

命令统一写作 `bash scripts/dispatch-pi.sh <子命令>`。

## 步骤

1. **确定执行模型**。按以下顺序选取：
   1. 参数中的 `provider/model`（第一个 `/` 之前是 provider）；
   2. `.agent/dispatch.config.json` 的 `allowed_executors`；
   3. 已有 `.agent/environment.md` 的记录。

   默认使用 Step 系列、思考级别 `high`。都没有时，运行 `pi --list-models step`，列出本机已有凭据的 Step 模型，请用户选定 provider 与精确的 model ID。
2. **收集事实**（不调用模型）：
   ```bash
   mkdir -p .agent/runs/_env
   bash scripts/dispatch-pi.sh doctor --provider <provider> --model <model> --thinking high --out .agent/runs/_env/doctor.json
   ```
   从输出中提取：
   - pi 版本与命令路径、支持的思考级别与内置工具、缺少的参数；
   - 执行模型是否在可用列表里、`pi auth check` 结果：
     - `executor_model_list` 记录了 `pi --list-models` 的退出码与行数；
     - 它执行失败或列表为空时，多半是沙箱挡住了 pi 读取 `~/.pi/agent`，改在沙箱外运行 doctor 再下结论；
   - 仓库状态，AGENTS.md（及 CLAUDE.md，如有）是否已提交，Git 作者身份是否可用（`repository.git_identity`，branch 需要）；
   - 规划端适配：`.claude/skills/` 是否与 `.agents/skills/` 一致，仓库有 CLAUDE.md 时其中是否有 `@AGENTS.md`，AGENTS.md 是否超过 Codex 的 32 KiB 上限；
   - Pi 会加载的上下文文件（全局与祖先目录）、全局 SYSTEM.md；
   - `problems` 与 `notes`。
3. **规划端事实**：按实际使用的工具记录，两种都用时各记一份。规则文件或技能中写的模型名不算配置。
   - **Claude Code**：
     - `claude --version`；
     - 当前会话实际使用的模型 ID，从你的运行上下文得知；不确定时请用户在 `/model` 中确认；
     - 模型配置来源：`--model`、`/model` 还是 settings；
     - 2.1.277 起，在没有 CLAUDE.md 时读取 AGENTS.md。仓库有 CLAUDE.md 时，确认其中有 `@AGENTS.md`。
   - **Codex**：
     - `codex --version`；
     - 模型与 `model_reasoning_effort` 及其来源：`~/.codex/config.toml`、受信任项目的 `.codex/config.toml` 或命令行。只记键名与取值，不记凭据；
     - 沙箱模式与审批策略；
     - 本仓库是否已受信任。未受信任时，项目的 `.codex/` 配置不会生效。
4. **项目工具链**：从锁文件与配置（如 package.json 的 packageManager / engines、.nvmrc、pyproject.toml、go.mod）识别需要的工具，运行它们的 `--version` 并记录版本。版本不符时只报告，不要升级。
   - 换了机器或操作系统之后，在当前工作区跑一次项目的全量检查，把结果写进“验证记录”，并与上一台机器记录的数字比较。只在新平台失败的用例先分类：测试夹具的平台假设（`/dev/fd`、`SIGKILL`、chmod、符号链接后的 `..`）还是产品的平台专用代码（PATH 分隔符、`O_NOFOLLOW`、boot id）。两类都按项目已有的写法加平台跳过标记（例如 `@unittest.skipIf(os.name != "posix", …)`），作为单独的规划端提交成为本机基线；不要让每份合同各自回避全量检查。实机：KitExperiment 从 macOS 回到 Windows 时 33 个用例失败，全是这两类，补标记后 551 passed / 286 skipped。
   - Windows 原生终端的控制台编码是 cp1252：规划端自己的 Python 脚本打印非 ASCII 之前设 `PYTHONUTF8=1`；调度器与检查命令不受影响。
5. **可选的连通性试跑**（会调用模型并产生少量费用）：只有参数包含 `--smoke`，或用户确认后才运行。
   ```bash
   bash scripts/dispatch-pi.sh smoke --provider <provider> --model <model> --thinking high --out .agent/runs/_env/smoke.json
   ```
   它分两步：先做无工具的一问一答，再在临时目录里写一个文件并读回。两步都通过，才能说明模型、凭据与工具调用可用。
   在 Codex 中，smoke 要联网并写系统临时目录，需要按提示批准在沙箱外运行。
6. **写入 `.agent/environment.md`**：
   - 以 [environment-template.md](environment-template.md) 为模板，写事实而不是期望。
   - 路径写成相对仓库或 `~` 开头的形式。
   - 有旧版本时，保留“变更记录”并追加一行。
7. **报告**：环境是否可用于派遣，以及阻塞项与建议。常见问题：
   - pi 低于 0.80.4（没有 agent_settled）；
   - 模型不在列表或凭据未就绪；
   - AGENTS.md 未提交（worktree 看不到）；
   - 仓库有 CLAUDE.md 却没有 `@AGENTS.md`，Claude Code 读不到 AGENTS.md；
   - `.claude/skills/` 与 `.agents/skills/` 不一致：运行 `bash scripts/dispatch-pi.sh sync-adapters`；
   - `.agent/runs/` 未被忽略；
   - `~/.pi/agent` 下有 AGENTS.md 或 SYSTEM.md，会影响执行器；
   - 缺少 rg / fd（Pi 会从 GitHub 下载）。
8. **可选**：建议把验证过的执行模型写进 `.agent/dispatch.config.json` 的 `allowed_executors`，并把 `thinking` 固定为 `"high"`。修改前先征得用户同意。
