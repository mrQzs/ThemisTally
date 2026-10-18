# Themis Tally 3.0 第二轮设计：角色绑定（轻量底座）与配置中心

状态：草稿，送 2gate 闸一第 1 轮（2026-10-18）。

- 分支：`themis-3.0`（本地，不推送）。起点是 `106e94a`（2.11.0，已快进合并到本地 master）。
- 上位设计：`docs/themis-tally-3.0-四端分层解耦架构.md`，涉及 3.4、6.3、7、8.1、8.5、8.6、11 节，以及 12 节的 P1、M1。
- 调查：`.agent/design/3.0-r2-调查摘要.md`，做于 `b5e9ea5`。
- 下文的 `file:line` 都在 `106e94a` 上重新核对过。缩写：
  - PD = `scripts/pi_dispatch.py`
  - KC = `scripts/kit_config.py`
  - TD = `tests/test_dispatch.py`
  - TD 的行号含前置提交（见第 5 节）。

## 0. 审核变更对照表

| 编号 | 结论 | 本稿处置 |
|---|---|---|
| — | 第 1 轮送审前为空 | — |

## 1. 范围

### 1.1 用户决定（2026-10-18）

- 开第二轮，走 2gate。
- **P1 做轻量底座**：
  - 做：解析 v3 的角色绑定与方案，登记适配器；内核按 execution 角色（以及声明为合同端的合同）解析执行模型；配置中心七项功能全做，`runtime scan` 只查 PATH。
  - 不做：把 Pi 抽成适配器，留到接第二个 CLI（P4）时再做。
- **执行模型以绑定为准**：
  - 新合同不写 provider 与 model；prepare 按当前绑定解析，并按合同版本记一份快照，同一版本之后的 attempt 沿用；
  - 写死了模型的合同仍以合同为准，与绑定不一致时提示；
  - AGENTS.md 的“换模型要写进新合同”改为“换绑定要用户同意”。

### 1.2 本轮交付

1. **配置 v3 的五个键**：`runtimes`、`profiles`、`roles`、`presets`、`active_preset`（D1）。
   - 实现与校验在新模块 `scripts/kit_roles.py`；
   - 在 `kit_config` 的 KEYS 末尾登记；
   - 本机覆盖文件 `.agent/dispatch.local.json`（D3）。
2. **配置中心命令**（上位设计 8.1 的七项与 8.6 的审计）：
   - runtime 的 scan / add / remove / probe / list；
   - models；
   - profile 的 add / edit / remove / show；
   - role 的 show / set；
   - preset 的 list / show / save / use / diff / remove；
   - history、rollback；
   - `config doctor`（D7–D10）。
3. **写入历史与审计**：每次写配置都在 `.agent/config-history/` 存快照，并在 `.agent/audit/management.jsonl` 追加一条审计记录（D7）。
4. **内核**：
   - 合同 executor 的两种写法（D4）；
   - prepare 解析绑定，把快照写进 `meta.json`，同一合同版本沿用；run 只用快照（D5）；
   - 按 runtime 定位 pi 的命令（D3）；
   - 摘要写明执行模型的来源。
5. **规则、技能与文档**：
   - AGENTS.md；
   - plan-task 的模板、contract-guide 与 SKILL.md；
   - check-pi-env；
   - README、CHANGELOG；
   - `gitignore.append.txt` 与本仓库的 `.gitignore`（D11、D12）。

### 1.3 不在本轮

- 把 Pi 抽成适配器、接入 `scripts/codekit/adapters/`、generic 适配器：P4。
- 第二个 CLI 的无头调用：P4，而且每次真实调用都要用户另行授权。
- 规划审核端与调度代理的无头调用（P6、P5）：本轮只记录它们的绑定，并在就绪总览里报告。
- 审核与批准随配置变化失效：P3 之前还没有批准记录（D8）。
- 管理台网页（M4）、用户级方案库（15.2 第 10 项的可选部分）。
- 上位设计 6.3 里的 `policies`、`feedback`、`logging`、`ui` 键。

## 2. 现状（承重事实）

### 2.1 合同里的执行模型

- **补齐与校验**：
  - `normalize_contract` 给 executor 补 thinking、tools、context_files，不补 provider、model（PD:1440-1450）；
  - `validate_contract` 允许 provider、model 缺省，只在有值时校验格式（PD:1814-1818）；thinking 必须是已知级别（PD:1819-1821）。
- **Markdown 写法**：
  - Identity 的 executor 行必须写成 `provider/model · thinking <级别>`（`derive_contract_json`，PD:1652-1655，派生结果见 PD:1709-1714）；
  - JSON 写了 provider、model 时，Identity 必须写明它们与 thinking（PD:1939-1944）。
- **解析时机**：
  - prepare 只在 raw 合同同时写了 provider 与 model 时提前解析（PD:4200-4202）；
  - 真正的解析在 run（PD:4323）；`executor.json` 在领取之后才写入（PD:4376）。
- **解析规则**（`resolve_executor`，PD:3270-3301）：
  - 合同为准；
  - `PI_EXEC_*` 只补缺，与合同的显式值冲突时报错；
  - `allowed_executors` 非空时检查。
- **读回**：
  - `executor.json` 不存在时，collect 退回 `contract["executor"]`（PD:4510）；
  - 摘要、branch、复审骨架、metrics 退回空对象（PD:3488、5955、6135、6806）。
- **meta.json**：在 prepare 时独占写入（PD:4245-4256），没有执行模型的来源或配置的快照。

### 2.2 pi 的命令与就绪检查

- `resolve_pi_command`（PD:2293-2320）：
  - `PI_DISPATCH_PI_CMD` 优先；否则用 PATH 上的 pi；
  - Windows 上绕过 npm 的 `.cmd` 包装；
  - 批处理特殊字符的检查在 `ensure_argv_safe`（PD:2322-2328）。
- `doctor`（PD:6943-6990）：
  - 运行 `--version` 与 `--help`；
  - 带 `--provider`、`--model` 时，再核对模型列表、`auth check --no-refresh` 与思考级别。
- 预检的 auth check 不带 `--no-refresh`（PD:2591）。这处不一致是既有现象（调查摘要第 6 条），本轮不改。
- 辅助函数：`parse_help`（PD:2393-2404）、`list_models_rows` / `list_models_empty_reason`（PD:2407-2429）。

### 2.3 配置管理器

- **键与校验**：
  - KEYS 在 KC:256-274；未知键是错误（KC:305-327）；
  - `split_path` 最多两层，只在第一个点处分开（KC:414-419）。所以 `config set roles.execution '{…}'` 与 `config unset roles.execution` 现在就能用。
- **写入**：
  - `write_config` 用固定的临时文件名加原子替换（KC:397-404）；
  - `write_checked` 先整份校验再写（KC:491-497）；
  - `cmd_init` 绕过 `write_checked`，直接调用 `write_config`（KC:541-555）；
  - `kit_plugins` 经 `write_checked` 写 plugins 段（第一轮）。
- **测试钉住的地方**：`config show` 的第二个键必须是 `worktree_root`（TD:2749）。新键追加在末尾，不受影响。
- **调度器读配置**：`Repo.config()` 宽松读取，忽略未知键（PD:1150-1160）。

### 2.4 离线参考实现不接

- `scripts/codekit/config_profiles.py`：
  - 用的是 v2 的角色名 supervisor、planner、executor、observer（CP:26）；
  - 只认 `schema_version` 2，凭据字段叫 `credential_refs`（调查摘要第 3 条）；
  - 只有 `tests/test_config_profiles.py` 与 `tests/test_config_policy_boundaries.py` 导入它。
- `scripts/codekit/adapters/` 的准入模型要求只读，与执行端冲突（调查摘要第 1 条）。

### 2.5 环境与凭据

- `child_env` 对执行器与检查命令移除默认列表与 `env_remove`（PD:599-617）。默认列表含 `CLAUDE_CODE_OAUTH_TOKEN`（PD:130）。
- 决策模型的 `Session` 缺省读 `os.environ`（`codekit/decisions.py:672`），调度器创建它时不传 environ（PD:3723）。
- `release-check` 的凭据形状规则是 `RELEASE_PATTERNS["api key"]`（PD:7302-7304）。

### 2.6 忽略规则、安装与测试接线

- 本仓库 `.gitignore` 忽略 `.agent/runs/` 与 `.agent/baseline/`。
- `kit_install` 把根目录的 `gitignore.append.txt` 追加进目标仓库的 `.gitignore`（`kit_install.py:63`）。
- 主工作区指纹不含被忽略的文件（PD:1058-1083）。
- `KIT_LOADED_FILES`（PD:96-101）同时决定两件事：执行器不可改，以及随 kit 发放（`kit_install.py:197`）。
- 端到端测试的临时仓库只拷 `pi_dispatch.py` 与 `dispatch-pi.sh`（TD:196）；需要 `kit_config.py` 的场景自己再拷（TD:2740）。所以调度器与 `kit_config` 都不能在导入时就依赖新模块。

### 2.7 规则与技能里写死的执行模型

- AGENTS.md:
  - 87-89：“执行模型默认用 Step 系列……更换模型或思考级别需要用户同意，并写进新合同”；
  - 103：改配置要征得用户同意。
- plan-task:
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

- **ID**：runtime、profile、preset 的 ID 沿用 `TASK_ID_RE`（PD:62），不新造口径。
- **严格形状**：每个对象只接受下面列出的键，下划线开头的键是说明。

**各键的规则**：

- **`runtimes.<id>`**：只有 `adapter`，取值是 D2 表里的适配器。不能写命令或路径（D3）。
- **`profiles.<id>`**：
  - `runtime`：必须已登记；
  - `model`：`{provider, id}`，两项都要符合 `MODEL_TOKEN_RE`，且不能命中 `PLACEHOLDER_RE`（PD:65、67）；
  - `options`：按适配器校验。pi 只接受 `thinking`，取值必须在 `FALLBACK_THINKING_LEVELS` 里（PD:74），不写时按 `high` 解析，与合同的缺省相同（PD:73）；其他适配器的 `options` 必须为空；
  - `credential_env`：环境变量名的列表，用 `env_remove` 的同一个检查（KC:131-136）。
- **`roles`**：只有四个角色名，每个角色允许的模式取自上位设计 6.3：

  | 角色 | 允许的模式 |
  |---|---|
  | planning_review | `interactive_host`（`host` 为 claude-code 或 codex）、`headless` |
  | contract | `manual`、`headless` |
  | execution | `headless` |
  | scheduler_agent | `disabled`、`headless`（可带 `cadence_seconds`，整数，至少 60） |

  - `headless` 必须带已登记的 `profile`；
  - 没写的角色取默认值：planning_review 是 `interactive_host`（宿主未声明），contract 是 `manual`，execution 由合同决定（2.10），scheduler_agent 是 `disabled`。
- **`presets.<name>`**：
  - `description` 可选；
  - `roles` 至少写一个角色，规则同上；
  - 方案只覆盖它列出的角色。
- **`active_preset`**：必须是已有的方案名。

**凭据**：五个键里所有的字符串都过 `RELEASE_PATTERNS["api key"]`，命中就报错。形状是严格的，没有地方放 `api_key` 一类的键，所以这条覆盖了上位设计 6.3 的“拒绝内联密钥”。

**接入 `kit_config`**：

- 五个键追加在 KEYS 末尾。
- 各自的检查函数惰性导入 `kit_roles`。这样 `config validate`、`write_checked`，以及第一轮的 plugins 写入，都能看到 v3 的错误。

**不加 `schema_version`**：五个键都缺省时，等价于 2.10 的兼容预设（上位设计 11 节）；写了 `roles` 才启用绑定。

**允许列表沿用 `allowed_executors`，不新增 `policies.allowed_models`**：它已经在 `resolve_executor` 里强制执行（PD:3290-3300），绑定解析出来的模型同样要过它。

### D2 适配器登记

适配器是 `kit_roles` 里的一张静态表，不是插件：

| 适配器 | 程序名 | 本轮接通的无头角色 | 交互式宿主 | 列模型 | 登录就绪 | options |
|---|---|---|---|---|---|---|
| pi | `pi` | execution、contract | 否 | `pi --list-models` | `pi auth check --no-refresh` | thinking |
| claude-code | `claude` | 无 | planning_review | 否 | 否 | 无 |
| codex | `codex` | 无 | planning_review | 否 | 否 | 无 |
| opencode | `opencode` | 无 | 否 | 否 | 否 | 无 |

- **未接通的组合**：绑定到“本轮未接通”的组合是合法配置，可以提前登记。这时：
  - `config role set` 与 `preset use` 打 WARN；
  - `config doctor` 报未就绪；
  - prepare 拒绝（D6）。
- **为什么用静态表**：接入一个 CLI 要实测（上位设计 7.3）；声明式的 generic 适配器留到插件安装那一轮。

### D3 命令路径与信任边界

**提交的配置里不写命令**：`runtimes.<id>` 只写 adapter，不写可执行文件的路径或参数。原因有两条：

- 配置随仓库分发。克隆来的仓库不应能让 `config doctor`、`prepare` 或 `run` 运行任意命令。
- 本机路径会被 release-check 的家目录规则报出（PD:7305-7306）。

**本机路径放 `.agent/dispatch.local.json`**：

- 新增文件，加入忽略规则（D11），只接受一个形状：`{"runtimes": {"<id>": {"command": ["<程序>", "<参数>", …]}}}`；
- `command` 是非空的字符串数组；
- 文件里的 runtime ID 在提交的配置里没有登记时，报 WARN，不报错：本机文件可能是给别的分支准备的；
- 读写它的代码只有 `kit_roles` 一处；
- 写它之前，用 `git check-ignore` 确认它已被忽略；没被忽略就拒绝写入，提示先运行 `kit_install update` 或补上忽略规则。这与 prepare 要求 `.agent/runs/` 被忽略是同一个道理（PD:4194-4195）：本机路径进了提交，release-check 才会发现。

**pi 的命令按以下顺序解析**：

1. `PI_DISPATCH_PI_CMD`：沿用，测试与现有用户都依赖它；
2. 本机文件里这个 runtime 的 `command`；
3. PATH 上的 pi，沿用 `resolve_pi_command` 对 `.cmd` 的处理。

其他适配器的顺序是：本机文件，然后 PATH 上的程序名。

**命令的安全**：

- 本机文件给出的命令，执行前过 `ensure_argv_safe`（PD:2322-2328）。
- 探测（scan、probe、`config doctor`）只运行 `<命令> --version`。pi 另外运行 `--help`、`--list-models` 与 `auth check --no-refresh`，和 `doctor` 相同（D10）。
- 探测时的环境用 `child_env(config)`：与执行器同样过滤推送凭据与 `env_remove`。

**写死模型的合同不读本机文件**：这类合同不引用 runtime，pi 的命令照 2.10 的方式解析（环境变量，然后 PATH）。

### D4 合同的两种 executor 写法（用户决定：绑定为准）

**写死**：raw 合同同时写了 provider 与 model。这是 2.10 的写法，现有合同全是这种。

- 以合同为准，解析规则不变：`PI_EXEC_*` 与显式值冲突就报错，再过 `allowed_executors`。
- 配置了 execution 绑定，而它解析出的 provider、model、thinking 有任何一项与合同不同时，prepare 打一行 NOTE，`meta.json` 记下差异，不阻塞。

**按角色**：raw 合同不写 provider、model，也不写 thinking。

- JSON 有可选的 `executor.role`，取值是 `execution` 或 `contract`，缺省是 `execution`。
- Markdown 的 Identity 写 `- executor: role:execution` 或 `role:contract`。`derive-json` 认这两种写法，派生出的 JSON 没有 provider、model、thinking。
- 解析：
  - 这个角色有 `headless` 绑定：provider、model、thinking 都取自绑定的 profile；
  - 没有绑定，且 role 是 `contract`：报错，提示用 `config role set contract <profile>` 配置绑定；
  - 没有绑定，且 role 是 `execution`：走 2.10 的路径（`PI_EXEC_*` 补缺）。缺模型时的错误提示加一句“或配置 execution 角色绑定”；
  - contract 角色是 `manual`，合同却写了 `role:contract`：报错，提示改绑定或改合同。
- `PI_EXEC_*` 与绑定同时存在且不同：报错。这与“合同为准”时的处理对称。

**写法混用**：

- raw 合同写了 `role`，又写了 provider、model 或 thinking：`validate` 报错。
- 只写了 provider 或 model 之一：
  - 有 execution 绑定时报错；
  - 没有绑定时，照 2.10 由 `PI_EXEC_*` 补缺。

**validate 也读配置**：按角色写的合同找不到对应的绑定时，validate 打 WARN。role 是 `contract` 的，prepare 会拒绝；role 是 `execution` 的，prepare 走 2.10 的路径。

**Markdown 与 JSON 一致**：Identity 是 `role:<r>` 时，JSON 不能有 provider、model、thinking，且 `executor.role` 必须是 `<r>`；反过来也一样。这一条扩展 PD:1939-1944，并跳过那里对 thinking 的检查。

**为什么 role 只有这两个值**：起草任务（第一轮的 B 组）就是经内核派给合同端 CLI 的普通合同；规划审核端与调度代理本轮没有无头调用。

**不在范围内**：planner-v2 合同（PD:2045）的 executor 规则不变，本轮不支持按角色写。

### D5 按合同版本快照

**prepare**：

- **只有按角色、并且找到了绑定的合同，才在 prepare 时解析**。解析发生在分配 attempt 之前，结果写进 `meta.json` 的 `executor_binding`，字段有：
  - `source`（`role:<角色>`）、`role`、`profile`、`runtime`、`adapter`、`active_preset`；
  - `provider`、`model`、`thinking`；
  - `config_sha256`（解析时配置文件字节的哈希）、`resolved_at`；
  - `reused_from`（沿用时写来源 attempt 的目录名）。
- **同一版本沿用最早的快照**：同一 task、同一 `plan_version` 已经有 attempt 带着 `executor_binding` 时，沿用其中最早的一份，不论那次 attempt 的状态，并打 NOTE。
  - 当前绑定与快照不同时，NOTE 写明“绑定已改为 …，本版本沿用 …；要用新绑定，出新版本合同”。
  - 枚举 attempt 时跳过链接与 junction，用 `is_link_or_junction`。
- **其他合同不在 prepare 时解析**：写死模型的合同、走 2.10 路径的合同，`meta.json` 不加字段，prepare 的行为也不变。这样第 11 节说的“兼容预设下 2.10 全量回归不变”才能成立：遗留刻画用例钉着 prepare 不提前解析时的行为。

**run**：

- `meta.json` 有 `executor_binding` 时，provider、model、thinking 取自快照，tools、context_files 仍取自合同；
- 然后再过一次 `allowed_executors`，因为允许列表可能在 prepare 之后收紧了，还有 `PI_EXEC_*` 的冲突检查；
- pi 的命令按快照里的 runtime 解析（D3 的顺序）。本机文件在 run 时读：路径是本机事实，不进快照。

**`executor.json` 的形状不变**：仍是 provider、model、thinking、tools、context_files；来源只记在 `meta.json`。执行说明与摘要照旧用解析结果。摘要多一行“执行模型来源”：

- 角色绑定：写明 profile、runtime、方案、配置哈希的前 12 位，沿用时写来源；
- 合同写死：与当时的绑定不同时，写明差异；
- 合同加 `PI_EXEC_*`。

**读回点**：collect 退回 `contract["executor"]` 的那一处（PD:4510），改为先看 `executor_binding`。

**为什么记在 `meta.json`**：

- 它在 prepare 时独占写入（PD:4256），本来就记录这次 attempt 的事实；
- 不新增证据文件，第一轮的 `logs` 枚举不受影响；
- 运行中与已准备的 attempt 都已经固定了执行模型，切换配置不会改变它们。所以上位设计 8.1 的“运行中切换执行端要确认”在这里不需要。

### D6 绑定未就绪时 prepare 拒绝

- **拒绝的情形**：按角色的合同，它的绑定指向本轮未接通的组合（适配器不是 pi，或 pi 没有接通这个角色）。
- **退出码**：
  - 未接通：`EXIT_BLOCKED`，与允许列表的拒绝相同（PD:3296）；
  - 配置类错误：`EXIT_USAGE`。
- **prepare 不运行任何 CLI**：模型列表与登录是 run 的预检和 `config doctor` 的事。

### D7 写入历史与审计

**所有写入都经 `kit_config.write_config`**：

- `cmd_init` 改为经 `write_checked`；
- `write_config` 新增参数：`action`、`target`、`raw_text`（rollback 用，写回原始字节）。

替换完成之后，按顺序做三件事：

1. **补外部改动**：`.agent/config-history/` 为空，或者最新快照与写入前的文件字节不同时，先把写入前的字节存为一个快照，action 记为 `external`。这一条涵盖在配置中心之外改过的情况，例如 git checkout 或手改。
2. **存写入后的快照**：把写入后的字节存为下一个快照。
3. **追加审计记录**：形状见 4.4。

**快照文件**：

- 编号是四位十进制数，递增，文件名 `NNNN.json`；
- 内容是配置文件的原始字节，以 `O_EXCL` 创建，撞号就取下一个。不加锁，沿用第一轮第 10 节第 3 项。

**疑似凭据不存内容**：要存的字节里，任何字符串命中 `RELEASE_PATTERNS["api key"]`，就不存内容，只存哈希，审计的 note 写明原因。否则用户用 `config unset` 删掉手抄进来的密钥后，历史里还留着一份。

**历史或审计写失败**：

- 配置已经写入，不回滚；
- 打一行 ERROR，写明“配置已写入，但历史或审计没有记下”，退出码 1。
- 下一次写入时，第 1 步会发现最新快照与当前文件不同，补一条 `external`，历史因此总能追上。

**rollback `<N>`**：

1. 读快照 N（没存内容的快照拒绝）；
2. 解析成 JSON 对象，整份校验；
3. 用 `raw_text` 写回原始字节，action 记为 `config.rollback`。

所以回滚后的文件与快照 N 逐字节相同，新快照也与它相同。

**`config history`**：

- 列出快照：编号、时间、动作、目标、哈希前 12 位、执行者；
- 审计缺失的快照写“无审计记录”。

**不提交**：`.agent/config-history/` 与 `.agent/audit/` 加入忽略规则（D11）。配置文件本身是提交的，团队视角的历史在 git 里；这两个目录是本机的切换记录。

**本机文件的写入**（`runtime add --command`）：

- 只记审计，写入前后的哈希也记在审计里；
- 不存快照：内容是本机路径。

### D8 方案与切换

- **`preset save <名> [--description …] [--roles a,b] [--force]`**：
  - 把当前 roles 中列出的角色存成方案；不带 `--roles` 时存全部已写的角色；
  - 同名方案已存在时，要加 `--force`。
- **`preset use <名>`**：
  - 把方案的角色写进 roles，只覆盖方案列出的角色，并把 `active_preset` 设为这个方案。
  - 写入之前列出影响：
    - 未结束的 attempt 个数：它们的执行模型已经固定，不受影响；
    - 还没派遣过、按角色写的合同版本：会用新绑定；
    - 派遣过的这类版本：沿用快照。
- **单独改角色之后**：`role set` 不清除 `active_preset`。`preset show <当前方案>` 与 `role show` 会标出与方案不一致的角色。
- **其余子命令**：`preset diff A B` 逐角色比较；`preset list`、`preset show`；`preset remove <名>` 拒绝删除当前方案。
  - 上位设计 8.5 没有列 remove。不加的话，方案只增不减，所以本轮加上。
- **批准失效**：上位设计 8.1 要求“受影响的批准被列出并失效”。P3 之前没有批准记录，审计里的 `invalidated_approvals` 固定为空列表，note 写明这一点。

### D9 凭据与环境

- profile 的 `credential_env` 只检查两件事：变量是否已设置（布尔值），以及在凭据库的哪一层（用 2.7 的 `describe`）。从不读取值。
- `credential_env` 里的名字同时出现在 `env_remove` 中时，`config doctor` 报未就绪：执行器拿不到它。
- 探测与就绪检查用 `child_env(config)`（D3）。

### D10 `config doctor`（就绪总览）

- **每个角色一行**，内容是：
  - 模式、profile、runtime、适配器；
  - 命令与它的来源（环境变量、本机文件或 PATH）；
  - 版本；
  - 模型是否在列表中；
  - 登录是否就绪；
  - 思考级别是否受支持；
  - 是否在 `allowed_executors` 中；
  - 接通状态。
- **pi 的检查与 `doctor` 共用一个函数**：把 `cmd_doctor` 中列模型、`auth check --no-refresh` 与思考级别的那一段（PD:6956-6990）抽出来，两处口径因此一致。这是纯重构，`doctor` 的输出不变。
- **只探测一次**：同一个 runtime 被几个角色用到时，只探测一次。
- **不调用模型**。
- **退出码**：全部就绪是 0；有未就绪的是 1；用法错误是 2。

### D11 忽略规则与规则文件

**忽略规则**：`gitignore.append.txt` 与本仓库的 `.gitignore` 追加三条，`kit_install update` 会把它们补给已安装的仓库：

- `.agent/dispatch.local.json`
- `.agent/config-history/`
- `.agent/audit/`

几点说明：

- **不用加进 `planner_paths`**：主工作区指纹不含被忽略的文件（PD:1058-1083）。上位设计 11 节说要加的那两条，随之不需要。
- **旧的安装可能还没补上这些规则**：这时历史与审计文件是未被忽略的新文件，运行期间写配置会进“复审需要关注”。所以写配置时，若历史目录或审计目录没被忽略，打一行 WARN，提示运行 `kit_install update`。
- **本机文件没被忽略时不写**（D3）。

**AGENTS.md 的“必须遵守”**：执行模型一条改为三层：

- 执行模型由角色绑定决定（`config role show`）；新合同的 Identity 写 `role:execution`，不写 provider 与 model；合同写死了模型时，以合同为准。
- provider 与 model 必须与 `.agent/environment.md` 和 `pi --list-models` 的精确 ID 一致。
- 下面三类改动都要用户同意：
  - 改角色绑定或方案（`config role set`、`config preset use`、`config rollback`）；
  - 改写死的模型；
  - 改思考级别。

  写死的模型要换，就出新版本合同。

AGENTS.md 的“Codex 的沙箱”一节写明新子命令的读写性质：

| 子命令 | 性质 |
|---|---|
| list / show / history / diff | 只读 |
| scan / probe / models / doctor | 运行本机 CLI 的只读命令；pi 的列模型在沙箱里可能失败，与 `doctor` 相同 |
| add / edit / remove / set / save / use / rollback | 只写工作区：配置、本机文件、历史与审计 |

**技能**：

- plan-task 的模板：Identity 的 executor 行给出两种写法，配置了 execution 绑定时用 `role:execution`；
- contract-guide：第四节与第九节补上规则；
- `SKILL.md:150`：改写；
- check-pi-env 第 8 步：建议用 `config runtime add`、`config profile add`、`config role set` 登记并绑定，不手写 JSON；
- review-pi：复审时核对摘要里的“执行模型来源”；
- 改完运行 `sync-adapters`。

### D12 模块与接入

- **新文件 `scripts/kit_roles.py`**：放解析、校验、适配器表、本机文件、历史与审计、各个命令，以及给内核用的 `resolve_role_executor`。
  - 只依赖标准库与 `pi_dispatch`（作为 `pd` 导入，与 `kit_config` 相同）。
- **加入 `KIT_LOADED_FILES`**：执行器因此不能改它，它也随 kit 发放。
- **惰性导入**：`kit_config` 与 `pi_dispatch` 都惰性导入它（2.6 的原因）：
  - 配置里没有 v3 键、合同不是按角色写的时候，都不导入，2.10 的路径不受影响；
  - 端到端测试里只拷了 `kit_config` 的临时仓库照常工作；
  - 需要它却缺文件时，报一行 ERROR，不冒堆栈。
- **给内核的函数不抛异常，返回（结果, 错误）**：
  - 调度器以脚本方式运行时，模块名是 `__main__`；`kit_roles` 里的 `import pi_dispatch` 会再载入一份 `pi_dispatch`。`kit_config` 现在就是这样（PD:7145-7151 转发，KC:44 导入）。
  - 两份模块各有自己的 `DispatchError`，内核的 `except DispatchError` 接不住另一份模块抛出的异常。
  - 所以 `resolve_role_executor` 等函数把错误作为返回值交回；由调度器自己构造 `DispatchError`，退出码按 D6。
  - 进程内导入 `pi_dispatch` 的单元测试碰不到这个问题，所以内核的场景放在以子进程运行的 `tests/test_dispatch.py` 里（9.3）。
- **`config` 的转发不变**（PD:7145-7151）：新子命令由 `kit_config.build_parser` 登记，转交给 `kit_roles`。

## 4. 接口

### 4.1 命令

| 命令 | 读写 | 说明 |
|---|---|---|
| `config runtime list [--json]` | 读 | 已登记的 runtime、适配器，以及命令的来源 |
| `config runtime scan [--add]` | 读；`--add` 写配置 | 在 PATH 上找 pi、claude、codex、opencode，运行 `--version`；`--add` 把找到但未登记的登记成与适配器同名的 runtime |
| `config runtime add <id> --adapter <a> [--command '<JSON 数组>']` | 写；`--command` 写本机文件 | ID 已存在时，要加 `--force` 才改 adapter |
| `config runtime remove <id>` | 写 | 有 profile 引用时拒绝；同时删除本机文件里的条目 |
| `config runtime probe <id> [--json]` | 读 | 版本；pi 另报缺少的参数、可用模型数与登录状态 |
| `config models <runtime> [--json]` | 读 | pi 列出 `pi --list-models` 的表，并标出哪些在允许列表里；其他适配器退出 1，提示在 profile 里手填 |
| `config profile show [<id>] [--json]` | 读 | |
| `config profile add <id> --runtime <r> --model <provider/id> [--thinking <级别>] [--credential-env <名>]…` | 写 | pi 的 runtime 缺省 thinking 是 high；模型不在本机列表里时打 WARN，不阻塞 |
| `config profile edit <id> [--model …] [--thinking …] [--credential-env …] [--runtime …]` | 写 | |
| `config profile remove <id>` | 写 | 有角色或方案引用时拒绝 |
| `config role show [--json]` | 读 | 四个角色的生效绑定，标出与当前方案不一致的地方 |
| `config role set <role> <profile>\|manual\|disabled\|interactive_host [--host <h>] [--cadence-seconds <n>]` | 写 | 未接通、不在允许列表时打 WARN |
| `config preset list / show <名> / save <名> … / use <名> / diff <A> <B> / remove <名>` | 见 D8 | |
| `config history [--json]` | 读 | |
| `config rollback <N>` | 写 | |
| `config doctor [--json]` | 读；运行 CLI 的只读命令 | 见 D10 |

- **退出码**：沿用 `kit_config`。0 是成功；1 是校验失败、未就绪，或历史没有记下；2 是用法错误。
- **写入都走同一条链**：先整份校验，再原子替换，然后存快照、写审计（D7）。
- **与通用命令的关系**：`config set` / `config unset` 照常可以改这五个键，例如 `config unset roles.execution` 回到“由合同决定”。它们同样经过校验、历史与审计。

### 4.2 合同的 executor

| 写法 | JSON | Markdown Identity |
|---|---|---|
| 写死（2.10） | `{"provider": "bb", "model": "step-5-preview", "thinking": "high", …}` | `- executor: bb/step-5-preview · thinking high` |
| 按角色 | `{"role": "execution", "tools": […], "context_files": "project"}`（`role` 可省，缺省 execution） | `- executor: role:execution` |
| 按角色（合同端） | `{"role": "contract", …}` | `- executor: role:contract` |

### 4.3 `meta.json` 的 `executor_binding`

只在“按角色并找到绑定”时写入，字段见 D5。示例：

```json
"executor_binding": {"source": "role:execution", "role": "execution", "profile": "exec-step", "runtime": "pi",
                     "adapter": "pi", "active_preset": "economy", "provider": "bb", "model": "step-5-preview",
                     "thinking": "high", "config_sha256": "<64 位十六进制>", "resolved_at": "2026-10-18T09:00:00Z",
                     "reused_from": null}
```

写死模型的合同与当前绑定不同时，`meta.json` 写 `executor_binding_note`：`{"role": "execution", "binding": {"provider", "model", "thinking"}, "profile"}`。

### 4.4 审计记录（`.agent/audit/management.jsonl`，每行一条）

```json
{"record_type": "management-audit", "schema_version": 1, "audit_id": "aud-20261018T090000123456-4242",
 "at": "2026-10-18T09:00:00Z", "actor": "cli", "action": "preset.use", "target": "economy",
 "before_ref": {"kind": "config-snapshot", "id": "0007", "sha256": "…", "path": ".agent/config-history/0007.json"},
 "after_ref": {"kind": "config-snapshot", "id": "0008", "sha256": "…", "path": ".agent/config-history/0008.json"},
 "invalidated_approvals": [], "confirmation": "none", "note": "P3 之前没有批准记录"}
```

- **`actor`**：固定为 `cli`。同一个系统账户下，分不出命令是人敲的还是代理敲的，如实记录。
- **`audit_id`**：由 UTC 时间（微秒）与进程号组成，不加锁也不会重复。
- **`action`** 的取值：`config.set`、`config.unset`、`config.init`、`config.rollback`、`runtime.add`、`runtime.remove`、`runtime.local_command`、`profile.add`、`profile.edit`、`profile.remove`、`role.set`、`preset.save`、`preset.use`、`preset.remove`、`plugin.enable`、`plugin.disable`、`external`。

## 5. 执行方式

- **由规划端直接做**。用户 2026-10-17 定了“M1 由规划端直接做”，P1 改的又是受保护文件（上位设计 11 节）。本轮不派 Pi，不调用任何模型；测试都用替身。
- **两个前置的单独提交**（第一轮 10.1）：
  - `tests/test_dispatch.py` 在 pytest 下能失败了，模块结束时清理临时目录，不再读本机真实的 `~/.pi/agent`：先于本轮对调度器的改动；
  - `resolve_run_dir` 的边界缺口。
- **实现顺序**：
  1. `kit_roles`：解析与校验；
  2. `kit_config` 接入：KEYS、`write_config` 的历史；
  3. 命令；
  4. 内核：D4、D5、D3；
  5. 规则、技能与文档。

  每步都跑相关测试，最后跑全量。

## 6. 刻意不做

- 把 Pi 抽成适配器；改 `pi_preflight`、事件解析与 Pi 品牌化的输出（调查摘要的绑定点 2–7、10）。
- 统一 `doctor` 与预检在 `auth check --no-refresh` 上的不一致（2.2）。
- 接入 `codekit/adapters/`、`codekit/config_profiles.py`。
- 第二个 CLI 的无头调用；规划审核端与调度代理的无头调用。
- 命令或路径写进提交的配置（D3）。
- 运行中切换的确认：快照已经保证运行中与已准备的 attempt 不变（D5）。
- 批准失效：P3。
- 给配置写入加锁：沿用第一轮的决定。
- 用户级方案库、方案的导入导出、管理台网页。
- `doctor` 的输出改动，以及在 prepare 里运行 CLI。
- planner-v2 合同按角色写。

## 7. 影响面清单

### 7.1 要改的

| 位置 | 改动 |
|---|---|
| `scripts/kit_roles.py`（新） | D1–D10 |
| KC:256-274 | 五个键追加在末尾，检查函数惰性导入 `kit_roles` |
| KC:397-404、491-497、541-555 | `write_config` 加历史与审计、`raw_text`；`write_checked` 透传 action；`cmd_init` 改经 `write_checked` |
| KC:502-538 | `cmd_set` / `cmd_unset` 传 action 与 target |
| KC:757-796 | 登记新子命令，转交 `kit_roles` |
| `scripts/kit_plugins.py` 的写入调用 | 传 action（`plugin.enable` / `plugin.disable`） |
| PD:96-101 | `KIT_LOADED_FILES` 加 `scripts/kit_roles.py` |
| PD:1641-1714 | `derive_contract_json` 认 `role:<r>` |
| PD:1814-1828、1939-1944 | `executor.role` 的校验、两种写法互斥，以及 Markdown 与 JSON 的一致性 |
| PD:2293-2320 | `resolve_pi_command` 可传 runtime（D3 的顺序） |
| PD:3270-3301 | `resolve_executor`：写死时与绑定比较；按角色时用绑定或快照；冲突检查 |
| PD:4196-4256 | prepare 解析与沿用快照，写 `executor_binding` / `executor_binding_note` |
| PD:4322-4330 | run 用快照、按 runtime 解析命令 |
| PD:4510 | 退回点先看快照 |
| PD:3484-3502 | 摘要的“执行模型来源” |
| PD:6943-6990 | 抽出 pi 的就绪检查，`doctor` 与 `config doctor` 共用 |
| `gitignore.append.txt`、`.gitignore` | 三条规则 |
| AGENTS.md:87-89、57-60 附近 | D11 |
| `.agents/skills/plan-task/`、`check-pi-env/`、`review-pi/` | D11，并运行 `sync-adapters` |
| README、CHANGELOG | 命令表、版本说明 |
| `.claude/settings.example.json` | 只读的新子命令加入放行规则（第一轮对 logs、plugins 的做法） |
| `tests/` | 第 9 节 |

### 7.2 刻意不改的

- `scripts/codekit/**`：本仓库对执行器受保护；本轮只读。
- `pi_preflight`（PD:2547-）与事件解析（PD:2693-）。
- `doctor` 的输出。
- 已有合同与证据。
- `allowed_executors` 的形状。

## 8. 上线顺序与回滚

- **兼容**：五个键都缺省时，行为与 2.10 一致。全量回归、遗留刻画用例与 `tests/test_dispatch.py` 的 404 项检查都不改期望值。只有新增场景，以及 `config show` 多出的键行。
- **回滚**：
  - 删掉五个键，就回到 2.10 的行为；
  - 已有 attempt 的 `meta.json` 多出来的字段，旧版本忽略；
  - 历史与审计目录可以直接删除，它们是本机记录。
- **本仓库自己的配置**：本轮不改 `.agent/dispatch.config.json`。登记 runtime、profile 并绑定 execution 由用户决定（10 节第 1 项）。

## 9. 测试计划

### 9.1 配置（`tests/test_kit_roles.py`）

| 编号 | 场景 | 防的失败 |
|---|---|---|
| C1 | 每个键的未知子键、类型错误、ID 不合法 | 坏配置被写入 |
| C2 | 模式与角色不匹配（execution 用 manual、contract 用 interactive_host、host 不是宿主适配器） | 绑定语义被绕过 |
| C3 | profile 引用不存在的 runtime；角色或方案引用不存在的 profile；`active_preset` 不存在 | 悬空引用 |
| C4 | 任一字符串含凭据形状（含方案的 description） | 内联密钥进配置 |
| C5 | runtime 带 `command` 或其他键 | 提交的配置让 doctor / prepare 运行任意命令 |
| C6 | 本机文件只接受 `runtimes.<id>.command`；未登记的 ID 打 WARN | 本机文件夹带模型或策略 |
| C7 | pi 的 thinking 不在级别里；其他适配器的 options 非空 | profile 选项错 |
| C8 | `credential_env` 名字不合法 | |
| C9 | 五个键缺省时，`config show` / `validate` 与 2.10 的输出一致（除新增键行） | 兼容被破坏 |

### 9.2 命令（`tests/test_kit_roles.py`；CLI 用 PATH 上的替身程序，pi 用 `tests/stub_pi.py`）

| 编号 | 场景 | 防的失败 |
|---|---|---|
| M1 | scan 找到替身、只运行 `--version`；`--add` 登记 | 探测运行了别的命令；登记错 |
| M2 | runtime add / remove：`--command` 只写本机文件；有引用时拒绝 remove | 命令进了提交的配置；悬空引用 |
| M3 | models：替身 pi 的表与允许列表标记；非 pi 退出 1 | |
| M4 | profile add / edit / remove；引用时拒绝 remove | |
| M5 | role set 各模式；未接通打 WARN；`config unset roles.execution` 回到合同决定 | |
| M6 | preset save / use / diff / remove；use 只覆盖列出的角色、写 `active_preset`、列出影响；不能删除当前方案 | 方案覆盖了未列出的角色 |
| M7 | 每次写入都存快照、写审计；rollback 后与快照逐字节相同 | 回滚复现不了原快照 |
| M8 | 手改配置之后再写，先补一条 `external`；疑似凭据只存哈希 | 外部改动丢失；密钥留在历史里 |
| M9 | 历史目录不可写：配置已写入，退出 1 并说明；下一次写入补上 | 写失败被吞掉 |
| M10 | doctor：替身 pi 就绪、模型不在列表、auth 失败、未接通适配器、`credential_env` 在 `env_remove` 里；退出码 | 就绪判断错 |
| M11 | 所有命令都不调用模型：替身记录 argv，没有提示类调用 | 管理面偷偷花钱 |
| M12 | `cmd_init` 也记历史；`plugins enable` 记 `plugin.enable` | 有写入绕过历史 |

### 9.3 内核（`tests/test_dispatch.py` 的新场景，替身 pi）

| 编号 | 场景 | 防的失败 |
|---|---|---|
| K1 | 写死合同、绑定不同：用合同的模型，打 NOTE，记 note | 写死的合同被绑定改掉 |
| K2 | 按角色合同 + 绑定：prepare 写快照，run 的 argv 用快照的模型 | 绑定没生效 |
| K3 | 同版本第二个 attempt 在改绑定之后：沿用快照并打 NOTE | 同一版本中途换模型 |
| K4 | 新版本用新绑定 | 快照锁死了新版本 |
| K5 | `role:contract` 没有绑定、contract 是 manual：prepare 拒绝 | |
| K6 | 绑定到未接通的适配器：prepare 退出 3 | 派给没实测的 CLI |
| K7 | `PI_EXEC_*` 与绑定冲突：拒绝 | |
| K8 | prepare 之后收紧 `allowed_executors`：run 拒绝 | 绕过允许列表 |
| K9 | 本机文件的命令被 run 使用；`PI_DISPATCH_PI_CMD` 仍然优先 | 命令来源错 |
| K10 | Markdown 的 `role:` 行，`derive-json` 与一致性校验；`role` 与 provider 同时写时报错 | 两种写法混用 |
| K11 | 摘要的“执行模型来源”三种写法 | |
| K12 | 快照沿用跳过链接的 attempt 目录 | 从仓库外读快照 |

### 9.4 接线

| 编号 | 场景 |
|---|---|
| W1 | `KIT_LOADED_FILES` 含 `kit_roles.py`；import 扫描一致；`kit_install` 装进临时仓库后，`config role show` 与 `config doctor` 可用（`tests/test_kit_v300.py`） |
| W2 | `gitignore.append.txt` 含三条规则；`kit_install update` 补上它们 |
| W3 | 全量 `python -m pytest tests`；`tests/test_dispatch.py` 以脚本方式运行 |

## 10. 待用户拍板（推荐项写在前）

1. **本仓库自己要不要现在就绑定**：
   - 推荐：本轮不改本仓库的配置，交付后由你决定。可以用 `config runtime add pi --adapter pi`、`config profile add exec-step --runtime pi --model bb/step-5-preview`、`config role set execution exec-step`；
   - 另一种：交付时顺带配好。
2. **历史与审计提交与否**：
   - 推荐：不提交，它们是本机的切换记录；
   - 另一种：提交。
3. **本机覆盖文件**：
   - 推荐：新增 `.agent/dispatch.local.json`，只放命令路径；
   - 另一种：本轮不做，自定义路径只能用 `PI_DISPATCH_PI_CMD`。
4. **`preset remove`**：
   - 推荐：加上；
   - 另一种：照上位设计 8.5 不加。
5. **版本号**：合并时再定。推荐 2.12.0：P2–P6 还没做，不记 3.0.0。
