// codekit/decisions.py 的客户端一半（迁移第 ④b4a 片）：HTTP 传输（迁移计划 D4）、回答校验、会话（时钟预算、重试一次、
// 记录）、用量合计、doctor 的事实与探测，以及 pi_dispatch 的 decisions_session。
//
// 传输用 node:http、node:https 而不用 fetch：Bun 的 fetch 会走 HTTP_PROXY（连 127.0.0.1 都走），http.client 不走代理；
// 证书用系统证书库（tls.getCACertificates("system")，去重后与 Python 的缺省上下文是同一组）；请求头的次序与写法照
// http.client，线上字节与 Python 逐字节相同；不跟随重定向；超时按每次 socket 操作算（空闲超时）。
// 调度器（dispatcher 包）不能 import 本包：命令经 cli 拿到会话（④b4b）。
import { appendFileSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
import http from "node:http";
import https from "node:https";
import { isIP } from "node:net";
import tls from "node:tls";
import { domainToASCII } from "node:url";
import { utcNow } from "@themis/base/clock";
import { PyCrash, type PyOut, pyFloatOf, pyRepr, pyReprValue, pyRound, pyStrValue, pySum, pyTruthy, pyTypeName } from "@themis/base/pyfmt";
import { pyDecodeUtf8Replace } from "@themis/base/pyio";
import { type PyDict, PyJsonError, type PyValue, dumps, encodeUtf8, floatRepr, loadsBytes } from "@themis/base/pyjson";
import { pathMkdir } from "@themis/base/pyos";
import { cmpCodePoints, codePoints, isDigitChar, pyIntParse, pyLen } from "@themis/base/pyre";
import { decisionsRedact, isSensitive, redactState } from "@themis/base/secrets";
import { urlHostname, urlPort, urlsplit } from "@themis/base/pyurl";
import { DispatchError, EXIT_USAGE } from "@themis/dispatcher/repo";
// usage_totals 在 dispatcher（decisions replay 要用，dispatcher 不能 import 本包），这里照旧转出
export { usageTotals } from "@themis/dispatcher/decision-records";
import {
  type Battery, DecisionError, batteryLinkProblem, checkQuestion, joinPath, loadBatteries, loadLockedBatteries, settingsActive,
  settingsFromConfig, settingsOfficial, type Settings, verifyBatteryLock,
} from "./decisions.ts";
import { secretConfigError } from "./secret-config.ts";
import { SecretError, resolve, source, storeMode } from "./secret-store.ts";

export const ENDPOINT_PATH = "/v1/systemone";
export const MAX_RESPONSE_BYTES = 1_000_000;
export const USER_AGENT = "code-kit-decisions/2.8.0";
const RETRYABLE = new Set(["rate_limited", "overloaded", "network", "http_500", "http_502", "http_503", "http_504"]);
const PROBABILITY_SUM_TOLERANCE = 0.01 + 1e-12;
const SCORE_MEAN_TOLERANCE = 0.02 + 1e-12;
const ARGMAX_TOLERANCE = 1e-9;
const LF = String.fromCharCode(10);

const dict = (entries: readonly (readonly [string, PyValue])[]): PyDict => new Map(entries);

/** 官方 Python SDK（typesafe-sdk）的常量，只作对照（doctor 原样列出）。 */
const SDK_REFERENCE = (): PyDict => dict([
  ["package", "typesafe-sdk"], ["python", ">=3.10"], ["api_key_env", "TYPESAFE_API_KEY"],
  ["base_url_env", "TYPESAFE_BASE_URL"], ["default_model_env", "TYPESAFE_DEFAULT_MODEL"],
  ["default_model", "jev-latest"], ["default_timeout_seconds", 10.0],
  ["retry", dict([["max_retries", 2n], ["budget_seconds", 30.0], ["statuses", "408, 429, 500-599"],
    ["backoff", "0.5s doubled to 5s, jitter 0.25, honours Retry-After"]])],
]);

const isDict = (value: PyValue | undefined): value is PyDict => value instanceof Map;
const isNumber = (value: PyValue | undefined): value is bigint | number => typeof value === "bigint" || typeof value === "number";
const firstPoints = (text: string, count: number): string => codePoints(text).slice(0, count).join("");
const sleep = (seconds: number): Promise<void> => new Promise((done) => setTimeout(done, seconds * 1000));

// ---------------------------------------------------------------------------
// 传输
// ---------------------------------------------------------------------------

/** 一次 POST：(请求体, 按次序的请求头, 每次 socket 操作的超时秒数, URL) → 回复正文；失败抛 DecisionError。 */
export type Transport = (body: Buffer, headers: readonly (readonly [string, string])[], timeout: number, url: string) => Promise<Buffer>;

let systemCa: string[] | undefined;

/** http.client 的 Host 头：缺省端口不写端口，IPv6 加方括号，非 ASCII 的主机名走 idna。 */
function hostHeader(host: string, port: number, defaultPort: number): string {
  const ascii = codePoints(host).every((char) => (char.codePointAt(0) ?? 0) < 0x80);
  let encoded = ascii ? host : domainToASCII(host);
  if (host.includes(":")) encoded = `[${encoded}]`;
  return port === defaultPort ? encoded : `${encoded}:${port}`;
}

/** 证书校验失败（Python 的 ssl.SSLCertVerificationError）的 OpenSSL 错误码。 */
const CERT_VERIFY_CODES = new Set([
  "DEPTH_ZERO_SELF_SIGNED_CERT", "SELF_SIGNED_CERT_IN_CHAIN", "UNABLE_TO_VERIFY_LEAF_SIGNATURE", "UNABLE_TO_GET_ISSUER_CERT",
  "UNABLE_TO_GET_ISSUER_CERT_LOCALLY", "CERT_HAS_EXPIRED", "CERT_NOT_YET_VALID", "CERT_UNTRUSTED", "CERT_REJECTED", "CERT_REVOKED",
  "CERT_SIGNATURE_FAILURE", "INVALID_CA", "PATH_LENGTH_EXCEEDED", "INVALID_PURPOSE", "ERR_TLS_CERT_ALTNAME_INVALID",
]);

/** Node 的网络错误码 → http.client 抛的异常类名（DecisionError("network", 类名)）。 */
const NETWORK_CLASSES: Readonly<Record<string, string>> = {
  ECONNREFUSED: "ConnectionRefusedError", ECONNRESET: "ConnectionResetError", ECONNABORTED: "ConnectionAbortedError",
  EPIPE: "BrokenPipeError", ENOTFOUND: "gaierror", EAI_AGAIN: "gaierror", EAI_FAIL: "gaierror", EAI_NONAME: "gaierror",
};

/** http.client 的 _MAXLINE、_MAXHEADERS。 */
const MAX_LINE = 65536;
const MAX_HEADERS = 100;

/**
 * http.client 读头时的两个上限，按行的次序查：一行（含 CRLF）超过 65536 是 LineTooLong，第 101 行是 HTTPException——结尾的
 * 空行也先计数再判断，所以最多 99 个头。行长按“名: 值”加 CRLF 算（服务端在冒号后多写的空白算不进来）。
 */
function headerLimit(raw: readonly string[]): string | null {
  for (let index = 0; index < raw.length; index += 2) {
    if ((raw[index] as string).length + (raw[index + 1] as string).length + 4 > MAX_LINE) return "LineTooLong";
    if (index / 2 + 1 > MAX_HEADERS) return "HTTPException";
  }
  return raw.length / 2 + 1 > MAX_HEADERS ? "HTTPException" : null;
}

/** CPython 3.12.10 的 ssl 在握手超时时的文字（带 _ssl.c 的行号，随 CPython 的构建变）。 */
const HANDSHAKE_TIMEOUT = "_ssl.c:993: The handshake operation timed out";

function networkError(error: NodeJS.ErrnoException): DecisionError {
  const code = error.code ?? "";
  if (CERT_VERIFY_CODES.has(code)) return new DecisionError("network", "SSLCertVerificationError");
  if (code === "ECONNRESET" && error.message === "socket hang up") return new DecisionError("network", "RemoteDisconnected");
  if (code in NETWORK_CLASSES) return new DecisionError("network", NETWORK_CLASSES[code] as string);
  if (code.startsWith("ERR_SSL_") || code === "EPROTO") return new DecisionError("network", "SSLError");
  if (code.startsWith("HPE_")) return new DecisionError("network", code === "HPE_HEADER_OVERFLOW" ? "LineTooLong" : "BadStatusLine");
  return new DecisionError("network", "OSError");
}

/**
 * http_transport：一个 POST，不跟随重定向（重定向会把凭据带去别的主机），状态码映射成原因码。正文读到 MAX+1 字节为止；
 * Content-Length 没收满就断开时照 http.client 返回已收到的部分（read(amt) 不报 IncompleteRead），分块编码断开才报。
 * 超时自己计：Bun 的 node:https 在 TLS 握手阶段不发 timeout 事件。http.client 按每次 socket 操作计时：连接一个期限，
 * TLS 握手整段一个期限，之后每次 recv 一个期限（头部慢慢滴也不会超时）；这里在连上、握手完成、之后 socket 每收到一次数据
 * 时重新计时。到时的文字照 Python 分阶段（明文与连接阶段 timed out，握手、读各自的）。
 */
export const httpTransport: Transport = (body, headers, timeout, url) => {
  const parsed = urlsplit(url);
  const secure = parsed.scheme === "https";
  const hostname = urlHostname(parsed) ?? "";
  const defaultPort = secure ? 443 : 80;
  const port = urlPort(parsed) ?? defaultPort;
  const raw = new Promise<[number, Buffer]>((resolveRaw, rejectRaw) => {
    let settled = false;
    let connected = false;
    let handshaken = false;
    let socketError: NodeJS.ErrnoException | null = null;
    let timer: NodeJS.Timeout | undefined;
    const settle = (outcome: [number, Buffer] | DecisionError): void => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (outcome instanceof DecisionError) rejectRaw(outcome);
      else resolveRaw(outcome);
    };
    const options: https.RequestOptions = {
      // agent: false 每个请求一条连接、不复用：下面的宽松解析在复用的连接上可能把剩下的字节认成下一个回复，别改
      host: hostname, port, path: parsed.path || "/", method: "POST", setHost: false, agent: false,
      // http.client 照收的回复 llhttp 缺省会拒：头部合计超过 16 KB、只用 LF 换行。行长与头数的上限照 Python 自己查（见下）
      maxHeaderSize: MAX_HEADERS * (MAX_LINE + 1), insecureHTTPParser: true,
    };
    if (secure) {
      systemCa ??= (tls as unknown as { getCACertificates(kind: string): string[] }).getCACertificates("system");
      options.ca = systemCa;
      if (isIP(hostname) === 0) options.servername = hostname;
    }
    const request = (secure ? https : http).request(options);
    const arm = (): void => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        settle(new DecisionError("timeout", !secure || !connected ? "timed out" : handshaken ? "The read operation timed out" : HANDSHAKE_TIMEOUT));
        request.destroy();
      }, timeout * 1000);
    };
    arm();
    request.setHeader("Host", hostHeader(hostname, port, defaultPort));
    request.setHeader("Accept-Encoding", "identity");
    request.setHeader("Content-Length", String(body.length));
    for (const [name, value] of headers) request.setHeader(name, value);
    request.removeHeader("Connection");
    request.on("socket", (socket) => {
      socket.on("connect", () => {
        connected = true;
        arm();
      });
      socket.on("secureConnect", () => {
        handshaken = true;
        arm();
      });
      socket.on("data", () => {
        if (secure ? handshaken : connected) arm();
      });
      socket.on("error", (error: NodeJS.ErrnoException) => (socketError ??= error));
    });
    request.on("error", (error: NodeJS.ErrnoException) => settle(networkError(error)));
    request.on("response", (response) => {
      arm();
      const limit = headerLimit(response.rawHeaders);
      if (limit !== null) {
        settle(new DecisionError("network", limit));
        response.destroy();
        return;
      }
      const chunks: Buffer[] = [];
      let size = 0;
      const finish = (): void => settle([response.statusCode ?? 0, Buffer.concat(chunks).subarray(0, MAX_RESPONSE_BYTES + 1)]);
      response.on("data", (chunk: Buffer) => {
        arm();
        chunks.push(chunk);
        size += chunk.length;
        if (size > MAX_RESPONSE_BYTES) {
          finish();
          response.destroy();
        }
      });
      response.on("end", finish);
      response.on("aborted", () => {
        if (socketError?.code === "ECONNRESET") settle(networkError(socketError));
        else if (/chunked/iu.test(String(response.headers["transfer-encoding"] ?? ""))) settle(new DecisionError("network", "IncompleteRead"));
        else finish();
      });
      response.on("error", () => undefined);
    });
    request.end(body);
  });
  return raw.then(([status, data]) => {
    if (data.length > MAX_RESPONSE_BYTES) throw new DecisionError("response_too_large");
    if (status !== 200) {
      const named: Readonly<Record<number, string>> = { 401: "auth_failed", 403: "auth_failed", 402: "credits_exhausted", 422: "invalid_request", 429: "rate_limited", 529: "overloaded" };
      throw new DecisionError(named[status] ?? `http_${status}`, status === 422 ? decisionsRedact(pyDecodeUtf8Replace(data), 300) : "");
    }
    return data;
  });
};

// ---------------------------------------------------------------------------
// 回复校验
// ---------------------------------------------------------------------------

function invalid(name: string, invariant: string, detail = ""): DecisionError {
  return new DecisionError("invalid_response", `answer ${name} violated ${invariant}${detail ? ` (${detail})` : ""}`);
}

/** _unit：0..1 的数（容 1e-6），夹到 [0, 1]；布尔不算数。 */
function unit(value: PyValue | undefined, name: string): number {
  if (!isNumber(value)) throw new DecisionError("malformed", `${name} is not numeric`);
  const number = pyFloatOf(value);
  if (!Number.isFinite(number) || !(-1e-6 <= number && number <= 1 + 1e-6)) throw new DecisionError("malformed", `${name} is outside 0..1`);
  return Math.min(1.0, Math.max(0.0, number));
}

const reprList = (items: Iterable<string>): string => {
  const sorted = [...items].sort(cmpCodePoints);
  return sorted.length ? pyReprValue(sorted) : "none";
};

function distribution(name: string, raw: PyValue | undefined, keys: readonly string[], invariant: string): Map<string, number> {
  if (!isDict(raw)) throw invalid(name, invariant, "probabilities are not an object");
  const expected = new Set(keys);
  const found = new Set([...raw.keys()] as string[]);
  if (found.size !== expected.size || [...found].some((key) => !expected.has(key))) {
    throw invalid(name, invariant, `missing ${reprList([...expected].filter((key) => !found.has(key)))}, unexpected ${reprList([...found].filter((key) => !expected.has(key)))}`);
  }
  const values = new Map(keys.map((key) => [key, unit(raw.get(key), `${name}.p[${key}]`)]));
  const total = pySum([...values.values()]) as number;
  if (Math.abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE) throw invalid(name, invariant, `mass sums to ${floatRepr(total)}`);
  return values;
}

/** str.isdigit()：非空且每个字符都是数字（含上标等，int() 未必认）。 */
const isdigit = (text: string): boolean => text.length > 0 && codePoints(text).every(isDigitChar);

/** int(text)：isdigit 为真却不是十进制数字（例如 ²）时照 Python 抛 ValueError。 */
function intOf(text: string): bigint {
  const value = pyIntParse(text);
  if (value === null) throw new PyCrash("ValueError", `invalid literal for int() with base 10: ${pyRepr(text)}`);
  return value;
}

/** check_answer：按所问的问题校验一条回答；自相矛盾的回答是 invalid_response，不是“勉强可用”。 */
export function checkAnswer(name: string, question: PyDict, answer: PyValue | undefined): PyDict {
  if (!isDict(answer) || answer.get("type") !== question.get("type")) throw new DecisionError("malformed", `answer ${name} has the wrong type`);
  const kind = question.get("type");
  if (kind === "noul") return dict([["type", "noul"], ["noul", unit(answer.get("noul") ?? null, `${name}.noul`)]]);
  if (kind === "choice") {
    const options = [...(question.get("criteria") as PyDict).keys()] as string[];
    const picked = answer.get("choice");
    if (typeof picked !== "string" || !options.includes(picked)) throw new DecisionError("malformed", `answer ${name} chose an option that was not offered`);
    const probabilities = distribution(name, answer.get("probabilities"), options, "choice_probability_key_set");
    const top = Math.max(...probabilities.values());
    const mass = probabilities.get(picked) as number;
    if (mass < top - ARGMAX_TOLERANCE) throw invalid(name, "choice_is_argmax", `chose ${picked} at ${floatRepr(mass)} against a maximum of ${floatRepr(top)}`);
    return dict([["type", "choice"], ["choice", picked], ["probabilities", probabilities], ["confidence", unit(answer.get("confidence") ?? null, `${name}.confidence`)]]);
  }
  const levels = (question.get("criteria") as PyValue[]).length;
  const value = answer.get("score");
  if (!isNumber(value) || !Number.isFinite(pyFloatOf(value))) throw new DecisionError("malformed", `answer ${name} has no numeric score`);
  const score = pyFloatOf(value);
  if (!(-0.5 <= score && score <= levels - 0.5)) throw new DecisionError("malformed", `answer ${name} scored off the rubric`);
  const raw = answer.get("probabilities");
  const spread = new Map<bigint, number>();
  if (isDict(raw) && raw.size) {
    const keys: string[] = [];
    for (const key of raw.keys()) {
      const text = pyStrValue(key as PyValue);
      if (!isdigit(text) || intOf(text) >= BigInt(levels)) {
        throw invalid(name, "score_distribution_on_rubric", `level ${pyReprValue(key as PyValue)} is not 0..${levels - 1}`);
      }
      keys.push(text);
    }
    const ordered = [...keys].sort((left, right) => {
      const [a, b] = [intOf(left), intOf(right)];
      return a < b ? -1 : a > b ? 1 : 0;
    });
    for (const [key, probability] of distribution(name, raw, ordered, "score_distribution_mass")) spread.set(intOf(key), probability);
    const mean = pySum([...spread].map(([level, probability]) => Number(level) * probability)) as number;
    if (Math.abs(mean - score) > SCORE_MEAN_TOLERANCE) {
      throw invalid(name, "score_matches_its_distribution", `score ${floatRepr(score)} against an expected value of ${floatRepr(mean)}`);
    }
  }
  const legend = new Map<bigint, PyValue>();
  const rawLegend = answer.get("legend");
  if (isDict(rawLegend)) {
    for (const [key, text] of rawLegend) {
      const shown = pyStrValue(key as PyValue);
      if (isdigit(shown) && intOf(shown) < BigInt(levels) && typeof text === "string") legend.set(intOf(shown), text);
    }
  }
  const out = dict([
    ["type", "score"], ["score", score], ["probabilities", spread as unknown as PyDict], ["spread_reported", spread.size > 0],
    ["confidence", unit(answer.has("confidence") ? (answer.get("confidence") as PyValue) : 1.0, `${name}.confidence`)], ["levels", BigInt(levels)],
  ]);
  if (legend.size) out.set("legend", legend as unknown as PyDict);
  return out;
}

// ---------------------------------------------------------------------------
// 会话
// ---------------------------------------------------------------------------

/** _stored_secret：环境变量没有时问凭据库；SecretError 与读不出都当没有。 */
async function storedSecret(name: string): Promise<string | null> {
  try {
    return await resolve(name);
  } catch (error) {
    if (error instanceof SecretError) return null;
    throw error;
  }
}

/** 问题清单在会话里用到的部分（probe 自己拼一份，不经文件）。 */
export type SessionBattery = Pick<Battery, "id" | "version" | "sha256" | "questions" | "thresholds">;

/**
 * Session：一条调度命令里的决策调用，共享时钟预算，记录追加到一个 decisions.jsonl。ask 总是交回一个结果，不因调用失败
 * 抛异常：status 是 answered 或 no_opinion（带 reason）。off 模式下不调用、不记录。
 */
export class Session {
  readonly settings: Settings;
  readonly recordPath: string | null;
  readonly transport: Transport;
  readonly environ: NodeJS.ProcessEnv;
  readonly clock: () => number;
  spentSeconds = 0.0;
  calls = 0;
  answered = 0;
  inputTokens = 0;
  readonly records: PyDict[] = [];
  batteries = new Map<string, Battery>();

  constructor(settings: Settings, recordPath: string | null = null, options: { transport?: Transport; environ?: NodeJS.ProcessEnv; clock?: () => number } = {}) {
    this.settings = settings;
    this.recordPath = recordPath;
    this.transport = options.transport ?? httpTransport;
    this.environ = options.environ ?? process.env;
    this.clock = options.clock ?? ((): number => performance.now() / 1000);
  }

  get active(): boolean {
    return settingsActive(this.settings);
  }

  get mode(): string {
    return this.settings.mode;
  }

  private noOpinion(result: PyDict, reason: string, detail = ""): PyDict {
    result.set("status", "no_opinion").set("reason", reason);
    if (detail) result.set("detail", firstPoints(detail, 300));
    return result;
  }

  private record(result: PyDict): void {
    this.records.push(result);
    if (this.recordPath === null) return;
    appendRecord(this.recordPath, result);
  }

  async ask(battery: SessionBattery, state: PyValue, context: PyDict | null = null): Promise<PyDict> {
    const settings = this.settings;
    const result = dict([
      ["at", utcNow()], ["point", battery.id], ["battery_version", battery.version], ["battery_sha256", battery.sha256],
      ["mode", settings.mode], ["model", settings.model], ["status", "no_opinion"], ["reason", ""], ["answers", new Map()],
      ["latency_ms", 0n], ["usage", new Map()], ["context", new Map(context ?? [])],
    ]);
    if (!settingsActive(settings)) return this.noOpinion(result, `off:${settings.reason}`);
    if (!settings.points.includes(battery.id)) return this.noOpinion(result, "point_disabled");
    const [redacted, redactions] = redactState(state);
    let encoded: string;
    try {
      encoded = dumps(redacted, { ensureAscii: false, separators: [",", ":"] });
    } catch (error) {
      if (!(error instanceof PyJsonError) || (error.kind !== "TypeError" && error.kind !== "ValueError")) throw error;
      result.set("state_chars", 0n);
      this.record(this.noOpinion(result, "state_not_json", error.message));
      return result;
    }
    result
      .set("state_sha256", createHash("sha256").update(encodeUtf8(encoded)).digest("hex"))
      .set("state_chars", BigInt(pyLen(encoded)))
      .set("redactions", BigInt(redactions));
    if (BigInt(pyLen(encoded)) > settings.max_state_chars) {
      this.record(this.noOpinion(result, "state_too_large"));
      return result;
    }
    if (isSensitive(encoded)) {
      this.record(this.noOpinion(result, "sensitive"));
      return result;
    }
    const remaining = settings.budget_seconds - this.spentSeconds;
    if (remaining <= 0.1) {
      this.record(this.noOpinion(result, "budget"));
      return result;
    }
    const key = this.environ[settings.api_key_env] || (await storedSecret(settings.api_key_env)) || "";
    if (settingsOfficial(settings) && !key) {
      this.record(this.noOpinion(result, "no_key"));
      return result;
    }
    const wire = new Map(
      [...battery.questions].map(([name, question]) => [name, new Map([...(question as PyDict)].filter(([field]) => field === "type" || field === "instructions" || field === "criteria"))]),
    );
    const body = Buffer.from(encodeUtf8(dumps(dict([["state", redacted], ["model", settings.model], ["questions", wire as PyDict]]), { ensureAscii: false, separators: [",", ":"] })));
    const headers: [string, string][] = [["Content-Type", "application/json"], ["Accept", "application/json"], ["User-Agent", USER_AGENT]];
    if (key) headers.push(["Authorization", `Bearer ${key}`]);
    const url = settings.base_url + ENDPOINT_PATH;
    const started = this.clock();
    this.calls += 1;
    let payload: PyValue;
    let checked: PyDict;
    try {
      let raw: Buffer;
      for (let attempt = 0; ; ) {
        const left = Math.min(settings.timeout_seconds, remaining - (this.clock() - started));
        if (left <= 0.05) throw new DecisionError("timeout", "budget exhausted");
        try {
          raw = await this.transport(body, headers, left, url);
          break;
        } catch (error) {
          if (!(error instanceof DecisionError)) throw error;
          attempt += 1;
          if (!RETRYABLE.has(error.code) || attempt > 1) throw error;
          await sleep(Math.min(0.25, Math.max(0.0, remaining - (this.clock() - started) - 0.1)));
        }
      }
      try {
        payload = loadsBytes(raw);
      } catch (error) {
        if (!(error instanceof PyJsonError) || error.kind === "RecursionError") throw error;
        throw new DecisionError("malformed", "reply is not JSON");
      }
      const answers = isDict(payload) ? (payload.get("answers") ?? null) : null;
      if (!isDict(answers)) throw new DecisionError("malformed", "reply has no answers");
      checked = new Map([...battery.questions].map(([name, question]) => [name, checkAnswer(name as string, question as PyDict, answers.get(name) ?? null)]));
    } catch (error) {
      if (!(error instanceof DecisionError)) throw error;
      this.spentSeconds += this.clock() - started;
      result.set("latency_ms", BigInt(Math.trunc((this.clock() - started) * 1000)));
      this.record(this.noOpinion(result, error.code, error.detail));
      return result;
    }
    const elapsed = this.clock() - started;
    this.spentSeconds += elapsed;
    const usage = isDict(payload) && isDict(payload.get("usage")) ? (payload.get("usage") as PyDict) : new Map();
    const tokens = usage.get("input_tokens");
    if (typeof tokens === "bigint") this.inputTokens += Number(tokens);
    this.answered += 1;
    const model = (payload as PyDict).get("model");
    result
      .set("status", "answered").set("reason", "").set("answers", checked).set("latency_ms", BigInt(Math.trunc(elapsed * 1000)))
      .set("usage", new Map([...usage].filter(([field]) => field === "input_tokens" || field === "output_tokens")))
      .set("served_model", typeof model === "string" ? model : null);
    this.record(result);
    return result;
  }
}

/**
 * 追加一条记录（sort_keys、ensure_ascii=False）；写不进不影响命令本身。Python 以文本模式打开，Windows 上行尾是 CRLF；
 * 编码是 strict（孤立代理项照样抛 UnicodeEncodeError）。
 */
function appendRecord(file: string, record: PyDict): void {
  const line = encodeUtf8(dumps(record, { ensureAscii: false, sortKeys: true }) + (process.platform === "win32" ? String.fromCharCode(13) : "") + LF);
  try {
    pathMkdir(parentOf(file), true, true);
    appendFileSync(file, line);
  } catch (error) {
    if (error instanceof PyCrash || error instanceof PyJsonError) throw error;
  }
}

function parentOf(file: string): string {
  const cut = Math.max(file.lastIndexOf("/"), file.lastIndexOf(String.fromCharCode(92)));
  return cut > 0 ? file.slice(0, cut) : file;
}

// ---------------------------------------------------------------------------
// 给调用方的小工具
// ---------------------------------------------------------------------------

/** Settings.as_dict。 */
export function settingsDict(settings: Settings): PyDict {
  return dict([
    ["mode", settings.mode], ["configured_mode", settings.configured_mode], ["reason", settings.reason], ["api_key_env", settings.api_key_env],
    ["base_url", settings.base_url], ["model", settings.model], ["timeout_seconds", settings.timeout_seconds], ["budget_seconds", settings.budget_seconds],
    ["max_state_chars", settings.max_state_chars], ["points", [...settings.points]], ["marker_present", settings.marker_present],
  ]);
}

/** describe：doctor 的事实（只记凭据的名字与来源，不碰值）。 */
export async function describe(settings: Settings, pluginDir: string | null, environ: NodeJS.ProcessEnv = process.env): Promise<PyDict> {
  const facts = settingsDict(settings);
  facts.set("api_key_set", Boolean(environ[settings.api_key_env]));
  facts.set("api_key_source", environ[settings.api_key_env] ? "env" : await source(settings.api_key_env));
  facts.set("secret_store_mode", storeMode());
  facts.set("official_endpoint", settingsOfficial(settings));
  facts.set("plugin_dir", pluginDir || null);
  const batteries: PyValue[] = [];
  const problems: PyValue[] = [];
  facts.set("battery_lock", null);
  if (pluginDir && isDirectory(joinPath(pluginDir, "questions"))) {
    try {
      verifyBatteryLock(pluginDir);
      facts.set("battery_lock", "ok");
    } catch (error) {
      if (!(error instanceof DecisionError)) throw error;
      facts.set("battery_lock", "drift");
      problems.push(error.message);
    }
    try {
      for (const battery of loadBatteries(joinPath(pluginDir, "questions")).values()) {
        batteries.push(dict([
          ["id", battery.id], ["version", battery.version], ["sha256", battery.sha256],
          ["questions", ([...battery.questions.keys()] as string[]).sort(cmpCodePoints)], ["thresholds", battery.thresholds],
        ]));
      }
    } catch (error) {
      if (!(error instanceof DecisionError)) throw error;
      problems.push(error.message);
    }
  }
  facts.set("batteries", batteries);
  facts.set("battery_problems", problems);
  facts.set("sdk_reference", SDK_REFERENCE());
  return facts;
}

function isDirectory(file: string): boolean {
  try {
    return statSync(file).isDirectory();
  } catch {
    return false;
  }
}

/**
 * probe：一次最小请求（一个 noul，几十个 token）。会联网、会花钱，只在用户批准后由 doctor --probe-decisions 调用；
 * 契约只对本机的假端点用它。
 */
export async function probe(settings: Settings, options: { transport?: Transport; environ?: NodeJS.ProcessEnv } = {}): Promise<PyDict> {
  const battery: SessionBattery = {
    id: "probe", version: "1.0.0", sha256: "0".repeat(64), thresholds: new Map(),
    questions: new Map([["ok", checkQuestion("noul", dict([["type", "noul"], ["instructions", "The text reports that every test passed."]]))]]),
  };
  const probeSettings: Settings = { ...settings, mode: "shadow", reason: "probe", points: ["probe"] };
  const session = new Session(probeSettings, null, options);
  const result = await session.ask(battery, "The build finished and all 12 tests passed.");
  const answered = result.get("status") === "answered";
  return dict([
    ["ok", answered], ["reason", result.get("reason") ?? ""], ["detail", result.get("detail") ?? ""], ["latency_ms", result.get("latency_ms") ?? null],
    ["served_model", result.get("served_model") ?? null], ["usage", result.get("usage") ?? null],
    ["answer", answered ? ((((result.get("answers") as PyDict).get("ok") as PyDict | undefined)?.get("noul") ?? null) as PyValue) : null],
  ]);
}

// ---------------------------------------------------------------------------
// pi_dispatch.decisions_session
// ---------------------------------------------------------------------------

/** DECISIONS_PLUGIN_DIR：kit 的 plugins/decisions。 */
export const decisionsPluginDir = (kitRoot: string): string => joinPath(joinPath(kitRoot, "plugins"), "decisions");

/**
 * decisions_session：按 dispatch.config.json 的 decisions 建一个会话；模式 off、决策点未启用时为 null。配置写错是用法错误；
 * 问题清单与内容锁不符时 strict（prepare）同样是用法错误，其余命令本次不问，打印并记一条 battery_drift。
 */
export function decisionsSession(
  config: PyValue, agentDir: string | null, recordPath: string | null, point: string | null, ctx: { kitRoot: string; out: Pick<PyOut, "print"> }, strict = false,
): Session | null {
  const secret = secretConfigError(config, "decisions");
  if (secret !== null) throw new DispatchError(`dispatch.config.json 的 decisions 无效：${secret}`, EXIT_USAGE);
  const pluginDir = decisionsPluginDir(ctx.kitRoot);
  let settings: Settings;
  try {
    settings = settingsFromConfig(config, agentDir, pluginDir);
  } catch (error) {
    if (!(error instanceof DecisionError)) throw error;
    throw new DispatchError(`dispatch.config.json 的 decisions 无效：${error.detail}`, EXIT_USAGE);
  }
  if (!settingsActive(settings) || (point !== null && !settings.points.includes(point))) return null;
  const link = batteryLinkProblem(ctx.kitRoot, pluginDir);
  if (link !== null) {
    const detail = `问题清单经过链接，不读取：${link}`;
    if (strict) throw new DispatchError(`决策插件的问题清单无效：${detail}`, EXIT_USAGE);
    recordBatteryDrift(settings, recordPath, point, detail, ctx.out);
    return null;
  }
  let batteries: Map<string, Battery>;
  try {
    batteries = loadLockedBatteries(pluginDir);
  } catch (error) {
    if (!(error instanceof DecisionError)) throw error;
    if (error.code !== "battery_drift" || strict) throw new DispatchError(`决策插件的问题清单无效：${error.detail}`, EXIT_USAGE);
    recordBatteryDrift(settings, recordPath, point, error.detail, ctx.out);
    return null;
  }
  const session = new Session(settings, recordPath);
  session.batteries = batteries;
  return session;
}

/** _record_battery_drift：打印一行，并在记录里留一条无意见（summary 与 replay 读得到）。 */
function recordBatteryDrift(settings: Settings, recordPath: string | null, point: string | null, detail: string, out: Pick<PyOut, "print">): void {
  out.print(`NOTE  决策：问题清单与插件内容锁不符（battery_drift），本次不问决策模型：${firstPoints(detail, 300)}`, { flush: true });
  if (recordPath === null) return;
  appendRecord(recordPath, dict([
    ["at", utcNow()], ["point", point || "-"], ["battery_version", null], ["battery_sha256", null], ["mode", settings.mode],
    ["model", settings.model], ["status", "no_opinion"], ["reason", "battery_drift"], ["detail", firstPoints(detail, 300)],
    ["answers", new Map()], ["latency_ms", 0n], ["usage", new Map()],
  ]));
}
