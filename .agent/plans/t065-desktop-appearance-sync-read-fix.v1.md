# TASK: t065-desktop-appearance-sync-read-fix

<!-- T065：主进程三个同步外观读取处理函数改成「每条路径恰好给 event.returnValue 赋一次」，
     页面首帧读到真实外观（原先恒为 null）。本片只改赋值的写法，T061 的其他行为一律不动。 -->

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 2fe5d38d261813248f690c599faa9a374798e16b
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
`desktop/shell/main.js` 的三个同步外观读取处理函数（外壳分支的宿主读取、外壳读取，以及带参数起服务分支那一处）改成每条路径**恰好给 `event.returnValue` 赋一次**：来源被认时答主进程当前的 `currentAppearance`，来源不认或读出错时答 `null`；于是服务窗口、外壳页窗口、设置窗口调 `getAppearance()` 时，首帧拿到的就是真实外观（不再恒为 `null`）。旧门禁 `tests/test_gate_t061_baseline.py` 的 S07 与 `desktop/shell/README.md:210` 的说法同步改成新形状。

## Non-goals
- 不改 T061 的其他行为：saveTheme 信封、三个窗口的外观广播、退订、窗口背景色、缺省暗与标准密度、`currentAppearance` 的持有与更新时机。
- 不碰 `desktop/web/**`（前端 T063）、不碰多仓库/托盘/单实例/打包（T064）、不碰 `registerHostIpc(`、`createHost(`、`new BrowserWindow`、`.protocol.handle(`、`guardedWindow(`、`flow.subscribe` 回调、`onAppearanceChange` 回调。
- 不新增文件、不加 `main.js` 的单测、不抽 helper：站主已定单测选 **a（不加单测）**，证据是改过的 S07 静态断言 + 站主的真窗口冒烟。
- 不改 `desktop/shell/package.json` 与锁文件，不新增或升级依赖。
- 不改 `desktop/shell/tests/**` 与 `src/**`；不动 `tests/` 下除 `tests/test_gate_t061_baseline.py` 以外的任何文件。
- 不退役任何过渡断言：`tests/test_gate_t012_baseline.py`、`tests/test_gate_t032_baseline.py` 的 `UNTOUCHED_REL`、前端过渡用例都不受影响。

## Repository facts
- 入口：
  - `desktop/shell/main.js` 的三处同步外观读取（按本基线行号：外壳分支宿主读取 `:86-95`、外壳分支外壳读取 `:98-110`、带参数起服务分支那一处 `:392-400`；**T064 并行改 `main.js` 会让行号漂移，按内容定位、不按行号钉**）；
  - `tests/test_gate_t061_baseline.py` 的 `test_s07_main_sync_reads`（`:443-484`）；
  - `desktop/shell/README.md:210`（外观段里讲同步读取的那一句）。
- 调用关系与现有约定：
  - 三处处理函数现在都内联写在 `ipcMain.on(...)` 的调用里（**不许抽成命名函数再传名字**，这是 T061 S07 的前提），形状都是：先 `event.returnValue = null;` → `try` 里来源被认时 `event.returnValue = currentAppearance;` → `catch` 里 `event.returnValue = null;`。Electron 的 `returnValue` 第一次赋值就是回复，所以页面恒读到 `null`。
  - 通道与注册位置不变：`ipcMain.on` 恰好三处；外壳分支两处（`HOST_APPEARANCE_CHANNEL` 认 `serviceWindow.webContents`；`SHELL_APPEARANCE_CHANNEL` 认 `shellWin`/`settingsWin` 的 `webContents`，窗口为 `null` 或已销毁一律不认），带参数起服务分支一处（`HOST_APPEARANCE_CHANNEL`，恒答 `null`）。来源判断的条件逐字不变。
  - 门禁扫描口径（**注释也算**，改动注释前必须知道）：
    - `tests/test_gate_t026_baseline.py:296-305` 与 `tests/test_gate_t030_baseline.py:349-360`：用 `ipcMain\s*\.\s*on\s*\(` 扫 `main.js` **原文**（不剥注释），把括号里第一个实参当通道核对 → `main.js` 的注释里**不许出现 `ipcMain.on(`**。
    - `tests/test_gate_t026_baseline.py:112-120`（`SRC_FORBIDDEN`）：`main.js` 与 `src/**` 原文里不许出现 T025 的 7 条禁令——`persist:`、`shell: true`、fs 写函数带括号（`writeFile(`/`writeFileSync(`/`appendFile(`/`appendFileSync(`/`mkdir(`/`mkdirSync(`/`rm(`/`rmSync(`/`unlink(`/`unlinkSync(`/`rename(`/`renameSync(`）、`fetch(`、`net.request`、`autoUpdater`、`crashReporter`。注释里同样不许出现。
  - T061 门禁 S07 的分段：`:450-459`（三处、通道白名单、宿主两处外壳一处）、`:460-464`（本片要改的三条：每个处理函数 `event.returnValue = null` 至少两处、catch 里也设、先设缺省再 try/catch）、`:465-475`（`RETURN_VALUE_NON_NULL_RE` 把「外壳两处答外观对象」与「带参数一处恒答 null」分开、外壳两处含 `isDestroyed`）、`:476-484`（`desktop/shell` 下除 `main.js` 外任何 `.js` 一处 `ipcMain.on` 都不许有）。同一文件里可复用的辅助函数：`_ipc_main_on_calls`（配平扫描取三处调用文本与首参）、`_match_bracket`、`_block_span`、`_strip_js_comments`（把注释换成等长空格）。
  - `RETURN_VALUE_NON_NULL_RE = event\s*\.\s*returnValue\s*=(?!\s*null\b)`（`:153`）：新写法下外壳两处 `= answer` 命中 answering、带参数那处 `= null` 命中 always_null，`:465-475` 照旧成立（**不动**）。
  - `desktop/shell/README.md:210` 现有句子：「……处理函数每条路径都设过 `event.returnValue`——来源不认、没有可读的外观、读出错一律回 `null`（发到没有监听的通道渲染进程会卡住，所以主进程必须保证有监听就一定答）。」。没有门禁钉这一句的措辞（`tests/` 里 grep「每条路径都设过」无命中）；T061 的 `test_s10_readme_appearance`（`:569-580`）只钉五个通道字面量、若干 needle 与 `theme`/`density`，不钉这一句。
- 工具链与锁文件：`desktop/shell/package.json:12` 锁 `electron: 44.9.0`；`scripts.test` = `node --test --test-reporter=tap <22 个 tests/*.test.js 逐字点名>`，tap 报告输出含 `# pass N` / `# fail N`；`desktop/shell` 无运行时依赖，不需要安装。
- 仓库外事实（站主 2026-11-19 在 Electron 44.9.0 上实测，合同按事实写）：`ipcMain.on` 处理函数的 `event.returnValue` 是 setter——**第一次赋值就是给渲染进程 `sendSync` 的回复，之后再赋值不抛错、直接被丢掉**；先赋 `null` 再赋外观对象 → 页面拿到 `null`；先赋外观对象再赋 `null` → 页面拿到外观对象；先在局部变量里算好、只赋一次 → 页面拿到外观对象；同一通道两个监听时先注册的赋值赢。站主在冒烟树里照本合同 Steps 2–4 的写法改了那两处，三轮真窗口冒烟 19/19、1/1、4/4 全过。
- 基线检查：核对了 `main.js` 三处处理函数的现状、`tests/test_gate_t061_baseline.py` 的 S07 四段与辅助函数、`tests/test_gate_t026_baseline.py` 与 `tests/test_gate_t030_baseline.py` 的 `ipcMain.on` 扫描口径、`tests/test_gate_t026_baseline.py:112-120` 的 7 条禁令、`desktop/shell/README.md:210` 现有句子与 S10 的 needle、`desktop/shell/package.json` 的 `scripts.test` 清单。整套检查在基线上的结果由内核在执行之前跑过并记入「基线检查记录」，执行端不必再跑一遍。

## Scope
- allowed_modified_files:
  - desktop/shell/main.js
  - desktop/shell/README.md
  - tests/test_gate_t061_baseline.py
- allowed_new_files: 无
- allowed_deleted_files: 无
- forbidden_paths: tests/test_gate_t065_*.py, src/**, desktop/web/**, desktop/shell/tests/**, desktop/shell/package.json, desktop/shell/package-lock.json
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
- 正常输入：
  - **外壳分支的两处处理函数**（宿主读取、外壳读取），函数体固定写成这个次序，局部变量名逐字 `answer`，形参仍叫 `event`：
    1. `let answer = null;`
    2. `try {` —— 来源判断的条件**逐字不变**，条件成立时 `answer = currentAppearance;`
    3. `} catch {` —— `answer = null;`
    4. 最后一句逐字 `event.returnValue = answer;`（**这是处理函数体里的最后一句**）
  - **带参数起服务分支那一处**，函数体**只有** `event.returnValue = null;` 一句，没有 `try`/`catch`；它上方原有的说明注释保留。
  - 每条路径给 `event.returnValue` 恰好赋一次：来源被认 → 答 `currentAppearance`；来源不认（别的窗口、窗口为 `null` 或已销毁）→ 答 `null`；读出错 → 答 `null`。
  - 通道字面量、`ipcMain.on` 的个数（仍恰好三处）、注册位置、来源判断条件一律不变。
- 边界输入：
  - 来源不认 → `answer` 保持缺省 `null` → 页面拿到 `null`。
  - 读设置/窗口状态出错（抛异常）→ `catch` 里 `answer = null` → 页面拿到 `null`。
  - 带参数起服务分支恒答 `null`（那条分支没有设置存储）。
- 错误与重试：处理函数不抛错、不重试；同步读取没有重试机会（发到没有监听的通道渲染进程会卡住），所以「有监听就一定答」这条既有约定照旧成立。
- 并发、取消与状态变化：不适用——本片只改赋值的写法与位置，不改 `currentAppearance` 的持有、更新时机与广播时序；同一通道多个监听时「先注册的赢」是既有行为，不在本片范围。
- 兼容性：
  - **页面可见行为的变化（这就是本片的目的）**：服务窗口、外壳页窗口、设置窗口调 `getAppearance()` 现在拿到 `currentAppearance`，原先恒为 `null`。除此之外页面侧接口、通道字面量、preload 的暴露面一律不动。
  - **取代关系**：`.agent/plans/t061-desktop-appearance-settings.v3.md` 的 `:116` 与 `:181` 规定的「先把 `event.returnValue = null` 再 `try/catch`、每个处理函数里 `event.returnValue = null` 至少出现两处」由本片设计取代；已派遣的 T061 合同不改，只在此处写明取代关系。
  - **本片推翻的旧断言**：`tests/test_gate_t061_baseline.py` 的 `test_s07_main_sync_reads` 里 `:460-464` 那三条（`event.returnValue = null` 至少两处、catch 里也要设、先设缺省再 try/catch）以及相关的说明文字，由本片的新 S07 取代；该文件在允许修改范围内（门禁端只能新增本片自己的基准，不会来改这份旧门禁）。
  - **不受影响的旧门禁**：T025/T026/T028/T030/T033/T035/T060 钉 `main.js` 的断言（接线标记、`new BrowserWindow`/`.protocol.handle(`/`createHost(` 的计数、`guardedWindow(` 五处、`ipcMain.on` 只许 `main.js` 且通道只许那两个读取字面量）、`tests/test_gate_t032_baseline.py` 的 `UNTOUCHED_REL`、`tests/test_gate_t012_baseline.py` 的过渡断言——本片一条都不推翻。
  - `desktop/shell/README.md` 的既有 needle 一条不许丢。

## Steps
1. 读 Repository facts 里列的文件，确认三处处理函数、T061 S07 四段、README:210 的现状与本节一致；不一致就停下并报告（行号漂移不算不一致，按内容定位）。
2. **改 `desktop/shell/main.js` 外壳分支的宿主读取**（`HOST_APPEARANCE_CHANNEL` 那处）：按 Behavior contract 的四步重写函数体——`let answer = null;` → `try` 里来源被认时 `answer = currentAppearance;`（来源判断条件逐字不变）→ `catch` 里 `answer = null;` → 最后一句逐字 `event.returnValue = answer;`。函数体里除这一句外，不许再出现任何 `event.returnValue =`。
3. **改 `desktop/shell/main.js` 外壳分支的外壳读取**（`SHELL_APPEARANCE_CHANNEL` 那处）：与第 2 步同款写法，来源判断仍认 `shellWin` 或 `settingsWin`（条件逐字不变）。
4. **改 `desktop/shell/main.js` 带参数起服务分支那一处**：函数体**只有** `event.returnValue = null;` 一句；原来的 `try`/`catch` 与 `catch` 里那句注释一并去掉，函数上方的说明注释保留（这一处的注释写在函数外面）。
5. **改 `tests/test_gate_t061_baseline.py` 的 S07（只改 `test_s07_main_sync_reads` 里 `:460-464` 那三条断言，`:450-459`、`:465-475`、`:476-484` 一行不许动）**，改成下面三条判定：
   - **每处恰好一次**：三处处理函数的跨度里，`event\s*\.\s*returnValue\s*=(?!=)` 恰好命中一处（用 `_ipc_main_on_calls` 取到的 span 计）。
   - **外壳两处**：这两处的跨度里有 `try` 与 `catch`；那一处赋值的右边是**标识符**（局部变量名），不是字面量 `null`；那一处**锚在处理函数体末尾**（它是函数体的最后一句，后面只剩 `}` 与 `)`）；`catch` 块（用同文件的 `_block_span(span, "catch")` 取）里不出现 `returnValue`。
   - **带参数那一处**：跨度里没有 `try`/`catch`，函数体只有 `event.returnValue = null;` 这一句。
   - 建议实现（等价写法亦可）：先 `_strip_js_comments(span)` 再做形状判定（注释换成等长空格，位置不变）；末尾锚点可用「赋值 → `;` → `}` → `)`」的尾锚匹配；标识符可用 `event\s*\.\s*returnValue\s*=\s*([A-Za-z_$][\w$]*)` 取出后断言它不是 `null`。
   - 判定必须能挡住这四种退化写法（验收端会做变异）：① 先 `event.returnValue = null;` 再覆盖成外观对象；② `catch` 里给 `event.returnValue` 赋值；③ 把赋值挪到 `try` 之前；④ 带参数分支赋两次。
6. **同步 `tests/test_gate_t061_baseline.py` 的说明文字**（只改说明，断言逻辑以外一处不多动）：模块头 `:37-40` 那句「每个处理函数先设 `event.returnValue = null` 再 `try/catch`，每条路径都设过 `returnValue`」与 `:57` 的结构说明「main.js 的同步读取（三处、通道白名单、每条路径都设 returnValue、ipcMain.on 只许 main.js）」，改成「每条路径恰好给 `event.returnValue` 赋一次；外壳两处在局部变量里算好、末尾赋一次；带参数分支那处只有一句 `= null`」；`test_s07_main_sync_reads` 的 docstring（`:445-447`）照同样的意思改写。
7. **改 `desktop/shell/README.md:210`**：把「处理函数每条路径都设过 `event.returnValue`」改成「处理函数每条路径恰好给 `event.returnValue` 赋一次」，并补一句原因：Electron 的 `returnValue` 第一次赋值就是给渲染进程的回复，之后的赋值不会报错、直接被丢掉。该行其余内容保留（三处全在 `main.js`、带参数分支恒答 `null`、来源不认/没有可读的外观/读出错一律回 `null`、为什么必须有监听就答）。
8. **注释与禁词自查**（`desktop/shell/main.js` 原文）：
   - 新注释只许放在 `let answer = null;` 之前，或处理函数的上方；**不许**放在 `event.returnValue = answer;` 与 `});` 之间——新 S07 把那句赋值锚在函数体末尾，中间夹注释会让正确实现变红。
   - 注释里**不许**出现 `ipcMain.on(`（T026/T030/T061 S07 都按原文扫，会把括号里的第一个实参当通道核对），也**不许**出现 T025 的 7 条禁令：`persist:`、`shell: true`、fs 写函数带括号、`fetch(`、`net.request`、`autoUpdater`、`crashReporter`。
   - 注释里也**不许**出现 `event.returnValue =` 这样的字样（新 S07 要数「恰好一处」）；写原因时用「returnValue 第一次赋值就是回复」这类说法。
9. 运行 Validation commands 里与改动相关的检查（V01、V02；R01 全量回归若单次时限内跑不完，在执行报告里写明跑过哪些、剩哪些），记录命令与结果。
10. 写执行报告；遇到合同未定义的行为，停止并报告。报告里没有内容的字段写空数组（例如 `contract_conflicts`、`interpretations`），不要留空字符串或「无」。

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态。变异检查（故意改坏实现）由验收端在固定候选上做，执行端不要自己做。

- V01（必要）：`npm test` · cwd：desktop/shell · 超时：900s · 期望退出码：0 · 输出须匹配：`# pass \d+`，不得出现：`# fail [1-9]`
- V02（必要）：`python -m pytest tests/test_gate_t061_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t065_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py tests/test_gate_t050_baseline.py tests/test_gate_t051_baseline.py tests/test_gate_t052_baseline.py tests/test_gate_t053_baseline.py tests/test_gate_t054_baseline.py tests/test_gate_t055_baseline.py tests/test_gate_t056_baseline.py tests/test_gate_t057_baseline.py tests/test_gate_t058_baseline.py tests/test_gate_t059_baseline.py tests/test_gate_t060_baseline.py tests/test_gate_t061_baseline.py -q` · cwd：仓库根 · 超时：3600s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：`desktop/shell/main.js` 的三处处理函数里，`event.returnValue` 恰好各赋一次——外壳两处先在局部变量 `answer` 里算好、最后一句 `event.returnValue = answer;` 锚在函数体末尾，带参数分支那处只有 `event.returnValue = null;` 一句；来源判断条件、通道、注册位置、`ipcMain.on` 的个数（仍恰好三处）逐字不变；证据：V02、review；目的：Electron 的 `returnValue` 第一次赋值就是回复，多一次赋值页面就永远读到 `null`。
- D02：改过的 T061 S07 在候选上通过，且能挡住四种退化写法（先赋 `null` 再覆盖、`catch` 里赋值、赋值挪到 `try` 之前、带参数分支赋两次）；T061 门禁其余用例（S01–S06、S08–S10 与 P01–P07）照旧全绿；证据：V02、G01；目的：门禁是本片唯一的自动化证据，它必须真的钉住「恰好一次」而不是走过场。
- D03：`desktop/shell/README.md` 的同步读取那一句改成「每条路径恰好给 `event.returnValue` 赋一次」并带上原因（第一次赋值即回复、之后的赋值被丢掉），该行其余内容与 README 的既有 needle 一条不少；证据：V02、R01；目的：下一片照 README 就能对齐写法。
- D04：外壳单测全绿（tap 输出有 `# pass` 且无 `# fail`）；证据：V01；目的：外壳侧既有行为没有被这次改写碰坏。
- D05：全套回归门禁（含 T025/T026/T028/T030/T033/T035/T060 钉 `main.js` 的断言、T032 的 `UNTOUCHED_REL`、T012 的过渡断言）全绿；证据：R01；目的：本次放开的只是赋值写法，别顺手放宽别的禁令。
- D06：本片新门禁 `tests/test_gate_t065_baseline.py` 在候选上通过（该文件由门禁端写，执行端不许碰）；证据：G01；目的：新旧两套门禁一起把「恰好一次」钉住。
- D07：所有修改都在允许集合内（只有 `desktop/shell/main.js`、`desktop/shell/README.md`、`tests/test_gate_t061_baseline.py`），没有新增文件、没有改依赖与锁文件、没有碰 `src/**`、`desktop/web/**`、`desktop/shell/tests/**`、`desktop/shell/package*.json`；证据：scope；目的：本片的边界是三个文件，不越。
- D08：没有删除、跳过或弱化既有测试；被改写的只有 T061 S07 的那三条断言与相关说明文字，且新判定严格于旧判定；证据：review；目的：门禁强度不因修 bug 而悄悄下降。
- D09：页面首帧读到真实外观（服务窗口、外壳页窗口、设置窗口的 `getAppearance()` 拿到 `currentAppearance`）——**这条的运行期证据在仓库外**，由站主落地后跑真窗口冒烟（落地前站主已在冒烟树用同样两处改动跑过三轮：19/19、1/1、4/4）；候选里没有这份证据，验收按「静态门禁 + 站主冒烟」判；证据：review；目的：这是本片要修的现象本身，但它只能靠真窗口证明。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如三处处理函数的现状不是「先赋 null 再 try/catch」、T061 S07 的分段已经不是四段、README:210 不是那一句话）。
- 必须修改允许范围之外的文件才能继续（例如必须改 `desktop/web/**`、`desktop/shell/package.json`、新增测试文件或新增/修改 `tests/test_gate_t065_*.py` 才能过门禁）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限（2700 秒）。

## Budget
- max_attempts_total: 4（按 task-id 汇总，包括返工版本；本版之前已用 0 次）
- max_wall_seconds_per_attempt: 2700
- max_wall_seconds_total: 10800（按 task-id 汇总；本版之前已用 0 秒）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读代码与核对基线形状 6 分钟；改 `main.js` 三处 8 分钟；改 T061 S07 断言与说明文字 15 分钟；改 README 一句 3 分钟；跑 V01/V02 与必要检查 8 分钟；写执行报告 3 分钟；总计约 43 分钟（不超过单轮时限 2700 秒）。若第一次超时，第二次只做定点补齐，不缩范围。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D09，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块；报告里没有内容的字段写空数组（例如 `contract_conflicts`、`interpretations`）。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过（本片唯一被改写的既有断言是 T061 S07 的 `:460-464` 三条，按 Steps 5 写成更严的三条判定）。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不新增文件、不改依赖与锁文件、不碰 `src/**`、`desktop/web/**`、`desktop/shell/tests/**`、`desktop/shell/package*.json`、不碰 `tests/test_gate_t065_*.py`。
- 不在 `desktop/shell/main.js` 的注释里写 `ipcMain.on(` 或 T025 的 7 条禁令；不把注释放在 `event.returnValue = answer;` 与 `});` 之间。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261119T231402888239Z-owner-f3a16e：

> 摘要: 唯一一条仓库外事实成立，放行合同端；同意规划（选 a、只改三个文件），另加两条：执行时限不低于 2700 秒、注释不要放在末尾那句赋值之后
> 提交: 无
> 验证: 站主 11-19 在 Electron 44.9.0 上的探针实测（仓库外），以及冒烟树里的三轮真窗口冒烟
> 偏离: 无
> 需协调人决定: 无
>
> 事实核实（规划第 12 节那一条）：成立。
> - 站主在 Electron 44.9.0 上实测，这个版本与 desktop/shell/package.json:12 一致。页面拿到的值：
>   - 先赋 null、再赋外观对象 → null；
>   - 先赋外观对象、再赋 null → 外观对象；
>   - 先在局部变量里算好、只赋一次 → 外观对象；
>   - 同一通道两个监听，先注册的赋外观对象、后注册的赋 null → 外观对象。
>   四种写法在主进程里的每次赋值都没有抛错。
> - 站主在冒烟树里照规划第 4 节的写法改了外壳分支两处（局部变量 answer，最后一句 event.returnValue = answer;），重跑三轮真窗口冒烟：19/19、1/1、4/4，全过。
>
> 站主决定：
> 1. 同意规划：单测选 a，执行端只改 main.js、README.md、tests/test_gate_t061_baseline.py 三个文件，门禁 S07 照第 7 节第 5、6 步改。
> 2. 合同的 budget.max_wall_seconds_per_attempt 不低于 2700。
>    - T061 合同定的是 1200。它第一次执行改了 25 个文件，输出 10.9 万 token，在 1200 秒处超时，候选建成返工提交后又多跑一轮，前后多花约 40 分钟。
>    - 规划自估本片要 30–45 分钟，1200 秒不够。
> 3. 注释只能放在两个位置：let answer = null; 之前，或处理函数上方。
>    - 不许放在 event.returnValue = answer; 和 }); 之间：新 S07 第 2 条把那句赋值锚在函数体末尾，中间夹一行注释正确实现也会红。
>    - 带参数分支的函数体只留 event.returnValue = null; 这一句，注释照样写在函数外面。
