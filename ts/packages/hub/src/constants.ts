// 七端 hub 的常量（迁移第 ⑤a 片，kit_hub.py 1–131 行与 ROSTER）：退出码、信件类型、阶段与依赖、审核的退回对象、名册。
// 取值逐项照 kit_hub.py；名册的选型理由见那里的注释，这里不重复。
export const EXIT_OK = 0;
export const EXIT_FAIL = 1;
export const EXIT_USAGE = 2;
export const EXIT_BLOCKED = 3;

export const OWNER = "站主";
export const KERNEL = "内核";
export const COORDINATOR = "womovie-c8";
/** 发信人的 ASCII 别名：只用在 msg-id 与文件名里（与 @themis/base/clock 的 SENDER_ALIAS 相同）。 */
export const SENDER_ALIAS: Readonly<Record<string, string>> = { [OWNER]: "owner", [KERNEL]: "kernel" };

export const WORKER_TYPES = ["交付", "返工完成", "提问", "阻塞", "交接", "进度"] as const;
export const COORDINATOR_TYPES = ["开工", "返工", "通过", "等待", "停止", "汇报", "提问"] as const;
export const OWNER_TYPES = ["任务", "回复", "停止"] as const;
export const KERNEL_TYPES = ["核验", "阻塞"] as const;
/** 第 112 轮：内核代办例行流转时发给工人的信。 */
export const ROUTED_TYPES = ["开工", "返工", "通过"] as const;
/** 发给工人时只登记、不唤醒。 */
export const INFO_TYPES = ["通过", "等待", "停止"] as const;
export const FIELDS = ["摘要", "提交", "验证", "偏离", "需协调人决定", "证据"] as const;
export const VERDICT_FIELDS = ["结论", "退回", "阻塞项"] as const;
/** 第 111 轮：给后面阶段的提醒，内核原样附进下游各回合的输入。 */
export const HANDOFF_FIELD = "下游须知";
export const KERNEL_FIELDS = ["内核核验"] as const;
export const KNOWN_FIELDS: readonly string[] = [...FIELDS, ...VERDICT_FIELDS, HANDOFF_FIELD, ...KERNEL_FIELDS];
export const MAX_BODY_LINES = 40;
/** 站主一封信的字数上限（send 的正文）。 */
export const MAX_OWNER_CHARS = 2000;
export const VERDICTS = ["通过", "返工"] as const;

export const STAGES: readonly (readonly [string, string])[] = [
  ["1-plan", "planner-opus"],
  ["2-contract", "contract-glm"],
  ["3-gate-pre", "gate-sonnet"],
  ["3j-jev", "jev-judge"],
  ["4-audit-pre", "audit-sonnet"],
  ["5-exec", "exec-step"],
  ["6-gate-post", "gate-sonnet"],
  ["6j-jev", "jev-judge"],
  ["7-audit-post", "audit-sonnet"],
];
export const STAGE_ORDER: readonly string[] = STAGES.map(([suffix]) => suffix);
export const STAGE_WORKER: Readonly<Record<string, string>> = Object.fromEntries(STAGES);
/** 阶段之间的数据依赖：上游重新交付，下游（传递闭包）的结论一律作废。 */
export const DEPENDS: Readonly<Record<string, readonly string[]>> = {
  "1-plan": [],
  "2-contract": ["1-plan"],
  "3-gate-pre": ["2-contract"],
  "3j-jev": ["2-contract"],
  "4-audit-pre": ["3-gate-pre", "3j-jev"],
  "5-exec": ["4-audit-pre"],
  "6-gate-post": ["5-exec"],
  "6j-jev": ["5-exec"],
  "7-audit-post": ["6-gate-post", "6j-jev"],
};
/** 交付通过后由内核接着跑的 JEV。 */
export const AUTO_JEV: Readonly<Record<string, string>> = { "2-contract": "3j-jev", "6-gate-post": "6j-jev" };
/** 执行端以外的阶段，协调人最多让它返工几次。 */
export const MAX_STAGE_REWORKS = 3;
export const WORKER_RETRIES_AFTER_TIMEOUT = 2;
/** 审核端“退回”的对象 → 阶段（键序就是报错里列出的次序）。 */
export const RETURN_TARGETS: Readonly<Record<string, string>> = {
  合同端: "2-contract",
  门禁端: "3-gate-pre",
  战后门禁: "6-gate-post",
  执行端: "5-exec",
  规划端: "1-plan",
};
/** 工人这一回合没交付就停下了：阶段转为 paused，协调人可以再开工。 */
export const PAUSE_TYPES = ["提问", "阻塞", "交接", "进度"] as const;
/** 阶段已经开工时拒收开工、返工的理由。 */
export const BUSY_GUARD = "已经开工、还没交付";
/** 第 112 轮：交付通过之后例行的下一步；审核端按结论另算，执行端只在检查通过时。 */
export const ROUTINE_NEXT: Readonly<Record<string, string>> = {
  "1-plan": "2-contract",
  "2-contract": "3-gate-pre",
  "3-gate-pre": "4-audit-pre",
  "5-exec": "6-gate-post",
  "6-gate-post": "7-audit-post",
};

export interface RosterSpec {
  readonly role: string;
  readonly label: string;
  readonly adapter: "pi" | "claude" | "dispatcher" | "jev";
  readonly provider?: string;
  readonly model?: string;
  readonly thinking?: string;
  readonly effort?: string;
  readonly tools?: readonly string[];
  readonly allowed_rules?: readonly string[];
  readonly timeout?: number;
  readonly workspace?: "base" | "stage";
  readonly routing?: "kernel";
}

/** 七个岗位（键序与 kit_hub.ROSTER 相同：协调人在前）。 */
export const ROSTER: Readonly<Record<string, RosterSpec>> = {
  [COORDINATOR]: {
    role: "coordinator", label: "调度代理端（协调人）", adapter: "pi", provider: "dsf", model: "deepseek-flash", thinking: "high",
    tools: ["read", "grep", "find", "ls"], timeout: 1200, workspace: "base", routing: "kernel",
  },
  "planner-opus": {
    role: "planner", label: "规划端", adapter: "claude", model: "claude-opus-5-5", effort: "max",
    tools: ["Read", "Grep", "Glob", "Bash"], allowed_rules: ["Bash(npm view:*)"], timeout: 2400, workspace: "base",
  },
  "contract-glm": {
    role: "contract", label: "合同端", adapter: "pi", provider: "minimax", model: "MiniMax-M3.1-Flash", thinking: "high",
    tools: ["read", "grep", "find", "ls"], timeout: 2400, workspace: "base",
  },
  "gate-sonnet": {
    role: "gate", label: "门禁端", adapter: "pi", provider: "cc-switch-zhipu-glm", model: "glm-5.3", thinking: "high",
    tools: ["read", "grep", "find", "ls", "edit", "write", "bash"], timeout: 2400, workspace: "stage",
  },
  "audit-sonnet": {
    role: "audit", label: "审核端", adapter: "pi", provider: "minimax", model: "MiniMax-M3.1-Flash", thinking: "max",
    tools: ["read", "grep", "find", "ls"], timeout: 2400, workspace: "stage",
  },
  "exec-step": { role: "exec", label: "执行端", adapter: "dispatcher", provider: "cc-switch-step-fun", model: "step-5-preview", thinking: "high" },
  "jev-judge": { role: "jev", label: "JEV 端", adapter: "jev" },
};
export const WORKERS: readonly string[] = Object.keys(ROSTER).filter((name) => name !== COORDINATOR);
const EXEC = ROSTER["exec-step"] as RosterSpec;
export const EXECUTOR: readonly [string, string, string] = [EXEC.provider ?? "", EXEC.model ?? "", EXEC.thinking ?? ""];
export const CONTRACT_EXECUTOR_LINE = `- executor: ${EXECUTOR[0]}/${EXECUTOR[1]} · thinking ${EXECUTOR[2]}`;
