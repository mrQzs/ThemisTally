// pi_dispatch 的仓库相对路径模式与保护名单（迁移第 ④b1 片）：glob_regex、compile_patterns、matches、pattern_error。
// glob 照 Python 拼成同样的正则文字（re.escape 用 3.12 的转义表），交给 @themis/base 的 sre 移植编译：IGNORECASE 下
// ſ、K、É 一类的大小写等价与 Python 一致。matches 是 fullmatch，写成 \A(?:…)\Z（不能用 $：它会放过末尾的换行）。
import { type SearchPattern, compilePattern } from "@themis/base/pyregex";
import type { PyValue } from "@themis/base/pyjson";

const BS = String.fromCharCode(92);
/** re.escape 在 3.12 里转义的字符（_special_chars_map）。 */
const RE_SPECIAL = new Set([..."()[]{}?*+-|^$.&~# ", BS, ...[9, 10, 13, 11, 12].map((code) => String.fromCharCode(code))]);

/** 调度器运行时实际加载的 kit 文件：目标仓库把 kit 复制进 scripts/ 时，它们与调度器本身一样受保护。 */
export const KIT_LOADED_FILES = [
  "scripts/kit_config.py", "scripts/kit_logs.py", "scripts/kit_plugins.py", "scripts/kit_roles.py",
  "scripts/codekit/__init__.py", "scripts/codekit/decisions.py",
  "scripts/codekit/secrets.py", "scripts/codekit/plugins.py", "scripts/codekit/planner.py",
  "scripts/codekit/planner_protocol.py", "scripts/codekit/protocols.py", "plugins/decisions/**",
];
/** 执行器永远不得修改的路径：合同、证据、代理规则与调度器本身（不区分大小写匹配）。 */
export const PROTECTED_PATTERNS = [
  ".agent/**", ".claude/**", ".codex/**", ".pi/**", ".agents/**", ".gitmodules",
  "**/AGENTS.md", "**/AGENTS.override.md", "**/CLAUDE.md", "**/CLAUDE.local.md",
  "scripts/pi_dispatch.py", "scripts/dispatch-pi.sh", "scripts/kernel-impl.json",
  ...KIT_LOADED_FILES,
];
/** TS 进入生产路径之后、被检查的仓库就是内核自己所在的仓库时，执行器也不得修改的路径（kernel_protected_paths）。 */
export const KERNEL_TS_PROTECTED = [
  "ts/package.json", "ts/bun.lock", "ts/bunfig.toml", "ts/tsconfig.json", "ts/vitest.config.ts", "ts/tools/**",
  "ts/mutations/**", "ts/packages/base/**", "ts/packages/cli/**", "ts/packages/config/**",
  "ts/packages/contracts/**", "ts/packages/dispatcher/**", "ts/packages/hub/**",
];
export const DEPENDENCY_PATTERNS = [
  "**/package.json", "**/package-lock.json", "**/npm-shrinkwrap.json", "**/pnpm-lock.yaml",
  "**/pnpm-workspace.yaml", "**/yarn.lock", "**/bun.lock", "**/bun.lockb", "**/.npmrc",
  "**/requirements*.txt", "**/pyproject.toml", "**/poetry.lock", "**/uv.lock", "**/Pipfile",
  "**/Pipfile.lock", "**/setup.py", "**/setup.cfg", "**/go.mod", "**/go.sum", "**/Cargo.toml",
  "**/Cargo.lock", "**/Gemfile", "**/Gemfile.lock", "**/composer.json", "**/composer.lock",
  "**/pom.xml", "**/build.gradle", "**/build.gradle.kts", "**/gradle.lockfile",
  "**/*.csproj", "**/packages.lock.json", "**/Directory.Packages.props",
];
export const SENSITIVE_PATTERNS = [
  ".github/**", ".gitlab-ci.yml", ".gitignore", "**/.gitattributes", "**/Makefile", "**/Dockerfile*",
  "**/.env*", "**/tsconfig*.json", "**/vitest.config.*", "**/vite.config.*", "**/jest.config.*",
  "**/karma.conf.*", "**/playwright.config.*", "**/cypress.config.*", "**/pytest.ini",
  "**/conftest.py", "**/tox.ini", "**/noxfile.py", "**/.eslintrc*", "**/eslint.config.*",
  "**/.prettierrc*", "**/biome.json", "**/ruff.toml", "**/.coveragerc",
];

/** re.escape(text)。 */
export function reEscape(text: string): string {
  let out = "";
  for (const char of text) out += RE_SPECIAL.has(char) ? BS + char : char;
  return out;
}

/** glob_regex 拼出的正则文字：* 匹配单层，** 匹配任意层级，? 匹配单个字符；按码点走。 */
export function globRegexText(pattern: string): string {
  const chars = Array.from(pattern);
  const at = (index: number, text: string): boolean => chars.slice(index, index + text.length).join("") === text;
  let out = "";
  let index = 0;
  while (index < chars.length) {
    const char = chars[index] as string;
    if (at(index, "**/")) {
      out += "(?:[^/]+/)*";
      index += 3;
    } else if (at(index, "**")) {
      out += ".*";
      index += 2;
    } else if (char === "*") {
      out += "[^/]*";
      index += 1;
    } else if (char === "?") {
      out += "[^/]";
      index += 1;
    } else {
      out += reEscape(char);
      index += 1;
    }
  }
  return out;
}

/** glob_regex(pattern, ignore_case) 编译后的 fullmatch。 */
export function globRegex(pattern: string, ignoreCase = false): SearchPattern {
  return compilePattern(`${ignoreCase ? "(?i)" : ""}${BS}A(?:${globRegexText(pattern)})${BS}Z`);
}

export function compilePatterns(patterns: readonly string[], ignoreCase = false): SearchPattern[] {
  return patterns.map((pattern) => globRegex(pattern, ignoreCase));
}

/** matches：任一模式整串匹配。 */
export function matches(compiled: readonly SearchPattern[], path: string): boolean {
  return compiled.some((regex) => regex.test(path));
}

export function hasControlChars(text: string): boolean {
  return Array.from(text).some((char) => {
    const code = char.codePointAt(0) as number;
    return code < 32 || code === 127;
  });
}

/** pattern_error：仓库相对路径模式不合法的原因，合法时为 null。 */
export function patternError(pattern: PyValue | undefined): string | null {
  if (typeof pattern !== "string" || !pattern) return "必须是非空字符串";
  if (hasControlChars(pattern)) return "包含控制字符";
  if (pattern.includes(BS)) return "请使用正斜杠";
  if (pattern.startsWith("/") || /^[A-Za-z]:/u.test(pattern) || pattern.startsWith("~")) return "不能是绝对路径";
  if (pattern.split("/").some((part) => part === "" || part === "." || part === "..")) return "不能包含空段、'.' 或 '..'";
  if (pattern === "*" || pattern === "**" || pattern === "**/*") return "范围过宽";
  return null;
}
