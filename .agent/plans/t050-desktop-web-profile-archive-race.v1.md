# TASK: t050-desktop-web-profile-archive-race

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 5884c3d1fcfef75e150df9192b7390ecd1c125d1
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
新建/编辑 profile 的表单对话框里，用户选了 quizs 运行时之后，Quizs 提供方档案**总能读到**：模型变成档案下拉、档位按档案给、[确认…] 照常可点——不管 `getRuntimes()` 回来与用户选运行时的先后，也不管读档案途中 effect 因为运行时列表换数组而重跑。读完了的（同一次打开里）照旧只读一次、迟到的结果照旧丢弃、非 quizs 照旧一次都不调、重新打开照旧重读。

## Non-goals
- 不改读运行时的 effect（依赖 `[open, mode]`、回来时 `setRuntimes` 与新建模式选第一项）、不改运行时列表的存法、不跨次打开缓存档案。
- 不改读档案 effect 的依赖数组（仍是 `[open, runtime, runtimes]`）。
- 不改 `ProfileForm.tsx` 的导出形态（`NewProfileAction({reload?})`、`EditProfileAction({profile, reload?})`）、不改逐字文案（t046 的六条新文案、七条旧文案、七段 THINKING_OPTIONS 一个字都不动）。
- 不改 `desktop/web/src/api.ts`、`src/mock/**`、`src/components/**`、`src/pages/**`、`src/live/**`、`App.tsx`、`src/writes/` 里除 `ProfileForm.tsx` 以外的文件；不改 `ts/packages/ui` 与内核。
- 不加读档案的重试按钮、超时、缓存；不做凭据录入、资格认证、续期按钮（M6）。
- 不放宽任何门禁断言；不改 `tests/test_gate_*.py`（含本片的 `tests/test_gate_t050_*.py`）；不删、不跳过、不弱化既有测试。
- 不新增或升级依赖；`desktop/web/package.json` 与 `package-lock.json` 一个字节都不动。

## Repository facts
（本回合只读探查；合同端没有命令执行工具，**没有跑** npm/pytest。下面每条都给得出文件与行号。）

### 入口与现状
- `desktop/web/src/writes/ProfileForm.tsx`（416 行）：
  - `:120-138` 读运行时的 effect：依赖 `[open, mode]`；`:124` 调 `getRuntimes()`；`:128` 回来时 `setRuntimes(rows)`（每次都是新数组）；`:129` 新建模式 `setRuntime((cur) => cur || rows[0]?.id || '')`；`:132` reject 时 `setRuntimes([])`（也是新数组）。
  - `:140-172` 读档案的 effect：依赖 `[open, runtime, runtimes]`；`:142` `const archiveRead = useRef(false)`；`:144-149` `!open` 分支把 `archiveRead.current` 复位成 false 并 `setArchive(null)`；`:150` `if (!isQuizsRuntime(runtime, runtimes) || archiveRead.current) return;`；`:151` **发请求时**就把 `archiveRead.current` 置真；`:152` `let alive = true`；`:153` `setArchive({ kind: 'loading' })`；`:154-168` `getQuizsProviders().then(成功分支, 失败分支)`（成功分支 `:156` 先 `if (!alive) return;`）；`:169-171` 清理函数**只**把 `alive` 置假。
  - `:226-229` 新建模式且模型为空时，档案读到后自动选档案第一项；`:249-253` `quizsBlocked = quizs && (archiveLoading || modelOutsideArchive || thinkingOutOfRange)`（读取中时 [确认…] 灰着）。
  - `:396-402` `NewProfileAction` 一直挂着 `ProfileFormDialog`，只切 `open`：两次打开之间组件不卸载，`runtimes`、`runtime`、`archive` 这些状态都留着；`:407-415` `EditProfileAction` 同理。
- 卡住的机制（站主登记的顺序，第二次打开）：`runtimes` 还是上一次的旧数组、`runtime` 是上次的值 → 用户在 `getRuntimes()` 回来之前就选了 quizs 运行时 → effect 读档案（`archiveRead.current` 置真，`archive` 变 loading）→ `getRuntimes()` 回来、`setRuntimes` 换了新数组 → effect 重跑：清理把还在路上的结果作废，重跑时 `archiveRead.current` 已是真，不再读 → `archive` 永远停在 loading，界面一直写「正在读 Quizs 的提供方档案…」，[确认…] 灰着。
- 第一次打开不撞：运行时下拉还没有可选项（`runtimes` 是空数组），用户没法提前选；`getRuntimes()` 回来时 `setRuntimes` 与 `setRuntime` 同一批提交，effect 只跑一次。

### 同根的另外两条触发路径（本片一并修好）
- 取消后重开（不用抢先操作）：取消不调 `resetForm`（`:174-188` 只在成功后清空），`runtime` 留着上次选的 quizs 运行时；重开时读档案的 effect 用旧 `runtimes` 判成 quizs，打开当场就发请求，只要 `getRuntimes()` 先回来就卡住。编辑模式一样（`EditProfileAction` 的 `runtime` 初值就是 quizs 运行时）。
- 读档案途中切换：切到非 quizs 再切回（或在两个 quizs 运行时之间切换）：第一次切换引起的重跑把在途结果作废；切回 quizs 时 `archiveRead` 仍为真，所以不读 → 卡住。

### 包内测试现状（`desktop/web/tests/writes-profile-quizs.test.tsx`，355 行）
- 现有断言（行号已核）：`:145`「选了 quizs 运行时读一次档案」= 1；`:153`「重新打开对话框会重读」= 2；`:222`「换回非 quizs 不再读档案」= 1；`:303-312`「读取中：写「正在读 Quizs 的提供方档案…」，不调预览」；`:323`「非 quizs 一次都不调」= 0。
- 模块级助手（都已存在，追加用例时直接用，**不改 import、不改原有用例**）：`buttonByText`(:88)、`controlByLabel`(:91)、`thinkingGroup`(:99)、`segTexts`(:100)、`checkedSeg`(:101)、`segByText`(:102)、`modelOptions`(:104)、`envLabels`(:105)、`formConfirm`(:106)、`settle`(:107)、`advance`(:113)、`set`(:117)、`spyCalls`(:119)、`openNew`(:120)、`openQuizsNew`(:127)、`openEdit`(:134)；常量 `SIX`(:34)、`QUIZS_PROFILE`(:35)、`INSIDE_PROFILE`(:36)；`runtimesEnv()`(:40-53) 返回**已兑现的 promise**，信封里有 `pi` 与 `quizs-cli` 两行（第二行 adapter 是 quizs）。
- `beforeEach`(:54-59)：清 override、清 spy、`set('getRuntimes', runtimesEnv)`；`afterEach`(:60-65)：`cleanup()`、真计时器、哈希清空。

### API 与夹具
- `desktop/web/src/api.ts`：`:386-391` `read()` 在桩模式返回 `Promise.resolve(...)`（已兑现）；`:612-618` `getRuntimes()`；`:623-627` `getQuizsProviders()`（桩模式走 `quizsProvidersEnvelope()`）。
- `desktop/web/src/mock/quizs.ts`：`:19-22` `PROVIDER_ROWS` 两行——`{provider:'stepfun', model:'step-5-preview', thinking:['low','medium','high'], billing:'step_plan_credits'}` 与 `{provider:'deepseek', model:'deepseek-chat', thinking:['low','high'], billing:'deepseek_prepaid_balance'}`；`:84` 导出 `quizsProvidersEnvelope()`，ok 信封形状是 `{ok:true, exit_code:0, data:{providers:[…]}, output:[], messages:[], command:[…], elapsed_ms:0}`。
- `desktop/web/src/writes/quizsProfile.ts`：`isQuizsRuntime(runtime, runtimes)` 按**适配器**认 quizs（不按 id）。

### 门禁事实（逐条读过原文）
- `tests/test_gate_t046_baseline.py`：`:285-325` S02 只查 `ProfileForm` 调了 `getQuizsProviders`、用了 `quizsProfile` 的六个导出、`ProfileForm` 不 import `src/mock/*`；`:128-134` `EXECUTOR_TEST_TOKENS`（`writes-profile-quizs.test.tsx` 必须留住 9 个记号——追加用例不删记号即可）；`:521-660` 的 form 探针里「选了 quizs 运行时读一次档案」= 1、「重新打开对话框会重读」= 2，`:768-776`「非 quizs 一次都不调」= 0，`:809-818` 挂起的读；S04 查记号与 skip/only/todo。S02 不查 effect 的写法。
- `tests/test_gate_t024_baseline.py`：`:99-104` `BAD_ENTRY_TEXTS` 与 `:108-114` `WRITES_TEXTS` 只作用在**入口文件**（`RolesPage.tsx`、`roles-ProfilesTable.tsx`）与 `src/writes/` 全文的逐字表；`ProfileForm.tsx` 里现有逐字文案一个都不许删（`:291-296`）。
- `tests/test_gate_t041_baseline.py`：`:338-345` 的禁字（已登记运行时 / 登记 runtime 等）只作用在入口文件；`ProfileForm.tsx` 的字段提示「先登记 runtime」是基线文案。
- 字节冻结：t043–t049 的 `BASELINE_DIGESTS` 里**没有** `ProfileForm.tsx` 与 `writes-profile-quizs.test.tsx`（本片可以改这两份）；t048 冻结 `api.ts`、两份桩、`roles-styles.css`、三份既有包内测试（含 `page-app.test.tsx`）与两份依赖文件。

### 已核实的仓库外事实（内核记录）
- `desktop/web` 已装 `react` 与 `react-dom` 都是 **18.3.1**；`@testing-library/react` 是 **16.1.0**。
- `act(async 回调)` 在回调的 promise 兑现之前，把期间排的更新都压在 `ReactCurrentActQueue` 里（react-dom 的 `scheduleCallback$1` 见到 act 队列就推进去，不走 Scheduler）；等回调兑现之后才 `recursivelyFlushAsyncActWork` → flush。**推论**：测试里 `settle()` 的那一次 `act` 中，两个**已兑现** promise 的 `.then` 都会在 React 提交之前跑完。
- `@testing-library/react` 的 `fireEvent` 用同步的 `act` 包住事件派发：派发引起的渲染与 effect 在 `fireEvent` 返回前就提交；effect 里 `.then` 的回调要等下一次 `await`（测试里的 `settle()`）才跑。
- 由此得出的两条写作要点（合同据此规定新用例）：
  1. **要复现这个竞态，两个读函数必须手动兑现**（`getRuntimes` 与 `getQuizsProviders` 都返回测试自己掌握兑现时机的 promise）。若两个读都用桩（已兑现），`settle()` 里两件事都先做完，竞态复现不出来，新用例在未修的实现上也是绿的——这样的用例不算数。
  2. 现有 `:153` 与 t046 探针的「重开 = 2 次」在修好后**仍是 2 次**（两个桩 promise 在同一次 act 里先兑现，档案那次已经 settled，复位不生效），所以这两条断言一条都不用改。

### 基线检查
- 本回合（合同端）只读探查，没有运行 npm/pytest。
- 工作目录里 `desktop/web/node_modules` 不存在；执行端需要按现有锁文件装（见 Setup 的 S01）。

## Scope
- allowed_modified_files:
  - desktop/web/src/writes/ProfileForm.tsx
  - desktop/web/tests/writes-profile-quizs.test.tsx
- allowed_new_files: 无
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t050_*.py
  - tests/test_gate_*.py
  - desktop/web/src/api.ts
  - desktop/web/src/mock/**
  - desktop/web/src/components/**
  - desktop/web/src/pages/**
  - desktop/web/src/live/**
  - desktop/web/src/App.tsx
  - desktop/web/src/writes/quizsProfile.ts
  - desktop/web/src/writes/profileRules.ts
  - desktop/web/src/writes/useWriteFlow.ts
  - desktop/web/src/writes/useLivePreview.ts
  - desktop/web/src/writes/WriteConfirmDialog.tsx
  - desktop/web/tests/writes-profile-form.test.tsx
  - desktop/web/tests/writes-profile-quizs-logic.test.ts
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/readonly2-app.test.tsx
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - ts/packages/ui/**
  - scripts/**
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden（不新增、不升级、不删依赖；package.json 与 package-lock.json 一个字节都不动）

## Behavior contract
- 正常输入：
  - 选了 quizs 运行时（所选运行时的适配器是 quizs）之后，档案**最终读到**：模型变成档案 Select、选项逐字是 `provider/model`、档位按档案给；不管 `getRuntimes()` 回来与用户选运行时的先后，也不管读档案途中 effect 因为运行时列表换数组而重跑。
  - 读完了的（读到或读不出都算读完了）：同一次打开里不再读第二次；重新打开对话框照旧重读（每次打开读一次）。
  - 迟到的结果照旧丢弃：被作废的那次读的结果回来时不得改界面。
  - 非 quizs 运行时：一次都不调 `getQuizsProviders`。
  - 逐字文案一个不改：读取中仍是「正在读 Quizs 的提供方档案…」，读不出仍是三种原因文案，档案外的模型仍标「不在 Quizs 已批准的档案里」，凭据仍是「凭据由 Quizs 保管」；档案读取中时模型是手填文本框、不调预览、[确认…] 灰着。
- 边界输入：
  - 档案读不出来（信封失败 / reject / 没有可选项）：三种「读不出」照旧退手填、档位六值、写明原因；读不出也算「读完了」，此后不再重读。
  - `getRuntimes()` 失败（reject）：运行时列表置空数组（照旧）。
  - 对话框关闭 / 组件卸载：在途结果丢弃；关闭时「本次打开已经读过」的标记复位（照旧：重开要重读）。
  - 读档案途中切到非 quizs 再切回 quizs：**结果还在路上时**切走会作废这次读，切回时重新读、档案照样读到；**读完之后**切走再切回，不重复读，但已读到的档案仍显示（模型仍是档案 Select）。
- 错误与重试：不新增重试按钮、超时或错误分支；读不出照旧三种原因文案；[确认…] 的门控条件（`:249-253`）一个都不改。
- 并发、取消与状态变化：
  - 读档案的 effect 依赖仍是 `[open, runtime, runtimes]`；每次重跑先跑上一次的清理（作废在途结果），再按新依赖判断要不要读。
  - 「本次打开已经读过档案」的标记：**结果还在路上时被清理 → 复位成未读**；**结果已经回来（成功或失败都算回来）→ 不复位**（不许多读）。
  - 同一个对话框实例里，被作废的那次读的结果回来时不得写界面（`alive` 语义照旧）。
  - 取消/重开：关闭时标记复位（照旧），重开后照旧重读。
- 兼容性：
  - `ProfileForm.tsx` 的导出形态不变（`NewProfileAction({reload?})`、`EditProfileAction({profile, reload?})`）；`api.ts` 的导出、`src/mock/**`、`src/components/**`、`src/pages/**`、`App.tsx` 都不改。
  - 既有断言一条不改、照旧通过：`writes-profile-quizs.test.tsx:145`=1、`:153`=2、`:222`=1、`:303-312` 挂起的读、`:323`=0；t046 门禁 form 探针的 1 次 / 2 次 / 0 次 / 挂起的读。
  - 门禁与验收只按**行为**核对，不钉变量名（`settled`、`archiveRead`）与 effect 的写法。

## Steps
1. 读 Repository facts 里的文件，确认签名与基线一致；不一致就停下并报告（不要自己改事实）。
2. **`desktop/web/src/writes/ProfileForm.tsx`**（只改读档案的 effect 及其上方注释，约 5–8 行）：
   - 在 `:140-141` 的注释后补一句这条反直觉的约束（措辞自拟，但不许出现「已登记运行时」「登记 runtime」「已登记表里加上」「；命令写进本机文件」「已登记为」「ERROR: runtime」「改 adapter 要加」这些字样——它们只被门禁作用在入口文件，但新注释也不必沾）：说明「结果还在路上时 effect 重跑（运行时列表换了数组、换了运行时）会把这次读作废，这时把『本次打开已经读过档案』的标记复位，重跑照样再读一次；结果已经回来就不复位，不多读」。
   - 在 effect 里加一个与 `alive` 并列的局部变量，表示「这次读的结果回来没有」：
     ```tsx
     archiveRead.current = true;
     let alive = true;
     // settled：这次读的结果回来没有（成功或失败都算回来）。
     let settled = false;
     setArchive({ kind: 'loading' });
     getQuizsProviders().then(
       (env) => {
         settled = true;          // 必须在 if (!alive) return; 之前
         if (!alive) return;
         …
       },
       () => {
         settled = true;
         if (alive) setArchive({ kind: 'failed', reason: QUIZS_READ_FAILED });
       },
     );
     return () => {
       alive = false;
       // 结果还在路上就被重跑：复位「已读过」，重跑时照样读。
       if (!settled) archiveRead.current = false;
     };
     ```
   - 清理函数**只在这次读的结果还没回来时**复位 `archiveRead.current`；已经回来的不复位（否则每次重跑都重读，会打破「读完了只读一次」）。
   - 等价写法也接受：把 `archiveRead.current = true` 从发请求时挪到「结果回来且 alive 为真」时（行为相同，少一个标记）。但默认按上面 settled 的写法做；门禁与验收按行为核对，不钉写法与变量名。
   - 这个 effect 以外的代码一个都不动（依赖数组、`!open` 分支、`setArchive` 的三态、逐字文案、导出的两个入口）。
3. **`desktop/web/tests/writes-profile-quizs.test.tsx`**：**只在文件末尾追加**一个 describe，不改 import、不改任何原有用例（基线全文必须仍是新文件的前缀，一个字节都不许动前面的部分）；新用例里不出现 `skip`/`only`/`todo`。
   - 文件末尾加一个「手动兑现」的小助手（写在末尾的 describe 里或文件末尾模块级都行）与两个信封常量：
     - 一个 deferred 助手：`{ promise, resolve }`，`promise` 是测试自己掌握兑现时机的 promise；
     - 档案 ok 信封（照 `desktop/web/src/mock/quizs.ts:19-22` 的两行 provider 写：`stepfun/step-5-preview` 档位 `low/medium/high`，`deepseek/deepseek-chat` 档位 `low/high`；信封形状照 `quizsProvidersEnvelope()`：`{ok:true, exit_code:0, data:{providers:[…]}, output:[], messages:[], command:[…], elapsed_ms:0}`）——自己写字面量即可，不必 import `src/mock`；
     - 运行时信封：文件里现成的 `runtimesEnv()` 返回已兑现的 promise，兑现 deferred 时用 `await runtimesEnv()` 拿到那个信封（两行 runtime：`pi` 与 `quizs-cli`，后者 adapter 是 quizs）。
   - **用例 A（站主登记的顺序；这一步必须让两个读函数都手动兑现，否则复现不出竞态，在未修的实现上也是绿的）**：
     1. `window.location.hash = '#/roles?write=ok&quizs=ok'`；
     2. 第一次打开：`render(<NewProfileAction />)`，点「新建 profile」，`await settle()`（此时 `getRuntimes` 用 `beforeEach` 的桩 → 运行时列表就位、runtime 落在 `pi`）；点「取消」，`await settle()`；
     3. 换成手动兑现：`set('getRuntimes', () => rtDeferred.promise)`；`set('getQuizsProviders', () => providerDeferreds[n++].promise)`（按调用次序依次给第 1、第 2 个 deferred）；
     4. **在同一个已挂载的组件上**再点一次「新建 profile」（不要重新 `render`），`await settle()`（此时 `getRuntimes` 还没兑现，运行时列表还是上一次的旧数组）；
     5. 填一个合法 ID（如 `t050-x`），把 runtime 改成 `quizs-cli`，`await settle()` → 此时发出第 1 次档案读（还在路上）；
     6. 兑现 `rtDeferred`（给运行时信封），`await settle()` → 运行时列表换新数组 → effect 重跑 → 第 1 次读被作废，重发第 2 次；
     7. 兑现第 2 个 provider deferred（ok 信封），`await settle()`；
     8. 断言：模型控件是 `SELECT`；选项逐字是 `['stepfun/step-5-preview', 'deepseek/deepseek-chat']`；值为 `stepfun/step-5-preview`（新建自动选档案第一项）；档位是 `['low','medium','high']`；界面**不再**写「正在读 Quizs 的提供方档案…」；`await advance(350)` 后命令含 `--runtime=quizs-cli --model=stepfun/step-5-preview`；[确认…] 不再 disabled；
     9. 再兑现第 1 个 provider deferred（给一个失败信封，`ok:false`），`await settle()` → 界面**仍是**档案 Select、选项不变（迟到的结果被丢弃）；
     10. 断言 `spyCalls('getQuizsProviders')` 是 2（作废的一次 + 重读的一次）；**不许断言为 1**（这一条是本用例的核心：修好后界面读到了档案）。
   - **用例 B（读完之后 effect 再重跑不再读）**：
     1. 同样先第一次打开（让运行时列表就位）再取消，然后换成手动兑现的读函数；
     2. 第二次打开，在 `getRuntimes` 兑现之前选 `quizs-cli` → 发出第 1 次档案读；先兑现第 1 个 provider deferred（档案读完了），`await settle()`；
     3. 再兑现 `rtDeferred`，`await settle()` → 运行时列表换新数组 → effect 重跑；
     4. 断言：`spyCalls('getQuizsProviders')` **仍是 1**（读完之后不再读第二次）；界面仍是档案 Select、选项不变；
     5. 追加一步：把 runtime 切到 `pi` 再切回 `quizs-cli`，`await settle()` → 档案**仍然显示**（模型仍是 SELECT、选项不变），且不重复读（次数仍为 1）。
   - 可选用例 C（同一根因的第三条路径，写了更好、不写不罚）：读档案途中（结果还在路上）切到 `pi` 再切回 `quizs-cli` → 切回时重新读、档案照样读到。
   - 写完后先跑本文件（`npm test -- tests/writes-profile-quizs.test.tsx`）确认新用例绿、原有 15 条用例照旧绿，再跑全量 `npm test`。
   - **自检（必须做，写进执行报告）**：用例 A 在**未修的实现**上必须是红的（停在「正在读 Quizs 的提供方档案…」）。做法：临时把清理函数里那行复位去掉（或把 `settled` 永远当真），跑一次用例 A 看它红，然后**改回来**并确认恢复绿；不要把这个临时改动留在候选里。
4. 跑 Validation commands 里与改动相关的检查（G01 → V01 → V02 → V03），记录命令与结果；R01（全量门禁回归）由验收端跑，执行端若跑要按文件分批、逐批记录，不许漏文件、不许用 `-x`/`--lf` 代替。
5. 写执行报告；遇到合同未定义的行为（例如档案三态或逐字文案与合同写的对不上），停下并报告，不要改范围外的文件，也不要为了变绿去改 `tests/test_gate_*.py`。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态，不能以 tail/echo 的成功退出码作为检查通过证据。

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t050_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run typecheck` · cwd：desktop/web · 超时：600s · 期望退出码：0
- V03（必要）：`npm run build` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`built in`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py tests/test_gate_t044_baseline.py tests/test_gate_t045_baseline.py tests/test_gate_t046_baseline.py tests/test_gate_t047_baseline.py tests/test_gate_t048_baseline.py tests/test_gate_t049_baseline.py -q` · cwd：仓库根 · 超时：2880s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：用例 A 走完站主登记的顺序（第二次打开、在 `getRuntimes()` 回来之前选 quizs 运行时）之后，档案仍读到：模型是档案 Select（两项 `stepfun/step-5-preview`、`deepseek/deepseek-chat`）、新建自动选第一项、档位 `low/medium/high`、界面不再写「正在读 Quizs 的提供方档案…」、`advance(350)` 后命令带 `--runtime=quizs-cli --model=stepfun/step-5-preview`、[确认…] 可点；证据：V01、G01；目的：站主登记的「第二次打开一直停在正在读…」不再发生，[确认…] 不再灰着。
- D02：用例 A 在**未修的实现**上是红的（基线上停在「正在读 Quizs 的提供方档案…」、模型仍是手填框），修好后是绿的；证据：G01（基线应失败）、V01；目的：竞态真被测住，不是一个恒绿的用例。
- D03：用例 B：档案读完之后 effect 再重跑（运行时列表换新数组）**不再读第二次**（`getQuizsProviders` 次数仍为 1），档案照旧显示；读完之后把 runtime 切到 `pi` 再切回 `quizs-cli`，档案仍显示且不重复读；证据：V01、G01；目的：修复不许变成「每次重跑都重读」。
- D04：迟到的结果照旧丢弃：用例 A 里被作废的那次读的结果回来后，界面仍是档案 Select、选项不变；证据：V01、G01；目的：旧结果不许盖掉新读到的档案。
- D05：既有断言一条不改、照旧通过：`writes-profile-quizs.test.tsx:145`=1、`:153`=2、`:222`=1、`:323`=0、`:303-312` 挂起的读照旧；t046 门禁 form 探针的 1 次 / 2 次 / 0 次 / 挂起的读照旧；证据：V01、R01、G01、review；目的：既有保护不许为新功能放松。
- D06：非 quizs 照旧一次都不调；重新打开照旧重读；逐字文案一个不改（t046 的六条新文案、七条旧文案、七段 THINKING_OPTIONS）；证据：V01、R01、G01；目的：这一片只修竞态，不动别的行为。
- D07：读档案途中（结果还在路上）切到非 quizs 再切回 quizs 时重新读到档案；读完之后切走再切回仍显示已读到的档案（不重复读）；证据：V01、review；目的：同根的第三条路径（切换运行时）也不卡。
- D08：所有修改都在允许集合内（可改 2 个文件、无新增文件、无删除文件），没有碰 forbidden_paths；`desktop/web/package.json` 与 `package-lock.json` 没变；没有新增依赖；证据：scope、R01、V02、V03；目的：这一片不许顺手改别的片的地盘。
- D09：没有删除、跳过或弱化既有测试；`writes-profile-quizs.test.tsx` 的基线全文仍是新文件的前缀；新用例不出现 `skip`/`only`/`todo`；证据：review、V01、R01；目的：验收看的是行为有没有被测住，不是测试文件在不在。
- D10：`desktop/web` 的 `npm test`、`npm run typecheck`、`npm run build` 全过；证据：V01、V02、V03。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如读档案的 effect 不在 `:140-172`、依赖数组不是 `[open, runtime, runtimes]`、或 `writes-profile-quizs.test.tsx` 里的行号与事实对不上），停下报告，不要自己改事实。
- 必须修改允许范围之外的文件才能继续（例如要动 `api.ts`、`src/mock/**`、既有门禁测试、`writes-profile-form.test.tsx`、`page-app.test.tsx`、依赖文件）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限（`npm ci` 装不上就停下报告，不要改锁文件、不要改依赖版本）。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如要在档案读取中加按钮、给读档案加超时或重试、给非 quizs 分支也读一次档案）。
- 基线检查（V01/V02/V03）在**未改代码时**就已经红：停下报告，不要改门禁或既有测试去凑绿。
- 达到单轮时限。

## Budget
- max_attempts_total: 2（按 task-id 汇总，含返工版本；累计已用 0 次——本版留 2 次实现与定点返工）
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 10800（2 次 × 5400；累计已用 0 秒，本版可用 10800 秒 ≥ 2×5400）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读源码与核对门禁 15 分钟；改 effect 与注释 15 分钟；写新用例 A/B（含手动兑现助手与自检）35 分钟；跑 G01、V01、V02、V03 20 分钟；写执行报告 10 分钟；总计约 95 分钟，单轮时限 5400 秒（90 分钟）——装依赖与跑检查的时间在 95 分钟里，多出的部分留给返工。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D10，列出自检命令与结果（含「用例 A 在未修实现上是红的」这一次临时改动的自检过程与恢复确认）、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过；不改 `tests/test_gate_*.py`（含 `tests/test_gate_t050_*.py`）。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
