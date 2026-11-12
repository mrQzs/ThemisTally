# Themis Tally 3.0：在界面里配置模型（Quizs 融入桌面端）

> 状态：**草案第 1 版（2026-11-12）**，规划端起草，等用户看过。不走 2gate，照 r3 的做法边做边改；每做完一期在第 9 节记下提交与发现。

## 0. 用户决定

| # | 决定 | 原话 |
|---|---|---|
| 1 | 真实任务是做完 quizs 与 tt 的 UI，实现过程中不断自我改进 | “真实的任务就是完成quizs和tt的UI,在实现的过程中不断自我改进”（2026-11-12） |
| 2 | Quizs 不单做界面：融进 TT 的界面，在 TT 的界面里配置不同的 AI 模型 | “quizs融入到tt的界面里,通过tt的ui来配置不同的ai模型”（2026-11-12） |

下面的设计是规划端照这两条定的，标了“规划端代定”的地方用户可以改。

## 1. 目标与不做

**目标**：用户在桌面端里能看到、能改“每个岗位用哪个运行时、哪个模型、什么思考档位”，Quizs 是其中一种运行时；改动经预览与确认，留历史与审计。

**不做**：
- 不给 Quizs 单做界面（它的设计文档里 Q6 的交互终端不在本文）；
- 不在界面里显示或编辑任何凭据的值；
- 不让界面替用户做会花钱的事而不确认：资格认证要调模型，属于桌面端设计 §11 第 2 项的“花钱的操作”，每次单独确认（第 6 节）；
- 岗位的工具白名单、时限、工作目录不开放配置：它们是安全边界，留在内核里。

## 2. 现状（承重事实）

| 事实 | 出处 |
|---|---|
| 配置中心管四个角色（`planning_review`、`contract`、`execution`、`scheduler_agent`），绑定到 profile（运行时、模型、选项、凭据变量名），写入经配置锁、整份校验、历史与审计 | `scripts/kit_roles.py:29–58`；`docs/themis-tally-3.0-r2-角色绑定与配置中心.md` |
| 适配器登记表只有 `pi`、`claude-code`、`codex`、`opencode`，没有 quizs | `scripts/kit_roles.py:45` |
| 七端的名册写死在内核里：每个岗位的载体、提供方、模型、思考档位、工具、时限 | `scripts/kit_hub.py` 的 `ROSTER`；`ts/packages/hub/src/constants.ts` 的 `ROSTER` |
| 名册“接进配置中心留待后续” | r3 §1 的“本轮不做” |
| 协调人已经在 quizs 载体上；起不了时退回 pi（名册的 `fallback`） | `kit_hub.py` 的 `effective_spec`、`quizs_unready`（第 143、145 轮） |
| quizs 回合要三份文件：live plan、提供方档案、资格证书；现在由环境变量 `QUIZS_LIVE_PLAN`、`QUIZS_PROVIDER_PROFILE`、`QUIZS_QUALIFICATION` 指给内核，全枢纽只有一套 | `kit_hub.py` 的 `QUIZS_LIVE_FILES` |
| Quizs 的提供方只有 StepFun 与 DeepSeek 两个；凭据在系统凭据库里，按引用名取（例如 `quizs:provider:deepseek`） | Quizs 仓库 `ts/packages/quizs/providers/src/`；live plan 的 `credential_ref` |
| 资格证书 24 小时有效，绑定构建；续期要跑一批真实请求（约 0.1 元） | Quizs 仓库 `scripts/renew-deepseek-worker.mjs`；r3 §10 第 137–153 轮 |
| 桌面端“角色与模型”页显示配置中心的四个角色，七端的名册不在这一页 | `docs/themis-tally-3.0-桌面端.md` D11 |
| AGENTS.md：换模型或思考级别要用户同意，改角色绑定也算 | AGENTS.md “必须遵守” |

## 3. 设计

### 3.1 一处配置：七端的名册接进配置中心

名册分成两层：

- **内核里的岗位定义**（不可配置）：岗位名、角色、工具白名单、时限、工作目录、流转方式，以及“这个岗位允许哪些适配器”。
- **配置中心里的岗位绑定**（可配置）：`dispatch.config.json` 新增一段 `hub_roles`，键是岗位，值是 `{"profile": "<profile 的 id>", "fallback": "<profile 的 id>"}`（`fallback` 可省，只有 quizs 上的岗位用得上）。

```json
"hub_roles": {
  "coordinator": {"profile": "quizs-deepseek-flash", "fallback": "pi-deepseek-flash"},
  "planner": {"profile": "claude-opus-max"},
  "contract": {"profile": "pi-minimax-flash"},
  "gate": {"profile": "pi-glm"},
  "audit": {"profile": "pi-minimax-flash-max"},
  "exec": {"profile": "pi-step"}
}
```

- 岗位名用角色名（`coordinator`、`planner`、`contract`、`gate`、`audit`、`exec`），不用工人的名字（`womovie-c8`、`gate-sonnet` 这些名字是历史遗留，改名只改名册）。JEV 不在这里：它由决策插件的配置管（`decisions.*`）。
- **没有 `hub_roles` 或缺某个岗位时，用内核里现在的缺省值**（就是今天 `ROSTER` 写的那些）。所以这一步落地之后行为不变，直到有人改配置。
- 另开一段而不是往现有的 `roles` 里加（规划端代定）：现有四个角色有“模式”（交互宿主、手工、无头、关闭），七端的岗位全是无头的；两套语义放在一张表里，校验与界面都要到处分情况。方案（`presets`）之后可以同时带上两段。
- **每个岗位允许的适配器**由内核定，配置校验时查：

| 岗位 | 现在允许的适配器 | 理由 |
|---|---|---|
| coordinator | `quizs`、`pi` | 两个载体都实跑过（第 145 轮起在 quizs 上，起不了时退回 pi） |
| planner | `claude-code` | 规划端的工具名与放行规则是按 claude 写的 |
| contract、audit | `pi` | quizs 上还没验过这两个岗位（Quizs 的 P3），验过再放开 |
| gate | `pi` | 要写测试、跑命令；quizs 的命令角色还没过验收 |
| exec | `pi`（经调度器） | 合同的 executor 一行由它生成；以后与 `execution` 角色并轨 |

名册里的工具名是按载体写的：一个岗位换载体之前，要先有那个载体的工具映射并实测过，所以每个岗位只列已经跑过的载体。同一个载体里换模型、换档位现在就能配。

- **适配器登记表加 `quizs`**；`claude-code` 的 profile 可以写档位。档位一律写在 `options.thinking`（界面上就是“思考档位”）：claude 的取值是 low、medium、high、xhigh、max，hub 把它传给 `claude --effort`；pi 与 quizs 照旧。
- **缺省值另放一份**：`config hub show` 在没装 hub 的仓库里也要能显示，所以各岗位的缺省（适配器、提供方、模型、档位、替补）在配置层放一份，与 hub 名册的同名字段由测试逐项核对。

### 3.2 命令

照配置中心现有的写法，全部带 `--json`，写命令带 `--dry-run --json` 与 `--expect-state`：

| 命令 | 作用 |
|---|---|
| `config hub show --json` | 六个岗位的生效绑定：岗位、profile、适配器、提供方、模型、思考档位、来源（配置或内核缺省）、替补、允许的适配器 |
| `config hub set <岗位> <profile> [--fallback <profile>]` | 改一个岗位的绑定 |
| `config hub unset <岗位>` | 回到内核缺省 |

`config doctor` 的就绪总览加上六个岗位。

### 3.3 什么时候生效，记在哪里

- hub 在**每个回合开始时**读一次生效绑定（现在 `effective_spec` 的位置），不缓存到进程里：改完配置，下一个回合就用新的。
- 每个回合的 `result.json` 与账本的 `turn.finished` 已经记了要求的模型与档位；再加一项 `binding_source`（`config` 或 `default`）与 profile 的 id。
- **执行端例外**：合同的 executor 一行在合同写出时定下，已派遣的合同版本不受后来的改动影响（与 r2 的“按版本记录”一致）。
- 有回合正在跑的岗位被改绑定：不打断正在跑的回合；预览里列出“这个岗位此刻有回合在跑”，照 r2 的运行中切换规则要 `--yes`。

### 3.4 授权

- AGENTS.md 的规矩不变：代理改岗位绑定等于换模型，要用户同意。
- 界面上的改动是用户本人做的：预览里显示命令与前后对比，确认后执行，审计记 `user-ui`。这就是用户同意的形式。

## 4. Quizs 这一侧

Quizs 是独立仓库，改动由规划端直接做（用户 2026-11-06 的决定），分支不推送。

内核与界面只经 Quizs 的命令行拿事实，不读它的内部文件格式：

| 命令（新增） | 作用 |
|---|---|
| `quizs providers list --json` | 登记表里的提供方档案：id、模型、协议、政策状态、可用的思考档位、输入输出上限、计费方式 |
| `quizs auth check --credential-ref <名> --json` | 凭据在不在（已有，补 `--json`）；不输出值 |
| `quizs live status --live-dir <目录> --json` | 这一套 live 文件的状态：档案、模型、证书的状态与到期时刻、能力上限、与当前构建是否对得上 |
| `quizs live renew --live-dir <目录> --policy <文件> --json` | 跑一批资格认证并换发证书（现在的 `scripts/renew-deepseek-worker.mjs` 收成正式命令，不再只认 DeepSeek） |

- **live 目录按 profile 分**：`.agent/quizs/<profile 的 id>/`（Git 忽略）。内核按岗位绑定的 profile 找目录，不再用三个环境变量；环境变量留作过渡期的兜底。
- **配置中心里 quizs 的 profile**：`runtime` 是 quizs 的运行时，`model` 写 `<提供方档案 id>/<模型>`（例如 `deepseek-api/deepseek-flash`），`options.thinking` 取档案允许的档位，`credential_env` 不用（凭据按引用名在系统凭据库里）。
- **“不同的 AI 模型”要靠 Quizs 多接提供方**：现在只有 StepFun 与 DeepSeek。下一批按 hub 现在在用的来：智谱 GLM、MiniMax（都是 OpenAI 兼容的接口）。每接一个要过 Quizs 自己的资格流程，这是持续的工作，不卡界面：界面按登记表里有什么显示什么；pi 与 claude 上的模型照旧可选。

## 5. 本机服务的路由

读路由（起内核子进程，照现有 19 条的规矩）：

| 路由 | 命令 |
|---|---|
| `GET /api/v1/hub/roles` | `config hub show --json` |
| `GET /api/v1/quizs/providers` | `quizs providers list --json` |
| `GET /api/v1/quizs/live` | 逐个 quizs 的 profile 调 `quizs live status --json`，合成一份 |

写路由（照现有 12 条的规矩：预览、确认号、`--expect-state`、操作终态）：

| 路由 | 命令 |
|---|---|
| `POST /api/v1/hub/roles/<岗位>` | `config hub set <岗位> <profile> [--fallback <profile>]` |
| `POST /api/v1/hub/roles/<岗位>/unset` | `config hub unset <岗位>` |

作业：

| 作业 | 命令 | 说明 |
|---|---|---|
| quizs 凭据录入 | 见第 6 节 | 值不经过界面 |
| quizs 资格认证 | `quizs live renew …` | 会花钱；确认框写明这一批最多多少个请求；默认不开放，见第 6 节 |

## 6. 界面

- **“角色与模型”页加一组“七端岗位”**：六行，每行是岗位、当前的运行时与模型、思考档位（要求与生效并列，照 D11 的规则）、来源（配置或缺省）、替补。点一行改绑定：从允许的 profile 里选，走现有的确认框。
- **“CLI 运行时”页加 Quizs 一块**：
  - 提供方档案列表（来自 `providers list`）；
  - 每个 quizs profile 的证书状态：有效、快到期、过期、与当前构建对不上；能力上限；
  - 凭据在不在（只显示在不在）。
- **profile 的新增与编辑**（已有的表单）加上 quizs 运行时：模型从提供方档案里选，思考档位从档案允许的档位里选。
- **凭据录入**（规划端代定，待用户确认）：Quizs 的凭据在系统凭据库里，录入要用户本人做。界面只给出要运行的命令与“复制”按钮，或者经外壳开一个一次性小窗口（照 D6 的凭据录入流程，值只进小窗口、不进界面）。先做前一种，简单且不新增攻击面。
- **资格认证**（规划端代定，待用户确认）：第一步只显示状态，续期仍靠定时任务；“立即续期”按钮放到用户同意开放花钱操作之后。

## 7. 分期

| 期 | 内容 | 谁做 | 依赖 |
|---|---|---|---|
| M0 | 桌面端接真实服务、外壳页与设置（T027、T028 起的 D3 各片） | hub | 无 |
| M1 | 内核：`hub_roles`、`config hub` 三条命令、适配器登记表加 quizs、hub 每回合读绑定；Python 与 TS 各一份，契约与变异 | 规划端（内核文件执行端碰不到） | 无 |
| M2 | Quizs：`providers list`、`live status`、`auth check --json`；live 目录按 profile 分 | 规划端 | 无 |
| M3 | 本机服务：第 5 节的读路由与写路由 | hub | M1、M2 |
| M4 | 界面：第 6 节的“七端岗位”与 Quizs 一块 | hub | M0 的读数据层、M3 |
| M5 | Quizs 多接提供方（GLM、MiniMax）；`live renew` 收成正式命令 | 规划端 | M2 |
| M6 | 界面里的凭据录入与资格认证作业 | hub | M4、M5；用户同意开放花钱操作 |

M0 与 M1、M2 并行：M0 走 hub，M1、M2 由规划端在 hub 跑的间隙做（改内核照 r3 的规矩：隔离的 worktree 里做，经 `exclusive` 合入）。

## 8. 风险与待定

| # | 事项 | 现在的处理 |
|---|---|---|
| 1 | 名册可配置之后，用户可能把岗位绑到没实测过的模型上，回合大量作废 | 校验只管“适配器允许不允许”；`config doctor` 报就绪；界面在确认框里提示“这个组合没有实测记录”。不拦 |
| 2 | 合同端与审核端绑到同一个模型，少一层独立性 | 预览里给一条警告，不拦（现在的缺省就是同一个模型） |
| 3 | hub 每回合读配置，多一次读文件 | 配置文件很小；与起一个模型回合相比可以忽略 |
| 4 | 配置里新增 `hub_roles`，旧版 kit 读到会不会报错 | 做 M1 时核对：旧版对未知顶层键的行为；必要时提高配置的版本号 |
| 5 | quizs 的 profile 没有可用的证书时，岗位怎么办 | 有 `fallback` 就退回，没有就这一回合不起、信扣住，与现在额度限制的处理一样 |
| 6 | 凭据录入与资格认证放不放进界面 | 待用户定（第 6 节两处“规划端代定”） |

## 9. 进度

| 期 | 状态 |
|---|---|
| M0 | T027（前端传输层与只读数据）、T028（外壳的设置存盘、校验与自动检测）于 2026-11-12 落地；T029（连接状态与页面接线）、T030（外壳页窗口与专用 preload）、T032（外壳页前端接外壳接口）在跑 |
| M1 | 已落地（r3 第 154 轮）：`hub_roles` 的校验，`config hub` 的 show、set、unset 三条命令，适配器表加 quizs，hub 每回合读绑定；Python 与 TS 各一份，契约三边一致，变异 28 条全部抓住 |
| M2 | 两条只读命令（`providers list`、`live status --live-dir`）已写完，在 Quizs 的分支 `tt-m2-commands` 上，待合入；`auth check` 原本就输出 JSON，不用改；live 目录按 profile 分还没做 |
| M3–M6 | 未开始（M3 的任务书已备好，M1 落地后登记） |
