# 复审记录：t026-desktop-shell-host attempt-002（七端信箱 hub）

- 合同：t026-desktop-shell-host.v2（base 038688fe7e55c16a5aa5413155fbcdb264e10887）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261106T111207663208Z-5041），终审报告如下

## 终审报告

# T026-7-audit-post 终审报告（attempt-002，audit-sonnet）

## 0. 结论

**通过。** 上一轮（attempt-001）我列的唯一阻塞项已由执行端补齐并经本轮复核通过；本轮候选零越界、零弱化、零删改既有断言；内核独立复跑三条检查全绿，战后门禁白盒与变异轮全绿。

- 复核对象：`.agent/runs/t026-desktop-shell-host/attempt-002/candidate.patch`（唯一改动：`desktop/shell/tests/host.test.js`，+79/-0）
- 审核方式：只读（审核端无 bash，本回合未跑任何命令）。所有「绿」的结论来自内核独立复跑的记录与门禁记录，源码判断来自逐文件阅读工作目录里的实现与测试。

## 1. 复审封板：上一轮阻塞项的逐条复核

上一轮阻塞项只有一条：**(归执行端) D12 的 stdout/stderr 证据缺失**——候选里没有任何一处捕获 `process.stdout`/`process.stderr`，而执行报告的 D12 行却按合同原文的口径报了 done。要求两件事：①在 `tests/host.test.js` 里补一条用例，在调用五个函数的成功与各失败分支期间接管两路输出并搜令牌、bootstrap nonce、一次性页面令牌；②把执行报告的 D12 一行改回合同原文（返回值、错误、stdout、stderr、`JSON.stringify(host)` 五处）。

### 1.1 阻塞项 ①：stdout/stderr 捕获用例 —— 已解决

**位置**：`desktop/shell/tests/host.test.js` 末尾新增用例 `test("D12：五个函数成功与各失败分支期间，stdout/stderr 不出现控制令牌、nonce、页面令牌")`（candidate.patch 唯一 hunk；工作目录里的文件内容与补丁逐字节一致）。

**机制核对**（读源码，不看自述）：

| 环节 | 源码事实 | 判断 |
|---|---|---|
| 接管 | `process.stdout.write = capture(savedOut); process.stderr.write = capture(savedErr);` | 两条流都被接管 |
| 收集 | `chunks.push(typeof chunk === "string" ? chunk : Buffer.from(chunk).toString("utf8"))` | 字符串与 Buffer 都收 |
| 转发 | `return saved.apply(this, args);` | 原样转发，不吞掉 TAP 输出（保住 `# pass N` 可解析性）；回调参数也一起转发 |
| 恢复 | `finally { process.stdout.write = savedOut; process.stderr.write = savedErr; }` | 断言失败也会恢复，不污染后续用例 |
| 搜索 | `const secrets = [TOKEN, bootstrapUrl, nonce, PAGE_TOK];` + `chunks.join("")` 后逐一 `!output.includes(secret)` | join 之后再搜，分片写（先写前半、后写后半）也逃不掉 |

**覆盖的分支**（逐条对合同 D12 的「任何路径」）：reauth 成功 / load-failed（注入的 `loadMain` 抛出的拒绝消息里带整条 `bootstrapUrl`）/ bad-response；openSecretWindow 成功（关窗发取消，头带 `TOKEN`）/ load-failed（假 `loadURL` 拒绝消息里带含 `PAGE_TOK` 的 url，关窗再取消）；openExternal 打开 / 取消 / 打开失败 / 非法地址；reveal 通过 / 字面拒绝；notify 两类合法 / `constructor` 拒绝。合同点名的「假的 `loadURL` 拒绝消息带着它们的情形」被显式覆盖。

**不是空转的论证**：① 实现侧确实一行输出都没有——grep 整个 `desktop/shell/src/`，只有 `core.js` 的 `io.stderr.write`（T025 既有代码，且 core.js 不是这五个函数的路径），`host.js`、`control.js`、`hostcheck.js` 里没有任何 `console.*` 或 `process.std(io).write`；② 若实现改成把秘密写进任一路输出，`console.log/console.error` 与 `process.stdout.write/process.stderr.write` 都经过被接管的 `write`，`chunks` 必含该秘密，断言必红；③ 反过来，测试自身不会因为「捕获没生效」而假绿：捕获窗内没有任何路径会写秘密，所以 `output` 里不会出现秘密，这是断言应有的行为，不是空转的理由。

**残余（不挡）**：捕获窗未覆盖 reauth 的 `request-failed`/`rate-limited`、openSecretWindow 的 `bad-args`/`busy`、openExternal 的 `internal` 三个分支。这三处都不经手秘密（`request-failed` 的失败来自网络错误，`rate-limited` 在碰令牌前就返回），当前实现又完全没有输出调用，所以不构成结果错误——写进建议（见 §6）。

### 1.2 阻塞项 ②：执行报告 D12 一行 —— 已解决

`executor-report.md` 的 D12 行与 `executor-report.json` 的 D12 note 现在都写全五处：「返回值（既有逐分支 `JSON.stringify(r)` 不含 TOKEN/bootstrapUrl/PAGE_TOK）、错误（reauth/openSecretWindow 的 load-failed 拒绝消息分别带 bootstrapUrl/PAGE_TOK，均不外传）、stdout（本轮新增：接管 `process.stdout.write` 收集）、stderr（本轮新增：接管 `process.stderr.write` 收集）、`JSON.stringify(createHost(...))`（既有）五处都有断言」。与合同原文口径一致，不再有「自述比证据宽」的问题。

**五处证据的落点**（我逐条核过，不是照抄自述）：

| 合同 D12 要求的落点 | 证据 | 位置 |
|---|---|---|
| 返回值 | 既有逐分支 `assert.ok(!JSON.stringify(r).includes(TOKEN))` 等 6 处 + `deepEqual` 整个返回对象（不容许多出字段） | host.test.js 既有 |
| 错误 | 注入的拒绝消息带秘密，返回值仍只有 `{ok:false, reason:"load-failed"}` | 「reauth 加载失败」「loadURL 失败」两条既有用例 |
| stdout | 本轮新增捕获用例 | host.test.js 末尾 |
| stderr | 本轮新增捕获用例 | host.test.js 末尾 |
| `JSON.stringify(createHost(...))` | 既有「控制令牌与引导地址不进宿主对象的 JSON」 | host.test.js 既有 |

### 1.3 其余 DoD 与实现

本轮**零实现文件改动**：candidate.patch 只含 `desktop/shell/tests/host.test.js` 一个 hunk，`scope.json`/`changes.json` 为 A0 M1 D0 T0、唯一路径 in_scope、`violations: []`。11 个非测试文件（main.js、preload.js、src/{control,core,host,hostcheck,ipc,service,window}.js、README.md、package.json）与 attempt-001 逐字节相同（门禁已核对）。因此 D01–D11、D13–D17 沿用上一轮的判断，不重新翻案；补丁对既有测试只有新增（0 删除），没有弱化任何断言，也没有 skip/only/todo。

## 2. 内核检查与门禁记录的核对

| 检查 | 内核独立复跑 | 结果 |
|---|---|---|
| V01（`npm test`，cwd=desktop/shell） | exit 0，`output_must_match`「# pass [1-9]\d*」matched | V01.log：# tests 137 / # pass 137 / # fail 0；第 432–433 行新用例 `ok 72 - D12：…` |
| G01（`python -m pytest tests/test_gate_t026_baseline.py -q`） | exit 0，「\d+ passed」matched | 14 passed |
| R01（t001–t025 门禁 25 份） | exit 0，「\d+ passed」matched | 764 passed |

- `checks.json`：`covers_all_required: true`、`all_required_passed: true`、`modified_by_checks: false`、`candidate_files_modified: []`、`unexpected_files_by_checks: []`——检查过程没改候选树，也没有意外文件。
- 战后门禁（T026-6-gate-post，attempt-002）：白盒 6 passed（新增 `test_w06_static_d12_capture`，六条 needle 逐字取自候选：两条流的接管与恢复、nonce 截取、secrets 四样、`!output.includes(secret)`）；G01 14 passed；W2 137/137 退出码 0；变异轮基线绿、**caught 31 / missed 0 / skipped 0 / error 0**、`unexpected` 全空、11 个被变异文件事后逐字节恢复；结论「通过，无 candidate_defects」。
- JEV（6j-jev）：`no_opinion auth_failed`，无意见需要裁定。
- 执行概述与门禁记录一致：候选树 `7c538b0d…`、补丁往返校验通过、越界 0、警告 0。

## 3. 门禁端标了「这条命令预期抓不住」的六条变异（逐条复核：真的测不到吗）

| 变异 | 门禁声明 | 我的复核 |
|---|---|---|
| M01 README：凭据窗口上限 1→2 | W2 测不到，W1 抓住 | 成立：W2 是 `desktop/shell` 下的 node 单测，不读 README（README 要点由 W02 静态查） |
| M03 main.js：拿掉 `createHost` 的 require | W2 测不到，W1 抓住 | 成立：`tests/**` 里没有任何一处 require `main.js`（grep：只有 `package.test.js` 断言 `pkg.main` 这个字段），单测不加载 Electron 主进程 |
| M04 main.js：主窗口 prefs 换成十键（少 preload） | W2 测不到，W1 抓住 | 成立：同上，prefs 的接线由 W01 静态钉 |
| M05 main.js：凭据窗口 prefs 换成带 preload 的 | W2 测不到，W1 抓住 | 成立：同上 |
| M06 main.js：`senderAllowed` 不再校验服务 origin | W2 测不到，W1 抓住 | 成立：来源校验在 main.js 侧，src/ipc.js 的单测用自己的注入物 |
| M19 hostcheck.js：`isExternalUrl` 去掉控制字符扫描 | W2 测不到，W1 抓住 | 成立：我核了 `tests/hostcheck.test.js` 的反例清单（协议、空白、换行、反斜杠、单斜杠、非字符串），**确实没有 NUL/DEL 用例**，仓库单测只覆盖空白/换行；而白盒 W03 探针（whitebox 第 195–202 行）钉了 DEL/NUL/0x1f/串中空格/制表符，W1 抓住 |

`mutations.json` 里这六条都是 `status: caught`、`expect_missed: ["W2"]`、`commands.W1.status = caught`、`commands.W2.status = missed`——**声明与事实相符，诚实，不退回战后门禁，也不退回门禁端**。

门禁端说「执行端唯一改动是测试文件，按规矩无需变异」：本轮确实只改了 `tests/host.test.js`，11 个非测试文件沿用上一轮 31 条变异并重跑（31/31 caught），无需新增——判断正确。

## 4. 内核摘要线索 ↔ 执行报告自述的逐条对账

| 内核线索 | 自述 | 结论 |
|---|---|---|
| 2 条检查命令退出码被管道掩盖（`npm test 2>&1 \| tail -n 20/15`） | 报告 V01 exit 0 | 不冲突：内核在固定候选树上独立重跑 V01 得 exit 0；pytest 两条执行端自己用了 `set -o pipefail`。**不构成自述不实** |
| 新增 gitignored 路径 `.pytest_cache/`、`desktop/web/dist/`、`node_modules/` 等 | D17 写「无临时文件落盘」 | 属跑 pytest / npm 装依赖产生的忽略项，在一次性 worktree 里，不在候选（A0/T0），不构成矛盾 |
| `temp_path_uses: 0`、`temp_dirs_without_cleanup: []`、`suspicious_commands: []`、`outside_worktree_paths: []`、`own_run_paths: []` | — | 执行端没往工作目录外写文件、没留临时目录；符合只读输入目录与工作目录的约束 |
| 1 处 ambiguity 提及（第 5676 行 thinking） | `contract_conflicts: []`、`interpretations: []`、`unresolved_questions: []` | 对得上：执行端想过之后确认本轮没引入歧义，报告留空属实 |
| 「取证该用例有效（非空跑）」 | 用一段不落盘的 `node -e` 复算接管逻辑，报 `CAPTURE-OK: caught 2 writes, len=38` | `shell_commands` 里确有该命令且不落盘；结论与源码事实一致（两路 write 都能被捕获） |
| `assertion_lines_removed: 0`、工具错误 0、自动重试 0 | — | 无弱化、无隐藏失败 |

## 5. 候选补丁源码审读（新改动部分）

新用例只做三件事：接管两路 write、把五个函数的成功与各失败分支各走一遍、结束后搜四样秘密。没有为了过测试而写的特判；没有把断言放宽；没有把别处的断言删掉；没有触碰 `src/**`、`main.js`、门禁文件或 `desktop/web/**`、`ts/**`、`scripts/**`。自述与源码一致。

## 6. 不挡的意见（进 report，不进阻塞项）

1. **捕获窗可以再宽一点**：把 reauth 的 `request-failed`（打死端口的服务）与 `openExternal` 的 `internal`（`confirmExternal` 抛错）也放进捕获窗，对未来「给 host.js 加日志」更保险。当前实现零输出，不影响正确性。
2. **给捕获本身加个自证**：这条用例是纯否定式断言，若将来有人把接管两行改空（例如改成收集但不搜），测试仍会绿。门禁的 W06 静态 needle 暂时兜住了这点，但更稳的做法是在捕获窗内写一个标记串并断言它出现在 `output` 里（证明捕获确实在工作）。
3. **白盒静态锚点偏脆**：W06 把六条 needle 逐字钉死，后续片重排 `host.test.js` 的 D12 用例就会红。这是门禁设计上的已知代价，届时改门禁，不要回退实现迁就 needle。
4. **执行端的自检命令口径**：`npm test | tail` 会丢退出码，后续自检统一加 `set -o pipefail`（本轮 pytest 已这么做，npm 那两条没做）。

## 7. 逐条复核结论汇总

| 上一轮阻塞项 | 归属 | 本轮结论 |
|---|---|---|
| ① D12 的 stdout/stderr 证据缺失（补捕获用例） | 执行端 | **已解决**：新增用例在五函数成功+各失败分支期间接管两路输出并搜 TOKEN/bootstrapUrl/nonce/PAGE_TOK，finally 恢复，join 后搜索 |
| ② 执行报告 D12 一行改回合同原文 | 执行端 | **已解决**：md 与 json 两处都写全返回值、错误、stdout、stderr、`JSON.stringify(host)` 五处 |

**本轮无新阻塞项。结论：通过。**

Verdict: PASS
