# 复审记录：t045-desktop-web-hub-bind-entry attempt-002（七端信箱 hub）

- 合同：t045-desktop-web-hub-bind-entry.v3（base df6521ae29ee2b764c91ded8e50622a67368a7b0）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261116T182452221186Z-4e69），终审报告如下

## 终审报告

# T045-7 终审报告（audit-sonnet，attempt-002）

## 结论：通过
候选（候选树 23d04a46，等于返工基线 df6521ae 的树）忠实于合同 v3；改动范围与授权集合逐字对上；attempt-002 的独立检查全绿且日志在案；战后门禁的静态覆盖与 31 条变异成立、候选缺陷为空；JEV 无意见（auth_failed）。没有阻塞项。

## 审法
先读候选源码（快照里的 6 个源文件 + 4 个测试文件 + t024 放宽的三处），再对合同 v3 的 Behavior contract 与 D01–D12 逐条，最后看执行概述、attempt-002 的 checks/04、战后门禁报告与变异记录。只用只读工具，没有跑命令。

## 候选是什么
- attempt-002 的 candidate.patch 是 0 字节：返工基线 df6521ae 已含 attempt-001 的完整实现，本轮零改动（checks/04：tree_before == tree_after == 23d04a46，modified_by_checks=false，candidate_files_modified=[]）。本片实际改动 = attempt-001 的 11 个文件。
- 这 11 个文件正好是合同授权集合：可改 7 个（roles-HubPosts.tsx、roles-RolesView.tsx、roles-logic.ts、useLivePreview.ts、page-app.test.tsx、page-hub.test.tsx、tests/test_gate_t024_baseline.py）+ 可新增 4 个（HubBindForm.tsx、hub-bind-form.css、roles-hub-candidates.test.ts、writes-hub-bind.test.tsx）。forbidden 一个没碰（api.ts、useWriteFlow.ts、WriteConfirmDialog.tsx、hubChangeLines.ts、mock/**、roles-styles.css、ts/packages/ui/**、scripts/**、其余 tests/test_gate_*.py、package.json 与锁文件）。

## DoD → 测试 → 断言
- **D01**（纯函数）｜roles-hub-candidates.test.ts：hubFallbackCandidates 五条 it（主选 quizs → 候选 [p1,p2,x1] 且不含 quizs、不出允许名单；非 quizs → 空；查不到 → 空；adapter 非字符串 → 空；名单空或去掉 quizs 后空 → 空）+ allowedProfiles / hubPostName 既有行为各一条｜证据 V01（1200 passed）、V02、R01。
- **D02**（预览两字段）｜候选 diff 只加两字段与两处取值（fromReply 取 data?.hub_changes ?? [] / data?.running_turns ?? []，失败分支补两个空数组；@@ -1,7 只动 import 行，开头两行注释与 DEBOUNCE_MS 未动）+ T040 预览探针（tests/test_gate_t040_baseline.py，R01 绿）+ 战后门禁 W02 与变异 M04/M05/M06｜证据 V01、R01。
- **D03**（候选与预填）｜writes-hub-bind.test.tsx「contract 行：主选候选只有允许名单里的 profile；…」：主选 option toEqual [quizs-m9,step-high,step-low]；main.value toBe quizs-m9（quizs-m3 不在候选 → 落第一个候选）；替补 option toEqual ['','step-high','step-low']、value 'step-high'；换成 step-high 后 fb.disabled true、fb.value ''｜证据 V01、G01（t045 探针 :1108–1120）。
- **D04**（底部预览与门控）｜writes-hub-bind.test.tsx「底部：命令…+前后对比四行…」：toContain('config hub set contract quizs-m9 --fallback=step-high')、对 hubChangeLines(change) 的四行逐行 toContain、warnings 与 running_turns 原文；「预览失败…」：toContain 报错原文且 确认… disabled true；「改绑定：确认发 POST…」：岗位写路由只发一次｜证据 V01、G01。
- **D05**（操作列）｜page-hub.test.tsx 新 it：每行两个入口、textContent 恰为两串、planner 改绑定…禁用、四个缺省行恢复缺省…禁用、contract/exec 可点；writes-hub-bind.test.tsx 桩下 describe：整页 button[disabled] 共 11、七端岗位组内禁用的改绑定… 1、恢复缺省… 4｜证据 V01、G01、R01。
- **D06**（既有写流程）｜writes-hub-bind.test.tsx：改绑定 → POST /api/v1/hub/roles/contract，body.profile=quizs-m9、body.fallback=step-high、body.confirmation 是字符串、只发一次；恢复缺省…（exec 配置行）→ POST /api/v1/hub/roles/exec/unset，body 键 toEqual ['confirmation']；两例都断言成功后 /api/v1/roles 读数增加（reload）｜证据 V01、G01。
- **D07**（两处包内测试）｜page-hub.test.tsx：列头 toEqual 七列且末位是「操作」、it 标题跟着改；page-app.test.tsx：角色页 toBe(11)、it 标题跟着改、运行时页 5 与总览 0 照旧；两个 describe 标题（七端岗位（桩模式渲染 #/roles）、写入口个数（过渡））逐字未动（按 diff 与现文件核对）｜证据 V01、R01。
- **D08**（两个新测试文件）｜roles-hub-candidates.test.ts 与 writes-hub-bind.test.tsx 都在；desktop/web/tests 全目录 grep 无 .skip/.only/.todo；前后对比用真的 hubChangeLines 导入而非抄一份；纯函数用例直接打 roles-logic 的真导出｜证据 V01。
- **D09**（范围）｜11 个文件 = 授权集合；forbidden 清单一个没动；package.json 与锁文件未动｜证据 scope + 我按 diff 逐 hunk 核对。
- **D10**（源码规矩）｜HubBindForm.tsx 只 import type { HubChange, WriteArgs } from '../api'；grep 无 console/debugger/role=/style=/dangerouslySetInnerHTML/fetch；hub-bind-form.css 只用 --tt-* 令牌、不声明令牌、类名全 hb- 前缀、px 只 0/1px；roles-* 无网络词｜证据 V02/V03、token-contract 通过、R01（t007/t009/t038）。
- **D11**（T038 静态形状）｜roles-HubPosts.tsx 保住 title=「七端岗位」、aria-label=「七端岗位」、rowHeight={40}、rl-hub、hubPostName、rowAttrs 给的 data-post、不出现 data-role、前六列头不变；roles-logic.ts 三个既有导出未动且只 import type｜证据 R01 里 t038 全绿。
- **D12**（t024 放宽）｜tests/test_gate_t024_baseline.py 只改三处：:1088 的 it 标题、:1106 的 expect(disabledCount, '角色页禁用按钮 9→6→11（T045 新增 5 个禁用入口；page-app 的口径）').toBe(11);、:1609 的 docstring——逐字与合同 Steps 第 8 步一致，其余一字未动｜证据 R01 1030 passed。

## 行为核对（合同字面逐条对上）
主选候选 allowedProfiles；替补候选 hubFallbackCandidates（主选非 quizs → 空数组）；预填（配置行且现有主选在候选里 → 填它，否则第一个候选；替补同理）；切换主选为非 quizs → 替补清空并禁用；args = {post, profile}，替补非空才带 fallback；底部顺序（命令 → 本岗位四行 → warnings → running_turns → 出错只显示错误行）；[确认…] 门控三条件（主选非空 + 预览对应当前取值 + 预览 ok）；点它先 onClose() 再 start({action:'hub.set', args})；恢复缺省… → start({action:'hub.unset', args:{post}})；成功之后 reload（RolesPage → RolesView → HubPosts → useWriteFlow(reload)，reload 一次重读 roles/profiles/presets/hub 四个）；原因句只在 src/writes/HubBindForm.tsx；按钮 textContent 恰为两串、按钮里没有岗位名；读失败分支零按钮、<WriteFlow flow={flow} /> 只在读成功分支；前后对比复用 A 片的 hubChangeLines（运行时 import，无第二份）。

桩下禁用数 11 我独立重算过：mock/profiles.json 两条 profile 的 adapter 都是 pi；mock/hub-roles.ts 里 coordinator(quizs+pi)、contract(pi+quizs)、gate(pi)、audit(pi+quizs)、exec(pi) 有候选，planner 只许 claude-code 无候选 → 改绑定…禁用 1；coordinator/planner/gate/audit 是缺省行 → 恢复缺省…禁用 4；6 + 1 + 4 = 11，与合同 H7 和门禁口径一致。

## 检查与门禁记录
- attempt-002 checks/04（独立工作区 …-a002-verify-zidbwvzi，candidate_tree=23d04a46）：G01 14 passed in 30.03s（退出码 0，匹配 \d+ passed）、V01 126 文件 1200 tests passed in 18.7s、V02 typecheck 退出码 0、V03 build 退出码 0、R01 全量 45 个门禁文件 1030 passed in 1722.43s（28:42，退出码 0）；covers_all_required 与 all_required_passed 均 true，candidate_files_modified 与 unexpected_files_by_checks 均空。
- 战后门禁（6-gate-post）：白盒 9 passed（tests/test_gate_t045_whitebox.py；9 条虽是静态断言，但含五层接入链 css ← HubBindForm ← roles-HubPosts ← roles-RolesView ← RolesPage，不是空心断言）；31 条变异逐条实际应用、跑白盒、逐字节回滚，31/31 CAUGHT（证据 mutations.json 与 M01…M31.log 在案），0 条声明等价，候选缺陷为空，锚点 31/31。
- 门禁端没在候选上重跑 Vitest（工作区无 node_modules、npm ci 被禁），运行时行为由执行端 V01/V02/V03/R01 与 G01 探针背书，门禁机上可复跑。这不构成本片的阻塞。
- G01 用的门禁文件热修补（tests/test_gate_t045_baseline.py:1261）我核过：把与 :1282 互相矛盾的命令期望改成同一串（config hub set contract quizs-m9 --fallback=step-high），是修正门禁自身矛盾，不是为实现放宽断言。
- 执行自述与内核摘要对得上：内核标的 4 处「歧义/矛盾」提法全在讲上一轮 G01 阻塞（门禁探针自身矛盾），不是本轮新选的解释；4 条 `|| true` 都在 ls/grep 一类查看命令上、不是检查命令。执行报告 interpretations/contract_conflicts/unresolved_questions 为空是合理的——enabled 的解读已如实记在 attempt-001 的执行报告里（quote/adopted/reason 齐全），本轮零改动不必重记。DoD 自述逐条与源码/日志相符（唯一措辞不准的是 D12 的「单 hunk」，见下）。
- JEV：no_opinion auth_failed，没有意见要采信。

## 发现（都不挡，写进 report，不进阻塞项）
1. useLivePreview 的 enabled 取 open && main !== ''，与合同字面「enabled 是主选非空」不同。执行端在 attempt-001 的 interpretations 里如实记录了（理由：对话框常驻挂载，只按主选非空会在页面加载时为 5 个关着的表单各发一次预览），战前门禁与战后门禁各评估一次，判为与可见行为不冲突。我核过：唯一可见差别是打开对话框时先显示「预览中…」（≥300ms）而不是可能已有缓存的预览；门控、底部内容、用例都不受影响。若站主要求逐字照合同，改成 main !== '' 是一行，代价是页面加载时多 5 次预览请求。
2. 每个有候选的行常驻挂载一个 HubBindDialog（各自的 useWriteFlow + WriteFlow + Toast），角色页上共 6 套写流程状态机常驻。功能无碍（Dialog open=false 返回 null、不进 DOM；预览不外发），只是常驻开销，属下一片可考虑收敛的点。
3. 执行报告 D12 自述「单 hunk」不准：git diff 实际是 3 个 hunk（三处相隔约 500 行，git 必然拆开）。实质（只改合同授权的三处、其余一字未动）我逐字核过为真。
4. 内核摘要提到运行期间主工作区 AGENT_LEARNINGS.md 变化：候选 11 个文件里没有它、attempt-002 零改动、快照里的 AGENT_LEARNINGS.md 也没有本片内容 → 不可归因于本片候选，请内核确认是别的进程写的。
5. 战后门禁的白盒文件 tests/test_gate_t045_whitebox.py 是新增未跟踪文件（门禁端交付物，不在候选里）。按门禁岗位说明它要留在仓库里当回归测试——请内核确认随本片入库，否则这层静态覆盖会丢。

## 复审封板
若后续有返工，只复核上面 5 条涉及的地方与新改动；本轮无阻塞项。

Verdict: PASS
