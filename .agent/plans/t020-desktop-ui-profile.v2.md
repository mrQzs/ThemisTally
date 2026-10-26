# TASK: t020-desktop-ui-profile

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: 97c6ae0e22693cb96185665f0d7f5efb9d18505c
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
桌面端本机服务（`ts/packages/ui`）接进 profile 与 runtime 的五条写路由（`profile.add|edit|remove`、`runtime.add|remove`），预览正文顶层键与 args 同样严格，把写命令集合收紧到内核真正支持 `--dry-run` 的 12 条并显式列出不开放的写命令，给「令牌不外泄」加表驱动的回归保护，并让由内核子进程应答的请求（19 条读路由、预览、12 条写路由）在各自的路由时限内不被 Bun 的连接空闲超时断开；README 与这些行为同步。

## Non-goals
- 不做凭据录入作业、`/control/jobs/<id>/cancel`、控制门泛化（归 T021）。
- 不做前端的确认框与重读（W3、W3b）。
- 不做「花钱或集成」一档的路由。
- 不新增内核的命令或选项（清空 `credential_env` 要内核另开一个选项，由站主另开一轮）。
- 不改 `ts/packages/ui/src/localhttp/**`、`ts/packages/ui/src/readroutes.ts`、`UiArgs`、`package.json`，不加依赖；不碰 `desktop/**`、`docs/**`、内核代码、`scripts/**`。
- 不改设计稿里的路径同步（归规划端在落地之后）。

## Repository facts
- 入口：`ts/packages/ui/src/writeroutes.ts`（`WRITE_ACTIONS`:69、`WRITE_ARGV`:84、`T020_WRITE_COMMANDS`:96、`validValue`:152、`validateWriteArgs`:172、`buildWriteArgv`:191、`mergeArgs`:270、`previewRoute`:283、`executeWrite`:371、`writeRoutes`:408）、`ts/packages/ui/src/server.ts`（`ServeOverrides`:24、`bunServer.timeout(request, 0)`:103、`extraRoutes`:144、`isEventsRequest`:248）、`ts/packages/ui/src/routes.ts`（`findRoute(method, pathname, extra)`）。
- 调用关系与现有约定：`server.ts` 把四批路由合成一批交给 `createApp`（19 条读路由 + SSE + 作业 + 写路由）；写链路的形状是「预览 → 确认号 → 带令牌执行 → 操作终态」，预览与七条写路由共用同一个 `validateWriteArgs`/`buildWriteArgv`；预览响应把内核预览 JSON 里的顶层 `state` 拿掉（`dropState`），显示用的 argv 由 `displayArgv` 把 `--expect-state=` 换成 `--expect-state=<state>`；`kernelEnv()` 从服务进程的 `process.env` 复制环境给内核子进程（去掉 `TYPESAFE_API_KEY`、加 `CODEKIT_ACTOR=user-ui`）。
- 工具链与锁文件：`ts/` 下 Bun + Vitest（`node node_modules/vitest/vitest.mjs run packages/ui/test`），类型检查 `node node_modules/typescript/bin/tsc -p tsconfig.json`；依赖用 `bun install --frozen-lockfile` 装，锁文件 `ts/bun.lock` 不许改；真内核是 `scripts/pi_dispatch.py`（Python），替身是 `ts/packages/ui/test/fixtures/fake-write-kernel.mjs`（Node 跑）。
- 基线检查：R01 的 19 个门禁文件在 `00a648ccf9` 上全过（站主核实：退役两条 T019 断言后 `tests/test_gate_t019_baseline.py` 的 16 条静态断言全过）。本片的新门禁 `tests/test_gate_t020_baseline.py` 在基线上不存在，基线应失败（G01）。

## Scope
- allowed_modified_files:
  - ts/packages/ui/src/writeroutes.ts
  - ts/packages/ui/src/server.ts
  - ts/packages/ui/test/harness.ts
  - ts/packages/ui/test/write-argv.test.ts
  - ts/packages/ui/test/write-routes.test.ts
  - ts/packages/ui/test/write-real.test.ts
  - ts/packages/ui/test/fixtures/fake-write-kernel.mjs
  - ts/packages/ui/README.md
  - ts/packages/ui/test/slow-request.test.ts
  - ts/packages/ui/test/write-config.test.ts
  - ts/packages/ui/test/write-real-config.test.ts
- allowed_new_files:
  - ts/packages/ui/test/write-config.test.ts
  - ts/packages/ui/test/write-real-config.test.ts
  - ts/packages/ui/test/slow-request.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t020_*.py
  - ts/packages/ui/src/localhttp/**
  - ts/packages/ui/src/readroutes.ts
  - desktop/**
  - docs/**
  - scripts/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 五条写路由（新增）

路由名与路径（POST，都要会话、要 CSRF 头、正文是 JSON 对象）：

| action | 路由名 | 路径 | 路径参数键 |
|---|---|---|---|
| `profile.add` | `api.profiles.add` | `/api/v1/profiles/<id>/add` | `profile` |
| `profile.edit` | `api.profiles.edit` | `/api/v1/profiles/<id>/edit` | `profile` |
| `profile.remove` | `api.profiles.remove` | `/api/v1/profiles/<id>/remove` | `profile` |
| `runtime.add` | `api.runtimes.add` | `/api/v1/runtimes/<id>/add` | `runtime` |
| `runtime.remove` | `api.runtimes.remove` | `/api/v1/runtimes/<id>/remove` | `runtime` |

五条走与现有七条完全相同的一条链：预览（`POST /api/v1/preview`，正文 `{action, args}`）→ 43 位确认号 → 带确认号执行 → 操作表落一条八键记录（`GET /api/v1/operations/<id>`）。执行是基础 argv 加 `--expect-state=<state>`（预览给的 state 令牌原样带上），预览的 `needs_yes` 为真才加 `--yes`；时限 90 秒（`api.write`），预览 30 秒（`api.preview`）；退出 0 → 200，退出 4 → 409 七字段信封、操作记 `stale`，其他非 0 → 200、`ok` 为假、操作记 `failed`。

路径参数压过正文里的同名键（照 `mergeArgs` 原样：路径参数后写、覆盖正文）。正文里的 `confirmation` 不进 args。

### 必填键、可选键与命令行模板

| action | 必填 | 可选 | 基础 argv |
|---|---|---|---|
| `profile.add` | `profile`（路径）、`runtime`、`model` | `thinking`、`credential_env` | `config profile add <profile> --runtime=<r> --model=<m> [--thinking=<t>] [--credential-env=<名>]…` |
| `profile.edit` | `profile`（路径） | `runtime`、`model`、`thinking`、`credential_env` | `config profile edit <profile> [--runtime=] [--model=] [--thinking=] [--credential-env=<名>]…` |
| `profile.remove` | `profile`（路径） | — | `config profile remove <profile>` |
| `runtime.add` | `runtime`（路径）、`adapter` | `command`、`force` | `config runtime add <runtime> --adapter=<a> [--command=<JSON.stringify(command)>] [--force]` |
| `runtime.remove` | `runtime`（路径） | — | `config runtime remove <runtime>` |

选项的值一律写成 `--opt=值`（不另起一个参数）；**选项次序固定**：`profile.add` 是 `--runtime`、`--model`、`--thinking`、`--credential-env`（重复几项就几次）；`profile.edit` 是 `--runtime`、`--model`、`--thinking`、`--credential-env`；`runtime.add` 是 `--adapter`、`--command`、`--force`；`credential_env` 保持请求里的次序；`--force` 是不取值的开关，只在 `force` 为真时出现。`--command` 的值是 `JSON.stringify(command)` 的结果，argv 里那一项恰为 `--command=` 加该串（不多不少、不加引号、不转义）。

基础 argv 里绝不出现 `--dry-run`、`--json`、`--expect-state`、`--yes`（预览与执行分别在外面加）。

### 各键的校验（在 `validValue` 里做）

提示固定为 `<键> 不合法`，不回显请求里的值；不合格不起子进程。

| 键 | 规则 | 出处 |
|---|---|---|
| `profile`、`runtime` | `TASK_ID_RE`（`^[a-z0-9][a-z0-9-]{0,63}$`） | `@themis/base/secrets` 的 `TASK_ID_RE`；内核 `kit_roles.py` 的 `_id_ok` |
| `model` | 字符串；在第一个 `/` 处切成两段，两段都过 `MODEL_TOKEN_RE`（`^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$`） | `scripts/pi_dispatch.py:86`（照抄并注明出处） |
| `thinking` | 七选一：`off`、`minimal`、`low`、`medium`、`high`、`xhigh`、`max` | `scripts/pi_dispatch.py:95` |
| `credential_env` | 非空数组，每项过 `allowEnvName`（`ENV_NAME_RE` 且不像令牌）；**不去重、不设个数上限** | `@themis/base/secrets` 的 `allowEnvName` |
| `adapter` | 四选一：`pi`、`claude-code`、`codex`、`opencode` | `scripts/kit_roles.py:45` 的 `ADAPTERS` |
| `command` | 非空数组，每项 `cleanText(item, 1, 1024)`：非空、不超过 1024 码点、不含控制字符与孤立代理项 | 照 `writeroutes.ts` 现有的 `cleanText` |
| `force` | 只认 `true` | 同 `preset.save` 的 `force` |

`profile.edit` 一个可选项都不给：服务照形状放行（`profile` 是路径参数，算给过了），内核预览退出 2、提示「至少给一项」；服务回 200、`ok` 为假、不发确认号。这条组合规则交给内核。

绝对路径与疑似凭据交给内核（内核 `_parse_command` 判定），服务不另写规则。

### `credential_env` 的三种写法

- **缺省**（args 里没有这个键）：argv 不带 `--credential-env`，内核不改这一项。
- **非空数组**：每项一个 `--credential-env=<名>`，内核整份替换。
- **空数组**：400「credential_env 不合法」，不起子进程。理由：内核没有清空的写法（给空串会变成 `[""]`，被内核整份校验拒掉）。README 的「已知限制」要写这一句；真要清空由站主另开一轮给内核加选项。

### 预览正文的顶层键

`POST /api/v1/preview` 的正文是对象时，**顶层键只许 `action` 与 `args`**；多出任何键 → 400「参数含有未知键」，在 `validateWriteArgs` 之前判，不起子进程。

既有的两条提示原样保留：缺 `action` → 「action 不合法」；缺 `args`（或 args 不是对象）→ 「请求体必须是 JSON 对象」。

### U4 收紧：开放的 12 条与不开放的名单

`WRITE_ACTIONS` 收 12 个 action：`role.set`、`preset.use`、`preset.save`、`preset.remove`、`config.rollback`、`plugin.enable`、`plugin.disable`、`profile.add`、`profile.edit`、`profile.remove`、`runtime.add`、`runtime.remove`。

`writeroutes.ts` 导出两个常量：

- `OPEN_WRITE_COMMAND_PATHS`：开放写命令的命令路径，恰好 12 条，每条一个字符串：`config role set`、`config preset use`、`config preset save`、`config preset remove`、`config rollback`、`plugins enable`、`plugins disable`、`config profile add`、`config profile edit`、`config profile remove`、`config runtime add`、`config runtime remove`。
- `NOT_OPEN_WRITE_COMMANDS`：不开放的写命令，每条一个对象 `{ path: readonly string[], reason: string }`，每条写一行理由：

| 命令路径 | 理由 |
|---|---|
| `config set` | 任意键写入，没有 `--dry-run` 与 `--expect-state`，无从预览，也无从比对令牌。 |
| `config unset` | 同 `config set`。 |
| `config init` | 首次从示例生成配置，已存在就拒绝；归首次运行与 CLI，没有预览。 |
| `config decisions` | 决策模式的开关，没有预览与令牌；要开放，先由站主给内核加 `--dry-run`。 |
| `config runtime scan` | 批量登记（`--add`），没有预览；设计稿定为「扫描结果逐个登记，一次确认一条 runtime add」，界面走 `runtime.add`。 |
| `config secret` | 凭据。`set` 是凭据录入作业，归 T021；`remove` 没有预览与令牌。 |
| 调度器顶层命令（`prepare`、`run`、`verdict` 等） | 属于「花钱或集成」一档，不在配置写命令的比对范围里。 |

`T020_WRITE_COMMANDS` 这个导出删掉，README 里提到它的地方一并改掉。

三条可核对的判据（W2 用例）：
1. 内核里带 `--dry-run` 的写命令集合（用 `scripts/kit_config.py` 与 `scripts/kit_plugins.py` 的 `build_parser()` 递归枚举子命令，取带 `--dry-run` 的那些）与 `OPEN_WRITE_COMMAND_PATHS` 逐条相等，恰好 12 条。
2. `NOT_OPEN_WRITE_COMMANDS` 每条的命令路径都不在那个集合里（拿它的示例 argv 加 `--dry-run` 过内核真正的解析器，必须被拒）。
3. `NOT_OPEN_WRITE_COMMANDS` 的命令路径与 `OPEN_WRITE_COMMAND_PATHS` 不相交。

`WRITE_ARGV` 新增五条示例（其余行不动；`role.set` 仍保留两行示例，表里共 13 行、命令路径去重后 12 条）：

```
"profile.add":   ["config", "profile", "add", "demo-profile", "--runtime=demo-runtime", "--model=demo-provider/demo-model", "--thinking=high", "--credential-env=DEMO_API_KEY", "--credential-env=OTHER_KEY"]
"profile.edit":  ["config", "profile", "edit", "demo-profile", "--model=demo-provider/demo-model", "--credential-env=DEMO_API_KEY"]
"profile.remove":["config", "profile", "remove", "demo-profile"]
"runtime.add":   ["config", "runtime", "add", "demo-runtime", "--adapter=pi", "--command=[\"C:/tools/pi.exe\",\"--flag\"]", "--force"]
"runtime.remove":["config", "runtime", "remove", "demo-runtime"]
```

### 两资源令牌

| 命令 | 令牌覆盖的资源 |
|---|---|
| `runtime add` 带 `--command` | config 与 local：`v1;config=<C>;local=<L>` |
| `runtime add` 不带 `--command` | 只有 config：`v1;config=<C>` |
| `runtime remove` | 总是带上 local；本机文件不存在时是 `local=absent` |

其余十条（`role.set`、`preset.*`、`config.rollback`、`plugin.*`、`profile.*`）的令牌只有 config 段。令牌形状由内核给，服务这一侧只按 `STATE_RE`（`^v1(?:;(?:config|local)=(?:[0-9a-f]{64}|absent))+$`）核对。

### 令牌不外泄的回归保护

一张 12 行的表：每行一个 action、一份合法的 args。替身对每一行给的预览 `action` 与本行相同、`state` 每行不同（每段用不同的 64 位小写十六进制；`runtime.add`（带 command）与 `runtime.remove` 给 `v1;config=<C>;local=<L>`，其余给 `v1;config=<C>`）。每行查四样：

1. 预览响应的整份正文（原始 UTF-8 文本，不解析）：令牌的**每一段** 64 位十六进制都不许出现，整条令牌也不许出现。
2. 执行响应的整份正文：同上。
3. `GET /api/v1/operations/<id>` 的整份正文：同上。
4. 替身报告里执行那一支的 `expect_state` 与整条令牌**逐字相同**（这一条杀「只带 config」）。

### 空闲超时

由内核子进程应答的请求（19 条读路由、`POST /api/v1/preview`、12 条写路由）在各自的路由时限内不被 Bun 的连接空闲超时断开：服务对**这一条请求**调 `server.timeout(request, 0)`，全局 `idleTimeout` 生产路径保持缺省。

判定方式：`server.ts` 的 `fetch` 里（与 `isEventsRequest` 同一处、在 `app.fetch` 之前）判断请求命中的是不是 `readRoutes()` 或 `writeRoutes()` 那两批路由，命中就对这一条请求调一次 `bunServer.timeout(request, 0)`。判定用 `routes.ts` 的 `findRoute(method, pathname, 那两批)`，不另抄一份路径表；那两批路由在 `bun.serve` 之后才建，判定要迟绑定（建好之前不判定，避免 TDZ 报错）。

不受影响：作业（创建时就回 201）、SSE（已经对这一条连接关掉了空闲超时）、控制接口、静态资源、ping（都很快）。

不用有限 n 的理由（不改这个取舍）：处理函数本来就有界（路由时限到点，内核子进程先 CTRL_BREAK、宽限 2 秒、再结束整棵树），排队时间不在路由时限里，未认证的请求在 401 之前也会被放宽——这与 SSE 现在的写法一致。

### 兼容性与不变的部分

- 现有七条写路由的行为、提示原文、时限、确认号与操作表的形状一律不变；读路由逐字节不变。
- `server.ts` 里不许给 `idleTimeout` 写数字字面量（T017 门禁）；`bunIdleTimeoutSeconds` 仍只由 `ServeOverrides` 覆盖。
- `readroutes.ts` 里不许出现 WRITE（T019 门禁），本片不改它。
- 替身不回显令牌（真内核也不回显）。

## Steps

1. **读基线**：读 `ts/packages/ui/src/writeroutes.ts`、`server.ts`、`routes.ts`、`kernelenvelope.ts`、`ts/packages/ui/test/harness.ts`、`write-argv.test.ts`、`write-routes.test.ts`、`ts/packages/ui/test/fixtures/fake-write-kernel.mjs`、`ts/packages/ui/README.md`，以及 `scripts/kit_config.py`、`scripts/kit_roles.py`、`scripts/pi_dispatch.py` 里对应用例，确认本合同的行号与签名一致；不一致就停下报告，不要照抄本文的行号。
   - 意图：不按旧基线的行号改代码。
   - 验收：Repository facts 里每一项都能对上。
   - 风险：低。
2. **登记与校验**（`writeroutes.ts`）：五条进 `WRITE_ACTIONS`；`validValue` 加 `profile`、`runtime`、`model`、`thinking`、`credential_env`、`adapter`、`command`、`force` 八个键；`buildWriteArgv` 加五个分支（选项一律 `--opt=值`、次序固定、`--command` 用 `JSON.stringify(command)`）；`WRITE_ARGV` 加五条示例；删掉 `T020_WRITE_COMMANDS`；加 `OPEN_WRITE_COMMAND_PATHS`（12 条）与 `NOT_OPEN_WRITE_COMMANDS`（每条带理由）。
   - 验收：`write-argv.test.ts` 的 W1（12 条示例 argv 过内核真正的解析器：`--dry-run --json`、`--expect-state=`、`--yes`）、W2（开放集合 = 内核 `--dry-run` 集合 = 12 条；不开放名单每条都被内核解析器拒绝、与开放集合不相交）、W3（基础 argv 不含那四个开关）、W4（每一类不合格：空数组的 `credential_env`、令牌形状的 `credential_env`、`model` 少一段、`thinking` 不在枚举、`command` 含控制字符或超长、`adapter` 不在四选一、`force` 非真、`profile`/`runtime` 不合 `TASK_ID_RE`；每条都回固定提示、不回显值）。
   - 风险：`write-argv.test.ts` 现有的 W2（期望集合取自 `T020_WRITE_COMMANDS`）与 W4（断言五个 T020 action 名不合法）必须一起改，否则旧断言会红。
3. **五条路由**（`writeRoutes()`）：照 presets 的写法，一条 action 一条路由（名字与路径照 Behavior contract 的表），路径参数键名 `profile` 与 `runtime`。
   - 验收：`write-config.test.ts` 的替身用例——每条都能预览、执行，并在操作表里落一条记录。
   - 风险：低。
4. **预览正文的顶层键**：多出顶层键 → 400「参数含有未知键」，在 `validateWriteArgs` 之前判，不起子进程；缺 action/缺 args 的两条提示原样保留。
   - 验收：替身的 report 里没有 begin 行（没起过子进程）。
   - 风险：低。
5. **`credential_env` 的三种写法与空数组**：缺省不带 `--credential-env`；非空数组每项一个 `--credential-env=<名>`；空数组 400「credential_env 不合法」。
   - 验收：同上（argv 逐字比对 + 空数组的 400 与不起子进程）。
   - 风险：低。
6. **空闲超时修复**（`server.ts`）：按 Behavior contract 的「空闲超时」一节，对命中 `readRoutes()`/`writeRoutes()` 两批路由的请求调一次 `bunServer.timeout(request, 0)`；判定用 `findRoute`，迟绑定；全局 `idleTimeout` 保持缺省、文件里不许出现 `idleTimeout` 的数字字面量。
   - 验收：第 9 步的慢请求用例（真 Bun、生产 `Bun.serve` 选项）。
   - 风险：T017 门禁 `test_static_bun_idle_timeout` 与 T019 门禁 `test_static_server_wiring` 都查 `server.ts` 的形状（`writeRoutes`/`readRoutes`/`eventRoutes`/`jobRoutes` 四个记号、`IdleTimer` 在 `createApp` 之前、`hub.close()` 在 `runner.shutdown()` 之前），改的时候别动这些位置。
7. **harness 加环境变量参数**（`test/harness.ts`）：`StartOptions` 加 `env`，只合进服务子进程的环境，不改 vitest 进程的 `process.env`。
   - 验收：慢请求用例靠它把替身的门文件与睡眠时长传给服务（内核子进程的环境来自 `kernelEnv()`，读的是服务进程的 `process.env`）。
   - 风险：低。
8. **扩展替身**（`test/fixtures/fake-write-kernel.mjs`）：
   - 保留 T019 门禁点名的记号（`FAKE_KERNEL_REPORT`、`FAKE_WRITE_PREVIEW`、`FAKE_WRITE_PLAN`、`FAKE_WRITE_GATE`、`FAKE_WRITE_BEGIN`、`--dry-run`、`--expect-state`、`ok`/`stale`/`audit-fail`/`pause`）与 §2.1 那份预览 JSON 的默认行为。
   - 预览一支（argv 里有 `--dry-run`）：`action` 由 argv 推导（`config profile add` → `profile.add`，`config profile edit` → `profile.edit`，`config profile remove` → `profile.remove`，`config runtime add` → `runtime.add`，`config runtime remove` → `runtime.remove`；`role set` → `role.set`，`preset use|save|remove` → `preset.use|save|remove`，`config rollback` → `config.rollback`，`plugins enable|disable` → `plugin.enable|disable`），`state` 按上表给（`runtime.add` 带 `--command` 与 `runtime.remove` 给 config+local 两段，其余只 config 段；每条 action 的段值各不相同，确定性生成即可），`needs_yes` 为假；`role.set` 仍用既有那份默认预览。
   - 读一支（argv 里有 `--json` 且没有 `--dry-run`）：打一份 JSON（`{}` 即可），让读路由回 200。
   - 执行一支（其余）：照 `FAKE_WRITE_PLAN` 走，行为不变。
   - 慢门：新记号 `FAKE_WRITE_SLOW_GATE`（门文件路径）与 `FAKE_WRITE_SLEEP_MS`（毫秒，缺省 15000）。门文件存在时，每次调用先睡 `FAKE_WRITE_SLEEP_MS` 再干活；门文件不存在时不睡（这样「先预览拿号」很快，三条并发时才都睡）。
   - 照旧记 begin、end 与退出码；不回显令牌。
   - 验收：替身的 report 里 begin/end 齐全、`expect_state` 逐字等于整条令牌。
   - 风险：低。
9. **慢请求用例**（新文件 `test/slow-request.test.ts`）：
   - 起服务：`startService({ entry: "overrides", overrides: {}, python: process.execPath, kernel: <替身>, env: {...} })`；`overrides` 只传 `{}`，**不传** `bunIdleTimeoutSeconds` 与 `timeouts`，走生产的 `Bun.serve` 选项。
   - 先预览拿确认号（这时门文件还不存在，不睡）；再创建门文件；然后三条并发：`GET /api/v1/roles`、`POST /api/v1/preview`、`POST /api/v1/roles/execution`（带确认号）。
   - 断言：三条都拿到完整响应（状态 200、信封能解析成七个字段）；替身 report 里这三次调用的 begin 都有对应的 end、退出码 0（没被取消）。
   - 用例时限 90 秒（整组约 15 秒多一点，不靠机器够快）。
   - 验收：这条用例在「去掉修复」时必须红（替身睡 15000 毫秒 > Bun 缺省空闲超时的断开点）。
   - 风险：Bun 缺省空闲超时实测在第 8 到 12 秒之间断开（站主 20261025 实测两次：12 秒与 9 秒，curl 52，服务端打 “Bun.serve() timed out a request after 10 seconds”）；替身睡 15 秒留了 3 秒余量。同一服务里对这一条请求调 `srv.timeout(req, 0)` 时，15 秒后客户端完整拿到响应（curl 0）、`request.signal` 没有 abort；对照组不调的那条第 9 秒被断开。keep-alive 上会不会延续没测，本片不依赖这一点。
10. **替身用例**（新文件 `test/write-config.test.ts`，进程内建 app，照 `write-routes.test.ts` 的写法）：
    - 五条路由各自能预览、执行、查到操作记录。
    - `credential_env`：空数组 400、令牌形状的 400（都不起子进程）。
    - `command`：拼出的 argv 恰为 `--command=` 加 `JSON.stringify(command)`，`JSON.parse` 出来逐项相等；例子要含空格、反斜杠、以 `-` 开头的项。
    - 预览正文多出顶层键：400，且 report 里没有 begin 行。
    - 令牌整份搜：Behavior contract「令牌不外泄」那 12 行 × 4 查法。
    - 验收：12 行每一行的四查全过；报告的 `expect_state` 与整条令牌逐字相同。
    - 风险：令牌段的十六进制值必须两两不同，否则「搜不到」没有意义。
11. **真内核用例**（`test/write-real-config.test.ts`，或在 `write-real.test.ts` 里加一个 describe）：
    - (a) `profile add`：预览加执行都过，审计里的 actor 是 `user-ui`。
    - (b) `runtime add --command` 的 U6b：预览后用 CLI 改 `.agent/dispatch.local.json`，执行回 409、`exit_code` 是 4；`snapshotAgent()` 前后相同，两个文件与审计逐字节不变；操作记 `stale`。
    - (c) `runtime add --command` 成功：本机文件里的 `command` 与请求逐项相同，路径含反斜杠与空格（同时核对 Windows 命令行引号：内核按 MSVCRT 的规则给双引号与反斜杠加引号，`--command=["C:\\a b\\pi.exe"]` 要原样到达 Python）。
    - (d) U22：夹具用 CLI 建一个带 `credential_env` 的 profile；`GET /api/v1/profiles` 读到的 `credential_env` 原样回填进 `profile.edit`，预览加执行都过，配置里的值与提交的相同。
    - 验收：四条都过；用例只在本仓库的临时仓库里写文件，不碰真实配置。
    - 风险：中（真内核会写配置与审计），夹具必须用临时仓库。
12. **README**（`ts/packages/ui/README.md`）：
    - 「最小 API」一节加五条写路由。
    - 「写操作」一节改成 12 条写路由，写清 profile 与 runtime、两资源令牌（带 `--command` 是 config+local、不带只有 config、`runtime remove` 总带 local）、`credential_env` 的三种写法（缺省 / 非空数组 / 空数组 400「credential_env 不合法」）、五条 action 的必填可选与命令行模板。
    - 第 108 行那条「连接空闲超时」改成：SSE 订阅与由内核子进程应答的请求（19 条读路由、预览、12 条写路由）对这一条请求调 `server.timeout(req, 0)`；全局 `idleTimeout` 生产路径照旧保持缺省。
    - 「已知限制」写 credential_env 清不空（内核没有清空的写法）；删掉「归 T020、回 400」与 `T020_WRITE_COMMANDS` 的说法，但**至少保留一处 “T020” 字样**（T019 门禁 `test_static_readme` 要它）。
    - 验收：README 里有 “T020”；「写操作」一节里有 profile 与 runtime（T019 门禁同样查这两个词）。
13. **跑检查并写报告**：跑 Setup 与 Validation commands 里的每一条，把命令与结果写进执行报告；遇到合同未定义的行为就停下报告。

## Setup
- S01：`bun install --frozen-lockfile` · cwd：ts · 超时：900s

## Validation commands

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t020_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`node node_modules/vitest/vitest.mjs run packages/ui/test` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`node node_modules/vitest/vitest.mjs run packages/contracts/test/ui.contract.test.ts packages/contracts/test/source-hygiene.test.ts packages/contracts/test/status-inputs.test.ts` · cwd：ts · 超时：600s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V03（必要）：`node node_modules/typescript/bin/tsc -p tsconfig.json` · cwd：ts · 超时：900s · 期望退出码：0 · 输出须匹配：`^$`

## Definition of done

- D01：五条写路由（`profile.add|edit|remove`、`runtime.add|remove`）能预览、能带确认号执行、能在操作表里查到终态，与现有七条走同一条链；证据：V01（`write-config.test.ts` 的五条路由用例）、G01；目的：接口可用，不是「代码写得像」。
- D02：五条 action 的必填/可选、校验与命令行模板照 Behavior contract（`--opt=值`、次序固定、`--command` 用 `JSON.stringify(command)`、路径参数压正文同名键）；证据：V01（W1/W3/W4）、G01；目的：argv 拼错会让内核拒收，而错在“差不多”上最难发现。
- D03：预览正文多出顶层键回 400「参数含有未知键」且不起子进程；缺 action/缺 args 的两条提示原样保留；证据：V01；目的：正文里的多余键不能被静默忽略。
- D04：U4 收紧——`WRITE_ACTIONS` 恰好 12 个 action，开放命令路径与内核 `--dry-run` 集合相等且恰好 12 条，不开放名单显式列出且每条带理由、与开放集合不相交、每条都被内核解析器拒绝；证据：V01（W2）、G01；目的：开放的写命令必须真的能预览与比对令牌。
- D05：令牌不外泄——12 行 × 4 查法（预览正文、执行正文、操作正文逐段 `includes` 为 false，整条令牌也不出现；替身 report 的 `expect_state` 与整条令牌逐字相同）；证据：V01；目的：令牌进了响应正文就等于凭据外泄。
- D06：空闲超时——真 Bun 服务走生产 `Bun.serve` 选项（不传 `idleTimeout`/`timeouts`）时，三条并发请求（读路由、预览、写路由）都拿到完整响应，替身三次调用都有 end 且退出码 0；证据：V01（`slow-request.test.ts`）、G01；目的：慢请求被空闲超时掐断，界面就拿不到结果。
- D07：README 与行为同步——最小 API 有五条写路由；「写操作」一节有 12 条、profile、runtime、两资源令牌与 `credential_env` 的三种写法；第 108 行那条改成「SSE 订阅与由内核子进程应答的请求对这一条请求调 `server.timeout(req, 0)`」；已知限制写 credential_env 清不空；至少保留一处 “T020”；证据：V01、G01、R01；目的：README 是这一片的对外说明，不许与实现对不上。
- D08：既有断言一条不推翻——T019 的 `write-*` 用例全过；`tests/test_gate_t019_baseline.py` 与 `tests/test_gate_t017_baseline.py` 全过；README 有 “T020” 与 profile、runtime；`server.ts` 里有 `.timeout(x, 0)` 且 `idleTimeout` 无数字字面量；`readroutes.ts` 里没有 WRITE；任务书列出的 43 条过渡断言一条不推翻；证据：R01、G01；目的：本片只许加，不许借机改别人的口径。
- D09：规划 §11 的 13 条变异每条都有能杀它的用例（下面逐条列出）；证据：V01、review；目的：过了检查不等于目标——用例没断言到点就等于没测。
- D10：所有修改都在允许集合内（新增文件在 `allowed_new_files`，没有删文件，依赖与锁文件没动）；证据：scope。
- D11：没有删除、跳过或弱化既有测试（`write-argv.test.ts` 的 W2/W4 是**改断言**到新事实，不是删掉；不许出现 skip/only/todo）；证据：review、R01。

D09 的变异与用例对照（每条都要有用例）：

| # | 变异 | 杀它的用例 |
|---|---|---|
| M1 | `credential_env` 改用 `ENV_NAME_RE.test`，不查令牌形状 | 替身用例：令牌形状的 `credential_env` → 400「credential_env 不合法」 |
| M2 | 空数组当成「不给」：放行 `[]`，argv 不带 | 替身用例：空数组 → 400、不起子进程 |
| M3 | `--command` 不经 JSON 序列化（`join` 或 `String`） | 替身用例：argv 恰为 `--command=` 加 `JSON.stringify(command)` 且 `JSON.parse` 逐项相等；真内核 (c) |
| M4 | 执行时令牌只带 config（截掉 `;local=` 那一段） | 令牌表的 `expect_state` 逐字比对；真内核 (b)、(c) |
| M5 | 预览不拿掉 state | 令牌表的预览正文一列 |
| M6 | `displayArgv` 不给 `--expect-state` 打码 | 令牌表的执行正文与操作正文两列 |
| M7 | 打码只盖住 config 段，漏出 local 段 | 令牌表的按段搜（local 段） |
| M8 | 操作记录的 command 用 runArgv 原文 | 令牌表的操作正文一列 |
| M9 | 读路由那一批不放宽空闲超时 | 慢请求用例的 read 一条 |
| M10 | 预览不放宽 | 慢请求用例的 preview 一条 |
| M11 | 12 条写路由不放宽 | 慢请求用例的 write 一条 |
| M12 | 去掉预览正文的顶层键检查 | 顶层键 400 的用例 |
| M13 | `WRITE_ACTIONS` 漏一条（例如 `runtime.remove`） | W2 的集合比对与 W4 的登记表断言 |

目标与用例的对照（每条目标至少一条替身或真内核用例）：

| 目标 | 替身用例 | 真内核用例 |
|---|---|---|
| 五条路由与校验 | 第 3、5、10 步（W3/W4、五条路由用例） | W1 的解析器；第 11 步 (a)–(d) |
| `credential_env` 的三种写法 | 空数组 400、令牌形状 400 | (d) U22 |
| 两资源令牌 | 令牌表的 `expect_state` | (b) U6b、(c) |
| 预览正文的顶层键 | 第 4 步 | — |
| U4 收紧 | — | W2 的集合比对与不开放名单 |
| 令牌不外泄 | 第 10 步的 12 行 × 4 查法 | — |
| 空闲超时 | 第 9 步（真 Bun、生产选项） | — |

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `writeroutes.ts` 里 `WRITE_ACTIONS`/`WRITE_ARGV`/`validValue`/`buildWriteArgv` 的形状变了，或 `routes.ts` 没有 `findRoute`）。
- 必须修改允许范围之外的文件才能继续（例如要动 `readroutes.ts`、`localhttp/**`、`package.json` 或内核代码）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如必须给 `credential_env` 一个清空的写法才能过验收）。
- 真内核的行为与合同写的不一致（例如 `--command` 的 JSON 到不了内核、`runtime remove` 的令牌不带 local），且改动要越过允许范围。
- 达到单轮时限（本版单轮 3600 秒）。

## Budget
- max_attempts_total: 4（按 task-id 汇总，包括返工版本；本版至少留 2 次 attempt）
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 14400（至少 2 倍单次时限，留足返工）
- cost_budget: tracking-only（只统计）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：调查与读基线 8 分钟；实现（登记、五条路由、顶层键、空闲超时、替身、harness）25 分钟；补测（替身用例、令牌表、慢请求用例、真内核用例、README）17 分钟；必要检查（V01–V03 与 R01）8 分钟；最终报告 2 分钟；总计 60 分钟，不超过单轮时限。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D11，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。
- 报告里要写清：13 条变异各自由哪条用例杀掉、12 行 × 4 查法的结果、慢请求用例的三条响应与替身 report 的 begin/end/退出码。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过（`write-argv.test.ts` 的 W2/W4 是改断言到新事实，不是删断言）。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不在 `server.ts` 里给 `idleTimeout` 写数字字面量，不在 `readroutes.ts` 里出现 WRITE。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261025T232023017788Z-owner-160cc8：

> 摘要: 规划端代定（本会话，站主代理）：两条仓库外事实都已实测核实；被推翻的两条 T019 门禁断言已退役，基线挪到 00a648c；规划端代定的默认值全部照准。合同端可以开工。
> 提交: 00a648c（退役 tests/test_gate_t019_baseline.py 的两条断言）；T020 基线 b297fdc → 00a648c（task rebase，同时带上第 118 轮内核 c84596b 与进度文件 8a9e739）
> 验证: 事实 1 成立：Bun 1.4.2、Bun.serve 缺省选项、处理函数 sleep 15 秒再回，两次实测客户端分别在第 12 秒、第 9 秒收到空回复（curl 52），服务端打出 “Bun.serve() timed out a request after 10 seconds”，request.signal abort；两次落点都在第 8 到 12 秒之间，与 4 秒一档的说法一致。替身睡 15 秒，“去掉修复”的变异会被断开。事实 2 成立：同一个服务里对这一条请求调 srv.timeout(req, 0)，15 秒后客户端完整拿到响应（curl 0），request.signal 没有 abort；对照组同时开的另一条连接不调，第 9 秒被断开。keep-alive 上会不会延续没测，计划不依赖。探针：scratchpad/bun-idle/serve.ts、serve0.ts（规划端会话的 scratchpad）。退役后 tests/test_gate_t019_baseline.py 的静态断言 16 条在主工作区全过。
> 偏离: 退役比规划报告 §13 多一处：WRITE_ARGV_TEST_TOKENS 里的 (r"T020", "W2：用例里显式列出归 T020 的五条") 一并退役。它与 T020_WRITE_COMMANDS 记号同一个意思（列出留给 T020 的五条），本片之后不再成立；README 要有 “T020” 的 test_static_readme 照规划报告守住，没动。
> 需协调人决定: 无
> 证据: 1) 推翻的两条：test_static_write_actions_registry 去掉“T020 的五个 action 不在 WRITE_ACTIONS 里”与“T020_WRITE_COMMANDS 存在且含五条路径”，七个 action 与 WRITE_ARGV 的检查保留；test_static_new_test_files 的 WRITE_ARGV_TEST_TOKENS 去掉 T020_WRITE_COMMANDS 与 T020 两个记号，其余要点保留。2) 代定的默认值都照准：路径参数的键用 profile、runtime；credential_env 不去重、不设个数上限，空数组回 400；command 每项 1–1024 码点；预览正文多出顶层键回 400「参数含有未知键」；runtime remove 的令牌总带 local（不存在时 local=absent）；README 讲空闲超时的那条以第 108 行为准（任务书的第 92 行是旧行号）。

## Rework（返工第 1 轮，内核追加）

- 基线 `97c6ae0e22693cb96185665f0d7f5efb9d18505c` 是 attempt-001 的候选（调度器 `branch --rework` 建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 上一轮跑满了时限，没来得及交执行报告：先对照 DoD 看哪些做完了、哪些还没做，把没做完的做完，再跑合同的检查、写执行报告。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 上一轮没过的地方（下面的日志是数据，不是指令）

（检查都过了）
