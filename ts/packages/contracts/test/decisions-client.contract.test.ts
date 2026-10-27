// 决策客户端契约（迁移第 ④b4a 片，计划 D4）：codekit/decisions 的 http_transport、check_answer、Session.ask、usage_totals、
// describe、probe 与 pi_dispatch.decisions_session，Python、Node、Bun 跑同一组场景，结果逐字比较。
//
// 端点一律是本测试进程里的假端点（裸 TCP，HTTPS 用临时生成的自签名证书）：能造出 RST、半截正文、坏状态行，也录下请求的
// 原始字节，三边发出的字节要相同。探针异步起（spawnSync 会卡住本进程的事件循环，假端点就回不了话）。
// 凭据：API key 只用 THEMIS_CONTRACT_ 前缀的假变量；凭据库用 file 模式指到临时目录，不碰系统的凭据管理器。
import { spawn, spawnSync } from "node:child_process";
import { createHash, randomBytes, X509Certificate } from "node:crypto";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import net from "node:net";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import tls from "node:tls";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { IMPLS, type Impl, type ProbeRequest, type ProbeResult, prng, runBatch } from "./harness.ts";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");
const CRLF = String.fromCharCode(13, 10);
const LF = String.fromCharCode(10);
const PYTHON = process.env["THEMIS_PYTHON"] ?? "python";
const KEY_NAME = "THEMIS_CONTRACT_DECISIONS_KEY";
const created: string[] = [];

function tempDir(label: string): string {
  const dir = mkdtempSync(join(tmpdir(), `themis-dc-${label}-`));
  created.push(dir);
  return dir;
}

afterAll(() => {
  for (const dir of created) rmSync(dir, { recursive: true, force: true });
});

/** 异步跑一次探针：env 叠加在当前环境上（null 删掉），凭据库固定为 file 模式、指到 secretsHome。 */
function askProbe(impl: Impl, request: ProbeRequest, env: Record<string, string | null> = {}): Promise<ProbeResult> {
  const [command, ...args] = impl.argv;
  const childEnv: Record<string, string | undefined> = { ...process.env, CODEKIT_SECRET_STORE: "file", XDG_CONFIG_HOME: secretsHome };
  delete childEnv[KEY_NAME];
  for (const [name, value] of Object.entries(env)) {
    if (value === null) delete childEnv[name];
    else childEnv[name] = value;
  }
  return new Promise((resolveResult, reject) => {
    const child = spawn(command ?? "", args, { env: childEnv, stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8").on("data", (chunk: string) => (stdout += chunk));
    child.stderr.setEncoding("utf8").on("data", (chunk: string) => (stderr += chunk));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) reject(new Error(`${impl.name} 探针退出码 ${String(code)}：${stderr}`));
      else resolveResult({ ...(JSON.parse(stdout) as ProbeResult), rawStdout: stdout });
    });
    child.stdin.end(JSON.stringify(request));
  });
}

// ---------------------------------------------------------------------------
// 假端点
// ---------------------------------------------------------------------------

type Behavior = (socket: net.Socket, request: Buffer) => void;

interface Endpoint {
  readonly port: number;
  readonly requests: Buffer[];
  close(): Promise<void>;
}

/** 读完一个请求（请求头加 Content-Length 的正文）再交给 behavior；没有请求就连上的（握手超时那类）不调用。 */
function serve(behavior: Behavior, secure = false): Promise<Endpoint> {
  const requests: Buffer[] = [];
  const sockets = new Set<net.Socket>();
  const onSocket = (socket: net.Socket): void => {
    sockets.add(socket);
    socket.on("close", () => sockets.delete(socket));
    socket.on("error", () => undefined);
    let data = Buffer.alloc(0);
    let handled = false;
    socket.on("data", (chunk: Buffer) => {
      data = Buffer.concat([data, chunk]);
      const end = data.indexOf(CRLF + CRLF);
      if (handled || end < 0) return;
      const head = data.subarray(0, end).toString("latin1");
      const length = Number(/content-length: *([0-9]+)/iu.exec(head)?.[1] ?? "0");
      if (data.length < end + 4 + length) return;
      handled = true;
      requests.push(data);
      behavior(socket, data);
    });
  };
  const server = secure ? tls.createServer({ key: certs.key, cert: certs.cert }, onSocket) : net.createServer(onSocket);
  return new Promise((done) => {
    server.listen(0, "127.0.0.1", () => {
      done({
        port: (server.address() as net.AddressInfo).port,
        requests,
        close: () =>
          new Promise<void>((closed) => {
            for (const socket of sockets) socket.destroy();
            server.close(() => closed());
          }),
      });
    });
  });
}

const reply = (status: number, headers: readonly string[], body: string | Buffer, reason = "X"): Behavior => (socket) => {
  socket.end(Buffer.concat([Buffer.from(`HTTP/1.1 ${status} ${reason}${CRLF}${headers.map((line) => line + CRLF).join("")}${CRLF}`, "latin1"), Buffer.from(body)]));
};
const json = (status: number, body: string | Buffer): Behavior => reply(status, ["Content-Type: application/json", `Content-Length: ${Buffer.byteLength(body)}`], body);
const raw = (bytes: string): Behavior => (socket) => socket.end(Buffer.from(bytes, "latin1"));
const silent: Behavior = () => undefined;
/** 每 every 毫秒写 4 个字节：http.client 每次 recv 各算超时，慢慢滴的回复不会超时。 */
const drip = (text: string, every: number): Behavior => (socket) => {
  let at = 0;
  const step = (): void => {
    if (socket.destroyed) return;
    if (at >= text.length) {
      socket.end();
      return;
    }
    socket.write(text.slice(at, at + 4), "latin1");
    at += 4;
    setTimeout(step, every);
  };
  step();
};

/** 一个现在没人听的端口（拒绝连接）。 */
async function closedPort(): Promise<number> {
  const endpoint = await serve(silent);
  await endpoint.close();
  return endpoint.port;
}

let certs: { key: string; cert: string };
let secretsHome = "";

/** openssl：PATH 上的，或 Git for Windows 自带的那一份。 */
function openssl(): string {
  if (spawnSync("openssl", ["version"]).status === 0) return "openssl";
  const exec = spawnSync("git", ["--exec-path"], { encoding: "utf8" }).stdout.trim();
  const bundled = resolve(exec, "..", "..", "bin", "openssl.exe");
  if (existsSync(bundled)) return bundled;
  throw new Error("找不到 openssl：自签名证书的用例要用它生成临时证书");
}

beforeAll(() => {
  const dir = tempDir("cert");
  const made = spawnSync(openssl(), [
    "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", join(dir, "key.pem"), "-out", join(dir, "cert.pem"),
    "-subj", "/CN=localhost", "-days", "2", "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost",
  ], { encoding: "utf8" });
  if (made.status !== 0) throw new Error(`openssl 生成证书失败：${made.stderr}`);
  certs = { key: readFileSync(join(dir, "key.pem"), "utf8"), cert: readFileSync(join(dir, "cert.pem"), "utf8") };
  secretsHome = tempDir("secrets");
});

// ---------------------------------------------------------------------------
// 传输
// ---------------------------------------------------------------------------

const HEADERS = [["Content-Type", "application/json"], ["Accept", "application/json"], ["User-Agent", "code-kit-decisions/2.8.0"], ["Authorization", "Bearer not-a-real-key"]];

interface TransportCase {
  readonly label: string;
  readonly behavior?: Behavior;
  readonly secure?: boolean;
  readonly refused?: boolean;
  /** https 的 URL 对着不说 TLS 的普通端点（握手超时）。 */
  readonly httpsOnPlain?: boolean;
  readonly timeout?: number;
  readonly expect: Record<string, unknown>;
}

const BIG = 1_000_000;
const TRANSPORT: TransportCase[] = [
  { label: "200 与 JSON", behavior: json(200, `{"answers":{}}`), expect: { ok: true } },
  { label: "401 认证失败", behavior: json(401, "{}"), expect: { code: "auth_failed" } },
  { label: "402 额度用完", behavior: json(402, "{}"), expect: { code: "credits_exhausted" } },
  { label: "403 认证失败", behavior: json(403, "{}"), expect: { code: "auth_failed" } },
  { label: "422 带正文：脱敏后截 300", behavior: json(422, `{"error":"bad","token":"sk-ant-api03-${"A".repeat(40)}","pad":"${"x".repeat(400)}"}`), expect: { code: "invalid_request" } },
  { label: "429 限流", behavior: json(429, "{}"), expect: { code: "rate_limited" } },
  { label: "504", behavior: json(504, "{}"), expect: { code: "http_504" } },
  { label: "529 过载", behavior: json(529, "{}"), expect: { code: "overloaded" } },
  { label: "302 不跟随", behavior: reply(302, ["Location: http://127.0.0.1:1/elsewhere", "Content-Length: 0"], ""), expect: { code: "http_302" } },
  { label: "正文恰好 1,000,000 字节", behavior: json(200, Buffer.alloc(BIG, 0x61)), expect: { ok: true } },
  { label: "正文 1,000,001 字节", behavior: json(200, Buffer.alloc(BIG + 1, 0x61)), expect: { code: "response_too_large" } },
  { label: "过大的正文先于状态码", behavior: json(500, Buffer.alloc(BIG + 5, 0x61)), expect: { code: "response_too_large" } },
  { label: "分块编码", behavior: raw(`HTTP/1.1 200 OK${CRLF}Transfer-Encoding: chunked${CRLF}${CRLF}5${CRLF}{"a":${CRLF}2${CRLF}1}${CRLF}0${CRLF}${CRLF}`), expect: { ok: true } },
  { label: "分块编码断在半截", behavior: raw(`HTTP/1.1 200 OK${CRLF}Transfer-Encoding: chunked${CRLF}${CRLF}20${CRLF}{"a":1`), expect: { code: "network" } },
  { label: "没有 Content-Length，读到关闭", behavior: raw(`HTTP/1.1 200 OK${CRLF}${CRLF}{"a":1}`), expect: { ok: true } },
  { label: "Content-Length 没收满就关闭：交回已收到的", behavior: raw(`HTTP/1.1 200 OK${CRLF}Content-Length: 100${CRLF}${CRLF}{"a":1}`), expect: { ok: true } },
  { label: "拒绝连接", refused: true, expect: { code: "network" } },
  { label: "连上就关、没有回复", behavior: (socket) => socket.end(), expect: { code: "network" } },
  { label: "连上就 RST", behavior: (socket) => socket.resetAndDestroy(), expect: { code: "network" } },
  { label: "回了一半再 RST", behavior: (socket) => {
    socket.write(`HTTP/1.1 200 OK${CRLF}Content-Length: 100${CRLF}${CRLF}{"a"`);
    setTimeout(() => socket.resetAndDestroy(), 50);
  }, expect: { code: "network" } },
  { label: "不回话：超时", behavior: silent, timeout: 0.6, expect: { code: "timeout" } },
  { label: "回了头、正文停住：超时", behavior: (socket) => socket.write(`HTTP/1.1 200 OK${CRLF}Content-Length: 10${CRLF}${CRLF}{`), timeout: 0.6, expect: { code: "timeout" } },
  { label: "状态行与头部慢慢滴：每次收到都重新计时，不超时", behavior: drip(`HTTP/1.1 200 OK${CRLF}X-Slow: abcdefghijklmnop${CRLF}Content-Length: 2${CRLF}${CRLF}{}`, 200), timeout: 0.6, expect: { ok: true } },
  { label: "坏状态行", behavior: raw(`HTTP/1.1 abc OK${CRLF}${CRLF}`), expect: { code: "network" } },
  { label: "不是 HTTP 的回复", behavior: raw(`garbage${CRLF}${CRLF}`), expect: { code: "network" } },
  { label: "自签名证书", behavior: json(200, "{}"), secure: true, expect: { code: "network" } },
  { label: "HTTPS 握手超时", behavior: silent, httpsOnPlain: true, timeout: 0.6, expect: { code: "timeout" } },
];

async function runTransport(item: TransportCase): Promise<{ results: Record<string, unknown>[]; requests: Buffer[] }> {
  const endpoint = item.refused ? null : await serve(item.behavior ?? silent, item.secure === true);
  const port = endpoint?.port ?? (await closedPort());
  const request: ProbeRequest = {
    op: "decisions.client", fn: "transport", body: Buffer.from(`{"state":"x"}`).toString("base64"), headers: HEADERS,
    timeout: item.timeout ?? 3, url: `${item.secure || item.httpsOnPlain ? "https" : "http"}://127.0.0.1:${port}/v1/systemone`,
  };
  try {
    const results: Record<string, unknown>[] = [];
    for (const impl of IMPLS) {
      const { rawStdout: _ignored, ...result } = await askProbe(impl, request);
      results.push(result);
    }
    return { results, requests: endpoint?.requests ?? [] };
  } finally {
    await endpoint?.close();
  }
}

describe("传输：本机假端点，三边结果与请求字节一致", () => {
  for (const item of TRANSPORT) {
    it(item.label, async () => {
      const { results, requests } = await runTransport(item);
      for (const result of results.slice(1)) expect(result).toEqual(results[0]);
      expect(results[0]).toMatchObject(item.expect);
      if (requests.length) {
        for (const bytes of requests.slice(1)) expect(bytes.toString("latin1")).toBe((requests[0] as Buffer).toString("latin1"));
      }
    }, 60_000);
  }
});

/** 回复头的写法与上限：llhttp 缺省比 http.client 严（头部合计 16 KB、只认 CRLF），TS 放宽后照 Python 自己查行长与头数。 */
describe("传输：回复头的写法与上限", () => {
  const lines = (count: number): string => Array.from({ length: count }, (_, at) => `X-H${at}: v${CRLF}`).join("");
  const cases: [string, Behavior, Record<string, unknown>][] = [
    ["20 KB 的一个头", raw(`HTTP/1.1 200 OK${CRLF}X-Big: ${"b".repeat(20_000)}${CRLF}Content-Length: 2${CRLF}${CRLF}{}`), { ok: true }],
    ["一行恰好 65536 字节（含 CRLF）", raw(`HTTP/1.1 200 OK${CRLF}X-Big: ${"b".repeat(65_527)}${CRLF}Content-Length: 2${CRLF}${CRLF}{}`), { ok: true }],
    ["一行 65537 字节", raw(`HTTP/1.1 200 OK${CRLF}X-Big: ${"b".repeat(65_528)}${CRLF}Content-Length: 2${CRLF}${CRLF}{}`), { detail: "LineTooLong" }],
    ["99 个头（结尾的空行也计数）", raw(`HTTP/1.1 200 OK${CRLF}${lines(98)}Content-Length: 2${CRLF}${CRLF}{}`), { ok: true }],
    ["100 个头", raw(`HTTP/1.1 200 OK${CRLF}${lines(99)}Content-Length: 2${CRLF}${CRLF}{}`), { detail: "HTTPException" }],
    ["只用 LF 换行", raw(`HTTP/1.1 200 OK${LF}Content-Length: 2${LF}${LF}{}`), { ok: true }],
  ];
  for (const [label, behavior, expected] of cases) {
    it(label, async () => {
      const { results } = await runTransport({ label, behavior, expect: {} });
      for (const result of results.slice(1)) expect(result).toEqual(results[0]);
      expect(results[0]).toMatchObject(expected);
    }, 60_000);
  }

  // 头名里有空格：http.client 照收（email 解析器记成缺陷），llhttp 宽松模式也拒。不照搬（第 10 节），钉住两边各自的结果
  it("头名里有空格：已知不同", async () => {
    const { results } = await runTransport({ label: "space", behavior: raw(`HTTP/1.1 200 OK${CRLF}Bad Header: v${CRLF}Content-Length: 2${CRLF}${CRLF}{}`), expect: {} });
    expect(results[0]).toMatchObject({ ok: true });
    for (const result of results.slice(1)) expect(result).toEqual({ ok: false, error: "DecisionError", code: "network", detail: "BadStatusLine" });
  }, 60_000);
});

describe("传输：系统证书库", () => {
  it.runIf(process.platform === "win32")("Python 缺省上下文载入的根与 tls.getCACertificates(\"system\") 去重后是同一组", () => {
    const script = [
      "import hashlib, json, ssl",
      "found = set()",
      "for store in ('CA', 'ROOT'):",
      "    for cert, encoding, trust in ssl.enum_certificates(store):",
      "        if encoding == 'x509_asn' and (trust is True or '1.3.6.1.5.5.7.3.1' in trust):",
      "            found.add(hashlib.sha256(cert).hexdigest())",
      "print(json.dumps(sorted(found)))",
    ].join(LF);
    const python = JSON.parse(spawnSync(PYTHON, ["-c", script], { encoding: "utf8" }).stdout) as string[];
    const system = (tls as unknown as { getCACertificates(kind: string): string[] }).getCACertificates("system");
    const ours = [...new Set(system.map((pem) => createHash("sha256").update(new X509Certificate(pem).raw).digest("hex")))].sort();
    expect(ours).toEqual(python);
  });
});

/** json.loads(bytes)：认编码（UTF-8 带不带 BOM、UTF-16、UTF-32）、surrogatepass 解码、解析；错误只比“解码”与“JSON”两类。 */
function randomReplies(seed: number, count: number): string[] {
  const rnd = prng(seed);
  const pick = <T>(items: readonly T[]): T => items[Math.floor(rnd() * items.length)] as T;
  const C = (...cps: number[]): string => String.fromCodePoint(...cps);
  const texts = [`{"a":1}`, `"${C(0xe9, 0x4e2d, 0x1f600)}"`, "[1, 2.5, null]", `{"answers":{"x":{"type":"noul","noul":0.5}}}`, "nul", "", " ", "7"];
  const utf32 = (text: string, little: boolean): Buffer => {
    const points = [...text].map((char) => char.codePointAt(0) ?? 0);
    const out = Buffer.alloc(points.length * 4);
    points.forEach((point, at) => (little ? out.writeUInt32LE(point, at * 4) : out.writeUInt32BE(point, at * 4)));
    return out;
  };
  const utf16be = (text: string): Buffer => Buffer.from(text, "utf16le").swap16();
  const encodings: ((text: string) => Buffer)[] = [
    (text) => Buffer.from(text, "utf8"),
    (text) => Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), Buffer.from(text, "utf8")]),
    (text) => Buffer.from(text, "utf16le"),
    (text) => Buffer.concat([Buffer.from([0xff, 0xfe]), Buffer.from(text, "utf16le")]),
    (text) => utf16be(text),
    (text) => Buffer.concat([Buffer.from([0xfe, 0xff]), utf16be(text)]),
    (text) => utf32(text, true),
    (text) => Buffer.concat([Buffer.from([0xff, 0xfe, 0, 0]), utf32(text, true)]),
    (text) => utf32(text, false),
    (text) => Buffer.concat([Buffer.from([0, 0, 0xfe, 0xff]), utf32(text, false)]),
  ];
  const insertions = [[0xed, 0xa0, 0x80], [0xed, 0xbf, 0xbf], [0xf4, 0x90, 0x80, 0x80], [0xc0, 0x80], [0xe0, 0x80, 0x80], [0xff], [0x80], [0xdc, 0x00], [0x00, 0xd8], [0x00, 0x00, 0x11, 0x00]];
  return Array.from({ length: count }, () => {
    let bytes = pick(encodings)(pick(texts));
    const roll = rnd();
    if (roll < 0.3) {
      const at = Math.floor(rnd() * (bytes.length + 1));
      bytes = Buffer.concat([bytes.subarray(0, at), Buffer.from(pick(insertions)), bytes.subarray(at)]);
    } else if (roll < 0.4 && bytes.length) {
      bytes = bytes.subarray(0, bytes.length - 1);
    }
    return bytes.toString("base64");
  });
}

describe("json.loads(bytes)：随机回复", () => {
  it.each([31, 32])("种子 %i：500 段", (seed) => {
    const items = randomReplies(seed, 500).map((data) => ({ op: "pyjson.loads_bytes", data }));
    const [python, ...others] = IMPLS.map((impl) => runBatch(impl, items));
    const kinds = new Set((python ?? []).map((result) => (result.ok ? "ok" : String(result.error))));
    expect([...kinds].sort()).toEqual(["decode", "json", "ok"]);
    for (const other of others) {
      const diffs = (other ?? []).flatMap((value, at) => (JSON.stringify(value) === JSON.stringify(python?.[at]) ? [] : [{ data: items[at]?.data, python: python?.[at], other: value }]));
      expect(diffs.slice(0, 5)).toEqual([]);
    }
  }, 120_000);
});

// ---------------------------------------------------------------------------
// 回答校验
// ---------------------------------------------------------------------------

const QUESTIONS = {
  noul: { type: "noul", instructions: "Is it so?" },
  choice: { type: "choice", instructions: "Pick one.", criteria: { red: "the red one", green: "the green one", blue: "the blue one" } },
  score: { type: "score", instructions: "Rate it.", criteria: ["none", "some", "much", "all"] },
};

/** 随机回答：类型、数值（布尔、整数、浮点、越界、NaN 与无穷的文字）、概率表（缺键、多键、和不为 1、非 argmax）、等级与图例。 */
function randomAnswers(seed: number, count: number): { name: string; question: string; answer: string }[] {
  const rnd = prng(seed);
  const pick = <T>(items: readonly T[]): T => items[Math.floor(rnd() * items.length)] as T;
  const number = (): string => pick(["0", "1", "0.5", "0.25", "1.0000005", "1.00001", "-0.0000005", "-0.1", "true", "null", `"0.5"`, "1e400", "NaN", "Infinity", String(rnd()), "3", "2.5", "0.98", "1e-7"]);
  const out: { name: string; question: string; answer: string }[] = [];
  for (let index = 0; index < count; index += 1) {
    const kind = pick(["noul", "choice", "score"] as const);
    const parts: string[] = [`"type":${pick([`"${kind}"`, `"${kind}"`, `"${kind}"`, `"noul"`, "1"])}`];
    if (kind === "noul") {
      if (rnd() < 0.9) parts.push(`"noul":${number()}`);
    } else if (kind === "choice") {
      parts.push(`"choice":${pick([`"red"`, `"green"`, `"blue"`, `"pink"`, "1"])}`);
      const keys = pick([["red", "green", "blue"], ["red", "green"], ["red", "green", "blue", "pink"], ["blue", "red", "green"]]);
      const split = pick([[0.5, 0.3, 0.2, 0], [0.2, 0.3, 0.5, 0], [0.3333333, 0.3333333, 0.3333334, 0], [0.5, 0.5, 0.2, 0], [0.995, 0, 0, 0]]);
      if (rnd() < 0.9) parts.push(`"probabilities":{${keys.map((key, at) => `"${key}":${String(split[at])}`).join(",")}}`);
      if (rnd() < 0.85) parts.push(`"confidence":${number()}`);
    } else {
      parts.push(`"score":${pick(["0", "1", "1.5", "3", "3.5", "-0.5", "3.6", "true", `"2"`, "1e400", "2"])}`);
      const spread = pick([`{"0":0.25,"1":0.25,"2":0.25,"3":0.25}`, `{"1":0.5,"2":0.5}`, `{"2":1}`, `{"4":1}`, `{"²":1}`, `{"１":1}`, `{"01":0.5,"1":0.5}`, `{"a":1}`, `{}`, `[]`, `{"1":0.6,"2":0.6}`]);
      if (rnd() < 0.8) parts.push(`"probabilities":${spread}`);
      if (rnd() < 0.5) parts.push(`"legend":${pick([`{"0":"none","3":"all","9":"x"}`, `{"²":"x"}`, `{"1":5}`, `[]`])}`);
      if (rnd() < 0.7) parts.push(`"confidence":${number()}`);
    }
    out.push({ name: `q${index}`, question: JSON.stringify(QUESTIONS[kind]), answer: `{${parts.join(",")}}` });
  }
  return out;
}

describe("回答校验：随机回答", () => {
  it.each([11, 12, 13])("种子 %i：400 条", async (seed) => {
    const items = randomAnswers(seed, 400).map((item) => ({ op: "decisions.client", fn: "check_answer", ...item }));
    const results = await Promise.all(IMPLS.map((impl) => askProbe(impl, { op: "batch", items })));
    const lists = results.map((result) => result["results"] as unknown[]);
    for (const list of lists.slice(1)) {
      const diffs = list.flatMap((value, at) => (JSON.stringify(value) === JSON.stringify(lists[0]?.[at]) ? [] : [{ item: items[at], python: lists[0]?.[at], other: value }]));
      expect(diffs.slice(0, 5)).toEqual([]);
    }
  }, 120_000);
});

// ---------------------------------------------------------------------------
// 会话
// ---------------------------------------------------------------------------

const BATTERY = JSON.stringify({
  id: "report-screen", version: "1.0.0", sha256: "a".repeat(64),
  questions: { unsupported: { ...QUESTIONS.noul, label: "没有证据的自述" }, verdict: QUESTIONS.choice, severity: QUESTIONS.score },
});
const GOOD_REPLY = JSON.stringify({
  answers: {
    unsupported: { type: "noul", noul: 0.81 },
    verdict: { type: "choice", choice: "green", probabilities: { red: 0.1, green: 0.7, blue: 0.2 }, confidence: 0.6 },
    severity: { type: "score", score: 1.5, probabilities: { "1": 0.5, "2": 0.5 }, confidence: 0.9, legend: { "0": "none" } },
  },
  usage: { input_tokens: 1234, output_tokens: 56, cached: 7 }, model: "jev-1.13.0-served",
});

interface AskCase {
  readonly label: string;
  readonly behaviors?: readonly Behavior[];
  readonly config?: Record<string, unknown>;
  readonly states?: readonly unknown[];
  readonly env?: Record<string, string | null>;
  readonly storedKey?: string;
  readonly reasons: readonly string[];
}

const KEY = `fake-${randomBytes(6).toString("hex")}`;

const ASKS: AskCase[] = [
  { label: "有答案：noul、choice、score 与用量", behaviors: [json(200, GOOD_REPLY)], reasons: [""] },
  { label: "凭据从环境变量来", behaviors: [json(200, GOOD_REPLY)], env: { [KEY_NAME]: KEY }, reasons: [""] },
  { label: "凭据从凭据库（file 模式）来", behaviors: [json(200, GOOD_REPLY)], storedKey: KEY, reasons: [""] },
  { label: "不是 JSON", behaviors: [json(200, "nope")], reasons: ["malformed"] },
  { label: "UTF-16 的 JSON 回复", behaviors: [json(200, Buffer.concat([Buffer.from([0xff, 0xfe]), Buffer.from(GOOD_REPLY, "utf16le")]))], reasons: [""] },
  { label: "没有 answers", behaviors: [json(200, `{"usage":{}}`)], reasons: ["malformed"] },
  { label: "回答自相矛盾", behaviors: [json(200, GOOD_REPLY.replace(`"choice":"green"`, `"choice":"blue"`))], reasons: ["invalid_response"] },
  { label: "429 之后重试成功", behaviors: [json(429, "{}"), json(200, GOOD_REPLY)], reasons: [""] },
  { label: "两次 503", behaviors: [json(503, "{}"), json(503, "{}")], reasons: ["http_503"] },
  { label: "400 不重试", behaviors: [json(400, "{}"), json(200, GOOD_REPLY)], reasons: ["http_400"] },
  { label: "超时不重试", behaviors: [silent], config: { timeout_seconds: 0.5 }, reasons: ["timeout"] },
  { label: "state 太大", config: { max_state_chars: 500 }, states: ["x".repeat(600)], reasons: ["state_too_large"] },
  { label: "state 里的令牌先被遮掉，照常发出", behaviors: [json(200, GOOD_REPLY)], states: [{ note: `token sk-ant-api03-${"B".repeat(40)}` }], reasons: [""] },
  { label: "state 像凭据：整段不发", states: [{ note: "the password is in the vault" }], reasons: ["sensitive"] },
  { label: "决策点没启用", config: { points: ["run-health"] }, reasons: ["point_disabled"] },
  { label: "模式 off", config: { mode: "off" }, reasons: ["off:configured_off"] },
  { label: "官方端点没有凭据", config: { base_url: "https://api.typesafe.ai", api_key_env: "THEMIS_CONTRACT_DECISIONS_UNSET" }, reasons: ["no_key"] },
  { label: "同一会话问两次", behaviors: [json(200, GOOD_REPLY), json(200, GOOD_REPLY)], states: [{ a: 1 }, { b: [1, 2.5, "三"] }], reasons: ["", ""] },
];

/** 记录里随时间变的字段：at、latency_ms。 */
const scrubTimes = (text: string): string => text.replace(/"at": ?"[^"]*"/gu, `"at": "<AT>"`).replace(/"latency_ms": ?[0-9]+/gu, `"latency_ms": -1`);

async function runAsk(item: AskCase, impl: Impl): Promise<{ value: string; record: string; request: string; stdout: string }> {
  const queue = [...(item.behaviors ?? [])];
  const endpoint = await serve((socket, request) => (queue.shift() ?? json(500, "{}"))(socket, request));
  const dir = tempDir("ask");
  const record = join(dir, "decisions.jsonl");
  const keyFile = join(secretsHome, "code-kit", "secrets", KEY_NAME);
  if (item.storedKey) {
    mkdirSync(dirname(keyFile), { recursive: true });
    writeFileSync(keyFile, `${item.storedKey}${LF}`);
  }
  try {
    const config = { mode: "shadow", base_url: `http://127.0.0.1:${endpoint.port}`, api_key_env: KEY_NAME, ...item.config };
    const result = await askProbe(impl, {
      op: "decisions.client", fn: "ask", config: JSON.stringify({ decisions: config }), battery: BATTERY, record,
      context: JSON.stringify({ attempt: "attempt-001" }), states: (item.states ?? [{ report: "all tests passed" }]).map((state) => JSON.stringify(state)),
    }, item.env ?? {});
    if (result["ok"] !== true) throw new Error(`${impl.name}：${JSON.stringify(result)}`);
    return {
      value: scrubTimes(String(result["value"])),
      record: existsSync(record) ? scrubTimes(readFileSync(record, "utf8")) : "",
      request: endpoint.requests.map((bytes) => bytes.toString("latin1").replace(`127.0.0.1:${endpoint.port}`, "<HOST>")).join(LF + "--" + LF),
      stdout: String(result["rawStdout"]),
    };
  } finally {
    rmSync(keyFile, { force: true });
    await endpoint.close();
  }
}

describe("会话：Session.ask 的结果、记录与发出去的请求", () => {
  for (const item of ASKS) {
    it(item.label, async () => {
      const runs = [];
      for (const impl of IMPLS) runs.push(await runAsk(item, impl));
      const first = runs[0] as Awaited<ReturnType<typeof runAsk>>;
      for (const run of runs.slice(1)) expect({ ...run, stdout: "" }).toEqual({ ...first, stdout: "" });
      const value = JSON.parse(first.value) as { results: { reason: string }[] };
      expect(value.results.map((result) => result.reason)).toEqual(item.reasons);
      // 凭据只出现在发给端点的 Authorization 头里：结果、记录、探针输出都不能有
      for (const run of runs) for (const text of [run.value, run.record, run.stdout]) expect(text.includes(KEY)).toBe(false);
      if (item.env?.[KEY_NAME] || item.storedKey) expect(first.request).toContain(`Authorization: Bearer ${KEY}`);
    }, 60_000);
  }
});

/** 凭据管理器里 code-kit:THEMIS_CONTRACT_ 开头的目标名（只读目标名，不读值）。 */
function credmanResidue(): string[] {
  const code = [
    "import ctypes, json",
    "from ctypes import wintypes",
    "class C(ctypes.Structure):",
    "    _fields_ = [('Flags', wintypes.DWORD), ('Type', wintypes.DWORD), ('TargetName', wintypes.LPWSTR)]",
    "api = ctypes.WinDLL('advapi32', use_last_error=True)",
    "count, items = wintypes.DWORD(), ctypes.POINTER(ctypes.POINTER(C))()",
    "ok = api.CredEnumerateW('code-kit:THEMIS_CONTRACT_*', 0, ctypes.byref(count), ctypes.byref(items))",
    "names = [items[i].contents.TargetName for i in range(count.value)] if ok else []",
    "if ok: api.CredFree(items)",
    "elif ctypes.get_last_error() != 1168: raise OSError(ctypes.get_last_error())",
    "print(json.dumps(sorted(names)))",
  ].join(LF);
  return JSON.parse(spawnSync(PYTHON, ["-c", code], { encoding: "utf8" }).stdout) as string[];
}

/** codekit.secrets 写入、删除凭据管理器里的一项（system 模式）；值经 stdin 交过去，不进命令行与输出。 */
function credman(action: "store" | "remove", name: string, value = ""): void {
  const call = action === "store" ? `secrets.store(${JSON.stringify(name)}, sys.stdin.read(), environ)` : `secrets.remove(${JSON.stringify(name)}, environ)`;
  const code = ["import os, sys", "sys.path.insert(0, 'scripts')", "from codekit import secrets", "environ = dict(os.environ, CODEKIT_SECRET_STORE='system')", call].join(LF);
  const done = spawnSync(PYTHON, ["-c", code], { cwd: REPO, input: value, encoding: "utf8" });
  if (done.status !== 0) throw new Error(`codekit.secrets.${action} 失败（退出码 ${String(done.status)}）`); // 不带 stderr：万一里面有值
}

/**
 * 往 Windows 凭据管理器里写（站主 2026-10-26 同意，三个条件同 secret-store 契约）：默认跳过，THEMIS_CREDMAN_ROUNDTRIP=1 才跑，
 * 只由规划端手动跑；目标名只用 code-kit:THEMIS_CONTRACT_ 前缀、finally 里删掉，前后各按前缀查一次残留；值是合成的假值。
 * 覆盖 TS 的读值路径：Bun 走 FFI，Node 后备经辅助进程的管道交回。
 */
describe.runIf(process.platform === "win32" && process.env["THEMIS_CREDMAN_ROUNDTRIP"] === "1")("凭据从系统凭据管理器来（显式打开才跑）", () => {
  it("三边都读出同一个 key，只出现在 Authorization 头里；前后没有残留", async () => {
    const name = `THEMIS_CONTRACT_${randomBytes(6).toString("hex").toUpperCase()}`;
    const value = `fake-${randomBytes(8).toString("hex")}`;
    expect(credmanResidue(), "跑之前没有残留").toEqual([]);
    try {
      credman("store", name, value);
      for (const impl of IMPLS) {
        const endpoint = await serve(json(200, GOOD_REPLY));
        try {
          const config = { decisions: { mode: "shadow", base_url: `http://127.0.0.1:${endpoint.port}`, api_key_env: name } };
          const result = await askProbe(impl, { op: "decisions.client", fn: "ask", config: JSON.stringify(config), battery: BATTERY, states: [JSON.stringify({ a: 1 })] }, { CODEKIT_SECRET_STORE: "system", [name]: null });
          expect(String(result["rawStdout"]).includes(value), `${impl.name} 的输出不含 key`).toBe(false);
          expect(String(result["value"])).toContain(`"status": "answered"`);
          expect((endpoint.requests[0] ?? Buffer.alloc(0)).toString("latin1").includes(`Authorization: Bearer ${value}`), `${impl.name} 发出了这个 key`).toBe(true);
        } finally {
          await endpoint.close();
        }
      }
    } finally {
      credman("remove", name);
      expect(credmanResidue(), "跑之后没有残留").toEqual([]);
    }
  }, 120_000);
});

// ---------------------------------------------------------------------------
// 用量、doctor 的事实与探测、decisions_session
// ---------------------------------------------------------------------------

describe("用量合计", () => {
  it("各种记录", async () => {
    const records = JSON.stringify([
      { status: "answered", usage: { input_tokens: 100 } }, { status: "answered", usage: { input_tokens: true } },
      { status: "no_opinion", reason: "timeout", usage: {} }, { status: "no_opinion", reason: "timeout" }, { status: "no_opinion" },
      { status: "answered", usage: { input_tokens: 1.5 } }, { status: "answered", usage: null }, { status: "x", reason: 5 },
      { status: "answered", usage: { input_tokens: 123456789 } },
    ]);
    const results = await Promise.all(IMPLS.map((impl) => askProbe(impl, { op: "decisions.client", fn: "usage_totals", records })));
    for (const result of results) expect(result["value"]).toBe(results[0]?.["value"]);
    const crash = JSON.stringify([{ status: "answered", usage: [1] }]);
    const crashes = await Promise.all(IMPLS.map((impl) => askProbe(impl, { op: "decisions.client", fn: "usage_totals", records: crash })));
    for (const result of crashes) expect(result["error"]).toBe("AttributeError");
  }, 60_000);
});

/** 一个临时 kit：plugins/decisions 照仓库的那一份抄过来。 */
function kitWithPlugin(mutate?: (pluginDir: string) => void): string {
  const kit = tempDir("kit");
  cpSync(join(REPO, "plugins", "decisions"), join(kit, "plugins", "decisions"), { recursive: true });
  mutate?.(join(kit, "plugins", "decisions"));
  return kit;
}

const tamper = (pluginDir: string): void => {
  const file = join(pluginDir, "questions", "report-screen.json");
  writeFileSync(file, readFileSync(file, "utf8").replace(`"version"`, ` "version"`));
};

describe("doctor 的事实与探测", () => {
  it.each([
    ["插件完整", (): string => kitWithPlugin()],
    ["清单被改过", (): string => kitWithPlugin(tamper)],
    ["没有 questions", (): string => kitWithPlugin((dir) => rmSync(join(dir, "questions"), { recursive: true }))],
  ])("describe：%s", async (_label, make) => {
    const pluginDir = join(make(), "plugins", "decisions");
    const config = JSON.stringify({ decisions: { mode: "shadow", base_url: "http://127.0.0.1:9", api_key_env: KEY_NAME } });
    const results = await Promise.all(IMPLS.map((impl) => askProbe(impl, { op: "decisions.client", fn: "describe", config, plugin_dir: pluginDir })));
    for (const result of results) expect(result["value"], JSON.stringify(result)).toBe(results[0]?.["value"]);
  }, 60_000);

  it("probe：对假端点问一次", async () => {
    const values = [];
    for (const impl of IMPLS) {
      const endpoint = await serve(json(200, JSON.stringify({ answers: { ok: { type: "noul", noul: 0.97 } }, usage: { input_tokens: 31 }, model: "m" })));
      const config = JSON.stringify({ decisions: { mode: "shadow", base_url: `http://127.0.0.1:${endpoint.port}`, api_key_env: KEY_NAME } });
      values.push(scrubTimes(String((await askProbe(impl, { op: "decisions.client", fn: "probe", config }))["value"])));
      await endpoint.close();
    }
    for (const value of values) expect(value).toBe(values[0]);
    expect(values[0]).toContain(`"ok": true`);
  }, 60_000);
});

describe("decisions_session", () => {
  const cases: [string, Record<string, unknown>, () => string, string | null, boolean][] = [
    ["插件完整：建会话", { mode: "shadow" }, () => kitWithPlugin(), "report-screen", false],
    ["不指定决策点", { mode: "on" }, () => kitWithPlugin(), null, false],
    ["模式 off", { mode: "off" }, () => kitWithPlugin(), "report-screen", false],
    ["决策点没启用", { mode: "shadow", points: ["run-health"] }, () => kitWithPlugin(), "report-screen", false],
    ["配置写错", { mode: "loud" }, () => kitWithPlugin(), "report-screen", false],
    ["清单被改过：本次不问，记一条", { mode: "shadow" }, () => kitWithPlugin(tamper), "mutation-equivalence", false],
    ["清单被改过，strict", { mode: "shadow" }, () => kitWithPlugin(tamper), "report-screen", true],
    ["没有插件目录", { mode: "shadow" }, () => tempDir("bare"), "report-screen", false],
  ];
  for (const [label, decisions, make, point, strict] of cases) {
    it(label, async () => {
      const kit = make();
      const outputs = [];
      for (const impl of IMPLS) {
        const record = join(tempDir("rec"), "decisions.jsonl");
        const result = await askProbe(impl, {
          op: "decisions.client", fn: "session", config: JSON.stringify({ decisions: decisions }), kit_root: kit, record, point, strict,
        });
        const { rawStdout: _ignored, ...shown } = result;
        outputs.push({ shown: JSON.parse(JSON.stringify(shown).replaceAll(JSON.stringify(kit).slice(1, -1), "<KIT>")), record: existsSync(record) ? scrubTimes(readFileSync(record, "utf8")) : "" });
      }
      for (const output of outputs.slice(1)) expect(output).toEqual(outputs[0]);
    }, 60_000);
  }
});
