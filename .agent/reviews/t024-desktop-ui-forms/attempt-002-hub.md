# 复审记录：t024-desktop-ui-forms attempt-002（七端信箱 hub）

- 合同：t024-desktop-ui-forms.v2（base b222d975ced43b9c1f7d7bbfab1031a690eea6f4）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（cc-switch-qianwenai-token-plan/qwen3.8-max，思考档位要求 high、生效 high；回合 20261029T172923344894Z-9214），终审报告如下

## 终审报告

# T024-7-audit-post 终审报告

## 结论：通过

候选 attempt-002（基线 b222d97 + candidate.patch，候选树 13a1499）忠实实现合同，无阻塞缺陷。

## 审核方法

先通读 candidate.patch 全文（1699 行，15 个文件），逐节对照合同 §1–§9；再核内核的检查与门禁记录、白盒测试源码与变异记录；最后人工审阅 D12/D14 与执行端三处解读。全绿不等于对：对每个 DoD 找了补丁里对应的实现证据，不只看测试通过。

## D01–D14 逐条裁定

| DoD | 裁定 | 依据（补丁/记录里的实证） |
|---|---|---|
| D01 | ✓ | api.ts 只新增 WriteArgs、addProfile/editProfile、WriteAction 两成员；preview/WriteSpec.args 只放宽（旧调用点未动）；无联网词（V03/R01 亦守） |
| D02 | ✓ | sameValue 数组按长度+逐项序比较，不拼字符串；profileArgs 对空 credential_env 不传键；变异 M01/M05/M07 均被杀 |
| D03 | ✓ | NEW_ACTIONS 加两 action → confirmWrite 六种不符都 409+exit_code null；writes-profile-api 逐项断言；M04 被杀 |
| D04 | ✓ | profileRules 三条正则与内核原式逐字一致（W01 静态断言+探针边界 64/65、128/129、200/201）；不合法时 canPreview=false → effect 不发 preview，用例断言调用次数 0 |
| D05 | ✓ | 编辑 ID readOnly；buildArgs 只放 changed 键；thinkingChanged 以 initial（缺省显示 high）为基准；「还没有改动」且断言不含「没有变化」（W3b）；清空凭据变量 → 提示+禁用 |
| D06 | ✓ | useLivePreview：DEBOUNCE_MS=300、序号丢弃迟到回应、命令滤 --dry-run/--json；confirmEnabled=canPreview && current && result.ok（current=key 匹配），四条件齐 |
| D07 | ✓ | preview-warn 警告原文逐字（有/无 model 两分支）；preview-invalid 400/ok:false/exit_code null/data:null/ERROR: model 不合法；表单底部与确认框均现原文；M02/M06 被杀 |
| D08 | ✓ | NewProfileAction secondary/md、EditProfileAction ghost/sm+stopPropagation；页头次序保留；Dialog open=false 不渲染 → 关框无按钮（用例断言按钮集合与打开前一致）；M33–M35 reload 接线被杀 |
| D09 | ✓ | 六条文字逐字在 useWriteFlow.ts（src/writes/）；入口文件 diff 无这些文字；RolesPage/roles-ProfilesTable 无 T022 四禁词、无「新建 profile」「修改 profile」（T013/S10 扫描范围核过 diff） |
| D10 | ✓ | applyFinal 未改（先 setToast→resetFlow→reload）；W3 用例挂起 getProfiles 断言重读前整页无「已新建」、Toast 空 |
| D11 | ✓ | profileSnapshot 六字段投影、options?.thinking ?? null、按 id 排序；用例断言 adapter/多余字段/顺序颠倒仍相同 |
| D12 | ✓（人工逐条比对完成） | 见下节 |
| D13 | ✓ | changes.json 15 文件全在允许集合；forbidden 零触碰；无删文件；依赖/锁文件未动 |
| D14 | ✓ | contract_conflicts 空是真实的（补丁与检查未见被掩盖的冲突）；events-summary：temp_path_uses 空、temp_dirs_without_cleanup 空、problems 空 |

## D12/D14 人工审阅（P1 全绿证明不了的部分）

- **page-roles.test.tsx** 完整 diff 只有：用例名改「…[编辑] 可点（ghost/sm）」、`disabled).toBe(true)` → `toBe(false)`、新增 data-variant=ghost 与 data-size=sm 两条断言。是合同 D12 点名的改法，且净增强（原文件没有 ghost/sm 断言，现在加了）。
- **page-app.test.tsx** 完整 diff 只有：角色页禁用数 9→6 与用例名。9→6 的账能对上：[新建 profile]（1）+ 两行 [编辑]（2）转为可点，剩「保存当前为方案…、4×[更改…]、[切换…]」=6。
- summary 里「删除了 2 行含断言的代码」即上述两处被替换的旧断言行，均为合同指令内改动。七份 A/B 片 writes-* 与其他既有测试一字未动（diff 与 R01 733 passed 双证）。
- 无 skip/only/todo；6 条掩盖退出码的命令均为只读查看（events-summary 标 check:false），不在检查命令上。

## 执行端三处解读的裁定

1. **新建 thinking==缺省 high 时不传**：合同 argv 规格 `[--thinking=<t>]` 本就可选，「只传改动字段」规则对新建的类比合理；已记录在 interpretations、被 flow 探针与白盒按实际行为断言。接受。
2. **表单对话框标题「新建 profile」/「修改 profile \<id\>」**：合同只写死确认框标题，未写表单框标题；文字在 src/writes/，不进 T013/T022 扫描面。接受。
3. **成功后清空的时机=「A 片关框且带成功轻提示」**：我读了 useWriteFlow 源码核实——applyFinal 只有 done 分支持 toast，failed/partiallyWritten/unknown/rereadFailed 都关不了框或无 toast，onAck 也无 toast。所以「失败后值保留、成功后清空」成立，且与合同 §4 对成功流程的定义（关框→轻提示→reload）一致。接受。边界见「不挡的意见」第 1 条。

## 白盒与变异记录裁定

- 37 条变异全 caught、0 missed、0 skipped、无 equivalent 声明、无 unmutated 文件（11 个非测试文件全打满）——无需做「等价变异」或「不可变异」逐条裁定。
- 抽查 M27/M28 日志：是 W02 静态断言的真实 AssertionError（十六进制颜色、类名缺失），不是导入错误冒充。
- 空心断言排查：白盒含接线类变异（摘 CSS import 由 dist 构建产物断言杀、假 reload 由「表里出现新行/模型列刷新」的行为探针杀），说明探针跑的是真实实现；探针 mock 采用 spy 包装真实 api（importOriginal 委托），非硬编码回声。两处 `pass` 是 finally 清理代码。
- 503+ok:true 自造信封用例是 D06「200 且 ok」边界的测试内覆盖，不是对产品的新要求，不构成范围扩大。

## JEV 关注点核实

- 自行解读合同 p=0.95：三处解读全部记录在 executor-report 的 interpretations（内核 summary 亦确认「都在报告里」），非隐匿自选；上文逐条裁定均成立。
- 自述完成而无证据 p=0.88：每条 DoD 引用的 G01/R01/V01–V04 日志都在 checks/01/ 且全过，另经战后门禁独立复跑（白盒 7 passed + 37 变异）。证据充分。
- 弱化测试 p=0.47（置信仅 0.06）：D12 人工比对结论见上，无弱化，实为增强。

## 不挡的意见（不构成打回）

1. **doneWithWarning 路径不清表单**：写成功但带警告时，用户 ack 关框无轻提示 → 表单值保留。严格读「成功后清空」这是一处偏差，但合同 §4 把成功定义为「关框→轻提示→reload」流程，且静态夹具下无实害（重开表单值与夹具一致）。后续片若接真后端或改口径，注意白盒与 flow 探针的对应断言（已写入下游须知）。
2. **EditProfileAction 的 initial 在挂载时捕获**（useState 惰性初始化），而非对话框打开时。mock 夹具静态、profile prop 永不变，故在本产品内不可能漂移；接真后端后会过期。属合同已承认的「夹具静态」局限族，建议后续片顺手改成打开时取值。
3. useWriteFlow confirm 分派里 `spec.args as unknown as AddProfileArgs` 的双重断言绕过类型检查——buildArgs 保证运行时形状正确，M32 亦守着分派，但若后续片加 action，建议给 WriteSpec 做可辨识联合以获得编译期保护。

## 遗留

无。建议内核放行合并。

Verdict: PASS
