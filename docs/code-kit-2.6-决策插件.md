# Code-Kit 2.6 设计说明：决策插件（Jev）与跨库引入

状态：草案（2026-10-12）。等用户决定第 7 节，再拆分实施。

## 1. 为什么做

用户 2026-10-12 的要求：把 Jev 决策模型以插件的形式引入 Code-Kit，并把 `Desktop/PLan` 下其他库里值得要的功能一并引入，改善 kit 本身。参考资料：

- Jev 官方文档 `https://docs.typesafe.ai/`（introduction、quickstart、primitives、confidence、patterns、api、models、state、how-to-build-with-system-one、coding-agents、model-jaggedness/jev-1.13、sdk/python、agent-skill）。
- `PLan/hermes-jev-skills`：一个把 Jev 接进 Hermes 代理的 MIT 仓库，`jevkit/` 是纯标准库的客户端与十个决策场景，`docs/` 是把它放到真实机队上得到的运维教训。
- `PLan/opus-manager`：Claude 当经理、便宜模型写代码的工单技能。
- `PLan/SemIf-OpenJev`：用开源模型复现 Jev 接口形状（读 logits，不生成文本）的研究项目。
- `PLan/SimpleMem`：跨会话记忆服务（MCP）。

Code-Kit 的流程里有一类工作“便宜但要判断”：报告里哪句自述与证据不符、漏掉的变异是不是等价改写、运行中的执行器是在推进还是卡住、合同的 DoD 能不能被列出的证据证实。现在这些要么靠正则（2.5.0 的三类备注），要么靠规划端读事件流花前沿模型的 token。Jev 的定位恰好是“对一个状态回答类型化的问题，返回校准过的概率，不写文本”。

## 2. Jev 是什么（从官方文档核对的事实）

- 接口：`POST https://api.typesafe.ai/v1/systemone`，头 `Authorization: Bearer <key>`、`Content-Type: application/json`。请求体 `state`（字符串、对象或数组）、`model`、`questions`（以调用方自选的 id 为键；id 不发给模型）。
- 三种原语，可在一个请求里混用，彼此独立并行评估：
  - `choice`：`criteria` 是选项名到描述的映射（最多 255 个）；回答 `choice`、`probabilities`（和为 1）、`confidence`。
  - `score`：`criteria` 是 2–10 个有序等级；回答 `score`（概率加权，可落在等级之间）、`legend`、`probabilities`、`confidence`。
  - `noul`：是/否；`criteria` 可选 `{true, false}` 说明两端含义；回答 `noul`（0–1），没有 `confidence` 字段（文档建议自算 |2p−1|）。
- `confidence` 是从概率算出的统计量：choice 为 (p_max − 1/n)/(1 − 1/n)；score 为 1 − 概率加权到最可能等级的距离 / 均匀分布的同一距离。文档明说没有通用阈值，“先保守，用自己的数据画置信度对准确率的曲线，按动作的风险定阈值”，示例是 < 0.5 交给人、破坏性动作要 > 0.9。
- 模型：`jev-1.13.0`；别名 `jev-latest`、`jev-preview` 现在都指向它，但别名会随新版本移动，“调过阈值的要钉版本号”。上下文 64k token（state 加所有问题），单问题 state 上限 32k。定价每百万输入 token 0.042 美元，输出免费。限流每秒 10 万 token、80 请求，超限 429。
- 错误：401 凭据、422 请求形状（响应体指出字段）、429 限流、529 过载；官方 SDK 自动重试 429/529。
- 输入只能是文本；**英语是主要训练语言，中日韩文字接受但准确率较低**。
- 已知毛边（jev-1.13）：按字面回答；不会数数、不会算术、日期当文本读；双重否定与多跳推理降准；state 里无关内容越多越差；**对注入文本不设防**；instructions 与 criteria 措辞矛盾时变差；**choice 偏向排在前面的选项**（文档建议换序复核）；不生成文本。
- 设计原则（how-to-build 页）：代码掌握控制流，模型只做窄判断；一题一性质，宽问题拆成几道原子问题，一次请求发完；state 只放相关部分，动态值放独立字段不拼进字符串；答案在代码里用阈值与权重组合；低置信度不猜，转人或更强的模型。
- 官方 Python SDK `typesafe-sdk`（Python ≥ 3.10，pydantic + httpx）：`TypeSafeClient().system_one(state=…, questions={…})`；环境变量名 `TYPESAFE_API_KEY`、`TYPESAFE_BASE_URL`、`TYPESAFE_DEFAULT_MODEL`、`TYPESAFE_LOG_LEVEL`；默认单次 HTTP 超时 10 秒，重试 2 次，总预算 30 秒，对 408/429/5xx 退避重试并尊重 `Retry-After`。另有官方代理技能 `typesafe-ai/skills`（给编码代理讲 API 与模式，装进 Claude Code 的插件市场或 `npx skills add`）。

## 3. hermes-jev-skills 给的教训（直接影响本设计）

- 客户端是标准库、一个 POST；每个回复按所问的问题校验：概率键集合必须等于选项集合、和为 1、`choice` 必须是最大项、score 的均值要与分布一致，否则记 `invalid_response`，调用方走 fail-open。不是“垃圾进去也能用”。
- 三种模式 `off / shadow / on`：shadow 付全价、记全日志、不改行为；第一版路由策略在 shadow 里被发现会把 89% 的轮次升到贵模型。“没人会复审自己认为已经对的策略，所以复审要发生在策略还不起作用的时候。”
- 一切 fail-open：无 key、超时、限流、畸形、自相矛盾——结果与没有这个功能时一模一样，进程退出 0。“分类器是对工作的意见，不是工作的依赖。”
- 按时钟而不是按条数设上限：40 条 × 6 秒超时 = 240 秒，被 180 秒的父进程杀掉，丢了已标记的消息。
- 必须不能静默失败的开关用标记文件，不用配置键：三次“配置键默认 off”事故。
- 出站边界：`privacy.redact`（邮箱、电话、令牌形状、长 hex、高熵串、`*_SECRET`/`*_TOKEN` 赋值）加 `is_sensitive`（看起来含凭据的片段整段不发）；日志只存决定（tier、model、confidence、latency），不存 prompt 文本。
- `supervise`：代码先判一切免费能判的（有没有新输出、尾部是否重复、进程是否退出），Jev 只判代码判不了的（是否在真进展、是否卡住、是否做完）；“监督器因自己眼睛坏了就杀掉工作，比没有监督器更糟”。
- `check_release.py`：推送前扫描 `git ls-files -co --exclude-standard`，模式是 key 形状、家目录路径、内网地址，外加一份放在仓库之外的拒绝清单；二进制文件列为 NOT SCANNED；扫到 0 个文件算失败不算通过。
- 问题写法：把“必须满足”与“只是偏好”分开写在 instructions 里，一句话让 44 例准确率从 16 升到 33。
- 代码里自带的阈值每一个都附带测量脚本与记分卡（`evals/`），改阈值先回放。

## 4. 它在 Code-Kit 里的位置

### 4.1 为什么是“声明式插件 + 受信任核心模块”

06 的规定：Code-Kit 的任务插件是声明式的，调度器不在自己进程里装载任意插件代码；插件的 permission 只是“需要什么”，有效权限是用户授权、项目策略、角色集合与合同授权的交集。所以“Jev 插件”在 Code-Kit 里是两部分：

- `plugins/decisions/`：manifest（`plugin_id: decisions`，capability `decision-questions`，permission `network-decisions`）、锁文件、README、`questions/*.json` 问题清单（每个决策点一份：问题 id、type、instructions、criteria、代码里要用的阈值名）。问题清单是插件资源，进完整内容锁；改一个字就要换哈希。这也是官方文档建议的“问题与阈值常量放在一个文件里给人复审”。
- `scripts/codekit/decisions.py`：受信任的核心模块，标准库实现，只认上面这一种问题形状。职责：问题形状校验（type、instructions 非空且不等于 id、choice ≤ 255 项、score 2–10 级、noul 的 criteria 只能是 `{true, false}`）、请求构造、回复校验（同 §3 第一条）、出站脱敏、模式判定、时钟预算、记录写入、`transport` 可注入（测试用假传输）。不依赖官方 SDK：kit 的约束是“不安装依赖”，而且 SDK 的 pydantic/httpx 对一个 POST 来说过重；SDK 的常量（环境变量名、默认模型、超时、重试策略）照抄进模块注释与 doctor 的输出，方便以后对照。

### 4.2 三条不变量

1. **决策只是意见，门禁不读它。** G0–G6、verdict、`check` 的退出码、`mutate` 的 caught/missed 计数、`validate` 的 ERROR 都与它无关。它的输出只进 summary.md 的一节、结果行的后缀、`validate` 的 WARN、`wait` 的一行提示。插件 manifest 不可能声明“直接 PASS”，这一条也不例外。
2. **一切 fail-open。** 无 key、模式 off、标记文件存在、超时、429/529、422、畸形或自相矛盾的回复、state 超过上限、片段看起来含凭据——都记为“无意见（原因码）”，命令照常完成、退出码不变。总预算按时钟：每条命令里决策调用的总时长有上限（默认 20 秒），到点后剩下的问题一律“无意见（budget）”。
3. **出站边界。** 只发与问题相关的片段（报告正文、变异的 old/new 与前后几行、事件流尾部的 assistant 文本与工具名），先过脱敏；看起来含凭据的片段整段不发；凭据只认环境变量名（配置 `api_key_env`，默认 `TYPESAFE_API_KEY`），值只在构造请求头时读一次，不打印、不落盘、不进 doctor 输出。记录里不存 state 原文，存 `state_sha256`、字符数与脱敏次数。

### 4.3 模式与开关

- `.agent/dispatch.config.json` 增加 `decisions` 对象：`mode`（`off | shadow | on`，缺省 `off`）、`api_key_env`（默认 `TYPESAFE_API_KEY`）、`base_url`（默认官方；只允许 `https://…` 或 `http://127.0.0.1:<port>`，后者给测试与本地兼容服务）、`model`（默认钉 `jev-1.13.0`，不用 `jev-latest`）、`timeout_seconds`（单次，默认 4）、`budget_seconds_per_command`（默认 20）、`max_state_chars`（默认 20000）、`points`（启用哪些决策点，缺省全部已实现的）。
- 标记文件 `.agent/DECISIONS_OFF`：存在就等于 `off`，无论配置怎么写。给“这个仓库的内容不能出机器”的场景；一个 `ls` 就能证明。
- `shadow`：调用、记录、不改任何输出与退出码；summary.md 多一节“决策（shadow）”，只列答案与置信度。
- `on`：答案进提示位置（§5 各决策点写明），每一行都标注“决策模型”来源；门禁仍然不读。
- 插件未启用（`plugins.enabled` 里没有 `decisions`，或权限交集里没有 `network-decisions`）等同 `off`，doctor 说明原因。

### 4.4 语言

合同、报告、复审记录是中文；官方明说 CJK 准确率较低。对策：问题文本一律英文；state 里优先放代码、命令、退出码、英文事件文本；中文正文照发但不做翻译（翻译又是一次模型调用）。因此必须先 shadow 跑若干轮，用 §6 的回放对照规划端自己的结论，看中文输入上的准确率，再决定哪些决策点能开 `on`。这是用户要知道的最大风险。

## 5. 决策点

每个决策点一份问题清单，阈值在 `decisions.py` 顶部的一张表里（不散落在各命令中）。调用处都在已收集的证据上运行，不在执行器运行中插入延迟（D3 除外，它本来就是轮询）。

| 编号 | 决策点 | 触发命令 | state（脱敏后） | 问题（英文，noul 除非注明） | 输出位置（on 模式） | 阈值初值 |
|---|---|---|---|---|---|---|
| D1 | 报告筛查 `report-screen` | `collect`/`run` 收尾写 summary 时 | 执行报告正文、DoD 自述、检查结果概要（id、退出码）、2.5.0 的三类备注摘录 | `claims_unsupported`（报告把某条 DoD 说成已完成而自己的证据段没有对应检查）、`chose_interpretation`（执行器替合同做了解释而没有报告冲突）、`scope_creep`（报告描述的改动超出合同 Scope）、`weakened_tests`（报告或命令显示删除、跳过或放宽了测试）、`severity`（score 0–3） | summary.md 新节“决策”；p ≥ 行动阈值的进“复审需要关注”末尾（标注来源） | 复审阈值 0.35、行动阈值 0.70（沿用官方 guardrails 食谱的 strict 策略，shadow 后再调） |
| D2 | 变异等价 `mutation-equivalence` | `mutate`（attempt 与 `--tree` 都是） | 每条 MISSED：文件相对路径、`old`、`new`、前后各 8 行、检查命令 | `equivalent`（替换后可观察行为与原代码相同）、`untested`（替换改变了行为但没有测试到达） | 结果行后缀 `等价 p=0.82` / `测试缺口 p=0.77`；`mutations.json` 每条加 `decision` 对象；计数不变 | 提示阈值 0.70 |
| D3 | 运行健康 `run-health` | `wait`、`status --assess`（显式参数） | 事件流尾部最近 3000 字符的 assistant 文本、最近 10 次工具名与是否出错、无新事件秒数、已用秒数、工具调用次数、是否重复（代码先算） | `progressing`、`blocked`、`looping`、`done`，`action`（choice：`keep_waiting`、`prepare_next_contract`、`collect`） | `wait` 的进度行多一段；永远不停止运行 | 行动阈值 0.70；连续两次才提示（hermes `alert_after`） |
| D4 | 合同筛查 `contract-screen` | `validate` | 每条 DoD 的 text 与 evidence 指向的检查项；整份合同的 Behavior contract、Steps、Scope | 每条 DoD：`verifiable_by_evidence`；整份：`internal_contradiction`、`steps_outside_scope` | WARN 行（标注来源）；不产生 ERROR | 提示阈值 0.70 |

首版建议只做 D1 与 D2：两者都在已收集的证据上运行、没有时间压力，而且规划端对同一证据有自己的结论（verdict、复审记录里的变异判定），shadow 记录可以直接对照打分。D3、D4 等 D1/D2 的回放数据说明中文输入上可用之后再做。

## 6. 记录与回放

- attempt 内的调用追加到 `<run-dir>/decisions.jsonl`；`validate` 与 `mutate --tree` 的调用写到 `.agent/decisions/<plan-key 或 tree 名>.jsonl`。每条：时间、模式、决策点 id 与清单哈希、模型、`state_sha256`、字符数、脱敏次数、答案（全部概率与置信度）、`latency_ms`、`usage`、错误码。
- `decisions replay`：把 shadow 记录与后来的事实配对——D1 对 verdict 结论与复审记录的发现、D2 对复审记录里“等价/测试缺口”的人工判定——按问题输出命中、漏报、误报与置信度分布，给出“这个问题在这个仓库上能不能开 on、阈值放哪”的依据。这是官方“用自己的数据画曲线”与 hermes `measuring-a-router` 的做法。
- `metrics` 汇总决策调用的次数、token 与费用（按官方定价算，输出免费）。

## 7. 从其他库引入的项

| 编号 | 来源 | 引入内容 | 落点 |
|---|---|---|---|
| E1 | hermes `scripts/check_release.py` | 新子命令 `release-check`：扫描 `git ls-files -co --exclude-standard`，模式为 API key 形状、家目录路径（`/Users/<x>/`、`/home/<x>/`、`C:\Users\<x>\` 与正斜杠写法）、内网地址；仓库之外的拒绝清单（环境变量 `CODEKIT_RELEASE_DENYLIST` 指路径，默认 `~/.config/code-kit/release-denylist.txt`，只记编号不回显内容）；二进制文件列为未扫描；扫到 0 个文件算失败；有命中退出 1。review-pi 的推送步骤与 memory 里“夹具带本机路径前缀”的提醒改成跑它 | `scripts/pi_dispatch.py`、review-pi SKILL |
| E2 | opus-manager 工单的“为什么这样验收” | 合同 DoD 行可加“目的：…”子句（“过了检查不是目标，这个才是”），`derive-json` 写进 `definition_of_done[].intent`（可选键，老合同不受影响）；mutation-check 按目的设计变异，independent-review 按目的而不只按检查判断 | 合同模板、`derive-json`、validate、两份技能文件 |
| E3 | opus-manager 的“换一家审查” | independent-review.md 增加一条：配置了第二 CLI（11 的 second_cli 适配器或 `codex exec --sandbox read-only`）时，独立复审用另一家模型只读运行；复审记录的“复审者”一行写明工具与模型。只改技能文本与模板，不改调度器 | review-pi 技能 |
| E4 | hermes 运维文档 | 写进技能：决策功能先 shadow；“日志安静不证明功能在跑”，用 doctor 列出当前生效的模式与决策点；“在它真正运行的地方验证”（doctor 的 `--probe-decisions` 从规划端会话发一次最小请求，会花钱，要用户批准）；“按时钟不按条数设上限” | check-pi-env、dispatch-pi、review-pi |
| E5 | hermes `privacy.py` | 脱敏与“整段不发”的规则移植进 `decisions.py`（邮箱、电话、令牌形状、长 hex、高熵串、`*_SECRET`/`*_TOKEN` 赋值、BEGIN PRIVATE KEY） | `decisions.py` |

不引入的：

- SimpleMem：是一个带向量库与模型调用的服务，kit 的记忆是反馈文档、设计说明与仓库本身，不加服务依赖。
- SemIf：接口形状相近但不是同一个协议；`base_url` 允许指向本地兼容服务，这就是以后接离线决策模型的门，本轮不做适配。
- 官方代理技能 `typesafe-ai/skills`：不复制进仓库（会变旧、两份规则无人维护）；plan-task 与 review-pi 只链接官方文档；kit 自己的问题清单就是“给人复审的那个文件”。
- hermes 的模型路由、技能选择、记忆过滤、邮箱分类、GUI 动作：与 kit 的流程无关。
- opus-manager 的工单目录、回执模板、首次摸环境：Code-Kit 已有合同、attempt 证据与 check-pi-env，而且更严格（回执是说法不是证据，这条 AGENTS.md 已有）。

## 8. 证据边界

- 本轮所有测试离线：`decisions.py` 用假 `transport`；端到端场景用 `base_url` 指向测试里起的本机 HTTP 服务（回放固定答案，也回放 422/429/畸形/自相矛盾）。真实 Jev 调用、凭据、联网一律 NOT_RUN，除非用户另行批准一次 `doctor --probe-decisions`。
- 不读取、不打印凭据；doctor 只报告 `api_key_env` 的名字与“是否已设置”的布尔值。
- 记录里不存 state 原文（见 §6）。

## 9. 文件范围（预计）

- 新增 `scripts/codekit/decisions.py`、`plugins/decisions/{manifest.json, lock.json, README.md, questions/report-screen.json, questions/mutation-equivalence.json}`、`schemas/decision-record-v1.schema.json`、`tests/test_decisions.py`（pytest，离线）。
- 修改 `scripts/pi_dispatch.py`：配置读取与校验、summary 的“决策”节与 attention 行（D1）、`mutate` 的后缀与记录（D2）、`doctor` 的 `decisions` 块、`metrics`、新子命令 `decisions replay` 与 `release-check`、`derive-json`/`validate` 的 `intent`（E2）。`TOOL_VERSION` 2.6.0。
- `tests/test_dispatch.py` 新场景：release-check、decisions 的 off/shadow/on 与各种失败的 fail-open、doctor、intent。`tests/codekit01_legacy.py` 登记 summary 新字段（2.5.0 的经验）。
- 技能：plan-task（intent、官方文档链接）、review-pi（决策节怎么读、E1 推送前、E3 异族复审）、check-pi-env（doctor 的决策块、probe 要批准）、dispatch-pi（shadow 先行）；`sync-adapters`。
- `CHANGELOG.md` 2.6.0；`docs/KitExperiment实机反馈.md` 下一轮起记录 shadow 的对照结果。
- 插件目录校验：`builtin_catalog.REQUIRED_PLUGIN_IDS` 是“必须存在”的集合，不是“只允许”的集合；实施时核对多一个插件目录不会被目录校验拒绝，否则先改校验。

## 10. 用户决定（2026-10-12）

1. 首版决策点：D1 报告筛查、D2 变异等价、D3 运行健康。D4 合同筛查留到回放数据说明中文输入可用之后。
2. `on` 模式只加提示行，每行标注来源；G0–G6、verdict、计数、退出码永远不读决策结果。
3. 本轮全部离线：假传输与本机回放服务覆盖成功与各类失败；真实 Jev 调用、凭据、联网 NOT_RUN。用户准备好 key（只告知环境变量名）后，另行批准一次 `doctor --probe-decisions`。
4. 引入项 E1–E5 全做。

状态：2.6.0 由规划端直接实施（执行器不得改 `scripts/pi_dispatch.py`）。

## 11. 进度与遗留

- 2026-10-12：核对官方文档与四个本地库，写成本说明；用户决定第 10 节四项。
