// 契约探针（TS 实现）：stdin 读一个 JSON 请求，stdout 写一个 JSON 结果，与 python_probe.py 收发同样的 JSON。
// 同一份源码由 `node`（类型擦除）与 `bun` 各跑一遍。
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { attemptDirName, auditId, newMsgId, newTurnId, utcCompact, utcNow } from "@themis/base/clock";
import { UnicodeDecodeError, readText, sleepSync, writeTextAtomic } from "@themis/base/fsutil";
import { SAFE_MAX_LINE_BYTES, appendEvent, iterLines, jsonlRecords, linesBefore, readJsonl } from "@themis/base/jsonl";
import { ConfigLock, DirLock, LockBusyError, TaskLock } from "@themis/base/locks";
import { FileLockTimeout, acquireFileLock } from "@themis/base/native";
import { pidAlive } from "@themis/base/process";
import { publishNew } from "@themis/base/publish";
import {
  type AllowList,
  allowEnum,
  allowEnvName,
  allowId,
  decisionsRedact,
  isSensitive,
  looksLikeSecret,
  normalize,
  redactJson,
  redactObj,
  redactSecrets,
  redactState,
  redactTokens,
  secretLikePaths,
  tokenShaped,
} from "@themis/base/secrets";
import { type DumpsOptions, type PyDict, PyJsonError, dumps, encodeUtf8, loads, rawDecode, unitIndex } from "@themis/base/pyjson";
import { type Tagged, fromTagged, toTagged } from "../src/tagged.ts";

type Request = Record<string, unknown> & { op: string; barrier?: string };
type Result = Record<string, unknown>;

async function readStdin(): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of process.stdin) chunks.push(chunk as Buffer);
  return Buffer.concat(chunks).toString("utf8");
}

/** 并发用例：先报“就绪”，等测试建好起跑文件再一起动手。 */
function waitFor(barrier: string): void {
  process.stderr.write("ready\n");
  const pause = new Int32Array(new SharedArrayBuffer(4));
  while (!existsSync(barrier)) Atomics.wait(pause, 0, 0, 1);
}

/** 请求里的参数用 Python 的名字（ensure_ascii、sort_keys…），换成 TS 的。 */
function dumpsOptions(raw: unknown): DumpsOptions {
  const options = (raw ?? {}) as Record<string, unknown>;
  const out: { -readonly [K in keyof DumpsOptions]: DumpsOptions[K] } = {};
  if ("ensure_ascii" in options) out.ensureAscii = options["ensure_ascii"] as boolean;
  if ("indent" in options) out.indent = options["indent"] as number | null;
  if ("sort_keys" in options) out.sortKeys = options["sort_keys"] as boolean;
  if ("allow_nan" in options) out.allowNan = options["allow_nan"] as boolean;
  if (options["separators"] != null) out.separators = options["separators"] as [string, string];
  return out;
}

function textResult(text: string, encode: unknown): Result {
  return encode ? { ok: true, b64: Buffer.from(encodeUtf8(text)).toString("base64") } : { ok: true, text };
}

function allowList(raw: unknown): AllowList | undefined {
  const items = (raw ?? []) as { path: string[]; check: { kind: string; choices?: Tagged[] } }[];
  if (items.length === 0) return undefined;
  return items.map((item) => {
    const kind = item.check.kind;
    const check = kind === "env_name" ? allowEnvName : kind === "id" ? allowId : allowEnum(...(item.check.choices ?? []).map(fromTagged));
    return [item.path, check] as const;
  });
}

function secretsCall(request: Request): Result {
  const text = String(request["text"] ?? "");
  const value = "value" in request ? fromTagged(request["value"] as Tagged) : null;
  switch (request["fn"]) {
    case "redact_secrets":
      return { ok: true, text: redactSecrets(text) };
    case "redact_tokens":
      return { ok: true, text: redactTokens(text) };
    case "redact_obj":
      return { ok: true, value: toTagged(redactObj(value)) };
    case "redact_json":
      return { ok: true, value: toTagged(redactJson(value, allowList(request["allow"]))) };
    case "secret_like_paths":
      return { ok: true, paths: secretLikePaths(value) };
    case "token_shaped":
      return { ok: true, result: tokenShaped(text) };
    case "looks_like_secret":
      return { ok: true, result: looksLikeSecret(value) };
    case "normalize":
      return { ok: true, text: normalize(text) };
    case "is_sensitive":
      return { ok: true, result: isSensitive(text) };
    case "decisions_redact":
      return { ok: true, text: decisionsRedact(text, Number(request["limit"] ?? 4000)) };
    case "redact_state": {
      const [result, changed] = redactState(value, Number(request["limit"] ?? 6000));
      return { ok: true, value: toTagged(result), changed };
    }
    default:
      return { ok: false, error: "UNKNOWN_FN" };
  }
}

const OPS: Record<string, (request: Request) => Result | Promise<Result>> = {
  "secrets.call": secretsCall,
  "jsonl.append": async (request) => {
    const path = join(String(request["repo"]), ".agent", "mailbox", "ledger", "events.jsonl");
    const data = "data" in request ? (fromTagged(request["data"] as Tagged) as PyDict) : new Map();
    const count = Number(request["count"] ?? 1);
    for (let seq = 0; seq < count; seq += 1) {
      const extra: PyDict = new Map(data);
      if (count > 1) extra.set("seq", BigInt(seq));
      await appendEvent(path, String(request["event"]), extra);
    }
    return { ok: true, done_ms: Date.now() };
  },
  "jsonl.read": (request) => ({ ok: true, value: toTagged(readJsonl(String(request["path"]))) }),
  "jsonl.records": (request) => ({
    ok: true,
    records: [
      ...jsonlRecords(
        String(request["path"]),
        Number(request["start"]),
        Boolean(request["final"]),
        Number(request["limit"] ?? SAFE_MAX_LINE_BYTES),
      ),
    ].map(([start, end, raw]) => [start, end, raw === null ? null : raw.toString("base64")]),
  }),
  "jsonl.iter_lines": (request) => ({ ok: true, lines: [...iterLines(String(request["path"]))] }),
  "jsonl.lines_before": (request) => ({ ok: true, count: linesBefore(String(request["path"]), Number(request["position"])) }),
  "filelock.run": async (request) => {
    const path = String(request["path"]);
    let lock;
    try {
      lock = await acquireFileLock(path, Number(request["wait"] ?? 60));
    } catch (error) {
      if (error instanceof FileLockTimeout) return { ok: false, error: "timeout", message: error.message };
      throw error;
    }
    const acquired = Date.now();
    if (request["signal"]) process.stderr.write("ready\n");
    await new Promise((done) => setTimeout(done, Number(request["hold_ms"] ?? 0)));
    lock.assertHeld();
    const released = Date.now();
    await lock.release();
    return { ok: true, acquired_ms: acquired, released_ms: released };
  },
  publish_new: (request) => ({
    ok: true,
    published: publishNew(String(request["path"]), Buffer.from(String(request["data_b64"]), "base64")),
  }),
  "pyjson.dumps": (request) =>
    textResult(dumps(fromTagged(request["value"] as Tagged), dumpsOptions(request["options"])), request["encode"]),
  "pyjson.loads": (request) => ({ ok: true, value: toTagged(loads(String(request["text"]))) }),
  "pyjson.raw_decode": (request) => {
    const text = String(request["text"]);
    const decoded = rawDecode(text, unitIndex(text, Number(request["index"] ?? 0)));
    return { ok: true, value: toTagged(decoded.value), end: decoded.end };
  },
  "fs.read_text": (request) => ({ ok: true, text: readText(String(request["path"])) }),
  "fs.write_text_atomic": (request) => {
    writeTextAtomic(String(request["path"]), String(request["text"]));
    return { ok: true };
  },
  pid_alive: (request) => ({ ok: true, alive: pidAlive(request["pid"] as number | null) }),
  "lock.run": (request) => {
    const wait = Number(request["wait"] ?? 5);
    const lock =
      request["kind"] === "dir"
        ? new DirLock(String(request["path"]), wait)
        : request["kind"] === "task"
          ? new TaskLock(String(request["root"]), String(request["task"]), wait, Number(request["stale"] ?? 300))
          : new ConfigLock(String(request["root"]), wait);
    try {
      lock.acquire();
    } catch (error) {
      if (error instanceof LockBusyError) return { ok: false, error: "busy" };
      throw error;
    }
    const acquired = Date.now();
    const owner = readFileSync(join(lock.path, "owner.json"));
    sleepSync(Number(request["hold_ms"] ?? 0));
    if (request["tamper"]) writeFileSync(join(lock.path, "owner.json"), '{"pid": 1, "token": "someone-else"}\n');
    lock.release();
    return { ok: true, owner_b64: owner.toString("base64"), acquired_ms: acquired, released_ms: Date.now(), left: existsSync(lock.path) };
  },
  "clock.sample": (request) => {
    const senders = request["senders"] as string[];
    const out = {
      utc_now: [] as string[],
      pd_utc_now: [] as string[],
      utc_compact: [] as string[],
      turn_ids: [] as string[],
      audit_ids: [] as string[],
      msg_ids: Object.fromEntries(senders.map((sender) => [sender, [] as string[]])),
    };
    for (let index = 0; index < Number(request["count"] ?? 1); index += 1) {
      out.utc_now.push(utcNow());
      out.pd_utc_now.push(utcNow());
      out.utc_compact.push(utcCompact());
      out.turn_ids.push(newTurnId());
      out.audit_ids.push(auditId());
      for (const sender of senders) out.msg_ids[sender]?.push(newMsgId(sender));
    }
    return { ok: true, ...out, attempt_dirs: (request["attempts"] as number[]).map(attemptDirName) };
  },
  "pyjson.roundtrip": (request) =>
    textResult(dumps(loads(String(request["text"])), dumpsOptions(request["options"])), request["encode"]),
};

async function runOne(request: Request): Promise<Result> {
  if (request.barrier) waitFor(request.barrier);
  const handler = OPS[request.op];
  if (handler === undefined) return { ok: false, error: "UNKNOWN_OP" };
  try {
    return await handler(request);
  } catch (error) {
    if (error instanceof PyJsonError) {
      // pyjson 的报错文字是契约的一部分（Python 会经 str(exc) 写进输出）
      return request.op.startsWith("pyjson.") ? { ok: false, error: error.kind, message: error.message } : { ok: false, error: error.kind };
    }
    if (error instanceof UnicodeDecodeError) return { ok: false, error: "UnicodeDecodeError" };
    return { ok: false, error: (error as NodeJS.ErrnoException).code ?? "EUNKNOWN" };
  }
}

const request = JSON.parse(await readStdin()) as Request;
let result: Result;
if (request.op === "batch") {
  const results: Result[] = [];
  for (const item of request["items"] as Request[]) results.push(await runOne(item));
  result = { ok: true, results };
} else {
  result = await runOne(request);
}
process.stdout.write(JSON.stringify(result));
