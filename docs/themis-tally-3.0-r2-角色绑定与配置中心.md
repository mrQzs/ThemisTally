# Themis Tally 3.0 第二轮设计：角色绑定（轻量底座）与配置中心

状态：第 2 稿，送 2gate 闸一第 2 轮（2026-10-18）。第 1 轮 7 个 Blocking、7 个 Should-fix、2 个 Nit，处置见 §0。

- 分支：`themis-3.0`（本地，不推送）。起点 `106e94a`（2.11.0，已快进合并到本地 master）。
- 上位设计：`docs/themis-tally-3.0-四端分层解耦架构.md`。相关的是 3.4、6.3、7、8.1、8.5、8.6、11 节，以及 12 节的 P1、M1。
- 调查：`.agent/design/3.0-r2-调查摘要.md`，是在 `b5e9ea5` 上做的。
- 下文的 `file:line` 都在 `b525cb8` 上核对过。那是 `resolve_run_dir` 修复之后的提交，`pi_dispatch.py` 第 3224 行之后比第 1 稿多 12 行。
- 缩写：
  - PD = `scripts/pi_dispatch.py`
  - KC = `scripts/kit_config.py`
  - TD = `tests/test_dispatch.py`

## 0. 审核变更对照表

| 编号 | 第 1 轮结论 | 本稿处置 |
|---|---|---|
| r1-B1 | 信任边界有缺口。本机文件被提交进仓库后，读取时不会拒绝。PATH 解析能执行仓库里的程序：Windows 上 `shutil.which` 先查当前目录，`.cmd` 包装也会被跟随 | D3 写明信任模型，并补两处：<br>① 读本机文件前确认三件事，任一不满足就报错，不退回 PATH：未被 Git 跟踪、已被忽略、路径上没有链接。<br>② 新增 `trusted_which`：只查 PATH 中的绝对路径，跳过仓库之内的目录，不隐式查当前目录。`resolve_pi_command` 找 pi 与 node、所有探测命令都改用它。这是对 2.10 的收紧（10 节第 7 项）。<br>③ 写明本轮的保证范围；Windows 上裸名启动的 git 等程序会先查当前目录，作为既有残余记下（10 节第 8 项） |
| r1-B2 | 三个窗口：<br>① 同一版本两次首次 prepare 并发，会各写一份快照；<br>② 没有绑定时的首次 prepare 不冻结任何东西；<br>③ 解析用的合同字节与冻结的字节不是同一份 | ① D5：每个合同版本只有一份记录 `.agent/runs/<task>/binding-v<N>.json`，以 O_EXCL 创建，先到者定，后来者读它。<br>② D4：按角色写的合同必须有绑定，不再退回 2.10 的路径；旧合同从不读绑定。<br>③ 解析改用冻结后的合同字节与只读一次的配置字节。记录里存合同 JSON 的哈希，之后的 attempt 字节不同就拒绝 |
| r1-B3 | 写死模型的合同本来就在 prepare 时提前解析（PD:4212-4214），遗留用例钉住的正是这个提前拒绝的顺序；“meta 不加字段”与 note 也矛盾 | **我在第 1 稿里把论证写反了**。D4、D5 更正：<br>① 写死合同的提前解析与拒绝顺序原样保留；<br>② 与绑定的比较放在这些检查全部通过之后，只打 NOTE；<br>③ 绑定本身的问题从不阻塞写死合同或旧合同；<br>④ `meta.json` 只在有差异时加 `executor_binding_note` |
| r1-B4 | 两处补记不成立：只有审计写失败时，之后不会补记；还没留档的前态在崩溃时会丢 | D7 改为事务：<br>① 替换之前，先按内容存前后两份快照并写 intent；<br>② intent 写不进就不替换；<br>③ 替换之后写 commit；<br>④ commit 缺失时，由读取方按当前文件的哈希补判 |
| r1-B5 | 固定临时文件名下并发替换，会发布另一个进程的内容；快照编号与审计对不上 | D7：<br>① 每次写入用同目录下独立的临时文件；<br>② 替换前重读文件，与前态不同就放弃（冲突，退出 1）；<br>③ 快照按内容寻址，不再编号；<br>④ external 改为“当前哈希不是任何已提交记录的 after”。<br>不加锁时剩下的窗口写明在 D7，是否加锁见 10 节第 6 项 |
| r1-B6 | 历史放在 kit_roles，与“旧入口不导入 kit_roles”冲突；KEYS 的检查函数会被无条件调用（KC:317-319） | 历史与审计放进 `kit_config`。五个新键的检查函数在键不存在时立即返回，不导入 kit_roles（D12） |
| r1-B7 | 用快照取消上位设计 8.1“运行中切换需要确认”不成立：快照实现的是“运行中的不受影响”，这是另一条要求 | D8：一次写入若改变 execution 或 contract 的生效绑定，而又有 attempt 在运行或收集证据，必须带 `--yes`，审计记 `confirmation: flag`；没带就拒绝，并列出这些 attempt |
| r1-S1 | 要分清 raw、normalized 与 resolved 三种 executor；“role 可省略”与“role 必须一致”矛盾；旧合同“没写模型但写了 thinking”没有归类 | D4 按 raw 分三类：<br>① 写了 `role` 的是按角色，必须显式写 role；<br>② 同时写了 provider 与 model 的是写死；<br>③ 其余是旧合同，行为与 2.10 相同，从不读绑定。<br>混用检查只看 raw；thinking 取 profile 的值，`PI_EXEC_THINKING` 与绑定的值比较 |
| r1-S2 | 同一 runtime 只探测一次，会把第二个 profile 的模型与登录误判为就绪；共用函数要保住旧 doctor 的语义 | D10：<br>① 版本与帮助按 runtime 缓存；<br>② 模型与登录按（runtime, provider, model）分别检查；<br>③ 共用函数显式接收环境参数，旧 doctor 照旧继承环境，测试钉住的输出不变 |
| r1-S3 | 凭据可用性的判断与实际子进程的环境不一致；“从不读取值”的说法不准确 | D9：<br>① 以 `child_env(config)` 的结果判断，含默认移除列表与 env_keep，名字按大写比较；<br>② 措辞改为“不返回、不输出、不记录凭据值”；<br>③ 凭据库里有值只作说明，不算就绪 |
| r1-S4 | 快照的凭据检测弱于已有的敏感键规则 | D7：存快照之前，对整份 JSON 的键用 `_SECRET_KEY_RE`，值用 `RELEASE_PATTERNS["api key"]` 与 `_SECRET_TOKEN_RE`（PD:2433-2439、7314-7316）；命中就只存哈希 |
| r1-S5 | 执行模型的各个读回点没有收口 | D5：新增 `attempt_executor`，五个读回点都改用它。取值顺序：<br>① `executor.json`；<br>② 版本记录的模型，加合同里的 tools 与 context_files；<br>③ 各调用处原来的后备 |
| r1-S6 | 几处缺口：<br>① history 没有差异；<br>② actor 应该由调用方自声明；<br>③ init 的空前态没有定义；<br>④ 插件写入的部分成功会被包装成失败；<br>⑤ `config decisions` 没有对应的动作 | D7 逐项补上：<br>① history 列出每条变化的键，`history show` 给出逐键差异；<br>② actor 取 `CODEKIT_ACTOR`（`user` 或 `agent:<角色>`），没有就记 `undeclared`；<br>③ init 的前态为空；<br>④ `kit_plugins` 原样透传“已写入但审计记录不全”；<br>⑤ `config decisions` 记 `config.decisions` |
| r1-S7 | 遗留单元测试经 `git show` 测的是锁定的历史实现（`tests/legacy_harness.py:203`、`266`）；测试清单逐条有缺口 | 第 9 节分开写针对本轮候选的测试与锁定历史的测试，并按审核表逐条补用例 |
| r1-N1 | “时间加进程号”不能证明 audit_id 唯一 | 改用 128 位随机数 |
| r1-N2 | 返回协议要带错误码，还要拦住 helper 里抛出的 `pd.DispatchError` | D12 写明返回值的形状与退出码。kit_roles 在接口边界，把自己那份模块的 `pd.DispatchError`，以及 OSError、ValueError，都转成返回值 |
| 自查 | 第 2 稿送审前发现：敏感键名规则会命中本来合法的 `decisions.api_key_env` 与 D1 的 `credential_env`，带决策配置的快照会永远存不下来 | D7 与 D1 豁免存放变量名的键（以 `_env` 结尾的键、`env_remove`、`env_keep`），前提是值确实是变量名；T2 补上正向用例 |
| 前置 | — | 两项前置已单独提交：<br>① `tests/test_dispatch.py` 在 pytest 下能失败了（`2aa8a61`）；<br>② `resolve_run_dir` 不再跟随链接（`b525cb8`）。<br>所以本稿的行号改在新 HEAD 上核对 |

## 1. 范围

### 1.1 用户决定（2026-10-18）

- 开第二轮，走 2gate。
- **P1 做轻量底座**：
  - 做：解析 v3 的角色绑定与方案，登记适配器；内核按 execution 角色（以及声明为合同端的合同）解析执行模型；配置中心七项功能全做，`runtime scan` 只查 PATH。
  - 不做：把 Pi 抽成适配器，留到接第二个 CLI（P4）时。
- **执行模型以绑定为准**：
  - 新合同不写 provider 与 model；prepare 按当前绑定解析，并按合同版本记一份快照，同一版本之后的 attempt 都沿用它；
  - 写死模型的合同仍以合同为准，与绑定不一致时提示；
  - AGENTS.md 的“换模型要写进新合同”改为“换绑定要用户同意”。

### 1.2 本轮交付

1. **配置 v3 的五个键**：`runtimes`、`profiles`、`roles`、`presets`、`active_preset`（D1）。
   - 新模块 `scripts/kit_roles.py`；
   - 在 `kit_config` 的 KEYS 末尾登记；
   - 本机覆盖文件 `.agent/dispatch.local.json`（D3）。
2. **配置中心命令**：覆盖上位设计 8.1 的七项与 8.6 的审计（D7–D10）：
   - runtime 的 list / scan / add / remove / probe；
   - models；
   - profile 的 show / add / edit / remove；
   - role 的 show / set；
   - preset 的 list / show / save / use / diff / remove；
   - history、history show、rollback；
   - `config doctor`。
3. **写入历史与审计**（D7）：
   - 每次写配置都是一个事务；
   - 快照按内容寻址，存在 `.agent/config-history/`；
   - 审计追加到 `.agent/audit/management.jsonl`；
   - 运行中切换绑定要确认（D8）。
4. **内核**：
   - 合同 executor 分三类（D4）；
   - 每个按角色的合同版本一份原子记录，prepare 用冻结的字节解析，run 用记录（D5）；
   - `trusted_which` 与按 runtime 定位命令（D3）；
   - `attempt_executor` 统一读回；
   - 摘要写明执行模型的来源。
5. **规则、技能与文档**：
   - AGENTS.md；
   - plan-task；
   - check-pi-env；
   - review-pi；
   - README、CHANGELOG；
   - `gitignore.append.txt` 与本仓库的 `.gitignore`；
   - `.claude/settings.example.json`（D11）。

### 1.3 不在本轮

- 把 Pi 抽成适配器、接入 `scripts/codekit/adapters/`、generic 适配器：P4。
- 第二个 CLI 的无头调用：P4，且每次真实调用都要用户另行授权。
- 规划审核端与调度代理的无头调用（P6、P5）：本轮只记录它们的绑定，并在就绪总览里报告。
- 审核与批准随配置失效：P3 之前没有批准记录（D8）。
- 管理台网页（M4）、用户级方案库（15.2 第 10 项的可选部分）。
- 上位设计 6.3 的 `policies`、`feedback`、`logging`、`ui` 四个键。

## 2. 现状（承重事实）

### 2.1 合同里的执行模型

- **补默认值**：`normalize_contract` 给 executor 补 thinking、tools、context_files，不补 provider、model（PD:1440-1450）。`validate_contract` 先补默认值再校验（PD:1781）；加载 attempt 时也会再补一次（`load_attempt`，PD:3245-3248）。
- **校验**：
  - provider、model 可以缺省，只在有值时校验格式（PD:1814-1818）；
  - thinking 必须是已知级别（PD:1819-1821）；
  - 旧合同不写模型也能通过校验，run 时由 `PI_EXEC_*` 补上，这是 `tests/test_legacy_cli.py:161`（LB-CONTRACT-003）钉住的合法输入。
- **Markdown**：
  - Identity 的 executor 行必须写成 `provider/model · thinking <级别>`（`derive_contract_json`，PD:1652-1655，派生结果见 PD:1709-1714）；
  - JSON 有 provider、model 时，Identity 必须写明它们与 thinking（PD:1939-1944）。
- **prepare**：
  - raw 合同同时写了 provider 与 model 时，prepare **提前**调用 `resolve_executor`（PD:4212-4214）；
  - 遗留用例钉住了这一步的拒绝顺序：
    - 环境变量冲突退出 2，先于允许列表的退出 3（`tests/test_legacy_cli.py:802`）；
    - 允许列表未命中时，在分配 attempt 之前就拒绝（`tests/test_legacy_lifecycle.py:783`）；
    - 思考级别被固定、合同不符时拒绝（TD:534-540）。
  - 冻结合同字节、写 `plan.md` 与 `contract.json` 都发生在分配 attempt 之后（PD:4232-4252）；
  - 之后的失败标记为 PREPARE_FAILED（PD:4276-4279）。
- **run**：
  - 再次解析执行模型（PD:4335）；
  - 领取之后写 `executor.json`（PD:4388）。
- **规则**（`resolve_executor`，PD:3282-3313）：
  - 合同为准；
  - `PI_EXEC_*` 只补缺，与合同的显式值冲突时报错；
  - `allowed_executors` 非空时检查。
- **读回点**：`executor.json` 不存在时，collect 退回 `contract["executor"]`（PD:4522）；摘要、branch、复审骨架、metrics 退回空对象（PD:3500、5967、6147、6818）。
- **attempt 的分配与锁**：
  - `allocate_attempt` 只保证目录不重名（PD:3196-）；
  - 任务锁 `TaskLock`（PD:3163-）只用在 run 的领取上。

### 2.2 pi 的命令与就绪检查

- **定位 pi**（`resolve_pi_command`，PD:2293-2320）：
  - `PI_DISPATCH_PI_CMD` 优先；
  - 否则 `shutil.which("pi")`（PD:2304）；
  - Windows 上解析 npm 的 `.cmd` 包装，node 用包装同目录的 `node.exe`，没有就 `shutil.which("node")`（PD:2307-2318）。
- **Windows 上会先查当前目录**：Python 的 `shutil.which` 在 Windows 上把当前目录排在 PATH 之前（3.12 起改由 `NeedCurrentDirectoryForExePathW` 决定，缺省仍然会查）。调度器通常在仓库根运行，所以仓库根下的 `pi.cmd` 会被选中。这是 2.10 就有的现象。
- **批处理特殊字符**：检查在 `ensure_argv_safe`（PD:2322-2328），只防参数里的特殊字符，不判断命令是否可信。
- **doctor**（PD:6955-7002）：
  - 运行 `--version` 与 `--help`；
  - 带 `--provider`、`--model` 时，再核对模型列表、`auth check --no-refresh` 与思考级别；
  - 不给子进程传过滤后的环境；
  - 测试钉住的地方：TD:738-770（模型列表失败、空列表、无匹配、脱敏与 JSON 字段）、TD:2368-2375（缺参数时的 NOTE）、`tests/test_legacy_cli.py:1039`（退出码）。
- **预检**的 `auth check` 不带 `--no-refresh`（PD:2591），与 doctor 不一致。这是既有现象（调查摘要第 6 条），本轮不改。
- **辅助函数**：`parse_help`（PD:2393-2404），`list_models_rows` / `list_models_empty_reason`（PD:2407-2429）。

### 2.3 配置管理器

- **键与校验**：
  - KEYS 在 KC:256-274；未知键是错误；
  - 每个注册的检查函数都被无条件调用（KC:317-319）；
  - `split_path` 最多两层，只在第一个点处分开（KC:414-419）。所以 `config set roles.execution '{…}'` 与 `config unset roles.execution` 现在就能用。
- **写入**：
  - `write_config` 用固定的临时文件名 `dispatch.config.json.tmp`，然后原子替换（KC:397-404）；
  - `write_checked` 先整份校验再写（KC:491-497）；
  - `cmd_init` 直接调用 `write_config`（KC:541-555）；
  - `config decisions` 经 `write_checked` 写入（KC:580）；
  - `kit_plugins` 的写入把 OSError 包成“写入失败”（`kit_plugins.py:634-635`）。
- **测试钉住的地方**：
  - `config show` 的第二个键必须是 `worktree_root`（TD:2749）；
  - `test_v270` 的临时仓库只拷 `kit_config.py` 与它原有的依赖（TD:2740-2743），却要求 `config set decisions …` 成功。
- **调度器读配置**：`Repo.config()` 宽松读取，忽略未知键（PD:1150-1160）。

### 2.4 离线参考实现不接

- `scripts/codekit/config_profiles.py` 与本轮设计不兼容：
  - 用的是 v2 的角色名 supervisor、planner、executor、observer（CP:26）；
  - 只认 `schema_version` 2，凭据字段叫 `credential_refs`；
  - 只有 `tests/test_config_profiles.py` 与 `tests/test_config_policy_boundaries.py` 导入它。
- `scripts/codekit/adapters/` 的准入模型要求只读，与执行端冲突（调查摘要第 1 条）。

### 2.5 环境与凭据

- `child_env` 对执行器与检查命令移除默认列表与 `env_remove`，`env_keep` 可以把名字留下，名字按大写比较（PD:599-617）。默认列表里有 `CLAUDE_CODE_OAUTH_TOKEN`（PD:130）。
- 决策模型的 `Session` 缺省读 `os.environ`（`codekit/decisions.py:672`），调度器创建它时不传 environ（PD:3735）。
- 凭据库的 `describe` 经 `source()` 判断变量在哪一层，`source()` 会读取凭据库（`codekit/secrets.py:306`、`366`）。
- 凭据形状的规则：
  - `RELEASE_PATTERNS["api key"]`（PD:7314-7316）；
  - 敏感键名 `_SECRET_KEY_RE` 与令牌 `_SECRET_TOKEN_RE`（PD:2433-2439）。

### 2.6 忽略规则、安装与测试接线

- 本仓库的 `.gitignore` 忽略 `.agent/runs/` 与 `.agent/baseline/`。
- `kit_install` 把根目录的 `gitignore.append.txt` 追加进目标仓库的 `.gitignore`（`kit_install.py:63`）。
- 主工作区指纹不含被忽略的文件（PD:1058-1083）。
- `KIT_LOADED_FILES`（PD:96-101）同时决定两件事：执行器不能改这些文件，它们随 kit 发放（`kit_install.py:197`）。
- **runs 下的任务目录**：调度器只列其中的子目录，并按 `ATTEMPT_DIR_RE` 认 attempt（PD:3138-3143、4170）；`kit_logs` 跳过名字不符的项，也不计数（`kit_logs.py:202-205`）。
- **端到端测试**：临时仓库只拷 `pi_dispatch.py` 与 `dispatch-pi.sh`（TD:196）。
- **遗留测试有两种**：
  - 进程内的单元测试经 `git show` 读锁定的历史源码（`tests/legacy_harness.py:203`、`266`）；
  - CLI 用例把当前脚本拷进临时仓库（`tests/legacy_harness.py:1445`）。

### 2.7 规则与技能里写死的执行模型

- AGENTS.md:
  - 87-89：“执行模型默认用 Step 系列……更换模型或思考级别需要用户同意，并写进新合同”；
  - 103：改配置要征得用户同意。
- plan-task：
  - `contract-template.md:15`；
  - `SKILL.md:150`；
  - `contract-guide.md` 的第四节与第 192 行。

## 3. 决策与理由

### D1 配置形状

在 `.agent/dispatch.config.json` 增加五个可选键。形状取自上位设计 6.3，删去本轮不用的字段：

```json
{
  "runtimes": {"pi": {"adapter": "pi"}},
  "profiles": {
    "exec-step": {"runtime": "pi", "model": {"provider": "bb", "id": "step-5-preview"},
                  "options": {"thinking": "high"}, "credential_env": []}
  },
  "roles": {
    "planning_review": {"mode": "interactive_host", "host": "claude-code"},
    "contract": {"mode": "manual"},
    "execution": {"mode": "headless", "profile": "exec-step"},
    "scheduler_agent": {"mode": "disabled"}
  },
  "presets": {
    "economy": {"description": "执行端用低价模型", "roles": {"execution": {"mode": "headless", "profile": "exec-step"}}}
  },
  "active_preset": "economy"
}
```

**通用规则**：

- **ID**：runtime、profile、方案的 ID 沿用 `TASK_ID_RE`（PD:62），不新造口径。
- **严格形状**：每个对象只接受下面列出的键；下划线开头的键是说明。

**各键的规则**：

- **`runtimes.<id>`**：只有 `adapter`，取值是 D2 表里的适配器。不能写命令或路径（D3）。
- **`profiles.<id>`**：
  - `runtime`：必须已登记；
  - `model`：`{provider, id}`，两项都要符合 `MODEL_TOKEN_RE`，且不能命中 `PLACEHOLDER_RE`（PD:65、67）；
  - `options`：按适配器校验。pi 只接受 `thinking`，取值在 `FALLBACK_THINKING_LEVELS` 里（PD:74），不写时按 high 解析，与合同的缺省相同（PD:73）；其他适配器的 `options` 必须为空；
  - `credential_env`：环境变量名的列表，与 `env_remove` 用同一个检查（KC:131-136）。
- **`roles`**：只有四个角色名。每个角色允许的模式取自上位设计 6.3：

  | 角色 | 允许的模式 |
  |---|---|
  | planning_review | `interactive_host`（`host` 为 claude-code 或 codex）、`headless` |
  | contract | `manual`、`headless` |
  | execution | `headless` |
  | scheduler_agent | `disabled`、`headless`（可带 `cadence_seconds`，整数，至少 60） |

  - `headless` 必须带已登记的 `profile`；
  - 没写的角色取默认值：planning_review 为 `interactive_host`（宿主未声明），contract 为 `manual`，execution 由合同决定（2.10），scheduler_agent 为 `disabled`。
- **`presets.<名>`**：
  - `description` 可选；
  - `roles` 至少写一个角色，规则同上；
  - 方案只覆盖它列出的角色。
- **`active_preset`**：必须是已有的方案名。

**凭据**：五个键里所有的键与字符串，都用 D7 的同一组规则检查，命中就报错。规则包括敏感键名、凭据形状、令牌形状，以及对存放变量名的键（如 `credential_env`）的豁免。

**接入 `kit_config`**：

- 五个键追加在 KEYS 末尾。
- 各自的检查函数在键不存在时立即返回，存在时才惰性导入 `kit_roles`（D12）。

**不加 `schema_version`**：五个键都缺省时，等价于 2.10 的兼容预设（上位设计 11 节）。

**允许列表沿用 `allowed_executors`**，不新增 `policies.allowed_models`：

- 它已经在 `resolve_executor` 里强制执行（PD:3302-3312）；
- 绑定解析出的模型同样要过它。

### D2 适配器登记

适配器是 `kit_roles` 里的一张静态表，不是插件：

| 适配器 | 程序名 | 本轮接通的无头角色 | 交互式宿主 | 列模型 | 登录就绪 | options |
|---|---|---|---|---|---|---|
| pi | `pi` | execution、contract | 否 | `pi --list-models` | `pi auth check --no-refresh` | thinking |
| claude-code | `claude` | 无 | planning_review | 否 | 否 | 无 |
| codex | `codex` | 无 | planning_review | 否 | 否 | 无 |
| opencode | `opencode` | 无 | 否 | 否 | 否 | 无 |

- **未接通的组合**：绑定到这种组合是合法配置，可以提前登记。这时：
  - `config role set` 与 `preset use` 打 WARN；
  - `config doctor` 报未就绪；
  - prepare 拒绝（D6）。
- **为什么用静态表**：接入一个 CLI 要实测（上位设计 7.3）；声明式的 generic 适配器留到插件安装那一轮。

### D3 命令路径与信任边界

**信任模型**：

- kit 是可信的，包括调度器与配置中心。
- 仓库内容不可信：配置、本机文件、仓库里的程序，都可能出自别人之手。
- kit 装在仓库里时（installed、source 布局），运行仓库里的调度器本身就是在运行仓库的代码。所以这条边界只在从外部 kit 目录运行时（external 布局）才完整。
- 但无论哪种布局，新命令都不应扩大这个面。
- **本轮的保证范围**：新增的命令（scan、probe、models、`config doctor`）以及 pi 与 node 的定位，都不会执行由仓库内容决定的程序。
- **既有的残余**：其他以裸名启动的子进程，例如 `git`、`bash`，在 Windows 上由 CreateProcess 查找程序，查找顺序里有调度器进程的当前目录。这是整个 kit 一直就有的现象，本轮不改，写进 10 节第 8 项。

**提交的配置里不写命令**：`runtimes.<id>` 只写 adapter。原因有两条：

- 克隆来的仓库，不能借配置让 `config doctor`、`scan`、`probe`、`models`、`prepare`、`run` 运行它指定的命令；
- 本机路径会被 release-check 的家目录规则报出（PD:7317-7318）。

**本机文件 `.agent/dispatch.local.json`**：

- **形状**：只接受 `{"runtimes": {"<id>": {"command": ["<程序>", "<参数>", …]}}}`，`command` 是非空的字符串数组。
- **读取前的检查**：以下任一项不满足，就报一行 ERROR、不使用它，也不退回 PATH：
  1. 不被 Git 跟踪（`git ls-files --error-unmatch` 失败）；
  2. 已被忽略（`git check-ignore` 成功）；
  3. 从仓库根到它的每一级都不是链接（`first_link_component(repo.root, ".agent/dispatch.local.json")`）。
- **写入前**做同样的三项检查。
- **ID 未登记**：文件里的 runtime ID 在提交的配置里没有登记时，报 WARN：本机文件可能是给别的分支准备的。
- **只有一处读写**：读写它的代码只在 `kit_roles` 里。

**PATH 查找**：PD 新增 `trusted_which(program, repo_root)`，内核与 kit_roles 共用。

- 只查 PATH 中的绝对路径，跳过空项与相对项；
- 跳过解析后落在仓库根之内的目录（`is_within`）；
- 不隐式查当前目录；
- Windows 上按 PATHEXT 补扩展名；
- 拿不到仓库根时，只排除当前目录。

**`resolve_pi_command` 改用它**（PD:2304、2316），并新增参数 `repo_root`。

- 找 pi 用它；`.cmd` 包装同目录没有 `node.exe` 时，找 node 也用它。
- 这是对 2.10 的收紧：仓库里的 `pi.cmd`、`node.exe` 不再被选中（10 节第 7 项）。
- 出错时的提示文字不变：仍是“PATH 中找不到 pi……”。

**pi 命令的解析顺序**：

1. `PI_DISPATCH_PI_CMD`：沿用，测试与现有用户都依赖它。这个变量是本机事实，不来自仓库。
2. 本机文件中这个 runtime 的 `command`，三项检查都通过时才用。
3. `trusted_which("pi")`。

其他适配器的顺序：本机文件，然后 `trusted_which(程序名)`。

**写死合同与旧合同**：不引用 runtime，直接按上面的 1、3 两步解析，跳过本机文件；第 3 步同样用 `trusted_which`。

**执行之前**：

- 本机文件给出的命令先过 `ensure_argv_safe`。
- 探测（scan、probe、`config doctor`）只运行 `<命令> --version`。pi 另外运行 `--help`、`--list-models <模型>` 与 `auth check --no-refresh`，与 doctor 相同（D10）。
- 探测时的环境用 `child_env(config)`。

### D4 合同的三类 executor（用户决定：绑定为准）

按 raw 合同分类，即 JSON 解析之后、`normalize_contract` 补默认值之前的样子：

| 类别 | raw executor | 执行模型从哪来 | 与绑定的关系 |
|---|---|---|---|
| 按角色（新） | 有 `role`（`execution` 或 `contract`），没有 provider、model、thinking | 该角色的 headless 绑定 | 必须有绑定，没有就拒绝 |
| 写死（2.10） | 同时有 provider 与 model | 合同 | 只比较，不一致时打 NOTE |
| 旧合同（2.10） | 其余情况：没写模型、只写了 provider 或 model 之一、只写了 thinking | 2.10 的规则：`PI_EXEC_*` 补缺 | 从不读绑定 |

**混用检查**：有 `role` 又有 provider、model、thinking 中的任何一项，validate 报错。判断只看 raw 合同，因为 normalize 会补上 `thinking=high`（PD:1444）。

**按角色**：

- provider、model 取自 `profile.model`；thinking 取 `profile.options.thinking`，没写时是 high。
- 设了 `PI_EXEC_*`，且与绑定的值不同：报错。
- contract 角色是 `manual`，合同却写了 `role:contract`：报错。
- 必须有绑定。这样就不存在“首次 prepare 时没有绑定，之后才有”的冻结问题（r1-B2）。

**写死**：

- prepare 的提前解析与拒绝顺序原样保留（PD:4212-4214，以及 2.1 列出的遗留用例与 TD:534-540）。
- 这些检查都通过之后，若配置了 execution 绑定，且它的 provider、model、thinking 有任何一项与合同不同：打 NOTE，`meta.json` 写 `executor_binding_note`。
- 比较只读配置，不运行任何 CLI。绑定无效或未接通，也只是 NOTE。

**旧合同**：行为与 2.10 完全相同，包括 LB-CONTRACT-003 钉住的输入。

**Markdown**：

- Identity 写 `- executor: role:execution` 或 `role:contract`，与 JSON 的 `executor.role` 必须一致，两边都要写。
- 其他写法，以及它们经 derive-json 派生的结果，都不变。

**validate**：按角色的合同找不到绑定时打 WARN，因为 prepare 会拒绝。

**为什么 role 只有 execution 与 contract 两个值**：起草任务（第一轮的 B 组）就是经内核派给合同端 CLI 的普通合同；规划审核端与调度代理本轮没有无头调用。

**不在范围内**：planner-v2 合同（PD:2045）的 executor 规则不变，本轮不支持按角色写。

### D5 按合同版本的原子记录

**记录文件**：每个按角色的合同版本一份，路径是 `.agent/runs/<task-id>/binding-v<N>.json`。

- **创建**：由第一个解析成功的 prepare 以独占方式创建（`write_json(…, exclusive=True)`，底层是 O_EXCL）。并发的另一个 prepare 创建失败时，读取已有的那份来用，丢弃自己解析的结果。
- **内容**：
  - `role`、`profile`、`runtime`、`adapter`、`active_preset`；
  - `provider`、`model`、`thinking`；
  - `config_sha256`：解析时读到的配置文件字节的哈希；
  - `contract_json_sha256`：冻结合同的哈希；
  - `created_at`、`created_by_attempt`。
- **沿用**：
  - 之后的 attempt，冻结合同的哈希与记录不同时，拒绝（EXIT_DRIFT），提示“已派遣的版本不能改，出新版本”；
  - 当前绑定与记录不同时，打 NOTE：“绑定已改为 …；本版本沿用 …；要用新绑定，出新版本合同”。
- **为什么放在这里**：
  - task 目录里的文件不会被当成 attempt（2.6）；
  - 不放进 `meta.json`，因为每个 attempt 独占写自己的 meta，做不到“同一版本只有一份”。

**prepare 的顺序**（只针对按角色的合同）：

1. 只读一次配置字节，从同一份字节得到 dict 与哈希，后面各步都用它。
2. 预检，发生在分配 attempt 之前，失败时不留下 attempt：
   - 绑定存在、模式是 headless、适配器接通了这个角色；
   - 记录已经存在时，核对它。
3. 分配 attempt，冻结合同字节（PD:4232-4252，现有流程）。
4. 用冻结后的 raw 合同与第 1 步的配置解析，创建或读取版本记录。冻结合同的哈希与记录不符时失败；这时 attempt 记 PREPARE_FAILED，沿用现有处理（PD:4276-4279）。
5. 在 `meta.json` 的 `executor_binding` 里写下版本记录的副本，外加 `record_path`。

**run**：

- `meta.json` 有 `executor_binding` 时：
  - provider、model、thinking 取自它，tools、context_files 取自合同；
  - 之后再检查一次 `allowed_executors`（允许列表可能在 prepare 之后收紧了）与 `PI_EXEC_*` 冲突。
- `verify_inputs`（PD:3251-）新增一项检查：版本记录存在，且模型三项与 meta 中的副本一致；不一致就以 G0 拒绝。
- pi 的命令按记录里的 runtime 解析（D3）。本机文件在 run 时读：路径是本机事实，不进记录。

**`executor.json` 的形状不变**：仍是 provider、model、thinking、tools、context_files。来源只记在 meta 与版本记录里。

**读回收口**：PD 新增 `attempt_executor(run_dir, contract, fallback)`，按以下顺序取值：

1. `executor.json`；
2. 否则，取 meta 中 `executor_binding` 的 provider、model、thinking，加上合同的 tools、context_files；
3. 否则，取调用处原来的后备：PD:4522 用 `contract["executor"]`，PD:3500、5967、6147、6818 用 `{}`。

五处都改用它。可以到达的情形：领取之后、写 `executor.json` 之前崩溃，`collect --recover` 补收证据；之后的 summary 与 review-draft 照样能显示要求的执行模型。

**摘要多一行“执行模型来源”**：

- 角色绑定：写明 profile、runtime、方案、配置哈希的前 12 位，以及版本记录的路径；
- 合同写死：与当时的绑定不同时，写明差异；
- 合同加 `PI_EXEC_*`。

### D6 拒绝与退出码

- 按角色的合同没有绑定、模式不是 headless、与 manual 冲突，或者写法混用：`EXIT_USAGE`。
- 绑定指向本轮未接通的组合：`EXIT_BLOCKED`，与允许列表的拒绝相同（PD:3308）。
- 冻结合同与版本记录不符：`EXIT_DRIFT`。
- prepare 不运行任何 CLI。

### D7 写入历史与审计（事务）

**位置**：实现放在 `kit_config`。所有写配置的入口都已经依赖它；没有新模块时也照样工作（r1-B6）。

**快照按内容寻址**：

- 路径是 `.agent/config-history/<sha256>.json`，内容是配置文件的原始字节；已存在就不重写。
- 存之前先做凭据检查，遍历整份 JSON 的每个键与每个字符串：
  - 键名用 `_SECRET_KEY_RE`。值为空的键不算。
  - 值用 `RELEASE_PATTERNS["api key"]` 与 `_SECRET_TOKEN_RE`（PD:2433-2439、7314-7316）。
- **豁免存放变量名的键**：以 `_env` 结尾的键、`env_remove`、`env_keep`，例如 `decisions.api_key_env` 与 profile 的 `credential_env`。它们的值是环境变量名，不是凭据：
  - 值是合法的环境变量名，或者是这种名字组成的列表时，不算可疑；
  - 值不是这种形状时，照常算可疑。

  不豁免的话，带决策配置的快照永远存不下来。
- 命中就不存内容，审计里只记哈希，并注明原因。

**审计**：

- 路径是 `.agent/audit/management.jsonl`，只追加；
- 每条记录一行，用一次 `O_APPEND` 写入；
- 记录分三种：`observed`、`intent`、`commit`。

**一次写入就是一个事务**（`txn` 取 128 位随机数），步骤如下：

1. 校验新配置（现有）。
2. 读取当前文件的字节 P；文件不存在时，P 为空。
3. P 不为空，而它的哈希不是任何已提交记录的 after（历史为空也算）：追加一条 `observed` 记录（action `external`），并存下 P 的快照。
4. 存新字节 N 的快照。
5. 追加 `intent` 记录：txn、action、target、actor、confirmation，以及前后两份内容的哈希。
   - 写不进：不替换，退出 1，提示“没有写入：审计写不进去”。
6. 重读文件，与 P 不同：
   - 追加 `commit`，result 为 `conflict`；
   - 不替换，退出 1，提示“配置在这期间被改过：没有写入，请重试”。
7. 在同一目录用 `mkstemp` 建独立的临时文件，写入 N，然后 `os.replace`。
8. 追加 `commit`，result 为 `published`。
   - 写不进：退出 1，提示“已写入，但审计记录不全”；之后由读取方补判（见下）。

**补判**：`config history` 与每次写入的第 3 步都会读审计。只有 intent、没有 commit 的事务：

- 当前文件的哈希等于它的 after：视为已发布，标“补判”；
- 否则标“未完成”。

**保证**：

- 前态不会丢失：替换之前已经存了快照（第 3、4 步）。
- 每次替换之前都有一条 intent。
- 独立临时文件保证不会发布别人的内容。
- external 只在内容不认识时才出现。

**残余**：

- 第 6 步与第 7 步之间，另一个进程可能替换了文件，这次写入会把它覆盖掉。原因是本轮不加锁，沿用第一轮第 10 节第 3 项。
- 这时审计里两条都是 published，当前文件等于后一条的 after；`config history` 按当前文件的哈希标出哪条是现状。
- 是否加锁，见 10 节第 6 项。

**history**：

- `config history` 列出已提交的记录，按审计中的顺序编号。每条给出：
  - 时间、动作、目标、执行者、确认方式；
  - 变化的键：比较前后两份快照，列出顶层键与子键；
  - 快照没存内容时，写“内容未存（疑似凭据）”。
- `config history show <编号>` 给出逐键差异：键路径、旧值、新值。

**rollback `<编号>`**：

1. 取这条记录的 after 快照；没存内容的拒绝。
2. 解析成对象，整份校验。
3. 用 `raw_text` 原样写回字节，作为一个新的事务（action `config.rollback`）。

写完之后，文件与快照逐字节相同。

**actor**：

- 取环境变量 `CODEKIT_ACTOR`，值为 `user` 或 `agent:<角色>`；没设就记 `undeclared`。
- 这是自声明，不是认证（上位设计 8.6）。
- AGENTS.md 要求规划端代为写配置时，声明 `agent:planning_review`。

**写入的入口**：

- `write_config` 是唯一的替换点。
- 每个写入口都传 action 与 target：
  - `config set` / `unset` 记 `config.set` / `config.unset`；
  - `config init` 记 `config.init`，前态为空；
  - `config decisions` 记 `config.decisions`；
  - `kit_plugins` 的 enable / disable 记 `plugin.enable` / `plugin.disable`。“已写入但审计记录不全”的错误原样透传，不包成“写入失败”（`kit_plugins.py:634-635`）；dry-run 与无变化不产生事务；
  - kit_roles 的命令记 4.4 列出的动作。

**本机文件**：

- 写入走同样的事务，但不存快照，因为内容是本机路径；
- 审计只记前后两份内容的哈希。

**不提交**：history 与 audit 两个目录都加入忽略规则（D11）。

### D8 方案与切换

**方案命令**：

- **`preset save <名> [--description …] [--roles a,b] [--force]`**：
  - 把当前 roles 中列出的角色存成方案；不带 `--roles` 时，存全部已写的角色；
  - 同名方案已存在时，要加 `--force`。
- **`preset use <名>`**：
  - 把方案里的角色写进 roles，只覆盖方案列出的那些，并把 `active_preset` 设为这个方案。
  - 写入之前列出影响：
    - 运行中与已准备的 attempt：不受影响，它们的执行模型已经固定；
    - 还没派遣过、按角色写的合同版本：会用新绑定；
    - 已派遣过的这类版本：沿用自己的版本记录。
- **单独改角色之后**：`role set` 不清除 `active_preset`。`preset show <当前方案>` 与 `role show` 会标出与方案不一致的角色。
- **其他子命令**：
  - `preset diff A B`：逐角色比较；
  - `preset list`、`preset show`；
  - `preset remove <名>`：拒绝删除当前方案。上位设计 8.5 没有列 remove；不加的话，方案只增不减（10 节第 4 项）。

**运行中切换要确认**（上位设计 8.1，r1-B7）：

- **触发条件**：同时满足两点。
  - 写入会改变 execution 或 contract 的生效绑定，即解析出的 runtime、provider、model、thinking 有任何一项变化；
  - 有 attempt 正处于 RUNNING 或 COLLECTING，或者已经领取。判断沿用 `get_state` 与 `claim/` 目录。
- **要求**：带 `--yes`；没带就拒绝，退出 1，并列出这些 attempt。带了，审计记 `confirmation: flag`；其余写入记 `none`。
- **适用范围**：对所有写入口一视同仁，不按命令名单判断，比较的是写入前后的生效绑定：
  - `role set`、`preset use`、`profile edit`、`runtime add --force`、`rollback`；
  - 对五个键的通用 `set` / `unset`。
- **只影响下一次 attempt**：版本记录（D5）已经固定了运行中的 attempt。

**批准失效**：P3 之前没有批准记录。审计的 `invalidated_approvals` 固定为空列表，note 注明这一点。

### D9 凭据与环境

- **可用性按子进程的实际环境判断**：
  - 一个 `credential_env` 名字算可用，要求它出现在 `child_env(config)` 的结果里；
  - 这个判断已经考虑默认移除列表、`env_remove` 与 `env_keep`，名字按大写比较（PD:599-617）。
- **凭据库只作说明**：
  - 另外报告凭据库在哪一层（2.7 的 `describe`）；
  - 凭据库里有值，不等于执行器拿到了这个环境变量，所以不算就绪。本轮不定义从凭据库注入环境的链路。
- **措辞**：配置中心不返回、不输出、不记录凭据值。`describe` 内部会读取凭据库来判断来源，这一点照实写明。

### D10 `config doctor`（就绪总览）

**每个角色一行**，内容是：

- 模式、profile、runtime、适配器；
- 命令与它的来源：环境变量、本机文件或 PATH；
- 版本；
- 模型是否在列表中；
- 登录是否就绪；
- 思考级别是否受支持；
- 是否在 `allowed_executors` 中；
- 凭据可用性（D9）；
- 接通状态。

**探测的复用**：

- 版本与帮助按 runtime 缓存；
- 模型列表与 `auth check` 按（runtime, provider, model）分别检查。所以两个角色共用一个 runtime、各用一个 profile 时，各自的模型与登录分开判断。

**与 doctor 共用一个函数**：

- 把 `cmd_doctor` 中列模型、`auth check --no-refresh` 与思考级别的那一段（PD:6972-7002）抽出来。
- 这个函数显式接收环境参数：旧 doctor 传 `None`，照旧继承环境；`config doctor` 传 `child_env(config)`。
- 旧 doctor 的参数条件、输出与退出码都不变，2.2 列出的测试照旧通过。

**其他**：

- 不调用模型。
- 退出码：全部就绪是 0；有未就绪的是 1；用法错误是 2。

### D11 忽略规则与规则文件

**忽略规则**：`gitignore.append.txt` 与本仓库的 `.gitignore` 追加三条，`kit_install update` 会把它们补给已安装的仓库：

- `.agent/dispatch.local.json`
- `.agent/config-history/`
- `.agent/audit/`

**几点说明**：

- **不用加进 `planner_paths`**：主工作区指纹不含被忽略的文件（PD:1058-1083）。上位设计 11 节说要加的那两条，随之不需要。
- **旧安装可能还没补上这些规则**：这时历史与审计文件是未被忽略的新文件，运行期间写配置会进“复审需要关注”。所以写配置时，若历史目录或审计目录没被忽略，打一行 WARN，提示运行 `kit_install update`。
- **本机文件没被忽略时不写，也不读**（D3）。

**AGENTS.md 的“必须遵守”**：执行模型一条改为三层。

- 执行模型由角色绑定决定（`config role show`）。新合同的 Identity 写 `role:execution`，不写 provider 与 model；合同写死了模型时，以合同为准。
- provider 与 model 必须与 `.agent/environment.md` 和 `pi --list-models` 中的精确 ID 一致。
- 下面几类改动都要用户同意：
  - 改角色绑定或方案（`config role set`、`config preset use`、`config rollback`）；
  - 改写死的模型；
  - 改思考级别。

  规划端代为写配置时，要设 `CODEKIT_ACTOR=agent:planning_review`。写死的模型要换，就出新版本合同。

**AGENTS.md 的“Codex 的沙箱”一节**写明各子命令的读写性质：

| 子命令 | 性质 |
|---|---|
| list / show / history / diff | 只读 |
| scan / probe / models / doctor | 运行本机 CLI 的只读命令；pi 的列模型在沙箱里可能失败，与 doctor 相同 |
| add / edit / remove / set / save / use / rollback | 只写工作区：配置、本机文件、历史与审计 |

**技能**：

- plan-task 的模板：Identity 的 executor 行给出两种写法，配置了 execution 绑定时用 `role:execution`；
- contract-guide：第四节与第九节补上规则；
- `SKILL.md:150`：改写；
- check-pi-env 第 8 步：改用 config 命令登记并绑定，不手写 JSON；
- review-pi：复审时核对“执行模型来源”与版本记录；
- 改完运行 `sync-adapters`。

### D12 模块与接入

**各部分放在哪里**：

| 位置 | 内容 |
|---|---|
| `scripts/kit_roles.py`（新） | v3 的解析与校验（D1）、适配器表（D2）、本机文件（D3）、各个命令、给内核用的 `resolve_role_executor` 与 `check_role_contract` |
| `kit_config` | 事务、快照与审计（D7）；运行中切换的确认（D8，经惰性导入 kit_roles 计算生效绑定；没有 v3 键时，生效绑定就是“由合同决定”，无需导入） |
| PD | `trusted_which`、`attempt_executor`、版本记录的读写、prepare 与 run 的接线 |

**`KIT_LOADED_FILES` 加入 `kit_roles.py`**：执行器因此不能改它，它也随 kit 发放。

**惰性导入**：

- 五个键都不存在、合同也不是按角色写的时候，`kit_config` 与 PD 都不导入 `kit_roles`。2.10 的路径与只拷了旧文件的临时仓库都不受影响（TD:196、2740-2743）。
- 需要它却缺文件时，报一行 ERROR，不冒堆栈。

**给内核的接口不抛异常**：

- **原因**：调度器以脚本方式运行时，模块名是 `__main__`，`kit_roles` 里的 `import pi_dispatch` 会再载入一份 PD（`kit_config` 现在就是这样，PD:7157-7163 → KC:44）。两份模块各有自己的 `DispatchError`。
- **返回值**：`resolve_role_executor` 等函数返回 `(值, 错误)`。
  - 错误是 `None`，或者 `{"message": …, "code": 2 | 3 | 4}`；
  - 三个码分别对应 `EXIT_USAGE`、`EXIT_BLOCKED`、`EXIT_DRIFT`（PD:59）。
- **边界上的转换**：kit_roles 在接口边界，把自己那份模块的 `pd.DispatchError`（取其 code）、OSError、ValueError 都转成错误返回值。调度器据此构造自己的 `DispatchError`。
- **其他跨模块依赖**：用到的只有 Repo 的属性与方法、字符串与整数常量，以及按同一文件路径算出的 `KIT_ROOT`，都不依赖对象的身份（第 1 轮 N2 的核对）。
- **测试位置**：内核的场景放在以子进程运行的 `tests/test_dispatch.py` 里（9.3）。

**`config` 的转发不变**（PD:7157-7163）：新子命令由 `kit_config.build_parser` 登记，转交给 `kit_roles`。`--yes` 是 `kit_config` 的全局选项。

## 4. 接口

### 4.1 命令

| 命令 | 读写 | 说明 |
|---|---|---|
| `config runtime list [--json]` | 读 | 已登记的 runtime、适配器，以及命令的来源 |
| `config runtime scan [--add]` | 读；`--add` 写配置 | 用 `trusted_which` 找 pi、claude、codex、opencode，只运行 `--version`；`--add` 把找到但未登记的，登记为与适配器同名的 runtime |
| `config runtime add <id> --adapter <a> [--command '<JSON 数组>'] [--force]` | 写；`--command` 写本机文件 | `--force` 才能改已有 runtime 的 adapter |
| `config runtime remove <id>` | 写 | 有 profile 引用时拒绝；同时删除本机文件里的条目 |
| `config runtime probe <id> [--json]` | 读 | 版本；pi 另报缺少的参数 |
| `config models <runtime> [--json]` | 读 | pi：列出 `pi --list-models` 的表，并标出哪些在允许列表里；其他适配器退出 1，提示在 profile 里手填 |
| `config profile show [<id>] [--json]` | 读 | |
| `config profile add <id> --runtime <r> --model <provider/id> [--thinking <级别>] [--credential-env <名>]…` | 写 | 不查本机模型列表（那是 `config doctor` 的事），所以不运行 CLI |
| `config profile edit <id> [--model …] [--thinking …] [--credential-env …] [--runtime …]` | 写 | |
| `config profile remove <id>` | 写 | 有角色或方案引用时拒绝 |
| `config role show [--json]` | 读 | 四个角色的生效绑定，并标出与当前方案不一致的地方 |
| `config role set <role> <profile>\|manual\|disabled\|interactive_host [--host <h>] [--cadence-seconds <n>]` | 写 | 未接通、不在允许列表时打 WARN |
| `config preset list / show <名> / save <名> … / use <名> / diff <A> <B> / remove <名>` | 见 D8 | |
| `config history [--json]`、`config history show <编号>` | 读 | 读时补判（D7） |
| `config rollback <编号>` | 写 | |
| `config doctor [--json]` | 读；运行 CLI 的只读命令 | D10 |

- **退出码**：沿用 `kit_config`。0 是成功；1 是校验失败、未就绪、冲突、需要确认，或审计记录不全；2 是用法错误。
- **全局选项**：`--yes`（D8）。
- **环境变量**：`CODEKIT_ACTOR`（D7）。
- **通用命令**：`config set` / `config unset` 照常可以改这五个键，同样经过校验、事务与确认。

### 4.2 合同的 executor

| 类别 | JSON | Markdown Identity |
|---|---|---|
| 写死（2.10） | `{"provider": "bb", "model": "step-5-preview", "thinking": "high", …}` | `- executor: bb/step-5-preview · thinking high` |
| 按角色 | `{"role": "execution", "tools": […], "context_files": "project"}` | `- executor: role:execution` |
| 按角色（合同端） | `{"role": "contract", …}` | `- executor: role:contract` |
| 旧合同（2.10） | 其余，例如 `{"thinking": "high", "tools": […]}` | 不变（`- executor: None/None · thinking high` 等） |

### 4.3 版本记录与 `meta.json`

版本记录 `.agent/runs/<task-id>/binding-v<N>.json`：

```json
{"role": "execution", "profile": "exec-step", "runtime": "pi", "adapter": "pi", "active_preset": "economy",
 "provider": "bb", "model": "step-5-preview", "thinking": "high",
 "config_sha256": "<64 位十六进制>", "contract_json_sha256": "<64 位十六进制>",
 "created_at": "2026-10-18T09:00:00Z", "created_by_attempt": "attempt-001"}
```

`meta.json` 里的两个字段：

- `executor_binding`：版本记录的副本，外加 `record_path`；
- `executor_binding_note`：只在写死合同与绑定不同时出现，内容是 `{"role": "execution", "profile": …, "binding": {"provider", "model", "thinking"}}`。

### 4.4 审计记录（每行一条）

```json
{"record_type": "management-audit", "schema_version": 1, "phase": "intent", "txn": "<32 位十六进制>",
 "audit_id": "aud-<32 位十六进制>", "at": "2026-10-18T09:00:00Z", "actor": "agent:planning_review",
 "action": "preset.use", "target": "economy",
 "before_ref": {"kind": "config-snapshot", "sha256": "…", "stored": true},
 "after_ref": {"kind": "config-snapshot", "sha256": "…", "stored": true},
 "invalidated_approvals": [], "confirmation": "flag", "note": "P3 之前没有批准记录"}
```

- **`commit` 记录**：只有 `phase`、`txn`、`audit_id`、`at`、`result`（`published` 或 `conflict`）。
- **`observed` 记录**：action 是 `external`，只带 after_ref。
- **action 的取值**：

  | 来源 | action |
  |---|---|
  | 配置管理器 | `config.set`、`config.unset`、`config.init`、`config.decisions`、`config.rollback` |
  | runtime | `runtime.add`、`runtime.remove`、`runtime.local_command` |
  | profile | `profile.add`、`profile.edit`、`profile.remove` |
  | 角色 | `role.set` |
  | 方案 | `preset.save`、`preset.use`、`preset.remove` |
  | 插件 | `plugin.enable`、`plugin.disable` |
  | 外部改动 | `external` |

## 5. 执行方式

- **由规划端直接做**。用户 2026-10-17 定了“M1 由规划端直接做”，P1 改的又是受保护文件（上位设计 11 节）。本轮不派 Pi，不调用任何模型；测试都用替身。
- **两项前置已单独提交**（§0 的“前置”）。
- **实现顺序**：
  1. kit_config 的事务、快照与审计；
  2. `kit_roles`：解析与校验；
  3. 命令；
  4. 内核：D3、D4、D5；
  5. 规则、技能与文档。

  每步都跑相关测试，最后跑全量与 `tests/test_dispatch.py` 的脚本方式。

## 6. 刻意不做

- 把 Pi 抽成适配器；改 `pi_preflight`、事件解析与 Pi 品牌化的输出（调查摘要的绑定点 2–7、10）。
- 统一 doctor 与预检在 `--no-refresh` 上的不一致（2.2）。
- 接入 `codekit/adapters/` 与 `codekit/config_profiles.py`。
- 第二个 CLI 的无头调用；规划审核端与调度代理的无头调用。
- 把命令或路径写进提交的配置（D3）。
- 批准失效：留到 P3。
- 给配置写入加锁：沿用第一轮的决定，残余窗口见 D7 与 10 节第 6 项。
- Windows 上以裸名启动的 `git`、`bash` 等子进程的查找（D3 的既有残余，10 节第 8 项）。
- 从凭据库向执行器注入环境变量（D9）。
- 用户级方案库、方案的导入导出、管理台网页。
- doctor 的输出改动，以及在 prepare 里运行 CLI。
- planner-v2 合同按角色写。

## 7. 影响面清单

### 7.1 要改的

| 位置 | 改动 |
|---|---|
| `scripts/kit_roles.py`（新） | D1–D3、D8 的命令部分、D10 |
| KC:256-274 | 五个键追加在末尾；检查函数在键缺省时立即返回 |
| KC:397-404 | `write_config` 改成事务：独立临时文件、CAS、快照、审计、`raw_text` |
| KC:491-497、502-538、541-555、558-583 | `write_checked` 与 set / unset / init / decisions 传 action 与 target；init 改经事务 |
| KC:757-796 | 登记新子命令与全局 `--yes`，转交 `kit_roles` |
| `kit_plugins.py:628-640` | 传 action；透传“审计记录不全” |
| PD:96-101 | `KIT_LOADED_FILES` 加 `scripts/kit_roles.py` |
| PD:1641-1714 | `derive_contract_json` 认 `role:<r>` |
| PD:1814-1828、1939-1944 | 三类的校验、混用检查，以及 Markdown 与 JSON 的一致性 |
| PD:2293-2320 | `trusted_which`；`resolve_pi_command` 加 `repo_root` 参数、按 runtime 解析 |
| PD:3251- | `verify_inputs` 核对版本记录 |
| PD:3282-3313 | 按角色时用记录；`PI_EXEC_*` 与记录比较 |
| PD:4194-4290 | prepare：按角色的预检、冻结之后创建或读取版本记录、meta；写死合同之后的 NOTE |
| PD:4334-4342 | run：用记录，按 runtime 解析命令，传 `repo_root` |
| PD:3500、4522、5967、6147、6818 | 改用 `attempt_executor` |
| PD:3497-3514 | 摘要的“执行模型来源” |
| PD:6955-7002 | 抽出 pi 的就绪检查，doctor 与 `config doctor` 共用 |
| PD:6956、7421 | doctor 与 smoke 调用 `resolve_pi_command` 时传 `repo_root` |
| `gitignore.append.txt`、`.gitignore` | 三条规则 |
| AGENTS.md:57-60、87-89 | D11 |
| `.agents/skills/plan-task/`、`check-pi-env/`、`review-pi/` | D11，改完运行 `sync-adapters` |
| README、CHANGELOG、`.claude/settings.example.json` | 命令表、版本说明，以及只读子命令的放行规则 |
| `tests/` | 第 9 节 |

### 7.2 刻意不改的

- `scripts/codekit/**`：本仓库对执行器受保护，本轮只读。
- `pi_preflight`（PD:2547-）与事件解析（PD:2693-）。
- doctor 的输出。
- 已有的合同与证据。
- `allowed_executors` 的形状。

## 8. 上线顺序与回滚

- **兼容**：五个键都缺省时，写死合同与旧合同的行为与 2.10 一致。只有两处行为变化：
  - `trusted_which` 的收紧（10 节第 7 项）；
  - 写配置会留下历史与审计。

  全量回归、遗留刻画用例与 `tests/test_dispatch.py` 的 404 项检查都不改期望值。新增的只有场景本身，以及 `config show` 多出的键行。
- **回滚**：
  - 删掉五个键，就回到 2.10 的行为；
  - 已有 attempt 的 meta 中多出的字段与版本记录文件，旧版本会忽略；
  - 历史与审计目录是本机记录，可以直接删除。
- **本仓库的配置**：本轮不改 `.agent/dispatch.config.json`（10 节第 1 项）。

## 9. 测试计划

针对本轮候选的测试，都以子进程或进程内的方式运行当前代码。锁定历史的遗留单元测试（经 `legacy_harness` 读 `git show` 的源码）只证明历史实现的刻画不变，不能算作本轮的证据。

### 9.1 配置（`tests/test_kit_roles.py`）

| 编号 | 场景 | 防的失败 |
|---|---|---|
| C1 | 每个键的未知子键、类型错误、ID 不合法；校验失败时配置字节不变 | 坏配置被写入 |
| C2 | 模式与角色不匹配：execution 用 manual、contract 用 interactive_host、host 不是宿主适配器 | 绑定语义被绕过 |
| C3 | 悬空引用：profile 引用不存在的 runtime，角色或方案引用不存在的 profile，`active_preset` 指向不存在的方案 | 悬空引用 |
| C4 | 凭据：任一键名是敏感键（如 `api_key`），或任一字符串含凭据或令牌形状（含方案的 description），都会被拒 | 内联密钥进配置 |
| C5 | runtime 带 `command` 或其他键时报错 | 提交的配置指定命令 |
| C6 | 本机文件只接受 `runtimes.<id>.command`；未登记的 ID 打 WARN | 本机文件夹带模型或策略 |
| C7 | pi 的 thinking 不在级别里；非 high 的值与缺省值都能解析；其他适配器的 options 非空 | profile 选项错 |
| C8 | `credential_env` 名字不合法 | |
| C9 | 五个键缺省时，`config show` 与 `validate` 的输出与 2.10 一致（新增键行除外）；只拷旧文件、没有 `kit_roles.py` 的临时仓库里，show、validate、set 都可用 | 兼容被破坏（r1-B6） |

### 9.2 写入事务（`tests/test_kit_config.py`）

| 编号 | 场景 | 防的失败 |
|---|---|---|
| T1 | 每次写入都依次产生快照、intent、commit；rollback 之后文件与快照逐字节相同，包括 CRLF、没有末尾换行、Unicode 与空白排版 | 回滚复现不了原快照 |
| T2 | 手改配置之后再写：先记 `observed`，并存下前态的快照；前态含敏感键（如 `"api_key": "opaque"`）或凭据形状时只存哈希；含 `decisions.api_key_env`、`credential_env` 与 `env_remove` 的正常配置照常存内容 | 外部改动丢失；密钥留在历史里；豁免缺失导致历史存不下 |
| T3 | intent 写不进：不替换，退出 1 | 没有记录的替换 |
| T4 | 替换成功但 commit 写不进：退出 1；history 补判为已发布 | 只有审计失败时之后不再补记（r1-B4 的第 1 条） |
| T5 | 第 5、6 步之间有别的进程改了文件（用替身）：结果是 conflict，没有替换 | 覆盖别人的写入 |
| T6 | 两个写入的临时文件互不覆盖：替身让 `os.replace` 之前暂停 | 发布别人的内容（r1-B5） |
| T7 | init：前态为空；decisions、`plugins enable` / `disable` 的动作都对；dry-run 与无变化不产生事务；插件“审计记录不全”的错误原样透传 | 有写入绕过历史 |
| T8 | 写入时历史目录没被忽略：打 WARN；`CODEKIT_ACTOR` 的取值，没设时记 undeclared；audit_id 不重复 | |
| T9 | history 列出变化的键；history show 给出逐键差异 | 历史没有差异 |

### 9.3 配置中心命令（`tests/test_kit_roles.py`；CLI 用 PATH 上的替身程序，pi 用 `tests/stub_pi.py`）

| 编号 | 场景 | 防的失败 |
|---|---|---|
| M1 | scan 用 `trusted_which` 找到替身，只运行 `--version`；仓库之内的 PATH 项与当前目录里的同名程序不被选中；`--add` 登记 | 探测运行了别的命令；执行了仓库里的程序 |
| M2 | runtime add / remove：`--command` 只写本机文件；本机文件已被跟踪、没被忽略、经过链接时，读和写都拒绝；有引用时拒绝 remove；命令的优先级 | 命令进了提交的配置；绕过信任边界（r1-B1） |
| M3 | models：替身 pi 的模型表，以及允许列表的标记；非 pi 退出 1 | |
| M4 | profile add 写对字段；edit 只改指定的项；非法的 edit 不写入；有引用时拒绝 remove | |
| M5 | role set 的各种模式；未接通时打 WARN；`config unset roles.execution` 回到“由合同决定” | |
| M6 | preset save / use / diff / remove：use 只覆盖列出的角色，写 `active_preset`，列出影响；不能删除当前方案 | 方案覆盖了没列出的角色 |
| M7 | 有 RUNNING 的 attempt 时，role set、preset use、profile edit、rollback 与通用 set 改变生效绑定都要 `--yes`；不改变生效绑定的写入不需要 | 运行中切换不确认（r1-B7） |
| M8 | doctor 的几种情况：替身 pi 就绪、模型不在列表、auth 失败、未接通的适配器；共用 runtime 的两个 profile 分开判断；`credential_env` 被默认列表或 `env_remove` 移除，以及被 `env_keep` 保留时；退出码 | 就绪判断错（r1-S2、S3） |
| M9 | 不调用模型：替身记录每次的 argv，成功与失败的分支里都没有带提示的调用；profile add 不运行 CLI | 管理面偷偷花钱 |
| M10 | 旧 doctor 的输出、退出码，以及不过滤环境的语义都不变（与 2.2 列出的测试一起） | 抽取共用函数时改了 doctor |

### 9.4 内核（`tests/test_dispatch.py` 的新场景，用替身 pi，子进程方式运行）

| 编号 | 场景 | 防的失败 |
|---|---|---|
| K1 | 写死合同、绑定不同：用合同的模型，打 NOTE，记 note；允许列表与环境变量冲突时的拒绝顺序不变 | 写死的合同被绑定改掉（r1-B3） |
| K2 | 按角色合同加绑定：prepare 创建版本记录，run 的 argv 用记录里的模型 | 绑定没生效 |
| K3 | 同一版本的第二个 attempt，在改绑定之后：沿用记录并打 NOTE | 同一版本中途换模型 |
| K4 | 并发首次准备同一版本：<br>① 单元测试：第二个创建者撞上已存在的记录（`FileExistsError`）时，读取并使用已有的那份，丢弃自己的解析结果；<br>② 端到端：两次 prepare 之间改绑定，两个 attempt 的 meta 都与同一份记录一致 | 同一版本两份快照（r1-B2） |
| K5 | 按角色合同在首次 prepare 之后被改：哈希不符，拒绝（EXIT_DRIFT） | 记录对应旧合同 |
| K6 | 新版本用新绑定 | 记录锁死了新版本 |
| K7 | `role:contract` 没有绑定、contract 是 manual：prepare 拒绝，退出 2，不留 attempt，不运行 CLI | |
| K8 | 绑定到未接通的适配器：prepare 退出 3，不留 attempt | 派给没实测的 CLI |
| K9 | `PI_EXEC_PROVIDER`、`PI_EXEC_MODEL`、`PI_EXEC_THINKING` 各自与记录冲突：拒绝，包括在 prepare 之后才设的情形 | |
| K10 | prepare 之后收紧 `allowed_executors`，或改了固定的 thinking：run 拒绝 | 绕过允许列表 |
| K11 | 本机文件的命令被 run 使用；`PI_DISPATCH_PI_CMD` 仍然优先；PATH 上仓库之内的 pi 不被选中 | 命令来源错（r1-B1） |
| K12 | Markdown 的 `role:` 行，经 derive-json 与一致性校验；`role` 与 provider 或 thinking 同时写时报错；旧合同（LB-CONTRACT-003 那种）的派生结果与校验警告都不变 | 三类混淆（r1-S1） |
| K13 | 领取之后、写 `executor.json` 之前崩溃，再 `collect --recover`：summary 与 review-draft 显示的是记录里的模型 | 读回点没收口（r1-S5） |
| K14 | 版本记录在 run 之前被改：G0 拒绝 | |
| K15 | 摘要中“执行模型来源”的三种写法 | |

### 9.5 接线

| 编号 | 场景 |
|---|---|
| W1 | `KIT_LOADED_FILES` 含 `kit_roles.py`；import 扫描一致；`kit_install` 装进临时仓库后，`config role show` 与 `config doctor` 可用（`tests/test_kit_v300.py`） |
| W2 | `gitignore.append.txt` 含三条规则；`kit_install update` 补上它们 |
| W3 | 全量 `python -m pytest tests`；`tests/test_dispatch.py` 以脚本方式运行。这一条是执行清单，不对应单个失败场景 |

## 10. 待用户拍板（推荐项写在前）

1. **本仓库自己要不要现在就绑定**：
   - 推荐：本轮不改本仓库的配置，交付后由你决定。命令是 `config runtime add pi --adapter pi`、`config profile add exec-step --runtime pi --model bb/step-5-preview`、`config role set execution exec-step`；
   - 或者：交付时顺带配好。
2. **历史与审计提交与否**：
   - 推荐：不提交，它们是本机的切换记录；
   - 或者：提交。
3. **本机覆盖文件**：
   - 推荐：新增 `.agent/dispatch.local.json`，只放命令路径；
   - 或者：本轮不做，自定义路径只能用 `PI_DISPATCH_PI_CMD`。
4. **`preset remove`**：
   - 推荐：加上；
   - 或者：照上位设计 8.5 不加。
5. **版本号**：合并时再定。推荐 2.12.0：P2–P6 还没做，不记 3.0.0。
6. **配置写入加不加锁**：
   - 推荐：本轮不加，用 CAS 检测冲突，D7 写明残余的竞争窗口；
   - 或者：加一把文件锁。这样会改变第一轮第 10 节第 3 项的决定，所有写配置的入口都要改成“持锁读改写”。
7. **PATH 查找的收紧**：
   - 推荐：`resolve_pi_command` 也改用 `trusted_which`，仓库里的 `pi.cmd` 与 `node.exe` 不再被选中。代价：把 pi 装在仓库之内、又把那个目录放进 PATH 的用户，要改设 `PI_DISPATCH_PI_CMD` 或本机文件；
   - 或者：只在新命令里用它，2.10 的路径不变，那一条列为残余。
8. **Windows 上裸名启动的其他程序**（`git`、`bash` 等，由 CreateProcess 查找，会先查调度器进程的当前目录）：
   - 推荐：本轮不改，作为既有残余记下，另立任务。修法是启动时用 `trusted_which` 定位，之后用绝对路径调用，要改调度器里每一处 `git(...)` 与 `run_capture`；
   - 或者：本轮一并修。
