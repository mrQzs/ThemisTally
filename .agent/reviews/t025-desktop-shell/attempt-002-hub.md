# 复审记录：t025-desktop-shell attempt-002（七端信箱 hub）

- 合同：t025-desktop-shell.v2（base a99cb77ad204d657065ffb3881b1b88a8775be92）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261101T083112112941Z-8c00），终审报告如下

## 终审报告

# T025-7 终审报告（audit-sonnet · attempt-002）

## 0. 结论

**返工 → 退回执行端（3 条阻塞项）。**

除下面 3 条外，候选实现是忠实的：范围干净（补丁恰好 22 个新增文件，全在 `allowed_new_files` 内，无删除、无既有文件改动）、合同 §一–§九 的绝大多数条目逐字对得上、执行端自己的 12 份测试与 5 个夹具是真断言（不是空心断言、不是把业务逻辑抄进测试）、战后门禁的白盒与 48 条变异记录成立、JEV 的两条「需关注」不构成缺陷。

阻塞项集中在同一个根因上：**启动期有两个事件监听注册在事件可能发生之后**（窗口的 `closed`、服务的 `exit`），外加合同 §七 写明的 `io` 默认值没有兜底。

## 1. 本回合读了什么

- 合同：`.agent/plans/t025-desktop-shell.v2.md`（全文）
- 候选：`candidate.patch`（22 个文件）+ 工作副本里 `desktop/shell/**` 的全部 22 个文件（逐行读）
- 执行：`summary.md`、`executor-report.md`（含 JSON）
- 门禁：`T025-6-gate-post/report.md`、`evidence/mutate-…/mutations.json`、白盒源文件
- JEV：`T025-6j-jev/report.md`
- 只读参照：`ts/packages/ui/src/server.ts`（握手行、关停、看门狗）、`scripts/pi_dispatch.py`（`ui` 选项与 `--idle-timeout` 缺省 1800）、`desktop/web/package.json`（有 `build` 脚本）、`tests/test_gate_t025_baseline.py`（基准静态扫描规则）

本回合我没有执行工具（只有读/搜/列目录），所有结论来自源码与记录，没有重跑 V01/V02/G01/R01；执行报告里的自检数字按其自述采信。

## 2. 范围与候选核对

- `candidate.patch` 的 `diff --git` 恰好 22 条：README.md、main.js、package.json、package-lock.json、src/{args,core,handshake,python,service,window}.js、tests/{args,core,handshake,package,python,service,window}.test.js、tests/fixtures/{fake-python-fail,fake-python-hang,fake-python-ok,fake-python-old,fake-service}.js —— 与 `allowed_new_files` 逐条相等，无多无少。补丁里没有 `tests/**`（仓库的）、`desktop/web/**`、`ts/**`、`scripts/**`、`docs/**` 的任何 diff → D13 成立。
- `package.json`：`private:true`、`version 0.0.0`、`type commonjs`、`main main.js`、`scripts.start = "electron ."`、`dependencies` 不存在、`devDependencies = {"electron":"44.9.0"}` 精确无范围。
- `scripts.test` 与合同 §一 那一行**逐字相等**（`node --test --test-reporter=tap` 在文件清单之前，7 个 `*.test.js` 全列出）。
- `package-lock.json`：根 `packages[""].devDependencies.electron = "44.9.0"`、`packages["node_modules/electron"].version = "44.9.0"`、lockfileVersion 3、其余全是 electron 自己的依赖树（13 个包，`dev:true`），没有把 `electron` 以外的直接依赖写进 `dependencies`。
- `.gitignore` 未动；`node_modules`、`dist` 已被忽略。

## 3. 合同逐节忠实度

| 合同节 | 实现位置 | 核对结果 |
|---|---|---|
| §一 包与依赖 | package.json / package-lock.json | ✅ 逐字一致 |
| §二 参数 | src/args.js | ✅ 七条错误文案、缺项次序（repo、kit、assets）、绝对路径、`--python` 原样、transcripts 保序；`parseArgs(strict, allowPositionals:false)` |
| §三 找 Python | src/python.js | ✅ 探测码与候选数组逐字；首个可用的候选就赢；ENOENT/非 0/超时三种跳过，超时 kill 探测进程；`--python` 只试一个且不回退；core 传 `findPython({ python })` |
| §四 握手 | src/handshake.js | ✅ 七类错误；`origin` 正则严格锚定 + 端口 1–65535；bootstrap 必须同 origin；pid 只校验正整数；错误里没有回显任何字段值 |
| §五 服务 | src/service.js | ✅ `serviceCommand` 数组顺序与合同一致（`--repo` 在 `ui` 前、`--transcript` 逐项）；`spawn(command, [], {stdio:["pipe","pipe","inherit"], windowsHide:true, shell:false})` 的调用形状正确（首参完整 argv、第二参恒 `[]`、默认实现自己 `command[0]`/`slice(1)` 拆包）；stdin 一个字节都不写；stdout 只认第一行、之后继续抽干丢弃；握手非法/超时/握手前退出三条都结束子进程 |
| §六 窗口 | src/window.js | ✅ `webPreferences` 恰好十键、无 `preload`；`partitionName` 是 randomUUID、无 `persist:`、两次不同；`isServiceUrl` 正反例（userinfo、子域、`javascript:`、`file:`、`data:`、`about:blank`、非法串）都对 |
| §七 编排与入口 | src/core.js、main.js | ⚠️ 流程与退出码 0/1/2 对；`openWindow` 只收 `{bootstrap, origin}`；main.js 的菜单/分区/两个权限处理器/新窗口拒绝/will-navigate/isPackaged 取参/app.exit 都在 —— 但有两个事件监听注册得太晚（阻塞项 1、2），`io` 的默认值没兜底（阻塞项 3） |
| §八 README | README.md | ✅ 装法、`npm start -- --repo …`、参数表、退出码表、三个时限、`npm ci` 不下载本体与 `node node_modules/electron/install.js`、手工冒烟四步；`npm --prefix ../web run build` 与 desktop/web 的 scripts 一致 |
| §九 不变量 | 全局 | ✅ 不经 shell、只读第一行、令牌与 nonce 不进 stdout/stderr、一次只起一个服务 |

静态禁令（`persist:`、`shell: true`、fs 写函数、`fetch`、`net.request`、`http(s).request`、`autoUpdater`、`crashReporter`、`openExternal`、`require('electron')` 只许在 main.js）：src 与 main.js 里都没有，基准的 `test_s03` 也会扫，判过。

## 4. DoD → 实现 → 证据（终审版）

| DoD | 实现 | 由哪条断言证明 | 结论 |
|---|---|---|---|
| D01 | package.json / lock | `tests/package.test.js` 四条；基准 s01/s02；白盒 w01/w02 | ✅ |
| D02 | src/args.js | `tests/args.test.js` 11 条（逐字文案 + 绝对路径 + 保序）；基准 p01 | ✅ |
| D03 | src/python.js | `tests/python.test.js` 11 条（含真起进程的 ENOENT/退出码/超时）；基准 p02 | ✅ |
| D04 | src/handshake.js | `tests/handshake.test.js` 8 条（错误不含 TOKEN/NONCE/4242）；基准 p03 | ✅ |
| D05 | src/service.js `serviceCommand` | `tests/service.test.js` 前两条 + 真进程 argv 文件逐项 deepEqual；基准 p05 | ✅ |
| D06 | src/service.js `startService` | service.test.js：spawn 形状/options、分两段写、坏握手、超时、握手前退出 2、第二行标记不泄漏 | ✅ |
| D07 | src/service.js `stopService` | service.test.js：干净关停 code 0/killed false；忽略 EOF → killed true/exited false/code null（Promise 只在 exit/close 后兑现，进程确实没了）；EOF 后 7 | ✅ |
| D08 | src/window.js | `tests/window.test.js` 3 条；基准 p04 | ✅ |
| D09 | src/core.js | `tests/core.test.js` 6 条（2/1/0/1/1）；**缺口**：服务在开窗口期间退出没被覆盖 → 阻塞项 2 | ⚠️ |
| D10 | src/core.js | core.test.js `assertNoSecrets`：输出不含 TOKEN/NONCE，`openWindow` 参数只有 bootstrap/origin | ✅ |
| D11 | main.js + 静态禁令 | 基准 s03/s04、白盒 w03；`require('electron')` 只在 main.js | ✅（接线完整，但 `closed` 的挂载时机见阻塞项 1） |
| D12 | README.md | 基准 s05、白盒 w04 | ✅ |
| D13 | 补丁文件清单 | candidate.patch 22 个 diff | ✅ |
| D14 | 测试与既有门禁 | 无 skip/only/todo（`grep` 结果 none）；R01 753 passed（执行报告自述） | ⚠️ 候选本身干净；但执行过程用了固定 `/tmp/…` 路径（不挡的意见 2） |

## 5. 测试质量核对（不是空心断言 / 不是为过测试而写的特判）

12 份测试 + 5 个夹具逐个看过，结论是**扎实**：

- 断言的是真实实现，没有把业务逻辑抄一份进测试；mock 只用在「假 spawn / 假窗口」这种边界上。
- 硬编码检查：`TOKEN="ctrl-tok-XYZ"`、`NONCE="nonceABC"`、`ORIGIN="http://127.0.0.1:8123"` 只是夹具常量，没有为了让实现通过而反向迁就实现。
- 时限全部用可覆盖的毫秒参数（`timeoutMs`/`graceMs`），没有等真时限。
- 「不经 shell」是用真进程 + argv 落盘后逐项 deepEqual 证明的，不是断言 spawn 的参数形状了事。
- 「stdin 一个字节都不写」由夹具「收到任何数据就以 9 退出」反证，是行为断言。
- 「第二行不泄漏」用带标记的第二行 + 200 ms 后断言标记不在任何输出里。
- 「错误不回显字段值」在 handshake.test.js 里逐个错误断言不含 TOKEN/NONCE/4242。
- 夹具用 `[process.execPath, 脚本]` 前缀（Windows 上不经 shell 起不了 .cmd），与规划端要求一致。
- 没有 skip / only / todo；`scripts.test` 显式列全 7 个测试文件，夹具目录里没有 `*.test.js`。

**缺口**：没有任何用例覆盖「服务在开窗口期间退出」和「窗口在 openWindow 返回前被关」，这正是两个阻塞项的来源。门禁的 48 条变异也覆盖不到这一类（静态标记看不出来，探针也没有这种时序），所以「全绿」在这里等于没测。

## 6. 门禁与内核记录核对

- 基准 G01 11 passed（执行报告）、白盒 8 passed、变异 48/48 caught、`files_left_modified: []`（树被还原干净）。
- 逐条判断「这些变异是不是真的测得出来」——抽查了接线类与取值类的代表：M24（收服务不关 stdin）、M31（去掉 serviceCommand 的解构引用）、M34（信封整个当值）、M35（openWindow 收整个握手对象）、M42（取参切片对调）、M44（scripts.test 去掉 tap）、M47（锁文件 electron 版本改错）——这些都是会改变**可观察行为**的变异，白盒/基准里都有对应的行为断言，不是靠文本匹配判红。结论：门禁端声明成立。
- M07（python 选项被忽略）与 M32（core 不传 python）判 caught 的机制是「探针挂起 → 内核超时杀进程」（`exit_code 3221225786`、`timed_out: true`），不是断言失败。检测有效，但每条要烧 90 秒，且白盒里没有为挂起型变异留有界超时断言（不挡的意见 3）。
- 「门禁端说没法变异的改动文件」：没有这种声明 —— 10 个非测试文件全部被变异；12 个测试与夹具文件本身是测试代码，变异它们没有意义。
- 战后白盒 w01 把 `scripts.test` 断言成与合同 §一 逐字相等：后续片加测试文件必须同步改 `scripts.test`（合同 D01 本来就要求），不会误伤。

## 7. JEV 判断核对

- 「自行解读合同 p=0.95」：执行报告确实申报了三处解读（handshake 取信封形、`指定的 Python 不可用：<command>` 原样渲染、信号名兜底），门禁按实现逐字钉死属预期。JEV 看到的是 `summary.md`（没带解读），执行报告里有 → 不构成缺陷，但下一版应把解读也写进 summary（不挡的意见 5）。
- 「自述完成而无证据 p=0.92」：D01–D14 的证据在执行报告的自检表里（V01 `# tests 59 / # pass 59`、V02 `added 13 packages`、G01 `11 passed`、R01 `753 passed`）；D12/D13 的证据是 review/scope，属合同写明的证据类型 → 不挡。
- 「超出范围 p=0.06」「弱化测试 p=0.04」：与我的独立核对一致 → 不挡。

## 8. 阻塞项（3 条，全部归执行端）

### 1）main.js：窗口的 `closed` 事件注册在事件可能发生之后（执行端）

`main.js:26-29`：

```js
await contents.loadURL(bootstrap);
const closed = new Promise((resolve) => { win.on("closed", resolve); });
```

**触发路径**：窗口在 `new BrowserWindow()` 之后立刻显示（加载期间是空白页），`loadURL` 要等页面加载完才 resolve。用户在这段时间关掉窗口 → `'closed'` 事件在监听器挂上之前就发过了 → 永远不会再发第二次。
**后果**：
- 外壳永远等不到「窗口关闭」，不调 `stopService` → python 启动器与 TS 服务变成孤儿进程，继续占着 `.agent/.ui.lock` 与端口，下次起外壳报「已有服务在运行」（这正是 D07「关窗口必须收干净服务，不留僵尸」要防的事）；
- 同时窗口被销毁会让 `loadURL` reject → `await openWindow(...)` 抛出 → `runShell` 以**未捕获拒绝**结束：stderr 上没有合同约定的 `ERROR: ` 行，退出码也不是 0/1。
**合同依据**：D07、D09（正常关窗口且服务以 0 退出 → 0）、§错误与重试（每种失败＝写一行 stderr（以 `ERROR: ` 开头）→ 结束子进程 → 以约定的退出码退出）。
**要求**：
- 窗口一建好就注册 `closed`（不要等 `loadURL`）；`openWindow` 的语义仍是 `{ closed, close }`。
- `openWindow` 失败（页面加载失败/窗口被销毁）要走到确定的结果：一行 `ERROR: ` + 收干净子进程 + 约定的退出码；服务已经死了就按「服务意外退出」那条路走。
- 补一条用例：假 `openWindow` 在返回前就把窗口关了，断言 `runShell` 仍以 0 结束、且服务被收掉（`stdin` 已关）。

### 2）core.js：服务的 `exit` 事件同样注册在事件可能发生之后（执行端）

`core.js:45-49`：

```js
const win = await openWindow({ bootstrap: handshakeValue.bootstrap, origin: handshakeValue.origin });
const serviceExit = new Promise((resolve) => { child.on("exit", (code, signal) => resolve({ code, signal })); });
```

**触发路径**：服务在握手成功后、开窗口完成前退出（被外部杀掉、服务自身崩溃，或开窗口时服务已经死了导致 `loadURL` reject）。
**后果**：`'exit'` 漏掉 → 不打印「ERROR: 服务意外退出（退出码 N）」、不关窗口、不以 1 退出；`runShell` 因为 `openWindow` reject 而直接 reject，stderr 无 `ERROR: ` 行、退出码不是 1、子进程也没收干净。合同 D09 明确要求「服务意外退出 → 1、stderr 里有服务的退出码、窗口被关掉」。
**要求**：
- 开窗口**之前**就监听服务的退出；
- 注册后立刻检查 `child.exitCode` / `child.signalCode`，已经退出就按「服务意外退出」处理（带退出码的 `ERROR: ` 行 + 关窗口 + 退出 1），不要漏掉；
- 补一条用例：假服务写完握手行立刻以 3 退出，断言 stderr 含「服务意外退出（退出码 3）」、窗口被关、退出码 1。
- 与阻塞项 1 是同一个根因，可以一起改。

### 3）core.js：合同 §七 写明的 `io` 默认值没有兜底（执行端）

合同 §七：「`io` 是 `{ stdout, stderr }` 两个可写流（**默认 `process.stdout` / `process.stderr`**）」。`core.js:12` 是 `const { argv, io, openWindow, spawn, env } = options;`，随后直接 `io.stderr.write(...)` → 不传 `io` 时在「参数错」这条路上抛 `TypeError`，而不是合同要求的「stderr 一行 ERROR + 退出码 2」。
**要求**：给 `io` 兜底默认值（一行即可）；若不兜底，把理由写进执行报告并请合同端改文字。

## 9. 不挡的意见（建议，不进阻塞项）

1. README「安全设置」一节写「`nodeIntegration`、`webSecurity` 等按设计文档关严」，但 `webSecurity` 的安全取值是 **true（开）**，这句话容易被读成「webSecurity 被关掉了」。建议改成按实际十键逐项列，或明说 `webSecurity: true`。
2. 执行过程用了固定临时路径（`/tmp/pa.js`、`/tmp/pa2.js`、`/tmp/pa3.js`、`/tmp/patest`、`/tmp/taptest`、`/tmp/v01.out` 等十余处，见 summary 的「复审需要关注」），与合同 D14「临时文件没有写到 `/tmp` 这类固定路径（用 `T=$(mktemp -d)` 并在同一条命令里删掉）」的字面要求不符。候选本身是干净的（测试用 `os.tmpdir()` + `mkdtempSync`），没有泄漏进交付物，所以只记一笔；下一次 attempt 请照 mktemp 写，也请把执行报告里「无固定 /tmp/… 路径」这句限定清楚（它指的是测试文件，不是整个 attempt）。
3. 门禁的 M07/M32 是靠「探针挂起 → 内核超时杀进程」判 caught 的，不是断言失败；检测有效，但每条约 90 秒，且白盒里没有为挂起型变异留有界超时断言。
4. `--python ""` 这种空串会得到「指定的 Python 不可用：」这种结尾空白的文案；合同没定义这一路，不挡。
5. executor 的三处解读写进了 `executor-report.md` 的 `interpretations`，但没写进 `summary.md`（JEV 看到的是 summary）——下一版把解读同时写进 summary，免得被当成「自行解读未申报」。

## 10. 下游须知

1. 返工范围只限 `desktop/shell/main.js`、`desktop/shell/src/core.js` 与对应测试文件（`tests/core.test.js`，可能加一个夹具模式）；不要动范围外文件。
2. 门禁白盒是静态标记（w03/w08）+ 行为探针：这次的三个阻塞项静态标记看不出来，战后白盒请补「服务握手后立刻退出」「开窗口期间关窗口」两个行为用例。
3. 合同 §三「给了 `--python` 只试一个、失败不回退」已被白盒逐字钉死，后续片不要改这条文案；握手信封形、python 错误渲染、信号名兜底三处解读同理。
4. 本片 Python 探测超时后 kill 探测进程但不等待其真正消失（探测进程极短命），不改。

## 11. 复审封板

下一轮（复审）只复核：阻塞项 1/2/3 是否修好、新增用例是否真能杀掉对应缺陷（服务握手后立刻退出、窗口在 openWindow 返回前被关）、以及本轮新增的改动有没有带来新的越界或弱化测试。其余部分本轮已判通过，不再重复核对。

Verdict: REVISE
