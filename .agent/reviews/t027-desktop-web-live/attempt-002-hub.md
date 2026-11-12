# 复审记录：t027-desktop-web-live attempt-002（七端信箱 hub）

- 合同：t027-desktop-web-live.v4（base 9ae38c97184bf8334af66abda32bc6bbb3fbd198）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261112T192422203629Z-7f68），终审报告如下

## 终审报告

# T027-7-audit-post 终审报告（审核端 audit-sonnet）

## 结论

**返工。退回：执行端。1 条阻塞项**（传输层在读响应体失败时会 reject，违反合同「绝不 reject」）。

其余部分：候选忠实实现了合同 v4 的 A 片，范围干净，测试没有走样，五条检查由内核独立跑出退出码 0，战后门禁 38 条变异全抓住。B1 修好即可封板，不必再动别的。

---

## 一、材料与核对方式

- 合同：`.agent/plans/t027-desktop-web-live.v4.md`（v4，base_sha 9ae38c97…）
- 候选：`.agent/runs/t027-desktop-web-live/attempt-002/candidate.patch`（16 个文件，A9 M7 D0 T0，全文读过）
- 执行自述：`attempt-002/executor-report.md`、`summary.md`、`scope.json`、`checks/01/checks.json` 与五份日志
- 战后门禁：`.agent/mailbox/tasks/T027-6-gate-post/report.md`、白盒源码 `evidence/whitebox-20261112T192127668735Z.py`、变异记录 `evidence/mutate-…/mutations.json`（38 条）
- JEV 判断（`T027-6j-jev/report.md`）：`no_opinion auth_failed` —— 筛查器本轮没给出意见，这一维度无从交叉核对；不影响下面的判断。

内核摘要里的线索逐条对上：「临时路径」`temp_path_uses: []`、`temp_dirs_without_cleanup: []` —— 与执行报告「未使用工作目录外的临时文件」一致 ✓；「可疑命令」`suspicious_commands: []`、`outside_worktree_paths: []` ✓；「12 条命令的退出码被管道掩盖」—— 那 12 条都是探索命令，最终三条 V 检查执行端改用了 `set -o pipefail` 并回显 `$?`（events-summary 的 shell_commands 末三条），且内核自己的 check runner 独立跑出五条检查的实测退出码均为 0（`checks.json` 里 `exit_code: 0`、`output_must_match.matched: true`），所以「reported_exit_code 是推断值」这条不构成阻塞 ✓；「删除了 1 行含断言的代码（新增 130 行）」—— 对应 `desktop/web/tests/readonly2-static.test.ts` 那一条被放宽的断言（合同 D10 授权的唯一一处），不是别的 ✓。

---

## 二、DoD 逐条核对（实现 ↔ 合同）

| DoD | 核对结果 | 依据 |
|---|---|---|
| D01 模式开关与 NODE_ENV 无关 | ✔ | `vite.config.ts` 改函数形式，`define.__THEMIS_LIVE_MODE__ = JSON.stringify(command === 'build' ? 'themis-live-real' : 'themis-live-fixture')`；文件里没有 `import.meta.env` / `process.env`；V03 `LIVE_BUILD_OK 3/3` 实测三种取值各构建一次，产物含 real、不含 fixture、含 `same-origin` |
| D02 模式语义 | ✔ | `mode.ts` 运行时 `import { createLiveClient } from './transport'`，`defaultClient` 懒建缓存；注入优先（`null`=不发请求、`undefined`=清除）；导出集合恰四个（我按源码逐个核过：liveModeIsReal / liveClient / setLiveClientForTests / type LiveClient） |
| D03 传输层成功路径 | **✘ 见 B1** | 相对路径、`URLSearchParams`、GET、`credentials:'same-origin'`、无自定义头、带 signal、时限=服务端+5 秒都对；但「**任何情况下** resolve 成信封、绝不 reject」在读响应体这一段破了（B1） |
| D04 失败分类、状态码优先 | ✔（401/503/其余 4xx/5xx/200 ok:false/坏 JSON 六条文案逐字核对无误；`>= 400` 一律不进「不是合法 JSON」那条） | `transport.ts` 的分支顺序：401 → 503 → 读体 → `status >= 400` 分流 → 2xx |
| D05 信封校验严格 | ✔ | 七字段齐全 + `ok` 布尔 + `exit_code` 数字/null + `data` 键必须在 + 三个字符串数组 + `elapsed_ms` 数字 |
| D06 连接状态 | ✔（但见 B1 的第二条后果） | 两态、初值 connected、同值不通知、退订不通知、`useSyncExternalStore` |
| D07 15 个读函数 | ✔ | 15 条路由/查询/服务端时限逐条对上合同表（15/30/30/60/30/30/30/30/30/30/30/120/120/30/30）；`getAttempt('a/b','x?y')` → `a%2Fb/x%3Fy`；`readFile` 的 `path`/`cursor` 与「cursor 不带不拼」；`?mock=` 不影响真实结果；真实分支里没有 `currentMock()` |
| D08 meta 映射 | ✔ | `pi_dispatch 2.12.0` → `2.12.0`、对不上格式原样；`getMetaNow()` 一字未改（diff 里没有它的 hunk） |
| D09 写操作 501 | ✔ | 10 个写函数 + `getOperation` 全部 `status 501` + 固定信封，不读夹具、不发读请求 |
| D10 common-readers 转出 + 旧测试那一条放宽 | ✔ | 转出语句逐字 `export { getHistoryEntry, getPlugin } from '../../api';`，**前一条语句以分号结尾**（T010 的 `[^;]*?` 不会跨语句）；两个函数的夹具分支逐字搬到 api.ts（command、报错原文 `ERROR 夹具里没有这份数据：…`、深拷贝都一致，api.ts 与 common-readers 的 `read/okEnvelope/missingEnvelope/errorEnvelope` 四个助手逐字相同）；`searchLogs` 真实模式回「ERROR: 检索尚未接通」且 command 数组照旧；旧测试**只改了那一条断言**，新正则与 `tests/test_gate_t010_baseline.py:786-787` 同口径（声明 **或** `export{…}` 含该名） |
| D11 tasks-data / tasks-live | ✔ | 两处 `liveModeIsReal()` 门槛；`subscribeMockEvents` 真实模式返回空函数；夹具模式逐字未动 |
| D12 网络扫描规则 | ✔ | `reports(rel,line)`：`src/live/` 放行、别处照报；成对自检样本在；`prefetchAll`/`fetchedAt`/`globalThis` 与四个网络接口名仍在文件里；`cleanup1-static.test.ts` 未动；我独立 grep：全 `src/` 只有 `live/transport.ts` 出现那四个整词，`src/live/` 无注入词 |
| D13 门禁与回归全绿 | ✔ | 内核实测 G01 `26 passed`、R01 `777 passed`；13 个读函数仍是 `export function 名字(`；`package.json`/`package-lock.json` 不在 diff 里 |
| D14 范围与卫生 | ✔ | scope.json 16 个文件全 in_scope、violations 为空、D0 T0；五份新测试无 skip/only/todo；`readonly2-static.test.ts` 仍 8 条 `it`、`:142` 的 `ExternalLinkIcon` 断言在；`dist/` 被 gitignore |

### 「三个名字都不导出时仍红」的性质（我按源码核，合同 Steps 第 6 步的自测没留痕）

新正则是 `export\s+(?:async\s+)?(?:function|const)\s+${name}\b` **或** `export\s*\{[^}]*\b${name}\b`。第二支的 `[^}]*` 跨不过 `}`，所以这个名字必须真的出现在花括号里；两个名字都不导出时该支不命中、第一支也不命中 → 仍然红 ✔。性质成立，但执行报告没写这条自测（见意见 4）。

---

## 三、门禁与白盒的核对（逐条判断「测不出来」的说法）

- 白盒 13 条（w01–w11 静态锚点 + w20/w21 流水线）在候选上全绿；静态锚点那几条是「读源文件文本」式的，但关键行为另有运行时探针（探针 A 45 条 + 探针 B 3 条）兜着，不算空心断言。
- 38 条变异覆盖 9 个非测试文件 + 两份被改的测试文件，**38 抓住 / 0 漏掉 / 0 出错**，逐文件复原后复跑仍 13 passed；`files_left_modified: []`。
- 但「38/38 全抓住」不等于这一段被覆盖：**白盒的 `res()`（:254-260）与执行端 `live-transport.test.ts` 的 `textResponse` 的 `text` 都是 `async () => body`，永不抛错**，所以「读体失败」这一段两边都没有用例，也没有变异打它 —— B1 就落在这个缝里。这也是我要提 B1 的原因之一：门禁的覆盖率报告在这里给了假安全感。

---

## 四、阻塞项（1 条）

### B1（执行端）传输层读响应体失败时会 reject，违反合同「绝不 reject」

`desktop/web/src/live/transport.ts` 的 `get()`：第一个 `try/catch` 只包住 `doFetch`；第二个 `try` 只有 `finally { clearTimeout(timer) }`，**没有 catch**。`const body = parseJson(await response.text())` 抛错时，异常直接穿出 `get()` → 调用方拿到的是 **rejected promise**，而不是合同 §2 与 D03 明写的「一律 resolve 成 `Envelope<T>`，绝不 reject（调用方不用补 catch）」。

- 触发路径（具体、可复现）：
  1. 本机服务在写响应体途中被关闭/崩溃（用户重启服务、桌面端拆服务、连接被重置）→ 读体中断，`response.text()` 以 TypeError 拒绝；
  2. 响应头先到、响应体迟迟不到 → 我方 `timeoutMs`（服务端时限 + 5 秒）到点，`controller.abort()` 会同时中止响应体流，正在进行的 `response.text()` 以 AbortError 拒绝 → 走不到合同第 1 条「我方中止（超时）」的文案分支，超时反而变成一个 reject。
- 后果：页面落到 PageFrame 的通用错误态（`catch` 分支把 `err` 置 null，界面显示「没有收到服务的回应」），丢掉合同定稿的失败文案；连接状态在 `setConnectionState('connected')` 之后没有机会改回 `disconnected`，B 片的离线胶囊会显示「已连接」而服务已经不在。执行报告「一律 resolve 成七字段信封，绝不 reject」这句自述因此不成立。
- 为什么现有检查没抓到：执行端假响应 `text: async () => body` 永不抛错；白盒 `res()` 同样；38 条变异里没有一条打这一段。
- 要求（只改这一处，不许顺带动别的）：
  - 读体失败必须收场成七字段信封、绝不 reject：我方中止/AbortError → 第 1 条文案 `ERROR: 请求超时（N 秒），没有收到服务的回应`；其余读体错误 → 第 2 条文案 `ERROR: 连不上本机服务（请求没有到达服务）`（若状态码 ≥ 400，也可按第 5 条回 `ERROR: 服务返回 HTTP <码>`，但必须 resolve 成信封）；两种都把连接状态置 `disconnected`。
  - 补用例：假 fetch 的 `text()` 抛错一条；让中止计时器在读体期间到点一条；每条都断言返回的是信封而不是 reject。
  - 不要改：mode.ts 的四个导出、transport 对 `./mode` 只许 type、+5 秒时限、状态码优先、401 去重按实例 —— 这五条已被白盒与 38 条变异钉死。

---

## 五、意见（不挡，由站主决定）

1. **401 的 reauth 去重按「每个 `createLiveClient` 实例一份」实现**，合同写的是「模块内一份」。生产里 `mode.ts` 只建一个缺省客户端并缓存，等价；但后续片若给不同 host 建多个客户端，去重范围会变大。已写进 interpretations 并被白盒钉死，不挡。
2. **`createLiveClient()` 在创建时读 `window.themisHost`**，合同写的是「调用时才取」。缺省客户端是懒建的，首次读请求时能取到；若 B 片在页面挂载之后才设置 `window.themisHost`，需要改成每次 `get()` 时取或另给一个 setter。
3. **`shell-no-network.test.ts` 的成对自检样本用的是 `'src/api.ts'`、`'src/pages/tasks/tasks-data.ts'`（仓库根相对）**，而规则实际比的是**相对 src** 的路径。规则本身是对的（`'live/transport.ts'` 放行、`'api.ts'` 照报），只是样本字符串容易让读的人误以为比的是仓库根路径；建议改成 `'api.ts'` / `'pages/tasks/tasks-data.ts'`。
4. **合同 Steps 第 6 步要求的「三个名字都不导出时仍红」自测没有留痕**（执行报告与 events-summary 里都没有相关命令或结论）。我按源码核过性质成立（见第二节），但下轮请把自测结果写进执行报告。
5. 合同 Repository facts 那句「`tsconfig.json` 不含 `vite/client` 类型」与实际不符（`desktop/web/src/vite-env.d.ts` 里有 `/// <reference types="vite/client" />`）；不影响本片任何 DoD，建议合同端顺手更正（上一轮已提，仍未改）。
6. 401 / 503 分支不读响应体，连接要等 GC 才回收；浏览器里无害，可不改。
7. `setConnectionState('connected')` 在读体之前调用 —— 已并入 B1 一并修。

---

## 六、给下一轮（执行端 / 战后门禁）的要点

- 只带 B1 一条返工：读体失败收场成信封 + 连接状态回 disconnected + 两条用例。
- 已封板、别改：`mode.ts` 四个导出、运行时引入 `createLiveClient`、`transport` 对 `./mode` 只许 type、+5 秒时限、六条定稿文案、状态码优先、信封七字段、401 去重按实例、`readonly2-static.test.ts` 只放宽那一条断言。
- 战后门禁要补：白盒探针里加一条「假响应的 `text()` 抛错」的用例（现有 `res()` 的 `text` 永不抛错），并把这一段加进变异清单。
- 本片 attempt 预算 3（已用 2，剩 1）；wall 预算 21600 秒（已用约 5200 秒），够一次返工。
- 后续片的退役提示不变：写操作接通片要动 api.ts 的 501 信封与 M20/M21、D09 相应断言；SSE 片要动 connection 两态与 M32；检索片要动 `searchLogs`「尚未接通」与 M27/M28。

Verdict: REVISE
