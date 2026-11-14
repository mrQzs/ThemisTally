# 复审记录：t036-desktop-web-live attempt-001（七端信箱 hub）

- 合同：t036-desktop-web-live.v1（base 6088bcdb4dcebbd6cda421916d60fe6cf1676875）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261113T205605946967Z-7fdb），终审报告如下

## 终审报告

# T036-7-audit-post 终审报告（审核端 audit-sonnet）

时间：2026-11-13（UTC）。候选：t036-desktop-web-live attempt-001（基线 `6088bcdb4dcebbd6cda421916d60fe6cf1676875`，候选树 `59cc824a6bf9eff3045307787736d23c929f1eb9`）。

## 0. 结论

**结论: 通过。** 退回：无。阻塞项：无。

候选 8 个文件全部在合同 Scope 内；实现逐条忠实于合同的 Behavior contract；内核在固定候选上把四条必需检查真跑了一遍，真实退出码全绿；战后门禁 25 条变异全部被抓住（caught 25 / missed 0）。执行报告的自述与内核摘要里的线索逐条对得上，没有自述不实。

本回合只读：没有修改任何文件、没有跑命令、没有碰主工作区（材料在只读输入目录与工作目录副本里读）。

## 1. 材料与核对方式

- 候选补丁：`.agent/runs/t036-desktop-web-live/attempt-001/candidate.patch`（40 KB，8 个文件全文读过）。
- 工作目录里的候选树逐文件复读：`desktop/web/src/live/{events.ts,useLiveStatus.ts,connection.ts}`、`desktop/web/src/pages/{OverviewPage.tsx,TasksPage.tsx}`、`desktop/web/tests/live-{events.test.ts,events-hook.test.tsx,pages-live.test.tsx}`。
- 内核检查记录：`checks/01/checks.json` 与 `G01.log / R01.log / V01.log / V02.log`（真实退出码、日志哈希、`output_must_match` 的 matched 标记）。
- 执行侧：`summary.md`、`executor-report.md`、`scope.json`、`candidate.stat.txt`。
- 战后门禁：`T036-6-gate-post/report.md`、白盒测试文件、`evidence/mutate-…/mutations.json`（25 条逐条）与 `M19.log`。
- 合同：`.agent/plans/t036-desktop-web-live.v1.md`（Behavior contract / Scope / Steps / D01–D14 / Compatibility / 站主决定原文）。
- JEV：`T036-6j-jev/report.md` = `no_opinion auth_failed`（授权失败，**没有出意见**）→ 本回合的合同忠实度与实现正确性全靠人工核，如实记下，不当阻塞项。
- 服务端既有实现（仓库内事实，用来验客户端假设）：`ts/packages/ui/src/kernelenvelope.ts`、`ts/packages/ui/src/events.ts`、`ts/packages/ui/README.md`「实时通道（SSE）」一节。

## 2. 候选源码核对（先读源码，再看门禁）

### 2.1 `src/live/events.ts`（新增，229 行）

逐条对着合同的 Behavior contract：

| 合同条款 | 实现位置 | 判定 |
|---|---|---|
| 四个 interface 的名字与语义写死 | `LiveStreamEvent` / `LiveStreamHandle` / `LiveEventsOptions` / `LiveEvents` 逐字对上（字段 readonly、签名一致） | ✅ |
| `createLiveEvents` 可注入假流/假计时器/随机数 | `options.setTimer/clearTimer/random` 都有缺省实现，缺省走 `setTimeout/clearTimeout/Math.random` | ✅ |
| 默认实例 `createStream` 建 `new EventSource('/api/v1/events')`，同源相对路径、不带凭据头 | `createDefaultStream()`：`new EventSource('/api/v1/events')`，无 options、无 header、无 withCredentials | ✅ |
| `subscribe` 在 `liveModeIsReal()` 为假时直接空操作（不登记、不建流、不排计时器） | `liveEvents.subscribe` 首行 `if (!liveModeIsReal()) return () => {};` | ✅ |
| 开关永远只有 `liveModeIsReal()`（不认 `liveClient`、不做 typeof 判断） | 全文件只有 `liveModeIsReal()` 一处判断；`grep liveClient` 0 命中 | ✅ |
| 收事件只用 `addEventListener('snapshot'|'update')`，不用 `onmessage` | `openStream()` 里 `handle.addEventListener('snapshot', onSnapshot)` / `('update', onUpdate)`；无 `onmessage` | ✅ |
| 流的 `error` 也用 `addEventListener` 收 | `openStream()` 里 `(handle as unknown as WideStream).addEventListener('error', onError)`（合同把 handle 的 union 写死成两值，实现用宽类型转型，已在执行报告写明） | ✅ |
| `snapshot` 整份替换、不比较序号大小、基线重置、次数清零、写 `connected`、通知 | `onSnapshot`：`baseline = seq; failures = 0; setReconnectCount(0); setConnectionState('connected'); status = push.data; notify();` | ✅ |
| `update` 序号不大于基线丢弃；没收到过 snapshot 丢弃；否则整份替换 + 基线推进 + 通知 | `onUpdate`：`if (baseline === null \|\| seq <= baseline) return;` → `baseline = seq` → 替换 + `notify()` | ✅ |
| 序号解析不出非负整数 → 整条丢弃（不改数据、不推进基线、不通知） | `parseSeq` 用 `/^\d+$/`（`-1`/`abc`/`''` 都拒），两个 handler 都先判 seq | ✅ |
| `ok:false` 推送不覆盖已显示数据、序号照常推进、不通知 | `parseEnvelope` 走 `push.ok` 分支：`baseline` 照常推进，`status` 不动，`notify()` 不调 | ✅ |
| data 不是合法 JSON → 整条丢弃（不推进基线） | `parseEnvelope` 的 `catch` 返回 `undefined`，两个 handler 都 `if (push === undefined) return;`（在 `baseline = seq` 之前） | ✅ |
| data 不是七字段信封 → 按 ok:false 处理 | `isEnvelope()` 校验七字段；不合格 → `{ok:false}`（不覆盖、序号照常推进） | ✅ |
| `error` 事件不论 readyState 都 `close()` 掉原生流、自己排重连 | `onError`：`closeStream()` → `failures += 1` → `setReconnectCount(failures)` → `setConnectionState('reconnecting')` → `clearPending()` → 排计时器 | ✅ |
| 退避 = `min(3000×2^(n-1), 30000) + floor(random()×1000)`，下限 3000、抖动只往后加、上限 31000 | `backoffMs(n)`：`Math.min(3000 * 2 ** (n-1), 30000) + Math.floor(random() * 1000)`（常量写成字面 3000 / 30000，无数字分隔符写法） | ✅ |
| 收到 snapshot → 次数清零、写 `connected` | `onSnapshot` 内 `failures = 0; setReconnectCount(0); setConnectionState('connected')` | ✅ |
| 最后一个订阅者离开：关流、清计时器、次数清零；状态是 `reconnecting` 时写 `disconnected`，否则不动 | 退订分支：`closeStream(); clearPending(); failures = 0; setReconnectCount(0); if (getConnectionState() === 'reconnecting') setConnectionState('disconnected');` | ✅ |
| 与 transport.ts 的写入以最后一次为准、不加仲裁 | 只调用 connection.ts 的 setter，无仲裁代码 | ✅ |
| 模块加载时无副作用（不建流、不排计时器、不读 window） | `core = createLiveEvents({...})` 只存闭包；`createStream` 只在 `openStream()` 里调，`setTimer` 只在 `onError` 里调；无 `window` 引用 | ✅ |
| 退订可重复调用且不抛 | `alive` 布尔守卫 | ✅ |
| `setEventStreamFactoryForTests` 只换建流方式、不参与开关判断 | `injectedFactory` 只在 `createStream` 里用；开关仍只看 `liveModeIsReal()` | ✅ |

与真服务端对得上（仓库内事实核对）：`ts/packages/ui/src/kernelenvelope.ts:71` 写出的信封正是七字段 `ok/exit_code/data/output/messages/command/elapsed_ms`，与客户端 `isEnvelope()` 的校验一致；`ts/packages/ui/README.md:109-112` 写明「先发一份全量快照并带序号，之后只在名单上的输入变了才推一份整份新信封」「`data` 拼回来的文本与 `/api/v1/status` 的正文逐字节相同」「序号在 hub 内单调递增、服务启动后从 1 起」——客户端的「整份替换 + 序号基线 + 重启后 snapshot 变小也照样替换」正好对上。

### 2.2 `src/live/connection.ts`（改）

- `export type ConnectionState = 'connected' | 'disconnected' | 'reconnecting';` —— **同一行、末尾追加、顺序不变** ✅（T027 S05 / T034 s13 的无尾锚正则继续匹配）。
- 四个原有导出与 `useSyncExternalStore` 原样保留 ✅；`setConnectionState` 值没变不通知 ✅。
- 新增 `getReconnectCount` / `setReconnectCount`（值没变不通知）/ `subscribeReconnectCount`，签名与合同逐字一致 ✅。
- 全 `src/` 里 `getReconnectCount` 只出现在 connection.ts 与 events.ts，**没有**经 `useShellConnection` 传给胶囊 ✅（`useShellConnection.ts` 未动，`ConnectionPill.tsx` 未动，胶囊的 `attempt` prop 仍没人传）。
- 轻微偏离：合同第 3 步写「文件其余部分不动」，执行端改了文件头两行注释（原文说「页面接线归后面的事件流那一片」→ 改成说明 reconnecting 由事件流写入）。改动在允许改动的文件内、内容与新实现相符、G01 与 R01 全绿；**不挡**，记在第 6 节。

### 2.3 `src/live/useLiveStatus.ts`（新增）

- 夹具模式原样返回 `initial`、不订阅、不建流、不起计时器 ✅（`if (!liveModeIsReal()) return initial;`，该渲染不调 `useSyncExternalStore`）。
- 真实模式 `useSyncExternalStore(liveEvents.subscribe, liveEvents.getStatus)`，有推送返回最新 status、没有推送返回本次渲染的 `initial` ✅（`return pushed ?? initial;`，`initial` 不缓存）。
- 夹具门是构建期常量（`mode.ts` 的 `BUILD_MODE` 在模块加载时定死），提前 return 不会破坏 hooks 顺序 ✅。

### 2.4 两个页面

- `OverviewPage.tsx`：新增同文件小组件 `OverviewLive` 承载 `useLiveStatus`（不在 `PageFrame` 的 children 回调里直接调钩子）✅；渲染时 `status` 用实时值覆盖、`history` 仍用首屏 ✅；`loadOverview` / `isOverviewEmpty` 仍是模块级命名函数、api 导入仍在白名单、T034 s08 的记号（`'—'`、`· kit `、`getMetaNow`、`useShellConnection(`、`const loadOverview`、`const isOverviewEmpty`）全在 ✅；**没有**轮询、没有重复取数（新增代码里没有定时器/再次取数）✅。
- `TasksPage.tsx`：列表页 `TaskListLive` 用实时 `status` 整份替换 `rows` ✅；详情页 `AttemptDetailLive` 的行匹配口径与 `tasks-data.ts:66` 完全一致（`r.task_id === task && attemptSeg(r.attempt) === attempt`），找不到同 attempt 行时回到首屏行 ✅；`PageFrame`、`from './tasks/'`、默认导出保留 ✅；未加 section ✅；`src/pages/tasks/` 仍 17 个文件（我逐个数过）✅；只**读**了 `tasks-model.ts` 的 `attemptSeg`，未改 `src/pages/tasks/**` ✅。
- 两页 + 两个新 `src/live/` 文件里四个网络接口名/注入词/`role=`/内联 `style`/十六进制色：grep 结果——`events.ts` 只有 `:200` 的 `new EventSource('/api/v1/events')`（Compatibility 节允许代码里出现），其余三个文件 0 命中 ✅；`events.ts` 的注释里没有网络词 ✅。

### 2.5 三份新测试

- 全部用假流 + 假计时器，不靠真实等待；断言的是真实实现（通过 `createLiveEvents`/`setEventStreamFactoryForTests` 注入），没有把业务逻辑抄进测试 ✅。
- 没有 `skip` / `only` / `todo`（grep `live-*.test.*` 0 命中）✅；既有测试文件一个都没改（scope.json）✅。
- 没有硬编码测试输入的特判：期望值（`工具调用 37 次`、`已用 19 分 6 秒`、`5,632,345`）都来自 `src/mock/status.json` 与既有格式化函数，与一审的核对一致 ✅。
- 没有空异常处理：`parseEnvelope` 的 `catch` 有明确语义（整条丢弃）✅。

## 3. DoD → 证据映射（D01–D14）

| DoD | 证据（本次复核） | 判定 |
|---|---|---|
| D01 开关只由 `liveModeIsReal()` 决定；夹具模式不建流不排计时器；模块加载无副作用 | `events.ts` 开关门 + `live-events.test.ts`「默认实例：夹具模式」（`created===0`、`vi.getTimerCount()===0`、`getStatus()` 为 null）；白盒 logic 探针 default it1 | ✅ |
| D02 引用计数建流/关流，多订阅者一条流 | `subscribe` 里 `listeners.size === 1` 才 `openStream()`、退订时 size 归零才关流；`live-events.test.ts`「多订阅者只一条流」；M08 变异被抓 | ✅ |
| D03 snapshot 整份替换重置基线；update 过期丢弃；重启后序号变小照样替换 | `onSnapshot`/`onUpdate`；`live-events.test.ts` 三条序号用例；M03/M10 变异被抓 | ✅ |
| D04 ok:false 不覆盖数据、序号照常推进 | `push.ok` 分支；`live-events.test.ts`「ok:false 的推送不覆盖…」；M04（两处守卫）变异被抓 | ✅ |
| D05 退避 ≥3000、指数、封顶 30000、抖动只往后加；等待期 `reconnecting` + 次数 n；snapshot 后清零 | `backoffMs` + `onError`；`live-events.test.ts` 退避用例（3000/6000/12000/24000/30000/30000、random 0.9999→3999）；M06/M12/M13/M09 变异被抓 | ✅ |
| D06 重连靠 snapshot 重建（整份替换） | `onSnapshot` 无合并逻辑；`live-events.test.ts`「重连后靠 snapshot 重建」 | ✅ |
| D07 union 三取值同行末尾、四个原导出保留、新增三个次数导出、值没变不通知 | `connection.ts` 逐字核对；既有 `desktop/web/tests/live-connection.test.ts` 未改且随 V01 绿；M15/M16/M17 变异被抓 | ✅ |
| D08 `useLiveStatus` 夹具原样返回不订阅；真实模式返回推送 | `live-events-hook.test.tsx` 三条用例（夹具 `'99'→'77'`、真实推送 `'41'`、卸载关流）；M18/M19/M20 变异被抓 | ✅ |
| D09 总览页首屏一次性读、推送后数字跟着变；load/isEmpty 模块级；api 白名单；T034 记号 | `OverviewPage.tsx` 逐条核对（人工）；`live-pages-live.test.tsx` it1（`'工具调用 37 次'`→`'41 次'`→`'45 次'`）；M21/M22 变异被抓 | ✅ |
| D10 列表 rows / 详情 row 按实时 status 覆盖；PageFrame、`from './tasks/'`、默认导出、tasks/ 17 文件 | `TasksPage.tsx` 核对（人工）+ `live-pages-live.test.tsx` it2/it3；M23/M24/M25 变异被抓 | ✅ |
| D11 禁改清单一个没动；既有测试一个没改 | `scope.json`：8 文件（3 改 5 新）、`violations: []`、`ok: true`；D=0、T=0；候选补丁里没有任何既有测试文件 | ✅ |
| D12 禁词/role=status/内联 style/hex 色 | 我逐文件 grep（见 2.4）✅ | ✅ |
| D13 三份新测试无 skip/only/todo；既有测试没删改 | grep 0 命中；scope.json | ✅ |
| D14 npm test、typecheck、G01、R01 全绿 | **内核 checks/01 在固定候选上真跑**：G01 exit 0（`15 passed`）、R01 exit 0（`889 passed in 1211.38s`）、V01 exit 0（`Test Files 110 passed / Tests 1013 passed`，含三份新测试 9+3+3）、V02 exit 0（无输出）；四条 `output_must_match` 均 matched | ✅ |

## 4. 内核检查与门禁记录核对

- 四条必需检查：`checks.json` 里 `covers_all_required: true`、`all_required_passed: true`、`modified_by_checks: false`、`candidate_files_modified: []`、`unexpected_files_by_checks: []`；退出码全是 0，没有被管道掩盖的退出码（内核自己跑，不用执行端那条 `| tail -n 15`）。
- **执行报告自述 × 内核摘要线索**逐条对上：
  - 摘要里的「可疑命令」`cd desktop/web && rm -f .ci.log && time npm test 2>&1 | tail -n 15`——退出码确实被管道掩盖，但内核在同一候选树上独立跑了 `npm test`（exit 0、`Tests 1013 passed`），结论不依赖执行端自述 ✅；`.ci.log` 是工作目录内的相对临时文件，没进候选 ✅。
  - 摘要里的「新增被 Git 忽略的路径」`.pytest_cache/`、`desktop/web/dist/`、`desktop/web/node_modules/`——都是 git 忽略的构建/缓存产物，不在 `scope.json` 的 8 个文件里、也不在候选补丁里 ✅；执行报告写了 `npm ci` 装依赖（package.json / package-lock.json 字节未动，G01 的 P1 已断言且通过）✅；`dist/` 来自 `npm run build`，执行报告没提，但它是忽略产物、不影响候选，不构成自述不实。
  - 执行报告 md 里 D14 写 `partial`、JSON 里写 `done`——两处不一致，但方向是**保守**（自述比实际更悲观）；内核已把 R01 全量跑完（889 passed），D14 实际成立 ✅，不算自述不实。
- 战后门禁：白盒 6 条（4 静态 + 2 探针）、logic 探针 15 条 it、pages 探针 3 条 it、变异 25 条。

## 5. 门禁端声明的「等价变异」逐条裁定

| 变异 | 门禁的声明 | 我的裁定 |
|---|---|---|
| **M15**（union 里 `'reconnecting'` 改名 `'retrying'`） | 「设计上只有静态断言能抓（类型层改动，运行时不红）」 | **成立**。类型层改动确实没有运行时表现；白盒静态断言 `test_static_connection_union_and_exports` 的 fullmatch 抓得住，实机 M15 exit 1（caught）✅。 |
| **M19**（`return pushed ?? initial;` → `return pushed;`） | 「在探针的单例残留下运行时等价——真实模式首渲染读到 core 残留快照，不崩也不变行为」 | **不成立（声明与证据矛盾）**。内核的变异记录 `mutations.json` 里 **M19 的 status 是 `caught`、exit_code 1**；`M19.log` 里两条都红了：静态断言 `assert 'return pushed ?? initial;' in code` 失败，pages 探针 `TypeError: Cannot read properties of null (reading 'find')`（`AttemptDetailLive` 第 91 行）。也就是说这个变异**测得出来**，不是等价变异；「core 残留快照」的推理只在探针文件的用例顺序下成立，真实首渲染（还没推送）时 `pushed` 为 null，会直接崩。 |

**是否要退回战后门禁**：不退回。理由：门禁的**结论**（无 candidate_defects、覆盖够）是对的——25 条变异 `caught 25 / missed 0 / skipped 0`，M19 也确实被抓住；出错的只是门禁**报告叙述**（§5/§6 与交付信第 ② 条说「有两条测不出来」），属陈述过时，不是白盒测试或变异清单不够。按角色规则，「白盒测试或变异清单不够」才退回战后门禁，这里不存在缺口，所以只写进报告与下游须知，让门禁端下一轮照实际记录写口径。

**门禁端说「没法变异」的改动文件**：没有——5 个改动的非测试文件每个都有变异（events.ts 14、connection.ts 3、useLiveStatus.ts 3、OverviewPage.tsx 2、TasksPage.tsx 3 = 25）。逐条看变异点都打在真行为上（开关、序号去重、ok:false 守卫、通知、退避上下限与抖动、error 关流、引用计数、次数写 connection、基线重置、getStatus 门控、error 监听接线、union 取值、两个守卫、夹具门、回退表达式、导入接线、两页覆盖行），**没有**「改了但不测」的文件 ✅。

## 6. 没测到 / 没钉住的地方（不挡）

1. **「最后一个订阅者离开时若状态是 `reconnecting` 就写 `disconnected`」这条合同明写的行为，两边都没断言**。实现是对的（`events.ts` 退订分支），但白盒探针与三份包内测试都没有针对它的断言 → 门禁侧覆盖缺口（非候选缺陷）。写进下游须知，建议战后门禁补一条断言。
2. `onError` 不检查「是否已无订阅者」：若在最后一个订阅者退订之后还有一条 `error` 事件到达，会再排一次重连并建一条**没有订阅者的流**（服务端会白占一个订阅名额，上限是全局 16 / 每会话 4）。**触发路径在真浏览器里不可达**：HTML 规范里 EventSource 在 `readyState === CLOSED`（`close()` 之后）不再派发 error 事件；只有假流/测试桩才可能触发。按角色规则这属于「几乎不会发生、说不出具体触发路径」的意见，不挡；要防的话加一行 `if (listeners.size === 0) return;` 即可。
3. `ok:true` 但 `data` 为 null 时不覆盖数据（`push.data != null` 才替换）：合同未涉及这种情况；真服务端 `ok:true` 的 status 信封 `data` 必非 null（`kernelenvelope.ts:71` 写 `"data": ...`），不构成现实缺陷。
4. 执行端解读 1：`createLiveEvents` 直接写 connection.ts 的状态源与次数（不再由默认实例包一层），把合同里「纯逻辑」的措辞拉宽了一点。影响面：纯实例也会写全局连接状态（应用里只有默认实例，行为无差；包内测试自己在 beforeEach/afterEach 复位）。UI 仍只从 connection.ts 读、次数没进胶囊 ✅，与合同的兼容性条款一致。
5. 执行端解读 2：合法但 `ok:false` 的 snapshot 写 `connected`、重置基线与次数，但不覆盖数据、不通知。合同对 ok:false 只约束「数据 + 通知 + 序号推进」，这三项都满足；「流通了就写 connected」是合理默认，已在执行报告写明 ✅。
6. 合同层面的 UX 尾巴（不是本片缺陷）：退订时写 `disconnected` 会让 `App.tsx` 的 `offline = state === 'disconnected'` 变真、外壳横幅与胶囊显示「已断开」，直到传输层下次写回 `connected`。合同明写「以最后一次为准、不加仲裁」，本片照做无错；但真机上「流断线后离开页面」会出现外壳说断开、服务其实在。留给下一片/合同端。

## 7. 合同忠实度与范围

- `scope.json`：8 个文件（A5 M3 D0 T0）、`violations: []`、`warnings: []`、`ok: true`；禁改清单（`App.tsx`、`api.ts`、`shell/*`、`live/mode.ts`、`live/transport.ts`、`components/**`、`pages/tasks/**`、`pages/readonly*/**`、`mock/**`、`vite.config.ts`、`scripts/check-live-build.mjs`、`package.json`、`ts/**`）一个都没动 ✅；既有测试文件一个都没改 ✅。
- 依赖：只跑过 `npm ci`（装已锁定的依赖），`package.json` / `package-lock.json` 字节未动（G01 P1 断言通过）✅。
- 合同里「不改 `src/pages/tasks/tasks-data.ts` 与 `src/mock/tasks-live.ts`」「不引 `events.ts`」✅（scope 里没有这两个文件；TasksPage 只是**读**了 `tasks-model.ts` 的 `attemptSeg`）。
- Non-goals 全部守住：没做作业客户端/检索/日志跟随、没动事件页签、没新增顶层 `*Page.tsx`、没新增 mock JSON（`src/mock/` 仍 14 份、`src/pages/` 顶层仍 9 个 `*Page.tsx`）。

## 8. 结论与下游提醒

- **结论: 通过。** 退回：无。阻塞项：无。
- 门禁端下一轮：把「M15/M19 测不出来」的口径改成实测（25/25 全抓住，M19 的实红证据在 `mutations.json` 与 `M19.log`）；补「退订时 reconnecting → disconnected」这条断言。
- 合同端下一版：改 D12 措辞（一审 O1）；可考虑把 `LiveStreamHandle` 的 union 留出 `'error'`。
- 下一片（B1/B2）注意：重连次数没进胶囊是本片的既定取舍；要动胶囊的「事件流」一行先问站主（T034 p7 要先退役）。

Verdict: PASS
