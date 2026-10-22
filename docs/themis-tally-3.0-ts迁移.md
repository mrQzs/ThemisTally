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

**与 quizs 共用**：
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
    - 语法树编译成带 u 标志的 JS 正则：`\w`、`\d`、`\s`、`\b` 用第 ① 步的区间表，`$`、`\Z`、`\A`、`(?m)`、`(?s)` 照 pyre 的写法；原子组与占有量词用 `(?=(…))\k<名字>` 模拟；后顾按 getwidth 判定，不定宽照 Python 报错；
    - `\N{name}` 支持：用 unicodedata 生成 15.0 的名字表（含别名），查找规则照 unicodedata.lookup，表的体积写进提交说明；
    - 反向引用（`\1`、`(?P=name)`）与条件分组（`(?(id)yes|no)`）JS 复现不了“有没有匹配”，两套实现都改成拒绝：另开一个内核轮次，Python 先改——cmd_search 编译之前用 `re._parser.parse` 走一遍语法树，遇到 GROUPREF、GROUPREF_EXISTS 报一句固定的错，退出码与非法正则相同（`re._parser` 是私有模块，环境里的 Python 固定为 3.12.10，在代码里注明）；同一轮把括号嵌套深度定成显式上限（超过就报固定的错），让 Python 碰不到取决于栈深的 RecursionError；MAXREPEAT、MAXGROUPS 引起的 OverflowError 是确定的，照原样移植。这算行为变更，第 10 节与桌面端文档的搜索框说明都要记；
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
  - 找 Bun 要确定：npm 只在 PATH 上放 `bun.cmd`，Python 不经 shell 起子进程认不出它，hub 的 kernel_env 还会过滤环境变量。用 `bun.exe` 的绝对路径：在 `.agent/dispatch.local.json` 里登记（`config runtime add` 那一套，本机文件、不提交），或按 `bun.exe` 查找。找不到就报错退出，不悄悄退回 Python，与选择文件的严格解析同理。
  - 原样转交：stdin、stdout、stderr 按字节透传，不重新编码；退出码原样返回。
  - 连带结束：TS 子进程放进带 KILL_ON_JOB_CLOSE 的 Job，复用 `run_supervised` 那一套。`run_pd` 超时只杀直接子进程（Python 启动器），不放进 Job，Bun 孙进程会成孤儿接着跑。
  - 环境一致：TS 子进程拿到的环境变量，与这条命令走 Python 时完全相同，不多不少。
- **切换**：三片都达到出口条件之后，一次提交把选择文件（第 5 节）的 `readonly` 改成 `ts`，照内核轮次走。同在这一次的：选择文件、`meta.json` 的 `impl`、指纹与执行器禁区的改动；启动器四条各一条测试（找不到 Bun 报错、字节透传与退出码、杀掉启动器后 TS 子进程随之消失、环境变量一致）；选择文件的严格解析测试（不存在等于全部 `python`，格式错就拒绝运行）。
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
- **随 kit 安装**：跟内核代码一起提交，算进指纹。
- **怎么改**：每次切换都是一次提交，在 kdev 里改、测试、照第 9 节的流程合入，不在主工作区直接改。提交说明写明切了哪个组件、出口条件的证据。
- **回退**：把对应的值改回 `python`，再提交一次。
- **自动换代**：内核文件指纹（`kit_hub.py:161-201`）把选择文件、两套入口（`kit_hub.py`、`pi_dispatch.py`、`ts/packages/*/src/**`）都纳入。哪一个变了，runner 都在两步之间按选择文件重新起。指纹只认选择文件指定的那一套入口作为“运行中的内核”。
- **执行器的禁区**：TS 代码一旦进入生产路径（第 ② 步起），`pi_dispatch.py` 的 `KIT_LOADED_FILES` 与 `PROTECTED_PATTERNS` 就要加上 `ts/packages/**` 与 `scripts/kernel-impl.json`。在那之前，执行器碰 `ts/` 只算普通改动，照合同的 Scope 管。

---

## 6. kit_install 的变化

| 阶段 | 装进目标仓库的东西 | 说明 |
|---|---|---|
| 现在到第 ⑤ 步 | 照旧：Python 文件与数据文件（`KIT_LOADED_FILES`、`scripts/hub/`、`plugins/decisions/` 等） | TS 部分只在本仓库开发，不随 kit 安装 |
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
   - TS：`ts/` 下 `vitest run` 与 `tsc`。
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
| Python `json.dumps` 与 JS 的差别（第 1.4 节） | 摘要对不上，证据绑定与信件 sha256 失效 | `pyjson` 逐字节对照，专门的浮点、大整数、码点排序用例 |
| 时间与编号的格式（`utc_now`、msg-id、turn id） | 两套实现写出的记录不能互认 | 第 ① 步之后补进 `base`，按契约对照 |
| Bun 在 Windows 上的成熟度；`bun:ffi` 是实验性 | 第 ④ 步卡住 | 先做 ④a 的验证；Node 后备一直保留 |
| npm 装的 Bun：`bun.exe` 不在 npm 的 bin 目录 | 子进程不经 shell 启动 `bun` 会失败（样板实测） | 已把 `bun.exe` 的目录加进用户 PATH，记进 `.agent/environment.md` |
| 两套实现同时写一个信箱或证据目录 | 并发语义不一致会丢信或覆盖证据 | 发布、锁、账本都有混跑的并发用例（样板已有） |
| Node 后备的原生操作（文件锁，以后还有 Job Object）仍要靠 Bun 跑辅助进程 | 没装 Bun 时 Node 后备拿不到文件锁 | 第 ⑥ 步之前，真正的退路是 Python 实现；第 ⑥ 步之后辅助进程是同一个单文件程序的 __native 子命令 |
| 执行器在 TS 代码进入生产路径后改动它 | 绕过内核 | 第 5 节：第 ② 步起把 `ts/packages/**` 加进执行器禁区 |
| quizs 的设计文档还没出 | 共用包的名字与协议边界可能要改 | 第 ⑤ 步之前不碰内核与 worker 的协议；包名改动只是重命名 |
| 只读命令遇到坏证据就打堆栈退出（现行 Python）：`status` 读到的 meta.json、run.json、checks.json 等不是对象（`.get` 抛 AttributeError），checks 的 results 不可迭代或项不是对象，verdicts 下有不是数字的 `*.json`（`int()` 抛 ValueError），run-started.json 的 started_at 是真值却不是字符串（TypeError），证据 JSON 嵌套太深（`read_json_or` 不接 RecursionError） | 退出码 1、堆栈进 stderr；TS 照样退出码 1，契约只比较退出码 | 以后开一轮改成干净的 ERROR 行，TS 跟着改（themistally-15，2026-10-22） |
| `logs show` 的显式相对路径：Python 拿“当前目录拼出来、没解析过”的路径逐段对照“解析过的 runs 根” | 当前目录带 8.3 短名（例如 `ADMINI~1`）时，指向 runs 之内的相对路径也报“不在 runs 根之下”（第 ②a 步的契约实测） | TS 照样；要修另开一轮（两边一起改成先解析再比较） |
| 路径语义的细差（TS 的 `pypath.ts`） | Windows 上 Python 3.12 的 normcase 用 LCMapStringEx 的不变区域小写，TS 用 toLowerCase；abspath 的 GetFullPathNameW 会去掉段尾的点与空格，`path.resolve` 不去 | 只在路径含特殊大小写字符、或段尾有点与空格时才可能不同；遇到再补 |
| Node 后备认不出一部分重解析点 | Python 把 Windows 上一切带 REPARSE_POINT 属性的条目都当链接；Bun 经 GetFileAttributesW 一致，Node 后备只用 lstat，认不出云文件占位、AppExecLink 这类 | 第 ⑥ 步之前 Python 一直是退路；需要时让 Node 后备经 `__native` 辅助进程批量查属性 |
| `logs search` 的 PATTERN 是用户可控的正则 | 灾难性回溯：JS 正则与现在的 Python 一样中断不了 | 启动器的 Job 加超时、超时结束整棵进程树；将来的本机服务调 logs search 一定要设超时（themistally-15，2026-10-22） |
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
| ②b2 | `logs search`（含 Python re 的语法分析移植，范围见第 ② 步） | | |
| ②c | `logs usage` | | |
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
