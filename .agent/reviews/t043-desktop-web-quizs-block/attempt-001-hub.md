# 复审记录：t043-desktop-web-quizs-block attempt-001（七端信箱 hub）

- 合同：t043-desktop-web-quizs-block.v2（base b73da92077dde894a5dfb47bee7d1c46c86a567a）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261115T160701010019Z-1d64），终审报告如下

## 终审报告

# T043 终审报告（audit-sonnet · T043-7-audit-post · attempt-001）

## 结论

**通过，无阻塞项。** 候选补丁（12 个文件）忠实实现合同 v2；DoD D01–D11 每一条都有对应的测试与断言支撑；没有弱化既有断言、没有为过测试而写的源码特判、没有悄悄扩大的改动面。四条不挡的意见记在第 6 节。

---

## 1. 材料与方法

- 合同：`.agent/plans/t043-desktop-web-quizs-block.v2.md`（v2，base_sha `b73da920`）
- 候选补丁：`.agent/runs/t043-desktop-web-quizs-block/attempt-001/candidate.patch`（12 个 diff header）
- 执行概述 / 执行报告：`summary.md`（状态 NEEDS_REVIEW、候选树 `73b636a7`、越界 0、警告 0、6 个工具错误）、`executor-report.md`（D01–D11 全报 done、2 处 contract_conflicts、4 处 interpretations、2 条 limitations）
- 战后门禁：`T043-6-gate-post/report.md`（结论「通过，无候选缺陷」；白盒 11 条全绿；变异 41/41 杀灭、0 漏、0 等价）
- JEV：`T043-6j-jev/report.md` → **no_opinion / auth_failed**，本回合没有筛查意见，核验由我按合同与门禁材料自行完成。

方法：先读候选源码（12 个文件逐个读，不只看补丁），再对合同 Behavior contract 与逐字表逐条对账；然后核对检查与门禁记录；最后把内核摘要的线索与执行端自述逐条对上。

---

## 2. DoD → 测试 → 断言 映射表

| DoD | 由哪条测试证明 | 证明它的那条断言 | 备注 |
|---|---|---|---|
| **D01** 两个读函数两分支 | `desktop/web/tests/live-api.test.ts`（ROWS 新两行）；G01 `test_s01_api_quizs_read_functions`；白盒 `test_w01_api_branches_and_types` | ROWS 行 `{name:'getQuizsProviders',path:'/api/v1/quizs/providers',timeout:60}` 与 `getQuizsLive`/`/api/v1/quizs/live`/`150`；白盒逐字 `if (client) return client.get<QuizsProvidersData>('/api/v1/quizs/providers', undefined, 60);`（同 live 150）——「不回落桩」由这条逐字断言钉住；桩命令逐字 `read(['config','quizs','providers','--json'], () => quizsProvidersEnvelope())` | 桩的 `?mock=loading/error` 由 `read()` 既有行为承担（G01 unit 探针 + page-quizs 的 `?mock=loading`） |
| **D02** 只用白名单字段 | G01 `test_s02_mock_quizs_fixture`；白盒 W01/W02 | 白盒：Quizs 类型区段不得出现 `live_dir/build_id/issued_at_ms/capabilities/credential/id:`；夹具区段不得出现前四个；列头恰四列（无「档案 id」） | 服务端形状我独立核过 `ts/packages/ui/src/redaction.ts:150-176`（`QUIZS_PROVIDERS_ALLOW`/`QUIZS_LIVE_ALLOW`）与 `quizs-routes.test.ts:24-30` |
| **D03** 并行三条、只有 runtimes 失败整页失败 | `page-quizs.test.tsx`（「?mock=loading 挂起」「?mock=empty 空态」「注入 runtimes 失败：整页出错」）；G01 `test_s03_runtimes_page_parallel` + page 探针；白盒 W03 | 白盒逐字 `Promise.all([getRuntimes(), getQuizsProviders(), getQuizsLive()])…`、`if (!runtimes.ok || runtimes.data == null)`、`data: { runtimes: runtimes.data, quizs: { providers, live } },`；行为断言 `expect(frame()…'data-page-state')).toBe('error')` 与 `expect(pageRoot()).toBeNull()` | 「并行」本身只有文本级断言（无时序断言），人工可核 |
| **D04** 区块位置、列数、DOM 规矩 | `page-quizs.test.tsx`；G01 S04/S05 + 双探针；白盒 W04/W05 | `expect(titles.slice(0,2)).toEqual(['已登记','就绪检查'])`、`expect(titles.indexOf('Quizs')).toBeGreaterThan(titles.indexOf('就绪检查'))`、`headsOf(pt)).toEqual(['提供方','模型','思考档位','计费'])`、`headsOf(lt)).toEqual(['提供方','来源','状态','证书到期','档案有效期','下一步'])`、`expect(qa(sec,'button')).toEqual([])`、`expect(qa(sec,'[role="status"]')).toEqual([])`、`expect(qa(sec,'[style]')).toEqual([])`、每个 section 的 `aria-labelledby` 指向 H2 | 独立 grep 复核：本片文件无 `<button`/`DisabledAction`/`role="status"`/`style={{` |
| **D05** 逐字表 | `quizs-logic.test.ts`（11 条）；`page-quizs.test.tsx`（ok/expired/missing/empty/broken 五个情景）；G01 S05/S06 + 探针；白盒 W05/W06 | 计费三值 + 认不出原样；状态七值与色调（`liveStateLabel('expired')` → `{label:'已过期',tone:'danger'}`，就绪 `success`）；来源两值；七句下一步；missing 追加；`nextStepCell('不用动','P1','S1')` → `'不用动；P1；S1'`、`nextStepCell('',null,null)` → `'—'`；两条空态文案 | 拼接顺序（下一步文本 → problem → status.problem）由 `nextStepCell` 的参数序与 W05 的逐字调用共同钉住 |
| **D06** 三条错误路径 | `page-quizs.test.tsx`（注入 providers 失败/退出码 null/注入 live 失败/broken）；G01 page 探针；白盒 W05 | `'Quizs 跑不起来'`、`'命令 config quizs providers --json 返回退出码 1'`、`'命令 config quizs providers --json 没有返回退出码'`、`'没能读到 Quizs 的 live 套'`、`'命令 config quizs live --json 返回退出码 4'`、messages 逐行（`E-ONE/E-TWO/E-NULL/E-LIVE`）、broken 时每套 `'看这一套自己的问题；quizs live status 失败（退出码 127）：'` 且整页仍 `'data'` | 「坏不影响另两节」由 `sectionNamed(pageRoot(),'已登记')`/`'就绪检查'` 仍为真 + `'data-page-state'` 为 `'data'` 证明 |
| **D07** 时刻经 formatLocalUtc | `quizs-logic.test.ts`；`page-quizs.test.tsx`；R01 的 T013；G01 S10；白盒 W10 | `formatMsUtc(null)`/`('not-a-number')`/`NaN` → `'—'`、`formatIsoUtc('not-a-date')` → `'—'`；页面断言用 `formatLocalUtc(new Date(1790000000000).toISOString())` 现算，不写死本地时间；我独立 grep 本片文件：「（UTC 」零命中 | |
| **D08** 新代码守既有规矩 | R01 的 T006/T009；G01 S07/S10；白盒 W07/W10 | 白盒：CSS 基线全文逐字保留、只在末尾追加、quizs 区只用令牌、无 `border-radius`、无 `900px`、无 `text-align: right`、无十六进制颜色/颜色函数、五个 `.rt-quizs-*` 类都要在 QuizsBlock 里用到（未接线＝没进产品）；新文件禁词表零命中 | 我独立 grep 复核网络词/危险 HTML/`matchMedia` 类/颜色字面量/「（UTC 」：零命中 |
| **D09** 既有测试未删未弱 | R01（含 page-app.test.tsx、readonly2-app.test.tsx）；G01 S08；白盒 W08/W08b | `page-app.test.tsx:98` 仍是 `expect(disabled().length,'运行时页').toBe(5)`（该文件不在改动面内）；白盒：live-api 的 ROWS 恰 19 行且基线 17 行名单与顺序逐字、`page-runtimes.test.tsx` 恰 4 处 `<RuntimesView …>` 每处都带 `quizs=`、`writes-remove.test.tsx` 恰 1 处；两个新文件禁 skip/only/todo/xit/xdescribe | 既有断言锚点（七列列头、五个 runtime 名、删除对话框文案）白盒逐个核过 |
| **D10** 改动在允许集合内 | G01 `test_s09_shared_surfaces`；白盒 W09；补丁 diff header 核对 | `src/mock` 恰 14 份 JSON、`src/pages` 顶层恰 9 个 `*Page.tsx`、`package.json`(820B)/`package-lock.json`(108793B) 摘要与基线一致；补丁的 12 个 diff header 全在合同的 7 改 + 5 新之内，无 forbidden_paths | 我按补丁逐个 diff header 核对过 |
| **D11** 九个纯函数都有测试 | `quizs-logic.test.ts`；G01 S06；白盒 W06 | 覆盖 `billingLabel/liveStateLabel/liveSourceLabel/liveNextStep/nextStepCell/formatMsUtc/formatIsoUtc/providersUnavailable/liveUnavailable`，含 null、非法值与 `<redacted>`/`weird` 认不出值 | 白盒另钉两个判定函数体恰为 `return !env.ok \|\| env.data == null;` |

**只能人工审阅的项（合同未定，测试也钉不了）**：
1. `.rt-quizs-table` 容器不声明 `border-radius`（合同第 8 步「照 .rt-table 那三条」与 G01 S07「border-radius 只许 var( 开头」冲突）——合同端与门禁端均已裁定放行，视觉上容器保留 `.tt-table-wrap` 自己的圆角。
2. missing 状态「补齐缺的文件」与「缺 qualification.json」之间的分隔符用「：」——合同端在下游须知里明写「合同没钉，执行端自选一个即可」。
3. live 表 `rowKey` 用「来源 + 1 起始行序」、提供方档案 `rowKey` 用提供方名（重名加序号）——合同未定。
4. broken 情景 providers 的报错原文写成情景说明「ERROR: 没有设置 QUIZS_CMD，读不到 Quizs 提供方档案」（不冒充内核原文）——合同明写不许编造内核原文。
5. providers 失败时错误块放在提供方档案表的位置（即合同所说「区块顶部」）——合同未细化排布。

---

## 3. 全绿不等于对：候选源码逐处核对

**api.ts**：只新增（补丁四个 hunk 全是 `+`）：5 个类型 + 2 个读函数 + 1 条 import，既有导出与签名一个没动。真实分支 `if (client) return client.get<…>(path, undefined, 60|150)`——**不回落桩**；桩分支走 `read(command, produce)`，`read()` 的 `loading/error` 先于情景（我读过 `api.ts:386-390`），produce 忽略 mode、按 `?quizs=` 取信封，与合同「其余模式由 ?quizs= 选情景」一致。类型用 `string` 收枚举（`<redacted>` 不会被类型挡在外）✓。

**RuntimesPage.tsx**：`Promise.all` 三条；失败分支按七字段重建信封并置 `data: null`；成功分支 `data: { runtimes, quizs: { providers, live } }`，两个 Quizs 信封整个放进去；`isRuntimesEmpty` 只读 runtimes 长度（参数写成超类型，未起类型别名，符合合同「不许另起别名」）；`children` 仍是 `(data, reload) =>`；页头两个按钮、`PageFrame` 用法一字未动 ✓。

**runtimes-RuntimesView.tsx**：`quizs` 必填、内联字面形状（`{ providers: Envelope<QuizsProvidersData>; live: Envelope<QuizsLiveData> }`），无类型别名 ✓；`QuizsBlock` 挂在「就绪检查」之后、`WriteFlow` 之前 ✓；既有两节一字未改 ✓；只 `import type` 自 `../../api` ✓。

**runtimes-QuizsBlock.tsx**：只收数据、无按钮、无 `role=status`、无内联 style、不嵌 section；两张表用 `Table`，`className="rt-quizs-table"` 且不带 `rt-table`（因此 `.rt-table` 的「最小宽 900px」「末列右对齐」两条规则结构性不生效）✓；提供方档案四列、live 六列，问题文字并进「下一步」列，没有第七列、没有操作列 ✓；错误路径三条按合同写（providers 失败→顶部「Quizs 跑不起来」+命令+退出码+messages；live 失败→只在 live 位置；两封都坏→每套「读不出」+各自 problem）✓。

**runtimes-quizs-logic.ts**：九个纯函数，逐字表与合同一致；`nextStepCell` 的拼接顺序（problem 在前、status.problem 在后，中间接「；」）与合同的逐字表一致；两段都空返回「—」；时刻一律经 `formatLocalUtc` ✓。纯函数不碰 DOM、不引计时器 ✓。

**mock/quizs.ts**：`.ts` 夹具、纯类型导入；`quizsScenario()` 只认 `quizs` 一个键、缺省或认不出按 `ok`；五个情景的信封形状与合同第 3 步一致；broken 的 providers 信封 `ok:false/exit_code:1/data:null/messages 一行以「ERROR: 」开头`，live 照常 `ok:true/exit_code:0`、两套 `status:null` 且各带 problem ✓；每次调用新建对象（桩数据不会互相改坏）✓。

**runtimes-styles.css**：只在末尾追加 5 条 `.rt-quizs-*` 规则，基线 20 行逐字保留（白盒 W07 用基线全文比对）；只用令牌；`border: 0` 与 `1px` 属 T009 豁免值；无颜色字面量 ✓。

**测试**：`page-quizs.test.tsx` 走真实 `App` 挂载 + `?quizs=` 情景，失败路径用 `setLiveClientForTests` 注入替身（**不 mock 被测实现**，替身只顶替网络层）✓；`quizs-logic.test.ts` 直接测纯函数 ✓；两个既有测试文件只加夹具与属性参数、既有断言一条没改 ✓。源码里没有任何 `import.meta.env`/`vitest`/`process.env` 分支（我 grep 过整个 `src`）✓。

---

## 4. 门禁端证据的裁定

- **41 条变异全杀灭**：我抽查了白盒文件的断言网（W01–W10b），确认它是精确文本/结构断言，且每条变异的锚点都落在被钉住的区域上；白盒里另有「五个 `.rt-quizs-*` 类都要在 QuizsBlock 里用到」这类**接线断言**，杜绝了「CSS 写了但没进产品」的空心问题（T009 的老教训）。声明无等价、无 expect_missed、无 unmutated，与文件内容相符 ✓。
- **未变异的 5 个文件是测试文件**（mutation-spec 的口径：非测试文件才有变异）。我判断这 5 份不需要变异：它们本身是断言的来源，变异测试文件只会测「断言本身会不会被改」，不属于「实现有没有被测到」；且其中三份由 W08/W08b 用名单与锚点做了逐字核对 ✓。
- **执行端自报的两处 contract_conflicts**，与门禁端的独立核验一致，我逐条复核：
  - 矛盾 1（describe 标题 16→18 与 T038 的「16 个读函数」子串断言冲突）：采用方案是加一行事实注释；**没有删改任何断言**，白盒 W08 还额外钉住「剥掉注释后全文不再出现该串、且该串恰出现一次」。我查了 `tests/test_gate_t038_baseline.py:496`，那条断言是 `if "16 个读函数" not in text:`（子串），语义是「基线 16 个读函数都在表里」，仍然为真 ✓。**不构成钻空子**（见第 6 节第 1 条的附带建议）。
  - 矛盾 2（`.rt-table` 的 `border-radius: 0` 与「border-radius 只许 var( 开头」冲突）：采用不声明 border-radius，视觉上容器保留 `.tt-table-wrap` 自己的圆角；T009 的「去圆角」意图部分落空，但令牌里确实没有 0 圆角，且门禁只允许 var()，取舍合理 ✓。
- **四处 interpretations**（broken 文案、missing 分隔符、「不用类型别名」下的 `isRuntimesEmpty` 超类型、live 行键）：逐条核对源码，与自述一致，无越白名单、无弱化断言；其中前两条合同端已明写可由执行端自选 ✓。
- **门禁端自报的局限**（npm 行为面未在其工作目录复跑、无 node_modules、需联网的 bun install 不做）：行为面由内核 fresh 工作区实测背书（G01 14 passed、V01 1119 passed、V02、V03、R01 985 passed、scope 0 违规、落地预演 999 passed），白盒负责源码级边界，职责划分合理 ✓。

---

## 5. 执行端自述 ↔ 内核线索对账

| 内核摘要里的线索 | 执行报告的自述 | 是否对得上 |
|---|---|---|
| 「临时路径：事件流第 11874 行 `cd desktop/web && npm ci > /tmp/npmci.log 2>&1; …`」 | limitations 第 2 条：为了跑 V01/V02/V03 在 `desktop/web` 跑了 `npm ci`，产物 `node_modules/` 与 `dist/` 都是 gitignore 产物 | **对得上**：npm ci 这件事被如实交代了；日志落在系统临时目录这件事报告没写，但它只是 `npm ci` 的输出重定向，不改候选内容（补丁里没有 node_modules/dist，git status 恰 12 项）。不算自述不实。 |
| 「新增被 Git 忽略的路径：.pytest_cache/、desktop/web/dist/、各 node_modules/」 | 同上（gitignore 产物） | 对得上 ✓ |
| 「执行器报告了 2 处合同矛盾」 | contract_conflicts 两条 | 对得上 ✓（第 4 节已逐条裁定） |
| 「执行器自行宣布了 3 处解读」 | interpretations 4 条（summary 说 3、报告列 4，以报告为准） | 对得上，数量差 1 是 summary 的概括口径，不影响裁定 ✓ |
| 「掩盖退出码的写法 14 条（例如 `ls tests \| grep t043; wc -l …`）」 | 未在 limitations 里提 | 这些都是探查/查看命令，不是测试或检查命令；**检查命令本身**（G01/V01/V02/V03/R01）用的是 `set -o pipefail; … \| tail -n 40`，退出码未被掩盖 ✓ |
| 执行端自报「探查期间几次 bash 写成 `cd -`，OLDPIR 指向主检出 `C:\Code\ThemisTally`，只读查看了两份门禁文件」 | 同一条 limitations | **自述属实**，且是主动披露。影响评估：只读、无写入；候选内容与主检出无关（内核 fresh 工作区独立复跑全绿、scope 0 违规）；**不构成阻塞项**，但按流程记一笔。 |

**结论：没有「DoD 自述不实」的情况。** D01–D11 全部报 done，逐条与源码、测试、门禁记录对得上。

---

## 6. 发现（不挡的意见，按站主裁量）

1. **T038 的「16 个读函数」断言已被一条事实注释顶住（门禁端的事）**：`live-api.test.ts` 标题按合同改成 18 之后，T038 那条子串断言只剩文件第 5 行的注释能满足。断言没被删改、语义仍为真，所以不挡本片；但**将来谁清理这行注释，T038 会以一条看不懂的红报出来**。建议门禁端在后续门禁补丁里把 T038 那条改成按 `ROWS` 的实际行数/名单核对（或改成 18）。
2. **provider 行的 `thinking`/`billing` 缺键没有兜底**（`QuizsBlock.tsx` 的 `row.thinking.length > 0` 与 `billingLabel(row.billing)`）：合同「边界输入」写的是「字段为 null / 缺键 / 不是预期形状时一律按兜底显示，不抛错、不整页崩」。触发路径：服务端某一行 provider **缺 `thinking` 键**（T042 的白名单只是「放行」，不会替内核补键）→ 渲染期 `TypeError` → 整个运行时页崩；`billing` 缺键则渲染成空格而不是「—」。概率很低（内核的 Quizs providers 每行都带 `thinking`，`quizs-routes.test.ts` 的样本也是），修起来是一行（`row.thinking?.length` / `billingLabel(row.billing ?? '')`）。按「说不出必然发生的路径」的口径写成不挡意见，请站主决定做不做。
3. **执行端探查阶段有只读访问落到主检出**（`cd -` 的 OLDPIR 指向 `C:\Code\ThemisTally`，只读看了两份门禁文件）。候选内容与主检出无关、内核已独立复跑，不挡；但流程上应记一笔（下一片的执行提示里可提醒先 `pwd` 确认工作目录）。
4. **门禁产物未进候选补丁**：`tests/test_gate_t043_whitebox.py` 与仓库根的 `mutation-spec.json` 都在工作目录里，但都不在候选补丁的 12 个文件里。合入时只取补丁，别把 `mutation-spec.json` 带进仓库（它自己写着「不进仓库」）。

---

## 7. 只能人工审阅的项

见第 2 节末尾五条（圆角取舍、missing 分隔符、行键规则、broken 报错原文、providers 失败块的排布位置）。这五条合同没钉，测试也钉不了；合同端与门禁端均已明示可由执行端自选。

---

## 8. 证据路径

- 候选与执行证据：`.agent/runs/t043-desktop-web-quizs-block/attempt-001/{candidate.patch,summary.md,executor-report.md}`
- 合同：`.agent/plans/t043-desktop-web-quizs-block.v2.md`
- 战后门禁：`.agent/mailbox/tasks/T043-6-gate-post/report.md`、`evidence/whitebox-20261115T160338175208Z.py`、`evidence/mutate-20261115T160338935190Z/mutations.json`
- JEV：`.agent/mailbox/tasks/T043-6j-jev/report.md`（no_opinion / auth_failed）
- 我读的候选源码（本工作目录）：`desktop/web/src/{api.ts,mock/quizs.ts,pages/RuntimesPage.tsx,pages/readonly1/runtimes-RuntimesView.tsx,pages/readonly1/runtimes-QuizsBlock.tsx,pages/readonly1/runtimes-quizs-logic.ts,pages/readonly1/runtimes-styles.css}`、`desktop/web/tests/{live-api,page-runtimes,writes-remove,page-quizs,quizs-logic}`、`tests/test_gate_t038_baseline.py:496`、`ts/packages/ui/src/redaction.ts:150-176`、`ts/packages/ui/test/quizs-routes.test.ts:24-30`

Verdict: PASS
