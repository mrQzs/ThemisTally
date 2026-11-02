# Themis Tally 3.0：实现语言迁移到 TypeScript 的计划

- **状态**：v1.6（见下）。v1.2 于 2026-10-22 themistally-15 同意，附的条件已补进（第 ② 步的启动器与切换测试、Schema 的位置、第 10 节的 `--assess`）。
  - v1 于 2026-10-22 带条件通过。站主委托 themistally-15 会话答复，第 0 步的提交 266cd33 照常合入。
  - v1.1 补进了通过时附的条件：第 2.1、2.2、2.4、3.2、4、5、8.2、8.5 节，以及第 1.4 节的 pyjson。
  - v1.2 按开工前的调查改第 ② 步：调度器的 `metrics` 没有 `--json`、只出 Markdown；带 `--json` 的 `status`、`metrics` 另有一份在 hub 里；`logs cat` 漏写了；仓库里没有 `themis` 入口，桌面端的本机服务也还没建。第 ② 步的范围、出口条件与拆分照实改（第 4 节）。
  - v1.3（2026-10-26，themistally-15 同意，附的七条已补进）按开工前的调查重写第 ③ 步：配置中心随桌面端 D2 长大了，原文“13 个 `--json` 子命令”过时；plugins 归入第 ③ 步，`secret set` 留在 Python，拆成六片加切换（第 4 节）。另记站主同日的决定：T022 的 A、B 做完后暂停开新切片，专心推迁移；以及 themistally-15 转达时附的协调意见（不是站主原话）：之后内核文件只修挡住工作的缺陷，迁移本身的切换不在其内（第 9 节、第 10.1 节）。
  - v1.4（2026-10-26，themistally-15 复审）按开工前的调查与复审重写第 ④ 节：21 条命令加 `status --assess`，八片加切换，开工前定下 D1（平台与版本经 `context` 交）、D2（Ctrl+C 与 CTRL_BREAK 的转发）、D3（`NODE_OPTIONS` 等经换名的环境变量交给 pi）、D4（决策会话的 HTTP 逐项对齐），写明对照办法五条、影子运行的隔离做法与混合期的 26 个名字。
  - v1.5（2026-10-26，themistally-15 复审 v1.4 时要求）补 D5：起真调度器子进程的测试在没装 TS 依赖的环境里怎么办，按实测清点、钉成 Python 的做法、包装与真脚本的逐字节比较和分环境的出口条件；第 11 节 ③-切换一行补上 A3 的更正。④b1 合入时补：切换那一轮的 context 加 `kit_root` 与 `kernel_impl`（第 ④ 节“切换”）。
  - v1.6（2026-10-29）按开工前的只读调查（基线 139a0fa）重写第 ⑤ 步：已经备好的与缺的、逐字节风险、开工前定下的 E1–E6、十片加切换、影子运行的做法；混合期表补第 27 个名字。
- **决定来源**：站主 2026-10-22 的指示“TT 技术栈迁移：在实现中逐步转到 Claude Code 的技术栈”。
- **进度**：记在第 11 节，每完成一步汇报。
- **问题与答复**：计划、quizs 接口、待决项都直接发给 themistally-15 会话，由它答复。AGENTS.md 规定只能由站主本人定的事，由它转给站主：
  - 换模型或思考级别；
  - 改 `dispatch.config`；
  - 要花钱的派遣；
  - 推送或 PR。

---

## 0. 决定与边界

**目标**：实现语言从 Python 逐步迁到 TypeScript。
- TS 用 strict 模式、ESM 模块。
- 运行时用 Bun，最终用 `bun build --compile` 打成单文件可执行程序。
- 同时保持 Node 24 兼容，作为后备。

**不做一次性重写**：
- 迁移穿插在后续的切片和内核轮次里。
- hub 照常交付，桌面端切片照常推进。

**与 quizs 共用**（站主 2026-10-22 决定 quizs 推迟到 TT 整体实现之后，下面为它预留的部分照迁移本身的需要排）：
- TS 内核与自研的 quizs CLI 共用一个 TypeScript 工作区和几个基础包。quizs 也是 TS，将替代 pi 作为工人运行时。
- 内核与 worker 之间的协议，以《设计文档_修订完整版.md》第 8 章和 quizs 设计文档为准。
- 迁移过程中不另造一套与之冲突的接口：第 ⑤ 步照搬现行的“一封信一个回合、最后一条消息交 JSON 块”模型。第 8 章的 IPC 等 quizs 设计文档落地后，另开内核轮次做。

**迁移不改变的东西**：

- **行为**：
  - AGENTS.md 的三方分工与规则；
  - 合同格式（`schema_version` 1）；
  - 证据目录布局与只读约定；
  - 门禁 G0–G6、verdict 枚举；
  - 七端的阶段、信件协议与守卫；
  - 站主权限；
  - 落地流程（exclusive、落地预演、失败撤回）。

  迁移只换实现语言。要改行为，另开内核轮次，按现有流程走。
- **执行模型与思考级别**：不因迁移改变，要改仍须站主同意。
- **Python 版本始终能跑**：迁移中途出问题，能退回 Python 实现继续交付。每一步的回退方式见第 4 节。

---

## 1. 现状清单（截至 3fbb2d1）

### 1.1 在用模块

| 模块 | 行数 | 职责 | 现有测试 | `--json` 子命令 | 移植时的难点 |
|---|---|---|---|---|---|
| `scripts/pi_dispatch.py` | 8407 | 合同校验；prepare、run、check、mutate、verdict、integrate；证据目录；门禁 G0–G6；脱敏；`publish_new` | `test_dispatch.py`（50 个用例），另有 `test_kit_v2100/v280/v300.py`、`test_dispatch_planner.py`、`test_legacy_*.py` 等 | 2 | `run_supervised` 经 ctypes 调 Windows Job Object（`:888-962`）；Git 与 worktree 操作；证据文件的字节摘要 |
| `scripts/kit_hub.py` | 5072 | 七端 hub：信箱、账本、阶段状态机、守卫、回合审计、并行 runner、落地 | `test_kit_hub.py`（209 个用例） | 2 | 回合审计要解析 claude 与 pi 两种流；`state.json` 的三方合并；锁与自动换代 |
| `scripts/kit_config.py` | 1575 | 配置中心：校验、历史、审计、配置锁 | `test_kit_config.py`（56） | 13 | 配置文件与历史快照的字节格式 |
| `scripts/kit_roles.py` | 1381 | 角色绑定：runtime、profile、preset、doctor | `test_kit_roles.py`（64） | 0 | 探测本机 CLI（`--version`、`--list-models`） |
| `scripts/kit_logs.py` | 1346 | 日志：list、show、search、usage | `test_kit_logs.py`（12）、`test_kit_logs_oracle.py` | 5 | 大文件按需截取；脱敏 |
| `scripts/kit_plugins.py` | 825 | 插件：list、show、verify、enable、disable | `test_kit_plugins.py`（6）、`test_kit_plugins_oracle.py` | 3 | 内容锁核对 |
| `scripts/kit_install.py` | 501 | 把 kit 装进目标仓库：比对、更新、冲突 | `test_kit_install.py`（5）、`test_kit_install_oracle.py` | 0 | 安装形态要跟着迁移变（第 6 节） |
| 调度器加载的 `codekit` 模块 | 6781 | `decisions.py`（955）、`secrets.py`（371）、`plugins.py`（406）、`planner.py`（917）、`planner_protocol.py`（492）、`protocols.py`（3639），`pi_dispatch.py:100` 的 `KIT_LOADED_FILES` | `test_decisions.py`、`test_plugins.py`、`test_planner_*.py`、`test_protocols.py` 等 | — | `protocols.py` 是 planner-v2 发布门禁的大块校验 |
| 决策插件 | 数据 | `plugins/decisions/`（manifest、lock、questions） | 同上 | — | 内容锁按字节核对 |

合计：在用 Python 约 2.6 万行，其中 7 个主模块 19107 行，加载的 codekit 6781 行。

### 1.2 数据与模板（不是代码，照原样沿用）

| 内容 | 位置 | 处理 |
|---|---|---|
| hub 的角色说明 | `scripts/hub/worker.md`、`coordinator.md` | 原样沿用 |
| JEV 题库 | `scripts/hub/questions/` | 原样沿用 |
| 入口脚本 | `scripts/dispatch-pi.sh` | 保留为稳定入口：它只是 exec `python scripts/pi_dispatch.py`，选哪一套由 `pi_dispatch.py` 的 main 读选择文件决定（第 5 节）。AGENTS.md 与技能写的命令在第 ⑥ 步之前都不用改 |
| 技能 | `.agents/skills/` | 技能文本写的命令不变；第 ⑥ 步撤 Python 时再统一核对 |

### 1.3 离线 v2 参考实现

- `scripts/codekit/` 里没有被调度器加载的模块：71 个，连同 `adapters/` 约 2.3 万行，例如 `scheduler_store.py`、`unified_ledger.py`。
- 仓库根的 `schemas/`：54 份 JSON Schema。
- 约 100 个测试文件。

它们不在运行路径上。处置见第 7 节。

### 1.4 “JCS”的现状：没有 JCS，只有几种排序键的 JSON

站主的指示把“JCS 规范化”列为第 ① 步的共享基础库。核对代码后的事实：
- 仓库里没有 RFC 8785（JCS）的实现。
- 现有的是 Python `json.dumps` 加 `sort_keys` 的几种写法，各模块不统一：

| 写法 | 例子 | 用途 |
|---|---|---|
| `json.dumps(v, ensure_ascii=False, sort_keys=True)`（默认分隔符 `", "`、`": "`） | `kit_hub.canonical_json`（`kit_hub.py:277`） | `state.json` 三方合并时比较键值 |
| 同上加 `indent=2` 与末尾换行 | `kit_hub.canonical_state`（`:281`） | `ledger/state.json` 落盘 |
| `separators=(",", ":")`、`allow_nan=False`、末尾换行，再编码成 UTF-8 | `codekit/planner.py:54`、`plugins.py:83`、`config_profiles.py:98` 等十来处 | 摘要、回执、内容锁 |
| `json.dumps(v, ensure_ascii=False, indent=2) + "\n"`（不排序） | `pi_dispatch.write_json` | 证据目录的 JSON 文件 |

这些字节进了摘要（信件 sha256、合同两份字节的摘要、内容锁），TS 版必须逐字节复刻 Python `json.dumps` 的排版。与 JS 的 `JSON.stringify` 至少有这些差别：

- **键的排序**：Python 按码点排，JS 按 UTF-16 码元排，补充平面的字符次序会不同。
- **浮点数格式**：
  - Python `repr(1e16)` 是 `1e+16`，JS 是 `10000000000000000`；
  - Python `1e-07` 对 JS `1e-7`；
  - Python 的 `1.0` 写成 `1.0`，JS 写成 `1`。
- **大整数**：Python 大于 2^53 的整数照写，JS 会丢精度，要用 BigInt，或者拒收。
- **默认分隔符与缩进**：Python 默认 `", "` 与 `": "`；`indent` 模式下的逗号与换行规则也要照抄。
- **转义**：`ensure_ascii=False` 时，控制字符与孤立代理项的转义方式。

所以第 ① 步的这一项改名为“**Python 兼容的规范化 JSON**”（`@themis/base/pyjson`）：逐个写法建契约，按字节对照。

**“读进来、改完、写回”也要逐字节复刻**：
- 只管序列化不够：`JSON.parse` 会把 `1.0` 读成 `1`，把超过 2^53 的整数读丢精度，之后怎么序列化都还原不了 Python 的字节。
- 所以 TS 侧凡是读旧文件、改完写回的地方（`state.json` 的三方合并、配置文件），都用 `pyjson` 自己的解析：保留整数与浮点的区别，大整数用 BigInt。
- 除了上面那几处差别，每种写法再各补一条用例：
  - `-0.0`；
  - `indent` 模式下的空容器 `{}` 与 `[]`；
  - `indent` 模式下项分隔符变成 `","`（行尾不带空格）；
  - 非字符串键（`{1: …}` 写成 `"1"`）；
  - 孤立代理项（Python 到 `encode` 时才报错）。

**真正的 JCS（RFC 8785）**：
- quizs 给新请求的字节做规范化时要用。它是新代码，放在 `@themis/base/jcs`，与 `pyjson` 并列，由 quizs 的 Q0 阶段做，不进迁移的第 ① 步。
- v2 摘要等其他协议需要时，另开内核轮次。

---

## 2. 目标形态

### 2.1 工作区布局

TS 工作区放在仓库根的 `ts/`。它有自己的 `package.json` 与 `bun.lock`，不碰 `desktop/web` 已有的 npm 工程（它有自己的 `package-lock.json` 与门禁流水线）。

```
ts/
  package.json        # 私有工作区，workspaces: packages/*；packageManager: bun@1.4.2
  bun.lock            # 锁文件，提交
  tsconfig.json       # strict、ESM（NodeNext）、erasableSyntaxOnly、allowImportingTsExtensions、noEmit
  vitest.config.ts
  mutations/          # 各模块的变异清单（调度器 mutate 的格式），随模块一起提交
  packages/
    base/             # ① 共享基础库：pyjson、secrets、locks、publish、jsonl（与 quizs 共用）
    contracts/        # 契约：Schema、行为用例、两套实现的探针、契约测试与对照测试
    config/           # ③ kit_config、kit_roles
    dispatcher/       # ④ prepare、run、check、mutate、verdict、integrate
    hub/              # ⑤ 七端 hub 内核
    cli/              # 单一入口 themis：各步移植完的子命令挂在这里，最后打成单文件程序
```

- **包名**：`@themis/*`，`private`，不发布。包名不改：quizs 设计文档直接用 `@themis/base`（pyjson、secrets、locks、publish、jsonl，以后的 sqlite）和 `@themis/contracts`。
- **quizs 的包**：`@quizs/*`，也放进 `ts/packages/`，共用 `bun.lock` 与 tsconfig。
- **包之间按包名 import**（例如 `@themis/base/publish`），在各包的 `package.json` 里写 `"@themis/base": "workspace:*"`。`contracts/test/workspace.test.ts` 实测 Node 与 Bun 都把它解析到 `ts/packages/` 下的真实源文件、不经 node_modules（第 2.2 节）。

### 2.2 运行时与打包

| 项 | 选择 | 理由与核实 |
|---|---|---|
| 主运行时 | Bun 1.4.2（固定） | 1.4.3 发布不到两周，取 1.4.2。内置 SQLite 3.53.2（实测），满足 3.51.3 及以上 |
| 后备运行时 | Node 24.19.0 | 源码只用可擦除的类型语法（`erasableSyntaxOnly`），包内 import 写 `.ts` 扩展名；Node 24 不经构建直接跑同一份 `.ts`（样板实测通过）。Node 不剥离 node_modules 里 `.ts` 的类型，所以包名必须解析到 `ts/packages/` 下的真实路径，由 `workspace.test.ts` 守住 |
| 单文件程序 | `bun build --compile` | 本机实测能打出单文件 exe，样板的探针打成 86 MB 的 exe，行为与源码一致 |
| Node 后备的分发 | `bun build --target=node` 打成单个 `.mjs` | 第 ⑥ 步定 |
| 类型检查 | TypeScript 6.0.3（`tsc -p ts/tsconfig.json`，`noEmit`） | 7.0 是 Go 重写的新编译器，发布才三个月，先不用 |
| 包管理 | `bun install --frozen-lockfile` | 锁文件 `ts/bun.lock` 提交 |

SQLite 的启动检查：
- 进程启动时读回 `select sqlite_version()`，低于 3.51.3 就拒绝运行。
- Bun 用 `bun:sqlite`，Node 后备用 `node:sqlite`（3.53.3）。
- 统一封装在 `@themis/base/sqlite`。第一次用到 SQLite 的那一步才写这层封装，现行实现没有 SQLite。

### 2.3 依赖

现在只有三个开发依赖，运行时依赖为零：

| 依赖 | 版本 | 理由 |
|---|---|---|
| `typescript` | 6.0.3 | 类型检查 |
| `vitest` | 2.1.8 | 唯一的测试框架，与 `desktop/web` 同版本 |
| `@types/node` | 24.19.0 | `node:` 模块的类型，对应本机 Node 24.19.0 |

规矩：
- 每加一个依赖，都写精确版本，并在提交说明里写理由。
- 优先用 `node:` 内置模块。Bun 与 Node 都支持它们，同一份代码两边都能跑。
- Bun 专有的 API（`bun:sqlite`、`bun:ffi`）只放在 `base` 的适配层里，各用一个 Node 的对应实现兜底。

预计会加的依赖：
- **JSON Schema 校验器**：Ajv 8，第一份 Schema 落地时引入，条件见第 3.2 节。
- **其余**：暂无。

### 2.4 测试

- **测试框架只用 Vitest**：契约测试、对照测试、单元测试都在 `ts/`。
- **Python 实现照样受测**：契约测试经探针调用 Python 实现，所以 Python 不需要第二套测试框架。原有的 pytest 测试照旧运行、不删。
- **门禁基准测试暂时仍用 pytest 写**：TS 部分像现在的前端门禁那样，经 pipeline 夹具调用 `ts/` 的 Vitest。等 hub 自己迁完再定。
- **运行方式**：
  - 在 `ts/` 下运行 `node node_modules/vitest/vitest.mjs run`；
  - 契约测试同时要用到 `python`、`node` 与 `bun`（`bun.exe` 要在 PATH 上）。
- **依赖各装各的**：
  - 每个 worktree（kdev、门禁、主工作区）各自运行 `bun install --frozen-lockfile`。
  - 绝不把 `ts/node_modules` 用 junction 或链接共享。T012 吃过亏：主工作区的 `desktop/web/node_modules` 被门禁的 `npm ci` 经链接清空。
  - TS 进生产路径之前，主工作区不用装。

---

## 3. 边界先行：把现有的外部形态整理成契约

### 3.1 要整理的边界

| 边界 | 内容 | 现在的定义 |
|---|---|---|
| 命令的 `--json` 输出 | 七个模块的 `--json` 子命令：`status`、`logs list/show/search/usage`、`metrics`、`config` 与 `plugins` 的约 30 条叶子命令（第 ③ 步）等 | 散在代码与测试里 |
| 合同 | `.agent/plans/<key>.vN.md` 与 `.json`（`schema_version` 1） | `pi_dispatch.validate_plan`、`derive_contract_json` |
| 证据目录 | `meta.json`、`state.json`、`summary.md`、`candidate.json`、`candidate.patch`、`scope.json`、`checks/NN/checks.json`、`executor-report.json`、`events.jsonl`、`run.json`、`history.jsonl`、`mutations/NN/*`、`verdicts/*` 等 | 代码 |
| 信件 | 头部六项、正文七个字段、续行规则、40 行上限 | `kit_hub.render_letter`、`parse_letter` |
| 账本事件 | `ledger/events.jsonl`：`kit_hub.py` 里写死的事件名 59 种，各带自己的字段 | 代码 |
| `state.json` | 主任务与阶段记录、三方合并 | `kit_hub.new_task_state` 等 |
| 配置文件 | `.agent/dispatch.config.json`、`dispatch.local.json`、`.agent/mailbox/runner.json`、`.agent/kit-install.json`、配置历史与审计 | `kit_config.py` |
| 复审报告 | `.agent/reviews/<task>/attempt-NNN*.md` 的固定段落 | `review-draft`、`verdict` |

### 3.2 契约的形式

- **数据形状**：用 JSON Schema 2020-12，与仓库已有的 `schemas/` 同一种，放在 `ts/packages/contracts/schemas/`。
  - Python 与 TS 的输出都经同一份 Schema 校验。
  - 比 Zod 好的地方：Schema 与语言无关，quizs 也能直接用；仓库已有 54 份同类文件。
- **行为**：写成用例（输入、初始磁盘状态、期望的返回与磁盘结果），放在 `contracts/test/`。
- **Schema 校验器用 Ajv 8**，条件：
  - 精确版本，发布满两周；
  - 先作开发依赖，只给契约测试校验两边的输出用；
  - 以后要进生产路径（例如 TS 版 `validate` 运行时用它），另说理由：`validate` 的报错文字是契约的一部分，不能变成 Ajv 的报错；
  - 用 `ajv/dist/2020` 的 `Ajv2020`，开 `strict: true`。默认导出是 draft-07，认不了 2020-12 的 `$schema`。
- **`format`**：
  - `schemas/` 的 54 份里只有一处 `"format": "date-time"`。要引用它，就加精确版本的 `ajv-formats`，否则 strict 模式编译时报 unknown format。
  - 新写的契约 Schema 尽量用 `pattern`，不用 `format`。
  - 第一次引入 Ajv 时，加一条“`plugin-lock-v1`、`plugin-manifest-v1` 在 strict 下能编译”的测试。
  - 不为迁就 Ajv 去改 `schemas/`：离线 v2 的 Python 测试还在用。

### 3.3 探针

每套实现各有一个探针程序：stdin 读一个 JSON 请求（`op` 加参数），stdout 写一个 JSON 结果。
- Python 探针（`contracts/probes/python_probe.py`）只 import `scripts/`，不改 Python 代码。
- TS 探针（`contracts/probes/ts_probe.ts`）由 `node` 与 `bun` 各跑一遍。
- 需要整条命令的边界（`--json` 输出、证据目录），探针换成直接运行两边的命令行，比较输出与磁盘结果。

### 3.4 测试的规矩

1. **契约测试先对 Python 跑通**：契约描述的必须是现行行为。Python 不过，说明契约写错了，改契约，不改 Python。
2. **TS 实现再过同一套契约**：Node、Bun 两种运行方式都要过。
3. **对照测试**：
   - 按种子生成输入，同一输入交给各套实现，返回结果与磁盘结果逐字节一致，或者按契约一致（时间戳、随机编号这类按契约列出的字段除外）。
   - 失败时用例名里带种子，可以重放。
4. **会被几个进程同时使用的模块**（发布、锁、账本），加上“两套实现混在一起并发”的用例：迁移期间，两套实现会同时写同一个信箱和证据目录。
5. **报错文字**（2026-10-22，themistally-15 定）：
   - 会进证据、要被复审或算摘要的（`state.json`、`executor-report.json`、verdict、合同校验结果等），必须与 Python 逐字一致，契约逐字比较。
   - 只进 stderr、退出信息或账本事件的，契约可以只比较异常类型与退出码，但要在契约里写明“只比较类型”。
   - 拿不准属于哪一类，就按第一类处理。
   - 真要复刻 Python 的 repr（例如 DirLock 超时文字里的 owner 字典），只覆盖用到的那类纯 ASCII 字典，不写通用的 repr。
6. **变异检验**：
   - 用调度器的 `mutate --tree <kdev> --spec ts/mutations/<模块>.json`，与内核轮次同一个工具。
   - TS 实现的每个变异都要抓住，漏掉就补测试。
   - Python 一侧也做一份变异，证明契约抓得住 Python 的回归。外部观察不到的，标 `equivalent` 并写理由。

---

## 4. 移植顺序

上一步达到出口条件，才开下一步。每一步都照第 9 节的流程交付。

### ① 共享基础库（`@themis/base`）

| 子项 | 现行实现 | 备注 |
|---|---|---|
| `publish`：永不覆盖的原子发布 | `pi_dispatch.publish_new` | **已做完，作为样板**（第 12 节） |
| `pyjson`：Python 兼容的规范化 JSON | 1.4 节的几种写法 | 逐种写法建契约；浮点数、大整数、码点排序、转义各有专门的用例 |
| `secrets`：疑似凭据检测与脱敏 | `codekit/secrets.looks_like_secret`、`pi_dispatch.redact_secrets/redact_json/redact_obj/redact_tokens`、`codekit/decisions.redact` | 正则逐条对照；用公开的样本串，不用真凭据 |
| `locks`：目录锁与文件锁 | `kit_hub.DirLock`（mkdir 加 `owner.json`，进程不在就接管）、`kit_hub.file_lock`、`kit_config.ConfigLock`、`pi_dispatch.TaskLock` | 两套实现混用同一把锁的并发用例；pid 存活判断 |
| `jsonl`：账本读写 | `kit_hub.Hub.append_event`（文件锁、追加、fsync）、`kit_logs` 的读取 | 两套实现交替追加同一份账本；大文件只读末尾 |
| `clock`：时间与编号的格式 | `kit_hub.utc_now`、`utc_compact`、`new_msg_id`（信件编号）、回合编号，`pi_dispatch` 的时间戳与 attempt 编号 | 第 ③ 步起要写带时间戳的历史与审计，所以挪进这一步；按契约比较格式（正则与解析回读），不比较取值 |

- **出口条件**：六项都通过契约测试（Python 先过）、对照测试、变异检验，`tsc` strict 无错。
- **回退**：这一步的 TS 代码不在生产路径上，无需回退。

### ② 只读命令

- **内容**：调度器入口的只读命令，桌面端读证据用的正是这几条（`desktop/web/src/api.ts` 的信封 command）：
  - `status --json`（`pi_dispatch.cmd_status`）：attempt 行，RUNNING 行加 `live`。`--assess` 与 `--json` 同用时照旧在 JSON 之后接文本行。
  - `logs` 的五个子命令（`kit_logs.py`，经 `pi_dispatch` 的 `forwarded_command` 转交）：`list`、`show`、`search`、`cat`、`usage`。`cat` 是 v1.1 漏写的：分页、游标与脱敏显示都在它身上，第 ① 步的 jsonl 读取原语就是为它准备的。
- **不做的**（v1.2 挪走）：
  - 调度器的 `metrics` 没有 `--json`，只出 Markdown，读的是决策记录与价格表：归第 ④ 步。
  - hub 的 `status --json`、`metrics --json` 是内核的命令：归第 ⑤ 步。
  - 不另建 `themis` 入口：照第 5 节，只认 `pi_dispatch.py` 这一个入口，按选择文件转交给 TS；程序名到第 ⑥ 步撤 Python 时再定。
- **拆成三片**，每片一次提交，各自走契约（Python 先过）、对照、变异：
  - ②a：`status --json`、`logs list`、`logs show`（枚举 attempt、读 state 与摘要、链接与跳过计数）；
  - ②b1：`logs cat`（逐行脱敏、分页与游标、超长行与隐藏行）；
  - ②b2：`logs search`。PATTERN 是用户给的任意 Python 正则，范围按 themistally-15（2026-10-22）收窄：cmd_search 对每行只看 `pattern.search(text)` 的真假，所以逐字一致的只有两样——编译成不成功（含 re.error 的报错文字与位置），以及每一行有没有匹配。做法：
    - 移植 CPython 3.12 的 `Lib/re/_parser.py`（报错照原样）与 `_compiler.py` 里字符集与大小写的部分（`_ignorecase_fixes`、iscased、tolower、toupper）；大小写映射表用 Python 的 `_sre.unicode_tolower`、`unicode_toupper`、`unicode_iscased` 生成（Unicode 15.0），不用 JS 的 toLowerCase；
    - ~~语法树编译成带 u 标志的 JS 正则~~（实做时改了，见第 11 节 ②b2）：JavaScriptCore（Bun）在前瞻里遇到 `^` 会回溯进去，`(?=(…))\k<名字>` 模拟不了原子组；占有量词“每轮取第一个匹配、空轮即停”的语义 JS 也没有。改成照 `_compiler._compile` 编出 sre 的字节码，再把 `Modules/_sre/sre_lib.h` 的 SRE(match)、SRE(search) 移植成 TS 的回溯机（显式上下文栈，不递归）；后顾按 getwidth 判定，不定宽照 Python 报错；
    - `\N{name}` 支持：用 unicodedata 生成 15.0 的名字表（含别名），查找规则照 unicodedata.lookup，表的体积写进提交说明；
    - 反向引用（`\1`、`(?P=name)`）与条件分组（`(?(id)yes|no)`）当时以为 JS 复现不了“有没有匹配”（改成移植 sre 匹配器之后其实能支持，只是不值得，见第 10 节），两套实现都改成拒绝：另开一个内核轮次，Python 先改——cmd_search 编译之前用 `re._parser.parse` 走一遍语法树，遇到 GROUPREF、GROUPREF_EXISTS 报一句固定的错，退出码与非法正则相同（`re._parser` 是私有模块，环境里的 Python 固定为 3.12.10，在代码里注明）；同一轮把括号嵌套深度定成显式上限（超过就报固定的错），让 Python 碰不到取决于栈深的 RecursionError；MAXREPEAT、MAXGROUPS 引起的 OverflowError 是确定的，照原样移植。这算行为变更，第 10 节与桌面端文档的搜索框说明都要记；
    - 对照：随机正则（合法与不合法、各种标志），种子语料取 CPython 的 `Lib/test/test_re.py` 加第 ① 步那批边界字符，比较编译结果与报错文字，以及每行 search 的真假；
  - ②c：`logs usage`（执行端与规划端的用量统计，含读 Claude Code 的会话记录）。
- **出口条件**：
  - 每条命令的 `--json` 输出写好 JSON Schema（放 `ts/packages/contracts/schemas/`，见第 3.2 节；仓库根的 `schemas/` 是离线 v2 的参考件，不混进去），两套实现的输出都过 Schema。第一份 Schema 在 ②a 落地，Ajv 同时引入，第 3.2 节的条件照办；
  - 提交进 `ts/` 的夹具只用合成数据：用 Python 实现在临时仓库里现跑生成，不复制任何真实的证据或信箱（AGENTS.md：证据只读、不提交）；
  - 真实数据的对照：测试时两套实现原地只读同一份 `.agent/runs/` 与信箱，比较输出。这类测试手动开启、不进门禁，什么也不复制。现取的值（`live.elapsed_seconds`）按契约比较格式与范围，不比较取值；
  - 选择文件的 `readonly` 为 `ts` 时，`python scripts/pi_dispatch.py status --json` 与 `logs …` 由 TS 作答，输出与 Python 逐字一致，退出码与 stderr 的报错一致。桌面端的本机服务（桌面端设计 D3）还没建：建成后它调 `pi_dispatch.py`，自然就认选择文件，不另做适配。
- **转交给 TS 的启动器**（`pi_dispatch.main` 读到 `ts` 时）：
  - 参数解析留在 Python：argparse 的帮助与用法错误都带程序名，`-h` 与用法错误由 Python 回答。解析成功之后，把应用默认值之后的完整参数加子命令路径（JSON，格式见 `ts/packages/contracts/schemas/pyargs-v1.schema.json`）经 argv 交给 TS：`--pyargs-b64 <base64>`，不走 stdin（第 ③ 步的 `config secret set --tty` 要求 stdin 本身是终端）。`status --assess` 要调决策模型，留在 Python。第 ⑥ 步撤 Python 时再处理参数解析。
  - stdin、stdout、stderr 让 TS 子进程直接继承句柄，不经管道中转：字节透传自然成立，isatty 与 Python 一致。启动器在转交之前一个字节也不写，等 TS 退出，把退出码原样交出。
  - TS 照 Python 的输出写字节：stdout、stderr 是 UTF-8、`errors=replace`（孤立代理项写成 `?`）；Windows 上文本模式把每个 `\n` 都写成 `\r\n`（原本的 `\r\n` 成了 `\r\r\n`，照样逐个替换）。
  - 找 Bun 要确定：npm 只在 PATH 上放 `bun.cmd`，Python 不经 shell 起子进程认不出它。用 `bun.exe` 的绝对路径，只按 PATH 找（2026-10-22 定，不在 `.agent/dispatch.local.json` 登记，那要走 `config runtime` 与站主同意）：先找 PATH 上的 `bun.exe`（Bun 官方安装器放的就是它）；没有时，PATH 上有 npm 的 `bun.cmd` 垫片，就取它旁边的 `node_modules/bun/bin/bun.exe`（npm 全局安装的布局）。POSIX 找 `bun`。找不到就报错退出，不悄悄退回 Python，与选择文件的严格解析同理。hub 的 `kernel_env` 只去掉决策 API 的 key，PATH 照旧，过滤后的环境里照样找得到（有测试）。
  - 原样转交：stdin、stdout、stderr 按字节透传，不重新编码；退出码原样返回。
  - 连带结束：TS 子进程挂起创建、放进带 KILL_ON_JOB_CLOSE 的 Job 之后才恢复，与 `run_supervised` 同一套（`_WinJob`）。`run_pd` 超时只杀直接子进程（Python 启动器），启动器的 Job 句柄随之关闭，Bun 孙进程跟着结束，不会成孤儿。TS 子进程另起进程组，Ctrl+C 只到启动器：启动器终止 Job，照 Python 写“已取消。”、退出码 130。POSIX 一侧父进程死、子进程跟着死的手段不同（Linux 有 PR_SET_PDEATHSIG 与进程组，macOS 没有对应机制），**未实机验证**。
  - 环境一致：TS 子进程拿到的是这条命令走 Python 时看到的 `os.environ`，只是运行时注入变量（`pi_dispatch.TS_RUNTIME_ENV_DROP`：BUN_OPTIONS、NODE_OPTIONS、NODE_PATH、BUN_INSPECT*）不以原名交给 TS 进程（切换 b 起换名交过去，TS 的入口还原给它起的子进程，见第 ④ 步的 D3）。“环境一致”指命令逻辑看到的变量一致，不包括这些（themistally-15，2026-10-22）：它们不影响 Python 的行为，却能往 TS 进程里塞代码。实测 Bun 1.4.2：BUN_OPTIONS 里的 `--preload` 照样生效，NODE_PATH 让裸模块名多一处解析来源；NODE_OPTIONS 现在 Bun 不理会（Node 后备会）。每个变量各有一条测试。Windows 上经 `os.environ` 转一道，变量名成了大写，变量名本来就不分大小写，不影响取值。
  - **不读当前目录的配置**（实测 Bun 1.4.2，2026-10-22）：Bun 默认从当前目录加载 `.env`（变量直接进 `process.env`）与 `bunfig.toml`（其中的 `preload` 会先执行任意脚本）。TS 子进程的当前目录必须是用户的当前目录（相对路径的参数照它解析），所以启动器固定带 `--no-env-file` 与 `--config=<ts/bunfig.toml>`（仓库里一份只有注释的空配置）。两样各一条测试：当前目录放 `.env` 与带 preload 的 `bunfig.toml`，输出不受影响（对照组不带防护时注入确实生效）。用户级的全局配置（HOME、USERPROFILE、XDG_CONFIG_HOME 下的 `.bunfig.toml`）也有一条测试：实测带不带 `--config` 它都没被执行，测试钉住这一点，Bun 升级后变了就会红。
  - **转交名单写死在代码里**（themistally-15，2026-10-22）：`status`（文本与 `--json`，不含 `--assess`）、`logs list`、`logs show`、`logs cat`、`logs search`、`logs usage`。其余子命令一律由 Python 回答，选择文件写 `ts` 也一样。名单与每条命令交给 TS 的参数键写在一处（`pi_dispatch.TS_READONLY_COMMANDS`），测试核对参数键与 argparse 的 Namespace 一致：argparse 多了一个选项而名单没跟上，测试就红，不会悄悄丢掉一个参数。hub 账本的 `dispatcher.called` 用同一份名单判定 `impl`。
  - **检查顺序**：选择文件在 main 开头读（格式错就拒绝运行，`-h` 也一样）；argparse 解析成功之后，(a) 看命令在不在转交名单里（纯判断，不在就照旧由 Python 回答，名单外的命令不多跑一次 git）；(b) 跑 Python 自己的 `Repo.discover`，出错就由 Python 照原文回答（`pi_dispatch.py:1204` 拒绝在 linked worktree 里运行，“不在 Git 仓库里”之类的报错都不碰 TS）；(c) 再查 TS 入口在不在、装好戳记对不对、Bun 是不是装依赖时那一个；(d) 最后转交。所以 TS 的依赖只需要装在主工作区。（themistally-15 提的次序是 discover 在名单之前；两种次序对外的结果相同，名单在前只是省掉名单外命令的一次 git。）
  - **选择文件读的是正在运行的 `pi_dispatch.py` 旁边那一份**（内核自己的 `scripts/kernel-impl.json`），与 `--repo` 指向哪个仓库无关。TS 入口同理：`pi_dispatch.py` 上一级目录的 `ts/packages/cli/src/main.ts`。选择文件指向 `ts` 却找不到入口（例如有人把选择文件拷进了没有 `ts/` 的仓库），报“选择文件指向 ts，但找不到 TS 入口”，不退回 Python。
  - **装好戳记**（themistally-15，2026-10-22）：`ts/package.json` 根包的 postinstall（`ts/tools/stamp-install.mjs`）在每次 `bun install` 之后写 `ts/node_modules/.themis-installed`：依赖清单的合并哈希、Bun 版本，以及安装时用的 Bun 可执行文件的绝对路径（`process.execPath`）。启动器按 PATH 找到 bun.exe 之后与戳记比对，不同就报“当前找到的 bun.exe 与安装依赖时用的不是同一个：<路径>”，PATH 顺序一变（另装了一个 Bun）不会悄悄换了运行时（themistally-15）。实测 Bun 1.4.2 每次 `bun install` 都跑根包的 postinstall，`--frozen-lockfile` 也一样。合并哈希覆盖 `ts/bun.lock`、`ts/package.json` 与 `ts/packages/*/package.json`，Python 与 JS 各算一份（有对照测试）。启动器每次转交之前现算一遍：戳记不存在报“TS 实现没装好：在 ts/ 下运行 bun install --frozen-lockfile”，哈希对不上报“TS 依赖与 bun.lock 不一致：在 ts/ 下运行 bun install --frozen-lockfile”，都不退回 Python。以后合入的提交改了 `bun.lock`、加了包，主工作区的工作区链接就旧了，这一步把莫名其妙的 import 错误换成一句能照做的话。
  - **主工作区自动跟上**：第 61 轮“站主动过 HEAD 之后的后台回归”多一步：主工作区的合并哈希与戳记对不上，就在落地锁里跑一次 `bun install --frozen-lockfile`，失败写阻塞信。在那之前，戳记检查兜底。
- **切换**：三片都达到出口条件之后，一次提交把选择文件（第 5 节）的 `readonly` 改成 `ts`，照内核轮次走。同在这一次的：选择文件、`meta.json` 的 `impl`、账本事件的 `impl` 与版本、指纹与执行器禁区的改动、戳记与第 61 轮回归的重装；测试：
  - 启动器四条各一条（找不到 Bun 报错、字节透传与退出码、杀掉启动器后 TS 子进程随之消失、环境变量一致），用假入口（Python 脚本）测，不依赖 TS 装没装；
  - 选择文件的严格解析（不存在等于全部 `python`，格式错就拒绝运行）；转交名单与参数键；`kernel_env` 过滤后的环境找得到 Bun；回退（选择文件改回 `python`，输出与没有选择文件时逐字节相同）；找不到 TS 入口、戳记缺失、戳记过期各一条；合并哈希的 Python 与 JS 对照；
  - 端到端：vitest 的 readonly 契约测试加第三种运行方式：引导脚本作为独立的 Python 子进程启动，在里面把 `pd.KERNEL_IMPL_PATH` 指向临时的 `readonly: ts` 选择文件再调 `pd.main(argv)`，每个用例与纯 Python 的输出逐字节比较。句柄继承、Job、退出码、输出次序与“pyargs 由启动器生成”这一环都由它真实覆盖。生产代码里不加“用环境变量改选择文件路径”之类的测试开关（themistally-15）。
  - 改的是内核文件 `pi_dispatch.py`、新增 `scripts/` 下的文件：照第 9 节，合入前跑全部门禁基准；合入后第 61 轮的后台回归再跑一遍。
- **回退**：改回 `python`，一次提交。

### ③ 配置中心

v1.3 按开工前的调查（2026-10-26）重写本节。

- **内容**：`config` 与 `plugins` 两个入口下的全部叶子命令（`secret set` 除外，见下），约 5,000 行 Python：
  - `kit_config.py`（1778 行，其中 argparse 约 150 行留在 Python）、`kit_roles.py`（1382 行）、`kit_plugins.py`（841 行）；
  - codekit 里被它们调用的部分：
    - `plugins.py` 的记录层，约 330 行；
    - `decisions.py` 的设置与题库锁，约 330 行，不含 `probe` 用的 Session；
    - `secrets.py`，约 330 行；
    - `protocols.strict_json_loads`，约 165 行。
  - `config_profiles.py` 配置中心不导入，不在范围内。
  - TS 里还没有的 `pd.*`，约 420 行：
    - 起程序与解析输出：`run_capture`、`child_env`、`resolve_pi_command`（含 `shutil.which` 的 PATHEXT 规则）、`parse_help`、`list_models_*`、`pi_model_readiness`；
    - 读配置与记录：`pricing_table`、`load_binding_record`、`battery_link_problem`；
    - 几项校验用的常量与正则。
  - 叶子命令约 30 条：
    - `config`：`show`、`validate`、`set`、`unset`、`history [show N]`、`rollback`、`init`、`decisions <模式>|marker`、`secret check|remove`、`runtime list|scan|add|remove|probe`、`models`、`profile show|add|edit|remove`、`role show|set`、`preset list|show|save|use|diff|remove`、`doctor`；
    - `plugins`：`list|show|verify|enable|disable`。
- **plugins 归第 ③ 步**。下面三点按 themistally-15 的要求写清。
  1. **两种做法各要多写什么**：
     - 归第 ③ 步：
       - 多移 `kit_plugins.py` 的命令层与 `strict_json_loads`，约 1,000 行；
       - 把 `test_kit_plugins_oracle.py` 的 P1–P17 裁定表（120 条）改写成整条命令的契约。
     - 不归第 ③ 步：
       - `plugins enable|disable` 留在 Python，直到第 ⑥ 步；
       - 这期间 Python 的写入事务（事务、审计、快照）与 TS 的那份一直并存，交替写同一份配置；
       - “交替写”就从过渡期的检查变成一直要守到第 ⑥ 步的约束；
       - 选择文件的 `config` 一项也就说不清“配置中心由哪一套回答”；
       - 到第 ⑥ 步，这 1,000 行照样要移。
     - 两种做法都要移插件的记录层（`validate_lock` 等）：`validate_config` 经 `verify_battery_lock` 用到它。
     - 所以归第 ③ 步总量更少。
  2. **混跑期间靠哪几条契约保证一致**：第 ③b 片起就要有，不管 plugins 归不归第 ③ 步。切换与回退的那一刻，两套实现都会写。
     - **交替写契约**（第 ③b 片建立，第 ③c、③e 片把各自的写命令加进去）：
       - 做法：
         - 在同一个临时仓库里，按种子生成一串写命令，每条随机交给 Python 或 TS 执行；
         - 随机序列里要有失败的命令：整份校验不过、`--expect-state` 对不上（退出 4）、D8 该带 `--yes` 没带；
         - 每一步之后比较：
           - 这一步命令自己的退出码、stdout、stderr；
           - 配置文件与本机文件的字节；
           - `.agent/config-history/` 下的文件名与字节：快照按内容寻址，多写、漏写或换了文件名，`history show` 不一定看得出来；
           - `history --json` 与 `history show N --json`；
           - 审计逐行按契约比较。
         - 比较口径：`at`、`audit_id`、`txn` 只比格式，其余字段逐字比。`history --json` 的每一行，以及命令输出里出现的审计号与时间，照同样的口径比，否则混跑与全 Python 对照的 `at` 必然不同；
         - 同一串命令全交给 Python 再跑一遍作对照，结果按契约一致。
       - 这条契约同时覆盖：
         - 对方写的 intent 与 commit 被认成本资源的事务，不当作 `observed` 的外部改动；
         - 中断的事务由另一套补判 `resolve`；
         - 快照按内容寻址，两边共用；
         - `--expect-state` 的令牌一套算出、另一套能核对。
     - **锁互斥契约**：
       - 两套实现抢同一把 `.agent/.config.lock`，两个方向都测，读改写不丢更新；
       - 被占用时的报错文字逐字一致。第 ① 步的契约只比较了类型，而 TS 的文字与 Python 不同，第 ③b 片改 `@themis/base` 的 ConfigLock，并同步改契约与变异清单。
     - **整份校验契约**（第 ③a2 片起）：`validate --json` 与写入前的整份校验，两套实现对同一份配置给出同样的错误列表，逐字比较：报错会进桌面端的预览，也会进 stdout。
  3. **桌面端本机服务的写路由，切换前后各调哪一套**：
     - 服务一直起 `python scripts/pi_dispatch.py --repo <仓库> config|plugins …`（`ts/packages/ui/src/kernel.ts`），自己不读选择文件。
     - 切换之前全是 Python；第 ③ 步切换之后，转交名单里的命令由 TS 回答，凭据录入作业用的 `secret set` 仍是 Python；回退时改回 `python`。服务都不用改。
     - 服务的预览与执行之间可能隔着一次切换或回退：预览由一套算出 `state`，执行由另一套核对。这正是交替写契约里“令牌一套算出、另一套能核对”那一条。
- **不转交名单**：下面两条命令选择文件写 `ts` 也由 Python 回答，到第 ⑥ 步再移。

  | 命令 | 不转交的原因 |
  |---|---|
  | `status --assess`（第 ② 步） | 要调决策模型 |
  | `secret set`（第 ③ 步） | • `--tty` 的 getpass 在 Windows 上直接读写控制台，不经 stdin 与 stderr；<br>• 网页模式打开的浏览器会落进启动器带 KILL_ON_JOB_CLOSE 的 Job，命令一结束就被杀；<br>• `--verify` 是真实的决策模型请求，花钱 |

  `secret check|remove` 只读或删除，照常转交。
  - 混跑契约：Python 存进去的凭据（file 模式），TS 的 `secret check` 认得出，`secret remove` 删得掉。
  - 凭据库读取（CredReadW）的契约与对照，只用测试专用的目标名（`THEMIS_CONTRACT_<随机>`）与合成的假值：
    - 做法：先写入，两边各读一次，比对，再删除；
    - 不碰真实凭据；
    - 值不出现在输出、日志与断言信息里（AGENTS.md：不读取、输出凭据）。
  - 往 Windows 凭据管理器里写测试目标，动的是用户的凭据库：
    - 要站主同意。themistally-15 2026-10-26 已转问站主，并建议同意，附三个条件：
      1. `system` 模式的往返用例默认跳过，显式打开才跑，只由规划端手动跑；门禁、执行端、hub 的回归都不跑；
      2. 目标名只用 `THEMIS_CONTRACT_` 前缀，在 finally 里删掉；跑之前、跑之后各扫一次残留的 `THEMIS_CONTRACT_*`；
      3. 枚举只按这个前缀过滤，不读、不列别的目标。
    - 站主答复之前，`system` 模式只读一个不存在的测试目标（应当得到 `none`），往返只在 file 模式下做；
    - 写入的白盒路径照 Python 测试的办法，注入假的 advapi32。

  argparse 的帮助与用法错误、`kit_config.main` 里的两条 `parser.error`、没给子命令时打帮助，都在转交之前由 Python 回答，照第 ② 步的规矩。
- **拆成六片加切换**，每片一次提交，各自走契约（Python 先过）、对照、变异：

  | 片 | 内容 | Python 量 |
  |---|---|---|
  | ③a1 | **插件记录与题库锁**：<br>• codekit/plugins 的记录层，含 NFC 与 casefold：照第 ① 步 NFKC 的做法，按 Unicode 15 生成表；<br>• decisions 的设置与 `_check_base_url`（`urlsplit` 的语义）；<br>• 题库锁与题目检查、`describe`；<br>• `pd.battery_link_problem`。<br>这一片没有新命令，用探针做契约 | 约 650 行 |
  | ③a2 | **校验与只读展示**：<br>• 全部键的校验、`load_config`、`validate`、`show`；<br>• 凭据库的读与删（Bun 经 FFI 调 CredReadW、CredDeleteW，Node 后备经辅助进程；FileStore）、`secret check|remove`；<br>• `history`、`history show`（读审计与快照、key_diff） | 约 1,000 行 |
  | ③b | **写入事务与 kit_config 的写命令**：<br>• 事务：审计追加、快照、resolve 与 observed、actor；<br>• 写模式与 state 令牌；<br>• D8：绑定变了又有在跑的 attempt 时要 `--yes`；<br>• ConfigLock 的报错文字；<br>• 命令：`set`、`unset`、`init`、`decisions`、`rollback`。<br>交替写契约与锁互斥契约在这一片建立 | 约 900 行 |
  | ③c | **kit_roles 不起 CLI 的部分**：<br>• 本机文件；<br>• 两资源事务；<br>• `runtime_command`：含 `which`，只解析、不运行；<br>• 命令：`runtime list|add|remove`、`profile *`、`role *`、`preset *` | 约 850 行 |
  | ③d | **CLI 探测**：<br>• `run_capture` 走第 ④a 步的原生 CreateProcessW：PATH 上的 `pi.CMD` 是批处理，Node 不经 shell 起不了；<br>• `child_env`、`--help` 与模型表的解析；<br>• 命令：`runtime scan [--add]`、`runtime probe`、`models`、`doctor [--record]`。<br>假 pi 用 `PI_DISPATCH_PI_CMD` 指向的脚本 | 约 550 行 |
  | ③e | **plugins**：<br>• 命令：`list`、`show`、`verify`、`enable`、`disable`（含文字预览）；<br>• `strict_json_loads`；<br>• oracle 的 P1–P17 改写成契约 | 约 950 行 |
  | ③-切换 | 见下 | — |

  - 依赖次序：③a1 → ③a2 → ③b，之后 ③c、③d、③e 可以换序。
  - `@themis/config` 现在只有 README。包的骨架（`package.json`、`bun.lock` 的工作区登记）由规划端在第 ③a1 片之前单独提交（第 5 节）。
  - **③d 的 `run_capture` 超时**：
    - Python 的 `subprocess.run(timeout=)` 在 Windows 上只 TerminateProcess 直接子进程（`pi.CMD` 的话是 cmd.exe），之后不设时限地 `communicate()`：孙进程（node）还握着管道时，Python 一直挂到它自己退出。TS 走第 ④a 步的 Job，整棵树一起结束。
    - 正常超时的输出两边一致：退出码 124、空 stdout、`timeout after Ns`，契约有用例。
    - 挂住的那种情形不照搬，记进第 10 节作为接受的差别；Python 一侧按第 9 节的冻结规矩不修。
    - 127（FileNotFoundError）与 126（OSError）两条路径各一条契约用例：`str(exc)` 是本地化的 WinError 文字。
  - **混合期**：第 ③ 步切换之后、第 ④、⑤ 步之前，仍是 Python 的内核在进程内调用配置中心的这些名字。③c、③d 把它们做成库函数导出（不埋在命令处理函数里），第 ④、⑤ 步直接用。

    | 调用方 | 名字（行号是 531a608 的） | 由哪份契约覆盖 |
    |---|---|---|
    | `pi_dispatch`（第 ④ 步之前） | `kit_roles.resolve_role_executor`（2381、3883、3894、3943 行） | 绑定解析契约（③c）：对同一份配置，TS 版 `resolve_role_executor` 的结果与 Python 逐字段一致。切换之后 `config role show`、`doctor` 由 TS 回答，prepare、run 解析绑定仍用 Python，两边对同一份配置必须得出同样的绑定 |
    | `pi_dispatch` | `kit_roles.local_command`（2592 行） | 本机文件契约（③c）：同一份 `.agent/dispatch.local.json`，两边得出同样的命令与报错 |
    | `pi_dispatch` | `kit_roles.config_errors`、`binding_tuple`（3913–3915 行） | 整份校验契约（③a2）与绑定解析契约（③c），`binding_tuple` 的相等照 Python 的 `==` |
    | `kit_hub`（第 ⑤ 步之前） | `pd.child_env`、`pd.Repo(...).config()`、`pd.resolve_pi_command` | ③d 的 `child_env` 与 `resolve_pi_command` 契约；`Repo.config()` 由整份校验契约（③a2）覆盖读法 |
- **字节一致的重点**：都是调查列出的风险，各片的契约要专门有用例。
  - **Python 的 `==`**：`1 == 1.0 == True`，NaN 不等于自身。
    - 用在 key_diff、preset 的比较、`binding_tuple`；
    - 在 PyValue 上实现，不比较 JSON 文本；
    - 再补三点，各有用例：
      - int 与 float 按精确值比较：`2**53+1` 不等于 `2.0**53`，尽管 `float(2**53+1)` 等于它；pyjson 读出的大整数不能先转成 double 再比；
      - `-0.0 == 0`；
      - dict 相等不看键序，list 要看次序。
  - **键序**是 dict 的插入次序：只用 pyjson 的 Map。
  - **OSError 的文字会进 stdout**：
    - 有 `[Errno 13] …` 与本地化的 `[WinError 5] …` 两种格式；
    - 复用 `supervise.ts` 的 `windowsErrorText`。
  - **`%-Ns` 按码点补齐**。
  - **`shutil.which`**（本机 3.12.10），以下几条都进契约：
    - PATHEXT 的次序与扩展名的大小写，实测返回 `pi.CMD`；
    - 当前目录优先：Windows 上 `_win_path_needs_curdir` 为真时，把 `.` 插到 PATH 最前面，命中时返回相对路径 `.\pi.CMD`。themistally-15 实测 `NeedCurrentDirectoryForExePathW`：
      - 没设 `NoDefaultCurrentDirectoryInExePath` 时，`pi`、`a\pi`、`a/pi` 都返回真；
      - 设了以后，`pi`、`a/pi` 返回假，`a\pi` 返回真。
      - 内核命令的当前目录是仓库根，这条走得到。
    - PATH 各项按 normcase 去重；
    - PATHEXT 各项先 `rstrip('.')`，空项丢掉；
    - 命令本身已经以 PATHEXT 里的扩展名结尾时，先试原名。
  - **stdout 与 stderr 分开比较**：
    - 合并到同一个管道时，Python 的 stdout 是块缓冲，次序会与 TS 不同；
    - 配置中心的调用方都分开收两路：桌面端写进两个文件，hub 不调 config；
    - 契约写明只分开比较。
  - **凭据**：
    - 契约与对照只在 `CODEKIT_SECRET_STORE=file|off` 下读写；
    - `system` 模式只读一个随机的、不存在的目标，应当得到 `none`；
    - 真实数据的对照设 `off`，不读凭据库。
- **启动器**（第 ③ 步切换时做，照第 ② 步）：
  - **解析与转交**：
    - `pi_dispatch.main` 读到选择文件的 `config` 为 `ts` 时，`config` 用 `kit_config.build_parser()` 解析，`plugins` 用 `kit_plugins.build_parser()` 解析；
    - `kit_config.main` 拆成“解析”与“执行”两步，两边共用解析那一步。
  - **转交名单**：
    - 写死在 `pd.TS_CONFIG_COMMANDS`（路径 → 参数键）；
    - 路径到子命令为止（`("config", "runtime", "add")`），`command` 键是这条路径；`runtime add` 的 `--command` 在 Namespace 里与子命令同名（`args.command`），转交时改叫 `command_option`（第 ③c 片按这个名字读）；
    - `test_kernel_impl.py` 核对它与 argparse 的 Namespace 一致；
    - `argv_impl` 与 hub 的 `dispatcher.called` 照新名单判定 `impl`。
  - **pyargs 加 `context`**（themistally-15 同意，附条件）：
    - 内容是 `kit_root`（取 `pd.KIT_ROOT`）与 `lock_wait_seconds`（取 `kit_config.LOCK_WAIT_SECONDS`），生产里就是这两个真实值；
    - 端到端的引导脚本照改 `KERNEL_IMPL_PATH` 的办法，在进程内改这两个值。这样 plugins oracle 的 junction 夹具与锁占用的用例不用复制整个 kit，也不用加环境变量开关；
    - 迁移期间 TS 只从 `context` 取这两个值，不另设环境变量，也不设默认值；缺了就按内部错误退出；
    - 启动器的测试断言传的正是 `pd.KIT_ROOT` 与 `kit_config.LOCK_WAIT_SECONDS` 的值；变异清单加上“启动器传错值”；
    - `pyargs-v1.schema.json` 原地加 `context`，不升版本，照第 87 轮 `complete_lines` 的做法；`test_kernel_impl.py` 核对参数键的用例跟着改；
    - 第 ⑥ 步撤 Python 时，这两个常量搬进 TS（记在第 ⑥ 步的内容里）。
  - **Ctrl+C**：
    - 经启动器时 TS 子进程另起了进程组，收不到 Ctrl+C，由启动器终止 Job；
    - 如果打断落在持锁的那一瞬（约百毫秒），配置锁会留下，Python 则会删掉；
    - 接受这个差别，记进第 10 节：被硬杀时两套实现本来都留锁，被占用的报错会告诉用户删哪个目录。
  - **直接运行**：`python scripts/kit_config.py …` 与 `kit_plugins.py …` 不读选择文件，照第 5 节只认 `pi_dispatch.py` 的入口。`kit_config.py` 开头的用法说明改成 `dispatch-pi.sh config …` 的写法。
- **出口条件**：
  - 六片各自达到契约、对照、变异的要求，`tsc` strict 无错；
  - 交替写契约与锁互斥契约通过，两个方向都测；
  - 同一串命令分别在两份临时仓库里跑，配置文件、本机文件、历史与审计按契约一致；
  - `config doctor`、`runtime scan|probe`、`models` 对同一组假 CLI 的探测结果一致；
  - 真实数据的对照：手动开启、不进门禁，设 `CODEKIT_SECRET_STORE=off`。两套实现在主工作区只读运行 `show`、`validate`、`history`、`role show`、`profile show`、`preset list`、`runtime list`、`plugins list|verify` 的 `--json` 形式，输出逐字节一致；
  - 桌面端本机服务（`ts/packages/ui`）里调真实内核的测试，在 `config: ts` 下照样通过。
- **切换**：`config` 改成 `ts`，照内核轮次走（第 9 节）。改的是 `pi_dispatch.py`，合入前跑全部门禁基准。
- **回退**：改回 `python`。配置文件、历史与审计的格式由契约保证一致，可以直接接着用。

### ④ 证据与门禁

v1.4 按开工前的调查（2026-10-26，基线 `d1873a9`，用 ast 建引用图，逐个名字核对 `ts/packages` 里有没有）与 themistally-15 的复审重写本节。

- **先决条件（④a）**：已完成（第 8.2 节）。欠的一项：stderr 并进 stdout 的“共用句柄”写法（第 8.2 节“第 ④ 步要处理的”），④b3 已补（supervise 的 `stderr: "stdout"`）。
- **内容**：调度器 `pi_dispatch.py` 里还没切走的全部子命令，共 21 条，外加第 ② 步留在 Python 的 `status --assess`：
  - attempt 的命令：`prepare`、`run`、`collect`、`check`、`baseline`、`mutate`、`verdict`、`branch`、`review-draft`、`integrate`、`mark`、`cleanup`、`wait`；
  - 合同：`validate`、`derive-json`；
  - 其余：`metrics`、`decisions`（replay）、`doctor`、`release-check`、`smoke`、`sync-adapters`。
  - `cmd_planner` 没有注册进 `build_parser`，没有调用方，是死代码，不移植。
  - 规模：attempt 与合同的 16 条命令，闭包约 6,690 行 Python。其中已移植约 1,040 行（进程监督、脱敏、锁、status 用到的读取、一部分配置校验），未移植约 5,650 行。另带 `codekit/decisions.py` 的会话与 HTTP（约 310 行）、`codekit/planner.validate_publication_receipt`（约 42 行）；`decisions`、`doctor`、`release-check`、`smoke`、`sync-adapters` 约 340 行。
- **拆成八片加切换**，每片一次提交，各自走契约（Python 先过）、对照、变异；库函数导出（hub 与后面几片要用），命令处理函数只做编排：

  | 片 | 内容 | Python 量 |
  |---|---|---|
  | ④b1 | **合同**：<br>• 解析与校验：`_md_*`、`normalize_contract`、`derive_contract_json`、`validate_contract`、`invisible_char_warnings`、`validate_plan`；<br>• 路径模式与保护名单（`glob_regex` 照 Python 拼出同样的正则文字，交给 ②b2 的 sre 移植编译）；<br>• `plan_key_from_arg`、`resolve_commit`、planner-v2 发布门禁；<br>• 命令 `validate`、`derive-json`。<br>base 补 `shlex.split`、Unicode Cf 表、Python 的 `str.split()`；pyregex 补不带 logs 限制的编译入口 | 约 1,050 |
  | ④b2 | **证据目录与 git 管道**：<br>• `write_json`、`sha256_file`；<br>• 完整的 `git()`：收 stderr、`index_file`、check 与报错格式，不受 Node 缺省 1 MiB 输出上限所限；<br>• `snapshot_tree`、`tree_drift`、`diff_raw`、主仓库指纹；<br>• `set_state`、`log_event`、`allocate_attempt`、`budget_usage`、`verify_inputs`、`record_candidate`、`evaluate_scope`；<br>• 命令 `mark`、`cleanup`、`wait`（不含 `--assess`）、`metrics`、`release-check`、`sync-adapters`。<br>证据目录契约在这一片建立：两边交替 `set_state`，Python 的 `get_state`、`budget_usage`、`_running_attempts` 读 TS 写的结果要一致（混合期 hub 进程内读它们） | 约 800 |
  | ④b6 | **事件分析与摘要**：`summarize_events`、`extract_report`、`review_hints`、`write_summary`。以探针为主，语料是 stub_pi 的剧本、test_legacy_events 的夹具与 codekit01 的投影，再加随机变形 | 约 905 |
  | ④b3 | **检查与门禁**：<br>• 命令运行器（`_resolve_argv`、`_run_command_item`、`_run_setup`、`prepare_fresh_workspace`）；<br>• `check`（含 `--fresh`）、`baseline`、`evaluate_gates`、`verdict`；<br>• supervise 补共用句柄，`pyWhich` 补 `path=`。<br>出口条件里 check、verdict 的影子运行从这一片起做 | 约 490 |
  | ④b4 | **决策会话**：<br>• `decisions_session`、report-screen、mutation-equivalence、run-health；<br>• `codekit/decisions` 的 `Session`、`http_transport`、`check_answer`、记录读写、`usage_totals`；<br>• 命令 `wait --assess`、`status --assess`、`decisions`（replay）。<br>D4 的 HTTP 对齐在这一片做。实施时拆成 ④b4a（决策客户端）与 ④b4b（命令）；`doctor` 挪到 ④b7：它要的上下文证据、pi 预检与 prepare 是同一套事实（2026-10-27，与 themistally-15 商定），挪过去之前照旧由 Python 回答 | 约 740 |
  | ④b5 | **mutate**：<br>• 清单、轮次、`--tree`、`--check-anchors`、`--out`，interrupted 照 test_mutate_interrupted；<br>• `difflib.SequenceMatcher` 逐行为移植：锚点提示的“最相近的行”与百分比逐字节进 `--check-anchors` 的输出，hub 原样转进信里。<br>出口条件里 `mutate --check-anchors` 的影子运行从这一片起做 | 约 630 |
  | ④b7 | **prepare、run、collect、smoke**：pi 预检、上下文证据、执行说明、领取与 TaskLock；另加从 ④b4 挪来的 `doctor` | 约 875 |
  | ④b8 | **branch、integrate、review-draft**：契约固定 `GIT_AUTHOR_*`、`GIT_COMMITTER_*` 的身份与日期，提交 SHA 就能逐字节比；`merge-tree --write-tree` 要 Git ≥ 2.40，`merge --ff-only` 只在临时仓库里比 | 约 635 |
  | ④-切换 | 见下 | — |

  - 次序：④b1 → ④b2 → ④b6 → ④b3 → ④b4 → ④b5 → ④b7 → ④b8。
  - 依赖：④b3 依赖 ④b1、④b2；④b4 只依赖第 ③ 步的 decisions 设置；④b5 依赖 ④b2–④b4；④b6 只依赖 ④b2，又挡着 ④b7，所以提前；④b7 依赖 ④b1–④b4、④b6；④b8 依赖 ④b2、④b3。
- **开工前定下的四件事**：
  - **D1 Python 的平台与版本**：prepare 写进 `meta.json` 的 `platform`（`platform.platform()`）与 `python`（`platform.python_version()`）；`attempt_origin_notes` 比较当前平台的系统名（3775 行），结果进 verdict JSON 与 `summary.md`；doctor 报 `platform.machine()`。TS 拿不到 Python 的这些值：启动器把它们放进 pyargs 的 `context`，TS 原样用。第 ⑥ 步撤掉 Python 之后 `python` 字段怎么写，到时再定，记在第 10 节。
  - **D2 Ctrl+C 与 CTRL_BREAK**：
    - 问题：经启动器时 TS 在另一个进程组，收不到 Ctrl+C。启动器也没装 SIGBREAK 处理，收到 CTRL_BREAK（桌面端靠它让 run 优雅停下）就按缺省退出，Job 一关，TS 被硬杀，attempt 停在 `RUNNING`；check、mutate、baseline、integrate 同理。Python 的 `run_supervised` 把 SIGINT、SIGTERM、SIGHUP、SIGBREAK 都当中断，照常收尾。
    - 启动器：SIGINT 与 SIGBREAK 都接住，给 TS 的进程组发 CTRL_BREAK（CTRL_C 发不到指定的进程组），之后一直等 TS 自己退出。TS 收到 break 之后要先等 pi 的宽限（`kill_grace_seconds`），再收集证据，所以不设固定的短宽限；用户再按一次 Ctrl+C，或启动器本身被杀（Job 关闭），才结束 Job。
    - 输出与退出码：TS 自己处理了（优雅收尾）的，原样交回。TS 没装处理、按缺省死掉的，启动器按原来的信号补：SIGINT 补“已取消。”、退出 130；SIGBREAK 补 0xC000013A（Python 在 `run_supervised` 之外收到 SIGBREAK 时按缺省退出，什么也不写）。Bun 与 Node 按缺省被 break 结束时的退出码实测确定，不猜。
    - 放在哪：TS 一侧在 ④b3、④b5、④b7 各自的命令里做，用例直接给 TS 的进程组发 CTRL_BREAK，与 Python 收到 CTRL_BREAK 比证据（状态 `CANCELLED`、`run.json` 的 interrupted）。启动器的转发放进切换那一轮：路由到那一轮才有，端到端用例只能在那里跑。
    - 实测（切换 b，2026-10-28；Bun 1.4.2、Node 24.19、Python 3.12，子进程在自己的进程组里收到 CTRL_BREAK）：
      - 没装处理、装了又摘掉、只装 SIGINT 的处理：bun.exe、node.exe、python 都以 0xC000013A 退出，什么也不写。所以 SIGBREAK 那条路启动器原样交回，只有“按的是 Ctrl+C、TS 按缺省结束”要补“已取消。”与 130。npm 的 `bun.CMD` 垫片是 cmd.exe，会写“终止批处理操作吗(Y/N)?”并停在那里；启动器用 `find_bun` 找到的 bun.exe，不经垫片。
      - Python 的 `run_supervised` 只记 `interrupted: true`，不记是哪个信号：Ctrl+C 转成 CTRL_BREAK 发给 TS，证据不变。
      - 不带超时的 `proc.wait()` 在 Windows 上要等子进程退出，信号处理函数一直排不上（子进程睡 5 秒、1 秒时发 SIGINT：处理函数 5.03 秒才运行；带 0.25 秒超时轮询是 1.02 秒）。切换 b 之前经启动器按 Ctrl+C，TS 照常做完，启动器事后才写“已取消。”。
    - 落点（切换 b）：`pi_dispatch._forward_interrupts`，只在 Windows 上装；启动器没有控制台（发不出 CTRL_BREAK，错误码 6）时照以前结束 Job。POSIX 不动：TS 与启动器同在终端的前台进程组，Ctrl+C 两边都收到，启动器照旧终止它（没有实机验证）。
    - 第 ③ 步的 config 写命令：TS 不装处理，经上面的对应照旧是“已取消。”、退出 130，行为不变；第 ③ 步接受的“持锁一瞬留锁”也不变。
  - **D3 交给 pi 的 `NODE_OPTIONS` 等变量**：启动器从 TS 进程的环境里去掉 `TS_RUNTIME_ENV_DROP`（`BUN_OPTIONS`、`NODE_OPTIONS`、`NODE_PATH`、`BUN_INSPECT*`），可 run 与 smoke 起的 pi 是 node 程序，照 Python 的 `child_env` 应当拿到它们（第 ③ 步的探测命令也一样，见第 10 节）。
    - 做法：启动器把被去掉的原值换个名字放进 TS 的环境（`THEMIS_PARENT_<名字>`），换过的原名用逗号连起来放进 `THEMIS_PARENT_NAMES`。不走 pyargs：值会出现在进程命令行里，同用户的任何进程都看得到。
    - 在哪还原（切换 b 改了，themistally-15 同意）：原计划在 `childEnv` 里还原，可 Python 有几处继承 `os.environ` 起 node 程序、不经 `child_env`（doctor 与 smoke 起 `pi --version`、`--help`；git 也继承，钩子可能是 node 程序），只改 `childEnv` 会漏。改成 TS 入口一开始照名单还原进 `process.env`（`@themis/base/parent-env`，cli 的 main.ts 的第一个 import，它和排第二的 harden 都不 import 别的模块，测试锁着这个次序），之后 `process.env` 与 Python 的 `os.environ` 一致。TS 进程自己仍不受影响：这几个变量都只在启动时读，实测 Bun 运行中改 `NODE_PATH` 不多出解析来源（`tests/test_kernel_impl.py` 锁着，Bun 哪天改成运行时读，测试就红）。只还原名单里的，用户环境里本来就有的 `THEMIS_PARENT_` 变量原样交给子进程，与 Python 一样。
    - 放在哪：启动器换名与 TS 的还原都在切换 b（④b7 没有做）。
    - 契约：调用方环境里设上这几个变量，比假 pi 收到的环境，dispatch.config 的过滤与 `env_remove` 一起比。
  - **D4 决策会话的 HTTP**：Python 的 `http_transport` 用 `http.client`。下面几处 Bun 的 fetch 缺省都不一样，逐项对齐：
    - 代理：`http.client` 不走代理（环境变量与注册表都不看）；
    - 证书：ssl 的缺省上下文，Windows 上读系统证书库；
    - 重定向：不跟随（凭据不跟去别的主机）；
    - 超时：每次 socket 操作各算，不是总时限；
    - 原因码：network 带异常类名（`ConnectionRefusedError`、`RemoteDisconnected`、`gaierror`、`SSLCertVerificationError` 等），定一张对照表。
    - 做法：用 `node:http`、`node:https` 一级的客户端，Bun 的实际语义实测。契约只用本机的假端点：拒绝连接、超时、连接被重置、各状态码、回复过大、自签名的 HTTPS。API key 一律用假值；碰 Credential Manager 的用例照站主同意时的三个条件（system 模式缺省跳过、只用 `THEMIS_CONTRACT_` 前缀并在 finally 里删、前后各扫一遍、只按前缀枚举）。
  - **D5 起真调度器子进程的测试**（themistally-15 复审 v1.4 时要求）：
    - 问题：选择文件选了 ts 的命令，测试里起的 `scripts/pi_dispatch.py` 子进程会转交 TS；没装 TS 依赖的工作树里只报“TS 实现没装好”。会遇到的环境：执行端的 attempt worktree、`check --fresh` 的干净副本、门禁的 pre/post 工作区、新建的临时 worktree（A3）。hub 的 scratch worktree（owner sweep、门禁回归、落地预演）只跑 `test_gate_*`，其中起调度器的 ui 门禁流水线自己装依赖，不受影响。
    - 清点（实测，不只靠读代码）：在 d1873a9 的新 worktree 里把选择文件改成无效值跑全量，凡是读真选择文件的用例都失败，8 failed。其中 6 条起真脚本跑调度器命令：`test_exe_search` 的 status、`test_kit_v300` 的 mark、`test_dispatch` 的 doctor、`test_codekit01_fixtures` 以当前实现重算、`test_kit_hub` 的两条锚点核对；2 条有意读它：`test_kernel_impl` 核对提交的选择文件，`test_kit_hub` 的账本用例跑 `--version`（从不转交，只在选择文件本身无效时失败）。另有两条会被启动器的报错蒙过去：`test_dispatch` 的 release-check 只断言非零，`test_kit_v300` 的 RepoArgument 只断言 `ERROR:` 与退出码 2。已经受影响的是 status（readonly，第 64 轮起）与 RepoArgument 的 plugins list（config，第 122 轮起）。
    - 做法：`tests/python_kernel.py` 写一个只有 `pi_dispatch.py` 的 kit，加载真的 `scripts/pi_dispatch.py`，把选择文件指向自己旁边（不放就不存在，等于全部 python）。上面 6 条与 RepoArgument、release-check 经它起，不加内核开关。RepoArgument 收紧为断言“ERROR: --repo 不是目录”，release-check 收紧为断言 `EXIT_USAGE` 与“不在 Git 仓库中”。`test_exe_search` 另留一份经启动器转交 TS 的：`harden.test.ts` 直接起 `main.ts`、不经启动器，守不到 `handoff_env` 带上的第 77 轮防护；`pd.ts_launch_command` 报错时 skip 并写明原因。TS 那一侧由契约测试与装了依赖的全量运行覆盖。以后新增起真脚本的测试照这个办法。
    - 包装与真脚本的差别：包装的进程里只有一份 `pi_dispatch` 模块，真脚本是 `__main__` 加上被别的模块 import 的第二份。在选择文件全是 python 的 worktree 里，把这几条测试起的 47 次调用各经包装与真脚本跑一遍、逐字节比较：除时间、新建仓库的提交号、随机临时目录名与带时间戳的清单文件名（两遍包装之间同样会变）之外，只有两条崩溃的堆栈最外层一帧不同（包装的第 5 行对真脚本的 `sys.exit(main())`），末行相同；codekit01 的投影本来就只取末行。
    - 出口条件（每个环境分开写）：
      1. 不装依赖：新建的 worktree，同一条命令里先核对 `ts/node_modules` 不在、pytest 跑完再核对一次；之前不跑任何会装依赖的步骤（点名运行的 ui 门禁流水线会 `bun install`）。全量 pytest 全过，经启动器转交 TS 的那一份 skip 并写明原因。
      2. 同样的新 worktree，选择文件改成无效值：全量只有那 2 条有意读真选择文件的失败。D5 合入前与 ④-切换那一轮各跑一次。
      3. 装了依赖、选择文件为提交的值：全量全过，TS 那一份真跑。
      4. ④-切换那一轮（`dispatcher: ts`）：1、2、3 再各跑一遍。
- **对照办法**（各片的命令行契约都照这几条）：
  1. 同一场景两套实现各跑一遍，比证据目录。每个文件列出允许变的字段（时间、耗时、pid、临时路径、随机 ID，以及 `meta.json` 的 `impl`：python 对 ts，按设计不同），先核格式，再换占位符，其余逐字节；两边的文件集合也要一致，不多不少。
  2. 每个场景断言自己走到了要测的路径（事件序列、状态转移），免得两边一样地早早失败也算一致。
  3. 同一个 attempt 的各个阶段交替跑：全 Python、全 TS、按阶段交替，再加中途回退（TS 开跑、Python 收尾，反过来也一样），即回退条件。
  4. 跨实现的锁与预算竞争：同一个任务，一个 Python 进程持 TaskLock、allocate，一个 TS 进程来抢，照第 ③ 步的锁互斥契约。
  5. stdout、stderr、退出码逐字节比。hub 解析输出的三处单列用例：prepare 的 attempt 路径（`kit_hub.py` 3039 行）、baseline 的“基线检查记录：”（2538 行，`BASELINE_RECORD_RE`）、`mutate --check-anchors` 的 `MISMATCH`/`MISSING`/`OK` 行（2819 行）。
  - pi 一律用 `tests/stub_pi.py` 的剧本。smoke 与 run 的契约只用 stub_pi；真跑 smoke 会调执行模型、花钱，要站主在对话里明确要求。
  - release-check 的拒绝清单：TS 版照样只报编号、不回显内容，用例用临时清单文件。
  - “崩溃只比退出码”照第 ② 步的规矩：`normalize_contract`、`summarize_events` 遇到深层嵌套抛 RecursionError；md 不是 UTF-8；`latest_verdict` 遇到非数字文件名；`plan_version` 是 `isdigit()` 为真、`int()` 却不收的字符（例如 ²）。
- **base 要补的**（各片用到时带上，不单独成片）：
  - `pyRound` 与 `%.Nf`：Python 对恰在中点的二进制值半数取偶，JS 的 `toFixed`、`Math.round` 不是；
  - 文本模式写文件：Windows 上是 CRLF（derive-json 写的合同 JSON、preflight 的 `pi-help.txt` 等、`metrics --out`、`decisions.jsonl` 的追加）；
  - `shlex.quote`：安全字符集只认 ASCII；Windows 上执行说明里的自检命令用 `list2cmdline`（`supervise.ts` 已有）；
  - `difflib.SequenceMatcher`（④b5）：语料覆盖 `len(b) ≥ 200` 时 autojunk 生效的情形与最长匹配并列时的取法，以 CPython 3.12 为参照。
- **出口条件**：
  - `test_dispatch.py`、legacy 四个文件、v2100、v280、v300 等现有用例（约 300 个）的场景全部有 TS 对应的契约（同场景两边各跑，不逐条重写断言）；
  - 切换之前照第 ③ 步的 A3、A4：在 `dispatcher: ts` 下跑全量 pytest（起真脚本的 legacy 与 test_dispatch 会走 TS，原有断言直接拿来测 TS），没装 TS 依赖的临时 worktree 里再跑一遍（环境照 D5 出口条件 1 证明）；
  - 影子运行：对最近的真实 attempt，TS 版的 `check`、`verdict`（④b3 起）与 `mutate --check-anchors`（④b5 起）的输出与 Python 版按契约一致。做法：
    - 仓库用 `git clone --shared` 建临时副本，新的 Git 对象写进副本自己的库，不碰真的 `.git` 与 `.agent/runs/`；
    - 每个副本各跑 `check --fresh`，各自建工作树，不共用原来的 worktree；
    - 耗时、时间戳换成占位符；每条检查命令的退出码两边必须一致，不一致就两边各重跑一次，还不一致才算差异、去查；
    - 影子运行是重活，不与 hub 的门禁、owner sweep 重叠；切换那一轮拿当时最近的 attempt 把三项再跑一遍（后面几片会改共用的代码）。
  - 至少一片真实切片在 `dispatcher: ts`、hub 仍是 Python 的组合下完整走完并落地。这是迁移验收片，属于站主允许的例外：登记前先告诉 themistally-15，并报告用户。
- **切换**：`dispatcher` 改成 `ts`。同在这一轮的：`TS_DISPATCHER_COMMANDS`（路径 → 参数键）与 pyargs Schema 补上全部命令；`argv_impl` 照新名单；常量表逐项对照（`RESOURCE_FLAGS`、`MUTATION_DEFAULT_TIMEOUT`、状态表、`TOOL_VERSION`）；`context` 加 D1 的平台与版本，以及 `kit_root` 与 `kernel_impl`（④b1 的 kernel_protected_paths 要用，即 Python 的 `KERNEL_TS_ROOT.parent` 与 `read_kernel_impl()`）；D2 的转发与 D3 的换名环境变量；全部命令行契约加“经真的启动器”。改的是内核文件，照第 9 节合入前跑全部门禁基准。
- **不回退**（用户 2026-10-28：“我们不会回退到Python,最后都转为ts”）：切换之后不留改回 `python` 的退路，只为回退准备的交替对照（TS 开跑、Python 收尾）不做；“Python 开跑、TS 收尾”照做（切换那一刻 Python 已经 prepare 的 attempt 由 TS 接着跑）。
- **混合期**：`dispatcher` 切到 `ts` 之后，hub 仍是 Python，`kit_hub.py` 在进程内直接调用的 `pi_dispatch` 名字仍是 Python 版（`d1873a9` 时 26 个；`139a0fa` 时 27 个，多了第 123 轮的 `quiet_error_mode`，由第 ⑤ 步的 ⑤j 补 FFI）。这些名字到第 ⑤ 步之后才能删，期间要由契约保证它们读得懂 TS 版写的东西：

  | 名字（`kit_hub.py` 里的次数） | 用途 | 由哪份契约覆盖 |
  |---|---|---|
  | `pd.get_state`（10） | 读 attempt 的 `state.json` | ④b2 证据目录契约：Python 的 `get_state` 读 TS 写的 `state.json` 得到同样的状态 |
  | `pd.pid_alive`（7） | 锁的持有进程还在不在 | 第 ① 步 `locks` |
  | `pd.Repo`（5） | 找仓库、读配置 | 第 ③ 步配置契约 |
  | `pd.run_supervised`（5） | 回合与门禁命令的进程监督 | ④a；hub 的 pytest 两边传同一个文件对象，TS 的共用句柄写法 ④b3 已补 |
  | `pd.DispatchError`（4） | 异常类型 | 不跨语言，留在 Python |
  | `pd.RESOURCE_FLAGS`（2）、`pd.MUTATION_DEFAULT_TIMEOUT`（1） | 常量 | 切换那一轮：两套实现的常量表逐项对照 |
  | `pd._md_section`（2）、`pd._CHECK_LINE_RE`（1）、`pd._md_scope_lists`（1） | 解析合同 Markdown | ④b1 合同契约（`derive-json` 的输入输出） |
  | `pd.compile_patterns`、`pd.matches`（各 1） | Scope 的路径通配 | ④b1 路径模式契约 |
  | `pd.child_env`、`pd.run_capture`、`pd.parse_help`（各 1） | 子进程环境与 pi 的探测 | 第 ③d 步 |
  | `pd.publish_new`（1） | 发布信件 | 第 ① 步 `publish` |
  | `pd.resolve_pi_command`（1） | 解析 pi 的命令 | 第 ③c 步角色绑定契约 |
  | `pd.write_json`（1） | 写证据 JSON（`indent=2`，不排序） | ④b2 |
  | `pd.budget_usage`、`pd._running_attempts`（各 1） | 各合同版本累计的 attempt 与墙钟、正在跑的 attempt | ④b2 证据目录契约（读 TS 写的 claim 与 `run.json`） |
  | `pd.argv_impl`、`pd.TOOL_VERSION`（各 1） | 账本记由哪一套回答 | 切换那一轮 |
  | `pd.read_kernel_impl`、`pd.TS_STAMP`、`pd.ts_deps_digest`、`pd.find_bun`（各 1） | 启动器与装好戳记 | 不属第 ④ 步 |

### ⑤ 七端 hub 内核

v1.6 按开工前的调查重写（2026-10-29，基线 `139a0fa`，只读盘点，themistally-15 复审）。

- **内容**：`kit_hub.py` 全部（6625 行、251 个顶层定义），含 hub 自己的 `status --json`、`metrics --json`。`tests/test_kit_hub.py` 的场景（现在 298 个）照第 ④ 步的规矩两边各跑，不逐条重写断言。工人运行时照旧是 `claude -p` 与 `pi --mode json`；quizs 替代 pi 另开轮次做。
- **已经备好的**：hub 在进程内调的 27 个 `pi_dispatch` 名字里，21 个在 TS 里已有对应；缺 `argv_impl`、`read_kernel_impl`、`TS_STAMP`、`ts_deps_digest`（只在 `ts/tools/stamp-install.mjs` 里有）与 `quiet_error_mode`（base 没有 SetErrorMode 的 FFI），`_running_attempts` 有但没导出。base 已有时钟与编号、账本追加、`DirLock`、与 msvcrt 互斥的文件锁、原子写、pyjson、Python 字符串与正则的辅助、不覆盖的 `pyRename`、支持共用句柄的 `runSupervised`；JEV 用的决策会话在 config 包。
- **逐字节的主要风险**（各片照此写契约）：
  - 约 105 处按码点截断、`len()`；`splitlines`、`strip`、无参 `split`、`lower` 的 Python 语义：一律用 base 的辅助。
  - 约 30 个常量正则：Python 的 `$`、Unicode 版的字符类；`FRONTEND_TRANSITIONAL_RE` 用了反向引用（见 E6）。
  - 七种 JSON 写法（sort_keys 与否、indent 0/1/2、ensure_ascii），`INPUTS.json` 在 Windows 上是 CRLF；银行家舍入与 `%` 格式。
  - 异常文字会进给站主的信与账本：只对齐类型名，堆栈照第 3.4 节只比类型。
  - Python 全同步，TS 的进程监督、文件锁、决策会话是异步：Engine 每一步严格串行 await，一个 runner 内不并发。
- **开工前定下的**：
  - E1 调度器怎么调：TS hub 照旧起 Python 启动器（`python scripts/pi_dispatch.py …`），选择文件仍只在启动器读（第 5 节）。账本 `dispatcher.called` 的 impl 由 TS 移植的 `argv_impl` 与转交名单算，契约逐个 argv 形状对照 Python。第 ⑥ 步撤 Python 时改成直接起 TS 入口。
  - E2 站主命令走哪一套：切换后 `kit_hub.py` 的全部子命令都转交 TS（同第 ④ 步的启动器），站主命令与 runner 用同一套实现，不让两套同时写信箱。切换时先经 `exclusive` 等执行端跑完、停掉 Python 的 supervisor，再翻选择文件、起 TS 的。混跑契约只覆盖切换那一刻（三方合并、DirLock、文件锁的交替与并发）。
    - 停没停掉做成机械的检查，不靠人记（themistally-15 提出：T024 的 hub 是 Start-Process 脱离起的，这种进程容易漏）：翻选择文件之前看 `.runner`、`.runners` 下的锁与 `agents/owner.json` 里的 pid 是否还活着，有活的就拒绝翻，并报出是哪个 pid。
  - E3 内核文件指纹：hub 为 ts 时纳入 `ts/packages/{base,config,dispatcher,hub,cli}/src/**` 与 `ts/package.json`、`bun.lock`、`bunfig.toml`；开销在 ⑤j 实测，每轮超过 50 毫秒就改成按修改时间缓存。
  - E4 回退：照“不回退”（用户 2026-10-28）。原先写的“停掉 TS hub、起 Python hub”删去；TS hub 出了问题照常修 TS。Python hub 留到第 ⑥ 步，只为对照与影子运行。
  - E5 迁移计划 10.1 里的 `retry_section` 改进是行为变更：切换之后另开内核轮次在 TS 上做，不混进逐字节移植的片。
  - E6 `FRONTEND_TRANSITIONAL_RE` 的反向引用：按三种引号展开成三个分支（双引号、单引号、反引号各一支，分支里的否定前瞻换成对应引号的字面量），交给 pyregex 编译（themistally-15 提出）。反向引用只可能是这三个字符之一，同一位置只有一支能开头，最左匹配与匹配长度都与原式相同；空白、单词字符、多行下的行首、点号都保留 Python 语义（手译成 JS 正则要逐个对齐的远不止点号）。pyregex 不记捕获组，标题从整段匹配里取：开引号之后到末尾的闭引号之前。对照另外生成带 U+FEFF、0x1c 到 0x1f、0x85、U+2028、U+2029 与非 ASCII 字母的标题，不只靠真实语料。
- **拆片**（每片一次提交：Python 先过契约，TS 再过，Node、Bun 各一遍；对照按种子生成输入；变异检验；库函数导出，命令处理只编排）：

  | 片 | 内容 | Python 行 | 依赖 | 契约与对照 |
  |---|---|---|---|---|
  | ⑤a | 常量与名册、schema 子集校验器、信件（解析、渲染、letter_errors）、主任务状态与守卫（guard、allowed_moves、routine_moves、render_routine_brief、invalidate_after）、阶段状态表 | 约 900 | 无 | 随机状态 × 全部（信件类型, 阶段）比 guard 文字与允许的下一步；随机信件（全角冒号、续行、超长、补充平面字符）的解析与往返 |
  | ⑤b | 信箱、账本与状态：Hub、HubState 三方合并、agent 记录、投递与收信、扣信 | 约 350 | ⑤a | 混跑契约：两套实现交替、并发改同一键与不同键（state.json 逐字节、state.conflict），并发投递不覆盖，take 与 requeue 的改名竞争 |
  | ⑤c | 回合审计：事件流、claude 与 pi 的审计、守卫配置、花费、半截会话 | 约 450 | ⑤a | 事件流夹具加随机变形，审计结果逐字节；guard.ts 与 TS 审计同一份配置三方一致；真实回合的回放一次（不进提交） |
  | ⑤d | 回合启动与输入：TurnRunner、提示词与模板、输入目录、交付文件核对 | 约 800 | ⑤a–⑤c | 注入 launcher：同一状态与剧本下两边的命令、环境（按名单）、role.md、prompt.md、result.json（时间与编号换占位）、INPUTS.json（含 CRLF）逐字节 |
  | ⑤e | 合同与战前门禁（含 E1 的 run_pd 与 argv_impl） | 约 500 | ⑤b | 临时仓库加真调度器：.agent/plans 下的文件、git 提交与 refs（固定作者与日期，SHA 可比）、问题清单逐字 |
  | ⑤f | 战后门禁与变异 | 约 400 | ⑤e | pytest 输出与 mutations.json 的语料对照；真工作树上跑白盒与 mutate --check-anchors |
  | ⑤g | 执行端代办与 JEV：派遣、接着改、返工与重派、交付信 | 约 750 | ⑤e、⑤f | contracts 的 attempt 夹具：各种状态组合下的结论、改写后的合同、交付信逐字；JEV 用假端点 |
  | ⑤h | 结项、落地与后台回归：finalize、撤销落地、复审记录、owner sweep 一族（补 TS_STAMP、depsDigest，导出 runningAttempts） | 约 650 | ⑤b、⑤g | 临时仓库的落地链：提交 SHA、复审记录字节、owner-sweep.json；Python exclusive 对 TS 结项的锁与标记 |
  | ⑤i | 调度循环与 Engine | 约 930 | ⑤a–⑤h | 同一初始信箱、同一回合剧本，两边跑到静止，比信箱、state.json、事件序列（时间与编号换占位）；被收掉之后续接、扣信、当场重交、代办到一半 |
  | ⑤j | 命令行与进程模型：子命令、内核文件指纹与换代（E3）、supervisor、exclusive、owner-sweep、status 与 metrics 的 --json、SetErrorMode 的 FFI、kit_hub.py 的转交（E2） | 约 1100 | ⑤i | stdout（CRLF）、stderr、退出码逐字节；supervisor 一轮（假子进程）；经真启动器各一遍；定 hub 命令的耗时目标（见下） |
  | ⑤-切换 | 选择文件的 hub 改成 ts；kernel_files 纳入 TS 源码；回合事件与 result.json 记 impl；全部门禁基准；验收片 | — | 全部 | 见出口条件 |

  ⑤a→⑤b→⑤c→⑤d；⑤e 只依赖 ⑤b，可以与 ⑤c、⑤d 并行；⑤f→⑤g→⑤h；⑤i 等前面全部；⑤j 最后。298 个场景按领域分到各片（⑤a 36、⑤b 约 10、⑤c 16、⑤d 46、⑤e 约 25、⑤f 约 14、⑤g 27、⑤h 33、⑤i 46、⑤j 约 44）。
- **影子运行**（⑤a、⑤b 之后就做起来，后面几片期间一直跑着攒证据）：
  - TS 加一个只读子命令，不拿 hub 的锁、不写 `.agent/mailbox`，结果写到 `.agent/runs/_shadow/`。轮询 `state.json` 的哈希与各信箱 `new` 下的文件名，变了就取快照。
  - 同一份快照交给 TS 与 Python 探针（探针在进程内调 kit_hub 的纯函数，不起 hub）：每个主任务 × 阶段 × 信件类型的 guard 结论、允许的下一步、内核代办的结论与任务书全文、新信的解析与往返。
  - 事后核对：账本里新出现的 `letter.rejected`、`route.kernel` 与 TS 在之前最近一份快照上的结论比；新回合的事件流用 TS 审计重算，与 Python 写下的 result.json 比。
  - 不改 Python 埋点（迁移期间内核文件只修挡路的缺陷）。轮询很轻；回合审计的重算在空闲时做，不与门禁、扫描、全量测试重叠。
  - 快照要防“取了一半”：取之前与之后各算一次 state.json 的哈希、核对各信箱 `new` 下的文件名，不一致就重取。事后核对时，快照与Python 当时的决定之间有时间差，对不上的先单列成“时序”一类逐条查，不直接算作不一致（themistally-15 提出）。
  - `.agent/runs/_shadow/` 要被各处扫描跳过：budget_usage、metrics、status、`_running_attempts`、cleanup，以及 hub 自己按目录名遍历的地方。`TASK_ID_RE` 要求首字符是字母或数字，按理都会跳过，用一条契约钉住。
  - **做成**（⑤-影子，2026-10-31；本该 ⑤a、⑤b 之后就做，⑤c 合入后才补上）：`ts/packages/contracts/tools/hub-shadow.ts`，--once 静态重放，--watch 有变化才重算；验收是主仓库上的静态重放零差异。付费任务的全程比对（出口条件那一条）等 ⑤d 合入、提示词与输入目录也进了影子之后，拿具体方案问用户。列 runs 下任务目录的五处（pending_attempt_notes、_running_attempts、cmd_status、cmd_metrics、cmd_decisions）由契约钉住跳过 _shadow。复核后补（themistally-15 复核 d1eff67 时指出）：上面“事后核对”的后半句起初漏了，影子只比两边探针彼此一致；补上之后，--watch 开始以后才结束的回合，TS 的审计还要与 hub 当时写下的 result.json 比（只比同一版内核写下的），这一类与 route.kernel、letter.rejected 两类比的才是“TS 与真实 hub 的决定一致”。
  - **付费全程比对**（2026-10-31 用户批了方案页里的做法，任务是桌面端 D3 第一片）：开跑前给影子补了“对不上时另存快照”（themistally-15 定的条件）。同一个差异键只存第一次（snapshots/index.json）；盘上已有 10 份或合计 2 GB 就只记报告，写明“快照已达上限”。目录按序号命名，类与键、各文件的路径大小哈希、kit_hub.py 的哈希、主仓库的 HEAD 记进 manifest.json。只带重放要用的：快照本身、上一份快照里要用的几样、提示词读过的任务书与 runs 记录；回合几类对不上才带那几个回合比对时读到的文件与会话文件；不带指向主仓库 git 目录的 .git（谁在留下的目录里跑一次 git status 就会刷新主仓库的 index）。`--snapshot <目录>` 从另存的快照重放：先复制到临时目录，watch 时的上一份快照照记下的重建；kit_hub.py 与另存时不同就报出来，退出码 4。会话文件是工人的完整对话：快照只放在本机的 .agent/runs/_shadow/snapshots/ 下，查完就删（只删那里的目录），不提交、不外传。回合文件随之改成只读一次字节：比对与另存用同一份，解码照 read_text（UTF-8、坏字节报错、通用换行）。变异：hub-shadow.ts.json 加 S25–S33（9 条），33 个里 32 个第一轮抓住；S32（另存时带上 .git）漏过一次：夹具仓库本来没有 .git，断言空过，keep-route 那条照主仓库的样子放了 .git 指针后单独重跑抓住。S18 的锚点随回合文件只读一次改写。
  - **付费全程比对的结果**（2026-11-01）：
    - 任务：T025（桌面端外壳第 1 片）04:26Z 登记、09:57Z 结项，verdict PASS 并 integrate。合同出了三版、执行三次：v1 的 V01 要匹配“# pass”，门禁机 Node 24.19.0 的 node --test 输出被管道接走时默认是 spec 报告，出不来这一行；v2 的 attempt-002 被终审以 3 条真缺陷退回；v3 的 attempt-003 落地。
    - 影子 --watch：04:20:55Z 开跑，最后一轮 09:59:09Z，共 30 轮，0 差异、0 出错，result_json_other_kernel 0，没另存过快照，峰值 1028 MB。hub 停下以后信箱不再变化，影子空转，按启动时刻核对后停掉。
    - 逐轮计数只留下第 12–24 轮（themistally-15 的只读记录器；watch 每轮覆盖 latest.json，只有带差异或连着出错的那一轮另存，累计计数随 ⑤e0 补上）。这 13 轮合计比过：状态 13、主任务 21、提示词 109、信件 16、代办 9、route.kernel 6（与账本 6）、回合 18、回合与 role.md 6、回合与 result.json 6，全部一致。第 1–11 轮与第 25–30 轮当时只能由“_shadow 下没有带时刻的差异文件、没有 snapshots/”间接证明，后由下面的补比补上。
    - 结项后的 --once（11:33:50Z，结果在 _shadow/once-T025/）：状态 1、主任务 26、提示词 179、信件 1228、代办 597、route.kernel 77（与账本 77）、回合 1625，guard 组合 46800，0 差异，峰值 1013 MB。
    - 资源：每分钟一次的记录里，观察期内空闲内存最低 2987 MB（09:25Z）、C 盘最低 11.74 GB（09:54Z）。09:22:25Z themistally-15 实测空闲 2418 MB、提交余量 2657 MB：09:18–09:23Z 本机另有一组经 SSH 起的 java 进程（约 4.9 GB），不是 hub 或影子起的。停影子的线（2 GB 内存、3 GB 盘）没碰到。那一阵 Claude Code 停掉了规划端的两个后台盯梢（等待脚本与记录器），T025 在没人盯的时段结项。
    - 09:00Z 太平洋时间从 PDT 回拨到 PST：提交时间里 -0700 与 -0800 并存是这个原因；第 24–30 轮都在回拨之后，同样 0 差异。
    - 补比（⑤e0 合入后，b2eeceb，12:48:04Z）：--once --records-since 2026-11-01T04:20:55Z（结果在 _shadow/recheck-T025/）。04:20:55Z 之后结束的 14 个回合（与 themistally-15 照 result.json 独立数的一致：都是同一内核，都有 finished_at、role.md），逐个与 hub 当时写下的 result.json、role.md 比：“回合与 result.json”14、“回合与 role.md”14，全部一致；别的内核 0、读不出结束时刻的 0。其余各类与结项后那次 --once 相同（回合 1639，多出的 14 是 role_prompt 的请求），0 差异，峰值 1069 MB。a7bd592 到 b2eeceb 之间 kit_hub.py、scripts/hub、AGENTS.md 都没改过，role.md 对得上不是碰巧。付费全程比对期间结束的 14 个回合都比过，全部一致。
- **出口条件**：
  - 场景用例全过，并且做一次覆盖审计（themistally-15 提出，第 ④ 步切换 c 的教训：pytest 一条调度器命令都没交给 TS）：298 个场景逐个对到 TS 契约，记成 COVERED、PARTIAL、MISSING，切换前 MISSING 清零或写明理由；每片交付时写明这一片对掉了哪些场景；
  - 影子运行：一片切片从登记到结项，零差异；（2026-11-01 T025 满足：watch 30 轮零差异，结项后的 --once 与按时刻补比 14 个回合也都零差异，见“付费全程比对的结果”）
  - 至少一片切片由 TS hub 从头到尾办完并落地（验收片，登记前先告诉 themistally-15，并报告用户）。
- **计时**：第 9 节的固定项加上 hub 的命令（`kit_hub.py status`、`status --json`、`metrics --json`）与空闲时调度循环一轮的耗时（E3 的指纹开销就在里面）；⑤j 定目标，切换时对照（themistally-15 提出）。
- **切换**：选择文件的 `hub` 改成 `ts`，次序照 E2。切换的验收里专门走一遍站主在主工作区的提交：`exclusive` 包住提交，再跑 owner-sweep，两者都经 TS（themistally-15 提出）。
- **不回退**：照 E4。

### ⑥ 撤掉 Python

- **前提**：全部组件选 `ts`，连续三片切片没有回退。
- **内容**：
  - 删掉在用的 Python 模块；
  - `dispatch-pi.sh` 直接调单文件程序；
  - `kit_install` 换成第 6 节的最终形态；
  - 统一核对 AGENTS.md、技能、README 里的命令；
  - 移植不转交名单里的命令（第 ③ 步）：
    - `status --assess`；
    - `secret set`，到时要解决三件事：
      1. 隐藏输入：经 FFI 打开控制台、关掉回显，照 `win_getpass` 处理回车、换行、Ctrl+C 与退格；
      2. 浏览器脱离 Job：带 `CREATE_BREAKAWAY_FROM_JOB`，Job 设 `JOB_OBJECT_LIMIT_BREAKAWAY_OK`；
      3. `--verify` 怎么对照：找不花钱的办法（本机假端点），或者明确写成人工核对，到时再请站主同意；
  - 启动器经 pyargs 的 `context` 传给 TS 的 `kit_root`、`lock_wait_seconds`（第 ③ 步），改由 TS 自己定义。
- **回退**：Git 历史里留一个标签（`python-final`），需要时从它恢复。

---

## 5. 两套实现并存时，hub 认哪一套

只认一个提交进仓库的**选择文件** `scripts/kernel-impl.json`：

```json
{"schema_version": 1, "readonly": "python", "config": "python", "dispatcher": "python", "hub": "python"}
```

- **谁读：只有两个 Python 入口的 main 开头**：
  - `pi_dispatch.py` 的 main 管 `readonly`、`config`、`dispatcher`。AGENTS.md 写明 `python scripts/pi_dispatch.py <子命令>` 与 `bash scripts/dispatch-pi.sh` 等价：`dispatch-pi.sh` 只是 exec 它，`kit_hub.run_pd` 也是起它的子进程，`status`、`metrics`、`logs`、`config`、`plugins` 都是它的子命令。所以只在这一处读、转交给 TS，所有入口就都认了。
  - `kit_hub.py` 的 supervisor 入口管 `hub`。
  - 不在 `dispatch-pi.sh`、`run_pd`、本机 UI 服务里各读一遍。第 ⑥ 步撤 Python 时，再让 `dispatch-pi.sh` 直接调程序，同时改 AGENTS.md 那句。
- **严格解析**：
  - 文件不存在，等于全部 `python`。
  - 存在但读不了、多键或少键、值不是 `python`/`ts`、`schema_version` 不是 1，都报错、拒绝运行，不悄悄退回 `python`。否则“运行中的内核”与提交的选择对不上。
- **记下是哪一套产生的**：从第 ② 步起，证据和账本都记实现与版本，复审时才分得清。
  - attempt 的 `meta.json` 加 `impl` 与版本；
  - hub 的 `dispatcher.called` 事件与回合事件也加。
  - 这是证据与账本格式的改动：第 ② 步做的时候照内核轮次走，在 r3 §10 记一轮。Python 版同时写 `impl: "python"`，不能只有 TS 版写。
- **何时加**：第 ② 步第一次需要切换时才加。在那之前，这个文件不存在，也不读，等于全部是 `python`。
- **读哪一份**：正在运行的 `pi_dispatch.py`（或 `kit_hub.py`）旁边那一份，即内核自己的 `scripts/kernel-impl.json`，与 `--repo` 指向哪个仓库无关。
- **随 kit 安装**：第 ⑤ 步之前不随 kit 安装，TS 也不装（第 6 节）。目标仓库里没有这个文件，就全是 `python`。所以它不进 `KIT_LOADED_FILES`（`kit_install.py:199` 装的正是这份清单）。
- **怎么改**：每次切换都是一次提交，在 kdev 里改、测试、照第 9 节的流程合入，不在主工作区直接改。提交说明写明切了哪个组件、出口条件的证据。
- **回退**：把对应的值改回 `python`，再提交一次。
- **自动换代**：内核文件指纹（`kit_hub.kernel_files`）管的是 hub 进程里加载的代码，换了就要在两步之间重启 hub。第 ② 步起把选择文件纳入；`ts/packages/*/src/**` 暂不纳入：TS 每条命令现起进程、现读源码，hub 进程从不加载它（2026-10-22 与 themistally-15 定）。第 ⑤ 步 hub 换成 TS 时，再按选择文件把那一套入口纳入。
- **执行器的禁区**（第 ② 步切换起，与 themistally-15 定）：
  - `scripts/kernel-impl.json` 无条件进 `PROTECTED_PATTERNS`，与 `pi_dispatch.py` 同等对待。
  - 内核的 TS 部分有条件：被检查的仓库就是内核自己所在的仓库（真实路径比较，8.3 短名、junction、大小写都看穿），并且选择文件至少有一项是 `ts`。`PROTECTED_PATTERNS` 随 kit 装进目标仓库、外部布局也会指向别的仓库，目标项目自己的 `ts/` 不能受影响；回退到全 `python` 时 TS 不在生产路径上，限制随之解除。
  - 禁的范围（`pi_dispatch.KERNEL_TS_PROTECTED`，第 69 轮从整个 `ts/` 收窄，与 themistally-15 定）：内核的包（`ts/packages/` 下的 base、cli、config、contracts、dispatcher、hub）；决定加载哪份代码、怎么装的工作区文件（`ts/package.json`、`bun.lock`、`bunfig.toml`、写装好戳记的 `ts/tools/`，`tsconfig.json` 的 paths 也影响模块解析）；决定门禁与变异检验跑什么的 `vitest.config.ts` 与 `ts/mutations/`。其余的包（桌面端本机服务的 `ts/packages/ui`）交给合同的 Scope 管：`PROTECTED_PATTERNS` 优先于 Scope，整个 `ts/` 都禁的话，这些包永远派不出去。新包的骨架（`package.json`、`bun.lock` 的工作区登记）由规划端先提交，执行器不碰锁文件。新加内核包要同时列进名单，有测试核对磁盘上的包都在名单里（`ui` 除外）。
  - 每个 attempt 冻结一次：prepare 时算出、记进 `meta.json` 的 `kernel_protected`，run 的执行说明与 collect 的范围门禁都用记下的那份。attempt 跑到一半时切换或回退，范围门禁照样与派遣时的合同对得上。
  - 不加进 `KIT_LOADED_FILES`，理由见上。

---

## 6. kit_install 的变化

| 阶段 | 装进目标仓库的东西 | 说明 |
|---|---|---|
| 现在到第 ⑤ 步 | 照旧：Python 文件与数据文件（`KIT_LOADED_FILES`、`scripts/hub/`、`plugins/decisions/` 等） | TS 部分只在本仓库开发，不随 kit 安装；`scripts/kernel-impl.json` 也不装，目标仓库里没有它就全是 `python`。有人把 `readonly: ts` 的选择文件拷进没有 `ts/` 的仓库，启动器报“选择文件指向 ts，但找不到 TS 入口”（第 ② 步） |
| 第 ⑤ 步完成后 | Python 文件照旧，另加单文件程序 `themis`（Windows 为 `themis.exe`）与 `kernel-impl.json` | `.agent/kit-install.json` 记下程序的版本与 sha256，`update` 时核对；目标仓库也能退回 Python |
| 第 ⑥ 步 | 只装单文件程序与数据文件；`dispatch-pi.sh` 改成调用程序的薄封装 | Node 后备：另附 `themis.mjs`（`bun build --target=node`），用 `node themis.mjs` 运行 |

`kit_install.py` 本身在第 ⑥ 步之前一直用 Python。它的 TS 版跟在第 ③ 步之后移植：它只做文件比对与复制，风险低。

---

## 7. 离线 v2 参考实现的处置

- **不逐行移植**。这 2.3 万行是 v2 设计的参考实现，不在运行路径上；v2 的 TS 实现按设计文档另开轮次重写。
- **`schemas/` 保留，当契约资产用**：
  - 其中 `plugin-lock-v1`、`plugin-manifest-v1` 与在用的插件管理有关，第 ① 步之后的契约直接引用；
  - 其余等对应的 v2 功能用 TS 实现时再用。
- **测试**：只对 Python 参考实现有效，原样保留到第 ⑥ 步。
- **第 ⑥ 步再决定**：整体移到 `legacy/v2-python/`，或者只留 Git 标签，届时请站主定。

---

## 8. 技术约束的落实

### 8.1 SQLite

- 权威库必须用 3.51.3 及以上（含 WAL-reset 修复）。
- 本机实测：
  - Bun 1.4.2 内置 3.53.2；
  - Node 24.19 的 `node:sqlite` 是 3.53.3；
  - Python 3.12.10 是 3.49.1，不满足。
- 程序启动时读回版本，不满足就拒绝运行（第 2.2 节）。

### 8.2 Windows 进程监督（第 ④ 步的先决条件）

现行 `run_supervised` 经 ctypes 做三件事：
1. 挂起状态创建子进程；
2. 加入 Job Object；
3. 超时结束整棵进程树。

Node 的 `child_process` 不能挂起创建进程，所以要用别的手段。候选按这个顺序验证：

1. **继承父进程所在的 Job**：
   - 一个很小的辅助程序先把自己放进带 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` 的 Job，再普通地 spawn 子进程。子进程从创建起就在 Job 里，用不着挂起创建。
   - 辅助程序退出或被结束，Job 关闭，整棵树一起结束。
   - 辅助程序用 stdin/stdout 的 JSON 跟内核通信，Bun 与 Node 都能用。
2. **`PROC_THREAD_ATTRIBUTE_JOB_LIST`**：`CreateProcessW` 的扩展属性在创建时直接指定 Job，同样不用挂起。
3. **Bun FFI**：`bun:ffi` 调 `kernel32`（`CreateProcessW` 带 `CREATE_SUSPENDED`、`CreateJobObjectW`、`AssignProcessToJobObject`、`ResumeThread`、`TerminateJobObject`），照搬现行做法。`bun:ffi` 官方还标着实验性，Node 后备用不了。

候选 1 的辅助程序用什么语言写（C、Bun 编译加 `bun:ffi`，或者别的）到 ④a 定，并写进本文：Node 自己调不了 Win32。

验证用例：
- 子进程从第一条指令起就在 Job 里。检验办法：子进程一启动就派生一个脱离父进程的孙进程然后退出，结束 Job 之后孙进程也必须不在了。候选 3（挂起创建）另外要验证“放行之前一条指令也不执行”，用一个一启动就写文件的程序检验；
- 孙进程也在 Job 里；
- 超时之后整棵树都结束，包括脱离父进程的孙进程；
- 宽限 15 秒的语义与现行一致。

三项都通过才替换。结果写进本文。

**④a 的方案（2026-10-22 与 themistally-15 定）**：选候选 3。

- **可行性试验**（Bun 1.4.2，`bun:ffi` 调 kernel32）：先建带 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` 的 Job，`CreateProcessW` 带 `CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP`，`AssignProcessToJobObject` 之后 `ResumeThread`。
  - 恢复之前等 1 秒，子进程“一启动就写的文件”不存在：放行之前一条指令也没执行；
  - 子进程派生一个 `DETACHED_PROCESS` 的孙进程后以 7 退出，退出码原样取到；子进程退出之后孙进程仍在；`TerminateJobObject` 之后孙进程消失：它也在 Job 里，整棵树一起结束。
- **为什么不是候选 1、2**：宽限期间要给子进程组发 `CTRL_BREAK`（现行 `_terminate_tree`），子进程必须在创建时就另起进程组。Node 的 `detached: true` 其实会带 `CREATE_NEW_PROCESS_GROUP`（libuv 的做法），但同时带 `DETACHED_PROCESS`，子进程没有控制台，`CTRL_BREAK` 一样发不进去；Bun 的 spawn 也给不出这个标志。候选 3 与 Python 的 `run_supervised` 一一对应。
- **实现**放在 `@themis/base/supervise`，照 `run_supervised` 的签名与返回（`exit_code`、`timed_out`、`interrupted`、`spawn_error`、`wall_seconds`、`stray_processes`、`kill_method`、`pid`），Python 先过契约，再对照、变异。逐条要求：
  1. **标准流**：`STARTF_USESTDHANDLES` 交给子进程，只让这三个句柄可继承（`PROC_THREAD_ATTRIBUTE_HANDLE_LIST`），不把别的句柄漏给子进程；stdin 固定接空设备。
  2. **命令行**照 `subprocess.list2cmdline` 的引号规则，与 Python 对照。
  3. **`.bat`、`.cmd` 照 Python 的分工**：supervise 本身不拒绝批处理文件，与 `run_supervised` 相同；调用方先过 `ensure_argv_safe`（argv[0] 以 `.cmd`、`.bat` 结尾时，参数里只要含 `BATCH_UNSAFE_CHARS` 里的字符就拒绝，防 BatBadBut 一类的命令注入，CVE-2024-24576；比较扩展名之前先去掉 argv[0] 末尾的空格与句点，第 71 轮），再调 supervise。`ensure_argv_safe` 逐字节移植进 `@themis/base`：同一个字符集、同样的报错文字，argv[0] 的小写比较用已移植的 Python lower。FFI 与 Python 的 subprocess 一致：`lpApplicationName` 传 NULL，命令行用 list2cmdline 拼好，`CreateProcessW` 碰到 `.cmd` 照样隐式起 cmd.exe，行为与 Python 相同（Node 系不经 shell 起不了 `.cmd`，这一点是 FFI 方案胜过 `Bun.spawn` 的地方）。契约加四个场景：一个 `.cmd` 假程序带安全参数能跑，退出码与输出与 Python 一致；参数含字符集里的每个字符时各自被拒、报错相同；参数带空格时引号正确；npm 这种经 `shutil.which` 解析得到 `.CMD` 的路径实跑一次。
     - **撤回的原写法**（themistally-15 2026-10-23 撤回）：原来写的是“supervise 与 `run_supervised` 一律拒绝 `.bat`、`.cmd`”。不成立：`.agent/plans/` 里有 16 条检查命令以 npm 开头（`npm ci`、`npm run build`、`npm test`），`_resolve_argv` 用 `shutil.which` 解析，Windows 上得到的就是 `npm.CMD`，照原写法改，桌面端各片的门禁检查会全部被拒；而“调用方先把垫片解析成 node 加脚本”只对 pi 成立。PD 本来就有 `ensure_argv_safe` 这道缓解。
  4. **环境块**照 CPython 的 `getenvironment`（`CREATE_UNICODE_ENVIRONMENT`）：排序、大小写不同的同名变量、键里含 `=` 或 NUL 时的处理，与 Python 逐条对照。
  5. **超时与宽限**：先 `GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, pid)` 给子进程组发信号，等 grace 秒（缺省 15），再 `TerminateJobObject`；之后查 `ActiveProcesses` 算出 `stray_processes`。语义与 Python 一致，宽限的情形配契约。
  6. **控制台**：`GenerateConsoleCtrlEvent` 只能发给与调用方共用同一个控制台的进程组。桌面外壳起服务时多半不给可见控制台。第 70 轮（Python 先改，与 themistally-15 定）：结果新增 `ctrl_break`（"sent" / "failed"，没发过为 None：returncode 已知时 CPython 的 `send_signal` 什么都不发）与 `ctrl_break_winerror`（失败的数字错误码，不记文字：文字随系统语言变）；"failed" 就不等宽限，直接结束 Job。`kill_method` 不改：它记的是结束整棵树的手段，Windows 上始终是 Job，本来就没撒谎。实测：调用方以 DETACHED_PROCESS 起（没有控制台）时发送失败、错误码 6；以 CREATE_NO_WINDOW 起（有控制台、不显示窗口）时子进程真的收到。"sent" 只说明事件交出去了，证明不了对方收到（GUI 程序、自己脱离控制台的进程都收不到）。桌面端设计 D3 的验证另加一条“照外壳的方式起服务”，核对子进程不弹控制台窗口、`CTRL_BREAK` 是否真的送到。
  7. **调用方意外死掉**：Job 句柄随进程关闭，`KILL_ON_JOB_CLOSE` 带走整棵树。测试真的杀掉调用方进程。
  8. **加入 Job 失败**：终止子进程、拒绝运行，与 Python 一样，不留没有监督的空窗。
  9. **Node 后备**：Node 调不了 Win32，照 native 文件锁的做法起一个 Bun 辅助进程，经 stdin/stdout 的 JSON 通信；辅助进程读到 stdin 的 EOF（调用方死了）就结束 Job 并退出。“杀掉调用方”那条测试在 Node 路径上也跑一遍。
  10. **POSIX**：进程组加 `PR_SET_PDEATHSIG`，未实机验证。
- **验证用例**：上面原有的四条，加上第 1、3、4、6、7、8、9 条，以及“孙进程脱离父进程”的情形。结果写回本节。
- **结果（2026-10-23，④a 完成）**：`@themis/base/supervise`（`runSupervised`）与 native.ts 的进程监督一节，`@themis/dispatcher/argv`（`ensureArgvSafe`）。契约 `contracts/test/supervise.contract.test.ts` 让 Python、TS 在 Bun 下、TS 在 Node 下（经辅助进程）跑同一组场景，结果逐字段比较（pid 与 wall_seconds 按范围），24 条全过：
  - 原有四条：S11 挂起创建之后在加入 Job 之前停 1 秒，子进程一启动就写的文件不存在（放行之前一条指令也不执行，Bun）；S5a、S6 孙进程脱离父进程（DETACHED_PROCESS）也在 Job 里，超时与子进程退出之后都被结束；S5a、S5b、S5c 超时之后整棵树结束，宽限的语义与 Python 一致（发出去了最多等 grace，子进程收到就提前结束、不理会就等满）。
  - 第 1 条：标准流只交三个句柄（S1 退出码与 stdout、stderr 逐字节）；第 2 条：S2 参数的引号（空串、制表符、引号前与末尾的反斜杠、中文、UNC）；第 3 条：S7 `.cmd` 假程序与 npm 经 which 解析出的 `npm.CMD` 照样能跑，S9 `ensure_argv_safe` 在 255 条语料（大小写、末尾的点与空格、全角、开尔文符号、İ 等，乘上每个特殊字符）上的判定与报错与 Python 逐条一致；第 4 条：S3 环境块（排序、大小写不同的同名变量留最后插入的、`=C:`、空值、Unicode）与 S3b 的六种报错。实测 CPython 3.12.10 是先按 dict 去重、再按排序后的次序逐个校验（被去掉的同名变量里含 NUL 不报错），空键交给 CreateProcessW、报错误码 87；
  - 第 6 条：调用方以 DETACHED_PROCESS 起时发送失败、错误码 6、不等宽限（S5a），以 CREATE_NO_WINDOW 起时子进程真的收到（S5b，标记文件）；S10 调用方的进程组收到 CTRL_BREAK，三套实现都照中断处理；
  - 第 7 条：S8 杀掉调用方，子进程与孙进程都结束（Python、Bun、Node 三条路径）；第 8 条：加入 Job 失败、恢复失败、建不了 Job 由 `base/test/supervise.test.ts` 用一套假的 Win32 调用覆盖（8 条），报错文字与 Python 相同；第 9 条：Node 后备的辅助进程以 DETACHED_PROCESS 起，再 `AttachConsole` 到调用方的控制台（调用方没有控制台就挂不上）。不这样的话，调用方没有控制台时 Windows 给辅助进程另配一个，CTRL_BREAK 就发得出去了，与进程内调用不一致（契约第一轮就是在这里红的）。
  - 启动失败的报错照 CPython 的 OSError：错误码先映射成 errno（PC/errmap.h）再定类名，文字是 FormatMessageW 去掉末尾的空白与句点（S4：找不到程序 2、工作目录不存在 267、不是可执行文件 193、空键 87）。`GetLastError` 在 bun:ffi 下取得到。
  - 坑：Windows 上 Python 的 `time.sleep` 只被 SIGINT 提前唤醒，测试用的子进程要分小段睡，SIGBREAK 的处理器才能及时运行。
  - POSIX（新会话、进程组、SIGTERM 加宽限再 SIGKILL）写了，未实机验证；本机只有 Windows，契约在 POSIX 上跳过。
- **复核之后的修补（2026-10-23，themistally-15 复核 ④a；内核第 71、72 轮）**：
  - **`ensure_argv_safe` 可以绕过**（第 71 轮）：Windows 会去掉文件名末尾的点与空格。`t.bat.`、`t.bat `、`t.bat. .` 躲过扩展名判断，照样经 cmd.exe 执行，参数里注入的命令真的执行了（Rust 的 CVE-2024-43402，CVE-2024-24576 修得不完整的那一处）。上面 S9 的“逐条一致”其实是两边一起漏。Python 与 TS 同一轮改：比较扩展名之前先去掉末尾的空格与句点（`rstrip(" .")`）。
    - S9 的语料加了几种末尾写法，并钉住判定：五种写法被拒；六种不算批处理（末尾是制表符、`::$DATA`、`t.exe.`、`t.bat.exe`、`.`、一个空格）。
    - 新增 S9b：三套实现先不经检查直接起 `t.bat.`，证明注入真的生效；再证明 `ensure_argv_safe` 把同一个 argv 拦下，报错相同。
  - **Node 后备在辅助进程起不来时整个崩掉**：两处 spawn（进程监督、文件锁）都没接 `error` 事件，找不到 Bun 时调用方进程直接崩。现在都接住了，报“起不了……的辅助进程（命令）：原因”。
    - Bun 也不再按名字起：npm 全局装的 Bun 在 PATH 上只有 `bun.cmd` 垫片，Node 不经 shell 起不了。
    - 改用与启动器同一个来源（`bunExecutable`）：先看 `THEMIS_BUN`，再看装好戳记里的 `bun_path`，最后照 `find_bun` 的规则在 PATH 上找（`findBunOnPath`：任何一处的 `bun.exe` 优先，其次第一个 npm 垫片旁边那个，相对路径与空项跳过）。
    - 契约的驱动也改用它（harness 的 ts-bun、runTsCli、workspace 测试）。复核时照缺省的 PATH，24 条里有 23 条报 `spawn bun ENOENT`，这个问题一并解决。
  - **FFI 缓冲区的生存期**：指针参数改为直接传 TypedArray，调用期间由 Bun 保活，不先换成 `ptr()` 的数字。地址被嵌进结构体的两块（属性表、句柄数组）留到 `DeleteProcThreadAttributeList` 之后。这一条变异测不出来（取决于 GC 时机），靠代码复核。
  - **给本机服务的两个选项**：
    - `signal`（AbortSignal，照中断处理）；
    - `handleSignals`（缺省 true，运行期间在 process 上装中断监听器，与 `run_supervised` 一样）。本机服务设为 false：Ctrl+C 停的是服务本身，由服务经 `signal` 取消每一次运行。
    - 进程内、辅助进程、POSIX 三条路径都接上了，POSIX 未实机验证。
  - **第 ④ 步要处理的**：Python 的调用方会把 stderr 并进 stdout。检查命令传 `subprocess.STDOUT`（`_run_command_item`）；hub 的内核 pytest 两边传同一个文件对象（`kit_hub.py` 的 `run_supervised(…, log, log, …)`）。TS 的 `SuperviseOptions` 现在只收两个路径，会开出两个句柄。移植这些调用方之前，要加一个“stderr 跟 stdout 用同一个句柄”的写法，配契约。
  - **测试**：
    - base 新增 `helper.test.ts`，4 条：Bun 的查找；辅助进程起不来时两处都报错、不崩；经辅助进程取消。取消这条在单独的 Node 进程里跑，由包装器以 CREATE_NO_WINDOW 起、有自己的控制台，原因见第 72 轮。
    - `supervise.test.ts` 加了 signal 与 handleSignals 两条；契约 25 条；TS 全量 383 条全过。
    - 变异 32 条全部抓住：原 19 条，新加 13 条，分别是不去末尾的点与空格、只去空格、两处不接 error、进程内与辅助进程一路的 signal 与 handleSignals、不看戳记、THEMIS_BUN 不优先、相对路径不跳过、垫片优先于 bun.exe。
  - **开始之前就取消（themistally-15 复核的补充）**：三条路径原来都是先起子进程、再按中断处理（发 CTRL_BREAK、最多等 grace、结束 Job）。本机服务里排队中的写请求，客户端断开之后照样会被起起来、再被中途打断，平白走一遍恢复路径。
    - 现在打开输出文件之后、起子进程之前先看是否已取消：已取消就不起子进程，结果是 interrupted、pid 与 exit_code 为 null、kill_method 照旧（Windows 是 "job-object"）。
    - 这与 Python 一致：`_Interrupted` 发生在 Popen 之前时 proc 是 None。输出文件照样建好，因为 Python 的输出文件由调用方先打开。
    - 辅助进程一路：“已取消”随 supervise 请求一起交代（`interrupted` 字段），不另发一行 interrupt，免得与起子进程赛跑。
    - 另一处：辅助进程起不来时，stdout 可能先于 error 事件关闭，报错就会退成笼统的“没有交回结果”。现在读完 stdout 先等进程的 close 事件（它在 error 之后），最多 5 秒，再判断原因。
    - 测试：`supervise.test.ts` 用假的 Win32 调用断言只建了 Job、没有 spawn、句柄都关掉、结果逐字段；`helper.test.ts` 经辅助进程实跑一条写标记文件的命令，断言标记文件不存在、输出文件建好了。
    - 变异 3 条全部抓住：进程内照样起子进程、辅助进程一路不交代、辅助进程不认这个字段。TS 全量 385 条全过。
  - **已验证的事实：CTRL_BREAK 的目标不是进程组时**（themistally-15 实验，在 CREATE_NO_WINDOW 起的独立控制台里，装了调用方、旁观者、目标三个接收者）：
    - 组长还活着：只有目标收到（约 30 毫秒），调用方与旁观者都没收到；
    - 组长已经退出、句柄还拿着（supervise 超时那一刻子进程恰好退出的情形）：谁都没收到，不会广播，这个竞态没有危险；
    - 目标不是组长（V17 的情形）：整个控制台都收到，调用方以 0xC000013A 退出。
  - **残留进程的判断等 Job 的计数归零**（内核第 74 轮，两边同改）：
    - 主进程刚退出时，Job 的 ActiveProcesses 偶尔还没减下来（实测约两百次一次，50 毫秒内归零），被误判成残留，契约 S3b 因此偶发红。
    - 现在计数大于 0 时最多等 2 秒（`JOB_SETTLE_SECONDS`），仍大于 0 才算残留。
    - 后备办法（themistally-15）：放宽之后还偶发，就改用 `JobObjectBasicProcessIdList` 列出 Job 里的进程号，只剩主进程自己的 pid 就不算残留；两边各多一套 FFI。
  - **第 72 轮的起因**：第一次跑这 32 条时，V17（不另起进程组）让子进程的 pid 不再是进程组号，取消测试发出的 CTRL_BREAK 广播到了整个控制台，跑 mutate 的外层 shell 被结束。mutate 自己接住了信号，却把这条算作抓住，还接着往下跑。内核改成：被中断的运行记出错，后面的变异不再运行。测试一侧把取消场景挪进了自己的控制台。重跑时 V17 被四条用例的断言抓住，不再波及外层。

### 8.3 依赖、锁文件、测试框架

见第 2.3、2.4 节。

### 8.4 内核文件指纹

见第 5 节。第 ② 步第一次切换时实现。

### 8.5 设计文档

《设计文档_修订完整版.md》第 3.3 节“项目现行内核是 Python 标准库程序”的表述与第 3.4 节，由 themistally-15 会话改：这份文档在主工作区是未入库文件（v2.1），不经 kdev 合入。本计划这边不动它。

---

## 9. 流程

每一步、每个模块都照内核轮次的流程：

1. 在 kdev worktree 开发。
2. Python 与 TS 全量测试：
   - Python：受影响模块的 pytest，加 `test_kit_hub.py`；
   - TS：`ts/` 下 `vitest run` 与 `tsc`；
   - 改到共享文件（`.gitignore`、根目录的配置、`tests/` 下的公共夹具）时，再跑全部门禁基准（`tests/test_gate_*_baseline.py`）。第 0 步给 `.gitignore` 追加了 `ts/` 的两行，T002 的门禁断言“追加的恰为三行”从那时起在分支末端上就是红的；没有主任务落地，合入后回归没跑，直到 T011 的落地预演才发现（2026-10-22，站主已收窄该断言）。
3. 变异检验：TS 侧全部抓住；Python 侧外部观察不到的写明 `equivalent`。
4. 写迭代记录：本文第 11 节加一行；涉及内核行为的，在 `docs/themis-tally-3.0-r3-七端与信箱.md` §10 另记一轮。
5. 提交，提交说明写新增依赖的理由。
6. `python scripts/kit_hub.py exclusive -- git merge --ff-only <sha>`。

另外：
- **计时（固定项，2026-10-29 起，themistally-15 提出）**：每次切换、每次动 TS 入口（`main.ts`、启动器）或公共模块（`@themis/base`、pyregex 等）的合入，在主仓库上跑 `python ts/tools/dispatch-timing.py`：同一批只读命令（validate、metrics、wait、sync-adapters --check、release-check、status --json、config show --json），钉成全部 Python 对比经启动器的全部 TS，各 10 次取中位数，记进第 11 节那一行。
  - 比上一次记下的涨了 0.2 秒以上，或超出目标，当问题处理，查清楚再合入。不加带时限的测试：负载下容易误报。
  - 目标（“TS 启动开销”那一片，r3 §10 第 129 轮）：单条命令的中位数比 Python 慢不超过 0.5 秒；release-check 逐个文件跑正则，受 sre 移植解释执行的速度所限（第 10 节），目标是不超过 Python 的 1.5 倍。达不到的，带着拆解交 themistally-15 与站主定。
  - 起因：第 122 轮量过 config show（0.13 → 0.28 秒），之后 `main.ts` 越来越大，没有再量；切换 d 之前量出来已是 0.17 → 0.75 秒。
- 每完成一步向站主汇报。子步也算：合入后把提交号与证据发给 themistally-15 独立复核，证据包括契约条数、对照方式与规模、变异数，以及漏网变异怎么处理的。
- 犯错照例记进 `AGENT_LEARNINGS.md`。
- **专心推迁移**（站主 2026-10-26 决定，themistally-15 转达）：
  - T022 的 A、B 两片做完后暂停开新切片，迁移按第 4 节的次序推进；
  - 第 ④、⑤、⑥ 步要真实切片验收时，才登记下一片桌面端任务，登记前先告诉 themistally-15；
  - B 落地之后，`kit_hub.py`、`pi_dispatch.py`、`kit_config.py`、`kit_roles.py` 只修挡住工作的缺陷（这一条是 themistally-15 转达时附的协调意见，不是站主原话；目的是别让要移植的 Python 继续变多。迁移计划本身的步骤，例如第 ③ 步的切换，不在其内）。对照中查出两边共有的错也算缺陷，照第 71、74 轮的做法两边在同一轮改；
  - 不挡路的改进记进第 10.1 节，等对应模块切到 TS 之后在 TS 上做；
  - 某个模块已经有了 TS 对应（例如第 ③ 步做到一半的配置中心），它的缺陷修补就两边同一轮改，不留单边。

---

## 10. 风险与待决

| 风险 | 影响 | 应对 |
|---|---|---|
| 本机只有 Windows，POSIX 语义没有实机验证（`os.link` 的分支、`O_NOFOLLOW`、信号） | TS 版在 Linux/macOS 上的行为没有证据 | 契约测试本身跨平台；需要时在 WSL 或另一台机器上跑一遍再说“跨平台” |
| 第 ② 步切换起执行器的禁区是整个 `ts/**`（themistally-15，2026-10-22） | 以后 quizs 的包（也在 `ts/packages/` 下）与它要补进 `@themis/base` 的子模块，执行器都碰不了 | **已解决（第 69 轮）**：桌面端本机服务改用 TS（`ts/packages/ui`）要经 hub 派给执行器，禁区收窄到内核包与工作区文件（第 5 节）。quizs 的包以后照样交给合同的 Scope 管；它要补进 `@themis/base` 的子模块仍在禁区里，由规划端做 |
| Python `json.dumps` 与 JS 的差别（第 1.4 节） | 摘要对不上，证据绑定与信件 sha256 失效 | `pyjson` 逐字节对照，专门的浮点、大整数、码点排序用例 |
| 时间与编号的格式（`utc_now`、msg-id、turn id） | 两套实现写出的记录不能互认 | 第 ① 步之后补进 `base`，按契约对照 |
| Bun 在 Windows 上的成熟度；`bun:ffi` 是实验性 | 第 ④ 步卡住 | 先做 ④a 的验证；Node 后备一直保留 |
| npm 装的 Bun：`bun.exe` 不在 npm 的 bin 目录 | 子进程不经 shell 启动 `bun` 会失败（样板实测） | 已把 `bun.exe` 的目录加进用户 PATH，记进 `.agent/environment.md` |
| 两套实现同时写一个信箱或证据目录 | 并发语义不一致会丢信或覆盖证据 | 发布、锁、账本都有混跑的并发用例（样板已有） |
| Node 后备的原生操作（文件锁，以后还有 Job Object）仍要靠 Bun 跑辅助进程 | 没装 Bun 时 Node 后备拿不到文件锁 | 第 ⑥ 步之前，真正的退路是 Python 实现；第 ⑥ 步之后辅助进程是同一个单文件程序的 __native 子命令 |
| 执行器在 TS 代码进入生产路径后改动它 | 绕过内核 | 第 5 节：第 ② 步起把 `ts/packages/**` 加进执行器禁区 |
| quizs 的设计文档还没出 | 共用包的名字与协议边界可能要改 | 第 ⑤ 步之前不碰内核与 worker 的协议；包名改动只是重命名。站主 2026-10-22 决定 quizs 推迟到 TT 整体实现（TS 迁移做完）之后，为它预留的部分（`@themis/base` 的 jcs、sqlite、objects，第 8 章 worker 协议的内核轮次）照迁移本身的需要排 |
| 只读命令遇到坏证据就打堆栈退出（现行 Python）：`status` 读到的 meta.json、run.json、checks.json 等不是对象（`.get` 抛 AttributeError），checks 的 results 不可迭代或项不是对象，verdicts 下有不是数字的 `*.json`（`int()` 抛 ValueError），run-started.json 的 started_at 是真值却不是字符串（TypeError），证据 JSON 嵌套太深（`read_json_or` 不接 RecursionError） | 退出码 1、堆栈进 stderr；TS 照样退出码 1，契约只比较退出码 | 以后开一轮改成干净的 ERROR 行，TS 跟着改（themistally-15，2026-10-22） |
| `logs show` 的显式相对路径：Python 拿“当前目录拼出来、没解析过”的路径逐段对照“解析过的 runs 根” | 当前目录带 8.3 短名（例如 `ADMINI~1`）时，指向 runs 之内的相对路径也报“不在 runs 根之下”（第 ②a 步的契约实测） | TS 照样；要修另开一轮（两边一起改成先解析再比较） |
| 路径语义的细差（TS 的 `pypath.ts`） | Windows 上 Python 3.12 的 normcase 用 LCMapStringEx 的不变区域小写：Bun 下照调（⑤c 起，guard_config 要把它的结果原样写出去）；Node 后备没有原生调用，用 toLowerCase，İ、ẞ、ǅ、开尔文符号（U+212A）、埃符号（U+212B）与词尾的 Σ 这六个字与 Python 不同。abspath 的 GetFullPathNameW 会去掉段尾的点与空格，Bun 下照调，Node 后备的 `path.resolve` 不去 | Bun 下逐字相同；Node 后备的差异由 events 契约钉住（Node 与 Python 不同的恰好是这六个字，多一个少一个都会红） |
| Node 后备认不出一部分重解析点 | Python 把 Windows 上一切带 REPARSE_POINT 属性的条目都当链接；Bun 经 GetFileAttributesW 一致，Node 后备只用 lstat，认不出云文件占位、AppExecLink 这类 | 第 ⑥ 步之前 Python 一直是退路；需要时让 Node 后备经 `__native` 辅助进程批量查属性 |
| `logs search` 拒绝反向引用与条件分组、括号嵌套超过 100 层（行为变更，r3 §10 第 58 轮，Python 先改） | 以前能搜的这两类写法现在报错（退出码 2） | 搜索框只做逐行过滤，两类构造在这里没有实际用途；桌面端文档的搜索说明已记。原因说准（themistally-15，2026-10-22）：第 58 轮当时以为 JS 正则做不到；②b2 改成移植 sre 匹配器之后，引擎其实已经能支持这两类，只是不值得（多两类操作码与它们的对照）。保留拒绝；需要时可以撤销第 58 轮，补上 GROUPREF、GROUPREF_EXISTS 两类操作码与对照 |
| `logs search` 的 PATTERN 是用户可控的正则 | 灾难性回溯：TS 的 sre 移植与现在的 Python 一样中断不了，而且更慢（解释执行：常见写法慢约 3 倍以内，`.*` 在 200 KB 长行上反复回溯约 3 倍；构造出的指数级写法约 20 倍，这一项是在后两轮优化之前测的） | 启动器的 Job 加超时、超时结束整棵进程树；将来的本机服务调 logs search 一定要设超时（themistally-15，2026-10-22） |
| `logs search` 的匹配语义要与 sre 一致 | JS 正则（尤其 JavaScriptCore）与 sre 的回溯次序、空匹配处理、原子组都不同；sre 自己还有怪癖：信息块的字符集前缀按整个模式的标志编译，`(?a:[^\w])` 开头的模式不把 µ 当起点 | 不用 JS 正则，移植 sre 的字节码与匹配器，怪癖照搬；对照测试在 Bun、Node 两种运行时各跑一遍 |
| 游标绑定的文件号 | CPython 3.12 在 Windows 上的 st_ino 取自文件 ID，ReFS 上可能是 128 位；Node 的 ino 是 libuv 给的 64 位 | 本机 NTFS 实测三套取值相同（②b1）；ReFS 上未验证，遇到再处理 |
| `status --json --assess` 在 JSON 之后接 assess 的文本行，stdout 不是合法 JSON（现行行为，第 ② 步照样保留） | 桌面端本机服务拿它当 JSON 解析会失败 | 赶在本机服务建成之前另开一轮修掉：assess 的文本挪到 stderr，或放进 JSON 的一个字段。在那之前，服务不拿 `--assess` 的输出当 JSON 解析（themistally-15，2026-10-22） |
| 经启动器转交的写命令被 Ctrl+C 打断（第 ③ 步切换之后） | **触发条件**：在交互终端里对转交给 TS 的写命令按 Ctrl+C，并且正好落在持锁的那一瞬。<br>• 写入都经 `config_transaction(s)`，共 19 处调用：17 个命令入口（kit_config 5 个：set、unset、init、decisions、rollback；kit_roles 10 个；kit_plugins 2 个），另有 `write_config`、`write_checked` 两个公开函数，只有测试在用；<br>• `runtime scan` 的探测在拿锁之前；<br>• 持锁期间只做读、改、快照、审计、替换，约百毫秒。<br>TS 子进程另起了进程组，收不到 Ctrl+C；切换 b 起启动器把它转成 CTRL_BREAK 发给 TS，配置中心的命令没装处理，按缺省结束。<br>**留下什么**：锁目录 `.agent/.config.lock/` 与其中的 `owner.json`；如果断在写临时文件与替换之间，还有其中的 `<文件名>.<16 位十六进制>.tmp`。Python 收到 KeyboardInterrupt 时 `ConfigLock.__exit__` 会删掉整个目录，连同临时文件。<br>审计的状态两边相同：断在 intent 之后、commit 之前，下一次写都补判 `resolve`。<br>**下一次写看到什么**：等满 30 秒，退出 1，报“配置锁被占用：<路径>，进程 <pid>（主机 <host>，已退出，<时间> 起持有）。确认没有别的写配置的命令在运行之后，删除这个目录再重试（锁从不自动清除）”。<br>**用户当场看到的两边一致**（v1.3 核对过代码）：<br>• Python：`kit_config.main` 接住 KeyboardInterrupt，stderr 写“已取消。”，退出 130；<br>• 经启动器（切换 b 起）：TS 按缺省结束，`run_handoff` 照 Python 抛 KeyboardInterrupt，`pi_dispatch.main` 写同样的“已取消。”，退出 130。切换 b 之前其实不是这样：不带超时的 `proc.wait()` 要等 TS 退出，处理函数排不上，TS 照常做完、不会留锁，启动器事后才写“已取消。”（2026-10-28 实测；这里原先是读代码写的，写错了）；<br>• 打断之前已经写出的 stdout 两边也相同：`@themis/config` 只经 `@themis/base/pyfmt` 的 `PyOut` 写 stdout 与 stderr，它用 `writeSync`，照程序次序同步写完才返回；Python 的块缓冲在退出时刷出。 | 接受（v1.3，themistally-15 同意）：<br>• 被硬杀（`run_pd` 超时、桌面端发 CTRL_BREAK 之后宽限期满）时，两套实现本来都会留锁；<br>• 报错写明了删哪个目录，能恢复；<br>• 要改，就让启动器先给 TS 的进程组发 CTRL_BREAK、宽限之后再终止 Job，TS 装上处理函数删锁，代价是启动器多一段信号转发与宽限逻辑，外加各一条测试。切换 b 做了转发（D2），配置中心的命令仍不装处理，留锁照旧接受 |
| 调度器命令在 `runSupervised` 之外被 Ctrl+C 或 CTRL_BREAK 打断（切换 b 之后） | TS 那一段没装处理，按缺省结束，不跑 finally；Python 抛 KeyboardInterrupt 会跑。漏掉的有：任务锁（临界区毫秒级，`TaskLock` 的 stale_seconds 300 秒后作废）、临时文件，以及正在建的或用完要删的 git worktree（连同登记）：prepare 正在建 attempt 的 worktree；check --fresh、baseline、mutate 的干净副本；integrate 的验证副本在 `runSupervised` 之前或之后的 git 步骤上被打断。后果是 %TEMP% 下留下目录、`git worktree list` 多出条目；不影响证据与状态，下次各用新的 mkdtemp 名字。窗口很小：这些命令绝大部分时间在 `runSupervised` 里，那里的中断 TS 照 Python 收尾 | 接受（themistally-15 同意，2026-10-28）：留下的锁 300 秒后作废；留下的临时目录与 worktree 登记用 `git worktree prune` 或手动清理；状态与证据两边相同 |
| 切换 d 之后，在没装 TS 依赖的树里直接跑这棵树自己的启动器（themistally-15 复核切换 c 时提出） | 调度器命令报“TS 实现没装好”。切换 c 实测（钩子记下每次转交）：全量 pytest 与门禁基准一条调度器命令都不经 TS，没装依赖的 worktree 里照样全绿（test_dispatch 的 make_repo 只拷脚本、不带选择文件；进程内调 `pd.main` 的由 conftest 钉成 python）；hub 的 `run_pd` 用主工作区自己的启动器，依赖由 `ts_install_if_stale` 跟上；kit_install 在第 ⑤ 步之前不装选择文件，目标仓库全是 python。会碰到的只剩：本仓库任务的合同检查直接调用启动器（例如 `bash scripts/dispatch-pi.sh validate …`）时，在 attempt worktree 里报错；复核方的实机克隆自己装依赖 | 切换 d 的注意事项：这类合同在 setup 里装依赖（`bun install --frozen-lockfile`），或者检查里不调用启动器。不做“没装就退回 Python”：同一份选择文件在不同环境走不同的实现，也与不回退的决定相冲突 |
| Node 后备下的 native-helper 拿到还原过的注入变量（切换 b 之后，themistally-15 复核时指出） | Node 后备拿文件锁（`native.ts`）、起监督进程（`supervise.ts`）都起 `bun native-helper.ts`，继承的是已经还原的 `process.env`，`BUN_OPTIONS` 会作用到这个辅助进程上。启动器只用 Bun，生产走不到 | 接受。哪天启动器真用上 Node 后备，起 native-helper 时先去掉 `TS_RUNTIME_ENV_DROP` 那几个 |
| K5 的触发方式：预检之后、冻结之前在窗口里改合同（r2 文档 9.4 节；切换 c3b） | Python 的用例靠替身让进程停在冻结前一刻，TS 没有这样的口子，这种触发方式在 TS 复现不了 | 接受（themistally-15 的口径）：冻结之后的路径由 prepare 契约“按角色：记录的合同哈希不对”那条覆盖（预检不核对记录里的合同哈希，照样走到冻结与发布，退出 4、PREPARE_FAILED）；写死模型的合同在窗口里被改时，两边都记 PREPARE_FAILED、退出 3（读代码核对，Python 第 5268 行与 TS prepare.ts 第 218 行） |
| `secret set` 留在 Python（第 ③ 步） | 第 ⑥ 步撤 Python 之前，凭据的写入还是 Python | 第 ⑥ 步再移，要解决的三件事写在第 ⑥ 步的内容里 |
| `run_capture` 超时后孙进程还握着管道（第 ③d 片） | Python 只结束直接子进程（`pi.CMD` 是 cmd.exe），再不设时限地 `communicate()`，孙进程（node）不退，命令就一直挂着；TS 经 Job 结束整棵树，按时返回 124 | 接受（v1.3，themistally-15 同意）：<br>• 正常超时（退出码 124、空 stdout、`timeout after Ns`）两边一致，契约有用例；<br>• 挂住的情形不照搬；<br>• Python 一侧按第 9 节的冻结规矩不修 |
| `run_pd` 超时后握着管道的进程还没退（第 ⑤e2a 片） | Python 的 subprocess.run 超时只结束直接子进程，再不设时限地 `communicate()`：启动器起的 bun、调度器起的 pi 与检查还握着管道，就一直等到调度器干完才交回 124；TS 经 runSupervised 用 Job 结束整棵树，按时交回 124 | 接受（照 ③d 的 run_capture，themistally-15 复核 ⑤e2 设计稿时同意）：<br>• 正常超时（124、`超时（N 秒）：…`、不记账本）两边一致，契约有用例；<br>• 挂住的情形不照搬；<br>• stdin：Python 继承父进程的，runSupervised 接空设备。调度器的命令都不读 stdin（pi_dispatch 起的子进程都接 DEVNULL，转交 TS 时只有 native-helper 读 stdin），两边看不出差别；<br>• 时限不大于 0 时 Python 立即超时，runSupervised 当作不限：内核传的时限都是正数（合同校验把单次时限限在 60..86400）；<br>• 超时时 runSupervised 先给进程组发 CTRL_BREAK，grace 为 0，紧接着结束 Job（同 ③d 的 run_capture）：调度器来不及收尾，证据停在中途，等于调度器崩溃；run 被结束时 attempt 停在进行中（ATTEMPT_IN_FLIGHT），之后照 interrupted_attempt 的提示用 collect --recover 收拾。Python 等调度器自己干完才交回 124。grace 照 0，不改；<br>• 正常退出时 Job 里还剩进程：TS 等 2 秒（JOB_SETTLE_MS）后结束它们，Python 等所有握着管道的进程退出；<br>• accept_gate_pre 的 pytest --collect-only（⑤e2b）同样经 runSupervised，超时照 subprocess.run 报 TimeoutExpired，文字照 str(TimeoutExpired)（命令按 Python 的列表 repr 写；内核 git() 的超时文字同样照改） |
| 只把 strerror 放进输出的 lstat、listdir 一类（第 ③ 步：运行中切换的扫描、本机文件“看不了”） | Python 的文字是 Win32 错误码经 FormatMessageW；TS 从 libuv 的错误码只认得出拒绝访问（EACCES、EPERM 当 5 号错误，文字照样取 FormatMessageW，跟着界面语言），其余错误码反推不回 | 接受（themistally-15 同意）：<br>• 拒绝访问以外的错误码，文字不保证一致；<br>• 会把整条报错放进输出的 os.replace、os.rename、Path.mkdir（“写入失败”“审计写不进去”“快照存不下”）走原生 Win32，逐字一致，契约有用例；<br>• 锁目录、marker 与凭据文件的 mkdir、unlink 失败时 Python 直接崩溃，不进受控的输出 |
| JSON 嵌套 1001 层到约 2994 层、里面又有文法错误（第 ③e 片，themistally-15 复核 ac10a2e 时实测） | TS 的 pyjson 在第 1001 层报 RecursionError，CPython 3.12 在 Windows 上要到约 2995–2998 层（看最底下是什么、钩子占几格）。这个窗口里 `strict_json_loads` 的错误码不同：Python 报 `E_JSON_SYNTAX`，TS 报 `E_JSON_LIMIT`；`plugins verify`、`plugins list --json` 里“解析失败：…”的码随之不同，退出码相同 | 接受（2026-10-26，themistally-15 建议）：不按调用路径模拟 CPython 的 C 递归预算。合法的深文档两边都是 `E_JSON_LIMIT`；正常的 manifest、锁不会嵌套上千层 |
| 配置嵌套约 993 层到约 2997 层（第 ①、③a2 步起就有，themistally-15 复核 ③e 时实测） | Python 的 `json.loads` 读得完，`secret_like_paths` 递归时撞上解释器的递归上限，打堆栈退出 1；TS 在 998 层以下报“配置无效…”，999 层以上报“ERROR: 无法解析 …：RecursionError”，都是退出 1。约 2998 层以上两边都报“无法解析…RecursionError”。契约里“嵌套很深”用的 3000 层在窗口外面 | 接受（同上）：退出码一致、文字不同；要逐字一致得同时模拟 C 递归预算与 `secret_like_paths` 当时的 Python 栈深，为至少 990 层深的配置加这些复杂度不值 |
| 切换之后，配置中心起的 CLI 拿不到 `NODE_OPTIONS`、`NODE_PATH`（第 ③ 步的切换，themistally-15 复核 ③d 时查出） | 启动器的 `handoff_env` 把 `TS_RUNTIME_ENV_DROP` 从 TS 进程的环境里去掉，TS 的 `childEnv` 又从 `process.env` 拼；Python 的 `child_env` 会把这两个变量带给 pi。runtime scan、probe、models、doctor 起的 pi 是 node 程序，用户要是靠 `NODE_OPTIONS` 给 pi 加内存上限，经 TS 探测时就没有 | 接受（2026-10-26）：本机的进程、用户、机器三层都没设这两个变量，选择文件也不随 kit 分发；探测只跑 --version、--help、--list-models 与 auth check。第 ④ 步照 D3 修：启动器把去掉的原值换名放进 TS 的环境，`childEnv` 还原成原名（④b7 与切换那一轮）。切换 b 已修：改在 TS 入口还原，探测起的 pi 也拿得到 |
| pricing 下的 `per_tokens` 被内核的疑似凭据检查当成凭据（④b2 写 metrics 契约时查出；Python 与 TS 的 secret_like_paths 逐字一致，两边一样错） | 用户照 kit_config 的说明给某个模型写了 per_tokens，Repo.config 就整份不读，所有调度器命令都报“有疑似凭据”、退出 2 | 已改（第 125 轮，r3 第 10 节）：只豁免 `pricing.<provider/model>.per_tokens`、值必须是数字，两边同一轮改，有契约与变异 |
| 事件流的一行、或执行报告最后一个 json 块嵌套 1001 层到约 2996 层（第 ④b6 片，2026-10-26 实测） | CPython 3.12.10 在 Windows 上的 `json.loads` 到 2997 层才放弃（数组与对象相同，与调用时的栈深无关），`summarize_events`、`extract_report` 照常往下走；TS 的 pyjson 在第 1001 层报 RecursionError，collect 崩溃。约 2997 层以上两边都崩 | 接受（2026-10-26，与 themistally-15 定，照第 ③e 片的口径）：把 TS 的上限改成 2997 只让 loads 本身一致，下游的 `write_json`（indent 走纯 Python 编码器，约 1000 层）、`repr`、`_json_spans` 各有各的上限，改一个常数缩不小窗口；执行器写不出上千层的事件或报告 |
| Windows 上的 `os.path.abspath` 与 `Path.exists`（④b6 复核时 themistally-15 查出：工具参数的路径是 nul、带长路径前缀） | Python 的 abspath 是 normpath 加 GetFullPathNameW：去掉段尾的点与空格，末段是 nul（可带结尾的点、空格、冒号）时映射成 NUL 设备；`Path.exists` 对 NUL 设备为真；`Path.resolve`（realpath）对带长路径前缀的输入保留前缀，规范化之后就是 nul 时是 NUL 设备。TS 原先用 path.resolve、existsSync 与 realpathSync.native，nul 被当成工作副本里的文件跳过，长路径前缀的主仓库路径被判成 main_repo | 已改（④b6 补）：Bun 下 abspath 经 native.ts 调 GetFullPathNameW（规则随系统版本变，照调不手写），pyExists 认映射成设备的路径，pyResolve 照 ntpath.realpath 写。Node 后备没有原生调用，照旧是原来的写法（Node 只跑测试，不进生产）；契约里这一组只比 Python 与 Bun。check 的 cwd 解析也在内（themistally-15 复核 d14ea7c：cwd 写成 "src." 时 Node 记 blocked，Python 与 Bun 照常跑）。让内核把长路径前缀的主仓库路径也认作主仓库是改行为，要站主定（10.1）。**再补**（themistally-15 复核 d544c14 查出）：pyExists 改照 os.stat 打开（CreateFileW 加 FILE_READ_ATTRIBUTES、BACKUP_SEMANTICS；拒绝访问、共享冲突退到 FindFirstFileW；参数错误加读权限再开），段尾的点与空格、页面文件、设备与上一级不在的情况都与 Python 一致，“不存在”之外的错误照 Python 抛出；pyResolve 照 ntpath.realpath 与 Path.resolve 写全（nt._getfinalpathname 经 GetFinalPathNameByHandleW、非严格时一段段往上退、不允许的错误码照样抛出、去长路径前缀前先核对），路径里有 NUL 字符时与 Python 一样崩在 ValueError。没有移植的两处：_readlink_deep（打不开的链接自己跟随）；Path.resolve 非严格时最后的 p.stat() 遇到符号链接环（1921 或 ELOOP）抛 RuntimeError("Symlink loop from ...")。只影响打不开、成环的链接 |
| Node 上的 lstat：`/nul`、`/pagefile.sys`（themistally-15 复核 ④b6 查出） | `_root_entry_exists` 的 lexists 在 Python 与 Bun 下为真，Node 的 lstatSync 失败（设备、共享冲突），Node 上 scan 的工作副本外路径少一条 | 接受：生产走 Bun；契约不放这类输入，放的话只比 Python 与 Bun |
| JSON 嵌套 2997 层以上时 RecursionError 的文字（themistally-15 复核 ④b6 查出） | 两边都崩，Python 说 “…decoding a JSON array/object from a unicode string”，TS 的 pyjson 原先固定说 “…decoding a JSON object” | 已解决（⑤f）：pyjson 照 CPython 的 C scanner 在进对象、进数组时各自检查，文字分开写；层数照旧固定在 1000（与 Python 的窗口见上面几行，仍然不比）。gate_spec 嵌套 10 万层的数组、对象都逐字对上；对象、数组混着嵌套时两边在不同的层放弃，报的类型可能不同，同样不比 |
| 检查的输出模式带反向引用或条件分组（第 ④b3 片对照时查出） | Python 的 check 照常匹配；TS 的 sre 移植只记整段匹配，编译不了，check 崩溃 | 第 129 轮起 validate 两边都拒绝这两种写法（prepare 前必过 validate），只剩第 129 轮之前冻结的合同：当时真实合同 977 条输出模式一条都没用到。接受 |
| 冻结合同的检查项、检查记录里的字段被手改成别的 JSON 类型（④b3 复核时 themistally-15 查出 meta 与 candidate 的几处，补的时候逐处对照了三条命令） | 合同 checks、setup 的 id、argv、env、timeout_seconds、输出模式，checks.json 的 results 与几个文件列表：Python 在各自的位置以 KeyError、TypeError（不可哈希、不能迭代）崩溃，或按字符、按键迭代照常往下走；TS 在别处崩、照常往下走或照常记录。例如检查项缺 id 时 Python 在跑任何检查之前就崩，TS 跑完全部检查才崩 | 照搬的是 meta、candidate 的字符串字段（worktree、base_sha、task_id、attempt_no、tree）与检查项的 cwd：都是“转成路径、当 git 参数、%d”的边界，各改一处（④b3 补，各配契约场景；崩溃场景另核对两边都真是崩溃）。其余不逐处照搬，判断口径两条，④b5、④b7、④b8 照用：这些文件都由调度器写出（合同还经过校验，verdict 的 G0 核对它的哈希），只有手改才会类型不对；散在内部的照搬要在三条命令里加二十来处分支。接受 |
| 决策端点回复头的写法（④b4a 对照时查出） | http.client 按行读头、交给 email 解析器，很宽松；llhttp 缺省更严：头部合计超过 16 KB、只用 LF 换行都拒。TS 每个请求调大 maxHeaderSize、开 insecureHTTPParser 之后这两种与 Python 一致，行长（含 CRLF 超过 65536 是 LineTooLong）与头数（结尾的空行也计数，第 100 个头就是 HTTPException）照 Python 自己查。剩下对不齐的：头名里有空格，Python 照收，llhttp 宽松模式也拒（TS 报 network/BadStatusLine）；行长按“名: 值”加 CRLF 算，服务端在冒号后多写空白时边界差几个字节 | 服务商不会回这种头。契约钉住两边各自的结果，Node、Bun 落在确定的原因码上、不崩。接受 |
| 决策端点 HTTPS 超时的文字 | http.client 的超时文字分阶段：连接是 timed out，TLS 握手是 "_ssl.c:993: The handshake operation timed out"（行号随 CPython 的构建变，这是 3.12.10），握手之后读是 "The read operation timed out"。TS 写死这三句 | 握手那句契约对本机 Python 核对（假端点只接不说 TLS）；读超时的那句要端点的证书被信任，契约造不出来（不往系统证书库加证书），照 CPython 源码写。换 Python 版本时核对握手那句的行号。接受 |
| review-draft 的检查结果按 id 建 Map（themistally-15 复核 ④b8a 时指出） | Python 的字典里 1、1.0、True 算同一个键，TS 的 Map 不算 | 接受：检查项的 id 由合同校验限定为字符串，走不到 |
| review-draft 的 --out 带链接与 ".."（themistally-15 复核 ④b8a 时指出） | TS 的 path.resolve 先按字面消掉 ".."，再解析链接；Python 的 Path.resolve 按顺序解析链接，".." 前面恰好是链接时两边落到不同的目录 | 接受：只有手写这种路径才会遇到；第 ⑥ 步撤掉 Python 之后不再有差异 |
| hub 读 state.json 撞上别的进程的独占打开（⑤b 实测；themistally-15 接受，要求先查清机制） | 持有者用 GENERIC_READ、dwShareMode=0 打开时，Python 的 open（CRT 的 _wopen，不带备份语义）报 PermissionError（CRT 把 ERROR_SHARING_VIOLATION 映射成 EACCES），read_text 短暂重试，过了期限 _read_state 报“读不出”。libuv 打开文件总带 FILE_FLAG_BACKUP_SEMANTICS：进程令牌的 SeBackupPrivilege 启用时，TS 的读既不受别的进程独占打开的限制，也不受 ACL 读权限的限制，直接读到内容；停用时与 Python 一样（共享冲突报 EBUSY，拒读报 EPERM），走同样的重试与报错。实测：同一个持有者下用 ctypes 打开，不带备份语义报 32、带上就成功，把特权移除之后带上也报 32；icacls 拒本用户读的文件，特权停用时 Node 报 EPERM、启用时读得到，Python 两种状态都报 PermissionError。Git Bash 起的进程里这个特权是启用的，PowerShell 起的是停用的（hub 的 supervisor 经 Start-Process 起，属于停用的）。只影响读：写打开报 EBUSY、改名覆盖报 EPERM，启用与否都与 Python 相同 | 接受，不在 TS 里另写原生的打开（themistally-15，2026-10-31）：state.json 只在 .state.lock 里经 write_text_atomic 整份替换，读穿也只读到完整的旧版或新版；真实的冲突来自别的进程正在替换它，两边最终结果一样；切换之后信箱只有 TS 读写。契约 hub-mailbox 的 C4 两种状态都跑（probes/backup_privilege.py 设好特权再起探针）：停用时三边逐字相同，启用时 TS 读到真实内容 |
| hub 存状态时一次保存里有两个以上冲突（themistally-15 复核 ⑤b 时指出） | Python 的 save_state 在合并的那一层循环里按 set(ts) 与 set(seen) 的并集遍历键（kit_hub 里别的集合都先 sorted 再用，只有这一处），字符串集合的遍历次序随进程的散列种子变：一次保存里有两个以上的键冲突时，Python 自己写 state.conflict 的先后就不固定；TS 按插入次序，是固定的。账本里这几条的集合相同、先后不定，与 ④b6 的“两个报错名字的先后 Python 自己也随散列变”同类 | 接受：state.json 按 sort_keys 写，盘上的内容不受影响。以后的契约要造“一次保存两个以上冲突”时，把这几条 state.conflict 当集合比；现有的 B2、C1 每次只造一个冲突，不受影响。⑤f 把 kit_hub 里的 set 全过了一遍（themistally-15 也 grep 了一遍）：只有这一处会把次序漏进输出，其余都先 sorted 或只做成员判断 |
| hub 审计遇到嵌套很深的值（⑤c；themistally-15 实测） | 1000 到 2997 层：base 的 loads 固定报 RecursionError（算读不出的行），Python 的 json.loads 却读得出（能读到约 2997 层），这一段是确定的差异，与栈深无关 | 接受：这种输入几乎不会出现，契约生成的嵌套避开这一段。第 134 轮前另有 900 到 999 层一段：Python 的 _arg_strings（递归）抛不抛 RecursionError 随调用栈深度变（实测模块顶层 995 层才崩，多垫 60 层调用栈 960 层就崩）；第 134 轮（用户 2026-11-01 同意）改成显式栈，堵上了，次序照旧（随机两万组与原来的递归逐个比过），tests/test_kit_hub.py 加了 990 与 2000 层的回归，hub-audit 手写的边界钉了 960、997 层（997 层加上探针的几层栈，原来的递归会崩） |
| 审计里的 sorted（⑤c） | TS 照 CPython 3.12 的 list.sort：64 个以内先 count_run、再二分插入，比较的先后与 Python 相同，混了不能比的值时在同一处报 TypeError；更长的退回稳定的归并排序，全是同一类可比的值时结果相同。64 个以上又混了不能比的值或 NaN 时，报的是哪一对类型、NaN 落在哪可能不同；claude 的模型名里有 NaN 时，Python 自己的次序也随散列变；模型名混了不能比较的类型时，Python 报错里两种类型谁先谁后也随集合的散列次序变（⑤f 起崩溃也比文字：只对流里确实有不是字符串的模型名的请求，把报错里的两个类型名换成占位） | 接受：init 的工具表与模型名都由 CLI 产生，实际上全是字符串；契约的列表都在 64 个以下，NaN 不进 claude 的模型名。⑤f 起 pySorted 挪进 base 的 pyset，gatepost 的 sorted(explained.items()) 也用它：unmutated 的条目来自模型，64 条以上又混了不能比的类型时报的那一对可能不同，同样接受 |
| 会话文件的 glob（⑤c） | session_cut_short、claude_session_effort 按会话号拼 glob 模式；TS 用 dispatcher 的 globPaths，只认 *，会话号里的 ? 与 [ ] 当成字面，Python 当成通配 | 接受：会话号是 CLI 给的 UUID；契约只用这一类号 |
| 过渡用例的 rglob（⑤d1） | transitional_section 照 sorted(tests.rglob(`*.test.ts*`))；TS 照 Python 3.12 的 Path.walk(follow_symlinks=False) 往下走，用 lstat 判断，不进符号链接。联接（junction）Python 当目录走、Node 的 lstat 当链接，测试目录里放了联接时两边会不同 | 接受：desktop/web/tests 里不会有联接 |
| Windows 错误的文字跟着系统界面的语言（⑤f） | [WinError 5]、[WinError 32]、[WinError 267] 这一类文字，Python 取 FormatMessageW；TS 的 pyWinErrorMessage、replaceError 也取 FormatMessageW。同一台机器上两边一致，换了界面语言的机器上两边一起变 | 接受：契约在本机比（对 Python 真触发的 WinError 2、5、32、183 逐字比），不跨机器比文字 |
| 复制文件（⑤f） | shutil.copyfile 只复制内容；Node 的 copyFileSync 在 Windows 上走 CopyFileW，连只读属性与修改时间一起复制。只有源文件只读时结果才不同（seed_whitebox、accept_gate_post 的两处，accept.ts 复制旧稿那处同样）；复制失败时的报错文字是 Node 的（探针记成 JS: 开头） | 接受：白盒测试的存档与旧稿都是内核自己写的，不会是只读的 |
| 白盒日志的独占新建（⑤f） | Python 先 open(whitebox_log, "xb") 再调 run_supervised，TS 把 create-new 交给 runSupervised。日志已经在时两边都失败，报错不同（TS 的报错出在 runSupervised 里） | 接受：日志名里的时刻精确到微秒，同一个主任务的两次战后验收之间隔着一个门禁回合，生产上碰不到；注入 run_supervised 的重放里钉住的时刻每次调用不同，也走不到 |
| 原子写最后一次替换失败的文字（⑤f） | writeTextAtomic 照 os.replace 报 [WinError N]，N 从 libuv 的错误码反推：EPERM、EACCES 对应 5，EBUSY 对应 32。libuv 把 33（锁冲突）、170（资源在用）、231（管道忙）也归成 EBUSY，这几种反推不回原来的码 | 接受：替换文件实际只会碰上 5 与 32；pybase-config 对 Python 真触发的 32（源文件被不共享地打开）与 5（目标是目录）逐字比 |
| 文件系统的环境故障时的报错文字（⑤f，themistally-15 定的口径） | fsutil.writeText 打开失败时报 Node 的文字（ENOENT: no such file or directory, open '…'），Python 的 Path.write_text 报 [Errno 2] No such file or directory: '…'；上面复制那行的 copyFileSync 失败也属于这一类。⑤f 里走得到的是 run_mutations 写清单存档：唯一的调用方 accept_gate_post 先用 parents=True 建好 stage_dir/evidence，只有没有权限、磁盘满这类故障才会走到 | 接受，不全局改：要连 locks.ts 的 DirLock 一起动，收益只在迁移期间的对照，切换之后只剩 TS。口径（⑤g 到 ⑤j 照用）：文件系统的环境故障（目录不在、没有权限、磁盘满、复制失败），报错文字不对齐，统一接受；生产上走得到的报错照旧逐字对齐，包括 HubError、模型交来的值引起的崩溃、内核自己造出来的状态。以后碰到同类，在这一行补上函数名。⑤g1：base 的 mtimeUtcSeconds stat 失败时（returned_blockers、final_audit_turn；调用方都先确认过文件在：previous 经过 carryable，final_audit_turn 没有补丁时退回 run_dir） |
| 内核自己写的 ts 字段是怪类型时的报错（⑤f、⑤g1、⑤g2） | exec.run_dir、contract_task 不是字符串时，Python 在拼路径处报 TypeError，TS 照 str() 拼下去（⑤g2 起交给 git 的提交与 run_jev 的 exec.run_dir 照 Python 报 TypeError）；audit_history 是 5 这类不能反转的值时，Python 报 'int' object is not reversible，TS 报 not iterable | 接受（themistally-15 定的口径）：这几个字段只有内核自己写，不会是怪类型；执行端、调度器、决策端点交来的值（执行报告、checks.json、scope.json、JEV 的回答）照旧逐字对齐 |

### 10.1 迁移期间暂缓的改进

站主 2026-10-26 决定专心推迁移（第 9 节）。按 themistally-15 的协调意见，从 T022 B 片落地起，内核文件只修挡住工作的缺陷，不挡路的改进记在这里，等对应模块切到 TS 之后在 TS 上做。

| 记下的日期 | 模块 | 改进 | 来源 |
|---|---|---|---|
| 2026-10-26 | `pi_dispatch.secret_like_paths`（Python 与 TS 一致） | 键名含 `token` 就算疑似凭据：`pricing` 文档写着可以填的 `per_tokens` 一写，`validate` 就整段报“pricing 里有疑似凭据”，内核也不读这份配置。改成只在值像凭据、或键名是凭据类名字（`api_key`、`access_token` 这类）时才算；两边同一轮改。现在没人写 `per_tokens`，不挡路。**已改（第 125 轮）**：口径收窄为只豁免 `pricing.<provider/model>.per_tokens`、值必须是数字（themistally-15 定） | 第 ③a2 片的整份校验契约 |
| 2026-10-26 | `ts/packages/ui/test/secret-entry.test.ts` 的“全部反例都不回 201” | 握手时限只有 1 秒，负载重时偶发少起子进程（2026-10-26 全量与 T023 的执行端同时跑时 5≠10，单独重跑两遍都过）。门禁与 hub 的回归常与别的重活同时跑，红了会被当成返工。再红一次就放宽这条用例的时限（只改测试夹具，不改产品行为）；合入前红了就单独重跑一遍 | themistally-15 复核 ③d |
| 2026-10-26 | `desktop/web/tests/shellpages-settings.test.tsx`（门禁 T004、T013 的流水线跑它） | `grabShell` 负载重时拿到 null（2026-10-26 在 6ed53d0 上跑全部门禁基准，正与 T023 的收尾同时跑，13 条红；dc53c27 那一遍与 3d1e101 的 owner sweep 都过）。用的是桩（createShellStub，jsdom 里），不碰真内核。处理同上一条：合入前红了就单独重跑一遍；门禁或 hub 回归里再红一次就改夹具 | themistally-15 复核切换 |
| 2026-10-27 | `ts/packages/contracts/test/supervise.contract.test.ts` 的 S5a（调用方没有控制台） | 全量 vitest 里红过一次：孙进程还没写下 grandchild.pid，整棵树就被结束了（ENOENT）。单跑 25 passed。可以让用例先等孙进程的 pid 文件出现再开始计时 | ④b6 的全量 vitest |
| 2026-10-27 | filelock 契约的 F2（ts-bun）、locks 契约的 PA1（ts-bun）、ui 的 kernel-runner U28 | 全量 vitest 与 hub 的 owner sweep 同时跑时各红过一次（F2：Python 那一侧还没拿到锁，ts-bun 就拿到了；PA1：已退出的进程还被判为活着），单跑 120 passed。F2 已改：持锁方一直拿着、由 finally 结束（themistally-15 查出：等待方的 Bun 探针启动可能超过持锁的 4 秒）。2026-11-01 U28 在整套里又红过两条（这回没与 owner sweep 重叠，单跑 22 passed） | ④b6 补的全量 vitest |
| 2026-10-27 | `ts/packages/base/src/native.ts` 里返回 64 位句柄、失败后再取 GetLastError 的几处（进程监督的 CreateFileW、CreateJobObjectW 等） | Bun 为 64 位返回值分配 BigInt，分配可能赶上垃圾回收，回收里的系统调用把 last error 清成 0：成败按句柄判断，不受影响，只是报错里的错误码可能是 0。os.stat 那一路已经改成取到 0 就重开（路径语义的再补）；进程监督这几处要不要照改，等实际碰到。**已改（第 130 轮，切换 e）**：切换 d 的全量 vitest 实际碰上了（roles-probe 的 runtime scan 偶发报成 `[WinError 0]`）。native.ts 里读 GetLastError 的 13 处全部改成取到 0 就重做（`retryWin32`，最多 5 次，各调用失败时都没有副作用，逐个核过）；5 次都取到 0 时仍交 0，与 Python 文字不同，概率可以不计 | 路径语义的再补 |
| 2026-10-27 | `pi_dispatch.summarize_events` 的主仓库判断（Python 与 TS 一致） | 工具参数写成长路径前缀（`\\?\` 开头）的主仓库路径，`is_within` 认不出来，记成 main_repo=false，G2 不拦。要认作主仓库是改行为，等站主定 | themistally-15 复核 ④b6（2026-10-27 站主经 themistally-15 定：推迟，记成已知限制） |
| 2026-10-27 | `pi_dispatch._load_mutation_spec`（Python 与 TS 一致，④b5a 照搬） | 命令 id 的正则 `MUTATION_COMMAND_ID_RE` 以 `$` 结尾，`$` 也匹配结尾的换行之前，`"abc\n"` 能过校验；mutate 拼日志文件名（`<变异>-<命令>.log`）时 Windows 上报 WinError 123，崩在半路。改用 `fullmatch` 或 `\Z` 是内核行为改动，切换之后与别的校验一起改。清单是规划端写的，几乎遇不到 | themistally-15 复核 ④b5a |
| 2026-10-27 | `prepare` 建 worktree 的路径长度 | 实机里离 MAX_PATH 只剩 3 个字符。站主经 themistally-15 定：先不改，记着。真出问题时 git 会明确报“Filename too long”，可以用 `git config --global core.longpaths true` 绕开 | themistally-15 的 ④b7a 实机 |
| 2026-10-27 | 决策 report-screen 的状态上限（`max_state_chars` 20000） | 真实 attempt 里 29% 超过上限。站主经 themistally-15 定：先不改，决策功能在生产里是关的；真要开启决策之前，按方案 2 在内核里截短每条命令，Python 与 TS 同一轮改 | themistally-15 的 ④b7c 实机 |
| 2026-10-27 | `locks.contract` 的“Python、Node、Bun 同时往同一份配置各写不同的键” | 配置中心那轮变异抽查（b 组 5 条）跑基线时红过一次：9 个写进程里 1 个退出码是 1。2026-10-28 themistally-15 在 4f9b55e 的临时克隆里单独连跑 5 遍，每遍 58 条全过，没有复现；b 组 5 条变异锚点都对得上、全部抓住，整轮 24 条抓住 23、1 条预期内漏网。按负载下的偶发处理：再出现时先看是不是写进程等锁超时退出，测试的等锁时限可以放宽。2026-11-01 ⑤e1a 的全量 vitest 又红一次（12 个写进程里 1 个退出码是 1），这一条单独重跑 3 遍都过；退出的原因还没看。同日 ⑤e2a 的全量又红一次（第 11 个写进程，Bun，退出码 1），单独重跑 3 遍都过。写进程以 stdio ignore 起，退出的原因留不下：测试已改成把每个写进程的标准错误写进自己的文件，非零退出的那个带进断言信息（⑤e2a 之后的单独提交），下次红了先看它 | themistally-15 的配置中心变异抽查 |
| 2026-10-28 | `collect --recover`（Python 与 TS 一致） | run.json 在、却读不出来时（调度器正好在独占写 run.json 的时候死掉）崩出堆栈，不是一句清楚的报错。概率很低；修法约三五行：读不出就报“run.json 损坏，检查后处理”，或先改名成 .partial 再重建。等 collect 只剩 TS 之后在 TS 上改 | themistally-15 实机比对时看到（切换 c） |
| 2026-10-29 | `check --fresh` 的干净副本、`integrate` 的验证副本（Python 与 TS 一致） | 副本由仓库当前的 core.autocrlf 检出、打补丁，却按 meta 记下的 git_autocrlf 快照：记下的值与当前仓库的有效值不同时（例如在另一台 core.autocrlf 设置不同的机器上做 check --fresh；契约里布置的是 prepare 时 false、之后改成 true），检出出来的 CRLF 让快照对不上候选，干净副本建不起来（chain 契约“反过来”那条守着现状）。这台机器上两者一直都是 true，碰不到。修法：检出与打补丁也带上记下的值（-c core.autocrlf=…）；等这两处只剩 TS 之后在 TS 上改。修好之后：把 ts/mutations/autocrlf-paths-c3b.ts.json 里 F1、F2 的 equivalent 去掉重跑（那时应被抓住），chain 契约“反过来”那条的断言改成修好后的行为 | 切换 c3b 实测（themistally-15 提出查这两条路径） |
| 2026-10-29 | `kit_hub.retry_section`（hub，第 ⑤ 步换成 TS 时改） | 重派说明只附没过的检查，不附上一轮的执行情况。T024 的 attempt-001 单条回复撞上输出上限、一个文件都没写（events-summary.json 的 final_stop_reason 是 length，changes.json 为空），重派说明里看不出来，执行端多半以为是实现错了。改成附上摘要的执行完整性问题与“上一轮没有任何改动”，再提示“先写文件，边写边想，单条回复不要长时间只思考”。这次 attempt-002 过了，不挡路 | T024 验收片（themistally-15 一同核过） |
| 2026-11-01 | 合同版本与 attempt 的绑定（hub 与调度器，切换后在 TS 上做） | 新版本合同如果只是把执行器已经采纳的做法（contract_conflicts 里 adopted 的那项、interpretations）写进合同，更省的走法是拿现有候选按新版本重新 check，不重新执行。T025 的 v1→v2 就是这样：v2 的三处都只是追认 attempt-001 的做法，多花了一次执行（约 40 分钟）加上 v2 的门禁与审核回合。attempt 现在绑定合同版本，要改得同时动内核与调度器的流程 | T025 付费全程比对（themistally-15 提） |
| 2026-11-01 | `kit_hub.record_pass`（终审的结论，切换后在 TS 上做） | 终审只能记 PASS：DoD 有一条没满足、由用户接受为例外时，内核自己的记录会是“PASS 但那条没满足”。改成终审能直接记 ACCEPTED_WITH_EXCEPTION，带上豁免的 DoD 条目与决定者（verdict 的 --waive、--decided-by）。T025 的 attempt-002 违反 D14（往 /tmp 写固定路径），用户接受为例外、不重跑；落地的 attempt-003 没有违反，这次没碰上 | T025 attempt-002（themistally-15 提） |
| 2026-11-01 | `kit_hub.scope_missing_prefix`（Python 与 TS 一致，切换后在 TS 上改） | git 不加 core.quotepath=off，ls-tree 列出的非 ASCII 路径整条加引号：roots 存的是带引号的第一段，endswith 也对不上，这样的路径永远报不出“少了目录前缀”。TS 照抄，hub-contract-repo 用非 ASCII 的顶层目录与文件名钉住；改法是 git 加 -c core.quotepath=off（调度器的 git 封装 pi_dispatch.py:1211 一律带这个开关） | ⑤e1b（themistally-15 读 Python 时看到的） |
| 2026-11-01 | `kit_hub.workspace_status`（Python 与 TS 一致，切换后在 TS 上改） | `git status -z` 把改名与复制写成“XY 新路径、NUL、旧路径”，旧路径前没有状态码：Python 按 NUL 切开后把旧路径当成单独一项，前两个字符当状态、第四个字符起当路径，不超过 3 个字符的整项丢掉。门禁只新增一个文件的核对因此会把暂存的改名报成两项。TS 照抄，hub-contract-gate 用长短两种旧路径钉住；改法是遇到 R、C 状态时把下一项并进来 | themistally-15 复核 ⑤e2 设计稿时定照抄 |
| 2026-11-01 | 合同改写时的换行（Python 与 TS 一致，切换后在 TS 上定） | (a) sync_executor_line、bump_contract_version、set_contract_base 都是 read_text 读（通用换行）、写回时换行固定成 LF，改写 CRLF 的合同时整份变成 LF；合同本来由内核按 LF 写出，CRLF 只来自手改，基本无害。(b) bump 与 set_contract_base 的正则在冒号后与行尾都是“空白”，空白也匹配换行：行尾那段会把后面的换行一起吃掉（后面是空行时空行没了；那一行是文件最后一行时文件末尾的换行没了，gate_setup 的合同正是 base_sha 在最后一行）；冒号后那段也能跨行（“- base_sha:”后面直接换行、下一行是值时，两行被换成一行，值那一行没了；plan_version 的值隔着空行也会被吞）。改法：冒号后与行尾的空白都只认空格与制表符。TS 照抄，hub-contract-flow 的手写对照钉住这几种 | themistally-15 复核 ⑤e2b 时定 |
| 2026-11-01 | 整套 vitest 的并发（契约工具，迁移后做） | 整套里负载偶发的红越来越多：config-write 的锁、supervise 的 S5a、run-pre 的探针超时、ui 的 kernel-runner U28。采样契约的重放在机器空闲时每套就要 50 秒上下（themistally-15 2026-11-01 实测，三套合计：⑤f 167 秒、⑤g1 150 秒、⑤e2b 147 秒、⑤e2a 116 秒），REPLAY_TIMEOUT 只放宽了采样重放的时限。迁移后考虑给重的契约文件限并发（vitest 的 maxWorkers，或把重的契约单独分组跑），让“整套过了”重新可信 | themistally-15 |

**已定**（2026-10-22，themistally-15 代站主答复）：
1. 选择文件就是 `scripts/kernel-impl.json`，规矩见第 5 节。
2. Schema 校验器用 Ajv 8，第一份 Schema 落地时引入，条件见第 3.2 节。

**待定**：第 ⑥ 步对离线 v2 参考实现的处置（移目录，还是只留标签），届时再问。

**已定**（2026-10-28，站主经 themistally-15 答复）：决策客户端的 bad_key（拼请求头之前先检查密钥，报错时不再带出密钥原文）先不改，等 TS 迁移跑通以后，与换密钥、加强防护一起做。

---

## 11. 进度

| 步 | 内容 | 状态 | 提交 |
|---|---|---|---|
| 0 | 本计划；`ts/` 工作区骨架；样板 `publish_new` | 带条件通过，合入 | 266cd33 |
| 0.1 | 计划 v1.1（补进通过时附的条件）；包之间改按包名 import，并实测 Node 与 Bun 的解析 | 完成 | 见提交说明 |
| ① | 共享基础库：publish、pyjson、secrets、locks、jsonl、clock | 六项完成，出口条件的证据见 ①-jsonl 一行之后的汇总；等复核 | |
| ①-jsonl | 账本写入：kit_hub.Hub.append_event（at 在拿锁之前取并盖掉调用方的 at；.events.lock 文件锁与 Python 互斥；ensure_ascii=False、sort_keys=True 加换行；fsync）。读账本：read_text 之后只按换行切（第 56 轮的 kit_hub.jsonl_lines；之前是 str.splitlines）、逐行 json.loads，只跳过 ValueError，RecursionError 照抛。kit_logs 读大文件的原语：_jsonl_records（按字节从偏移逐行读，单行上限、超长只计长度，final 管末行）、_strip_eol、_iter_lines（坏 UTF-8 换 U+FFFD，BOM 照留）、_lines_before；分页、游标与脱敏显示归第 ② 步。契约 10 条（写入 J1–J5、读取 R1–R5），Python 先过；pyre 的白盒单元测试加 1 条（splitlines 的行界）；对照：Python、Node、Bun 各两个进程同时各追加 40 条（240 行完整、各自有序、三套读法一致），随机字节文件 6 个种子 × 40 个文件 × 9 次读取；变异 20 个全部抓住（“不建目录”是等价变异：文件锁本身就建上级目录，两边都是，已从清单拿掉）。原先照现行行为保留的一处已经修掉：ensure_ascii=False 不转义 0x85、U+2028、U+2029，str.splitlines 却把它们当行界，含这几个字符的记录读的时候被拆坏跳过；themistally-15 查出工人事件流的审计也因此能被绕过，内核第 56 轮改成只按换行切，TS 跟着改（契约 J2 先在 Python 上过）。更正 c5eb837 提交说明里 J4 的理由：并发对照没抓到“去掉锁”，是因为竞争窗口小，不是因为追加写原子——Node 以 FILE_APPEND_DATA 打开才是原子的，CPython 走 CRT、先 seek 到末尾再写，不是原子的；混跑期间 .events.lock 必不可少 | 完成 | 见提交说明 |
| ①-出口 | 六项：publish、pyjson、secrets、locks（目录锁、文件锁）、jsonl、clock 都有契约测试（Python 先过）、对照测试、变异检验（publish 11、pyjson 31、clock 13、目录锁 13、文件锁 8、secrets 20、jsonl 20，全部抓住；等价变异单列在各自的提交说明），全量 238 条测试与 tsc strict 无错 | 达到，等复核 | |
| ①-secrets | 疑似凭据的检测与脱敏（凭据库挪到第 ③ 步）：pi_dispatch 的 redact_secrets、redact_json（含白名单）、redact_obj、redact_tokens、secret_like_paths，codekit 的 looks_like_secret，decisions 的 normalize、is_sensitive、redact、redact_state。正则逐条翻译成 Python 语义：\w、\d、\s、str 的 isspace/isprintable/isupper/islower/isdigit、Cf/Cc、Cn 都查本机 Python 3.12.10（Unicode 15.0）生成的区间表（tools/gen_pyunicode.py），\b 写完整形式，re.I 按 Python 展开（多匹配 İ ı ſ K），Python 的 $ 写成 (?=\n?$)，替换一律用函数，长度与切片按码点。NFKC：Node、Bun 的 ICU 是 Unicode 17.0，把 Python 眼里未分配的码点换成私用区占位符再规范化（themistally-15 提出并验证），运行时比 15.0 旧就拒绝。契约 34 条，Python 先过；对照 6 个种子各 2400 次文本调用、600 次结构调用，加 74 个新分配码点 × 8 种上下文，三种运行方式逐字一致；变异 20 个全部抓住 | 完成 | 见提交说明 |
| ①-native（文件锁） | @themis/base/native：Bun 下经 bun:ffi 调 kernel32 的 CreateFileW、LockFileEx、UnlockFileEx、CloseHandle（POSIX 用 flock，未实机验证）；Node 下每次拿锁起辅助进程 native-helper.ts（第 ⑥ 步后是 __native 子命令）替本进程持锁，stdin 一关就显式退出，辅助进程意外退出时 assertHeld 报 FileLockLost。语义与 kit_hub.file_lock 逐项一致（同一个哨兵文件的第 0 字节、非阻塞、每 10ms 重试、60 秒超时、同样的超时文字），API 是异步的。④a 的文件锁验证全部通过：Python、Bun、Node 两两互斥（6 个方向），三种持锁进程被强杀后等待方在超时之内拿到锁，辅助进程手上有活动句柄时 stdin 一关照样退出。变异 8 个全部抓住 | 完成 | 见提交说明 |
| ①-locks（目录锁部分） | DirLock、TaskLock、ConfigLock 照现行三份实现各自的规则（接管、释放、owner.json 的字节与换行）；pid_alive（Windows 上调 tasklist）；read_text（通用换行、保留 BOM、严格 UTF-8、共享冲突重试）与 write_text_atomic。契约 15 条，Python 先过；对照：两套实现抢同一把锁互斥（三把锁 × 两个方向），ConfigLock 的主机名一致；变异 13 个全部抓住。DirLock 的接管竞争照样保留，另开内核轮次修。kit_hub.file_lock 要操作系统的文件锁，走 @themis/base/native（站主经 themistally-15 定：选项 1），jsonl 的追加等它的验证用例过了再接 | 完成 | 见提交说明 |
| ①-pyjson 补：报错文字 | themistally-15 审阅指出报错文字会经 str(exc) 写进输出（9 处）。JSONDecodeError 改成 Python 的 "<msg>: line <行> column <列> (char <位置>)"，位置按码点，错误对象带 msg、pos、lineno、colno；u 转义的边界条件照搬 CPython 的 _json.c；int 位数上限分读写两种措辞；编码报错写出位置与代理项；新增 rawDecode（不跳空白、不查 BOM，end 按码点与码元各给一个）。契约加“报错位置”“raw_decode”两张表，报错文字逐字比较；themistally-15 的 234 条独立用例（35 条非法输入）Node、Bun 全部逐字一致；变异 31 个全部抓住（BOM 那个不再算等价）。TypeError（sort_keys 遇到混用的键）只比类型，文字里类型名的先后取决于 CPython 的排序，现行代码走不到 | 完成 | 见提交说明 |
| ①-clock | 时间与编号的格式：utc_now、utc_compact（微秒）、信件编号、回合编号、attempt 目录名、审计编号。契约 5 条（格式、取值落在采样前后、一个进程里不重复、次序不倒退），Python 先过；对照：三种运行方式轮流发信，时间前缀按生成次序不倒退（同一微秒内靠随机后缀分先后，哪一套都不保证次序）；变异 11 个全部抓住。单元测试把 TZ 设成 Asia/Shanghai，在 UTC 的机器上也查得出误用本地时间。kit_logs 解析 ISO 时间（fromisoformat）放到第 ② 步 | 完成 | 见提交说明 |
| ①-pyjson | json.dumps/loads 的 Python 兼容实现：契约三张表（dumps 20 条、loads 23 条、读改写 3 条），Python 先过；对照 4 个种子，每个 600 次 dumps、900 次 loads（含随机变形的非法输入）、300 次读改写，三种运行方式逐字节一致；变异 22 个，抓住 21 个，1 个声明等价（Y17：去掉 BOM 检查只改报错文字） | 完成 | 见提交说明 |
| 0.2 | 计划 v1.2：按开工前的调查改第 ② 步的范围、出口条件与拆分（metrics 挪到 ④、⑤，补 logs cat，不另建 themis 入口）；补进同意时附的条件 | 同意 | 2cbd9aa 与之后一次 |
| ①-复核 | themistally-15 在独立 worktree 上复现第 ① 步全部 116 个变异（publish 的 Python 侧漏掉的是事先声明等价的 P04） | 完全核实 | |
| ② | 只读命令：调度器的 `status --json` 与 `logs` 五个子命令，三片做完一次切换 | | |
| ②a | `status`（文本与 `--json`，不含 `--assess`）、`logs list`、`logs show`。新包 `@themis/dispatcher`（repo、status、logs）与 `@themis/cli`（入口，收 `--pyargs-b64`）；base 加 `pyfmt`（repr、str、真值、len、照 Python 写 stdout 的字节）、`pypath`（abspath、normcase、relpath、Path.resolve、is_within、display_path、链接判定）、`native.fileAttributes`（Bun 经 FFI 调 GetFileAttributesW）、`pyre.pyIntParse`（Python 的 int()）。对照 37 个用例：Python 走真实命令行，TS 走规整参数，stdout 逐字节、stderr、退出码一致（现取的 elapsed_seconds 比格式与范围，崩溃只比退出码），每个 `--json` 输出过 Schema；pyfmt 对照 4 个种子各 800 次。Ajv 8.17.1 引入（fast-uri 用 overrides 钉在 3.1.8：3.1.9 发布才三天），四份 Schema 与仓库根的 plugin-lock-v1、plugin-manifest-v1 在 strict 下能编译。真实数据手动对照：主仓库 40 个 attempt 的 10 种调用逐字节一致（Node 与 Bun），输出都过 Schema。变异 37 个全部抓住（F12 起初漏掉：变异工具下临时目录是长名，补了经过 junction 的显式路径用例才分得出） | 完成 | 见提交说明 |
| ②b1 | `logs cat`：`@themis/dispatcher/logs-cat`（safe_page 的文本页与 JSONL 页、游标的编码与核对、整份与逐行脱敏、超长行与隐藏行；偏移与切片按码点，64 MiB 的文本不拆数组，用补充平面字符的位置二分换算）。游标绑定的文件身份 (size, mtime_ns, ino)：本机 NTFS 上 Python、Node、Bun 实测取值相同。入口改用 pyjson 解析参数（`--limit` 这类 Python int 超出 JS 数字精度时，报错里原样写出）。对照：合成夹具的用例 17 个，加同一仓库里逐页翻的 3 个（文本长行按片、JSONL 长行按行内字符续读、文件变长后续读与改写后作废，含变长同时改写）；真实证据手动对照：3 个 attempt × 9 种文件与页大小顺着游标翻页，加 7 种报错，共 78 次调用，Node 与 Bun 都与 Python 逐字节一致。（2026-10-24 七端第 87 轮补 `--complete-lines`：pyargs v1 的 logs cat 一支原地加 `complete_lines`，Python 与 TS 同一个提交；对照加 4 例与逐页的 P04。）变异 21 个全部抓住（K11“JSONL 游标不核对之前的一段”起初漏掉：原用例改写时大小不变，修改时间那条先报了作废；补了“文件变长、之前的字节也被改了”才抓住）；“rfind 的边界保护”是等价变异（首页以换行开头时切片必以换行结尾，构造不出），没列 | 完成 | 见提交说明 |
| ②b2 | `logs search`。`@themis/base/pyregex`：parser（`Lib/re/_parser.py` 逐段移植，报错文字与位置照原样，`\N{…}` 用生成的 Unicode 15.0 名字表，含别名、谚文音节与 CJK 统一表意文字的规则）、compile（`_compiler._compile` 编出 sre 的字节码；单字符的匹配器按 sre 运行时的判定算成码点集合，大小写用 `_sre` 的简单映射与 `_casefix`；信息块的字面量前缀与字符集前缀照 `_compile_info`，字符集前缀按整个模式的标志编译的怪癖照搬）、engine（`sre_lib.h` 的 SRE(match)、SRE(search) 移植，显式上下文栈，长行上的重复不撑爆调用栈）、search（第 58 轮的三道检查，次序写死）。Python 侧把三道检查与编译抽成 `kit_logs._compile_search`（行为不变，109 条测试照过）。`@themis/dispatcher/logs-search`：safe_lines 与 cmd_search。第一版编成 JS 正则，Node 下对照全过，到 Bun 下才撞上 JavaScriptCore 的前瞻缺陷与原子组的语义差别，改成移植匹配器（r3 §10 与 AGENT_LEARNINGS 有记录）。对照：CPython `test_re.py` 的 1265 个字面量语法分析逐字一致；搜索语料 1.85 万项、随机模式 8 组 47 万项，Python 与 TS 结果一致（Bun 全跑，Node 跑了语料与其中 4 组）；仓库里的对照测试（手挑的 79 个写法 × 40 段文本，两种随机生成各 3 个种子 × 400 个模式，Python、Node、Bun 三方比较）。契约：logs search 的用例 20 个（文本与 JSON、截断、跳过计数、报错原文、崩溃、`--max`、`--task`、sre 的前缀怪癖），stdout 逐字节一致，`--json` 过 logs-search-v1。性能：2000 万字节、4.9 万行的合成日志上，10 种常见写法里慢的约 3 倍（`(?:read|edit) src/\w+\.ts` 223 对 73 毫秒），快的比 Python 还快（`\bfail(?:ed|ure)\b` 58 对 156 毫秒）。变异：正则 32 个，抓住 30 个，2 个声明等价（没有大小写的字面量与字符集要不要小写化：逐个码点核对过 `\w`、`\d`、`\s` 与 sre 的小写映射）；logs search 8 个全部抓住 | 完成 | 见提交说明 |
| ②c | `logs usage`。`@themis/base/pydatetime`：`datetime.fromisoformat` 的 C 实现（CPython 3.12.10 `_datetimemodule.c`，Python 实际用的就是它，不是 `_pydatetime.py`）逐段移植，在 UTF-8 字节上按 C 字符串解析，怪癖照搬并逐条在 Python 上实测过：秒后面的冒号当小数（`10:00:00:5` 是 0.5 秒）、小数点后一位都没有也收、`Z` 后面跟 NUL 当结尾、分隔符可以是任意字符（多字节按首字节跳过）、时区偏移的秒为零时连带的微秒丢掉、偏移的分钟不查上限（`+00:99`）；加 kit_logs._parse_iso 的换算（结尾 Z、必须带时区、换成 UTC、溢出为不可用）。`@themis/dispatcher/logs-usage`：执行端（events-summary.json 的 known、partial、unknown，按模型合计，计数一律 bigint）与规划端（会话记录逐行读、按消息 id 归组、重复与两种冲突、未完成、时间窗、坏行与非候选的计数、按模型与是否子代理合计）。对照：pydatetime 手挑 62 个写法加 4 个种子各 3000 个随机串，Python、Node、Bun 一致；logs usage 的契约用例 11 个，stdout 逐字节一致，`--json` 过 logs-usage-v1；真实数据：主仓库的 runs 加本机 119 MB 的会话记录，6 组参数在 Node、Bun 下共 12 次调用逐字节一致。变异：pydatetime 15 个、logs usage 16 个全部抓住（起初各漏一个：分隔符以外的代理字符、带 usage 的空 id，补了用例） | 完成 | 见提交说明 |
| ②-切换 | 选择文件 `scripts/kernel-impl.json` 的 `readonly` 改成 `ts`（r3 §10 第 64 轮）。启动器照第 ② 步“转交给 TS 的启动器”：转交名单写死、检查次序（名单、discover、TS 入口、装好戳记、Bun 路径）、`--pyargs-b64`、句柄直接继承、带 KILL_ON_JOB_CLOSE 的 Job、退出码原样；Bun 固定带 `--no-env-file` 与 `--config=ts/bunfig.toml`，子进程环境去掉运行时注入变量。装好戳记由 `ts/package.json` 的 postinstall 写，第 61 轮的后台回归在戳记过期时于落地锁里重装。`meta.json` 记 `impl` 与冻结的 `kernel_protected`，账本的 `dispatcher.called` 记 `impl` 与 `tool_version`。测试：`tests/test_kernel_impl.py` 70 条（选择文件的严格解析、名单与参数键、检查次序、启动器四条、六种注入各一条并带对照组、回退逐字节、禁区与同目录判断）；hub 新增 5 条；readonly 契约用例全部加上经真的启动器的端到端（87 条全过）；全量 pytest 在藏起装好戳记时照过（2578 passed，test_dispatch.py 另 50 passed），说明没有测试依赖 TS 装没装。变异 36 个全部抓住（第一轮漏 2 个：规格的 `-k` 漏选一条、回退测试两边走同一份坏代码，补断言后抓住） | 完成 | 见提交说明 |
| 0.3 | 计划 v1.3：按开工前的调查重写第 ③ 步（plugins 归入、`secret set` 留在 Python、六片加切换、混跑的三条契约、混合期的进程内调用）；记下站主 2026-10-26 专心推迁移的决定 | 同意 | 与 @themis/config 的骨架同一次提交 |
| ③ | 配置中心 | | |
| ③a1 | 插件记录与题库锁。`@themis/config`：`plugin-records`（codekit/plugins 的记录层）、`decisions`（问题的形状、清单与内容锁、配置解析与生效模式、`battery_link_problem`）。`@themis/base` 加 `pyNfc`、`pyLower`、`pyCasefold`（CASEFOLD 表由 gen_pyunicode.py 生成）、`pyurl`（urlsplit、port、hostname、ip_address）、`pyio`（read_bytes、read_text 的 OSError 与 UnicodeDecodeError 原文）、`pyvalue`（Python 的 ==）。契约：插件记录 75 条（以 plugins/ 下提交的 9 个真实插件为底），决策 118 条（含临时目录里复制改坏的插件、junction 与文件符号链接）；对照：三个种子各 600 份改坏的 manifest 与锁、lower 与 casefold 与 NFC 跑遍全部码点、3,200 段随机字节解码、2,500 个拼出来的 URL、3,016 个地址、2,000 对随机值的 ==。变异：TS 42 个全部抓住（第一轮漏 4 个，补用例后重跑抓住），Python 12 个全部抓住 | 完成 | 见提交说明 |
| ③a2 | 校验与只读展示。`validate`（kit_config 的 18 个键与 pi_dispatch 的几个校验函数、plugins 的修复提示、读配置文件）、`roles-check`（v3 五个键）、`secret-config`、`secret-store`（来源、删除、describe；Windows 凭据管理器经 FFI 只取字节数，Node 后备经辅助进程）、`history`（读审计、编号、快照、逐键差异）、`commands`（validate、show、history、secret check、secret remove）、`cli`。`@themis/base` 加 `purePathStr`（pathlib 的规整写法，含 ntpath.join）、`native.credentialBlobSize`、`credentialDelete`（FFI 单列：advapi32 的 CredReadW、CredDeleteW、CredFree）。契约：整份校验 80 条、凭据库 20 条（file 与 off 模式往返；system 模式只读不存在的测试目标）、命令行 41 次运行的 stdout、stderr、退出码逐字节；对照：600 个随机路径与固定的盘符、UNC、设备路径。变异：TS 39 个，第一轮漏 11 个，补 8 条用例后重跑抓住；H05 等价；R02 移到 ③c；V12 测不到（见提交说明）。Python 10 个：抓住 9，Q02 等价。查出 Python 一侧一个不挡路的缺陷，记在第 10.1 节 | 完成 | 见提交说明 |
| ③b | 写入事务与 kit_config 的写命令。`transaction`（审计追加、快照、resolve 与 observed、actor、写模式与 state 令牌、D8 的确认）、`roles-binding`（生效绑定、`binding_tuple`、在跑的 attempt）、`write-commands`（set、unset、init、decisions、rollback）、`cli` 的写命令；`@themis/base` 的 ConfigLock 报错文字照 Python 逐字。契约：交替写 3 个种子各 32 步（每步随机交给 Python、Node 或 Bun，与全 Python 的仓库逐步比较输出、配置、快照、history 与审计）、中断的事务与半行、init、WARN 与 actor、运行中的一串命令（D8、预览、令牌格式、删光子键），锁互斥 9 个进程同时写；锁契约加 CL4、CL5。变异：TS 24 个、Python 7 个，第一轮各漏 4 个与 1 个，补用例后重跑全部抓住 | 完成 | 见提交说明 |
| ③c | kit_roles 不起 CLI 的部分。`roles-local`（本机文件的核对与读、`local_command`、`runtime_command`）、`roles-binding` 的 `resolve_role_executor`、`roles-commands`（runtime list\|add\|remove、profile、role、preset 的全部子命令）、`cli` 的写模式按 Namespace 里有没有 dry_run 判定；`@themis/dispatcher` 的 `executor`（executor_class、allowed_executor_check、load_binding_record、不带 runtime 的 resolve_pi_command）；`@themis/base` 的 `pyshutil`（shutil.which）与 pypath 的 join、split、parent。契约：库函数 79 条（假的 pi、node、claude 放在临时目录）；85 步写命令序列在三个仓库里各由一种实现执行，每一步与最终状态一致，断言走到 20 处关键路径；读命令三种仓库逐字节；交替写序列加进 ③c 的写命令。变异：TS 库函数 24 个抓 23、1 个等价（L14），命令 19 个全抓；Python 库函数 5 个、命令 3 个全抓；第 ③a2 片移来的 R02 抓住 | 完成 | 见提交说明 |
| ③e | plugins 命令与 strict_json_loads。`plugins-commands`（kit_plugins 的 list、show、verify、enable、disable：枚举、读前链接检查、单插件核对、权限授予与影响、题库门禁、dry-run 的文字与 JSON 预览）、`cli` 转交 plugins；`@themis/base` 的 `protocols`（strict_json_loads，错误码与先后次序照 Python）、pyjson 的组装器、pyio 的读错误不带文件名。契约：严格 JSON 51 条加三个种子各 600 份随机文档；plugins 21 个场景、98 步，覆盖 oracle 的 P1–P17 与复审补的场景，每个场景断言走到了要测的路径；交替写序列加进 plugins 的写命令。变异：TS 严格 JSON 12 个、plugins 24 个，第一轮各漏 1 个、补用例后抓住，另 3 个等价；Python 8 个，抓住 7、1 个等价 | 完成 | 见提交说明 |
| ③d | 会运行本机 CLI 的命令。`@themis/dispatcher/pi-cli`（run_capture 走 ④a 的 runSupervised、child_env、parse_help 与 --list-models 的解析、pi_model_readiness）、`@themis/config/roles-probe`（runtime scan [--add]、runtime probe、models、doctor [--record]），cli 转交这四条。契约：探针级 6 条（解析 26 条手写加三个种子各 400 段、child_env、cwd_relative_parts、run_capture 12 条，另一条只测 TS 的进程树超时）；命令行 12 条，假 pi 经 npm 样式垫片与 PI_DISPATCH_PI_CMD 两条路起，每步另比假 pi 收到的 argv 与环境。变异：TS 47 个，第一轮各漏 1 个（C07 等价、R18 补夹具后抓住）；Python 8 个全部抓住 | 完成 | 见提交说明 |
| ③-切换 | 选择文件 `scripts/kernel-impl.json` 的 `config` 改成 `ts`（r3 §10 第 122 轮）。`TS_CONFIG_COMMANDS` 写死 config、plugins 下 33 个叶子命令（`secret set` 不转交），`config_handoff` 用 kit_config、kit_plugins 自己的 argparse 解析，帮助、用法错误与 kit_config 的两条组合检查由 Python 答，不先找仓库，context 交 kit 根与等配置锁的秒数；`argv_impl` 照同一份名单。契约：配置中心五份都加第四种运行方式“经真的启动器”（交替写与锁互斥里也有）；pyargs Schema 按 argparse 补上 33 条，并核对启动器生成的参数。**更正（2026-10-26）**：第 122 轮提交说明里的 A3（“没装 TS 依赖的临时 worktree 里全量 pytest 3015 passed”）不成立：那个 worktree 里先跑了全部门禁基准，ui 门禁的流水线自己 `bun install --frozen-lockfile`、写下了装好戳记，之后的全量其实装了依赖。2026-10-26 在 d1873a9 的新 worktree 里补跑（同一条命令里先后核对 `ts/node_modules` 不在）：1 failed / 3029 passed / 229 skipped，失败的是 `test_exe_search` 的 `status --json`（第 64 轮把 readonly 切到 TS 起就有，报“TS 实现没装好”）；另有 `test_kit_v300` 的 RepoArgument 里 `plugins list` 被启动器的同一句报错蒙过去（只断言了 `ERROR:` 与退出码 2）。两处都由迁移计划 D5 修好 | 完成 | 见提交说明 |
| 0.4 | 计划 v1.4：按开工前的调查与 themistally-15 的复审重写第 ④ 步（21 条命令加 `status --assess`、八片加切换、D1–D4、对照办法、影子运行、混合期的 26 个名字）；v1.5 补 D5（起真调度器子进程的测试在没装 TS 依赖时钉成 Python，分环境的出口条件） | v1.4 复审通过（themistally-15）；v1.5 待看 | |
| ④a | Windows 进程监督的验证（第 8.2 节，选候选 3）。`@themis/base/supervise`：`runSupervised` 与 `run_supervised`（第 70 轮）逐项一致，Bun 下经 native.ts 调 kernel32（挂起创建、另起进程组、加入带 KILL_ON_JOB_CLOSE 的 Job 再恢复、只继承三个标准流句柄、CTRL_BREAK 与宽限、残留进程），Node 下经 Bun 辅助进程（DETACHED_PROCESS 起、再挂到调用方的控制台）；`@themis/dispatcher/argv`：`ensure_argv_safe` 逐字节移植。契约 24 条（三套实现跑同一组场景，结果逐字段比较；含挂起之后一条指令也不执行、孙进程脱离父进程也被结束、两种控制台状态下 CTRL_BREAK 的去向、中断、杀掉调用方、`.cmd` 与 npm、255 条 `ensure_argv_safe` 语料）、白盒 8 条；变异 19 个全部抓住。第一轮契约查出 Node 后备的辅助进程在调用方没有控制台时被另配一个控制台，CTRL_BREAK 的结果与进程内调用不一致，改成 DETACHED_PROCESS 加 AttachConsole | 完成 | 见提交说明 |
| ④b1 | 合同。`@themis/dispatcher/contract`（`_md_*`、`normalize_contract`、`derive_contract_json`、`validate_contract`、`invisible_char_warnings`、`branch_subject`）；`contract-plan`（`validate_plan`、`_load_fixed_contract_pair`、planner-v2 的发布门禁与 `codekit.planner.validate_publication_receipt`、`role_binding_warnings`、`missing_fact_path_warnings`、`base_behind_head_message`、`plan_key_from_arg`、`resolve_commit`，命令 validate、derive-json）；`kernel-config`（内核读配置的 `Repo.config`、`extra_protected_paths`、`planner_paths`、`kernel_protected_paths`，config 包改为从这里导入）；`patterns`（glob 与保护名单）。base 补 `pyshlex`、`pySplit`、`isCf`、sre 的 `compilePattern`，修了 `ci` 把连字符转义成 u 模式不认的写法。cli 接上 validate、derive-json：context 交 `kit_root`、`kernel_impl`，kit_roles 由 cli 交进去（dispatcher 不反过来依赖 config）。契约：本仓库 475 对真实合同的 derive 与 validate，两个种子各 200 份改坏的变体，8 条手写的边界；validate_plan 在临时仓库里的 64 种合同对（缺文件、坏 JSON、不是 UTF-8、planner-v2 回执与 outbox 的 36 种情形、按角色写、基线落后、配置的几种毛病）与 80 次真实合同抽查（选择文件全部 python 与 readonly 为 ts），kernel_protected_paths 的 24 种组合；两条命令在三份实现各自的仓库里跑同一串 17 步，比退出码、输出与写出的文件字节（Windows 上是 CRLF）。变异 43 个（解析 24、validate_plan 一层 19）：第一遍漏 8 个，都是真实合同与随机改坏碰不到的写法（节名的大小写、时间分配的同级条目与 70%–80% 之间、顿号、optional、程序名对不上、两个“；证据：”、没写 required），补手写用例之后全部抓住 | 完成 | 见提交说明 |
| ④b2 | 证据目录与 git。`@themis/dispatcher/evidence`（三张状态表、write_json、read_json、set_state、log_event、load_attempt、sha256_file、candidate_patch_ok、artifact_matchers、split_extras、remove_worktree）；`gitops`（line_ending_args、snapshot_tree、unindexable_paths、diff_raw、tree_drift）；repo.ts 的 git 加 env 与 index_file，另有 check=True 的 gitChecked 与 gitText（Windows 上 cwd 不存在时照 Python 报 NotADirectoryError 崩溃，不说成找不到 git）。命令 mark、cleanup、wait（不含 --assess，④b4 再接；TS 收到 --assess 时报还没有这条命令）、metrics、release-check、sync-adapters。pricing_table、_release_allow_rules 挪进 dispatcher 的 kernel-config，expanduser 挪进 base 的 pypath，config 照旧转出；base 补 pyFixed（`%.Nf` 按二进制的精确值舍入、中点取偶）、pyRound、pyAdd、pySum。契约：mark、cleanup、wait 31 个场景（真的 git worktree；每个场景另断言输出里有对应分支的文字，第一版有几条 cleanup 场景因为 8.3 短路径其实没走到要测的分支，状态码碰巧对上），metrics、release-check、sync-adapters 21 个场景（8 个任务通过 1 个的 12.5%、全角数字的内网地址、BOM、CRLF、不合法的 UTF-8、一个文件命中过多、允许规则、拒绝清单、junction、目标是文件），数字格式化手写与两个种子共 1,300 多条；三份实现逐字一致，崩溃只比退出码。变异 34 个，第一遍全部抓住。顺带查出 Python 内核的一个问题：pricing 下的 per_tokens 被疑似凭据检查当成凭据（第 10 节） | 完成 | 见提交说明 |
| ④b3 | 检查、基线与结论。`@themis/dispatcher/command-runner`（ANSI_ESCAPE_RE、_next_number、worktree_root、_resolve_argv、_supervised_record、_run_command_item、run_setup、prepare_fresh_workspace）；`gates`（FAILURE_CLASSES、GATES、binding_record_problems、verify_inputs、attempt_origin_notes、planner_attempt_publication_errors、evaluate_gates 的 G0–G6、failed_gates）；`check-commands`（cmd_check、cmd_baseline、cmd_verdict）；gitops 补 effective_autocrlf、_line_endings_only。base 补 pyMkdir（照 pathlib 的 parents、exist_ok）、pyReadTextReplace、pytempfile（gettempdir、mkdtemp）、pyWhich、compilePy 带标志编译（parse 收 flags，re.X 照 CPython 交给顶层）、supervise 的 stderr 可以并进 stdout、PyOut 照 Python 的块缓冲（标准输出写进文件或管道时，ERROR 先于还没冲出的 NOTE、GATE 行；CHECK、BASELINE 行照 Python flush）。cli 接上 check、baseline、verdict，context 交 platform（Python 的 platform.platform()，G0 比对派遣机器用；④ 切换时由启动器交）。契约 98 条：check 38、verdict 43（含门禁 G0–G6 的各种组合）、baseline 10，stdout 与 stderr 写进同一个文件的次序 5 条，D2（命令的进程组收到 CTRL_BREAK，check 与 baseline 各一）2 条；真的 git worktree 与干净副本，比退出码、输出与跑完之后的证据目录（checks.json、verdicts、基线记录逐字段，时间、pid、mkdtemp 的后缀换占位符），Python、Node、Bun 逐字一致。sre 移植的带标志编译另对照手挑的写法 × 8 种标志与两个种子各 300 个随机模式。写契约时查出输出模式里的反向引用与条件分组 TS 编不了，先由第 129 轮在校验时拒绝。变异 108 个，第一遍跑的 106 个抓住 101；漏掉的 5 个：CHECK、BASELINE 行的 flush 只有边跑边读看得出（变异命令加上 D2 一组后抓住），补 CI=1 那一句外层本来就有 CI（场景用 env_remove 去掉外层的后抓住），检查之前就有、被检查删掉的缓存（补用例后抓住），报告是目录时 Windows 上大小为 0（写明等价）；带标志解析的 2 个之后加，都抓住。全量 pytest 3047 passed / 228 skipped，全量 vitest 1028 passed / 1 skipped。**复核后补**（themistally-15 复核 d14ea7c）：PyOut 照 CPython 3.12 的两层缓冲重写（一次 print 是两次 write；单次 write 有 8192 字节及以上时先交出手上的 pending，这一条是补的时候实测出来的），另加 pyout 对照（手挑 10 组、12 个种子的随机串，stderr 与 flush 穿插）与 120 行 GATE 的合并输出；mkdir 改走 pyos 的 pathMkdir、osMkdir，--fresh 时 worktree_root 建不出来照 Python 记 aborted；meta、candidate 的字符串字段与检查项的 cwd 类型不对时照 Python 崩（其余见第 10 节），崩溃场景另核对两边都真是崩溃。变异 24 个，22 个抓住、2 个写明等价。全量 pytest 3047 passed / 228 skipped，vitest 1064 passed / 1 skipped。 | 完成 | 见提交说明 |
| ④b4a | 决策客户端（④b4 拆成两片的前一片）。`@themis/config/decisions-client`：http_transport、check_answer、Session、usage_totals、describe、probe、decisions_session 与 battery_drift 的记录（dispatcher 不能 import config，用它的命令在 ④b4b 经 cli 接进来）。config 的 decisions 加 load_locked_batteries；secret-store 加 resolve，native 加 credentialRead（Session 在环境变量没设时从凭据库读 key，照 Python；Node 后备经辅助进程的管道交回）；base 的 pyjson 加 loadsBytes（json.loads(bytes)：detect_encoding 加 surrogatepass）。D4 的做法：node:http、node:https（Bun 的 fetch 会走 HTTP_PROXY）；系统证书库（去重后与 Python 缺省上下文是同一组，契约逐张核对 SHA-256）；请求头照 http.client 的次序与写法，线上字节三边相同；不跟随重定向；超时自己计（Bun 在 TLS 握手阶段不发 timeout 事件；连接、握手各一个期限，之后每收到一次数据重新计时）；llhttp 放宽之后照 http.client 查行长与头数（结尾的空行也计数，最多 99 个头）。契约 72 条，其中一条显式打开才跑（凭据管理器里的假 key，三边都读出、只出现在 Authorization 头里，规划端手动跑过）：本机裸 TCP 假端点的传输场景 27 个，比结果与请求字节；回复头的写法与上限 7 条；证书集合；json.loads(bytes) 随机 1000 段；check_answer 随机 1200 条；Session.ask 18 条（结果、记录、请求）；用量、describe、probe；decisions_session 8 条。变异 40 个，39 个抓住，1 个写明等价（问题清单经 check_question 规整过，发出去时的过滤是防御性的）。全量 pytest 3047 passed / 228 skipped，vitest 1135 passed / 2 skipped。另加 vitest 的 globalSetup：装好戳记过期就整轮先停（themistally-15 建议）。**复核后补**（themistally-15 复核 b29ab6c）：base 的 pySum 照 CPython 3.12 的 builtin_sum 重写（float 的 Neumaier 补偿、C long 的快速路径在 Windows 上是 32 位；原来逐个相加，0.1+0.2+0.3 差在末位，已在生产上走 TS 的 metrics 也受影响），check_answer 的两处求和改用它；native 的 nextLine 解析失败不再从回调里抛、报错不带原文。sum 对照 1200 串、坏回答 600 条、metrics 一条，变异 6 个全部抓住。全量 pytest 3047 passed / 228 skipped，vitest 1139 passed / 2 skipped。 | 完成 | 见提交说明 |
| ④b4b | 运行健康判断与决策回放（④b4 拆成两片的后一片）。`@themis/dispatcher/run-health`（_run_health_state、assess_run、decisions_records_of；会话只用接口，cli 从 config 的 decisions_session 接进来）、`decisions-replay`（decisions replay 的文字与 --json、--out）；wait、status 接上 --assess（改成 async），usage_totals 挪进 dispatcher 的 decision-records；cli 加 decisions 路由。启动器照旧不转交带 --assess 的 status，路由在 ④ 切换那一轮改。顺带修 pySum：int 快速路径里每一项按 C long、累加和按 Py_ssize_t 判溢出（themistally-15 复核 cf99239 的 2 万串里查出一串）。doctor 挪到 ④b7。契约 22 条（决策端点是单独进程的替身，被测命令照常同步起；比退出码、输出、发给端点的请求与决策记录）：status --assess 7 条、wait --assess 5 条、assess_run 跨 tick 3 条（探针连问：连续提示、打转、shadow 不提示）、decisions replay 7 条。变异 20 个，第一遍抓住 19，漏掉的 D01（通过类只认 PASS）补了带例外接受的任务后抓住。全量 pytest 3047 passed / 228 skipped；vitest 1159 passed / 2 skipped、2 条测试侧的失败（随时间变的 state 哈希没抹；usage_totals 挪动后④b4a 清单 U01、U02 的锚点过期），修后两个文件 23 条全过，U01、U02 重跑抓住 | 完成 | 见提交说明 |
| ④b5a | difflib 移植、变异清单校验与 `mutate --check-anchors`（④b5 拆成两片的前一片）。`@themis/base/pydifflib`（SequenceMatcher：autojunk、find_longest_match、get_matching_blocks、get_opcodes、ratio，按码点）；`@themis/dispatcher/mutate`（_load_mutation_spec、_mutation_spec_warnings、_anchor_count、_anchor_hints、_first_difference、_later_difference、_check_anchors，cmd_mutate 与 _mutate_tree 的开头）；cli 的 mutate 走块缓冲。--check-anchors 只读，不运行命令、不写文件，所以真数据可以直接用：仓库 ts/mutations 下全部 67 份清单，对当前的树与一棵改坏的副本各核对一遍，三边逐字一致。契约：difflib 对照 6 组（手挑 14 对 × autojunk 开关、随机串 1200 对跨 200 的门槛、代码行的变体 800 对）；mutate-anchors 17 条（真数据 2 条、各个提示分支、清单的各种坏法与合并输出、参数组合）。变异 20 个，第一遍抓住 18：L02（popular 按 >= ntest）补了恰好 n//100+1 次的手挑输入后抓住；L05（相邻的块不合并）写明等价（isjunk 为 None 时两头已扩到底，不会有相邻的块）。全量 pytest 3047 passed / 228 skipped，vitest 1184 passed / 2 skipped | 完成 | 见提交说明 |
| ④b5b | mutate 的整轮运行（④b5 拆成两片的后一片）。`@themis/dispatcher/mutate` 补 _apply_mutation、_run_mutation_rounds、_mutation_outcome、_session_aborted、结果行与计数、决策点 mutation-equivalence（_decide_mutation 等），cmd_mutate 的 attempt 模式与 _mutate_tree。--tree 在原树上原地改：每条变异跑完在 finally 里写回原始字节，全部跑完再把清单里的文件与开始时逐字节比一遍；attempt 模式在干净副本（git worktree）上跑，用完移除。`@themis/base/pyre` 补按码点的 pyStrFind、pyStrCount、pyStrReplace（孤立的代理项按码点对不上补充平面字符的半边；空串与 replace 的次数照 Python），顺带修 ④b5a 的 anchorCount（原来按 UTF-16 数）。契约：mutate-run 41 条（--tree 25、D2 两条、attempt 14；比输出、记录目录、发给决策端点的请求与跑完之后的树）；pystr.compare 手挑 24 条加随机 3000 条；mutate-anchors 加孤立代理项一条。check 与决策契约里的夹具挪进 attempt-fixtures.ts、endpoint-fixtures.ts。变异 54 条全部抓住；全量 vitest 1229 passed、2 skipped，pytest 3047 passed、228 skipped。 | 完成 | 见提交说明 |
| ④b7a | prepare（④b7 按 themistally-15 的建议拆成三片：b7a prepare；b7b collect 与 run；b7c smoke 与 doctor）。`@themis/dispatcher/executor-resolve`：resolve_executor、resolve_bound_executor、_role_binding_candidate、_binding_drift_note、_written_binding_note、_publish_binding_record（单独成模块：contract.ts 引用 executor.ts，放进 executor.ts 会成环；版本记录照 Python 用 pyPublishNew，写不进去时的报错文字与 os.rename 一致）。`@themis/dispatcher/prepare`：budget_usage、allocate_attempt、pending_attempt_notes、cmd_prepare；TOOL_VERSION 写进 meta.json，切换那一轮再与常量表逐项对照。kit_roles 经 BindingRoles 交进来（多 configErrors、bindingTuple）；决策配置的严格检查由 cli 交进来。D1：context 加 python（platform.python_version()），切换那一轮由启动器交。契约：prepare 30 条（三边比退出码、两路输出、.agent/runs 下的全部证据、worktree 的数目、检出的文件与目录名的前缀；meta.json 的 impl 单独断言），D2 一条（setup 跑到一半收到 CTRL_BREAK）。变异 45 条全部抓住（首轮 44 条漏 P09：重叠的文件之间用什么连没有用例；补“重叠超过 10 个文件”一条，另加 P30，两条补跑都抓住）；全量 vitest 1259 passed、2 skipped，pytest 3047 passed、228 skipped（全量在补那条用例之前跑，补的用例随变异的基线跑过）。 | 完成 | 见提交说明 |
| ④b7b | collect 与 collect --recover（④b7 与 themistally-15 商定再拆：b7b collect；b7c run；b7d smoke 与 doctor）。`@themis/dispatcher/collect`：record_candidate、evaluate_scope、attempt_protected_paths、main_repo_changes、decide_report_screen、collect、cmd_collect（_expects_settled 与恢复时补的 run.json）。gitops 补 tree_from_patch、ignored_inventory、main_repo_fingerprint；pi-cli 补 parse_version、MIN_PI_VERSION；status 补 attempt_in_flight、state_in_flight（config 的私有副本改为引用它，config-b 清单的 B02 跟着挪到 status.ts）。决策会话与 summary.md 的 report-screen 清单由 cli 交进来。契约：collect 43 条（三份实现各建相同的仓库、worktree 与证据，在 worktree 里真跑 stub_pi 的剧本，比退出码、两路输出、.agent/runs 下的全部证据与发给决策端点的请求；主工作区的新提交、改已跟踪文件、新增未跟踪文件、只动被忽略文件与中文目录名照 themistally-15 的建议）。变异 52 条（collect 43、gitops 3、pi-cli 3、status 3）：首轮漏 C43（plan.md 的文字没交给事件摘要），补“合同自己两次提到 ambiguous”的契约后补跑抓住；config-b 的 B02 挪到 status.ts 后单独补跑抓住。全量 vitest 1302 passed、2 skipped，pytest 3047 passed、228 skipped（补那条契约之前跑；补的契约随变异的基线跑过），tsc 通过。 | 完成 | 见提交说明 |
| ④b7c1 | run 之前的几步（④b7c 与 themistally-15 商定再拆：b7c1 用探针逐字比的部件；b7c2 cmd_run 整条路径与带 runtime 的 resolve_pi_command）。`@themis/dispatcher/instruction`：INSTRUCTION_TEMPLATE、render_instruction、setup_facts_text、self_check_command、machine_summary、measured_check_seconds（Path.glob 照 Python 3.12 逐级匹配，Windows 上不分大小写）。`@themis/dispatcher/preflight`：pi_agent_dir、context_evidence、pi_preflight（四份输出照 Path.write_text 写成 CRLF）。base 补 shlex.quote。契约 run-pre 10 条（探针逐字比；预检用 fake-cli 的假 pi，三套实现各写各的 preflight/ 再逐字节比；PI_CODING_AGENT_DIR 一律指向临时目录）。变异 73 条（instruction 34、preflight 35、shlex.quote 4）：首轮 72 条漏 F14（pi-help.txt 写之前的 strip_ansi；redact_secrets 里面还会再去一遍，但 strip_ansi 不幂等，去掉中间一段会拼出新的色码），补嵌套色码的预检情形，另加 F35（list-models.txt 同一处），两条补跑都抓住。全量 vitest 1313 passed、2 skipped，pytest 3047 passed、228 skipped（补情形之前跑；补的情形随变异的基线跑过），tsc 通过。 | 完成 | 见提交说明 |
| ④b7c2 | run 整条路径。`@themis/dispatcher/run`：cmd_run（状态与领取的检查、G0：verify_inputs、planner-v2 发布门禁、worktree 在基线上且干净；按冻结合同的类别解析执行模型；pi 的命令照 PI_DISPATCH_PI_CMD、按角色时本机文件里 runtime 的命令（cli 把 kit_roles.local_command 交进来）、PATH 的次序；预检与上下文取证；任务锁里重新核算预算、预留时限、领取；执行说明与运行前的证据；附件放在中性的临时目录；领取后启动前出错补 run.json 记 INFRA_FAILURE；runSupervised；collect）。base/pyio 的映射表补 EEXIST（open 的 x 模式撞上已有文件报 FileExistsError [Errno 17]），pyos 加 isFileExists。顺带改了 themistally-15 复核 ④b7c1 查出的三处（预检取 context_files 用 get、执行说明的 tools 照 join 崩、machine_summary 先取期望退出码），另有五处被合同校验挡住的类型差异记为已知差异（检查项的 id 或 expect_on_base 是列表、self_check 的 env 是列表、tools 里混了列表、authorization.executor 是字符串、检查项是列表）。契约 run 30 条（每个场景先用 Python 的 prepare 建 attempt，三边各跑 run；pi 是 stub_pi，PI_CODING_AGENT_DIR 指向临时目录）。变异 39 条（run 36、run-pre 3）首轮全部抓住。全量 vitest 1342 passed（另 1 条是只读命令 S08 的墙钟容差，与本片无关，随后的提交修）、pytest 3047 passed。 | 完成 | 见提交说明 |
| ④b7c2 复核修正 | themistally-15 复核 c3769a6 查出的两处“文件已存在”差异与一处测试缺口。evidence.ts 加 writeText（照 Python 的 write_text 报 OSError 子类），run、events、summary 改用它；events.jsonl 与 stderr.log 照 Python 的 open “xb” 在启动之前依次独占建出，撞上就崩、状态停在 RUNNING；kill_grace_seconds 在 try 之前求值。契约 run 加 5 条（wrap_pi.py 在预检时建目录，走到任务锁里的第二次核算与领取撞车；三个文件已存在）。6 条首轮全部抓住。单独跑过契约 run（35 条）、collect、events、mutation-specs 与 source-hygiene，tsc 通过；复核方的实机脚本正在跑，全量放到合入之后的 owner sweep。 | 完成 | 见提交说明 |
| ④b7d | doctor 与 smoke。`@themis/dispatcher/doctor`：cmd_doctor（本机事实、pi 的版本与参数、pi_model_readiness、仓库、planner_file_notes、Git 身份、上下文取证、kit 的布局与安装记录）；`@themis/config/doctor-decisions`：_doctor_decisions 与 describe_decisions（cli 交给 cmdDoctor）；`@themis/dispatcher/smoke`：cmd_smoke。Python 的 _decisions_module 改接 ImportError（codekit 在、decisions.py 不在时原来崩溃，现在记 module_missing）。契约 doctor 42 条、smoke 25 条。变异 81 条（doctor 59、smoke 22，按区域拆成 5 份，每份用 -t 只跑相关场景）：首轮漏 3 条，补契约后重跑都抓住。D19 不带上下文取证的提示：原来没有场景带 warning，~/.pi/agent 那条加了全局 SYSTEM.md。S12、S13：长回复里的凭据写成 token=…，脱敏吃掉后面整段，截多少都一样，改成裸的 sk- 令牌。全量 vitest 1415 passed、pytest 3048 passed。 | 完成 | 见提交说明 |
| ④b8a | branch 与 review-draft（④b8 拆成两片：b8a branch 与 review-draft；b8b integrate）。`@themis/dispatcher/branch`：cmd_branch、_branch_trailers、_candidate_commit（导出给 integrate；尾注规则由 cli 从 config 交进来）；gates 加 require_authorized_action；`@themis/dispatcher/review-draft`：cmd_review_draft、_cell、_summary_section、_mutation_review_lines、_interpretation_clue_lines。契约 46 条（提交身份与时间固定，候选提交的 SHA 三边相同）。变异 65 条（branch 27，含 gates 的 2 条；review-draft 38），各用 -t 只跑自己的场景：首轮漏 1 条（R05 单元格多留一个码点：长目的 700 个码点，截不截都一样），补了一条恰好 401 个码点的 DoD 文字后重跑抓住。全量 vitest 1461 passed、pytest 3048 passed。 | 完成 | 见提交说明 |
| ④b8b | integrate（验证后落地）。`@themis/dispatcher/integrate`：cmd_integrate、_running_attempts、_merge_preview、_commit_message_bytes、_fresh_check_reuse（复用 branch 的 _candidate_commit 与尾注规则）。契约 46 条（提交身份与时间固定，落地提交的 SHA 三边相同；验证期间末端变了、快进被拒都在检查里动主工作区造出来）。变异 44 条（跑整个 integrate 契约）：首轮漏 3 条（I01 发布门禁、I02 G0、I12 Git 身份：契约原来没有这三种情形），补 3 条契约后重跑都抓住。第一次重活在全量阶段被内存不足打断，按站主的意思拆开重跑：全量 vitest（1 到 4 个 worker）1507 passed、pytest 3048 passed。 | 完成 | 见提交说明 |
| ④-切换 a | 启动器把调度器命令转交给 TS（选择文件仍是 python）。`TS_DISPATCHER_COMMANDS` 23 条、`dispatcher_handoff`（context：kit_root、kernel_impl、platform、python、machine）、main 与 `argv_impl` 接上、pyargs Schema 补 23 个条目；契约加第四个 runner launcher（选择文件的 dispatcher 为 ts，经真的启动器）。全量 vitest 1507 通过（launcher 一边全过），pytest 3076 通过；变异 launcher-switch-a 10 条全部抓住。 | 完成 | 见提交说明 |
| ④-切换 b | 启动器转发 Ctrl+C 与 CTRL_BREAK（D2：`_forward_interrupts`，等待改成带超时的轮询），运行时注入变量换名交给 TS、入口 `@themis/base/parent-env` 照 `THEMIS_PARENT_NAMES` 还原（D3）；常量表逐项对照；中断契约改回四种 runner，run 加 D2 端到端与 D3。全量 vitest 1516 通过，pytest 3085 通过（另 2 个因改了钉字节的 stub_pi 而红，已退回、单跑通过），全部门禁基准 733 通过；变异 22 条全部抓住。 | 完成 | 见提交说明 |
| ④-切换 c1 | 实测全量 pytest 一条调度器命令都不经 TS，对等性只靠契约；补安全两类：新契约 secret-config（疑似凭据配置下每条调度器命令，令牌不出现在输出、.agent、工作树与提交说明里），prepare、run 补按角色绑定的 K7、K8、K10、K11、K14、K14b、K16、K17，K4 同时起步的压力，publishBindingRecord 被抢先的单测；修一条不稳的测试。全量 vitest 1561、pytest 3086 通过，复核后改过的文件单跑通过；变异 11 条全部抓住。 | 完成 | 见提交说明 |
| ④-切换 c2 | 新契约 chain：“Python 开跑、TS 收尾”两条链（Python prepare 之后各 runner 做到 INTEGRATED；Python 的 run 被硬杀，各 runner 的 collect --recover 收尾），每一步之后用 hub 在进程内调的 get_state、budget_usage、_running_attempts、_CHECK_LINE_RE 读 TS 写的证据；secret-config 的 collect 单列（读不了配置就失败收尾）。全量 vitest 1572 通过；变异 2 条全部抓住。 | 完成 | 见提交说明 |
| ④-切换 c3a | 按覆盖审计补命令层面的缺口：新契约 repo-arg（--repo 不对，8 条调度器命令），wait 四条（state 是数组、PREPARED 宽限、没有 git、CTRL_BREAK），validate 四条与写坏的 commit_trailers，doctor 两条（no_models、no_match），sync-adapters 三条（链接），run 四条（meta 损坏、批处理包装、新建符号链接）。全量 vitest 1609 通过；变异 7 条全部抓住。 | 完成 | 见提交说明 |
| ④-切换 c3b | 按覆盖审计补其余缺口：chain 加 core.autocrlf=true 与 K13 两条链，prepare 加 K12③ 三条，run 加领取之前的 CTRL_BREAK 与运行期间问题清单漂移，doctor 与 mutate 的凭据只在文件凭据库里；第 10 节记 K5 的触发方式。全量 vitest 1618 通过，改过的两个文件单跑通过；变异 5 条抓住，3 条照实测标为等价。 | 完成 | 见提交说明 |
| ④-切换 d | 选择文件 `scripts/kernel-impl.json` 的 `dispatcher` 改成 `ts`（r3 §10 第 129 轮）。翻之前 themistally-15 在 211c34d 的临时克隆里过了全量关：72 步，dispatcher 为 python 与 ts 经真启动器逐字节一致，崩溃 0、泄露 0；最近的真实 attempt（t023）上的影子运行两边一致。hub 仍是 Python。不回退（用户 2026-10-28）。耗时：每条调度器命令经 TS 多 0.6 到 1.0 秒，release-check 3.80 → 8.33 秒（main.ts 加载 0.55 秒、pyregex 在模块加载时编译），下一片（紧接验收片、第 ⑤ 步之前）做启动开销，目标与计时见第 9 节。doctor-smoke 的 kit 拷贝不再带选择文件。全量 vitest 时查出 `CreateProcessW` 失败偶尔取到错误码 0（与翻转无关），验收片之前单独一片修。 | 完成 | 见提交说明 |
| ④-切换 e | `@themis/base/native` 的 `retryWin32`：Win32 调用失败却取到错误码 0 时重做（r3 §10 第 130 轮）。切换 d 的全量 vitest 时偶发查出：roles-probe 的 runtime scan，Python 报 `[WinError 216]`，TS 报 `[WinError 0]`。native.ts 里读 GetLastError 的 13 处全部经它取（fail() 的七处、SetInformationJobObject、ctrlBreak、MoveFileExW 与 CreateDirectoryW、statPath 的两段、GetFinalPathNameByHandleW）。变异 8 条抓住；全量 pytest 3086、门禁基准 733、全量 vitest 1627 都通过。 | 完成 | 见提交说明 |
| ④ 验收片 | T024（桌面端前端：需要填表单的写入口，D2 之六）在 `dispatcher: ts`、hub 仍是 Python 下完整走完并落地。从登记到落地 19 次调度器调用全是 ts（derive-json 3、validate 3、baseline、prepare 2、run 2、check 2、mutate 2、mark、verdict、integrate、cleanup），hub 读 TS 写的证据没有出错。attempt-001 是执行模型在一条回复里想了 6.4 万个 token、撞上输出上限被截断，一个文件都没写；内核把合同升到 v2 重派，attempt-002 过了检查并落地。themistally-15 独立验收复审通过。第 ④ 步的出口条件至此全部满足 | 完成 | c381566、514e836 |
| ④-启动开销 | r3 §10 第 131 轮。剖析下来大头不在模块加载次序：①sre 移植编译 IGNORECASE 字面量时，每次都把约 1400 个“小写会变的码点”现排一遍（只算一次、线性归并、按“码点加是否 Unicode”缓存字面量集合），34 个固定模式的编译 336 → 30 毫秒，main.ts 光加载 0.55 → 0.17 秒；②release-check 每个文件都无条件算 Python 式小写（拒绝清单为空就不算；withPythonUnicode 没有未分配码点就直接交给 JS；globRegex 按模式缓存）。命令模块的按需加载没做（剩下的固定开销不值得），parent-env 与 harden 的次序不动。计时（第 9 节的固定项，两遍对得上）：validate +0.92 → +0.43~0.46 秒，metrics +0.76 → +0.38~0.40，wait 与 sync-adapters +0.67 → +0.29~0.30，status +0.64 → +0.29，config show +0.56 → +0.21~0.23，release-check 7.5 → 2.05 秒（Python 3.36）。都达到目标 | 完成 | 见提交说明 |
| ⑤a | 新包 `@themis/hub` 的常量、信件、schema 子集校验、主任务状态与守卫（kit_hub.py 1–131、231–329、610–744、923–1306 行，加 stage_status_table 与 upstream_notes）。FIELD_LINE_RE 要分组、pyregex 不记组，照语义手写；任务号与 js_pattern 交给 pyregex（js_pattern 带 FLAG_ASCII，报错逐字一致）；relative_to 用 base 新加的 purePathRelativePosix。探针两边各加 hub.call，Python 侧另加 hub.samples 从 tests/test_kit_hub.py 取参数化的样例。对照 hub-state.compare 13 条：随机状态三个种子各 60 个、随机信件与 schema各两个种子、照搬 pytest 场景四条（守卫按步骤搭状态）。覆盖审计 docs/themis-tally-3.0-ts迁移-hub覆盖.md 的 ⑤a 一节：26 个场景，COVERED 21、PARTIAL 5（其余归 ⑤d、⑤i）。变异 30 条，抓住 27，3 条等价 | 完成 | 见提交说明 |
| ⑤b | 信箱、账本与状态（kit_hub.py 540–565、603–630、751–922、4695–4760 行：canonical_json 与 canonical_state、HubState 与三方合并、keep_previous、letter_main、Hub、DirLock、hold_letters 与 release_held、ledger_events）。`@themis/hub/mailbox`：存状态在 .state.lock 里按主任务、再按顶层键三方合并（同一键以后存的为准，记 state.conflict），工人会话在 .agents.lock 里只写本回合的；投递经 pyPublishNew，不覆盖；DirLock 包 base 的目录锁，占用时的文字照 Python 的 dict repr。探针两边各加 hub.box（在一个信箱上按步骤跑，交回每一步的结果），Python 侧另加 fs.hold_exclusive（GENERIC_READ、dwShareMode=0 独占一个文件）；新加 probes/backup_privilege.py（设好令牌的备份与还原特权再起探针），harness 加 withBackupPrivilege。契约 hub-mailbox 26 条：三套实现跑同一份步骤脚本、比每一步的结果与落盘文件 11 条（B1–B11），混跑 15 条（一套读完停住、另一套在中间存，不同键合并、同一键记冲突；同时投递同一个编号；同时写会话；别的进程独占 state.json 时的读写，备份特权两种状态；Python 拿着文件锁时的写）。查出一处已知差异，记进第 10 节：libuv 打开文件总带备份语义，备份特权启用时 TS 的读绕过别的进程的独占打开与 ACL 的读权限。覆盖审计 ⑤b 一节：10 个场景，COVERED 6、PARTIAL 4（其余归 ⑤g、⑤h、⑤i）。变异 21 条，全部抓住。第一轮 20 条漏掉 5 条（存完不更新读出来时的样子、会话记录不加锁、new 里的信不排序、到点的边界、读不出时不报错），补了 B7 的只有空白的文件、B9 到 B11、C4 的备份特权停用状态与 C5 之后都抓住；另加“三方合并不加锁”一条。全量 pytest 3100 passed / 234 skipped，vitest 1668 passed / 2 skipped。 | 完成 | 见提交说明 |
| ⑤c | 回合审计（kit_hub.py 的 turn_cost_usd、jsonl_lines、stream_events、session_cut_short、claude_session_effort、claude_path_rule、audit_claude_stream、path_forms、pi_reach_problem、guard_config、audit_pi_stream、pi_supported_flags、pi_flags_problem）。`@themis/hub/audit`；hub 加依赖 `@themis/dispatcher`，只引子路径（instruction 的 globPaths，pi-cli 的 runCapture、parseHelp、RESOURCE_FLAGS）；审计用到的常量进 constants.ts，常量对照自动比到。事件是任意的 JSON 值：取键、遍历、集合（不可散列报 TypeError，1、1.0、True 是同一个）、dict()、sorted（照 CPython 的 count_run 与二分插入）都照 Python。开工前查出两处内核问题，第 133 轮先修（path_forms 的次序随散列变；坏行被算成 deliver 读不出参数），同轮照 themistally-15 的建议把门禁基准的全文落盘（站主扫描写 ledger/owner-sweep-pytest.log）。base：normcase 在 Bun 下照 Python 3.12 调 LCMapStringEx（native.ts 加绑定），Node 后备仍用 toLowerCase（第 10 节）。探针两边各加 hub.audit，Python 侧另加 hub.audit_samples（跑 pytest 的审计用例、记下顶层调用）；pypath.call 加 normcase。契约 hub-audit 17 条：pytest 用例记下的 94 次调用三边重放；guard.ts 在 Node 与 Bun 下与 Python、TS 用同一份 guard_config 逐条一致；按种子改坏的 pi 与 claude 事件流各 450 份、随机调用 400 个；手写的边界（花费恰好一半取偶、float 的写法、中文与带 İ、ẞ 的目录、8.3 短名、崩溃的类型、会话文件、假 pi 的 --help）。events 契约加 normcase 一条。信箱里 779 个真实回合的一次性比对（不进提交）：741 个 pi 审计、38 个 claude 审计、779 次 session_cut_short、38 次 claude_session_effort 三边逐字相同。覆盖审计 ⑤c 一节：22 个场景，COVERED 15、PARTIAL 7（其余归 ⑤d、⑤i、⑤j）。变异 37 条，抓住 36，1 条等价。计时：hub 在 Bun 下加载 audit 模块 0.07 秒（mailbox 0.08、constants 0.03）；以 kb3 为内核的调度器计时两遍与 7011943 一致（release-check 1.90～1.92 秒）。全量 pytest 3103 passed / 234 skipped，门禁基准 24 份 753 passed，vitest 1687 passed / 2 skipped。 | 完成 | 见提交说明 |
| ⑤-影子 | 影子运行（第 ⑤ 步“影子运行”一条）。`ts/packages/contracts/tools/hub-shadow.ts`（Bun，套 backup_privilege.py off）：--once 静态重放；--watch 只在 state.json 的哈希或账本长度变了时重算，主任务只算 ts 变了的，信只算新的，回合只算新结束的。快照前后各核一次 state.json 的哈希、账本长度与信件的文件名，不一致就重取，5 次仍不一致记“快照不稳，跳过”。探针不开在用的文件：状态与账本复制进临时的快照仓库，信件与事件流经 fs 读出、按原始字节传，两边各用自己的 read_text 解码；会话文件按会话号复制进临时的 USERPROFILE 与快照仓库。比：状态与账本；每个主任务的只读结论与 guard 的整张表（信件类型 × 收信人 × 主任务号与各阶段号，约 1800 种，另加不存在的主任务）；每封信的读出、解析、往返、形状校验；写给协调人的信的内核代办与任务书；每次 route.kernel 重算的下一步（两边一致，并且与账本记的相同，partial 时是前缀）；已结束回合的审计、半截会话与生效档位；--watch 时新出现的 letter.rejected 用上一份与这一份快照各算一次 guard，都对不上记“时序”。结果写 .agent/runs/_shadow/latest.json（--once 与有差异的那几轮另存一份），只写数量、对不上的键（主任务号、信的文件名、回合号、账本行号）、快照的哈希，以及每类两边探针进程与影子自己的峰值内存。--watch 察觉到变化后等指纹连着两次相同再取快照；回合按事件流的字节数每 10 MB 一批。探针两边各加 hub.shadow_task、hub.shadow_letter、hub.shadow_routine、hub.shadow_route，批量回复带 peak_bytes。契约 hub-shadow 7 条：临时信箱上 --once 零差异、各类都比到（guard 的组合数、一次 partial 的 route.kernel、没写 result.json 的回合不审）；两边真有差异时报得出来（第 10 节的已知差异：嵌套 1500 层的一行，只在那个回合的审计上报一处）；账本记的下一步被改过时只报一处；取快照时被改一次就重取、次次被改就跳过（测试钩子 THEMIS_SHADOW_PAUSE）；--watch 第二轮只重算状态变了的主任务，拒信的原因只在上一份快照上对得上也算一致；status --json、metrics、decisions replay --json 在带 _shadow 的仓库里 Python 与经启动器的 TS 相同、不提 _shadow。prepare 与 integrate 两份契约的仓库也放了 _shadow（pending_attempt_notes、_running_attempts 两处；cleanup 只处理给定的 attempt，不列 runs）。变异 ts/mutations/hub-shadow.ts.json 13 个全部抓住（第一轮只抓住 7 个，契约补了六处漏洞：两边真有差异的阳性对照、guard 组合数、partial、上一份快照的拒信、没结束的回合、--watch 重算几个主任务）。验收：主仓库 f2bdab9 时的信箱上静态重放（--once，写在主仓库的 .agent/runs/_shadow/）零差异：快照一次取到；状态 1、主任务 25（guard 组合 45000 种）、信件 1188、代办 576、route.kernel 61（与账本记的 61 次一致）、回合 1596，约 5 分钟。峰值内存：影子 919 MB；探针在回合那一类最高，Python 268 MB、TS 1225 MB，其余各类两边都在 300 MB 以内。TS 的大头不在探针：直接调 auditPiStream 审最大那条 30 MB 的流也到 1092 MB（Python 280 MB），是 streamEvents 留着整个事件数组（Map 与 BigInt），逐行解析完就丢只有 209 MB；改成边读边审列进 ⑤d，放在 ⑤ 切换验收之前。并进这一片的 ⑤c 复核后补：audit.ts 的工具名映射改用自有属性判断；第 10 节“嵌套很深的值”“审计里的 sorted”两行改准；⑤c 的进度行挪回第 11 节。全量 vitest 118 个文件 1694 条过、2 条跳过；Python 一侧只改了契约探针，全量 pytest 与门禁基准留给合入后的站主扫描。 | 完成 | 见提交说明 |
| ⑤-影子 复核后补 | themistally-15 复核 d1eff67 提的两条与由此查出的两处。（1）计划要求的“新回合的事件流用 TS 审计重算，与 Python 写下的 result.json 比”起初漏了：--watch 有了上一份成功的快照之后，新结束的回合把 TS 的审计按 run_turn 的写法折成 result.json 的字段（models、tool_calls、violations、warnings、usage、terminal、thinking_chars、thinking_tokens、deliver_refusals 的条数与总长、effort_effective）逐个比，对不上的单列“回合与 result.json”，键只写字段名；api_error、output_error 会被 blocked、interface_problem、delivered_output 改写，归 ⑤d。只比 hub_sha256 等于影子这棵树里 kit_hub.py 哈希的（HUB_SHA256 在 hub 启动时定下，历史回合跨了 80 个版本），别的记 result_json_other_kernel；claude 的生效档位取会话文件里最后一个 effort，会话文件比 result.json 新时对不上记“时序”。Comparison.run 改为交回 TS 的结果。（2）影子审回合的输入照 run_turn：工具表加上交差工具（pi 的 deliver、claude 的 StructuredOutput；原来按名册原样，真实回合里调用 deliver 会被算成白名单之外），事件流按 readText 加 jsonlLines 的通用换行读（原来按 LF 切）。两边探针拿到的输入相同，这两处只有与 result.json 比时才看得出。（3）--watch 每轮接住异常接着跑：只记错误类型（Error 的 name 与 fs 的 code，不记消息），出错与快照不稳的那一轮都不更新上一份、下一轮重试；latest.json 带 watch 的开始时刻、轮数、出错数与最后一轮的时刻，同一串错误只另存第一份；--once 出错退出码 2。契约 hub-shadow 加两条（共 9 条）：第二轮新结束的三个回合，一个由 Python 照 run_turn 写下 result.json（事件流调用 deliver、有单独的 CR 分行）须一致，一个 violations 被改过须报出，一个是别的内核写的只计数；第一轮碰上写了一半的 result.json 出错、第二轮整份补比。验收：主仓库 d1eff67 时的信箱上静态重放（新的审计输入）零差异：快照一次取到；主任务 25 项（24 个主任务加不存在的 T999，guard 组合 45000 种）、信件 1188、代办 576、route.kernel 61（与账本记的一致）、回合 1596 项（779 个回合的审计与半截会话各 779 项、claude 回合的生效档位 38 项）。“回合与 result.json”只在 --watch 时比；主仓库的 hub 从 10-26 起暂停，现有 779 个回合没有一个是当前这版 kit_hub 写的，这一类要到付费任务全程比对时才第一次在真实数据上跑。契约 9 条全过，变异 21 个全部抓住。 | 完成 | 见提交说明 |
| ⑤d0 | ⑤d 的第一个提交，两项待办。（1）审计边读边审：⑤-影子量出最大那条 30 MB 的事件流（92860 行），TS 直接调 auditPiStream 峰值 1092 MB（Python 280 MB），大头是 streamEvents 留着整个事件数组（base 的 loads 解析成 Map 与 BigInt 留着 956 MB，逐行丢掉 209 MB）；hub 的 runner 并行，几个大回合撞上就是几个 GB。audit.ts 加生成器 eachEvent，读不出的行数记进计数器；两个审计函数、sessionCutShort、claudeSessionEffort 四处都改用它，审计在循环之后把读不出的那条 unshift 到 violations 最前面（循环之前 violations 都是空的，循环里只往后加，次序与 Python 相同）；sessionCutShort 只留最后一条匹配，claudeSessionEffort 只留最后一个 effort。streamEvents 保留（在 eachEvent 上组装），探针拿它对照 stream_events。之后：30 MB 那条 294–298 MB；最大的 claude 会话（7.9 MB）取档位 126 MB、判半截 138 MB；最大的 pi 会话（2.9 MB）判半截 107 MB。（2）影子把生效档位对不上记成“时序”只限 claude（themistally-15 复核 5bb77b7 提出）：pi 的档位来自事件流，会话文件续接时变新与它无关；契约多一个这样的 pi 回合须记进“回合与 result.json”。⑤c 的契约与变异照旧（37 个抓住 36，C25 等价；C08 的锚点随写法换了），影子契约 9 条、变异 22 个全部抓住 | 完成 | 见提交说明 |
| ⑤d1 | 提示词与交差核对（kit_hub.py 的 render_template、role_prompt、engineering_rules、transitional_section、external_facts_section、input_path、turn_prompt、letter_from_output、role_schema、delivered_output、interface_problem、delivery_problem、worker_file_problem、DELIVERY_SHA256、worker_env，加上 turn_prompt 合同端那一段要用、提前移植给 ⑤e 复用的 regression_gates、next_contract_version、budget_usage）。新模块 kernel.ts（内核目录照 Path(__file__).resolve() 解析到真实路径；照 kit_hub 原样调用的 git()：不加 core.quotepath=off，ls-tree 列出的非 ASCII 文件名照 Git 缺省加引号）、delivery.ts、prompt.ts；常量（OUTPUT_SPECS、ROLE_EXTRA_OUTPUT、GATE_PITFALLS 等）由脚本从 kit_hub 取值生成，hub.constants 的对照逐项再比。E6：FRONTEND_TRANSITIONAL_RE 按三种引号展开成三支交给 pyregex，分支里“不是开引号”的点号写成“不是这个引号、也不是换行”，标题从整段匹配里取；TRANSITIONAL_RE 的用例名与说明行同样从整段匹配里取。rglob 照 Python 3.12 的 Path.walk(follow_symlinks=False) 不进符号链接（联接 Python 当目录走、lstat 当链接，测试目录里不会有）。读模板目录、内核仓库的两个函数带一个缺省取内核目录的参数，契约两边设同一个值。契约 hub-prompt：pytest 采样重放（采样照 pytest 先搭 autouse 夹具与 engine_env）、手写的对照（全部岗位的角色提示词、临时模板目录、空模板与正被替换的模板、四种内核仓库、worker_env 只比名字）、生成的过渡断言、三个种子的随机回合输入（随机主任务状态的生成器从 hub-state.compare 原样搬进 hub-fixtures.ts，⑤a 的对照照旧全过）、回合输入的小件、交差核对与信。影子加“提示词”一类（themistally-15 提出）：全部 pi、claude 岗位的 role_prompt，各主任务协调人与不是 idle 的阶段的 turn_prompt；任务书、state.md、合同任务的 runs 证据由影子经 fs 复制进快照仓库，快照仓库的 .git 指向主仓库的 git 目录。探针加 hub.prompt；TS 探针按 errno 交回 Python 的 OSError 子类名。⑤d0 复核后补：audit.ts 里 const expected 后面吃掉的空格。变异 ts/mutations/hub-d1.ts.json 37 个全部抓住（第一轮漏 2 个：模板只重读一次——“正被替换”那条靠时序碰运气，改成探针调用前写标记、写入的进程等标记再过 0.3 秒；说明行只认 r、R 前缀——后面的去引号顺手去掉了多留下的引号，加了以空白加引号开头的说明）；影子的变异加 S23，23 个全部抓住。全量 vitest 119 个文件 1711 passed / 2 skipped（加“当时的结果”核对之前跑的；之后 ⑤c、⑤d1、影子三份契约 41 条重跑全过）。 | 完成 | 见提交说明 |
| ⑤d2 | 输入目录与 TurnRunner（kit_hub.py 的 worktree_root、input_sources、_input_files、stage_inputs、remove_inputs、TurnRunner.run）。新模块 inputs.ts、turn.ts：run() 是 async，launcher 的形状照 pd.run_supervised（缺省经 base 的 runSupervised）；stream.jsonl 与 stderr.log 照 Python 的 xb 先建好；不确定的几样（回合号用的时刻与两字节随机数、claude 的 uuid4、限流退避的当前秒数）由构造参数注入、缺省取真的；stageInputs 的 options（worktree 根目录与文件上限）只给契约的采样重放用。kernel.ts 加 HUB_SHA256（kit_hub.py 的 sha256；切换之后它该指什么，归 ⑤j 或切换再定）；constants.ts 加限流的三个数。契约 hub-turn：手写的 pi 与 claude 场景、名册与交差文件换过的场景（两边设同一个覆盖值）、真的来源的形状核对、claude 的路径（同一目录里 .cmd、.exe、没扩展名并存）、只读输入目录、pytest 采样重放（TurnRunner.run 与 stage_inputs；快照还原回原位置，链接与联接照记下的重建，覆盖值照调用当时记下的，假 pi；先核对 Python 重放与当时的结果，全部对上）。探针两边加 hub.inputs、hub.turn（env、roster、delivery_sha256、restore、worktree_root、input_file_limit 几个参数只给契约用）。影子：加“回合与 role.md”；与 result.json 比的几个回合改由当前内核真的 TurnRunner.run 写出（待办第 9 项）。待办第 3 项（piSupportedFlags 缓存进行中的 Promise）与第 11 项（turnPrompt 头部的路径照 str(Path)、git() 的 cwd 不存在时抛 NotADirectoryError、inputPath 用 SEP、第 10 节与覆盖审计各一处）随这一片。变异：hub-d2.ts.json 34 个全部抓住（turn.ts 24 个、inputs.ts 10 个）；hub-shadow.ts.json 加 S24，24 个里 23 个第一轮抓住，S22 漏过一次，把会话文件的时刻错开后单独重跑抓住。全量 vitest：120 个文件，1719 过、2 跳过。 | 完成 | 见提交说明 |
| ⑤e0 | ⑤e 的第一个提交，带上复核与付费全程比对时记下的待办。（1）影子：--once 加 --records-since <ISO 时刻>，result.json 的 finished_at 不早于它、同一内核写下的回合也与 result.json、role.md 比（补比付费全程比对 watch 那一段，计数没留下的几轮靠它）；--watch 每轮往标准输出写一行数量，latest.json 的 watch 段带每类累计比过几个、对不上几个与 result_json_other_kernel 的累计。（2）另存快照里的会话文件（修改时刻照原文件）与拒信时序的重放有契约管着；影子的说明写上重放的限度与“回合与 role.md”的时序情形（模板或 AGENTS.md 改了、kit_hub.py 没改）。（3）turn.ts 的 blocked 照 Python 的 or 与真值判断写；inputs.ts 的 contract_task 用 pyTruthy；探针的 hub.turn 在调用期间设 USERPROFILE、HOME，调用完还原（两边）。（4）piSupportedFlags 的 TS 测试（对等契约看不到）：并发只起一次 pi、非零退出缓存成 null、探的时候抛了异常不留缓存。变异：hub-c 加 C38、C39（39 个抓住 38，漏掉的 C25 是早已记下的等价变异）；hub-shadow 加 S34–S41，S16、S20 的锚点随改动更新（加 S41 之前的树上 40 个全部抓住；补上“读不出结束时刻的回合计数”之后，S16、S20、S34–S41 这 10 个重跑也全部抓住）。hub-d2 的 T13 锚点随 blocked 改用 || 更新（单独重跑抓住）。全量 vitest：1725 passed、1 failed、2 skipped（120 个文件），失败的那条是 mutation-specs 查出 T13 的锚点没跟着改，改正后单独重跑通过。 | 完成 | 见提交说明 |
| ⑤e1a | 合同与战前门禁里纯文字的部分（⑤e1 拆成 a、b，themistally-15 同意）：kit_hub.py 的 tail、tail_file、normalize_identity、normalize_markup、strip_decisions、decisions_section、unparsed_check_ids、external_fact_problems、unverified_facts、pytest_outcomes（⑤f 的，hollow_baseline_problems 要用，提前移植）。新模块 @themis/hub/contract，探针加 hub.contract。契约 hub-contract：80 条用例的记下的调用三边重放（tail 去重，每个函数都要有比得上当时结果的样本；DRIFTED 2 条，都是 tail_file 读的日志后来删了），手写的对照与按种子生成的合同文字。采样器照 pytest 截下用例的输出。argv_impl、read_kernel_impl 挪到 ⑤e1b（报错要逐字对上 Python 的 JSON 解析与 OSError 原文，离 ⑤e2 的 run_pd 也近）。变异 ts/mutations/hub-e1a.ts.json 31 条：第一轮 30 条抓住 29 条，漏掉的 E08（括号说明里允许嵌套）是因为用例里只有配平的嵌套括号，两种写法都匹配不上，补了一行括号没配平的 Scope 项之后单独重跑抓住。themistally-15 复核后：E12 原先靠崩溃抓住，换成语义上的“Scope 一节不在下一个标题处结束”；补 E31（单数的 warning 不改成复数，手写日志补一行 1 warning）；读文件改用 base 的 pyOSErrorOf、PyOSError 与 pyReadTextReplace，E03、E04 换锚点，E27 改打在 pyio.ts 的 pyReadTextReplace 上；这 5 条重跑都抓住。全量 vitest：第一次采样那条的 Python 探针在全量并行下超过 runProbe 缺省的 60 秒（单独跑约 40 秒），runProbe 加了可选的时限、采样给 10 分钟；第二次 1738 passed、1 failed、2 skipped，失败的是 config-write 的锁互斥契约（第 10.1 节记过的同一种，这一片没碰配置），单独重跑 3 遍都过。 | 完成 | 见提交说明 |
| ⑤e1b | 合同与战前门禁里要读仓库、账本与信箱的部分：kit_hub.py 的 contract_paths、scope_missing_prefix、contract_requirements、dod_coverage_problems、budget_problems、answers_question（@themis/hub/contract），pi_dispatch.py 的 read_kernel_impl、argv_impl 与四张转交名单的键（新模块 @themis/dispatcher/kernel-impl：TS 调度器拿的是启动器交来的 kernelImpl，TS 的 hub 要自己读，路径由调用方给；argv_impl 照 Python 在 -h 与只有 TS 实现的命令判定之后才读）。base 的 PY_BUILDER 导出，选择文件查重复键在它上面换掉 object。探针：hub.audit 的 home 只在调用期间设（待办第 23 项）；hub.contract 的 tail_file 显式给的 null 照传（第 24 项）。契约 hub-contract-repo：44 条用例的记下的调用三边重放（DRIFTED 7 条，⑤e2 有了带 .git 的快照之后拿掉）、临时仓库上的手写对照、选择文件的坏法与判定次序、按种子生成的命令行；hub-audit 加一条 home 不沿用。变异 ts/mutations/hub-e1b.ts.json 38 条全部抓住（contract.ts 的 ⑤e1b 部分 24 条、kernel-impl.ts 14 条：K14 是复核后补的“只有 TS 实现的命令先于 -h 判定”）；hub-c 加 C40（hub.audit 的 home 不还原），抓住。全量 vitest：1753 passed、2 skipped（122 个文件）。 | 完成 | 见提交说明 |
| ⑤e2a | 内核调调度器，战前门禁里读工作区与基线记录的部分（⑤e2 拆成 a、b，themistally-15 同意）：kit_hub.py 的 workspace_status（@themis/hub/kernel，照抄 -z 改名项的毛病，第 10.1 节）、contract_digest、hollow_baseline_problems（@themis/hub/contract），run_pd、kernel_env、kernel_pytest_env、KERNEL_PYTEST（新模块 @themis/hub/runpd：Python 解释器由入口设定，没设就报错；kernel_env 照 dict(os.environ)，用调度器 pi-cli 导出的 pyEnviron；标准错误并进标准输出的同一个临时文件；经 runSupervised 用 Job 结束整棵树，超时按时交回 124、不记账本，第 10 节；账本的 impl 读内核目录下的选择文件，待办第 26 项）。采样器加调用当时的快照（带 .git，仓库外的 worktree 连主仓库一起），三边重放前原地放回；hub-contract-repo 读仓库的五个函数也改用它，⑤e1b 的 DRIFTED 7 条拿掉（待办第 25 项）。契约 hub-contract-gate：24 条用例的 100 次调用三边重放，每一次都与当时的结果相同；临时仓库上的手写对照（git status 的各种状态、合同两个文件、基线检查记录的每个分支）；真调度器上的 run_pd 与内核的几份环境。变异 ts/mutations/hub-e2a.ts.json 31 条：第一轮 29 条抓住 27 条；漏掉的 R03（mutate 起的命令本来就带 PYTHONDONTWRITEBYTECODE，只比名字看不出来）与 H10（超时那几条的退出码沿用了 1）补了用例（探针另交这个变量的值、契约先设成 0；退出码改成真实记录里的 null）之后单独重跑都抓住。复核后（themistally-15）kernel_env 改照 dict(os.environ)，R02（去 key 时分大小写）在 Windows 上成了等价变异，标 equivalent；补 R13（缺省的选择文件读 hub 仓库下的）与 R14（名字不照 os.environ 转大写）；H05 改由真的浮点退出码抓。这几条重跑：R01、R13、R14、H05 抓住，R02 记作预期内的等价。全量 vitest：复核后重跑 1762 passed、2 skipped（123 个文件）；复核前那一遍红过一条 locks.contract 的并发写配置（第 10.1 节已记的偶发，第 11 个写进程退出码 1），单独重跑 3 遍都过。 | 完成 | 见提交说明 |
| ⑤e2b | 合同与战前门禁里改状态的部分：kit_hub.py 的 sync_executor_line、revalidate_contract、accept_contract、bump_contract_version、set_contract_base、accept_gate_pre（新模块 @themis/hub/accept；用例当时换掉的 run_pd、contract_requirements、budget_problems、revalidate_contract 经可选的末位参数 deps 注入，真的 revalidate 里也走传进来的 deps，生产调用方不传；accept_gate_pre 的 --collect-only 经 runSupervised）。base 的 clock 加 withPinnedClock（只给契约用）。探针：采样器的 flow_recorder 与两边的 hub.contract_flow（设计稿第 8 节）。契约 hub-contract-flow：23 条用例的 76 次调用照调用当时三边重放，交回值、ts、两棵树的文件、账本、git 状态都与当时的结果相同；手写的对照（真调度器的门禁基准测试、KERNEL_PYTEST 的缓存、样本没走到的分支、注入核对）。变异 ts/mutations/hub-e2b.ts.json 49 条全部抓住：第一轮 47 条抓住 44 条，漏掉的 A01（缺“只有空白”的用例）、G09（用例里 baseline 的输出都不到 20 行）补了用例；G12 起初当成等价，themistally-15 复核时指出用例换上的假 revalidate 不碰合同哈希，补了 baseline 那次改合同 JSON 的场景；复核后另加 S02（base_sha 的行尾空白不跨行）与 W01（合同照 Node 的写法写，孤立代理项悄悄换成 U+FFFD）；改完整份重跑。全量 vitest：1770 passed、2 skipped（124 个文件）。 | 完成 | 见提交说明 |
| ⑤f | 战后门禁与变异：kit_hub.py 的 attempt_base、apply_candidate、ensure_worktree、add_worktree、seed_whitebox、accept_gate_post、mutant_timeout、TEST_FILE_RE、unmutated_problems、gate_spec、unchanged_mismatches、run_mutations、expected_missed_everywhere、candidate_defects、defect_matches、defect_match_problems、mutation_problems（新模块 @themis/hub/gatepost；用例当时换掉的 run_pd、worktree_root，与白盒测试那一次 run_supervised、建 worktree 的 mkdtemp 经可选的末位参数 deps 注入，生产调用方不传；模型交来的值可以是任何 JSON 值，取键、迭代、集合、排序、乘加的语义与报错的类型、文字都照 Python）。base：pyset（hashKey、PySet、PyKeyedDict、pySorted 等从 audit.ts 挪出）；pyjson 的 RecursionError 照 C scanner 分对象、数组（第 10 节那行改记）；fsutil 的 writeTextAtomic 最后失败时照 os.replace 报 [WinError 32、5]；supervise 加 pyWinErrorMessage，kernel.ts、turn.ts 与调度器三处写死的报错改用它；taskstate 的 relativeTo 照 CPython 的文字，accept.ts 的那份并掉。探针：flow 的注入名单加 worktree_root、run_supervised（环境两边各自与 kernel_pytest_env() 比，值不进记录）、mkdtemp（建出的目录重放前先删）；所有异常都交回 str(exc)，⑤a 的 hub.call 与影子同样（一改就查出 relative_to 的文字不同）。契约 hub-gatepost：41 条用例的 155 次调用（改状态的五个函数 48 次）照调用当时三边重放，都与当时的结果相同；hub-gatepost-scenes 16 组手写场景（白盒测试的十一种结果、run_mutations 的时限、清单、锚点、记录、unmutated，纯函数的边界，按种子随机换类型的 1120 次调用，真 git 的三个函数，add_worktree 真失败三次，真跑白盒 pytest 与 mutate）；hub-gatepost-lock：别的进程拿着 .git-worktrees.lock 70 秒，三边都等满 60 秒、超时一次、再试时建成。pybase-config 加 sorted、Windows 错误文字、os.replace 文字的对照；attempt-commands、repo-commands 的 WinError 267 带文字比；hub-audit 的占位收窄到流里确实有不是字符串的模型名的请求。变异：hub-f.ts.json 60 条第一轮抓住 59 条，漏掉的 P57（没列的红用例只列前 10 条）补了 12 条都没列的场景之后单独重跑抓住；base-f.ts.json 5 条全部抓住；hub-c 的 C32、C33 随 pyset 挪锚点，locks 的 F02、F03 随 readText 挪锚点，都抓住；复核后（themistally-15 抽查 17 条，漏掉的是它自己设计的 X03–X05）补了三组手写场景：mutate 的 30 行输出（mutate_tail 与“没有跑完”都只附 25 行）、expect_missed 有两项以上又没列满、锚点对不上的条目名字不是字符串；并进 P61–P64，单独重跑都抓住。全量 vitest：1795 passed、2 skipped（127 个文件）；typecheck 通过。 | 完成 | 见提交说明 |
| ⑤g1 | 执行端代办里只读与纯文字的部分（⑤g 拆成 g1、g2，themistally-15 同意）：kit_hub.py 的 ATTEMPT_IN_FLIGHT、ATTEMPT_CONCLUDED、interrupted_attempt、attempts_left、rework_source、latest_checks、cut_off、rework_commits、carryable、checks_passed、unfinished_why、carry_back、carry_source、returned_blockers、add_modified_files、failed_attempt、retry_section、failed_checks_brief、failure_lines、report_leftovers、rework_section、gate_claims、unreported_gate_claims、jev_flag，以及 start_rework 要用的 empty_commit（⑤h 的，提前移植）。新模块 @themis/hub/exec；runs.glob("attempt-[0-9][0-9][0-9]") 由 globAttempts 照 fnmatch 过滤（dispatcher 的 globPaths 只认 *，不改，themistally-15 定的），另导出排好序的 attemptsOf。base：clock 的 mtimeUtcSeconds（文件修改时刻照 CPython 的 fromtimestamp 换到秒：微秒半数取偶，满 1e6 进位）；新模块 pyexc（pyExceptionName、pyCaught：base 里带 Python 类名的异常照继承关系接，⑤g2 的 except OSError 也用它）。探针：快照与还原保留文件与目录的修改时刻（Python 的 _copy_dir_times，TS 的 copyTreeTimes，flow-fixtures 的 scene() 同样）；采样器把元组里的 Path 记成字符串，call_snapshots 也认 previous。契约 hub-exec：只采 ⑤g1 的函数，44 条用例的 248 次调用三边重放，都与当时的结果相同；hub-exec-scenes 14 组手写场景；pybase-config 加修改时刻的对照（40 个设在边界上的文件）。写场景时三边比出来的：3.12 起 slice 能散列，字典切片报 KeyError。变异 ts/mutations/hub-g1.ts.json 65 条：第一轮 61 条抓住 58 条，漏掉的 E12（返工链里没有 commit 的条目）、E30（Scope 标题前面的空白）、E59（四位数的 attempt）补了场景；写到一半复核后改的 pyCaught、pyIn 连同新加的 E60，7 条单独重跑都抓住；完整复核后 pyexc 补了 base 造得出的六个类名（BrokenPipeError、ConnectionError、ChildProcessError、BlockingIOError、TimeoutExpired、SubprocessError）与三边对照（继承关系逐对比 __mro__，认类逐个比 type(exc).__name__），并进 E61–E63（认不出 fsutil 的 UnicodeDecodeError、RecursionError 挂到 ValueError 下、ConnectionError 不算 OSError），单独重跑都抓住。themistally-15 另抽查的 X03（st_mtime 用 nsec / 1e9 算）、X04（微秒半数不取偶）判为等价：只出到秒，它在 Python 上跑的 40378 组时刻与 datetime.fromtimestamp 全同；X09（TS 探针还原时不设修改时刻）在 Windows 上 cpSync 照抄文件时刻、⑤g1 只比 candidate.patch，目录的时刻要到 final_audit_turn 才用上，届时补这条变异（final_audit_turn 实际在 ⑤g2 移植，X09 随 ⑤g2 补上，抓住）。全量 vitest：1812 passed、2 skipped（129 个文件）；typecheck 通过。harness 的 runBatch 加可选时限，hub-exec 与 hub-gatepost 的采样重放给 10 分钟（一次整套并行时，几百次重放超过了缺省的 60 秒）。 | 完成 | 见提交说明 |
| ⑤g2 | 执行端代办里改状态的部分（⑤g 设计稿第 12、13 节）：kit_hub.py 的 run_exec、dispatch_attempt、start_rework、rebase_candidate、scratch_worktree、rework_added_files、ensure_rework_scope、start_retry、finish_exec、final_audit_turn、write_review、exec_marks、exec_window、LandBusy、EXEC_LAND_WAIT_SECONDS 与 EXEC_LAND_RETRY_SECONDS、load_contract_screen、run_jev（新模块 @themis/hub/runexec，⑤g1 的只读部分留在 exec.ts；用例当时换掉的 run_pd、contract_requirements、rework_added_files、worktree_root、mkdtemp、load_locked_batteries 与决策端 Session 的 ask 经可选的末位参数 deps 注入，等锁时限也在里面，生产调用方不传）。内核直接起的四处子进程不套 git()：diff --binary 不设缓冲上限、按字节判空白，apply --3way 两路接同一个 fd，merge-base --is-ancestor 只认退出码 1，worktree remove 不看结果；交给 git 的提交与 run_jev 的 exec.run_dir 不是字符串时照 Python 报 TypeError（第 10 节那行改记）。base 的 pyexc 认 Node 的文件错误（带 syscall、code 是字符串的：先走 pyio 的 pyOSErrorOf，ENOTDIR 另补，别的是 OSError；Node 的参数错不认）。config 导出 batteryDict；hub 依赖 @themis/config。探针：flow 的注入名单加 rework_added_files、Session（记它的 ask）、load_locked_batteries，run_exec 的 mkdtemp 照记录注入，落地锁被占的那一条记 skip；HubError 的子类记自己的类名；手写场景用的等锁时限与 JEV 真会话（两边的传输层只认官方地址，改发本机的假端点，只给假 key，凭据库关掉）。契约 hub-runexec：31 条用例的 63 次顶层调用，跳过落地锁那 1 次，62 次三边重放都与当时的结果相同；hub-runexec-scenes 15 组手写场景；pybase-config 加 except OSError 认 Node 的文件错误（Python 真触发 7 种）。变异 ts/mutations/hub-g2.ts.json 58 条：R 的 55 条抓住 53 条，R18、R51 等价（R51 第一轮意外漏掉，查明 Session.ask 两边都不读阈值）；X09 单独跑抓住；base-g2 4 条全部抓住。themistally-15 抽查 11 条，10 条抓住；Y02 第一轮漏掉，补场景后并进 X10，抓住；Y08 漏掉，原因是 Python 用例从没给 finish_exec 带违规的 scope.json，补场景后并进 X11，单独跑抓住。全量 vitest：131 个文件，1829 passed、1 failed、2 skipped；挂的是 pi-cli 的 run_capture 进程树超时那一条（⑤g2 没碰：整套并行时超时之后清临时目录报 EPERM，单跑三次都过），themistally-15 的副本上同样的字节整套 1830 passed、2 skipped。 | 完成 | 见提交说明 |
| ④b6 | 事件流摘要与 summary.md。`@themis/dispatcher/events`（summarize_events、extract_report、review_hints、_message_text、ambiguity_domain_words、ambiguity_mentions、interpretation_mentions）；`shell-scan`（_path_forms、_escapes、_protected_mentions、_root_entry_exists、_outside_mentions、_mask_paths、_cache_dir_cleanup、_match_excerpt、_masked_exit_mention、_temp_dir_without_cleanup）；`summary`（write_summary、executor_source_text、_decisions_summary；问题清单由命令层经 SummaryContext 注入，dispatcher 不能 import config）；`decision-records`（latest_by_point、answer_value、noul_confidence）。正则原文由 `tools/gen_event_patterns.py` 从 pi_dispatch 生成（`event-patterns.ts`，`--check` 挂在契约里），交给 sre 移植编译；`_CACHE_TARGET_RE` 带反向引用，按步骤解析，形状由生成脚本钉住。base 的 sre 引擎交回匹配的起止位置（searchSpan、matchSpan、PyPattern），pyfmt 补 pyPlus、pyPositive、pyPercentD、pyIntOf、pyFloatOf、pyIter、pyItem、pyJoin（pyAdd 对超大 int 照 Python 抛 OverflowError），pypath 补 purePathIsAbsolute。写契约时查出 Python 内核自己的不确定（_path_forms 等长写法的次序随散列变），先由第 124 轮修掉。契约 11 条：stub_pi 的 18 个剧本加 3 种环境、按种子改坏的 252 份变体、手写的边界事件流、主工作区 8 份真实事件流（0.8–45 MB）、构造的 shell 命令 613 条、提及与领域用语 1,500 条、extract_report 160 条与补丁 84 份（含恰好 20 MiB）、write_summary 221 个 attempt 目录（证据字段随机换类型，崩溃比类名与文字；比较不了的两种类型的报错按类型名排好再比，那两个名字的先后 Python 自己也随散列变）。三份实现逐字一致，写文件的逐字节比。变异 51 个，第一遍抓住 37；漏掉的 14 个里 11 个补了手写用例后抓住，1 个改的是走不到的分支（删掉，换成字典的一条），2 个写明等价（开头的空段、行尾多个回车）。全量 pytest 3044 passed / 228 skipped，全量 vitest 920 passed，只有两条红：③a2 的 validate 契约钉着第 125 轮之前的行为（b63ea51 补），supervise 的 S5a 负载重时偶发（单跑 25 passed，记在 10.1）。跑之前与之后各数一次系统日志的事件 26：9 → 9。**复核后补**（themistally-15 复核 c877077）：own_run_paths 全是 null 时 sorted 只有一项不比较；report-screen 清单的读取挪进 @themis/config 的 reportScreenBattery；Windows 上 abspath 经 GetFullPathNameW、pyResolve 照 ntpath.realpath、新增 pyExists（映射成设备且上一级在才算存在），工具参数是 nul 或带长路径前缀时两边一致（第 10 节）；探针加 pypath.call，TS 探针先做原生初始化。变异另加 pypath-b6 的 7 个（6 个抓住、1 个写明等价）与 W14 | 完成 | 见提交说明 |
| ④ | 证据与门禁 | | |
| ⑤ | 七端 hub 内核 | | |
| ⑥ | 撤掉 Python | | |

---

## 12. 样板：`publish_new`

完整走一遍“契约测试 → 移植 → 对照测试 → 变异检验”，后续模块照这个样子做。

### 12.1 契约（`ts/packages/contracts/test/publish-new.contract.test.ts`）

契约取自 `pi_dispatch.publish_new` 的说明，共 9 条，每套实现逐条通过：

| 编号 | 场景 | 期望 |
|---|---|---|
| C1 | 目标不存在 | 返回 true，字节原样，不留临时文件 |
| C2 | 目标已存在 | 返回 false，原字节不变，不留临时文件 |
| C3 | 目标是只读文件 | 返回 false，原字节不变 |
| C4 | 目录不存在 | 报 ENOENT，什么也不建 |
| C5 | 空数据 | 返回 true，建出空文件 |
| C6 | 0–255 全部字节、CRLF、NUL | 原样写入，不做行尾转换 |
| C7 | 目标是目录 | 返回 false，目录不变 |
| C8 | 六个进程同时发布 | 恰好一个返回 true，文件是它的数据，不留临时文件 |
| C9 | 4 MiB 数据 | 完整写入 |

**先对 Python 跑**：9 条全过。这也是第一次实测确认 Windows 上“目标是目录”时 `os.rename` 报 `FileExistsError`、返回 false。

### 12.2 移植（`ts/packages/base/src/publish.ts`）

- **发布那一步改用硬链接**：Node 与 Bun 的 `renameSync` 在 Windows 上会**覆盖**已有目标（Python 的 `os.rename` 不会）。所以 TS 版两个平台都用 `linkSync`：遇到已有目标一律报 EEXIST，再删临时文件。这是契约测试要守住的关键差别，变异 M01 专门检验它。
- **其余照 Python 版**：
  - 临时文件放在同一目录，命名 `<目标名>.<16 位十六进制>.tmp`；
  - 用 `O_EXCL` 创建；
  - 发布那一步之外的错误原样抛出；
  - 成功、失败都删临时文件。

### 12.3 对照（`publish-new.compare.test.ts`）

- **24 个按种子生成的场景**：
  - 覆盖五种初始状态：不存在、已存在、只读、是目录、缺父目录；
  - 数据 0–8192 字节。
  - Python、Node、Bun 三种运行方式的返回结果与目录字节逐一相同。
- **三轮混跑并发**：每轮九个进程（每种运行方式三个）抢同一个文件，恰好一个成功，文件是它的数据。

### 12.4 白盒单元测试（`ts/packages/base/test/publish.test.ts`）

契约从外部观察不到的内部约定：
- 临时文件的位置与命名；
- 用 8 个随机字节起名；
- 撞名时报 EEXIST、不碰别人的文件；
- 发布那一步的其他错误原样抛出、临时文件照删；
- 描述符在三条路径上都关。

### 12.5 结果

- **测试**：61 条全过（契约 27、对照 28、单元 6），用时约 6 秒；`tsc` strict 无错。
- **TS 变异**：11 个，全部抓住。
  - 第一轮漏了 M11“写完不关描述符”：契约看不出描述符泄漏，补了一条白盒用例之后抓住。hub 每封信发布一次，泄漏会慢慢耗尽句柄。
- **Python 变异**：4 个，抓住 3 个。P04“临时文件不用 O_EXCL”从外部观察不到，标为等价；TS 侧的同一规则由白盒用例守住。
- **打包**：`bun build --compile` 把 TS 探针打成单文件 exe，发布一次返回 true，第二次返回 false，原内容不变，不留临时文件。

### 12.6 做样板时踩到的坑（后续模块照此避开）

- **Windows 上 Python 的 stderr 是文本模式**：`ready\n` 实际写成 `ready\r\n`。探针之间的握手不能按 `\n` 精确匹配。
- **Vitest 2.1.8 的分组名**：`describe.each` 用对象参数时，`$name` 会带引号插进名字（`impl='python'`）。按实现过滤要写 `-t "impl=.python."`。
- **调度器的变异清单不能设环境变量**：按实现分组的测试只能靠名字过滤。
- **npm 装的 Bun 只在 bin 目录放 `bun.cmd`**：Node 不经 shell 启动子进程时找不到 `bun`。已把 `bun.exe` 的目录加进 PATH。
