# 复审记录：t018-desktop-ui-follow attempt-001（七端信箱 hub）

- 合同：t018-desktop-ui-follow.v1（base fe538fc14404dff32e6e0478f2a861fb5d933795）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（cc-switch-qianwenai-token-plan/qwen3.8-max，思考档位要求 high、生效 high；回合 20261025T164850403997Z-b941），终审报告如下

## 终审报告

# T018-7-audit-post 终审报告（audit-sonnet）

## 结论

**通过。** 实现忠实于合同，无越界、无弱化测试、无为过测试而写的特判；变异与白盒证据充分；JEV 两个「需关注」点均裁定不成立；门禁端未举证候选缺陷（其结论「未发现」经复核成立）。

## 审核方法

先通读候选补丁源码（`candidate.patch` 全部 565 行：readroutes.ts +56/−6、README +21/−2、两个新测试文件 491 行），再对照合同 Behavior contract 与 DoD D01–D18 逐条核对，最后核检查与门禁记录（mutations.json、白盒日志、V04 存档日志、candidate.stat.txt）。全绿不等于对：对每条 DoD 找了具名断言，对每条 expect_missed 独立判断了是否真不可测。

## 一、源码忠实性（对合同的逐条核对）

| 合同条款 | 实现 | 判定 |
|---|---|---|
| 校验次序 1–7（task→attempt→path→follow 取值→JSONL→句柄→起子进程，全在起子进程之前） | `fileRoute` 中顺序完全一致；两种 400 都不回显请求值/路径 | ✓ |
| 跟随 argv（`--json --complete-lines`，`--cursor=` 最后） | 组装用 `...(following ? ["--complete-lines"] : [])`，游标仍在末尾 | ✓ |
| `FOLLOW_ARGV` 登记表两条、不并进 `READ_ROUTE_ARGV` | 单独导出，示例值与合同逐项相同 | ✓ |
| 末尾也发句柄（不看 done）；非跟随 done 为真给 null | `followCursor` 只要内核给了非空字符串游标就 `issue`；非跟随分支逻辑一字未动 | ✓ |
| 空页复用请求句柄、表项数不变；不带句柄的空页发一个后复用 | `requested !== null && emptyPage(page) → requested`；`emptyPage` 判 `lines` 为空数组 | ✓ |
| 有内容发新句柄、旧句柄不 drop（站主 Q1） | 走 `issue`，全文仍只有 1 处 `drop(`（T016 既有） | ✓ |
| `poll_after_ms=2000` 只在跟随 data、追加在末尾、键序保持原序 | `withHandle` 跟随分支复制原 Map 后 `out.set("poll_after_ms", FOLLOW_MIN_INTERVAL_MS)` | ✓ |
| 服务不强制下限、不回 429 | readroutes.ts 无 429（门禁 grep 0 处） | ✓ |
| 409 四种情形沿用 T016、跟随不新增 | 未新增任何 409 路径 | ✓ |
| 非跟随逐字节不变（D14） | 非跟随分支 git diff 零逻辑改动；cursors/argv-templates/kernel-real 未改且全绿 | ✓ |
| 范围与依赖（D16） | candidate.stat.txt 恰 4 个允许路径 +565/−9；V01 锁文件无变更 | ✓ |

**没有发现**：对测试输入的硬编码（F12 的 `--cursor=fake-cursor-part-1` 来自替身内核自己的输出，合法）、空的异常处理、为过测试的特判、悄悄扩大的范围。

## 二、JEV 判断的逐条裁定

1. **「自行解读合同 p=0.93【需关注】」——不成立。** 判据说「执行器选了一种读法且没列为冲突或问题」，与事实不符：两处解读都如实列在 executor-report 的 `interpretations[]`。解读①（README 三处旧话修订）有站主口径 20261025T145408733509Z 背书（gate-post brief 第 15 行原文可查：「不要把这一句当执行端缺陷」），结项后由规划端修订；解读②（内核没给可用游标时回显请求句柄）合同确实未定义该支，真内核不可达（`kit_logs.py` 的 `_jsonl_page` 恒带非空 `next_cursor`），兜底只影响跟随分支，门禁端已独立裁定不构成违反。本审同意。
2. **「自述完成而无证据 p=0.84【需关注】」——不成立。** D01–D18 逐条核到具名证据：D01–D11 → F1–F12（补丁里逐条读过断言）；D12/D13 → R1/R2（真内核 + `build_parser`）；D14 → V02/V06 + diff 零改动；D15 → 白盒 `test_readme_follow_section`（12 个结论 + 5 句点名段落逐字 + V08 八字面量）；D16 → candidate.stat + V01/V07；D17 → G01/R01/V01–V09 存档日志 + 变异 12/12；D18 → V09 STABLE5。没有一条只有口头声明。
3. 超出范围 p=0.12、弱化测试 p=0.08：与本审独立核对一致（范围恰 4 文件；既有测试一字未改）。

## 三、变异与 expect_missed 的独立判断

- 终版清单 12 条：合同 M1–M8 逐条对齐（M01/M02 分别打登记表与组装两处锚点，合计覆盖合同 M1/M2 的 kill 箭头），另加 M9 接线、M10 README 值、M11 取值门、M12 常量。`--check-anchors` 12/12，每条锚点恰出现 1 次。
- **W1（白盒）12/12 全抓住，0 意外漏掉、0 跳过、0 出错**（mutations.json counts 核实）。
- expect_missed 逐条判断为**真不可测，不是漏测**：M07（非 JSONL 放行）/M11（取值门放行）漏在 W3——W3 只跑 `follow-real.test.ts`，全程 `follow=1` + `events.jsonl`，确实碰不到这两条规则；规则由 W2 的 F7/F8 抓住（实测 W2 caught）。M10（README 值）漏在 W2/W3——执行端两个测试文件都不读 README；由 W1 的 README 断言抓住（实测 W1 caught）。分工与合同「D15 由 V08/白盒把守、F7/F8 把守取值与后缀」一致。
- 门禁端没有声明「无法变异」的改动文件（readroutes.ts 与 README 都有变异覆盖），无需另行判断。

## 四、检查记录核对

- G01 11 passed（门禁在干净树复跑）；R01 629 passed + 内核落地预演 640 passed；V01/V02/V03/V05–V09 全绿（V02 238、V09 STABLE5 均为门禁干净复跑）。
- **V04 缺口**：门禁两次复跑被并发变异污染、未在时限内独立重跑。背书链完整：执行端在**同一候选树**上的存档日志（checks/01/V04.log）尾部本审亲眼核实「Test Files 57 passed / Tests 645 passed」；候选只改 `ts/packages/ui` 下 4 文件，其余包测试文件与基线逐字节相同，受影响面由门禁干净复跑的 V02+V03 覆盖。本回合工具无 bash，无法亲手补跑，接受存档证据，**不构成打回理由**（下一次全量回归自然覆盖）。
- 白盒探针文件已删（门禁交付前核实无残留）；mutations.json `files_left_modified: []`，本审 grep 工作目录 readroutes.ts 确认 `FOLLOW_ARGV` 在位——树已还原、与候选一致。
- 摘要里的「可疑命令」`bun install --frozen-lockfile` 就是合同要求的 V01 本尊，非依赖变更。新增被忽略路径（.pytest_cache、desktop/web/dist、node_modules）均为运行产物，不在候选里。

## 五、执行端自报偏离的复核（同意门禁 5 条结论）

1. README 三处旧话修订：站主口径在案，不算缺陷，结项后规划端修订（已写进下游须知）。
2. 不可达兜底（回显请求句柄）：不构成合同违反，选择合理。
3. R2 第二个 409 只断言 409 本身：「不再起子进程」由 F6 与白盒钉住，可接受。
4. 第四种 409 只写 README：覆盖矩阵未要求用例，符合合同。
5. 执行端未自跑变异：合同分工如此。

## 六、不挡的意见（无需本轮处理）

- `followCursor` 的第一分支（游标不可用→回显 requested）若未来内核改变 JSONL 页形状会变成活路径，届时需补一条用例钉住该支的行为；现在真内核不可达，不值得加测试。
- README「日志跟随」一节的 409 表述「已知的一种」与合同「已知的第四种 409」措辞略异，语义一致；规划端结项修订 README 时可顺带统一。

## 七、DoD 总表

D01–D18 全部核实为 done 且证据充分（映射见第二节第 2 条）。无退回事项。

Verdict: PASS
