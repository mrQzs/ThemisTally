# 复审记录：t038-desktop-web-hub-posts attempt-002（七端信箱 hub）

- 合同：t038-desktop-web-hub-posts.v3（base c637a9a797a9fd7b56faf2bd6cd14b46846b804b）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 1；变异检查退出码 None
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261114T180638966686Z-fb9e），终审报告如下

## 终审报告

# T038-7 终审报告（audit-sonnet · attempt-002 · 候选 31b721c4）

## 结论

**返工** —— 退回 **执行端**。阻塞项 1 条：配置行来源的 profile id「等宽」没有真的接进样式表（门禁端举证的 W12 成立，不是白盒误读合同）。

候选的其余部分我逐条独立读过源码后认为忠实于合同 v3：没有越界、没有删改既有断言、没有为过测试写的特判，执行报告的自述与内核记录对得上。

## 一、门禁端举证的候选缺陷裁定（逐条）

### W12 `test_w12_source_profile_id_mechanism_wired` —— **成立**

- 合同原文（Behavior contract·边界输入）：「来源列：`source === 'config'` → 显示该行的 `profile` id（**等宽**）。」（D05 同款）
- 候选实现：`desktop/web/src/pages/readonly1/roles-HubPosts.tsx:50`
  `return p.profile != null ? <span className="tt-table__mono">{p.profile}</span> : DASH;`
- 我在 `desktop/web/src` 全量 grep `tt-table__mono`，全仓库只有三处：
  1. `src/components/Table.tsx:106` —— 列级 `mono` 把类名加在 **td** 上；
  2. `src/components/Table.css:64` —— `.tt-table td.tt-table__mono { font: var(--tt-mono-sm); }`（要求类名在 **td** 上）；
  3. `src/pages/readonly1/roles-HubPosts.tsx:50` —— 候选把类名加在 **span** 上。
  另 `src/components/Tag.css:8,11` 有 `.tt-tag { font: var(--tt-text-caption-strong); }` 与 `.tt-tag--mono`，本片没用到。
- `src/components/Table.css:26-29`：`.tt-table td { … font: var(--tt-text-sm); … }` —— td 是比例字体。span 继承 td → **真实浏览器里配置行的 profile id（quizs-m3、step-high）不是等宽**，与合同那句相反。
- 白盒的判据不是误读：`selector_can_style()`（白盒文件 :132-149）按「选择器里有没有一个复合体能命中『带该类的该 tag 元素』」判断，`.tt-table td.tt-table__mono` 对 `(span, tt-table__mono)` 返回 False 是正确的 CSS 语义；白盒还自检了匹配器不会恒红/恒绿。
- 为什么此前全绿：`tests/test_gate_t038_baseline.py:732-735` 的 `isMono()` 只查「类名里含 mono 的子元素」，不看有没有 CSS 规则能作用到它 —— 这正是 T009 的教训（样式写得再对、没接进样式表照样全绿）。这条基线断言是**空心**的，白盒 W12 补的正是这一面。

**修法不限定写法，但必须落在合同的允许改动集内**：`allowed_modified_files` 不含 `desktop/web/src/components/Table.css`，所以等宽规则只能追加到 `roles-styles.css`（推荐 `.rl-hub .tt-table__mono { font: var(--tt-mono-sm); }`）。我核过 G01 的 `css_tail_problems()`（:294-344）对这条追加的判定：只追加（基线前缀 sha 不变）、无 px、无十六进制、无颜色函数、`var(--tt-mono-sm)` 会被 `var(--tt-[^)]*)` 剥离规则吃掉（不算拼接令牌名）→ 追加守卫与 S08 都仍成立，追加部分原有的 `.rl-hub .tt-table { min-width: 760px; }` 规则保留即可。另一条路是改用 Table 的列级 `mono` 承载（`Table.tsx:106` 已有该机制），但那会让缺省行的「默认」Tag 也落在等宽 td 里（Tag 自己有 `font` 才没被带跑），要一并核对。**保留 span 写法时，白盒 W12 会自动转绿，白盒文件不用改**；若换了承载元素，按白盒文件注释里的约定改它开头那一行断言（那是战后门禁的文件）。

## 二、我独立复核的候选（不只看全绿）

| 面 | 我看到的事实 | 判定 |
|---|---|---|
| api.ts | 只增不改：`HubPostFallback`（profile/runtime 可选键）、`HubPostRow`、`HubRolesData`、`getHubRoles()`（真实分支 `client.get('/api/v1/hub/roles', undefined, 30)` 不回落桩；桩分支 `read(['config','hub','show','--json'], () => okEnvelope(同命令, clone(HUB_ROLES_POSTS)))`）。patch 里 api.ts 是 36 行纯插入，既有导出与签名一个没动 | 合合同第 2 步、D01 |
| 桩 | `src/mock/hub-roles.ts` 六行逐字段对上合同第 3 步：coordinator 缺省+四键替补（无 profile/runtime）、planner provider=null、contract 配置行 quizs-m3+六键替补、gate/audit 缺省 runtime=null、exec 配置行 step-high；纯 `import type`（擦除，无运行时环） | 合 D02 |
| 页面 | `loadRoles` = `Promise.all([getRoles(),getProfiles(),getPresets(),getHubRoles()])`，失败判定仍只看前三个且顺序不变，hub 信封整个进 `data.hub`；`RolesView` 在角色卡网格之后、`ProfilesTable` 之前渲染 `<HubPosts hub={data.hub}/>` | 合 D03、D04 |
| 字段格式 | null→「—」；`runtime（adapter）`（gate/audit 是「—（pi）」）；`provider/model`（planner 是「—/claude-opus-5-5」）；`EffortPair effective={null}`（「要求 X · 生效 未知」）；来源 Tag「默认」/ profile id；替补三段「·」连接，四键→「—（pi） · dsf/deepseek-flash」、六键→「step-high · pi（pi） · bb/step-5-preview」 | 合 D05（**等宽一项不合，见阻塞项**） |
| 纯函数 | `hubPostName`（六个中文名，未知原样）、`allowedProfiles`（adapter 非空且在名单内、按输入顺序）、`normalizeHubPost`（缺键归 null；四键替补补出 profile/runtime 两个 null） | 合 D06 |
| 源码规矩 | `RolesPage.tsx` 无 preview/getOperation/usePreset/setPluginEnabled；readonly1 下无 `style=`、无 `role=status`、无危险 HTML/动态求值；CSS 只追加四条，px 行有同行出处注释 | 合 D07 |
| 既有测试 | patch 的删除行只有 6 处：RolesPage 的 loadRoles、RolesView/roles-logic 的 import 与注释头、live-api 的 describe 标题 15→16。没有删/跳/弱化任何既有断言；`page-app.test.tsx`、`readonly2-app.test.tsx` 未出现在 patch 里 | 合 D08、D09、D10 |
| 依赖 | candidate.stat 与 scope.json 里没有 package.json / package-lock.json | 合 D10 |
| D11 | 桩与页面文字只出现 `step-high`、`quizs-m3`，没有 profiles.json 里档位为 low 的那条 profile id | 合 D11 |

**全绿不等于对 —— 我另外查的几件事**

- **测的是真实现吗**：`page-hub.test.tsx` 走真实 `App` + 真实 api（桩模式）+ 真实 `HubPosts`/`EffortPair`/`Table`；`roles-hub-logic.test.ts` 直接调真纯函数。两份新测试无 skip/only/todo；没有把业务逻辑抄进测试。
- **硬编码/为过测试的特判**：桩是合同第 3 步逐行写死的内核形状（不是照着断言反推）；`roles-logic` 的归一里没有任何按岗位码分支；`sourceCell` 只按 `source` 分支。
- **空的异常处理**：hub 失败分支渲染「没能读到七端岗位：命令 … 返回退出码 N。」+ messages 的 `pre`，没有空 catch、没有吞错。
- **范围**：scope.json `violations: []`、`ok: true`，7 改 + 4 新全部 in_scope，forbidden_paths 未碰。
- **自述 vs 内核线索**：内核摘要提示的「6 条退出码被管道掩盖」是探索命令（`ls | wc -l` 之类），不是四项检查；四项检查的内核独立复跑（`attempt-002/checks/02/checks.json`）退出码全 0、`candidate_files_modified: []`、`modified_by_checks: false`。执行报告的自检表与之一致。**没有发现写死临时路径或自述不实**（与 T025 attempt-002 那类问题不同）。
- **解释 1（allowedProfiles 签名）**：合同字面形式 `readonly ProfilesData['profiles']` 在 tsc 下报 TS1354，执行端改成等价的 `readonly ProfilesData['profiles'][number][]`，V02（tsc --noEmit，退出 0）已证可编译 —— 认可，不算缺陷。
- **解释 2（配置行来源的 span）**：即上面的阻塞项。

## 三、DoD 结论表（D01–D11）

| DoD | 结论 | 依据 |
|---|---|---|
| D01 getHubRoles 两条分支 | 成立 | api.ts:442-448；live-api.test.ts:98（路径/时限 30）、describe 标题 16；G01 P6 |
| D02 桩是 .ts、mock 恰 14 JSON、pages 恰 9 个 *Page.tsx | 成立 | mock/hub-roles.ts；G01 S01；R01 T036 |
| D03 并行四读、失败顺序、失败隔离 | 成立 | RolesPage.tsx:23-42；page-hub.test.tsx 两个 describe；G01 P3/P4/P5 |
| D04 六列无操作列、data-post、位置 | 成立 | roles-HubPosts.tsx COLUMNS/rowAttrs；page-hub.test.tsx 列头与位置用例；G01 P1 + trans 探针 |
| D05 六行逐格 | **部分不合** | 字段全对；「等宽」一项不合（阻塞项 1） |
| D06 三个纯函数有测试 | 成立 | roles-hub-logic.test.ts（9 个用例） |
| D07 源码规矩 | 成立 | S08/S11 + R01 T006/T024 |
| D08 既有测试未动 | 成立 | patch 删除行 6 处；R01 923 passed |
| D09 范围 | 成立 | scope.json ok、violations 空 |
| D10 无删跳弱化、无依赖变更 | 成立 | candidate.stat（11 文件，无 package*.json） |
| D11 不出现 low 档 profile id | 成立 | mock 与页面文字只有 step-high/quizs-m3；R01 T009 D09 通过 |

## 四、阻塞项（一次列全）

1. **（执行端）配置行来源的 profile id 没有真的等宽** —— `roles-HubPosts.tsx:50` 把 `tt-table__mono` 加在 span 上，而 src 下唯一含该类的规则是 `Table.css:64` 的 `.tt-table td.tt-table__mono`（类名要求在 td 上），span 继承 td 的 `--tt-text-sm` 比例字体；违反合同「来源列：source === 'config' → 显示该行的 profile id（等宽）」。修法不限定写法，但必须在允许改动集内：`roles-styles.css` 追加一条能命中该元素的规则（推荐 `.rl-hub .tt-table__mono { font: var(--tt-mono-sm); }`，我已核过不撞 G01 的 CSS 追加守卫），或改用 Table 的列级 mono 承载并核对缺省行 Tag 的字体。保留 span 时白盒 W12 自动转绿、测试不用改。

（除这一条外没有别的阻塞项；其余 DoD 见上表。）

## 五、非阻塞意见（不挡，供站主决定）

- `tests/test_gate_t038_baseline.py:732-735` 的 `isMono()` 是空心断言（只看类名），门禁端可考虑补一条「带该类的该元素能被 src 下某条 CSS 规则命中」的接线断言，避免同类问题再次全绿放过。
- 合同第 3 步写的 `readonly ProfilesData['profiles']` 过不了 tsc（TS1354）；执行端的等价改写已被 V02 证明可编译，合同端可在下一版把字面形式改对。
- 白盒 W12 开头 `("span","tt-table__mono") in pairs` 写死了承载机制；换机制时按该文件注释里的约定改这一行即可（战后门禁的文件，本回合不动）。

Verdict: REVISE
