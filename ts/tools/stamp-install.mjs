// 装好戳记（迁移计划第 ② 步）：根包的 postinstall 在每次 bun install 之后运行它，写 node_modules/.themis-installed。
// pi_dispatch.py 的启动器每次转交给 TS 之前现算依赖清单的合并哈希与戳记比对（算法与 pi_dispatch.ts_deps_digest
// 相同，tests/test_kernel_impl.py 对照），再核对按 PATH 找到的 bun 与这里记下的是同一个。
// `--digest <目录>` 只打印那个目录的合并哈希，供对照测试用。
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = fileURLToPath(import.meta.url);

function isFile(file) {
  try {
    return statSync(file).isFile();
  } catch {
    return false;
  }
}

function isDir(dir) {
  try {
    return statSync(dir).isDirectory();
  } catch {
    return false;
  }
}

/** 按码点比较（Python 的 sorted 对 str 的次序），不按 UTF-16 码元。 */
function byCodePoint(a, b) {
  const x = Array.from(a, (c) => c.codePointAt(0));
  const y = Array.from(b, (c) => c.codePointAt(0));
  for (let i = 0; i < Math.min(x.length, y.length); i += 1) if (x[i] !== y[i]) return x[i] - y[i];
  return x.length - y.length;
}

/** 依赖清单的合并哈希：bun.lock、package.json 与 packages/*\/package.json，按相对路径排序，逐个写
 * “路径\0文件的 sha256\n”（文件不在写 “-”），再取整体的 sha256。 */
export function depsDigest(tsRoot) {
  const names = ["bun.lock", "package.json"];
  const packages = path.join(tsRoot, "packages");
  if (isDir(packages)) {
    for (const name of readdirSync(packages)) {
      if (isFile(path.join(packages, name, "package.json"))) names.push(`packages/${name}/package.json`);
    }
  }
  names.sort(byCodePoint);
  const digest = createHash("sha256");
  for (const name of names) {
    const file = path.join(tsRoot, ...name.split("/"));
    const part = isFile(file) ? createHash("sha256").update(readFileSync(file)).digest("hex") : "-";
    digest.update(`${name}\0${part}\n`, "utf8");
  }
  return digest.digest("hex");
}

if (process.argv[1] !== undefined && path.resolve(process.argv[1]) === HERE) {
  const at = process.argv.indexOf("--digest");
  if (at >= 0) {
    process.stdout.write(`${depsDigest(path.resolve(process.argv[at + 1] ?? "."))}\n`);
  } else {
    const root = path.resolve(path.dirname(HERE), "..");
    const bun = process.versions.bun ?? null;
    const stamp = {
      schema_version: 1,
      deps_sha256: depsDigest(root),
      bun_version: bun,
      bun_path: bun === null ? null : process.execPath,
    };
    mkdirSync(path.join(root, "node_modules"), { recursive: true });
    writeFileSync(path.join(root, "node_modules", ".themis-installed"), `${JSON.stringify(stamp, null, 2)}\n`);
  }
}
