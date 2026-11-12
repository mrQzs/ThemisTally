// 三取值构建检查（合同第 9 步 / D01）：模式开关只跟 vite 的 command 走，与 NODE_ENV 无关，
// 所以 NODE_ENV 未设、development、test 三种取值下 npm run build 的产物都必须是真实模式。
// 每次用本地 vite 构建（不由全局或远程拿 vite），读 dist/assets 下的产物，断言：
//   ① 含真实模式标记串 themis-live-real；② 不含 themis-live-fixture；③ 含传输层特征串 same-origin
//      （证明传输层真进了生产产物，不是只有 mode.ts 的标记串在）。
// 三种都过打印 LIVE_BUILD_OK 3/3，否则非零退出并说明是哪一种取值、哪一条断言不成立。
import { spawnSync } from 'node:child_process';
import { readdirSync, readFileSync, rmSync, statSync } from 'node:fs';
import { join } from 'node:path';

const REPO_WEB = process.cwd();
const VITE = join(REPO_WEB, 'node_modules', 'vite', 'bin', 'vite.js');
const DIST = join(REPO_WEB, 'dist');
const ASSETS = join(DIST, 'assets');
const REAL = 'themis-live-real';
const FIXTURE = 'themis-live-fixture';
const TRANSPORT_MARKER = 'same-origin';

// 未设放在第一位（env 里删掉 NODE_ENV），另外两种是 development 与 test。
const VARIANTS = [
  { label: 'NODE_ENV 未设', nodeEnv: null },
  { label: 'NODE_ENV=development', nodeEnv: 'development' },
  { label: 'NODE_ENV=test', nodeEnv: 'test' },
];

function listAssetFiles(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...listAssetFiles(path));
    else if (statSync(path).isFile()) out.push(path);
  }
  return out;
}

function readAssets() {
  if (!statSync(ASSETS, { throwIfNoEntry: false })) return '';
  return listAssetFiles(ASSETS)
    .map((path) => readFileSync(path, 'utf8'))
    .join('\n');
}

function buildOnce(nodeEnv) {
  rmSync(DIST, { recursive: true, force: true });
  const env = { ...process.env };
  if (nodeEnv === null) delete env.NODE_ENV;
  else env.NODE_ENV = nodeEnv;
  const proc = spawnSync(process.execPath, [VITE, 'build'], { cwd: REPO_WEB, env, encoding: 'utf8' });
  const out = `${proc.stdout ?? ''}${proc.stderr ?? ''}`;
  return { code: proc.status ?? 1, out };
}

const problems = [];
let ok = 0;
for (const variant of VARIANTS) {
  const built = buildOnce(variant.nodeEnv);
  if (built.code !== 0) {
    problems.push(`${variant.label}：构建失败（退出码 ${built.code}）\n${built.out.split('\n').slice(-15).join('\n')}`);
    continue;
  }
  const blob = readAssets();
  const missing = [];
  if (!blob.includes(REAL)) missing.push(`产物里没有 ${REAL}`);
  if (blob.includes(FIXTURE)) missing.push(`产物里出现 ${FIXTURE}`);
  if (!blob.includes(TRANSPORT_MARKER)) missing.push(`产物里没有传输层特征串 ${TRANSPORT_MARKER}`);
  if (missing.length > 0) {
    problems.push(`${variant.label}：${missing.join('；')}`);
  } else {
    ok += 1;
  }
}

if (problems.length > 0) {
  console.error(`LIVE_BUILD_FAILED ${ok}/${VARIANTS.length}`);
  for (const problem of problems) console.error(`- ${problem}`);
  process.exit(1);
}

console.log(`LIVE_BUILD_OK ${ok}/${VARIANTS.length}`);
