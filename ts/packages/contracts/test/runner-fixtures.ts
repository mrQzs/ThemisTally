// ⑤j 进程与锁的契约辅助：账本里进程自己的 pid 换成占位（themistally-04 定的比法，同 engine-fixtures.ts 的 crashNormalized 放在契约测试这边）；
// 另一个进程拿着的锁（⑤j1、⑤j2 的手写场景共用）。
import { type ChildProcess, spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { sleepSync } from "@themis/base/fsutil";
import { kernelPython } from "./flow-fixtures.ts";
import { REPO } from "./harness.ts";
import { put } from "./repo-fixtures.ts";

const LF = String.fromCharCode(10);

/** 另一个进程（真的 Python 子进程，kit_hub.DirLock）拿着 path 这把锁，直到被结束；mode 给了就照 supervise 写进锁目录。 */
export function holdLock(path: string, held: ChildProcess[], mode: string | null = null): void {
  const script = [
    "import sys, time", "sys.path.insert(0, sys.argv[1])", "import kit_hub", "from pathlib import Path",
    "kit_hub.DirLock(Path(sys.argv[2])).__enter__()", "time.sleep(600)",
  ].join(LF);
  held.push(spawn(kernelPython(), ["-c", script, join(REPO, "scripts"), path], { stdio: "ignore" }));
  for (let waited = 0; !existsSync(join(path, "owner.json")) && waited < 200; waited += 1) sleepSync(100);
  if (mode !== null) put(path, "mode", `${mode}${LF}`);
}

/**
 * 一次 ⑤j2 流程调用的结果：账本事件顶层的 pid 是 own 里的就换成 "<pid>"，账本新增的部分与 files 里写下的 events.jsonl 都换；探针交回的
 * self_pid 去掉不比；别的逐字。own 是进程自己的 pid：当时的结果只有采样那个进程的；重放的结果另加重放那个进程的（events.jsonl 前面几行是
 * 快照放回的，带的是采样那个进程的 pid）。runner.child_started 一类的 pid 是注入的子进程号，三边本来相同，照原样比。
 * 只改 pid 那一个键的文字、别的字节不动：整行重新序列化会抹掉 1.0 与 1 这类不同。
 */
export function pidNormalized(state: unknown, own: ReadonlySet<number>): unknown {
  if (typeof state !== "object" || state === null || !("ledger" in state)) return state;
  const { self_pid: _ignored, ...rest } = state as Record<string, unknown>;
  const files = rest["files"] as { write?: Record<string, string> } | undefined;
  const write = Object.fromEntries(Object.entries(files?.write ?? {})
    .map(([key, data]) => [key, key.endsWith("/ledger/events.jsonl") ? pidFree(data, own) : data]));
  return { ...rest, ledger: pidFree(rest["ledger"] as string, own), files: { ...files, write } };
}

/** 一份账本（base64）里顶层 pid 是 own 里的那几行，把 "pid": N 换成 "pid": "<pid>"；交回 base64。 */
function pidFree(data: string, own: ReadonlySet<number>): string {
  const lines = Buffer.from(data, "base64").toString("utf8").split(LF).map((line) => {
    if (!line) return line;
    const pid = (JSON.parse(line) as Record<string, unknown>)["pid"];
    if (typeof pid !== "number" || !own.has(pid)) return line;
    return line.split(`"pid": ${pid},`).join(`"pid": "<pid>",`).split(`"pid": ${pid}}`).join(`"pid": "<pid>"}`);
  });
  return Buffer.from(lines.join(LF), "utf8").toString("base64");
}
