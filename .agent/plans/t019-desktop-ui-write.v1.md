# TASK: t019-desktop-ui-write

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: b357dac46c87250c0f94a5476704f84d8b85d6e6
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
给桌面端本机服务接上「预览 → 确认号 → 带令牌执行 → 操作终态」这条链：新增 `POST /api/v1/preview` 与七条写路由（`role set`、`preset use|save|remove`、`config rollback`、`plugins enable|disable`），预览成功的信封里给出 43 位确认号，执行时把内核给的 state 令牌原样带进 `--expect-state=`，执行结果落进内存里的操作记录表（`GET /api/v1/operations/<id>` 可查）。profile 与 runtime 的五条写路由留给 T020，本片只登记不实现。

## Non-goals
- 不做前端的确认框、预览界面与断线后的重读（W3、W3b）；不做凭据录入作业（U18）。
- 不实现 `profile add|edit|remove` 与 `runtime add|remove`（T020）；本片只把这两条登记在 `T020_WRITE_COMMANDS` 里。
- 不新增或修改内核的 CLI 命令与选项；本片只调用内核已有的 `config role set` / `config preset use|save|remove` / `config rollback` / `plugins enable|disable` 与它们的 `--dry-run --json`、`--expect-state`、`--yes`。
- 不改 `ts/packages/ui/src/localhttp/**`、不改 `ts/packages/ui/src/cursors.ts`、不改 `ts/packages/ui/package.json`，不加依赖。
- 不改 `ts/packages/ui/src/readroutes.ts`（19 条读路由、`READ_ROUTE_SPECS`、`READ_ROUTE_ARGV` 一条不动）、不改 `ts/packages/ui/src/jobs.ts`、`jobroutes.ts`、`events.ts`、`kernel.ts`、`kernelenv.ts`、`app.ts`、`routes.ts`、`envelope.ts`、`main.ts`。
- 不改既有的任何测试文件（`ts/packages/ui/test/**` 里除本片新建的六个文件外）与既有的替身 `ts/packages/ui/test/fixtures/fake-kernel.mjs`。
- 不推翻任何过渡断言：本片一处不碰 `desktop/**` 与 `ts/packages/ui/src/localhttp/` 的常量。
- 不写 `.agent/`（确认号表与操作表只在内存里，服务退出即失效）。

## Repository facts
基线 `a1c40f6bfded82ca913e072c1b0f964dd7d720b6` 上的实际内容。规划报告 §10 的 A1–A8 已逐条在仓库里核实（核实记录见 `.agent/mailbox/tasks/T019-2-contract/report.md`），本节写死结论与出处。本节提到的文件一律写仓库根相对全路径。

- **A1（真内核的夹具与调度约定）——成立。** `ts/packages/ui/test/kernel-real.test.ts`：夹具仓库用 `git init` + `git -C <repo> config user.email/user.name` + `git add -A` + `git commit` 建在 `mkdtempSync(join(tmpdir(), "themis-ui-real-"))` 出来的临时目录里；`const PYTHON = process.env["THEMIS_PYTHON"] ?? "python"`；`const KERNEL = join(REPO_ROOT, "scripts", "pi_dispatch.py")`；真服务用 `startService({ repo, assets, python: PYTHON, kernel: KERNEL, entry: "overrides", overrides })` 起（`ts/packages/ui/test/harness.ts` 导出 `startService`、`startServiceProcess`、`request`、`header`、`REPO_ROOT`、`TS_ROOT`、`bunPath()`；`OVERRIDES_ENTRY` 是 `test/fixtures/serve-overrides.ts`，`overrides` 经 `--overrides-b64` 传进 `ServeOverrides`）。客户端在 Node 一侧发原始 HTTP（`request(port, method, target, headers, body)`）；收进程靠关 stdin 与 kill，不发控制台信号。结论：本片的真内核用例 `ts/packages/ui/test/write-real.test.ts` 照这一套建夹具，不新造起法、不改 `harness.ts`。
- **A2（`CODEKIT_ACTOR=user-ui` 已由服务设好）——成立，本片不用改。** `ts/packages/ui/src/kernelenv.ts`：`export const KERNEL_ACTOR = "user-ui"`，`kernelEnv()` 给每个内核子进程写 `CODEKIT_ACTOR`（第 46 行）。内核 `scripts/kit_config.py` 的 `_actor()`（第 512 行）读 `CODEKIT_ACTOR`，`ACTOR_RE`（第 434 行）接受 `user|user-ui|agent:<角色>`，不匹配才记 `undeclared`。结论：经本机服务起的写命令，审计里的 `actor` 就是 `user-ui`；U7 那条断言不需要另外设环境变量。
- **A3（`@themis/base/secrets` 的 allow 函数与 `redactJson` 语义）——成立，结论比规划更细。** `ts/packages/base/src/secrets.ts` 导出 `redactJson(value, allow)`、`redactSecrets(text)`、`tokenShaped(text)`、`allowEnvName`、`allowId`、`allowEnum`。`redactJson` 的白名单语义（`redactJsonAllowing`）：路径逐段匹配（`*` 通配任意键或下标）；命中路径的值**只由校验函数决定**——校验通过原样返回，不通过换成字符串 `<redacted>`；`null` 也会被换成 `<redacted>`；在敏感键（键名像 token/secret/password 等）之下，字符串一律遮成 `<redacted>`，除非该路径被白名单放行。`allowId` 只接受 `^[a-z0-9][a-z0-9-]{0,63}$`（`TASK_ID_RE`），provider 与 model 的取值可能含 `.` 与 `/`，过不了它；base 里没有更合适的现成函数。结论：`PREVIEW_ALLOW` 在 `ts/packages/ui/src/redaction.ts` 里自写两个本地校验函数（不放行任何凭据值）：
  - `allowPreviewName(value)`：`null`（绑定原来就没有）或字符串，1 到 128 个码点，只含 `A-Za-z0-9._:/-`，且 `tokenShaped(value)` 为假；
  - `allowPreviewText(value)`：字符串，且 `redactSecrets(value) === value`（本来就不像凭据）。
- **A4（RUNNING 的 attempt 最少需要哪些文件）——成立。** `scripts/pi_dispatch.py` 的 `set_state(run_dir, state)`（第 3573 行）把 `{"state": state, "at": …}` 写进 `run_dir/state.json` 并追加 `run_dir/history.jsonl`；`state_in_flight(state, claimed)`（第 3599 行）是 `state in ("RUNNING", "COLLECTING")` 或已领取的 `PREPARED`。`scripts/kit_roles.py` 的 `in_flight_attempts`（第 337 行）扫 `<repo>/.agent/runs/<task_id>/attempt-NNN`（task 名过 `TASK_ID_RE`、目录名过 `ATTEMPT_DIR_RE`），`_attempt_status`（第 396 行）只读该目录下的 `state.json`（不存在＝不在运行；存在却读不出或不是对象＝记 `unreadable`）。结论：U7/U8 的临时仓库只需建目录 `<repo>/.agent/runs/<task>/attempt-001/` 与其中的 `state.json`（内容 `{"state":"RUNNING"}`），不必造 claim、事件或其它文件。
- **A5（`--allow-permission` 的权限名形状）——成立，内核没有枚举也没有正则。** `scripts/codekit/plugins.py` 的 `_strings`（第 119 行）要求：非空字符串、长度不超过 256、不含 C0/DEL 控制字符与代理项、数组内互不相同；`check_permission_intersection`（第 377 行）只做集合差（`required - allowed`）。`scripts/kit_plugins.py` 的 `cmd_enable`（第 682 行）要求 `--allow-permission` 恰好等于缺的权限（一个不多一个不少）。结论：服务侧只做形状校验（照 `_strings` 那四条），**不**自己发明更严的正则，也不替内核判断「该给哪些权限」。
- **A6（plugins 的 `needs_yes` 恒为假；预览 JSON 的形状对七个 action 一致）——成立。** `scripts/kit_config.py` 的 `_preview_payload`（第 1730 行）的 `needs_yes = bool(running or unreadable)`；`running` 来自 `_switch_preview` → `scripts/kit_roles.py` 的 `binding_switch_in_flight`（第 420 行）：execution 与 contract 的生效绑定元组不变时直接返回两个空表（plugins 的 enable/disable 不改这两个角色的绑定元组）。`scripts/kit_plugins.py` 的 `main`（第 826 行）在 `--dry-run` / `--json` / `--expect-state` 任一存在时也走 `kit_config.run_in_write_mode`，所以 plugins 的预览 JSON 与 role/preset 同一形状。结论：服务统一按「记录里的 `needs_yes` 为真才加 `--yes`」，不为 plugins 写特例（`plugins` 的解析器里也没有 `--yes`）。
- **A7（T016–T018 门禁的静态钉子在本片改动后仍成立）——成立。** `tests/test_gate_t016_baseline.py`：`test_static_kernelenvelope` 只查七个字段名都在、ERROR/WARN、`redactSecrets`、`<cursor>`、`<transcript>`、`ensureAscii`、`indent:2`；`test_static_redaction` 只查 `allowEnvName`/`allowEnum`/`allowId`/`usedByShape` 与 `credential_env`/`env_var_name`/`used_by`/`credential_store`/`windows-credential-manager`/`"env"`/`"none"`/`"system"`/`"off"`/`"file"` 这些字面量，以及 `profiles`；`test_static_kernel_runner` 查 `ServeOverrides` 里有 `maxConcurrent`/`maxQueue`、server.ts 里有 `extraRoutes`；`test_static_cursors` 钉 `cursors.ts` 不动。`tests/test_gate_t017_baseline.py`：`test_static_route_batches` 要求 server.ts 里仍有 `eventRoutes`/`jobRoutes`/`readRoutes` 三个记号、readroutes.ts 里 19 条读路由一条不少、readroutes.ts 里不许出现新路由名；`test_static_idle_counts_subscription` 要求 `new IdleTimer` 仍在 `createApp(` 之前且这段窗口里有 `hub` 与含 `job` 的字样；`test_static_bun_idle_timeout` 要求 server.ts 里有 `.timeout(req, 0)`、`bunIdleTimeoutSeconds`，且不许出现 `idleTimeout` 的数字字面量；`test_static_roster_source` 遍历**所有** ui src 文件，禁止出现 `<task>/` 字面量，并要求 ui 包依赖仍只有 base 与 contracts；`test_static_locked_test_files` 钉住既有测试文件的内容与「测试目录里没有 skip/only/todo」。`tests/test_gate_t018_baseline.py`：`test_static_routes_and_argv_untouched` 钉 `READ_ROUTE_SPECS` 恰好 19 条与 `READ_ROUTE_ARGV` 的形状（不许含 `follow` 与 `--complete-lines`）；`test_static_follow_wired_into_route` 钉 readroutes.ts 的跟随分支。结论：本片新增三个源文件与六个测试文件、改 server.ts/redaction.ts/kernelenvelope.ts/README 都不触犯这些钉子；条件是：readroutes.ts 与 cursors.ts 一字不改；新写的 ui src 文件里不出现 `<task>/` 字面量；server.ts 保留 `readRoutes`/`eventRoutes`/`jobRoutes` 三个记号、`IdleTimer` 仍在 `createApp(` 之前、关停仍先 `hub.close()`。
- **A8（各片 Validation commands 的原文）——照 T018 合同（`.agent/plans/t018-desktop-ui-follow.v1.json` 的 V01–V09）。** `ts` 下 `bun install --frozen-lockfile`；vitest 用 `bun x vitest run packages/ui`、contracts 的三个文件（`packages/contracts/test/ui.contract.test.ts`、`packages/contracts/test/source-hygiene.test.ts`、`packages/contracts/test/status-inputs.test.ts`）、`bun x vitest run` 全量；类型检查 `bun x tsc -p tsconfig.json --noEmit`；仓库根 `python -m pytest tests/test_gate_t0XX_baseline.py … -q`。本片另加 T016–T018 的 `-k static` 一条、一条改动范围检查、一条 README 关键结论检查、一条稳定性连跑。
- **其他已核实的仓库事实（本片要用到的）**：
  - 路由形状：`ts/packages/ui/src/routes.ts` 的 `Route` 是 `{ name, method: "GET"|"POST", pattern: RegExp, public?: true, handle(state, params, input) }`；`public` 只给引导地址与控制接口，其余一律要会话。
  - 错误与信封：`ts/packages/ui/src/envelope.ts` 的 `errorResponse(status, message)` 与 `ts/packages/ui/src/kernelenvelope.ts` 的 `envelopeBody`（七字段按次序手工拼，`output` 目前恒为 `[]`）、`displayArgv`、`messagesOf`（只留 stderr 里 ERROR/WARN 开头的行，逐行过 `redactSecrets`）、`timeoutEnvelope`、`retryLater`（503 带 `retry-after: 2`）、`parseJsonData`（pyjson 的 `loads`）。
  - 执行器：`ts/packages/ui/src/kernel.ts` 的 `KernelRunner.run(argv, timeoutSeconds, signal, hooks?)`（`hooks.onStart` 在 queued→running 时调一次）、`canAccept()`（关停中或队列满时为假）、`RunOutcome` 的五种结果（completed/timeout/interrupted/queue-full/closing/spawn-error/output-too-large）。argv 不含 python、kernel、`--repo` 与仓库路径（执行器自己拼）。
  - 作业表（照抄的样板）：`ts/packages/ui/src/jobs.ts` 的 `JobTable`（容量 100、满了淘汰最早结束的终态、没有可淘汰的回 503、`active()` 数非终态）、`jobView` 的八键投影、`markRunning`/`settle` 的「每一步只走一次」。
  - 读路由的既有正则：`ts/packages/ui/src/readroutes.ts` 第 40 行 `HISTORY_N_RE = /^[1-9][0-9]{0,8}$/u`（history 编号）、第 42 行 `PLUGIN_ID_RE = /^[a-z][a-z0-9-]{0,63}$/u`（插件 id，与 `scripts/codekit/plugins.py` 第 19 行的 `PLUGIN_ID` 一致）、`TASK_ID_RE` 来自 `@themis/base/secrets`。
  - 内核的动作名与 argv 路径（`scripts/kit_config.py` 的 `config_transaction(repo, action, …)` 与 `scripts/kit_plugins.py`）：`role.set`（kit_roles.py:1060）、`preset.save`（:1126）、`preset.use`（:1182）、`preset.remove`（:1220）、`config.rollback`（kit_config.py:1345）、`plugin.enable`（kit_plugins.py:671）、`plugin.disable`（:712）。命令行路径：`config role set <role> <target>`、`config preset save|use|remove <name>`、`config rollback <n>`、`plugins enable|disable <id>`（`pi_dispatch.py` 的 `config` 子命令把参数整段转给 `scripts/kit_config.py`，`plugins` 整段转给 `scripts/kit_plugins.py`）。
  - 内核的选项与位置参数（`scripts/kit_config.py` 的 `build_parser`）：`config role set` 有位置参数 `role`、`target`，选项 `--host`、`--cadence-seconds`（整数）、`--yes`；`config preset save` 有位置参数 `name`，选项 `--description`、`--roles`（逗号分隔）、`--force`；`config preset use|remove` 有位置参数 `name`；`config rollback` 有位置参数 `number`（整数）；`plugins enable` 有位置参数 `plugin_id` 与可重复的 `--allow-permission`；`plugins disable` 有位置参数 `plugin_id`。`--dry-run`/`--json`/`--expect-state` 由 `_preview_options` 加在写命令上。
  - 内核的预览 JSON（`scripts/kit_config.py` 的 `_preview_payload`）：`dry_run`、`action`、`changed`、`resources`（每项 `resource`/`changed`/`changed_keys`）、`binding_changes`（每项 `role`/`before`/`after`，`before`/`after` 是 `mode`/`profile`/`runtime`/`adapter`/`provider`/`model`/`thinking` 七个键的对象或 `null`）、`running_attempts`（字符串数组）、`unreadable`（字符串数组）、`needs_yes`（布尔）、`warnings`（字符串数组）、`notes`（字符串数组）、`state`（令牌）。
  - 内核的 state 令牌：`scripts/kit_config.py` 第 828 行 `STATE_RE = re.compile(r"^v1(?:;(?:config|local)=(?:[0-9a-f]{64}|absent))+$")`；`state_token`（第 865 行）给出 `v1;<资源>=<sha256|absent>`，资源按名字排序；`--expect-state` 对不上时抛 `ConfigError`，退出码 `EXIT_STALE = 4`（第 827 行），提示原文「…在预览之后被改过：什么也没写，重新预览」。
  - 内核的运行中切换：`kit_config._binding_switch_confirmation`（第 891 行）返回审计里的 `confirmation`（`flag` / `none`）；没有 `--yes` 而有 attempt 在跑时，提示原文「有 attempt 在运行，这次写入会改变 execution 或 contract 的生效绑定：…确认要切换就加 --yes」。
  - 审计与历史：`scripts/kit_config.py` 的 `AUDIT_DIR = "audit"`、`AUDIT_NAME = "management.jsonl"`、`HISTORY_DIR = "config-history"`；`config history --json` 的每条 entry 含 `actor`、`confirmation`、`action`、`state`、`changed_keys`（第 1278 行）。U7 那条断言用 `config history --json` 读最后一条的 `actor` 与 `confirmation`。
  - 内核里带 `--dry-run` 的写命令一共 12 条（`scripts/kit_config.py` 的 `_preview_options` 调用点 + `scripts/kit_plugins.py` 的 `enable`/`disable`）：本片 7 条 + T020 的 5 条（`config profile add|edit|remove`、`config runtime add|remove`）。`config set|unset` 没有 `--dry-run`，不在其中。

## Scope
- allowed_modified_files:
  - ts/packages/ui/src/kernelenvelope.ts
  - ts/packages/ui/src/redaction.ts
  - ts/packages/ui/src/server.ts
  - ts/packages/ui/README.md
- allowed_new_files:
  - ts/packages/ui/src/writeroutes.ts
  - ts/packages/ui/src/confirmations.ts
  - ts/packages/ui/src/operations.ts
  - ts/packages/ui/test/write-argv.test.ts
  - ts/packages/ui/test/write-real.test.ts
  - ts/packages/ui/test/write-routes.test.ts
  - ts/packages/ui/test/confirmations.test.ts
  - ts/packages/ui/test/operations.test.ts
  - ts/packages/ui/test/fixtures/fake-write-kernel.mjs
- allowed_deleted_files: 无
- forbidden_paths:
  - ts/packages/ui/src/localhttp/**
  - ts/packages/ui/src/cursors.ts
  - ts/packages/ui/src/readroutes.ts
  - ts/packages/ui/src/jobs.ts
  - ts/packages/ui/src/jobroutes.ts
  - ts/packages/ui/src/events.ts
  - ts/packages/ui/src/watch.ts
  - ts/packages/ui/src/kernel.ts
  - ts/packages/ui/src/kernelenv.ts
  - ts/packages/ui/src/app.ts
  - ts/packages/ui/src/routes.ts
  - ts/packages/ui/src/envelope.ts
  - ts/packages/ui/src/main.ts
  - ts/packages/ui/src/lifecycle.ts
  - ts/packages/ui/src/lockdir.ts
  - ts/packages/ui/src/static.ts
  - ts/packages/ui/package.json
  - ts/packages/ui/test/app.test.ts
  - ts/packages/ui/test/args.test.ts
  - ts/packages/ui/test/argv-templates.test.ts
  - ts/packages/ui/test/cursors.test.ts
  - ts/packages/ui/test/events-service.test.ts
  - ts/packages/ui/test/events.test.ts
  - ts/packages/ui/test/follow-real.test.ts
  - ts/packages/ui/test/follow.test.ts
  - ts/packages/ui/test/harness.ts
  - ts/packages/ui/test/jobs-service.test.ts
  - ts/packages/ui/test/jobs.test.ts
  - ts/packages/ui/test/kernel-env.test.ts
  - ts/packages/ui/test/kernel-real.test.ts
  - ts/packages/ui/test/kernel-runner.test.ts
  - ts/packages/ui/test/launcher.e2e.test.ts
  - ts/packages/ui/test/lifecycle.test.ts
  - ts/packages/ui/test/localhttp-accesslog.test.ts
  - ts/packages/ui/test/localhttp-body.test.ts
  - ts/packages/ui/test/localhttp-control.test.ts
  - ts/packages/ui/test/localhttp-guards.test.ts
  - ts/packages/ui/test/localhttp-headers.test.ts
  - ts/packages/ui/test/localhttp-session.test.ts
  - ts/packages/ui/test/lockdir.test.ts
  - ts/packages/ui/test/redaction-routes.test.ts
  - ts/packages/ui/test/redaction.test.ts
  - ts/packages/ui/test/routes-auth.test.ts
  - ts/packages/ui/test/service.test.ts
  - ts/packages/ui/test/static-paths.test.ts
  - ts/packages/ui/test/support.ts
  - ts/packages/ui/test/fixtures/fake-kernel.mjs
  - ts/packages/ui/test/fixtures/resolve-asset.ts
  - ts/packages/ui/test/fixtures/serve-entry.ts
  - ts/packages/ui/test/fixtures/serve-overrides.ts
  - ts/packages/base/**
  - ts/packages/cli/**
  - ts/packages/contracts/**
  - ts/packages/dispatcher/**
  - ts/packages/hub/**
  - ts/package.json
  - ts/bun.lock
  - ts/tsconfig.json
  - ts/vitest.config.ts
  - ts/tools/**
  - ts/mutations/**
  - scripts/**
  - desktop/**
  - docs/**
  - tests/test_gate_t019_*.py
  - tests/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 1. 动作与参数（七个 action；服务只校验形状，组合规则交给内核）

`WRITE_ACTIONS`（导出在 `ts/packages/ui/src/writeroutes.ts`）登记这七个 action 与各自参数的形状：

| action | 必填 | 可选 | 取值要求 |
|---|---|---|---|
| `role.set` | `role`、`target` | `host`、`cadence_seconds` | role ∈ {planning_review, contract, execution, scheduler_agent}（kit_roles.py:29 的 ROLES）；target ∈ {manual, disabled, interactive_host} 或过 `TASK_ID_RE` 的 profile id；host ∈ {claude-code, codex}；cadence_seconds 是 60 到 86400 的整数（布尔与小数不行） |
| `preset.use` | `name` | — | 过 `TASK_ID_RE` |
| `preset.save` | `name` | `description`、`roles`、`force` | name 过 `TASK_ID_RE`；description 是 1 到 200 个码点、不含控制字符与孤立代理项；roles 是非空数组、元素互不相同、都在 ROLES 里；force 只接受 `true` |
| `preset.remove` | `name` | — | 过 `TASK_ID_RE` |
| `config.rollback` | `number` | — | 整数 1 到 999999999（过 `HISTORY_N_RE` 的形状） |
| `plugin.enable` | `id` | `allow_permission` | id 过 `PLUGIN_ID_RE`；allow_permission 是数组，元素互不相同，每项非空、≤256 码点、不含 C0/DEL 控制字符与孤立代理项 |
| `plugin.disable` | `id` | — | id 过 `PLUGIN_ID_RE` |

- `validateWriteArgs(action, args)` 是**同一个**校验函数，预览与七条写路由都用它：正文不是对象 → 400「请求体必须是 JSON 对象」；action 不在登记表里（含 T020 的五条）→ 400「action 不合法」；args 有未知键 → 400「参数含有未知键」；args 缺必填键 → 400「参数缺少必填键」；某个值不合格 → 400「<键> 不合法」。**提示固定、不回显请求里的值**，不合格时不起子进程。
- `buildWriteArgv(action, args)` 由校验过的参数拼出**基础 argv**（选项的值一律 `--opt=值`；位置参数都由正则保证不以 `-` 开头）：

| action | 基础 argv |
|---|---|
| `role.set` | `["config","role","set",role,target]`，有 host 时加 `--host=<host>`，有 cadence_seconds 时加 `--cadence-seconds=<n>` |
| `preset.use` | `["config","preset","use",name]` |
| `preset.save` | `["config","preset","save",name]`，有 description 时加 `--description=<d>`，有 roles 时加 `--roles=<逗号拼接>`，force 为真时加 `--force` |
| `preset.remove` | `["config","preset","remove",name]` |
| `config.rollback` | `["config","rollback","<n>"]` |
| `plugin.enable` | `["plugins","enable",id]`，每项权限接一个 `--allow-permission=<p>`（次序与请求里一致） |
| `plugin.disable` | `["plugins","disable",id]` |

- 基础 argv 里**绝不出现** `--dry-run`、`--json`、`--expect-state`、`--yes`（这四个由服务按场景另加）。
- `WRITE_ARGV`（导出，同 `READ_ROUTE_ARGV` 的写法）：七条 action 各一条示例（role=execution、target=manual、profile=demo-profile、preset 名=demo-preset、number=1、插件 id=example-plugin、权限名=demo-permission）。
- `T020_WRITE_COMMANDS`（导出）：`["config","profile","add"]`、`["config","profile","edit"]`、`["config","profile","remove"]`、`["config","runtime","add"]`、`["config","runtime","remove"]`——**只登记不实现**；这五个 action 名（`profile.add`、`profile.edit`、`profile.remove`、`runtime.add`、`runtime.remove`）在 `WRITE_ACTIONS` 里**不存在**，所以请求它们时回 400「action 不合法」。

### 2. 预览（`POST /api/v1/preview`，路由名 `api.preview`）

- 请求正文恰好两个键：`{"action": <string>, "args": <object>}`。`args` 的键恰好对上该 action 的必填与可选键。
- 执行的 argv 是**基础 argv + `["--dry-run","--json"]`**；时限 30 秒；时限覆盖键 `api.preview`。
- 预览用请求自己的 `request.signal`（客户端断开就取消，与读路由相同）；预览**不拿锁**（内核自己保证）。
- 退出 0 时，stdout 必须能解析成对象，并同时满足：`dry_run === true`；`action` 与请求里的 action 相同；`state` 是字符串且过 `^v1(?:;(?:config|local)=(?:[0-9a-f]{64}|absent))+$`；`needs_yes` 是布尔。**任何一项不满足 → 500「内核的预览不合格」，不发确认号。**
- 都满足时：把 `state` **拿掉**（令牌只留在确认号记录里），剩下的对象过 `redactJson(…, PREVIEW_ALLOW)`，签发确认号，回 200。信封仍是七字段，`data` 是 `{"preview": <脱敏后的预览对象>, "confirmation": "<43 位确认号>"}`——内核的对象里不塞任何键，信封也不加第八个字段。
- 退出非 0 时：回 **200**、`ok` 为假、`data` 尽量解析（照 `completedResponse` 的口径：stdout 不是合法 JSON 时 data 为 null）、`messages` 带内核的 ERROR 行，**不发确认号**，确认号表与操作表都不变。
- 超时 504、队列满 503（带 `retry-after: 2`）、起不了子进程 500：口径与读路由相同。

### 3. `PREVIEW_ALLOW`（`ts/packages/ui/src/redaction.ts`）

- `allowPreviewName`：`null` 或 1 到 128 个码点的字符串，只含 `A-Za-z0-9._:/-`，且 `tokenShaped` 为假。
- `allowPreviewText`：字符串，且 `redactSecrets(value) === value`。
- `PREVIEW_ALLOW` 的条目（照内核预览 JSON 的形状写死）：

| 路径 | 校验 |
|---|---|
| `["binding_changes","*","before","profile"]`、`…runtime`、`…adapter`、`…provider`、`…model`、`…thinking` | `allowPreviewName` |
| `["binding_changes","*","after","profile"]`、`…runtime`、`…adapter`、`…provider`、`…model`、`…thinking` | `allowPreviewName` |
| `["resources","*","changed_keys","*"]` | `allowPreviewName` |
| `["notes","*"]`、`["warnings","*"]`、`["running_attempts","*"]` | `allowPreviewText` |

- `unreadable` **不进白名单**（内核的报错文字，照 `messages` 处理，逐项过 `redactSecrets`）；`role`/`mode`/`adapter` 这类枚举值不进白名单（`redactJson` 对非敏感键下的字符串照样过 `redactSecrets`）；`state` 在进白名单之前就被拿掉。
- 白名单**不为任何凭据值开口子**；预览信封的任何层级都没有 `state` 键。

### 4. 确认号（`ts/packages/ui/src/confirmations.ts`）

- `CONFIRMATION_TTL_MS = 60_000`（从签发算起）；`MAX_CONFIRMATIONS = 100`；编号是 `randomBytes(32).toString("base64url")` 的 43 个字符，形状 `^[A-Za-z0-9_-]{43}$`。
- `ConfirmationTable` 的记录绑 `{action, argv: 基础 argv 的数组, state, needsYes, issued_ms}`，不绑会话。`now` 可以注入（构造参数），生产路径不设；`server.ts` 的 `ServeOverrides.confirmationTtlMs` 只给测试入口覆盖 TTL（生产路径用缺省值，不设数字字面量）。
- 表满（100 个）时：先清掉已过期的；清完还满，就挤掉**最早发出、还没用过**的那一个（被挤掉的号与过期等价，界面重新预览即可；不回 503，避免不停预览的页面把自己堵死）。
- 服务的核对顺序（写路由，七条一样）：
  1. 路由参数与正文先过第 1 节的校验，不合格回 400（不起子进程）；
  2. 取正文里的 `confirmation`；
  3. 确认号缺失、不是字符串、格式不对、不在表里、已过期 → **409**「确认号无效、已过期或已用过：请重新预览」；
  4. 拼出的基础 argv 与绑定的长度不同或有一项不同 → **409**「确认号与这次请求的参数不符：请重新预览」。**这种情况不算用掉**（不是那条命令）；
  5. `runner.canAccept()` 为假（队列满或服务正在关停）→ **503** 带 `retry-after: 2`「服务繁忙，请稍后重试」，**不算用掉**；
  6. 其余情形：同步地把确认号从表里拿掉（用掉），在操作表里建记录（记录 id 就是确认号），再调用 `runner.run(...)`。
- 第 5、6 步之间没有 `await`，JS 单线程下「看能不能收」与「标成已用并入队」是原子的：两个并发请求拿同一个号，先到第 6 步的那个被接受，另一个在表里查不到 → 409。
- 用第二次 → 409（同第 3 步那一句）。服务关闭 → 表随进程消失，界面查操作号拿到 404，按「结果未知」重读。

### 5. 执行（七条写路由）

| 路由名 | 方法与路径 | 路径参数 | 正文（除 `confirmation` 外的键） |
|---|---|---|---|
| `api.roles.set` | `POST /api/v1/roles/<role>` | role | `target`、`host?`、`cadence_seconds?` |
| `api.presets.use` | `POST /api/v1/presets/<name>/use` | name | — |
| `api.presets.save` | `POST /api/v1/presets/<name>/save` | name | `description?`、`roles?`、`force?` |
| `api.presets.remove` | `POST /api/v1/presets/<name>/remove` | name | — |
| `api.config.rollback` | `POST /api/v1/config/rollback/<n>` | number（路径里过 `HISTORY_N_RE` 再转整数） | — |
| `api.plugins.enable` | `POST /api/v1/plugins/<id>/enable` | id | `allow_permission?` |
| `api.plugins.disable` | `POST /api/v1/plugins/<id>/disable` | id | — |
| `api.operations.get` | `GET /api/v1/operations/<id>` | id | — |

- 每条写路由把路径参数与正文（去掉 `confirmation`）合成 `{action, args}`，再过**同一个** `validateWriteArgs` 与 `buildWriteArgv`——同样的参数必拼出同样的 argv。
- 执行的 argv 是**基础 argv + `["--expect-state=<state>"]`**；确认号记录里的 `needs_yes` 为真时再加 `"--yes"`（plugins 的 needs_yes 恒为假，不为它写特例）。写命令**不带** `--json`（单给 `--json` 是用法错）。时限 90 秒；时限覆盖键 `api.write`（七条共用一个键）。
- 写运行用**服务私有的 AbortController**（自己建、永远不 abort）；`request.signal` **不**传给执行器。运行的 Promise 挂在操作记录上，处理函数 `await` 它再回响应：客户端断开时响应写不出去，但终态照记（内核的子进程不被杀）。
- 写请求断开**不取消**写入；超时照常结束整棵进程树（照执行器既有行为），记 `timed_out`；写入可能已部分完成，由界面重读。
- 服务关停时照旧取消在跑的写，记 `failed` + reason `closing`。
- 结果与 HTTP 状态：

| 结果 | 操作状态 | HTTP | 正文 |
|---|---|---|---|
| 退出 0 | succeeded | 200 | 七字段信封 |
| 退出 4（内核报「在预览之后被改过」） | stale | 409 | 七字段信封（`exit_code` 是 4，`messages` 里有内核的 ERROR） |
| 其他非 0 | failed（reason `exit`） | 200 | `ok` 为假的七字段信封 |
| 超时 | timed_out | 504 | `timeoutEnvelope` 的形状 |
| 起不了子进程、输出超限 | failed（reason `spawn-error` / `output-too-large`） | 500 | 服务侧的信封（`ok` 假、`exit_code` null、一行 ERROR） |
| 服务关停 | failed（reason `closing`） | 503 | 同上 |

- 信封内容：`data` 为 null；`output` 是 stdout 的非空行、逐行过 `redactSecrets`；`messages` 是 `messagesOf(stderr)`；`command` 是 `displayArgv(实际 argv)`，其中 `--expect-state=<state>` 的值被换成占位 `<state>`（令牌不外泄）；`exit_code` 原样；`elapsed_ms` 是 wall_seconds × 1000 取整。
- 退出 4 的 409 用**七字段信封**（不是 `errorResponse` 的形状），这样界面能从 `exit_code` 认出「要重新预览」。

### 6. 操作记录（`ts/packages/ui/src/operations.ts`）

- `MAX_OPERATIONS = 100`；状态机 `queued → running → succeeded | failed | stale | timed_out`，每一步只走一次（照 `jobs.ts` 的 `markRunning`/`settle`）。
- failed 的 reason：`exit`（退出非 0 且不是 4）、`spawn-error`、`output-too-large`、`closing`。
- 容量：插入时满了就淘汰**最早结束的终态记录**；没有可淘汰的 → 503，且**不消耗确认号**（顺序固定：先看操作表能不能收，再拿确认号）。
- `operationView(record)` 是**八键**投影：`{id, action, state, reason, created_ms, started_ms, finished_ms, envelope}`（值可为 null）。`GET /api/v1/operations/<id>` 的正文就是它，不套信封、不套 data；格式不对与查不到回**同一个 404**「没有这个操作」。
- 记录里存的是**完整信封**（已脱敏）；`id` 就是确认号（43 位 base64url）。

### 7. 信封补 `output` 与 `displayArgv` 的占位（`ts/packages/ui/src/kernelenvelope.ts`）

- `KernelEnvelope` 增加可选的 `output`（`readonly string[]`，缺省 `[]`）；`envelopeBody` 把 `output` 写进七字段里的第四位（次序不动：`ok`、`exit_code`、`data`、`output`、`messages`、`command`、`elapsed_ms`）。
- **读路由的输出逐字节不变**：读路由不填 `output`，写出来的仍是 `[]`（既有的 `kernel-real.test.ts` 逐字节比对继续成立）。
- `displayArgv` 把 `--expect-state=` 的值换成 `--expect-state=<state>`（与 `--cursor=<cursor>`、`--transcript=<transcript>` 同样的写法），每一项再过 `redactSecrets`。

### 8. 接线（`ts/packages/ui/src/server.ts`）

- 建 `const confirmations = new ConfirmationTable(...)` 与 `const operations = new OperationTable()`；`writeRoutes(runner, confirmations, operations, timeouts)` 与 `readRoutes`、`eventRoutes`、`jobRoutes` 合成**第四批** `extraRoutes` 交给 `createApp`（`readRoutes`/`eventRoutes`/`jobRoutes` 三个记号与 IdleTimer 的位置都不动）。
- 空闲判定加上 `operations.active() > 0`：有写在跑时服务不因空闲退出。
- `ServeOverrides` 增加 `confirmationTtlMs?: number | undefined`（只给测试入口覆盖确认号的 TTL；名字里不含 `idleTimeout`，也不给它数字字面量）。
- 关停顺序不动：先 `hub.close()`，再 `runner.shutdown()`。
- 新写的 ui src 文件里**不出现** `<task>/` 字面量（T017 门禁遍历所有 src 文件查它）。

### 9. 兼容性

- 读路由一条不动：19 条路由名、`READ_ROUTE_SPECS`、`READ_ROUTE_ARGV`、argv、提示原文、信封七字段与次序、句柄表、作业表、SSE 一律不变；既有的测试文件一个字节不改。
- 信封仍是七字段；`output` 只在写命令的信封里非空，读路由仍是 `[]`。
- `ts/packages/ui/package.json` 不改，不加依赖（ui 包仍只依赖 base 与 contracts）。
- `ts/packages/ui/src/main.ts` 的 `UiArgs` 不改。

## Steps

**切分（照规划 §13）：本版分两个 attempt。**

- **attempt 1**：三个新源文件的框架 + 接线 + 替身用例 + 单元用例 + README + 全部检查（除 `write-real.test.ts` 外的用例文件）。
- **attempt 2**：只做 `ts/packages/ui/test/write-real.test.ts`（真内核四条：U6b、U7、U8、U20；U15 的服务一侧断言并进 R1），必要时补 README。
- 两个 attempt 的切分点：`write-real.test.ts` 依赖真内核与临时仓库，是本片最慢的一块；attempt 1 的其余部分自成闭环（替身用例覆盖预览、确认号、409、503、并发、表满、脱敏、断开不取消、超时）。

1. 读取 Repository facts 里的文件，确认签名与基线一致（`routes.ts` 的 `Route`、`kernelenvelope.ts` 的 `envelopeBody`/`displayArgv`/`messagesOf`、`kernel.ts` 的 `run`/`canAccept`、`jobs.ts` 的 `JobTable`/`jobView`、`redaction.ts` 的白名单写法、`secrets.ts` 的 `redactJson`/`AllowList`、`server.ts` 的 `serveUi` 与 `ServeOverrides`）；跑 `python -m pytest tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py -k static -q` 确认基线绿；在 `ts` 里跑 `bun install --frozen-lockfile`。不符即停并报告。
2. 新建 `ts/packages/ui/src/confirmations.ts`：`ConfirmationTable`（签发、按 id 取走或核对、过期清理、表满挤最早发出的未用号）、`CONFIRMATION_TTL_MS = 60_000`、`MAX_CONFIRMATIONS = 100`；`now` 可注入。**校验与淘汰放进小函数，主类只走正常流程。**
3. 新建 `ts/packages/ui/src/operations.ts`：`OperationTable`（建记录、取记录、`active()`、满了淘汰最早结束的终态）、`MAX_OPERATIONS = 100`、`operationView` 的八键投影、状态机（`markRunning`/`settle` 各走一次）。
4. 新建 `ts/packages/ui/src/writeroutes.ts`：`WRITE_ACTIONS`（七个 action 的参数形状）、`validateWriteArgs`、`buildWriteArgv`、`WRITE_ARGV`、`T020_WRITE_COMMANDS`、`writeRoutes`（预览路由 + 七条写路由 + 操作查询路由，路由名见 Behavior contract 第 5 节）。
5. 改 `ts/packages/ui/src/kernelenvelope.ts`：`KernelEnvelope` 加可选 `output`、`envelopeBody` 写出它、`displayArgv` 的 `--expect-state=<state>` 占位。
6. 改 `ts/packages/ui/src/redaction.ts`：`allowPreviewName`、`allowPreviewText`、`PREVIEW_ALLOW`。
7. 改 `ts/packages/ui/src/server.ts`：建两张表、`writeRoutes` 进 `extraRoutes`、空闲判定加 `operations.active() > 0`、`ServeOverrides.confirmationTtlMs`；`readRoutes`/`eventRoutes`/`jobRoutes` 三个记号、IdleTimer 的位置、关停先 `hub.close()` 一律不动。
8. 替身用例（新建 `ts/packages/ui/test/write-routes.test.ts` 与 `ts/packages/ui/test/fixtures/fake-write-kernel.mjs`）：替身按 argv 里有没有 `--dry-run` 分两支——预览一支把 `FAKE_WRITE_PREVIEW` 给的 JSON 打到 stdout；执行一支按 `FAKE_WRITE_PLAN` 走，取值 `ok` / `stale` / `audit-fail` / `pause`；`pause` 先往 stdout 写一行 `FAKE_WRITE_BEGIN` 再等门文件 `FAKE_WRITE_GATE` 出现；begin 与 end 行照既有替身的格式记进 `FAKE_KERNEL_REPORT`（同一份报告文件、同一套字段）。用例照 `ts/packages/ui/test/support.ts` 的 `startAppWithHub` 写法在进程内建 app（自己实现 `RunKernel` 的替身，或用 `KernelRunner` 指向新替身）。
9. 单元用例（新建 `ts/packages/ui/test/confirmations.test.ts` 与 `ts/packages/ui/test/operations.test.ts`）：TTL 边界、一次性、挤掉最早发出的、argv 绑定核对、状态机只走一次、八键投影、容量淘汰、`active()`。
10. 真内核用例（新建 `ts/packages/ui/test/write-real.test.ts`，**attempt 2**）：照 `kernel-real.test.ts` 的夹具与 `startService({entry:"overrides"})`；用 `THEMIS_PYTHON` 与 `scripts/pi_dispatch.py`；临时仓库里按 A4 建 `state.json` 造 RUNNING 的 attempt；断言审计里的 `actor` 是 `user-ui`、`confirmation` 是 `none`/`flag`（照 A8 用 `config history --json`）。
11. README（改 `ts/packages/ui/README.md`）：「最小 API」补预览与七条写路由；加「写操作」一节（确认号 60 秒、409 的三种提示、503、504、操作记录、断开不取消、部分写入与「结果未知」）；「已知限制」补本片的限制并写清 T020 接的 5 条；既有的段落逐字保留。
12. 跑 Validation commands 里与改动相关的检查，记录命令与结果；确认 `git status --porcelain --untracked-files=all` 只出现允许范围内的路径；写执行报告；遇到合同未定义的行为，停止并报告。

### 基准测试文件清单（门禁端据此锁定；执行端不许删改既有用例）

新加的六个文件（attempt 1 五个 + attempt 2 一个）：

- `ts/packages/ui/src/writeroutes.ts`（新；`WRITE_ACTIONS`、`WRITE_ARGV`、`validateWriteArgs`、`buildWriteArgv`、`T020_WRITE_COMMANDS`、`writeRoutes`）
- `ts/packages/ui/src/confirmations.ts`（新；`ConfirmationTable`、`CONFIRMATION_TTL_MS`、`MAX_CONFIRMATIONS`）
- `ts/packages/ui/src/operations.ts`（新；`OperationTable`、`MAX_OPERATIONS`、`operationView`）
- `ts/packages/ui/src/kernelenvelope.ts`（既有，追加 `output` 与 `--expect-state=<state>` 占位）
- `ts/packages/ui/src/redaction.ts`（既有，追加 `PREVIEW_ALLOW` 与两个校验函数）
- `ts/packages/ui/src/server.ts`（既有，追加接线）
- `ts/packages/ui/README.md`（既有，追加「写操作」一节）
- `ts/packages/ui/test/write-argv.test.ts`（新；W1–W4）
- `ts/packages/ui/test/write-routes.test.ts`（新；S1–S12）
- `ts/packages/ui/test/confirmations.test.ts`（新；C1–C5）
- `ts/packages/ui/test/operations.test.ts`（新；O1–O4）
- `ts/packages/ui/test/fixtures/fake-write-kernel.mjs`（新替身；计划 ok/stale/audit-fail/pause）
- `ts/packages/ui/test/write-real.test.ts`（新；R1–R5，attempt 2）

### 覆盖矩阵（用例文件 → 断言的内容；名字里的编号对着规划 §8 的目标编号）

- **W1**（`ts/packages/ui/test/write-argv.test.ts`）：`WRITE_ARGV` 的七条基础 argv，分别加 `--dry-run --json`、加 `--expect-state=v1;config=<64 个 0>`、加 `--yes`（plugins 的两条不加），都过内核真正的解析器（`kit_config.build_parser()` 与 `kit_plugins.build_parser()`，剥掉组名 `config`/`plugins`；照 `argv-templates.test.ts` 的 `parseWithKernel` 的写法在本文件里另写一份，`argv-templates.test.ts` 禁改），断言 `dry_run`、`json`、`expect_state` 解析出来是期望的值。
- **W2**（同文件）：遍历内核两个解析器里带 `--dry-run` 的子命令（照 `tests/test_kit_roles.py:1461` 的 `_preview_commands` 的写法），这个集合恰好等于本片 7 条的命令路径加上 `T020_WRITE_COMMANDS`（五条，用例里显式列出、注明归 T020）。
- **W3**（同文件）：七条基础 argv 里不出现 `--dry-run`、`--json`、`--expect-state`、`--yes`。
- **W4**（同文件）：`validateWriteArgs` 的每一类不合格各一例（正文不是对象、action 不合法、未知键、缺必填键、每个参数各自的取值不合格），提示原文固定、不回显请求里的值；T020 的五个 action 名回 400「action 不合法」。
- **R1（U6b）**（`ts/packages/ui/test/write-real.test.ts`）：预览 `role.set` 成功 → 用 CLI 写一次配置（`config set kill_grace_seconds 20`）→ 用同一个确认号执行 → 回 409、`exit_code` 是 4、配置与审计文件逐字节不变；操作记录是 `stale`。
- **R2（U7）**（同文件）：经界面执行一次 `role.set` → `config history --json` 的最后一条 `actor` 是 `user-ui`、`confirmation` 是 `none`；再建一个 RUNNING 的 attempt（按 A4）并改变 execution 的绑定 → 预览的 `needs_yes` 为真 → 执行时带上 `--yes` → `confirmation` 是 `flag`。
- **R3（U8）**（同文件）：先预览（此时没有 attempt，`needs_yes` 为假）→ 再建 RUNNING 的 attempt → 执行：内核退出 1，提示里有 `--yes`，配置不变，信封的 `messages` 里有内核的提示，操作记 `failed`/`exit`。
- **R4（U20）**（同文件）：`role.set` 把某个角色绑到一个没接通这个角色的适配器上 → 信封的 `output` 里有那条 `WARN  …`，`ok` 为真。
- **R5（U15）**（同文件）：预览前后 `<repo>/.agent/` 逐字节不变（预览不写任何文件）。
- **S1（U6 缺号/格式不对）**（`ts/packages/ui/test/write-routes.test.ts`）：缺 `confirmation`、不是字符串、格式不对、不在表里 → 409「确认号无效、已过期或已用过：请重新预览」；替身没有执行记录。
- **S2（U6 过期）**：注入的时钟拨过 60 秒 → 409；替身没有执行记录。
- **S3（U6 用第二次）**：同一个号用第二次 → 409；替身的执行只记了一次。
- **S4（U6 换参数）**：同一个号换参数（argv 不符）→ 409「确认号与这次请求的参数不符：请重新预览」，**号仍可以按原参数用**（随后按原参数执行成功）；替身只在后一次有执行记录。
- **S5（并发）**：同一个号同时发两个请求 → 一个 200、一个 409；替身只执行一次。
- **S6（503）**：`maxConcurrent=1`、`maxQueue=0`，先用 `pause` 计划占住名额 → 第二个写请求回 503 且带 `retry-after: 2`；放行之后，同一个号重试成功（503 没有消耗确认号）。
- **S7（表满）**：发 101 个确认号 → 第 1 个回 409，第 101 个能用（表满时挤掉最早发出的未用号）。操作表满了而且没有可淘汰的终态记录 → 回 503，且确认号不消耗（单元用例）。
- **S8（needs_yes）**：确认号记录里的 `needs_yes` 为假时，执行 argv 里没有 `--yes`；为真时有。
- **S9（令牌）**：执行时替身记下的 `--expect-state=` 与内核预览给的逐字相同；预览信封里没有 `state` 键、正文里也不出现令牌原文；`command` 里是 `--expect-state=<state>`。
- **S10（预览不合格）**：替身回一个 `action` 不同的预览 → 服务回 500「内核的预览不合格」、不发确认号；替身给一个形状不对的 `state` → 同样回 500。
- **S11（预览失败）**：替身退出 1 → 回 200、`ok` 为假、`data` 里没有 `confirmation`；确认号表与操作表都不变。
- **S12（U19/U21）**：U19——替身往 stdout 写「已设置…」、往 stderr 写「ERROR: 已写入 …，但审计记录不全…」、退出 1 → 信封 `ok` 为假，`output` 与 `messages` 都在。U21——用 AbortController 发写请求、替身走 `pause` 计划：读到 begin 行之后就断开（不靠计时）→ 建门文件 → 替身往 stdout 写 WARN、往 stderr 写 ERROR、退出 1 → 轮询 `GET /api/v1/operations/<id>` 直到终态：`state` 是 `failed`，`envelope.output` 里有 WARN、`envelope.messages` 里有 ERROR，替身的报告里有 end 行（子进程没被杀）；查一个不存在的号 → 404。
- **S13（超时）**：时限覆盖成 1 秒、替身挂住 → 504，操作记 `timed_out`，进程树被结束。
- **C1**（`ts/packages/ui/test/confirmations.test.ts`）：TTL 的边界（正好 60 秒仍有效、过 60 秒无效）。
- **C2**：确认号一次性（取走后不在表里）。
- **C3**：表满时先清过期的；清完还满就挤掉最早发出、还没用的那个。
- **C4**：绑定核对——argv 长度不同或有一项不同即判不符；`state`/`needs_yes`/`action` 记在表里。
- **C5**：编号是 43 位 base64url（形状 `^[A-Za-z0-9_-]{43}$`）。
- **O1**（`ts/packages/ui/test/operations.test.ts`）：状态机每一步只走一次（重复 settle 忽略）。
- **O2**：`operationView` 的八键投影（键一个不少、值可为 null）。
- **O3**：容量 100，满了淘汰最早结束的终态记录；没有可淘汰的回 503。
- **O4**：`active()` 数的是非终态记录。

### 变异清单（验收端 mutate 用；每条写明会让哪条用例变红）

1. 确认号不过期（去掉 TTL 判断）→ S2、C1。
2. 确认号能用第二次（核对通过之后不删除）→ S3、C2。
3. 不核对 argv → S4、C4。
4. 基础 argv 里混进 `--dry-run` → W3；执行模板会同时给 `--dry-run` 与 `--expect-state`，内核报用法错 → S1/S8 的 argv 断言与 R2。
5. 执行时不带 `--expect-state` → S9（argv 断言）与 R1（不回 409）。
6. `needs_yes` 为假也带 `--yes` → S8 与 R2（`confirmation` 会记成 flag）。
7. 退出 4 不转 409 → R1 与 S12 里的 stale 情形。
8. 503 也把确认号算用掉 → S6 的重试那一步。
9. 预览信封里留着 `state` → S9、S10。
10. 预览失败也发确认号 → S11。
11. 写请求断开时取消子进程（把 `request.signal` 传给执行器）→ S12（没有 end 行，终态是 `failed`/`closing`）。
12. 操作记录不留 `messages` → S12 与 S12 的 U19 那半。
13. 预览的 `action` 不核对 → S10。
14. `displayArgv` 不把 `--expect-state` 换成 `<state>` → S9（令牌原文的断言）。
15. 两个并发请求都被接受（先 `await` 再标成已用）→ S5。
16. 表满时不清过期、不挤掉最早发出的 → S7、C3。
17. `output` 恒为空 → R4 与 S12。
18. 空闲判定不看操作表 → S13 的静态断言，加上 T017 的空闲用例照常。
19. argv 不符也消耗确认号 → S4 的后半段（号仍可用）。
20. args 有未知键也放行 → W4（替身没有调用记录）。
21. 预览不核对 `state` 的形状 → S10（替身给坏令牌时回 500）。

## Setup
- S01：`bun install --frozen-lockfile` · cwd：ts · 超时：900s

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t019_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`bun install --frozen-lockfile` · cwd：ts · 超时：900s · 期望退出码：0
- V02（必要）：`bun x vitest run packages/ui` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V03（必要）：`bun x vitest run packages/contracts/test/ui.contract.test.ts packages/contracts/test/source-hygiene.test.ts packages/contracts/test/status-inputs.test.ts` · cwd：ts · 超时：600s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V04（必要）：`bun x vitest run` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V05（必要）：`bun x tsc -p tsconfig.json --noEmit` · cwd：ts · 超时：900s · 期望退出码：0
- V06（必要）：`python -m pytest tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py -k static -q` · cwd：仓库根 · 超时：900s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V07（必要）：`git status --porcelain --untracked-files=all` · cwd：仓库根 · 超时：120s · 期望退出码：0 · 输出须匹配：`ts/packages/ui/`，不得出现：`(?m)^\s*\S+\s+(?!ts/packages/ui/)`
- V08（必要）：`node -e "const fs=require('fs');const s=fs.readFileSync('packages/ui/README.md','utf8');const need=['preview','confirmation','operations','--expect-state','409','503','504','60','已知限制','T020'];const miss=need.filter((x)=>!s.includes(x));if(miss.length){console.error('README missing: '+miss.join(','));process.exit(1)}console.log('README ok')"` · cwd：ts · 超时：120s · 期望退出码：0 · 输出须匹配：`README ok`
- V09（必要）：`node -e "const {spawnSync}=require('child_process');for(let i=0;i<5;i++){const r=spawnSync(process.execPath,['node_modules/vitest/vitest.mjs','run','packages/ui/test/write-argv.test.ts','packages/ui/test/write-routes.test.ts','packages/ui/test/confirmations.test.ts','packages/ui/test/operations.test.ts'],{stdio:'inherit'});if(r.status===0){continue}console.error('run '+(i+1)+' failed');process.exit(1)}console.log('STABLE5')"` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`STABLE5`

## 检查清单
合同里被引用的检查 id 只有下面这些。Definition of done 的「证据」字段只允许填这里定义的 id，不得填 W/R/S/C/O 编号，也不得填未定义的 id。

| id | 检查什么 | 命令（见 Validation commands） | 通过判据 |
|---|---|---|---|
| G01 | T019 的门禁基准测试（基线应失败；门禁端写好后由内核做成基线提交） | `python -m pytest tests/test_gate_t019_baseline.py -q` | 退出码 0 且输出匹配 `\d+ passed` |
| R01 | T001–T018 的门禁回归（基线应通过） | `python -m pytest tests/test_gate_t001_baseline.py … tests/test_gate_t018_baseline.py -q` | 退出码 0 且输出匹配 `\d+ passed` |
| V01 | 依赖按锁文件装好 | `bun install --frozen-lockfile`（cwd：ts） | 退出码 0 |
| V02 | ui 包自己的用例全过（含本片 W1–W4、S1–S13、C1–C5、O1–O4 与 attempt 2 的 R1–R5） | `bun x vitest run packages/ui`（cwd：ts） | 退出码 0 且输出匹配 `Tests[^\n]*[1-9]\d*[^\n]*passed` |
| V03 | 内核契约相关的三个用例文件全过 | `bun x vitest run packages/contracts/test/ui.contract.test.ts packages/contracts/test/source-hygiene.test.ts packages/contracts/test/status-inputs.test.ts`（cwd：ts） | 同上 |
| V04 | 全量 vitest 全过 | `bun x vitest run`（cwd：ts） | 同上 |
| V05 | 类型检查 | `bun x tsc -p tsconfig.json --noEmit`（cwd：ts） | 退出码 0 |
| V06 | T016–T018 的静态钉子没破（19 条读路由、既有白盒用例清单、README 结构、server.ts 的三个记号与 IdleTimer 位置） | `python -m pytest tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py -k static -q`（cwd：仓库根） | 退出码 0 且输出匹配 `\d+ passed` |
| V07 | 改动范围：只出现允许范围内的路径 | `git status --porcelain --untracked-files=all`（cwd：仓库根） | 只出现 `ts/packages/ui/` 下的路径 |
| V08 | README 写到了写操作的关键结论（preview、confirmation、operations、--expect-state、409、503、504、60 秒、已知限制、T020） | `node -e "…"`（cwd：ts） | 退出码 0 且输出 `README ok` |
| V09 | 稳定性：本片四个新用例文件连跑 5 次都过（全量并行下也稳） | `node -e "…"`（cwd：ts） | 退出码 0 且输出 `STABLE5` |

## Definition of done
- D01：七个写动作的登记与校验——`validateWriteArgs` 的每一类不合格都回 400 且提示固定、不回显请求里的值、不起子进程；T020 的五个 action 名回 400「action 不合法」；`buildWriteArgv` 拼出的基础 argv 与 `WRITE_ARGV` 逐条一致，且不含 `--dry-run`、`--json`、`--expect-state`、`--yes`；用例：`ts/packages/ui/test/write-argv.test.ts` 的 W3、W4；证据：V02；目的：不合法与不认识的动作到不了内核，服务也不给攻击者反馈。
- D02：argv 过内核真正的解析器——七条基础 argv 加 `--dry-run --json`、加 `--expect-state=v1;config=<64 个 0>`、加 `--yes`（plugins 不加）都过 `kit_config.build_parser()` 与 `kit_plugins.build_parser()`，解析出的 `dry_run`、`json`、`expect_state` 是期望的值；内核里带 `--dry-run` 的写命令集合恰好等于本片 7 条加 `T020_WRITE_COMMANDS` 的 5 条；用例：`ts/packages/ui/test/write-argv.test.ts` 的 W1、W2；证据：V02；目的：命令行是内核真认的写法，不是照着猜的。
- D03：预览成功时的形状——stdout 解析成对象、`dry_run` 为真、`action` 与请求相同、`state` 过 `^v1(?:;(?:config|local)=(?:[0-9a-f]{64}|absent))+$`、`needs_yes` 是布尔；去掉 `state` 之后过 `redactJson(…, PREVIEW_ALLOW)`；回 200，信封的 `data` 是 `{"preview": …, "confirmation": "<43 位>"}`，信封仍是七字段；预览信封的任何层级都没有 `state` 键，正文里不出现令牌原文；用例：`ts/packages/ui/test/write-routes.test.ts` 的 S9、S10 与 `ts/packages/ui/test/write-argv.test.ts` 的 W4；证据：V02；目的：令牌不外泄，预览能显示内核算出来的变化。
- D04：预览不合格与预览失败——形状不合格（`action` 不对、`state` 不对）回 500「内核的预览不合格」、不发确认号；内核退出非 0 回 200、`ok` 为假、`data` 里没有 `confirmation`，确认号表与操作表都不变；用例：S10、S11；证据：V02；目的：不合格的预览不会变成一个能执行的确认号。
- D05：确认号的核对次序——缺号/不是字符串/格式不对/不在表里/已过期/用第二次一律 409「确认号无效、已过期或已用过：请重新预览」；argv 不符 409「确认号与这次请求的参数不符：请重新预览」且**不**消耗这个号；503（队列满或关停中）**不**消耗这个号；用例：S1–S4、S6；证据：V02；目的：界面能分清「重新预览」与「参数变了」，重试不会白白丢掉确认号。
- D06：确认号的一次性与表满——同一个号只能用一次；表满 100 时先清过期的、再挤掉最早发出还没用的那个（第 1 个号回 409、第 101 个号能用）；TTL 是 60 秒，过期即失效；用例：S3、S7、C1、C2、C3、C5；证据：V02；目的：失控的客户端不会把服务堵死，过期的令牌也不会一直能用。
- D07：执行的 argv——起的是 `基础 argv + --expect-state=<state>`，`needs_yes` 为真才加 `--yes`（plugins 的 needs_yes 恒为假，不加也不写特例），不带 `--json`；替身记下的 `--expect-state=` 与预览给的逐字相同；用例：S8、S9 与 R2；证据：V02；目的：带令牌执行、该确认时才确认，写命令的形态是内核认的。
- D08：结果与 HTTP 状态——退出 0 回 200 信封；退出 4 回 409 且正文是七字段信封（`exit_code` 是 4、`messages` 里有内核的 ERROR）、操作记 `stale`；其他非 0 回 200 且 `ok` 为假、操作记 `failed`/`exit`；超时回 504、操作记 `timed_out`；起不了子进程或输出超限回 500；用例：S12、S13 与 R1、R3；证据：V02；目的：界面能分清「写成了」「配置变了要重新预览」「没写成」「超时」。
- D09：信封补 `output`——写命令的 `output` 是 stdout 的非空行、逐行过 `redactSecrets`，`messages` 是 stderr 里 ERROR/WARN 开头的行，`command` 是 `displayArgv(实际 argv)` 且 `--expect-state=<state>` 的值是占位；读路由的信封逐字节不变（`output` 仍是 `[]`）；用例：S9、S12 与 R4；证据：V02、V06；目的：界面能显示内核写了什么，同时令牌不外泄、读路由不被带坏。
- D10：操作记录——状态机 `queued → running → succeeded | failed | stale | timed_out` 每一步只走一次；`operationView` 是八键投影；`GET /api/v1/operations/<id>` 的正文就是它，格式不对与查不到回同一个 404「没有这个操作」；容量 100，满了淘汰最早结束的终态记录，没有可淘汰的回 503 且不消耗确认号；用例：S7、S12、O1、O2、O3、O4；证据：V02；目的：断线之后界面能靠操作号把结果读回来。
- D11：断开不取消——写请求的客户端断开之后，子进程不被杀（替身的报告里有 end 行），终态照记；写运行用服务私有的信号，`request.signal` 不传给执行器；用例：S12；证据：V02；目的：界面断线不会把正在写的配置留在半途而「没人知道」。
- D12：二道脱敏——预览只放行 `binding_changes.*.before|after` 的七个绑定字段、`resources.*.changed_keys.*`、`notes.*`、`warnings.*`、`running_attempts.*`；放行的值要么是 `allowPreviewName` 认的形状（null 或名字），要么是 `redactSecrets(v) === v` 的文字；`unreadable` 不进白名单；用例：S9（令牌原文的断言）与 W4；证据：V02；目的：预览能显示变化，但不因此把凭据值放出去。
- D13：接线与空闲——`server.ts` 建两张表、`writeRoutes` 进 `extraRoutes`（`readRoutes`/`eventRoutes`/`jobRoutes` 三个记号与 IdleTimer 的位置不动、关停仍先 `hub.close()`）；空闲判定加上 `operations.active() > 0`，有写在跑时服务不因空闲退出；用例：S13 的静态断言与 T017 的空闲用例；证据：V02、V06；目的：写操作期间服务不会被空闲计时器关掉。
- D14：真内核的四条——U6b：预览后用 CLI 改配置再执行 → 409、`exit_code` 是 4、配置与审计逐字节不变、操作记 stale；U7：经界面执行的审计 `actor` 是 `user-ui`、`confirmation` 是 `none`，有 RUNNING 的 attempt 且改变 execution 的绑定时 `needs_yes` 为真、执行带 `--yes`、`confirmation` 是 `flag`；U8：先预览再建 RUNNING 的 attempt 再执行 → 内核退出 1、提示里有 `--yes`、配置不变、操作记 failed/exit；U20：绑到未接通该角色的适配器 → `output` 里有那条 WARN、`ok` 为真；用例：`ts/packages/ui/test/write-real.test.ts` 的 R1–R4；证据：V02；目的：确认号、令牌与 `--yes` 的语义在内核那侧真的成立，不是服务自己假装。
- D15：预览不写盘——预览前后 `<repo>/.agent/` 逐字节不变；用例：R5；证据：V02；目的：预览只是预览。
- D16：README——「最小 API」补预览与七条写路由；加「写操作」一节（确认号 60 秒、409 的三种提示、503 与 `Retry-After: 2`、504、操作记录、断开不取消、部分写入与「结果未知」）；「已知限制」补本片限制并写清 T020 接的 5 条；既有的段落逐字保留；证据：V08；目的：界面前端拿这份 README 就能把预览与写操作接上。
- D17：范围与依赖——改动只落在 Scope 的允许集合内；`ts/packages/ui/src/localhttp/**`、`cursors.ts`、`readroutes.ts`、`ts/packages/ui/package.json`、`ts/bun.lock`、`ts/package.json` 一个字未改；没有新增、升级或删除依赖；证据：scope、V07、review；目的：内核禁区、本机 HTTP 的安全基线与既有读路由不受本片影响。
- D18：门禁与回归——G01、R01、V01–V09 全部通过；既有用例未删未跳未弱化（ui 测试目录里没有 skip、only、todo）；21 条变异每条都有会变红的用例；证据：G01、R01、V01、V02、V03、V04、V05、V06、V07、V08、V09、review；目的：不靠削弱测试过关，也不破坏已有门禁。
- D19：稳定性——本片的用例文件连跑 5 次都通过（全量并行下也稳）；证据：V09；目的：偶发红不能靠重跑蒙过去。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `routes.ts` 的 `Route` 没有 `handle`、`kernelenvelope.ts` 的 `envelopeBody` 不再是七字段、`kernel.ts` 的 `run` 签名变了、`jobs.ts` 里没有 `JobTable`/`jobView`、503 不再带 `Retry-After: 2`）。
- 内核的写命令与本片写死的不一致：`config role set` / `config preset save|use|remove` / `config rollback` / `plugins enable|disable` 的位置参数或选项名变了；`--dry-run --json` 的预览 JSON 不再是 `dry_run`/`action`/`state`/`needs_yes` 那几个键；`--expect-state` 不对时不再是退出码 4；带 `--dry-run` 的写命令集合不再是 12 条。遇到这些就停下报告，不许自己改内核或换一种做法。
- 必须修改允许范围之外的文件才能继续（例如必须改 `ts/packages/ui/src/readroutes.ts` 才能加路由、必须改 `ts/packages/ui/test/harness.ts` 才能起真服务、必须改 `scripts/**` 才能加选项、必须改 `ts/packages/ui/package.json` 才能加依赖）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限：先交出已完成的部分（attempt 1 的框架与替身/单元用例），把 `write-real.test.ts` 留给 attempt 2，并在执行报告里写明。

## Budget
- max_attempts_total: 3（按 task-id 汇总，包括返工版本；本任务此前已用 0 次）
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 16200（已用 0 秒；= 3 倍单次时限，给这一版留 2 次 attempt）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：预检 300s、确认号与操作记录 600s、写路由与校验 900s、信封与脱敏 300s、替身与单元用例 1200s、真内核用例 1200s、README 300s、必要检查（含稳定性）900s、最终报告 200s；总计 5900s，超过单轮时限 5400s 的部分归到 attempt 2（真内核用例），两个 attempt 各按自己的时限走。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D19，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
