# 复审记录：t041-desktop-web-runtime-add attempt-002（七端信箱 hub）

- 合同：t041-desktop-web-runtime-add.v3（base 4b6e409986a11d68acad7d78daf0245b5e41cd0b）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261115T013611804054Z-8e15），终审报告如下

## 终审报告

# T041-7 终审报告（audit-sonnet，审核端）

合同：`.agent/plans/t041-desktop-web-runtime-add.v3.md`（plan_version 3）
候选：`attempt-002`，候选树 `49534db5c8ac9cfcca605282abdf9c95993ef608`（= 返工基线 `4b6e409` + attempt-001 的候选，attempt-002 零改动）
本回合结论：**通过**

## 0. 本回合范围

attempt-002 的 `candidate.patch` 是 0 字节、`changes.json` 是 `[]`、`scope.json` 的 `files` 为空且 `ok: true`（`head_after` = `4b6e409`）——执行端本轮没有改任何代码，只是把返工说明里的对照项（上一轮 D07 的 G01 冲突）对着热修补后的门禁重跑了一遍。返工说明里的「终审列的阻塞项」一节为空（「这个候选之后终审没有退回执行端」），所以本轮终审的对象其实是**被搬进返工基线的 attempt-001 候选整体**，我按合同 v3 对它逐文件核对，而不是只看「本轮没改动」。

## 1. 源码核对（先读源码，再看门禁记录）

### 1.1 改动集合与范围（D05）

候选补丁共 15 个文件：`desktop/web/src/{api.ts, mock/writes.ts, pages/RuntimesPage.tsx, writes/RuntimeForm.tsx(新), writes/runtime-form.css(新), writes/runtimeRules.ts(新), writes/useWriteFlow.ts}`、`desktop/web/tests/{live-api.test.ts, page-app.test.tsx, writes-runtime-api.test.ts(新), writes-runtime-form.test.tsx(新)}`、`ts/packages/ui/{README.md, src/redaction.ts, src/writeroutes.ts, test/write-argv.test.ts}`。与合同 `allowed_modified_files`（15 条，其中 5 条同时在 `allowed_new_files`）逐条对上，**全部在允许集合内**；`forbidden_paths` 里的内核脚本、components、readonly1/2、`src/mock/*.json`、`snapshots.ts`、`ProfileForm.tsx`、`useLivePreview.ts`、`profileRules.ts`、`tests/test_gate_*.py` 一个字没动。**执行报告里写「恰为合同允许的 14 个文件」是数目笔误**（实际 15），集合本身核对无误。

### 1.2 D01 写路由接通

- `api.ts`：新增同步 `export function addRuntime(args, confirmation)`——真实模式 `POST /api/v1/runtimes/${encodeURIComponent(args.runtime)}/add`，正文 `{...writeArgs(w), confirmation}`，`WRITE_TIMEOUT_SECONDS`（=90，已核 api.ts:164），`command` 只在调用方给了这个键时才进 `w`（空数组由 `writeArgs` 丢掉，api.ts:181-191）；桩模式转 `mockAddRuntime`；`import { mockAddRuntime }` 已接上；`WriteAction` 加 `'runtime.add'`，既有 11 个成员一个不丢。
- `useWriteFlow.ts`：三张文字表各加一条（`登记运行时 X？` / `已登记运行时 X` / `已登记表里加上 X（适配器 A）`，带非空命令数组才接「；命令写进本机文件」）；**`readSnapshot` 有显式的 `runtime.add` 分支**（`getRuntimes()` + `runtimeRemoveSnapshot`，与 runtime.remove 同一份投影），没有落到 `getPlugins` 兜底；`confirm` 的分派链 `runtime.add → addRuntime`；import 已接。
- `mock/writes.ts`：`baseArgv` 的 `runtime.add` 分支逐字照服务 `buildWriteArgv`（`['config','runtime','add',<id>,'--adapter=<a>']`，有命令再 `--command=` + `JSON.stringify`）；`NEW_ACTIONS` 加 `runtime.add`；`previewData` 加分支（`binding_changes` 恒空、`resources` 无命令 `['config']` / 有命令 `['config','local']`）；新增 `mockAddRuntime`（空数组不带键，走 `confirmWrite`）；新增情景 `preview-registered`（200 / ok 假 / exit_code 1 / data null / 一行内核原文），返回点在 `newOpId` **之前**，所以不签发确认号。
- `RuntimeForm.tsx`（新）：`AddRuntimeAction` 是 `primary`/`md`、`PlusIcon` 在文字前、离线也可点；对话框标题「登记运行时」；三字段（ID 等宽复用 `profileRules.validId`、适配器 `Select` 五值缺省 pi、命令等宽 + help 原文）；底部 `useLivePreview('runtime.add', args, canPreview)`，`result.error` 原样显示、命令走 `dispatchCommand(result.command)`；`[确认…]` 门控 `canPreview && current && result !== null && result.ok`（与 ProfileForm 样板逐字同构）；确认时先 `onClose()` 再 `start(spec)`；成功后清空表单；自渲染 `<WriteFlow flow={flow} />`；全文件无 force。
- `RuntimesPage.tsx`：只放按钮——`actions={(reload) => (<><DisabledAction label="扫描 PATH" …/><AddRuntimeAction reload={reload} /></>)}`，次序不变（扫描 PATH → 手动登记… → 刷新）；空态标题「还没有登记的 runtime」不动，说明改成合同第八步的原文；`loadRuntimes`/`isRuntimesEmpty` 仍具名、`children` 仍是 `(data, reload)`；入口文件不含确认框标题/轻提示/内核原文/字段提示。
- 界面显示的命令口径：`useLivePreview.ts:29` 确实过滤 `--dry-run`/`--json`（服务侧预览请求那一条仍带这两个开关，mock 的 `previewData`/`mockPreview` 都在基础 argv 后加 `--dry-run --json`）——合同的「界面不带、请求带」口径成立。

### 1.3 D02/D03/D04 的实现面

- 适配器五值：`RuntimeForm` 的 `ADAPTER_OPTIONS` = pi/claude-code/codex/opencode/quizs，缺省 pi；服务 `writeroutes.ts` 的 `ADAPTERS` 恰五值，注释改成「五个取值」。
- D03：`preview-registered` 情景回 200/ok 假/退出码 1/data null/一行 `ERROR: runtime <id> 已登记为 <adapter>；改 adapter 要加 --force`；界面逐字显示该行、`[确认…]` 不可点、界面无 force 控件（源码里没有 force，DOM 里也没有）。
- D04：`runtimeRules.parseCommand` 与服务 `validCommand` 的四条规则（非空数组、每项非空、≤1024 码点、不含 C0/DEL）一致，不强制绝对路径。**差一条**：服务 `cleanText`（writeroutes.ts:169-179）还拒孤立代理项（0xD800–0xDFFF），本地没拒（见第 6 节意见 1）。

### 1.4 D06 不削弱既有测试

逐行看 diff：对既有测试文件只有两处、且都是合同第 10 步与站主来信第 3 条授权的增量——`page-app.test.tsx` 的过渡计数（运行时页禁用按钮 6→5，连标题一起改，工作树现状与断言一致）、`live-api.test.ts` 的 `WRITE_ROWS` 加两行（addRuntime 的路径/正文两种）。**没有删除、跳过或弱化任何既有断言**，新测试文件里也没有 `skip`/`only`/`todo`。

### 1.5 D08 服务只改四处

`writeroutes.ts`（ADAPTERS + :53 注释）、`write-argv.test.ts`（+1 条 quizs 通过用例）、`README.md`（runtime.add 那条补「adapter 取五值…」；另把同文件校验段的「adapter 四选一」改成「五选一」——这一处正是站主来信「修正 README 与 redaction.ts:14 注释里『四值』的说法」点名要的）、`redaction.ts`（:14 注释；`HUB_ADAPTER_ENUM` 枚举逐字未动）。**其余服务代码一字未动**。

## 2. DoD → 证据映射（终审版）

| DoD | 证据（测试 → 断言） | 判定 |
|---|---|---|
| D01 | 候选自测 `writes-runtime-api.test.ts`（真实模式 POST 路径/正文/时限 90；桩模式预览 argv 逐字带 `--dry-run --json`；执行 `--expect-state=<state>`；号或参数不符 409）+ `writes-runtime-form.test.tsx`（入口可点、对话框标题、300ms 防抖、门控、全流程、轻提示「已登记运行时 X」、成功后清空）；G01 的 form/api 两条黑盒探针钉同样的行为；**人工审阅**：`useWriteFlow` 的显式 `runtime.add` 快照分支（`getRuntimes` + `runtimeRemoveSnapshot`）、`api.addRuntime`、`mock` 的四处接线 | ✓ |
| D02 | form 探针与候选自测：下拉恰五值、缺省 pi；api 探针：`--adapter=quizs` 的 argv 逐字；S07 静态（服务 ADAPTERS 恰五值、注释、README、redaction 注释、write-argv 用例）；V03（16 passed） | ✓ |
| D03 | form 探针与候选自测：内核原文逐字显示、`[确认…]` 不可点、无 force 控件（按钮/选项/整页文本）；api 探针：200/ok 假/退出码 1/data null/一行原文/不发确认号、执行 409 | ✓ |
| D04 | form 探针与候选自测：六个非法值（非 JSON、非数组、空数组、空串项、1025 码点项、含控制字符项）逐个「提示逐字 + 不调 preview + 禁确认」；「不强制绝对路径」靠合法值 `["C:/tools/pi.exe","--flag"]` 被放行间接覆盖 | ✓（孤立代理项差一条，见意见 1） |
| D05 | **人工审阅候选补丁**：15 个文件全在允许集合；禁改路径零改动；attempt-002 自身零改动（scope.json ok、changes.json 空、patch 0 字节） | ✓ |
| D06 | **人工审阅 diff**：只有两处授权增量，无删除/跳过/弱化；V01 全绿（114 文件 / 1078 用例）、R01 943 passed | ✓ |
| D07 | G01 13 passed（热修补后的 S06 窄豁免）、R01 943 passed（t009/t023/t024/t031/t037 在内） | ✓ |
| D08 | **人工审阅 diff**：服务只有上述四处；枚举/接口形状未动 | ✓ |

## 3. 内核检查记录与门禁记录（自述对账）

内核对候选树的独立检查（`attempt-002/checks/01/checks.json`，run 01，fresh verify workspace）：V01/V02/V03/V04/G01/R01 **全部 passed，真实退出码 0**，`output_must_match` 全部 `matched: true`：

- V01 `Tests\s+[1-9]\d* passed` → 日志末行 `Test Files 114 passed (114) / Tests 1078 passed (1078)`，其中含新文件 `writes-runtime-form.test.tsx (12 tests)`、`writes-runtime-api.test.ts (5 tests)`；
- V02 `built in` → `✓ built in …`；
- V03 `Tests\s+[1-9]\d* passed` → ts 侧 16 passed；
- G01 `\d+ passed` → `13 passed in 25.19s`（上一轮唯一的红就是被热修补掉的 S06 误报，现已转绿）；
- R01 `\d+ passed` → `943 passed in 1206.70s`。

**与内核摘要线索逐条对上的结果**：
- 「测试或检查命令的退出码被管道掩盖」：执行端自跑的命令确实用了 `| tail`（事件流第 416 行的 G01 探索跑等 13 条探索命令），但执行器随后用 `set -o pipefail` / `echo exit=$?` 重跑拿到真实退出码；更重要的是内核自己的独立检查是**不带管道**的真实退出码（0），DoD 自述与内核记录一致，**不是自述不实**。
- 「临时路径」：事件摘要 `temp_path_uses: []`、`temp_path_use_count: 0`、`outside_worktree_paths: []`——本轮没有 T025 attempt-002 那种往固定临时路径写文件的情况。
- 新增被忽略路径 `.pytest_cache/`、`desktop/web/dist/`：都在 `.gitignore` 里（`desktop/**/dist/`），不是交付物。

## 4. 执行端三处解读的裁定

| 解读 | 裁定 | 依据 |
|---|---|---|
| ① 空 ID 不弹字段错误文字（只做「不调预览 + 禁 [确认…]」） | **接受**（不挡） | 合同自称 ProfileForm 是「表单样板」，而 `ProfileForm.tsx` 的 ID 字段正是 `error={id !== '' && !idValid ? ID_ERROR : undefined}`——同一条惯例；合同「边界输入」把「空」列进不合法一组是字面读法；门禁 docstring 明写「合同对『空』是否显示提示文字的写法留了空间，门禁不钉死」，白盒 W06/变异 M21 把这一取舍钉住。功能要求（不调预览、[确认…] 不可点）都已满足。站主若要严格按字面执行，须同时改实现、W06 断言与 M21 |
| ② 命令字段只填空白按「留空」处理 | **接受**（不挡） | 合同的不合法清单是「非 JSON、空数组、含空串、超长、控制字符」，全空白严格说算「非 JSON」；但文本框里的空白等同未填是常见口径，后果轻（用户打了一个空格 → 静默按无命令登记）。执行器已写进 interpretations，门禁 M23 钉住 |
| ③ README 校验段「四选一」→「五选一」 | **接受**（在授权内） | 站主来信原文就要求「修正 ts/packages/ui/README.md 与 redaction.ts:14 注释里『四值』的说法」，这一处不算越界；仍限于合同允许的 README 这一处 |

## 5. 战后门禁记录核对

- 门禁端举证的候选缺陷：**无**（candidate_defects 空），故无缺陷需要裁定。
- 白盒 9 条（W01–W09）逐条看过：都是静态原文锚点断言，但**不是空心断言**——每条都对着「这行改动会改变哪个可观察行为」选点，且覆盖了接线：`import { parseCommand }`/`import './runtime-form.css'`/`import { mockAddRuntime }`/`import { addRuntime }`（去掉 import 就红）、`NEW_ACTIONS` 注册、`readSnapshot` 的显式分支（正则要求 `getRuntimes` + `runtimeRemoveSnapshot` 的完整形状）、分派链 `→ addRuntime`、`preview-registered` 返回点排在 `newOpId` 之前（所以不签发确认号）、CSS 里每个 `rt-*` 类都在 `RuntimeForm.tsx` 用上、只用 `--tt-*` 令牌不写死颜色。行为面由 G01 的 npm 流水线黑盒探针兜底，不是靠源码文本自证。
- 变异记录：32 条，覆盖执行端改动的全部 10 个非测试文件（api 3 / mock 6 / flow 5 / form 7 / css 1 / rules 5 / page 2 / writeroutes 1 / README 1 / redaction 1，`unmutated: 无`），`counts: caught 32 / missed 0 / skipped 0 / error 0`，每条 `count_found: 1`（锚点唯一）、退出码都是 1。我抽查了 M21/M23/M24/M25/M26/M27/M28/M29/M30/M31/M32 的日志：**全是带中文说明的 `AssertionError`**，不是收集错误或中断（例如 M21 命中「ID 的错误文字应只在非空且不合法时显示」、M23 命中「命令全空白应按留空处理」、M30 命中「服务的 ADAPTERS 应恰为五值」）。声明等价的变异，逐条都能测出来。
- 环境备注：门禁 worktree 没装前端依赖，白盒只能静态断言，变异走进程内 Python 实现——这是环境限制，已在报告写明，TS 与 Python 的对等由 ts/ 契约测试覆盖；内核复跑若遇同一报错按同款口径即可。

## 6. 不挡的意见（建议类，不进阻塞项）

1. **命令项的孤立代理项本地没拒**：`runtimeRules.ts` 的注释与 D04 都写「与服务侧 `validCommand` 同一条规则」，但服务 `cleanText` 还拒 0xD800–0xDFFF 的孤立代理项。触发路径具体（剪贴板里带半个代理对的命令项），后果轻：本地放行 → 预览时服务回 400「command 不合法」→ 界面显示该行、[确认…] 不可点，不崩溃、不越权。建议二选一：加一行拒绝代理项，或把注释改成「与服务 validCommand 的四条规则一致（服务端另拒孤立代理项）」。
2. **白盒 W03 的两处「恰」断言违背仓库既有约定**：W03 断言 `NEW_ACTIONS` 恰 9 个成员、`SCENARIOS` 恰 23 个情景；而 t037 的 docstring 与 t041 的 S02 都明写「按包含不卡恰好，后续片合法地加导出或情景值不会误红」。该文件目前是门禁 worktree 里的**未跟踪**文件（门禁 state 记 `git status` 只有 `?? mutation-spec.json` 与 `?? tests/test_gate_t041_whitebox.py`），不在候选树里、也不影响本轮合并；但若内核/站主要把它落进仓库，下一片往 `mock/writes.ts` 加写动作或情景时它必然误红，而门禁文件在执行端的 `forbidden_paths` 里——正是 T041 这一轮自己踩过的死结。落库前请先把这两处改成「包含 + 不少于」。
3. **空 ID 的字段提示**：见第 4 节①。合同字面把「空」列进要显示提示的一组，实现按样板惯例不显示；我按默认接受，请站主知情。
4. **命令全空白按留空**：见第 4 节②。同样请站主知情。
5. **门禁文件 docstring 的基线号**仍写 `f4012ee`（实际返工链 `591dd8e7 → 4b6e409`）：纯文档，门禁端与内核都提过，仍未改，留给内核/站主。
6. 执行报告的「14 个文件」数目笔误（实为 15 个），已在 1.1 节说明。

## 7. 结论

候选忠实于合同 v3 的 Behavior contract 与 Steps 1–10：15 个改动文件全在允许集合内，禁改路径零改动，既有测试未被削弱，服务只改了站主拍板的四处；内核对候选树的独立检查六项全绿且是真实退出码，上一轮唯一的红（G01 的 S06 误报）已由门禁热修补解除且本轮复核转绿；战后门禁未举证任何候选缺陷，32 条变异全被有意义的断言抓住。**结论：通过。**

留给站主的两件事（不挡下一阶段开工）：真 Electron 窗口里的写操作冒烟（登记 quizs 与 pi 运行时 → 新建 profile → 删除），以及白盒文件落库前先放宽 W03 的两处「恰」断言。

Verdict: PASS
