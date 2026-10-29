// profile 表单的内核原式校验（合同第三节）：ID、凭据变量名与模型两段的正则，加「只传改动字段」的数组比较。
// 正则照 scripts/pi_dispatch.py 的 TASK_ID_RE / ENV_NAME_RE 与服务侧 validModel / validCredentialEnv：
// 表单不放过内核不认的值（不合法的取值不调 preview）。

// ID：TASK_ID_RE ^[a-z0-9][a-z0-9-]{0,63}$（首字符不能是连字符，最长 64 个字符）。
const ID_RE = /^[a-z0-9][a-z0-9-]{0,63}$/;
// 凭据变量名：ENV_NAME_RE ^[A-Za-z_][A-Za-z0-9_]{0,127}$（不能以数字开头，最长 128 个字符）。
const ENV_NAME_RE = /^[A-Za-z_][A-Za-z0-9_]{0,127}$/;
// 模型两段：在第一个 / 处切开，两段都过这个（provider/model，各段只能用字母、数字与 . _ : / @ + -）。
const MODEL_SEGMENT_RE = /^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$/;

export function validId(id: string): boolean {
  return ID_RE.test(id);
}

export function validEnvName(name: string): boolean {
  return ENV_NAME_RE.test(name);
}

/** 模型：在第一个 / 处切成两段，两段都过 MODEL_SEGMENT_RE 才算合法。 */
export function validModel(model: string): boolean {
  const slash = model.indexOf('/');
  if (slash < 0) return false;
  return MODEL_SEGMENT_RE.test(model.slice(0, slash)) && MODEL_SEGMENT_RE.test(model.slice(slash + 1));
}

/** 两个字符串数组是否按顺序完全相同（凭据变量改动检测用）。 */
export function sameStringArray(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((v, i) => v === b[i]);
}
