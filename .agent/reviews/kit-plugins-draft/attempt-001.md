# REVIEW：kit-plugins-draft v1 · attempt-001

Verdict: REVISE

<!-- review-draft 生成（2026-10-17T11:43:01Z，调度工具 2.10.0）：事实取自 .agent/runs/kit-plugins-draft/attempt-001；标着“待填”的地方是复审判断，全部填完 verdict 才收。
     Verdict 行只能写一个结论，并与 verdict 命令的 --verdict 一致。 -->

## 基本信息
- 基线：`ce04541889a5b6cfbc34ce603a65b42afd08c241`
- 候选树：`6145f08ad934c26e033530f4bfafafb7c7d550bf`（补丁往返校验通过；4 files changed, 1581 insertions(+)）
- 要求的执行模型：bb/step-5-preview · thinking high
- 实际模型：bb/step-5-preview；providerThinkingLevel：未回报
- 运行：退出码 0 · 用时 2136.188 s / 上限 2700 s · 正常结束 · 工具错误 1
- token：输入 269382 · 输出 131815 · 缓存读 6806272 · 缓存写 0；费用 unknown（unknown）
- 复审者：B 组规划审核端——Claude Code 子代理（general-purpose，`claude-haiku-5-5`，只读，在 scratchpad 的副本里跑变异与复现）；主会话（Claude Code，Opus 5.5）逐条复核了 B1–B4：B1、B2、B4 读候选源码与草稿合同确认，B3 在临时 Git 仓库复现出堆栈。

## 门禁

| 门禁 | 结果 | 说明 |
|---|---|---|
| G0 输入一致 | passed | 工具：通过 |
| G1 执行完整 | passed | 工具：通过；提供商未回报思考级别：只能确认请求的级别（high） |
| G2 范围合规 | passed | 工具：通过；执行器的命令里出现工作副本外路径：/c（bash，事件流第 6801 行） |
| G3 行为正确 | 未通过（复审） | 工具：通过；参考实现有两处缺陷而 oracle 没有抓住：B2 授予路径读取其他插件的 manifest 之前没有链接检查、读取错误被静默吞掉；B3 插件 ID 不校验，`show ../plugins/code-change` 冒出 `first_link_component` 的 ValueError 堆栈、退出码 1。G3（“本轮不支持”计为问题、verify 退出 1）没有违背：草稿合同第 80 行、oracle P11、实现一致，事件流第 22761 行的推断终稿未采用 |
| G4 回归检查 | passed | 工具：通过；检查记录：checks/01（fresh，3/3 通过）；检查在干净副本（基线 + 候选补丁 + setup）上运行 |
| G5 质量复审 | 未通过（复审） | oracle 测不出 G1、G2、G4（B1，变异 33/33 通过）；P1 的期望值来自被测实现的私有函数（M2）；P5 可构造的子情形缺失（M1）；若干弱断言（m1）。过程偏差见下（M4） |
| G6 可集成 | passed | 工具：通过 |

## DoD 映射

| DoD | 结果 | 证据 | 说明 |
|---|---|---|---|
| D01 | 部分满足（草稿合同第 67 行与 G1 自相矛盾，B4；contract.json 的 coverage 没有 D07 的落点、scope 写成字符串，M3） | V02 passed、scope（越界 0） | 三个交付物就位，合同草稿按模板并通过 JSON 必需键检查；目的：草稿可以被审核端直接改写成正式合同 |
| D02 | 未满足（B1：G1、G2、G4 没有用例；M1：P5 子情形缺失；M2：P1 的期望值取自实现；m1 弱断言） | V01 passed、复审 | oracle 覆盖 §9 的 P1–P17（能写的都写），在本机真正运行（执行报告写明跳过的用例数与原因，若有），只用合成副本，从不修改仓库里的真实 plugins/；目的：oracle 能区分正确实现与错误实现，而不是只能证明“能跑” |
| D03 | 部分满足（参考实现让 oracle 全过，但有 B2、B3 两处缺陷，说明 oracle 区分不了；没有调用私有函数，枚举自写并经 `pd.is_link_or_junction` 检查） | V01 passed、V03 passed、复审 | 参考实现让 oracle 全部通过，只调用既有公开函数，不另写同类实现；目的：证明 oracle 在正确实现上可以通过（上位设计 4.7 第 2 步） |
| D04 | 满足 | scope（越界 0） | 所有修改都在允许集合内 |
| D05 | 满足 | 复审 | 没有修改既有文件，没有删除、跳过或弱化既有测试 |

## 范围与质量
- 越界与警告：越界 0、警告 0
- 测试可信度：oracle 33 项，参考实现上全过；没有参考实现时是 1 个收集错误（设计 4.7 第 2 步说导入失败只算弱证据）。审核端的变异：G2 改成退出 1 且 G4 跳过校验，33/33 通过；单独把 G1 改成退出 1，33/33 通过；去掉“本轮不支持”的问题项，P11 失败。没有 skip 或弱化既有测试（只新增文件）。
- 变异检查：没有记录（中高风险任务要做一轮，见 review-pi/mutation-check.md）
- 兼容性与残余风险：起草任务的产物不集成（设计 4.7 第 6 步：参考实现不进基线）；风险全在将发布的合同与 oracle：按现稿发布，执行端可以写出 G1、G2、G4 错误、ID 穿越崩溃、授予路径读链接的实现而 oracle 全过。
- 执行器自述与证据是否一致：`contract_conflicts` 为空，但草稿合同第 67 行（list 退出码恒为 0）与第 78 行 G1（list 不在 Git 仓库时退出 2）冲突，按执行说明应报告并阻塞相关 DoD；事件流第 20622、22761 行推理过的 G3 与私有函数歧义没有写进 interpretations；执行器自测时 4 条 python 命令用 `tempfile.mkdtemp()` 建目录（事件流第 32525、33056、33506、34304 行，末尾 `shutil.rmtree(T, ignore_errors=True)`），违反 AGENTS.md 的临时目录规定；第 6801 行的 `T=$(mktemp -d) … rm -rf "$T"` 合规。
  - 执行报告：json_ok（executor_status completed）
  - 合同矛盾：无
  - 自定解读（4，原文）：
    - {"quote": "T1 --json 的键名与结构；oracle 只断言输出可解析为 JSON 对象，不断言键名", "adopted": "各子命令 --json 输出一个 dict（list:{plugins,not_installed,problems}；verify:{ok,plugins,not_installed,problems}；show:{id,'manifest.json':{...},'lock.json':{...},...}），oracle 只断言可解析为对象", "reason": "T1 明确放开；设计 §4.2 未固定 --json 键名（不同于 logs §4.1）"}
    - {"quote": "T2 文字输出的格式、列宽与提示语措辞；oracle 只断言固定词、插件 ID、退出码与文件字节", "adopted": "每插件一行，含状态词与原因；提示语自定", "reason": "T2 明确放开"}
    - {"quote": "T3 授予权限时受影响插件清单的排序与格式（§4.2 要求列出）", "adopted": "按插件 ID 排序，格式为“授予 P 后，以下插件也满足权限条件：id1, id2, ...”，oracle 断言这些 ID 出现", "reason": "T3 明确放开排序与格式"}
    - {"quote": "T4 写入失败（OSError）时的提示文字自定；退出码记为 1", "adopted": "stderr 打印“ERROR: 写入 dispatch.config.json 失败：...”，退出码 1", "reason": "T4 放开措辞；退出码 1 沿用 §4.2“被拒绝 1”"}
  - 限制与取舍（4，原文）：
    - 参考实现 scripts/kit_plugins.py 为草稿参考，不发布；发布时只取合同与 oracle
    - 内层 base_sha 为全零占位，待审核端替换为 oracle 基线提交
    - P5 的“文件是链接”场景用目录 junction 实现（读取前即检出，无需文件符号链接权限）；本机建不了文件符号链接，但未因此跳过任何用例
    - 未跑全仓测试，只跑 V01–V03 指定文件；未修改既有文件，既有测试不受影响
  - 未决问题：无
  - 事件流里的解读线索（逐条核对是否都在上面的自定解读、合同矛盾或未决问题里）：
    - 第 22761 行（thinking）：. But "本轮不支持" is a deliberate limitation, and flagging it as a failure every time might be noise. I'll go with: 本轮不支持 does NOT cause verify to fail (exit 0), because it's a known limitation, not drift. So verify exits 1 only for 漂移/无效/资源不一致/battery-d
    - 第 22761 行（thinking）：t、锁、资源文件核对结果与问题清单；... 全部一致 0；有问题 1". "有问题" = has problems. Is "本轮不支持" a problem? It's a limitation. I'll interpret "有问题" as "有不一致/漂移/无效/未安装" — real integrity problems. "本轮不支持" is neither — it's "we didn't check". So verify exits 0 for a 本轮不支持-only plugin
    - 第 22761 行（thinking）：h it. The oracle asserts exit 0. Hmm, actually, let me reconsider ONE more time, because this is a judgment call that affects the oracle. Let me re-read the design §4.2 verify row: "全部一致 0；有问题 1；ID 不存在 2". And r1-S1: "`list` / `verify` 把它们报为'本轮不支持'".
- 摘要里的“复审需要关注”（原文）：
  - 可疑命令（递归或强制删除）：命令第 1 / 1 行 `…import os; os.symlink(r'$T\\target', r'$T\\dlink', target_is_directory=True); print('DIR_SYMLINK_OK', os.path.islink(r'$T\\dlink'))" 2>&1 | head -3; rm -rf "$T"`（事件流第 6801 行）
  - 可疑命令（递归或强制删除）：命令第 1 / 6 行 `cd . && rm -rf .linktest && mkdir -p .linktest/target && echo hi > .linktest/target/f.txt && python -c "`（事件流第 7104 行）
  - 可疑命令（递归或强制删除）：命令第 1 / 27 行 `cd . && rm -rf _smoke && mkdir -p _smoke/.agent && git -C _smoke init -q && python -c "`（事件流第 23501 行）
  - 系统临时路径线索（5 个命中片段）：逐项按 AGENTS.md 核对写法、用途和工具结果。这些是事后扫描线索，不是命令阻断或违规裁定；清理输出或路径当前不存在，不能证明此前未覆盖既有内容
  - 临时路径：事件流第 6801 行，命令第 1 行 `date +%s; T=$(mktemp -d); echo "T=$T"; mkdir -p "$T/target"; echo hi > "$T/target/f.txt"; echo "--- dir junction ---"; cmd /c mklink /J "$T\\jlink" "$T\\target"…`
  - 临时路径：事件流第 32525 行，命令第 5 行 `T = pathlib.Path(tempfile.mkdtemp()).resolve()`
  - 临时路径：事件流第 33056 行，命令第 7 行 `T = pathlib.Path(tempfile.mkdtemp()).resolve()`
  - 临时路径：事件流第 33506 行，命令第 7 行 `T = pathlib.Path(tempfile.mkdtemp()).resolve()`
  - 临时路径：事件流第 34304 行，命令第 10 行 `T = pathlib.Path(tempfile.mkdtemp()).resolve()`
  - 工作副本外路径（bash，调用成功，事件流第 6801 行，共 4 条命令）：`/c`
  - 新增被 Git 忽略的路径：`.pytest_cache/`
  - 新增被 Git 忽略的路径：`.pytest_cache/.gitignore`
  - 新增被 Git 忽略的路径：`.pytest_cache/CACHEDIR.TAG`
  - 新增被 Git 忽略的路径：`.pytest_cache/README.md`
  - 新增被 Git 忽略的路径：`.pytest_cache/v/`
  - 新增被 Git 忽略的路径：`scripts/__pycache__/`
  - 测试或检查命令的退出码被管道掩盖（4 条，例如事件流第 33056 行 `" 2>&1 | head -20`；另有 10 条探索命令也如此）：执行器没有看到被检查程序的退出码，报告里的 reported_exit_code 是推断值，以 check 的结果为准（2.10.0 起执行说明给了每条检查的自检照抄写法）

## 结论理由
交付物齐全（越界 0，fresh 检查 3/3），命令语义、退出码、D5 读前检查、D6 语义与修复提示来源大体忠实。但起草合同 v1 本身有缺口，执行端照着它写出的合同与 oracle 达不到发布标准，所以判 REVISE、分类 PLAN_ERROR（缺口主要来自规划审核端的起草合同）：
- B1：起草合同没有要求 oracle 覆盖写死的 G1–G4，结果 G1、G2、G4 都没有用例；
- B2、B3：起草合同没有写“插件 ID 先按 `PLUGIN_ID` 校验”与“授予路径读取其他插件 manifest 前的链接检查”，参考实现在这两处出错，oracle 也测不出；
- B4：起草合同的 G1 把 list 列进“不在 Git 仓库时退出 2”，与设计 §4.2 的“list 退出码 0”直接冲突，草稿照抄两处而没有报告；
- M1–M3、m1–m5 见规划审核端的意见，打包进 v2。
执行端的过程偏差（M4：`tempfile.mkdtemp()`、未报告的冲突与解读）记在本 attempt 上。草稿的大部分可以沿用：在本候选上继续，出 kit-plugins-draft.v2，派最后一次（max_attempts_total 2）。

## 后续动作
- 需要修正的具体差异（REVISE）：
  - B1：oracle 补 G1（五个子命令不在 Git 仓库时都退出 2）、G2（enable、disable、show、verify 的 ID 不存在退出 2）、G4（`--dry-run` 校验失败退出 1，配置文件字节不变；通过时退出 0、不写文件）。
  - B2：合同写明授予路径读取其他插件 manifest 前做同样的读前链接检查（`pd.first_link_component`），失败计为该插件的问题而不是静默跳过；oracle 补一例（另一个插件的 manifest 是链接）。
  - B3：合同写明所有子命令的插件 ID 先按 `PLUGIN_ID` 校验，不合法或不存在退出 2、打印 `ERROR:` 一行；oracle 补 `../plugins/<id>`、`a/b`、空串等用例，断言退出 2 且没有 Traceback。
  - B4：草稿合同第 67 行改成“退出码 0（不在 Git 仓库时 2，见 G1）”。
  - M1：P5 补可构造的子情形（plugins 根、中间目录、资源路径为目录 junction）；只有文件链接才能构造的变体用 `pytest.skip` 并写明原因。
  - M2：P1 的期望值取自测试副本的 plugins/ 目录或字面 ID，不调用被测模块的函数。
  - M3：contract.json 的 coverage 给 D07 落点（或列为 added），`coverage.scope` 改成数组，S7 补上 D01–D03 的 CLI 部分。
  - m1：补强 P7、P16a、P2c、P6、P17 的断言；“无效：链接”逐字断言；P9 的顺序断言要有合同依据（规划端裁定：`allowed_permissions` 写入时去重并按字符串排序，与 `enabled` 一致，写进合同）。
  - m2：show 输出锁的 generation 与逐资源的哈希核对结果（合同第 68 行已要求）。
  - m3：题库阶段除 `DecisionError` 外也收集 `OSError`、`ValueError`；plugins 根是链接时枚举为空，`disable X` 按 ID 不存在退出 2，不写配置。
  - m4：事实表删去私有的 `_installed_plugin_ids()`（或注明不得调用）；读前检查补 D5 的枚举规则。
  - m5（规划端裁定）：去掉设计没有要求的 `--version`；disable 写显式列表时排除链接目录，写进合同；oracle 改成在用例内导入被测模块，基线上逐例失败。
  - 过程约束重申：临时目录只用 `tmp_path` 或 `T=$(mktemp -d) … rm -rf "$T"`；合同前后矛盾写进 `contract_conflicts`。
- 待决的业务或环境问题（BLOCKED / ESCALATE）：无
- 已授权且可以继续的集成动作：合同没有授权集成动作：交付候选，等待决定
- 人工介入：0（审核由 B 组规划审核端子代理完成，主会话复核，用户未介入）
