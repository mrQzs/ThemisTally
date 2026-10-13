# Code-Kit 2.7 设计说明：配置管理器（`kit-config`）

状态：草案（2026-10-12）。等用户决定第 6 节，再实施。

## 1. 为什么做

用户 2026-10-12 的要求：做一个简单的配置管理器软件，可以配置 Jev key 等。现在 kit 的配置散在三处，各有各的办法，没有一个入口：

- 仓库配置 `.agent/dispatch.config.json`（11 个键：`allowed_executors`、`worktree_root`、`kill_grace_seconds`、`check_artifact_patterns`、`extra_protected_paths`、`planner_paths`、`commit_trailers`、`env_remove`、`env_keep`、`release_check`、`decisions`）：手写 JSON，写错了要等 `prepare` 才报（2.6.0 起 decisions 写错在 prepare 就报，其它键有的在 run 时才报）。
- 标记文件 `.agent/DECISIONS_OFF`：手建。
- 凭据：决策模型的 key 只认环境变量（缺省 `TYPESAFE_API_KEY`），现在没有任何办法在不把 key 经过对话或文件的情况下把它放进去；pi 自己的凭据由 `pi auth` 管，不归 kit。

目标：一条命令看清楚当前生效的配置来自哪里、改一个键不用手写 JSON、把 key 放进操作系统的凭据库而**规划端与对话永远看不到它**。参考 hermes-jev-skills 的 `jev setup-key`（一次性本机网页、不可猜的路径、拒绝外来 Host、只用一次、十分钟关闭、代理只看到 stored/verified 两个布尔值）与 `keystore.py`（环境变量 → 系统凭据库 → 0600 文件的解析顺序，`describe()` 只报有无与长度）。

## 2. 现状（2026-10-12 核对）

- `Repo.config()` 读 `.agent/dispatch.config.json`（顶层必须是对象，以下划线开头的键被忽略，是写说明用的）；各键在用到的命令里各自校验（`extra_protected_paths`、`planner_paths`、`commit_trailers`、`allowed_executors`、`release_check.allow`、`decisions`）。没有“一次校验全部键”的入口；`doctor` 不读配置里除 decisions 以外的键。
- `decisions.settings_from_config` 只从 `environ.get(api_key_env)` 取 key；`describe` 只报 `api_key_set` 布尔值。
- `doctor` 已是“事实清单”的入口（`.agent/runs/_env/doctor.json`）；check-pi-env 技能生成 `environment.md`。
- hermes 的 keystore 在 Windows 上没有凭据库后端（只有 macOS `security` 与 Linux `secret-tool`，否则 0600 文件）；Windows 的对应物是凭据管理器（`advapi32` 的 `CredWriteW`/`CredReadW`/`CredDeleteW`，`ctypes` 标准库就能调，类型 `CRED_TYPE_GENERIC`，按 `TargetName` 索引）。

## 3. 方案草图

新文件 `scripts/kit_config.py`（标准库，单文件，可以 `python scripts/kit_config.py …` 直接跑；`pi_dispatch.py` 加一个 `config` 子命令转发给它，技能里统一写 `bash scripts/dispatch-pi.sh config …`）。四类命令：

1. **看**：`config show [--json]`：每个键的生效值、来源（配置文件 / 缺省 / 环境变量 `PI_DISPATCH_WORKTREE_ROOT`）、一句说明；`decisions` 一节另加生效模式与原因（复用 `decisions.describe`）、标记文件有无；凭据只报“环境变量名 → 已设置 / 凭据库中有 / 都没有”，不报值、不报长度。
2. **改**：`config set <键路径> <JSON 值>`（例如 `config set decisions.mode shadow`、`config set release_check.allow '["tests/fixtures/**:home path"]'`）、`config unset <键路径>`、`config init`（从 `dispatch.config.example.json` 生成，已存在则拒绝）。写之前整份校验（`config validate` 单独也能跑）：键名必须在已知集合里（未知键拒绝，下划线键放过），每个键按调度器现有的校验函数校验（复用，不另写一套），`decisions` 走 `settings_from_config`。写法：读原文件 → 改 → 校验 → 原子写回（临时文件加替换），保留下划线说明键与键顺序。
3. **开关**：`config decisions off|shadow|on`（等于 set），`config decisions marker on|off`（建或删 `.agent/DECISIONS_OFF`）。
4. **凭据**：`config secret set <环境变量名>`：默认开一次性本机网页（hermes 的设计：`127.0.0.1` 随机端口、路径带 24 字节随机令牌、拒绝外来 `Host`、`no-referrer`、`autocomplete=off`、只接受一次 POST、十分钟后关闭、不记日志），用户在网页里粘贴，值直接进凭据库；`--tty` 在终端用 `getpass` 隐藏输入。存完可选 `--verify`：对 decisions 的 key 做一次 `probe`（会联网、会花钱，要用户在命令行明确加这个参数）。`config secret check <名>`：报告在哪一层找到（环境变量 / 凭据库），不报值。`config secret remove <名>`。规划端运行这些命令时看到的输出只有 `{"stored": true, "verified": true|null}` 一行。
   - 凭据库后端：Windows 凭据管理器（`ctypes` 调 `advapi32`，`TargetName` 为 `code-kit:<环境变量名>`，`CRED_PERSIST_LOCAL_MACHINE`）；macOS `security add-generic-password`；Linux `secret-tool`；都没有时 `~/.config/code-kit/secrets/<名>`（`0600`，Windows 上用 `icacls` 只留当前用户）。解析顺序与 hermes 相同：环境变量 → 凭据库 → 文件。
   - `decisions.py` 加一层：`environ.get(api_key_env)` 为空时问凭据库（`kit_config.resolve_secret(name)`），仍然只在构造请求头时读一次；`describe` 多报一个 `source`（`env` / `credential_store` / `file` / `none`）。doctor 跟着显示来源。
5. **规划端的边界**：技能里写明——`config secret set` 由规划端启动、用户自己粘贴；规划端不读凭据库、不执行 `config secret show`（没有这个命令）；`show` 与 `doctor` 的输出照旧经 `redact_obj`。

## 4. 证据边界

- 凭据库后端用假的 `ctypes`/子进程桩离线测试；Windows 真实凭据管理器只在规划端会话里用一个一次性名字（`code-kit:KIT_CONFIG_SELFTEST`）存、读、删一次作为实机验证，值是测试字符串，不是任何真实 key。
- 网页用本机回放客户端测试（随机令牌、错误 Host 被拒、第二次 POST 被拒、超时关闭）。
- 真实 Jev 的 `--verify` NOT_RUN，等用户有 key 再批准。

## 5. 不做

- 不管 pi 的凭据（`pi auth` 是它自己的）；不管 Git 的身份。
- 不做图形界面程序（托盘、Electron）；网页只是粘贴 key 的那一页。
- 不把 key 写进 `.agent/`、`environment.md`、任何仓库文件或对话。
- 不做多用户、远程配置、配置同步。

## 6. 用户决定（2026-10-12，均选推荐项）

1. **形态**：CLI 子命令（`config show/set/unset/validate/init/decisions/secret`）加一次性本机网页只用来粘贴 key（`--tty` 用隐藏输入）。
2. **凭据存放**：操作系统凭据库（Windows 凭据管理器 / macOS Keychain / Linux secret-tool），没有就 0600 文件；解析顺序环境变量 → 凭据库 → 文件。
3. **覆盖范围**：`dispatch.config.json` 全部键、decisions 开关与标记文件、凭据。
4. **实施**：规划端直接做，全程离线；Windows 凭据管理器只用一次性测试条目实机验证。

## 7. 进度与遗留

- 2026-10-12：核对现状与 hermes 的两处实现，写成本说明。
