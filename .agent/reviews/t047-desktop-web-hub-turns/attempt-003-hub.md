# 复审记录：t047-desktop-web-hub-turns attempt-003（七端信箱 hub）

- 合同：t047-desktop-web-hub-turns.v4（base be9a03e2af3d3349641724559d5fcf57baba922f）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261117T082212921977Z-6854），终审报告如下

## 终审报告

# T047-7-audit-post 终审报告（audit-sonnet，attempt-003 候选）

## 0. 结论

**通过。阻塞项 0 条，不退回任何一端。**

候选实现忠实于合同 v4 的 D01–D13：改动面恰好 11 个文件（Scope 允许改 9＋允许新增 2），没有碰 forbidden_paths，没有依赖或锁文件变更，主工作区 HEAD 未动；§12 的 T045 三处放宽里除一处「逐字插入必炸」的必然修正外逐字落地；门禁端标「这条命令预期抓不住」的 16 条变异逐条复核为真——每一条都至少被另一条命令抓住，不存在空心基线、空心断言或被弱化的测试。

## 1. 本回合读的材料

- 合同：`.agent/plans/t047-desktop-web-hub-turns.v4.md`（第 1–12 节、Scope、D01–D13、§12.1–12.4）
- 候选：`.agent/runs/t047-desktop-web-hub-turns/attempt-003/candidate.patch`（1366 行，11 个 `diff --git`）、`summary.md`、`executor-report.md`、`executor-report.json`、`observations.json`、`checks/01/{checks.json,R01.log,G01.log,V01–V07.log}`
- 工作目录冻结快照里的实现本体：`desktop/web/src/{api.ts,mock/hub-roles.ts}`、`desktop/web/src/pages/readonly1/{roles-logic.ts,roles-HubPosts.tsx,roles-hub-turns.css}`、`desktop/web/tests/{page-hub.test.tsx,roles-hub-turns.test.ts}`、`ts/packages/ui/src/redaction.ts`、`ts/packages/ui/test/{redaction.test.ts,hub-routes-real.test.ts}`、`tests/test_gate_t045_baseline.py`
- 战后门禁：`.agent/mailbox/tasks/T047-6-gate-post/report.md`、`evidence/mutate-20261117T075244026536Z/{mutations.json,spec.json,16×3 份实测日志}`、`evidence/whitebox-20261117T075243205478Z.py`
- JEV：`.agent/mailbox/tasks/T047-6j-jev/report.md`（no_opinion auth_failed，无意见）

本回合只有只读工具，没跑 pytest；下面的「实测」数字都注明出处（执行端或门禁端的实测记录），其余是我逐字读代码的结论。

## 2. 候选源码逐层核对（先读源码，再看检查与门禁记录）

### 2.1 D01–D13 逐条

| DoD | 我的判定 | 依据（读到的实现） |
|---|---|---|
| D01 | 成立 | `redaction.ts` 新增四个 `export function allowNonNegativeInt/allowToolName/allowIsoSecondUtc/allowEffortLevels`，参数名 `value`；判据逐字照合同（`0n`/`Number.isInteger`/`>= 0`；正则 + `!tokenShaped`；秒级 UTC 正则；逗号拆段 + 七档枚举）。15 条新路径排在原 15 条之后（共 30 条），四层对象（`posts.*.turn`、`posts.*.last_turn`、`posts.*.turn.budgets`、`posts.*.last_turn.thinking`）不登记；注释注明 `kit_roles.py` 的 `_hub_turn`/`_hub_last_turn`、`kit_hub.py:2683`/`:2145`；既有校验函数未动（diff 只增）。 |
| D02 | 成立 | `redaction.test.ts` 只追加一个 describe，既有断言未动；新用例覆盖合格值（`Bash(npm view:*)`、`high,medium`、`Z` 与 `+00:00` 两种秒级时刻、带本机路径的 fallback 原文）与不合格值（-1、1.5、带毫秒、`high,bogus`、令牌形状工具名）。 |
| D03 | 成立 | `hub-routes-real.test.ts` 追加的是真内核用例：在夹具仓库信箱写 `turns/womovie-c8/20261115T080000Z-demo/result.json`（`effort_effective: "high,medium"`、带本机路径的 `quizs_fallback`），断言 `/api/v1/hub/roles` 与 `config hub show --json` 整份 `toEqual`、coordinator 的 600/四工具/预算 32·48、`last_turn` 各字段未被遮、其余五岗位 `last_turn` 为 null。不是假数据自证。 |
| D04 | 成立 | `api.ts` 只增：四个接口 + `HubPostRow` 的 `turn?`/`last_turn?` 两个可选键；既有十字段原样（两空格缩进），`HubRolesData` 未动。 |
| D05 | 成立 | 桩六行的 `turn`/`last_turn` 与合同第 3 节表逐字段一致（coordinator 600/四工具/32·48、planner `Bash(npm view:*)`、gate 七工具、contract fallback 带本机路径、audit/exec 的 null）；十个绑定字段未动——T045 的 S09 结构钉住与 T038 的 PROBE_LIB 都过。 |
| D06 | 成立 | `roles-logic.ts` 只追加：四个归一类型、九个纯函数签名逐字（`hubLastTurnMark` 双参数、`hubFallbackExcerpt` 返回 `{ shown: string; full: string; }`）、归一边界照第 4 节（非对象→null、tools 非数组→[]、thinking 非对象→三个 null、fallback 非字符串→null）；三个既有导出与「只 `import type`」不变。 |
| D07 | 成立 | 十列，三列插在「替补」与「操作」之间；有最近一回合的四行走三值格，audit/exec 照旧 `<EffortPair requested={p.thinking} effective={null} />`（data-state=unknown、文字「要求 X · 生效 未知」）；前六列与「操作」列未改。 |
| D08 | 成立 | 时限 60 整除写分钟否则秒、工具「、」连接；预算 `请求 N · 工具调用 N · 2 / 8 / 8 MiB`，MiB 段单独 span 带 `aria-label="单次输入 2 MiB、单次回应 8 MiB、单个对象 8 MiB"`；最近一回合 `时刻 · 载体 · 模型`，退回替补 warning Tag + 截断显示 + `title` 全文，与当前绑定不同是 neutral Tag。纯函数口径与第 4 节逐字一致（`hubMib` 用 `Math.round(字节/1048576)`，`hubBudgetText` 复用 `hubMib`，没有第二份换算）。 |
| D09 | 成立 | `roles-hub-turns.css` 只有一个规则 `.rl-hub table.tt-table { min-width: 1120px; }`，px 字面量与出处注释同行，无颜色、无令牌声明；`roles-styles.css` 一字节未动（T045/T038 的冻结 digest 过）。 |
| D10 | 成立 | `page-hub.test.tsx` 只改列头断言、思考档位逐行断言与两个 `it()` 标题；`describe('七端岗位（桩模式渲染 #/roles）')` 标题未动；其余用例未动。新增的三列逐格用例逐字断言合同第 6 节给的那些字符串。新文件 `roles-hub-turns.test.ts` 七组齐备（我逐组读过：归一边界、时限、预算、三值、标记、截断、真实模式不出现桩值），测的是真实现，没有把业务逻辑抄进测试。 |
| D11 | 成立 | `roles-HubPosts.tsx` 从 `../../api` 只 `import type`；grep 无 `getQuizsLive`/`tabIndex`/`<a `/`role="status"`/内联 style/`data-role`；新三格里只有 span 与 Tag。 |
| D12 | 成立 | `RolesPage.tsx` 不在候选 diff 里；T038 S04 的并行四读逐字断言在 R01 里绿。本片不读 live、不加证书列。 |
| D13 | 成立 | 候选恰 11 个文件 = Scope 允许改 9 + 允许新增 2，逐条对得上；`tests/` 下只动了 `tests/test_gate_t045_baseline.py`；`package.json`/锁文件未动；主工作区 HEAD 未变（observations.json）。 |

### 2.2 §12 三处放宽的落地

- 12.1（S07 的 docstring 与函数头）：逐字落地，列头断言改成十列数组。
- 12.2（page 探针）：逐字落地为三段式断言（前六列 `slice(0,6)`、第七至九列 `slice(6,9)`、末列是「操作」）——比旧的七列断言更强，不是放松。
- 12.3(a)：桩的字节冻结条目删除，其余五个冻结面一字未动。
- 12.3(b)：新增块逐字落地（`BINDING_FIELDS`/`_WS`/`_skip_string`/`_stub_rows`/`_binding_value`/`_six_rows_ts`/`_mock_stub_problems`），S09 里加 `problems.extend(_mock_stub_problems())`；桩由「按字节冻结」改成「结构钉住」（六个岗位名与行序、十个绑定字段的值逐字不变、仍是普通 TS 字面量），对照的是 T038 的 `SIX_ROWS_TS`，不是按当前文件重算字节再冻结——符合合同「不许按当前文件重算字节再冻结」的要求。
- **唯一偏离**：`read_rel(f"{TESTS_REL}/test_gate_t038_baseline.py")` → `read_rel("tests/test_gate_t038_baseline.py")`。我核了事实：`tests/test_gate_t045_baseline.py:73` 是 `TESTS_REL = f"{WEB_REL}/tests"`（= `desktop/web/tests`），T038 门禁文件在根 `tests/test_gate_t038_baseline.py`（其 601 行确有 `SIX_ROWS_TS`）。逐字插入必抛 `FileNotFoundError`，与 §12.4 自己的「14 passed」验收口径直接冲突。执行端申报了、战後门禁核过并由协调人裁定，白盒 `test_t045_gate_deviation_soundness` 把「逐字插入必炸」钉成了回归断言。**判：成立，不退回。**

### 2.3 没有发现的问题类型

- 没有为过测试而写的特判：九个纯函数与视图里没有出现桩里的具体值（除合同点名的夹具值），实现里也没有 `if (post === 'coordinator')` 之类分支。
- 没有空的异常处理：归一函数对每种坏输入都有明确口径（null / [] / 三个 null），不是 `catch {}`。
- 没有悄悄扩大范围：11 个文件与 Scope 逐条一致；`RolesPage.tsx`、`roles-RolesView.tsx`、`roles-styles.css`、`tests/test_gate_t047_*.py` 都不在 diff 里；依赖与锁文件未动。
- 没有硬编码测试输入：桩里那串带本机路径的 fallback 是合同第 3 节逐字要求的夹具值；服务侧用例走的是真内核路由 + `config hub show --json`。

## 3. 门禁端「预期抓不住」清单的逐条复核

我按「那条命令真的测不到吗」逐条看了实现与实测日志，结论：**16 条声明全部为真，且每条至少被另一条命令抓住**（W2 只覆盖 M6，其余由 W1/W3 覆盖），不存在无人抓的变异。

| 变异 | 声明 | 我的复核依据 | 结果 |
|---|---|---|---|
| M1 删 `last_turn.fallback` 白名单注册 | W2 测不到 | T045 只看共享面与十个绑定字段，不看白名单接线；W1（白盒第 1 例）与 W3（S01）抓 | 声明成立，有抓点 |
| M2 `allowToolName` 去掉 tokenShaped | W1、W2 测不到 | 白盒钉的是路径登记不是函数体；W3 的 `NEW_VALIDATOR_MARKS` 里 `allowToolName` 含 `"tokenShaped"` 记号（第 144 行）＋ts 行为探针 → W3 抓 | 声明成立，W3 抓 |
| M3 `allowEffortLevels` 按分号拆段 | W1、W2 测不到 | 同上，W3 的记号是 `split(",", "trim", "=== null")`＋ts 探针的 `high,medium` → W3 抓 | 声明成立，W3 抓 |
| M4 `HubPostRow.model` 去掉 null | W2 测不到 | api.ts 既有声明逐字由白盒钉；W3 的 S04 钉既有十字段 → W1/W3 抓 | 声明成立 |
| M5 `turn?` 去问号 | W2 测不到 | 同上，可选键记号在 S04 | 声明成立 |
| M6 桩 coordinator 的 provider 改一字 | W1 测不到 | 白盒不钉桩的绑定字段；T045 的 S09 结构钉住（十个绑定字段逐字）与 W3 的 S05 抓 | 声明成立（W2 实测红 4 failed，W3 本轮 `....F.....`） |
| M7 桩 timeout 600→601 | W2 测不到 | 白盒钉桩的 turn/last_turn 关键值（coordinator 600 秒）；W3 的 S05 也钉 | 声明成立 |
| M8 注释掉 css import | W2、W3 测不到 | 我读了 `tests/test_gate_t047_baseline.py:719`：`css_pos = text.find("import './roles-hub-turns.css';")` 是子串 find，被注释掉的 import 仍含该子串 → W3 确实漏（门禁端实测 15 passed）；白盒用 `^import '\./roles-hub-turns\.css';$` 整行正则（whitebox 第 167 行）→ W1 抓 | 声明成立（W1 抓） |
| M9 三值格去掉 data-state | W2 测不到 | W1 钉 `<span className="tt-effort" data-state={hubEffortState(lastTurn)}>`；W3 的 S07 钉三值格形状 | 声明成立 |
| M10 MiB 段去掉 aria-label | W2 测不到 | W1/W3 都钉 aria-label | 声明成立 |
| M11 退回替补 Tag tone 改 neutral | W2 测不到 | W1 钉两个 Tag 的 tone | 声明成立 |
| M12 时限去掉 60 整除分支 | W2 测不到 | W1 钉 60 整除分支记号；W3 的 unit 探针逐值钉（600→10 分钟、45→45 秒） | 声明成立 |
| M13 `hubMib` 换算常数改 1024 | W2 测不到 | W1 钉 `1048576`；W3 的 unit 探针逐值钉（2097152→2、8388608→8） | 声明成立 |
| M16 `hubBudgetText` 把 MiB 写死常量 | W2 测不到 | 我在 4-audit-pre 提的这条变异，白盒钉「`hubBudgetText` 复用 `hubMib`」 | 声明成立 |
| M14 表宽规则降特异性改数值 | W2 测不到 | W3 的 S08 钉 `.rl-hub table.tt-table{min-width:1120px;}` 逐字 | 声明成立 |
| M15 px 出处注释换成无关的话 | W2、W3 测不到 | W3 的 S08 只查 px 行「有注释」（第 217 行取 `/*…*/` 但不查内容）→ 确实漏；白盒第 218 行断言注释里含「画布」（合同第 5 节给的样例措辞）→ W1 抓 | 声明成立（W1 抓） |

结论：**门禁端声明的等价性成立，没有需要退回战後门禁的项。** 白盒是本轮新增的 `tests/test_gate_t047_whitebox.py`（7 例，全静态 0.05s），它抓的正是基准里被子串/记号放过的洞；两条「只有 W1 能抓」的变异（M8、M15）实测都红（W1 日志 3485/3171 字节的失败输出）。

一个残留的口径问题（不挡）：T047 基准的 css import 检查是子串 find，注释掉的 import 照样过 W3——门禁端自己已披露并用白盒整行正则补上。若 T048 再接新样式表，建议直接按白盒的整行正则写，别再留子串检查。

## 4. 内核摘要线索与执行报告自述的逐条对照

内核摘要给了 4 类线索，我逐条对上了执行报告：

1. **临时路径（2 处命中）**：`cd ts && cat > /tmp/dbg.mjs <<'EOF'` 与 `bun /tmp/dbg.mjs`（事件流 8628 行）。执行报告**没有提到这两个临时文件**——这是一条「自述遗漏」的发现：报告的「运行事实」只讲了工作目录干净与各项检查，没有申报自己写过工作目录之外的临时脚本。**判：不挡。** 理由：这是诊断 pyjson/redaction 行为的草稿脚本，没有进候选（candidate.patch 恰 11 个文件，无 `/tmp`、无 `C:\Users\Administrator`、无真实本机路径），不影响任何检查结果（合同各检查的退出码在 checks.json 里逐条为 0），不涉及凭据，也没有外部数据派生内容落进候选。它是过程纪律问题（临时文件应放在工作目录的 `.agent/runs/_scratch/` 一类被忽略的位置），不是正确性或安全问题，故按「意见」记，不进阻塞项。
2. **工作副本外路径（5 条命令、调用成功）**：`C:\Users\example\.agent\mailbox\quizs\live\minimax\qualification.json`。我核了这 5 条命令的出处（events-summary 第 119–123 行）：它们是 `cd ts && python - <<'EOF'` 的夹具编辑脚本，路径是**字符串字面量**（合同第 2/3 节点名要的 fallback 文本），不是对工作区外文件的读写。**判：扫描器的假阳性，不构成发现。** 候选里这串路径只出现在合同点名的夹具值处。
3. **38 条 `|| true`/管道掩码退出码**：逐条看都是 `ls`/`sed`/`grep` 之类非检查命令；合同要求的每一条检查在 checks.json 里都有独立记录且退出码 0（G01/R01/V01–V07 全 passed）。**不构成发现。**
4. **新增被忽略路径 `.pytest_cache/`、`desktop/web/dist/`**：是跑检查的副产物，git 忽略，未进候选（候选里没有它们）。**不构成发现。**
5. **「删除了 5 行含断言的代码（新增 125 行）」**：逐行核过，删除的 5 行全部落在合同第 6 节允许改的 `page-hub.test.tsx` 两处断言（旧 it 标题、七列断言、think 数组、两条 EffortPair 断言）内，换成了更强的十列/三值断言；禁改的 `roles-hub-logic.test.ts`、`page-app.test.tsx` 不在 diff 里。**不构成发现。**
6. **执行器申报的 2 处合同矛盾与 8 处自行判定**：我在第 2.2 节核了第 1 处（§12.3(b) 路径），成立；第 2 处（站主「实现保留、不要重写」vs 干净基线 worktree）属实且与合同不冲突。8 处 interpretation 我逐条对过第 4/5/11 节：①非数字 `timeout_seconds` 按 null 显示「—」符合第 4 节归一口径；②三值格按 `' · '` 拆段、显示文字与纯函数逐字一致；③预算格拆整句只包第三段、文字与纯函数逐字一致；④空格间隔是合同未定处的合理默认；⑤⑥⑦是写法形状（`};` 收尾、`HubPostLastTurn` 排在 `HubPostLastTurnThinking` 之前以免门禁 `find` 命中前缀、两个签名按门禁正则微调），都不改口径；⑧React key 用整段文字，三段互不相同。**判：无越界、无弱化。**

## 5. 执行报告里 DoD 自述的核对

D01–D13 的自述逐条与候选源码对得上（见第 2.1 节），没有一条「报 done 但代码里没有」；自述里引用的证据（R01/G01/V01–V07）都有对应的日志与退出码。唯一与自述有落差的是第 4 节第 1 条（临时文件未申报），已按意见处理。

## 6. 发现与意见（都不挡）

1. 临时文件写到工作目录之外（`/tmp/dbg.mjs`）且执行报告未申报——过程纪律问题，候选干净、结论不受影响。建议后续执行端把草稿放在工作目录的被忽略位置并在报告里申报。
2. T047 基准的 css import 检查是子串 find（W3 漏 M8）；M8/M15 目前只有白盒能抓。白盒留在了仓库里当回归测试，可以接受，但 T048 接线新文件时按白盒的整行正则写。
3. 白盒与基准把候选的部分实现形状钉死了（如 `data-state={hubEffortState(lastTurn)}`、注释含「画布」、十列表头），T048 动同一批文件时这些钉子会变红——那是「正当改动」还是「放松断言迁就实现」需要人判，别默默改白盒。

## 7. 下游须知（T048 片二·证书列）

见交差信的「下游须知」四条：T048 的合同要像 §12 那样显式授权放宽 `tests/test_gate_t047_baseline.py`（十列表头钉死 + page 探针），否则 T048 会被自己的旧门禁挡死；白盒的逐字钉子要逐条判；我在 4-audit-pre 提的 S10 放宽（RolesPage.tsx / roles-styles.css 整份冻结、以及「RolesPage 里不许出现 getQuizsLive」这条全局否定）仍待站主在 T048 开工前处理。

Verdict: PASS
