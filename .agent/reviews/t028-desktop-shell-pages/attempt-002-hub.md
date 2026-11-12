# 复审记录：t028-desktop-shell-pages attempt-002（七端信箱 hub）

- 合同：t028-desktop-shell-pages.v2（base 1a2a57de5151123ce4cf6809bcd6021cafe60b6d）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261112T183752867784Z-447f），终审报告如下

## 终审报告

# T028-7-audit-post · 终审报告（attempt-002，复审封板）

审核对象：`.agent/runs/t028-desktop-shell-pages/attempt-002/`（候选树 78ab737，基线 1a2a57de）。
材料：合同 `.agent/plans/t028-desktop-shell-pages.v2.md`；候选补丁 `candidate.patch`；执行概述 `summary.md` 与执行报告 `executor-report.md/.json`；战后门禁 `.agent/mailbox/tasks/T028-6-gate-post/report.md`；JEV 判断 `.agent/mailbox/tasks/T028-6j-jev/report.md`（`no_opinion auth_failed`，无意见可核）；内核自跑检查 `checks/01/checks.json` 与四份日志；变异记录 `evidence/mutate-20261112T183506477251Z/{mutations.json,spec.json}` 与 62 份日志。
审核方式：只读。逐行读工作树里的候选源码与两份测试文件，对照合同 Behavior contract 与 Steps；核内核的检查记录、scope 与门禁端声明的每一条「预期抓不住」。本回合只复核上一轮列的 3 条阻塞项与本轮新改动的内容。

## 一、上一轮 3 条阻塞项的复核结论

### 1) `probePython` 认合同写明的 `code` 选项 —— 已解决

- 源码：`desktop/shell/src/detect.js:104-106` 现为
  `const opts = options || {};`
  `const code = typeof opts.code === "string" ? opts.code : PYTHON_INFO_CODE;`
  `const full = [...commandArgs, "-c", code];`
  与合同第 135 行 `probePython(commandArgs, {timeoutMs = 10000, code = PYTHON_INFO_CODE})` 一致：`-c` 之后传调用方给的 code，缺省仍是 `PYTHON_INFO_CODE`。
- 缺省路径未变：`detectPython` 仍按 `python3 → python → py -3` 逐个 `probePython(candidate, { timeoutMs })`，不传 code；门禁基线探针断言 `args[1] === PYTHON_INFO_CODE`（tests/test_gate_t028_baseline.py:885）仍成立，G01 12 条全过。
- 断言钉住（不是空心）：执行端新测试 `probePython：options.code 到达 argv，缺省仍是 PYTHON_INFO_CODE`（tests/detect.test.js:182-201）断言 `spawnCalls[0].args[2] === custom`（自定义 code 真的进了 argv），再跑一次不给 code 的调用断言回到 `PYTHON_INFO_CODE`；白盒另有独立一条（tests/test_gate_t028_whitebox.py:332-345），变异 M31（把 code 选项短路回缺省）被它抓住，M31-W.log 的红点正是「调用方传 {code} 时不许静默回落 PYTHON_INFO_CODE」（actual=PYTHON_INFO_CODE、expected=marker code），不是别处报错带红。

### 2) `shellapi.test.js` 补 `openExternal` 用例 —— 已解决

- 新增 4 条用例（tests/shellapi.test.js:526-575）：① 11 种输入（非 http/https 的 `ftp://`/`javascript:`/`file:///`、带 `\n` 与 `\0` 的地址、首尾空白、无 scheme、空串、`42`、`null`、`undefined`）→ 一律 `{ok:false, reason:"bad-url"}`，并断言确认框与 opener 的 `calls` 都是 0（不许进确认框、不许打开）；② 确认框回 false → `cancelled`，且确认框拿到的是待打开地址、opener 未被调用；③ 确认框抛错 → `internal`（opener 未调用）、注入的 opener 抛错 → `open-failed`（opener 确实收到地址）；④ 用户确认 → `{ok:true, value:null}`，地址同时经过确认框与 opener。
- 不是空心断言：harness 的 `confirm`/`opener` 钩子第一次被真正调用（`calls` 数组与调用次数都被断言），行为走的是真实实现 `shellapi.js:222-237`（`isExternalUrl` 复用 hostcheck.js，非字符串直接 false，控制字符与协议都在 `isExternalUrl` 里判）。D06 的证据 V01 现在对 openExternal 有东西可证了。
- 合同第 178/187 行与 Step 5 点名的内容全覆盖，失败原因集合 `bad-url / cancelled / internal / open-failed` 与合同一致（合同的 reason 集合里 `internal` 也写着）。

### 3) `saveSettings({resetKit:true})` 之后 kit 缓存刷新的断言 —— 已解决

- 新增 `缓存：saveSettings({resetKit:true}) 之后 kit 缓存刷新`（tests/shellapi.test.js:409-427）：两次 `getState` 只许探测一次 kit（断言探测数 == 1），`saveSettings({resetKit:true})` 成功后 `r.value.kit.source === "repo"`（kitPath 已清空、改按当前仓库探测），再一次 `getState` 探测数变成 2。
- 构型合理（同时放 pythonPath、kitPath 与当前仓库），钉住合同第 199 行「检测缓存在选择与两个 reset 之后刷新」的第二个 reset；实现 `saveSettings` 里 `dropCache()` 无条件执行（shellapi.js:216），断言走的是真实路径。

三条阻塞项全部解决且都有可复现的断言，没有靠放宽断言迁就实现：候选补丁 +92/-1，只有一处删除（`const full = [...commandArgs, "-c", PYTHON_INFO_CODE];` 那一行被替换），没有删改任何既有测试。

## 二、门禁端标「预期抓不住」的 5 条变异：逐条裁定

判定依据：`mutations.json` 的逐条结果（每条带 commands.W / commands.B 的 status 与日志）+ `spec.json` 的 old/new 锚点 + 我自己读的基线/白盒断言源码。

| 变异 | 声明 | 实际结果 | 我的裁定 |
|---|---|---|---|
| M07 settings-tmp-suffix（`TMP_SUFFIX ".tmp"→".tmpx"`） | W 抓不住 | W missed、B caught | **成立**。白盒全文没有临时文件名的断言（grep 不到 TMP_SUFFIX），它确实测不到；基线 P01 的探针用「先建一个 settings.json.tmp 目录逼写失败、原文件不动」这条行为断言抓住改后缀的变异（改名后写盘不抛错 → 断言失败），红得有理由，不是文件不存在的空心红。 |
| M23 api-save-dropcache（saveSettings 里去掉 dropCache()） | W 抓不住 | W missed、B caught | **成立**。白盒对 saveSettings 只有白名单/拒绝后字节不变的断言，没有「保存后重新探测」的断言；基线 P04 的探针有「getState 不重复探测；pickPython / saveSettings(resetPython) 之后刷新」（detectPythonCalls 2→3），去掉 dropCache 后这条红，红点明确。 |
| M28 readme-section-title（`## 设置与校验`→`## 设置与存档`） | B 抓不住 | B missed、W caught | **成立**。基线 `test_s05_readme` 是全文针脚（README_T028_NEEDLES 含「设置与校验」），而 README 正文第 5 行本来就写着「（见下文「设置与校验」）」，改标题后针脚仍在 → 基线过。白盒 `test_wb_static_readme` 用 `^##\s*设置与校验\s*$` 按节取 → 抓住。分工合理。 |
| M29 readme-section-10s（`**每个子进程 10 秒**`→`9 秒`） | B 抓不住 | B missed、W caught | **成立**。基线只做全文 `10\s*(秒|s|S)` 搜索，README 第 51/53 行（别的章节）也有「10 秒」→ 仍匹配；白盒按「设置与校验」一节取并在该节内找 10 秒 → 抓住。 |
| M31 detect-code-option-ignored（code 选项短路回缺省） | B 抓不住 | B missed、W caught | **成立**。基线 P03 只断言缺省路径的 `args[1] === PYTHON_INFO_CODE`，从不传自定义 code，设计上测不到；白盒新用例抓住（见上一节）。 |

结论：5 条声明都诚实，没有「其实测得到却写成测不到」的虚报；31 条变异每条都至少被一条检验命令抓住，意外漏掉 0、出错 0。**不退回战后门禁。**

## 三、执行报告自述与内核摘要线索的逐条对上

- 内核摘要的「掩盖退出码的写法（3 条命令，如 `git show --stat HEAD | head -40`）」：都不是测试或检查命令（管道后取的是 `head` 的退出码），执行报告没有拿它们当检查证据 → 不构成 DoD 自述不实。
- 内核摘要的「新增被 Git 忽略的路径」（`.pytest_cache/`、`desktop/web/dist/`、`node_modules/` 等）：是跑 pytest/npm 的产物，Git 忽略，不在候选补丁里（补丁只有 3 个文件，见 candidate.stat.txt）→ 与 D08「无新增、无删除」不矛盾。
- 内核摘要的「运行期间规划路径有变化（`A .agent/plans/t027-desktop-web-live.v4.*`）」：是并行 T027 规划端自己的合同文件，不在执行端改动清单里（changes.json 只有 3 条 M）→ 不构成越界。
- 执行报告的两条 interpretations（非字符串 code 回落缺省、用 argv 断言而非探测成功证明 code 到达）都在 executor-report.json 里如实登记；两条都是合同未规定处的取舍，白盒没有把非字符串回落钉成断言（行为未被擅自加码）→ 披露与实现一致。
- D01–D10 的自述与我在源码/测试里读到的证据一致：D06 的证据 V01 现在真的覆盖 openExternal；D03 的 code 选项已生效且缺省路径未变；D07 的「既有测试一条没删没改」与补丁一致（只增不删）；D08 与 scope.json 一致（3 文件全 in_scope，violations 0，warnings 0）。
- JEV：6j 是 `no_opinion auth_failed`，无可核意见，不影响判定。

## 四、内核独立检查记录

| ID | 命令 | 结果 | output_must_match |
|---|---|---|---|
| V01 | `npm test`（desktop/shell） | exit 0，`# tests 254 / # pass 254 / # fail 0`，12.8s | `# pass [1-9][0-9]*` 命中；`# fail [1]` 未命中 |
| V02 | `python -m pytest tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py -q` | exit 0，25 passed | `\d+ passed` 命中 |
| G01 | `python -m pytest tests/test_gate_t028_baseline.py -q` | exit 0，12 passed | `\d+ passed` 命中 |
| R01 | T001–T026 全量 | exit 0，777 passed | `\d+ passed` 命中 |

checks.json：tree_before == tree_after == 候选树 78ab737（`modified_by_checks: false`，`candidate_files_modified: []`），`covers_all_required: true`、`all_required_passed: true`。执行报告的「V02/G01 合计 37 passed」= 内核分跑的 25 + 12，数字对得上。

## 五、DoD → 证据（本片相关的复核结论）

| DoD | 证据 | 结论 |
|---|---|---|
| D01 设置存盘 | settings.js（attempt-001 定稿）+ 基线 P01 探针 | 成立 |
| D02 六键补丁三类拒绝 | settings.test.js + 基线 P02 | 成立 |
| D03 三项校验与自动检测 | detect.test.js（本轮补 code 选项）+ 基线 P03 | 成立 |
| D04 四个选择器三态 | shellapi.test.js + 基线 P04 | 成立 |
| D05 形状比对 | shellshape.test.js 读 themisShell.ts（未改） | 成立 |
| D06 openExternal | **本轮补齐**：shellapi.test.js 四条用例（基线 P06 之外） | 成立 |
| D07 全过、既有测试未删改 | V01/V02/G01/R01 + 补丁只增不删 | 成立 |
| D08 范围 | scope.json：3 文件全 in_scope、violations 0 | 成立 |
| D09 README/package.json | attempt-001 定稿，白盒按节复核 | 成立 |
| D10 desktop/web 未改 | 补丁不含 desktop/web；R01 全绿 | 成立 |

## 六、不挡的意见（不构成阻塞项，也不升级）

1. `probePython` 的 code 只接受字符串、非字符串回落缺省：合同写的是解构默认值 `{code = PYTHON_INFO_CODE}`（`code: null` 会原样传 null），实现的回落更保守、方向安全，且已披露；合同未规定，不判偏离。
2. `runProcess` 监听 `exit` 而非 `close`：stdout 理论上可能被截断；触发路径窄、概率极低，站主定。
3. `createShellApi` 接受 `now` 但没用（坏副本时刻由 settings store 自己取）：合同把 `now` 挂在 createShellApi 上，实现挂在 store 上，已披露，不影响行为。
4. `detectKit` 返回的 `path` 在相对 kitDir 下不是绝对路径：合同要求绝对路径，当前无调用方给相对路径；T028b 接线时注意。
5. 仓库根留下 `.pytest_cache/`（Git 忽略）：跑 pytest 的产物，不影响候选。
6. 门禁基线 `test_gate_t028_baseline.py` docstring 里的「基线 0592200dd4」是文案残留（上一轮已说，不挡）。

## 七、结论

**结论: 通过**。3 条阻塞项全部修复、被断言钉住且由独立白盒交叉验证；范围 0 越界；内核四条检查全绿且 output_must_match 均命中；门禁端声明的 5 条「预期抓不住」经逐条复核全部成立，无需退回任何一端。

Verdict: PASS
