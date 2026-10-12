# 任务合同编写指南

合同由两份文件组成：Markdown 给执行器和人阅读，JSON 给调度器做确定性校验。两者不能各自维护：
`bash scripts/dispatch-pi.sh validate <key>` 会检查它们是否一致，prepare 时会把两份文件复制进 attempt 目录并计算哈希。已经派遣过的版本不再修改，有变化就出新版本。

## 一、八个问题（写完后逐条自问）

1. 从哪个确定的提交开始？（base_sha，且被测代码、AGENTS.md 都在这个提交里）
2. 要改变什么行为？哪些行为明确不改？（Goal / Non-goals）
3. 允许读什么、改什么、新增什么、删除什么？（Scope）
4. 接口、异常、边界、并发、取消的语义是什么？（Behavior contract）
5. 每条完成标准由什么独立证据确认？（Definition of done → checks / scope / review）
6. 遇到需求、环境或权限阻塞时怎样停止？（Stop conditions）
7. 最多运行多久、返工几次、花多少钱，由谁强制？（Budget）
8. 完成后留下哪些可复核的产物？（执行报告、候选补丁、检查日志）

“一个中等水平的开发者不用提问就能做完”是清晰度目标，但不能因此要求执行器在事实缺失时去猜。执行器合理地停止并报告问题，本身就是合格行为。

## 二、JSON 字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `schema_version` | 是 | 固定为 `1` |
| `task_id` / `plan_version` | 是 | 与文件名 `<task_id>.v<plan_version>` 一致 |
| `base_sha` | 是 | 完整提交 ID，必须能在本仓库解析 |
| `risk_level` | 是 | `low` / `medium` / `high`，见第三节 |
| `authorization.executor` | 否 | 执行器可做的事，默认 `["local_edit","local_test"]` |
| `authorization.integration` | 否 | 验收通过后验收端可做的集成动作，默认 `[]` |
| `executor` | 是 | 执行模型与工具，见第四节 |
| `scope` | 是 | 允许与禁止的路径，见第五节 |
| `setup` | 否 | prepare 阶段在 worktree 中运行的准备命令 |
| `checks` | 是 | 验收命令，至少一个 `required: true`，见第六节 |
| `definition_of_done` | 是 | 每项都要有 `evidence` |
| `budget` | 否 | 默认 2 次、单轮 1200 秒、合计 2400 秒 |

未知字段会被忽略，可以用来写 `title` 等说明性信息。

### 授权词表

**计划不能创造授权。** 只写用户已经明确给出的授权；原始请求没有授权的动作，要先问用户。

| 取值 | 含义 |
|---|---|
| `local_edit` | 在 worktree 中修改允许范围内的文件（必需） |
| `local_test` | 运行本地检查 |
| `local_commit` | 在 worktree 中创建本地提交（很少需要；未授权时 HEAD 移动算越界） |
| `network` | 访问模型服务之外的网络（只是提示，不能强制；需要强制时在网络层实现） |
| `local_branch`（集成） | 为通过验收的候选建本地分支 |
| `commit` / `push` / `open_pr` / `merge` / `deploy`（集成） | 验收端在 PASS 后可执行的动作，执行器永远不做 |

## 三、风险等级

| 等级 | 典型任务 | 额外要求 |
|---|---|---|
| low | 局部修复、补测试、确定性重构 | 标准流程 |
| medium | 跨两三个模块的接口接入、配置迁移 | 记录基线检查结果；复审时做独立复审（Claude Code 用 `pi-reviewer` 子代理，Codex 用只读的 `codex exec` 会话，见 review-pi） |
| high | 认证授权、并发、数据迁移、计费 | 先定语义表与验收矩阵（参考 auth-refresh-401 示例）；拆小；复审时做独立复审，结论交用户确认 |

高风险任务中无法拆出清晰合同的部分，由规划器自己完成或交给人。

## 四、执行器配置（executor）

```json
"executor": {
  "provider": "step",
  "model": "step-5-preview",
  "thinking": "high",
  "tools": ["read", "grep", "find", "ls", "edit", "write", "bash"],
  "context_files": "project"
}
```

- **模型**：默认使用 Step 系列，思考级别 `high`。provider 与 model 必须与本机 `pi --list-models step` 输出的精确 ID 一致；这个命令只列出已配置凭据的提供商。
  - 本机（2026-09-22 核验）：自定义 provider `step` 定义在 `~/.pi/agent/models.json`，使用阶跃星辰的 `step_plan` 端点与 anthropic-messages 协议；模型 `step-5-preview`，reasoning 已开启。
  - 其他来源：Pi 0.87.0 内置目录中的 Step 3.7 Flash，可以经 `openrouter` 或 `vercel-ai-gateway`（`stepfun/step-3.7-flash`）或 `huggingface`（`stepfun-ai/Step-3.7-Flash`）调用。
  - 模型名或 provider 写错时，Pi 可能只打印 `Using custom model id` 警告，然后照样发请求。调度器预检会拒绝不在列表里的模型，运行后也会核对实际模型。
- **思考级别**：Pi 对无效值只警告、不报错，并把级别调整到模型支持的范围（先向更高档找，再向更低档找）。
  - `step-5-preview` 按 Pi 的规则支持 off / minimal / low / medium / high / max，不支持 xhigh（写 xhigh 会被调整成 max）。
  - Pi 接受 `high` 以后，实际发给提供商的形式取决于协议。本机 `step` 使用 anthropic-messages 协议且未开启 adaptive thinking，所以 Pi 发送的是**思考预算**：`thinking.budget_tokens` 默认为 16384（minimal 1024、low 2048、medium 8192；这种模式下 xhigh 与 max 也按 high 的预算发送）。预算可以在 Pi 的 settings 中用 `thinkingBudgets.high` 调整。
  - 只有模型配置了特定的 compat（如 `supportsMidConvoEffort`）时，assistant 消息才会带回 `providerThinkingLevel`。对本机的 Step 配置，调度器只能确认请求的级别，不能证明服务端实际按 high 推理。
  - Step 3.7 Flash 只支持 low / medium / high。
  - 提供商回报了级别时，调度器会记录并与合同比较，不一致即判为执行问题；没有回报时注明“只能确认请求的级别”。
  - `high` 会增加输出 token 和耗时，设置 budget 时要预留余量。
- **不要**在合同外用环境变量改模型：`PI_EXEC_*` 与合同冲突时，调度器会拒绝运行。
- **工具组合**：

| 组合 | tools | 谁运行检查 | 适用 |
|---|---|---|---|
| 执行器自检 | 上例（含 `bash`） | 执行器自检，验收端再独立复跑 | 可信环境中的一般任务 |
| 修改与检查分离 | 去掉 `bash` | 只由验收端的 `check` 运行 | 希望减少执行器直接跑 shell |
| Windows 原生 | 用 `powershell` 替换 `bash` | 同上 | 项目脚本依赖 PowerShell 时 |

  - Pi 会静默丢弃未知的工具名，所以调度器预检会先核对工具名。
  - 去掉 `bash` 只是缩小了直接能力：执行器写入的代码、测试和配置，之后仍会在检查中运行。
- **上下文文件**：
  - `project`（默认）按 Pi 的规则加载 `~/.pi/agent` 与 worktree 所在目录链上的 AGENTS.md / CLAUDE.md，每个目录只取第一个存在的文件，AGENTS.md 优先于 CLAUDE.md。
  - `none` 会传入 `--no-context-files`。只有在合同已经包含全部必要约束时才用。
  - 调度器会把实际会加载的文件及其哈希记入 `preflight/context-files.json`。

## 五、范围（scope）

- 首选**确切路径**。确实需要模式时：`*` 匹配单层，`**` 匹配任意层级，`?` 匹配单个字符。
- 路径一律是仓库相对的 POSIX 形式：不能是绝对路径，不能含 `..`、反斜杠或控制字符。
- 状态对应关系：新增（A）要在 `allowed_new_files` 里，修改（M）和类型变化（T）要在 `allowed_modified_files` 里，删除（D）要在 `allowed_deleted_files` 里。
- **始终受保护**，写进允许集合会被校验拒绝：`.agent/**`、`.agents/**`、`.claude/**`、`.codex/**`、`.pi/**`、`.gitmodules`、任意层级的 `AGENTS.md`、`AGENTS.override.md`、`CLAUDE.md`、`CLAUDE.local.md`，以及调度脚本。
- `dependency_changes: forbidden` 时，依赖清单或锁文件（package.json、pnpm-lock.yaml、pyproject.toml、go.mod 等）发生变化会被判为越界。
  - 如果任务需要修改 package.json 中与依赖无关的部分，把它列为确切路径。调度器会降级为警告，由验收端确认没有依赖变化。
- 格式化工具、代码生成或测试快照可能改动计划外的文件。要么把这些文件纳入范围，要么在 Steps 中禁止运行相应工具。
- 符号链接、子模块指针、执行位变化都会被单独标记。

## 六、检查（checks）与准备命令（setup）

```json
{
  "id": "V01",
  "argv": ["pnpm", "exec", "vitest", "run", "src/search/normalize.test.ts"],
  "cwd": ".",
  "timeout_seconds": 300,
  "required": true,
  "expected_exit_code": 0,
  "output_must_match": ["Tests\\s+[1-9]\\d* passed"],
  "output_must_not_match": ["No test files found", "\\bskipped\\b"],
  "env": {}
}
```

- **argv 是参数数组**，不经过 shell。这只能避免 shell 拼接问题，不是沙箱：`python -c` 或脚本仍然可以做任何事。
- **用 `output_must_match` 防止“0 个测试也是绿色”**。常见写法：
  - vitest：`Tests\s+[1-9]\d* passed`
  - pytest：`[1-9]\d* passed`
  - go：`^ok\s`
  - jest：`Tests:\s+[1-9]\d* passed`
- **避免监听模式**：vitest 用 `run`，jest 不加 `--watch`。
- **调度器设置的环境**：
  - 检查命令默认带 `CI=1`、`PYTHONDONTWRITEBYTECODE=1`。
  - 推送和发布类凭据（GITHUB_TOKEN、NPM_TOKEN、SSH_AUTH_SOCK 等）会被移除。
  - 确实需要的变量写进 `env`，或在 `.agent/dispatch.config.json` 的 `env_keep` 中保留。
- **检查必须针对确切的候选**：
  - 运行检查前，worktree 中出现候选之外的新文件（例如复审时补上的模块），或候选文件被改动，`check` 会拒绝运行：否则测试可能因为额外文件通过，而这些文件并不在要集成的候选里。
  - 检查过程中改动了候选文件，或产生了候选之外的新文件，门禁 G4 不通过。
  - 例外只有缓存类文件：默认是 Python 的 `__pycache__`、`*.pyc`、`.pytest_cache`、`.mypy_cache`、`.ruff_cache`。其他报告或缓存文件，加入 `.gitignore`，或写进 `.agent/dispatch.config.json` 的 `check_artifact_patterns`。
- **`check --fresh`**：在一个干净副本（基线 + 候选补丁 + 合同 setup）上运行检查，不受执行 worktree 中被忽略文件（依赖、构建产物）的影响。中高风险任务建议用它作为 PASS 依据；合同的 setup 要能在全新副本中准备好依赖。
- **修复类任务**：尽量让回归测试在旧实现上失败、在新实现上通过。
  - 派遣前用 `baseline` 在基线副本上运行全部检查，并记录结果。
  - 专门证明修复的探针（常见是 `python -c "…; print('PROBE_OK')"`）加上 `"expect_on_base": "fail"`，Markdown 检查行写“基线应失败”。
  - 回归保护类检查可以标 `"expect_on_base": "pass"`。
  - 探针的第一条断言最好就是被修复的行为本身：如果只是因为新函数不存在而 ImportError，只能证明“接口是新加的”。
  - baseline 只能证明探针在基线上失败，后面的断言在基线上根本没运行到。多段探针派遣前在草稿修复上跑一次，确认能通过，否则执行器会被一条写错的探针卡住。
  - 修复涉及几条规则时，再用只修了一部分的草稿各跑一次，确认每个探针只在它对应的规则没修时失败。
- **中断类探针**：用真实 SIGINT 测试中断吸收（KeyboardInterrupt）时：
  - 信号只发给测试进程自己；
  - 发送前用文件或进程状态握手，确认被测代码已经进入目标窗口；
  - 测试期间装一个只在被测调用期间生效的处理器，调用一返回就解除；
  - 在测试里拦住冒出的 KeyboardInterrupt，让失败只落在这个用例上。否则 pytest 整个会话会中断，退出码为 2，后面的用例都不运行。
- **探针里的不可见字符**：需要零宽字符、双向控制符时用 `chr(0x200E)` 这类写法，不要写 `\u200e` 转义。编辑工具可能把转义写成实际字符，导致 Markdown 与 JSON 比对不上。
- **Windows 注意**：命令解析到 `.cmd` 或 `.bat`（如 `pnpm.cmd`）时，参数里不能含 `& | < > ^ % ! "`，调度器会拒绝执行这类命令。
- **setup**：
  - 格式与 checks 相同（没有 `required`），在 prepare 阶段于 worktree 中运行，例如 `["pnpm", "install", "--frozen-lockfile"]`。
  - Markdown 里可以写成可选的 `## Setup` 节（行格式与检查行相同，如 `- S01：\`npm ci\` · cwd：仓库根 · 超时：900s`），`derive-json` 会转写成 JSON 的 `setup`；validate 不比较这一节。
  - setup 之后 worktree 不能出现未忽略的变更，例如锁文件被改写。
  - 执行说明会把 prepare 阶段 setup 的结果（命令、退出码）告诉执行器，执行器不必再猜依赖是否已装好。

## 七、完成标准（definition_of_done）

- 每项 `evidence` 至少一个：
  - 检查 ID：必须通过。
  - `scope`：范围报告没有越界。
  - `review`：由复审报告人工判断。
- 每条行为都要能指向证据。“代码看起来对”不是证据。
- 每条 DoD 可以带“目的”子句（调度工具 2.6.0，来自 opus-manager 工单的“为什么这样验收”）：`- D01：行为；证据：V01；目的：…`。过了检查不是目标，这句写的才是——执行器可能过了检查却没达到目的（测试什么都没断言）。它进 JSON 的 `intent`，验收时变异按它设计、独立复审按它判断，而不只按检查通过与否。
- 必要检查应被某个 DoD 引用，否则校验会给出警告。
- 合同至少要有一个 `required: true` 的检查，否则校验不通过：只靠人工复审的任务无法通过验收门禁，不适合用这套流程委派。

## 八、预算（budget）

- `max_attempts_total` 按 task-id 汇总，包括所有版本；只有真正运行过的 attempt 才计数，预检失败的不计。
- `max_wall_seconds_total` 同样按 task-id 累计。
- 单轮时限取 `max_wall_seconds_per_attempt` 与剩余总额中的较小值。
- 费用只统计，不做强制：Pi 按模型目录价格估算，最终以提供商或网关账单为准；账户硬上限只能在提供商或网关设置。
- 起步建议：一次初始执行加一次定点返工（2 次）。thinking 为 high 时，单轮 1200 秒适合局部任务；跨模块任务先拆小，不要简单调高时限。

## 九、Markdown 与 JSON 的一致性（校验器会检查）

Pi 读 Markdown，调度器执行 JSON，所以与执行相关的内容都要比较：

- 标题为 `# TASK: <task-id>`；十三个英文章节标题齐全。
- Identity：
  - `plan_version`、`base_sha`、`risk_level` 与 JSON 相同；
  - `authorized_actions` 与 `authorization.executor` 的集合相同；
  - `integration_actions` 与 `authorization.integration` 的集合相同（没有时写 `none`）；
  - `executor` 一行写明 `provider/model` 与 `thinking <级别>`。
- Scope：
  - JSON 中的每个允许路径与禁止路径都在 Markdown 中出现；
  - `dependency_changes` 的取值相同。
- Budget：`max_attempts_total`、`max_wall_seconds_per_attempt`、`max_wall_seconds_total` 三个数值相同。
- Validation commands：
  - 每个检查 ID 都有一行说明；
  - 该行按顺序包含 argv 的每个参数（程序名只比较文件名主干）。
- 每个 DoD ID 都在 Markdown 中出现。
- 两份文件中都不能残留 `【待填` 或 `REPLACE_WITH`。

setup 命令只由调度器执行，不做比较。另外，调度器会把 JSON 中的范围、依赖策略、授权与检查命令写进执行说明的“机器合同摘要”，与 plan.md 一起交给 Pi；两者不一致时，执行器应停止并报告。

**用 `derive-json` 避免手工同步**：`bash scripts/dispatch-pi.sh derive-json <plan-key> --title "<标题>"` 会从 Markdown 生成 JSON，写完立即校验。Markdown 需按模板书写：

- Scope 的列表可以写在同一行（`- allowed_new_files: a, b`），也可以写成缩进列表；没有时写“无”。
- 单值字段（Identity 各项、`dependency_changes`）后面可以用括号写说明，例如 `- dependency_changes: forbidden（只加命令入口，不增删依赖）`。工具只取括号前的值，说明留给执行器阅读。
- 检查行写成：
  ```
  - V01（必要）：`命令` · cwd：仓库根 · 超时：300s · 期望退出码：0 · 输出须匹配 `正则`，不得出现 `正则`
  ```
  - 可选检查写“（可选）”，探针可以写“（必要，基线应失败）”；
  - `python -c "…"` 的代码原样保留；其他命令按 shell 规则拆成参数，含复杂引号时请手工写 JSON。
- DoD 行写成：
  ```
  - D01：行为；证据：V01、V03。
  ```
  证据里的检查 ID、`scope`、`review` 会被提取出来。“；目的：…”子句可写在证据前或证据后，进 `intent`（2.6.0）。
- 标题取 `--title`，没有时取 Goal 的第一行（超过 60 字时提示改用 `--title`）。标题会成为分支提交的主题行，宜短。`cost_budget` 固定生成为 null（只统计）。
