// 请求体的上限（桌面端设计第 7 版 §5.2、T15）：本机服务只收一行有限的正文——Content-Length 声明超过上限时一个
// 字节也不读，流式正文边读边数、第 65537 个字节就取消读取并回 413。服务自己的计数必须先于 Bun 的
// maxRequestBodySize 触发，所以上限是 64 KiB，Bun 那一层设成两倍。坏的 UTF-8、不是 JSON、空正文都是 400，
// 并且不回显原值（正文里可能有敏感内容）。
/** 请求体上限：64 KiB。 */
export const MAX_BODY_BYTES = 65536;

export type BodyResult = { readonly ok: true; readonly bytes: Uint8Array } | { readonly ok: false; readonly status: 413 };

/** 读正文，超过 limit 一个字节就停：声明超限时直接 413（不读），流式读到第 limit+1 个字节时 cancel 再 413。 */
export async function readBodyLimited(request: Request, limit: number = MAX_BODY_BYTES): Promise<BodyResult> {
  const declared = request.headers.get("content-length");
  if (declared !== null) {
    const size = Number(declared.trim());
    if (Number.isFinite(size) && size > limit) return { ok: false, status: 413 };
  }
  const body = request.body;
  if (body === null) return { ok: true, bytes: new Uint8Array(0) };
  const reader = body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const step = await reader.read();
    if (step.done) break;
    const value = step.value;
    if (value === undefined) continue;
    total += value.byteLength;
    if (total > limit) {
      await reader.cancel();
      return { ok: false, status: 413 };
    }
    chunks.push(value);
  }
  const bytes = new Uint8Array(total);
  let at = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, at);
    at += chunk.byteLength;
  }
  return { ok: true, bytes };
}

export type JsonResult = { readonly ok: true; readonly value: unknown } | { readonly ok: false; readonly status: 400 | 413 };

/** 读 JSON 正文：超限 413；空正文、坏的 UTF-8、解析失败都是 400（都不回显原值）。 */
export async function readJsonBody(request: Request, limit: number = MAX_BODY_BYTES): Promise<JsonResult> {
  const body = await readBodyLimited(request, limit);
  if (!body.ok) return { ok: false, status: body.status };
  if (body.bytes.byteLength === 0) return { ok: false, status: 400 };
  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(body.bytes);
  } catch {
    return { ok: false, status: 400 };
  }
  try {
    return { ok: true, value: JSON.parse(text) as unknown };
  } catch {
    return { ok: false, status: 400 };
  }
}
