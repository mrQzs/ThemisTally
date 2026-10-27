// shutil.which（Python 3.12，迁移第 ③c 片）：配置中心按 PATH 找 runtime 的程序。mode 固定是缺省的 F_OK | X_OK。
// 调用方只传固定的程序名（pi、node、claude、codex、opencode），PATHEXT 与名字的大小写比较按 ASCII 写。
// 去重用 normcase：Python 用 LCMapStringEx 转小写，这里用 toLowerCase；两者只在非 ASCII 的少数字符上不同，
// 而去掉的只是与前面同名的目录，再查一遍结果也一样，不影响找到哪一个。
import { accessSync, constants, statSync } from "node:fs";
import { normcase, osPathJoin, osPathSplit } from "./pypath.ts";

const WIN = process.platform === "win32";
/** shutil._WIN_DEFAULT_PATHEXT。 */
const WIN_DEFAULT_PATHEXT = ".COM;.EXE;.BAT;.CMD;.VBS;.JS;.WS;.MSC";
/** os.defpath：Windows 上没有 os.confstr，取 ".;C:\bin"。 */
const WIN_DEFPATH = `.;C:${String.fromCharCode(92)}bin`;

/** shutil._access_check：存在（跟随链接）、不是目录；Windows 上 os.access 的 X_OK 只看取不取得到属性。 */
function accessCheck(name: string): boolean {
  try {
    if (statSync(name).isDirectory()) return false;
    if (!WIN) accessSync(name, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

/**
 * 搜索的目录：带目录的名字只查那个目录；给了 path（不是 null）就按它，否则按本进程的 PATH；Windows 上名字不带分隔符时，
 * _winapi.NeedCurrentDirectoryForExePath（看本进程的环境，不看 path）让当前目录排第一。
 */
function searchDirs(dirname: string, given: string | null): string[] | null {
  if (dirname) return [dirname];
  const raw = given ?? process.env["PATH"];
  const path = raw ?? (WIN ? WIN_DEFPATH : "/bin:/usr/bin");
  if (!path) return null;
  const dirs = path.split(WIN ? ";" : ":");
  // NoDefaultCurrentDirectoryInExePath 设了（非空）才不查当前目录
  if (WIN && !process.env["NoDefaultCurrentDirectoryInExePath"]) dirs.unshift(".");
  return dirs;
}

/** 要试的文件名：Windows 上依次加 PATHEXT 里的后缀；名字本身已带其中一个后缀时，先试名字本身。 */
function candidates(cmd: string): string[] {
  if (!WIN) return [cmd];
  const exts = (process.env["PATHEXT"] || WIN_DEFAULT_PATHEXT)
    .split(";")
    .filter(Boolean)
    .map((ext) => ext.replace(/\.+$/u, ""));
  const files = exts.map((ext) => cmd + ext);
  const upper = cmd.toUpperCase();
  if (exts.some((ext) => upper.endsWith(ext.toUpperCase()))) files.unshift(cmd);
  return files;
}

/** shutil.which(cmd, path=path)：找到时返回 os.path.join(目录, 文件名) 的原样拼法，找不到返回 null。path 为 null 时按本进程的 PATH。 */
export function pyWhich(name: string, path: string | null = null): string | null {
  const [dirname, cmd] = osPathSplit(name);
  const dirs = searchDirs(dirname, path);
  if (dirs === null) return null;
  const files = candidates(cmd);
  const seen = new Set<string>();
  for (const dir of dirs) {
    const key = normcase(dir);
    if (seen.has(key)) continue;
    seen.add(key);
    for (const file of files) {
      const found = osPathJoin(dir, file);
      if (accessCheck(found)) return found;
    }
  }
  return null;
}
