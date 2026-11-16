# TASK: t046-desktop-web-quizs-profile

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: 19b45497ca7b42d4aefd0f2a937e188e5a15de79
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
给 profile 新建/编辑表单接上 quizs 运行时：所选运行时的适配器是 quizs 时，模型从 `getQuizsProviders` 的已批准提供方档案里选（显示与交给服务端的都是 `provider/model` 一段），思考档位只给该档案允许的那几个；档案读不出、模型不在档案里、凭据这几条分支各有定好的表现。其余运行时的控件、文案、命令、请求一字不变。

## Non-goals
- 不改 `src/api.ts`、`src/mock/*`（不新增 JSON，运行时列表不变）、`useWriteFlow`、`useLivePreview`、`WriteConfirmDialog`、`snapshots`、任何页面文件、`profileRules.ts` 的正则、`ts/packages/ui`（服务端）与内核。
- 不做岗位「拿到了什么」（档位三值、回合预算、工具面、证书状态）、不做凭据录入/续期/认证、不给页面加按钮。
- 不做设计文档 `docs/themis-tally-3.0-模型配置.md` §4 例子（档案 id 写法）的修订；本片一律按 `provider/model` 一段。
- 不改 `desktop/web/tests/writes-profile-form.test.tsx`（一个字都不改），不改任何既有门禁测试，不改 `tests/test_gate_t046_*.py`。

## Repository facts
以下事实均在基线 `185d077722609384f479a9b981fec6fc18ee8a68` 的工作目录里核对过（只读读文件；本回合未运行 npm/pytest）。
- 数据层（T043 已合入）：
  - `desktop/web/src/api.ts:510-514`：`getQuizsProviders(): Promise<Envelope<QuizsProvidersData>>`；真实分支 `client.get<QuizsProvidersData>('/api/v1/quizs/providers', undefined, 60)`（不回落桩）；桩分支 `read(['config','quizs','providers','--json'], () => quizsProvidersEnvelope())`。
  - `desktop/web/src/api.ts:162-167`：`QuizsProviderRow { provider: string | null; model: string | null; thinking: string[]; billing: string }`；`:168-170`：`QuizsProvidersData { providers: QuizsProviderRow[] }`。枚举外的值是字面量 `<redacted>`（按普通字符串处理，不用字面量联合类型挡在类型外）。
  - `desktop/web/src/api.ts:499-505`：`getRuntimes(): Promise<Envelope<RuntimesData>>`；`:126` `RuntimesData = typeof runtimesJson`；`desktop/web/src/mock/runtimes.json` 每行键为 id、adapter、source、command、notes（pi、claude-code、opencode 三行，适配器与 id 同名）。
  - `desktop/web/src/api.ts:386-391` 的 `read()`：`?mock=loading` 挂起、`?mock=error` 回错误信封（`ok:false`、`data:null`、messages 一行），其余情景由 `produce` 给。
- 桩与情景：
  - `desktop/web/src/mock/quizs.ts`：`QuizsScenario = 'ok' | 'expired' | 'missing' | 'broken' | 'empty'`；`quizsScenario()` 读 `location.hash` 查询串里的 `quizs` 键，缺省或认不出按 `ok`。
  - ok 情景的 providers 两行：`{ provider:'stepfun', model:'step-5-preview', thinking:['low','medium','high'], billing:'step_plan_credits' }`、`{ provider:'deepseek', model:'deepseek-chat', thinking:['low','high'], billing:'deepseek_prepaid_balance' }`。
  - broken 情景的 providers 信封：`ok:false`、`exit_code:1`、`data:null`、messages 恰好一行「ERROR: 没有设置 QUIZS_CMD，读不到 Quizs 提供方档案」。
  - empty 情景的 providers：`{ providers: [] }`（信封 `ok:true`）。
- 服务端白名单：`ts/packages/ui/src/redaction.ts:121` `QUIZS_THINKING_ENUM = allowEnum("off","low","medium","high","xhigh","max")`（六值，**没有 minimal**）；`:156-161` `QUIZS_PROVIDERS_ALLOW` 只登记 provider、model、thinking[*]、billing；`id` 与 `build_id` 未登记（前端拿不到，也不显示）。
- 表单现状（`desktop/web/src/writes/ProfileForm.tsx`）：
  - runtime 下拉只取 `getRuntimes()` 每项的 id；`THINKING_OPTIONS` 固定七段（off、minimal、low、medium、high、xhigh、max）；模型是手填 `TextField`，带 `MODEL_HELP = '手填的模型没有核实'` 与 `MODEL_ERROR`；`validModel` 来自 `writes/profileRules.ts`（两段正则，本片不改）。
  - `desktop/web/src/writes/profileRules.ts:10` `MODEL_SEGMENT_RE = /^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$/`；`:21-25` `validModel` 在第一个 `/` 处切成两段，两段各过一遍正则才为真。**两段里 `-` 合法**：`p/no-slash` 两段都合法（`validModel('p/no-slash') === true`），只有不含 `/` 或某段含正则之外的字符（如 `p!`、`p/m!`）才过不了。
  - `makeInitial`：`edit` 分支模型初值是 `${provider}/${model}` 一段、thinking 缺省时显示 `high`；`new` 分支 `id:'', runtime:'', model:'', thinking:'high', creds:[]`。
  - `canPreview = fieldValid && hasRuntime && !clearingCred && hasChanges`；`thinkingChanged = thinking !== initial.thinking`；`buildArgs` 现在只传与初值不同的字段（新建时传 runtime、model），`if (thinkingChanged) args.thinking = thinking;`；`useLivePreview(action, args, enabled)`（300ms 防抖）。
  - 底部渲染次序照旧：没有 runtime → 「先登记 runtime」；`clearingCred` → 「内核没有清空凭据变量的写法」；字段不合法 → 空；没改动 → 「还没有改动」。
- 组件接口：`components/SegmentedControl.tsx` 受控（`options` + `value` + `onChange`），**value 不在 options 里时没有任何段是 `aria-checked="true"`**；`components/Select.tsx` 是原生 `select`（`options` 的 value/label、`error` 会带 `aria-invalid`）；`components/TextField.tsx` 支持 `label`、`help`、`error`、`mono`、`readOnly`。
- 其它接口（T044/T045 尚未合入，接口照旧）：`writes/useWriteFlow.ts` 的 `useWriteFlow(reload?) → { start, flow }`；`writes/useLivePreview.ts` 的 `useLivePreview(action, args, enabled) → { result, current }`（300ms 防抖）。
- 内核与 hub 的口径：`scripts/kit_config.py:1646` `config profile add --model <provider>/<模型 ID>`；config 键 `profiles` 的 model 存成 `{provider, id}`（内核把一段拆成两段）；`scripts/kit_hub.py:2573` quizs 回合的命令是 `quizs worker turn --provider <短名> --model <模型> --thinking <档位>`；`scripts/kit_hub.py:661` `QUIZS_PROFILE_IDS = {"deepseek":"deepseek-api","minimax":"minimax-m-plan","stepfun":"stepfun-cn-step-plan"}` 只把短名映射到档案 id（live 文件用）。**所以模型值写 `provider/model`，provider 用档案的短名（stepfun、deepseek），不用档案 id。**
- 与规划不同的地方（按新基线改写）：规划写档案第二行是 `deepseek/deepseek-flash`，新基线的桩是 `deepseek/deepseek-chat`；规划以为「读不出档案·无可选项」只能由纯函数覆盖，新基线的桩有 `empty` 情景（`?quizs=empty`），这一分支由桩情景测。
- 门禁事实：
  - `tests/test_gate_t024_baseline.py:128` `NETWORK_WORDS = ("fetch","XMLHttpRequest","EventSource","WebSocket")`：`src` 下（含注释）不许出现；`:108-114` `WRITES_TEXTS` 要求既有逐字文案保留在 `src/writes`；`src/mock` 仍恰 14 份 JSON；`src/pages` 顶层仍恰 9 个 `*Page.tsx`；既有 `desktop/web/tests/writes-profile-form.test.tsx` 钉着三个运行时与七档，**不改**。
  - `tests/test_gate_t041_baseline.py:336-351`：`src/writes` 里除 ProfileForm 原有的「先登记 runtime」外，不许出现「登记 runtime」。
  - `tests/test_gate_t009_baseline.py`：每份 CSS 要有自己独有的类名且打进构建产物；CSS 里除 `0` 与 `1px` 外的 px 字面量，所在行要带出处注释；不许十六进制颜色与颜色函数。
  - `desktop/web/tests/writes-runtime-api.test.ts:12-44`：`setLiveClientForTests(fakeClient)` 是测试里切到「真实模式」的既有写法（`desktop/web/src/live/mode.ts` 导出）。
  - `desktop/web/package.json`：`npm test` = `vitest run`；`npm run typecheck` = `tsc --noEmit`；`npm run build` = `tsc --noEmit && vite build`。

## Scope
- allowed_modified_files:
  - desktop/web/src/writes/ProfileForm.tsx
  - desktop/web/src/writes/profile-form.css
- allowed_new_files:
  - desktop/web/src/writes/quizsProfile.ts
  - desktop/web/tests/writes-profile-quizs-logic.test.ts
  - desktop/web/tests/writes-profile-quizs.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t046_*.py
  - desktop/web/src/api.ts
  - desktop/web/src/mock/**
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/writes/useLivePreview.ts
  - desktop/web/src/writes/WriteConfirmDialog.tsx
  - desktop/web/src/writes/profileRules.ts
  - desktop/web/src/writes/snapshots.ts
  - desktop/web/src/writes/RuntimeForm.tsx
  - desktop/web/src/pages/**
  - desktop/web/src/components/**
  - desktop/web/src/shell/**
  - desktop/web/src/live/**
  - desktop/web/tests/writes-profile-form.test.tsx
  - desktop/web/tests/live-api.test.ts
  - ts/packages/ui/**
  - scripts/**
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden

## Behavior contract
- 正常输入：
  - 认 quizs：按所选 runtime 的 id 在 `getRuntimes()` 的行里找那一行，**看它的 `adapter`** 等不等于 `quizs`（不看 id；id 叫 quizs 而 adapter 是 pi 的不算 quizs）；列表里找不到这个 runtime 时按非 quizs 走（现状）。runtime 下拉的选项照旧：value 与 label 都是 id，顺序照旧。
  - 读档案：对话框打开、且所选运行时的适配器是 quizs 时，调 `getQuizsProviders()` 一次（每次打开对话框只调一次，结果存在表单状态里）；非 quizs 运行时一次都不调（真实模式下多出来的请求为零）。几个 quizs 运行时共用同一份档案。读取中：写「正在读 Quizs 的提供方档案…」，**不调预览**，没有重试钮（重新打开对话框会重读）；关闭对话框时迟到的结果丢弃（照现有 `getRuntimes` 那一段的 alive 标志写法）。
  - 档案转模型选项（纯函数）：每一项的 value 与 label 都是 `${provider}/${model}`；跳过的行是 provider 或 model 不是字符串、是空串、是 `<redacted>`、或拼起来过不了 `validModel`（`validModel` 的口径是「两段都过 `MODEL_SEGMENT_RE`」，`-` 在字符类里，所以 `p/no-slash` 这类两段都合法的值**要留下**）；value 相同的只留第一项。档案里有一项以上时，模型控件是 `Select`（label 仍是「模型」），选项恰好是这些 `provider/model`；新建时模型为空 → 档案读到后自动选第一项；编辑时初值在档案里 → 照旧选中。
  - 档案转档位（纯函数）：`thinking` 是数组时，按原顺序取出属于 `QUIZS_LEVELS` 的元素并去重；`QUIZS_LEVELS` 是六值 `off`、`low`、`medium`、`high`、`xhigh`、`max`（照 `QUIZS_THINKING_ENUM`，**没有 minimal**）；`<redacted>` 自然不进；`thinking` 不是数组时档位为空。档位段照旧用 `SegmentedControl`（`aria-label="thinking"`）。
  - 交给服务端的模型值就是 `provider/model` 一段（与现在 `validModel` 的写法一致），预览命令里是 `--model=<provider>/<model>`。
- 边界输入：
  - 档位从**不自动改**：当前档位在所选档案允许的档位里 → 照旧选中；不在 → `SegmentedControl` 一个段都不选（value 不在 options 里），控件下写「<档位> 不在这个档案允许的档位里」，**不调预览**，[确认…] 不可点；用户点一个允许的档位之后恢复（该档位成为改动值）。编辑时 thinking 原来缺省、界面显示 high 而档案不含 high 的，同样处理。
  - **档位改动怎么传给内核（这一条写死，不再有两种读法）：quizs 分支里，用户显式点过档位段（`SegmentedControl` 的 onChange 触发过）之后，这一项就算「改动值」，`buildArgs` 一律带上 `--thinking=<当前档位>`，即使用户点的档位与打开时的初值相同（新建时初值是 `high`，点 `high` 也要传）；用户没点过时按现状处理（与初值不同才传）。非 quizs 分支的 `buildArgs` 一个字不改，仍然只传与初值不同的字段。**
  - 模型不在档案里（编辑一个档案外的 quizs profile，或先在别的运行时下手填了再切到 quizs）：原值作为**额外的第一项**照样显示并选中，用 `Select` 的 error 写「不在 Quizs 已批准的档案里」（带上 `aria-invalid`），**不调预览**；从档案里选一项之后恢复（error 消失）。这时档位给六值（档案不明）。
  - 有档案可选时不显示「手填的模型没有核实」；换回非 quizs 运行时，模型值留在原来那个文本框里，照旧按 `validModel` 校验，档位回到七段。
  - 读不出档案（三种）：信封失败（`!ok || data == null`）、Promise reject、ok 但转不出任何一项。文案：
    - 信封失败：「读不出 Quizs 的提供方档案」，后面接「：<messages 第一行>」（messages 非空时）；
    - reject：「读不出 Quizs 的提供方档案」；
    - 无可选项：「Quizs 没有列出可用的提供方档案」。
    这时模型退回原来那个手填 `TextField`（同样的 `MODEL_HELP`、`MODEL_ERROR`、`validModel`），档位给六值（off、low、medium、high、xhigh、max，无 minimal），**预览照常可用**（表单不卡死）。
  - 凭据：quizs 运行时不显示凭据输入框、[添加] 与已加的 Tag，原位换成一行短说明「凭据由 Quizs 保管」，外层 `role="group"`、`aria-label="凭据变量"`（保留无障碍名称）；`buildArgs` 对 quizs 一律不交 `credential_env`（免得把切换前在别的运行时下加的凭据悄悄交上去）；`credsChanged` 与 `clearingCred` 只在非 quizs 时算。**非 quizs 分支一个字都不动。**
  - 预览门控：`canPreview` 照原来的四个条件，再加三个只对 quizs 生效的条件——档案不在读取中；有档案时模型在档案里；档位在允许范围内。底部渲染次序照旧（字段不合法时底部为空，原因写在对应控件下）。
- 错误与重试：
  - 读档案失败不重试，没有重试钮；重新打开对话框会重读一次。
  - 档案读不出来不阻塞表单：模型退回手填、预览照常可用。
  - 档案里的档位为空（该档案没有 thinking 元素）时，与「档位不在范围内」同一表现（一个段都不选、写提示、不调预览、[确认…] 不可点），不另写代码。
- 并发、取消与状态变化：不适用——本片没有取消、没有并发写。档案的读取只有一次，迟到的结果按 alive 标志丢弃；表单状态是单线程的 useState。
- 兼容性：
  - `src/api.ts` 一个字不改（只用 `getQuizsProviders` 与它的类型，不 import `src/mock/*`）；`src/mock` 仍恰 14 份 JSON；`src/pages` 顶层仍恰 9 个 `*Page.tsx`；`package.json` 与锁文件不变。
  - 既有逐字文案保留在 `src/writes`（`MODEL_HELP`、`MODEL_ERROR`、`先登记 runtime`、`还没有改动` 等一个都不删不改）；`desktop/web/tests/writes-profile-form.test.tsx` 一个字不改，它钉着的三个运行时、七档与常显的「手填的模型没有核实」都照旧成立（非 quizs 时一字不变）。
  - 非 quizs 运行时的控件、文字、命令、请求一字不变；选 pi 时 `getQuizsProviders` 的调用次数是 0，表单里凭据输入仍恰一个。
  - `buildArgs` 的现行口径（只传与初值不同的字段，新建时传 runtime、model）在**非 quizs 分支一字不变**；quizs 分支只有一处例外：用户点过档位之后一律传 `--thinking=<当前档位>`（见边界输入里写死的那一条），其余字段的传法照旧。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。
2. **新增纯逻辑文件 `desktop/web/src/writes/quizsProfile.ts`**（只放纯函数；从 `../api` 只 `import type`；复用 `profileRules` 的 `validModel`）：
   - `export const QUIZS_LEVELS = ['off','low','medium','high','xhigh','max'] as const;`（六值，无 minimal）。
   - `export interface QuizsProviderOption { value: string; label: string; thinking: readonly string[] }`.
   - `export function isQuizsRuntime(runtimeId: string, runtimes: readonly { id: string; adapter: string }[]): boolean` —— 按所选 id 找行、看 adapter；找不到行返回 false。
   - `export function quizsProviderOptions(providers: readonly QuizsProviderRow[]): QuizsProviderOption[]` —— 按 Behavior contract 的规则转模型选项（跳过非字符串/空串/`<redacted>`/过不了 `validModel` 的行；同 value 只留第一项；`thinking` 按 `QUIZS_LEVELS` 过滤、保序、去重；`thinking` 不是数组时为空）。
   - `export function thinkingLevelsFor(option: QuizsProviderOption | null): readonly string[]` —— 有档案项就给它的档位；没有（模型不在档案里或档案不明）就给 `QUIZS_LEVELS` 六值。
   - `export function thinkingAllowed(value: string, levels: readonly string[]): boolean` —— 档位在不在允许范围。
   - `export function modelInArchive(value: string, options: readonly QuizsProviderOption[]): boolean` —— 模型在不在档案里。
   - 纯函数不碰 DOM、不引计时器、不读 `window`。
3. **`ProfileForm.tsx`：运行时行留适配器**——`getRuntimes()` 的结果存成 `{ id, adapter }[]`（原来只留 id 的数组改掉），下拉的选项仍照旧由 id 生成（value 与 label 都是 id，顺序照旧），`hasRuntime` 的判据照旧。
4. **`ProfileForm.tsx`：读档案的状态**——`useState` 存三态（读取中、成功、失败）；`useEffect` 照现有 `getRuntimes` 那一段的写法（`open` 依赖、alive 标志丢弃迟到结果）：打开且所选运行时是 quizs 时读一次；所选运行时不是 quizs 时不读；关闭对话框时丢弃迟到的结果。
5. **`ProfileForm.tsx`：模型控件**——按状态在三种形态之间切换：(a) quizs 且档案读到且有选项 → `Select`（label「模型」，options 是档案的 `provider/model`；新建时模型为空则自动选第一项；档案外的原值作额外第一项并照样选中；`error` 写「不在 Quizs 已批准的档案里」）；(b) quizs 且档案读不出 → 原来那个手填 `TextField`（`MODEL_HELP`、`MODEL_ERROR` 照旧）；(c) 读取中或非 quizs → 与 (b) 同样的手填 `TextField`（读取中另写「正在读 Quizs 的提供方档案…」）。**非 quizs 时的手填分支与现在一字不差。**
6. **`ProfileForm.tsx`：档位与门控**——`SegmentedControl` 的 options 按状态取：quizs 且模型在档案里 → 该档案允许的档位（过滤后保序）；其余情形 → `QUIZS_LEVELS` 六值；非 quizs → 现在的七段（`THINKING_OPTIONS` 一个字不改）。档位不在允许范围时，控件下写「<档位> 不在这个档案允许的档位里」并加一个类名（样式写进 `profile-form.css`）。**另加一个只在 quizs 分支使用的布尔状态（例如 `thinkingTouched`），在档位段的 `onChange` 里置真、随对话框重开复位；`buildArgs` 里：非 quizs 分支照旧 `if (thinkingChanged) args.thinking = thinking;`，quizs 分支改成「`thinkingTouched` 为真时一律 `args.thinking = thinking`，否则沿用 `thinkingChanged` 的旧判断」——即用户点过档位即算改动，即使点的档位与初值相同也照传 `--thinking=`。** `canPreview` 加上 Behavior contract 的三个 quizs 条件。
7. **`ProfileForm.tsx`：凭据**——quizs 时不渲染凭据输入、`[添加]` 与 Tag 区，原位渲染一行说明（`role="group"`、`aria-label="凭据变量"`）；`credsChanged`、`clearingCred` 与 `buildArgs` 里的 `credential_env` 只在非 quizs 时算。**非 quizs 的这段代码一个字都不动。**
8. **`profile-form.css`**——只追加新规则（不改现有规则）：新类名（如 `.pf-note` 给说明行、`.pf-warn` 给提示行）只用 `--tt-*` 令牌，不写十六进制颜色与颜色函数；除 `0` 与 `1px` 外的 px 字面量，所在行要带出处注释；新类名要在组件里真的用到（要打进构建产物）。
9. **测试 `desktop/web/tests/writes-profile-quizs-logic.test.ts`（新）**：`isQuizsRuntime`（含 id 叫 quizs 而 adapter 是 pi 的反例、找不到行）；`quizsProviderOptions`（`<redacted>` 与非字符串/空串的 provider、model 不进选项；过不了 `validModel` 的不进，**反例要真过不了**：`provider: 'p!'` 或 `model: 'm!'`；`{provider:'p', model:'no-slash'}` 是**合法**的（两段都过 `MODEL_SEGMENT_RE`，`-` 在字符类里），要留下、不许当反例）；同 value 只留第一项；档位按六值过滤保序去重；`thinking` 不是数组时为空）；`thinkingLevelsFor`（档案内的档位 / 档案外给六值）；`thinkingAllowed`；`modelInArchive`。
10. **测试 `desktop/web/tests/writes-profile-quizs.test.tsx`（新）**：照 `desktop/web/tests/writes-profile-form.test.tsx` 的 `vi.mock('../src/api')` 转调写法（`getRuntimes` 的替身给 `[pi, { id:'quizs-cli', adapter:'quizs' }]`），用 `?quizs=` 选情景：
    - `?quizs=ok` 新建：选 quizs 运行时后，模型是 `Select`，选项恰好是 `stepfun/step-5-preview` 与 `deepseek/deepseek-chat`，自动选中第一项；档位段恰好是 low、medium、high，high 选中；没有「手填的模型没有核实」；没有凭据输入框，有「凭据由 Quizs 保管」；预览命令里有 `--runtime=quizs-cli --model=stepfun/step-5-preview`；先在 pi 下加过凭据再切到 quizs，命令里没有 `--credential-env`。
    - `?quizs=ok` 新建、点过档位：用户点一下档位 `high`（新建初值就是 `high`）之后，命令里出现 `--thinking=high`（按合同写死的口径：点过即算改动）。
    - `?quizs=ok` 换档案：先选 stepfun 的 medium，再选 deepseek → 一个段都不选、有提示、预览调用次数不增加、[确认…] 不可点；点 high 之后命令里有 `--thinking=high`（新建初值是 high，点回初值也算改动，照传）。
    - `?quizs=ok` 编辑：档案内的 quizs profile 全都没改时写「还没有改动」；档案外的（例如 `stepfun/step-4`）原值照样选中、标「不在 Quizs 已批准的档案里」、不调预览；从档案里选一项之后命令只含 `--model`。
    - `?quizs=broken` 新建与编辑：写明原因（信封失败那一行）；模型是手填文本框、有「手填的模型没有核实」；档位六段且没有 minimal；手填之后照常预览。
    - `?quizs=empty`：写「Quizs 没有列出可用的提供方档案」，模型退回手填、档位六值。
    - 选 pi：`getQuizsProviders` 的调用次数是 0。
    - 真实模式：用 `setLiveClientForTests` 注入假客户端（照 `desktop/web/tests/writes-runtime-api.test.ts:12-44` 的写法），断言读的是服务回的信封、桩的档案（stepfun/step-5-preview）不出现。
    - 新测试不用 `skip`/`only`/`todo`；不新增依赖。
11. 跑 Validation commands 里的检查，顺序 **G01 → V01 → V02 → V03 → R01**（G01 的流水线会先在验证工作区的 `desktop/web` 里 `npm ci`，排在它前面的 `npm test`、`npm run typecheck` 找不到 vitest、tsc，基线上也是红的），记录命令与结果。
12. 写执行报告；遇到合同未定义的行为（例如服务回的字段形状与合同写的类型对不上），停下并报告，不要自己改合同。

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t046_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d+ passed`
- V02（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V03（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：非 quizs 运行时的表单行为一字不变——控件、七段档位、常显的「手填的模型没有核实」、命令与请求照旧；选 pi 时 `getQuizsProviders` 的调用次数是 0；表单里凭据输入仍恰一个。证据：V01、G01、R01；目的：这一片只加 quizs 的分支，别的一概不动。
- D02：认 quizs 靠适配器不靠 id——`isQuizsRuntime` 有「id 叫 quizs 而 adapter 是 pi」的反例；运行时列表里找不到所选 runtime 时按非 quizs 走。证据：V01、G01；目的：适配器才是「这个运行时是不是 quizs」的依据。
- D03：档案转选项的规则成立——模型项的 value 与 label 都是 `provider/model`；非字符串、空串、`<redacted>`、过不了 `validModel` 的行不进选项（`validModel` 是「两段都过 `MODEL_SEGMENT_RE`」，`-` 合法，`p/no-slash` 这样的行要留下）；同 value 只留第一项；档位按六值（off、low、medium、high、xhigh、max，无 minimal）过滤、保序、去重；`thinking` 不是数组时为空。证据：V01、G01；目的：服务只放行这些字段，越界值不能变成选项。
- D04：档位从不被自动改——当前档位不在所选档案允许的范围里时，一个段都不选、控件下写「<档位> 不在这个档案允许的档位里」、不调预览、[确认…] 不可点；用户点一个允许的档位后恢复，恢复后命令里带 `--thinking=<该档位>`（quizs 分支里点过即算改动，即使用户点的档位与初值相同；非 quizs 分支仍只传与初值不同的字段）。证据：V01、G01；目的：不悄悄交一个档案不认的档位。
- D05：档案外的模型照旧显示——原值作为额外第一项并选中，标「不在 Quizs 已批准的档案里」（`aria-invalid`），不调预览；从档案里选一项之后恢复。证据：V01、G01；目的：编辑旧 profile 时不悄悄改掉它原来的模型。
- D06：读不出档案时表单不卡死——信封失败、reject、无可选项三种情形各写明原因；模型退回手填文本框并照旧提示「手填的模型没有核实」；档位给六值（无 minimal）；预览照常可用。证据：V01、G01；目的：Quizs 跑不起来时这一页仍然能用。
- D07：凭据对 quizs 不适用——不显示凭据输入与 [添加]，写「凭据由 Quizs 保管」（`role="group"`、`aria-label="凭据变量"`）；`buildArgs` 不交 `credential_env`；非 quizs 分支一个字不动。证据：V01、G01、R01；目的：别把看不见的值悄悄交上去，也别让无障碍名称消失。
- D08：新建时自动选档案第一项；交给服务端的模型是 `provider/model` 一段（预览命令里有 `--model=stepfun/step-5-preview`）；档位按档案给。证据：V01、G01；目的：值与内核（`config profile add --model <provider>/<模型 ID>`）和 hub（`--provider` 短名）对得上。
- D09：真实模式下不出现桩的档案——注入 live 客户端后读的是服务回的信封，桩数据不出现。证据：V01、G01；目的：真窗口里不能拿演示数据当已批准的档案。
- D10：门禁红线一条都不破——`src/writes` 里除 ProfileForm 原有的「先登记 runtime」外没有「登记 runtime」；`src` 下（含注释）没有 `fetch`、`XMLHttpRequest`、`EventSource`、`WebSocket`；`src/mock` 仍恰 14 份 JSON；新 CSS 类名只用 `--tt-*` 令牌、不写颜色函数、带 px 的行有出处注释，且打进构建产物；`desktop/web/tests/writes-profile-form.test.tsx` 一字不改。证据：G01、R01、V03；目的：不破 T024、T041、T009 的长期门禁。
- D11：所有修改都在允许集合内（可改 2 个文件、可新增 3 个文件），没有碰 forbidden_paths；`package.json` 与锁文件不变、没有新增依赖。证据：scope、G01、R01；目的：这一片不许顺手改别的片的地盘。
- D12：既有测试没被删、跳过或弱化；新测试不用 `skip`/`only`/`todo`；`desktop/web` 的 `npm test` 与 `npm run build` 全绿。证据：V01、V03、review；目的：过了检查不等于目标，目标是新功能可用而旧行为没松。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `getQuizsProviders` 不导出、`QuizsProviderRow` 的字段不是 provider/model/thinking/billing、`mock/quizs.ts` 没有 ok/broken/empty 情景、`useWriteFlow`/`useLivePreview` 的签名与合同写的不同）。
- 必须修改允许范围之外的文件才能继续（例如要动 `src/api.ts`、`src/mock/*`、`useWriteFlow`、`useLivePreview`、`WriteConfirmDialog`、既有门禁测试或 `writes-profile-form.test.tsx`）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如要在本片加写入口、显示服务未放行的字段、或让档位自动改）。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id 汇总，含返工版本；累计已用 0 次——本版留 2 次实现与定点返工，余量 1 次）
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 16200（3 次 × 5400；累计已用 0 秒，本版可用 16200 秒 ≥ 2×5400）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读现有代码与核对事实 20 分钟；实现（纯逻辑、ProfileForm 三处接线、CSS）70 分钟；补测（纯逻辑 100 行、组件 250 行）50 分钟；必要检查（G01、V01、V02、V03、R01）50 分钟；最终报告 15 分钟；总计约 205 分钟，单轮时限 5400 秒。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D12，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
