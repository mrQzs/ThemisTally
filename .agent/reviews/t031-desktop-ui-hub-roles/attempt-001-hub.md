# 复审记录：t031-desktop-ui-hub-roles attempt-001（七端信箱 hub）

- 合同：t031-desktop-ui-hub-roles.v2（base cd13d10756fd0025b67f0b604601118510126b80）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261113T070506222401Z-0d64），终审报告如下

## 终审报告

# T031-7 终审报告（audit-sonnet · 审核端）

任务：T031 桌面端本机服务第 8 片「七端岗位绑定的读写路由（模型配置 M3）」终审（-7-audit-post）。
候选：执行端 attempt-001，候选树 `879f9eb97486b30fb0f5761230fec857bb645edc`，基线 `cd13d10756fd0025b67f0b604601118510126b80`。

## 0. 结论

**通过**。无阻塞项。实现忠实于合同 v2；门禁端标为「这条命令预期抓不住」的那条（M17 / W2）经复核属实，不构成候选缺陷；执行端自述与内核记录对得上，没有把没做的事报成做了。

本回合我只读，未改任何文件。

## 1. 我核了什么

| 材料 | 路径 |
|---|---|
| 合同 v2（唯一口径） | `.agent/plans/t031-desktop-ui-hub-roles.v2.md` |
| 候选补丁（12 文件，+656/−74） | `.agent/runs/t031-desktop-ui-hub-roles/attempt-001/candidate.patch` |
| 候选源码（工作目录里的候选树） | `ts/packages/ui/{src/readroutes.ts,src/redaction.ts,src/writeroutes.ts,README.md,test/*}` |
| 执行概述与执行报告 | `.agent/runs/.../attempt-001/{summary.md,executor-report.md,executor-report.json,events-summary.json}` |
| 内核的检查记录（权威退出码） | `.agent/runs/.../attempt-001/checks/02/{checks.json,V01.log,G01.log,R01.log,V02.log,V03.log}` |
| 战后门禁报告 | `.agent/mailbox/tasks/T031-6-gate-post/report.md` |
| 白盒测试 / 变异记录 | `.agent/mailbox/tasks/T031-6-gate-post/evidence/whitebox-…py`、`evidence/mutate-…/mutations.json` + 34 份变异日志 |
| 执行概述的 JEV 判断 | `.agent/mailbox/tasks/T031-6j-jev/report.md` → `no_opinion auth_failed`（无意见，不构成阻塞） |

本回合无 bash 工具，我不跑命令；结论以源码、补丁、内核检查记录与门禁变异日志为据。

## 2. 实现忠实性（逐条对合同）

| 合同条款 | 实现落点 | 核对 |
|---|---|---|
| §1 第 20 条读路由 `api.hub.roles.get`，GET `/api/v1/hub/roles`，30 秒 | `readroutes.ts:609-613`（路由项）、`:103`（`READ_ROUTE_ARGV`）、`:641`（`READ_ROUTE_SPECS` 第 20 条，追加在表末） | ✓ argv 恰为 `["config","hub","show","--json"]`；处理器用 `jsonRoute(..., HUB_ROLES_ALLOW)`；`DEFAULT_TIMEOUT=30` |
| §1 readroutes.ts 去注释后不许出现 `WRITE`/写路由名 | grep 全文 | ✓ 一处也没有（`hub` 只出现在 `api.hub.roles.get` 与注释里） |
| §1 两处「19 条」注释改 20 | `readroutes.ts:1`、`:434`、`:618` | ✓ |
| §2 `HUB_ROLES_ALLOW` 恰好 15 条路径 | `redaction.ts:101-117` | ✓ 逐条与合同表一致；`posts.*.fallback` 本身未登记；`posts` 下无别的路径 |
| §2 可空字段放行 null | `allowNullableId`（`value===null \|\| allowId`）、`allowBindingName`（首句 null 放行）、`HUB_ADAPTER_ENUM`/`HUB_THINKING_ENUM` 的 choices 带 null | ✓ 与合同写死的函数体逐字相同 |
| §2 `allowBindingName` 正则 | `redaction.ts:25-29`：`/^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$/u` 且 `!tokenShaped` | ✓ 与合同逐字相同（正则内联是合同 §2 第 3 条自己给的写法，不是为过门禁的特判） |
| §2 出处注释 | `redaction.ts` 的 `HUB_ADAPTER_ENUM`/`HUB_ROLES_ALLOW` 注释、`writeroutes.ts` 的 `HUB_POSTS` 注释 | ✓ 岗位名与适配器名注明抄 `scripts/kit_roles.py` 的 `HUB_POST_ADAPTERS`/`ADAPTERS` |
| §3 两条写路由 | `writeroutes.ts:610-621`（`api.hub.roles.set` / `api.hub.roles.unset`，路径参数键 `post`，正则 `([^/]+)`，unset 在后） | ✓ `/api/v1/hub/roles/coordinator/unset` 不会被 set 接住（`[^/]+` 不跨 `/`）；action 名逐字 `hub.set`/`hub.unset` |
| §3 校验 | `validValue` 的 `post`（六岗位枚举）与 `fallback`（`TASK_ID_RE`）两行 | ✓ 提示固定不回显、不合格不起子进程（替身报告无 begin 行） |
| §3 路径参数压正文 | `mergeArgs` 未改（路径参数后写、覆盖正文） | ✓ |
| §5 `OPEN_WRITE_COMMAND_PATHS` 14 条、`PENDING` 导出保留且为 `[]`、`NOT_OPEN` 未动 | `writeroutes.ts:123-138`/`:145` | ✓ 既有十二条一条不改不删 |
| §5 `WRITE_ARGV` 15 行示例 | 含 `hub.set`/`hub.unset` 两行 | ✓ |
| §7 README 九处 | 逐处核对 | ✓ 路由表三条新路由在位；八处条数全 20/14；无「19 条」「12 条写路由」残留；T020 保留；既有段落一字未动（补丁逐行核过） |

**实现里没有为过测试写的特判**：`validValue` 用真枚举、`mergeArgs` 用真合并、白名单用真约束；唯一两处「为别的门禁让路」的动作（`READ_ROUTE_SPECS` 挪位、正则内联）都写进了执行报告的 interpretations，且合同本身就给了正则内联的写法、没规定 const 的位置。

## 3. DoD → 证据映射（D01–D15）

| DoD | 证明它的检查/断言 | 备注 |
|---|---|---|
| D01 | V01（`routes-auth` 401+顺序、`kernel-runner` argv+时限数组、`argv-templates` 真解析器）、G01 | argv/时限/401/模板四处独立钉住 |
| D02 | V01 替身白名单断言（越界枚举、带空格的绑定名、凭据形状 model、越界 ID → `<redacted>`；null 原样）+ V01 真内核 U9 整份 `toEqual` | 变异 M1/M2/M3 实证被抓 |
| D03 | V01 替身 argv 逐项 + W4 `buildWriteArgv` + W1 过内核真解析器 | M6/M7/M16 实证被抓 |
| D04 | V01 W4 新用例（post 不认识/profile 与 fallback 以 `-` 开头/fallback 不合格/未知键/缺必填）+ 替身 7 例 400 且无 begin 行 | M4/M5 实证被抓 |
| D05 | V01 W2（14 条、与内核 `--dry-run` 集合逐条相等、两表不相交） | M8/M9 实证被抓 |
| D06 | V01 替身四种 409（缺号/换参数/用第二次/过期）+ 两种提示原文 + 无带 `--expect-state=` 的 begin 行 | M11 实证被抓 |
| D07 | V01 真内核 U6b（409、`exit_code` 4、`stale`、`.agent/` 快照逐字节不变） | — |
| D08 | V01 真内核 U7（actor 逐字 `user-ui`、再读 `source=config`、profile 新值） | — |
| D09 | V01 真内核 U9（整份 `data` 与 `config hub show --json` 的 stdout `toEqual`，加逐行点检） | — |
| D10 | V01 `write-config` 令牌表 14 行 × 4 查法 | M12 实证被抓 |
| D11 | 补丁逐行核对（四份锁定测试只改点名处）、scope（12 文件全在允许集合、0 越界）、G01/R01 | 白盒另钉依赖清单/`public: true` 两处/无 WRITE |
| D12 | V01 + G01 + R01 + 补丁逐行核 README | README 的 20/14 一致性本片无机械判据（合同端已把门禁放宽成「只认写明了」），由 D12 + 白盒 + M17 承担 |
| D13 | scope：12 文件 = 10 改 + 2 新，全在 `allowed_modified_files`/`allowed_new_files`；`tests/test_gate_*`、`server.ts`、`routes.ts`、`localhttp/**`、`package.json`、`ts/bun.lock`、`base/**` 一个都没动 | ✓ |
| D14 | 补丁逐行：被删的断言行都对应合同点名的数字/名单更新（19→20、12→14、时限数组补 30、名单加两个名字、示例补齐）；新增两份用例无 `skip/only/todo`（grep 确认） | ✓ |
| D15 | 源码核对：action 名逐字、三个符号都在 `redaction.ts`、`server.ts` 零改动、`PREVIEW_ALLOW`/`allowPreviewName` 零改动（redaction 补丁只增）、新用例等子进程用 `waitForBegins` | ✓ |

D12 里「README 与实现一致」这一条**只能人工审阅**（本片无机械判据，见 pre-audit 的下游须知第 2 条）；我逐行核过补丁，结论成立。

## 4. 测试质量检查（终审重点）

- **空心基线**：没有。两份新用例都起真的服务进程（`harness.ts` 的 `startService`），断言落在真实响应体与替身报告的 begin 行上，不是「文件不存在导致失败」。
- **空心断言**：替身那一支的读路由走 `fake-kernel.mjs` + `FAKE_KERNEL_JSON`（写路由那一支走 `fake-write-kernel.mjs`，两个替身各起各的服务实例），白名单断言是「越界值变 `<redacted>`、合格值与 null 原样」的**行为**断言；真内核那一支的 U9 是与内核 stdout 的整份 `toEqual`。没有「只读源文件文本就说它在产品里生效」的情况。
- **硬编码输入**：替身 JSON 里的越界值（`bogus-adapter`/`bad model`/`bad provider`/`Bad_Profile`/凭据形状 model）是**故意**的越界样本，且执行端在 interpretations 里说明了它们是为杀 M1 的约束面补的；默认值一律取内核合同点名的名字（deepseek、minimax、cc-switch-zhipu-glm、cc-switch-step-fun、dsf、deepseek-flash、MiniMax-M3.1-Flash、claude-opus-5-5、glm-5.3、step-5-preview）。
- **空异常处理/特判**：源码里没有为通过用例加的分支；`validValue` 的 `post`/`fallback` 是真校验。
- **范围悄悄扩大**：补丁 12 文件全在允许集合；新增的 git 忽略产物（`.pytest_cache/`、`desktop/web/dist/`、`desktop/web/node_modules/`）不在补丁里，不进候选。

## 5. 门禁端标为「预期抓不住」的变异：逐条复核（M17 / W2）

门禁端声明：M17（README「写操作」条数退回 12 条）标 `expect_missed: ["W2"]`，由白盒 W1 抓。

我的复核：

1. W2 的命令是 `node node_modules/vitest/vitest.mjs run packages/ui/test/{hub-routes,write-argv,kernel-runner,write-config}.test.ts`（cwd `ts`），只跑这四个 vitest 用例文件。
2. grep 整个 `ts/packages/ui`：**没有任何一个用例读 `ts/packages/ui/README.md`**；命中的 `README.md` 全是夹具仓库里 `writeFileSync(join(repo,"README.md"))` 的写入，与包内 README 无关。
3. `M17-W2.log`：4 个文件 59 用例**真跑真过**（`Tests 59 passed`）→ 是「真的测不到」，不是跑挂了或命令没执行。
4. `mutations.json` 里 M17 的 W1 状态 `caught`（exit 1），W2 `missed`（exit 0）——与声明一致。
5. 17 条变异里**只有** M17 的 W2 是 missed；M01–M16 的源码变异全部被行为命令 W2 抓到（我逐条看过状态，例如 M02 是替身用例的 `expected '<redacted>' to be null` 真抓的，不是静态检查抓的）。

**裁定：门禁端的声明属实，M17 由白盒真杀，不构成候选缺陷，不退回。**

## 6. 执行端自述 ↔ 内核记录的对账

| 内核摘要里的线索 | 我的核对 | 结论 |
|---|---|---|
| 「新增被 Git 忽略的路径：`.pytest_cache/`、`desktop/web/dist/`、`desktop/web/node_modules/`」 | 都不在 `candidate.patch` 里（补丁只有 12 个 `ts/packages/ui` 文件），scope 检查 0 越界 | 不进候选，不构成越界 |
| 「删除了 8 行含断言的代码」 | 补丁逐行核：被删的断言行都对应合同点名的数字/名单更新，每处都有等价新行（`toBe(19)`→`toBe(20)`、`toHaveLength(12)`→`toHaveLength(14)`、时限数组补 30、action 名单加两个名字、示例补齐）；`READ_ROUTE_SPECS` 是整块挪位（内容为原 19 条 + 新 1 条） | 无弱化 |
| 「6 条检查命令的退出码被管道掩盖」 | 内核 `checks/02` 独立跑了五条：G01 exit 0（`20 passed`）、R01 exit 0（815 passed）、V01 exit 0（`40 files / 346 passed`）、V02 exit 0（空输出）、V03 exit 0（13 passed），五条 `output_must_match` 全中；`modified_by_checks=false`、`candidate_files_modified=[]` | 自述的「All checks pass」与内核记录一致，无不实 |
| 「临时路径 / 可疑命令」 | `events-summary.json`：`temp_dirs_without_cleanup: []`、`problems: []`、`ok: true`；命令清单里没有固定路径写入（都在 `ts/`、`tests/` 内） | 无临时路径问题 |
| 「执行器自行宣布了 9 处解读」 | 这 9 处是事件流里提及解读的次数（同一话题多次自问），不是 9 条不同决策；执行报告里的 6 条 interpretations 覆盖了这些话题（M14 读法、过期 TTL 造法、`READ_ROUTE_SPECS` 挪位、正则内联、起服务方式、替身 JSON 增强），另有 1 条 limitations、0 条 contract_conflicts、0 条 unresolved_questions | 无漏报的自定口径 |
| DoD 自述 D01–D15 全 done | 我逐条对源码与内核记录复核（见第 3 节），全部成立 | 无「把 D14 报成 done」那类不实 |

**M14 的读法裁定（独立于门禁端）**：合同 §3 正文明文「路径参数压过正文里的同名键」，D15 变异表那句「正文给错 post 时回 409 参数不符」描述的是**变异后**代码的症状。执行端断言「正文给错 post 仍按路径执行、argv 用路径的 post（200）」是正确行为的断言，且真能杀 M14（门禁 M14 变异实证 caught）。成立。

**过期 409 的造法**：用的是 `server.ts` 里本来就有的测试入口 `ServeOverrides.confirmationTtlMs`（禁区文件零改动），合同「不许固定睡几百毫秒」的主语是「凡是要等子进程起来」，TTL 等待是另一件事。成立。

## 7. 不挡的意见（写进 report，不进阻塞项）

1. `src/server.ts` 是禁区文件，本片不能改，但里面三处注释仍写「19 条读路由 / 12 条写路由」（`:95`、`:121`、`:148`）。下一片若动 server.ts 请一并更新，否则留给站主。
2. `ts/packages/ui/test/write-config.test.ts:201` 的行内注释仍写「十二条命令的预览参数…」（合同 §4 第 5 条只点了 describe 名与文件头注释）。一个词的活，可顺手改。
3. README 文件头「第 2 片加 20 条只读数据路由」按合同 §7 第 1 条的字面要求改的（历史上第 2 片确实是 19 条），照合同执行即可，不挡。
4. `READ_ROUTE_SPECS` 挪到 `readRoutes()` 之后，是为迎合静态门禁 `_block(code, 'name: "api.hub.roles.get"')` 的「第一处匹配」语义；语义无害（导出顺序不影响任何调用方），但**下一片加第 21 条读路由时会再撞一次**。建议门禁端把锚点改成带上下文的标记（或按 route name + `pattern` 联合定位）。
5. 白盒里 README 的整页否定（「19 条」「12 条写路由」不许出现）与合同 §7 第 9 条绑定：下一片改条数时**必须连同合同一起放宽**，否则必红。门禁端已写进下游须知，我再确认一次。
6. 执行端自述的 limitations（M1 对「只可能出现合法值」的字段是等价变异）属实：真内核与替身的数据都触发不到那些字段的白名单约束。合同 M1 点名的例子 `fallback.model` 已被替身真杀，不构成缺陷。
7. 门禁的白盒文件 `tests/test_gate_t031_whitebox.py` 与工作目录根的 `mutation-spec.json` 不在 `candidate.patch` 里（是门禁产物，不进候选）。要把它当仓库里的长期回归测试留着，需要站主另行决定入库。

## 8. 结论

**通过**。实现忠实于合同 v2，DoD D01–D15 全部成立，范围没有越界，既有测试没有被削弱，门禁端标的那条「预期抓不住」的变异经复核属实（M17 由白盒 W1 真杀）。**无阻塞项，不退回任何一端。**

Verdict: PASS
