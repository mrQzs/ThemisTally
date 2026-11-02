// 合同与战前门禁里改状态的部分（迁移第 ⑤e2b 片）：kit_hub.py 的 sync_executor_line、revalidate_contract、accept_contract、
// bump_contract_version、set_contract_base、accept_gate_pre。改 ts、写合同与证据、记账本、提交门禁的基准测试。
// deps 只给契约用（themistally-15 定的，设计稿第 8.8 节）：契约把用例当时换掉的 run_pd、contract_requirements、budget_problems、
// revalidate_contract 照记录注入；真的 revalidate 里调的也走传进来的 deps。生产调用方不传。
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { utcCompact } from "@themis/base/clock";
import { readText, writeText } from "@themis/base/fsutil";
import { PyCrash, pyGet, pyIntOf, pyItem, pyPercentD, pyReprValue, pyStrValue, pyTruthy } from "@themis/base/pyfmt";
import { pyDecodeUtf8Replace } from "@themis/base/pyio";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { purePathName, purePathParent, purePathStr } from "@themis/base/pypath";
import { D, S, pyLstrip, pyRegex, pyRstrip, pySplitlines, pyStrip } from "@themis/base/pyre";
import { runSupervised } from "@themis/base/supervise";
import { CONTRACT_EXECUTOR_LINE } from "./constants.ts";
import {
  budgetProblems, contractDigest, contractPaths, contractRequirements, decisionsSection, hollowBaselineProblems, normalizeIdentity, normalizeMarkup,
  stripDecisions, tail,
} from "./contract.ts";
import { git, workspaceStatus } from "./kernel.ts";
import type { Hub } from "./mailbox.ts";
import { nextContractVersion } from "./prompt.ts";
import { kernelPytest, kernelPytestEnv, runPd } from "./runpd.ts";
import { gateFile, relativeTo as relative } from "./taskstate.ts";

const LF = String.fromCharCode(10);
const TAB = String.fromCharCode(9);
const LINE_START = `(?<![^${LF}])`;
const LINE_END = `(?=${LF}|$)`;
/** Python 正则的非空白类：不是空白的任何字符。 */
const NOT_SPACE = `(?:(?!${S})[^])`;

/** 用例当时换掉的几个内核函数（契约照记录注入）；缺省是真函数。 */
export interface ContractDeps {
  readonly runPd: (hub: Hub, args: readonly string[], timeout?: number) => Promise<[number, string]>;
  readonly contractRequirements: (hub: Hub, ts: PyDict) => string[] | Promise<string[]>;
  readonly budgetProblems: (hub: Hub, ts: PyDict) => string[] | Promise<string[]>;
  readonly revalidateContract: (hub: Hub, ts: PyDict, deps: ContractDeps) => Promise<string[]>;
}

export const REAL_DEPS: ContractDeps = {
  runPd: (hub, args, timeout) => runPd(hub, args, timeout),
  contractRequirements,
  budgetProblems,
  revalidateContract: (hub, ts, deps) => revalidateContract(hub, ts, deps),
};

const dict = (value: PyValue): PyDict => {
  if (!(value instanceof Map)) throw new PyCrash("TypeError", `'${typeof value}' object does not support item assignment`);
  return value;
};

/** re.subn 只换字面的替换串：交回（新文本，换了几处）。 */
function subn(pattern: RegExp, replacement: string, value: string): [string, number] {
  let count = 0;
  const out = value.replace(pattern, () => {
    count += 1;
    return replacement;
  });
  return [out, count];
}

export const EXECUTOR_LINE_RE = pyRegex(`${LINE_START}-[ ${TAB}]*executor:[^${LF}]*${LINE_END}`);
/** re.M 下的“行首 - plan_version:、空白、数字、空白、行尾”：空白可以跨行（照抄，后面接空行时会吃掉一个换行）。 */
const PLAN_VERSION_RE = pyRegex(`${LINE_START}- plan_version:${S}*${D}+${S}*${LINE_END}`, true);
const BASE_SHA_RE = pyRegex(`${LINE_START}- base_sha:${S}*${NOT_SPACE}+${S}*${LINE_END}`, true);

/**
 * 名册换了执行模型：还没派遣的合同版本，执行模型一行改写成名册的；交回原来写的，没改时 null。已派遣的版本只增不改。
 * 行尾的回车算在行里（不是换行的字符都算），换掉的那一行就没有回车了，照 Python。
 */
export async function syncExecutorLine(hub: Hub, ts: PyDict): Promise<string | null> {
  if (pyTruthy(pyGet(pyItem(ts, "contract"), "dispatched"))) return null;
  const [md] = contractPaths(hub, ts);
  const text = readText(md);
  const match = EXECUTOR_LINE_RE.exec(text);
  if (match === null || pyStrip(match[0]) === CONTRACT_EXECUTOR_LINE) return null;
  writeText(md, text.slice(0, match.index) + CONTRACT_EXECUTOR_LINE + text.slice(match.index + match[0].length), false);
  await hub.appendEvent("contract.executor_synced", [["task", pyItem(ts, "task")], ["key", pyItem(pyItem(ts, "contract"), "key")], ["previous", pyStrip(match[0])]]);
  return pyStrip(match[0]);
}

/** derive-json 后 validate；交回问题清单（空表示通过），并更新合同的哈希与状态。 */
export async function revalidateContract(hub: Hub, ts: PyDict, deps: ContractDeps = REAL_DEPS): Promise<string[]> {
  const key = pyItem(pyItem(ts, "contract"), "key") as string;
  await syncExecutorLine(hub, ts);
  const args = ["derive-json", key, "--force"];
  if (pyTruthy(pyGet(ts, "title"))) args.push("--title", pyItem(ts, "title") as string); // 合同标题是分支提交的主题行（第 12 轮）
  let [code, out] = await deps.runPd(hub, args);
  const problems: string[] = [];
  if (code !== 0) {
    problems.push(`derive-json 失败：${LF}${tail(out)}`);
  } else {
    [code, out] = await deps.runPd(hub, ["validate", key]);
    if (code !== 0) problems.push(`validate 失败：${LF}${tail(out)}`);
  }
  if (!problems.length) problems.push(...(await deps.contractRequirements(hub, ts)));
  const contract = dict(pyItem(ts, "contract"));
  contract.set("validated", !problems.length);
  contract.set("sha256", contractDigest(hub, ts));
  contract.set("problems", problems);
  return problems;
}

/** 合同端交的合同：首行、版本号、Identity 与粗体编号的规整、站主决定段，写成新版本（还没核验过的同号重交时旧稿进 evidence）。 */
export async function acceptContract(hub: Hub, ts: PyDict, output: PyValue, deps: ContractDeps = REAL_DEPS): Promise<string[]> {
  const given = pyGet(output, "contract_md");
  if (typeof given !== "string" || !pyStrip(given)) return ["输出里没有 contract_md（合同 Markdown 全文）"];
  const [version, redraft] = nextContractVersion(ts);
  const header = `# TASK: ${pyStrValue(pyItem(ts, "contract_task"))}`;
  if (pyStrip(pySplitlines(pyLstrip(given))[0] as string) !== header) return [`合同第一行必须是“${header}”`];
  const key = `${pyStrValue(pyItem(ts, "contract_task"))}.v${pyPercentD(version)}`;
  const path = purePathStr(hub.repo, ".agent", "plans", `${key}.md`);
  const json = purePathStr(hub.repo, ".agent", "plans", `${key}.json`);
  mkdirSync(purePathParent(path), { recursive: true });
  if (existsSync(path)) {
    if (!redraft) return [`${purePathName(path)} 已存在，合同版本只增不改`];
    const evidence = purePathStr(hub.taskDir(`${pyStrValue(pyItem(ts, "task"))}-2-contract`), "evidence"); // 没过核验的旧稿留档
    mkdirSync(evidence, { recursive: true });
    const stamp = utcCompact();
    for (const [old, suffix] of [[path, ".md"], [json, ".json"]] as const) {
      if (existsSync(old)) copyFileSync(old, purePathStr(evidence, `${key}.rejected-${stamp}${suffix}`));
    }
    await hub.appendEvent("contract.redrafted", [["task", pyItem(ts, "task")], ["key", key]]);
  }
  const [identity, changed] = normalizeIdentity(given, new Map<string, PyValue>([["plan_version", String(version)], ["base_sha", pyItem(ts, "base_head")]]));
  if (changed.size) await hub.appendEvent("contract.identity_normalized", [["task", pyItem(ts, "task")], ["key", key], ["written", changed]]);
  const [markup, bold] = normalizeMarkup(identity);
  if (bold) await hub.appendEvent("contract.markup_normalized", [["task", pyItem(ts, "task")], ["key", key], ["lines", bold]]);
  let text = `${pyRstrip(stripDecisions(markup))}${LF}`;
  if (pyTruthy(pyGet(ts, "decisions"))) text += LF + decisionsSection(pyItem(ts, "decisions"));
  writeText(path, `${pyRstrip(text)}${LF}`, false);
  // written_version：合同端写的这一版。之后热修补、重派、返工只复制升版，内容不变（carry_source 据此判断旧 attempt 的候选是不是按同一份合同做的）
  ts.set("contract", new Map<string, PyValue>([
    ["version", version], ["key", key], ["md", relative(path, hub.repo)], ["json", relative(json, hub.repo)],
    ["written_version", version],
  ]));
  await hub.appendEvent("contract.written", [["task", pyItem(ts, "task")], ["key", key]]);
  let problems = await deps.revalidateContract(hub, ts, deps);
  if (!problems.length) {
    // 只查合同端交的新版本：热修补复制出来的版本照搬旧预算，门禁端改不了它
    problems = await deps.budgetProblems(hub, ts);
    dict(pyItem(ts, "contract")).set("validated", !problems.length);
  }
  return problems;
}

/** 已派遣过的合同不再改：复制成下一个版本（只改 plan_version），之后的 base_sha 改在新版本上。 */
export async function bumpContractVersion(hub: Hub, ts: PyDict): Promise<string[]> {
  const [oldMd] = contractPaths(hub, ts);
  const version = pyIntOf(pyItem(pyItem(ts, "contract"), "version")) + 1n;
  const key = `${pyStrValue(pyItem(ts, "contract_task"))}.v${version}`;
  const newMd = purePathStr(purePathParent(oldMd), `${key}.md`);
  if (existsSync(newMd)) return [`${purePathName(newMd)} 已存在，合同版本只增不改`];
  const [text, count] = subn(PLAN_VERSION_RE, `- plan_version: ${version}`, readText(oldMd));
  if (count !== 1) return ["合同 Identity 里找不到唯一的“- plan_version:”行"];
  writeText(newMd, text, false);
  const newJson = purePathStr(purePathParent(newMd), `${key}.json`);
  ts.set("contract", new Map<string, PyValue>([
    ["version", version], ["key", key], ["md", relative(newMd, hub.repo)], ["json", relative(newJson, hub.repo)], ["bumped_from", version - 1n],
    ["written_version", pyGet(pyItem(ts, "contract"), "written_version")],
  ]));
  await hub.appendEvent("contract.bumped", [["task", pyItem(ts, "task")], ["key", key]]);
  return [];
}

export async function setContractBase(hub: Hub, ts: PyDict, sha: string, deps: ContractDeps = REAL_DEPS): Promise<string[]> {
  const [md] = contractPaths(hub, ts);
  const [updated, count] = subn(BASE_SHA_RE, `- base_sha: ${sha}`, readText(md));
  if (count !== 1) return ["合同 Identity 里找不到唯一的“- base_sha:”行"];
  writeText(md, updated, false);
  return deps.revalidateContract(hub, ts, deps);
}

/**
 * KERNEL_PYTEST 的 --collect-only：标准输出与标准错误合进同一个文件（Python 的 stderr=STDOUT），stdin 接空设备，600 秒时限，
 * 超时照 subprocess.run 报 TimeoutExpired。交回（退出码，utf-8 加 replace 解码的输出）。
 */
async function collectOnly(workspace: string, file: string): Promise<[number, string]> {
  const cmd = [...kernelPytest(), "--collect-only", "-q", file];
  const dir = mkdtempSync(join(tmpdir(), "themis-collect-"));
  const out = join(dir, "output");
  try {
    const result = await runSupervised(cmd, {
      cwd: workspace, env: [...kernelPytestEnv()], stdout: { path: out, how: "create-new" }, stderr: "stdout", timeout: 600, grace: 0, handleSignals: false,
    });
    if (result.timed_out) throw new PyCrash("TimeoutExpired", `Command '${pyReprValue(cmd)}' timed out after 600 seconds`); // str(TimeoutExpired)
    if (result.spawn_error !== null) throw new PyCrash("OSError", result.spawn_error);
    return [result.exit_code as number, pyDecodeUtf8Replace(readFileSync(out))];
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

/** 门禁端只能新增 tests/test_gate_<t>_baseline.py；内核提交、挂引用、改合同 base_sha、跑 baseline。 */
export async function acceptGatePre(hub: Hub, ts: PyDict, workspace: string, deps: ContractDeps = REAL_DEPS): Promise<string[]> {
  const changes = workspaceStatus(workspace);
  const expected = gateFile(ts, "baseline");
  if (!changes.length) return [`门禁草稿 worktree 里没有新增文件：要新增 ${expected}`];
  const bad = changes.filter(([status, path]) => status !== "??" || path !== expected).map(([, path]) => path);
  if (bad.length) return [`只能新增 ${expected}，不能改动别的文件：${bad.slice(0, 8).join(", ")}`];
  // 基准测试要“收集得到、在断言上失败”：语法错误或模块级导入失败的测试在基线上也是失败，不先挡下就会被当成合格的基准锁进禁改路径
  const [collected, collectOut] = await collectOnly(workspace, expected);
  if (collected !== 0) {
    return [`${expected} 收集失败（pytest --collect-only 退出码 ${collected}：语法错误、模块级导入失败或没有用例；被测的新符号要在用例函数里再 import）：${LF}`
      + tail(collectOut, 15n)];
  }
  const hotfix = pyGet(ts, "hotfix");
  const previous = pyGet(pyTruthy(hotfix) ? hotfix : new Map(), "previous_oracle");
  if (pyTruthy(pyGet(pyItem(ts, "contract"), "dispatched"))) {
    const problems = await bumpContractVersion(hub, ts);
    if (problems.length) return problems;
  }
  git(["add", "--", expected], workspace);
  const task = pyItem(ts, "task");
  git(["commit", "-q", "-m", `门禁端基准测试：${pyStrValue(task)}（gate-sonnet，hub）`], workspace);
  const sha = pyStrip(git(["rev-parse", "HEAD"], workspace));
  const ref = `refs/themis/oracle/${pyStrValue(pyItem(ts, "contract_task"))}/v${pyPercentD(pyItem(pyItem(ts, "contract"), "version"))}`;
  git(["update-ref", ref, sha], hub.repo);
  dict(pyItem(pyItem(ts, "workspaces"), "gate")).set("commit", sha);
  ts.set("oracle", new Map<string, PyValue>([["sha", sha], ["ref", ref], ["files", [expected]], ["locked", false]]));
  await hub.appendEvent("oracle.committed", [["task", task], ["sha", sha], ["ref", ref]]);
  if (pyTruthy(previous)) { // 热修补：把测试差异留给重做的一审（审核端只看这一份差异）
    const diff = git(["diff", previous as string, sha, "--", expected], hub.repo);
    const evidence = purePathStr(hub.taskDir(`${pyStrValue(task)}-3-gate-pre`), "evidence");
    mkdirSync(evidence, { recursive: true });
    const diffPath = purePathStr(evidence, `hotfix-${utcCompact()}.diff`);
    writeText(diffPath, diff, false);
    const oracle = dict(pyItem(ts, "oracle"));
    oracle.set("hotfix_diff", relative(diffPath, hub.repo));
    oracle.set("hotfix_from", previous);
  }
  let problems = await setContractBase(hub, ts, sha, deps);
  if (problems.length) return problems;
  const [code, out] = await deps.runPd(hub, ["baseline", pyItem(pyItem(ts, "contract"), "key") as string], 1800);
  dict(pyItem(ts, "oracle")).set("baseline_exit", BigInt(code));
  dict(pyItem(ts, "oracle")).set("baseline_tail", tail(out, 20n));
  if (code !== 0) return [`baseline 不符合预期（基准测试应在基线上失败，其余检查按合同）：${LF}${tail(out, 20n)}`];
  problems = hollowBaselineProblems(hub, out, expected);
  if (problems.length) return problems;
  dict(pyItem(ts, "oracle")).set("locked", true);
  dict(pyItem(ts, "contract")).set("sha256", contractDigest(hub, ts));
  if (pyTruthy(pyGet(ts, "hotfix"))) {
    if (!ts.has("hotfixes")) ts.set("hotfixes", []);
    const hotfixes = pyItem(ts, "hotfixes") as PyValue[];
    const record = new Map(dict(pyItem(ts, "hotfix")));
    ts.delete("hotfix");
    record.set("oracle", sha);
    record.set("contract", pyItem(pyItem(ts, "contract"), "key"));
    hotfixes.push(record);
  }
  return [];
}
