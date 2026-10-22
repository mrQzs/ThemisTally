# Themis Tally 3.0：实现语言迁移到 TypeScript 的计划

- **状态**：v1.2，2026-10-22 themistally-15 同意，附的条件已补进（第 ② 步的启动器与切换测试、Schema 的位置、第 10 节的 `--assess`）。
  - v1 于 2026-10-22 带条件通过。站主委托 themistally-15 会话答复，第 0 步的提交 266cd33 照常合入。
  - v1.1 补进了通过时附的条件：第 2.1、2.2、2.4、3.2、4、5、8.2、8.5 节，以及第 1.4 节的 pyjson。
  - v1.2 按开工前的调查改第 ② 步：调度器的 `metrics` 没有 `--json`、只出 Markdown；带 `--json` 的 `status`、`metrics` 另有一份在 hub 里；`logs cat` 漏写了；仓库里没有 `themis` 入口，桌面端的本机服务也还没建。第 ② 步的范围、出口条件与拆分照实改（第 4 节）。
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
| 命令的 `--json` 输出 | 七个模块共 25 个 `--json` 子命令：`status`、`logs list/show/search/usage`、`metrics`、`config` 的 13 个子命令、`plugins` 的 3 个等 | 散在代码与测试里 |
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

- **内容**：`kit_config.py`、`kit_roles.py`：13 个 `--json` 子命令、配置锁、历史快照、审计记录。
- **出口条件**：
  - 同一串命令分别在两份临时仓库里跑，配置文件、历史与审计按契约一致；
  - 两套实现交替写同一份配置，配置锁照样互斥；
  - `config doctor` 的探测结果一致。
- **切换**：`config` 改成 `ts`。
- **回退**：改回 `python`。配置文件格式由契约保证一致，可以直接接着用。

### ④ 证据与门禁

- **先决条件（④a）**：Windows 进程监督的三项行为先在 TS 下验证（第 8.2 节），通过才开工。
- **内容**：prepare、run、check、mutate、verdict、integrate，加上合同校验、范围门禁、脱敏与证据目录的写法；`metrics`（只出 Markdown，读决策记录与价格表，v1.2 从第 ② 步挪来）。
- **出口条件**：
  - `test_dispatch.py` 等现有用例的场景全部有 TS 对应用例；
  - 影子运行：对最近的真实 attempt，TS 版的 `check`、`verdict` 与 `mutate --check-anchors` 的输出与 Python 版按契约一致。`check`、`verdict` 会写 attempt 目录（`checks/NN`、`verdicts/`）和 Git 对象，所以 TS 版的写命令只在复制到临时目录的副本上跑，绝不碰真实的 `.agent/runs/`；
  - 至少一片真实切片在 `dispatcher` 选 `ts`、hub 仍是 Python 的组合下完整走完并落地。
- **切换**：`dispatcher` 改成 `ts`，由 `pi_dispatch.py` 的入口按选择文件转交（第 5 节）。
- **回退**：改回 `python`。证据目录格式由契约保证一致，已经开跑的 attempt 用 Python 的 `collect --recover`、`check` 接着处理。
- **混合期**：dispatcher 切到 `ts` 之后，hub 仍是 Python，`kit_hub.py` 在进程内直接调用的 `pi_dispatch` 名字仍是 Python 版。这些名字到第 ⑤ 步之后才能删，期间要由契约保证它们读得懂 TS 版写的东西：

  | 名字（`kit_hub.py` 里的次数） | 用途 | 由哪份契约覆盖 |
  |---|---|---|
  | `pd.get_state`（10） | 读 attempt 的 `state.json` | 第 ④ 步证据目录契约：Python 的 `get_state` 读 TS 版写的 `state.json` 要得到同样的状态 |
  | `pd.pid_alive`（6） | 锁的持有进程还在不在 | 第 ① 步 `locks` |
  | `pd.Repo`（5） | 找仓库、读配置 | 第 ③ 步配置契约 |
  | `pd.run_supervised`（3） | 回合与门禁命令的进程监督 | 第 ④a 步的验证用例 |
  | `pd.DispatchError`（3） | 异常类型 | 不跨语言，留在 Python |
  | `pd._md_section`（2）、`pd._md_scope_lists`（1）、`pd._CHECK_LINE_RE`（1） | 解析合同 Markdown | 第 ④ 步合同契约（`derive-json` 的输入输出） |
  | `pd.write_json`（1） | 写证据 JSON（`indent=2`，不排序） | 第 ① 步 `pyjson` |
  | `pd.publish_new`（1） | 发布信件 | 第 ① 步 `publish`（已完成） |
  | `pd.compile_patterns`（1）、`pd.matches`（1） | Scope 的路径通配 | 第 ④ 步范围门禁契约 |
  | `pd.child_env`（1） | 子进程环境变量的过滤 | 第 ④ 步 |
  | `pd.budget_usage`（1） | 各合同版本累计的 attempt 与墙钟 | 第 ④ 步证据目录契约（读 TS 版写的 claim 与 run 记录） |
  | `pd._running_attempts`（1） | 正在跑的 attempt | 同上 |
  | `pd.resolve_pi_command`（1） | 解析 pi 的命令 | 第 ③ 步角色绑定契约 |
  | `pd.RESOURCE_FLAGS`、`pd.MUTATION_DEFAULT_TIMEOUT`（各 1） | 常量 | 第 ④ 步：两套实现的常量表逐项对照 |

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
  - 统一核对 AGENTS.md、技能、README 里的命令。
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
- 每完成一步向站主汇报。
- 犯错照例记进 `AGENT_LEARNINGS.md`。

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
| ②b1 | `logs cat`：`@themis/dispatcher/logs-cat`（safe_page 的文本页与 JSONL 页、游标的编码与核对、整份与逐行脱敏、超长行与隐藏行；偏移与切片按码点，64 MiB 的文本不拆数组，用补充平面字符的位置二分换算）。游标绑定的文件身份 (size, mtime_ns, ino)：本机 NTFS 上 Python、Node、Bun 实测取值相同。入口改用 pyjson 解析参数（`--limit` 这类 Python int 超出 JS 数字精度时，报错里原样写出）。对照：合成夹具的用例 17 个，加同一仓库里逐页翻的 3 个（文本长行按片、JSONL 长行按行内字符续读、文件变长后续读与改写后作废，含变长同时改写）；真实证据手动对照：3 个 attempt × 9 种文件与页大小顺着游标翻页，加 7 种报错，共 78 次调用，Node 与 Bun 都与 Python 逐字节一致。变异 21 个全部抓住（K11“JSONL 游标不核对之前的一段”起初漏掉：原用例改写时大小不变，修改时间那条先报了作废；补了“文件变长、之前的字节也被改了”才抓住）；“rfind 的边界保护”是等价变异（首页以换行开头时切片必以换行结尾，构造不出），没列 | 完成 | 见提交说明 |
| ②b2 | `logs search`。`@themis/base/pyregex`：parser（`Lib/re/_parser.py` 逐段移植，报错文字与位置照原样，`\N{…}` 用生成的 Unicode 15.0 名字表，含别名、谚文音节与 CJK 统一表意文字的规则）、compile（`_compiler._compile` 编出 sre 的字节码；单字符的匹配器按 sre 运行时的判定算成码点集合，大小写用 `_sre` 的简单映射与 `_casefix`；信息块的字面量前缀与字符集前缀照 `_compile_info`，字符集前缀按整个模式的标志编译的怪癖照搬）、engine（`sre_lib.h` 的 SRE(match)、SRE(search) 移植，显式上下文栈，长行上的重复不撑爆调用栈）、search（第 58 轮的三道检查，次序写死）。Python 侧把三道检查与编译抽成 `kit_logs._compile_search`（行为不变，109 条测试照过）。`@themis/dispatcher/logs-search`：safe_lines 与 cmd_search。第一版编成 JS 正则，Node 下对照全过，到 Bun 下才撞上 JavaScriptCore 的前瞻缺陷与原子组的语义差别，改成移植匹配器（r3 §10 与 AGENT_LEARNINGS 有记录）。对照：CPython `test_re.py` 的 1265 个字面量语法分析逐字一致；搜索语料 1.85 万项、随机模式 8 组 47 万项，Python 与 TS 结果一致（Bun 全跑，Node 跑了语料与其中 4 组）；仓库里的对照测试（手挑的 79 个写法 × 40 段文本，两种随机生成各 3 个种子 × 400 个模式，Python、Node、Bun 三方比较）。契约：logs search 的用例 20 个（文本与 JSON、截断、跳过计数、报错原文、崩溃、`--max`、`--task`、sre 的前缀怪癖），stdout 逐字节一致，`--json` 过 logs-search-v1。性能：2000 万字节、4.9 万行的合成日志上，10 种常见写法里慢的约 3 倍（`(?:read|edit) src/\w+\.ts` 223 对 73 毫秒），快的比 Python 还快（`\bfail(?:ed|ure)\b` 58 对 156 毫秒）。变异：正则 32 个，抓住 30 个，2 个声明等价（没有大小写的字面量与字符集要不要小写化：逐个码点核对过 `\w`、`\d`、`\s` 与 sre 的小写映射）；logs search 8 个全部抓住 | 完成 | 见提交说明 |
| ②c | `logs usage`。`@themis/base/pydatetime`：`datetime.fromisoformat` 的 C 实现（CPython 3.12.10 `_datetimemodule.c`，Python 实际用的就是它，不是 `_pydatetime.py`）逐段移植，在 UTF-8 字节上按 C 字符串解析，怪癖照搬并逐条在 Python 上实测过：秒后面的冒号当小数（`10:00:00:5` 是 0.5 秒）、小数点后一位都没有也收、`Z` 后面跟 NUL 当结尾、分隔符可以是任意字符（多字节按首字节跳过）、时区偏移的秒为零时连带的微秒丢掉、偏移的分钟不查上限（`+00:99`）；加 kit_logs._parse_iso 的换算（结尾 Z、必须带时区、换成 UTC、溢出为不可用）。`@themis/dispatcher/logs-usage`：执行端（events-summary.json 的 known、partial、unknown，按模型合计，计数一律 bigint）与规划端（会话记录逐行读、按消息 id 归组、重复与两种冲突、未完成、时间窗、坏行与非候选的计数、按模型与是否子代理合计）。对照：pydatetime 手挑 62 个写法加 4 个种子各 3000 个随机串，Python、Node、Bun 一致；logs usage 的契约用例 11 个，stdout 逐字节一致，`--json` 过 logs-usage-v1；真实数据：主仓库的 runs 加本机 119 MB 的会话记录，6 组参数在 Node、Bun 下共 12 次调用逐字节一致。变异：pydatetime 15 个、logs usage 16 个全部抓住（起初各漏一个：分隔符以外的代理字符、带 usage 的空 id，补了用例） | 完成 | 见提交说明 |
| ②-切换 | 选择文件 `scripts/kernel-impl.json` 的 `readonly` 改成 `ts`（r3 §10 第 64 轮）。启动器照第 ② 步“转交给 TS 的启动器”：转交名单写死、检查次序（名单、discover、TS 入口、装好戳记、Bun 路径）、`--pyargs-b64`、句柄直接继承、带 KILL_ON_JOB_CLOSE 的 Job、退出码原样；Bun 固定带 `--no-env-file` 与 `--config=ts/bunfig.toml`，子进程环境去掉运行时注入变量。装好戳记由 `ts/package.json` 的 postinstall 写，第 61 轮的后台回归在戳记过期时于落地锁里重装。`meta.json` 记 `impl` 与冻结的 `kernel_protected`，账本的 `dispatcher.called` 记 `impl` 与 `tool_version`。测试：`tests/test_kernel_impl.py` 70 条（选择文件的严格解析、名单与参数键、检查次序、启动器四条、六种注入各一条并带对照组、回退逐字节、禁区与同目录判断）；hub 新增 5 条；readonly 契约用例全部加上经真的启动器的端到端（87 条全过）；全量 pytest 在藏起装好戳记时照过（2578 passed，test_dispatch.py 另 50 passed），说明没有测试依赖 TS 装没装。变异 36 个全部抓住（第一轮漏 2 个：规格的 `-k` 漏选一条、回退测试两边走同一份坏代码，补断言后抓住） | 完成 | 见提交说明 |
| ③ | 配置中心 | | |
| ④a | Windows 进程监督的验证 | | |
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
