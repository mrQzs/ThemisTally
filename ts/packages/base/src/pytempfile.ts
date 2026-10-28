// tempfile.gettempdir 与 tempfile.mkdtemp（Python 3.12，迁移第 ④b3 片）：baseline 与 check --fresh 在 worktree 根下
// 建临时副本。名字照 Python：前缀加 8 个 [a-z0-9_] 的随机字符；Node 的 mkdtemp 是 6 个、字符集不同，Windows 上也不看
// TMPDIR。随机部分两边当然不同，契约里按“前缀 + 8 个字符”比。
import { randomInt } from "node:crypto";
import { closeSync, openSync, statSync, unlinkSync, writeSync } from "node:fs";
import { pyReprValue } from "./pyfmt.ts";
import { PyOSError } from "./pyio.ts";
import { PyWinError, isFileExists, osMkdir } from "./pyos.ts";
import { abspath, expanduser, osPathJoin } from "./pypath.ts";

const WIN = process.platform === "win32";
const BS = String.fromCharCode(92);
/** tempfile._RandomNameSequence.characters。 */
const CHARACTERS = "abcdefghijklmnopqrstuvwxyz0123456789_";
/** tempfile.TMP_MAX。 */
const TMP_MAX = 10000;

function randomName(): string {
  let name = "";
  for (let index = 0; index < 8; index += 1) name += CHARACTERS[randomInt(CHARACTERS.length)];
  return name;
}

function isDir(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

/** tempfile._candidate_tempdir_list：TMPDIR、TEMP、TMP，Windows 上再加几处缺省位置，最后是当前目录。 */
function candidateDirs(): string[] {
  const dirs = ["TMPDIR", "TEMP", "TMP"].map((name) => process.env[name]).filter((value): value is string => Boolean(value));
  if (WIN) {
    const systemRoot = process.env["SYSTEMROOT"];
    dirs.push(
      expanduser(`~${BS}AppData${BS}Local${BS}Temp`),
      `${systemRoot ?? "%SYSTEMROOT%"}${BS}Temp`,
      `c:${BS}temp`,
      `c:${BS}tmp`,
      `${BS}temp`,
      `${BS}tmp`,
    );
  } else {
    dirs.push("/tmp", "/var/tmp", "/usr/tmp");
  }
  dirs.push(process.cwd());
  return dirs;
}

let tempdir: string | undefined;

/** tempfile.gettempdir()：第一个建得了文件的候选目录（abspath），进程里只算一次。 */
export function pyGettempdir(): string {
  tempdir ??= defaultTempdir();
  return tempdir;
}

function defaultTempdir(): string {
  const dirs = candidateDirs();
  for (const candidate of dirs) {
    const dir = abspath(candidate);
    for (let attempt = 0; attempt < 100; attempt += 1) {
      const file = osPathJoin(dir, randomName());
      let fd: number;
      try {
        fd = openSync(file, "wx", 0o600);
      } catch (error) {
        const code = (error as NodeJS.ErrnoException).code;
        if (code === "EEXIST") continue;
        // Windows 上同名的是目录时报 PermissionError：目录可写就换个名字再试
        if ((code === "EPERM" || code === "EACCES") && WIN && isDir(dir)) continue;
        break;
      }
      try {
        writeSync(fd, Buffer.from("blat"));
      } finally {
        closeSync(fd);
        unlinkSync(file);
      }
      return dir;
    }
  }
  throw new PyOSError(2, `No usable temporary directory found in ${pyReprValue(dirs)}`, null);
}

/** tempfile.mkdtemp(prefix=prefix, dir=dir)：dir 下建 prefix 加 8 个随机字符的目录，交回它的 abspath。 */
export function pyMkdtemp(prefix: string, dir: string): string {
  for (let attempt = 0; attempt < TMP_MAX; attempt += 1) {
    const file = osPathJoin(dir, prefix + randomName());
    try {
      osMkdir(file, 0o700);
    } catch (error) {
      if (isFileExists(error)) continue;
      // Windows 上同名的是目录时报 PermissionError：dir 是目录（os.access 对目录总说可写）就换个名字再试
      if (error instanceof PyWinError && error.name === "PermissionError" && isDir(dir)) continue;
      throw error;
    }
    return abspath(file);
  }
  throw new PyOSError(17, "No usable temporary directory name found", null);
}
