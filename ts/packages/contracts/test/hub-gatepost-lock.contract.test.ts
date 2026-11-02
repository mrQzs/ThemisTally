// 第 ⑤f 片：add_worktree 等文件锁超时之后重试。kit_hub 的 file_lock 等满 60 秒报 HubError（EXIT_BLOCKED），add_worktree 与 git 失败一样
// 重试；TS 的 FileLockTimeout 照此转成 HubError。别的进程拿着 .git-worktrees.lock 约 70 秒：第一次等满 60 秒超时，等 1 秒再试，第二次
// 等到锁、建成 worktree。持锁的进程会挡住“先放回快照”（要整个删掉仓库），所以三边各搭一份同样的场景、不放快照、同时起跑；比较前把各自
// 场景的路径换成占位。不写转义序列。
import { basename, join } from "node:path";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { newTaskState } from "@themis/hub/taskstate";
import { afterAll, describe, expect, it } from "vitest";
import { toTagged } from "../src/tagged.ts";
import { IMPLS, PYTHON, startProbe } from "./harness.ts";
import { AT, LF, type Scene, flow, scene } from "./flow-fixtures.ts";
import { removeCreated, tempDir } from "./repo-fixtures.ts";

afterAll(removeCreated);

const BASE_FILES = { "src/doc.py": ["def title():", "    return 'old'", ""].join(LF) };
const LOCK = ".agent/mailbox/ledger/.git-worktrees.lock";

/** 字符串里的 from 都换成 to；base64 的几处（账本、新建改动的文件）先解开成文字再换。 */
function placeholders(value: unknown, pairs: readonly (readonly [string, string])[]): unknown {
  const swap = (text: string): string => pairs.reduce((acc, [from, to]) => acc.split(from).join(to).split(JSON.stringify(from).slice(1, -1)).join(to), text);
  const walk = (item: unknown): unknown => {
    if (typeof item === "string") return swap(item);
    if (Array.isArray(item)) return item.map(walk);
    if (item !== null && typeof item === "object") return Object.fromEntries(Object.entries(item).map(([key, child]) => [swap(key), walk(child)]));
    return item;
  };
  const state = value as Record<string, unknown>;
  const files = state["files"] as { write: Record<string, string>; delete: string[] };
  const decoded = Object.fromEntries(Object.entries(files.write).map(([key, data]) => [key, Buffer.from(data, "base64").toString("utf8")]));
  return walk({ ...state, ledger: Buffer.from(String(state["ledger"]), "base64").toString("utf8"), files: { ...files, write: decoded } });
}

describe("第 ⑤f 片：add_worktree 等文件锁超时之后重试", () => {
  it("别的进程拿着锁约 70 秒：三边都等满 60 秒、超时一次、再试时拿到锁建成；交回值、ts、文件、账本、git 状态（路径换成占位）相同", async () => {
    const runs = IMPLS.map((impl) => {
      const sc: Scene = scene(BASE_FILES, () => undefined, false);
      const root = tempDir("lock-root");
      const prefix = `${basename(sc.repo).slice(0, 16)}-hub-t001-post-attempt-001-`;
      const path = join(root, `${prefix}fixed123`);
      const none = { write: {}, delete: [] };
      const inner = [{ fn: "worktree_root", repo: sc.repo, value: toTagged(root), files: none }, { fn: "mkdtemp", prefix, dir: root, value: toTagged(path), files: none }];
      const ts: PyDict = newTaskState("T001", "doc", "改文档", sc.head, true, AT);
      const request = { ...flow("ensure_worktree", sc, [ts, "post-attempt-001", sc.head], { inner, replaced: ["worktree_root", "mkdtemp"], fresh: [path] }), restores: [] };
      return { impl, sc, root, request };
    });
    const holders = runs.map(({ sc }) => startProbe(PYTHON, {
      op: "hub.box", repo: sc.repo, steps: [["hold_file_lock", ...([LOCK, 70_000n, "released"] as PyValue[]).map((item) => toTagged(item))]],
    }));
    try {
      await Promise.all(holders.map((holder) => holder.ready));
      const started = Date.now();
      const tested = runs.map(({ impl, request }) => startProbe(impl, request));
      try {
        const results = await Promise.all(tested.map((probe) => probe.result));
        expect(results.map((result) => result.ok), JSON.stringify(results).slice(0, 3000)).toEqual(IMPLS.map(() => true));
        const seconds = (Date.now() - started) / 1000;
        const shown = results.map((result, at) => placeholders(result["value"], [[runs[at]?.root as string, "<ROOT>"], [runs[at]?.sc.repo as string, "<REPO>"],
          [runs[at]?.sc.head as string, "<HEAD>"]]));
        for (const [at, item] of shown.entries()) expect(item, runs[at]?.impl.name).toEqual(shown[0]);
        const first = shown[0] as Record<string, unknown>;
        expect([(first["result"] as Record<string, unknown>)["ok"], seconds >= 60]).toEqual([true, true]);
        expect(String(first["ledger"])).toContain("workspace.created");
      } finally {
        for (const probe of tested) probe.stop();
      }
    } finally {
      for (const holder of holders) holder.stop();
    }
  }, 300_000);
});
