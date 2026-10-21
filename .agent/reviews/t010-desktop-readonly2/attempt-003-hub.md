# 复审记录：t010-desktop-readonly2 attempt-003（七端信箱 hub）

- 合同：t010-desktop-readonly2.v4（base 3ffc216fef0e3ba43660b4d56f3e55c1ff8d7af5）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T010-7-audit-post 终审报告（audit-sonnet）

## 结论
**通过**。T010 候选（基线 3ffc216 + attempt-003 三文件补丁；候选树 78b28f569f）满足合同 v4 的 DoD，未发现阻塞缺陷。执行端两处偏离（解读 1/2）经我独立核实均与合同分支一致、非缺陷。合同预算已用尽（3/3），无需追加。

## 复核依据
- 一审 T010-4-audit-pre：通过，无新阻塞（上一轮唯一阻塞项 G6 已解决）。
- 战后门禁 T010-6-gate-post：通过，candidate_defects 为空；V01 26 passed；白盒 7 passed；12 条变异全抓住。
- JEV T010-6j-jev：见下节处理。
- 执行报告 attempt-003：DoD D01–D12 全覆盖，自检命令与结果表齐全。
- 落地预演：9 份门禁基准 359 passed in 338.41s。

## 独立核实（读工作树源码，不依赖自述）
1. **补丁范围**：candidate.patch 仅 3 文件，全在合同 Scope 内——logs-SearchResults.tsx（格式修复：</span> 与 </div> 分行，去同行尾随空格）、readonly2-plugins.test.tsx（+3 测试）、readonly2-history.test.tsx（+1 测试）。其余 28 源码/夹具 + 6 测试在基线已存在。
2. **格式修复**：logs-SearchResults.tsx:63 计数 span 独占一行以 </span> 收尾，:64 </div> 独立成行；计数文字仍「N 条 · 上限 M」、带 tt-num，标题仍「结果」。渲染不变。
3. **解读 1**：readonly2-history-entries.ts 第 40 条 note 逐字「（含疑似凭据，不显示）」，与 forbidden 的 src/mock/history.json 第 40 条 note 逐字一致（已核对）。该串既是 UI 文档 7.13 的遮蔽占位、又含「疑似凭据」，合同案例四两种触发条件都命中同一分支；diffKind 因 list note 是占位 + changed_keys 非空 → masked-keys，与合同「9.10 第 40 条的样子」一致。非缺陷。
4. **解读 2**：history-logic.ts diffKind 用 entry.changed_keys ?? [] 再判 keys.length > 0；history-HistoryView.tsx ChangedKeysCell 用 keys && keys.length > 0。两处 [] 与 null 走同一分支（回落 note、再否则「—」）。合同只区分「非空」与「两者都没有」，空数组语义等价 null。非缺陷。
5. **无测试特判/硬编码/空异常**：readonly2 源码无 NODE_ENV/process.env/__test/isTest/vitest/jest/import.meta；catch 均有实际处理（common-copy 返回 'failed'、logs-logic 返回 false、三个抽屉/面板的 catch 带 alive/请求号守卫）。
6. **Drawer.css**：top 已改 40px 并同行写出来处注释，文件头注释改为「顶边让位 40 高的标题栏」，删掉「顶边取 0」。符合合同。
7. **一审提示的注意点**：readonly2/ 全目录检索 data-page-state / Toast / scrim / backdrop 均无命中——视图不写 data-page-state、抽屉不自写遮罩、复制反馈不用 Toast。

## 偏离（均为合理解释，非缺陷）
- **解读 1**：夹具第 40 条 note 用「（含疑似凭据，不显示）」。行为落合同案例四同一分支；且与 forbidden 的 history.json 逐字一致，避免同一历史在列表与抽屉显示两句不同 note。唯一与合同夹具 spec 引文的字面差异见「需协调人决定」。
- **解读 2**：changed_keys 空数组 [] 与 null 同样处理。合同只区分「非空」与「两者都没有」。行为一致。

## JEV 处理
- 自行解读合同 p=0.94：执行端在 interpretations 里明列两条并给理由，非默默择一；门禁与我核实均与合同一致。
- 自述完成而无证据 p=0.93：执行端附完整自检命令与结果表；门禁独立复跑 V01/白盒/变异、落地预演 359 passed，关键声明已独立验证。
- 误导程度 2.16/3 但置信仅 0.16（近乎噪声）；超出范围 p=0.16、弱化测试 p=0.04（低）。均不构成阻塞。

## DoD 覆盖（依据 V01 + 白盒 + 一审映射表）
D01–D12 均有证据覆盖，详见一审 T010-4 的 DoD→测试→断言映射表与门禁报告。本轮补的 4 条测试覆盖 D05 焦点/Esc 顺序、D07 焦点/Esc 同 D05、D09 悬停 400ms 提示，补齐了既有实现的真实测试缺口。

## 需协调人决定（知会，不阻塞）
- 解读 1 的夹具 note 字面「（含疑似凭据，不显示）」与合同夹具 spec 引文「疑似凭据，不显示」不同。行为一致；若站主希望严格对齐 spec 引文，需注意会与 forbidden 的 history.json 产生不一致。门禁与我均倾向维持现状。

## 阻塞项
无。

Verdict: PASS
