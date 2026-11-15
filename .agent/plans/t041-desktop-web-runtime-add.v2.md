# TASK: t041-desktop-web-runtime-add

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: df8ce22adce2d2383341137516e5cf04a2c4bc5c
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
把「CLI 运行时」页页头的[手动登记…]从禁用按钮接成真入口：点开表单对话框，填运行时 ID、适配器（五值，含 quizs）与可选的命令（JSON 字符串数组），底部实时显示内核预览（服务侧的预览请求带 `--dry-run --json`；界面显示的是「将运行的命令」，按既有口径去掉这两个开关），[确认…] 走现有确认框（预览 → 确认 → 执行 runtime.add → 重读 → 终态），成功后重读并出成功轻提示；`api.ts` 加 `addRuntime`、`WriteAction` 加 `'runtime.add'`，桩模式补桩与情景；同一个 id 已登记为别的适配器时按内核原文显示，界面上不提供 force。

## Non-goals
- 不做[扫描 PATH]（服务没有 `config runtime scan` 写路由）。
- 不做 quizs 运行时的证书状态与提供方档案。
- 不改内核（`scripts/kit_roles.py`、`scripts/kit_config.py` 一字不动）。
- 除站主拍板的四处外不改服务。
- 不给界面加 force；把岗位绑到某个运行时的事留给 T038 B 片。
- 不扩 `PreviewData`（不加 `changed` 字段），不显示「没有变化」。
- 不新增 `src/mock/*.json`（仍 14 份），不新增 `src/pages` 顶层 `*Page.tsx`（仍 9 个），不动 `components/**`。
- 不改任何依赖清单与锁文件（`ts/bun.lock`、`desktop/web/package-lock.json` 一个字不动）。

## Repository facts
- 入口：
  - `desktop/web/src/pages/RuntimesPage.tsx`：页头两个 `DisabledAction`（[扫描 PATH] 带 SearchIcon、[手动登记…] 带 PlusIcon 且 variant=primary）；`loadRuntimes` 与 `isRuntimesEmpty` 是模块级具名函数；children 形如 `(data, reload) =>`；空态说明原文「在命令行里用 config runtime scan --add 登记；界面上的登记入口在第二阶段接入」。
  - `desktop/web/src/writes/ProfileForm.tsx`：表单样板（300ms 防抖实时预览、[确认…] 门控、确认时先 onClose 再 start、成功后才清空表单、自渲染 `<WriteFlow flow={flow} />`）。
  - `desktop/web/src/writes/useLivePreview.ts`：预览 300ms 防抖、迟到回应丢弃；`result.error` 是预览原文；`fromReply` 把服务回的命令里的 `--dry-run`、`--json` 过滤掉（注释写着「去掉 --dry-run 与 --json 的命令」），所以界面显示的是「将运行的命令」，不含这两个开关。
  - `desktop/web/src/writes/useWriteFlow.ts`：`runPreview` 同样把 `--dry-run`、`--json` 过滤掉（注释：「将运行的命令」要的是真正会跑的写命令）。
  - `desktop/web/src/api.ts`：`WriteAction`（:60-72）现有 11 个成员，没有 `'runtime.add'`；`PreviewData`（:90-99）八键，没有 changed；`writeArgs`（:179-190）空串与空数组不传这个键；`toPreviewData`（:215-244）不保留 changed；`removeRuntime`（:574-584）是同步 `export function`，真实模式 POST `/api/v1/runtimes/<id>/remove`，时限 `WRITE_TIMEOUT_SECONDS` = 90。
  - `desktop/web/src/mock/writes.ts`：`baseArgv`（:59-92）兜底是 profile.edit；`NEW_ACTIONS`（:106）八个 action；`previewData`（:120-180）兜底 resources 是 `['plugins']`；`confirmWrite`（:316-330）确认号或参数不符回 409；情景值共 22 个（:24-31）。
  - `desktop/web/src/writes/snapshots.ts`：`runtimeRemoveSnapshot`（:91-98）投影 `runtimes[].{id, adapter}`，本片原样复用，不改名、不改这个文件。
  - `desktop/web/src/writes/profileRules.ts`：`validId` 用 `^[a-z0-9][a-z0-9-]{0,63}$`（与内核 `TASK_ID_RE` 一致）；本片只引用它。
  - `desktop/web/src/shell/PageFrame.tsx`：页头 actions 在 loading/data/empty/error 各态都渲染（:183-184），`actions` 可以是 `(reload) => ReactNode`；刷新钮排在 actions 之后。
  - `desktop/web/src/components/Button.tsx`：没有 icon 属性，图标作为 children 放在文字前面；`data-variant` 就是 variant。
  - `desktop/web/src/components/actionTitle.ts:14`：动作说明「登记 runtime」的唯一出处；入口文件与 `src/writes` 都不许再写这一句。
  - 服务 `ts/packages/ui/src/writeroutes.ts`：`ADAPTERS`（:53-54）四个值 pi、claude-code、codex、opencode；`runtime.add` 必填 runtime、adapter，可选 command、force（:89）；`validCommand`（:219-223）非空数组、每项 1–1024 码点且不含控制字符与孤立代理项；`buildWriteArgv`（:318-322）拼 `config runtime add <id> --adapter=<a>`，有 command 再加 `--command=<JSON.stringify(command)>`；路由 `POST /api/v1/runtimes/<id>/add`（:600）；参数不合法回 400「<键> 不合法」（:405-406）；内核退出非 0 时回 200、ok 为假、messages 带内核的 ERROR 行（:411-421）。
  - 内核 `scripts/kit_roles.py`：适配器五值 pi、claude-code、codex、opencode、quizs；`_runtime_add`（:833-861）——已登记为别的适配器且没有 `--force` 时报「runtime %s 已登记为 %s；改 adapter 要加 --force」；同一个适配器不报错，打印「没有变化：runtime X（adapter Y）」；`_parse_command`（:795-805）要求非空 JSON 字符串数组，疑似凭据退出 2，不检查绝对路径。
  - 内核报错前缀与退出码：`scripts/kit_config.py:1798` 打印 `ERROR: <原文>` 到 stderr 并返回 `exc.code`；退出码常量 `scripts/kit_config.py:65`（EXIT_OK=0、EXIT_FAIL=1、EXIT_USAGE=2）。所以「已登记为别的适配器」在预览时的原文是 `ERROR: runtime <id> 已登记为 <adapter>；改 adapter 要加 --force`，退出码 1。
  - `desktop/web/tests/page-app.test.tsx`：:91-98 是过渡计数（角色页 6、运行时页 6、总览 0）；[手动登记…] 可点以后运行时页的禁用按钮数从 6 变 5。
  - `desktop/web/tests/live-api.test.ts`：:389-425 有 `WRITE_ROWS` 表；本片加 addRuntime 一行。
  - `ts/packages/ui/test/write-argv.test.ts`：:228-247 是各参数的取值用例（含 runtime.add 的 ok/bad）；本片加一条 quizs 的 ok 用例。
  - 门禁（本基线已含站主 2026-11-14 的四处放宽，逐条核对过文件内容）：
    - `tests/test_gate_t009_baseline.py`：:2879-2888（页头按钮次序 `['扫描 PATH','手动登记…','刷新']`、[扫描 PATH] 禁用、[手动登记…] 带 PlusIcon 且 `data-variant` 为 primary；可点与否不钉）、:2913-2917（空态只钉标题「还没有登记的 runtime」）、:2974-2981（运行时页可用按钮白名单 `['删除…','手动登记…']`；仍禁用的按钮悬停提示必须是「第二阶段接入」，禁用按钮数要大于 0）、:865-890（`page_wiring_problems`：三个页面只许从 `../api` 引入读函数，load/isEmpty 必须是具名模块级函数，children 形如 `(data, reload)`）。
    - `tests/test_gate_t031_baseline.py`：:520、:536（runtime.add 的 ADAPTERS 至少有原来四个值；「不许加 quizs」已退役）。
    - `tests/test_gate_t023_baseline.py`：S08、S10、S11、S13、S15（见上文各条）。
    - `tests/test_gate_t037_baseline.py`：S03（写侧函数必须是同步 `export function`；导出集合按包含不卡恰好）、S04（mock 的导出与情景值按包含不卡恰好）。
    - `tests/test_gate_t013_baseline.py`：D02（13 条动作说明只在 components/actionTitle.ts）。
    - `tests/test_gate_t032_baseline.py`：UNTOUCHED_REL（:115-130）名单一个字不许动。
- 调用关系与现有约定：
  - 页面只从 `../api` 取读函数；表单与写流程都在 `src/writes`；确认框标题、成功轻提示、变化摘要一律由 `src/writes/useWriteFlow.ts` 的 `titleOf` / `successTextOf` / `changeSummaryOf` 按 action 与 args 拼。
  - 写流程：`useWriteFlow.start(spec)` → `preview` → 确认框 → 执行 → 重读（`readSnapshot`）→ 终态与轻提示。
- 工具链与锁文件：
  - `desktop/web` 用 npm：目录里有 `package-lock.json`（锁文件提交），基线上依赖已装好（内核基线 V01 在 `desktop/web` 通过）；`npm run build` = `tsc --noEmit && vite build`，`npm test` = `vitest run`，另有 `npm run check:contract`。
  - `ts` 用 Bun：`ts/package.json` 的 `packageManager` 是 `bun@1.4.2`，目录里有 `bun.lock` 与 `bunfig.toml`，没有 `package-lock.json`；worktree 的 `node_modules` 不提交，所以基线上 ts 的依赖未装好——基线跑 V03 是红的（`Cannot find module …/ts/node_modules/vitest/vitest.mjs`，退出码 1），靠 Setup 的 S02（`bun install --frozen-lockfile`，cwd ts）装上；ts 侧的 vitest 按 `node node_modules/vitest/vitest.mjs run …` 调用（已验收先例 t015/t016/t017/t020/t021/t031 同款）。
  - 仓库门禁用 `python -m pytest`。
  - 本片不改任何依赖清单与锁文件；`bun install --frozen-lockfile` 只按锁文件重链，不改 `ts/bun.lock`。
- 基线检查：回归门禁（R01 列出的各片基线测试）在基线上必须全绿（基线实测 943 passed，约 1225s）；本片门禁 G01 在基线上应失败（门禁测试文件由门禁端写好、内核做成基线提交）；`desktop/web` 的依赖在基线上已装好，`ts` 的依赖在基线上未装（见上）。

## Scope
- allowed_modified_files:
  - desktop/web/src/api.ts
  - desktop/web/src/mock/writes.ts
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/pages/RuntimesPage.tsx
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/live-api.test.ts
  - ts/packages/ui/src/writeroutes.ts
  - ts/packages/ui/test/write-argv.test.ts
  - ts/packages/ui/README.md
  - ts/packages/ui/src/redaction.ts
- allowed_new_files:
  - desktop/web/src/writes/RuntimeForm.tsx
  - desktop/web/src/writes/runtimeRules.ts
  - desktop/web/src/writes/runtime-form.css
  - desktop/web/tests/writes-runtime-form.test.tsx
  - desktop/web/tests/writes-runtime-api.test.ts
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t041_*.py
  - tests/test_gate_*.py
  - desktop/web/src/shell/PageFrame.tsx
  - desktop/web/src/App.tsx
  - desktop/web/src/shellpages/shellStub.ts
  - desktop/web/src/shellpages/ShellWindow.tsx
  - desktop/web/src/shellpages/SettingsView.tsx
  - desktop/web/src/shellpages/shellWindowRoute.ts
  - desktop/web/vite.config.ts
  - desktop/web/scripts/check-live-build.mjs
  - desktop/web/tests/shellpages-*.test.*
  - desktop/web/tests/cleanup2-static.test.ts
  - desktop/web/src/live/**
  - desktop/web/src/components/**
  - desktop/web/src/pages/readonly1/**
  - desktop/web/src/pages/readonly2/**
  - desktop/web/src/mock/*.json
  - desktop/web/src/writes/snapshots.ts
  - desktop/web/src/writes/useLivePreview.ts
  - desktop/web/src/writes/ProfileForm.tsx
  - desktop/web/src/writes/profileRules.ts
  - scripts/kit_roles.py
  - scripts/kit_config.py
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
- 正常输入：
  - 运行时 ID：小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符（复用 `profileRules.validId`）。
  - 适配器：下拉五个值 pi、claude-code、codex、opencode、quizs，缺省 pi。
  - 命令：可选。留空 → 不传 `command` 这个键；非空 → JSON 字符串数组，例如 `["C:/tools/pi.exe","--flag"]`。
  - 流程：点页头[手动登记…] → 对话框（标题「登记运行时」）→ 表单合法时 300ms 防抖后调预览 → 底部显示将运行的命令、警告与内核报错原文（显示的命令与服务 `buildWriteArgv` 逐字一致，不含 `--dry-run`、`--json`；这两个开关只出现在服务侧的预览请求里）→ [确认…] → 确认框（标题「登记运行时 X？」，变化区摘要「已登记表里加上 X（适配器 A）」，带命令时接「；命令写进本机文件」）→ 执行 runtime.add → 重读 → 终态；成功才出轻提示「已登记运行时 X」，成功且对话框关闭后表单清空。
  - 离线（`?mock=offline`）时[手动登记…]照样可点。
- 边界输入：
  - ID 不合法（空、大写、下划线、超 64 字符、以连字符开头）→ 表单不合法，不调预览，[确认…] 不可点，字段下显示「只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符」。
  - 命令不是合法 JSON 字符串数组（非 JSON、空数组、含空串、某项超过 1024 码点、含控制字符）→ 表单不合法，不调预览，字段下显示「命令要写成 JSON 字符串数组，例如 ["C:/tools/pi.exe"]；每项非空、不超过 1024 个字符、不含控制字符」。不强制绝对路径。
  - 同一个 id、同一个适配器、不带命令 → 预览不算错，界面照常走完流程并出成功轻提示；不显示「没有变化」。
  - 同一个 id 已登记为别的适配器 → 预览阶段内核退出 1，界面原样显示 `ERROR: runtime <id> 已登记为 <adapter>；改 adapter 要加 --force`，[确认…] 不可点；界面任何位置没有 force。
  - 服务参数不合法（回 400「<键> 不合法」）→ 预览区显示该行，[确认…] 不可点。
- 错误与重试：
  - 预览失败或服务没回应 → 预览区显示「预览失败：服务没有回应」，[确认…] 不可点；改取值后重新预览（防抖 300ms，迟到回应丢弃）。
  - 执行失败（退出非 0）→ 终态显示内核原文；快照（`runtimeRemoveSnapshot`）变了就判「已部分写入」，没变判「失败」。
  - 确认号失效或参数不符 → 服务回 409「确认号无效、已过期或已用过：请重新预览」。
  - 桩模式：`?write=preview-registered` 时预览回 200、ok 为假、退出码 1、messages 一行 `ERROR: runtime <id> 已登记为 <adapter>；改 adapter 要加 --force`，不发确认号；确认号或参数不符回 409。
- 并发、取消与状态变化：取消对话框不写任何东西；执行中的写操作由现有轮询与终态判定负责；快照在预览与重读各读一次，比较 `runtimes[].{id,adapter}`，新 id 出现即判「已部分写入」。
- 兼容性：
  - `WriteAction` 新增成员 `'runtime.add'`，既有成员与导出集合一个不丢；新增导出 `addRuntime`（同步 `export function`）。
  - 服务侧公开形状不变：`POST /api/v1/runtimes/<id>/add` 的路径与正文不变；只有 `ADAPTERS` 的取值集合由四个扩到五个。
  - `PreviewData` 形状不变；`src/mock/*.json` 数量不变；`src/pages` 顶层页面数不变；`components/index.ts` 不引用 writes/。

## Steps
1. 依赖：确认 Setup 的 S01（`desktop/web` 的 `npm ci --no-audit --no-fund`）与 S02（`ts` 的 `bun install --frozen-lockfile`）都已跑过，`desktop/web/node_modules` 与 `ts/node_modules` 在位；不在位就自己按这两条命令补装（不改任何依赖清单与锁文件，`bun install --frozen-lockfile` 只按锁文件重链）。装完先跑一遍 `node node_modules/vitest/vitest.mjs run packages/ui/test/write-argv.test.ts`（cwd ts）确认 V03 能跑起来，再动代码。
2. 读 `desktop/web/src/api.ts`、`desktop/web/src/writes/useWriteFlow.ts`、`desktop/web/src/mock/writes.ts`、`desktop/web/src/pages/RuntimesPage.tsx`、`desktop/web/src/writes/ProfileForm.tsx`、`ts/packages/ui/src/writeroutes.ts`，确认签名与「Repository facts」一致；不一致就停止并报告。
3. `desktop/web/src/api.ts`：`WriteAction` 加 `'runtime.add'`；新增 `export function addRuntime(args: { runtime: string; adapter: string; command?: string[] }, confirmation: string): Promise<HttpReply<null>>`——真实模式 POST `/api/v1/runtimes/${encodeURIComponent(args.runtime)}/add`，正文 `{ ...writeArgs({ adapter, command }), confirmation }`（空数组的 command 会被去掉，等于「命令留空不传」），时限 `WRITE_TIMEOUT_SECONDS`；桩模式转 `mockAddRuntime`。函数保持同步 `export function`。
4. `desktop/web/src/mock/writes.ts`：`baseArgv` 加 runtime.add 分支，逐字照服务 `buildWriteArgv`——`['config','runtime','add',runtime,'--adapter='+adapter]`，命令非空时再加 `'--command=' + JSON.stringify(command)`；`NEW_ACTIONS` 加 `'runtime.add'`；`previewData` 加 runtime.add 分支（`binding_changes` 恒空；`resources` 无命令时 `['config']`、有命令时 `['config','local']`）；新增 `mockAddRuntime(args, confirmation)`，参数整理成 WriteArgs（command 为空数组时不带这个键）后走 `confirmWrite`；新增情景 `preview-registered` 并加进 `SCENARIOS`——预览回 200、`ok:false`、`exit_code:1`、`data:null`、messages 一行 `ERROR: runtime <id> 已登记为 <adapter>；改 adapter 要加 --force`，不发确认号。
5. `desktop/web/src/writes/useWriteFlow.ts`：`titleOf` 增 `登记运行时 ${args.runtime}？`；`successTextOf` 增 `已登记运行时 ${args.runtime}`；`changeSummaryOf` 增 `已登记表里加上 ${args.runtime}（适配器 ${args.adapter}）`，args 里有 command 时接 `；命令写进本机文件`；`readSnapshot` 必须新增 runtime.add 分支——`getRuntimes()` + `runtimeRemoveSnapshot`，不许落到 `getPlugins` 的兜底分支；`confirm` 的分派链增 runtime.add → `addRuntime`；`dangerOf` 不变（primary）。
6. 新文件 `desktop/web/src/writes/RuntimeForm.tsx`（样式可新建 `runtime-form.css` 并 import，或复用 `profile-form.css` 的 pf-* 类）：导出 `AddRuntimeAction({ reload })`——按钮 `variant="primary"`、`size="md"`、children 里先放 `<PlusIcon width={16} height={16} />` 再放文字「手动登记…」，离线也可点；点开对话框，标题「登记运行时」；三个字段：ID（等宽，`validId`）、适配器（`Select`，五个值，缺省 pi）、命令（等宽，help「JSON 字符串数组，第一项写命令的绝对路径」）；底部用 `useLivePreview('runtime.add', args, canPreview)` 显示命令、警告与内核报错原文（`result.error` 原样显示；显示出来的命令是 `useLivePreview` 过滤后的「将运行的命令」，不含 `--dry-run`、`--json`）；[确认…] 的门控照 ProfileForm：`canPreview && current && result !== null && result.ok`；确认时先 `onClose()` 再 `start({ action: 'runtime.add', args })`；成功（有轻提示）后清空表单；自己渲染 `<WriteFlow flow={flow} />`。整个界面不许出现 force。
7. 新文件 `desktop/web/src/writes/runtimeRules.ts`（或在 `RuntimeForm.tsx` 内，但不改 `profileRules.ts`）：导出命令文本的解析与校验——空串 → 不传 command（合法）；否则 `JSON.parse` 必须是数组且非空，每项是非空字符串、不超过 1024 码点、不含控制字符（C0 与 DEL）；不合规则表单不合法。
8. `desktop/web/src/pages/RuntimesPage.tsx`：`actions` 改成函数形式拿到 reload——`<DisabledAction label="扫描 PATH" icon={<SearchIcon width={16} height={16} />} />` 之后接 `<AddRuntimeAction reload={reload} />`（次序不变：扫描 PATH、手动登记…、刷新）；页头说明原文、具名的 `loadRuntimes` / `isRuntimesEmpty`、`children` 形如 `(data, reload) =>` 与 `reload={reload}` 一律不动；空态标题「还没有登记的 runtime」不动，说明改成「用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）」；文件头注释同步更新。入口文件不许出现确认框标题、成功轻提示与内核原文。
9. 服务侧四处（站主拍板的方案乙，只改这四处）：`ts/packages/ui/src/writeroutes.ts` 的 `ADAPTERS` 改成 `["pi","claude-code","codex","opencode","quizs"]` 并改 :53 的注释；`ts/packages/ui/test/write-argv.test.ts` 加一条 quizs 通过的用例（`ok("runtime.add", { runtime: "demo-runtime", adapter: "quizs" })`）；`ts/packages/ui/README.md` 里 runtime.add 那一条补一句「adapter 取五值：pi、claude-code、codex、opencode、quizs」；`ts/packages/ui/src/redaction.ts` 的 :14 注释把「quizs 只承载七端岗位（不进 runtime.add 的四值 ADAPTERS）」改成 runtime.add 的 ADAPTERS 也是这五个（只改注释，枚举不动）。
10. 测试：
   - 新增 `desktop/web/tests/writes-runtime-form.test.tsx`：表单门控、预览显示将运行的命令（不含 `--dry-run`、`--json`）、内核报错原文原样显示、成功轻提示「已登记运行时 X」、离线时[手动登记…]仍可点、界面没有 force。
   - 新增 `desktop/web/tests/writes-runtime-api.test.ts`：`addRuntime` 真实模式的路径与正文（用 `src/live/mode.ts` 的 `setLiveClientForTests` 注入替身；命令留空时正文不含 command）、桩模式预览请求的命令与服务侧 `buildWriteArgv` 逐字一致（服务侧那条带 `--dry-run`、`--json`）、确认号或参数不符回 409、`preview-registered` 情景的原文与退出码。
   - `desktop/web/tests/page-app.test.tsx`：:91-98 的过渡计数里运行时页的禁用按钮数由 6 改成 5。
   - `desktop/web/tests/live-api.test.ts`：`WRITE_ROWS` 表加 addRuntime 一行。
11. 跑 Validation commands 里的全部必要检查（V01、V02、V03、G01、R01；V04 可选），逐条把命令、退出码与结果写进执行报告；R01 在基线上实测约 1225s，1800s 的超时留给它。遇到合同未定义的行为，停止并报告。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s
- S02：`bun install --frozen-lockfile` · cwd：ts · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态。

- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0 · 输出须匹配：`built in`
- V03（必要）：`node node_modules/vitest/vitest.mjs run packages/ui/test/write-argv.test.ts` · cwd：ts · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V04（可选）：`npm run check:contract` · cwd：desktop/web · 超时：300s · 期望退出码：0
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t041_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配:`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配:`\d+ passed`

## Definition of done
- D01：写路由接通——点页头[手动登记…]出表单，合法时出实时预览（界面显示的命令与服务 `buildWriteArgv` 逐字一致，不含 `--dry-run`、`--json`；服务侧的预览请求另带 `--dry-run`、`--json`，界面按既有口径 `useLivePreview`/`useWriteFlow` 把这两个开关过滤掉），[确认…] 进确认框（标题「登记运行时 X？」、变化区摘要「已登记表里加上 X（适配器 A）」），执行 runtime.add 后重读并出终态与成功轻提示「已登记运行时 X」；`WriteAction` 含 `'runtime.add'`；真实模式与桩模式两条路都有用例覆盖；证据：V01、V02；目的：界面真能登记一个运行时，而不是只多了一个按钮。
- D02：适配器下拉含五个值 pi、claude-code、codex、opencode、quizs，与 `writeroutes.ts` 的 ADAPTERS、`kit_roles.py` 的 ADAPTERS 一致；命令留空不传 `command`，非空按 JSON 字符串数组校验；证据：V01、V03；目的：选 quizs 的运行时不会在预览就被 400 拒掉，命令写错时在本地就被拦下。
- D03：同一个 id 已登记为别的适配器时，界面原样显示 `ERROR: runtime <id> 已登记为 <adapter>；改 adapter 要加 --force`，[确认…] 不可点；界面任何位置没有 force；证据：V01；目的：不越权替用户改适配器，也不让用户以为界面能改。
- D04：命令输入的本地校验与服务 `validCommand` 一致（非空数组、每项非空、不超过 1024 码点、不含控制字符），不强制绝对路径；证据：V01；目的：不把内核一定会拒的值发到服务。
- D05：所有修改都在允许集合内；门禁文件、T032 禁改名单、内核、components、readonly1/2、`src/mock/*.json`、snapshots.ts 一个字没动；证据：scope、review；目的：这片不许顺手改别的片的地盘。
- D06：没有删除、跳过或弱化既有测试；`desktop/web` 与 `ts` 的既有用例原样通过；证据：V01、V02、V03、review。
- D07：门禁在站主放宽（R1、R2、R3、R4）之后照样过——T009 的页头探针（次序、PlusIcon、primary、可用按钮白名单、仍禁用按钮的「第二阶段接入」悬停）、T023 的 S08/S10/S11/S13、T024 的 S06/S11、T031 的适配器检查、T037 的写函数与导出检查；证据：R01、G01、review；目的：本片接入口以后，早先为「入口还没接」而写的断言不该被顺手改掉。
- D08：服务只改了站主拍板的四处（ADAPTERS 加 quizs、:53 注释、写路由用例、README 与 redaction.ts 的注释），其余服务代码一字未动；证据：scope、review；目的：改适配器表是登记运行时的前提，不是扩范围。

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
- 强制方：调度器强制次数与墙钟；费用只统计
- 时间分配：依赖安装与基线核对 300s、实现 1200s、补测与新测试 500s、必要检查（V01、V02、V03、G01、R01；R01 在基线上实测约 1225s）1900s、最终报告 300s；总计 4200s，不超过单轮时限。

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

站主来信 20261114T091415931189Z-owner-3f158e：

> 站主决定（T041 规划交付后的提问）：
>
> 1. quizs 选乙：这一片顺带改服务，`ts/packages/ui/src/writeroutes.ts` 里 runtime.add 的适配器表加 quizs，与内核的五值表对齐；照规划报告第 3 节一并改 :53 的注释、`ts/packages/ui/test/write-argv.test.ts` 加一条 quizs 通过的用例、修正 `ts/packages/ui/README.md` 与 `redaction.ts:14` 注释里“四值”的说法。任务书的“不改服务”放宽到这几处为止，别的服务代码不动。理由：登记运行时不改任何岗位的模型；把岗位绑到 quizs 才是换模型，那一步走 T038 B 片的确认框，由用户本人确认。
> 2. 门禁断言由站主落盘，已在合同开工前合入（提交 c3d8ad9）：R1（T009 `test_d10_probe_runtimes_table` 不再钉[手动登记…]禁用）、R2（`test_d11_probe_write_entries_disabled` 运行时页的白名单加[手动登记…]）、R3 放宽（`test_d10_probe_readiness_and_empty` 只钉空态标题「还没有登记的 runtime」；入口接上之后说明不能再写“界面上的登记入口在第二阶段接入”，新说明由合同定）、R4（T031 `test_static_valid_value_hub_keys` 退役“不许加 quizs”，保留四个值都在）。都只放宽，现在的代码照样过。合同的允许修改范围不含门禁文件。
> 3. `desktop/web/tests/page-app.test.tsx` :91、:98 的过渡计数照规划报告列进允许修改范围，由执行端照新行为改。
> 4. 规划端按默认定下的几项照走：PreviewData 不扩 changed、命令不强制绝对路径、界面不提供 force、快照沿用 runtimeRemoveSnapshot、离线时[手动登记…]照样可点、桩加“已登记为别的适配器”的情景。
> 5. 合同端照旧等 T040 结项、内核把基线挪到新末端（会包含上面的门禁准备）再开工。合入后站主在真 Electron 窗口里走一遍：登记一个 quizs 运行时与一个 pi 运行时 → 新建 profile → 删掉。
