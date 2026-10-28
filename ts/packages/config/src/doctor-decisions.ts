// doctor 的 decisions 块（迁移第 ④b7d 片）：pi_dispatch._doctor_decisions 与 describe_decisions。决策的配置、凭据与会话都在
// 本包，dispatcher 不依赖本包，所以由 cli 把它交给 cmdDoctor。
//   - 决策模块是否在：照 Python 的 import，看 kit 的 scripts/codekit/decisions.py 在不在（第 ⑥ 步撤掉 Python 时再改）。
//   - --probe-decisions 会联网、会花钱：只在用户批准后使用；契约只对本机的假端点用它。
import { statSync } from "node:fs";
import type { PyDict, PyValue } from "@themis/base/pyjson";
import { purePathStr } from "@themis/base/pypath";
import { ConfigSecretError, repoConfig } from "@themis/dispatcher/kernel-config";
import { DispatchError, Repo } from "@themis/dispatcher/repo";
import { DecisionError, type Settings, batteryLinkProblem, settingsActive, settingsFromConfig, settingsOfficial } from "./decisions.ts";
import { decisionsPluginDir, describe, probe } from "./decisions-client.ts";
import { secretConfigError } from "./secret-config.ts";

const BT = String.fromCharCode(96);

/**
 * _doctor_decisions：生效模式与原因、凭据环境变量名与是否已设置（只记布尔值）、清单摘要（2.6.0）。probeDecisions 另外发
 * 一次最小请求，在它真正运行的地方验证环境变量可见、端点应答、回复形状与本工具一致。
 */
export async function doctorDecisions(
  kitRoot: string, repoArg: string | null, probeDecisions: boolean, facts: PyDict, problems: string[], notes: string[],
): Promise<void> {
  const invalid = (problem: string): void => {
    facts.set("decisions", new Map([["mode", "off"], ["reason", "config_invalid"]]));
    problems.push(problem);
  };
  if (!isFile(purePathStr(kitRoot, "scripts", "codekit", "decisions.py"))) {
    facts.set("decisions", new Map([["mode", "off"], ["reason", "module_missing"]]));
    notes.push("决策模块不可用：scripts/codekit/decisions.py 不在本工具旁边，决策功能等同 off");
    return;
  }
  let config: PyDict = new Map();
  let agentDir: string | null = null;
  try {
    const repo = Repo.discover(repoArg);
    config = repoConfig(repo);
    agentDir = repo.agentDir;
  } catch (error) {
    if (error instanceof ConfigSecretError) return invalid(error.message); // 照实报告，不当作没有配置（D9）
    if (!(error instanceof DispatchError)) throw error;
  }
  const secret = secretConfigError(config, "decisions");
  if (secret !== null) return invalid(`dispatch.config.json 的 decisions 无效：${secret}`); // 与 decisions_session 相同：有疑似凭据就不解析
  let settings: Settings;
  try {
    settings = settingsFromConfig(config, agentDir, decisionsPluginDir(kitRoot));
  } catch (error) {
    if (!(error instanceof DecisionError)) throw error;
    return invalid(`dispatch.config.json 的 decisions 无效：${error.detail}`);
  }
  const described = await describeDecisions(settings, kitRoot);
  const fact = (key: string): PyValue => described.get(key) ?? null;
  // 键名避开 redact_obj 会遮蔽的“api_key”写法：这里记的是环境变量的名字与有无，不是值。
  const decisions: PyDict = new Map<string, PyValue>([
    ["mode", fact("mode")], ["configured_mode", fact("configured_mode")], ["reason", fact("reason")],
    ["env_var_name", fact("api_key_env")], ["env_var_set", fact("api_key_set")],
    ["secret_source", fact("api_key_source")], ["secret_store_mode", fact("secret_store_mode")],
    ["base_url", fact("base_url")], ["official_endpoint", fact("official_endpoint")],
    ["model", fact("model")], ["points", fact("points")], ["marker_present", fact("marker_present")],
    ["plugin_dir", fact("plugin_dir")], ["batteries", fact("batteries")],
    ["battery_lock", fact("battery_lock")], ["sdk_reference", fact("sdk_reference")],
  ]);
  facts.set("decisions", decisions);
  problems.push(...(fact("battery_problems") as string[]).map((item) => `决策插件的问题清单无效：${item}`));
  const active = settingsActive(settings);
  const noSecret = fact("api_key_source") === "none";
  if (settings.configured_mode !== "off" && !active) notes.push(`决策配置为 ${settings.configured_mode}，实际生效 off：${settings.reason}`);
  if (active && noSecret) {
    const effect = settingsOfficial(settings) ? "每次调用都会记为无意见（no_key）" : "自定义端点将不带凭据头调用";
    notes.push(`决策模式为 ${settings.mode}，但凭据 ${settings.api_key_env} 既不在环境变量也不在凭据库里：${effect}` +
      `（用 ${BT}config secret set ${settings.api_key_env}${BT} 存入）`);
  }
  if (active) notes.push(`决策功能生效（${settings.mode}）：先用 shadow 记录对照 verdict 与复审记录（decisions replay），再决定开 on`);
  if (!probeDecisions) {
    decisions.set("probe", null);
  } else if (settingsOfficial(settings) && noSecret) {
    problems.push(`--probe-decisions：凭据 ${settings.api_key_env} 既不在环境变量也不在凭据库里，无法探测`);
  } else {
    const result = await probe(settings);
    decisions.set("probe", result);
    if (!result.get("ok")) {
      const detail = result.get("detail");
      problems.push(`决策探测失败：${String(result.get("reason"))}${detail ? `（${String(detail)}）` : ""}`);
    }
  }
}

/** describe_decisions：问题清单经过链接时不读它，battery_lock 记 link。 */
async function describeDecisions(settings: Settings, kitRoot: string): Promise<PyDict> {
  const pluginDir = decisionsPluginDir(kitRoot);
  const link = batteryLinkProblem(kitRoot, pluginDir);
  if (link === null) return describe(settings, pluginDir);
  const described = await describe(settings, null);
  described.set("plugin_dir", pluginDir);
  described.set("battery_lock", "link");
  described.set("battery_problems", [`问题清单经过链接，不读取：${link}`]);
  return described;
}

function isFile(file: string): boolean {
  try {
    return statSync(file).isFile();
  } catch {
    return false;
  }
}
