# 复审记录：t013-desktop-cleanup1 attempt-001（七端信箱 hub）

- 合同：t013-desktop-cleanup1.v1（base 009efa081bcdb3b7fddc9c3401d72fe3a5dea38c）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T013 终审报告（T013-7-audit-post）

合同：`t013-desktop-cleanup1.v1` · 候选：基线 009efa0 + attempt-001 执行端改动 · 复核基准：战后门禁 T013-6、JEV T013-6j、站主 Q1 原文、候选源码与测试。

## 结论

**退回（返工）。退回对象：执行端。**

候选在功能、视觉、回归上基本达标：D01–D10 除一处外全部满足，白盒 16 条全绿、18 处变异全被抓，634 条测试、415 条回归、构建与契约检查全过。但**指标卡「待验收」图标形状偏离站主 Q1 的明确拍板**（站主定 `ScaleIcon`，执行端用了 `CircleCheckIcon`）。绑定 DoD D05 未钉形状、战后门禁据此判为「非 D05 违约」——此判断在 DoD 字面上成立；但 D05 未钉形状不等于站主没有决定，站主 Q1 已明确且带理由地选了 ScaleIcon。终审的职责是让交付物对齐站主意图，而不是仅以 DoD 字面为界。该偏离是一行改动、零风险的纠正，故退回执行端返工。

## 阻塞项（唯一）

1. **（执行端）指标卡「待验收」图标改为 `ScaleIcon`。**
   - 现状：`overview-MetricCard.tsx` 的 `CARD_ICON.review = CircleCheckIcon`。
   - 应为：`ScaleIcon`（站主 Q1 原文：「待验收：ScaleIcon，--tt-accent-text」）。
   - 改动：把 `CARD_ICON.review` 改成 `ScaleIcon`，从 `../../icons` 引入 `ScaleIcon`、去掉 `CircleCheckIcon` 的引入（若他处未再用）。
   - 不需动：颜色 `--tt-accent-text`（CSS 已正确，见 `overview-styles.css` 的 `.ov-metric[data-metric="review"] .ov-metric__icon { color: var(--tt-accent-text); }`）、色调条 `--tt-accent`（Q1 的 (c) 已明确待验收色调条仍用 --tt-accent、图标用 --tt-accent-text，候选已符合）。
   - `ScaleIcon` 已存在于 `desktop/web/src/icons/index.tsx:72`，不新增图标，符合 Q1「不新增图标」。
   - 后续：战后白盒断言（`tests/test_gate_t013_whitebox.py` 的 `METRIC_ICONS`）当前钉的是 `CircleCheckIcon`，改后需同步更新为 `ScaleIcon` 再复跑，否则会误红。

## 关键问题：review 图标形状

- **站主 Q1（20261021T211322852348Z-owner-0031d0）原文**：「待验收：ScaleIcon，--tt-accent-text」，并给出理由：这四个图标就是同一分组的状态标签用的图标（domain/attemptStates.ts），卡和标签一致；画布 Main :96–101 也是这个排法；(c) 待验收色调条仍用 --tt-accent、图标用 --tt-accent-text。
- **执行端实际**：`review = CircleCheckIcon`，颜色 `--tt-accent-text`（正确）。
- **执行端理由**：合同 Step 5 只写「图标按 Q1」，Q1 原文未随合同附上；门禁 ASSUMPTIONS 亦写明不指定具体图标。
- **门禁判断**：D05 只要求 16px、aria-hidden、颜色取本卡色调令牌（review=--tt-accent-text，候选正确）；D05 未钉形状，故不列候选缺陷；但承认偏离站主明确决定，交协调人/站主定。
- **终审裁定**：站主已明确拍板，交付物应照此实现。选 (a) 返工：把 `CARD_ICON.review` 改成 `ScaleIcon`（一行改动）。不选 (b) 接受，因为那等于终审单方面推翻站主的明确决定并改写 Q1 记录——越权，且一行即可对齐、成本极低。

## DoD 逐项复核

| DoD | 结论 | 依据 |
|---|---|---|
| D01 共用件 | 满足 | 白盒 d01（copyText 三态+缺省 navigator、三条文字；actionTitle 13 条逐字+hasOwnProperty+表外 null；actorTone 五类且 `tone={actorTone(actor)}`；formatLocalUtc 格式含「（UTC 」+null 且 RelativeTime 的 title 取它；index.ts 只末尾追加，基线 sha 前缀校验）；V02 |
| D02 没有第二份 | 满足 | 白盒 d02：copyText/ActorTag 各一处；三条复制文字、13 条动作说明、带引号 undeclared、「（UTC 」各只在对应共用件；三份重复件已删；overview-logic.actionLabel、history-logic.timeCell 与本地 actorTone/动作表、common-format.formatLocalUtc 均不在（relativeFrom 保留） |
| D03 总览渲染 | 满足 | 白盒 d03 接线 + cleanup1-merge 渲染（动作 title 13 条、执行者五色、相对时间文字与 title、复制三结果） |
| D04 只读二渲染 | 满足 | 白盒 d04：HistoryView 的 at 格用 `<RelativeTime iso={e.at}>`（time+dateTime 原文）；抽屉 dl 时间、插件抽屉复制三结果；cleanup1-merge 覆盖三形态 |
| D05 指标卡 | **部分满足——图标形状偏离** | CSS 卡片/色调条/四卡图标颜色齐备（review=--tt-accent-text ✓）；DOM 顺序 色调条→标签行(16px 图标 aria-hidden)→数字(tt-num)、唯一 tt-num、无内联 style 均满足；唯 `CARD_ICON.review` 用了 CircleCheckIcon，站主要求 ScaleIcon |
| D06 .rt-cmd | 满足 | 白盒 d06：display block、max-width 280px、overflow hidden、white-space nowrap、--tt-mono-sm 同规则 |
| D07 aria-controls | 满足 | roles-PresetsTable 用 useId+行序号：`aria-controls={openName===p.name ? `${diffId}-${i}` : undefined}`、`PresetDiff id={panelId}` 且 `panelId=`${diffId}-${openIndex}``；展开时同源、收起省略、各行互不相同、不用方案名拼 id |
| D08 .ov-row__name | 满足 | 白盒 d08：font var(--tt-mono-md) 且 overflow/nowrap/ellipsis |
| D09 样式表接线 | 满足 | 白盒 d09：readonly1、readonly2 共 9 份 CSS 都能从 src/main.tsx 顺 import 到达 |
| D10 回归与范围 | 满足 | G01（22 passed）、R01（415 passed）、V01/V02/V03 全过；只改允许文件；依赖未动；新测试无 skip/only/todo |

## 执行端 7 条自行决定逐条审核

1. **指标卡图标具体选择**：不合理处见上——review 应 ScaleIcon。其余三枚（running=LoaderCircleIcon 不转、decide=CircleArrowUpIcon、integrate=GitMergeIcon）与 Q1 一致，颜色亦正确。
2. **history-logic.ts 的 timeCell 删除（断言搬家）**：合理。D04 要求 at 格改用 RelativeTime，timeCell 职责被取代；cleanup1-merge 保留了三种形态（解析得 time+dateTime 原文+title=formatLocalUtc；解析不了回落原文且无 title；抽屉 dl 回落原文），是搬家非删减。
3. **common-format.ts 的 relativeFrom 保留**：合理。它不是四样重复件之一，是 readonly2 公共纯函数，删它超范围且会顺带删一条纯函数断言。
4. **overview-logic.ts 的 actionLabel 去掉**：合理。D02 要求 13 条动作说明只出现在 components/actionTitle.ts；page-logic 原用例改测 actionTitle（断言未减），13 条逐字+原型名用例在 cleanup1-shared。
5. **标签行图标与文字间距取 --tt-space-1**：合理。设计稿该段 6px 非仓库令牌，取最近令牌避免新增需出处注释的 px 字面量。
6. **MetricCardProps.group 收窄为 CardGroup**：合理。唯一调用方传的本来就是 CARD_META 的 id，渲染与地址不变，收窄后图标查表无需兜底。
7. **三份删除的 git 操作（git rm + git restore --staged）**：合理。调度器不提交；取消暂存只为让删除在两种 diff 口径可见，工作区内容不变，终态干净（无 dbg/tmp 残留）。

## JEV flags 核实

- **自行解读合同 p=0.96**：属实且是本轮核心。执行端对「按 Q1」采取了自选图标的读法（CircleCheckIcon），虽在报告 interpretations 中列了，但未作为「需站主/协调人决定」的问题上抛，实际与站主已定 ScaleIcon 不一致。此 flag 支持返工。
- **自述完成而无证据 p=0.89**：不成立/不构成阻塞。执行端每个 DoD 都指向了 V02/G01/cleanup* 测试；测试实际存在且 634 条全过、白盒复核取值与接线一致。属报告引用粒度问题，非「无证据」的实质缺失。
- **弱化测试 p=0.51（置信 0.02）**：不成立。timeCell 断言是搬家到 cleanup1-merge 的渲染用例（三形态俱在）；全仓测试无 skip/only/todo（grep 命中的 skipped_links/skipped_large 是数据字段非测试修饰）；cleanup1-shared 覆盖 13 条逐字与 8 个原型名；page-logic 仍测 actionTitle。

## 说明

除指标卡 review 图标外，候选质量良好、证据充分，返工面极小。请执行端只做上述一行（含 import）修正；其余不需改动。改后由战后门禁按 ScaleIcon 复跑白盒并复验 D05。

Verdict: REVISE
