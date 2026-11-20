# 复审记录：t064-desktop-repo-switch-shell attempt-001（七端信箱 hub）

- 合同：t064-desktop-repo-switch-shell.v1（base 1cd1fbbcf85c823c1dc85b67f295c0eb3cbeaa55）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261120T013819556095Z-ee43），终审报告如下

## 终审报告

# T064-7-audit-post 终审报告（审核端 audit-sonnet）

## 结论

**通过。** 候选实现逐条忠实于合同的 Behavior contract；四个旧门禁只改个数与清单、断言强度只增不减；改动全在 Scope 内、无新增文件；内核三条检查全绿，战后门禁 26 条变异全被抓住。执行报告自述的 4 条 interpretation 我逐条核过，都不违反合同。**无阻塞项。**

审的材料：候选补丁 `candidate.patch`（20 个文件，75604 字节）、`changes.json`、`candidate.stat.txt`、`summary.md`、`executor-report.md`（含末尾 JSON 块）、内核检查记录 `checks/01/{checks.json,V01.log,G01.log,R01.log}`、合同 `.agent/plans/t064-desktop-repo-switch-shell.v1.md`、战后门禁 `T064-6-gate-post/report.md` 与 `evidence/whitebox-*.py`、`evidence/mutate-*/mutations.json`、JEV `T064-6j-jev/report.md`。逐字读过 9 个改动的非测试文件（settings/shellapi/serviceflow/host/hostrelay/ipc/preload/main/README）与 4 份旧门禁的 diff；另外只读核了 `desktop/web/src/shellpages/FirstRunView.tsx`、`firstRunModel.ts`（未改）以验证切换链路的仓库内前提。

本回合只用了只读工具：没有跑命令、没有写文件、没有碰主工作区。

## 1. 实现忠实度：合同 Behavior contract 逐条

| 合同条款 | 实现位置 | 判定 |
|---|---|---|
| `settings.selectRepo(settings,id,at)` 纯函数 | `src/settings.js:299-309`：`typeof id !== "string" || !settings.repos.some(...)` → `unknown-repo`；`copySettings` 复制后只改 `currentRepo` 与目标条目的 `lastOpened = new Date(at).toISOString()`；入参不动 | ✓ |
| `shellapi` 两内部函数经 `onRepoOps` 同步交出、返回对象仍十成员 | `src/shellapi.js:47`（注入项）、`:320-343`（listRepos/selectRepo）、`:345`（`if (onRepoOps !== null) onRepoOps({ listRepos, selectRepo })`）、返回对象未加成员 | ✓ |
| `selectRepo` 次序 bad-args→unknown-repo→current-repo→纯函数→dropCache→persist；`at` 非有限数字兜底 | `src/shellapi.js:330-341` 逐行对上 | ✓ |
| `serviceflow.reset()` 只在 exited 回 idle、`{byShell:false}` 通知、不经 moveTo、全文件无 `afterRunning: false` | `src/serviceflow.js:199-208`；`moveTo` 一字未改；全文件只有 `afterRunning: true` | ✓ |
| `host` 三个新成员与 addRepo 四形状映射 | `src/host.js:197-224`：`listRepos` 只取三键、`switchRepo` 原样回、`addRepo` 四形状 + 不认识回 internal；返回对象旧七项后接三个（`:227-237`） | ✓（多一行透传，见 §3-4） |
| 接线：三条新通道、实参 0/1/0、三张表十项、`HOST_METHODS` 十项、preload 十二成员、注释「十二个函数」 | `src/ipc.js:4-45`、`src/hostrelay.js:7`、`preload.js:7,25-28` | ✓ |
| `main.js` 单实例：函数开头拿锁、拿不到 `app.exit(0); return;`、唯一 `second-instance`、先 restore 再 focus、带参数分支不动 | `main.js:51-68`；带参数分支（`:78-95`）在 diff 里逐字未改 | ✓ |
| `main.js` 切换编排：独立函数、次序固定、存盘过了立刻回 `{ok:true}`、收尾自接错误、开页失败 `ERROR:`+`app.exit(1)` | `main.js:335-365` | ✓ |
| `current`/`current-repo` 用正在跑的服务的仓库 id | `main.js:236-243`：`repoOps.listRepos(repo)`、`switchRepoEntry(id, repo)`，`repo` 是 `onRunning` 的实参 | ✓ |
| `chooseDirectory` 父窗口三级次序；`chooseFile`/`confirmExternal` 不动 | `main.js:384-397`；diff 显示另两处未改 | ✓ |
| 冻结面：外壳 IPC 九条、`shell-preload.js` 十一个、`createShellApi` 十成员、`PATCH_KEYS`/`SETTINGS_FILE_KEYS` | diff 里 `src/shellipc.js`、`shell-preload.js`、`package.json`、`desktop/web/**`、`ts/**` 一字未动 | ✓ |

切换链路的仓库内前提我也核过（只读）：`flow.reset()` 把状态从 exited 拉回 idle，正是 `FirstRunView.tsx:68-73` 里「`exited` 不自动起、`idle` 才自动起」这条规则所要求的；`firstRunModel.ts:77` 的 `repoToStart = state.settings.currentRepo` 在存盘后就是新仓库。合同把这条写成仓库事实，成立。

## 2. DoD 逐条核对

| DoD | 证据 | 判定 |
|---|---|---|
| D01 宿主接口多三函数 | preload 12 成员（逐个数过）、ipc 三表各 10、hostrelay 10、createHost 10 键、三条新通道实参 0/1/0；V01/G01/R01 | ✓ |
| D02 settings.selectRepo 纯函数 | `settings.js:299-309` + `tests/settings.test.js` 新增 3 例（未知/非字符串 id 入参深比较不变、命中只改两处、at=0 → 1970） | ✓ |
| D03 shellapi 两内部函数 | `shellapi.js:345` + `tests/shellapi.test.js` 新增 6 例（交出两函数、返回仍十成员、不带 path、拒绝次序、成功存盘、write-failed 内存不变、at 兜底） | ✓ |
| D04 serviceflow.reset | `serviceflow.js:199-208` + `tests/serviceflow.test.js` 新增 3 例（exited→idle+byShell:false、idle/starting/running 不动不发、reset 后能再 start） | ✓ |
| D05 host 三新成员 | `host.js:197-224` + `tests/host.test.js` 新增 5 例（未注入 unavailable、bad-args 四种不进注入项、四形状映射、结果不带 path/state、只取三键） | ✓ |
| D06 单实例 | `main.js:51-68`；静态部分由战前 S07 与白盒 W01 钉住；**真 Electron 的锁语义与「第二份以 0 退出」只能人工审阅**（README 冒烟第 6 条 + 站主实测事实） | ✓（运行时部分人工） |
| D07 切换次序 | `main.js:335-365`；战前 S09 与白盒 W03 钉住次序与错误处理；**「过程中不出现服务状态页」「任何时刻至少有一个窗口」只能人工审阅**——我按源码推过一遍：订阅回调因 `serviceWindow === null` 与 `info.byShell` 提前返回，旧服务窗口的 `closed` 被既有的 `serviceWindow !== opened` 身份检查挡掉，收尾期间旧服务窗口还开着，不会出现零窗口 | ✓（运行时部分人工） |
| D08 选目录父窗口 | `main.js:384-397` + 白盒 W04 | ✓ |
| D09 README | 逐条对合同 Step 10：第 5 行只留「托盘」、「外壳页在本片就位」留着；宿主接口首句「十二个函数」+三行（各带 reason 词表）；`createHost` 一节「十个函数」；退出码 0 行加「第二份」、1 行加「切换」（1 行仍无「服务意外退出」）；冒烟加第 6、7 两条 | ✓ |
| D10 Scope | `changes.json` 20 个文件全在 `allowed_modified_files`；无新增/删除文件；`package.json`、`package-lock.json`、`desktop/web/**`、`ts/**` 未动 | ✓ |
| D11 不弱化测试 | 见 §3 | ✓ |

## 3. 有没有弱化测试（D11）

四个旧门禁的 diff 我逐处看过：改动只有「个数」与「清单」两类，没有一条用例被删、被 skip 或被改成更松的断言。

- T026：模块常量 `HOST_CHANNELS` 从基线的 5 项补到 10 项（基线实际只有 5 项，合同写「七项」是行数笔误；补 5 项才到合同写明的「十项」目标，是加强不是放松）；preload 探针清单、ipc 探针清单各加三条；两处标题改数字；preload 真跑的键表从九项加到十二项（旧键全在）。
- T035：模块常量与探针 `METHODS` 各到十项；两处标题改数字；**合同 Step 11 没列**的「重入」探针里 `registrations == 7` / `handlers.size == 7` 也改成 10——`registerHostIpc` 现在注册 10 条通道，不改必然红 R01；断言本身（精确等于）没松。
- T060：两个无人引用的模块常量补到十项；S01 的「九个函数」→「十二个函数」（断言消息同步改）；P01 暴露面七键→十键；P02 的 `CHANNELS`/`HOST_METHODS`/preload 键表各加三项；标题里的旧数字一并改准。
- T061：`HOST_METHODS` 十项、`HOST_KEYS_SORTED` 十二项（按 JS 默认排序插入）、`HOST_LIST` 十条、P03 暴露面十键、P04 十项、P05 标题、P06 preload 键表十二项。

执行端 4 条 interpretation 我逐条核过，都不违反合同：

1. T026/T060 模块常量按基线实况补到十项——目标状态明确，只增强。
2. T035 重入计数 7→10——必改项，否则 R01 红；属「只改个数」。
3. T061 `HOST_LIST` 按内容定位——合同行号笔误，行为不变。
4. `host.listRepos` 加 `if (result.ok !== true) return result;`——合同 main.js 一节写明「`repoOps` 为 null 时回 `{ok:false, reason:"unavailable"}`」，若 host 不透传，这一句会变成 ipc 外层的 `internal`，与合同给 listRepos 的词表（unavailable/forbidden）自相矛盾；不加这一行反而是违约。战后门禁 W07 已钉住。

新加的包内用例（7 个文件二十余例）都是打真模块：`settings.test.js` 打纯函数、`shellapi.test.js` 打真 store（读回 `settings.json` 核对 `currentRepo`/`lastOpened`、用假 store 让 save 抛错验内存不变）、`serviceflow.test.js` 用 `tests/fixtures/fake-service.js` 真起子进程、`host.test.js`/`ipc.test.js`/`hostrelay.test.js`/`preload.test.js` 打真模块与 `vm` 真跑 preload。没有把业务逻辑抄进测试，也没有把断言写死到实现文本上。

## 4. 范围与越界

`changes.json` 与 `candidate.stat.txt` 一致：20 个 M、0 新增、0 删除，全在 Scope 的 `allowed_modified_files` 里。`desktop/web/**`、`ts/**`、`src/shellipc.js`、`src/window.js`、`src/detect.js`、`package.json`、`package-lock.json` 一字未动（diff 里没有它们）。执行端自报的 4 条 interpretation 都写进了报告的 `interpretations`，`contract_conflicts` 为空、`unresolved_questions` 为空——与事件流里的思考记录（24 处提到歧义、5 处提到 interpretation）对得上，没有隐瞒。

## 5. 内核的检查与门禁记录

- V01（`npm test`，cwd `desktop/shell`）：`checks.json` 记 exit 0、`# pass` 匹配；`V01.log` 尾部 `# tests 358 / # pass 358 / # fail 0 / # cancelled 0 / # skipped 0`——与执行报告的「358 pass / 0 fail」一致，且没有 skip。
- G01（`python -m pytest tests/test_gate_t064_baseline.py -q`）：exit 0，`G01.log` 为 `17 passed in 1.61s`，与匹配式 `\d+ passed` 相符。
- R01（合同写死的 57 份门禁全跑）：`checks.json` 记 exit 0、匹配成立；`R01.log` 为 `1195 passed in 1177.95s`——执行端自报只跑了其中 10 份（53+56+11），内核跑的是全套，把这条限制补上了。
- 三条检查的 `modified_by_checks: false`、`candidate_files_modified: []`、`unexpected_files_by_checks: []`、`covers_all_required: true`、`all_required_passed: true`：检查过程没有改候选树。

## 6. 执行报告的自述 vs 内核摘要的线索

内核摘要点名的几条线索我逐条对上了：

- 「新增被 Git 忽略的路径：`desktop/web/dist/`、`desktop/web/node_modules/`」：这两条是构建产物/依赖目录，不在候选补丁里（20 个文件全是已跟踪文件的 M）；R01 里 T032 的前端冻结名单也全绿，说明 `desktop/web/**` 的已跟踪文件一个字没动。执行端自报没有声称动过它们，不构成不实自述。
- 「删除了 11 行含断言的代码（新增 99 行）」：逐处核过，删掉的都是用例标题行与键表字面量（如 preload 键表两行、T035 的 `registrations, 7` 那一行），每一处都在同一个 hunk 里被更长的等值/超集断言换回，没有一条断言被删掉或放松（见 §3）。
- 「掩盖退出码的写法（6 条命令）」：`events-summary.json` 的 `masked_exit_commands` 6 条全是 `grep … | head` 之类的查资料管道，没有一条是测试或检查命令；`suspicious_commands: []`、`temp_path_uses: []`、`temp_dirs_without_cleanup: []`、`problems: []`、`ok: true`。
- 执行报告的 DoD 自述 D01–D11 与源码逐条对得上（§2），没有「报告里说 done、代码里其实没做」的情形。

## 7. 战后门禁的核对

- 白盒 `whitebox-20261120T012434064223Z.py`：9 条（W01–W09），前 5 条是 main.js/README 的静态形状，后 4 条是打真模块的探针。逐条读过，不是空心断言：W01 按花括号取 `second-instance` 的函数体再查 `isDestroyed`/`isMinimized`/`restore` 在 `focus` 之前、取用次序 serviceWindow 先于 shellWin；W03 在 `switchRepoEntry` 的函数体里按文本位置钉「存盘失败先回 → relay.clear() → serviceWindow = null → flow.stop() → flow.reset() → openShellWindow(SHELL_START_URL) → ERROR+app.exit(1)」，并钉「置 null 之后收尾不再读 serviceWindow 变量」；W02 钉第一次 `createHost(` 带 `repoOps.listRepos(repo)`、`switchRepoEntry(id, repo)`、`api.pickRepo()` 与 `return result.value`，第二次 `createHost(` 不含这些记号。
- 变异记录 `mutations.json`：26 条全部 `caught`（caught 26 / missed 0 / skipped 0 / error 0），覆盖执行端改动的全部 9 个非测试文件，每个至少一条（settings 2、shellapi 5、serviceflow 2、host 3、hostrelay 1、ipc 3、preload 2、main 6、README 2），接线类变异（onRepoOps 只交一半、HOST_CHANNELS 少通道、preload 少暴露、切换编排漏 `relay.clear()`）都在内。
- 「声明等价的变异」：`decisions: null`——门禁端没有声明任何「测不出来」的等价变异，没有需要我逐条裁定的等价声明。
- 「没法变异的改动文件」：门禁端没有声明任何文件不用测；9 个改动的非测试文件全部有变异覆盖。
- 门禁端声明「无候选缺陷」：我独立核过源码，没有找到它漏掉的缺陷（§1、§2）。
- 门禁端的两条偏离（没用官方 `mutate --check-anchors` 改用同口径自检；白盒与基准合成一条命令）不影响本次核验的结论。按规矩，白盒文件与变异清单只用于本次核验、不进仓库，我不对它们在仓库里的形态提意见。

## 8. JEV 三条 flag 的复核

- 「自行解读合同而没写进冲突/提问」（p=0.92）：4 条解读都写进了报告的 `interpretations` 并给了理由，其中第 4 条（host 透传）还是修正合同自身两节互相矛盾所必需的；不构成隐瞒。
- 「自述完成而无证据」（p=0.87）：11 条 DoD 都指到了具体文件/命令；唯一的机械证据缺口是 D06/D07 的真 Electron 运行时部分，那是合同自己写明的范围（README 手工冒烟 + 站主实测），不是执行端编的。
- 「误导程度 2.03/3」：我核到的范围项、弱化测试项、自述项三项都不成立。
- 「超出范围 p=0.15」「弱化测试 p=0.30」：与我的核对一致。

## 9. 不挡的意见（建议类，不进阻塞项）

1. 合同正文没写「host.listRepos 对非 ok 注入物要透传」，执行端补了这一行并写进 interpretations。合同端下一版可以把这条写进 host.js 一节，免得每片都要现场判断。
2. 合同 Step 11 没列 T035「重入」探针里的两处 `registrations/handlers.size` 计数，实际必须一起改（否则 R01 红）。合同端下一版把这处补进去。
3. `switchRepo` 本片只有主进程侧的宿主接口，前端入口留给 T062；端到端只能靠 README 第 7 条手工冒烟（或 T062 落地后）。这是任务书既定的分工，不挡。
4. 单实例锁只在不带参数的外壳分支拿（带参数分支按合同一字不改），所以「带参数起服务」仍可能同时跑两份。这是合同的取舍，不是缺陷；若站主以后要全局单实例，需要另开一片。
5. `desktop/web/dist/`、`desktop/web/node_modules/` 这类被忽略的构建产物在执行工作区里出现过（不在候选补丁里）。不影响本片结论，只是提醒后续片别把 `desktop/web` 的产物当成已跟踪文件去改。

## 10. 一句话结论

实现忠实于合同、范围没有越界、旧门禁只加强不放松、内核三条检查与战后门禁 26 条变异全绿，执行报告的自述逐条对得上 → **通过**。

Verdict: PASS
