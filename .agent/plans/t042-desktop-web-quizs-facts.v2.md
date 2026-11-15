# TASK: t042-desktop-web-quizs-facts

<!-- 合同正文。执行端只看这份合同与机器合同摘要，看不到规划报告与信箱；下面写到的每条事实都已核对过。 -->

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: d2fe3db4139109e2fc7c4a1ef6cde45cca113182
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
给本机服务（`ts/packages/ui`）加两条只读的 Quizs 路由——`GET /api/v1/quizs/providers` 与 `GET /api/v1/quizs/live`——并给它们各配一份逐字段的脱敏白名单：能显示的字段（提供方、模型、思考档位、计费方式、live 的来源/状态/到期时刻/问题）按形状放行，其余字段照既有口径走；两份新的服务侧用例（替身 + 真内核）把 argv、信封、退出码、超时与白名单的遮盖行为钉住；`ts/packages/ui/README.md` 的条数与路由表同步到 22 条。

## Non-goals
- 不做前端：`desktop/web/**` 一个字不改（`api.ts` 的读函数、桩、`RuntimesPage.tsx`、运行时页的 Quizs 区块、前端测试是另登记的 T043）。
- 不改 `ts/packages/ui/src/server.ts`（两条路由进 `readRoutes()` 就自动进 `kernelAnsweredRoutes`）。
- 不改内核：`scripts/**` 一个字不改（`scripts/kit_roles.py`、`scripts/kit_config.py` 已有 `config quizs providers|live --json`）。
- 不碰 `src/live/**`、不改 `desktop/web/src/live/**`、不新增依赖、不改任何依赖清单与锁文件（`ts/bun.lock`、`ts/package.json`）。
- 不改任何门禁文件（`tests/test_gate_*.py`）；R1–R3 三处门禁放宽由站主自己落盘，已在本基线里。
- 不做 Quizs 的续期、资格认证、凭据录入、岗位绑定，也不改 Quizs 仓库本身。
- 不改既有 20 条读路由与 14 条写路由的路径、时限与信封口径。

## Repository facts
- 基线：`53f2d47aa56dfdcacc868a9589384c423fc803ec`（T041 已全部结项；站主 2026-11-14 的门禁放宽也已在这个基线里）。
- 入口：`ts/packages/ui/src/readroutes.ts`
  - 现状 20 条只读路由；文件头注释写「20 条只读数据路由」；`readRoutes(state, timeouts)` 返回路由数组，最后一条是 `api.hub.roles.get`（`exact("/api/v1/hub/roles")`，走 `jsonRoute`，白名单 `HUB_ROLES_ALLOW`，时限 `DEFAULT_TIMEOUT`）。
  - `READ_ROUTE_ARGV`（20 个模板，键是路由名）与 `READ_ROUTE_SPECS`（20 行登记项 `{name, path, timeoutSeconds}`，顺序与 `readRoutes()` 一致）；`READ_ROUTE_SPECS` 的注释里有「api.hub.roles.get 是第 20 条（追加在表末）」这句。
  - `jsonRoute(state, argv, timeoutSeconds, input, allow)`：跑完照信封回 200（退出非 0 也是 200，`ok` 为假、`exit_code` 原样）；超时回 504（`runResponse` → `timeoutEnvelope`）；`data` 过 `redactJson(data, allow)`；`messages` 只留 stderr 里 `ERROR`/`WARN` 开头的行。
  - `at(name, fallback)` 是测试入口的时限覆盖（路由名 → 秒）。
  - 时限常量都在文件头导出：`META_TIMEOUT=15`、`DEFAULT_TIMEOUT=30`、`FILE_TIMEOUT=60`、`USAGE_TIMEOUT=120`、`SECRET_ITEM_TIMEOUT=30`、`SECRETS_TOTAL_TIMEOUT=120`。
- 白名单：`ts/packages/ui/src/redaction.ts`
  - 已导出 `allowEnum(...choices)`（值相等且类型相同）、`allowBindingName`（字符串过名字形状，允许 null）、`allowPreviewText`（字符串且过 `redactSecrets` 原样不变）、`allowPreviewName`。
  - `AllowList` 的路径语法（`ts/packages/base/src/secrets.ts`）：路径是键名序列，`*` 匹配任意键名或数组下标；命中路径的值若校验不过，整条变成 `<redacted>`；没有命中任何路径的字符串照 `redactSecrets` 过一遍；键名像凭据（`token`、`secret`、`credential` 等）的值一律 `<redacted>`；数字（`bigint` 与 `number` 两种都算）不额外处理。
- 内核（本片只读、只跑，不改）：
  - `scripts/kit_config.py:1687-1694`：`config` 组下已有 `quizs` 子命令，`providers` 与 `live` 两个动作都带 `--json`；因此 `config quizs providers --json` 与 `config quizs live --json` 能过 `argv-templates.test.ts` 用例里内核真正的解析器。
  - `scripts/kit_roles.py:1324-1440`：`QUIZS_TIMEOUT=30`（内核自己每次调 Quizs 的时限）、`QUIZS_LIVE_STATES=("ready","expired","build_mismatch","invalid","missing")`、`QUIZS_LIVE_NAMES=("plan.json","profile.json","qualification.json")`、`QUIZS_LIVE_ENV=("QUIZS_LIVE_PLAN","QUIZS_PROVIDER_PROFILE","QUIZS_QUALIFICATION")`、`QUIZS_PROFILE_IDS`（deepseek/minimax/stepfun）。
  - `quizs_command()`：`QUIZS_CMD` 是 JSON 的字符串列表，缺省是 PATH 里的 `quizs`；内核跑 `QUIZS_CMD + ["providers","list"]` 与 `QUIZS_CMD + ["live","status","--live-dir", <目录>]`，要求 stdout 是 `schema_version` 分别等于 `quizs.providers.v1` 与 `quizs.live-status.v1` 的 JSON 对象。
  - `config quizs providers --json` 的 stdout：`{"build_id": …, "providers": [ {…provider…} ]}`，每个 provider 里有 `provider`、`id`、`model`、`thinking`（档位数组）、`billing`。
  - `config quizs live --json` 的 stdout：`{"live": [ {"source": "mailbox"|"env", "provider": …|null, "live_dir": …|null, "problem": …|null, "status": {…}|null} ]}`；某一套读不出来时内核只在该行的 `problem` 里写原因，整条命令照常退出 0。
- 仓库外事实（站主 2026-11-14 核实，合同按事实写）：
  - `billing` 是字符串枚举，取值在 `none_test_only`、`step_plan_credits`、`deepseek_prepaid_balance` 之内。
  - `thinking` 是档位数组，取值在 `off`、`low`、`medium`、`high`、`xhigh`、`max` 之内。
  - live 的时间字段：`certificate.issued_at_ms`、`certificate.expires_at_ms`、`plan.expires_at_ms` 是毫秒整数；`profile.valid_until` 是带毫秒的 ISO 8601 UTC 字符串，可为 null。
  - `QUIZS_CMD` 与三个 `QUIZS_LIVE_*` 设在用户级环境变量里。
  - 本机没设 `QUIZS_CMD` 时：`config quizs providers --json` 每套 problem 写「quizs live status 失败（退出码 127）」一类的原因且命令退出 0（`providers` 退出 1）；装原生启动器的机器上才是用法错误。
- 门禁（本基线已含站主 2026-11-14 的放宽，执行端不碰门禁文件）：
  - `tests/test_gate_t031_baseline.py` 的条数检查已改成只认写明了条数（`readroutes.ts` 文件头有「N 条」即可）；对 `routes-auth.test.ts` 的 `toBe(N)`、`kernel-runner.test.ts` 的时限数组、`argv-templates.test.ts` 的 `toHaveLength(N)` 只认「不少于 20」；`READ_ROUTE_SPECS` 里 `api.hub.roles.get` 仍按「不早于第 20 个」判。
  - `tests/test_gate_t031_baseline.py` 的 README 静态断言：README 里要有「N 条只读数据路由」的说法，「连接空闲超时」那一条要写成「N 条读路由、预览、M 条写路由」，`GET /api/v1/hub/roles`、`POST /api/v1/hub/roles/<post>` 两行不许丢。
- 既有三份被改动的用例（都在允许范围内）：
  - `ts/packages/ui/test/routes-auth.test.ts`：`READ_ROUTE_EXAMPLES` 20 行 + `expect(listed.length).toBe(20)`。
  - `ts/packages/ui/test/kernel-runner.test.ts`：`CASES` 22 行（`api.attempts.list` 有两条）+ `expect(READ_ROUTE_SPECS.map((spec) => spec.timeoutSeconds)).toEqual([…20 个值…])` + 一条「时限照合同：15/30/60/120 四档」的用例（它对每条 spec 断言：不是 15/60/120 就必须是 30）。
  - `ts/packages/ui/test/argv-templates.test.ts`：`expect(READ_ROUTE_SPECS).toHaveLength(20)`。
- 工具链与锁文件：`ts` 用 Bun（`ts/package.json` 的 `packageManager` 是 `bun@1.4.2`，有 `bun.lock` 与 `bunfig.toml`）；vitest 按 `node node_modules/vitest/vitest.mjs run …` 调用（cwd `ts`）；类型检查按 `node node_modules/typescript/bin/tsc -p tsconfig.json`（cwd `ts`）；仓库门禁用 `python -m pytest`。本片不改任何依赖清单与锁文件；`bun install --frozen-lockfile` 只按锁文件重链。
- 基线检查：R01 列出的各片基线测试在本基线上应全绿；G01（`tests/test_gate_t042_baseline.py`）由门禁端稍后写好并由内核做成基线提交，在本基线上应失败。

## Scope
- allowed_modified_files:
  - ts/packages/ui/src/readroutes.ts
  - ts/packages/ui/src/redaction.ts
  - ts/packages/ui/test/routes-auth.test.ts
  - ts/packages/ui/test/kernel-runner.test.ts
  - ts/packages/ui/test/argv-templates.test.ts
  - ts/packages/ui/README.md
  - ts/packages/ui/test/quizs-routes.test.ts
- allowed_new_files:
  - ts/packages/ui/test/quizs-routes.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t042_*.py
  - tests/test_gate_*.py
  - desktop/web/**
  - ts/packages/ui/src/server.ts
  - ts/packages/ui/src/app.ts
  - ts/packages/ui/src/writeroutes.ts
  - ts/packages/ui/src/jobroutes.ts
  - ts/packages/ui/src/live/**
  - scripts/**
  - src/live/**
  - ts/package.json
  - ts/bun.lock
  - desktop/web/package-lock.json
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
- 正常输入：
  - `GET /api/v1/quizs/providers`：服务起一个内核子进程，命令行是 `[python, kernel, "--repo", <仓库>, "config", "quizs", "providers", "--json"]`（argv 列表、不经 shell），时限 60 秒。回七字段信封，`data` 是内核 stdout 的 JSON 过 `QUIZS_PROVIDERS_ALLOW` 之后的结果（形状 `{"build_id": …, "providers": [ {provider, id, model, thinking[], billing, …} ]}`）。
  - `GET /api/v1/quizs/live`：命令行同上但 argv 是 `["config", "quizs", "live", "--json"]`，时限 150 秒。`data` 形状 `{"live": [ {"source", "provider", "live_dir", "problem", "status"} ]}`。
  - 两条路由都要会话（不标 `public`），与既有 20 条读路由同一口径。
- 白名单（逐字段，就这两份；服务不另做投影，没登记的字段走 `redactJson` 的默认口径）：
  - `QUIZS_PROVIDERS_ALLOW`（4 条路径）：
    - `providers.*.provider` → 名字形状（用现成的 `allowBindingName`：字符串过 `^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$` 且不像凭据；null 也放行）。
    - `providers.*.model` → 同上（`allowBindingName`）。
    - `providers.*.thinking.*` → 枚举 `off`、`low`、`medium`、`high`、`xhigh`、`max`（六个值；不在集合里的元素变成 `<redacted>`）。
    - `providers.*.billing` → 枚举 `none_test_only`、`step_plan_credits`、`deepseek_prepaid_balance`。
  - `QUIZS_LIVE_ALLOW`（8 条路径）：
    - `live.*.source` → 枚举 `mailbox`、`env`。
    - `live.*.provider` → 名字形状或 null（`allowBindingName`）。
    - `live.*.problem` → null 或一条本来就不像凭据的自由文字（在 `redaction.ts` 里加一个「可空版」的自由文字校验函数：null 放行，否则沿用 `allowPreviewText` 的口径）。
    - `live.*.status.problem` → 同上。
    - `live.*.status.state` → 枚举 `ready`、`expired`、`build_mismatch`、`invalid`、`missing`。
    - `live.*.status.missing.*` → 枚举 `plan.json`、`profile.json`、`qualification.json`。
    - `live.*.status.certificate.expires_at_ms` → null 或非负整数（`bigint` 与 `number` 两种都接；`number` 要是整数且 ≥ 0）。
    - `live.*.status.profile.valid_until` → null 或带毫秒的 ISO 8601 UTC 字符串（形如 `2026-11-14T08:00:00.000Z`；以 `Z` 或 `+00:00` 结尾都算，带三 位毫秒）。
  - **不登记**（照 `redactJson` 的默认口径，不额外开口子）：`build_id`、`live_dir`、`plan.*`、`implementation_digest`、`capabilities`、`credential_*`、`*_tokens`——键名像凭据的（`credential`、`token` 等）值一律 `<redacted>`，其余走 `redactSecrets`。
- 边界输入：
  - 内核退出 0 但 stdout 不是合法 JSON → 500，信封 `messages` 是「ERROR: 内核输出不是合法的 JSON」（照 `jsonRoute` 原样）。
  - 内核退出非 0（例：没设 `QUIZS_CMD` 时 `providers` 退出 1）→ 仍回 200，信封 `ok` 为假、`exit_code` 原样、`messages` 里带内核的 `ERROR:` 原文、`data` 为 null（stdout 不是合法 JSON 时）。
  - 「某一套 live 读不出来」的语义原样透传：内核整条命令退出 0，`data.live` 里那一行只有 `problem` 有内容、`status` 为 null；服务不替它造状态、不把整条路由判成失败。
  - 超时 → 504，信封 `ok` 为假、`exit_code` 为 null、`data` 为 null、`messages` 只有一行「ERROR: 命令超时（N 秒），子进程已结束；请改用 CLI 查看」。
  - 客户端断开、服务关停、队列满 → 与既有读路由一致（503 / 取消）。
- 错误与重试：服务不重试、不缓存；界面重读即重跑一次内核命令。内核自己每次调 Quizs 的时限是 30 秒（`kit_roles.py` 的 `QUIZS_TIMEOUT`），路由的 60/150 秒比它长，内核自己的报错先回来。
- 并发、取消与状态变化：两条路由与其他读路由共用同一个执行器（同时最多 4 个子进程、FIFO 队列 16、队列满 503 带 `Retry-After: 2`）；请求的 `signal` 传给执行器（客户端断开即取消那一次运行）；服务关停时在跑的被取消、队列被清空、新请求 503。服务不数 live 的目录、不改执行器的并发与队列参数。
- 兼容性：服务的公开面只多两条 GET 路由；既有 20 条读路由、14 条写路由、SSE、作业、凭据录入的路径、时限、信封与错误映射一字不变；`server.ts` 不改（两条路由进 `readRoutes()` 就自动进 `kernelAnsweredRoutes`）。

## Steps
1. 确认 Setup 的 S01（`ts` 的 `bun install --frozen-lockfile`）跑过、`ts/node_modules` 在位；不在位就自己跑这条命令补装（不改任何依赖清单与锁文件）。装完先跑一遍 `node node_modules/vitest/vitest.mjs run packages/ui/test/routes-auth.test.ts`（cwd `ts`）确认 V01 能跑起来，再动代码。
2. 读 `ts/packages/ui/src/readroutes.ts`、`ts/packages/ui/src/redaction.ts`、`ts/packages/base/src/secrets.ts`、`scripts/kit_config.py`（`config quizs` 那一段）与 `scripts/kit_roles.py`（`--- quizs ---` 那一段），确认签名与「Repository facts」一致；不一致就停止并报告。
3. `ts/packages/ui/src/readroutes.ts`：
   - 文件头导出两个时限常量：`QUIZS_PROVIDERS_TIMEOUT = 60`、`QUIZS_LIVE_TIMEOUT = 150`（照 `META_TIMEOUT` 等既有常量的写法与注释）。
   - `READ_ROUTE_ARGV` 末尾加两条：`"api.quizs.providers.get": ["config", "quizs", "providers", "--json"]`、`"api.quizs.live.get": ["config", "quizs", "live", "--json"]`。
   - `readRoutes()` 末尾加两条路由项：`api.quizs.providers.get` → `exact("/api/v1/quizs/providers")`，`api.quizs.live.get` → `exact("/api/v1/quizs/live")`；处理器照 `api.hub.roles.get` 的写法走 `jsonRoute`，argv 逐字是上面模板里的三条，时限分别 `at("api.quizs.providers.get", QUIZS_PROVIDERS_TIMEOUT)` 与 `at("api.quizs.live.get", QUIZS_LIVE_TIMEOUT)`，白名单分别是 `QUIZS_PROVIDERS_ALLOW` 与 `QUIZS_LIVE_ALLOW`（从 `./redaction.ts` 导入）。
   - `READ_ROUTE_SPECS` 末尾加两行登记项：`{ name: "api.quizs.providers.get", path: "/api/v1/quizs/providers", timeoutSeconds: QUIZS_PROVIDERS_TIMEOUT }`、`{ name: "api.quizs.live.get", path: "/api/v1/quizs/live", timeoutSeconds: QUIZS_LIVE_TIMEOUT }`。
   - 条数：文件头注释、`readRoutes()` 的说明、`READ_ROUTE_SPECS` 的说明三处都改成 22 条；**保留**「api.hub.roles.get 是第 20 条（追加在表末）」这句原文，另在登记表的说明里补一句后面两条是本片加的 Quizs 读路由。不要改 `server.ts`。
4. `ts/packages/ui/src/redaction.ts`：加本片的两份白名单与它们用到的枚举/校验函数（照 `HUB_ROLES_ALLOW` 的写法与注释风格，注释里注明取值抄自 `scripts/kit_roles.py` 与站主核实的 Quizs 输出形状）：
   - `QUIZS_THINKING_ENUM = allowEnum("off", "low", "medium", "high", "xhigh", "max")`；
   - `QUIZS_BILLING_ENUM = allowEnum("none_test_only", "step_plan_credits", "deepseek_prepaid_balance")`；
   - `QUIZS_LIVE_SOURCE_ENUM = allowEnum("mailbox", "env")`；
   - `QUIZS_LIVE_STATE_ENUM = allowEnum("ready", "expired", "build_mismatch", "invalid", "missing")`；
   - `QUIZS_LIVE_FILE_ENUM = allowEnum("plan.json", "profile.json", "qualification.json")`；
   - 一个「可空自由文字」的校验函数（null 放行，否则沿用 `allowPreviewText` 的口径）；
   - 一个「非负整数毫秒」的校验函数（null 放行；`bigint` 与 `number` 都接，`number` 要是整数且 ≥ 0）；
   - 一个「带毫秒的 ISO 8601 UTC 字符串」的校验函数（null 放行；形如 `2026-11-14T08:00:00.000Z`，`Z` 与 `+00:00` 两种结尾都放行，三位毫秒要有）；
   - `QUIZS_PROVIDERS_ALLOW`（4 条路径）与 `QUIZS_LIVE_ALLOW`（8 条路径），路径与校验函数照「Behavior contract」的白名单一节逐条写死。
5. 改既有用例（照新行为改，不删、不弱化任何既有断言）：
   - `ts/packages/ui/test/routes-auth.test.ts`：`READ_ROUTE_EXAMPLES` 加两行——`"api.quizs.providers.get": "/api/v1/quizs/providers"`、`"api.quizs.live.get": "/api/v1/quizs/live"`；`expect(listed.length).toBe(20)` 改成 `toBe(22)`；文件头注释里的「20 条读路由」改成 22。
   - `ts/packages/ui/test/kernel-runner.test.ts`：`CASES` 末尾加两行（`name` 取新路由名、`path` 取上面的示例路径、`argv` 取 `READ_ROUTE_ARGV["api.quizs.providers.get"]` 与 `READ_ROUTE_ARGV["api.quizs.live.get"]`）；时限数组断言 `toEqual([…])` 从 20 个值改成 22 个值（末尾补 `60, 150`）；**同文件里那条「时限照合同：15/30/60/120 四档」的用例要一起改**：它的档位集合加上 150（否则新路由的 150 会被它判成「应该是 30」而红），并改成按名字断言这两条新路由的时限是 60 与 150；文件头注释里的「20 条读路由」改成 22。
   - `ts/packages/ui/test/argv-templates.test.ts`：`expect(READ_ROUTE_SPECS).toHaveLength(20)` 改成 `toHaveLength(22)`；文件头注释里的「20 条读路由」改成 22（这条用例会用内核真正的解析器逐条解析 `READ_ROUTE_ARGV`，新模板 `config quizs providers --json` 与 `config quizs live --json` 已被 `scripts/kit_config.py` 支持，照旧会过）。
6. 新增 `ts/packages/ui/test/quizs-routes.test.ts`（必跑，不标可选）。两部分都要有：
   - **替身部分**（照 `ts/packages/ui/test/kernel-runner.test.ts` 与 `test/support.ts` 的 `startApp` 写法，内核替身是 `test/fixtures/fake-kernel.mjs`）：两条路由各一条用例，断言替身报告里交出的 argv 逐字是 `["config","quizs","providers","--json"]` 与 `["config","quizs","live","--json"]`、信封七字段齐全（`ok`/`exit_code`/`data`/`output`/`messages`/`command`/`elapsed_ms`）；一条白名单用例：`FAKE_KERNEL_JSON` 给一份 providers 的 JSON，其中 `billing` 取一个不在三个枚举里的值、`thinking` 里放一个不在六个档位里的值、`credential_ref` 与 `access_tokens` 各给一个值，断言这三个字段在 `data` 里是 `<redacted>` 而 `provider`/`model` 原样；一条 live 用例：`FAKE_KERNEL_JSON` 给一份 live 的 JSON（`source`、`provider`、`status.state`、`status.certificate.expires_at_ms`、`status.profile.valid_until`、`status.missing` 三个文件名、`problem`），断言放行的字段原样、`status.state` 取错值时变 `<redacted>`、`status.missing` 里塞第四个文件名时那一条变 `<redacted>`；一条退出码用例：`FAKE_KERNEL_EXIT=1` 时回 200、`ok` 为假、`exit_code` 是 1；一条超时用例：用 `startApp({ timeouts: { "api.quizs.live.get": 1 } })` 与 `FAKE_KERNEL_SLEEP_MS=8000`，断言回 504、信封 `exit_code` 是 null、`messages` 只有一行「ERROR: 命令超时（1 秒），子进程已结束；请改用 CLI 查看」。
   - **真内核部分**（必跑）：起真的内核（`scripts/pi_dispatch.py`，解释器用 `process.env["THEMIS_PYTHON"] ?? "python"`，仓库用 `test/harness.ts` 的 `REPO_ROOT` 推出来的路径——**不许写死任何机器上的绝对路径**），在一个 git 夹具仓库上跑（照 `ts/packages/ui/test/hub-routes-real.test.ts` 的夹具写法：`git init` + 一次提交；不需要登记 runtime/profile）。把 `process.env["QUIZS_CMD"]` 设成 JSON 的字符串列表，指向夹具目录里自己写的假 Quizs 脚本（可以是一个 Node 脚本：`[process.execPath, "<夹具里的脚本路径>"]`），脚本按参数分两支：`providers` 打印 `{"schema_version":"quizs.providers.v1","build_id":"…","providers":[{"provider":"deepseek","id":"deepseek-api","model":"deepseek-chat","thinking":["off","high"],"billing":"step_plan_credits"}]}`；`live` 打印 `{"schema_version":"quizs.live-status.v1","state":"ready","certificate":{"expires_at_ms":1790000000000},"profile":{"valid_until":"2026-11-14T08:00:00.000Z"}}`；另备一个退�� 1 的分支（脚本按环境变量或参数决定退出码并往 stderr 写一行）。断言：
     - `GET /api/v1/quizs/providers` 回 200，信封的 `command` 逐字是 `["config","quizs","providers","--json"]`，`data.providers[0]` 的 `provider`/`model`/`thinking`/`billing` 与脚本给的一致；
     - `GET /api/v1/quizs/live` 回 200，信封的 `command` 逐字是 `["config","quizs","live","--json"]`；夹具仓库里放一套 live 文件（`<仓库>/.agent/mailbox/quizs-live/deepseek/` 下 `plan.json`、`profile.json`、`qualification.json`），断言 `data.live` 至少有一行 `source` 是 `mailbox`、`status.state` 是 `ready`、`status.certificate.expires_at_ms` 是那个毫秒整数、`status.profile.valid_until` 是那个带毫秒的 ISO 串；
     - 把 `QUIZS_CMD` 换成那个退 1 的脚本后，`GET /api/v1/quizs/providers` 仍回 200，但 `ok` 为假、`exit_code` 是 1、`messages` 里有内核的 `ERROR:` 原文；
     - 「某一套读不出来」的语义：让假脚本对 `live` 那一支以非 0 退出，断言整条路由回 200、`ok` 为真，`data.live` 里那一行的 `problem` 有内容（内核只在该行写原因、整条退出 0）。
     - 用完把 `QUIZS_CMD` 与三个 `QUIZS_LIVE_PLAN`/`QUIZS_PROVIDER_PROFILE`/`QUIZS_QUALIFICATION` 环境变量恢复原状（用完 `delete`，或在 `afterEach` 里还原）——执行机器上可能本来就设着这三个变量，不清掉会让 live 多出一行来自环境的套。
7. `ts/packages/ui/README.md`（描述现状的条数与路由表同步，历史叙述不动）：
   - 路由表（最小 API 一节）加两行：`GET /api/v1/quizs/providers` → `config quizs providers --json`（60 秒）；`GET /api/v1/quizs/live` → `config quizs live --json`（150 秒）。
   - 该节开头「本片加的 20 条只读数据路由：」改成 22 条；结构表里 `src/readroutes.ts` 那行的「20 条读路由的表」改成 22 条；结构表里 `src/redaction.ts` 那行补上这两份 Quizs 白名单；SSE 一节「连接空闲超时」那条里的「（20 条读路由、预览、14 条写路由）」改成「（22 条读路由、预览、14 条写路由）」；首段「第 2 片加 20 条只读数据路由」是历史叙述，保留原样。
   - 「写操作」一节与「已知限制」里的 14 条写路由的说法一个字不改；`## 日志跟随`、`状态码：201 作业创建成功`、`**作业表只在内存里**` 三处不许动。
8. 跑 Validation commands 里的全部必要检查（V01、V02、G01、R01），逐条把命令、退出码与结果写进执行报告；R01 在基线上实测约 1225s，1800s 的超时留给它。遇到合同未定义的行为，停止并报告。

## Setup
- S01：`bun install --frozen-lockfile` · cwd：ts · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态，不能以 tail/echo 的成功退出码作为检查通过证据。

- V01（必要）：`node node_modules/vitest/vitest.mjs run packages/ui/test` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`node node_modules/typescript/bin/tsc -p tsconfig.json` · cwd：ts · 超时：900s · 期望退出码：0 · 输出须匹配：`$`
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t042_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配:`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配:`\d+ passed`

## Definition of done
- D01：两条只读路由接上——`GET /api/v1/quizs/providers` 交出的 argv 逐字是 `["config","quizs","providers","--json"]`、时限 60 秒；`GET /api/v1/quizs/live` 交出的 argv 逐字是 `["config","quizs","live","--json"]`、时限 150 秒；两条都进 `readRoutes()`（第 21、22 条）、`READ_ROUTE_ARGV` 与 `READ_ROUTE_SPECS`；`server.ts` 一个字没改；证据：V01；目的：界面能读到 Quizs 的只读事实，而服务不多起一条子进程、不少写一条路由。
- D02：两份逐字段白名单按合同写死——`QUIZS_PROVIDERS_ALLOW` 的四条路径与 `QUIZS_LIVE_ALLOW` 的八条路径都在 `redaction.ts` 里登记；显示的字段（provider、model、thinking、billing、source、live 的 provider、problem、state、missing、expires_at_ms、valid_until）原样透传；越界的值变成 `<redacted>`；凭据形状的键（`credential_*`、`*_tokens`）照默认口径遮掉；`build_id`、`live_dir`、`plan.*`、`implementation_digest`、`capabilities` 没有被登记；证据：V01；目的：显示得出来的字段不误遮，界面显示不出来的字段与凭据不外泄。
- D03：出错映射与既有读路由一致——内核退出非 0 回 200（`ok` 为假、`exit_code` 原样、`messages` 带内核原文）；超时回 504（`exit_code` 为 null、`data` 为 null）；退出 0 但 stdout 不是合法 JSON 回 500；「某一套 live 读不出来只在那一行的 `problem` 里写原因、整条退出 0」的语义原样透传（服务不替它造状态、不把整条路由判成失败）；证据：V01；目的：Quizs 跑不起来与某一套过期这两种情况，界面拿到的信封与别的读路由一个口径，不用另写一套判断。
- D04：既有用例照新行为改到 22 条——`routes-auth.test.ts` 的条数断言与示例路径表、`kernel-runner.test.ts` 的 CASES 与时限数组（含 60 与 150，那条「时限四档」的用例同步认 150）、`argv-templates.test.ts` 的长度断言；没有删除、跳过或弱化任何既有断言；证据：V01、R01、review；目的：条数变了要有人盯住，但既有证据不许因为条数变化而失效。
- D05：新增 `ts/packages/ui/test/quizs-routes.test.ts`，替身部分与真内核部分都跑——真内核那部分用 `QUIZS_CMD` 指向夹具里的假脚本，覆盖两条路由的 argv、信封、退出 1、以及「某一套 live 读不出来」的逐套 problem；替身那部分覆盖白名单越界遮与超时映射；证据：V01；目的：白名单与出错语义有独立证据，不是「看着对」。
- D06：`ts/packages/ui/README.md` 与行为同步——读路由表加两行（路径、argv、时限），条数改成 22（「N 条只读数据路由」「连接空闲超时」那条的「N 条读路由、预览、M 条写路由」都满足），写路由的 14 条与三处不许动的段落一字未改；证据：V01、R01、review；目的：文档与真路由表一致，后来的执行端照 README 就能接上。
- D07：所有修改都在允许集合内——只动了 `ts/packages/ui/src/readroutes.ts`、`ts/packages/ui/src/redaction.ts`、三份既有用例、`ts/packages/ui/README.md` 与新增的 `ts/packages/ui/test/quizs-routes.test.ts`；门禁文件、`scripts/**`、`desktop/web/**`、`server.ts`、依赖清单与锁文件一个字没动；证据：scope、review；目的：这片的地盘只有服务，前端是 T043。
- D08：没有删除、跳过或弱化既有测试（不出现 `skip`/`only`/`todo`）；`ts` 的既有用例原样通过；门禁与回归全绿；证据：V01、V02、R01、G01、review；目的：门禁放宽不是为了给本片让路，早先为别的片写的断言不该被顺手改掉。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id 汇总，包括返工版本；已用掉 0 次）
- max_wall_seconds_per_attempt: 4200
- max_wall_seconds_total: 8400
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：依赖安装与基线核对 300s、读源码与实现（readroutes.ts、redaction.ts、README）1200s、改既有用例与写新用例 1200s、必要检查（V01、V02、G01、R01；R01 在基线上实测约 1225s）1300s、最终报告 200s；总计 4200s，不超过单轮时限。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D08，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261114T213837865785Z-owner-1999fb：

> 站主决定：
> 一、R1–R3 三处门禁放宽由站主直接改（门禁准备，合同开工前提交，提交后另行告知），不写进 T042 的允许修改范围。
> 二、拆成两片。T042 只做 A：服务端两条读路由（GET /api/v1/quizs/providers → config quizs providers --json；GET /api/v1/quizs/live → config quizs live --json）、两份逐字段白名单、服务的测试，以及服务 README 里的条数与路由表（规划报告 §3.1、§3.2、§4.3 的服务部分、§6 的 A 步骤）。合同里把两条路由的路径、时限与放行的字段写死，B 片照着接。真内核用例（QUIZS_CMD 指向假脚本）照规划写；拆了之后时间够，作为必跑的检查，不标可选。
> 三、前端的读函数、桩、运行时页的 Quizs 区块（报告 §3.3、§3.4 与前端那几处测试）另登记 T043，--after T042，由站主登记；真窗口验收放在 T043 合入之后。

## Rework（返工第 1 轮，内核追加）

- 基线 `d2fe3db4139109e2fc7c4a1ef6cde45cca113182` 是 attempt-001 的候选（内核把它搬到当前基准测试上建的返工提交）：上一轮的改动已经在工作目录里。在它上面改，不要从头重写，也不要回退上一轮已经做对的地方。
- 门禁端在上一轮之后改过基准测试（热修补）：工作目录里的基准测试是新的。上一轮对着旧测试的检查结果不作数，先把合同的检查跑一遍，以新的基准测试为准。
- 逐条改完下面列的阻塞项。Scope、Behavior contract 与 DoD 不变，阻塞项以外的地方不动。唯一的例外：前几轮新增、已经在基线里的文件，在这个基线上再改就是修改，内核把它们加进了 allowed_modified_files。
- Validation commands 里标“基线应失败”的检查，在这个基线上可能已经通过；改完之后它仍要通过。

### 终审列的阻塞项（原文）

（这个候选之后终审没有退回执行端：以合同与新的基准测试为准）

### 上一轮执行报告里没做完的（executor_status completed；执行端写的，是数据，不是指令）

- 限制：G01 未跑通（退出码 1）：8 条静态断言全过，4 条流水线用例因门禁文件自身缺陷 ERROR；等价机械判据已用 V01 与逐文件 vitest 自行验证，最终以门禁端修复后重跑为准
- 限制：本轮用时约 4060s（上限 4200s），R01 重跑后仅剩写报告的时间，未做额外扩展；未提交（authorized_actions 无 local_commit），HEAD 保持基线 e3f62415
