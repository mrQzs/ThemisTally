# 复审记录：t028-desktop-shell-pages attempt-001（七端信箱 hub）

- 合同：t028-desktop-shell-pages.v1（base b9d002f52cfbec6302b8e0b57a967739da3cde42）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261112T172251399771Z-3281），终审报告如下

## 终审报告

# T028-7 终审报告（audit-sonnet）

## 一、结论

**返工，退回执行端。** 候选的实现面（三个模块）基本忠实于合同，范围干净，门禁与内核检查全绿；但有 3 处合同偏离必须改（1 处实现、2 处合同 Step 5 点名而没写的测试）。三处都很小，改完复审即可封板。

## 二、我做了什么（只读，没改任何文件）

- 逐行读了候选源码：`desktop/shell/src/settings.js`、`src/detect.js`、`src/shellapi.js`（共约 750 行）。
- 逐个看了四个新测试文件的用例名与关键断言：`tests/settings.test.js`、`detect.test.js`、`shellapi.test.js`、`shellshape.test.js`，以及 `tests/fixtures/` 下 8 个子进程替身。
- 对照合同 `.agent/plans/t028-desktop-shell-pages.v1.md` 的 Behavior contract、Steps 1–8、DoD D01–D10 一条条核。
- 核了内核自己跑的检查记录（`checks/01/checks.json` 与四份日志），不是执行端的自述。
- 核了战后门禁的白盒报告、30 条变异记录（`mutations.json`）与逐条日志，并逐条裁定门禁端标「预期抓不住」的四条。
- 核了范围（`scope.json`、补丁 stat、README/package.json 的 diff）与执行报告的 DoD 自述，和内核摘要里的线索对账。

## 三、候选源码逐条核对（与合同对照）

### settings.js（对照合同「模块与接口·settings.js」）

- `DEFAULT_SETTINGS` 八个键与值逐字照合同；`SETTINGS_FILE_KEYS` 顺序一致；`THEME_VALUES`/`DENSITY_VALUES`/`PATCH_KEYS` 一致。
- `createSettingsStore({dir, now})`：`filePath` 是 `<dir>/settings.json`；`load()` 文件不存在回缺省深拷贝 + `badCopy:null`；坏 JSON、顶层非对象、任一已知键取值非法 → 缺省 + 原始字节副本 `settings.bad-<YYYYMMDDTHHMMSSmmmZ>.json`，同名依次 `-2`/`-3`（`badCopyPath` 用 existsSync 循环，不覆盖）✓。未知键在 `copySettings` 里被丢掉 ✓。`save()` 按键序拼对象 → `JSON.stringify(obj,null,2)+"\n"` → `mkdirSync(recursive)` → 写 `<filePath>.tmp` → `renameSync` 覆盖；失败时 `unlinkSync` 临时文件（忽略删除失败）后抛错，正式文件不动 ✓。写盘只用合同允许的四个写函数 ✓（`grep` 确认 `src/**` 里只有 settings.js 出现写函数）。
- `normalizeSettings`：`ok:true/ok:false`，非法即 false、不产副本 ✓；缺键按缺省补齐（执行端 interpretation #5，合同未定义缺键，可接受）。
- `applyPatch`：校验顺序形状/未知键 → id 存在性 → 当前仓库，三类原因 `bad-patch`/`unknown-id`/`current-repo` 全对；拒绝与成功都不改入参 ✓。
- `addRepo`/`addTranscriptDir`：`path.resolve` 后 Windows 转小写去重；reused 沿用原 id、条目不增；id 基名 `name`/`dir`，撞了 `-2`/`-3`；`name` 去尾斜杠、空则 `repo`；**只有 `currentRepo === null` 时新条目才成为当前仓库** ✓。

### detect.js

- `PYTHON_INFO_CODE` 逐字照合同；`KIT_VERSION_RE = /\d+\.\d+\.\d+/` ✓。
- `runProcess`：`spawn(command, args, {stdio:["ignore","pipe","pipe"], shell:false, windowsHide:true})`，超时 kill 回 `{code:null, stdout, stderr, timedOut:true}`，起不来回 `{code:null, stdout:"", stderr:"", timedOut:false, error:<码>}` ✓，没有 `shell:true`。
- `checkRepo`：只看文件系统，`.git` 目录或文件都算，`.agent` 必须是目录，路径不存在按 `not-git` ✓。
- `probeKit`：无 pythonPath → `python-unusable` 且不起子进程；`[pythonPath, <kit>/scripts/pi_dispatch.py, --version]`；stdout+stderr 合起来取第一个 `x.y.z` ✓。
- `detectPython`：从 `./python.js` 只读引用 `DEFAULT_PYTHON_CANDIDATES`，首胜即停 ✓（`python.js` 未改）。
- `detectKit`：kitPath 优先 external、否则 repo；`path` 是被验证的 `pi_dispatch.py` ✓。
- **偏离**：合同写的是 `probePython(commandArgs, {timeoutMs = 10000, code = PYTHON_INFO_CODE})`，实现只读 `timeoutMs`，`code` 被写死成 `PYTHON_INFO_CODE`（`detect.js:105`）。见阻塞项 1。

### shellapi.js

- 返回对象恰好十个成员，名字与 `themisShell.ts` 的 `interface ThemisShell` 一致 ✓。
- 信封 `{ok:true,value}` / `{ok:false,reason}`，主进程侧不抛错 ✓。
- `getState`：`settings` 只五个字段（`pythonPath`/`kitPath` 不进 state）✓；`currentRepoCheck` 每次重算（不缓存）✓；`python` 自定义→`source:"custom"`、空→`detectPython()`→`source:"auto"` ✓；`kit` external/repo 两路，失败 `status:"missing"`、path/version 空 ✓；`service` 恒 `{kind:"idle"}` ✓。
- 四个选择器：取消/保存/被拒三态齐全；只有保存写盘（测试里按字节比对）；`pickRepo` 只在 `currentRepo` 为空时设当前；`pickPython`/`pickKit` 的 saved 没有 `id`；`pickKit` 没有可用 Python → `python-unusable`；`pickTranscriptDir` 不回 rejected ✓。
- `saveSettings`：不合格 → `{ok:false, reason}`，状态与文件都不变；写盘失败 → `write-failed` 且内存回滚（`persist()` 只在 save 成功后才更新 `settings`）✓。
- `openExternal`：复用 `hostcheck.js` 的 `isExternalUrl`（该函数的 `EXTERNAL_URL_RE = /^https?:\/\/[^\s]+$/i` 已排除首尾空白与控制字符）→ `bad-url`；确认框回假 → `cancelled`，抛错 → `internal`；打开抛错 → `open-failed`；成功 → `{ok:true, value:null}` ✓。
- `startService`/`restartService` → `not-implemented`；`on()` 同步返回空退订函数、不抛错、不调 listener ✓。
- 缓存：`pickPython`/`pickKit`/`saveSettings` 成功后清（实现放在入口，取消这一支也清），`getState` 不重复起子进程 ✓。

### 范围与门禁字样

`scope.json` 显示改动 17 个文件（A15/M2），与合同允许集合一致；`desktop/web`、`ts/`、`scripts/`、门禁测试、`main.js`、`preload.js` 与冻结的 `src/*.js` 未动 ✓。`grep` 确认 `src/**` 与 `main.js` 里没有 `fetch(`、`shell: true`、`persist:`、`dialog`、`shell.openExternal`、`showItemInFolder`、`Notification`（`host.js` 里原有的 `showNotification` 是既有文件，正则按词边界不命中）✓。`package.json` 只改了 `scripts.test`，`devDependencies` 仍是 `{electron:"44.9.0"}`，`package-lock.json` 未动 ✓。

### README

新增「设置与校验」一节：设置文件位置与字段、坏文件副本不覆盖、三项判据、10 秒时限与不经 shell、不存凭据与控制令牌、选择器三态 ✓；合同点名要保留的字样（`npm ci`、`npm start`、`--repo`、`--kit`、`--assets`、退出码表、`install.js`、`node_modules/electron`、冒烟、10 秒、30 秒）都在（内核 G01/V02 门禁也逐条核过）。引言里「也没有设置存盘与 `openSettings()`」改成指向新一节——这是**已披露**的一处文档一致性修正，不在合同点名保留的字样表里，不算越界。

## 四、阻塞项（3 条，全部归执行端）

1. **`probePython` 静默忽略合同写明的 `code` 选项**（`src/detect.js`）。合同 Behavior contract 明写 `probePython(commandArgs, {timeoutMs = 10000, code = PYTHON_INFO_CODE})`，实现把 code 写死（`const full = [...commandArgs, "-c", PYTHON_INFO_CODE];`）。触发路径：调用方按合同传 `{code: "print(1)"}` 想换探测脚本，实际仍跑 `PYTHON_INFO_CODE`，探测结果与预期不符且无任何提示——这个选项本来就是为注入而设的。修法：读 `options.code`，缺省仍是 `PYTHON_INFO_CODE`，`-c` 后面传它；补一条断言自定义 code 到达 argv 的测试；默认路径不许变（门禁探针断言 `args[1] === PYTHON_INFO_CODE`，仍要过）。执行报告的 6 条 interpretations 里没有这一条，属于未披露的偏离。
2. **`shellapi.test.js` 里一条 `openExternal` 用例都没有**。合同 Step 5 点名「`shellapi.test.js` 覆盖：…`openExternal` 的三种原因」，但候选的测试文件里 `openExternal` 只出现在 harness 的注入钩子（`confirmExternal`/`openExternal`）、另一个 harness 和「十个成员」的名字清单里，**从来没有调用过 `api.openExternal(...)`**；harness 里的 `confirm.calls`/`opener.calls` 也没被断言。后果：D06 的证据写的是 V01，而 V01（`npm test`）现在对 openExternal 一条也证明不了（行为本身是对的，门禁探针 `test_p06_probe_openexternal` 覆盖了它，但合同要求执行端自己的回归套件里有）。补测试：非 http/https、带控制字符、带首尾空白 → `bad-url` 且不进确认框；确认框回假 → `cancelled`；确认框抛错 → `internal`；`openExternal` 抛错 → `open-failed`；成功 → `{ok:true, value:null}`。
3. **`saveSettings({resetKit: true})` 之后清缓存没有断言**。合同 Step 5 点名「检测缓存在选择与**两个 reset** 之后刷新」，候选只测了 `pickPython`、`pickKit` 与 `saveSettings(resetPython)`（`shellapi.test.js:392`），`resetKit` 这条在执行端套件与门禁探针里都没有断言；实现是对的（`saveSettings` 成功后无条件 `dropCache()`），但仓库里没有钉住它。补一条断言即可。

## 五、不挡的意见（写进 report，不进阻塞项）

- `runProcess` 监听的是子进程的 `exit` 而不是 `close`：Node 文档说 `exit` 可能早于 stdio 流关闭，极端情况下 `stdout` 可能只收到一部分，`probePython` 会误判 `bad-output`（把好 Python 说成不可用）。触发路径具体但概率很低（探测脚本只打印两行），改法是改听 `close`（一个词的改动）。由站主定。
- `createShellApi` 的 `now` 选项接受但不用（执行端 interpretation #1 已披露）：合同没写它在 createShellApi 里干什么（`lastOpened` 合同钉死为 null、坏副本时刻出自 store 的 `now`），属合同未定义处的合理解读。若 T028b 以后要出时间戳，位置在 `createSettingsStore` 的 `now`。
- `detectKit` 返回的 `path` 是 `path.join(kitDir, "scripts", "pi_dispatch.py")`，`kitDir` 若是相对路径就不是绝对路径；实际来源是系统选择框（绝对路径），无碍。

## 六、门禁端标「这条命令预期抓不住」的四条变异：逐条裁定

我逐条读了 `mutations.json` 与对应日志，结论是**四条划分都成立**，不需要退回战后门禁：

| 变异 | 改动 | 标漏的那条 | 实际抓住的那条 | 裁定 |
|---|---|---|---|---|
| M07 `settings-tmp-suffix` | `TMP_SUFFIX` `.tmp`→`.tmpx` | W（白盒） | **B**：基线探针 `t028-settings` 的「临时路径就是 settings.json.tmp」断言失败（M07-B.log：✖ 写临时文件失败…临时路径就是 settings.json.tmp） | 成立：`.tmp` 是合同钉死的名字，B 的门禁文件留在仓库里当回归，钉得住 |
| M23 `api-save-dropcache` | `saveSettings` 里删掉 `dropCache()` | W | **B**：基线探针 `t028-api` 的「缓存：…saveSettings(resetPython) 之后要重新探测」断言 `2 !== 3`（M23-B.log） | 成立：清缓存是合同要求，B 探针按行为断言 |
| M28 `readme-section-title` | `## 设置与校验`→`## 设置与存档` | B（基准） | **W**：白盒按 `^##\s*设置与校验\s*$` 取节，取不到即断言失败（M28-W.log：README 缺「## 设置与校验」一节） | 成立：B 的 needle 因引言里也出现「设置与校验」而仍命中，弱点由 W 的按节取补上（建议见第八节） |
| M29 `readme-section-10s` | 节内「10 秒」→「9 秒」 | B | **W**：白盒在节内找 `10\s*(秒|s|S)`，找不到即断言失败（M29-W.log） | 成立：README 别处也有 10 秒字样，B 的全局 needle 抓不到，W 按节取抓到了 |

每条至少被一条命令抓住，且漏掉的那条确实测不到（不是门禁端偷懒），变异后文件逐字节恢复。门禁端报告的「30/30 OK、意外漏掉 0」与日志一致。

## 七、DoD → 测试 → 断言 映射表

| DoD | 由哪条测试的哪个断言证明 |
|---|---|
| D01 设置存盘 | `settings.test.js`：「文件不存在 → 缺省深拷贝、badCopy null」「坏文件（坏 JSON/顶层数组/顶层字符串/顶层数字/theme 非法/version 不是 1/repos 不是数组/repos 条目缺字段/currentRepo 类型不对/pythonPath 类型不对）→ 缺省 + 原始字节副本」「副本名带 UTC 时刻 YYYYMMDDTHHMMSSmmmZ」「副本同名不覆盖，依次 -2、-3」「未知键忽略、写盘后消失」「save：内容是 JSON.stringify(obj,null,2)+换行、键序照 SETTINGS_FILE_KEYS、只保留这些键」「原子写——先写 `<filePath>.tmp` 再换名覆盖」（用 `fs.renameSync` 探针断言来源是 `${filePath}.tmp`）「写临时文件失败 → 抛错且原文件不动」「换名失败 → 抛错且临时文件被清掉」；门禁侧 `test_p01_probe_settings` 同口径 |
| D02 六键与三类拒绝 | `settings.test.js`「applyPatch 拒绝：…」六条 +「校验顺序：形状 → id 存在性 → 当前仓库」+「saveSettings 的六类拒绝：文件字节不变（经 store 走一遍）」；`shellapi.test.js`「saveSettings：垃圾输入与各类拒绝都回信封、文件字节与内存状态都不变」「saveSettings：校验顺序 bad-patch → unknown-id → current-repo」；门禁 `test_p02_probe_patch` |
| D03 三项校验与自动检测 | `detect.test.js`：checkRepo 四条（.git 目录 ok / .git 是文件 ok / 缺 .git 与路径不存在 not-git / 缺 .agent 或 .agent 是文件 no-agent）、probePython 四条（两行 ok / 一行与空 bad-output / 非 0 version-too-old / 超时 timeout / 起不来 no-command）、probeKit 五条（stdout 取版本 / 只在 stderr 也认 / 没有版本号 kit-unusable / --version 跑不通与脚本缺失 / 没有 pythonPath）、detectPython 两条（按 python3→python→py -3 首胜即停 / 全失败 missing）、detectKit 四条（kitPath 优先 external / repo 来源 / 失败 missing / 两处都空不起子进程）、「runProcess：…（不经 shell）」断言 `opts.shell===false`、`opts.windowsHide===true`、`opts.stdio===["ignore","pipe","pipe"]`、元字符原样到达、「子进程时限默认 10 秒」；门禁 `test_p03_probe_detect` |
| D04 四个选择器三态 | `shellapi.test.js`：pickRepo 四条（取消/不是 Git 仓库 rejected(not-git)/没有 .agent rejected(no-agent)/合法仓库 saved+写盘+currentRepo 为空时设当前；currentRepo 已有时不换、同一路径沿用原 id）、pickPython 三条、pickKit 四条（含「没有可用 Python → rejected(python-unusable)，不写盘」）、pickTranscriptDir 一条（取消不写盘 + saved 时 id 为 `dir`/`dir-2`、同路径沿用 id 不重复、条目数不增）、「写盘失败 → write-failed、内存状态回滚（pickRepo 与 saveSettings 都不抛错）」；门禁 `test_p04_probe_shellapi` |
| D05 形状逐字段一致 | `shellshape.test.js` 五条：解析 themisShell.ts 后逐项比 `ThemisShell` 十个成员、`PATCH_KEYS` vs `SettingsPatch`、`THEME_VALUES`/`DENSITY_VALUES` vs 类型文件里的字面量、`SETTINGS_FILE_KEYS` 含 `ShellSettings` 全字段、`getState()` 各层键（app/settings/repos[0]/transcriptDirs[0]/python/kit）、`service.kind ∈ ServiceState`、`currentRepoCheck ∈ RepoCheck ∪ {null}`、被拒的 `problem ∈ PickProblem`；解析不到块即断言失败，测试里没有第二份键表；门禁 `test_p05_probe_shape` |
| D06 openExternal | **只能人工审阅 + 门禁探针**：合同指定证据是 V01，但候选的 `shellapi.test.js` 没有 openExternal 用例（见阻塞项 2）；`tests/test_gate_t028_baseline.py::test_p06_probe_openexternal` 覆盖三种失败原因（内核 G01 12 passed），白盒也覆盖取消/放行 |
| D07 回归全过 | 内核自己跑的检查：V01 `npm test` 248 pass / # fail 0（exit 0）、V02 `25 passed`、G01 `12 passed`、R01 `777 passed`；既有测试一条没删没改（scope 只列两个改动文件与允许的新增文件） |
| D08 范围 | `scope.json`：17 个文件全在允许集合内，越界 0；`desktop/web`、`ts/`、`scripts/`、门禁测试、`main.js`、`preload.js`、冻结的 `src/*.js` 未动 |
| D09 README 与 package.json | README 新增「设置与校验」一节、合同点名字样全在（内核 G01 的 `test_s05_readme` 与 V02 的 T025/T026 README 断言全过）；`package.json` 只改 `scripts.test`，依赖与锁文件未动 |
| D10 过渡断言未推翻 | `desktop/web/**` 未改；T028 门禁的 `test_transitional_s04_electron_and_ipc_scan` 在候选上通过（G01 12 passed） |

## 八、执行自述与内核摘要的线索对账

- 内核摘要的「可疑命令：`rm -rf desktop/shell/.scratch`」：是执行端在自己工作目录里清自己的草稿目录，不在仓库外、不是固定 `/tmp` 路径；候选补丁（17 个文件）里没有任何残留，`scope.json` 与 D08 的自述对得上，不构成不实自述。
- 「新增被 Git 忽略的路径：`.pytest_cache/`、`desktop/web/node_modules/`、`ts/node_modules/` 等」：依赖与缓存目录，非候选内容 ✓。
- 「`desktop/shell/package.json` 依赖清单变更」的警告：diff 显示只改了 `scripts.test` 一行，`devDependencies` 与 `package-lock.json` 未动——是启发式误报，非缺陷 ✓。
- 「退出码被管道掩盖」：内核自己的四条检查是直接 spawn 记退出码，不带管道，不受影响 ✓。
- 执行报告的 6 条 interpretations 逐条核对：与合同一致或属合同未定义处的合理解读；`contract_conflicts` 为空、`unresolved_questions` 为空，与内核摘要「执行过程中提到 2 处歧义」不矛盾（那两处都落在报告列出的 interpretations 里）。唯一未披露的偏离是上面阻塞项 1。

## 九、给下游的提醒

- 执行端：只改上面三条，其余一字不动（别顺手"优化"）；改完重跑 V01/V02/G01/R01。
- 门禁端：基线门禁 README 的 needle「设置与校验」现在会被引言里那句「（见下文「设置与校验」）」命中，节标题其实只有白盒按 `^##\s*设置与校验\s*$` 取节才钉得住（M28 变异就是这件事）。建议把该 needle 收成按节取，属改进不是缺陷，本回合不退回门禁端。
- T028b：`pickRepo` 之后 Python/kit 的检测缓存不刷新（合同枚举的清缓存时机只有 pickPython/pickKit/saveSettings）；要 pickRepo 后立即重探 kit，写进新合同。`createShellApi` 的 `now` 合同没定用途，别依赖它出时间戳。
- 门禁端本回合新增的 `tests/test_gate_t028_whitebox.py` 留在仓库里当回归，是本片最有效的行为网（30 条变异里它抓住 28 条），别删。

Verdict: REVISE
