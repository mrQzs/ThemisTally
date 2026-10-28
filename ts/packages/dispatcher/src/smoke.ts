// smoke（迁移第 ④b7d 片）：最小连通性试跑，会调用执行模型、产生费用。两步：先做无工具的一问一答，再在临时目录里写一个
// 文件并读回；两步都通过，才说明模型、凭据与工具调用可用。
//   - 契约只用 stub_pi（PI_DISPATCH_PI_CMD）；真跑 smoke 要站主在对话里明确要求。
//   - 都通过且没有 --keep 时删掉临时目录（删不掉不报错）；没通过时留着，路径在报告的 workspace 里。
import { existsSync, rmSync, writeFileSync } from "node:fs";
import { utcNow } from "@themis/base/clock";
import { type PyOut, pyGet } from "@themis/base/pyfmt";
import { pyReadText } from "@themis/base/pyio";
import { type PyDict, type PyValue, dumps } from "@themis/base/pyjson";
import { purePathStr } from "@themis/base/pypath";
import { codePoints, pyStrip } from "@themis/base/pyre";
import { pyGettempdir, pyMkdtemp } from "@themis/base/pytempfile";
import { redactObj, redactSecrets } from "@themis/base/secrets";
import { runSupervised } from "@themis/base/supervise";
import { ensureArgvSafe } from "./argv.ts";
import { supervisedRecord } from "./command-runner.ts";
import { MODEL_TOKEN_RE } from "./contract.ts";
import { summarizeEvents } from "./events.ts";
import { resolvePiCommand } from "./executor.ts";
import { safeOutputPath } from "./metrics.ts";
import { FALLBACK_THINKING_LEVELS, RESOURCE_FLAGS, childEnv, expectsSettled, runCapture } from "./pi-cli.ts";
import { DispatchError, EXIT_FAIL, EXIT_OK, EXIT_USAGE } from "./repo.ts";

const WIN = process.platform === "win32";
const LF = String.fromCharCode(10);
const CRLF = String.fromCharCode(13, 10);

const STEPS: readonly (readonly [string, readonly string[]])[] = [
  ["no_tools", ["--no-tools", "Reply with exactly PI_SMOKE_OK and nothing else."]],
  ["tools", ["--tools", "read,write", "Use the write tool to create a file named smoke.txt whose entire " +
    "content is PI_TOOL_OK. Then use the read tool to read it back. Finally reply with DONE."]],
];

export interface SmokeArgs {
  readonly repo: string | null;
  readonly provider: string;
  readonly model: string;
  readonly thinking: string;
  readonly timeout: bigint | number;
  readonly out: string | null;
  readonly keep: boolean;
}

/** cmd_smoke：两步都通过时退出码 0，否则 1；参数不合法是用法错误。 */
export async function cmdSmoke(args: SmokeArgs, out: PyOut): Promise<number> {
  const outPath = safeOutputPath(args.out, args.repo);
  const piCmd = resolvePiCommand();
  const executor: PyDict = new Map<string, PyValue>([["provider", args.provider], ["model", args.model], ["thinking", args.thinking]]);
  for (const field of ["provider", "model"] as const) {
    if (!MODEL_TOKEN_RE.test(args[field])) throw new DispatchError(`无效的 ${field}：${args[field]}`, EXIT_USAGE);
  }
  if (!FALLBACK_THINKING_LEVELS.includes(args.thinking)) throw new DispatchError(`无效的思考级别：${args.thinking}`, EXIT_USAGE);
  const versionText = (await runCapture([...piCmd, "--version"], { timeout: 60 }))[1];
  const settled = expectsSettled(versionText);
  const baseFlags = ["--provider", args.provider, "--model", args.model, "--thinking", args.thinking, "--no-session", ...RESOURCE_FLAGS,
    "--no-context-files", "--mode", "json"];
  const workspace = purePathStr(pyMkdtemp("pi-smoke-", pyGettempdir()));
  const [env] = childEnv(new Map());
  const steps: PyDict[] = [];
  const report: PyDict = new Map<string, PyValue>([
    ["at", utcNow()], ["executor", executor], ["pi_version", pyStrip(versionText)], ["workspace", workspace], ["steps", steps],
  ]);
  let allOk = true;
  for (const [name, extra] of STEPS) {
    const cmd = [...piCmd, ...baseFlags, ...extra];
    ensureArgvSafe(cmd);
    const eventsPath = purePathStr(workspace, `${name}.events.jsonl`);
    const stderrPath = purePathStr(workspace, `${name}.stderr.log`);
    const result = new Map(supervisedRecord(await runSupervised(cmd, {
      cwd: workspace,
      env: [...env],
      stdout: { path: eventsPath, how: "create-new" },
      stderr: { path: stderrPath, how: "create-new" },
      timeout: Number(args.timeout),
      grace: 15,
    })));
    const [summary, finalText] = summarizeEvents(eventsPath, workspace, executor, { stderrPath, expectsSettled: settled });
    const passed = stepPassed(name, workspace, summary, finalText);
    const ok = result.get("exit_code") === 0n && summary.get("ok") === true && passed;
    allOk = allOk && ok;
    steps.push(new Map<string, PyValue>([
      ["name", name], ["ok", ok], ["exit_code", result.get("exit_code") ?? null], ["spawn_error", result.get("spawn_error") ?? null],
      ["wall_seconds", result.get("wall_seconds") ?? null], ["timed_out", result.get("timed_out") ?? null],
      ["final_text", codePoints(redactSecrets(finalText)).slice(0, 500).join("")], ["problems", pyGet(summary, "problems")],
      ["actual_models", pyGet(summary, "actual_models")], ["provider_thinking_levels", pyGet(summary, "provider_thinking_levels")],
      ["thinking_evidence", pyGet(summary, "thinking_evidence")], ["usage", pyGet(summary, "usage")], ["cost", pyGet(summary, "cost")],
    ]));
    if (!ok) break;
  }
  report.set("ok", allOk);
  const text = dumps(redactObj(report), { ensureAscii: false, indent: 2 });
  if (outPath !== null) writeTextMode(outPath, text + LF);
  out.print(text);
  if (allOk && !args.keep) removeQuietly(workspace);
  return allOk ? EXIT_OK : EXIT_FAIL;
}

/** shutil.rmtree(ignore_errors=True)。 */
function removeQuietly(dir: string): void {
  try {
    rmSync(dir, { recursive: true, force: true });
  } catch {
    // 删不掉的留着
  }
}

/**
 * 每一步自己的判定：no_tools 的回复里有 PI_SMOKE_OK；tools 写出的 smoke.txt 内容是 PI_TOOL_OK、没有工具错误、write 与 read
 * 各至少调用一次。smoke.txt 照 Python 先读（读的时候不看前面是否已经失败）。
 */
function stepPassed(name: string, workspace: string, summary: PyDict, finalText: string): boolean {
  if (name === "no_tools") return finalText.includes("PI_SMOKE_OK");
  const smokeFile = purePathStr(workspace, "smoke.txt");
  const content = existsSync(smokeFile) ? pyStrip(pyReadText(smokeFile)) : null;
  const calls = (tool: string): bigint => pyGet(pyGet(summary, "tool_calls"), tool, 0n) as bigint;
  return content === "PI_TOOL_OK" && pyGet(summary, "tool_errors") === 0n && calls("write") >= 1n && calls("read") >= 1n;
}

/** Path.write_text(text, encoding="utf-8")：文本模式，Windows 上换行写成 CRLF。 */
function writeTextMode(file: string, text: string): void {
  writeFileSync(file, Buffer.from(WIN ? text.replaceAll(LF, CRLF) : text, "utf8"));
}
