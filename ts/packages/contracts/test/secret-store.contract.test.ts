// codekit/secrets.py 里配置中心用到的部分的契约（迁移第 ③a2 片）：source、describe、remove、凭据名的检查。
// 只用测试专用的名字（THEMIS_CONTRACT_ 开头）与合成的假值，值不出现在断言与输出里。凭据库：file 模式在临时的
// XDG_CONFIG_HOME 下往返；system 模式只读一个随机的、不存在的测试目标（应当得到 none），不往 Windows 凭据管理器里写
// （要站主同意，见迁移计划第 ③ 步）。
import { mkdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { IMPLS, type ProbeRequest, type ProbeResult, removeDir, runAgreeing, runBatch, scratchDir } from "./harness.ts";

const ROOT = scratchDir("secret-store");
afterAll(() => removeDir(ROOT));
const NAME = `THEMIS_CONTRACT_${randomBytes(6).toString("hex").toUpperCase()}`;
const FAKE = "0123456789abcdef"; // 合成的假值：形状像凭据，不是任何真实凭据

const call = (fn: string, name: string, env: Record<string, string | null>): ProbeRequest => ({ op: "secret_store.call", fn, name, env });

interface Case {
  readonly name: string;
  readonly request: ProbeRequest;
  readonly check: (result: ProbeResult) => string | null;
}

const tagged = (result: ProbeResult): unknown => {
  const value = result["value"] as { t: string; v?: unknown } | undefined;
  if (value?.t === "list") return (value.v as { v: string }[]).map((item) => item.v);
  if (value?.t === "dict") return Object.fromEntries((value.v as [{ v: string }, { t: string; v?: unknown }][]).map(([key, item]) => [key.v, item.t === "none" ? null : item.v]));
  return value?.v;
};
const gives = (name: string, request: ProbeRequest, expected: unknown): Case => ({
  name,
  request,
  check: (result) => (result.ok && JSON.stringify(tagged(result)) === JSON.stringify(expected) ? null : JSON.stringify(result)),
});
const fails = (name: string, request: ProbeRequest, error: string): Case => ({ name, request, check: (result) => (result["error"] === error ? null : JSON.stringify(result)) });

function verifyAll(cases: readonly Case[]): void {
  const { python, mismatches } = runAgreeing(cases.map((item) => item.request));
  const wrong = cases.flatMap((item, index) => {
    const problem = item.check(python[index] as ProbeResult);
    return problem === null ? [] : [{ name: item.name, python: problem }];
  });
  expect(wrong, "Python 的结果不符合契约").toEqual([]);
  expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
}

describe("凭据库：source、describe、remove", () => {
  it("file 模式的往返、off 模式、system 模式只读不存在的测试目标", () => {
    const home = join(ROOT, "config-home");
    const dir = join(home, "code-kit", "secrets");
    mkdirSync(dir, { recursive: true });
    const file = (name: string): string => join(dir, name);
    const fileMode = { CODEKIT_SECRET_STORE: "file", XDG_CONFIG_HOME: home, [NAME]: null };
    writeFileSync(file(`${NAME}_A`), `${FAKE}\n`);
    writeFileSync(file(`${NAME}_BLANK`), " \n\t");
    writeFileSync(file(`${NAME}_BAD`), Buffer.from([0x61, 0xff]));
    mkdirSync(file(`${NAME}_DIR`));
    symlinkSync(file(`${NAME}_A`), file(`${NAME}_LINK`), "file");
    const messy = `${home.replaceAll("\\", "/")}//./`;
    verifyAll([
      gives("文件里有值", call("source", `${NAME}_A`, fileMode), "file"),
      gives("文件只有空白", call("source", `${NAME}_BLANK`, fileMode), "none"),
      fails("文件不是合法 UTF-8（Python 打堆栈）", call("source", `${NAME}_BAD`, fileMode), "UnicodeDecodeError"),
      gives("同名的是目录", call("source", `${NAME}_DIR`, fileMode), "none"),
      gives("同名的是符号链接", call("source", `${NAME}_LINK`, fileMode), "none"),
      gives("环境变量优先", call("source", `${NAME}_A`, { ...fileMode, [`${NAME}_A`]: FAKE }), "env"),
      gives("off 模式只认环境变量", call("source", `${NAME}_A`, { ...fileMode, CODEKIT_SECRET_STORE: " OFF " }), "none"),
      gives("模式认不出时按 system", call("describe", NAME, { ...fileMode, CODEKIT_SECRET_STORE: "bogus" }), {
        name: NAME,
        source: "none",
        store_mode: "system",
        system_backend: "windows-credential-manager",
        file_dir: dir,
      }),
      gives("XDG_CONFIG_HOME 照 pathlib 规整", call("describe", NAME, { ...fileMode, XDG_CONFIG_HOME: messy }), {
        name: NAME,
        source: "none",
        store_mode: "file",
        system_backend: null,
        file_dir: dir,
      }),
      gives("没有 XDG_CONFIG_HOME 时在用户目录的 .config 下", call("describe", NAME, { CODEKIT_SECRET_STORE: "off", XDG_CONFIG_HOME: null, USERPROFILE: home }), {
        name: NAME,
        source: "none",
        store_mode: "off",
        system_backend: null,
        file_dir: join(home, ".config", "code-kit", "secrets"),
      }),
      gives("system 模式：凭据管理器里没有这个测试目标", call("source", NAME, { CODEKIT_SECRET_STORE: "system", XDG_CONFIG_HOME: home, [NAME]: null }), "none"),
      gives("system 模式删不存在的测试目标", call("remove", NAME, { CODEKIT_SECRET_STORE: "system", XDG_CONFIG_HOME: home }), []),
    ]);
    rmSync(file(`${NAME}_LINK`));
  });

  it("删除会改磁盘：每套实现各删自己的一份，结果相同（删掉了 file，再删一次什么也没删）", () => {
    const home = join(ROOT, "remove-home");
    const dir = join(home, "code-kit", "secrets");
    mkdirSync(dir, { recursive: true });
    const env = { CODEKIT_SECRET_STORE: "file", XDG_CONFIG_HOME: home };
    const results = IMPLS.map((impl) => {
      writeFileSync(join(dir, `${NAME}_GONE`), FAKE);
      return runBatch(impl, [call("remove", `${NAME}_GONE`, env), call("remove", `${NAME}_GONE`, env)]).map(tagged);
    });
    for (const result of results) expect(result).toEqual([["file"], []]);
  });

  it("凭据名的检查", () => {
    const off = { CODEKIT_SECRET_STORE: "off" };
    verifyAll([
      gives("Unicode 字母算 isalnum", call("check_name", "éT١_", off), "éT١_"),
      fails("数字开头", call("check_name", "1X", off), "SecretError"),
      fails("Unicode 数字开头", call("check_name", "١X", off), "SecretError"),
      fails("带连字符", call("check_name", "A-B", off), "SecretError"),
      fails("空串", call("check_name", "", off), "SecretError"),
      gives("正好 128 个码点", call("check_name", "é".repeat(128), off), "é".repeat(128)),
      fails("129 个码点", call("check_name", "A".repeat(129), off), "SecretError"),
      fails("describe 也先查名字", call("describe", "A B", off), "SecretError"),
    ]);
  });
});
