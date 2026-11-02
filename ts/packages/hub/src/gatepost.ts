// 战后门禁与变异（迁移第 ⑤f 片）：kit_hub.py 的 attempt_base、apply_candidate、ensure_worktree、add_worktree、seed_whitebox、
// accept_gate_post、mutant_timeout、TEST_FILE_RE、unmutated_problems、gate_spec、unchanged_mismatches、run_mutations、
// expected_missed_everywhere、candidate_defects、defect_matches、defect_match_problems、mutation_problems。
// 模型交来的值（输出里的 mutation_spec、unmutated、candidate_defects，清单文件的内容）可以是任何 JSON 值：取键、迭代、取长度、
// 做集合与排序、乘加都照 Python 的语义，报错的类型与文字也照 Python（设计稿第 4 节第三张表）。
// deps 只给契约用（themistally-15 定的，设计稿第 3 节、第 10 节）：用例当时换掉的 run_pd、worktree_root，以及白盒测试那一次
// run_supervised 与 mkdtemp 照记录注入。生产调用方不传。
import { copyFileSync, existsSync, lstatSync, statSync } from "node:fs";
import { utcCompact, utcNow } from "@themis/base/clock";
import { readText, writeText } from "@themis/base/fsutil";
import { FileLockTimeout, withFileLock } from "@themis/base/native";
import { PyCrash, pyFloatOf, pyGet, pyIntOf, pyItem, pyIter, pyLenValue, pyPercentD, pyPlus, pyReprValue, pyStrValue, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { PyUnicodeDecodeError, pyReadText } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyKey, type PyValue, dumps, loads } from "@themis/base/pyjson";
import { pathMkdir } from "@themis/base/pyos";
import { purePathName, purePathParent, purePathStr } from "@themis/base/pypath";
import { D, PY_END, S, codePoints, pyIntParse, pyLower, pyRegex, pySplitlines, pyStrip } from "@themis/base/pyre";
import { PyKeyedDict, PySet, hashKey, pyLess, pySorted } from "@themis/base/pyset";
import { pyMkdtemp } from "@themis/base/pytempfile";
import { pyEq } from "@themis/base/pyvalue";
import { type SuperviseOptions, type SuperviseResult, runSupervised } from "@themis/base/supervise";
import { globPaths } from "@themis/dispatcher/instruction";
import { MUTATION_DEFAULT_TIMEOUT } from "@themis/dispatcher/mutate";
import { comparePaths } from "./audit.ts";
import { EXIT_BLOCKED } from "./constants.ts";
import { pytestOutcomes, tail, tailFile } from "./contract.ts";
import { HubError } from "./errors.ts";
import { worktreeRoot } from "./inputs.ts";
import { git, workspaceStatus } from "./kernel.ts";
import type { Hub } from "./mailbox.ts";
import { kernelPytest, kernelPytestEnv, runPd } from "./runpd.ts";
import { gateFile, relativeTo as relative } from "./taskstate.ts";

const LF = String.fromCharCode(10);
const LINE_START = `(?<![^${LF}])`;

/** 用例当时换掉、或这一片要录下来的几个内层调用（契约照记录注入）；缺省是真函数。 */
export interface GatePostDeps {
  readonly runPd: (hub: Hub, args: readonly string[], timeout?: number) => Promise<[number, string]>;
  readonly worktreeRoot: (repo: string) => string | Promise<string>;
  readonly runSupervised: (cmd: readonly string[], options: SuperviseOptions) => Promise<SuperviseResult>;
  readonly mkdtemp: (prefix: string, dir: string) => string | Promise<string>;
}

export const REAL_GATE_POST_DEPS: GatePostDeps = {
  runPd: (hub, args, timeout) => runPd(hub, args, timeout),
  worktreeRoot,
  runSupervised,
  mkdtemp: pyMkdtemp,
};

/** x or y。 */
const or = (value: PyValue, fallback: PyValue): PyValue => (pyTruthy(value) ? value : fallback);
const isDict = (value: PyValue): value is PyDict => value instanceof Map;

function dict(value: PyValue): PyDict {
  if (!isDict(value)) throw new PyCrash("TypeError", `'${pyTypeName(value)}' object does not support item assignment`);
  return value;
}

function isDir(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

/** Path.is_symlink()：Windows 上 lstat 把联接也当链接，联接指向目录，is_file 本来就是假，结果相同。 */
function isSymlink(path: string): boolean {
  try {
    return lstatSync(path).isSymbolicLink();
  } catch {
    return false;
  }
}

/** except ValueError 接得住的：json.loads 的报错，以及 read_text 读到不是 UTF-8 的文件（base 的 fsutil 与 pyio 各有一个，名字相同）。 */
const isValueError = (error: unknown): boolean =>
  (error instanceof PyJsonError && (error.kind === "ValueError" || error.kind === "JSONDecodeError")) || (error as Error | null)?.name === "UnicodeDecodeError";

/** str(Path(ts["exec"]["run_dir"]))。 */
const runDirOf = (ts: PyDict): string => purePathStr(pyStrValue(pyItem(pyItem(ts, "exec"), "run_dir")));

/** attempt 实际的基线：返工版本的基线是上一轮的返工提交，不是基准测试提交（第 10 轮）。 */
export function attemptBase(ts: PyDict, runDir: string): PyValue {
  let base: PyValue;
  try {
    base = pyGet(loads(readText(purePathStr(runDir, "meta.json")) || "{}"), "base_sha");
  } catch (error) {
    if (!isValueError(error)) throw error;
    return pyItem(pyItem(ts, "oracle"), "sha");
  }
  return pyTruthy(base) ? base : pyItem(pyItem(ts, "oracle"), "sha");
}

/** 战后与终审用的候选 worktree：attempt 的基线提交（含基准测试）加候选补丁，不提交。 */
export async function applyCandidate(hub: Hub, ts: PyDict, deps: GatePostDeps = REAL_GATE_POST_DEPS): Promise<string> {
  const runDir = runDirOf(ts);
  const key = `post-${purePathName(runDir)}`;
  const workspace = await ensureWorktree(hub, ts, key, attemptBase(ts, runDir), deps);
  const record = dict(pyItem(pyItem(ts, "workspaces"), key));
  if (!pyTruthy(pyGet(record, "patched"))) {
    const patch = purePathStr(runDir, "candidate.patch");
    if (existsSync(patch) && statSync(patch).size) git(["apply", "--whitespace=nowarn", patch], workspace);
    record.set("patched", true);
    record.set("baseline_status", workspaceStatus(workspace));
  }
  return workspace;
}

/** 阶段用的分离 HEAD worktree；同一种类在同一主任务里复用（会话续接要求工作目录不变）。 */
export async function ensureWorktree(hub: Hub, ts: PyDict, kind: string, commit: PyValue, deps: GatePostDeps = REAL_GATE_POST_DEPS): Promise<string> {
  const workspaces = dict(pyItem(ts, "workspaces"));
  const recorded = or(pyGet(workspaces, kind), new Map());
  const given = pyGet(recorded, "path");
  const existing = pyTruthy(given) ? purePathStr(pyStrValue(given)) : null;
  if (existing !== null && isDir(existing) && pyEq(pyGet(recorded, "commit"), commit)) return existing;
  const task = pyItem(ts, "task");
  if (typeof task !== "string") throw new PyCrash("AttributeError", `'${pyTypeName(task)}' object has no attribute 'lower'`);
  const prefix = `${codePoints(purePathName(hub.repo)).slice(0, 16).join("")}-hub-${pyLower(task)}-${kind}-`;
  const path = purePathStr(await deps.mkdtemp(prefix, purePathStr(await deps.worktreeRoot(hub.repo))));
  await addWorktree(hub, path, pyStrValue(commit));
  workspaces.set(kind, new Map<string, PyValue>([["path", path], ["commit", commit], ["created_at", utcNow()]]));
  await hub.appendEvent("workspace.created", [["task", task], ["kind", kind], ["path", path], ["commit", commit]]);
  return path;
}

/** worktree add 撞上并发的 Git 元数据锁时重试几次。 */
export const WORKTREE_ADD_TRIES = 3;

/**
 * git worktree add，几个主任务的 runner 之间串行（第 20 轮）。撞上 Git 自己的锁就重试，每次多等一秒。kit_hub 的 file_lock 等锁超时
 * 报的也是 HubError（EXIT_BLOCKED），一样重试。
 */
export async function addWorktree(hub: Hub, path: string, commit: string): Promise<void> {
  for (let attempt = 1; attempt <= WORKTREE_ADD_TRIES; attempt += 1) {
    try {
      await withFileLock(purePathStr(hub.root, "ledger", ".git-worktrees.lock"), () => {
        git(["worktree", "add", "--detach", path, commit], hub.repo);
      });
      return;
    } catch (caught) {
      const error = caught instanceof FileLockTimeout ? new HubError(caught.message, EXIT_BLOCKED) : caught;
      if (!(error instanceof HubError) || attempt === WORKTREE_ADD_TRIES) throw error;
      await new Promise((done) => setTimeout(done, attempt * 1000));
    }
  }
}

/**
 * 新 attempt 的战后门禁从上一轮的白盒测试接着改（第 28 轮）：每个 worktree 只放一次，门禁删了它就是不要。返回放进来的那一份
 * （相对仓库的路径）。Windows 上 glob 与 Path 的排序都不分大小写。
 */
export async function seedWhitebox(hub: Hub, ts: PyDict, workspace: string): Promise<string | null> {
  const record = dict(pyItem(pyItem(ts, "workspaces"), `post-${purePathName(runDirOf(ts))}`));
  const target = purePathStr(workspace, gateFile(ts, "whitebox"));
  if (pyTruthy(pyGet(record, "whitebox_seeded")) || existsSync(target)) return null;
  const evidence = purePathStr(hub.taskDir(`${pyStrValue(pyItem(ts, "task"))}-6-gate-post`), "evidence");
  const copies = globPaths(evidence, ["whitebox-*.py"]).sort(comparePaths);
  const latest = copies.at(-1);
  if (latest === undefined) return null;
  pathMkdir(purePathParent(target), true, true);
  copyFileSync(latest, target);
  const seeded = relative(latest, hub.repo);
  record.set("whitebox_seeded", seeded);
  await hub.appendEvent("whitebox.seeded", [["task", pyItem(ts, "task")], ["source", seeded], ["workspace", purePathStr(workspace)]]);
  return seeded;
}

/** 白盒测试的结果里不许出现的几种：T002 的战后门禁把 3 处合同违反标成 xfail(strict=True)，候选照样“通过”（第 9 轮）。 */
export const SOFT_OUTCOMES = ["xfailed", "xpassed", "skipped"] as const;

/** 只增不改：只能新增 tests/test_gate_<t>_whitebox.py；内核在候选上跑白盒测试与变异清单。 */
export async function acceptGatePost(hub: Hub, ts: PyDict, workspace: string, output: PyValue, deps: GatePostDeps = REAL_GATE_POST_DEPS): Promise<string[]> {
  const key = `post-${purePathName(runDirOf(ts))}`;
  const before = new Set(pyIter(or(pyGet(pyItem(pyItem(ts, "workspaces"), key), "baseline_status"), [])).map((item) => JSON.stringify(item)));
  const after = new Map(workspaceStatus(workspace).map((item) => [JSON.stringify(item), item]));
  const added = pySorted([...after].filter(([seen]) => !before.has(seen)).map(([, item]) => item)) as [string, string][];
  const expected = gateFile(ts, "whitebox");
  // 第 85 轮：工作目录根下的变异清单文件也可以新增（mutation_spec_file），它不进仓库，内核读完存档
  const bad = added.filter(([status, path]) => status !== "??" || (path !== expected && path !== GATE_SPEC_FILE)).map(([, path]) => path);
  const mismatch = pyGet(pyItem(ts, "gate_post"), "anchor_mismatch"); // 上一版清单锚点对不上的条目，跨交付留着（第 85 轮）
  const gatePost = new Map<string, PyValue>([["ran", true], ["ok", false]]);
  ts.set("gate_post", gatePost);
  if (pyTruthy(mismatch)) gatePost.set("anchor_mismatch", mismatch);
  if (bad.length) return [`战后只能新增 ${expected}（只增不改）：${bad.slice(0, 8).join(", ")}`];
  if (!existsSync(purePathStr(workspace, expected))) return [`没有新增 ${expected}`];
  const stageDir = hub.taskDir(`${pyStrValue(pyItem(ts, "task"))}-6-gate-post`);
  const evidence = purePathStr(stageDir, "evidence");
  pathMkdir(evidence, true, true);
  const stamp = utcCompact();
  // 白盒测试是这次 attempt 的证据，不并入仓库：存一份在信箱，结项清理 worktree 之后还能复核（第 12 轮）
  const whiteboxCopy = purePathStr(evidence, `whitebox-${stamp}.py`);
  copyFileSync(purePathStr(workspace, expected), whiteboxCopy);
  gatePost.set("whitebox_file", relative(whiteboxCopy, hub.repo));
  const whiteboxLog = purePathStr(evidence, `whitebox-${stamp}.log`);
  // Job Object 监督：超时连同子进程一起清掉；输出进文件（独占新建，标准错误同一个句柄），不整份读进内存
  const result = await deps.runSupervised([...kernelPytest(), expected, "-q", "-rfE"], {
    cwd: purePathStr(workspace), env: [...kernelPytestEnv()], stdout: { path: whiteboxLog, how: "create-new" }, stderr: "stdout", timeout: 1800, grace: 15,
    handleSignals: true,
  });
  const whiteboxTail = tailFile(whiteboxLog, 15n);
  gatePost.set("whitebox_seconds", result.wall_seconds);
  gatePost.set("whitebox_exit", result.exit_code === null ? null : BigInt(result.exit_code));
  gatePost.set("whitebox_tail", whiteboxTail);
  gatePost.set("whitebox_log", relative(whiteboxLog, hub.repo));
  const [counts, failed, errored] = pytestOutcomes(whiteboxLog);
  gatePost.set("whitebox_counts", counts);
  const problems: string[] = [];
  const soft = SOFT_OUTCOMES.filter((name) => pyTruthy(counts.get(name) ?? null)).map((name) => `${pyPercentD(counts.get(name))} 个 ${name}`);
  if (soft.length) {
    problems.push(`白盒测试里有 ${soft.join("、")}：不许用 xfail、skip 标掉失败。合同写明的行为候选不满足，就让测试红着、写进 `
      + "candidate_defects；合同本身没说清的不写断言，写进“需协调人决定”");
  }
  const [defects, defectProblems] = candidateDefects(output);
  problems.push(...defectProblems);
  if (result.exit_code === 0 && !result.timed_out) {
    if (defects.length) problems.push(`candidate_defects 列了 ${defects.length} 条，可白盒测试在候选上全部通过：每处缺陷要有一条红的测试证明`);
    problems.push(...(await runMutations(hub, ts, workspace, stageDir, output, deps)));
  } else if (result.exit_code === 1 && !result.timed_out && failed.length && !errored.length && defects.length) {
    // 门禁端举证候选有缺陷（第 9 轮）：红的正好是它列的那几条才算数；变异检查不跑，mutate 要求测试在候选上是绿的
    problems.push(...defectMatchProblems(defects, failed));
    if (!problems.length) gatePost.set("defects", defects);
  } else {
    problems.push(`白盒测试在候选上没有全部通过${result.timed_out ? "（超时）" : ""}（候选不满足合同写明的行为时，在 candidate_defects 里逐条写明`
      + `红的用例）：${LF}${whiteboxTail}`);
  }
  gatePost.set("ok", !problems.length && !pyTruthy(pyGet(gatePost, "defects")));
  return problems;
}

/** 每条变异的时限：白盒测试在候选上用时的几倍，下限多少秒（第 15 轮）。 */
export const MUTANT_TIMEOUT_FACTOR = 5;
export const MUTANT_TIMEOUT_MIN = 60n;

/** 变异常把代码改成死循环；门禁端自己写了时限就照它的。 */
export function mutantTimeout(spec: PyValue, whiteboxSeconds: PyValue): bigint | null {
  if (pyTruthy(pyGet(spec, "timeout_seconds")) || !pyTruthy(whiteboxSeconds)) return null;
  const scaled = pyIntOf(pyFloatOf(whiteboxSeconds) * MUTANT_TIMEOUT_FACTOR) + 1n;
  return scaled > MUTANT_TIMEOUT_MIN ? scaled : MUTANT_TIMEOUT_MIN;
}

/** 执行端自己的测试文件：不要求变异打在上面。 */
export const TEST_FILE_RE = pyRegex(`(?:^|/)tests?/|(?:^|/)test_[^/]*[.]py${PY_END}|[.](?:test|spec)[.][cm]?[jt]sx?${PY_END}`);

function isTestFile(path: PyValue): boolean {
  if (typeof path !== "string") throw new PyCrash("TypeError", `expected string or bytes-like object, got '${pyTypeName(path)}'`);
  return TEST_FILE_RE.test(path);
}

/** 变异要打在执行端改动的文件上（第 14 轮）；确实没法变异的写进 unmutated，终审复核。 */
export function unmutatedProblems(ts: PyDict, spec: PyValue, output: PyValue): string[] {
  const scope = loads(readText(purePathStr(runDirOf(ts), "scope.json")) || "{}");
  const changed = pySorted(pyIter(or(pyGet(scope, "files"), [])).filter((item) => isDict(item) && pyTruthy(pyGet(item, "path"))
    && !pyEq(pyGet(item, "status"), "D") && !isTestFile(pyItem(item, "path"))).map((item) => pyItem(item, "path"))) as string[];
  const covered = new PySet(pyIter(pyItem(spec, "mutations")).filter(isDict).map((item) => pyGet(item, "file")));
  const explained = new PyKeyedDict();
  for (const item of pyIter(or(pyGet(output, "unmutated"), []))) {
    if (isDict(item) && pyStrip(pyStrValue(or(pyGet(item, "reason"), "")))) explained.set(pyGet(item, "file") as PyKey, pyStrip(pyStrValue(pyGet(item, "reason"))));
  }
  const pairs = pySorted([...explained.toDict()].map(([file, reason]) => [file, reason] as PyValue[])) as [PyValue, string][];
  dict(pyItem(ts, "gate_post")).set("unmutated", pairs.filter(([file]) => typeof file === "string" && changed.includes(file))
    .map(([file, reason]) => `${pyStrValue(file)}：${reason}`));
  const missing = changed.filter((path) => !covered.has(path) && !explained.has(path));
  if (missing.length) {
    return [`执行端改动了这些文件，变异清单却一条也没打在上面：${missing.join("、")}。每个改动的文件至少一条变异；确实没法变异的`
      + `（例如二进制文件），在输出的 unmutated 里写 {"file": ..., "reason": ...}，终审会复核`];
  }
  return [];
}

/** 战后门禁的变异清单文件（第 85 轮）：工作目录根下，输出里用 mutation_spec_file 指它。 */
export const GATE_SPEC_FILE = "mutation-spec.json";

/** 战后门禁交的变异清单：内联的 mutation_spec，或工作目录根下 mutation-spec.json 文件（二选一）。交回（清单, 问题）。 */
export function gateSpec(workspace: string, output: PyValue): [PyValue, string | null] {
  const named = pyGet(output, "mutation_spec_file");
  if (named === null) return [pyGet(output, "mutation_spec"), null];
  if (pyGet(output, "mutation_spec") !== null) return [null, "mutation_spec 与 mutation_spec_file 只给一样（建议只给文件）"];
  if (named !== GATE_SPEC_FILE) return [null, `mutation_spec_file 只能是工作目录根下的 ${GATE_SPEC_FILE}，收到的是 ${pyReprValue(named)}`];
  const path = purePathStr(workspace, GATE_SPEC_FILE);
  if (isSymlink(path) || !isFile(path)) return [null, `mutation_spec_file 指的 ${GATE_SPEC_FILE} 不在工作目录根下，或者不是普通文件`];
  try {
    return [loads(pyReadText(path)), null];
  } catch (error) {
    if (!(error instanceof PyUnicodeDecodeError) && !isValueError(error)) throw error;
    return [null, `${GATE_SPEC_FILE} 不是合法的 UTF-8 JSON：${(error as Error).message}`];
  }
}

/** item in 字典：键要能散列（不能就照 Python 报 TypeError）；JSON 字典的键都是字符串。 */
function inDict(item: PyValue, container: PyDict): boolean {
  hashKey(item);
  return typeof item === "string" && container.has(item);
}

/** 上一版清单锚点对不上的条目，这一版一字没改的（第 85 轮：T016 的 W-M20 连着两回合说改了、实际没改）。 */
export function unchangedMismatches(ts: PyDict, spec: PyValue): string[] {
  const before = or(pyGet(pyItem(ts, "gate_post"), "anchor_mismatch"), new Map());
  return pyIter(or(pyGet(spec, "mutations"), [])).filter((item) => isDict(item) && inDict(pyGet(item, "name"), dict(before))
    && pyEq(dict(before).get(pyItem(item, "name") as string) as PyValue, pyGet(item, "old"))).map((item) => pyStrValue(pyGet(item, "name")));
}

/** runs * timeout：int 乘 int、bool、float 是数，乘 str 与 list 是重复，别的照 Python 报 TypeError。 */
function pyTimes(runs: bigint, value: PyValue): PyValue {
  if (typeof value === "bigint") return runs * value;
  if (typeof value === "boolean") return value ? runs : 0n;
  if (typeof value === "number") return Number(runs) * value;
  if (typeof value === "string") return value.repeat(Number(runs));
  if (Array.isArray(value)) return Array.from({ length: Number(runs) }, () => value).flat();
  throw new PyCrash("TypeError", `unsupported operand type(s) for *: 'int' and '${pyTypeName(value)}'`);
}

const ANCHOR_FAILED_RE = pyRegex(`${LINE_START}(?:MISMATCH|MISSING)${S}+M(${D}+)${S}`, true);

export async function runMutations(hub: Hub, ts: PyDict, workspace: string, stageDir: string, output: PyValue,
  deps: GatePostDeps = REAL_GATE_POST_DEPS): Promise<string[]> {
  const [given, problem] = gateSpec(workspace, output);
  if (problem !== null) return [problem];
  if (!isDict(given) || !pyTruthy(pyGet(given, "mutations"))) return ["输出里没有 mutation_spec（mutate --spec 的格式，至少一条变异），也没有 mutation_spec_file"];
  let problems = expectedMissedEverywhere(given);
  if (problems.length) return problems;
  const gatePost = dict(pyItem(ts, "gate_post"));
  const perMutant = mutantTimeout(given, pyGet(gatePost, "whitebox_seconds"));
  const spec: PyDict = perMutant ? new Map([...given, ["timeout_seconds", perMutant]]) : given;
  const runs = BigInt(pyLenValue(or(pyGet(spec, "commands"), [null]))) * BigInt(pyLenValue(pyItem(spec, "mutations")) + 1); // 每条命令先在候选上跑一遍基线
  const specPath = purePathStr(stageDir, `mutation-spec-${utcCompact()}.json`);
  writeText(specPath, `${dumps(spec, { ensureAscii: false, indent: 2 })}${LF}`, false);
  gatePost.set("mutate_spec", specPath);
  problems = unmutatedProblems(ts, spec, output);
  if (problems.length) return problems;
  // 先只核对锚点（不跑命令）：T003 的 M29 把全角括号写成了半角，跑完整个 mutate 才发现也白等了几分钟（第 12 轮）
  let [code, out] = await deps.runPd(hub, ["mutate", "--tree", purePathStr(workspace), "--spec", specPath, "--check-anchors"]);
  if (code !== 0) return [anchorProblem(hub, ts, spec, specPath, out)];
  gatePost.delete("anchor_mismatch");
  // 变异记录放在信箱的证据目录：终审能读主工作区（--add-dir），放系统临时目录它就读不到（T001 终审的意见）
  const outDir = purePathStr(stageDir, "evidence", `mutate-${utcCompact()}`);
  // 整份的时限按条数放宽：此前固定 3600 秒，几条变异卡到各自的时限，整份就判“没有跑完”
  const total = pyPlus(pyTimes(runs, or(pyGet(spec, "timeout_seconds"), MUTATION_DEFAULT_TIMEOUT)), 600n);
  const budget = pyLess(3600n, total) ? total : 3600n;
  [code, out] = await deps.runPd(hub, ["mutate", "--tree", purePathStr(workspace), "--spec", specPath, "--out", outDir], Number(budget));
  let record: PyValue;
  try {
    record = loads(readText(purePathStr(outDir, "mutations.json")) || "{}");
  } catch (error) {
    if (!isValueError(error)) throw error;
    record = new Map();
  }
  const mutations = pyIter(pyItem(spec, "mutations")).filter(isDict);
  const update: [string, PyValue][] = [
    ["mutate_exit", BigInt(code)], ["mutate_tail", tail(out, 25n)], ["mutant_timeout", pyGet(spec, "timeout_seconds")],
    ["mutate_record", relative(purePathStr(outDir, "mutations.json"), hub.repo)], ["mutation_counts", pyGet(record, "counts")],
    ["equivalent", mutations.filter((m) => pyTruthy(pyGet(m, "equivalent"))).map((m) => `${pyStrValue(pyGet(m, "name"))}：${pyStrValue(pyItem(m, "equivalent"))}`)],
    ["expect_missed", mutations.filter((m) => Array.isArray(pyGet(m, "expect_missed")))
      .map((m) => `${pyStrValue(pyGet(m, "name"))}：${(pyItem(m, "expect_missed") as PyValue[]).map(pyStrValue).join("、")}`)],
  ];
  for (const [name, value] of update) gatePost.set(name, value);
  return mutationProblems(code, record, out);
}

/** 锚点核对没过：记下对不上的条目（下一版一字没改就点名），把 --check-anchors 的结果交给门禁端。 */
function anchorProblem(hub: Hub, ts: PyDict, spec: PyDict, specPath: string, out: string): string {
  const listing = pySplitlines(out).filter((line) => pyStrip(line) && !line.startsWith("OK "));
  const failed = new Set([...out.matchAll(ANCHOR_FAILED_RE)].map((match) => pyIntParse(match[1] as string)));
  const numbered = pyIter(pyItem(spec, "mutations")).map((item, index) => [BigInt(index + 1), item] as const)
    .filter(([index, item]) => failed.has(index) && isDict(item));
  const names = new Set(numbered.map(([, item]) => pyStrValue(pyGet(item, "name"))));
  const unchanged = unchangedMismatches(ts, spec).filter((name) => names.has(name));
  dict(pyItem(ts, "gate_post")).set("anchor_mismatch", new Map(numbered.map(([, item]) => [pyStrValue(pyGet(item, "name")), pyGet(item, "old")])));
  const note = unchanged.length
    ? `这几条与上一版清单一字不差：上次就对不上，这次没有改：${unchanged.join("、")}。先在文件里改好、自己核对过锚点再交；`
      + `建议把清单写进 ${GATE_SPEC_FILE}，输出里只给 mutation_spec_file，不要再把清单抄进输出。`
    : "";
  return `${note}变异清单没有通过锚点核对，变异没有跑：每条 old 要在候选文件里逐字出现 count 次（缺省 1 次；`
    + `CRLF 先按 LF 比对），全角、半角标点与缩进都要照抄。清单存档在 ${relative(specPath, hub.repo)}；mutate --check-anchors 的结果`
    + `（不符的条目下列出文件里最相近的行）：${LF}${listing.slice(-40).join(LF)}`;
}

/** 第 118 轮：expect_missed 列满了每一条命令的变异，等于声明等价，却绕开了终审对 equivalent 的逐条复核。 */
export function expectedMissedEverywhere(spec: PyValue): string[] {
  const commands = pyGet(spec, "commands");
  // 单条 command 的清单，调度器把那条命令叫 main
  const ids = Array.isArray(commands) ? new PySet(commands.filter(isDict).map((c) => pyGet(c, "id"))) : new PySet(["main"]);
  const names = pyIter(or(pyGet(spec, "mutations"), [])).filter((m) => isDict(m) && Array.isArray(pyGet(m, "expect_missed"))
    && !ids.minus(new PySet(pyItem(m, "expect_missed") as PyValue[])).size).map((m) => pyStrValue(pyGet(m, "name")));
  if (!names.length) return [];
  return [`这几条变异的 expect_missed 列满了每一条命令，等于声明等价：${names.join("、")}。真是等价改写的，去掉 expect_missed、`
    + `改写 "equivalent": "<为什么改了行为也不变>"（终审会逐条复核）；不是的，至少留一条命令抓它`];
}

const DEFECT_KEYS = ["test", "contract", "where"] as const;

/** 门禁端举证的候选缺陷：每条写红的用例、合同原文与候选的位置。交回（缺陷, 问题）。 */
export function candidateDefects(output: PyValue): [PyDict[], string[]] {
  const items = pyGet(output, "candidate_defects");
  if (!pyTruthy(items)) return [[], []];
  if (!Array.isArray(items)) return [[], [`candidate_defects 要是列表：[{"test", "contract", "where"}]`]];
  const defects: PyDict[] = [];
  const problems: string[] = [];
  items.forEach((item, index) => {
    const entry: PyDict = isDict(item) ? new Map(DEFECT_KEYS.map((key) => [key, pyStrip(pyStrValue(or(pyGet(item, key), "")))])) : new Map();
    const missing = DEFECT_KEYS.filter((key) => !pyTruthy(entry.get(key) ?? null));
    if (missing.length) problems.push(`candidate_defects 第 ${index + 1} 条缺 ${missing.join("、")}`);
    else defects.push(entry);
  });
  return [defects, problems];
}

/** 用例可以写完整 node id、去掉文件的部分（Class::test_x[参数]）或函数名（覆盖它的全部参数）。 */
export function defectMatches(declared: string, nodeid: string): boolean {
  return declared === nodeid || nodeid.endsWith(`::${declared}`) || (nodeid.split("::").at(-1) as string).split("[")[0] === declared;
}

export function defectMatchProblems(defects: readonly PyDict[], failed: readonly string[]): string[] {
  const problems: string[] = [];
  const declared = defects.map((defect) => pyItem(defect, "test") as string);
  const undeclared = failed.filter((node) => !declared.some((test) => defectMatches(test, node)));
  if (undeclared.length) problems.push(`这些用例红了，candidate_defects 却没有列：${undeclared.slice(0, 10).join("、")}（白盒测试自己有错就改测试）`);
  const unshown = declared.filter((test) => !failed.some((node) => defectMatches(test, node)));
  if (unshown.length) problems.push(`candidate_defects 列的这些用例没有红：${unshown.slice(0, 10).join("、")}`);
  return problems;
}

/** item.get("commands") 里各条命令的结果，没有就是 {"": item.get("status")}。 */
function statuses(item: PyValue): PyDict {
  const runs = or(pyGet(item, "commands"), new Map());
  if (!isDict(runs)) throw new PyCrash("AttributeError", `'${pyTypeName(runs)}' object has no attribute 'items'`);
  const found: PyDict = new Map([...runs].map(([cid, run]) => [cid, pyGet(run, "status")]));
  return found.size ? found : new Map([["", pyGet(item, "status")]]);
}

/** statuses(r).get(cid, fallback)：cid 要能散列；键都是字符串。 */
function statusOf(found: PyDict, cid: PyValue, fallback: PyValue): PyValue {
  return inDict(cid, found) ? (found.get(cid as string) as PyValue) : fallback;
}

/** cid in r.get("unexpected") or []：列表比元素、字符串查子串、字典查键。 */
function unexpected(item: PyValue, cid: string): boolean {
  const container = or(pyGet(item, "unexpected"), []);
  if (Array.isArray(container)) return container.some((value) => pyEq([value], [cid]));
  if (typeof container === "string") return container.includes(cid);
  if (isDict(container)) return container.has(cid);
  throw new PyCrash("TypeError", `argument of type '${pyTypeName(container)}' is not iterable`);
}

/**
 * 判定变异检查。mutate --tree 的退出码只说明它跑完了：变异漏网时也是 0，所以读它写下的 mutations.json：意外漏网、没生效或出错的
 * 变异都不行，至少要抓住一条。
 */
export function mutationProblems(code: PyValue, record: PyValue, out: PyValue): string[] {
  const results = or(pyGet(record, "results"), []);
  if (!pyEq(code, 0n) || !pyTruthy(results)) {
    // 第 118 轮：T019 的门禁端看到基线红，把 bun install 塞进了 commands
    const hint = pyEq(pyGet(record, "aborted"), "baseline_failed")
      ? `${LF}基线就红了：不做变异时这条命令在你的工作目录里本来就跑不通（依赖没装、cwd 或路径不对）。交差前先在`
        + "回合里跑通；依赖照合同的 setup 在回合里装，不要放进 commands。"
      : "";
    return [`变异检查没有跑完（退出码 ${pyPercentD(code)}）：${LF}${tail(out, 25n)}${hint}`];
  }
  const rows = pyIter(results);
  const missedBy = (cid: string): string[] => rows.filter((r) => unexpected(r, cid) && pyEq(statusOf(statuses(r), cid, pyGet(r, "status")), "missed"))
    .map((r) => pyStrValue(pyGet(r, "id")));
  const problems: string[] = [];
  const missed = rows.filter((r) => pyIter(or(pyGet(r, "unexpected"), [])).some((cid) => pyEq(statusOf(statuses(r), cid, pyGet(r, "status")), "missed")))
    .map((r) => pyGet(r, "id"));
  const broken = rows.filter((r) => {
    const status = pyGet(r, "status");
    hashKey(status);
    const values = [...statuses(r).values()];
    values.forEach(hashKey);
    return [status, ...values].some((value) => value === "skipped" || value === "error");
  }).map((r) => pyGet(r, "id"));
  // 第 118 轮：多命令清单要按命令拆开说（T019：vitest 其实抓住了 24 条，信里只有“26 条漏网”）
  const ids = pyIter(or(pyGet(record, "commands"), [])).filter(isDict).map((c) => pyStrValue(pyGet(c, "id")));
  const multi = ids.length > 1;
  if (missed.length) {
    const detail = ids.filter((cid) => missedBy(cid).length).map((cid) => `${cid} 漏掉 ${missedBy(cid).join("、")}`).join("；");
    problems.push(`${missed.length} 条变异漏网、也没有声明等价：${missed.map(pyStrValue).join("、")}${multi && detail ? `（按命令：${detail}）` : ""}`);
  }
  const idle = ids.filter((cid) => multi && missedBy(cid).length && !rows.some((r) => pyEq(statusOf(statuses(r), cid, null), "caught")));
  if (idle.length) {
    problems.push(`命令 ${idle.join("、")} 一条变异都没抓住。commands 里每一条都是检验命令，每条变异缺省要被每一条抓住：`
      + "安装依赖这类准备步骤不要放进 commands（mutate 在你的工作目录里原地跑，依赖在你的回合里"
      + `装好就在）；某条命令本来就测不到的变异，在那一条变异里写 "expect_missed": ["<命令 id>"]`);
  }
  if (broken.length) problems.push(`${broken.length} 条变异没有生效或运行出错（skipped / error；old 片段要在文件里逐字出现）：${broken.map(pyStrValue).join("、")}`);
  if (!rows.some((r) => [...statuses(r).values()].some((value) => pyEq([value], ["caught"])))) problems.push("没有一条变异被抓住：变异检查什么也没证明");
  return problems;
}
