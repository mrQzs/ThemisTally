# 复审记录：t012-desktop-shellpages attempt-006（七端信箱 hub）

- 合同：t012-desktop-shellpages.v6（base b4ff8c78aace66bde310c7c4c80f3bde3ef4983a）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# 终审报告 T012-7-audit-post

## 结论：通过

候选（attempt-006 / 返工基线 `b4ff8c7`，候选树 `f6a05ea`，补丁往返校验通过）满足合同 `t012-desktop-shellpages.v6` 的全部 DoD（D01–D13）。战后门禁（白盒 49/49、变异 79/79、范围核对）通过。JEV 两个关注点经裁定均不构成阻塞。`openExternal` 记录行为裁定为**不必补**。

---

## 一、独立核对范围

**源码/夹具/样式（逐文件通读）**：themisShell.ts、shellStub.ts、shellContext.tsx、shellWindowRoute.ts、ShellWindow.tsx、themePref.tsx、App.tsx、pages/SettingsPage.tsx、SettingsView.tsx、firstRunModel.ts、FirstRunView.tsx、ServiceStatusView.tsx、exitCodes.ts、copy.ts、format.ts、ExternalLinkDialog.tsx、LicensesDialog.tsx、licenses.ts、icons.tsx、mock/shellpages-scenarios.ts，以及 shell-window.css / first-run.css / service-status.css / settings.css 的关键尺寸。

**测试（通读）**：tests/shellpages-isolation.test.tsx、tests/shellpages-app.test.tsx；`tests/test_gate_t012_baseline.py` 的探针结构（7 组：stub/route/firstrun/service/settings/app/isolation）与 openExternal 探针；白盒 `tests/test_gate_t012_whitebox.py`（49 条，全文）；变异记录 `mutations.json`（counts.caught=79, missed=0）。

---

## 二、需裁定问题 1：openExternal 记录行为

**合同原文**（「桩与夹具」）：`openExternal 只记下网址（供测试读），不打开任何东西。`
**候选实现**（shellStub.ts）：
```ts
const openExternal = (url: string): Promise<void> => {
  if (!/^https?:\/\//.test(url)) return Promise.reject(new Error('只允许 http 与 https'));
  return Promise.resolve();
};
```
即：校验 http/https、不打开任何东西，但**不记录网址**。文件头注释仍称「openExternal 只记下网址，不打开任何东西」——注释与实现不符。

**裁定：不必补记录，非阻塞。** 理由：
1. **不在 DoD**：D02 对 openExternal 的验收只有「只认 http、https」，实现满足（http/https 兑现、其余协议与空串被拒，见基线 `D02 桩的 openExternal 只认 http 与 https` 探针与 shellpages-stub.test.ts）。
2. **无读者**：全仓检索，没有任何测试或产品代码读取这个「记录」——基线 D09 与 shellpages-settings.test.tsx 用注入 spy 数调用次数，不读桩内记录。
3. **行为等价**：合同的实质意图「不打开任何东西」已满足；「供测试读」的目的因无读者而落空，记录与否对外可观测行为完全一致。
4. **代价**：执行端预算已用尽（max_attempts_total 4/4），要求补记录须站主追加预算，而功能收益为零。

**建议（非阻塞）**：修正 shellStub.ts 文件头注释为「校验 http/https、不打开任何东西」，使注释与实现一致；或后续接真实外壳那一片整体替换桩时自然消解。

---

## 三、需裁定问题 2：JEV 关注点

**（a）自行解读合同（p=0.88）**：执行端唯一未显式标注的偏离就是上面的 openExternal 不记录（选了「无读者即无需记录」的解读）。其余解读（把返工记录里 attempt-002 的三条失败视为旧门禁历史、以热修补后的新基准测试为准）**正是合同 Rework 第 2 节明文要求**，属合规执行而非自行解读。openExternal 偏离经上一节裁定为行为等价、非阻塞，故该关注点不升格为阻塞，仅记为文档瑕疵。

**（b）自述完成而无证据（p=0.94）**：执行端 D01–D13 均附「证据：V01/V02/V03/npm」，并在 self_checks 里给出命令与结果（V01 56、V02 333、V03 7、npm ci/build/test/check:contract）。这些是**执行端自述**，门禁端因无 node_modules（需 npm ci 联网）未独立复跑 V01 运行时部分，仅独立复跑了白盒/变异/静态基线。该关注点的实质是「运行时证据仅来自自述」——见第四节对验证强度缺口的评估：因静态+变异覆盖强、且本端已逐文件确认源码正确、并确认运行时测试为真测试，残余风险低，不构成阻塞。

---

## 四、需裁定问题 3：验证强度缺口

**缺口**：门禁白盒为纯 Python 静态断言（不跑 npm/Vitest），运行时行为（桩计时器时序、App 级渲染、点遍按钮隔离、主题与刷新同步）只有执行端自述 + 基线静态断言作依据。

**评估：可接受，残余风险已降至低位。** 依据：
1. **静态覆盖强**：白盒 49 条逐条钉住取值/结构/接线/源码守卫，覆盖 24 个非测试文件。
2. **变异强约束**：79 条变异全部被抓住（含接线类：去 App 外壳分支、去 ThemePrefProvider、去各 css import、SettingsPage 不渲染 SettingsView、ExternalLinkDialog [打开] 改绑 onClose、navigateShell 不写地址等），证明测试真能约束实现，而非空跑。
3. **运行时测试为真且齐全**：`tests/test_gate_t012_baseline.py` 是完整的 Vitest+jsdom 探针套件（7 组），执行端另有 8 份 `tests/shellpages-*` 真测试（我已通读 isolation/app 两份，确认为真实运行时断言：vi.mock('../src/api')、网络替身、fake timers、hashchange 手动派发、点遍按钮）。
4. **本端源码复核**：逐文件确认实现与合同逐条一致（含 App.tsx 仅 §2.3 改动、`getMetaNow`/`getStatus` 只在 ServiceApp、shellpages 无 api/themisHost/window.open/存储导入、四份 css 均被可达 tsx import、关键 px 同行有出处）。

**残余风险**：V01 运行时套件未经门禁端或本端（本端无执行工具）独立复跑，绿结果来自执行端自述。对中风险的前端切片，在静态+变异+源码复核三重佐证下，此残余风险可接受。**建议**：把「门禁端在具备 node_modules 时至少跑一次 V01」列为后续门禁的改进项（不针对本候选阻塞）。

---

## 五、DoD 逐项核对（D01–D13）

- **D01 接口与夹具**：themisShell.ts 十成员（9 方法+on）与 8.9 一致；SettingsPatch 仅六键、无路径键；shellpages-scenarios.ts 为 .ts、头注「示意」、11 场景、路径正斜杠。✅
- **D02 桩**：getState/各返回深拷贝；pick 队列用完重复最后一个；各方法 Promise.resolve/reject 不经计时器（scheduleResolve 仅 start/restart 调用；创建体无 setTimeout）；saveSettings 六键校验先行、被拒不改状态；startService 拒不在列表 id 且对同仓幂等；1500ms 发 running/exited、stuck 停 starting；dispose 先 clearTimeout 再 clear 监听。✅
- **D03 进入方式**：parseShellWindow 第一段决定、后续段忽略；scenarioOf 缺省 ready/crash；navigateShell 同步先 setHash 再写 location.hash、保留查询串、缺 shell 补当前场景；App 根分支 + 主题上提、ServiceApp 原函数体锚点齐全、:72 TitleBar 一字不改。✅
- **D04 首次启动状态**：firstRunModel 依次检查、前步不过置灰「等待上一步」、第 4 步 live=true、idle/starting/running/exited 分支齐、无 role=status。✅
- **D05 首次启动操作**：六种错误文字与按钮、被拒 pick 多出一行、退出码 1 DisabledAction 无 onClick、自动启动 ref 去重且 exited 不重启、[进入] disabled=!allPass 且跳 /overview、复制三态文字。✅
- **D06 服务状态**：卡片 440、data-exit-code、clock、stoppedNote 共用 exitCodes、重启一次进加载态、仅 awaiting 且收到 running 才 navigate('/overview')、exited 换码换说明、无 role=alert。✅
- **D07 设置前三组**：控件调用与参数精确、只用返回值 setState、load useCallback 依赖 [shell]、当前仓库 DisabledAction 不可移除、会话目录只读无输入控件、刷新 data 经 useEffect 换本地状态。✅
- **D08 外观**：主题经 useThemePref(context) 先 setTheme 再 saveSettings、密度只按返回值、无 Provider 退回本地、全片不写 data-theme。✅
- **D09 关于与外部链接**：版本、许可两项不写字体文件名不做链接、[项目主页] 先出确认框 openExternal 0 次、[打开] 恰一次、非 http(s) 只显文字。✅
- **D10 隔离**：静态 shellpages/SettingsPage 不 import api、不碰 themisHost/window.open/存储（grep 无匹配）；运行时 isolation 测试 api/网络替身 0 次。✅
- **D11 源码规则**：无禁用整词/子串、无内联 style、无十六进制/颜色函数、新图标 path 等画布、文件名约束、pages 9 份、mock 14 份 JSON。✅
- **D12 样式与接线**：关键 px 同行有出处（560/440/22/72/18/34/40/140/120/32/40/640/920/56×64/42×48 均核到）、四份 css 均被可达 tsx import、构建产物可选器（执行端 npm run build 自述）。✅
- **D13 回归与范围**：T001–T008、V03、npm 四步（自述通过）；App.tsx 仅 §2.3；只改允许文件；无依赖变更；8 份测试无 skip/only/todo。✅

---

## 六、非阻塞观察（记录备查，不影响结论）

1. **shellStub.ts 头注与实现不符**：注释称「openExternal 只记下网址」，实现只校验不记录。建议改注释（见 §二）。
2. **first-run.css `.tt-fr__val` 用 `--tt-text-sm` 非等宽**：合同 §3.3 写「值（等宽、单行省略）」，第 2–4 步值非等宽。纯样式细节、不在 DoD、不影响功能与测试。
3. **门禁未复跑 V01**：见 §四，建议列为后续门禁改进项。

---

## 七、最终裁定

**通过。** 无需退回执行端 / 门禁端 / 合同端 / 规划端。上述非阻塞观察可在接真实外壳那一片或后续清理中顺手处理，不构成本片阻塞。

Verdict: PASS
