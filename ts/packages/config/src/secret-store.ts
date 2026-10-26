// codekit/secrets.py 里配置中心用到的部分（迁移第 ③a2 片）：凭据在哪一层（env / credential_store / file / none）、删除、
// describe。只报有无与来源，不读值：系统凭据库只取字节数（native.credentialBlobSize），文件只看去掉空白之后是不是空的。
// 写入（secret set）留在 Python（迁移计划第 ③ 步的不转交名单）。macOS Keychain 与 Linux secret-tool 的后端没有移植：
// 第 ⑥ 步之前 TS 只在 Windows 上跑真实数据，POSIX 一侧未实机验证。
import { lstatSync, statSync, unlinkSync } from "node:fs";
import { credentialBlobSize, credentialDelete } from "@themis/base/native";
import { PyCrash } from "@themis/base/pyfmt";
import { PyOSError, PyUnicodeDecodeError, pyReadText } from "@themis/base/pyio";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { codePoints, inTable, isDigitChar, pyLen, pyLower, pyStrip } from "@themis/base/pyre";
import { purePathStr } from "@themis/base/pypath";
import { IS_ALNUM } from "@themis/base/pyunicode";
import { expanduser } from "./validate.ts";

export const STORE_ENV = "CODEKIT_SECRET_STORE";
const STORE_MODES = ["system", "file", "off"];
const TARGET_PREFIX = "code-kit:";
const WINDOWS_BACKEND = "windows-credential-manager";

export class SecretError extends Error {
  override readonly name = "SecretError";
  readonly code: string;
  readonly detail: string;
  constructor(code: string, detail = "") {
    super(detail ? `${code}: ${detail}` : code);
    this.code = code;
    this.detail = detail;
  }
}

/** 凭据以环境变量名为名字：字母、数字（Unicode 意义上的 isalnum）与下划线，不以数字开头，不超过 128 个字符。 */
export function checkName(name: PyValue | undefined): string {
  const chars = typeof name === "string" ? codePoints(name) : [];
  if (
    typeof name !== "string" ||
    !name ||
    pyLen(name) > 128 ||
    !chars.every((char) => char === "_" || inTable(IS_ALNUM, char.codePointAt(0) ?? 0)) ||
    isDigitChar(chars[0] as string)
  ) {
    throw new SecretError("name", "a secret is named by an environment variable name");
  }
  return name;
}

/** CODEKIT_SECRET_STORE：system（缺省）、file、off；认不出的按 system。 */
export function storeMode(): string {
  const mode = pyLower(pyStrip(process.env[STORE_ENV] || "system"));
  return STORE_MODES.includes(mode) ? mode : "system";
}

/** <XDG_CONFIG_HOME 或 ~/.config>/code-kit/secrets（pathlib 的写法）。 */
export function secretsDir(): string {
  const base = process.env["XDG_CONFIG_HOME"] || purePathStr(expanduser("~"), ".config");
  return purePathStr(base, "code-kit", "secrets");
}

interface Backend {
  readonly name: string;
  /** 读到的值是否为真（非空）；读不出时为假。 */
  holds(name: string): Promise<boolean>;
  remove(name: string): Promise<boolean>;
}

/** Windows 凭据管理器：值按 UTF-16LE 存，长度为 0 读成空串；长度是奇数时 Python 解码抛 UnicodeDecodeError（没接住）。 */
const windowsBackend: Backend = {
  name: WINDOWS_BACKEND,
  async holds(name) {
    const size = await credentialBlobSize(TARGET_PREFIX + name);
    if (size === null || size === 0) return false;
    if (size % 2 === 1) throw new PyCrash("UnicodeDecodeError", "'utf-16-le' codec can't decode byte: truncated data");
    return true;
  },
  remove: (name) => credentialDelete(TARGET_PREFIX + name),
};

const fileBackend: Backend = {
  name: "file",
  async holds(name) {
    const file = purePathStr(secretsDir(), name);
    try {
      if (lstatSync(file).isSymbolicLink() || !statSync(file).isFile()) return false;
    } catch {
      return false;
    }
    try {
      return pyStrip(pyReadText(file)) !== "";
    } catch (error) {
      if (error instanceof PyOSError) return false;
      if (error instanceof PyUnicodeDecodeError) throw new PyCrash("UnicodeDecodeError", error.message);
      throw error;
    }
  },
  async remove(name) {
    try {
      unlinkSync(purePathStr(secretsDir(), name));
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
      throw error;
    }
    return true;
  },
};

function systemBackend(): Backend | null {
  return process.platform === "win32" ? windowsBackend : null;
}

/** 按解析顺序（环境变量之后）的后端；off 时为空。 */
function backends(): Backend[] {
  const mode = storeMode();
  if (mode === "off") return [];
  const system = mode === "system" ? systemBackend() : null;
  return system === null ? [fileBackend] : [system, fileBackend];
}

/** 凭据在哪一层：env / credential_store / file / none。不返回值。 */
export async function source(name: string): Promise<string> {
  checkName(name);
  if (process.env[name]) return "env";
  for (const backend of backends()) {
    let found = false;
    try {
      found = await backend.holds(name);
    } catch (error) {
      if (error instanceof PyCrash) throw error;
      found = false;
    }
    if (found) return backend === fileBackend ? "file" : "credential_store";
  }
  return "none";
}

/** 从每个后端删除；返回删掉了的后端名。 */
export async function removeSecret(name: string): Promise<string[]> {
  checkName(name);
  const removed: string[] = [];
  for (const backend of backends()) {
    try {
      if (await backend.remove(name)) removed.push(backend.name);
    } catch {
      continue;
    }
  }
  return removed;
}

/** secrets.describe：名字、来源、凭据库模式、系统后端名与文件目录。 */
export async function describeSecret(name: string): Promise<PyDict> {
  const mode = storeMode();
  const system = mode === "system" ? systemBackend() : null;
  return new Map<string, PyValue>([
    ["name", name],
    ["source", await source(name)],
    ["store_mode", mode],
    ["system_backend", system === null ? null : system.name],
    ["file_dir", secretsDir()],
  ]);
}
