# 复审记录：t009-desktop-pages-a attempt-001（七端信箱 hub）

- 合同：t009-desktop-pages-a.v3（base c6c8cace12b513c4b9964e93dbb647a371fdf3e6）
- 内核 check --fresh：退出码 None；范围违规 None
- 战后门禁：白盒测试退出码 None；变异检查退出码 None
- JEV：一审前 answered；终审前 None
- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下

## 终审报告

# T009-7-audit-post 终审报告（attempt-001）

结论: 返工
退回: 执行端、门禁端、战后门禁

## 摘要
候选的 `overview-styles.css`、`roles-styles.css`、`runtimes-styles.css` 没有被任何模块 import，真实构建里总览、角色与模型、CLI 运行时三页没有页面样式。V01、V02、V03 和门禁白盒全绿，是因为所有 CSS 检查都按文本读文件，没有一条证明样式表被应用。其余核对（范围、T006 加法、写入口、门禁 5 条、执行端 5 条解读、JEV 三处疑点）没有发现阻塞项。

## 阻塞项（一次列全，每条标明归谁）

### B1【执行端】三份页面样式表没有接进应用
- 位置：`desktop/web/src/pages/readonly1/overview-styles.css`、`roles-styles.css`、`runtimes-styles.css`。在 `desktop/web`（不含 node_modules）里搜这三个文件名，只命中 `tests/page-css.test.ts:9`（按文本读）。`src/pages/readonly1/` 下唯一的样式表引入是 `common-Section.tsx:3` 的 `./common-section.css`；`main.tsx`、`App.tsx`、`vite.config.ts`、`index.html` 都没有引入或 glob 它们。
- 后果：Vite 从 `/src/main.tsx` 出发，只打包被 import 到的 CSS。三页在真实构建里没有这三份文件里的任何规则：`.ov-metrics` 网格、`.ov-metric` 卡片外观与 `.ov-metric__bar` 色调条（D01）、`.ov-pill` 计数胶囊、`.ov-judge` 金色左边框、`.ov-row` 与 `.ov-change` 的列网格、`.rl-*` 的当前方案条/角色卡/键值/差异面板/表格最小宽与末列靠右、`.rt-*` 的命令单元格与就绪检查虚线框（D13 的 §8 取值）都不生效；只有 `common-section.css`（区块卡、标题、复制结果行）生效。Vitest 默认不处理普通 CSS 引入、jsdom 也不做布局，所以执行端测试、V01、V02 都看不出来。
- 要改：
  1. 在各视图模块里引入自己的样式表：`overview-OverviewView.tsx` ← `overview-styles.css`，`roles-RolesView.tsx` ← `roles-styles.css`，`runtimes-RuntimesView.tsx` ← `runtimes-styles.css`。
  2. import 写在组件 import 之后，使它们晚于 `common-section.css` 载入：`.common-section` 的 `border` 简写与 `.ov-judge` 的 `border-left` 同特异性，顺序反了金色左边框会被盖掉。也可以把选择器抬成 `.common-section.ov-judge`，与顺序无关。
  3. 在 `tests/page-css.test.ts` 补一条断言：三份页面样式表各被 `src` 下某个 .ts/.tsx 模块 import。
  4. 自检：`npm run build` 后 `dist/assets/*.css` 里能搜到 `.ov-metric`、`.rl-card`、`.rt-ready`（dist 被 Git 忽略，不入提交）。
  5. 除此之外不改行为；CSS 取值、px 注释、令牌规则保持原样。

### B2【门禁端，热修补】基准测试证明不了样式表被应用
- 位置：`tests/test_gate_t009_baseline.py` 的 `css_value_problems`、`test_d13_css_values_match_section_8`、`test_d13_css_tokens_px_comments_and_w4`、`test_d01_tone_stripe_colors`：都用 `css_text(key)` 读四份 CSS 的文本，不看它们是否进了应用。候选没接线时仍全绿，所以 D01「色调条四色正确」与 D13「§8 取值」只证明了「文件里写着」，是空心断言。
- 要改：加一条留在仓库里的回归断言，证明四份 CSS 都进了应用：静态（`src` 下有 .ts/.tsx 以 import 引入每一份）和/或流水线（`npm run build` 后 `dist/assets/*.css` 含每份 CSS 里一个独有的类选择器，选择器从文件里解析，不写死类名）。自检里加「去掉某条 import」的变异，必须报问题。只加不放宽既有断言。这条在当前候选上应红，B1 做完应绿。

### B3【战后门禁】白盒测试与变异清单漏了同一处
- 位置：`tests/test_gate_t009_whitebox.py` 与 `mutation-spec-20261021T135450821255Z.json`：157 个变异全 caught，但每条变异的 `old` 文本里都没有 import 或 .css，白盒里也没有「样式表被引入」的断言；报告里「候选缺陷：无」因此不成立。
- 要改：白盒加同一断言；变异清单加「删掉 overview/roles/runtimes 任一份样式表的 import」三条，在返工后的候选上重跑，全部 caught。

建议顺序（供协调人参考，不是要求）：门禁端热修补 → 执行端返工 → 战后门禁复跑。这样 B2 的新断言先在旧候选上变红，再作为 B1 的验收。

## 核对记录

### 1. 范围（独立核对补丁）
- 候选补丁 40 个文件（32 新增、8 修改）逐个对 Scope：8 个修改都在 allowed_modified_files；32 个新增都在 allowed_new_files（22 个 readonly1 文件、RelativeTime、ActorTag、8 份 page-* 测试）。没有碰 forbidden_paths、package.json、锁文件、`tests/test_gate_*.py`、docs、.agent。与内核 scope.json（违规 0、警告 0）一致。
- 既有测试只动了 `desktop/web/tests/shell-app.test.tsx` 一处（站主 Q2）；基准测试与其余 T001–T008 测试没动；page-* 没有 skip/only/todo（grep 无命中）。

### 2. T006 的加法
- `router.ts`：`parseHash`、`mockOfQuery`、`useHashRoute()` 的签名与返回值不变；`navigate` 对不带 `?` 的 path 与原来逐字相同（`#` + path + 整段当前 query）。新增：`activeNavigate`（第 46 行）、`buildHash`（第 50–58 行）、`useHashRoute` 里一个登记用 effect（第 83–88 行，卸载时让位）、`useAppNavigate()`（第 94–98 行，`useCallback([])`，调用时读 `activeNavigate`）。
- `attemptGroups.ts`：`RUNNING`、`NEED_JUDGE`、`countByGroup`、`StatusCounts` 原样；新增 `AttemptGroup`、`ATTEMPT_GROUPS`、`groupOfState`，映射与合同 §1 逐项一致。

### 3. 写入口与网络
- 三页写入口全部经 `DisabledAction`；可用按钮只有刷新、分段选择段、[查看差异]、NextStep 的复制命令；可用链接是指标卡、[查看证据]、[跟随事件]、[查看全部历史]。
- 页面只调 api.ts 的读函数（getStatus、getHistory、getMeta/getMetaNow、getRoles、getProfiles、getPresets、diffPresets、getRuntimes）。新源码里没有 fetch、XMLHttpRequest、EventSource、WebSocket，没有 T007 禁用词、ServerIcon、字体词；W4（十六进制色、颜色函数、拼接 --tt-）、内联 style、role=status、四个禁用接口也都无命中。CSS 里用到的令牌在 tokens.css 里都存在。

### 4. 检查结果
- 内核 check（`checks/01/checks.json`，fresh 验证工作区，候选树 2225bc47…，检查前后树相同、未改候选文件）：V01 52 passed（43.3s）、V02 333 passed（255.7s，无 failed|error）、V03 7 passed，`all_required_passed: true`。V02 因此已由内核在候选上跑过，不再需要站主另行确认。
- 门禁端白盒 W1：461 passed，无 skip/xfail。简报里的「内核落地预演 385 passed」我没有核实，也没有依赖它。

### 5. 门禁端 5 条裁定
1. 指标卡「图标同色」：不是阻塞缺陷，记为合同未写清加人工项。合同 §4 写了「图标同色」但没指定图标，D01 与基准都不验，候选没加图标，已在 interpretations 与 limitations 里写明。设计稿 `docs/ui-design/screens/Main.dc.html` 第 97–100 行的卡是「16px 图标加标签」一行、大数字一行，图标颜色同色调条（那一版是七端卡片，只作结构参考）。图标用哪四枚需规划端或站主定，自然的选择是与各分组状态标签同一枚（LoaderCircle、Scale、CircleArrowUp、GitMerge）。
2. `.rt-cmd` 行内：成立，记为人工项，不阻塞。`runtimes-RuntimesView.tsx` 里 `.rt-cmd` 是行内 span，`runtimes-styles.css` 的 `max-width: 280px` 与 `overflow: hidden` 对非替换行内框无效（`white-space: nowrap` 有效）。影响小：文字已按码点截到 40 个（22 加 3 加 15），等宽小字约 290px 上下。建议加 `display: inline-block; vertical-align: bottom;`；基准只要求同一条规则里有 max-width、overflow、white-space，不受影响。
3. 色调条位置：成立，记为人工项，不阻塞。`.ov-metric` 是 flex 行，`.ov-metric__bar` 是普通 flex 子项，落在 20px 左内边距之后，不贴卡的左缘；合同给了 `overflow hidden` 与 `--tt-space-5` 左内边距，设计稿（`Main.dc.html` 第 97 行）是绝对定位的 `left:0; top:0; bottom:0; width:3px`。合同与基准只定「宽 3px」，不验位置。另外设计稿的卡是纵向（标签行在上、大数字在下），候选是横向，合同没写方向。注意这些视觉判断要等 B1 修复后才有意义。
4. `buildHash` 经 `URLSearchParams` 重新序列化：与合并语义相符，不是缺陷。合同要求「合并当前 query 参数（保留 mock 与其他参数，path 的 query 覆盖同名），结果 #pathname?merged」。同名覆盖、其余保留都正确；重新序列化只会把空格写成 `+`、对少数字符做百分号编码，经 `URLSearchParams` 读回值不变；`mock`、`group`、`tab` 不含特殊字符，不受影响。`parseHash().query` 仍是原串，`mockOfQuery` 按原串切，不受影响。给任务页那一片的提醒：用 `URLSearchParams` 读查询，不要手写 decode。
5. `aria-controls` 悬空：成立，记为可访问性小问题，不阻塞。`roles-PresetsTable.tsx` 里 `aria-controls` 取值是 `rl-diff-` 加方案名，面板只在展开时存在；收起时指向不存在的 id（披露式按钮常见写法，读屏容忍）；`aria-controls` 是以空白分隔的 id 列表，名称含空格会被拆开；合同公共约定写的是「id 用 useId」，这里用了名称拼接。建议：id 用 `useId()` 加行下标，收起时不设 `aria-controls`。

### 6. 执行端 5 条解读裁定（没有一条是合同矛盾）
1. useAppNavigate：合同原文就是「返回稳定回调，委托当前挂载路由的 navigate（effect 注册）」，候选照字面做，是落实不是解读。成立。限制：模块级单例，两个 useHashRoute 同时挂载时后写者胜；App 只有一个实例。
2. 图标：不是「按最合理读法」，是合同写了要求而实现省略（理由是门禁不验、图标没指定）。合同确实没指定图标，属合同未写清。执行端写进了 interpretations 与 limitations，没写进 unresolved_questions。接受为已披露的缺口，不阻塞（见建议 S1）。
3. 编号后的空格文本节点：实现细节，不是合同读法。grid 忽略纯空白文本，布局不受影响；基准在文本里取 `#` 后的数字，没有这个空格会把编号和相对时间的数字连成一个数。无害，接受。
4. 当前方案初值与「其余 M 个角色」：合同没定义「角色总数」；取当前方案 roles.length 是合理读法（夹具 4 个角色、差异 1 行，得「其余 3 个角色」，与基准一致）。这是真正的合同未写清，已写进 interpretations，接受。
5. 总览说明：合同原文「description 用 getMetaNow()+getMeta()」，候选保留了占位页已有的写法。落实，不是解读。

### 7. JEV 三处疑点裁定
- 自行解读合同（p=0.94）：不应写成 contract_conflicts。5 条里 #1、#5 是合同字面要求，#3 是实现细节，只有 #2、#4 是合同没写清；没有任何两处合同互相矛盾，所以 `contract_conflicts` 为空是对的。AGENTS.md 规定「合同没写死、需要自己定的地方不算矛盾，按最合理读法继续并写进 interpretations」，执行端照做了。小瑕疵：#2 更像 unresolved_questions；报告正文「合同矛盾与处理」只提了 RelativeTime「本地时间」的措辞，没提图标。
- 自述完成而无证据（p=0.93）：不是「没有命令或输出」。D01–D14 都有证据指向（见第 8 节）：合同给 D01 的证据是 V01、V02，D02–D13 是 V01，D14 是 V02、V03、scope、review；内核 check 在 fresh 工作区复跑过，全过。但有一半说得对：D01（色调条）与 D13（取值）的 done，证据只到 CSS 文本，证明不了产品里生效，B1 推翻了这两条的 done。
- 弱化测试（p=0.53，置信 0.06）：不成立。补丁里被改的既有测试只有 `desktop/web/tests/shell-app.test.tsx` 一处（站主 Q2 授权）：标题改为「总览页渲染真页面」，旧断言（「夹具数据已读到：getStatus，7 条」，那段文字已不存在）换成 `[data-page=overview]` 存在与 4 张 `[data-metric]`；没有 1/2/1/1 计数断言（合同写的是「如……」示例），计数在 `page-app.test.tsx` 里断言。基准测试与 T001–T008 测试没动。内核提示的「删除 1 行含断言的代码」就是这一行。

### 8. DoD 证据表
| DoD | 证据 | 终审结论 |
|---|---|---|
| D01 | V01：test_d01_*、overview 探针（指标卡与链接）、色调条 CSS 文本检查；V02；内核 check 复跑 | 计数、顺序、链接、点击、修饰键成立。「色调条四色正确」只在 CSS 文本里成立，B1 修复前产品里不生效；图标同色缺（非阻塞，见建议） |
| D02 | V01 overview 探针（需要你判断、复制三态） | 成立（overview-OverviewView.tsx、overview-logic.ts 核对）；胶囊与金色左边框的样式待 B1 |
| D03 | V01 overview 探针 | 成立；行样式待 B1 |
| D04 | V01 overview 探针 | 成立；动作说明表与 UI 文档 10.4 逐条一致 |
| D05 | V01 overview 探针 + TRANS1 | 成立 |
| D06 | V01 roles 探针 | 成立 |
| D07 | V01 roles 探针 | 成立 |
| D08 | V01 roles 探针 | 成立 |
| D09 | V01 roles 探针 | 成立（aria-controls 见建议） |
| D10 | V01 runtimes 探针 | 成立（.rt-cmd 与就绪检查按钮位置见建议） |
| D11 | V01 pages 探针 + TRANS3 | 成立；源码核对写入口全经 DisabledAction |
| D12 | V01 common 探针、test_d12_* | 成立 |
| D13 | V01 test_d13_*（文本级） | 禁用词、W4、px 注释、令牌成立；「§8 取值在产品里生效」被 B1 推翻 |
| D14 | V02、V03（内核 check）、scope.json、grep | 成立 |

### 9. 变异清单核对
- 157 个变异全 caught。候选改的 31 个非测试文件（3 页、router、attemptGroups、index.ts、icons、RelativeTime、ActorTag、22 个 readonly1 文件）每个至少有一条变异。门禁没有声明等价变异，也没有声明「没法变异」的文件，所以没有需要逐条裁定的等价项。
- 缺口：全部变异都改文本，没有一条动 import 或接线（B3）。

### 10. 建议（不进阻塞项；执行端可顺带改，改了会被复审）
- S1 指标卡：补四枚 16px 图标（颜色同色调条），色调条改成贴卡左缘（卡 `position: relative`，条绝对定位），必要时改成纵向布局。图标用哪四枚要先由规划端或站主定。
- S2 `.ov-row__name` 缺等宽：合同 §4 写「名称……等宽省略」，`overview-styles.css` 里只有省略，没有 `font: var(--tt-mono-sm)`。
- S3 `.rt-cmd` 改成 `display: inline-block`（见门禁第 2 条）。
- S4 方案表 `aria-controls` 的 id 改用 `useId()`（见门禁第 5 条）。
- S5 就绪检查：[运行就绪检查] 在区块体内（`rt-ready-area`），合同 §6 写的是「h2 就绪检查 加 [运行就绪检查]」，倾向放在 h2 同一行（Section 已有 action 位）；基准只验在区块里。
- S6 执行端自己的测试比合同 §9 薄：page-roles 缺差异面板「读取中」「同时只开一个」「过期丢弃」；page-app 缺悬停提示与可用按钮白名单扫描；page-static 的禁用词表缺 `createContextualFragment` 与字体词，也没扫三个页面文件；page-app.test.tsx 首行没写 §10 要求的「接本机服务那一片推翻（夹具与 ?mock= 开关换成真实数据）」。这些行为由基准探针覆盖，所以不阻塞。
- S7 `PresetsTable` 里 `onDiff(...).then(...)` 没有 `.catch`：`diffPresets` 现在不会 reject，若以后会，面板会停在「正在读取…」。
- S8 低优先级：基准用「文本里 `#` 后取数字」读配置变更编号，对相邻文本节点很脆；合同没固定类名，所以没有更中立的写法，仅提醒。

### 11. 人工项（不算阻塞，B1 修复后再做）
视觉对照（暗/亮主题、1024 窄窗口）、悬停手感、读屏、真浏览器里的点击导航（含 Ctrl 或中键点指标卡）；另加：指标卡色调条与图标、attempt 行名称字体、命令单元格宽度的目视。

### 12. 本端的限制
没有 shell 工具：没跑 `npm run build`，没看 dist；B1 的结论来自 import 依赖图（grep 全仓）加 Vite 的打包规则，不是看构建产物。没读 events.jsonl 全文，只抽查了解读与图标相关的段落。悬停提示、读屏等 DOM 行为依赖基准探针与内核记录，我没有独立复现。

Verdict: REVISE
