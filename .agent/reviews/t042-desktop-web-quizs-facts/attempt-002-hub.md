# 复审记录：t042-desktop-web-quizs-facts attempt-002（七端信箱 hub）

- 合同：t042-desktop-web-quizs-facts.v2（base d2fe3db4139109e2fc7c4a1ef6cde45cca113182）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261115T092044808568Z-4620），终审报告如下

## 终审报告

# T042-7-audit-post 终审报告

## 结论

**通过（PASS）**。候选 = 返工基线 `d2fe3db4`（attempt-001 的 7 个文件改动 + 门禁端热修补 `Pipeline.group()`），attempt-002 零新增修改（A0 M0 D0 T0，越界 0）。实现逐条忠实于合同 v2；既有断言只增不减；内核独立跑的四个必要检查全绿；战后白盒 4 条全绿、29 条变异全抓；无候选缺陷可裁定。

## 一、审的范围与方法（按任务书打法：先骨架，后抽样）

1. 候选源码：`ts/packages/ui/src/readroutes.ts`（接线段）、`src/redaction.ts`（两份白名单 + 三个校验函数）、`README.md`（四处）、三份既有用例的改动、`test/quizs-routes.test.ts` 全文件。
2. 执行证据：attempt-002 的 `summary.md`、`executor-report.md`、`scope.json`、`events-summary.json`、`checks/01/checks.json` 与 V01/V02/G01/R01 四份日志。
3. 门禁证据：`T042-6-gate-post/report.md`、`evidence/whitebox-*.py`（只读用例与探针结构）、`evidence/mutate-*/mutations.json`（逐条结果）。
4. JEV：`T042-6j-jev/report.md` = `no_opinion auth_failed` → 按「无意见」记，既不当反对也不当通过。
5. 未重跑全量基准（任务书：只审这次候选）。

## 二、DoD 逐条核对（终审视角：实现是否忠实于合同、测试有没有被弱化）

### D01 两条只读路由接上 — 忠实
- `readroutes.ts:46` `QUIZS_PROVIDERS_TIMEOUT = 60`、`:48` `QUIZS_LIVE_TIMEOUT = 150`（注释按既有常量写法）。
- `READ_ROUTE_ARGV:117-118`：`["config","quizs","providers","--json"]`、`["config","quizs","live","--json"]` 逐字。
- `readRoutes():630-642`：两条路由项，`exact("/api/v1/quizs/providers")` / `exact("/api/v1/quizs/live")`，走 `jsonRoute`，时限 `at("api.quizs.providers.get", QUIZS_PROVIDERS_TIMEOUT)` / `at("api.quizs.live.get", QUIZS_LIVE_TIMEOUT)`，白名单 `QUIZS_PROVIDERS_ALLOW` / `QUIZS_LIVE_ALLOW`，均不标 public（会话口径与既有 20 条一致）。
- `READ_ROUTE_SPECS:673-674` 追加为第 21、22 条；文件头三处条数注释改 22；`readroutes.ts:647` 「api.hub.roles.get 是第 20 条（追加在表末）」原文保留。
- `server.ts` 未改（补丁只含 7 个文件，见 D07）。

### D02 两份逐字段白名单 — 忠实
- 五个枚举（`redaction.ts:121-129`）：thinking 六档、billing 三值、source 两值、state 五值、missing 三文件名，取值与合同逐字一致。
- 三个可空校验：`allowNullablePreviewText`（null 放行，否则沿用 `allowPreviewText` 口径）、`allowNonNegativeMs`（null 放行；bigint 与 number 都接，number 须整数且 ≥ 0）、`allowIsoMsUtc`（`/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}(?:Z|\+00:00)$/u`）。
- `QUIZS_PROVIDERS_ALLOW:156-161` 恰好 4 条路径；`QUIZS_LIVE_ALLOW:168-177` 恰好 8 条路径，与合同「白名单」一节逐条对应。
- 不登记项按合同走默认口径：`build_id`、`live_dir`、`plan.*`、`implementation_digest`、`capabilities` 未登记；`credential_*`、`*_tokens` 靠默认口径遮（替身用例断言 `credential_ref`/`access_tokens` 为 `<redacted>`）。

### D03 出错映射与既有读路由一致 — 忠实
- 退出非 0 → 仍 200、`ok` 假、`exit_code` 原样、`messages` 带内核 `ERROR:` 原文（替身用例断言 `["ERROR: quizs providers 失败"]`）。
- 超时 → 504、`exit_code` 为 null、`data` 为 null、`messages` 只有一行 `ERROR: 命令超时（1 秒），子进程已结束；请改用 CLI 查看`（文案与 `kernelenvelope.ts:88` 同一处，非新写）。
- 退出 0 但 stdout 非 JSON → 500「内核输出不是合法的 JSON」（`readroutes.ts:191` 等既有分支，未新造口径）。
- 「某一套 live 读不出来」：真内核用例断言整条 200、`ok` 为真、该行 `problem` 有内容、`status` 为 null——服务没有替它造状态。

### D04 既有用例改到 22 条 — 只增不减
- `argv-templates.test.ts`：`toHaveLength(20)` → `toHaveLength(22)`，其余不动。
- `routes-auth.test.ts`：示例表 +2 行、`toBe(20)` → `toBe(22)`，其余断言（去重、逐条命中、401 逐条走表）未动。
- `kernel-runner.test.ts`：CASES +2 行、时限数组末尾补 `60, 150`、「时限四档」用例按合同改成五档并**按名字**断言新路由是 60 与 150（不是把 150 塞进豁免集合了事）。
- 补丁逐行核过：无删除、无 `skip`/`only`/`todo`（grep 四份测试文件零命中）。

### D05 新增 quizs-routes.test.ts — 替身 5 + 真内核 5
- 替身：`argv` 逐字 + 信封七字段（`Object.keys(body)).toEqual([...ENVELOPE_KEYS])`）、providers 白名单越界（thinking 第三档、billing、credential 形状）、live 白名单越界（`state` 越界、第四个 missing 文件名）、退出 1、504 超时。
- 真内核：起真内核（`scripts/pi_dispatch.py`，解释器取 `THEMIS_PYTHON`，仓库路径从 `harness.ts` 的 `REPO_ROOT` 推，**无写死绝对路径**）、git 夹具仓库（init + 一次提交）、`QUIZS_CMD` 指向夹具里的假 Quizs 脚本（按 `providers`/`live` 两支打印 `schema_version` 合法的 JSON）、覆盖两条路由的 argv 与逐字段、退出 1、以及 live 那一支失败时的逐套 problem。
- 环境变量卫生：`beforeEach` 记录并删除 `QUIZS_CMD`/`QUIZS_LIVE_PLAN`/`QUIZS_PROVIDER_PROFILE`/`QUIZS_QUALIFICATION`，`afterEach` 原样还原（执行机器上本来就设着也不会串进多一套）。
- V01 日志：该文件 `packages/ui/test/quizs-routes.test.ts (10 tests)` ✓。

### D06 README 与行为同步 — 同步
- 路由表 +2 行（含 60/150 秒时限）；「本片加的 22 条只读数据路由」；结构表 `src/readroutes.ts` → 22 条、`src/redaction.ts` 补两份 Quizs 白名单；「连接空闲超时」那条 → 「22 条读路由、预览、14 条写路由」。
- 首段历史叙述「第 2 片加 20 条只读数据路由」保留；写路由 14 条与三处不许动的段落一字未改（README 的补丁只有 4 个 hunk）。

### D07 范围 — 合规
- `git diff --name-only 53f2d47 HEAD`（执行端在 events 里实跑）：`tests/test_gate_t042_baseline.py`（门禁端提交 `08817cbb` 所带，非执行端）+ 7 个允许文件：`ts/packages/ui/{README.md,src/readroutes.ts,src/redaction.ts,test/argv-templates.test.ts,test/kernel-runner.test.ts,test/quizs-routes.test.ts,test/routes-auth.test.ts}`。
- attempt-001 的 candidate.patch 逐个文件核对，也正是这 7 个；`scope.json` 越界 0、警告 0；门禁文件、`scripts/**`、`desktop/web/**`、`server.ts`、`ts/package.json`、`ts/bun.lock` 一个字没动。

### D08 不弱化测试 — 合规
- 四份测试文件无 `skip`/`only`/`todo`；`ts` 既有用例原样通过（V01 41 files / 358 tests）；门禁与回归全绿（见第三节）。

## 三、内核独立跑的检查（attempt-002 `checks/01/checks.json` + 日志）

| 检查 | 命令 | 退出码 | 输出 |
|---|---|---|---|
| V01 | `node node_modules/vitest/vitest.mjs run packages/ui/test`（ts） | 0 | `Test Files 41 passed`、`Tests 358 passed`；quizs-routes.test.ts 10 tests |
| V02 | `node node_modules/typescript/bin/tsc -p tsconfig.json`（ts） | 0 | 空输出 |
| G01 | `python -m pytest tests/test_gate_t042_baseline.py -q` | 0 | `12 passed in 22.52s` |
| R01 | `python -m pytest tests/test_gate_t001…t041_baseline.py -q` | 0 | `974 passed in 1282.87s` |

`modified_by_checks: false`、`candidate_files_modified: []`、`covers_all_required: true`、`all_required_passed: true`。执行报告自述的条数与退出码与内核记录一致（`358 passed / 41 files`、`12 passed`、`974 passed`）。

## 四、门禁端声明的逐条判断

1. **白盒 4 条全绿、无 candidate_defects**：本回合输入没有「门禁端举证的候选缺陷」一节，无可裁定项；门禁报告的自述与 `mutations.json` 一致。
2. **29 条变异全抓**（`counts: caught 29 / missed 0 / skipped 0 / errored 0`）：清单覆盖执行端改动的三个非测试文件各 ≥1 条（readroutes 11、redaction 15、README 3）。接线类变异都在清单里——去掉 import 里的 `QUIZS_LIVE_ALLOW`（M05）、处理器换成 `HUB_ROLES_ALLOW`（M08）、删掉 `READ_ROUTE_SPECS` 登记行（M10）、state 路径换成 source 枚举（M24）、删掉 providers 的 provider 路径（M25）、删掉 live 的逐套 problem 路径（M26）——即「接上了但接错」这一类测得到，不是只测文本。
3. **白盒不是空心断言**：静态三条只读源码文本，但第四条是 vitest **行为探针**（临时写 `ts/packages/ui/test/gate-probe/`，跑完即删），直接调三个校验函数与五个枚举，并对两份白名单跑 `redactJson`，钉住 0n / -1n / 1.5 / 缺毫秒 / `+00:00` / 凭据形状的自由文字 / 带空格的名字 / 未登记字段原样等边界——执行端与基准探针都没覆盖的组合。
4. **门禁端没有「没法变异」的文件**，不需要我裁定豁免。

## 五、自述与内核摘要的对照（发现，均不挡）

1. **措辞过强**：执行报告写「工作目录与给定基线逐字节一致」，而内核摘要列出新增被 Git 忽略的路径 `.pytest_cache/`、`desktop/web/dist/`、`desktop/web/node_modules/`。核对结果：这些是被忽略的缓存与构建产物（`.gitignore:15-16` 明确忽略 `desktop/**/node_modules/`、`desktop/**/dist/`；pytest 自己写 `.pytest_cache/.gitignore`），**tracked 内容确实一致**，且不在候选补丁里（attempt-002 的 candidate.patch 为空）。措辞不严谨，不是缺陷。
2. **3 条掩盖退出码的命令**：`git show --stat HEAD | head -30`、`grep … | head -50`、`ls ts/packages/ui/test/gate-probe … | wc -l`——都是查看类命令，不是 V01/V02/G01/R01 里的任何一条；四个检查命令本身用 `set -o pipefail` 跑，并且由内核在候选树上独立跑过（退出码 0 属实）。合同「输出管道必须保留被检查程序的真实失败状态」针对的是检查命令，此处不违反。
3. **真内核用例走进程内 `createApp` + `KernelRunner`**（不经 TCP 监听），而不是像 `hub-routes-real.test.ts` 那样起真实服务。核对：路由匹配、信封拼装、错误映射、会话握手（真做了 bootstrap + cookie）仍是真代码路径，断言的 200/504/退出码/逐字段 data 全部经由真实内核子进程；合同只要求「起真的内核 + git 夹具仓库 + `QUIZS_CMD` 假脚本」，未要求独立进程。不挡。

## 六、不挡的意见（供站主与下一片）

- `QUIZS_CMD` 与三个 `QUIZS_LIVE_*` 是**用户级环境变量**（仓库外事实）：真窗口验收时启动 Electron 的环境必须设好，否则 Quizs 原生启动器不认这两条命令，路线那一块会报 Quizs 跑不起来。这条仓库里改不了，落到站主的验收环境上（上游各阶段已一致提示）。
- 真内核用例不覆盖 HTTP 监听层；真窗口若对会话/并发有疑义，以真窗口为准。
- 战后白盒 `tests/test_gate_t042_whitebox.py` 是门禁端新增的未提交文件，它把「候选恰好 22 条、新路由恰在第 21/22 位」钉死（比基准门禁的「不早于」更严）；后续片再加读路由时，这两条要按站主口径同步放宽（先改基准门禁，再改白盒）。

## 七、阻塞项

无。

Verdict: PASS
