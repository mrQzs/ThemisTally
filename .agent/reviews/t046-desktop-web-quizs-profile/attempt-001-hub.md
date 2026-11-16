# 复审记录：t046-desktop-web-quizs-profile attempt-001（七端信箱 hub）

- 合同：t046-desktop-web-quizs-profile.v2（base 19b45497ca7b42d4aefd0f2a937e188e5a15de79）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261116T020115896994Z-1c0f），终审报告如下

## 终审报告

# T046-7-audit-post 终审报告（audit-sonnet）

- 任务：T046 桌面端前端第 12 片 · 合同 `t046-desktop-web-quizs-profile.v2` · attempt-001 · 基线 `19b45497`
- 结论：**通过**（无阻塞项，不退回）

## 一、我看了什么

| 材料 | 位置 | 结论 |
|---|---|---|
| 合同 v2 | `.agent/plans/t046-desktop-web-quizs-profile.v2.md` | 逐条对照行为契约、第 2–10 步、D01–D12 |
| 候选补丁 | `.agent/runs/t046-desktop-web-quizs-profile/attempt-001/candidate.patch` | 2 改 3 新，全在允许集合内 |
| 候选源码 | 工作目录 `desktop/web/src/writes/ProfileForm.tsx`、`quizsProfile.ts`、`profile-form.css` | 与补丁一致，逐行读过 |
| 新测试 | `desktop/web/tests/writes-profile-quizs-logic.test.ts`（11 例）、`writes-profile-quizs.test.tsx`（14 例） | 逐条读过，无 skip/only/todo |
| 执行概述与报告 | `summary.md`、`executor-report.md` | 自述与证据对得上（见第五节） |
| 内核检查记录 | `checks/01/checks.json` + G01/V01/V02/V03/R01.log | 5 条全绿，3 条 output_must_match 全中 |
| 战后门禁 | `.agent/mailbox/tasks/T046-6-gate-post/report.md` + `mutations.json` | 白盒 20 passed、变异 32/32 CAUGHT |
| JEV | `.agent/mailbox/tasks/T046-6j-jev/report.md` | `no_opinion auth_failed`，无外部意见可依 |

先读源码、再看检查与门禁记录；全绿不等于对，下面逐条说。

## 二、实现是否忠实于合同（Behavior contract 逐条）

1. **认 quizs 靠适配器不靠 id**：`isQuizsRuntime` 按 id 找行看 `adapter === 'quizs'`，找不到行返回 false；`ProfileForm` 把 `getRuntimes()` 的结果存成 `{id, adapter}[]`，下拉的 value/label 仍都是 id、顺序照旧。与合同一致。
2. **读档案**：打开且所选运行时是 quizs 时调 `getQuizsProviders()`；`archiveRead` 门闩保证每次打开只调一次、几个 quizs 运行时共用一份；非 quizs 一次都不调；`alive` 守卫丢弃迟到结果；`!open` 时复位门闩、档案与 `thinkingTouched`（重开会重读）。
3. **档案转模型选项**（`quizsProfile.ts`）：`usableSegment` 挡非字符串/空串/`<redacted>`；`validModel` 闸门（`p/no-slash` 两段都合法会留下，`p!/m`、`p/m!` 进不来）；同 value 只留第一项；value 与 label 都是 `provider/model`。
4. **档案转档位**：`QUIZS_LEVELS` 恰六值（off/low/medium/high/xhigh/max，无 minimal），按原顺序过滤去重；`thinking` 非数组时为空。
5. **交给服务端的值**：`provider/model` 一段，与 `config profile add --model <provider>/<id>`、hub 的 `--provider` 短名对得上（合同的模型配置 M4 之六口径）。
6. **档位从不自动改**：`thinkingOutOfRange = archiveOption !== null && !thinkingAllowed(...)` → 一个段都不选 + 「<档位> 不在这个档案允许的档位里」+ 不调预览 + `[确认…]` 不可点；用户点允许档位后恢复。
7. **口径 (a)**：`buildArgs` 里 `if (quizs ? thinkingTouched || thinkingChanged : thinkingChanged) args.thinking = thinking;` —— quizs 分支点过即传（含点回初值 `high`），非 quizs 分支一字未改。
8. **模型不在档案里**：原值作额外第一项并选中，`Select` 的 `error` 写「不在 Quizs 已批准的档案里」（`components/Select.tsx` 的 `useFieldA11y` 会在有 error 时给 `aria-invalid="true"`），不调预览；选回档案项后 error 消失。
9. **读不出档案的三种**：信封失败 → 「读不出 Quizs 的提供方档案：<messages 第一行>」；reject → 「读不出 Quizs 的提供方档案」；无可选项 → 「Quizs 没有列出可用的提供方档案」；三种都退回手填 `TextField`（`MODEL_HELP`/`MODEL_ERROR`/`validModel` 照旧）、档位六值、预览照常可用。
10. **凭据**：quizs 时不渲染凭据输入/`[添加]`/Tag，原位 `<div className="pf-env" role="group" aria-label="凭据变量">` + 「凭据由 Quizs 保管」（无障碍名称保留）；`buildArgs` 一律不交 `credential_env`；`credsChanged`/`clearingCred` 只在非 quizs 时算。
11. **兼容面**：`api.ts`、`src/mock/**`、`useWriteFlow`、`useLivePreview`、`WriteConfirmDialog`、`profileRules.ts`、`writes-profile-form.test.tsx`、页面与组件目录都没碰（补丁只有 5 个文件）；`package.json` 与锁文件按基线字节冻结（G01 S05 过）；既有逐字文案一个没删。
12. **CSS**：只在末尾追加 `.pf-note` / `.pf-warn`，只用 `--tt-text-caption` / `--tt-text-3` / `--tt-tone-warning-fg`（三个令牌在 `src/styles/tokens.css` 都有定义），无十六进制颜色、无颜色函数、无越界 px；两个类都在组件里用到（`pf-note` 两处、`pf-warn` 一处）并打进构建产物。

**「档案里档位为空」这一支**（合同「错误与重试」点名，合同第 10 步未点名用例）：我按代码路径核对过 —— `archiveOption.thinking` 为空数组时 `thinkingLevels=[]`（一个段都不选）、`thinkingAllowed(x,[])` 为 false → 越界提示照写、`quizsBlocked` 生效 → 不调预览、`[确认…]` 不可点，与「档位不在范围内」同一表现。行为对，但**没有专门用例**（执行端在 `limitations` 里已声明）。不挡，列在下面。

## 三、D01–D12 逐条判断（证据来自候选源码 + 内核检查记录）

| DoD | 判断 | 依据 |
|---|---|---|
| D01 非 quizs 一字不变 | 成立 | 既有 `writes-profile-form.test.tsx` 12 例未改且绿；新测试钉「选 pi 时 `getQuizsProviders` 0 次、凭据输入恰一个、七段、常显手填提示、命令 `--runtime=pi --model=bb/m1`」；源码里 `credsChanged`/`clearingCred`/`buildArgs`/`canPreview` 的非 quizs 支路与基线逐字同形 |
| D02 认适配器不认 id | 成立 | `isQuizsRuntime` 反例 `id='quizs'/adapter='pi'`、找不到行、空列表都有用例 |
| D03 档案转选项规则 | 成立 | 纯逻辑用例覆盖 `<redacted>`/非字符串/空串/非法段跳过、`p/no-slash` 保留、同值留第一、六值过滤保序去重、非数组为空 |
| D04 档位从不自动改 | 成立 | 越界 → 一个段都不选 + 提示 + 不调预览 + 不可点；点允许档位后恢复且带 `--thinking=high` |
| D05 档案外模型照旧显示 | 成立 | 额外第一项 + 选中 + `aria-invalid` + 不调预览；选回档案项后恢复、命令只含 `--model` |
| D06 读不出档案不卡死 | 成立 | 三种情形各有文案；退回手填、档位六值、预览可用（reject 一支也有专门用例，audit-pre 点的两个缺口之一已补） |
| D07 凭据对 quizs 不适用 | 成立 | 无凭据框/`[添加]`/Tag，`role=group`+`aria-label="凭据变量"`，命令无 `--credential-env`（先在 pi 加过凭据再切 quizs 也有用例） |
| D08 自动选首项 + `provider/model` | 成立 | 新建自动选 `stepfun/step-5-preview`；命令 `--runtime=quizs-cli --model=stepfun/step-5-preview` |
| D09 真实模式不出现桩档案 | 成立 | 注入 live 客户端后读的是 `qwen/qwen-max`，桩档案不出现 |
| D10 门禁红线 | 成立 | G01 S02/S03/S05 与 R01（43 份、999 passed）过；CSS 只追加、只用令牌；既有测试一字未改 |
| D11 范围与依赖 | 成立 | `scope.json`：A3 M2、越界 0、警告 0；`package.json`/锁文件字节冻结 |
| D12 既有测试没被弱化 | 成立 | `observations.json`：`skip_markers_added: []`，断言行 +118/-0；V01 120 文件 1144 用例全绿 |

## 四、内核检查与门禁记录（复核）

- `checks/01/checks.json`：G01/V01/V02/V03/R01 全部 `passed`，`candidate_files_modified: []`、`modified_by_checks: false`、`unexpected_files_by_checks: []`；G01/V01/R01 的 `output_must_match` 全部 `matched: true`（`\d+ passed`、`Tests\s+[1-9]\d+ passed`）。
- G01.log：`9 passed in 29.41s` —— 5 条静态（S01–S05）+ 4 条流水线（P1、P2、logic 探针、form 探针）。门禁文件里 `assert_probe_ok` 会要求探针输出里出现探针文件名、通过数不少于 `it(` 行数、无 failed/skipped/todo，所以两份黑盒探针是真跑过的，不是空过。
- V01.log：`Test Files 120 passed (120)` / `Tests 1144 passed (1144)`，其中 `tests/writes-profile-quizs.test.tsx (14 tests)`、`tests/writes-profile-quizs-logic.test.ts (11 tests)`、`tests/writes-profile-form.test.tsx (12 tests)` 都在列。
- 战后门禁：白盒 20 passed；变异 32 条全 CAUGHT、missed 0、skipped 0、error 0，`files_left_modified: []`（树恢复原样）。清单覆盖全部 3 个非测试改动文件（quizsProfile.ts 9、ProfileForm.tsx 21、profile-form.css 2）；两个新测试文件不要求变异 —— 这一条是对的，测试文件本身不需要被变异。
- 我对变异清单的判断：M02（按 id 认 quizs）、M04（去掉 validModel 闸门）、M14（credential_env 泄漏）、M17（越界门控去掉档案项守卫）、M24（adapter 改成从 id 取）、M25（touched 永不置真）、M26（去掉 getQuizsProviders 导入）、M31/M32（CSS 规则与令牌）都打在要害上，32 条不是凑数。缺的只有「alive 守卫在 runtime 变化时也被拆除」这一条语义（见下面第五节 1），白盒是源码锚定型，天然测不出运行时序。
- JEV：`no_opinion auth_failed`，无外部意见；本轮的判断全部出自源码与门禁记录。

## 五、发现（都不挡，供站主取舍）

1. **窄竞态：在档案读取在途时切换运行时，表单会停在「正在读 Quizs 的提供方档案…」**。触发路径：`archiveRead` 门闩在**发起读取时**置真，而 effect 的 cleanup（`alive = false`）在 `runtime`/`runtimes` 变化时也会跑。于是「选 quizs → 读取未完 → 切到 pi（或切到另一个 quizs 运行时）→ 再切回 quizs」时：迟到结果被 `alive` 丢弃，门闩已是真 → 不再读 → `archive` 停在 `loading` → `quizsBlocked` 生效 → 预览卡住、模型退回手填，直到关闭重开对话框（合同把「重新打开对话框会重读」定为唯一重试路，兜底成立）。概率：要在一次本地读取的窗口内（几十到几百毫秒）切换运行时；两个 quizs 运行时之间互切、或 quizs→pi→quizs 两次切换都落在窗口内才会踩到。修法（一行级）：把 `alive` 只绑在 `open` 上（cleanup 只在关闭时置假），或把门闩改成「读到结果才置真」。属可选加固，不影响本片结论。
2. **「档案里 thinking 为空」没有专门用例**（合同「错误与重试」点名、合同第 10 步没点名）。我按代码路径核对，行为与「档位不在范围内」一致（一个段都不选 + 提示 + 不调预览 + 不可点）；执行端在 `limitations` 里如实声明了。要锁住的话补一条即可。
3. **执行端解读 2**（越界提示与门控只在模型命中档案项时生效；档案读不出/模型在档案外时给六值、不卡预览）：我核对过，与合同「读不出档案时预览照常可用（表单不卡死）」和「模型不在档案里 → 档位给六值（档案不明）」一致，判成立。它已被白盒 W11 与变异 M17 钉住；日后若改判（例如读不出档案且档位在六值外也要卡），要先动这两处再重跑。
4. **编辑模式的口径 (a) 可达边界**：只点与初值相同的档位且无其他改动时 `hasChanges` 仍为假（底部「还没有改动」），此时 buildArgs 里虽已按 (a) 带上 `--thinking=`，但没有预览可显示。合同写死的是 buildArgs 的算法，且同值重传幂等、语义无损失，不判缺陷。
5. **模型 Select 在新建自动选首项前会有一帧空选项**（`value=''` 且选项里没有空串）：纯瞬时、视觉上无感，记录备查。
6. **执行端自跑了一次 `npm ci`**（联网装依赖）。合同第 11 步预告了 G01 流水线会 `npm ci`；`package.json` 与锁文件按基线字节冻结（S05 过），无依赖变更，执行端在 `interpretations` 里声明过 —— 可接受。

## 六、执行报告自述与内核摘要的线索对账

- 内核摘要的「新增被 Git 忽略的路径」（`.pytest_cache/`、`desktop/web/dist/`、各 `node_modules/`）与「掩盖退出码的写法（22 条）」逐条对上了：22 条全是只读探查（`cat`/`grep`/`ls`/`git diff`）与 `npm ci`；**五条验证命令都带 `set -o pipefail` 跑**，退出码有意义。`temp_path_uses: []`、`outside_worktree_paths: []`、`suspicious_commands: []` —— 没有往工作区外写东西，也没有硬编码临时路径。
- 内核摘要点名的「1 处解读 / 1 处歧义」（事件流第 4662 行）对应执行报告 `interpretations` 第 2 条（越界提示与门控的边界），报告里 4 条 interpretations 都与源码对得上；`contract_conflicts: []`、`unresolved_questions: []` 与事件流里那一处「contradict」的思考相符（它最终收敛到 interpretations 2，不是未解决的矛盾）。
- DoD 自述逐条与证据对得上：执行报告说「120 文件 1144 用例全绿」，V01.log 正是 `Test Files 120 passed (120)` / `Tests 1144 passed (1144)`；说「dist CSS 含 pf-note/pf-warn」，命令流里有对应的 `grep -o "pf-note\|pf-warn" dist/assets/*.css`。**没有发现自述不实。**

## 七、结论

**结论: 通过**。不退回任何一端（执行端、战后门禁、门禁端、合同端、规划端均无需返工）。

Verdict: PASS
