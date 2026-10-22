// 契约 Schema 的校验器（第 ② 步起）：Ajv2020、strict，迁移计划第 3.2 节的条件。Schema 放在 contracts/schemas/；
// 仓库根的 schemas/ 是离线 v2 的参考件，只用来确认在 strict 下能编译，不往里加东西。
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Ajv2020, type ValidateFunction } from "ajv/dist/2020.js";

const HERE = dirname(fileURLToPath(import.meta.url));
export const CONTRACT_SCHEMAS = resolve(HERE, "..", "schemas");
export const REPO_SCHEMAS = resolve(HERE, "..", "..", "..", "..", "schemas");

export function newAjv(): Ajv2020 {
  return new Ajv2020({ strict: true, allErrors: true });
}

const ajv = newAjv();
const cache = new Map<string, ValidateFunction>();

/** contracts/schemas/<name>.schema.json 编译好的校验函数。 */
export function contractSchema(name: string): ValidateFunction {
  let validate = cache.get(name);
  if (validate === undefined) {
    validate = ajv.compile(JSON.parse(readFileSync(join(CONTRACT_SCHEMAS, `${name}.schema.json`), "utf8")) as object);
    cache.set(name, validate);
  }
  return validate;
}

/** 校验不过时把 Ajv 的报错拼成一行，断言失败时看得出是哪个字段。 */
export function schemaErrors(name: string, value: unknown): string[] {
  const validate = contractSchema(name);
  return validate(value) ? [] : (validate.errors ?? []).map((error) => `${error.instancePath || "/"} ${error.message ?? ""}`);
}
