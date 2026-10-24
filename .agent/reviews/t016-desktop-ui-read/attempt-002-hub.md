# 复审记录：t016-desktop-ui-read attempt-002（七端信箱 hub）

- 合同：t016-desktop-ui-read.v2（base 656a5d6753406df2a21239f877dc56a857a9e40a）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T016-7-audit-post 终审报告

审核端：audit-sonnet，2026-10-24（UTC）。对象：`.agent/runs/t016-desktop-ui-read/attempt-002/candidate.patch`（8 文件）、执行报告、战后门禁记录（白盒 26 条、36 条变异）、JEV 判断（无意见）、一审移交重点。

## 结论：通过

候选可合入，D03 做旧这一点已核对。

## 一、站主点名项：D03 用例是否先把锁目录做旧再探

- `ts/packages/ui/test/lockdir.test.ts:119-131`「自己的 pid 加一个关闭的端口：连接被拒 → 接管」注入 `now: () => Date.now() + PROBE_TAKEOVER_MIN_AGE_MS + 60_000`；`lockAge = now() - statSync(dir).mtimeMs`，注入后年纪约 60 秒 > 10 秒，属先做旧再探，不是在新鲜锁上探 refused 就断言接管。
- 对侧用例（:134-141）「锁目录还新时端口连不上」不注入时钟，断言 busy running、提示原文、锁目录未被删——10 秒保护两侧都钉住。
- `src/lockdir.ts` 的 `PROBE_TAKEOVER_MIN_AGE_MS = LOCK_STARTUP_MS`（10000）只在 refused 分支查年纪；connected/timeout/other、端口 null、pidAlive null 各分支与合同 T19 一字不差；`server.ts` await 拿锁。
- 白盒 `test_d03_takeover_case_ages_the_lock` 用正则强制接管用例含 now 注入、还新用例不得推时钟，与候选一致。

## 二、执行概述三处解读（对照站主认可）

1. file 最后一页 `next_cursor` 为 null：`readroutes.ts:393-402` `hasNext = done !== true && …`，done 为真时给 null、不发句柄；`kernel-real.test.ts` 第二页断言 `next_cursor` 为 null。符合站主认可（file 最后一页 done→null）。
2. T19 的 10 秒保护：站主已认可；实现、用例、白盒三层核对一致（见上）。
3. argv 组名剥离与开关豁免：`argv-templates.test.ts` 对 logs/plugins/config 剥组名交 kit_* 解析器（与内核 argparse 前截获转发的事实一致），`--version`/`--json` 作为不取值开关豁免「--opt=值」；白盒 `test_argv_templates_parsing_conventions` 钉住恰好三处剥离。符合合同 U4 的意图（模板被内核真正的解析器解析）。

## 三、门禁证据

- 变异：内核存档 36 条（M01–M36，mutation-spec-20261024T141233761830Z.json，锚点 0 条不符），mutations.json 逐条 status=caught，覆盖合同 M1–M21 每一类；baseline passed。
- M09 漏网修复（甲方案）核实：白盒 `test_kernel_runner_source`（:316-369）对 kernel.ts 先逐字符剥行注释（跟踪字符串状态）再做子串断言，报错文案带「（剥注释后）」；`AbortSignal.any` 与 queue-full 检查同样用剥后文本。门禁端等价验证（注释化该行→1 failed/25 passed；恢复→26 passed、文本逐字一致）有记录，CRLF 事故已用 git checkout 恢复。
- 白盒 26 条在候选上全绿（whitebox-20261024T142749330996Z.log：26 passed in 20.56s），无 skip/xfail（`test_no_skip_or_xfail_in_ui_tests`）。
- 白盒不含 service.test.ts 的理由成立：它是第 1 片既有集成测试，V04 两红经站主核实为计时抖动（候选树单跑 5 次全过、全量 3 次 576/576）；T016 行为由 ui 包 21 文件 174 条用例钉住。
- 一审移交的人工审阅项抽查：U28（10 请求、峰值 ≤4 且 >1、`retry-after` 恰为 "2"、503 信封 messages 逐字）；断开/关停取消都轮询 `pidAlive(pid) !== false` 至 pid 真消失（10 秒期限）；超时信封 exit_code=null、messages 单行原文（kernel-runner:170-181 与 kernel-real:162）；U9 逐字节（CRLF 归一的 cliText 对 rendered(data)，file 把句柄换回 CLI next_cursor 再比，kernel-real:106/:120-121）；每路由时限与示例表由白盒 `test_read_route_specs_and_timeouts`、`test_routes_auth_example_table` 钉住。均落实。

## 四、范围与长期断言

- 内核 check --fresh 通过、范围违规 0、站主 exec-recheck 复核；候选 8 个文件全在允许清单内；`UiArgs`/`package.json`/锁文件未改、无新依赖。
- T015 长期断言：白盒 `test_t15_long_term_assertions` 通过；R01 576 passed；三条 busy 提示原文逐字保留（lockdir.ts busyMessage 与测试 :139-141、:170-172）。

## 五、README（D16）

结构表（六个新源文件）、最小 API（19 条与时限）、状态码 409/503+`Retry-After: 2`/504、已知限制齐备；决策 key 一节写明 source **不会**是 env、权威口径是终端里 `config secret check`、原因（开始菜单/资源管理器、登录时的用户与系统环境变量、终端临时变量与 PowerShell profile 看不到）、前端文案不在本片。V08 通过。

## 六、非阻塞观察（留档，不影响结论）

- 白盒对 readroutes.ts、redaction.ts、cursors.ts、kernelenv.ts 等源文件的子串断言未剥注释（剥注释只加在 kernel.ts 组）。这些文件的语义主要由 vitest 行为用例钉住，注释化会先弄坏行为测试，风险低；建议门禁端后续统一剥注释。
- 一审留档的 harness 解构默认值写法不识别问题，本轮候选未触发，维持不升级。

## 七、结论

通过。候选可合入，D03 做旧这一点已核对。无阻塞项，无 candidate_defects。

Verdict: PASS
