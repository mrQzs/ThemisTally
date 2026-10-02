# TASK: 05-1-command-platform-entry

## Identity
- plan_version: 2
- repository: Code-Kit
- base_sha: 1e1363a34857873609bead54d43812c0cd45611a
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: none
- executor: step/step-5-preview · thinking high
- execution_lane: adapter-fixtures/docs（Pi dispatchable: true）

## Goal
建立 CommandSet/CommandSpec 严格模型、平台唯一载体选择、FinalLaunchPlan 静态参考与 argv 同源回显；证明数据不被 shell 展开或变体覆盖。

## Non-goals
- 不读取凭据，不调用真实 provider/CLI/模型，不联网、不安装依赖或打开浏览器。
- 不修改 AGENTS.md、已有合同、.agent/、调度脚本、scripts/codekit/** 或 schemas/**；受保护核心由主模型另行实现。
- 合成 fixture 只能证明离线算法/证据形状，真实平台能力、生产锁、预算、审核与候选门禁另行验收。

## Repository facts
- 入口：基线已有 scripts/codekit/ 的纯 Python 协议、资源和状态模块；现有测试在 tests/；04–06 设计文档是拟议新增能力，本合同只列离线 adapter、测试、fixture 与文档路径。
- 调用关系与现状：04 适配器、05 平台监督、06 插件清单尚未在基线接线；真实 CLI、平台、账本和审核证据不能由合成样本代替。
- 工具链与锁文件：Python 3.9/3.12，标准库 unittest/compileall；无项目依赖锁文件；禁止安装或升级依赖。
- 基线检查：既有路线图记录定向测试约 195 项通过；Pi doctor 记录模型未列出且凭据未就绪。本批只要求离线检查。

## Scope
- allowed_modified_files:
  - 无
- allowed_new_files:
  - adapters/platforms.py
  - adapters/command_model.py
  - tests/test_platform_commands.py
  - tests/fixtures/platform_runtime/commands/**
  - docs/code-kit-v2/05-platform-command-evidence.md
- allowed_deleted_files: 无
- forbidden_paths: .agent/**, .agents/**, .claude/**, .codex/**, .pi/**, AGENTS.md, scripts/pi_dispatch.py, scripts/dispatch-pi.sh
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh、scripts/codekit/**、schemas/**

## Inputs and outputs
- Inputs: current base SHA, approved requirements/reference documents, and existing offline fixtures within the contract scope.
- Outputs: deterministic implementation, tests, fixtures, and evidence inside Scope; no production connector claim.
- Evidence: commands and paths are recorded in `.agent/runs/` or planner reviews; unavailable external evidence remains BLOCKED/NOT_RUN.

## Failure handling
- Classify malformed, drifted, missing, unsupported platform/provider, and unavailable connector inputs as explicit error, UNKNOWN, BLOCKED, or NOT_RUN; stop on scope or base mismatch.
- Never use fixtures, synthetic receipts, or offline results as production evidence.

## Rollback boundary
- Revert only files within this contract's Scope; do not alter AGENTS.md, dispatch scripts, `.agent/`, protected core paths, dependencies, credentials, or external systems.

## Behavior contract
- CommandSet 先全平台校验，再选一个完整 argv 或登记 shell+script；共同字段和断言不可覆盖，展示与机器对象同源。
- argv/shell 互斥、缺平台、空项、Unicode、引号、CRLF、NUL、不安全 shim、非法 cwd、未知字段在创建前拒绝；不翻译 Bash/PowerShell、不混 WSL/native。
- 保留非零退出、语法错误、wait=3 和 LASTEXITCODE；不以另一变体自动回退。
- 静态模型无外部状态；同输入同指纹；环境身份变化使旧计划失效。
- 保留 v1 参数/退出；新 schema/version 独立。

## Steps
1. 核对现有 pi_dispatch 参数转发和 test_dispatch 事实，不改受保护入口。
2. 实现 adapters/platforms.py/command_model.py 纯校验和同源渲染。
3. 添加 echo/退出、缺平台、载体冲突、特殊字符、CRLF fixture；规则逐条断言。
4. 运行 V01–V03；native Windows/macOS/PowerShell 矩阵列 NOT_RUN。

## Validation commands
- V01（必要）：`python -m unittest tests.test_platform_commands` · cwd：仓库根 · 超时：300s · 期望退出码：0 · 输出须匹配：`Ran\s+[1-9]\d* tests`
- V02（必要）：`python -m compileall -q adapters tests` · cwd：仓库根 · 超时：120s · 期望退出码：0 · 输出须匹配：``
- V03（必要）：`git diff --check` · cwd：仓库根 · 超时：60s · 期望退出码：0 · 输出须匹配：``

- G01（必要）：`python tests/test_dispatch.py` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：``

- G02（必要）：`python -m compileall -q scripts/codekit tests` · cwd：仓库根 · 超时：180s · 期望退出码：0 · 输出须匹配：``

- G03（必要）：`python -m unittest discover -s tests -q` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：``

## Definition of done
- D01：建立 CommandSet/CommandSpec 严格模型、平台唯一载体选择、FinalLaunchPlan 静态参考与 argv 同源回显；证明数据不被 shell 展开或变体覆盖。；证据：V01。
- D02：每条 Behavior contract 的合法、边界、错误及状态规则都有独立离线证据且无未授权副作用；证据：V01、V02。
- D03：修改只在 Scope，未改变依赖、网络、凭据或生产锁；证据：scope、V03。
- D04：既有测试、入口和历史证据未删除、跳过、弱化或重写；证据：review。

## Stop conditions
- 基线、公共接口、依赖合同或必要文件与 facts 不符。
- 必须修改 Scope 之外或 scripts/codekit/**、schemas/**，或需要依赖、网络、凭据、真实 provider/CLI、生产账本或外部写入。
- 上下游版本/语义冲突；未知平台、能力或原始证据无法证明时标记 BLOCKED/NOT_RUN，不猜测。
- 达到单轮时限。

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 1200
- max_wall_seconds_total: 2400
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；当前合同只允许本地编辑和离线检查。
- 时间分配：调查 20%，实现 50%，补测与离线检查 20%，最终报告 10%。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D04，列出 V01–V03 命令与结果、证据路径、NOT_RUN/BLOCKED 项和遗留问题，末尾附执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由独立验收端决定。

## Forbidden
- 不修改本合同、代理规则、权限配置、调度脚本或 scripts/codekit/**、schemas/**。
- 不删除、跳过或弱化测试，不吞掉错误，不以合成 fixture 冒充真实平台能力。
- 不提交、不推送、不合并、不部署，不安装或升级依赖。

