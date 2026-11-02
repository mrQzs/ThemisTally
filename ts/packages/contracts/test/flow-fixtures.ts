// 照调用当时重放的契约（⑤e2b 的 hub-contract-flow、⑤f 的 hub-gatepost）共用的手写场景工具：搭场景（仓库与仓库外的 worktree，
// 带 .git 原样拷一份当快照），拼 hub.contract_flow 的请求与手写的注入记录，三边逐个比。不写转义序列。
import { cpSync } from "node:fs";
import { join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { expect } from "vitest";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";
import { copyTreeTimes } from "../src/tree-times.ts";
import { IMPLS, PYTHON, type ProbeRequest, type ProbeResult, runBatch, runProbe } from "./harness.ts";
import { git, newRepo, tempDir } from "./repo-fixtures.ts";

export const C = (...codes: number[]): string => String.fromCodePoint(...codes);
export const LF = C(10);
export const CR = C(13);
export const BT = C(96);
/** 2026-11-01T00:00:00Z 的 Unix 微秒数：手写场景都钉在这一刻。 */
export const PIN = Date.UTC(2026, 10, 1) * 1000;
export const AT = "2026-11-01T00:00:00Z";

/** pytest 的用时（行尾的“ in 0.12s”，满 60 秒时后面多一段“ (0:01:02)”）：只在比较这一步换成占位。 */
export const DURATION = new RegExp(" in [0-9]+[.][0-9]{2}s(?: [(][0-9]+:[0-9]{2}:[0-9]{2}[)])?$", "gm");
export function scrub(value: unknown): unknown {
  if (typeof value === "string") return value.replace(DURATION, " in <DURATION>");
  if (Array.isArray(value)) return value.map(scrub);
  if (value !== null && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, scrub(item)]));
  return value;
}
/** 只给交回值打用时的占位：ts、文件、账本、git 状态照样逐字比，用时漏进去时测试直接红（themistally-15 复核 ⑤e2b 时定）。 */
export function scrubResult(state: unknown): unknown {
  if (state === null || typeof state !== "object" || !("result" in state)) return state;
  const record = state as Record<string, unknown>;
  return { ...record, result: scrub(record["result"]) };
}

let kernelPythonPath: string | null = null;
export function kernelPython(): string {
  kernelPythonPath ??= (fromTagged(runProbe(PYTHON, { op: "hub.contract", fn: "kernel_pytest", args: [] })["value"] as Tagged) as string[])[0] as string;
  return kernelPythonPath;
}

export function py(value: unknown): PyValue {
  if (value === null || typeof value === "string" || typeof value === "boolean" || typeof value === "bigint") return value;
  if (typeof value === "number") return Number.isInteger(value) ? BigInt(value) : value;
  if (Array.isArray(value)) return value.map(py);
  if (value instanceof Map) return value as PyDict;
  return new Map(Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, py(item)]));
}

export interface Scene {
  readonly repo: string;
  readonly wt: string;
  readonly head: string;
  readonly restores: unknown[];
  readonly roots: string[];
}

/** 一个场景：仓库提交了 files，prepare 在提交之后写别的（合同、worktree 里的文件）；搭在原处，再带 .git 原样拷一份当快照。 */
export function scene(files: Record<string, string>, prepare: (repo: string, wt: string, head: string) => void = () => undefined, worktree = true): Scene {
  const { repo, head } = newRepo("flow-scene", files);
  const wt = join(tempDir("flow-wt"), "wt");
  if (worktree) git(repo, "worktree", "add", "-q", "--detach", wt, head);
  prepare(repo, wt, head);
  const tpl = tempDir("flow-tpl");
  cpSync(repo, join(tpl, "repo"), { recursive: true, preserveTimestamps: true });
  copyTreeTimes(repo, join(tpl, "repo")); // ⑤g：修改时刻也是场景的一部分（kit_hub 有两处拿它跟记录比）
  const restores: unknown[] = [{ from: join(tpl, "repo"), to: repo, links: [], git: true }];
  if (worktree) {
    cpSync(wt, join(tpl, "wt"), { recursive: true, preserveTimestamps: true });
    copyTreeTimes(wt, join(tpl, "wt"));
    restores.push({ from: join(tpl, "wt"), to: wt, links: [], git: true });
  }
  return { repo, wt, head, restores, roots: worktree ? [repo, wt] : [repo] };
}

export interface Extra {
  readonly inner?: unknown[];
  readonly replaced?: string[];
  readonly env?: Record<string, string>;
  /** ⑤f：调用之后才有的树（mkdtemp 建的 worktree），比较时排在 sc.roots 之后；重放前先删掉。 */
  readonly fresh?: string[];
}
export const flow = (fn: string, sc: Scene, args: unknown[], extra: Extra = {}): ProbeRequest => ({
  op: "hub.contract_flow", fn, args: [sc.repo, ...args].map((arg) => toTagged(py(arg))), restores: sc.restores, roots: [...sc.roots, ...(extra.fresh ?? [])],
  fresh: extra.fresh ?? [], pin: PIN, replaced: extra.replaced ?? (extra.inner ? ["run_pd"] : []), inner: extra.inner ?? [], python: kernelPython(), env: extra.env ?? {},
});
/** 手写的一次 run_pd：argv、timeout（没给是 null）、交回值，调用期间写的文件（“树的序号/相对路径”: 文字）。 */
export const pd = (argv: string[], code: number, out: string, timeout: number | null = null, write: Record<string, string> = {}, remove: string[] = []): unknown => ({
  fn: "run_pd", argv, timeout, value: toTagged([BigInt(code), out]),
  files: { write: Object.fromEntries(Object.entries(write).map(([key, text]) => [key, Buffer.from(text, "utf8").toString("base64")])), delete: remove },
});

/**
 * 三边各跑一遍、逐个比（pytest 的用时换成占位；normalize 给真跑的场景换掉钉不住的证据）；交回 Python 那边的结果（解开的 value）。
 */
export function agreeFlow(requests: readonly ProbeRequest[], normalize: (state: Record<string, unknown>) => unknown = (state) => state): Record<string, unknown>[] {
  const shown = (result: ProbeResult | undefined): unknown => {
    const value = result?.["value"] as Record<string, unknown> | undefined;
    // 注入核对出错时的 detail 两边各用自己的 JSON 写法，只比错误类型
    const result_ = value?.["result"] as Record<string, unknown> | undefined;
    const plain = value && result_ && "detail" in result_ ? { ...value, result: { ...result_, detail: "<DETAIL>" } } : value;
    return scrubResult(plain ? normalize(plain) : result);
  };
  const [python, ...others] = IMPLS.map((impl) => runBatch(impl, requests));
  for (const [index, other] of others.entries()) {
    const bad = requests.map((_, at) => at).filter((at) => JSON.stringify(shown(python?.[at])) !== JSON.stringify(shown(other[at])));
    const detail = bad.slice(0, 2).map((at) => ({ at, fn: requests[at]?.["fn"], python: shown(python?.[at]), other: shown(other[at]) }));
    expect(JSON.stringify(detail).slice(0, 6000), `${IMPLS[index + 1]?.name} 与 Python 不同（共 ${bad.length} 处）`).toBe("[]");
  }
  return (python ?? []).map((result) => result["value"] as Record<string, unknown>);
}
export const returned = (state: Record<string, unknown> | undefined): PyValue => {
  const result = state?.["result"] as Record<string, unknown>;
  return result["ok"] ? fromTagged(result["value"] as Tagged) : (result["error"] as string);
};
export const tsAfter = (state: Record<string, unknown> | undefined): PyDict => fromTagged(state?.["ts"] as Tagged) as PyDict;
export const written = (state: Record<string, unknown> | undefined): Record<string, string> => (state?.["files"] as { write: Record<string, string> }).write;
export const text = (state: Record<string, unknown> | undefined, key: string): string => Buffer.from(written(state)[key] as string, "base64").toString("utf8");
