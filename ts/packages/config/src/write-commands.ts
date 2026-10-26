// kit_config.py 的写命令（迁移第 ③b 片）：set、unset、init、decisions（含 marker）、rollback。都经写入事务；
// 带 --dry-run 或 --expect-state 的（目前只有 rollback）由 cli.ts 的 runInWriteMode 包一层。
import { existsSync, mkdirSync, statSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { type PyOut, pyReprValue } from "@themis/base/pyfmt";
import { PyJsonError, type PyDict, type PyValue, dumps, loads } from "@themis/base/pyjson";
import { pyReadText } from "@themis/base/pyio";
import { EXIT_OK, EXIT_USAGE } from "@themis/dispatcher/repo";
import { type ConfigArgs, discoverRepo } from "./commands.ts";
import { OFF_MARKER, joinPath, settingsFromConfig } from "./decisions.ts";
import { HISTORY_DIR, STATE_WORDS, contentNote, findEntry, historyEntries, snapshotBytes } from "./history.ts";
import { type WriteContext, withConfigTransaction } from "./transaction.ts";
import { ConfigError, KEYS, type Kit, configPath, parseObject, validateConfig } from "./validate.ts";

const EXAMPLE_NAME = "dispatch.config.example.json";

export interface WriteArgs extends ConfigArgs {
  readonly key?: string;
  readonly value?: string;
  readonly yes?: boolean;
  readonly what?: string;
  readonly state?: string | null;
}

const json = (value: PyValue): string => dumps(value, { ensureAscii: false });

/** 写命令的运行环境：仓库来自 --repo，kit 与等锁的秒数来自 context。 */
export function writeContext(args: WriteArgs, kit: Kit, lockWaitSeconds: number, out: PyOut): WriteContext {
  const repo = discoverRepo(args.repo);
  return { repo, kit, lockWaitSeconds, out };
}

/** kit_config.split_path：键或键.子键，只在第一个点处分开（子键可以含点）。 */
function splitPath(keyPath: string): string[] {
  const dot = keyPath.indexOf(".");
  const parts = dot < 0 ? [keyPath] : [keyPath.slice(0, dot), keyPath.slice(dot + 1)];
  if (parts.some((part) => !part) || !KEYS.has(parts[0] as string)) {
    throw new ConfigError(`键路径必须是已知键，最多两层（例如 decisions.mode）：${pyReprValue(keyPath)}；已知键：${[...KEYS.keys()].join(", ")}`, EXIT_USAGE);
  }
  return parts;
}

/** kit_config.parse_value：先按 JSON 解析，解析不了按字符串（嵌套太深的 RecursionError 照抛）。 */
function parseValue(text: string): PyValue {
  try {
    return loads(text);
  } catch (error) {
    if (error instanceof PyJsonError && error.kind !== "RecursionError") return text;
    throw error;
  }
}

export function cmdSet(ctx: WriteContext, args: WriteArgs): number {
  const key = args.key as string;
  const parts = splitPath(key);
  const value = parseValue(args.value as string);
  const changed = withConfigTransaction(ctx, "config.set", key, { confirm: Boolean(args.yes) }, (txn) => {
    const config = txn.config;
    if (parts.length === 1) {
      config.set(parts[0] as string, value);
    } else {
      let section = config.get(parts[0] as string) ?? null;
      if (section === null) {
        section = new Map();
        config.set(parts[0] as string, section);
      }
      if (!(section instanceof Map)) throw new ConfigError(`${parts[0] as string} 不是对象，不能设置 ${key}`);
      section.set(parts[1] as string, value);
    }
    return txn.publish(config);
  });
  ctx.out.print(`${changed ? "已写入" : "没有变化"} ${configPath(ctx.repo)}：${key} = ${json(value)}`);
  return EXIT_OK;
}

export function cmdUnset(ctx: WriteContext, args: WriteArgs): number {
  const key = args.key as string;
  const parts = splitPath(key);
  withConfigTransaction(ctx, "config.unset", key, { confirm: Boolean(args.yes) }, (txn) => {
    const config = txn.config;
    if (parts.length === 1) {
      if (!config.has(parts[0] as string)) throw new ConfigError(`${key} 本来就没有设置`);
      config.delete(parts[0] as string);
    } else {
      const section = config.get(parts[0] as string);
      if (!(section instanceof Map) || !section.has(parts[1] as string)) throw new ConfigError(`${key} 本来就没有设置`);
      section.delete(parts[1] as string);
      if (!section.size) config.delete(parts[0] as string);
    }
    txn.publish(config);
  });
  ctx.out.print(`已删除 ${key}（${configPath(ctx.repo)}）`);
  return EXIT_OK;
}

export function cmdInit(ctx: WriteContext): number {
  const target = configPath(ctx.repo);
  const example = joinPath(ctx.kit.kitRoot, ".agent", EXAMPLE_NAME);
  withConfigTransaction(ctx, "config.init", null, {}, (txn) => {
    if (txn.before !== null) throw new ConfigError(`已存在：${target}（用 set 修改，或先删除它）`);
    if (!isFile(example)) throw new ConfigError(`kit 里没有 ${example}`);
    const config = loads(pyReadText(example)) as PyDict;
    const errors = validateConfig(config, ctx.repo, ctx.kit);
    if (errors.length) throw new ConfigError(`示例配置在本仓库上无效：${errors.join("；")}`);
    txn.publish(config);
  });
  ctx.out.print(`已生成 ${target}（来自 kit 的 ${EXAMPLE_NAME}）；用 show 查看、set 修改`);
  return EXIT_OK;
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

export function cmdDecisions(ctx: WriteContext, args: WriteArgs): number {
  if (args.what === "marker") {
    const marker = joinPath(ctx.repo.agentDir, OFF_MARKER);
    if (args.state === "on") {
      mkdirSync(dirname(marker), { recursive: true });
      // Path.write_text 用文本模式：Windows 上 \n 写成 \r\n
      writeFileSync(marker, process.platform === "win32" ? "decisions are off while this file exists\r\n" : "decisions are off while this file exists\n");
      ctx.out.print(`已创建 ${marker}：决策功能一票否决为 off`);
    } else if (existsSync(marker)) {
      unlinkSync(marker);
      ctx.out.print(`已删除 ${marker}：决策功能按配置生效`);
    } else {
      ctx.out.print(`${marker} 本来就不存在`);
    }
    return EXIT_OK;
  }
  const config = withConfigTransaction(ctx, "config.decisions", "decisions.mode", {}, (txn) => {
    const whole = txn.config;
    let section = whole.get("decisions") ?? null;
    if (section === null) {
      section = new Map();
      whole.set("decisions", section);
    }
    if (!(section instanceof Map)) throw new ConfigError("decisions 不是对象");
    section.set("mode", args.what as string);
    txn.publish(whole);
    return whole;
  });
  const settings = settingsFromConfig(config, ctx.repo.agentDir, ctx.kit.decisionsDir);
  ctx.out.print(`已写入 decisions.mode = ${args.what as string}；实际生效 ${settings.mode}（${settings.reason}）`);
  return EXIT_OK;
}

/** 回到某条已发布写入之后的配置：原样写回那份快照的字节，本身也是一个新的事务（action config.rollback）。 */
export function cmdRollback(ctx: WriteContext, args: WriteArgs): number {
  const number = BigInt(args.number ?? 0);
  const changed = withConfigTransaction(ctx, "config.rollback", String(number), { confirm: Boolean(args.yes) }, (txn) => {
    const entry = findEntry(historyEntries(ctx.repo).entries, number);
    if (entry.resource !== "config") throw new ConfigError(`第 ${number} 条是本机文件的写入：rollback 只接受配置文件的记录`, EXIT_USAGE);
    if (entry.state !== "published") {
      throw new ConfigError(`第 ${number} 条没有发布（${STATE_WORDS.get(entry.state) ?? String(entry.state)}），不能回滚到它`, EXIT_USAGE);
    }
    const data = snapshotBytes(ctx.repo, entry.afterRef);
    if (data === null) {
      throw new ConfigError(`第 ${number} 条的快照没有存内容或已缺失（${contentNote("config", entry.afterRef, ctx.repo) ?? "快照文件缺失"}），不能回滚`);
    }
    const sha = (entry.afterRef as PyDict).get("sha256") as string;
    const target = parseObject(joinPath(ctx.repo.agentDir, HISTORY_DIR, `${sha}.json`), data);
    return txn.publish(target, data);
  });
  ctx.out.print(`${changed ? "已回滚" : "没有变化"}：${configPath(ctx.repo)} 回到第 ${number} 条之后的内容`);
  return EXIT_OK;
}
