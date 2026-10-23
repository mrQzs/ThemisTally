// 静态资源边界在 Bun 下的探针（桌面端 T13）：Bun 绑定着 GetFileAttributesW，junction 是靠 FILE_ATTRIBUTE_REPARSE_POINT
// 认出来的；Node 下退回 lstat 也能认，但两条路都要钉住。用法：bun resolve-asset.ts <root> <pathname>，结果打成 JSON。
import { resolveAsset } from "../../src/static.ts";

const root = process.argv[2];
const pathname = process.argv[3];
if (root === undefined || pathname === undefined) {
  process.stderr.write("用法：resolve-asset.ts <root> <pathname>\n");
  process.exit(2);
}
process.stdout.write(`${JSON.stringify(resolveAsset(root, pathname))}\n`);
