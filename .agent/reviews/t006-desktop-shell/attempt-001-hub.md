# 复审记录：t006-desktop-shell attempt-001（七端信箱 hub）

- 合同：t006-desktop-shell.v1（base 8fff68d511a94a2a86dc00cc6f430461241229ee）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 1；变异检查退出码 None
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T006-7-audit-post 终审报告（audit-sonnet）

- 主任务：T006 桌面端前端应用框架与夹具数据层（第六片）
- 候选：attempt-001，候选树 1085f62c9a708fcda35950caa9cca32fe6b0c540，补丁往返校验通过，68 个文件（A62 M6）
- 结论：返工；退回：执行端（exec-step，attempt-002）
- 阻塞项：1 条（B1，见第 2 节）
- 我怎么查的：审核端只读，没有执行工具，我没有重跑任何测试。测试结果取自内核的 check 记录与门禁日志；源码、差异、夹具、文档是我逐文件读的，并对 src 与补丁做了 grep。

## 1. 裁定一览

- RolesPage 传 isEmpty（WB53）：成立，列为阻塞项 B1，退回执行端。
- WB53 本身：断言没有误读合同，不退回战后门禁。
- 变异检查：补做，放在 attempt-002 的候选上做（第 4 节）。
- 执行端的解读（任务书列 6 条，执行报告列 7 条）：全部与合同不冲突，没有阻塞项（第 5 节）。
- JEV 四条：自行解读合同——部分采纳（遗漏的读法只有 RolesPage 一处，即 B1）；自述完成而无证据——不作阻塞项（D10 除外，同为 B1）；误导程度——部分采纳（同为 B1）；弱化测试——不采纳（第 6 节）。
- 范围与禁区：通过（第 7 节）。
- 既有 3 份测试：通过，只改挂载（第 8 节）。
- D01–D14：除 D10 因 B1 不成立外，都有证据（第 10 节）。

## 2. 阻塞项（一次列全，只有这一条）

B1 角色页不应传 isEmpty（退回：执行端）
- 文件与行：desktop/web/src/pages/RolesPage.tsx:5（定义 isRolesEmpty）、:13（isEmpty={isRolesEmpty}）。
- 依据：合同第 9 条（.agent/plans/t006-desktop-shell.v1.md:218）「没写空态的页不传 isEmpty」。该段只给总览与任务、CLI 运行时、凭据、插件、历史与审计写了空态，角色与模型只写了说明。门禁 WB53 可复现：python -m pytest tests/test_gate_t006_whitebox.py -q -k WB53，探针 pages.test.tsx:204 报 expected 'empty' to be 'data'。
- 怎么改：删掉 RolesPage.tsx 的 isRolesEmpty 与 isEmpty 传参即可；不要给角色页补 empty 文案；RolesData 类型导入仍被 PageFrame<RolesData> 用到，保留；其余文件一律不动。
- 改完应当：getRoles 返回空的 roles 列表时，data-page-state 为 data，正文含「夹具数据已读到」。
- 建议，不是阻塞：在 desktop/web/tests/shell-*.test.tsx 里加一条用例钉住这一点。白盒不并入仓库，基准里也没有这条，合入后没有任何测试守着它。执行端若加了，下一轮我当作新改动来看。

## 3. 核心裁定：为什么 RolesPage 传 isEmpty 算缺陷

1. 合同写的是一条明文禁令，角色页在禁令之内。第 9 条逐页列了加载函数、说明与空态：总览与任务、CLI 运行时、凭据、插件、历史与审计写了空态；角色与模型、日志与用量、设置没写；末句「没写空态的页不传 isEmpty」把没写的页点成了禁止项。候选对日志与用量、设置都照办，只有角色页例外。
2. 这不是合同的灰区。AGENTS.md 让执行端自行取舍的是「合同没写死」的地方，并要写进 interpretations；这里合同写死了，执行报告的 7 条解读里也没有这一条，说明执行端没有把它当成一次取舍，只是多写了。
3. 设计文档也没有角色列表的空态。UI 设计文档 6.4（:552–623）写的是四张固定的角色卡、profile 表与方案表；整页唯一的空状态「还没有方案…」（:587）属于方案列表（getPresets），不属于本页加载的 getRoles。角色是内核固定的四个，空列表现实里也不会出现。所以「角色页有空态」既没有合同依据，也没有设计依据。
4. 实现自己不自洽，这是比「字面」更实质的理由。RolesPage 只传了 isEmpty，没传 empty（其余 5 个传 isEmpty 的页都成对传了 empty）。PageFrame.tsx:136–139：phase 为 empty 而 empty 未给时，落到 children(data)。于是角色列表为空时，根元素 data-page-state 是 empty，正文却是「夹具数据已读到：getRoles，0 条。」。data-page-state 是合同第 8 条定下的对外状态，测试和后面的片都读它；这个占位页又是后面真实角色页的起点。
5. 对反方的回应。「夹具产生不了空角色列表」属实：roles.json 有 4 个角色，?mock=empty 也不碰 getRoles，所以缺陷是潜在的，界面上现在看不到。我判成立不靠「会不会被看见」，靠第 1–4 点：明文禁令被违反且未声明、半成品状态可复现、修复只删两行。反过来判不算缺陷，要门禁重写断言、再占一次门禁次数，结果是把「状态说空、屏上说有数据」的代码留在主线，代价更高。「执行端可能认为角色页有空态是合理读法」：这个读法和第 9 条的明文冲突，不算合理读法。
6. WB53 没有误读合同。它让 getRoles 返回 {active_preset:'default', roles:[]}，断言 data-page-state 为 data 且正文含「夹具数据已读到」，正是「不传 isEmpty」应有的行为。同组 WB52 用同样办法验证 5 个写了空态的页（含任务页）都进空态，门禁对「哪些页该有空态」的读法与合同一致。
7. 任务页的空态不是问题：合同把总览与任务并在一条里（总览、任务→getStatus，空态…），执行端与门禁都按两页共用来读，这是执行报告第 6 条解读，我认可。

## 4. 变异检查：补做，放在 attempt-002 的候选上

- 时点与对象：由 attempt-002 对应的 6-gate-post 那一轮，在返工后的候选上做并交 mutation_spec；不在 attempt-001 这份红候选上做。
- 理由一：变异检查证明的是「测试能发现实现被改坏」，要对最终会进入主线的那份代码做才有意义。attempt-001 会被 attempt-002 取代（至少 RolesPage.tsx 会变），在它上面做的结果不能直接当终审证据。
- 理由二：到目前为止这份候选一次变异也没做（门禁因红候选没给 mutation_spec）。PASS 之前必须有，否则「全绿」只证明测试通过，没证明测试有用。
- 理由三：成本低。返工只动一个文件，8 份探针与 7 条静态检查可原样复用；与白盒复跑在同一轮，不另占门禁次数（6-gate-post 已用 1 次，上限 3）。
- 必含一条：把 RolesPage 的 isEmpty 加回去，WB53 必须变红。这是 B1 的回归保护。
- 建议覆盖（门禁自行取舍，我下一轮逐条判断「等价」声明与「不能变异」的文件）：PageFrame 的最近一次请求守卫与卸载守卫、empty 分支、data-stale 与「可能已过期」标签；attemptGroups 的 17 个状态；TabBar 的 count>0 与 aria-label、tt-hide-narrow 与 aria-live 取值、陈列页不渲染「上次更新」；shortcuts 的各修饰键与模态判断；ShellMenu 的禁用项守卫、Esc 的 stopPropagation、Tab 关闭、菜单外按下鼠标；router 的保留查询与「相同地址不重复写 hash」；api 的 read 中 loading/error 先于参数校验、empty 只对 5 个资源、clone 深拷贝；ShowcasePage 的 sort 与 display:contents。
- 我预先看到的死代码（变异它们测不出来是正常的，门禁可直接声明等价）：PageFrame.tsx:108 的 hasData（未使用）、router.ts:18 与 :70 的 mockOfQuery（仓库内没有使用者，只有白盒 WB02 引用）。

## 5. 执行端解读逐条核对

任务书列 6 条，执行报告 interpretations 实际 7 条（多出的一条是「任务页与总览共用空态」，任务书漏列，不影响结论）。全部与合同不冲突。

1. 总览说明（OverviewPage 调一次 getMeta，并用同步的 getMetaNow 打底）：合同要的是「仓库名 · kit 版本」（来自 getMeta），PageFrame 的 description 是同步属性。执行端同时做了首屏同步与异步 getMeta 一次；白盒 WB50 断言「首屏就有」与「getMeta 恰好调用一次」，通过。副作用：api.ts 多导出第 14 个 getMetaNow；基准 test_transitional_d06_api_only_thirteen_functions 只查 13 个都在、后面的片才补的函数不得提前出现，没禁这种辅助导出。不冲突。
2. 未知路径渲染总览内容并高亮总览 Tab、不改写地址：合同第 1 条写「未知路径都显示总览，不改写地址」，没写 Tab 高亮；只规定陈列页没有当前项。显示的内容就是总览，高亮与内容一致更合理；白盒 WB30、WB60 采用同一读法。不冲突。
3. PageFrame 不含 offline 属性，由框架按 ?mock= 与 shell.ts 推导：合同第 8 条的属性清单确实没有 offline，第 2、7 条规定连接状态来自夹具开关，自行推导是不改属性清单的唯一做法；白盒 test_wb_page_frame_props_are_the_contract_set 通过。不冲突。
4. [重新连接] 放进 danger Banner 内：合同写「danger Banner（role=alert），文字…，后面接一个 DisabledAction [重新连接]」，Banner 没有放操作钮的位置（合同 Repository facts 已写明），所以只能作为 children 放在文字之后。不冲突。
5. 换路由滚回顶部（外壳 height:100vh，main 为滚动容器，按路由 key 重挂载）：合同要求「给内容区按路由加 key」。key 在 main 上而 main 自己就是滚动容器，key 变整个容器重建、scrollTop 归 0；若内容区不自持滚动，加 key 不会复位。白盒 test_wb_app_layout_css_makes_content_the_scroll_container 通过。routeKey 含 query，所以改 ?mock= 也会重挂载并重新取数，对五态演示是需要的。不冲突。
6. 页面计数写法（status、roles、runtimes、secrets、plugins、history 写条数；usage、meta 只写函数名）：合同写「列表数据写条数」。usage 是 {executor, planner}、meta 是 {kit_version, repo_name}，都不是列表；其余六页的主数据是数组。白盒 WB51 一致。不冲突。
7. 任务页与总览共用 getStatus 空态：见第 3 节第 7 点。不冲突。

另有两处小选择执行报告没列，我判断都不构成阻塞：PageFrame 的 empty 属性写成可选（合同签名没带问号，但日志与用量、设置、角色三页没有空态可传，可选是唯一自洽的写法）；导航保留当前整串查询而不只是 mock（合同「查询里只认 mock」，白盒与基准都只用 ?mock= 测）。

## 6. JEV 四条判断的采纳情况（JEV 只作参考）

- 自行解读合同（p=0.95）：部分采纳。7 条解读都在执行报告里；遗漏的读法只有 RolesPage 的 isEmpty，已列为 B1。另有合同 :190 笔误与上面两处小选择，没列但不构成阻塞。
- 自述完成而无证据（p=0.90）：不作为阻塞项。执行报告的证据栏写得笼统（「V01 通过」），但 D01–D12 由基准 49 条（内核 fresh check 退出码 0）与白盒证明，D13 由 V02/V03/V01 的 check 记录证明，D12、D14 要求的 review 与 scope 由我和 scope.json 补齐（第 7、8、10 节）。唯一例外是 D10，已并入 B1。
- 误导程度（2.40/3）：部分采纳。能改变裁定、而独立基准没发现的声明只有一处：D10「9 页各自……空态」done，与合同第 9 条冲突，是白盒才发现的。其余声明（范围、网络词、T007 禁用词、既有测试只改挂载）我都独立核对过，属实。执行报告写「无合同内部矛盾」略显绝对（:190 笔误），无影响。
- 弱化测试（p=0.68）：不采纳。三份既有测试的差异里，被删的行只有 font-specimen 的 import 行（里面有 expect 一词，换成加了 beforeEach 的同一行）与两份测试里的 beforeEach 行；断言一条没动。summary 里「删除了 1 行含断言的代码」就是那行 import 的误报。新测试没有 skip、only、todo。

## 7. 范围与禁区

- candidate.patch 共 68 个文件（A62 M6），全在 desktop/web/ 下；scope.json 的 violations 为空；我把文件清单逐项对过 allowed_modified_files 与 allowed_new_files（shell 目录下的 ts、tsx、css；mock 下 14 份 json 与 scenario、empty、shell；pages 下 9 个 *Page.tsx；showcase 下 5 个文件；11 个 shell-*.test.ts(x)；README、App.tsx、App.css、api.ts、icons/frame.tsx；3 份既有测试）。
- 补丁里没有 src/components/**、src/icons/index.tsx、src/styles/**、src/main.tsx、src/domain/**、src/vite-env.d.ts、package.json、锁文件、index.html、vite.config.ts、tsconfig.json、scripts/**、public/**、fonts/**、THIRD_PARTY_NOTICES.md、FormsShowcase.tsx、showcase-forms.css，也没有其余既有测试与 tests/test_gate_*.py。
- T007：没有 EvidenceShowcase.tsx、showcase-evidence.css。README 里有一句文字提到 EvidenceShowcase「留给后续片」，只是名字，不是文件，README 是本片的文件，不冲突。
- T008：DiffShowcase、showcase-diff、diff- 前缀、log-follow、text-viewer-slots、t008 在补丁全文无命中。
- 禁用词：src 下 fetch、XMLHttpRequest、EventSource、WebSocket 无命中；dangerouslySetInnerHTML、innerHTML、outerHTML、insertAdjacentHTML、eval(、new Function、document.write、srcdoc、createContextualFragment、DOMParser 无命中；matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver 无命中。
- 新代码里 role=status 一个没有（整页只留 Toast 的那一个）；没有内联 style；没有 ts-ignore、eslint-disable、as any、空 catch；没有 skip、only、todo。
- 依赖：package.json 与锁文件不在补丁里，没有新增依赖。

## 8. 既有 3 份测试（Q2）

- font-specimen.test.tsx：import 行加 beforeEach；加一行注释与 beforeEach(() => { location.hash = '#/showcase'; });。
- showcase-forms.test.tsx 与 showcase-overlays.test.tsx：各改 1 行，成为 beforeEach(() => { location.hash = '#/showcase'; vi.useFakeTimers(); });。
- 用例、标题清单、expect 条数不变；基准 test_d14_existing_tests_only_mount_changed（标题清单与 expect 条数取自 e4be51f）通过。结论：只改了挂载，通过。

## 9. 门禁记录

- 内核 check（fresh，2026-10-20T13:55:05Z–13:58:20Z，候选树与检查前后一致，未被检查改动）：V01 49 passed；V02 222 passed；V03 7 passed；三条退出码均为 0，all_required_passed 为真。
- 白盒（35 个用例：8 份探针分组加 7 条静态检查与清理检查）：门禁两次整跑结果一致，34 passed、1 failed。失败信息带探针文件名与行号（pages.test.tsx:204），说明探针确实被 Vitest 收集并实跑，不是空心；没有收集或语法错误。
- 白盒里没有 xfail、skip；白盒文件未提交、不并入仓库（任务书已说明）。
- 门禁没给 mutation_spec，变异检查一次未做（第 4 节）。

## 10. DoD 证据核对（D01–D14）

- D01 路由：V01 的 test_d01_probe_routes_and_tabs、test_d01_files_in_place；白盒 WB01、WB03、WB60；我读了 router.ts、routes.ts、App.tsx（未知路径回总览不改写地址、其余段原样保留、title 随页面变）。成立。
- D02 标题栏：V01 的 test_d02_probe_titlebar_and_menus、test_d02_probe_logo_and_icons、test_d02_logo_and_frame_icons_static、test_s4_titlebar_css、test_s4_shell_menu_css；白盒 WB40–WB43；我读了 TitleBar、ShellMenu、Logo 与两份 CSS。成立。
- D03 Tab 栏：V01 的 test_d03_probe_tabbar、test_d03_probe_status_groups、test_s4_tabbar_css、test_s5_base_css_keeps_hide_narrow；白盒 WB30、WB31（17 个状态分组）、WB61；我把 attemptGroups.ts 与 UI 文档 3.4 :169–177 逐项对过。成立。
- D04 快捷键：test_d04_probe_shortcuts；白盒 WB04、WB05、WB62；shortcuts.ts 逐条件对过合同第 5 条。成立。
- D05 主题：test_d05_probe_theme、test_d06_theme_single_writer（名字带 d06，内容是 D05）；白盒 WB06、WB62。成立。
- D06 数据层：test_transitional_d06_probe_api_fixtures、test_s2_fixtures_equal_ui_doc、test_transitional_d06_api_only_thirteen_functions；白盒 WB10、WB11、WB12；我把 13 个函数的 command 与桌面端架构文档 5.2（:721–735）逐条对过。成立。
- D07 夹具开关：test_transitional_d07_probe_mock_switch；白盒 WB12、WB61。成立。
- D08 不连服务：test_d08_no_network_words_in_src、test_d08_probe_no_network、执行端的 shell-no-network.test.ts；我对 src 全文 grep，0 命中。成立。
- D09 页面框架：test_d09_probe_page_frame；白盒 WB20–WB23。成立。
- D10 页面占位：test_transitional_d10_probe_page_placeholders、test_transitional_p10_probe_five_states；白盒 WB50–WB52 通过，WB53 失败。不成立（B1）。
- D11 禁用入口：test_d11_probe_disabled_action；白盒 WB22、WB70。成立。
- D12 陈列页：test_d12_probe_showcase_collection、test_transitional_p11_probe_showcase_content、test_s6_showcase_page_collects_by_glob、test_transitional_d12_*、test_d14_existing_tests_only_mount_changed；白盒 WB70；DoD 还要 review，我把 BaseShowcase.tsx 与旧 App.tsx 的演示逐节对过：文字、顺序、已有 data-* 不变，只给五节原子加了 data-demo（button、tag、status-tag、card、banner）；3 份既有测试只改挂载。成立。
- D13 回归：V02 222 passed、V03 7 passed、V01 49 passed（内核 fresh check）；npm ci、build、test、check:contract 由基准 test_d13_pipeline_steps_pass 与白盒 test_wb_check_contract_passes 在门禁流水线里跑，通过。成立。
- D14 范围与纪律：scope.json violations 为空；test_d14_* 四条；我的 grep 与差异核对（第 7、8 节）。成立。

## 11. 复审封板：下一轮我只看什么

下一轮（收到返工完成信后）我只复核：
1. RolesPage.tsx 的改动，以及 WB53 是否转绿、白盒整体是否变成 35 passed；
2. attempt-002 相对返工提交的全部新改动（应当只有 RolesPage.tsx，多出别的文件要有理由；若加了回归测试，我按新改动看）；
3. 门禁的 mutation_spec 与结果：等价声明、不能变异的改动文件逐条判断；变异清单或白盒不够的，退回战后门禁。
第 5–10 节已确认的内容不再重看；我不会再提新的阻塞项，除非来自新改动或变异结果暴露的测试缺口。

## 12. 风险与建议（都不进阻塞项）

- R1 合同 :190 笔误：「为 0 或未读到时渲染」应为「不渲染」，与 D03 和 UI 文档 5.3 :369（数量为 0 时不显示）相反。执行端按 D03 实现，是对的。建议下次出合同新版本时改掉，不需要为此重派遣。
- R2 router.ts 的 navigate 在 setRoute 的更新函数里写 location.hash（副作用在更新函数内）。目前靠「地址相同就不写」保持幂等，StrictMode 下白盒 WB03 通过；但更新函数有可能在渲染阶段执行，后面的片若在路由里加更多副作用要留意。
- R3 PageFrame 在 load 或 isEmpty 的引用变化时会重新加载（门禁已提醒）。本片 9 个页都用模块级常量，现在安全；后面的片若传内联函数会反复请求，建议后面的合同写明，或让 PageFrame 用 ref 保存最新的 load 与 isEmpty。
- R4 死代码：PageFrame.tsx:108 的 hasData 未使用（tsconfig 未开 noUnusedLocals，所以 build 不报）；router.ts 的 mockOfQuery 仓库内无使用者；route.segments 暂无页面消费（执行报告已写）。返工时顺手删 hasData 也可以，但不要求。
- R5 api.ts 多导出第 14 个 getMetaNow：基准允许；接本机服务那一片要一并处理。
- R6 过渡内容的小瑕疵：ShellShowcase 说明文字写「悬停或聚焦 400ms 后提示」，禁用按钮聚焦不到，只有悬停会出提示；EmptyState 没传图标（UI 文档 6.2 :488 有 list-checks，合同第 9 条没要求）。
- R7 没有任何真浏览器与视觉证据：H1–H10 待人工。main 现在既是滚动容器又是 .tt-content 容器查询元素，陈列页的对话框、抽屉、轻提示的定位与五态建议在 H5、H6、H9 里亲眼看一次。
- R8 README 提到 EvidenceShowcase 这个名字（仅文字），T007 落地后注意一并更新说明。

Verdict: REVISE
