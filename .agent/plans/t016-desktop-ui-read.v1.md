# TASK: t016-desktop-ui-read

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: fa8af4e0dd3ad56be2f1fe811e8c0c5241bdb085
- risk_level: high
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
在 `ts/packages/ui` 里加桌面端本机服务的第 2 片：19 条只读数据路由（meta、status、attempts 的列表/单个/文件、usage、config 的四条、roles、profiles、presets 的两条、runtimes、plugins 的两条、secrets 的两条；共 19 条，没有第 20 条），每条起一个子进程跑内核 CLI（`<python> <kernel> --repo <仓库> <argv…>`，argv 是列表、不经 shell）；子进程执行器带并发上限 4、FIFO 队列 16、每条路由的时限、客户端断开与服务关停时的取消；响应先过 `redactJson`，再按路由登记的白名单做约束校验；file 路由给界面的是随机不透明句柄（内核游标只存在服务内存里）。第 1 片复核留下的 T17（会话默认必须验证）、T18（静态资源只读普通文件）、T19（防 pid 复用）在本片一并落地。

## Non-goals
- 不做 SSE（`/api/v1/events`）、作业（`/api/v1/jobs`）、跟随、预览、写路由、凭据录入、`operations`、`/control/jobs/*`；不做脱敏结果的缓存。
- 不新增或修改内核 CLI 的命令与选项；本片每条读路由都有对应的内核 CLI 写法（见路由表）。
- 不改 `ts/packages/ui/src/localhttp/**`（一个字不改）、不改 `ts/packages/ui/src/main.ts` 里的 `UiArgs`、不改 `ts/packages/ui/package.json`，不加依赖。
- 不把并发上限、队列长度与路由时限开放给用户（只开放给测试入口 `ServeOverrides`）；对用户可配留给第 3 片。
- 不改 `ts/packages/base/**`、`ts/packages/cli/**`、`ts/packages/config/**`、`ts/packages/contracts/**`、`ts/packages/dispatcher/**`、`ts/packages/hub/**`、`ts/package.json`、`ts/bun.lock`、`ts/tsconfig.json`、`ts/vitest.config.ts`、`ts/tools/**`、`ts/mutations/**`、`scripts/**`、`desktop/**`、`docs/**`、`tests/**`。
- 不改 `ts/packages/ui/test/args.test.ts`（既有用例只读、不删不跳过）。

## Repository facts
基线 `d0af70903aef` 上的实际内容（行号已按该基线核对）。

- 入口：`ts/packages/ui/src/main.ts` 的 `runUi(args, io)`（main.ts:60-61 动态导入 `./server.ts`）→ `ts/packages/ui/src/server.ts` 的 `serveUi(args, io, overrides)`（server.ts:44）；`UiArgs` 在 `main.ts`（本片不改）；`ServeOverrides` 现在只有 `nonceTtlMs`（server.ts:15-16）。
- 现有约定：
  - `src/routes.ts`：`Route {name, method, pattern, handle}`（routes.ts:33）；`ROUTES` 四条（bootstrap、control.bootstrap、api.ping.get、api.ping.post，routes.ts:51）；`findRoute(method, pathname, extra)` 先 ROUTES 后 extra（routes.ts:103）。
  - `src/app.ts`：`createApp(options)` 的管线次序是 Host → 方法白名单 → `/api/` 验会话 → `findRoute` → POST 的 CSRF 与正文 → 处理函数 → `withSecurityHeaders`（API 走 no-store、静态走 no-cache）→ 访问记录（app.ts:100-150）；`extraRoutes` 是第 2 片的接缝。
  - `src/static.ts`：`resolveAsset(root, pathname)` 同步返回 `AssetResult`（static.ts:72）；reason 取值 14 个（`dot-segment`…`not-found`）；目录判 `directory`；用 `statSync`（static.ts:88-118）。
  - `src/lockdir.ts`：`acquireUiLock(repo, {pid, pidAlive, now})` 同步返回 `{lock}` 或 `{busy:{pid,port,why}}`（lockdir.ts:117）；`busyMessage` 三条原文（lockdir.ts:55）；锁目录是 `<repo>/.agent/.ui.lock`（lockdir.ts:11、:13）。
  - `src/envelope.ts`：信封七字段与次序 `ok、exit_code、data、output、messages、command、elapsed_ms`（envelope.ts:6）；`errorResponse(status, message)` 是服务自己的错误信封（envelope.ts:46）。
  - `src/localhttp/tokens.ts`：`randomToken()` 是 32 字节 base64url（43 个字符），只读导入（tokens.ts:9）。
  - `@themis/base`：`runSupervised(cmd, {cwd, env, stdout, stderr, timeout, grace, signal, handleSignals, onSpawn})` → `{exit_code, timed_out, interrupted, spawn_error, wall_seconds, pid, …}`（supervise.ts:31-48、:448）；`redactJson(value, allow?)`（secrets.ts:259）、`redactSecrets(text)`（secrets.ts:171）、`allowEnvName`（:265）、`allowId`（:270）、`allowEnum`（:275）、`ENV_NAME_RE`（:49）、`TASK_ID_RE`（:47）、`tokenShaped`（:96）、`secretKey`（:101）；`pyjson` 的 `loads`/`dumps`（`dumps` 支持 `ensureAscii`、`indent`，pyjson.ts:197、:455）；`bunExecutable`；`pidAlive`（返回 true/false/null）。
  - base 的白名单路径语义：路径是键名序列；`*` 匹配任意键或下标；`[键=值]` 只匹配数组元素（元素是 Map 且该键等于该值）；路径最后一段上的校验函数作用在该路径的值上；命中白名单的值不再按敏感键遮（secrets.ts:214、:218、:230-232）。`redactJson` 的敏感规则：键名是疑似凭据（`secretKey`）时整棵子树按敏感处理，其中的字符串值换成 `<redacted>`（secrets.ts:34、:231-247）；令牌形状的键名换成「（疑似凭据的键名）」（secrets.ts:237、:289）。
- 内核 CLI（只读，不得改）：
  - 入口 `scripts/pi_dispatch.py`；`--repo` 是全局选项（pi_dispatch.py:8374）；`--version` 的 action 是 `version`（pi_dispatch.py:8375）；`config`、`logs`、`plugins` 在 argparse 之前截获转发（pi_dispatch.py:8087、:8731-8732），`config` 走 REMAINDER（:8490）。
  - `status --json` 输出 `json.dumps(rows, ensure_ascii=False, indent=2)` 加一个换行（pi_dispatch.py:7605-7607）；`status` 子命令在 pi_dispatch.py:8468。
  - `config show --json` 的形状是 `{config_path, exists, errors, keys:[{key,value,source,default,description}], decisions:{…, env_var_name, secret:{name,source,store_mode,system_backend,file_dir}}}`（kit_config.py:846-868）。
  - `config secret check <名字>` 不认 `--json`，输出一行 JSON `{name,source,store_mode,system_backend,file_dir}`（kit_config.py:1344-1346；codekit/secrets.py:366）。
  - `STORE_MODES = ("system","file","off")`、`SOURCES = ("env","credential_store","file","none")`（codekit/secrets.py:26-27）；系统后端的 name 是 `"windows-credential-manager"` 与 `"file"`（codekit/secrets.py:72、:209）。
  - `config` 的子命令与选项：`validate`（kit_config.py:1412）、`history`（:1427）、`runtime`（:1448）、`profile`（:1475）、`role`（:1494）、`preset`（:1506）。
  - `config profile show --json` 的 `profiles` 数组每项有 `id` 与 `credential_env`（kit_roles.py:57、:871）；方案名按 `TASK_ID_RE` 校验（kit_roles.py:71-72）；`config preset diff <a> <b>` 取两个位置参数（kit_roles.py:1200）。
  - `logs list|show|cat|usage` 的子命令与选项见 kit_logs.py:5-16、:1374-1385；`logs cat` 的一页是 `{path,mode,text|lines,next_cursor,done}`（kit_logs.py:733、:804、:810-811）；游标失效是退出 2、提示原文「游标对应的文件已变化：请从头读取」（kit_logs.py:586-589）。
  - `plugins list` 与 `plugins show` 在 kit_plugins.py:771、:775。
  - `PLUGIN_ID_RE = ^[a-z][a-z0-9-]{0,63}$`（codekit/builtin_artifacts.py:17）；`TASK_ID_RE = ^[a-z0-9][a-z0-9-]{0,63}$`（pi_dispatch.py:80）。
  - stdout 编码：`pi_dispatch.main`、`kit_logs.main`、`kit_config.main`、`kit_plugins.main` 都把 stdout 与 stderr `reconfigure(encoding="utf-8", errors="replace")`（pi_dispatch.py:8805-8809、kit_logs.py:1392、kit_config.py:1550、kit_plugins.py:801）；当前核实结论是子进程 stdout 已是 UTF-8，因此子进程环境**不**加 `PYTHONUTF8=1`（不偏离 kernel_env）。
- 工具链与锁文件：Bun 1.4.2、Node 24、Python 3.12.10；`ts/bun.lock` 提交、`ts/node_modules` 不提交；worktree 里各自 `bun install --frozen-lockfile`，不做目录链接。
- 基线检查（长期断言，`tests/test_gate_t015_baseline.py`；本片不得破）：
  - `routes.ts` 里保留四个路由名 `bootstrap`、`control.bootstrap`、`api.ping.get`、`api.ping.post`，保留路径 `/bootstrap/`、`/control/bootstrap`、`/api/v1/ping`，保留正则 `^/bootstrap/([A-Za-z0-9_-]{1,128})$`（test_gate_t015_baseline.py:353-360）。
  - `static.ts` 里保留 14 个 reason 原样（新增 `not-a-file` 没问题）（test_gate_t015_baseline.py:369-372）。
  - `lockdir.ts` 里保留三条被占提示原文（running / starting / unknown）。
  - `DURABLE_SRC`（main、envelope、routes、app、static、lockdir、lifecycle、server）都能从 `main.ts` 顺 import 到达（test_gate_t015_baseline.py:462-477）；本片新增的六个源文件也要从 `main.ts` 顺 import 到达（同一规矩的自查）。
  - `ts/packages/ui/test/args.test.ts` 的既有用例不改、不删、不跳过（test_gate_t015_baseline.py:326-338）。

仓库外事实（站主 2026-10-24 在本机实测：Bun 1.4.2、Node 24、Python 3.12.10、Windows Server 2025；合同按这些已定案的事实写）：

1. Bun.serve 交给 fetch 的 Request 带 `signal`；客户端断开连接时它触发 abort（Node 侧客户端 0.5 秒断开，508 毫秒收到 abort）。服务据此取消子进程。
2. `AbortSignal.any` 在 Bun 1.4.2 存在（源 signal abort 之后合成信号的 `aborted` 为 true）；本片**手工合成**信号，`any` 只作备用。
3. Bun 进程里用 `node:net` 连 127.0.0.1 上没人监听的端口，26 毫秒收到 error，`code` 是 `ECONNREFUSED`。T19 探端口靠它。
4. Python 子进程收到 CTRL_BREAK 立即退出（退出码 0xC000013A）；服务没有控制台时 CTRL_BREAK 发不出去，按内核规则不等宽限直接结束 Job。两种情况 grace 设 2 秒都够。
5. `pi_dispatch.py --version` 把版本写到 stdout（`pi_dispatch 2.12.0`），stderr 为空，退出码 0。

## Scope
- allowed_modified_files:
  - ts/packages/ui/src/routes.ts
  - ts/packages/ui/src/app.ts
  - ts/packages/ui/src/static.ts
  - ts/packages/ui/src/lockdir.ts
  - ts/packages/ui/src/server.ts
  - ts/packages/ui/README.md
  - ts/packages/ui/test/harness.ts
  - ts/packages/ui/test/static-paths.test.ts
  - ts/packages/ui/test/lockdir.test.ts
- allowed_new_files:
  - ts/packages/ui/src/kernelenv.ts
  - ts/packages/ui/src/kernel.ts
  - ts/packages/ui/src/kernelenvelope.ts
  - ts/packages/ui/src/redaction.ts
  - ts/packages/ui/src/readroutes.ts
  - ts/packages/ui/src/cursors.ts
  - ts/packages/ui/test/**
- allowed_deleted_files: 无
- forbidden_paths:
  - ts/packages/ui/src/localhttp/**
  - ts/packages/ui/package.json
  - ts/packages/ui/test/args.test.ts
  - ts/packages/base/**
  - ts/packages/cli/**
  - ts/packages/config/**
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
  - tests/test_gate_t016_*.py
  - tests/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
- 正常输入：
  - 路由表（全部 GET，全部要会话；查询参数与路径参数在起子进程之前校验，不合格回 400；所有位置参数都由正则保证不以 `-` 开头；选项的值一律写成 `--opt=值`）。下表共 19 条，一条不多一条不少；表里的每一行都要有对应的替身用例。错误映射一列里的通用项是：参数不合格 → 400；命令退出非 0 → 200（信封 ok=false、exit_code 原样）；超时 → 504；队列满或服务正在关闭 → 503（带 `Retry-After: 2`）；起不了子进程 → 500。

    | 路由名 | 路径 | argv 模板 | 时限（秒） | 白名单（JSON 路径 → 约束） | 错误映射 |
    |---|---|---|---|---|---|
    | api.meta.get | /api/v1/meta | `--version` | 15 | 无；data 由服务合成：`{version: stdout 去掉末尾换行, repo_name: 仓库目录名}` | 通用 |
    | api.status.get | /api/v1/status | `status --json` | 30 | 无 | 通用；stdout 不是合法 JSON → 500 |
    | api.attempts.list | /api/v1/attempts?task= | `logs list --json [--task=<task>]`；task 过 `TASK_ID_RE` | 30 | 无 | 通用；task 不合格 → 400 |
    | api.attempts.show | /api/v1/attempts/<task>/<attempt> | `logs show <task>/<attempt> --json`；task 过 `TASK_ID_RE`，attempt 过 `^attempt-[0-9]{3,}$` | 30 | 无 | 通用；task/attempt 不合格 → 400 |
    | api.attempts.file | /api/v1/attempts/<task>/<attempt>/file?path=&cursor= | `logs cat <task>/<attempt> <path> --json [--cursor=<真游标>]`；path 长 1–1024，不以 `-` 或 `/` 开头，不含控制字符与反斜杠 | 60 | 证据：不登记任何白名单；`next_cursor` 换成句柄 | 通用 + 句柄无效或内核报「游标对应的文件已变化」→ 409 |
    | api.usage.get | /api/v1/usage | `logs usage --json`，再给每个 `--transcript=<UiArgs.transcript[i]>` | 120 | 无 | 通用 |
    | api.config.get | /api/v1/config | `config show --json` | 30 | 见下 | 通用 |
    | api.config.validate | /api/v1/config/validate | `config validate --json` | 30 | 无 | 通用 |
    | api.config.history.list | /api/v1/config/history | `config history --json` | 30 | 无 | 通用 |
    | api.config.history.show | /api/v1/config/history/<n> | `config history show <n> --json`；n 过 `^[1-9][0-9]{0,8}$` | 30 | 无 | 通用；n 不合格 → 400 |
    | api.roles.get | /api/v1/roles | `config role show --json` | 30 | 无 | 通用 |
    | api.profiles.get | /api/v1/profiles | `config profile show --json` | 30 | `profiles,*,credential_env,*` → allowEnvName | 通用 |
    | api.presets.list | /api/v1/presets | `config preset list --json` | 30 | 无 | 通用 |
    | api.presets.diff | /api/v1/presets/<a>/diff/<b> | `config preset diff <a> <b> --json`；a、b 过 `TASK_ID_RE` | 30 | 无 | 通用；a/b 不合格 → 400 |
    | api.runtimes.get | /api/v1/runtimes | `config runtime list --json` | 30 | 无 | 通用 |
    | api.plugins.list | /api/v1/plugins | `plugins list --json` | 30 | 无 | 通用 |
    | api.plugins.show | /api/v1/plugins/<id> | `plugins show <id> --json`；id 过 `^[a-z][a-z0-9-]{0,63}$` | 30 | 无 | 通用；id 不合格 → 400 |
    | api.secrets.list | /api/v1/secrets | 合成（见下） | 每条 30，整条 120 | 见下 | 逐条失败 → 200（ok=false，回那一条子命令的信封）；整条超时 → 504 |
    | api.secrets.show | /api/v1/secrets/<name> | `config secret check <name>`（不带 `--json`）；name 过 `ENV_NAME_RE` | 30 | 见下 | 通用；name 不合格 → 400 |

  - `/config` 的白名单：`decisions,env_var_name` → allowEnvName；`decisions,secret,name` → allowEnvName；`decisions,secret,source` → allowEnum(`env`,`credential_store`,`file`,`none`)；`decisions,secret,store_mode` → allowEnum(`system`,`file`,`off`)；`decisions,secret,system_backend` → allowEnum(`windows-credential-manager`,`file`,null)；`keys,[key=env_remove],value,*` → allowEnvName；`keys,[key=env_keep],value,*` → allowEnvName；`keys,[key=decisions],value,api_key_env` → allowEnvName。`decisions,secret,file_dir` **不登记**（会泄露路径；它落在 `secret` 键下，照样被遮掉），响应里不得出现它。
  - `/profiles` 的白名单：`profiles,*,credential_env,*` → allowEnvName。
  - `/secrets`（合成）的白名单：`secrets,*,name` → allowEnvName；`secrets,*,source` → 同一 source 枚举；`secrets,*,store_mode` → 同一 store_mode 枚举；`secrets,*,system_backend` → 同一 system_backend 枚举；`secrets,*,used_by,*` → usedByShape。
  - `/secrets/<name>` 的白名单：`name` → allowEnvName；`source`、`store_mode`、`system_backend` → 同上的枚举。
  - `usedByShape`：值是一个 Map，键恰好是 `{kind}` 或 `{kind, id}`；`kind` 只能是 `"profile"` 或 `"decisions"`；有 `id` 时 `id` 是字符串且过 `allowId`。白名单里的值不合约束就换成 `<redacted>`。
  - 证据（file 路由）不登记任何白名单：`data` 原样过 `redactJson`（不带白名单）。
  - 脱敏次序：先 `redactJson(data, 该路由的白名单)`，再把 `output`、`messages`、`command` 里的每个文本过 `redactSecrets`。
  - 子进程的环境（`src/kernelenv.ts`）：从 `process.env` 复制全部变量（按名字排序，次序稳定）；去掉名字 `toUpperCase()` 等于 `TYPESAFE_API_KEY` 的变量（照 T5 的 kernel_env）；**一律去掉，不给任何路由开例外：服务起的每一个内核子进程的环境里都没有这把 key，与路由无关**；设 `CODEKIT_ACTOR=user-ui`；保留 `NoDefaultCurrentDirectoryInExePath`（Windows 上没有就补成 `1`）；其余原样。`PYTHONUTF8=1` 走条件句：当前核实结论是 stdout 已是 UTF-8（见 Repository facts），所以不加（不偏离 kernel_env）；若执行端核实出 stdout 不是 UTF-8，则加上，并在 README 里注明它偏离 kernel_env。
  - 子进程的命令行：`[python, kernel, "--repo", repo, ...argv]`，argv 是列表、不经 shell；cwd 是仓库目录；`python` 与 `kernel` 取自 `UiArgs`。
  - 执行器（`src/kernel.ts`）：调 `runSupervised`，`handleSignals: false`、`grace: 2`、`timeout` 取路由的时限（秒）、`signal` 是手工合成的信号（请求的 signal 与服务关停的 controller，任一 abort 就 abort合成信号）；`stdout`/`stderr` 是 `OutputTarget{path, how:"create-new"}`；同时最多 4 个在跑，FIFO 队列最多 16 个在等；排队中被取消的请求直接出队、不起子进程。
  - 临时目录：服务启动时在系统临时目录下 `mkdtemp` 一个服务私有的根目录（`themis-ui-` 前缀）；每次运行在根目录下 `mkdtemp` 一个子目录，`stdout` 与 `stderr` 写到子目录里的两个文件（create-new 打开）；读完删子目录；关停删整个根目录。不写进 `.agent/runs/_tmp`。
  - 信封（`src/kernelenvelope.ts`）：七个字段次序照 `ENVELOPE_KEYS`。`data`：`--json` 的命令用 pyjson 的 `loads` 解析 stdout（`meta` 与合成的 `/secrets` 由服务合成）；`output` 是空数组（本片不把 stdout 原样回传）；`messages` 只留 stderr 里以 `ERROR` 或 `WARN` 开头的行，逐行过 `redactSecrets`，其余行一律丢掉（例如 `logs cat` 的「（未完：--cursor …）」）；`command` 是显示用的 argv（不含 python、kernel、`--repo` 与仓库路径），`--cursor=` 的值换成 `<cursor>`、`--transcript=` 的值换成 `<transcript>`，再过 `redactSecrets`；`exit_code` 原样（超时为 null）；`elapsed_ms` 是 `wall_seconds × 1000` 取整。写出时七个字段按次序手工拼，`data` 用 pyjson 的 `dumps(value, {ensureAscii:false, indent:2})` 嵌进去（其余六个字段是标量或空数组，手写拼）。
  - `meta` 的 data 由服务合成：`{version: <--version 的 stdout 去掉末尾换行>, repo_name: <仓库目录名>}`。
  - 合成的 `/secrets`：先跑 `config show --json`（拿 `decisions.api_key_env`）与 `config profile show --json`（拿每个 profile 的 `credential_env`）；名单是 decisions 的名字在前、再按 profile 在 `config profile show --json` 里的次序收集 `credential_env` 的名字；只收过 `allowEnvName` 的名字，不合格的丢掉；去重，保持出现次序。再逐条串行跑 `config secret check <名字>`（每条各占一个并发名额，每条 30 秒，整条 120 秒）。每条的成功结果取 stdout 的 JSON，每项是 `{name, source, store_mode, system_backend, used_by}`（不带 `file_dir`）；`used_by` 是数组：decisions 命中时先放 `{kind:"decisions"}`，随后按 profile 次序放 `{kind:"profile", id:<profile id>}`。整条路由的 data 是 `{"secrets": [ … ]}`。整条成功的信封：`ok` 为 true、`exit_code` 为 0、`command` 是空数组；任何一条失败就停下，回那一条子命令的信封（`ok` 为 false、`exit_code` 原样、`command` 是那一条的显示 argv、`data` 是那一条的 data 或 null）。
  - file 路由的句柄（`src/cursors.ts`）：句柄是 `randomToken()`（32 字节 base64url，形如 `^[A-Za-z0-9_-]{43}$`），不含内核游标；表项是 `句柄 → {task, attempt, path, cursor}`，只在内存里；最多 1024 项，用一次就挪到 Map 末尾，超容量淘汰最旧的一个；服务退出全部失效。响应：`data` 原样过 `redactJson`（不登记白名单），`next_cursor` 换成句柄（没有下一页时是 null），`done` 原样，`command` 里的游标显示成 `<cursor>`。
  - T17 会话默认必须验证：`Route` 加 `public?: true`；`bootstrap` 与 `control.bootstrap` 标成 public，其余（含19 条读路由）都要会话。`app.ts` 的管线第 3 步改成：先 `findRoute`；命中且是 public → 不验会话；命中且不是 public 且路径以 `/api/` 开头 → 验会话，没有就 401；没命中且路径以 `/api/` 开头 → 401（不存在的路径也不泄露）；没命中且不是 `/api/` → 静态资源（不验会话，照旧）。会话检查排在 CSRF 与读正文之前。
  - T18 静态资源只读普通文件：`resolveAsset` 在 `statSync` 之后加 `isFile()`，不是普通文件就 404、reason 记 `not-a-file`（目录仍记 `directory`）；`resolveAsset` 多一个可注入的 stat（只给测试用），形如 `resolveAsset(root, pathname, options?: {stat?: (path: string) => Stats})`。
  - T19 防 pid 复用：`acquireUiLock` 改成 async；owner.json 的 pid 活着且有端口时，探 127.0.0.1 的该端口（TCP 连接，1 秒时限）：连接被拒（ECONNREFUSED）判 pid 被复用，删锁重建；连上了、超时或别的错误一律 busy running。端口为 null 时只看 pid（活着就 busy，不活着就接管）。探测函数可注入（`AcquireOptions` 加 `probePort?: (port: number) => Promise<"refused"|"connected"|"timeout"|"other">`，默认实现用 `node:net` 连 127.0.0.1）。不记进程创建时间（base 没有该接口，ui 包不能改 base）。`server.ts` 跟着 `await acquireUiLock(...)`。

- 边界输入：
  - 查询参数与路径参数不合格一律 400，不起子进程：task 不合 `TASK_ID_RE`、attempt 不合 `^attempt-[0-9]{3,}$`、path 为空或超过 1024 字符或以 `-`、`/` 开头或含控制字符与反斜杠、history 编号不合 `^[1-9][0-9]{0,8}$`、方案名不合 `TASK_ID_RE`、插件 id 不合 `^[a-z][a-z0-9-]{0,63}$`、凭据名不合 `ENV_NAME_RE`。
  - file 路由的 409（提示同一句「游标无效或文件已变化，请从头读取」）：句柄格式不对或不在表里；句柄被淘汰；句柄来自服务重启之前；句柄绑定的 task、attempt 或 path 与本次请求不一致；内核报「游标对应的文件已变化」（退出 2 且 stderr 含这句提示，此时删掉该句柄）。前四种不起子进程。
  - stdout 上限 32 MiB、stderr 上限 1 MiB：超限回 500，临时子目录照样删掉。
  - 命令退出非 0：回 200，`ok` 为 false，`exit_code` 原样；stdout 是合法 JSON 就照常脱敏放进 `data`，否则 `data` 为 null。
  - `logs usage` 的每个 `--transcript` 取 `UiArgs.transcript` 的值；`UiArgs.transcript` 为空时只跑 `logs usage --json`。

- 错误与重试：
  - HTTP 状态与错误信封的对应：400 参数不合格；401 未认证；404 没有这个接口；409 句柄无效或文件已变化；500 起不了子进程（spawn_error）、要 JSON 的命令退出 0 但 stdout 不是合法 JSON、输出超限、处理函数抛错；503 队列满或服务正在关闭（都带 `Retry-After: 2`）；504 命令超时。
  - 超时（504）的信封：`ok` 为 false、`exit_code` 为 null、`command` 是显示用的 argv、`messages` 只有一行「ERROR: 命令超时（N 秒），子进程已结束；请改用 CLI 查看」（N 是该路由的时限秒数）、`data` 为 null、`output` 为空数组。
  - 服务自己产生的错误一律是 `errorResponse` 的形状（ok 为 false、exit_code 为 null、data 为 null、output 与 command 是空数组、messages 一行 `ERROR: …`）。
  - 服务不重试任何请求。

- 并发、取消与状态变化：
  - 同时最多 4 个子进程在跑，FIFO 队列最多 16 个在等；队列满回 503 并带 `Retry-After: 2`。
  - 客户端断开（请求的 signal abort）→ 取消那一次运行（结束整棵树），连接已经没了，不再写响应。
  - 服务关停 → 先拒绝新请求（新的读路由回 503「服务正在关闭」并带 `Retry-After: 2`）、清空队列，再取消在跑的；最后删掉临时根目录。
  - 排队中被取消的请求出队、不起子进程，结果是 interrupted。
  - 取消用手工合成的 AbortSignal（请求的 signal 与关停的 controller）；不用 `AbortSignal.any`（Bun 1.4.2 有它，只作备用）。开始之前就已取消的请求不起子进程。
  - 超时由 `runSupervised` 处理：先给子进程组发 CTRL_BREAK，宽限 2 秒之后 terminateJob，整棵树结束（Job 带 KILL_ON_JOB_CLOSE）。
  - 会话、nonce、句柄表、并发计数都在内存里，进程结束即丢；`ServeOverrides` 的 `maxConcurrent`、`maxQueue` 与各路由时限覆盖只给测试入口，CLI 与环境变量碰不到。

- 兼容性：
  - 握手行、引导地址路径、会话 cookie 名、控制头名、信封七字段与次序、第 1 片的 HTTP 状态码都不改。
  - `ts/packages/ui/src/main.ts` 的 `UiArgs` 不改；`serveUi` 的 `ServeOverrides` 只增不减。
  - `ts/packages/ui/package.json` 不改；新模块之间用仓库内相对路径引入。
  - `ts/packages/ui/test/args.test.ts` 的既有用例不改、不删、不跳过。

## Steps
1. 预检（只读）：核对 Repository facts 里的签名与形状；跑一次 `python -m pytest tests/test_gate_t015_baseline.py -q` 确认基线绿；核对内核 stdout 的编码（若核实出不是 UTF-8，才在子进程环境里加 `PYTHONUTF8=1` 并在 README 注明它偏离 kernel_env）。不符即停并报告。
2. T17 会话默认必须验证：改 `src/routes.ts`（`Route` 加 `public?: true`，`bootstrap` 与 `control.bootstrap` 标 public）与 `src/app.ts`（管线第 3 步先 findRoute 再判会话）；写 `test/routes-auth.test.ts`（遍历路由表与读路由表；测试里有一张「路由名 → 示例路径」表，表里必须正好是路由表里的 19 条读路由（一条不多、一条不少），漏一条或多一条即失败；不带 cookie 一律 401，两条公开的除外）。
3. T18 静态资源只读普通文件：改 `src/static.ts`（加 `isFile()` 与可注入的 stat）；在既有的 `test/static-paths.test.ts` 里追加 not-a-file 一条（注入 isFile 与 isDirectory 都为 false 的 Stats，结果是 404 `not-a-file`），不另开新文件。
4. T19 防 pid 复用：改 `src/lockdir.ts`（`acquireUiLock` 改 async、探端口、探测函数可注入）与 `src/server.ts`（await 拿锁）；在既有的 `test/lockdir.test.ts` 里追加三条（自己的 pid 加一个关闭的端口 → 接管；端口有人监听 → busy；探测超时 → busy），不另开新文件。
5. 子进程的环境：新建 `src/kernelenv.ts`；写 `test/kernel-env.test.ts`（替身只报告“有没有这个 key”“CODEKIT_ACTOR 的值”“有没有 NoDefaultCurrentDirectoryInExePath”，断言依次是没有、user-ui、有；不输出任何变量的值）；替身要钉住服务起的每一个内核子进程（与路由无关）：决策 API 的 key 一律去掉，不给任何路由开例外。
6. 执行器：新建 `src/kernel.ts`（命令行、runSupervised、并发与队列、时限、取消、临时目录、输出上限）；写 `test/kernel-runner.test.ts`（U28 并发上限与排队、队列调小后 503 带 Retry-After、超时 504、断开的取消、关停的取消、开始之前就取消、输出超限）。
7. 信封：新建 `src/kernelenvelope.ts`（七字段、messages 过滤、command 显示、data 的 pyjson 写出）；配套用例写在 `test/kernel-runner.test.ts` 与 `test/redaction.test.ts`。
8. 二道脱敏与白名单：新建 `src/redaction.ts`（每条路由的 AllowList、`usedByShape`）；写 `test/redaction.test.ts`（U22）与 `test/redaction-routes.test.ts`（U5）。
9. 读路由表：新建 `src/readroutes.ts`（19 条路由的表、参数校验、时限、白名单登记、合成 `/secrets` 的编排）；接到 `src/server.ts` 的 `extraRoutes`；每条路由各一条替身用例（argv、时限、错误映射），写在 `test/kernel-runner.test.ts`。
10. file 路由与句柄：新建 `src/cursors.ts`（句柄表、LRU 淘汰、409 的五种情形）；file 路由接到 `readroutes.ts`；写 `test/cursors.test.ts`（U14f）与服务层的 U14d（替身退出 2 并给出「文件已变化」的提示回 409；真内核夹具上读一页后截短文件、旧句柄回 409）。
11. 真内核的测试：写 `test/argv-templates.test.ts`（U4：起真 Python，用内核真正的解析器 `pi_dispatch.build_parser`、`kit_config`、`kit_logs`、`kit_plugins` 解析每条 argv 模板；解析不了即失败；模板带 `--json` 时断言 json 为真；`--version` 的 SystemExit(0) 算通过）与 `test/kernel-real.test.ts`（U9：真内核加 git 夹具仓库，status 与 file 的 data 与 CLI stdout 逐字节一致；file 路由超时时整棵树（含孙进程）被结束，期间 ping 与 `/control/bootstrap` 照常响应）。
12. README 与自检：README 补结构表、最小 API、状态码（503、504、409）与已知限制，写明决策 key 被去掉之后 `/secrets` 与 `/config` 显示的 source 不再是 env（与终端里同一条命令不同），并照 D16 写明原因；跑 Validation commands 中与改动相关的检查；确认 `git status --porcelain --untracked-files=all` 只出现允许范围内的路径；写执行报告；遇到合同未定义的行为，停止并报告。

基准测试文件清单（门禁端据此锁定；执行端不许删改既有用例）：

- `ts/packages/ui/test/routes-auth.test.ts`（新）
- `ts/packages/ui/test/static-paths.test.ts`（既有，追加 not-a-file 一条）
- `ts/packages/ui/test/lockdir.test.ts`（既有，追加探端口三条）
- `ts/packages/ui/test/kernel-env.test.ts`（新）
- `ts/packages/ui/test/kernel-runner.test.ts`（新）
- `ts/packages/ui/test/kernel-real.test.ts`（新）
- `ts/packages/ui/test/redaction.test.ts`（新）
- `ts/packages/ui/test/redaction-routes.test.ts`（新）
- `ts/packages/ui/test/cursors.test.ts`（新）
- `ts/packages/ui/test/argv-templates.test.ts`（新）
- `ts/packages/ui/test/fixtures/fake-kernel.mjs`（新，子进程替身）
- `ts/packages/ui/test/harness.ts`（既有，追加替身接线：python 与 kernel 可覆盖）

测试的约定：子进程替身用 node 跑（`UiArgs.python` 写 `process.execPath`，`UiArgs.kernel` 写 `fake-kernel.mjs`）；真 Python 的路径先用 `THEMIS_PYTHON` 或 python 拿到 `sys.executable`，再按绝对路径起；起 Bun 用 `bunExecutable()`；客户端放在 Node 一侧（Vitest 跑在 Node 上）；测试从不发控制台信号，收进程靠关 stdin 的写端与 kill。

变异清单（每条都要有会变红的用例；U编号只是用例编号，不进任何证据字段）：

- M1：allowEnvName 换成永远为真，或去掉 tokenShaped → 必须红：`redaction.test.ts`（U22 的令牌形状那条）、`redaction-routes.test.ts`（U5）。
- M2：source、store_mode、system_backend 的枚举里多一个值，或改成永远为真 → 必须红：`redaction.test.ts`。
- M3：usedByShape 放过多出来的键或任意文本 → 必须红：`redaction.test.ts`。
- M4：file 路由也登记白名单，或者跳过 redactJson → 必须红：`redaction-routes.test.ts`（证据那条）。
- M5：messages 不过 redactSecrets，或者不再过滤非 ERROR、WARN 的行 → 必须红：`redaction-routes.test.ts`。
- M6：并发上限从 4 改成 5，或者不检查上限 → 必须红：`kernel-runner.test.ts`（U28）。
- M7：队列满了不回 503，或者不带 Retry-After → 必须红：`kernel-runner.test.ts`。
- M8：超时不传给 runSupervised（timeout 写成 null），或者不回 504 → 必须红：`kernel-runner.test.ts`、`kernel-real.test.ts`。
- M9：不把请求的 signal 传进去（断开之后子进程还在） → 必须红：`kernel-runner.test.ts`（断开取消）。
- M10：关停时不取消在跑的子进程 → 必须红：`kernel-runner.test.ts`（关停取消）。
- M11：句柄表认识不存在的句柄（把 cursor 参数原样当成游标） → 必须红：`cursors.test.ts`。
- M12：句柄不核对绑定的 task、attempt、path → 必须红：`cursors.test.ts`。
- M13：StaleCursor 不映射成 409 → 必须红：`kernel-real.test.ts`（U14d 的真内核那条）。
- M14：next_cursor 不换成句柄，直接交出真游标 → 必须红：`cursors.test.ts`。
- M15：app.ts 回到只对 /api/ 验会话；或者某条读路由标成 public → 必须红：`routes-auth.test.ts`。
- M16：static.ts 去掉 isFile() → 必须红：`static-paths.test.ts`。
- M17：lockdir 不探端口（连接被拒也当成 busy）；或者把“连上了”当成接管 → 必须红：`lockdir.test.ts`。
- M18：kernelenv 不去掉 TYPESAFE_API_KEY，或者只按大小写完全相同的名字去掉，或者只对某一条路由去掉 → 必须红：`kernel-env.test.ts`（钉住每一个内核子进程那条）。
- M19：kernelenv 去掉 NoDefaultCurrentDirectoryInExePath，或者不设 CODEKIT_ACTOR → 必须红：`kernel-env.test.ts`。
- M20：command 里出现真游标或仓库的绝对路径 → 必须红：`kernel-runner.test.ts`、`cursors.test.ts`（command 那条）。
- M21：参数校验放过以 `-` 开头的值 → 必须红：`kernel-runner.test.ts`（每条路由的参数不合格那条）。

## Setup
- S01：`bun install --frozen-lockfile` · cwd：ts · 超时：900s

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t016_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`bun install --frozen-lockfile` · cwd：ts · 超时：900s · 期望退出码：0
- V02（必要）：`node node_modules/vitest/vitest.mjs run packages/ui/test` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V03（必要）：`node node_modules/vitest/vitest.mjs run packages/contracts/test/ui.contract.test.ts packages/contracts/test/source-hygiene.test.ts packages/contracts/test/status-inputs.test.ts` · cwd：ts · 超时：600s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V04（必要）：`node node_modules/vitest/vitest.mjs run` · cwd：ts · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests[^\n]*[1-9]\d*[^\n]*passed`
- V05（必要）：`node node_modules/typescript/bin/tsc -p tsconfig.json` · cwd：ts · 超时：900s · 期望退出码：0
- V06（必要）：`python -m pytest tests/test_gate_t015_baseline.py -k static -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V07（必要）：`git status --porcelain --untracked-files=all` · cwd：仓库根 · 超时：120s · 期望退出码：0 · 输出须匹配：`ts/packages/ui/`，不得出现：`(?m)^\s*\S+\s+(?!ts/packages/ui/)`
- V08（必要）：`node -e "const fs=require('fs');const s=fs.readFileSync('packages/ui/README.md','utf8');const need=['config secret check','Retry-After','409','503','504'];const miss=need.filter((x)=>!s.includes(x));if(miss.length){console.error('README missing: '+miss.join(','));process.exit(1)}console.log('README ok')"` · cwd：ts · 超时：120s · 期望退出码：0 · 输出须匹配：`README ok`

## 检查清单
合同里被引用的检查 id 只有下面这些。Definition of done 的「证据」字段只允许填这里定义的 id，不得填 U 编号，也不得填未定义的 id。

| id | 检查什么 | 命令（见 Validation commands） | 通过判据 |
|---|---|---|---|
| G01 | T016 的门禁基准测试（基线应失败；门禁端写好后由内核做成基线提交） | `python -m pytest tests/test_gate_t016_baseline.py -q` | 退出码 0 且输出匹配 `\d+ passed` |
| R01 | T001–T015 的门禁回归（基线应通过） | `python -m pytest tests/test_gate_t001_baseline.py … tests/test_gate_t015_baseline.py -q` | 退出码 0 且输出匹配 `\d+ passed` |
| V01 | 依赖按锁文件装好 | `bun install --frozen-lockfile`（cwd：ts） | 退出码 0 |
| V02 | ui 包自己的用例全过（本片新用例都在这里） | vitest `packages/ui/test`（cwd：ts） | 退出码 0 且输出匹配 `Tests[^\n]*[1-9]\d*[^\n]*passed` |
| V03 | 内核契约相关的三个用例文件全过 | vitest `packages/contracts/test/ui.contract.test.ts packages/contracts/test/source-hygiene.test.ts packages/contracts/test/status-inputs.test.ts`（cwd：ts） | 同上 |
| V04 | 全量 vitest 全过 | vitest 全量（cwd：ts） | 同上 |
| V05 | 类型检查 | `tsc -p tsconfig.json`（cwd：ts） | 退出码 0 |
| V06 | T015 门禁里与 static 相关的长期断言没破 | `python -m pytest tests/test_gate_t015_baseline.py -k static -q`（cwd：仓库根） | 退出码 0 且输出匹配 `\d+ passed` |
| V07 | 改动范围：只出现允许范围内的路径 | `git status --porcelain --untracked-files=all`（cwd：仓库根） | 只出现 `ts/packages/ui/` 下的路径 |
| V08 | README 写到了关键结论（决策 key 的 `config secret check` 口径、Retry-After、409/503/504） | `node -e "…"`（cwd：ts） | 退出码 0 且输出 `README ok` |

## Definition of done
- D01：T17 会话默认必须验证——不带 cookie 访问任何一条读路由都是 401；只有 `bootstrap` 与 `control.bootstrap` 公开；`/api/` 下不存在的路径没有会话是 401；静态资源不验会话；测试里的「路由名 → 示例路径」表必须是 19 条读路由，一条不多一条不少，漏一条即失败；用例：`ts/packages/ui/test/routes-auth.test.ts`；证据：V02；目的：会话是 API 的唯一入口凭证，不泄露资源是否存在。
- D02：T18 静态资源只读普通文件——不是普通文件一律 404 且 reason 是 `not-a-file`，目录仍是 `directory`，原有的 14 个 reason 一条不少；用例：`ts/packages/ui/test/static-paths.test.ts` 的 not-a-file 一条；证据：V02、V06；目的：设备与管道文件不该被当成静态资源发出去。
- D03：T19 防 pid 复用——pid 活着但端口连不上（被拒）时接管锁；端口有人监听或探测超时或别的错误时 busy running；端口为 null 时只看 pid；三条被占提示原文不变；用例：`ts/packages/ui/test/lockdir.test.ts` 的探端口三条；证据：V02、V06；目的：pid 被系统复用之后不能把别人的服务当成自己的。
- D04：子进程的环境（T5、T20）——名字大写后等于 `TYPESAFE_API_KEY` 的变量不在子进程环境里（服务起的每一个内核子进程都如此，与路由无关，不给任何路由开例外）；`CODEKIT_ACTOR` 是 `user-ui`；`NoDefaultCurrentDirectoryInExePath` 在；不设 `PYTHONUTF8=1`（除非执行端核实出 stdout 不是 UTF-8，那时才加并在 README 注明偏离 kernel_env）；用例：`ts/packages/ui/test/kernel-env.test.ts`；证据：V02；目的：子进程拿不到决策 API 的 key，也不改内核认定的环境。
- D05：19 条读路由都有对应的内核 CLI 写法与 argv 模板，每条模板都能被内核真正的解析器解析，模板带 `--json` 时解析结果的 json 为真；每条路由各有一条替身用例（argv、时限、错误映射）；用例：`ts/packages/ui/test/argv-templates.test.ts` 与 `ts/packages/ui/test/kernel-runner.test.ts` 里的每条路由那条；证据：V02；目的：路由与内核的命令行一一对应，不靠猜。
- D06：信封的形状与脱敏次序——七个字段与次序照 `ENVELOPE_KEYS`；`messages` 只留 `ERROR`、`WARN` 开头的行且逐行过 redactSecrets；`command` 不含 python、kernel、`--repo` 与仓库路径，游标显示成 `<cursor>`、transcript 显示成 `<transcript>`；`data` 用 pyjson 的 dumps(ensureAscii:false, indent:2) 写出；用例：`ts/packages/ui/test/kernel-runner.test.ts` 与 `ts/packages/ui/test/redaction.test.ts`；证据：V02；目的：信封是界面的唯一契约，顺序与写法不能各路由各一套。
- D07：二道脱敏与白名单——`/profiles` 的 credential_env、`/config` 的 secret.source、env_remove、env_keep、`/secrets` 的 name、source、used_by 原样返回；换成令牌形状、枚举之外的值或任意文本之后被遮掉；不合约束的白名单值照样遮掉；file 路由的数据不登记任何白名单条目；用例：`ts/packages/ui/test/redaction.test.ts` 的 U22 与 `ts/packages/ui/test/redaction-routes.test.ts` 的 U5；证据：V02；目的：白名单只放名字与来源这类可枚举的形状，绝不放凭据值。
- D08：并发上限、队列与 503——同时 10 个请求，任何时刻在跑的子进程不超过 4；排队的都拿到结果；队列调小之后回 503 且带 `Retry-After: 2`；用例：`ts/packages/ui/test/kernel-runner.test.ts` 的 U28；证据：V02；目的：服务不被请求洪水拖垮，也把排队这件事说清楚。
- D09：超时限时整棵树结束——超时回 504，信封是 ok=false、exit_code=null、command 是显示 argv、messages 只有「ERROR: 命令超时（N 秒），子进程已结束；请改用 CLI 查看」；子进程与孙进程都不在了；用例：`ts/packages/ui/test/kernel-runner.test.ts` 与 `ts/packages/ui/test/kernel-real.test.ts` 的 file 超时那条；证据：V02；目的：超时不能留下还在跑的进程。
- D10：断开取消与关停取消——客户端断开后 10 秒内那个 pid 不在了；关停时在跑的子进程被取消、队列被清空、新请求回 503；排队中被取消的请求不起子进程；用例：`ts/packages/ui/test/kernel-runner.test.ts`；证据：V02；目的：连接没了就别占着机器。
- D11：file 路由的句柄与 409——句柄是 43 个字符的随机不透明句柄、不含内核游标；伪造的句柄、服务重启之前的句柄、换了 task/attempt/path 的句柄都回 409 且替身没有被调用；内核报「游标对应的文件已变化」回 409；`next_cursor` 是句柄；用例：`ts/packages/ui/test/cursors.test.ts` 的 U14f、`ts/packages/ui/test/kernel-real.test.ts` 与服务层的 U14d；证据：V02；目的：界面拿不到也伪造不了内核游标。
- D12：合成的 `/secrets` 与 `/secrets/<name>`——名单来自 decisions 与各 profile 的 credential_env，去重且保序；逐条串行跑 `config secret check`；成功的信封 command 是空数组、exit_code 是 0；任何一条失败就停下并回那一条子命令的信封；每项是 `{name, source, store_mode, system_backend, used_by}`，不含 `file_dir`；用例：`ts/packages/ui/test/redaction.test.ts` 的 secrets 部分与 `ts/packages/ui/test/kernel-runner.test.ts`；证据：V02；目的：凭据只报来源与名字，永不报值与路径。
- D13：meta 的 data 合成——`{version, repo_name}`，version 取 `--version` 的 stdout 去掉末尾换行，repo_name 取仓库目录名；用例：`ts/packages/ui/test/kernel-runner.test.ts` 的 meta 那条；证据：V02；目的：版本与仓库名不必起子进程就能给，也不外泄别的。
- D14：U12 安全头与 no-store——读路由的响应带 CSP、`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer` 与 `Cache-Control: no-store`，响应里没有 `Access-Control-*`；用例：`ts/packages/ui/test/` 下的安全头那条；证据：V02；目的：本机响应不给浏览器别的能力。
- D15：U9 真内核逐字节一致——同一夹具仓库上，status 与 file 的 data 用 pyjson 的 dumps(ensure_ascii:false, indent:2) 拼出来，与 CLI 的 stdout（去掉末尾换行；file 另把句柄换回 CLI 的 next_cursor）逐字节相同；用例：`ts/packages/ui/test/kernel-real.test.ts`；证据：V02；目的：服务给界面的与终端里看到的是同一份数据。
- D16：README——写结构表、最小 API、状态码（409、503 带 Retry-After、504）、已知限制；并写明决策 key 被去掉之后 `/secrets` 与 `/config` 显示的这把 key 的 source 不再是 env（与终端里同一条命令不同）；还要写明原因：桌面应用从开始菜单或资源管理器起，它的环境来自登录时的用户与系统环境变量；用户在终端里临时设的、或写在 PowerShell profile 里的变量，桌面应用看不到；所以「这把 key 在不在环境变量里」的权威说法只有用户在自己的终端里跑 `config secret check` 给出的那一个；服务不把这把 key 传给内核，`/secrets` 与 `/config` 里它的 source 不会是 env，以终端里的 `config secret check` 为准；界面上的文案（这把 key 显示成「环境变量：服务不检查，以终端为准」）属于前端，不在本片；用例：`ts/packages/ui/README.md` 由 V08 检查；证据：V08、V02；目的：显示不一致这件事写清楚，别被当成 bug。
- D17：门禁、范围、变异与接线——G01、R01、V01–V08 全部通过；改动只落在允许范围内的路径（V07 核对）；依赖清单与锁文件未改；既有用例未删未跳未弱化；M1–M21 每条都有会变红的用例；新增的六个源文件都能从 `main.ts` 顺 import 到达；T015 的长期断言（routes.ts 四条路由名/路径/引导正则、static.ts 原有 14 个 reason、lockdir.ts 三条被占提示原文、DURABLE_SRC 顺 import 可达）一条未破；证据：G01、R01、V01、V02、V03、V04、V05、V06、V07、V08；目的：不破坏已有门禁，也不靠削弱测试过关。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 发现某条读路由没有对应的内核 CLI 写法（不新增内核命令与选项），停下并报告。
- 达到单轮时限。

## Budget
- max_attempts_total: 2（按 task-id 汇总，包括返工版本；本任务此前已用 0 次）
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 7200（已用 0 秒；= 2 倍单次时限）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：预检 300s、T17/T18/T19 与路由表 1200s、执行器与脱敏 1200s、补测（U4、U9、U22、U5、U28、U14f）900s、必要检查 600s、最终报告 200s；总计不超过单轮时限

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D17，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261024T074113217939Z-owner-b597ad：

> 摘要: 规划报告第 13 节的十条，规划端（本会话）代定，都照规划的建议，用户没有逐条看过。合同端照此写。
>
> 1. 超时回 504，加超时信封。
> 2. 时限照建议：meta 15 秒；file 60 秒；usage 120 秒；合成的 /secrets 每条 30 秒、整条 120 秒；其余 30 秒。
> 3. 并发上限 4、队列 16、Retry-After 2 秒。“可配”这一片只开放给测试入口。
> 4. 合成的 /secrets：逐条串行，任何一条失败就停下，回那一条子命令的信封；成功时 command 为 []、exit_code 为 0。
> 5. 照 T5 去掉 TYPESAFE_API_KEY。
>    - README 写明：/secrets 与 /config 显示的这把 key 的 source 不会是 env，与终端里同一条命令不同。
>    - 这一条的利弊（界面与终端显示不一致）规划端会与 themistally-15 复议，有变化另出决定，本片照此做。
> 6. 白名单加 `keys[key=decisions].value.api_key_env`，并照环境变量名的约束校验；`decisions.secret.file_dir` 不加。
> 7. T19 用探端口。
> 8. meta 的 data 写成 `{version, repo_name}`。
> 9. 临时目录放在系统临时目录。
> 10. A2 若核出 pi_dispatch 的 stdout 不是 UTF-8，子进程的环境加 PYTHONUTF8=1。pi_dispatch.main 已经把 stdout 改成 UTF-8，预计不需要。真要加，在 README 里注明它偏离 kernel_env。

站主来信 20261024T074226475428Z-owner-3aed88：

> 摘要: 补充上一封第 5 条。规划端（本会话）与 themistally-15 复议后代定：照 T5 一律去掉决策 API 的 key，不给任何路由开例外；README 写明原因；测试钉住所有内核子进程。
>
> 1. 不开例外的原因，README 照写：
>    - 桌面应用从开始菜单或资源管理器起，它的环境来自登录时的用户与系统环境变量；用户在终端里临时设的、或写在 PowerShell profile 里的变量，桌面应用看不到。
>    - 所以“这把 key 在不在环境变量里”，权威说法只有用户在自己的终端里跑 `config secret check` 给出的那一个。服务即使不去掉它，两边也对不上。
> 2. README 写明：服务不把这把 key 传给内核，/secrets 与 /config 里它的 source 不会是 env，以终端里的 `config secret check` 为准。
> 3. 测试钉住 T5：服务起的每一个内核子进程，环境里都没有这把 key，与路由无关。变异清单里“决策 key 被去掉”那一条要真的覆盖到所有路由，已有的测试覆盖了就不另写。
> 4. 界面上的文案（这把 key 不显示成“无”或“未配置”，而是写“环境变量：服务不检查，以终端为准”）属于前端，不在本片；已记进设计，留给前端接入真实服务的那一片。
