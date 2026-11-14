# 复审记录：t038-desktop-web-hub-posts attempt-003（七端信箱 hub）

- 合同：t038-desktop-web-hub-posts.v4（base bf50473d147cced0a0cfbad8e7eb910aa657c3d7）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261114T201216667386Z-450b），终审报告如下

## 终审报告

# T038-7 终审报告（attempt-003，复审封板）

审核端：audit-sonnet · 2026-11-14T20:xxZ · 只读审核，未改任何文件。
本回合性质：上一轮（attempt-002）终审返工后的复审封板——只复核上一轮列的阻塞项 + 本轮新改动的内容。

## 1. 材料

- 合同：`.agent/plans/t038-desktop-web-hub-posts.v4.md`（Scope 允许集 7 个可改文件 + 4 个可新增文件；Behavior contract；第 9 步 CSS 规矩；DoD D01–D11；Rework 段抄了我上一轮的阻塞项原文）
- 候选：`.agent/runs/t038-desktop-web-hub-posts/attempt-003/candidate.patch`、`candidate.stat.txt`、`changes.json`
- 执行概述/报告：`attempt-003/summary.md`、`attempt-003/executor-report.md`、`attempt-003/events-summary.json`
- 内核检查记录：`attempt-003/checks/01/{checks.json,G01.log,V01.log,V02.log,R01.log}`
- 战后门禁：`.agent/mailbox/tasks/T038-6-gate-post/report.md` + 白盒存档（`evidence/whitebox-20261114T195952361151Z.py`、`.log`）+ 内核变异记录（`evidence/mutate-20261114T195953310848Z/mutations.json`）
- JEV：`.agent/mailbox/tasks/T038-6j-jev/report.md`（no_opinion / auth_failed）
- 候选源码（工作目录）：`desktop/web/src/pages/readonly1/roles-styles.css`、`roles-HubPosts.tsx`、`desktop/web/src/components/{Table.tsx,Table.css,Tag.tsx}`、`desktop/web/src/styles/tokens.css`；门禁文件 `tests/test_gate_t038_baseline.py`、`tests/test_gate_t038_whitebox.py`

## 2. 上一轮阻塞项的复核（逐条）

### 阻塞项 1（归执行端）：配置行来源的 profile id 没有真的等宽 —— **已解决**

候选补丁只做了一件事（`candidate.patch` 全文一个 hunk）：

```diff
--- a/desktop/web/src/pages/readonly1/roles-styles.css
+++ b/desktop/web/src/pages/readonly1/roles-styles.css
@@ -67,6 +67,7 @@
 .rl-hub .tt-table { min-width: 760px; } /* 画布：七端岗位表最小宽 */
+.rl-hub .tt-table__mono { font: var(--tt-mono-sm); } /* Table.css 的 mono 规则只命中 td，来源列的 span 自己也要等宽 */
```

我不采信「白盒说绿」就签字，独立核了接线链：

| 环节 | 核对结果 |
|---|---|
| 承载元素 | `roles-HubPosts.tsx:50`：`p.source === 'config'` → `<span className="tt-table__mono">{p.profile}</span>`（写法未改，仍是 span） |
| 祖先链 | `Table.tsx:90`：`wrapClass = className ? \`tt-table-wrap ${className}\` : 'tt-table-wrap'`；`roles-HubPosts.tsx:64` 传 `className="rl-table rl-hub"` ⇒ 渲染成 `<div class="tt-table-wrap rl-table rl-hub">`，span 是 `.rl-hub` 的后代 |
| 规则命中 | `.rl-hub .tt-table__mono` 第二复合体无标签要求 ⇒ 能命中该 span（不再是 `.tt-table td.tt-table__mono` 那种要求类名在 td 上的写法） |
| 是否压得住继承 | `Table.css:29` 的 `.tt-table td { font: var(--tt-text-sm); }` 设在 td 上，span 继承它；span 自己有 `font` 声明 ⇒ 自身声明胜过继承 ⇒ 真的等宽 |
| 令牌存在 | `styles/tokens.css:35`：`--tt-mono-sm: 400 12px/18px var(--tt-font-mono)` ✔ |
| 不误伤缺省行 | 「默认」是 `Tag`，类名 `tt-tag tt-tag--neutral`（`Tag.tsx:21-25`），不带 `tt-table__mono` ⇒ 新规则碰不到它，字体不变 |
| 不误伤模型列 | 模型列 td 带 `tt-table__mono`，由特异性更高的 `Table.css:64` 命中，值相同 ⇒ 无视觉变化 |
| 影响面 | 全仓 grep `tt-table__mono` 只有 4 处：`Table.tsx:106`、`Table.css:64`、`roles-HubPosts.tsx:50`、`roles-styles.css:70`；`.rl-hub` 只出现在这一张表（`roles-HubPosts.tsx:64`）⇒ 不波及其它页面 |

门禁侧（用于佐证，非唯一依据）：白盒 W12「等宽机制必须接到能作用到该元素的规则」与 W13「该规则的 font 声明必须用 `--tt-mono-` 令牌」在候选上 13 passed；内核自己的变异记录 26/26 caught，其中 **M23（整行删掉这条等宽规则）** 与 **M24（把值换成比例字体令牌）** 都被抓住——说明这不是靠类名子串空转的断言（M20 曾因整文件比对被同款模式遮住，门禁端已收紧）。

**裁定：阻塞项 1 已解决，本轮无新增阻塞项。**

## 3. 本轮新改动的内容复核

- **范围**：`candidate.stat.txt` = `1 file changed, 1 insertion(+)`；`changes.json` 记 A0 M1 D0 T0。改的文件 `desktop/web/src/pages/readonly1/roles-styles.css` 在合同 v4 的 `allowed_modified_files` 内；没碰 `forbidden_paths`（`tests/test_gate_t038_*.py`、`ts/packages/ui/**`、`scripts/**` 等）；`package.json` 与锁文件未出现在 diff 里 ⇒ D09/D10 成立。
- **合同第 9 步（CSS 规矩）**：只追加、没改现有规则（diff 上下文行原样）；新行无十六进制颜色、无颜色函数、无 `--tt-` 拼接（只有 `var(--tt-mono-sm)`，正则去掉 var() 后尾部无 `--tt-`）、无 px 字面量 ⇒ 不撞 G01 的 `css_tail_problems`；`css_tail_problems` 那条「追加部分必须有一条 `.rl-hub` 与 `.tt-table` 同在且 `min-width: 760px`」由既有的 `.rl-hub .tt-table { min-width: 760px; }` 满足（该行在基线前缀之后的 tail 区内，门禁 S08 与自检都过 ⇒ 前缀 3779 字节未被改）。
- **测试面**：本轮一个测试文件都没碰；没有删改既有断言、没有 skip/only/todo、没有为了过门禁改断言迁就实现 ⇒ D08/D10 成立。
- **实现质量**：`roles-HubPosts.tsx` 里 `hub.ok && hub.data ? <Table …/> : <div className="rl-hub-err">…` 是合同要的失败信封分支，不是空异常处理；`sourceCell` 的分支是合同要的「配置行→id、缺省行→Tag」；没有为过测试写的特判、没有悄悄扩大的范围。
- **执行自述 vs 内核记录**（DoD 自述逐条对上）：
  - `events-summary.json`：`temp_path_use_count: 0`、`suspicious_commands: []`、`outside_worktree_paths: []`、`parse_error_lines: []`；5 条 `masked_exit_commands` 全是 `grep`/`git show`（`check: false`，不是测试或检查命令），真正的检查命令都写了 `set -o pipefail`。
  - 执行报告主动交代的「编辑工具首次把整个文件行尾改成 CRLF、已用字节级替换还原并复核前缀逐字节一致」与 `candidate.stat.txt`（1 insertion）、G01 的 S08 前缀 sha 校验一致 ⇒ 自述属实，没有「临时路径」或自述不实的迹象。
  - 内核 `checks/01`：G01 exit 0 / `18 passed`；V01 exit 0 / `112 passed (112 files)`、`1052 passed (1052)`；V02 exit 0；R01 exit 0 / `923 passed`。与 executor-report.md 的自检表逐条相符（含命令与结果数字）。
- **战后门禁**：报告结论「候选无合同违反，无 candidate_defects」；本回合输入里**没有**「门禁端举证的候选缺陷」一节 ⇒ 无需逐条裁定缺陷。
- **JEV**：`T038-6j-jev` 为 `no_opinion / auth_failed` ⇒ 无意见可裁，不影响结论。

## 4. DoD → 证据 → 本轮结论

| DoD | 由什么证明 | 本轮结论 |
|---|---|---|
| D01 | G01 S02（api 形状）+ V01 `live-api.test.ts` 读函数表（含 `getHubRoles`） | 成立（本轮未改 api.ts，上轮已核） |
| D02 | G01 S01/S03 + R01（T024/T036 计数：src/mock 恰 14 份 JSON、src/pages 顶层恰 9 个 *Page.tsx） | 成立（未改） |
| D03 | G01 S04/S05 + V01 `page-hub.test.tsx`（并行四读、失败顺序、hub 失败隔离） | 成立（未改） |
| D04 | G01 S10 + V01 `page-hub.test.tsx`（六行六列、`data-post`、位置） | 成立（未改） |
| D05 | G01 逐行断言 + V01 `page-hub.test.tsx` + **白盒 W12/W13（等宽接线 + 等宽值）** | **本轮直接相关**：W12/W13 现在真能证明「样式生效」——M23（删规则）、M24（换值）都被抓住；成立 |
| D06 | V01 `roles-hub-logic.test.ts`（三个纯函数边界） | 成立（未改） |
| D07 | G01 S08/S11 + R01（T024 禁词、T009）；新 CSS 行我逐条核过 | 成立（无十六进制/颜色函数/令牌拼接/px） |
| D08 | V01 + review（本轮未碰任何测试文件） | 成立 |
| D09 | scope：改动文件在允许集内、无 forbidden_paths | 成立 |
| D10 | review/scope：无测试删改、无依赖改动 | 成立 |
| D11 | R01（T009 D09）+ 白盒「桩与页面零出现」；本轮 CSS 行不含该 id | 成立 |

## 5. 结论

**通过**（结论: 通过；退回: 无；阻塞项: 无）。

理由：上一轮唯一的阻塞项已按推荐修法解决且我独立核过接线链；本轮新改动只有一行 CSS，落在合同允许集与 CSS 规矩内；无越界、无弱化测试、无自述不实；内核检查与门禁记录自洽，变异 26/26 全被抓住。

## 6. 遗留（非阻塞，只提醒，不升级为阻塞项）

1. **B 片开工前**仍要退役转场用例 `tests/test_gate_t038_baseline.py:1355` 的 `test_transitional_probe_no_write_entries` 与 trans 探针（合同要求，属 B 片合同范围）。
2. B 片给 `api.ts` 加读函数时，t038 门禁里「16 个读函数」那条断言要同步改（合同第 10 步）。
3. G01 探针的 `isMono` 只认类名子串（空心断言），「等宽是否真生效」如今只由白盒 W12/W13 兜着；白盒文件归门禁端，候选代码不要去引用它。
4. 工作区里留着门禁端的两件产物：`tests/test_gate_t038_whitebox.py` 与根目录 `mutation-spec.json`——都不在 `candidate.patch` 里（候选树未含），提交流程注意别混进候选提交。
5. 合同第 3 步的 `readonly ProfilesData['profiles']` 字面形式过不了 tsc，执行端是绕开的；后续片沿用同一写法即可，别照抄合同字面形式。

Verdict: PASS
