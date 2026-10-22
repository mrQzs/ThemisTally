# 复审记录：t013-desktop-cleanup1 attempt-002（七端信箱 hub）

- 合同：t013-desktop-cleanup1.v2（base 02943a4d9536ed022ba62f57c8448663bf7ac81d）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T013 终审报告（T013-7-audit-post · 战后 attempt-002）

合同：`t013-desktop-cleanup1.v1` · 候选：基线 02943a4（含 attempt-001）+ attempt-002 返工（2 文件）· 复核基准：战后门禁 T013-6、JEV T013-6j、站主 Q1、候选源码/测试与 attempt-002 自检日志。

## 结论

**通过。**

上一轮唯一阻塞项——指标卡「待验收」图标 `CircleCheckIcon → ScaleIcon`——已在 attempt-002 正确落地，与站主 Q1「待验收：ScaleIcon，--tt-accent-text」一致。D01–D10 逐项满足；战后门禁白盒 17 条全绿、22 处变异全被抓、无候选缺陷；执行端 G01/R01/V01/V02/V03 全过。返工面仅两文件、均在 Scope 内，无越界、无新增阻塞。

## 上一轮阻塞项逐条复核

1. **（执行端）CARD_ICON.review 由 CircleCheckIcon 改为 ScaleIcon，并同步 import（加 ScaleIcon、去 CircleCheckIcon）** —— 已解决。
   - 源码核对 `overview-MetricCard.tsx`：`CARD_ICON = { running: LoaderCircleIcon, review: ScaleIcon, decide: CircleArrowUpIcon, integrate: GitMergeIcon }`；import 为 `{ CircleArrowUpIcon, GitMergeIcon, LoaderCircleIcon, ScaleIcon } from '../../icons'`（CircleCheckIcon 已移除、ScaleIcon 已加入）；全文不再出现 `CircleCheckIcon`。
   - `ScaleIcon` 已存在于 `desktop/web/src/icons/index.tsx`，未新增图标；四枚卡图标子节点两两不同，innerHTML 比对能区分换图标。
   - 颜色 `--tt-accent-text`（`.ov-metric[data-metric="review"] .ov-metric__icon { color: var(--tt-accent-text); }`）与色调条 `--tt-accent`（`.ov-metric[data-metric="review"] .ov-metric__bar`）均未动、与 Q1 (c) 一致。
2. **战后白盒断言随图标同步为 ScaleIcon 并复跑** —— 已解决。
   - 门禁白盒 `test_gate_t013_whitebox.py` 的 `METRIC_ICONS.review=ScaleIcon`，`test_wb_d05_metric_card_dom` 增加「四枚图标都从 '../../icons' 引入」与「本文件不再出现 CircleCheckIcon」断言；新增 `test_wb_d05_visual_test_pins_scaleicon` 静态守住执行端视觉测试。
   - 执行端 `cleanup1-visual.test.tsx` 新增断言：渲染 group='review' 卡，与直接渲染的 `<ScaleIcon width={16} height={16} className="ov-metric__icon" aria-hidden="true" />` 比对 `.ov-metric__label svg` 的 innerHTML 与 class='tt-i ov-metric__icon'；V02 日志显示该文件 5 tests 通过。
   - 执行端所述「基线上不存在按名钉 CircleCheckIcon 的白盒断言」（tests 下 grep CircleCheckIcon 无命中）经核实属实——因此「新增等价断言」而非「改旧断言」是合理取舍，不构成弱化。

## DoD 逐项复核（按战后门禁报告核对）

| DoD | 结论 | 依据 |
|---|---|---|
| D01 共用件取值 | 满足 | 白盒 d01（copyText 三态+缺省 navigator、三条文字；actionTitle 13 条逐字+hasOwnProperty+表外 null；actorTone 五类且 tone={actorTone(actor)}；formatLocalUtc 含「（UTC 」+null 且 RelativeTime title 取它；index.ts 只末尾追加 sha 前缀校验）；V02 |
| D02 没有第二份 | 满足 | 白盒 d02：copyText/ActorTag 各一处；三条复制文字、13 条动作说明、带引号 undeclared、「（UTC 」各只在对应共用件；三份重复件已删；overview-logic.actionLabel、history-logic.timeCell/本地 actorTone、common-format.formatLocalUtc 均不在（relativeFrom 保留） |
| D03 总览渲染 | 满足 | 白盒 d03 接线 + cleanup1-merge（动作 title、执行者五色、相对时间文字与 title、复制三结果） |
| D04 只读二渲染 | 满足 | 白盒 d04：HistoryView at 格用 `<RelativeTime iso={e.at}>`、抽屉 dl 时间、插件抽屉复制三结果 |
| D05 指标卡 | 满足（本轮修订点） | CSS 卡片 position relative/flex column/gap --tt-space-0_5、色调条 absolute left/top/bottom 0 width 3px（M11 改 4px 红）；四卡图标色各取本卡令牌（review=--tt-accent-text、色调条 --tt-accent）；DOM 顺序 色调条→标签行(16px 图标 aria-hidden)→数字(tt-num)、唯一 tt-num、无内联 style；review 图标=ScaleIcon 且白盒钉住（M19 回退 CircleCheckIcon、M20 改 CircleArrowUpIcon、M21 去 import 均红） |
| D06 .rt-cmd | 满足 | 白盒 d06：display block、max-width 280px、overflow hidden、white-space nowrap、--tt-mono-sm 同规则（M13 红） |
| D07 aria-controls | 满足 | 白盒 d07：useId+行序号、aria-controls 收起含 undefined、与面板 id 同源、不用方案名拼 id（M12 红） |
| D08 .ov-row__name | 满足 | 白盒 d08：font var(--tt-mono-md) 且 overflow/nowrap/ellipsis |
| D09 样式表接线 | 满足 | 白盒 d09：readonly1、readonly2 共 9 份 CSS 都能从 src/main.tsx 顺 import 到达 |
| D10 回归与范围 | 满足 | G01 22 passed、R01 415 passed、V01 构建退出码 0、V02 71 files/635 tests、V03 契约检查通过；只改允许的两文件；依赖未动；新测试无 skip/only/todo；未提交推送 |

## 战后门禁验证

- 白盒：`17 passed`（日志 `17 passed in 0.15s`）。
- 变异：`counts.caught=22 / missed=0 / skipped=0 / error=0`；其中 M19（review 回退 CircleCheckIcon）、M20（改 CircleArrowUpIcon）、M21（去 ScaleIcon import）、M22（弱化执行端视觉测试）专钉本轮返工，全部被抓。
- 候选缺陷：无。

## 范围核实

候选相对基线只改两文件（`candidate.stat.txt`：2 files changed, 14 insertions(+), 2 deletions(-)；`changes.json` 亦仅两文件 M），均在 Scope 允许列表内；无越界。

## JEV flags 解读

- 自行解读合同 p=0.93、自述完成无证据 p=0.85、误导程度 2.04/3（置信 0.38）：均为「需关注」级，但本轮经独立核对不构成阻塞——(1) 自行解读指执行端对「让白盒断言与图标同步」的取舍（找不到旧断言则新增等价断言），经核实基线确无该旧断言，取舍合理；(2) 自述完成的每一项 DoD 均有 V02/G01/cleanup* 测试支撑，测试实际存在且通过，非实质无证据；(3) 误导程度置信仅 0.38，独立检查（白盒/变异/源码/自检日志）已覆盖关键断言，未见可改变结论且检查无法揭示的改动。弱化测试 p=0.05 低。

## 说明

上一轮打回仅一项图标形状，本轮已一行（含 import）修正并由白盒 M19/M21 钉住。未引入新阻塞理由，其余建议类事项不再升级为阻塞。终审裁定：通过。

Verdict: PASS
