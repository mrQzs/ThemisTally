# Themis Tally 3.0：实现语言迁移到 TypeScript 的计划

- **状态**：v1.4（见下）。v1.2 于 2026-10-22 themistally-15 同意，附的条件已补进（第 ② 步的启动器与切换测试、Schema 的位置、第 10 节的 `--assess`）。
  - v1 于 2026-10-22 带条件通过。站主委托 themistally-15 会话答复，第 0 步的提交 266cd33 照常合入。
  - v1.1 补进了通过时附的条件：第 2.1、2.2、2.4、3.2、4、5、8.2、8.5 节，以及第 1.4 节的 pyjson。
  - v1.2 按开工前的调查改第 ② 步：调度器的 `metrics` 没有 `--json`、只出 Markdown；带 `--json` 的 `status`、`metrics` 另有一份在 hub 里；`logs cat` 漏写了；仓库里没有 `themis` 入口，桌面端的本机服务也还没建。第 ② 步的范围、出口条件与拆分照实改（第 4 节）。
  - v1.3（2026-10-26，themistally-15 同意，附的七条已补进）按开工前的调查重写第 ③ 步：配置中心随桌面端 D2 长大了，原文“13 个 `--json` 子命令”过时；plugins 归入第 ③ 步，`secret set` 留在 Python，拆成六片加切换（第 4 节）。另记站主同日的决定：T022 的 A、B 做完后暂停开新切片，专心推迁移；以及 themistally-15 转达时附的协调意见（不是站主原话）：之后内核文件只修挡住工作的缺陷，迁移本身的切换不在其内（第 9 节、第 10.1 节）。
  - v1.4（2026-10-26，themistally-15 复审）按开工前的调查与复审重写第 ④ 节：21 条命令加 `status --assess`，八片加切换，开工前定下 D1（平台与版本经 `context` 交）、D2（Ctrl+C 与 CTRL_BREAK 的转发）、D3（`NODE_OPTIONS` 等经换名的环境变量交给 pi）、D4（决策会话的 HTTP 逐项对齐），写明对照办法五条、影子运行的隔离做法与混合期的 26 个名字。
  - v1.5（2026-10-26，themistally-15 复审 v1.4 时要求）补 D5：起真调度器子进程的测试在没装 TS 依赖的环境里怎么办，按实测清点、钉成 Python 的做法、包装与真脚本的逐字节比较和分环境的出口条件；第 11 节 ③-切换一行补上 A3 的更正。④b1 合入时补：切换那一轮的 context 加 `kit_root` 与 `kernel_impl`（第 ④ 节“切换”）。
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
  - 环境一致：TS 子进程拿到的是这条命令走 Python 时看到的 `os.environ`，只去掉运行时注入变量（`pi_dispatch.TS_RUNTIME_ENV_DROP`：BUN_OPTIONS、NODE_OPTIONS、NODE_PATH、BUN_INSPECT*）。“环境一致”指命令逻辑看到的变量一致，不包括这些（themistally-15，2026-10-22）：它们不影响 Python 的行为，却能往 TS 进程里塞代码。实测 Bun 1.4.2：BUN_OPTIONS 里的 `--preload` 照样生效，NODE_PATH 让裸模块名多一处解析来源；NODE_OPTIONS 现在 Bun 不理会（Node 后备会）。每个变量各有一条测试。Windows 上经 `os.environ` 转一道，变量名成了大写，变量名本来就不分大小写，不影响取值。
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

- **先决条件（④a）**：已完成（第 8.2 节）。欠一项：stderr 并进 stdout 的“共用句柄”写法（第 8.2 节“第 ④ 步要处理的”），在 ④b3 补。
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
  | ④b4 | **决策会话**：<br>• `decisions_session`、report-screen、mutation-equivalence、run-health；<br>• `codekit/decisions` 的 `Session`、`http_transport`、`check_answer`、记录读写、`usage_totals`；<br>• 命令 `wait --assess`、`status --assess`、`decisions`（replay）、`doctor`。<br>D4 的 HTTP 对齐在这一片做 | 约 740 |
  | ④b5 | **mutate**：<br>• 清单、轮次、`--tree`、`--check-anchors`、`--out`，interrupted 照 test_mutate_interrupted；<br>• `difflib.SequenceMatcher` 逐行为移植：锚点提示的“最相近的行”与百分比逐字节进 `--check-anchors` 的输出，hub 原样转进信里。<br>出口条件里 `mutate --check-anchors` 的影子运行从这一片起做 | 约 630 |
  | ④b7 | **prepare、run、collect、smoke**：pi 预检、上下文证据、执行说明、领取与 TaskLock | 约 875 |
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
    - 第 ③ 步的 config 写命令：TS 不装处理，经上面的对应照旧是“已取消。”、退出 130，行为不变；第 ③ 步接受的“持锁一瞬留锁”也不变。
  - **D3 交给 pi 的 `NODE_OPTIONS` 等变量**：启动器从 TS 进程的环境里去掉 `TS_RUNTIME_ENV_DROP`（`BUN_OPTIONS`、`NODE_OPTIONS`、`NODE_PATH`、`BUN_INSPECT*`），可 run 与 smoke 起的 pi 是 node 程序，照 Python 的 `child_env` 应当拿到它们（第 ③ 步的探测命令也一样，见第 10 节）。
    - 做法：启动器把被去掉的原值换个名字放进 TS 的环境（`THEMIS_PARENT_<名字>`），TS 自己不用；`childEnv` 拼子进程环境时还原成原名，再删掉换过名的那几个。不走 pyargs：值会出现在进程命令行里，同用户的任何进程都看得到。
    - 放在哪：TS 的还原在 ④b7，启动器换名放进切换那一轮。
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
- **回退**：改回 `python`。证据目录格式由契约保证一致，已经开跑的 attempt 用 Python 的 `collect --recover`、`check` 接着处理。
- **混合期**：`dispatcher` 切到 `ts` 之后，hub 仍是 Python，`kit_hub.py` 在进程内直接调用的 `pi_dispatch` 名字仍是 Python 版（`d1873a9` 时 26 个）。这些名字到第 ⑤ 步之后才能删，期间要由契约保证它们读得懂 TS 版写的东西：

  | 名字（`kit_hub.py` 里的次数） | 用途 | 由哪份契约覆盖 |
  |---|---|---|
  | `pd.get_state`（10） | 读 attempt 的 `state.json` | ④b2 证据目录契约：Python 的 `get_state` 读 TS 写的 `state.json` 得到同样的状态 |
  | `pd.pid_alive`（7） | 锁的持有进程还在不在 | 第 ① 步 `locks` |
  | `pd.Repo`（5） | 找仓库、读配置 | 第 ③ 步配置契约 |
  | `pd.run_supervised`（5） | 回合与门禁命令的进程监督 | ④a；hub 的 pytest 两边传同一个文件对象，TS 的共用句柄写法在 ④b3 |
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

- **内容**：`kit_hub.py` 全部，含 hub 自己的 `status --json`、`metrics --json`（v1.2 从第 ② 步挪来）。现有的 pytest 场景（第 56 轮时 216 个）逐个移成 TS 用例。工人运行时照旧是 `claude -p` 与 `pi --mode json`；quizs 替代 pi 另开轮次做。
- **出口条件**：
  - 场景用例全过；
  - 影子运行：TS hub 以只读方式读同一个信箱，对每封待办信算出守卫结论与“允许的下一步”，与 Python hub 一致，连续一片切片不出差异；
  - 至少一片切片由 TS hub 从头到尾办完并落地。
- **切换**：`hub` 改成 `ts`，由 supervisor 的入口决定起哪一套。
- **回退**：停掉 TS hub，起 Python hub，接着用同一个信箱。信件、账本、`state.json` 的格式由契约保证一致。

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
| 路径语义的细差（TS 的 `pypath.ts`） | Windows 上 Python 3.12 的 normcase 用 LCMapStringEx 的不变区域小写，TS 用 toLowerCase；abspath 的 GetFullPathNameW 会去掉段尾的点与空格，`path.resolve` 不去 | 只在路径含特殊大小写字符、或段尾有点与空格时才可能不同；遇到再补 |
| Node 后备认不出一部分重解析点 | Python 把 Windows 上一切带 REPARSE_POINT 属性的条目都当链接；Bun 经 GetFileAttributesW 一致，Node 后备只用 lstat，认不出云文件占位、AppExecLink 这类 | 第 ⑥ 步之前 Python 一直是退路；需要时让 Node 后备经 `__native` 辅助进程批量查属性 |
| `logs search` 拒绝反向引用与条件分组、括号嵌套超过 100 层（行为变更，r3 §10 第 58 轮，Python 先改） | 以前能搜的这两类写法现在报错（退出码 2） | 搜索框只做逐行过滤，两类构造在这里没有实际用途；桌面端文档的搜索说明已记。原因说准（themistally-15，2026-10-22）：第 58 轮当时以为 JS 正则做不到；②b2 改成移植 sre 匹配器之后，引擎其实已经能支持这两类，只是不值得（多两类操作码与它们的对照）。保留拒绝；需要时可以撤销第 58 轮，补上 GROUPREF、GROUPREF_EXISTS 两类操作码与对照 |
| `logs search` 的 PATTERN 是用户可控的正则 | 灾难性回溯：TS 的 sre 移植与现在的 Python 一样中断不了，而且更慢（解释执行：常见写法慢约 3 倍以内，`.*` 在 200 KB 长行上反复回溯约 3 倍；构造出的指数级写法约 20 倍，这一项是在后两轮优化之前测的） | 启动器的 Job 加超时、超时结束整棵进程树；将来的本机服务调 logs search 一定要设超时（themistally-15，2026-10-22） |
| `logs search` 的匹配语义要与 sre 一致 | JS 正则（尤其 JavaScriptCore）与 sre 的回溯次序、空匹配处理、原子组都不同；sre 自己还有怪癖：信息块的字符集前缀按整个模式的标志编译，`(?a:[^\w])` 开头的模式不把 µ 当起点 | 不用 JS 正则，移植 sre 的字节码与匹配器，怪癖照搬；对照测试在 Bun、Node 两种运行时各跑一遍 |
| 游标绑定的文件号 | CPython 3.12 在 Windows 上的 st_ino 取自文件 ID，ReFS 上可能是 128 位；Node 的 ino 是 libuv 给的 64 位 | 本机 NTFS 实测三套取值相同（②b1）；ReFS 上未验证，遇到再处理 |
| `status --json --assess` 在 JSON 之后接 assess 的文本行，stdout 不是合法 JSON（现行行为，第 ② 步照样保留） | 桌面端本机服务拿它当 JSON 解析会失败 | 赶在本机服务建成之前另开一轮修掉：assess 的文本挪到 stderr，或放进 JSON 的一个字段。在那之前，服务不拿 `--assess` 的输出当 JSON 解析（themistally-15，2026-10-22） |
| 经启动器转交的写命令被 Ctrl+C 打断（第 ③ 步切换之后） | **触发条件**：在交互终端里对转交给 TS 的写命令按 Ctrl+C，并且正好落在持锁的那一瞬。<br>• 写入都经 `config_transaction(s)`，共 19 处调用：17 个命令入口（kit_config 5 个：set、unset、init、decisions、rollback；kit_roles 10 个；kit_plugins 2 个），另有 `write_config`、`write_checked` 两个公开函数，只有测试在用；<br>• `runtime scan` 的探测在拿锁之前；<br>• 持锁期间只做读、改、快照、审计、替换，约百毫秒。<br>TS 子进程另起了进程组，收不到 Ctrl+C，由启动器终止 Job。<br>**留下什么**：锁目录 `.agent/.config.lock/` 与其中的 `owner.json`；如果断在写临时文件与替换之间，还有其中的 `<文件名>.<16 位十六进制>.tmp`。Python 收到 KeyboardInterrupt 时 `ConfigLock.__exit__` 会删掉整个目录，连同临时文件。<br>审计的状态两边相同：断在 intent 之后、commit 之前，下一次写都补判 `resolve`。<br>**下一次写看到什么**：等满 30 秒，退出 1，报“配置锁被占用：<路径>，进程 <pid>（主机 <host>，已退出，<时间> 起持有）。确认没有别的写配置的命令在运行之后，删除这个目录再重试（锁从不自动清除）”。<br>**用户当场看到的两边一致**（v1.3 核对过代码）：<br>• Python：`kit_config.main` 接住 KeyboardInterrupt，stderr 写“已取消。”，退出 130；<br>• 经启动器：`run_handoff` 在 `proc.wait()` 处接到 KeyboardInterrupt，终止 Job 后再抛出，`pi_dispatch.main` 写同样的“已取消。”，退出 130；<br>• 打断之前已经写出的 stdout 两边也相同：`@themis/config` 只经 `@themis/base/pyfmt` 的 `PyOut` 写 stdout 与 stderr，它用 `writeSync`，照程序次序同步写完才返回；Python 的块缓冲在退出时刷出。 | 接受（v1.3，themistally-15 同意）：<br>• 被硬杀（`run_pd` 超时、桌面端发 CTRL_BREAK 之后宽限期满）时，两套实现本来都会留锁；<br>• 报错写明了删哪个目录，能恢复；<br>• 要改，就让启动器先给 TS 的进程组发 CTRL_BREAK、宽限之后再终止 Job，TS 装上处理函数删锁，代价是启动器多一段信号转发与宽限逻辑，外加各一条测试 |
| `secret set` 留在 Python（第 ③ 步） | 第 ⑥ 步撤 Python 之前，凭据的写入还是 Python | 第 ⑥ 步再移，要解决的三件事写在第 ⑥ 步的内容里 |
| `run_capture` 超时后孙进程还握着管道（第 ③d 片） | Python 只结束直接子进程（`pi.CMD` 是 cmd.exe），再不设时限地 `communicate()`，孙进程（node）不退，命令就一直挂着；TS 经 Job 结束整棵树，按时返回 124 | 接受（v1.3，themistally-15 同意）：<br>• 正常超时（退出码 124、空 stdout、`timeout after Ns`）两边一致，契约有用例；<br>• 挂住的情形不照搬；<br>• Python 一侧按第 9 节的冻结规矩不修 |
| 只把 strerror 放进输出的 lstat、listdir 一类（第 ③ 步：运行中切换的扫描、本机文件“看不了”） | Python 的文字是 Win32 错误码经 FormatMessageW；TS 从 libuv 的错误码只认得出拒绝访问（EACCES、EPERM 当 5 号错误，文字照样取 FormatMessageW，跟着界面语言），其余错误码反推不回 | 接受（themistally-15 同意）：<br>• 拒绝访问以外的错误码，文字不保证一致；<br>• 会把整条报错放进输出的 os.replace、os.rename、Path.mkdir（“写入失败”“审计写不进去”“快照存不下”）走原生 Win32，逐字一致，契约有用例；<br>• 锁目录、marker 与凭据文件的 mkdir、unlink 失败时 Python 直接崩溃，不进受控的输出 |
| JSON 嵌套 1001 层到约 2994 层、里面又有文法错误（第 ③e 片，themistally-15 复核 ac10a2e 时实测） | TS 的 pyjson 在第 1001 层报 RecursionError，CPython 3.12 在 Windows 上要到约 2995–2998 层（看最底下是什么、钩子占几格）。这个窗口里 `strict_json_loads` 的错误码不同：Python 报 `E_JSON_SYNTAX`，TS 报 `E_JSON_LIMIT`；`plugins verify`、`plugins list --json` 里“解析失败：…”的码随之不同，退出码相同 | 接受（2026-10-26，themistally-15 建议）：不按调用路径模拟 CPython 的 C 递归预算。合法的深文档两边都是 `E_JSON_LIMIT`；正常的 manifest、锁不会嵌套上千层 |
| 配置嵌套约 993 层到约 2997 层（第 ①、③a2 步起就有，themistally-15 复核 ③e 时实测） | Python 的 `json.loads` 读得完，`secret_like_paths` 递归时撞上解释器的递归上限，打堆栈退出 1；TS 在 998 层以下报“配置无效…”，999 层以上报“ERROR: 无法解析 …：RecursionError”，都是退出 1。约 2998 层以上两边都报“无法解析…RecursionError”。契约里“嵌套很深”用的 3000 层在窗口外面 | 接受（同上）：退出码一致、文字不同；要逐字一致得同时模拟 C 递归预算与 `secret_like_paths` 当时的 Python 栈深，为至少 990 层深的配置加这些复杂度不值 |
| 切换之后，配置中心起的 CLI 拿不到 `NODE_OPTIONS`、`NODE_PATH`（第 ③ 步的切换，themistally-15 复核 ③d 时查出） | 启动器的 `handoff_env` 把 `TS_RUNTIME_ENV_DROP` 从 TS 进程的环境里去掉，TS 的 `childEnv` 又从 `process.env` 拼；Python 的 `child_env` 会把这两个变量带给 pi。runtime scan、probe、models、doctor 起的 pi 是 node 程序，用户要是靠 `NODE_OPTIONS` 给 pi 加内存上限，经 TS 探测时就没有 | 接受（2026-10-26）：本机的进程、用户、机器三层都没设这两个变量，选择文件也不随 kit 分发；探测只跑 --version、--help、--list-models 与 auth check。第 ④ 步照 D3 修：启动器把去掉的原值换名放进 TS 的环境，`childEnv` 还原成原名（④b7 与切换那一轮） |

### 10.1 迁移期间暂缓的改进

站主 2026-10-26 决定专心推迁移（第 9 节）。按 themistally-15 的协调意见，从 T022 B 片落地起，内核文件只修挡住工作的缺陷，不挡路的改进记在这里，等对应模块切到 TS 之后在 TS 上做。

| 记下的日期 | 模块 | 改进 | 来源 |
|---|---|---|---|
| 2026-10-26 | `pi_dispatch.secret_like_paths`（Python 与 TS 一致） | 键名含 `token` 就算疑似凭据：`pricing` 文档写着可以填的 `per_tokens` 一写，`validate` 就整段报“pricing 里有疑似凭据”，内核也不读这份配置。改成只在值像凭据、或键名是凭据类名字（`api_key`、`access_token` 这类）时才算；两边同一轮改。现在没人写 `per_tokens`，不挡路 | 第 ③a2 片的整份校验契约 |
| 2026-10-26 | `ts/packages/ui/test/secret-entry.test.ts` 的“全部反例都不回 201” | 握手时限只有 1 秒，负载重时偶发少起子进程（2026-10-26 全量与 T023 的执行端同时跑时 5≠10，单独重跑两遍都过）。门禁与 hub 的回归常与别的重活同时跑，红了会被当成返工。再红一次就放宽这条用例的时限（只改测试夹具，不改产品行为）；合入前红了就单独重跑一遍 | themistally-15 复核 ③d |
| 2026-10-26 | `desktop/web/tests/shellpages-settings.test.tsx`（门禁 T004、T013 的流水线跑它） | `grabShell` 负载重时拿到 null（2026-10-26 在 6ed53d0 上跑全部门禁基准，正与 T023 的收尾同时跑，13 条红；dc53c27 那一遍与 3d1e101 的 owner sweep 都过）。用的是桩（createShellStub，jsdom 里），不碰真内核。处理同上一条：合入前红了就单独重跑一遍；门禁或 hub 回归里再红一次就改夹具 | themistally-15 复核切换 |

**已定**（2026-10-22，themistally-15 代站主答复）：
1. 选择文件就是 `scripts/kernel-impl.json`，规矩见第 5 节。
2. Schema 校验器用 Ajv 8，第一份 Schema 落地时引入，条件见第 3.2 节。

**待定**：第 ⑥ 步对离线 v2 参考实现的处置（移目录，还是只留标签），届时再问。

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
