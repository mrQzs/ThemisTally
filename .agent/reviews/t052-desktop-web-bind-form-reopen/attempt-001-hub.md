# 复审记录：t052-desktop-web-bind-form-reopen attempt-001（七端信箱 hub）

- 合同：t052-desktop-web-bind-form-reopen.v1（base f7c06d495764509ad569c8729f9470ec9d44266b）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261118T091509043961Z-9add），终审报告如下

## 终审报告

# T052-7 终审（战后复审）报告 — audit-sonnet，2026-11-18

## 结论

**通过**。候选忠实合同（写法钉死 1–6、预填规则、写流程次序、有意的行为变化逐条对过），范围只有 2 改 1 增；内核在独立树上复跑的六个必要检查全绿；战后门禁 15 条变异全部抓住、未举证任何候选缺陷；执行报告的自述与内核记录逐条对得上，没有自述不实。本回合没有阻塞项，不退回任何一端。

## 一、本回合核了什么

- 候选：`candidate.patch`（31962 字节，patch_roundtrip_verified 为 true，tree d1d3e60）、`candidate.stat.txt`、`changes.json`、`scope.json`（A1 M2 D0 T0，violations 空，head_after 仍是基线 f7c06d49）。
- 源码（冻结核心里就是候选态）：`desktop/web/src/writes/HubBindForm.tsx`、`desktop/web/src/writes/RoleBindForm.tsx`、`desktop/web/tests/writes-bind-reopen.test.tsx`（补丁全文 413 行，逐条读过）。
- 内核检查记录：`checks/01/checks.json` 与 G01 / R01 / V01 / V02 / V03 / V04 六份日志（内核在独立的 fresh verify 工作区跑，退出码、output_must_match、耗时都是机器记的；`modified_by_checks` 为 false，候选树跑前跑后一致）。
- 战后门禁：`T052-6-gate-post/report.md`、白盒文件 `tests/test_gate_t052_whitebox.py`、`mutate-…/mutations.json`（15 条逐条结果）。
- 执行侧：`summary.md`、`executor-report.md`、`events-summary.json`。
- JEV：`T052-6j-jev/report.md` = no_opinion（auth_failed），没有意见要裁。
- 相关共享件（只读核对）：`useWriteFlow.ts`、`useLivePreview.ts`、`components/Dialog.tsx`、`components/overlay/useOverlayFocus.ts`、`src/api.ts`。
- 本回合只有只读工具、没有 shell，未复跑 npm/pytest；一切运行结论以内核记录与门禁记录为准。

## 二、实现是否忠实于合同

1. 写法钉死第 1/2 条（字面量）：两个文件的导出、两个原因句常量、标题 `改绑定：${postLabel}` 与 `改绑定：${roleLabel}`、四个 Select 的 label（主绑定 / 替补 / 模式 / profile）、「不设替补」、「更改…」配 variant secondary 与 size sm、`DisabledAction`、`useLivePreview(`、`'hub.set'` 与 `'role.set'`、`<WriteFlow flow={flow} />`、门控里的 `current` / `result.ok` / `onClose` / `onConfirm`、运行时引 `{ hubChangeLines } from './hubChangeLines'`、从 `../api` 只 `import type`、`import './hub-bind-form.css';` 之后没有新的 import、代码里不出现 `aria-label` / `step-low` / `style={{`、不写死颜色、不跨层引 `src/pages` —— 逐条在位（内核 G01 的 S01/S02 也逐条核过，7 passed）。
2. 写法钉死第 3 条（不新增 import）：两个文件的 import 行与基线逐字相同（9 行 / 8 行，含 css 副作用 import），补丁里没有 import 段的改动。
3. 写法钉死第 4 条（名字）：内层 `HubBindFormDialog` / `RoleBindFormDialog`，模块级 function、都不导出；外层仍是 `HubBindDialog` / `RoleBindDialog`。
4. 写法钉死第 5 条（分工）：外层只做三件事 —— `const { start, flow } = useWriteFlow(reload);`、`{open && <内层 … />}`、`<WriteFlow flow={flow} />`；`useWriteFlow(reload)` 全文恰一次、外层无 `useState`、不渲染表单 `Dialog`。内层收下预填计算、两个 `useState`、候选联动、`buildArgs`、`useLivePreview`、门控、`renderBottom` 与 `<Dialog open …>`。`canPreview` 去掉 `open &&`（hub 是 `main !== ''`；role 是 `mode !== '' && (!headless || profile !== '')`）。[确认…] 先 `onClose()` 再 `onConfirm(spec)`，外层 `onConfirm={start}`。与合同一字不差。
5. 写法钉死第 6 条（注释）：文件头两行说明照旧；新增了「内层只在打开时挂载」「写流程留在外层」两句约束注释；两处 `canPreview` 上方注释改了措辞（「只有表单开着且…」→「内层只在表单开着时挂载：…」），意思未变（旧措辞在新结构下会写成不成立的前提），门禁剥注释后再查、无人依赖注释文本。
6. Behavior contract 的预填规则一字未改（hub 主选/替补、role 模式/profile 的条件与 else 落点都在原处）；「每次打开重算」由「关掉即卸载内层」保证；表单开着时 props 变了不重置用户正在改的字段（`useState` 初值只在挂载时取）；写流程次序照旧；[确认…] 门控照旧；对话框关着时 DOM 与今天一致（关掉时内层根本不挂载，`Dialog` 关着时也不渲染任何 select 与按钮）。
7. 有意的行为变化：内层卸载 → `useLivePreview` 的 `result`（只活在调用它的组件里）随组件一起消失 → 再开先「预览中…」、[确认…] 灰着，新预览回来才可点。落地了。
8. 边界输入：没有主选候选 → [改绑定…] 仍禁用并给原因句（禁用分支未动）；`candidates` 为空 → `modeOptionsOf` 照旧拿掉「无头」、原因句仍在 `help` 里、`[更改…]` 仍禁用；现有绑定不在候选里 → 落到第一个候选 / 第一个可选（未新增规则）；预览失败 → 底部错误原文、[确认…] 不可点（`renderBottom` 未改）；写流程失败 → 走既有 `useWriteFlow` 分支（未动）。
9. 焦点语义：`useOverlayFocus` 的 cleanup 在卸载时同样把焦点还给打开前的元素（我按 `useOverlayFocus.ts` 的 cleanup 分支逐行核过），所以「挂载即开、卸载即关」与原来的开关切换在焦点上等价 —— 与合同 Repository facts 的结论一致。
10. 写路由与正文没变：`api.ts` 的 `setHubRole` / `setRoleBinding` 一个字没动，正文仍是 `{...writeArgs(w), confirmation}`（role侧 target 之外只带给了才有的 host 与 cadence_seconds）。
11. 没有越界：只改两个源文件 + 新增一个测试文件；入口文件、`api.ts`、`useWriteFlow.ts`、`useLivePreview.ts`、`components/**`、`shell/**`、`hub-bind-form.css`、`package.json` 与锁文件、`src/mock`、`src/pages` 一个字没动（`scope.json` 与 `changes.json` 佐证）。

## 三、DoD → 测试 → 断言

| DoD | 由哪条测试的哪个断言证明 | 机器可验 |
|---|---|---|
| D01 情形1（改字段取消后再开回到现有绑定） | 新测试 hub(a)：主绑定 value 为 quizs-m9、替补 value 为 step-high 且 disabled 为 false；role(a)：profile value 为 step-high；role(a2)：模式回到 interactive_host 且框里只有 1 个 select | 是（V04） |
| D01 情形2（外部改了绑定、重读后 props 变再开） | hub(b)：预览请求 `args.profile` 为 step-high、`args.fallback` 未带；role(b)：预览请求 `args.target` 为 step-low、`args.role` 为 execution、`args.host` 未带 | 是 |
| D01 情形3（新增候选后再开按当时候选预填） | hub(c)：预览 `args.profile` 为 quizs-m9 且 `[确认…].disabled` 为 false；role(c)：预览 `args.target` 为第一个候选 quizs-m9 且 `[确认…].disabled` 为 false —— 断言的是预览请求的 args 与按钮态，不是 select.value，避开了 react-dom 把第一个未禁用 option 设成 selected 的坑 | 是 |
| D02（写流程不变：先关表单再 start） | hub(d)/role(d)：写确认框标题含「改绑定 contract？」/「改角色绑定 execution？」、框里 select 数为 0（表单已关）、写路由恰 1 次、role 正文恰为 `{target, confirmation}`、成功轻提示、reload 被调、写完重读后再开按新绑定预填 | 是 |
| D03（有意的行为变化 + 开着不重置） | hub(e)/role(e)：再开文本含「预览中…」、`[确认…].disabled` 为 true，新预览回来后为 false、命令文本出现、预览请求数 = before+1；两条守卫：表单开着时 rerender 换 props，用户正在改的主选 / profile 不被重置 | 是 |
| D04（两个源文件的门禁字面量一个不少） | G01 的 S01/S02（逐条字面量核对）；R01 的 51 份既有门禁基准 | 是 |
| D05（其余行为、文字、样式与导出形态不变） | G01 的 S01/S02 + scope/changes（没碰共享件、锁文件、入口文件）+ 人工审阅 diff | 部分：导出与字面量机器可验；共享件与锁文件只能人工审阅（本回合已逐行看过 diff） |
| D06（新增测试文件，覆盖 D01–D03，测真实实现，无 skip/only/todo） | V04（13 passed）；G01 的 S03（文件在位与覆盖记号）；我 grep 过新测试文件：skip / only / todo / vi.mock 零命中 | 是 |
| D07（改动都在允许集合内） | scope.json（violations 空）+ changes.json（3 个文件）+ candidate.stat.txt | 是 |
| D08（npm test / typecheck / build 全过、51 份门禁全过） | V01（131 文件 / 1279 用例）、V02（退出 0）、V03（built in）、R01（1086 passed） | 是 |

D01–D03 的行为面在战前门禁的两份探针里也各有一份（G01 通过），两边独立成立。

## 四、内核检查与门禁记录

- 内核在独立工作区复跑六个必要检查，全部 passed 且 output_must_match 命中：G01 `7 passed in 33.80s`、V04 `13 passed`（6.91s）、V01 `131 files / 1279 tests passed`（20.86s）、V02 退出 0、V03 `built in`、R01 `1086 passed in 1049.48s`。候选树跑前跑后一致、`modified_by_checks` 为 false、`candidate_files_modified` 与 `unexpected_files_by_checks` 都空。
- 战后门禁：candidate_defects 为空；15 条变异 15 抓住 / 0 漏 / 0 跳 / 0 错，baseline 通过，变异后 `files_left_modified` 为空。我逐条判断这 15 条：M01/M09 挂载门、M02/M10 写流程交接、M03/M11 import 接线、M04/M12 防抖启用条件、M05 替补带参、M06/M13 预填条件、M07 确认次序、M08 写流程挂载、M14 profile 预填 else 落点、M15 `modeOptionsOf` 候选门 —— 每条都打在「本片行为真正依赖的接线或取值条件」上，没有一条改无关代码凑数。白盒是静态结构核对（它自己也在文件头声明了行为面不在本文件重复），行为面由执行端的 13 条组件测试与战前门禁探针兜住，不构成空心断言。
- 门禁端没有声明「没法变异的改动文件」；两个非测试文件都有多条变异，新增的测试文件按惯例不参与变异。

## 五、执行报告自述 ↔ 内核记录 逐条对账

| 内核线索 | 执行报告的说法 | 裁定 |
|---|---|---|
| 可疑命令（递归或强制删除）：`rm -f …/HubBindForm.tsx.orig …/RoleBindForm.tsx.orig` | 「基线对照用备份 + 同命令恢复的方式做，跑完即删；md5 与 git status 已核对恢复一致」 | 对得上：只删执行端自己造的 .orig 备份，文件在工作目录内；候选里没有 .orig（candidate.stat 只有 3 个文件），恢复后的源码就是现在的候选态。**不是自述不实** |
| 临时路径 | events-summary 的 `temp_path_uses`、`outside_worktree_paths`、`own_run_paths` 皆为空 | 一致：没有往工作目录外写东西 |
| 退出码被管道掩盖 3 条（事件流 2193 / 3533 / 3550 的探索命令，npm test 接 tail） | 自检表里报了退出码 0 | 这三条是动手前的探索命令；正式自检那几批都加了 `set -o pipefail`；且内核在独立树上重跑了六个必要检查，退出码与匹配都是机器记的，报告数字与内核记录一致（7 / 13 / 1279 / 1086）。不算自述不实，列为意见 |
| 「新增被 Git 忽略的路径」（.pytest_cache/、desktop/web/dist/、ts/node_modules/ …） | 「dist/ 由 V03 生成、已被 .gitignore 忽略，未进候选」 | 一致：都是被忽略的构建/依赖产物，不进候选 |
| 变更范围 | 「只改 2 个源文件、新增 1 个测试文件」 | 与 scope.json / changes.json / candidate.stat.txt 一致（A1 M2 D0 T0，violations 空） |

D01–D08 的「done」都有对应证据，没有对不上的自述。

## 六、非阻塞意见（不挡，供站主决定）

1. 13 条新用例里有 2 条（两条「表单开着时 props 变了不重置字段」守卫）在基线代码上也是绿的：它们断言的是要保住的旧行为（合同 D03 点名要求），不是本片要修的行为。执行端已披露。不挡。
2. 门禁把这两个源文件的 import 行逐字冻结（T052 的 baseline 与战后白盒两份都是）：将来任何要给 `HubBindForm.tsx` / `RoleBindForm.tsx` 加 import 的片（例如 T053）都会被卡住，那一片改自己的门禁文件即可。战前已记过一次，仍有效。
3. 战后白盒文件 `tests/test_gate_t052_whitebox.py` 现在留在仓库里（仓库里第一份这种文件）：它逐字钉死本片结构（内层/外层名字、挂载门、`canPreview` 字面量、`onClose(); onConfirm(spec);` 的缩进），并且不在 R01 的文件清单里（R01 只列 t001–t051）。将来动这两个文件的片，除了放宽 t052 的 baseline，还要记得这份白盒。
4. 门禁报告的变异表有一行编号写乱（M15 出现两次）。以 `mutations.json` 为准（M01–M15 齐全、全部 caught）。报告文字问题，不挡。
5. D02 的「重读次数照旧」只断言到「reload 被调用」，没断言次数；`useWriteFlow` 一个字没动，判为可接受。
6. 执行端解释里的 4 条取舍（onConfirm 签名与本地 onConfirmClick 的命名、两处 canPreview 注释措辞、13 条用例多于点名的 10 条、R01 不分批）逐条核对都在合同 latitude 内，不削弱任何 DoD；多出的两条守卫正是 D03 要的。

## 七、阻塞项

无。

Verdict: PASS
