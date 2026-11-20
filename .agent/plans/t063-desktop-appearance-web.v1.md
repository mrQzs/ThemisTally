# TASK: t063-desktop-appearance-web

<!-- 片 B（前端侧）：页面用宿主给的外观起步、跟着外观事件变、标题栏主题菜单真的会保存、紧凑密度生效。
     基线是 T061 结项后的 9da7f2a3ce；T061 的合同与已落地代码是接口名与字面量的唯一依据。
     规划报告在旧基线（2488d36b）上写，本合同里逐条核对过，核对结果写在「Repository facts」的事实表里。 -->

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 10f1496e1775e842928769a9e42f5072020ab6b9
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
前端页面在外观上「跟得上」桌面外壳：服务窗口与外壳页窗口（设置、首启、服务状态）都用宿主或外壳给的外观起步（首帧之前就把主题与密度写好），任何一次成功保存后所有还开着的窗口跟着外观事件变；服务窗口与设置窗口标题栏的主题菜单真的会把主题存到外壳；紧凑密度生效——数据表行高 40/44/52 在紧凑时分别是 32/36/44。

## Non-goals
- `desktop/shell/**` 一个字不改（外壳侧是 T061，已结项）。
- `desktop/web/src/shellpages/SettingsView.tsx` 不改：设置页照旧「先改后存」，保存失败照旧提示「主题已切换，但没能保存：…」、本窗口照切、别的窗口不跟（站主 2026-11-19 拍板）。
- 主题设为跟随系统时，标题栏不显示解析后的「暗 / 亮」。
- 日志页检索轮询、多仓库、托盘、单实例、打包、依赖升级：本片都不碰。
- 不退役任何既有门禁断言，不改任何既有测试文件；不改 `desktop/shell/package.json` 与锁文件。

## Repository facts

### 入口与调用关系（已读，签名与基线一致）
- 外观能力的外壳侧（`desktop/shell`，本片只读）：
  - `desktop/shell/preload.js` 暴露 `window.themisHost` 九个成员：`reauth`、`openSecretWindow`、`openExternal`、`reveal`、`notify`、`openSettings`（原六个）+ `saveTheme(pref)`、`getAppearance()`、`onAppearance(listener)`。`saveTheme` **不拆信封**，回信封对象；`getAppearance()` 经 `ipcRenderer.sendSync("themis-host:get-appearance")` **同步**返回外观对象或 `null`；`onAppearance` 同步返回退订函数，监听只收外观对象一个实参。
  - `desktop/shell/shell-preload.js` 暴露 `window.themisShell` 十一个成员：原十个 + `getAppearance()`（同样是 `sendSync("themis-shell:get-appearance")`，同步返回外观对象或 `null`）；`on(event, listener)` 认两个事件名 `"service-state"` 与 `"appearance"`，别的事件名同步回空退订函数；`on('appearance', cb)` 的 cb 只收外观对象一个实参。
  - 外观对象形状固定 `{ theme, density }`：`theme ∈ {"system","light","dark"}`、`density ∈ {"standard","compact"}`。
  - `saveTheme` 的信封：成功 `{ ok: true, value: { theme, density } }`；失败 `{ ok: false, reason }`，`reason ∈ {bad-args, unavailable, forbidden, write-failed, internal}`。
  - 缺省主题是暗（`"dark"`）、缺省密度是标准（`"standard"`）；外壳只在保存成功且外观真的变了时才把新外观广播给所有还开着的窗口。
- 前端侧（本片要改的 7 个文件）：
  - `desktop/web/src/shell/theme.ts`：现导出 `type ThemePref = 'dark' | 'light' | 'system'` 与 `applyTheme(pref)`（暗 → `removeAttribute('data-theme')`，亮/跟随系统 → `setAttribute`）。`applyTheme` 是唯一写 `data-theme` 的地方。
  - `desktop/web/src/components/Table.css`：三条数据表行高规则 `.tt-table[data-row-height="40"] td { height: 40px; }`、`…="44"… 44px`、`…="52"… 52px`（紧挨着写，后面跟 `tbody tr:hover` 等规则）。
  - `desktop/web/src/shellpages/themisShell.ts`：只放类型、不导出值；`export interface ThemisShell` 现**恰好十个成员**（`getState`、`pickRepo`、`pickPython`、`pickKit`、`pickTranscriptDir`、`saveSettings`、`startService`、`restartService`、`openExternal`、`on`）；另有 `SettingsPatch`（六键）、`ShellSettings`（含 `theme`/`density`）、`ShellState` 等类型。
  - `desktop/web/src/shellpages/shellBridge.ts`：全前端唯一读 `window.themisShell` 的地方，也是 `themisShell?: unknown` 的全局声明处；导出 `SHELL_MEMBERS`（十个名字逐字）、`shellBridgeInstance()`、`unavailableShell()`、`resetShellBridge()`；`SHELL_MEMBERS` 十个成员齐全才算有外壳，包装按原对象用 WeakMap 缓存，`on` 的转发只认 `service-state`。
  - `desktop/web/src/live/hostSettings.ts`：唯一读 `window.themisHost` 的地方；现导出 `HostEnvelope`（`ok?`/`reason?`）、`hostHasOpenSettings()`、`hostOpenSettings()`；沿用 `hostBridge()` 的类型断言写法，不写 `declare global`。
  - `desktop/web/src/App.tsx`：根组件现 `useState<ThemePref>('dark')`，`useEffect` 里 `applyTheme(theme)`；`ThemePrefProvider` 的 `onThemeChange` 给 `setTheme`；`ServiceApp` 把 `theme`/`setTheme` 传给 `TitleBar`。
  - `desktop/web/README.md:59`：现在写「…由标题栏的主题菜单切换（theme.ts 的 applyTheme 是唯一写 data-theme 的地方，偏好只存内存）。」
- 门禁与测试（钉住本片不许碰的地方）：
  - `tests/test_gate_t034_baseline.py:106-107`：`APP_FORBIDDEN = (… \bthemisHost\b …, r"themisShell", …)`；`themisShell` 是**区分大小写的子串匹配**（`'./shellpages/themisShell'` 这样的导入路径也撞上），`themisHost` 是整词。:339-363 用 `strip_ts_comments` 后的 App.tsx 原文来扫。
  - `tests/test_gate_t012_baseline.py`：`new_ts_files()`（:270-274）= shellpages 的 ts/tsx + `desktop/web/src/App.tsx` + `desktop/web/src/pages/SettingsPage.tsx`；:795-803 的 `interface_problems` 要求 `interface ThemisShell` 的成员集合**恰好**等于那十个；:847-857 另要求该文件只导出类型（不许 `export const|function|class`）；:1031-1059（D10/D11）要求这些文件原文里不出现 `data-theme`、四个网络词、`themisHost`、`window.themisShell`、`declare global`、`localStorage`/`sessionStorage`、`window.open`/`window.confirm`、`ServerIcon`。
  - `tests/test_gate_t032_baseline.py:117-128`（`UNTOUCHED_REL`）：`desktop/web/src/shellpages/shellStub.ts`、`desktop/web/src/shellpages/ShellWindow.tsx`、`desktop/web/src/shellpages/SettingsView.tsx`、`desktop/web/src/shellpages/shellWindowRoute.ts`、`desktop/web/vite.config.ts`、`desktop/web/scripts/check-live-build.mjs`、`desktop/web/tests/shellpages-static.test.ts`、`desktop/web/tests/cleanup2-static.test.ts` 与七份 `desktop/web/tests/shellpages-*.test.*`——本片一个都不碰。:240-254（S02）只要求 `shellBridgeInstance`/`unavailableShell`/`resetShellBridge` 三个导出**存在**，不禁止再加导出；:257-263（S03）shellBridge.ts 原文不许有四个网络词、不许 import api、剥注释后不许有 `themisHost`；:266-282（S04）整个 `desktop/web/src` 里只有 shellBridge.ts 读/声明 `window.themisShell`。
  - `tests/test_gate_t006_baseline.py:3457-3476`（D06）：theme.ts 导出 `applyTheme`、含 `data-theme`、不许 `classList|className`、`.style`、`document.body`、`localStorage|sessionStorage`；`new_source_files()`（:3353-3359）含 `desktop/web/src/App.tsx` 与 `desktop/web/src/shell/**` 下全部文件，这些文件剥注释后不许出现 `data-theme`（theme.ts 除外）。主题探针断言：缺省无 `data-theme`、触发钮名称「主题：暗」、经菜单依次是 light/system/去掉、html 与 body 其余属性不变、无内联样式、`localStorage.length === 0`。
  - `tests/test_gate_t005_baseline.py:287-317,811-833`：`TABLE_SPECS` 的判定是「有一条规则满足就行」（`has_decl`），行高 40/44/52 三条各有一条规则即可。
  - `tests/test_gate_t007_baseline.py:397-425,619-651`：Table.css 走 `px_literal_problems` —— 除 0 与 1px 外的 px 字面量，**所在行**必须有出处注释。
  - `tests/test_gate_t060_baseline.py:423-434`（S06）：hostSettings.ts 要保留 `hostOpenSettings`、`themisHost`、`openSettings` 与 `typeof x !== 'function'` 的判断；不许 `declare global`、不许读 `window.themisShell`、不许 import api。
  - `desktop/web/tests/shellpages-static.test.ts`（冻结）：`desktop/web/src/shellpages/**` 全部 ts/tsx 不许有 `data-theme`、`themisHost`、`matchMedia` 等。
  - `desktop/web/tests/shellpages-live-bridge-static.test.ts`（冻结）：读/声明 `window.themisShell` 只许在 shellBridge.ts。
- 工具链：
  - `desktop/web/package.json`：`test` = `vitest run`；`build` = `tsc --noEmit && vite build`；`check:contract` = `node scripts/token-contract.mjs`（成功时打印「契约检查：通过，无违规。」）。
  - `desktop/shell/package.json`：`test` = `node --test --test-reporter=tap` 加 22 个测试文件逐字点名（报告是 tap，输出有 `# pass N`）；清单逐字点名，本片不许新增外壳测试文件。

### 事实核对表（规划报告哪一条 / 新基线上的实际事实）
| 规划报告 | 新基线上的实际事实 | 本片的处置 |
|---|---|---|
| 第 3 节「T061 改过的解析器要求 themisShell.ts 怎么写」（H2） | T012 的接口检查、外壳单测 `desktop/shell/tests/shellpreload.test.js` 与 T030 的 P04 探针**都**要求 `interface ThemisShell` 解析出的成员恰好十个，暴露面 = 十个 + `getAppearance`（十一）。T061 合同里那句「T063 片 B 起 themisShell.ts 加 `getAppearance` 后恢复逐字相等」与这些断言冲突 | `interface ThemisShell` **一个成员都不动**；外观类型另起 `export interface ShellAppearance`（同文件、只放类型）。`desktop/shell` 禁改，三处断言原样保持绿 |
| 第 4 节步骤 4「`on` 的类型签名要放宽到两个事件」（风险段） | `ThemisShell.on` 的签名若放宽，接口检查解析出的成员就会多出第二个 `on`，T012 的 D01 直接红 | `ThemisShell.on` 不动；外观事件经 shellBridge 里的局部类型调用原对象的 `on` |
| H1（成员名与形状） | 核实成立：`themisHost` 九个成员（`saveTheme`/`getAppearance`/`onAppearance`）、`themisShell` 十一个成员（多 `getAppearance`，`on` 认 `appearance`）；外观对象 `{ theme, density }`；`saveTheme` 回 `{ok:true,value:{theme,density}}` / `{ok:false,reason}`，**不拆信封**；`getAppearance()` 同步返回对象或 `null` | 合同逐字写死这些名字与形状 |
| H3（T012 PROBE_APP 不装外壳/宿主） | 成立：全文件里 `themisHost` 只出现在检查器 `forbidden_api_problems` 里，探针不装 `window.themisShell` 也不装 `themisHost` | 桩模式照旧走「只 setTheme」，`test_transitional_d08_theme_sync_through_app` 不退役 |
| H4（没有挂 App 的用例装了带外观成员的假外壳/宿主） | 成立：`desktop/web/tests/host-settings-open.test.tsx` 装 `{ openSettings }`、`desktop/web/tests/live-transport.test.ts` 装 `{ reauth }`、`desktop/web/tests/shellpages-live-bridge.test.tsx` 装十成员假外壳，都没有外观成员 | 既有用例一个不改；新成员缺失时回到缺省、不调用、不抛错 |
| H5（Table.css 追加规则不影响 T005/T007） | 成立：T005 是「有一条规则满足就行」；T007 的 Table.css 检查里有 `px_literal_problems` → 每条带 px 的行要同行出处注释 | 三条紧凑规则各带同行出处注释 |
| H6（T034 的 `themisShell` 是子串匹配） | 成立：区分大小写的子串，剥注释后扫 App.tsx | App.tsx 只从 `./shellpages/shellBridge`、`./live/hostSettings`、`./shell/theme` 引东西，引进来的名字不带小写的 `themisShell`/`themisHost` |
| 第 5 节「过渡断言一条都不退役」 | 仍成立：`UNTOUCHED_REL` 不含本片要改的任何文件；T012 的 D01 与 d08 过渡断言未动；T061 没有改 `tests/test_gate_t012_baseline.py` 与 `tests/test_gate_t032_baseline.py` | 退役名单为空；允许修改范围不含任何测试文件 |
| 第 4 节步骤 6「同步读取值非法时回 null」 | 与第 7 节「逐字段校验、初值不合法就回缺省」口径不同 | 按第 7 节定：只有「没有能力/抛错/回值不是对象」才回 `null`；字段非法时该字段取缺省（见 Behavior contract） |
| 第 4 节步骤 7「README 改掉偏好只存内存」 | `desktop/web/README.md:59` 现在正是这句话 | 照办，另加四点新说法并保留「主题」「标题栏」两词 |

- 基线检查：本回合逐条读了上面列出的文件与行号（`desktop/shell/preload.js`、`desktop/shell/shell-preload.js`、`desktop/shell/tests/shellpreload.test.js`、`desktop/shell/package.json`、`.agent/plans/t061-desktop-appearance-settings.v3.md`、六份相关门禁、`desktop/web/src/**` 的七个目标文件、`desktop/web/tests/**` 与 `desktop/web/package.json`）。整套检查在基线上的结果由内核在执行之前跑过并记入「基线检查记录」，执行端不必再跑一遍。

## Scope
- allowed_modified_files:
  - desktop/web/src/shell/theme.ts
  - desktop/web/src/components/Table.css
  - desktop/web/src/shellpages/themisShell.ts
  - desktop/web/src/shellpages/shellBridge.ts
  - desktop/web/src/live/hostSettings.ts
  - desktop/web/src/App.tsx
  - desktop/web/README.md
- allowed_new_files:
  - desktop/web/tests/appearance-units.test.ts
  - desktop/web/tests/appearance-app.test.tsx
- allowed_deleted_files: 无
- forbidden_paths: tests/test_gate_t063_*.py, desktop/shell/**, desktop/web/src/shellpages/SettingsView.tsx, desktop/web/src/shellpages/shellStub.ts, desktop/web/src/shellpages/ShellWindow.tsx, desktop/web/src/shellpages/shellWindowRoute.ts, desktop/web/vite.config.ts, desktop/web/scripts/check-live-build.mjs, desktop/web/tests/shellpages-static.test.ts, desktop/web/tests/cleanup2-static.test.ts, desktop/web/tests/shellpages-stub.test.ts, desktop/web/tests/shellpages-route.test.ts, desktop/web/tests/shellpages-first-run.test.tsx, desktop/web/tests/shellpages-settings.test.tsx, desktop/web/tests/shellpages-app.test.tsx, desktop/web/tests/shellpages-isolation.test.tsx
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- 既有测试文件（`desktop/web/tests/` 里除上面两个新文件以外的）与 `tests/` 下的门禁基准文件一个都不许改；门禁基准文件由门禁端写，执行端不许碰。

## Behavior contract

### 正常输入
- **外观对象**：形状固定 `{ theme, density }`。`theme` 只认 `'dark' | 'light' | 'system'`，`density` 只认 `'standard' | 'compact'`。来源有三处，形状一致：宿主同步读、外壳桥同步读、外观事件实参。
- **`theme.ts` 新增**：`export type DensityPref = 'standard' | 'compact';` 与 `export function applyDensity(pref: DensityPref): void;`。`applyDensity('standard')` 去掉 `document.documentElement` 上的 `data-density` 属性；`applyDensity('compact')` 写 `data-density="compact"`。它只碰 `document.documentElement` 的这一个属性：不加类、不写内联样式、不动 `document.body`、不碰存储、不用 `matchMedia`。`applyTheme` 保持现状（暗 → 去掉属性，亮/跟随系统 → 写值），仍是唯一写 `data-theme` 的地方。theme.ts 的头注释把「偏好只存内存」改成「偏好由桌面外壳保存，页面只持有当前值」一类说法。
- **`Table.css` 追加三条规则**，紧跟在现有三条 `.tt-table[data-row-height="N"] td { height: Npx; }` 之后，每条**同一行**带出处注释（写清「紧凑：行高 32/36/44」与出处，如设置页 :360 与 handoff :142）：
  - `:root[data-density="compact"] .tt-table[data-row-height="40"] td { height: 32px; }`
  - `:root[data-density="compact"] .tt-table[data-row-height="44"] td { height: 36px; }`
  - `:root[data-density="compact"] .tt-table[data-row-height="52"] td { height: 44px; }`
  只作用于 `td`（不碰 `th` 表头 32），只作用于写了 `data-row-height` 的表格；标准密度下这三条不生效（`data-density` 属性不存在）。
- **`themisShell.ts` 只补类型**：`export interface ShellAppearance { theme: 'system' | 'light' | 'dark'; density: 'standard' | 'compact'; }`（类型名与字段照此写，别名不改）。`export interface ThemisShell` **一个成员都不加不改**（仍恰好十个），文件仍只导出类型、不导出值。
- **`shellBridge.ts` 另导出两个函数**（`SHELL_MEMBERS`、`wrap`、`unavailableShell`、`resetShellBridge` 与十成员核对一行不动）：
  - `export function shellAppearanceNow(): ShellAppearance | null;` —— 能力判据：`window.themisShell` 存在、十成员齐全（`SHELL_MEMBERS` 十个都是函数）、且 `getAppearance` 是函数。满足才调 `getAppearance()`；回值逐字段校验（`theme` 合法就用，非法取缺省 `'dark'`；`density` 合法就用，非法取缺省 `'standard'`），返回 `{ theme, density }`。不满足能力、`getAppearance()` 抛错、回值不是对象 → 回 `null`。
  - `export function shellOnAppearance(listener: (appearance: ShellAppearance) => void): () => void;` —— 能力判据同上（十成员齐全且 `getAppearance` 是函数）。满足才调原对象的 `on('appearance', listener)`（`on` 已是十成员之一，必是函数）；返回的退订若不是函数则回空退订函数；`on` 调用抛错也回空退订函数。退订函数真的能退订（调用后监听不再收到事件）。
  - 两个函数都不抛错；`window.themisShell` 的读取仍只发生在 shellBridge.ts（`shellBridgeInstance()` 认不认外壳仍按十成员，与外观能力无关：**只有十个成员的旧假外壳仍被认作有外壳**）。
- **`hostSettings.ts` 新增三个函数**（沿用现有 `hostBridge()` 类型断言写法，不写 `declare global`，不读 `window.themisShell`，不 import api；`hostOpenSettings`、`hostHasOpenSettings` 与 `HostEnvelope` 照旧保留）：
  - `export function hostGetAppearance(): ShellAppearance | null;` —— `themisHost.getAppearance` 是函数才调；回值逐字段校验（同上，非法字段取缺省）；不是函数、抛错、回值不是对象 → 回 `null`。
  - `export function hostOnAppearance(listener: (appearance: ShellAppearance) => void): () => void;` —— `themisHost.onAppearance` 是函数才调（监听只收外观对象一个实参）；返回的退订不是函数或调用抛错 → 回空退订函数。
  - `export function hostSaveTheme(pref: ThemePref): Promise<HostEnvelope> | null;` —— `themisHost.saveTheme` 是函数才调，**只转交 `pref` 一个实参**；不是函数 → 回 `null`；调用的结果包成 Promise 返回（信封原样：成功 `{ ok: true, value: { theme, density } }`，失败 `{ ok: false, reason }`）；调用本身抛错 → 回 `null`。`HostEnvelope` 要能装下 `value`（`value?: { theme: string; density: string }`）。
- **`App.tsx`（根组件 `App`）**：
  - 两个状态：`theme: ThemePref` 与 `density: DensityPref`，都用**懒初值**：先 `hostGetAppearance()`，回 `null` 再 `shellAppearanceNow()`，还回 `null`（或没有能力）就用缺省 `'dark'` 与 `'standard'`。读外观只在这一步做一次。
  - 根上订阅外观事件：`useEffect` 里优先 `hostOnAppearance(...)`，没有这个能力再 `shellOnAppearance(...)`；都没有就不订。事件回调**逐字段校验**：`theme` 合法才 `setTheme`，`density` 合法才 `setDensity`，非法字段忽略（不写缺省、不报错）。卸载时退订。
  - 写属性：`useLayoutEffect` 里 `applyTheme(theme)` 与 `applyDensity(density)`（首帧之前写好，别用 `useEffect`）。`App.tsx` 里不出现 `data-theme`、`data-density` 这两个字样（连注释里也不许），属性名只留在 `theme.ts`。
  - 标题栏（`TitleBar` 的 `onThemeChange`）分三档，按顺序取第一个可用的保存途径：
    1. **宿主档**：`hostSaveTheme` 存在（返回非 `null`）→ 调它；信封 `ok === true` 才 `setTheme(pref)`；`ok === false` 或 Promise 被拒 → **保持原主题**、不弹提示。
    2. **桥档**：宿主档不可用且 `shellBridgeInstance()` 不是 `null` → 调 `saveSettings({ theme: pref })`；Promise 兑现后 `setTheme(pref)`；被拒 → 保持原主题、不弹提示。
    3. **内存档**：上面两档都不可用 → 只 `setTheme(pref)`。
  - `ThemePrefProvider` 的 `onThemeChange` 仍给 `setTheme`（设置页自己管保存，本片不碰 `SettingsView.tsx`）。
  - `App.tsx` 的禁词：`themisShell`（子串，含导入路径）、`themisHost`、`declare global`、`localStorage`、`sessionStorage`、`window.open`、`window.confirm`、`ServerIcon`、`liveModeIsReal`、`liveClient`（T034 的 S03/S04/S12）。引进来的名字只能是 `shellAppearanceNow`、`shellOnAppearance`、`shellBridgeInstance`、`hostGetAppearance`、`hostOnAppearance`、`hostSaveTheme` 这类不带小写 `themisShell`/`themisHost` 的。
  - 渲染照旧：`getMetaNow()`、`getMeta()`、「—」、`repoName={`、`kitVersion`、`offline`、`TitleBar`、`TabBar`、`useShellConnection()` 都在。
- **`desktop/web/README.md:59`**：把「偏好只存内存」改掉，写清四点——外观由桌面外壳保存（服务窗口经宿主、外壳页经桥）；启动时同步读当前外观；任何一次成功保存后外壳会把新外观广播给所有开着的窗口；紧凑时数据表的 40/44/52 各降 8（32/36/44）。保留「主题」「标题栏」两个词（T006 的 README 段断言照旧）。

### 边界输入
- 桩模式（开发/测试：既没有 `window.themisShell`，也没有 `themisHost`）：缺省暗 + 标准；`document.documentElement` 上**不多出任何属性**（标准密度是「去掉属性」，不是「写 standard」）；标题栏只改内存；`localStorage`/`sessionStorage` 保持空；`html` 与 `body` 的其余属性不变。
- `window.themisShell` 存在但只有十个成员（没有 `getAppearance`）：仍被认作「有外壳」（`shellBridgeInstance()` 不为 `null`）；但外观能力按「没有」处理——同步读回 `null`、订阅回空退订函数、不调用 `getAppearance`、不抛错。
- `getAppearance` 存在但不是函数：同上（回 `null` / 空退订），不调用。
- `getAppearance()` 抛错：同步读回 `null`、不抛到调用方。
- `getAppearance()` 回值不是对象（`null`、`undefined`、字符串、数字）：回 `null`。
- 回值里 `theme` 非法（如 `"neon"`、`null`、数字）：该字段取缺省 `'dark'`，另一个字段照常取用；`density` 非法时该字段取缺省 `'standard'`。同步读**不因单个字段非法而整体回 `null`**。
- 事件里 `theme` 非法 → 只忽略这一个字段（`density` 合法仍生效）；`density` 非法 → 只忽略这一个字段；事件实参不是对象 → 整个忽略。
- 宿主缺 `getAppearance`/`onAppearance`/`saveTheme`（旧宿主）：对应能力按「没有」处理——读回 `null`、订阅回空退订、保存档落到下一档；不调用、不抛错。
- `saveTheme` 的信封是 `{ ok: false, reason }`（写盘失败等）：保持原主题、不弹提示；`reason` 原文照收，不自己拼前缀。
- `saveSettings({ theme })` 被拒（外壳回 `{ ok: false, reason }` → preload 以 `new Error(reason)` reject）：保持原主题、不弹提示；错误文案只取 `message`，不自己加前缀。
- 外观事件来时正好组件已卸载：退订之后不再收到，不报错。

### 错误与重试
- 外观的读、订阅、保存都不抛错给调用方：读回 `null`、订阅回空退订、保存档不可用就往下退一档。
- 同步读没有重试（宿主与桥的同步读是一次调用，不重试）。
- 保存失败**不重试**，保持原主题、不弹提示（标题栏菜单里没有放错误的位置；设置页自己那条提示照旧，不在本片）。
- 事件订阅失败（`on`/`onAppearance` 抛错）不重试，回空退订函数。

### 并发、取消与状态变化
- 同步读与订阅之间可能漏掉一个外观事件（极小的窗口）；**不加补偿逻辑**，漏了就漏了。
- 事件与本地保存并发：以事件为准（事件里的值逐字段校验后覆盖）；两个窗口同时保存由外壳决定后写的那次，本片不排队、不去重。
- 服务窗口整页重载（`reauth`）后 preload 重跑，页面再次同步读当前外观。
- 组件卸载时退订（宿主档或桥档 whichever 订上了）。

### 兼容性
- `window.themisHost` 与 `window.themisShell` 的既有成员与行为不变；前端只**新增**读取点，不改外壳的暴露面。
- `interface ThemisShell` 仍是十个成员；`desktop/shell` 的 `shellpreload.test.js` 与 `tests/test_gate_t030_baseline.py` 的 P04 探针（暴露面 = 解析出的十个成员 + `getAppearance`）原样绿——所以 `themisShell.ts` 里**不许**把 `getAppearance` 加进 `interface ThemisShell`。
- `shellBridge.ts` 的 `SHELL_MEMBERS`（十个名字）、包装与 `on` 的转发、`unavailableShell()` 的九个被拒方法与空退订，一行都不改；只新增两个导出。
- `hostSettings.ts` 的 `hostHasOpenSettings()`、`hostOpenSettings()`、`HostEnvelope` 的既有形状与 T060 S06 要求的记号（`hostOpenSettings`、`themisHost`、`openSettings`、`typeof x !== 'function'`）都留着。
- `App.tsx` 的既有渲染照旧；`ThemePrefProvider` 的 props 不变。
- 过渡断言一条不退役：`tests/test_gate_t012_baseline.py::test_transitional_d08_theme_sync_through_app`（标题栏选跟随系统不再调 `saveSettings`——桩模式下桥与宿主都没有，仍走第三档）、`test_transitional_d08_appearance_without_provider`、`tests/test_gate_t032_baseline.py::test_transitional_s09_baseline_files_untouched` 与 `test_transitional_p2_probe_bridge` 等，全部照旧绿。
- 旧测试文件一个不改；新行为写进两个新测试文件。

## Steps
1. 读「Repository facts」列出的文件，确认签名与基线一致；不一致就停止并报告。
2. `desktop/web/src/shell/theme.ts`：加 `DensityPref` 与 `applyDensity`（标准去属性、紧凑写 `compact`），改头注释（「偏好只存内存」这句去掉），`applyTheme` 一行不动。
3. `desktop/web/src/components/Table.css`：在现有三条行高规则之后追加三条紧凑规则（40→32、44→36、52→44），每条同一行带出处注释；其余一行不动。
4. `desktop/web/src/shellpages/themisShell.ts`：只加 `export interface ShellAppearance { theme: 'system' | 'light' | 'dark'; density: 'standard' | 'compact'; }`（带一行说明注释）；`interface ThemisShell` 与其它类型一个字不动。
5. `desktop/web/src/shellpages/shellBridge.ts`：另导出 `shellAppearanceNow()` 与 `shellOnAppearance(listener)`（能力判据、逐字段校验、空退订如上）；`SHELL_MEMBERS`、包装、`unavailableShell`、`resetShellBridge` 一行不动。
6. `desktop/web/src/live/hostSettings.ts`：另导出 `hostGetAppearance()`、`hostOnAppearance(listener)`、`hostSaveTheme(pref)`；`HostEnvelope` 补 `value?` 字段；沿用 `hostBridge()` 的类型断言写法；既有导出与记号一行不动。
7. `desktop/web/src/App.tsx`：主题与密度两个状态（懒初值：宿主 → 桥 → 缺省暗/标准）、根上订阅外观事件（逐字段校验）、`useLayoutEffect` 写属性、标题栏三档保存、`ThemePrefProvider` 的 `onThemeChange` 仍给 `setTheme`；既有渲染与 props 照旧。
8. `desktop/web/README.md:59`：改掉「偏好只存内存」，写清四点（外壳保存、启动同步读、改了广播、紧凑 40/44/52 各降 8），保留「主题」「标题栏」两词。
9. 新测试：`desktop/web/tests/appearance-units.test.ts`（theme.ts 的 `applyDensity`；Table.css 三条规则与取值；shellBridge 两个新函数的缺成员/非函数/抛错/非法值/退订/十成员旧壳仍算有外壳；hostSettings 三个函数）与 `desktop/web/tests/appearance-app.test.tsx`（App 的桩模式、服务窗口（假宿主给亮+紧凑）、设置窗口（十成员假外壳加外观成员）、事件对齐、保存三档、非法取值被忽略、卸载退订、静态断言 App 用 `useLayoutEffect` 写属性且没有禁词）。
10. 运行 Validation commands 里与改动相关的检查，记录命令与结果。
11. 写执行报告；遇到合同未定义的行为，停止并报告。

## Validation commands
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run build` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`built in`
- V03（必要）：`npm run check:contract` · cwd：desktop/web · 超时：300s · 期望退出码：0 · 输出须匹配：`契约检查：通过`
- V04（必要）：`npm test` · cwd：desktop/shell · 超时：600s · 期望退出码：0 · 输出须匹配：`# pass \d+`，不得出现：`# fail [1-9]`
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t063_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py tests/test_gate_t050_baseline.py tests/test_gate_t051_baseline.py tests/test_gate_t052_baseline.py tests/test_gate_t053_baseline.py tests/test_gate_t054_baseline.py tests/test_gate_t055_baseline.py tests/test_gate_t056_baseline.py tests/test_gate_t057_baseline.py tests/test_gate_t058_baseline.py tests/test_gate_t059_baseline.py tests/test_gate_t060_baseline.py tests/test_gate_t061_baseline.py -q` · cwd：仓库根 · 超时：3600s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：主题与密度各只有一个写入口——`theme.ts` 的 `applyTheme`/`applyDensity` 写属性，标准密度去掉 `data-density`、紧凑写 `compact`，不碰类、内联样式、body 与存储；证据：V01、V03；目的：密度这块「标准要去属性」的半边最容易漏，漏了就变成标准也带属性。
- D02：紧凑时数据表行高 40/44/52 变成 32/36/44，表头与没写 `data-row-height` 的表格不动，三条规则各带同行出处注释；证据：V01、R01；目的：紧凑要真的把数据表压下去，且不误伤表头与别的表格。
- D03：外壳页能同步读外观、能订阅外观事件——十成员齐全且 `getAppearance` 是函数才调；缺成员/非函数/抛错/回值不是对象分别回 `null` 或空退订；十成员的旧假外壳仍被认作有外壳；退订真的能退；证据：V01；目的：别把「旧外壳」误判成「没有外壳」，也别在能力不存在时抛错。
- D04：服务窗口能同步读外观、能订阅外观事件、能保存主题——三个宿主函数在能力缺失时回 `null`/空退订/落到下一档；`saveTheme` 恰好调一次、只转交 `pref` 一个实参、信封原样；证据：V01、R01；目的：服务窗口标题栏的菜单要真能存下主题。
- D05：页面用宿主给的外观起步、跟着外观事件变——初值宿主优先、其次桥、都没有暗+标准；事件逐字段校验（非法字段忽略）；桩模式下根元素不多属性、标题栏只改内存、不写存储；证据：V01、R01；目的：外观要跨窗口一致，且开发与测试里的夹具模式行为一个字不变。
- D06：标题栏的主题菜单按三档保存——宿主保存 `ok:true` 才切、桥保存兑现后才切、都没有只切内存；保存失败保持原主题、不弹提示；证据：V01；目的：菜单点了要有效果，失败时不假装成功。
- D07：`themisShell.ts` 只补类型、`interface ThemisShell` 仍恰好十个成员、外壳侧一个字没改；类型检查与构建通过，外壳单测全过；证据：V02、V04、R01；目的：类型文件与外壳暴露面不能被这一片弄歪。
- D08：README 改掉「偏好只存内存」，写清外壳保存、启动同步读、改了广播、紧凑 40/44/52 各降 8，并保留「主题」「标题栏」两词；证据：R01、review；目的：下一片照 README 就能对齐名字与字面量。
- D09：所有修改都在允许集合内；没有退役任何过渡断言、没有改任何既有测试文件与门禁文件；证据：scope、review；目的：本片放开的只是「前端能读外观」，别的门禁强度不因它下降。
- D10：新行为都有用例与门禁基准钉住——applyDensity、Table.css 三条规则、shellBridge 与 hostSettings 的失败分支、App 的桩模式/服务窗口/设置窗口/事件对齐/保存三档/非法取值/useLayoutEffect 静态断言；证据：V01、G01；目的：过了检查不是目标，这些行为各自有独立证据才算数。
- D11：站主真窗口冒烟三段通过（预置亮+紧凑启动后服务窗口根即 light/compact、40/44/52 量出 32/36/44；设置窗口单选显示「亮」「紧凑」；两个窗口双向改动互通；重启读回；settings.json 不写外观时两窗都暗+标准）；证据：review；目的：jsdom 不排版也不闪，首帧与真实行高只能靠真窗口看。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（特别是 `window.themisHost`/`window.themisShell` 的成员名与形状、外观对象的字段、saveTheme 的信封、`interface ThemisShell` 的十成员）。
- 必须修改允许范围之外的文件才能继续（例如必须改 `desktop/shell/**`、`desktop/web/src/shellpages/SettingsView.tsx`、既有测试文件或门禁文件，或必须改 `package.json` 才能过检查）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限（1800 秒）。

## Budget
- max_attempts_total: 4（按 task-id 汇总，包括返工版本；本片已用 0 次）
- max_wall_seconds_per_attempt: 1800
- max_wall_seconds_total: 7200
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读代码与定位门禁 6 分钟；实现 7 个源码文件 12 分钟；补两个新测试文件 8 分钟；跑 V01–V04 必要检查 4 分钟；写执行报告 2 分钟；总计约 32 分钟（不超过单轮时限 1800 秒）。若第一次超时，第二次只做定点补齐，不缩范围。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D11，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块；报告里没有内容的字段写空数组（例如 `contract_conflicts`、`interpretations`）。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过；不退役任何既有门禁断言；不改既有测试文件与门禁文件。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
- 不碰 `desktop/shell/**`、`desktop/web/src/shellpages/SettingsView.tsx` 与 T032 冻结名单里的任何文件。
- 不在 `App.tsx` 里出现 `themisShell`（子串）、`themisHost`、`declare global`、`localStorage`/`sessionStorage`、`window.open`/`window.confirm`、`ServerIcon`、`liveModeIsReal`、`liveClient`、`data-theme`（含注释）。
- 不在 `theme.ts` 之外写 `data-theme`、不在 `theme.ts` 之外写 `data-density`。
