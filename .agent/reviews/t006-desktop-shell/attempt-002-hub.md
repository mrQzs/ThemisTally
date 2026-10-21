# 复审记录：t006-desktop-shell attempt-002（七端信箱 hub）

- 合同：t006-desktop-shell.v2（base 50b823d744da48e3266fd3a6459057c8d8d943e0）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T006-7-audit-post 终审报告（audit-sonnet，attempt-002）

- 主任务：T006 桌面端前端应用框架与夹具数据层（第六片）
- 候选：attempt-002，候选树 83c6cb23dbb2d54702e5e91b2773fbacfbd3e917（补丁往返校验通过），基线 50b823d744（合同 v2）。只改 desktop/web/src/pages/RolesPage.tsx：删 3 行（isRolesEmpty 的定义、其后的空行、isEmpty 传参），加 0 行。
- 结论：通过。阻塞项：无。
- 我怎么查的：审核端只读，没有执行工具，没有重跑任何测试。测试结果取自内核的 check 记录、门禁日志与变异记录；源码、补丁、日志、规格我逐文件读过，并对 src 与 tests 做了 grep。读码推断、没有执行证据的地方，下面都标了「推断」。

## 1. 裁定一览

- 上一轮阻塞项 B1：已解决（第 2 节）。
- D01–D14：都有证据（第 3 节）。
- 执行端的解读：全部与合同 v2 不冲突，没有阻塞项（第 4 节）。
- 门禁三点提示：TasksPage 传 isEmpty，不阻塞；PageFrame 在 load 或 isEmpty 引用变化时重载，不阻塞，记为风险，M01 给出了实测的死循环；mutation_spec 只带 W1，不必给全部变异补带基准（第 5 节）。
- 变异记录：内核记 72 条全捉到。我核对日志后的实情是：70 条由白盒断言真捉到，M01 靠超时，M40 白盒没捉到（第 6 节）。两处都有独立证据补足，不阻塞。
- JEV 四条：自述无证据，不采纳为阻塞；误导程度，只采纳 D10 一处过度表述；弱化测试，不采纳；自行解读合同，不采纳（第 7 节）。
- 范围、禁区、既有 3 份测试、禁止项：通过（第 8 节）。

## 2. 上一轮阻塞项复核

B1（RolesPage.tsx:5 与 :13，退回执行端）：已解决。
- 补丁：删了 isRolesEmpty 的定义、其后的空行、isEmpty={isRolesEmpty} 三行，没有新增行。RolesData 的 type 导入仍被 PageFrame<RolesData> 使用（RolesPage.tsx:3、:7），保留。没有给角色页补 empty 文案。其余文件没动：changes.json 只有这一项，scope.json A0 M1、越界 0，head_after 仍是 50b823d744。
- 行为：PageFrame.tsx:71 是 emptyNow = isEmpty ? isEmpty(env.data) : false，不传 isEmpty 时恒为假，走 :76–80 的 data 分支，:139 渲染 children(data)。所以空的 roles 列表也是 data-page-state=data，正文是「夹具数据已读到：getRoles，0 条。」。
- 其他页：传 isEmpty 的恰是总览、任务、CLI 运行时、凭据、插件、历史与审计 6 页，且都成对传了 empty；角色与模型、日志与用量、设置不传。与合同第 9 条「没写空态的页不传 isEmpty」一致。
- 证据：WB53（白盒 :1529–1536，用模块替换让 getRoles 返回 roles: []）在 attempt-001 上两次整跑都红（expected 'empty' to be 'data'），在 attempt-002 上绿：门禁整跑 35 passed，变异基线 35 passed。归档的白盒文件与工作目录里的白盒，WB53 段行号一致。
- 注意：V01 分不出 B1 改前改后（第 7 节）。B1 的回归证据只有 WB53。

## 3. D01–D14 证据核对（以合同 v2 为准）

V01 的 49 项是 39 项实质用例加 10 项门禁自检。

| DoD | 证据命令 | 测试与断言 | 结论 |
|---|---|---|---|
| D01 路由 | V01 | 基准 test_d01_files_in_place、test_d01_probe_routes_and_tabs（空 hash 总览；9 个 Tab 的顺序、文字、title、分隔线；点击切页后地址、当前项、h1 同步；未知路由回总览；#/tasks/x/y 归任务；#/showcase 无当前项；document.title）；白盒 WB01、WB03、WB60 | 成立 |
| D02 标题栏 | V01 | test_d02_probe_titlebar_and_menus、test_d02_probe_logo_and_icons、test_d02_logo_and_frame_icons_static、test_s4_titlebar_css、test_s4_shell_menu_css、test_transitional_d02_mock_shell_values；WB40–WB43 | 成立 |
| D03 Tab 栏 | V01 | test_d03_probe_tabbar、test_d03_probe_status_groups、test_s4_tabbar_css、test_s5_base_css_keeps_hide_narrow；WB30、WB31、WB61 | 成立 |
| D04 快捷键 | V01 | test_d04_probe_shortcuts；WB04、WB05、WB62 | 成立 |
| D05 主题 | V01 | test_d05_probe_theme、test_d06_theme_single_writer（名字带 d06，内容是主题单一写入点）；WB06、WB62 | 成立 |
| D06 数据层 | V01 | test_transitional_d06_api_only_thirteen_functions、test_s2_fixtures_equal_ui_doc、test_transitional_d06_probe_api_fixtures；WB10–WB12 | 成立 |
| D07 夹具开关 | V01 | test_transitional_d07_probe_mock_switch；WB02、WB12、WB61 | 成立 |
| D08 不连服务 | V01 | test_d08_no_network_words_in_src、test_d08_probe_no_network；执行端 shell-no-network.test.ts；我对 src 做整词 grep，四个词 0 命中 | 成立 |
| D09 页面框架 | V01 | test_d09_probe_page_frame（含 :1873、:1884 的先发后回）；WB20–WB23；执行端 shell-page-frame.test.tsx:105–117 | 成立 |
| D10 页面占位 | V01 | test_transitional_d10_probe_page_placeholders（D10 一组在 :2032–2085；:2079–2083 断言角色、日志与用量、设置在 ?mock=empty 下是 data）、test_transitional_p10_probe_five_states；WB50–WB53，WB53 现在绿 | 成立；V01 分不出 B1 改前改后，B1 的证据是 WB53 |
| D11 禁用入口 | V01 | test_d11_probe_disabled_action；WB22（399/400ms）、WB70 | 成立 |
| D12 陈列页 | V01、review | test_d12_probe_showcase_collection、test_transitional_p11_probe_showcase_content、test_s6_showcase_page_collects_by_glob、test_transitional_d12_showcase_css_moved、test_transitional_d12_base_and_shell_showcase_sources、test_d14_existing_tests_only_mount_changed；WB70；review 部分上一轮已逐节对过 BaseShowcase 与旧 App.tsx，本轮这些文件没动 | 成立 |
| D13 回归 | V02、V03、V01 | 内核 fresh check（2026-10-20T14:34:05Z–14:37:01Z，候选树前后一致）：V01 49 passed（44.12s）、V02 222 passed（128.19s）、V03 7 passed（0.20s），退出码均为 0，无 failed/error；test_d13_pipeline_steps_pass（npm ci、build、test、check:contract）、test_d13_worktree_unchanged_by_pipeline；白盒 test_wb_check_contract_passes | 成立 |
| D14 范围与纪律 | scope、review | scope.json A0 M1、越界 0；test_d14_forbidden_sink_words_in_src、test_d14_new_sources_guards、test_d14_existing_tests_only_mount_changed、test_d14_new_tests_not_skipped；白盒 test_wb_forbidden_words_and_names_absent、test_wb_candidate_tests_have_no_skip_only_todo；我的 grep（第 8 节） | 成立 |

## 4. 执行端解读逐条核对（以合同 v2 为准）

v2 与 v1 的第 9 条同在 :218，文字一致；内核的 Rework 说明也写明 Scope、Behavior contract 与 DoD 不变。v1、v2 全文都搜不到「解读」「getMetaNow」，所以这些解读没有被 v2 吸收，也不需要被吸收：它们与 v2 正文不冲突。attempt-002 报告里 interpretations 写「无」是准确的：本轮唯一的改动是 B1 指定的删除，没有取舍空间；attempt-001 的解读留在基线代码里，上一轮已逐条判过。任务书列 6 条，attempt-001 的报告实际 7 条（多出的是任务页与总览共用空态）。我对照 v2 正文再核一遍：

1. 总览说明（OverviewPage.tsx:11–21，getMetaNow 同步打底，再调一次 getMeta）：v2 第 9 条「总览说明是仓库名 · kit 版本（来自 getMeta）」，第 8 条 description? 是同步属性。基准 D10 用例（:2054–2058）断言 getMeta 被调用、说明形如 demo-repo · kit 2.12.0。不冲突。
2. 未知路径渲染总览并高亮总览 Tab、不改写地址：v2 第 1 条「空、#、#/ 与未知路径都显示总览，不改写地址」，没有当前项只规定了 #/showcase。不冲突。
3. PageFrame 不含 offline 属性：v2 第 8 条属性清单没有 offline；断线来自第 2、7 条的夹具开关，PageFrame.tsx:46 自行推导。白盒 test_wb_page_frame_props_are_the_contract_set 通过。不冲突。
4. [重新连接] 放进 danger Banner 内：v2 第 8 条「danger Banner（role=alert），文字…，后面接一个 DisabledAction [重新连接]」；Banner 没有放操作钮的位置（Repository facts），PageFrame.tsx:160–165 作为 children 放在文字之后。不冲突。
5. 换路由滚回顶部：v2 第 1 条「给内容区按路由加 key」；App.tsx:82 的 main 按 routeKey 重挂载，外壳 height:100vh 且 main 为滚动容器（白盒 test_wb_app_layout_css_makes_content_the_scroll_container 通过）。不冲突。
6. 页面计数写法：v2 第 9 条「列表数据写条数」；usage、meta 不是列表，只写函数名。不冲突。
7. 任务页与总览共用空态：v2 第 9 条「总览、任务→getStatus，空态…」，基准的空态清单含 tasks（:2003–2010），见第 5 节 (a)。不冲突。

另有两处小选择，报告没列，不构成阻塞：PageFrame 的 empty 写成可选（角色、日志与用量、设置没有空态可传，合同签名没带问号）；导航保留整串查询而不只是 mock。

## 5. 门禁三点提示的裁定

(a) TasksPage 传 isEmpty：不阻塞，记为风险。合同第 9 条把「总览、任务」并成一项再写 getStatus 与空态，字面是两页共用；UI 文档 6.2 的空状态属于总览（:488），6.3 任务与 attempt（:492–551）没有空状态，所以文档层面任务页的空态没有出处。但基准（审核过、留在仓库里）已经把读法定死：空态清单 EMPTIES 含 tasks（:2003–2010），D10 的 ?mock=empty 用例要求任务页进入 empty 并带标题与说明（:2070–2078），去掉它 V01 就红。合同「过渡断言」一节也把页面占位的空态文案列为后面的片会推翻的内容。后面真做任务页的片要照 6.3 重新定空态。

(b) PageFrame 在 load 或 isEmpty 引用变化时重载：不阻塞，记为风险（R3，上一轮已记）。本片 9 个页都传模块级函数，安全。M01 给出了实测：RolesPage 上加内联箭头 isEmpty，白盒 60 秒没跑完被杀。推断的机理：PageFrame.tsx:62–106 的 request 以 isEmpty 为依赖、挂载 effect 以 request 为依赖；App.tsx:24、:70 把 setPage 当作上报函数，PageFrame 每次重跑 effect 都上报一个新对象；App 重渲染，RolesPage 重渲染，又得到一个新的内联函数，如此循环。后面的片如果写 load={() => api.xxx(...)} 就会撞上，建议把「load、isEmpty 须为稳定引用」写进后面的合同，或让 PageFrame 用 ref 保存最新的 load 与 isEmpty。

(c) mutation_spec 只带 W1，是否补带基准：不需要给全部变异补带。理由：① 白盒 70 条干净捉到，补带基准只会让「捉到」更多，推翻不了候选；② 候选已过基准 49 passed 与 V01–V03；③ 72 条全跑基准要 50 分钟以上，信息增量很小。M40 暴露的缺口用单条确认即可（见第 9 节 R12）。

## 6. 变异记录核对

1. 数量：规格文件与内核记录都是 72 条（M01–M72），任务书与门禁信写的 66 条是笔误。内核记 caught 72、missed 0、skipped 0、error 0。门禁没有声明等价的变异，也没有声明「不能变异」的文件。
2. 本次改动的文件 RolesPage.tsx 有 3 条（M01–M03）：M02（条数加 1）由 WB51 真捉到，M03（标题改字）由 WB60、WB62 真捉到，M01 见下。
3. 内核只用退出码判 caught，所以我逐份读了日志，找真实的断言失败。M02–M72 共 71 份日志，70 份含白盒断言失败（test_wb_probe_group 或静态检查失败）；抽读 M02、M03、M41、M72，失败的分组和变异内容对得上（WB51；WB60 与 WB62；WB20；WB52 与 WB60）。例外是 M01 与 M40。
4. 污染：M02–M72 的每份日志都另有一条 test_wb_probe_cleanup 失败。推断的原因：M01 被超时杀死，白盒夹具 pipeline 的 finally（白盒 :2002–2012）没来得及删它写进 desktop/web/gate-probe/ 的探针文件；之后每次 rmdir 都因目录非空失败，gate_probe_left 为真。印证：变异用的 worktree（就是本回合的工作目录）里 desktop/web/gate-probe/ 现在还留着 8 个 probe-t006wb-a04fd86f69-*.test.tsx（该目录被 .gitignore:17 忽略，不进补丁）；变异前的基线（baseline.log）35 passed，清理用例是绿的。结论：M02–M72 的退出码 1 与变异是否被捉到无关，不能当证据，要看日志里有没有真实的断言失败。
5. M01（加回 isEmpty，WB53）：记为 caught，实为超时（timed_out 为真，退出码 3221225786 即 0xC000013A，日志为空），机理见第 5 节 (b)。所以 M01 没有直接证明「WB53 变红」。我上一轮要的是 B1 的回归保护，这一点由真实缺陷的前后对照补足：attempt-001 的真实代码（模块级稳定函数 isRolesEmpty）上 WB53 红两次，attempt-002 上绿。不要求门禁重做 M01。
6. M40（PF7，PageFrame.tsx:64 的 += 1 改成不递增）：记为 caught，实为假阳性。M40.log 只有 1 条失败，就是 test_wb_probe_cleanup，27 个探针分组全绿，说明 W1 没捉到 PF7。原因是白盒 WB21 第三条（:845–864）「旧回应后到不覆盖新结果」是空心的：ds[0] 在刷新之前就已兑现为 A，最后的 ds[0].resolve(OLD) 对已兑现的 Promise 不起作用，PF7 改不改它都是绿。仓库里留下的测试能捉到 PF7（推断，未执行）：执行端 desktop/web/tests/shell-page-frame.test.tsx:105–117（挂载请求 defs[0] 未兑现，刷新请求 defs[1] 先兑现，再兑现 defs[0]；PF7 下 defs[0] 被接受，页面变成「值 1」，:116 的 toContain 值 2 失败）与基准 test_gate_t006_baseline.py:1873–1882（StrictMode 下先发的请求后回来）；两者都跑在 V01 的 pipeline 里（test_d13_pipeline_steps_pass 跑 npm test）。所以 PF7 并非没人守，空心的是白盒这份证据；白盒不并入仓库，对仓库没有影响。
7. 没有被变异的文件（不是本次改动，也没有被声明为不能变异）：ShowcasePage.tsx、DisabledAction.tsx、ShellStatusContext.tsx、Logo.tsx、icons/frame.tsx、BaseShowcase.tsx、ShellShowcase.tsx、mock/empty.ts、除 Roles、Overview、Tasks 外的 6 个页面、各 CSS、README。它们由基准探针与静态检查守着（test_d12_probe_showcase_collection、test_s6_showcase_page_collects_by_glob、test_d11_probe_disabled_action、test_transitional_d10_probe_page_placeholders、test_s4_*_css 等），没有变异证据。
8. 结论：变异证据有瑕疵，但不构成阻塞。70 条干净捉到；M01 由真实缺陷前后对照替代；M40 由仓库内的测试替代（读码推断）。候选本身没有缺陷，我不为证据质量再占一次战后门禁的次数。

## 7. JEV 四条判断的采纳情况（只作参考）

- 自述完成而无证据（p=0.94）：不采纳为阻塞。合同里 DoD 的证据栏就是 V01–V03、scope、review；执行报告的 self_checks 给了三条命令与结果（49、222、7 passed），与内核 fresh check 一致（49 passed in 44.12s、222 passed in 128.19s、7 passed in 0.20s，退出码 0）。形式上 D01–D09、D11、D12 的 note 只写「由 V01 覆盖」，确实笼统，实质上 V01 的用例我已逐条对到 DoD（第 3 节）。有两处说法不准，不影响候选：
  (a) D10：报告称 V01 的 D10 用例断言 #/roles?mock=empty 为 data，「基线改前为 empty，即 WB53 复现点」。不对：?mock=empty 只让 5 个资源变空，getRoles 不受影响（合同第 7 条；基准 :2079–2083 的循环还专门断言角色、日志与用量、设置在 ?mock=empty 下是 data），roles.json 有 4 个角色，改前这条用例也是 data；V01 在 attempt-001 候选上同样是 49 passed。WB53 是门禁用模块替换让 getRoles 返回 roles: [] 才复现的，两回事。
  (b) check:contract：报告写「退出码 0」，命令却是 npm run check:contract 2>&1 | tail -n 15; echo exit=$?，$? 取的是 tail 的（内核 summary 已标出掩盖退出码）。输出文字「契约检查：通过，无违规」是真的，内核 pipeline 里的真实退出码（test_d13_pipeline_steps_pass）也佐证。另外 npm test 的「34 files、196 tests」只是自述，内核没单独记数字。
- 误导程度（2.67/3）：不采纳这个量级，评「轻度」。没有隐藏冲突、范围违规或弱化测试：scope 越界 0；候选不动任何测试，断言行增减 0/0，skip 标记 0；shell 命令里 cd /d/ 一条是多余的切目录（随后 git -C 指向自己的 worktree），内核扫描 outside_worktree_paths 为空。只有上面 (a) 一处过度表述，以及报告写「合同内部矛盾：无」偏绝对：v2 的 :190 与 :282 对计数胶囊为 0 时的说法相反（上一轮已记 R1），执行端按 D03、UI 文档 5.3 :369 与基准的读法做，结果正确。
- 弱化测试（p=0.04）：同意不采纳，没有具体证据；本轮候选不动测试。
- 自行解读合同（p=0.10）：不采纳为问题：本轮没有取舍；之前的解读见第 4 节，与 v2 不冲突。

## 8. 范围、禁区、既有 3 份测试、禁止项

- 范围：候选只在 desktop/web/src/pages/ 下，RolesPage.tsx 在 v2 的 allowed_modified_files 内（desktop/web/src/pages/*Page.tsx）；forbidden_paths 一项没碰。attempt-001 的补丁（68 个文件）里也没有 src/components、src/icons/index.tsx、src/styles、src/main.tsx、src/domain、package*.json、index.html、vite.config.ts、tsconfig.json、scripts、public、fonts、THIRD_PARTY_NOTICES.md 的差异。
- T007、T008：src 下没有 EvidenceShowcase、showcase-evidence、DiffShowcase、showcase-diff、text-viewer-slots、log-follow、t007、t008 等名字。
- --tt-diff-add、--tt-diff-del：--tt-diff- 在 src 下共 5 处，全在 src/styles/tokens.css；attempt-001 的补丁没有 src/styles 的差异，所以是 T001 既有令牌，不是本片新增；W4 对应的 test_d14_new_sources_guards 与 pipeline 的 check:contract 都绿。确认。
- 禁止项：src 与 tests 下 skip、only、todo、xfail 0 处；src 下四个网络词（整词）0 处；十个注入类词（dangerouslySetInnerHTML、innerHTML、outerHTML、insertAdjacentHTML、eval(、new Function、document.write、srcdoc、createContextualFragment、DOMParser）0 处。基准 test_d14_forbidden_sink_words_in_src、test_d08_no_network_words_in_src 绿。
- 既有 3 份测试：font-specimen 只在 import 行加 beforeEach，并加一行 beforeEach 设 location.hash 为 #/showcase；showcase-forms 与 showcase-overlays 各改 1 行，变成 beforeEach(() => { location.hash = '#/showcase'; vi.useFakeTimers(); })。用例与断言一条没动；基准 test_d14_existing_tests_only_mount_changed（标题清单与 expect 条数取自 e4be51f）绿。本轮候选没碰这三份。
- 执行过程：Pi 退出码 0，用时 438 秒；事件流完整；工具错误 1 次（bash 超时参数不合法，无影响）；没有 git stash、checkout、reset；新增的被忽略路径只有 .pytest_cache、dist、node_modules；运行期间主仓库多了 t008 的规划文件，是规划端所为，不是执行端。

## 9. 风险与建议（都不进阻塞项）

延续上一轮：
- R1 合同 :190 笔误：「为 0 或未读到时渲染」应为「不渲染」，v2 里没改，与 :282 的 D03 相反。
- R2 router.ts 的 navigate 在 setRoute 的更新函数里写 location.hash；目前靠「地址相同就不写」保持幂等。
- R3 PageFrame 对 load、isEmpty 的引用敏感；M01 实测内联函数会死循环（第 5 节 (b)）。建议后面的合同写明，或让 PageFrame 用 ref。
- R4 死代码：PageFrame.tsx:108 的 hasData 未使用；router.ts 的 mockOfQuery 仓库内无使用者。
- R5 api.ts 多导出第 14 个 getMetaNow，接本机服务那一片要一并处理。
- R6 过渡内容的小瑕疵：ShellShowcase 说明写「悬停或聚焦」，禁用按钮聚焦不到；EmptyState 没传图标。
- R7 没有真浏览器与视觉证据，H1–H10 待人工；main 既是滚动容器又是 .tt-content 容器查询元素，浮层定位要在 H5、H6、H9 里亲眼看。
- R8 README 提到 EvidenceShowcase 这个名字（仅文字），T007 落地后一并更新。

本轮新增：
- R9 合入后没有仓库内测试守着「角色页不传 isEmpty」：白盒不并入；基准 D10 用 ?mock=empty，触不到空的角色列表；执行端的测试也没覆盖。真正的角色页换掉占位页后这条就不再有意义，优先级低。
- R10 任务页空态在 UI 文档 6.3 没有出处，靠合同并列写法和基准定下来；做真正的任务页时照文档重定。
- R11 变异工具的假阳性：超时（M01）与残留的探针目录（M02–M72 的清理用例）都会让退出码非零而被记成 caught。建议内核开跑前清空 desktop/web/gate-probe/、把超时记为未定；白盒若以后复用，WB21 第三条要改成真正的先发后回（旧请求保持未兑现，新请求兑现后再兑现旧请求）。
- R12 M40 的单条确认：对 PageFrame.tsx:64 做 PF7 变异后跑 npm test -- tests/shell-page-frame.test.tsx，应当红；可选，几秒钟。若它意外全绿，说明执行端那条测试也漏了，要回头再看。
- R13 任务书与门禁信写 66 条变异，实为 72 条，仅是计数笔误。
- R14 变异用的 worktree 里残留 8 个被忽略的探针文件，结项清理阶段 worktree 时一并删掉。

## 10. 没法做的事

我没有执行工具：没有重跑任何测试，也没有复现 M01 的死循环、M40 的覆盖与残留探针的因果；这三处都是读码加文件清单的推断，已在对应位置标明，它们不改变结论。

Verdict: PASS
