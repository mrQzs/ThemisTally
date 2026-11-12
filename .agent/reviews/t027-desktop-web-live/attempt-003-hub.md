# 复审记录：t027-desktop-web-live attempt-003（七端信箱 hub）

- 合同：t027-desktop-web-live.v5（base d54160087c806cdcd95f9b8e6d8bae5078ecb55a）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261112T203947455916Z-6a1a），终审报告如下

## 终审报告

# T027-7 终审报告（attempt-003，A 片返工第 2 轮）

结论：**通过**（无阻塞项，无退回对象）。

复核口径：上一轮（attempt-002）我只列了 B1 一条阻塞项，其余条款已封板。本轮按「复审封板」只复核 B1 与本轮新改动，并把新改动里可能出现的严重问题再扫一遍；已封板条款不重开。

## 一、B1 逐条复核（唯一阻塞项）

B1 原文（合同 v5 Rework 附录 :374-378）要求：读体失败必须收场成七字段信封、绝不 reject；我方中止/AbortError → 合同第 1 条文案；其余读体错误 → 第 2 条（≥400 也可按第 5 条）；两种都置 disconnected；并补「text() 抛错」与「中止计时器在读体期间到点」两条用例。

| B1 要求 | 候选实现（`desktop/web/src/live/transport.ts:140-151`） | 证明它的东西 | 结论 |
|---|---|---|---|
| 读体失败收场成信封、**绝不 reject** | `let body: unknown;` + 内层 `try { body = parseJson(await response.text()); } catch (error) { … }`，catch 里三条路径全是 `return failure<T>(…)`，没有 rethrow | 执行端 `live-transport.test.ts:299/307/315` 三条新用例都 `await client.get(...)` 后 `expect(env).toEqual(failureEnvelope(...))`（若 reject，用例会直接抛出失败）；白盒探针 4 条同款断言 | 解决 |
| 我方中止 / AbortError → 第 1 条文案 | `if (timedOut \|\| (error as Error)?.name === 'AbortError') return failure<T>(MSG_TIMEOUT(Math.round(timeoutMs / 1000)));`（:147-149） | 新用例 3（:315）断言 `ERROR: 请求超时（35 秒），没有收到服务的回应`（30 秒路由 + 5 秒 = 中止秒数，与合同第 1 条的 N 定义一致）；白盒探针 3（读体期间超时）与探针 4（非我方中止的 AbortError） | 解决 |
| 其余读体错误 → 第 2 条；≥400 可按第 5 条 | `return response.status >= 400 ? failure<T>(MSG_HTTP(response.status)) : failure<T>(MSG_DISCONNECT);`（:150） | 新用例 1（200 + TypeError）→ `ERROR: 连不上本机服务（请求没有到达服务）`；新用例 2（502 + TypeError）→ `ERROR: 服务返回 HTTP 502`；白盒探针 1/2 | 解决（选了第 5 条，与合同 §2「状态码优先于正文」一致，属我在 B1 里明确允许的两种写法之一） |
| 两种都置 `disconnected` | catch 首行 `setConnectionState('disconnected');`（:146） | 三条新用例都断言 `getConnectionState()).toBe('disconnected')`；白盒探针 1/2/3 | 解决 |
| 补两条用例并断言是信封不是 reject | `bodyThrows`（text() 直接 reject）、`bodyHangsOnSignal`（体挂起到 signal 中止）两个假响应 + 三条用例（:299、:307、:315）；第 3 条显式 `expect(rejected).toBe(false)`，另断言 `signal.aborted === true`、`vi.getTimerCount() === 0` | V01 日志：`tests/live-transport.test.ts (18 tests)` 通过；执行端自测记录：把 `transport.ts` 换回基线带 bug 版后正是这 3 条红（3 failed / 15 passed），换回修复版 18/18 —— 说明这 3 条不是空心断言，去掉 catch 就会红 | 解决 |

补一条我特意核的：新代码块仍落在外层 `try { … } finally { clearTimeout(timer) }` 里，`return` 会先走 finally，计时器不会泄漏；用例 3 的 `expect(vi.getTimerCount()).toBe(0)` 钉住了这一点。

## 二、本轮新改动的内容审查

- **范围**：candidate.patch 只两个文件（`desktop/web/src/live/transport.ts`、`desktop/web/tests/live-transport.test.ts`），与 scope.json（M2、violations 空）、changes.json 一致；两个文件都在合同 v5 的 allowed_modified_files（:69、:75）里；没有碰 `tests/**`、`ts/**`、`scripts/**`、package.json/lock。
- **有没有为过测试而写的特判**：没有。catch 里的分支只依赖 `timedOut`、错误名、状态码三个真实输入，与假响应的形状无关。
- **有没有弱化既有测试**：没有。测试文件的 diff 全文是新增（两个辅助函数 + 三条用例），既有 15 条断言一字未动；我独立数过：18 条 `it(`、2 个 `describe(`，无 `.skip`/`.only`/`.todo`。
- **有没有空心断言**：三条新用例都打到真实的 `get()` 路径（假 fetch → `response.text()` 真的 reject / 真的挂起到中止），去掉 catch 就会红（执行端与门禁两侧都独立验过）。
- **异常处理是不是空的**：不是，catch 里三条 return 路径都有文案与状态处理，没有空 catch、没有 `catch {}` 吞异常。
- **悄悄扩大的范围**：没有。

## 三、内核检查与门禁记录核对

内核 checks.json 五条 required 检查全部 `exit_code 0`、`passed true`，`output_must_match` 全部 `matched: true`，`candidate_files_modified` 与 `unexpected_files_by_checks` 均为空，`covers_all_required: true`。我逐份读了日志原文：

| 检查 | 日志原文 | 判定 |
|---|---|---|
| G01 | `26 passed in 43.34s` | 绿 |
| R01（T001–T026） | `777 passed in 909.96s` | 绿 |
| V01 | `Test Files 104 passed (104)` / `Tests 977 passed (977)`，其中 `tests/live-transport.test.ts (18 tests)` | 绿 |
| V02 | `tsc --noEmit && vite build` → `✓ built in 1.13s` | 绿（类型检查也在内） |
| V03 | `LIVE_BUILD_OK 3/3` | 绿 |

战后门禁（T027-6）本轮口径：只对执行端本轮改动的非测试文件 `transport.ts` 编 5 条变异，全部打在 B1 修复段上（撤掉 try/catch、去掉 disconnected、AbortError 判定退化成只看 timedOut、≥400 分支退成一律 MSG_DISCONNECT、超时秒数写成 0），记录 `caught 5 / missed 0 / error 0`，`files_left_modified` 为空。**逐条判断是不是真的测不出来：都不是** —— 这 5 条每条都打在 B1 新写的代码上，且都有对应的红点（w12 静态锚点 + 4 条探针）。上一轮的 38 条变异随基线 d541600 入库，本轮树相对它只差这两个文件；我核过归档清单里 transport.ts 的旧锚点在候选里仍然唯一（`if (response.status >= 400) {` 仍只出现一次），旧结论对未改动的部分继续成立。

JEV 判断（6j）：`no_opinion auth_failed` —— 无意见，不影响本轮结论。

## 四、执行报告 DoD 自述 vs 内核摘要线索（逐条对账）

| 内核摘要里的线索 | 执行报告的自述 | 对账结果 |
|---|---|---|
| 「新增被 Git 忽略的路径」：`.pytest_cache/`、`desktop/web/dist/`、各处 `node_modules/` | 「`dist/` 已被 .gitignore 忽略」「无未跟踪残留文件（`.orig` 备份已删）」 | 对得上：这些都是跑 pytest/npm 产生的忽略项，未进候选（candidate.patch 只有 2 个文件）。我另外查了工作目录 `desktop/web/src/live/`，只有 connection.ts / mode.ts / transport.ts，**没有 .orig 残留**；D14「无残留临时文件」这句成立 |
| 「掩盖退出码的写法（3 条）」 | 自检表里 5 条命令都写了 `set -o pipefail; … | tail -n N` | 对得上：内核点名的 3 条是 `git status --porcelain=v1 \| head -50`、`git show HEAD:… > src/live/transport.ts; npx vitest … \| tail -n 12`、`git diff -- … \| head -5`，都是查看/自测命令，不是检查命令；events-summary 里 `suspicious_commands: []`、`temp_path_uses: 0`、`outside_worktree_paths: []` |
| 「运行期间规划路径有变化：A .agent/plans/t030-…」 | 报告未提 | 对得上：那是并行的 T030 规划件，不在本候选的 patch 里；合同的 forbidden_paths 里 `.agent/**` 本来就不许执行端动 |
| 「工具错误 4」 | 报告未提 | 不影响结论：最终 diff 与自检结果自洽（两个文件的改动都在，18/18 通过），无「跳过没做的动作」的迹象 |
| DoD 自述「一律 resolve 成七字段信封，绝不 reject」 | — | **这轮成立了**（上一轮这句是不成立的，见 B1） |

DoD 与本轮改动的对应：D03（绝不 reject）、D04（失败分类/状态码优先）、D06（连接状态）三条被本轮改动直接触及，都由上面的用例与探针钉住；D01/D02/D05/D07–D14 本轮未动文件，沿用上一轮已核对过的证据（V01/V02/V03/G01/R01 在本候选上实跑通过）。

## 五、不挡的意见（写给后续，不构成打回）

1. 读体失败、且状态码 ≥ 400 时，文案是「服务返回 HTTP 502」但连接状态被置 `disconnected`；合同 §2 只说「收到任何 HTTP 响应（哪怕 4xx/5xx）都置 connected」，没有覆盖「响应体没读完」这种半截响应。这是我在 B1 里明确要求的状态口径，不是缺陷；但下一版合同最好补一句写死，免得后面有人按字面把它改回 connected。
2. 「读体期间 reject 的是 AbortError 就一律走第 1 条超时文案」这条（执行端 interpretation 2）意味着「服务端主动中止且耗时远小于 35 秒」时用户会看到「请求超时（35 秒）」。合同没有第 8 种文案可归，与 fetch 级同款判定一致，按现状可接受，已被门禁钉死。
3. 归档清单 `mutation-spec-20261112T192133679741Z.json` 里的 `transport-abort-flag` 锚点（`if (timedOut || (error as Error)?.name === 'AbortError') {`）现在在 transport.ts 里出现两处（fetch 级 :127 与读体级 :147）；本轮没重跑那份清单所以没暴露，下一片合并清单时要把锚点拆成带上下文的整块。
4. 白盒文件 `tests/test_gate_t027_whitebox.py` 与 `mutation-spec.json` 目前只落在工作目录；B1 的回归钉子建议随基线提交进仓库，否则后面的片会丢掉这层保护。

## 六、结论

- B1：已解决，五项要求逐条有实现、有用例、有门禁钉子。
- 本轮新改动：范围合规、无特判、无弱化、无空心断言。
- 内核检查、门禁记录、JEV：无异常。
- **结论：通过。** 不退回任何对象，无阻塞项。

Verdict: PASS
