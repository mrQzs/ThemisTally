# 复审记录：t020-desktop-ui-profile attempt-002（七端信箱 hub）

- 合同：t020-desktop-ui-profile.v2（base 97c6ae0e22693cb96185665f0d7f5efb9d18505c）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（cc-switch-qianwenai-token-plan/qwen3.8-max，思考档位要求 high、生效 high；回合 20261026T024258584023Z-11e8），终审报告如下

## 终审报告

# T020-7-audit-post 终审报告

**结论：通过。** 候选树 bec4c9589a（attempt-002，基线 97c6ae0 = attempt-001 候选）。

## 1. 审阅方法

先逐文件读候选源码（不是先看检查记录）：`writeroutes.ts`、`server.ts`、`harness.ts`、`fake-write-kernel.mjs`、`write-config.test.ts`、`write-real-config.test.ts`、`write-argv.test.ts`、`slow-request.test.ts`、`README.md`、白盒 `tests/test_gate_t020_whitebox.py`、`candidate.patch`；再核对内核的检查与门禁记录。

## 2. 实现忠实于合同（逐条核过）

- **五条写路由**：路由名/路径/路径参数键照合同表；与既有七条共用 `validateWriteArgs`/`buildWriteArgv`/`mergeArgs`/确认号/操作表；退出 0/4/其他的分支未动。
- **校验**：八个新键的规则与合同逐条一致（`TASK_ID_RE`、model 两段 `MODEL_TOKEN_RE`、thinking 七选一、`credential_env` 非空数组且每项 `allowEnvName`、adapter 四选一、command 每项 `cleanText(1,1024)`、force 只认 true）；提示固定不回显。
- **argv 模板**：`--opt=值`、次序固定、`--command=JSON.stringify(command)`、基础 argv 无四个开关；`WRITE_ARGV` 13 行、`OPEN_WRITE_COMMAND_PATHS` 恰 12 条、`NOT_OPEN_WRITE_COMMANDS` 7 条带理由、`T020_WRITE_COMMANDS` 已删（grep 全仓：源码/测试无残留，只有门禁文件断言其不存在与历史 .agent 文档）。
- **顶层键检查**：在 `previewRoute` 里、`validateWriteArgs` 之前，多出键 400「参数含有未知键」；缺 action/args 两条提示原样。
- **空闲超时**：`kernelAnsweredRoutes` 迟绑定（`bun.serve` 之后建），`matchesBatch` 用 `findRoute` 不抄路径表，`bunServer.timeout(request, 0)` 只对命中请求；`idleTimeout` 无数字字面量、只由 overrides 覆盖。`readroutes.ts`、`localhttp/**` 未动。
- **harness env**：`childEnv(extra)` 只合进子进程环境，无 vitest `process.env` 赋值（write-config 里进程内 app 用 `process.env.FAKE_KERNEL_REPORT` 是 T019 既有模式，有 beforeEach/afterEach 清理）。
- **替身**：action 由 argv 推导（真推导，不是回显请求）、state 按 sha256 种子确定性生成（12 config + 2 local = 14 段互不相同）、慢门 `FAKE_WRITE_SLOW_GATE`/`FAKE_WRITE_SLEEP_MS` 缺省 15000、读一支打 `{}`、T019 记号全保留、不回显令牌。
- **README**：12 条写路由、两资源令牌、credential_env 三种写法、第 113 行空闲超时改写、已知限制写清不空、保留两处 T020。

## 3. 测试真实性（查硬编码、空断言、特判）

- **令牌 12×4 查法**不是自洽循环：token 取自服务端确认号表（预览时存），`expect_state` 取自替身报告的执行支（子进程侧），两条独立路径逐字比对；三份正文按段 `not.toContain`；先断言 token 过 `STATE_RE`（空/坏 token 会红）、12 条令牌与全部段两两不同。
- **W1/W2** 起真 Python 解析器：13 行示例 argv 逐条过 `kit_config/kit_plugins.build_parser()`；W2 递归枚举内核 `--dry-run` 集合与 `OPEN_WRITE_COMMAND_PATHS` 逐条相等；NOT_OPEN 每条加 `--dry-run` 被真解析器拒。
- **真内核 C1–C5** 在临时 git 夹具仓库上跑完整链路：actor=user-ui、U6b 409+snapshot 逐字节不变、`C:\\a b\\pi.exe` 反斜杠+空格 round-trip、U22 credential_env 回填、C5「至少给一项」退出 2 不发确认号（本轮唯一新增，补上了合同里只在正文描述的组合规则）。
- **slow-request**：`overrides: {}`，无 `bunIdleTimeoutSeconds`/`timeouts`；4 begin 全有 end 且退出 0；90s 时限。
- 无 skip/only/todo；W2/W4 是改断言到新事实（旧「7+T020 五条」→「内核集合=12 条」，更强）；未发现对测试输入硬编码、空 catch 或为过测试写的特判；改动范围恰为 9 个允许文件。

## 4. 检查与门禁记录核对

- 独立检查（checks.json，fresh 模式、树前后一致 bec4c9589a）：G01 17 passed、R01 660 passed、V01 35 files/304 tests、V02 13 passed、V03 空输出，全部 required 通过。
- 白盒 C1：16 passed（日志核实）。C2 14 passed、C3 1 passed（门禁报告，与 mutations.json 的 baseline 记录一致）。
- 变异记录：18 条，16 caught；全部 missed 都在 expect_missed 内，`unexpected` 均为空——门禁声明与实际记录逐条相符。

## 5. 三项裁量

- **M10 等价：成立。** 依据是门禁本回合的探针实测（真 Bun、生产选项、替身睡 15 秒）：GET 约 12 秒被断（两次复现），POST 不放宽也 15 秒完整 200——Bun 1.4.2 的空闲超时掐不断有正文流的 POST 连接，「预览不放宽」在行为面不可观察。接线仍有双保险：C1 对 `kernelAnsweredRoutes = [...readRoutes(...), ...writeRoutes(...)]` 的整行断言（预览在 writeRoutes 批里，摘掉即红，M11 变异实测 caught 佐证），加 M10b（去掉全部放宽）被 C3 抓住证明 `timeout(request,0)` 真的在起作用。合同 D09/M10 预设「慢请求用例的 preview 一条」能杀，是写合同时的仓库外事实认知（站主 20261025 实测用的探针是 GET）被更精确的实测修正，不是实现或测试的缺陷。
- **F02（替身两资源令牌退化成一段）只有静态面：可接受。** 令牌表的 token 与 expect_state 都经服务中转、替身自洽不红，这是替身类夹具的固有性质；行为级保护在真内核 C2/C3（服务若截掉 local 段，真内核报 stale，C3 的「成功」必红），只是不在变异命令集里（真内核太慢不进 C 命令）。建议（非阻塞）：后续路过 write-config 时补一条「runtime.add 带 command 与 runtime.remove 的 token 段数恰为 2、全表段数恰为 14」的断言，把 F02 的行为面也钉在快命令里。
- **解读②（NOT_OPEN 合成 prepare/run/verdict 一条）：合理。** 合同表格是一行、对象形状 `{path, reason}` 装不下三条各带理由；判据 3（不相交）由 W2 断言，判据 2 对这条的实现是「没有匹配解析器 → SystemExit → toThrow」，语义上弱（拒绝原因是命令不存在而非无 --dry-run），但合同本就写明调度器顶层命令「不在配置写命令的比对范围里」，不构成缺陷。解读①（行号按符号核对）合同第 1 步明文允许；解读③（D08「43 条过渡断言」定位不到）：本审同样未能在合同与 tests/ 里找到 43 这个数，按 G01+R01 全绿（677 条断言）为可核对证据，接受，不阻塞。

## 6. 不阻塞的意见

1. **路径参数压正文的“冲突方向”没有专门用例**：五条新路由的测试正文都省略路径同名键，证明的是路径参数确实进了 args（必填键全靠它），没有一条「正文给不同值、路径压过」的断言。`mergeArgs` 是 T019 既有共享函数、本片未改，我人工核过实现（pathArgs 后写覆盖），正确性无疑；旧七条当时也没有冲突用例。后续若有人改 `mergeArgs` 的写入次序，现有测试抓不到——建议下片路过时补一条。
2. `matchesBatch` 里 `batch.includes(matched.route)` 恒真（findRoute 就是从 batch 里挑的），冗余无害。
3. `write-argv.test.ts` W1/W3 的 describe 标题仍写「七条」，内容是 12/13 条，纯文案。
4. 白盒的整行逐字断言（server.ts 接线行、runArgv 行、displayArgv 行）对未来的合法重构较脆，但与本仓 T017/T019 门禁的既有惯例一致，属预期内的冻结锚点。
5. **集成前请协调人核实**：summary 警示执行期间主工作区 `AGENT_LEARNINGS.md` 有改动。候选不含它（越界 0、checks 前后树一致、changed_files 里没有），大概率是别的会话写的，但按规矩点名给协调人确认来源。

## 7. JEV 关注点核验

JEV 给「自述完成而无证据」p=0.85：不成立。D01–D11 每项都有独立证据（checks.json 全绿、白盒 16 条、变异 18 条逐条记录），执行报告自述与内核记录逐项相符，无夸大。

## 8. 结论

实现忠实于合同，测试真实且有杀伤力，检查与门禁记录全绿且相互印证，三项裁量全部成立。**通过**，无阻塞项。

Verdict: PASS
