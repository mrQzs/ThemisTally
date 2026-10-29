// pi_dispatch 的 validate_plan 与 validate、derive-json 两条命令的契约（迁移第 ④b1 片）。
// 探针一层：在临时 Git 仓库里摆出各种合同对（缺文件、坏 JSON、不是 UTF-8、planner-v2 的回执与 outbox 的各种毛病、按角色写的
// 合同、基线落后、Repository facts 点名的文件不在基线里、不可见字符、配置有毛病、没有忽略 .agent/runs/），再抽查本仓库
// .agent/plans 下的真实合同（选择文件分别是全部 python 与 readonly 为 ts，后者给本仓库加上内核 TS 的禁区）。每条先由 Python
// 回答，Node、Bun 逐字一致。命令一层：validate 与 derive-json 经真的 argv（Python，选择文件钉成 python）与 pyargs（TS）
// 各跑一遍，比退出码与输出，derive-json 另比写出来的文件字节；崩溃只比退出码。不写转义序列，特殊字符用 ch() 拼。
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { type CliRun, type ProbeRequest, type ProbeResult, REPO, removeDir, runAgreeing, runDispatcherLauncherCli, runPythonCli, runTsCli, scratchDir } from "./harness.ts";
import { type Json, type MdOptions, jsonOf, mdOf, text } from "./plan-fixtures.ts";

const ch = (...codes: number[]): string => String.fromCodePoint(...codes);
const LF = ch(10);
const BT = "`";
const ALL_PYTHON = { readonly: "python", config: "python", dispatcher: "python", hub: "python" };
const READONLY_TS = { ...ALL_PYTHON, readonly: "ts" };
const CONTEXT = { kit_root: REPO, kernel_impl: ALL_PYTHON };
// 固定作者与时间：三份实现各建一份仓库，提交号相同
const GIT_ENV = {
  ...process.env, GIT_AUTHOR_NAME: "t", GIT_AUTHOR_EMAIL: "t@example.invalid", GIT_COMMITTER_NAME: "t", GIT_COMMITTER_EMAIL: "t@example.invalid",
  GIT_AUTHOR_DATE: "2026-01-01T00:00:00+00:00", GIT_COMMITTER_DATE: "2026-01-01T00:00:00+00:00",
};
const created: string[] = [];
afterAll(() => {
  for (const dir of created) removeDir(dir);
});

function git(repo: string, ...args: string[]): string {
  const done = spawnSync("git", args, { cwd: repo, env: GIT_ENV, encoding: "utf8" });
  if (done.status !== 0) throw new Error(`git ${args.join(" ")} 失败：${done.stderr}`);
  return done.stdout.trim();
}

function put(repo: string, rel: string, content: string | Uint8Array): void {
  mkdirSync(dirname(join(repo, rel)), { recursive: true });
  writeFileSync(join(repo, rel), content);
}

interface History {
  readonly repo: string;
  readonly c0: string;
  readonly c1: string;
  readonly head: string;
}

/** c0：AGENTS.md、.gitignore、src/a.ts、sub/pkg/x.ts；c1：加 src/b.ts；c2（HEAD）：只动规划路径。 */
function history(name: string, options: { agents?: boolean; ignore?: boolean } = {}): History {
  const repo = scratchDir(name);
  created.push(repo);
  git(repo, "init", "-q");
  git(repo, "config", "core.autocrlf", "false");
  if (options.agents ?? true) put(repo, "AGENTS.md", `# AGENTS${LF}`);
  if (options.ignore ?? true) put(repo, ".gitignore", `.agent/runs/${LF}`);
  put(repo, "src/a.ts", `export const a = 1;${LF}`);
  put(repo, "sub/pkg/x.ts", `export const x = 1;${LF}`);
  git(repo, "add", "-A");
  git(repo, "commit", "-q", "-m", "c0");
  const c0 = git(repo, "rev-parse", "HEAD");
  put(repo, "src/b.ts", `export const b = 1;${LF}`);
  git(repo, "add", "-A");
  git(repo, "commit", "-q", "-m", "c1");
  const c1 = git(repo, "rev-parse", "HEAD");
  put(repo, ".agent/plans/keep.md", `# keep${LF}`);
  git(repo, "add", "-A");
  git(repo, "commit", "-q", "-m", "c2");
  return { repo, c0, c1, head: git(repo, "rev-parse", "HEAD") };
}

function plan(repo: string, task: string, md: string | Uint8Array | null, json: string | Uint8Array | null): string {
  if (md !== null) put(repo, `.agent/plans/${task}.v1.md`, md);
  if (json !== null) put(repo, `.agent/plans/${task}.v1.json`, json);
  return `${task}.v1`;
}

const sha256 = (data: string | Uint8Array): string => createHash("sha256").update(data).digest("hex");

function receiptOf(task: string, md: string, json: string): Json {
  return {
    record_type: "publication-receipt", schema_version: 1, publication_id: `pub-${task}`, candidate_id: `cand-${task}`, task_id: task,
    plan_version: 1, members: { markdown_sha256: sha256(md), json_sha256: sha256(json) }, review_ref: { decision: "APPROVED", approval_id: "ap-1" },
    idempotency_key: `idem-${task}`, generation: 1, state: "PUBLISHED", outbox_seq: 1,
  };
}

interface Case {
  readonly repo: string;
  readonly key: string;
}

/** planner-v2 的一份合同：change 改回执，outbox 交回写进 outbox 的那几行（缺省是回执本身一行）；receipt 为 null 时不写回执。 */
function plannerCase(h: History, task: string, outbox: string[], options: {
  json?: (data: Json) => void; receipt?: ((data: Json) => void) | null; receiptText?: (raw: string) => string; outbox?: (line: string) => string[];
} = {}): Case {
  const md = mdOf(task, h.head);
  const data = { ...jsonOf(task, h.head), contract_family: "planner-v2" };
  options.json?.(data);
  const json = text(data);
  const key = plan(h.repo, task, md, json);
  if (options.receipt !== null) {
    const receipt = receiptOf(task, md, json);
    options.receipt?.(receipt);
    const raw = (options.receiptText ?? ((value: string) => value))(JSON.stringify(receipt));
    put(h.repo, `.agent/publications/${key}.json`, raw);
    outbox.push(...(options.outbox ?? ((line: string) => [line]))(raw));
  }
  return { repo: h.repo, key };
}

/** 探针一层的全部用例。 */
function probeCases(): Case[] {
  const cases: Case[] = [];
  const main = history("plan-main");
  const add = (key: string, repo = main.repo): void => {
    cases.push({ repo, key });
  };
  const ok = (h: History, task: string, base: string, md: MdOptions = {}, json: (data: Json) => void = () => undefined): string => {
    const data = jsonOf(task, base);
    json(data);
    return plan(h.repo, task, mdOf(task, base, md), text(data));
  };
  add(ok(main, "ok-head", main.head));
  add(ok(main, "ok-c1", main.c1));
  add(ok(main, "ok-c0", main.c0));
  add(ok(main, "bad-base", "1".repeat(40)));
  add(ok(main, "short-base", "abc"));
  add(ok(main, "facts", main.head, {
    facts: [`- ${BT}src/a.ts${BT}`, `- ${BT}src/missing.ts${BT} 与 ${BT}src/missing.ts${BT}`, `- ${BT}.agent/reviews/r.md${BT}`, `- ${BT}pkg/x.ts${BT}`,
      `- ${BT}src/new.ts${BT}`, `- ${BT}docs/*.md${BT}`, `- ${BT}a.ts${BT}`],
    newFiles: "src/new.ts", cwd: "sub",
  }, (data) => {
    (data["scope"] as Json)["allowed_new_files"] = ["src/new.ts"];
    ((data["checks"] as Json[])[0] as Json)["cwd"] = "sub";
  }));
  add(ok(main, "invisible", main.head, { goal: `改一个${ch(0x200b)}文件。${ch(0xfeff)}` }, (data) => {
    data["title"] = `标题${ch(0x200e)}`;
  }));
  add(ok(main, "role-plain", main.head, { executor: "role:execution" }, (data) => {
    data["executor"] = { role: "execution", tools: ["read", "edit", "bash"], context_files: "project" };
  }));
  add(ok(main, "role-record", main.head, { executor: "role:execution" }, (data) => {
    data["executor"] = { role: "execution", tools: ["read", "edit", "bash"], context_files: "project" };
  }));
  put(main.repo, ".agent/runs/role-record/binding-v1.json", "{");
  add(plan(main.repo, "missing-md", null, text(jsonOf("missing-md", main.head))));
  add(plan(main.repo, "missing-json", mdOf("missing-json", main.head), null));
  add(plan(main.repo, "json-syntax", mdOf("json-syntax", main.head), "{"));
  add(plan(main.repo, "json-bom", mdOf("json-bom", main.head), `${ch(0xfeff)}${text(jsonOf("json-bom", main.head))}`));
  add(plan(main.repo, "json-utf8", mdOf("json-utf8", main.head), Uint8Array.from([0x7b, 0xff, 0x7d])));
  add(plan(main.repo, "json-array", mdOf("json-array", main.head), "[]"));
  add(plan(main.repo, "md-utf8", Uint8Array.from([0x23, 0x20, 0xff]), text(jsonOf("md-utf8", main.head))));
  add("Bad.v1");
  add("x.v0");
  add("nothing-here.v1");

  // planner-v2：一个仓库共用一份 outbox
  const outbox: string[] = [];
  const pv = (task: string, options: Parameters<typeof plannerCase>[3] = {}): void => {
    cases.push(plannerCase(main, task, outbox, options));
  };
  const review = (value: Json) => (data: Json): void => {
    data["review_ref"] = value;
  };
  pv("p-ok");
  pv("p-norec", { receipt: null });
  pv("p-recsyntax", { receiptText: () => "{", outbox: () => [] });
  pv("p-recarray", { receiptText: () => "[]", outbox: () => [] });
  pv("p-recdup", { receiptText: (raw) => raw.replace("{", `{"state":"X",`), outbox: () => [] });
  pv("p-missing", { receipt: (data) => void delete data["generation"] });
  pv("p-extra", { receipt: (data) => void (data["x"] = 1) });
  pv("p-rtype", { receipt: (data) => void (data["record_type"] = "other") });
  pv("p-schema-float", { receiptText: (raw) => raw.replace(`"schema_version":1`, `"schema_version":1.0`) });
  pv("p-schema-true", { receipt: (data) => void (data["schema_version"] = true) });
  pv("p-pubid", { receipt: (data) => void (data["publication_id"] = "Pub-x") });
  pv("p-pubid-ctl", { receipt: (data) => void (data["publication_id"] = `p${ch(0x7f)}x`) });
  pv("p-taskid", { receipt: (data) => void (data["task_id"] = "p_taskid") });
  pv("p-task-other", { receipt: (data) => void (data["task_id"] = "other-task") });
  pv("p-version0", { receipt: (data) => void (data["plan_version"] = 0) });
  pv("p-version2", { receipt: (data) => void (data["plan_version"] = 2) });
  pv("p-versiontrue", { receipt: (data) => void (data["plan_version"] = true) });
  pv("p-members", { receipt: (data) => void delete (data["members"] as Json)["json_sha256"] });
  pv("p-members-hex", { receipt: (data) => void ((data["members"] as Json)["json_sha256"] = "Z".repeat(64)) });
  pv("p-members-wrong", { receipt: (data) => void ((data["members"] as Json)["json_sha256"] = "0".repeat(64)) });
  pv("p-decision", { receipt: review({ decision: "REJECTED", approval_id: "a" }) });
  pv("p-noapproval", { receipt: review({ decision: "APPROVED" }) });
  pv("p-candidate", { receipt: review({ decision: "APPROVED", approval_id: "a", candidate_id: "other" }) });
  pv("p-candidate-same", { receipt: review({ decision: "APPROVED", approval_id: "a", candidate_id: "cand-p-candidate-same" }) });
  pv("p-ref-open", { receipt: review({ decision: "APPROVED", approval_ref: { scope: "s" } }) });
  pv("p-ref-ok", { receipt: review({ decision: "APPROVED", approval_ref: { scope: "scope-1", generation: 1, sha256: "a".repeat(64) } }) });
  pv("p-ref-gen", { receipt: review({ decision: "APPROVED", approval_ref: { scope: "scope-1", generation: 0, sha256: "a".repeat(64) } }) });
  pv("p-ref-sha", { receipt: review({ decision: "APPROVED", approval_ref: { scope: "scope-1", generation: 1, sha256: "A".repeat(64) } }) });
  pv("p-gen0", { receipt: (data) => void (data["generation"] = 0) });
  pv("p-state", { receipt: (data) => void (data["state"] = "DRAFT") });
  pv("p-seq0", { receipt: (data) => void (data["outbox_seq"] = 0) });
  pv("p-outbox-diff", { outbox: (line) => [line.replace(`"outbox_seq":1`, `"outbox_seq":2`)] });
  pv("p-outbox-twice", { outbox: (line) => [line, line] });
  pv("p-outbox-none", { outbox: () => [] });
  pv("p-role", { json: (data) => void (data["executor"] = { role: "execution", tools: ["read"], context_files: "project" }) });
  pv("p-dupkey", { json: () => undefined, receipt: null });
  // 合同 JSON 里有重复键：按家族认出是 planner-v2，再严格解码同一份字节
  put(main.repo, ".agent/plans/p-dupkey.v1.json", text({ ...jsonOf("p-dupkey", main.head), contract_family: "planner-v2" }).replace("{", `{"risk_level":"low",`));
  put(main.repo, ".agent/publications/outbox.jsonl", [...outbox, ""].join(ch(13, 10)) + LF);

  // 其余仓库：outbox 坏了、没有 outbox、没有 AGENTS.md 与忽略规则、配置的几种情形
  const broken = history("plan-pv2-broken");
  const brokenBox: string[] = [];
  cases.push(plannerCase(broken, "p-broken", brokenBox));
  put(broken.repo, ".agent/publications/outbox.jsonl", [...brokenBox, "{"].join(LF));
  const none = history("plan-pv2-none");
  cases.push(plannerCase(none, "p-nobox", []));
  const bare = history("plan-bare", { agents: false, ignore: false });
  add(ok(bare, "bare-ok", bare.head), bare.repo);
  const extra = history("plan-cfg-extra");
  put(extra.repo, ".agent/dispatch.config.json", JSON.stringify({ extra_protected_paths: ["docs/**"], planner_paths: [".agent/**"] }));
  add(ok(extra, "extra-docs", extra.head, { modified: "docs/x.md" }, (data) => void ((data["scope"] as Json)["allowed_modified_files"] = ["docs/x.md"])), extra.repo);
  add(ok(extra, "extra-c1", extra.c1), extra.repo);
  for (const [name, config] of [["plan-cfg-secret", JSON.stringify({ github_token: "abc" })], ["plan-cfg-syntax", "{"], ["plan-cfg-array", "[]"],
    ["plan-cfg-planner", JSON.stringify({ planner_paths: "x" })]] as const) {
    const h = history(name);
    put(h.repo, ".agent/dispatch.config.json", config);
    add(ok(h, "cfg-ok", h.c1), h.repo);
  }
  return cases;
}

const request = (c: Case, kernelImpl: Record<string, string> = ALL_PYTHON): ProbeRequest => ({
  op: "contract.call", fn: "validate_plan", root: c.repo, plan_key: c.key, kit_root: REPO, kernel_impl: kernelImpl,
});

function agreeInBatches(requests: readonly ProbeRequest[], size: number): ProbeResult[] {
  const python: ProbeResult[] = [];
  const mismatches: unknown[] = [];
  for (let start = 0; start < requests.length; start += size) {
    const batch = runAgreeing(requests.slice(start, start + size));
    python.push(...batch.python);
    mismatches.push(...batch.mismatches);
  }
  expect(mismatches.slice(0, 2), `共 ${mismatches.length} 条不一致`).toEqual([]);
  return python;
}

const allText = (results: readonly ProbeResult[]): string => results.map((result) => JSON.stringify(result)).join(LF);

describe("validate_plan", () => {
  it("临时仓库里的各种合同对", () => {
    const python = agreeInBatches(probeCases().map((c) => request(c)), 25);
    const seen = allText(python);
    for (const fragment of [
      "NOTE：base_sha 不是当前 HEAD", "确认这是有意选择的输入版本", "不存在或不是提交", "Repository facts 提到的文件在基线", "Repository facts 提到的规划文件",
      "不可见格式字符", "缺少文件", "JSON 合同解析失败", "UnicodeDecodeError", "计划标识不合法", "合同按角色写 executor", "版本记录",
      "planner-v2 合同缺少登记回执", "发布回执解析失败", "发布回执必须是对象", "发布回执严格校验失败：E_SCHEMA_FIELDS", "E_ID_SYNTAX", "E_JSON_UNICODE",
      "E_REVIEW_BINDING", "E_SCHEMA_VERSION", "与固定合同字节不一致", "回执与持久 outbox 登记不一致", "持久 outbox 无法解析", "缺少持久 outbox 登记",
      "planner-v2 合同不支持按角色写 executor", "基线提交中没有 AGENTS.md", ".agent/runs/ 尚未被 .gitignore 忽略", "包含受保护路径",
      "ConfigSecretError", "无法解析", "顶层必须是对象", "planner_paths 必须是",
    ]) {
      expect(seen, fragment).toContain(fragment);
    }
    // 两份 planner-v2 合同完整通过（p-ok 与 p-ref-ok）
    expect(python.filter((result) => result.ok && result["contract"] !== null).length).toBeGreaterThan(5);
  });

  it("kernel_protected_paths：被检查的仓库是不是 kit 自己、选择文件有没有 ts", () => {
    const other = scratchDir("plan-kernel-other");
    created.push(other);
    const roots = [REPO, join(REPO, "."), join(REPO, "ts", ".."), REPO.toUpperCase(), join(REPO, "scripts"), other];
    const impls = [ALL_PYTHON, READONLY_TS, { ...ALL_PYTHON, hub: "ts" }, { ...ALL_PYTHON, dispatcher: "ts" }];
    const python = agreeInBatches(roots.flatMap((root) => impls.map((kernelImpl) => ({ op: "contract.call", fn: "kernel_protected", root, kit_root: REPO, kernel_impl: kernelImpl }))), 50);
    expect(python.some((result) => (result["value"] as string[]).length > 0)).toBe(true);
    expect(python.some((result) => (result["value"] as string[]).length === 0)).toBe(true);
  });

  it("本仓库的真实合同：抽查，选择文件全部 python 与 readonly 为 ts 各一遍", () => {
    const names = readdirSync(join(REPO, ".agent", "plans")).sort();
    const keys = names.filter((name) => name.endsWith(".md") && names.includes(`${name.slice(0, -3)}.json`)).map((name) => name.slice(0, -3));
    const sample = keys.filter((_key, index) => index % 9 === 0);
    const repo = { repo: REPO, key: "" };
    const requests = [
      ...sample.map((key) => request({ ...repo, key })),
      ...sample.filter((_key, index) => index % 2 === 0).map((key) => request({ ...repo, key }, READONLY_TS)),
    ];
    const python = agreeInBatches(requests, 12);
    expect(python.length).toBeGreaterThan(50);
    expect(python.some((result) => result.ok && (result["warnings"] as string[]).length > 0)).toBe(true);
  });
});

// --- 命令一层 ------------------------------------------------------------------------------------

/** launcher：选择文件的 dispatcher 是 ts，经真的启动器转交（第 ④ 步切换）。 */
type Runner = "python" | "node" | "bun" | "launcher";
const RUNNERS: readonly Runner[] = ["python", "node", "bun", "launcher"];

interface Step {
  readonly label: string;
  readonly argv: readonly string[];
  readonly args: Json;
  readonly file?: string;
  readonly crash?: boolean;
}

function commandFixture(name: string): History {
  const h = history(name);
  const base = h.head;
  plan(h.repo, "ok-head", mdOf("ok-head", base), text(jsonOf("ok-head", base)));
  plan(h.repo, "bad", mdOf("bad", base), text({ ...jsonOf("bad", base), risk_level: "huge" }));
  plan(h.repo, "md-utf8", Uint8Array.from([0x23, 0xff]), text(jsonOf("md-utf8", base)));
  plan(h.repo, "d-new", mdOf("d-new", base), null);
  plan(h.repo, "d-v2", mdOf("d-v2", base, { family: "planner-v2" }), null);
  plan(h.repo, "d-has-v2", mdOf("d-has-v2", base), text({ ...jsonOf("d-has-v2", base), contract_family: "planner-v2" }));
  plan(h.repo, "d-long", mdOf("d-long", base, { goal: `把${"很长的一句话".repeat(12)}写成标题。` }), null);
  plan(h.repo, "d-bad", mdOf("d-bad", base).replace("## Budget", "## Spending"), null);
  put(h.repo, "src/ok-head.v1.md", "x");
  // 覆盖审计的缺口（切换 c3a）：JSON 里的条目类型不对要报错、不崩；只在 JSON 里改了 forbidden_paths；DoD 的 intent 是空字符串
  const dod = (extra: Json): Json[] => [{ id: "D01", text: "行为正确", evidence: ["V01"], ...extra }];
  plan(h.repo, "v-auth", mdOf("v-auth", base), text({ ...jsonOf("v-auth", base), authorization: { executor: [{}], integration: [] } }));
  plan(h.repo, "v-evid", mdOf("v-evid", base), text({ ...jsonOf("v-evid", base), definition_of_done: dod({ evidence: [{ a: 1 }] }) }));
  const forbid = jsonOf("v-forbid", base);
  plan(h.repo, "v-forbid", mdOf("v-forbid", base), text({ ...forbid, scope: { ...(forbid["scope"] as Json), forbidden_paths: ["secrets.txt"] } }));
  plan(h.repo, "v-intent", mdOf("v-intent", base), text({ ...jsonOf("v-intent", base), definition_of_done: dod({ intent: "" }) }));
  // 配置里的 commit_trailers 写坏了（带换行）：validate 不管它，“合法”那一步照样通过；branch 才拒绝（branch-review 契约）
  put(h.repo, ".agent/dispatch.config.json", text({ commit_trailers: [`not a trailer${ch(10)}with newline`] }));
  return h;
}

function steps(repo: string): Step[] {
  const validate = (label: string, key: string, crash = false): Step => ({
    label, argv: ["validate", key], args: { command: ["validate"], repo, plan_key: key, context: CONTEXT }, crash,
  });
  const derive = (label: string, key: string, flags: { title?: string; force?: boolean; print?: boolean } = {}): Step => ({
    label,
    argv: ["derive-json", key, ...(flags.print ? ["--print"] : []), ...(flags.force ? ["--force"] : []), ...(flags.title ? ["--title", flags.title] : [])],
    args: { command: ["derive-json"], repo, plan_key: key, title: flags.title ?? null, force: flags.force ?? false, print_only: flags.print ?? false, context: CONTEXT },
    file: join(repo, ".agent", "plans", `${basename(key).replace(/[.]md$/u, "")}.json`),
  });
  return [
    validate("合法", "ok-head.v1"),
    validate("相对路径", ".agent/plans/ok-head.v1.md"),
    validate("绝对路径", join(repo, ".agent", "plans", "ok-head.v1.json")),
    validate("不在 plans 下", "src/ok-head.v1.md"),
    validate("标识不合法", "Bad"),
    validate("缺文件", "nothing.v1"),
    validate("合同无效", "bad.v1"),
    validate("Markdown 不是 UTF-8", "md-utf8.v1", true),
    derive("只打印", "d-new.v1", { print: true }),
    derive("写出", "d-new.v1"),
    derive("已存在", "d-new.v1"),
    derive("覆盖并给标题", "d-new.v1", { force: true, title: "短标题" }),
    derive("Markdown 声明 planner-v2", "d-v2.v1"),
    derive("现有 JSON 是 planner-v2", "d-has-v2.v1", { force: true }),
    derive("长标题", "d-long.v1", { print: true }),
    derive("有问题照样写出", ".agent/plans/d-bad.v1.md"),
    derive("缺 Markdown", "nothing.v1"),
    validate("authorization.executor 里有不是字符串的", "v-auth.v1"),
    validate("DoD 的 evidence 里有不是字符串的", "v-evid.v1"),
    validate("只在 JSON 里改了 forbidden_paths", "v-forbid.v1"),
    validate("DoD 的 intent 是空字符串", "v-intent.v1"),
  ];
}

function runStep(runner: Runner, repo: string, step: Step): CliRun {
  if (runner === "python") return runPythonCli(["--repo", repo, ...step.argv], repo);
  if (runner === "launcher") return runDispatcherLauncherCli(["--repo", repo, ...step.argv], repo);
  return runTsCli(runner, step.args, repo);
}

function shown(result: CliRun, repo: string, step: Step): Json {
  const slash = ch(92);
  const norm = (value: string): string => value.replaceAll(repo.replaceAll(slash, slash + slash), "<REPO>").replaceAll(repo, "<REPO>");
  if (step.crash) return { status: result.status };
  const file = step.file && existsSync(step.file) ? readFileSync(step.file).toString("base64") : "<absent>";
  return { status: result.status, stdout: norm(result.stdout.toString("utf8")), stderr: norm(result.stderr.toString("utf8")), file };
}

describe("validate 与 derive-json 命令", () => {
  it("同一串命令在三份实现各自的仓库里跑，退出码、输出与写出的文件一致", () => {
    const transcripts = RUNNERS.map((runner) => {
      const h = commandFixture(`plan-cli-${runner}`);
      return steps(h.repo).map((step) => ({ label: step.label, ...shown(runStep(runner, h.repo, step), h.repo, step) }));
    });
    for (const transcript of transcripts.slice(1)) expect(transcript).toEqual(transcripts[0]);
    const python = transcripts[0] as Json[];
    expect(python.map((row) => row["status"])).toEqual([0, 0, 0, 2, 2, 2, 2, 1, 0, 0, 2, 0, 3, 3, 0, 2, 2, 2, 2, 2, 2]);
    const said = (index: number): string => `${String((python[index] as Json)["stdout"])}${String((python[index] as Json)["stderr"])}`;
    expect([said(17).includes("authorization.executor"), said(18).includes("evidence"), said(19).includes("secrets.txt"),
      said(20).includes("intent（目的）必须是非空字符串")]).toEqual([true, true, true, true]);
    // 写出的 JSON 是文本模式：Windows 上换行是 CRLF
    const written = Buffer.from(String((python[9] as Json)["file"]), "base64").toString("utf8");
    expect(written.includes(ch(13, 10))).toBe(process.platform === "win32");
  });
});
