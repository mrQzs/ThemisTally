# 复审记录：t022-desktop-ui-confirm attempt-003（七端信箱 hub）

- 合同：t022-desktop-ui-confirm.v3（base 13fc8c1471fdb944c496fb2d008c5d046856c741）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（cc-switch-qianwenai-token-plan/qwen3.8-max，思考档位要求 high、生效 high；回合 20261026T170419963204Z-e066），终审报告如下

## 终审报告

# T022-7-audit-post 终审报告（audit-sonnet）

## 一、审阅范围与方法

- 通读候选源码（工作目录即冻结候选树 f9f63b26）：`desktop/web/src/writes/{useWriteFlow.ts,writeOutcome.ts,snapshots.ts,WriteConfirmDialog.tsx,write-flow.css}`、`src/api.ts`（导出面）、`src/mock/writes.ts`（全文）、`src/components/Dialog.tsx`、`src/shell/PageFrame.tsx`、三个入口（`roles-PresetBar.tsx`、`roles-PresetsTable.tsx`、`plugins-PluginsView.tsx`）与 reload 转交链（RolesPage→RolesView→PresetBar/PresetsTable、PluginsPage→PluginsView）。
- 通读四份新测试（writes-outcome/snapshots/flow/dialog）关键断言；用 attempt-003 candidate.patch 逐 hunk 审阅四份既有测试的改动，并用 attempt-002 candidate.patch 确认基线（13fc8c14）没碰过这四份——因此 attempt-003 的 diff 就是累计 diff。
- 核对战后门禁的白盒测试文件、mutations.json 逐条结果、内核独立检查记录（R01 692 passed、V01–V04 绿）、JEV 判断。
- 对照合同 v3（含站主四条决定）、一审下游须知第 7 条的五处人工审阅点与 W3 时序要求。

## 二、一审五处人工审阅点的核实结果

1. **D05（部分写入）——通过**：`writes-outcome.test.ts` 从 `../src/writes/writeOutcome` import 真实的 `classifyWrite/classifyTerminal/finalFromReread/warnLines/errorText`，用注入的信封（自建 `env()`/`op()` 工厂）逐行断言映射，没有把映射表抄进测试；「退出非 0＋快照不同→partiallyWritten、相同→failed、重读失败→unknown」「退出 0＋重读失败→rereadFailed 且 warnings 保留」都在。流程层 `writes-flow.test.tsx` 用真实 PresetBar＋`?write=exit1`＋覆写 getPresets 翻转 active_preset 走通「已部分写入」路径（M2/M3/M19）。
2. **D13（`<b>x</b>` 原样文字）——通过**：`writes-dialog.test.tsx:113–135` 断言 `textContent` 含 `<b>x</b>` 原文且 `d.querySelector('b')` 为 null（failed 与 doneWithWarning 两处）；源码里报错走 `<pre>{view.error}</pre>`、WARN 走 `<p>{w}</p>`，均为 React 文本节点，无 dangerouslySetInnerHTML/innerHTML（全文件 grep 无命中）。
3. **D16（四份既有测试只改点名断言）——通过**：累计 diff 共删 8 行断言、增 225 行（与内核摘要一致）。逐文件：page-app 只改 D17 那一处（13→12＋用例名逐字，运行时页 9 与总览 0 未动，其余用例未动）；page-roles 的 PresetBar 用例改「选中当前禁用/改选可点」并新增两条断言（无提示包裹）；readonly2-app 禁用清单去掉启用/停用、白名单加两名字（合同 D11 明许）；readonly2-plugins 操作列 disabled→可点＋点按钮只弹确认框（新增 getPlugin 不被调用断言，比原用例更强）、悬停用例改挂 [重新核对]（interpretation ②，仍断言 role=tooltip、400ms 时序、「第二阶段接入」全文）。没有删用例、没有 skip/only/todo（tests/ 全目录 grep 为 0）。
4. **D09（无方案不渲染 [切换…]）——通过**：`roles-PresetBar.tsx` 在 `presets.length === 0` 时只返回提示 `<p>`，分段与按钮都不渲染；既有 page-roles「无方案时只写提示」用例未改动、照旧守着。
5. **D18（两条纪律）——通过**：scope 报告 0 越界 0 警告；候选新增只有 4 个 writes-* 测试；被 Git 忽略的 .pytest_cache/dist/node_modules 是本地产物不进候选；执行报告自述未写固定路径临时文件，事件流未见 /tmp 写入记录（内核摘要亦未标）。

## 三、W3 时序核查（一审专项要求）

`confirm()` 点击后直接 setView('executing') 并发出写请求，**没有**再读快照；快照只在 `runPreview` 里 `Promise.all([preview, readSnapshot(action,false)])` 与预览并行读一次，存进 snapRef；重读只发生在 `doReread`（执行响应归类之后）。合同第五节「快照在预览阶段与预览并行读」满足，flow 探针的 hangReread（writes-flow 的 M1 用例覆写 getPresets 卡重读）挂的位置正确。轮询上限：elapsed 每 tick +1000，119000 时仍 running 不下结论、120000 进 unknown，与 D12/M10/M11 一致（测试用 119000/121000 断言）。

## 四、映射表与状态机逐行核对

`classifyWrite`：409 按 exit_code===4 分 stale/expired；503→busy（先查 getOperation，404 回可确认带「服务繁忙，请稍后再确认」）；400/401/403/413→rejected「请求被拒」；504→timeout「超时」；500→serverError「服务出错」；200 ok 按 WARN 分 success/successWarn；200 !ok 按退出码 1/3→内核拒绝、2→用法错误、N→失败（退出 N）；其他状态码→checkOperation（404→unknown）。`classifyTerminal` 五种终态映射照第四节。`finalFromReread` 的成功/失败两族分支照表。写请求抛错→startPolling（确认结果中），轮询本身抛错继续轮到上限。19 个 `?write=` 情景在 `mock/writes.ts` 的实现与第二节表逐行一致（含 drop-done 第一次 running 第二次 succeeded、expired/busy/drop-lost 404）。未发现为过测试的特判、空 catch（`.catch(() => {})` 只在 reload——合同明说 reload 只刷显示——与 readSnapshot 的 catch→{ok:false}，后者正是合同「重读失败」的路径）或对测试输入的硬编码。

## 五、门禁端声明的 6 条 expect_missed:[W2] 变异——逐条裁定：真的只有 W1 抓、且 W1 确实抓

- **rolespage-drop-reload / pluginspage-drop-reload / rolesview-drop-presetbar-reload / pageframe-children-no-reload / flow-done-no-reload**：白盒探针第 4/5 条在真实页面（#/roles、#/plugins）走完 ok 流程后断言 getPresets/getPlugins 调用差 ≥2（流程内重读 1 次＋页面 reload 1 次）。任一环节的 reload 转交断掉，差值降为 1，探针红。基线门禁的 flow 探针不数调用差，W2 确实测不到——声明成立。mutations.json 里五条 status 均为 caught（W1 caught、W2 missed），pageframe 一条门禁端还实际施加复核过。
- **flow-command-no-filter**：白盒探针第 3 条断言确认框「将运行的命令」含 `config preset use economy` 且不含 `--dry-run`/`--json`；基线探针无此断言。caught。
- 结论：6 条全部成立，不构成缺陷。32 条变异全 caught、`unmutated` 为空；六个类型放宽文件靠 tsc（V01/V04 两条命令都有）杀，门禁端已逐文件验证报错独立，认可。

## 六、JEV 三个「需关注」的核实

- **自行解读合同 p=0.95**：指 interpretation ①（preview.command 带开关、对话框过滤）。合同第二节与第六节确实各说一处，执行端的读法（预览响应照 README、对话框显示真正会跑的写命令）符合合同意图且已列进 interpretations（不是隐瞒）；战后门禁已把它钉成边界（wbs03＋探针第 3 条＋变异）。认可，不构成缺陷。
- **自述完成无证据 p=0.81**：唯一无当时证据的是 R01（在最后一处 mock 改动前跑的），内核已在冻结候选上独立补跑 692 passed，闭合。
- **弱化测试 p=0.48**：见第二节第 3 条，逐 hunk 核实无削弱；悬停用例改挂后断言反而更精确（aria-describedby 定位＋399/400ms 时序保留）。

## 七、不挡的意见（不進阻塞项）

1. `mock/writes.ts` 的 `mockGetOperation` 在 reread-fail/reread-fail-exit1 情景落 default 返回 404，合同第二节表该列写的是 succeeded。流程里不可达（这两个情景执行响应是 200，不会进轮询），门禁 api 探针也没探这一列，无行为影响；B 片动这个文件时可顺手对齐（已写进下游须知）。
2. `useWriteFlow.ts` 里 proceed/startPolling 闭包引用 queryOp/proceed 而依赖数组不含对方（互相引用避免不了）；现状所有 callback 的依赖都稳定（[]/稳定引用），无 stale 闭包。B 片改这个文件时留意别引入会变的依赖（已写进下游须知）。
3. 内核摘要提到运行期间主工作区 `AGENT_LEARNINGS.md` 变化——不在候选树内，审核端无权也未查主工作区；请协调人在集成前确认来源（已写进下游须知）。
4. 执行事件流有 3 条检查命令退出码被管道掩盖——内核独立检查已全绿覆盖，不构成缺陷。

## 八、结论

实现忠实于合同 v3 与站主四条决定；无越界、无弱化测试、无为过测试的特判；门禁端声明的等价变异逐条成立。**结论：通过**，无退回、无阻塞项。

Verdict: PASS
