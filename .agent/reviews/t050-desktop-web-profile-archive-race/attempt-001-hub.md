# 复审记录：t050-desktop-web-profile-archive-race attempt-001（七端信箱 hub）

- 合同：t050-desktop-web-profile-archive-race.v1（base 5884c3d1fcfef75e150df9192b7390ecd1c125d1）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261117T195724883579Z-8fd4），终审报告如下

## 终审报告

# T050-7-audit-post 审核报告（审核端 audit-sonnet · 终审）

## 结论

**通过。** 候选忠实于合同（DoD D01–D10 逐条都有实跑证据），改动面只有允许的 2 个文件、129 行纯新增、0 删除，没有越界、没有弱化既有断言、没有为过测试写的特判；三条新用例在未修实现上真红（内核基线 G01 exit_code=1 ＋ 执行端 SELFCHECK ＋ 变异 M01 复现原缺陷）；战后门禁 6 条变异全被抓住且红点与报告一致。本轮没有阻塞项，不退回任何一端。

## 一、审了什么

- 合同 `.agent/plans/t050-desktop-web-profile-archive-race.v1.md`（DoD D01–D10、Non-goals、Stop conditions）
- 候选 `.agent/runs/t050-desktop-web-profile-archive-race/attempt-001/candidate.patch`、`candidate.stat.txt`、`scope.json`、`changes.json`
- 执行概述 `summary.md`、执行报告 `executor-report.md`（含 10 条 DoD 自述、2 条 interpretations、2 条 limitations）
- 内核检查 `checks/01/`（G01/R01/V01/V02/V03）、基线 `baseline/01`（G01 exit 1）
- 战后门禁 `.agent/mailbox/tasks/T050-6-gate-post/`（白盒文件、6 条变异与 mutations.json、M01.log 实读、报告）
- JEV `.agent/mailbox/tasks/T050-6j-jev/report.md`：no_opinion（auth_failed），无额外约束要核对

## 二、改动面与实现忠实度

- 范围：`candidate.stat.txt` = 2 files changed, 129 insertions(+), 0 deletions；`scope.json` violations 0 / warnings 0 / counts A0 M2 D0 T0、head_after 仍是基线 5884c3d1；`changes.json` 只有这 2 个 M，mode 未变。
- 改动只有两处：
  1. `desktop/web/src/writes/ProfileForm.tsx`（+9）：读档案的 effect 里加一个**每次 effect 运行独有**的局部变量 `settled`（成功分支在 `if (!alive) return;` 之前置真，reject 分支也置真），清理函数改成 `alive = false;` 之后 `if (!settled) archiveRead.current = false;`，外加 5 行说明这条反直觉约束的注释。依赖数组 `[open, runtime, runtimes]`、`!open` 分支、`setArchive` 三态、逐字文案、两个导出入口一个字节没动。
  2. `desktop/web/tests/writes-profile-quizs.test.tsx`（+120）：文件末尾追加 `deferred()` 助手、两个信封常量、共用开场 `secondOpenWithDeferredReads(id)`，以及一个含 3 条用例的 describe（:406–474）。
- 机制复核（为什么这样既修好又不多读）：`settled` 是每次 effect 运行独有的闭包变量，而清理函数每个 effect run 只跑一次。
  - 结果还在路上时 effect 重跑 → 清理时 `settled` 仍为假 → 复位 `archiveRead` → 重跑照样再读一次（正是站主登记的第二次打开卡在正在读那条路径）。
  - 结果已经回来（读到 / 读不出 / ok:false / 无提供方都算）→ `settled` 为真 → 不复位 → 同一次打开不再读第二次。
  - 作废的读迟到回来 → 它自己的 `alive` 已是假 → 只改自己闭包里的 `settled`，不回写 `archiveRead`、不改界面（迟到的结果照旧丢弃）。
  - 依赖数组没动，所以切到非 quizs 再切回、重新打开重读这两条老路由既有断言与白盒 R1–R3 兜住。
- 没有为过测试写的特判：实现里没有任何与测试 ID、文案、次数相关的分支；新增代码里没有空的 catch；新用例断言的是真实渲染出来的 SELECT/选项/档位/按钮 disabled 与真实调用次数，没有把业务逻辑抄一份进测试。

## 三、DoD → 证据映射（终审版）

| DoD | 由谁证明 | 证据 |
|---|---|---|
| D01 | 包内用例 A（writes-profile-quizs.test.tsx:407–431） | 断言模型是 SELECT、两项逐字 stepfun/step-5-preview 与 deepseek/deepseek-chat、自动选第一项、档位 low/medium/high、不再写正在读、advance(350) 后命令含 --runtime=quizs-cli --model=stepfun/step-5-preview、formConfirm(d).disabled === false；V01（129 files/1252 passed）、G01（4 passed）、白盒 R4 同覆盖 |
| D02 | 未修实现上真红 | 内核 baseline/01/checks.json 的 G01 exit_code=1（门禁基线在未修树上红）；执行端 SELFCHECK（临时去掉复位行 → 用例 A/C 红在 expected 1 to be 2，恢复后 sha256 逐字节一致）；战后变异 M01/M05 复现原缺陷 → R4 expected 1 to be 2、R1 expected 2 to be 3（M01.log 实读） |
| D03 | 包内用例 B（:433–451） | 读完后列表换数组仍 1 次、切 pi 再切回仍 1 次、档案仍显示；白盒 R1/R2/R3 另证读不出/ok:false/无提供方三种读完态 |
| D04 | 包内用例 A 尾部 + 用例 C 尾部 | 迟到的失败信封回来后仍是 SELECT、选项不变、次数不变；白盒 R4 末段同证 |
| D05 | 0 删除 + 既有测试照旧通过 | 候选 0 删除 → 既有断言一字未改；V01 1252 passed（本文件原 14 条 + 新 3 条 = 17）；R01 1069 passed（t046 门禁 form 探针的 1/2/0 次与挂起的读照旧） |
| D06 | 未动文案与依赖数组 | diff 只 +9 行（一个变量、一行条件复位、5 行注释），文案常量与 [open, runtime, runtimes] 未动；既有 :145/:153/:222/:323 断言在 V01 里照旧通过；白盒 R1–R3 覆盖重开重读与六档/失败文案 |
| D07 | 包内用例 C（:453–474） | 读途中切 pi 再切回 quizs → 重读（2 次）、档案照样读到、迟到结果丢弃 |
| D08 | 范围（人工审） | candidate.stat.txt（2 files, +129, −0）、scope.json（violations 0）、V02 typecheck 通过、V03 build 通过；package.json 与 package-lock.json 不在 diff 内（无新增依赖） |
| D09 | 纯追加（人工审） | 0 删除 ⇒ 基线全文是新文件的严格前缀；我另 grep 新用例区，无 skip/only/todo（也无 it.only / describe.only / it.skip / todo），既有用例一个没删没改 |
| D10 | 全过 | V01 npm test 1252 passed；V02 npm run typecheck 退出码 0；V03 npm run build ✓ built in 1.40s |

D08/D09 按上一轮一审的结论属人工审阅项，本轮按候选 diff 逐条核过，结论：满足。

## 四、战后门禁与变异核对

- 白盒 `tests/test_gate_t050_whitebox.py` 在候选上全绿（探针 4/4），无 candidate_defects；文件里没有写死绝对路径、没有往仓库外写文件（grep `C:\` / `/tmp` / `tempfile` / `mktemp` 零命中）。
- 变异 6 条全打在唯一非测试改动文件 ProfileForm.tsx 上，测试文件不变异（合理：变异检验的是测试能否抓住实现变化）；mutations.json：caught 6 / missed 0 / skipped 0 / error 0，files_left_modified 为空。
- 逐条判断「门禁端声明的变异是不是真测不出来」：
  - M1 去掉条件复位（复现原缺陷）→ 抓住，红点 R4 expected 1 to be 2、R1 expected 2 to be 3（M01.log 实读，与门禁报告一致）。
  - M2 复位改成无条件 → 抓住（R1/R2/R3 的不再读第二次次数变 2）。
  - M3 成功分支不置 settled → 抓住（读完后换数组被当成还在路上 → 多读）。
  - M4 reject 分支不置 settled → 抓住（读不出后多读）。
  - M5 settled 初值改真 → 抓住（永不复位 → 停在正在读）。
  - M6 摘掉 getQuizsProviders 接线 → 四条全红（接线变异）。
  六条都是可观察的行为变化，没有假变异。
- 门禁端说「没法变异的改动」= 5 行注释：确实无行为，不必测。
- 门禁端 ASSUMPTION 4（settled=true 挪到 if(!alive) 之后是行为等价）我复核成立：settled 只被同一 effect run 的清理函数读一次，promise 回调与清理不会交错，清理之后再写 settled 无人再读 → 等价，无需补测。
- 门禁端 ASSUMPTION 1（R1 的重开 = 3 次）复核：deferred 桩下重开那次打开 = 当场 1 次 + 运行时列表换新数组重跑 1 次（此前会话 1 次）= 3；与既有 :153 的重开 = 2（两个桩已兑现、结果已 settled 不复位）口径不同但不冲突，两种口径在同一实现下都成立（V01 里 :153 仍绿）。
- 战后门禁没有举证的候选缺陷，也没有需要我裁定的白盒缺陷；不需要退回战后门禁。

## 五、执行端自述与内核线索逐条对上（没有自述不实的项）

| 内核摘要线索 | 核对结果 |
|---|---|
| 掩盖退出码的写法（9 条命令，例 cd desktop/web && ls && cat package.json && ls node_modules 管道接 head -5） | 抽查 events.jsonl 第 57–67 行：是探查目录、看 package.json 一类的命令，不是测试或检查命令；执行端报告里所有自检命令都带 set -o pipefail（npm test 2>&1 管道接 tail -n 40 等），退出码没被抹 |
| 新增被 Git 忽略的路径 .pytest_cache/、desktop/web/dist/、ts/node_modules/** | 是 pytest / vite build / npm ci 的副产物，都被 Git 忽略，不在候选里（stat 只有 2 个 M）；执行端没把它们列进改动，与实际一致，不算自述不实 |
| 执行器自行宣布 1 处解读：未运行 R01 全量（49 份，约 945 秒） | 与报告 limitations 一致；内核自己跑了 R01 全量（1069 passed / 941s），D05、D10 由内核检查兜住，执行端没有把没跑的写成跑了 |
| 工具错误 1 | 是执行期工具调用错误，不是测试失败；不影响候选内容（候选 2 文件 129 增 0 删，V01/V02/V03/G01/R01 全绿） |
| 执行端 SELFCHECK 临时去掉复位行 | 临时改动在工作目录内、备份 .orig 已删、sha256 复核逐字节一致、候选 numstat 为 9/0 与 120/0 → 临时改动没进候选、无残留 |
| DoD 自述 D01–D10 全 done | 逐条与第三节证据对上，全部有实跑记录支撑，没有靠推断写成 done 的项 |
| JEV | no_opinion（auth_failed），无额外约束 |

## 六、意见（不挡，供站主与后续片参考）

1. StrictMode：desktop/web/src/main.tsx 用了 StrictMode。开发模式下若对话框在挂载时就是打开的，effect 会跑两遍（cleanup → 重跑），修复后这次会多发一次请求（第一次被作废、第二次生效），界面结果正确；实际用法是挂载时关闭、用户点开才置 open=true（更新而非挂载），不触发双跑；生产构建里 StrictMode 不双跑。不是回归，后续片动这块要知道。
2. 白盒文件 tests/test_gate_t050_whitebox.py 是门禁端新增的仓库文件、不在候选补丁里，是否随基准入库由协调人/hub 定（规划端下游须知建议留作回归）。
3. 白盒里的重开 = 3 次、六档、三条读不出文案是行为钉：以后要改这些行为，先退役对应断言，别直接改数字。
4. 后续片若用等价写法重写这段 effect（例如把已读置真挪到结果回来且 alive），包内用例与白盒都按行为断言，不受影响。

## 七、阻塞项

无。

Verdict: PASS
