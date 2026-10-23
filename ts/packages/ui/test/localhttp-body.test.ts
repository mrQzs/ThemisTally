// 请求体上限（桌面端 T15）：Content-Length 声明超限时一个字节也不读，流式正文读到第 65537 个字节就 cancel 并回
// 413，正好 65536 字节收下；空正文、坏的 UTF-8、不是 JSON 都是 400。
import { describe, expect, it, vi } from "vitest";
import { MAX_BODY_BYTES, readBodyLimited, readJsonBody } from "../src/localhttp/body.ts";

const OVER = MAX_BODY_BYTES + 1;

function post(body: string | Uint8Array | ReadableStream<Uint8Array>, headers: Record<string, string> = {}): Request {
  return new Request("http://127.0.0.1:1/api/v1/ping", { method: "POST", body, headers, duplex: "half" });
}

/**
 * 一份流：每次 read 给一块，并记录 read 与 cancel 的次数。highWaterMark 是 0，所以没人读它就自己不拉——
 * 「一个字节也不读」这才断言得动。
 */
function countedStream(chunks: readonly Uint8Array[]): { stream: ReadableStream<Uint8Array>; reads: () => number; cancels: () => number } {
  let reads = 0;
  let cancels = 0;
  let at = 0;
  const stream = new ReadableStream<Uint8Array>(
    {
      pull(controller) {
        reads += 1;
        const chunk = chunks[at];
        at += 1;
        if (chunk === undefined) controller.close();
        else controller.enqueue(chunk);
      },
      cancel() {
        cancels += 1;
      },
    },
    { highWaterMark: 0 },
  );
  return { stream, reads: () => reads, cancels: () => cancels };
}

describe("请求体上限", () => {
  it("常量照合同", () => {
    expect(MAX_BODY_BYTES).toBe(65536);
  });

  it("正好 65536 字节收下，第 65537 个字节就 413 并 cancel", async () => {
    const exact = new Uint8Array(MAX_BODY_BYTES).fill(0x61);
    const ok = await readBodyLimited(post(exact));
    expect(ok).toEqual({ ok: true, bytes: exact });
    const watched = countedStream([new Uint8Array(MAX_BODY_BYTES).fill(0x61), new Uint8Array(1).fill(0x62)]);
    const over = await readBodyLimited(post(watched.stream));
    expect(over).toEqual({ ok: false, status: 413 });
    expect(watched.cancels()).toBe(1);
  });

  it("Content-Length 声明超过上限：413 且一个字节也不读", async () => {
    const watched = countedStream([new Uint8Array(16).fill(0x61)]);
    const before = watched.reads();
    const result = await readBodyLimited(post(watched.stream, { "content-length": String(OVER) }));
    expect(result).toEqual({ ok: false, status: 413 });
    expect(watched.reads()).toBe(before);
  });

  it("空正文与没有正文都是空字节", async () => {
    expect(await readBodyLimited(post(new Uint8Array(0)))).toEqual({ ok: true, bytes: new Uint8Array(0) });
    const empty = new Request("http://127.0.0.1:1/api/v1/ping", { method: "POST" });
    expect(await readBodyLimited(empty)).toEqual({ ok: true, bytes: new Uint8Array(0) });
  });

  it("readJsonBody：合法 JSON 收下；空正文、坏 UTF-8、不是 JSON 都是 400", async () => {
    expect(await readJsonBody(post(new TextEncoder().encode('{"a":1}')))).toEqual({ ok: true, value: { a: 1 } });
    for (const bad of [new Uint8Array(0), new Uint8Array([0xff, 0xfe, 0xff]), new TextEncoder().encode("not json")]) {
      expect(await readJsonBody(post(bad))).toEqual({ ok: false, status: 400 });
    }
  });

  it("readJsonBody：超限是 413 而不是 400", async () => {
    const result = await readJsonBody(post(new Uint8Array(OVER).fill(0x61)));
    expect(result).toEqual({ ok: false, status: 413 });
  });

  it("正文不回显原值：错误响应里没有正文", async () => {
    const secret = "T015-SECRET-CANARY";
    const result = await readJsonBody(post(new TextEncoder().encode(`${secret} not json`)));
    expect(result.ok).toBe(false);
    expect(JSON.stringify(result)).not.toContain(secret);
  });

  it("假的流被读到时不会无限等（cancel 之后不再 pull）", async () => {
    const pull = vi.fn();
    const stream = new ReadableStream<Uint8Array>({
      pull(controller) {
        pull();
        controller.enqueue(new Uint8Array(MAX_BODY_BYTES).fill(0x61));
      },
    });
    expect(await readBodyLimited(post(stream))).toEqual({ ok: false, status: 413 });
    expect(pull).toHaveBeenCalled();
  });
});
