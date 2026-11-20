# 复审记录：t065-desktop-appearance-sync-read-fix attempt-001（七端信箱 hub）

- 合同：t065-desktop-appearance-sync-read-fix.v1（base 2fe5d38d261813248f690c599faa9a374798e16b）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261120T020132683623Z-7720），终审报告如下

## 终审报告

# T065-7 终审报告（audit-sonnet）

## 结论

**通过**。候选 attempt-001 忠实于合同 t065-desktop-appearance-sync-read-fix.v1；改过的 T061 S07 严于旧判定；两套门禁 + 战后白盒把合同点名的四种退化写法、两条接线错误和 README 说法退化全部拦住；执行报告的自述与内核记录逐条对得上，没有虚报。本回合无阻塞项。

## 材料

- 合同 `.agent/plans/t065-desktop-appearance-sync-read-fix.v1.md`（含站主决定原文）
- 候选 `.agent/runs/t065-desktop-appearance-sync-read-fix/attempt-001/candidate.patch`（3 个 M：main.js、README.md、test_gate_t061_baseline.py）
- 执行概述/报告 `summary.md`、`executor-report.md`/`.json`、`events-summary.json`；内核检查 `checks/01/checks.json` 与 V01/V02/G01/R01 四份日志；基线检查 `baseline/01/`
- 战后门禁 `T065-6-gate-post/report.md`、白盒 `evidence/whitebox-20261120T014815491761Z.py`、变异记录 `evidence/mutate-20261120T014816297123Z/mutations.json`
- JEV 判断 `T065-6j-jev/report.md`
- 工作树现状：`desktop/shell/main.js`、`tests/test_gate_t061_baseline.py`、`tests/test_gate_t065_baseline.py`、`desktop/shell/README.md`

## 一、实现是否忠实于合同（先读源码，再看记录）

逐字比对了 Behavior contract 与 Steps 2–4、8：

- `desktop/shell/main.js:87-97`（外壳分支宿主读取）：`let answer = null;` → `try` 里来源被认时 `answer = currentAppearance;` → `catch { answer = null; }` → 末句 `event.returnValue = answer;` 紧接 `});`。来源判断条件（`serviceWindow !== null && !serviceWindow.isDestroyed() && event.sender === serviceWindow.webContents`）与通道逐字未动。
- `desktop/shell/main.js:100-113`（外壳分支外壳读取）：同款写法，`shellWin`/`settingsWin` 两个来源条件逐字未动。
- `desktop/shell/main.js:395-397`（带参数起服务分支）：函数体只剩 `event.returnValue = null;` 一句，原 try/catch 与其中注释一并删掉，函数上方的说明注释保留。
- 赋值次数：三处跨度内 `event.returnValue =` 各恰好一次；`ipcMain.on` 仍恰好三处、通道字面量与注册位置未动。
- 注释：新增只有一行（`:86`，宿主读取处理函数**上方**），写「returnValue 的第一次赋值就是给渲染进程的回复……所以先在局部变量里算好、只赋一次」；`event.returnValue = answer;` 与 `});` 之间没有任何注释（:96→:97、:112→:113 直接相邻）；注释里没有 `ipcMain.on(`、没有 `event.returnValue =` 这样的字样，也没有 T025 的 7 条禁令（`persist:`、`shell: true`、fs 写函数带括号、`fetch(`、`net.request`、`autoUpdater`、`crashReporter`）——符合合同 Step 8 与站主「注释只能放在 `let answer = null;` 之前或处理函数上方」的决定。
- `desktop/shell/README.md:210`：改成「处理函数每条路径恰好给 `event.returnValue` 赋一次——Electron 的 `returnValue` 第一次赋值就是给渲染进程的回复，之后的赋值不会报错、直接被丢掉，所以主进程先在局部变量里算好、只赋一次」；该行其余内容（三处全在 `main.js`、带参数分支恒答 `null`、来源不认/没有可读的外观/读出错一律回 `null`、为什么有监听就要答）原样保留；原因句落在「## 外观」一节内，既有 needle 一个没丢。
- 范围：`changes.json` 只有 3 个 M，无新增/删除，未碰依赖与锁文件、`src/**`、`desktop/web/**`、`desktop/shell/tests/**`、`package*.json`（D07 成立）。

## 二、改过的 T061 S07：强度没有下降（D08）

被替换的只有原 `:460-464` 那三条断言与相关说明文字；`:450-459`、`:465-475`、`:476-484` 三段在补丁里是上下文行，一行未动（补丁 hunk 只在中间插入）。新旧对比：

| 旧断言 | 新判定 | 关系 |
|---|---|---|
| 每个处理函数含 `event.returnValue = null` | 每个处理函数 `event.returnValue =` 恰好一次（`RETURN_VALUE_ASSIGN_RE`，`==` 不算） | 更严（挡住「先 null 再覆盖」） |
| `= null` 至少两处 | 外壳两处：尾锚 `= <标识符>; })` 锚在函数体末尾、rhs 逐字 `answer`、有 `let answer = null;`、有 try/catch、catch 块里不出现 `returnValue` 且有 `answer = null;` | 更严（形状与字面量都钉住） |
| 三处都要 try/catch | 带参数那一处：无 try/catch、函数体只有 `= null` 一句（`RETURN_VALUE_ONLY_NULL_RE`） | 按合同改形状（合同 Step 5 第三条），不属弱化 |
| — | 保留：`ipcMain.on` 恰好三处 + 通道白名单 + 宿主两处/外壳一处 + `answering`/`always_null` 计数 + `isDestroyed` 检查 + `desktop/shell` 下别的 `.js` 一处 `ipcMain.on` 都不许有 | 原样 |

新增的三个模块级正则（`RETURN_VALUE_ASSIGN_RE`、`RETURN_VALUE_TAIL_RE`、`RETURN_VALUE_ONLY_NULL_RE`）是合同 Step 5「建议实现」里点名的写法（尾锚 + 标识符 RHS），执行端在报告的 `interpretations` 里说明了取舍，属于合同允许的等价实现。T061 的 `_main_code()` 本身先剥注释，所以形状扫描不会把注释里的字样算进去（与合同建议一致）。

## 三、门禁与检查记录（内核侧）

| 检查 | 内核记录 | 结论 |
|---|---|---|
| V01（npm test） | exit 0，`# pass 336` / `# fail 0` | 通过（D04） |
| V02（T061 门禁） | exit 0，`17 passed` | 通过（D02/D08） |
| G01（T065 新门禁） | exit 0，`4 passed` | 通过（D06） |
| R01（63 份门禁全量） | exit 0，`1195 passed` | 通过（D05） |
| 基线 G01 | `4 failed`，每条都带真实断言与 baseline 代码片段（不是收集失败、不是文件不存在） | 无「空心基线」 |

新门禁 `tests/test_gate_t065_baseline.py` 逐条在基线上红在断言上（S01「这段跨度里有 3 次」、S02 尾锚不成立、S03 带参数分支还有 try/catch、S04 README 旧说法），断言本身有证明力。

## 四、执行概述、内核记录与 JEV 判断的对账

- 内核摘要里的「临时路径」「可疑命令」线索：`events-summary.json` 显示 `temp_path_uses=0`、`outside_worktree_paths=[]`、`suspicious_commands=[]`、`temp_dirs_without_cleanup=[]`。被点名的 4 条「掩盖退出码」命令逐条看过，都是 `grep`/`git status` 一类查看命令（管道后接 `head`/`|| true`），没有一条是检查或测试命令；测试命令全部带 `set -o pipefail`。**自述与证据一致，没有「自述不实」。**
- 摘要里的「删除了 3 行含断言的代码（新增 10 行）」对应 S07 那三条旧断言被替换 —— 逐行读过替换后的形状，是加强不是放松（见第二节）。
- JEV 的「自行解读合同 p=0.78」：唯一的一处解读是模块级另加三个正则常量，已在 `interpretations` 里登记，且核对为合同 Step 5 点名的写法，不是私自选另一种需求解读。
- JEV 的「自述完成而无证据 p=0.90」：对应 D09。合同 D09 自己写明「证据：review」「候选里没有这份证据，验收按『静态门禁 + 站主冒烟』判」，执行端标 done 的同时在 DoD 与 `limitations` 里明说「只有静态形状证据，真窗口冒烟需站主落地后跑、我未运行任何真 Electron 窗口」——不构成误导性自述。
- 执行报告 D04 那行留了自纠痕迹「`# pass 326`…实为 336 pass / 0 fail」，与内核 V01.log 的 `# pass 336` / `# fail 0` 一致；JSON 报告里写的是正确的 336。

## 五、战后门禁举证的复核

- 变异清单 13 条：`mutations.json` counts = caught 13 / missed 0 / error 0，逐条对应 main.js 11 条（末句答 null 两条、catch 碰 returnValue、赋值挪到 try 之前、带参数分支赋两次、删注册、接错通道、赋值挪出来源判断、try 里恒 null、缺省值改成 currentAppearance、退回基线形状）与 README 2 条（说法退回、删原因句）。没有「声明等价但其实测不出来」的条目。
- 白盒 W01–W08：夹具都有自检（如 W02 断言构造器确实把两处改成覆盖写法、W04 断言赋值确实挪到 try 之前），不是空转；W06 钉注册位置（挡分支对调）、W07 钉 `answer = currentAppearance;` 必须在来源判断的 if 块内且条件含 `event.sender ===`（挡挪出 if），这两条正是我一审指出的两套门禁盲区，已被钉住；W08 按原文（非剥注释）检查 `event.returnValue = answer;` 与 `});` 相邻，并查注释里不许出现 `ipcMain.on(` / `event.returnValue =`。
- 白盒与变异清单是本次核验用物，按规矩不进仓库，我没有把它们当成会留在仓库里的回归测试来提意见。

## 六、不挡的意见（写进 report，不进阻塞项）

1. T061 S07 里 `answering` 那一行的断言文案还写着旧形状的「来源被认时把 event.returnValue 覆盖成当前外观对象」。该行属合同明令不许动的 `:465-475` 段，所以不改是对的；文案过时可在后续片顺手改，不影响判定。
2. 「恰好一次」只数 `event.returnValue =` 这一种写法；若有人写成 `event["returnValue"] = null;`，计数与 catch 块检查都看不见。触发路径具体但几乎不会有人这么写（写出来人眼就能看出），按规则不挡；要堵的话可在 S07 里加一条 `returnValue` 的括号写法检查。
3. D09 的运行期证据仍在仓库外：站主在冒烟树用同两处改法跑过三轮真窗口冒烟（19/19、1/1、4/4），但落地进仓库后的那一次还得站主自己跑。
4. 执行报告 markdown 里 D04 那行的自纠痕迹（`# pass 326`…）建议下一版清掉，属排版问题。

## 七、下游须知

- 落地必带 `tests/test_gate_t065_baseline.py`（门禁端产物，D06 靠它）；`tests/test_gate_t065_whitebox.py` 与根下 `mutation-spec.json` 是核验用物，不进仓库。
- T064 并行改 main.js：T061 S07 与 T065 基准都钉「恰好三处 `ipcMain.on`」，T064 若新增注册，两套门禁一起红；落地次序照合同由内核排，两片都落地后重跑这两套门禁。
- 站主落地后跑真窗口冒烟补 D09。

Verdict: PASS
