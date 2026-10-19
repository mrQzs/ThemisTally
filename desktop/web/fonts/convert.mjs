// 把更纱等距黑体 SC 的 Regular 与 SemiBold 从 TTF 转成 woff2（说明见同目录的 SOURCE.md）。
// 用法：node convert.mjs <解出 TTF 的目录> <输出目录>
// 依赖：wawoff2@2.0.1（Google woff2 的 wasm 版）。把本脚本复制到仓库之外、装了它的临时目录里运行：
// ESM 的 import 从脚本所在目录往上找 node_modules，不认 NODE_PATH。
import wawoff2 from 'wawoff2';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join } from 'node:path';

const [srcDir, outDir] = process.argv.slice(2);
if (!srcDir || !outDir) {
  console.error('用法：node convert.mjs <TTF 目录> <输出目录>');
  process.exit(2);
}
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');
for (const weight of ['regular', 'semibold']) {
  const ttf = readFileSync(join(srcDir, `sarasa-mono-sc-${weight}.ttf`));
  const woff2 = Buffer.from(await wawoff2.compress(ttf));
  writeFileSync(join(outDir, `sarasa-mono-sc-${weight}.woff2`), woff2);
  console.log(JSON.stringify({ weight, ttf_bytes: ttf.length, ttf_sha256: sha256(ttf),
    woff2_bytes: woff2.length, woff2_sha256: sha256(woff2) }));
}
