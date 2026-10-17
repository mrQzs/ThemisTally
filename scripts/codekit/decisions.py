"""决策模型（Jev）的受信任客户端：类型化问题、校验过的回答、脱敏的出站边界、一切 fail-open（2.6.0）。

调度器把“便宜但要判断”的事交给它：报告里哪句自述没有证据、漏掉的变异是不是等价改写、运行中的执行器
是在推进还是卡住。它只给意见，不是门禁的依赖：G0–G6、verdict、mutate 的计数、check 的退出码都不读它。

接口形状照 TypeSafe 的 System One API（POST /v1/systemone）：``state`` 加 ``questions``，三种原语
``choice``（选项映射，最多 255 个）、``score``（2–10 个有序等级）、``noul``（是/否，可选 ``criteria``
``{true, false}``）；回答按所问的问题逐条校验：概率键集合等于选项集合、和为 1、``choice`` 必须是最大项、
score 的均值与分布一致。校验不过的回答是“无意见”，不是“勉强用”。

出站边界：发出去的每个字符串先过 ``redact``；整个 state 看起来含凭据时不发（``is_sensitive``）；凭据只认
配置里的环境变量名，值只在构造请求头时读一次；记录里不存 state 原文，只存 sha256、字符数与脱敏次数。

只依赖标准库。官方 Python SDK（typesafe-sdk）的常量抄在 SDK_REFERENCE 里只作对照，不作依赖。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import http.client
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

DEFAULT_BASE_URL = "https://api.typesafe.ai"
ENDPOINT_PATH = "/v1/systemone"
#: 钉版本号：官方文档说 jev-latest / jev-preview 会随新版本移动，调过阈值的要钉版本。
DEFAULT_MODEL = "jev-1.13.0"
DEFAULT_API_KEY_ENV = "TYPESAFE_API_KEY"
DEFAULT_TIMEOUT_SECONDS = 4.0
DEFAULT_BUDGET_SECONDS = 20.0
DEFAULT_MAX_STATE_CHARS = 20000
MAX_RESPONSE_BYTES = 1_000_000
MAX_CHOICE_OPTIONS = 255
SCORE_LEVELS = (2, 10)
QUESTION_TYPES = ("choice", "score", "noul")
MODES = ("off", "shadow", "on")
#: 存在就等于 off，无论配置怎么写；一个 ls 就能证明（hermes-jev-skills 的三次“配置键默认 off”事故）。
OFF_MARKER = "DECISIONS_OFF"
POINTS = ("report-screen", "mutation-equivalence", "run-health")
PLUGIN_ID = "decisions"
PERMISSION = "network-decisions"
USER_AGENT = "code-kit-decisions/2.8.0"
#: 官方定价：每百万输入 token 0.042 美元，输出免费（models 页，2026-10-12）。
PRICE_USD_PER_MILLION_INPUT = 0.042
#: 官方 Python SDK 的常量，只作对照（sdk/python/api/constants、retries 页，2026-10-12）。
SDK_REFERENCE = {
    "package": "typesafe-sdk", "python": ">=3.10", "api_key_env": "TYPESAFE_API_KEY",
    "base_url_env": "TYPESAFE_BASE_URL", "default_model_env": "TYPESAFE_DEFAULT_MODEL",
    "default_model": "jev-latest", "default_timeout_seconds": 10.0,
    "retry": {"max_retries": 2, "budget_seconds": 30.0, "statuses": "408, 429, 500-599",
              "backoff": "0.5s doubled to 5s, jitter 0.25, honours Retry-After"},
}
RETRYABLE = frozenset({"rate_limited", "overloaded", "network", "http_500", "http_502", "http_503", "http_504"})
PROBABILITY_SUM_TOLERANCE = 0.01 + 1e-12
SCORE_MEAN_TOLERANCE = 0.02 + 1e-12
ARGMAX_TOLERANCE = 1e-9
#: 问题清单里除线上字段之外允许的键（给人看的）。
QUESTION_EXTRA_KEYS = ("label",)
BATTERY_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")

Transport = Callable[[bytes, Dict[str, str], float, str], bytes]


class DecisionError(RuntimeError):
    """任何“不要信、不要用这个结果”的情况。code 是机器可读的原因。"""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__("%s: %s" % (code, detail) if detail else code)
        self.code = code
        self.detail = detail


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# 问题的形状
# ---------------------------------------------------------------------------

def _identifier(text: Any) -> str:
    return re.sub(r"[\W_]+", " ", str(text).lower()).strip()


def _shown(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    return text if len(text) <= 80 else text[:77] + "..."


def _content(value: Any) -> bool:
    """instructions / criteria 的值：字符串、对象或数组（API 文档的 JSONContent）。"""
    return isinstance(value, (str, dict, list))


def check_question(name: str, question: Any) -> Dict[str, Any]:
    """一个问题的线上形状；不合的以 ValueError 指出是哪个问题、缺什么（调用方的 bug，不花一次往返）。"""
    if not isinstance(question, Mapping):
        raise ValueError('question "%s" must be an object like {"type": ..., "instructions": ...}' % _shown(name))
    unknown = set(question) - {"type", "instructions", "criteria"} - set(QUESTION_EXTRA_KEYS)
    if unknown:
        raise ValueError('question "%s" has unknown keys %s' % (_shown(name), sorted(unknown)))
    kind = question.get("type")
    if kind not in QUESTION_TYPES:
        raise ValueError('question "%s" has type %r; use one of %s' % (_shown(name), kind, ", ".join(QUESTION_TYPES)))
    text = question.get("instructions")
    if not isinstance(text, str) or not text.strip():
        raise ValueError('question "%s" has no instructions: the text of the question, as a string' % _shown(name))
    if _identifier(text) == _identifier(name):
        raise ValueError('question "%s" asks nothing: its instructions only repeat its own name' % _shown(name))
    criteria = question.get("criteria")
    if kind == "noul":
        if criteria is not None:
            if not isinstance(criteria, Mapping) or set(criteria) - {"true", "false"} or not criteria:
                raise ValueError('question "%s" is a noul: criteria can only be {"true": ..., "false": ...}' % _shown(name))
            if any(not _content(value) for value in criteria.values()):
                raise ValueError('question "%s": noul criteria must be text, objects or arrays' % _shown(name))
        out: Dict[str, Any] = {"type": "noul", "instructions": text}
        if criteria is not None:
            out["criteria"] = dict(criteria)
        return out
    if kind == "choice":
        if not isinstance(criteria, Mapping) or len(criteria) < 2:
            raise ValueError('question "%s": a choice needs an object of at least two options' % _shown(name))
        if len(criteria) > MAX_CHOICE_OPTIONS:
            raise ValueError('question "%s": a choice takes at most %d options' % (_shown(name), MAX_CHOICE_OPTIONS))
        if any(not isinstance(key, str) or not key for key in criteria) or any(
                value is not None and not _content(value) for value in criteria.values()):
            raise ValueError('question "%s": choice options map names to descriptions (or null)' % _shown(name))
        return {"type": "choice", "instructions": text, "criteria": dict(criteria)}
    if not isinstance(criteria, list) or not SCORE_LEVELS[0] <= len(criteria) <= SCORE_LEVELS[1]:
        raise ValueError('question "%s": a score needs a list of %d to %d levels, lowest first'
                         % (_shown(name), SCORE_LEVELS[0], SCORE_LEVELS[1]))
    if any(not _content(level) for level in criteria):
        raise ValueError('question "%s": score levels must be text, objects or arrays' % _shown(name))
    return {"type": "score", "instructions": text, "criteria": list(criteria)}


def check_questions(questions: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    if not isinstance(questions, Mapping) or not questions:
        raise ValueError("questions must be a non-empty mapping of {name: question}")
    return {str(name): check_question(str(name), question) for name, question in questions.items()}


def noul(instructions: str, true: Optional[str] = None, false: Optional[str] = None) -> Dict[str, Any]:
    question: Dict[str, Any] = {"type": "noul", "instructions": instructions}
    if true is not None or false is not None:
        question["criteria"] = {"true": true, "false": false}
    return check_question("noul", question)


def choice(instructions: str, options: Mapping[str, Any]) -> Dict[str, Any]:
    return check_question("choice", {"type": "choice", "instructions": instructions, "criteria": dict(options)})


def score(instructions: str, levels: Sequence[Any]) -> Dict[str, Any]:
    return check_question("score", {"type": "score", "instructions": instructions, "criteria": list(levels)})


# ---------------------------------------------------------------------------
# 出站边界：脱敏与“整段不发”
# ---------------------------------------------------------------------------

_SECRET_WORDS = re.compile(
    r"(?i)(api[_ -]?key|access[_ -]?token|authorization\s*:|bearer\s+[a-z0-9._-]{8,}|password|passwd|"
    r"client[_ -]?secret|session[_ -]?cookie|private[_ -]?key|BEGIN [A-Z ]*PRIVATE KEY)")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b[A-Z][A-Z0-9]*(?:[_-][A-Z0-9]+)*[_-]"
    r"(?:SECRET|SECRET[_-]?\w*KEY|API[_-]?KEY|KEY|TOKEN|PASSWORD|PASSWD|CREDENTIALS?|AUTH)\b\s*[:=]\s*\S*")
_TOKEN_SHAPES = re.compile(
    r"\b(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|"
    r"AIza[0-9A-Za-z_-]{30,}|apikey_[A-Za-z0-9_]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,})\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_INTL_PHONE = re.compile(r"(?<![\d+])\+\d{1,3}[\s.-]?(?:\d[\s.-]?){7,13}\d(?!\d)")
_LONG_HEX = re.compile(r"\b[a-fA-F0-9]{40,}\b")
_HIGH_ENTROPY = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/_-]{40,}={0,2}(?![A-Za-z0-9+/=_-])")


def normalize(text: str) -> str:
    """折叠形近与不可见字符，免得用 Unicode 绕过规则。"""
    folded = unicodedata.normalize("NFKC", text)
    return "".join(c for c in folded if unicodedata.category(c) not in {"Cf", "Cc"} or c in "\n\t")


def is_sensitive(text: str) -> bool:
    """看起来含凭据：整段不发，调用方走 fail-open。"""
    probe = normalize(text)
    return bool(_SECRET_WORDS.search(probe) or _SECRET_ASSIGNMENT.search(probe) or _TOKEN_SHAPES.search(probe))


def _mask_credential(match: "re.Match[str]") -> str:
    run = match.group(0)
    mixed = any(c.isupper() for c in run) and any(c.islower() for c in run) and any(c.isdigit() for c in run)
    return "[secret]" if mixed else run


def redact(text: str, limit: int = 4000) -> str:
    """遮住令牌形状、疑似凭据的赋值（保留变量名）、长 hex、高熵串、邮箱与国际电话；过长时取头尾。"""
    out = normalize(text)
    out = _TOKEN_SHAPES.sub("[secret]", out)
    out = _SECRET_ASSIGNMENT.sub(lambda m: re.split(r"[:=]", m.group(0), maxsplit=1)[0].rstrip() + "=[secret]", out)
    out = _LONG_HEX.sub("[hex]", out)
    out = _HIGH_ENTROPY.sub(_mask_credential, out)
    out = _EMAIL.sub("[email]", out)
    out = _INTL_PHONE.sub("[phone]", out)
    if len(out) > limit:
        half = limit // 2
        out = out[:half] + "\n[...]\n" + out[-half:]
    return out


def redact_state(value: Any, limit: int = 6000) -> Tuple[Any, int]:
    """递归脱敏 state 里的每个字符串；返回（脱敏后的值, 改动过的字符串个数）。"""
    changed = 0
    if isinstance(value, str):
        out = redact(value, limit)
        return out, int(out != value)
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for key, item in value.items():
            result[str(key)], n = redact_state(item, limit)
            changed += n
        return result, changed
    if isinstance(value, (list, tuple)):
        items = []
        for item in value:
            out, n = redact_state(item, limit)
            items.append(out)
            changed += n
        return items, changed
    return value, 0


# ---------------------------------------------------------------------------
# 问题清单（插件资源 plugins/decisions/questions/<point>.json）
# ---------------------------------------------------------------------------

def load_battery(path: Path) -> Dict[str, Any]:
    """读一份问题清单：id、version、questions（线上形状）、thresholds（0..1 或正数）、给人看的 label。"""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DecisionError("battery_unreadable", "%s: %s" % (path, exc))
    if not isinstance(raw, dict):
        raise DecisionError("battery_invalid", "%s: top level must be an object" % path)
    unknown = set(raw) - {"id", "version", "description", "state_fields", "questions", "thresholds"}
    if unknown:
        raise DecisionError("battery_invalid", "%s: unknown keys %s" % (path, sorted(unknown)))
    if not isinstance(raw.get("id"), str) or not BATTERY_ID_RE.match(raw["id"]):
        raise DecisionError("battery_invalid", "%s: id must match %s" % (path, BATTERY_ID_RE.pattern))
    if not isinstance(raw.get("version"), str) or not VERSION_RE.match(raw["version"]):
        raise DecisionError("battery_invalid", "%s: version must be an exact semantic version" % path)
    try:
        questions = check_questions(raw.get("questions"))
    except ValueError as exc:
        raise DecisionError("battery_invalid", "%s: %s" % (path, exc))
    thresholds = raw.get("thresholds", {})
    if not isinstance(thresholds, dict) or any(
            not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(float(value)) or float(value) < 0 for key, value in thresholds.items()):
        raise DecisionError("battery_invalid", "%s: thresholds must map names to non-negative numbers" % path)
    labels = {name: str(question.get("label") or name) for name, question in raw["questions"].items()}
    return {"id": raw["id"], "version": raw["version"], "description": raw.get("description", ""),
            "state_fields": list(raw.get("state_fields", [])), "questions": questions, "labels": labels,
            "thresholds": {key: float(value) for key, value in thresholds.items()},
            "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(), "path": str(path)}


def load_batteries(root: Path) -> Dict[str, Dict[str, Any]]:
    """目录下全部清单，按 id 索引；文件名必须等于 id。"""
    root = Path(root)
    if not root.is_dir():
        raise DecisionError("plugin_missing", "no battery directory at %s" % root)
    found: Dict[str, Dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        battery = load_battery(path)
        if battery["id"] != path.stem:
            raise DecisionError("battery_invalid", "%s: file name must equal the battery id %s" % (path, battery["id"]))
        found[battery["id"]] = battery
    return found


# ---------------------------------------------------------------------------
# 内容锁（2.8.0）：运行时只用锁里记着的问题清单
# ---------------------------------------------------------------------------

def _plugin_records():
    """codekit/plugins.py：规范 JSON 与锁校验的唯一实现。以脚本方式运行本文件时也能找到它。"""
    try:
        from . import plugins as module  # type: ignore[no-redef]
    except ImportError:
        if __package__:  # 作为 codekit 包的一部分导入：plugins.py 就是不在
            raise
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from codekit import plugins as module  # type: ignore[no-redef]
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_battery_lock(plugin_dir: Path) -> Dict[str, str]:
    """问题清单与插件的 manifest / lock 一致（2.8.0）。返回 {清单文件名: sha256}。

    锁自身的摘要、锁与 manifest 的绑定由 codekit/plugins.py 的 validate_lock 核对；这里再核对
    questions/ 下每份清单的字节与锁里同一路径的 sha256 相同，目录里多出或缺少的清单都算不符。
    不符时抛 DecisionError("battery_drift")：问题清单是插件资源，改了就要重算锁
    （``decisions.py --write-lock <插件目录>``），否则运行时问的不是复审过的那一份。
    """
    plugin_dir = Path(plugin_dir)
    try:
        manifest = json.loads((plugin_dir / "manifest.json").read_text(encoding="utf-8"))
        lock = json.loads((plugin_dir / "lock.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DecisionError("battery_drift", "plugin manifest or lock unreadable: %s" % exc)
    try:
        records = _plugin_records()
    except ImportError as exc:
        raise DecisionError("battery_drift", "codekit/plugins.py is missing: %s" % exc)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("plugin_id"), str):
        raise DecisionError("battery_drift", "plugin manifest has no plugin_id")
    try:
        records.validate_lock(lock, {manifest["plugin_id"]: manifest})
    except records.PluginError as exc:
        raise DecisionError("battery_drift", "lock does not verify: %s" % exc)
    prefix = "plugins/%s/questions/" % manifest["plugin_id"]
    locked = {ref["path"][len(prefix):]: ref["sha256"] for ref in manifest["resources"]
              if ref.get("kind") == "file" and ref["path"].startswith(prefix)}
    present = sorted(path.name for path in (plugin_dir / "questions").glob("*.json"))
    problems = ["%s is not in the lock" % name for name in present if name not in locked]
    problems += ["%s is locked but missing" % name for name in sorted(locked) if name not in present]
    for name in present:
        if name not in locked:
            continue
        data = (plugin_dir / "questions" / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != locked[name]:
            crlf = (chr(13) + chr(10)).encode()
            only_eol = hashlib.sha256(data.replace(crlf, chr(10).encode())).hexdigest() == locked[name]
            problems.append("%s differs from the locked bytes%s" % (
                name, " only in line endings (checked out with CRLF; .gitattributes keeps plugins/decisions/** -text)"
                if only_eol else ""))
    if problems:
        raise DecisionError("battery_drift", "; ".join(problems)
                            + "; after a reviewed change run: python scripts/codekit/decisions.py --write-lock "
                            + str(plugin_dir))
    return locked


def load_locked_batteries(plugin_dir: Path) -> Dict[str, Dict[str, Any]]:
    """运行时的入口（2.8.0）：先核对内容锁，再读清单，读到的字节也要等于锁里的。"""
    locked = verify_battery_lock(plugin_dir)
    batteries = load_batteries(Path(plugin_dir) / "questions")
    for battery in batteries.values():
        name = Path(battery["path"]).name
        if locked.get(name) != battery["sha256"]:
            raise DecisionError("battery_drift", "%s changed while it was being read" % name)
    return batteries


def write_lock(plugin_dir: Path) -> str:
    """改过问题清单之后重算 manifest 的资源哈希与锁（2.8.0；原先是规划端临时目录里的生成脚本）。

    资源是 README.md（有就记）加 questions/*.json，id 为 ``<plugin_id>.readme`` 与 ``<plugin_id>.<文件名>``；
    manifest 的其余字段不动，锁的 compiler_sha256 与 generation 沿用旧锁。写之前先校验每份清单的形状，
    写完再核对一遍。返回新锁的 lock_sha256。
    """
    plugin_dir = Path(plugin_dir).resolve()
    records = _plugin_records()
    manifest_path, lock_path = plugin_dir / "manifest.json", plugin_dir / "lock.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    previous = json.loads(lock_path.read_text(encoding="utf-8"))
    load_batteries(plugin_dir / "questions")
    base = "plugins/%s/" % manifest["plugin_id"]
    resources: List[Dict[str, str]] = []
    if (plugin_dir / "README.md").is_file():
        resources.append({"kind": "file", "id": manifest["plugin_id"] + ".readme", "path": base + "README.md",
                          "sha256": _sha256(plugin_dir / "README.md")})
    for path in sorted((plugin_dir / "questions").glob("*.json")):
        resources.append({"kind": "file", "id": "%s.%s" % (manifest["plugin_id"], path.stem),
                          "path": base + "questions/" + path.name, "sha256": _sha256(path)})
    manifest["resources"] = resources
    normalized = records.validate_manifest(manifest)
    lock = records.build_lock([normalized], compiler_sha256=previous["compiler_sha256"],
                              generation=previous["generation"])
    for path, data in ((manifest_path, manifest), (lock_path, lock)):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + chr(10),
                        encoding="utf-8", newline=chr(10))
    verify_battery_lock(plugin_dir)
    return lock["lock_sha256"]


# ---------------------------------------------------------------------------
# 配置与模式
# ---------------------------------------------------------------------------

class Settings:
    """``dispatch.config.json`` 的 ``decisions`` 对象解析后的结果，加上实际生效的模式与原因。"""

    def __init__(self) -> None:
        self.mode = "off"
        self.configured_mode = "off"
        self.reason = "not_configured"
        self.api_key_env = DEFAULT_API_KEY_ENV
        self.base_url = DEFAULT_BASE_URL
        self.model = DEFAULT_MODEL
        self.timeout_seconds = DEFAULT_TIMEOUT_SECONDS
        self.budget_seconds = DEFAULT_BUDGET_SECONDS
        self.max_state_chars = DEFAULT_MAX_STATE_CHARS
        self.points: List[str] = list(POINTS)
        self.marker_present = False

    @property
    def active(self) -> bool:
        return self.mode != "off"

    @property
    def official(self) -> bool:
        return self.base_url == DEFAULT_BASE_URL

    def as_dict(self) -> Dict[str, Any]:
        return {"mode": self.mode, "configured_mode": self.configured_mode, "reason": self.reason,
                "api_key_env": self.api_key_env, "base_url": self.base_url, "model": self.model,
                "timeout_seconds": self.timeout_seconds, "budget_seconds": self.budget_seconds,
                "max_state_chars": self.max_state_chars, "points": list(self.points),
                "marker_present": self.marker_present}


def _check_base_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError:
        raise DecisionError("config", "decisions.base_url is not a URL")
    loopback = parsed.hostname in ("127.0.0.1", "::1", "localhost")
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or (parsed.path not in ("", "/")) or port == 0
            or (parsed.scheme == "http" and not loopback)):
        raise DecisionError("config", "decisions.base_url must be https://host[:port] or http://127.0.0.1:port")
    return value.rstrip("/")


def settings_from_config(config: Mapping[str, Any], agent_dir: Optional[Path] = None,
                         plugin_dir: Optional[Path] = None) -> Settings:
    """解析配置并判定生效的模式。配置写错是 DecisionError('config')，调用方当用法错误报告。

    生效模式的判定顺序：标记文件存在 → off（marker）；``plugins.enabled`` 存在却没有 ``decisions``，或
    ``plugins.allowed_permissions`` 存在却没有 ``network-decisions`` → off（plugin_disabled / permission_missing）；
    插件目录不存在 → off（plugin_missing）；否则就是配置的模式。凭据是否存在不改变模式：缺 key 在调用时
    记为无意见（no_key），doctor 会提前说明。
    """
    settings = Settings()
    raw = config.get("decisions") if isinstance(config, Mapping) else None
    configured = raw is not None
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise DecisionError("config", "decisions must be an object")
    unknown = set(raw) - {"mode", "api_key_env", "base_url", "model", "timeout_seconds", "budget_seconds",
                          "max_state_chars", "points"}
    if unknown:
        raise DecisionError("config", "decisions has unknown keys %s" % sorted(unknown))
    mode = raw.get("mode", "off")
    if mode not in MODES:
        raise DecisionError("config", "decisions.mode must be one of %s" % ", ".join(MODES))
    settings.configured_mode = mode
    env_name = raw.get("api_key_env", DEFAULT_API_KEY_ENV)
    if not isinstance(env_name, str) or not ENV_NAME_RE.match(env_name):
        raise DecisionError("config", "decisions.api_key_env must be an environment variable name")
    settings.api_key_env = env_name
    base = raw.get("base_url", DEFAULT_BASE_URL)
    if not isinstance(base, str):
        raise DecisionError("config", "decisions.base_url must be a string")
    settings.base_url = _check_base_url(base)
    if not settings.official and settings.api_key_env == DEFAULT_API_KEY_ENV:
        # 自定义端点不得收到官方凭据：换端点就要换一个自己的环境变量名（可以不设）。
        raise DecisionError("config", "a custom decisions.base_url needs its own decisions.api_key_env "
                                      "(never the official %s)" % DEFAULT_API_KEY_ENV)
    model = raw.get("model", DEFAULT_MODEL)
    if not isinstance(model, str) or not re.match(r"^[A-Za-z0-9][A-Za-z0-9._:/~-]{0,99}$", model):
        raise DecisionError("config", "decisions.model is not a model id")
    settings.model = model
    for key, default, low, high in (("timeout_seconds", DEFAULT_TIMEOUT_SECONDS, 0.5, 60.0),
                                    ("budget_seconds", DEFAULT_BUDGET_SECONDS, 1.0, 600.0)):
        value = raw.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= float(value) <= high:
            raise DecisionError("config", "decisions.%s must be a number between %s and %s" % (key, low, high))
        setattr(settings, key, float(value))
    chars = raw.get("max_state_chars", DEFAULT_MAX_STATE_CHARS)
    if isinstance(chars, bool) or not isinstance(chars, int) or not 500 <= chars <= 120000:
        raise DecisionError("config", "decisions.max_state_chars must be an integer between 500 and 120000")
    settings.max_state_chars = chars
    points = raw.get("points", list(POINTS))
    if not isinstance(points, list) or any(point not in POINTS for point in points) or len(set(points)) != len(points):
        raise DecisionError("config", "decisions.points must list distinct names from %s" % ", ".join(POINTS))
    settings.points = list(points)
    settings.mode = mode
    settings.reason = "configured" if mode != "off" else ("configured_off" if configured else "not_configured")
    if agent_dir is not None and (Path(agent_dir) / OFF_MARKER).exists():
        settings.marker_present = True
        settings.mode, settings.reason = "off", "marker"
        return settings
    plugins = config.get("plugins") if isinstance(config, Mapping) else None
    if isinstance(plugins, Mapping):
        enabled = plugins.get("enabled")
        if isinstance(enabled, list) and PLUGIN_ID not in enabled:
            settings.mode, settings.reason = "off", "plugin_disabled"
            return settings
        allowed = plugins.get("allowed_permissions")
        if isinstance(allowed, list) and PERMISSION not in allowed:
            settings.mode, settings.reason = "off", "permission_missing"
            return settings
    if settings.mode != "off" and plugin_dir is not None and not (Path(plugin_dir) / "questions").is_dir():
        settings.mode, settings.reason = "off", "plugin_missing"
    return settings


# ---------------------------------------------------------------------------
# 传输与回复校验
# ---------------------------------------------------------------------------

def http_transport(body: bytes, headers: Dict[str, str], timeout: float, url: str) -> bytes:
    """一个 POST，不跟随重定向（重定向会把凭据带去别的主机），状态码映射成原因码。"""
    parsed = urllib.parse.urlsplit(url)
    connection_type = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = connection_type(parsed.hostname or "", parsed.port, timeout=timeout)
    try:
        try:
            connection.request("POST", parsed.path or "/", body=body, headers=headers)
            response = connection.getresponse()
            status = response.status
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (http.client.HTTPException, OSError) as exc:
            if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower():
                raise DecisionError("timeout", str(exc))
            raise DecisionError("network", exc.__class__.__name__)
    finally:
        try:
            connection.close()
        except Exception:  # noqa: BLE001
            pass
    if len(raw) > MAX_RESPONSE_BYTES:
        raise DecisionError("response_too_large")
    if status != 200:
        code = {401: "auth_failed", 403: "auth_failed", 402: "credits_exhausted", 422: "invalid_request",
                429: "rate_limited", 529: "overloaded"}.get(status, "http_%d" % status)
        detail = ""
        if status == 422:
            detail = redact(raw.decode("utf-8", "replace"), 300)
        raise DecisionError(code, detail)
    return raw


def _invalid(name: str, invariant: str, detail: str = "") -> DecisionError:
    error = DecisionError("invalid_response", "answer %s violated %s%s" % (name, invariant, " (%s)" % detail if detail else ""))
    error.invariant = invariant  # type: ignore[attr-defined]
    return error


def _unit(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DecisionError("malformed", "%s is not numeric" % name)
    number = float(value)
    if not math.isfinite(number) or not -1e-6 <= number <= 1 + 1e-6:
        raise DecisionError("malformed", "%s is outside 0..1" % name)
    return min(1.0, max(0.0, number))


def _distribution(name: str, raw: Any, keys: Sequence[str], invariant: str) -> Dict[str, float]:
    if not isinstance(raw, dict):
        raise _invalid(name, invariant, "probabilities are not an object")
    expected, found = set(keys), set(raw)
    if found != expected:
        raise _invalid(name, invariant, "missing %s, unexpected %s"
                       % (sorted(expected - found) or "none", sorted(found - expected) or "none"))
    values = {key: _unit(raw[key], "%s.p[%s]" % (name, key)) for key in keys}
    total = sum(values.values())
    if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
        raise _invalid(name, invariant, "mass sums to %r" % total)
    return values


def check_answer(name: str, question: Mapping[str, Any], answer: Any) -> Dict[str, Any]:
    """按所问的问题校验一条回答；自相矛盾的回答是 invalid_response，不是“勉强可用”。"""
    if not isinstance(answer, dict) or answer.get("type") != question["type"]:
        raise DecisionError("malformed", "answer %s has the wrong type" % name)
    kind = question["type"]
    if kind == "noul":
        return {"type": "noul", "noul": _unit(answer.get("noul"), "%s.noul" % name)}
    if kind == "choice":
        options = list(question["criteria"])
        picked = answer.get("choice")
        if not isinstance(picked, str) or picked not in set(options):
            raise DecisionError("malformed", "answer %s chose an option that was not offered" % name)
        probabilities = _distribution(name, answer.get("probabilities"), options, "choice_probability_key_set")
        top = max(probabilities.values())
        if probabilities[picked] < top - ARGMAX_TOLERANCE:
            raise _invalid(name, "choice_is_argmax", "chose %s at %r against a maximum of %r"
                           % (picked, probabilities[picked], top))
        return {"type": "choice", "choice": picked, "probabilities": probabilities,
                "confidence": _unit(answer.get("confidence"), "%s.confidence" % name)}
    levels = len(question["criteria"])
    value = answer.get("score")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise DecisionError("malformed", "answer %s has no numeric score" % name)
    if not -0.5 <= float(value) <= levels - 0.5:
        raise DecisionError("malformed", "answer %s scored off the rubric" % name)
    raw = answer.get("probabilities")
    spread: Dict[int, float] = {}
    if isinstance(raw, dict) and raw:
        keys = []
        for key in raw:
            if not str(key).isdigit() or int(key) >= levels:
                raise _invalid(name, "score_distribution_on_rubric", "level %r is not 0..%d" % (key, levels - 1))
            keys.append(str(key))
        spread = {int(key): prob for key, prob in
                  _distribution(name, raw, sorted(keys, key=int), "score_distribution_mass").items()}
        mean = sum(level * probability for level, probability in spread.items())
        if abs(mean - float(value)) > SCORE_MEAN_TOLERANCE:
            raise _invalid(name, "score_matches_its_distribution",
                           "score %r against an expected value of %r" % (float(value), mean))
    legend = {}
    if isinstance(answer.get("legend"), dict):
        legend = {int(key): str(text) for key, text in answer["legend"].items()
                  if str(key).isdigit() and int(key) < levels and isinstance(text, str)}
    out = {"type": "score", "score": float(value), "probabilities": spread, "spread_reported": bool(spread),
           "confidence": _unit(answer.get("confidence", 1.0), "%s.confidence" % name), "levels": levels}
    if legend:
        out["legend"] = legend
    return out


def noul_confidence(p: float) -> float:
    """noul 没有 confidence 字段；官方文档建议 |2p-1|（就是二选一的 choice 公式）。"""
    return abs(2.0 * p - 1.0)


# ---------------------------------------------------------------------------
# 会话：模式、时钟预算、记录
# ---------------------------------------------------------------------------

class Session:
    """一条调度命令里的决策调用：共享时钟预算，记录追加到一个 decisions.jsonl。

    ``ask`` 永远返回一个结果对象，从不抛异常（配置错误在构造 Settings 时就已拒绝）：``status`` 是
    ``answered`` 或 ``no_opinion``，后者带 ``reason``。off 模式下不调用、不记录。
    """

    def __init__(self, settings: Settings, record_path: Optional[Path] = None, *,
                 transport: Optional[Transport] = None, environ: Optional[Mapping[str, str]] = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.settings = settings
        self.record_path = Path(record_path) if record_path else None
        self.transport = transport or http_transport
        self.environ = environ if environ is not None else os.environ
        self.clock = clock
        self.spent_seconds = 0.0
        self.calls = 0
        self.answered = 0
        self.input_tokens = 0
        self.records: List[Dict[str, Any]] = []

    @property
    def active(self) -> bool:
        return self.settings.active

    @property
    def mode(self) -> str:
        return self.settings.mode

    def _no_opinion(self, result: Dict[str, Any], reason: str, detail: str = "") -> Dict[str, Any]:
        result.update(status="no_opinion", reason=reason)
        if detail:
            result["detail"] = detail[:300]
        return result

    def _record(self, result: Dict[str, Any]) -> None:
        self.records.append(result)
        if self.record_path is None:
            return
        try:
            self.record_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.record_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError:
            pass  # 记录失败不能影响命令本身

    def ask(self, battery: Mapping[str, Any], state: Any, context: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        settings = self.settings
        result: Dict[str, Any] = {"at": utc_now(), "point": battery["id"], "battery_version": battery["version"],
                                  "battery_sha256": battery["sha256"], "mode": settings.mode,
                                  "model": settings.model, "status": "no_opinion", "reason": "",
                                  "answers": {}, "latency_ms": 0, "usage": {},
                                  "context": dict(context or {})}
        if not settings.active:
            return self._no_opinion(result, "off:" + settings.reason)
        if battery["id"] not in settings.points:
            return self._no_opinion(result, "point_disabled")
        redacted, redactions = redact_state(state)
        try:
            encoded = json.dumps(redacted, ensure_ascii=False, separators=(",", ":"), default=str)
        except (TypeError, ValueError) as exc:
            result.update(state_chars=0)
            self._record(self._no_opinion(result, "state_not_json", str(exc)))
            return result
        result.update(state_sha256=hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                      state_chars=len(encoded), redactions=redactions)
        if len(encoded) > settings.max_state_chars:
            self._record(self._no_opinion(result, "state_too_large"))
            return result
        if is_sensitive(encoded):
            self._record(self._no_opinion(result, "sensitive"))
            return result
        remaining = settings.budget_seconds - self.spent_seconds
        if remaining <= 0.1:
            self._record(self._no_opinion(result, "budget"))
            return result
        key = self.environ.get(settings.api_key_env) or _stored_secret(settings.api_key_env) or ""
        if settings.official and not key:
            self._record(self._no_opinion(result, "no_key"))
            return result
        wire = {name: {k: v for k, v in question.items() if k in ("type", "instructions", "criteria")}
                for name, question in battery["questions"].items()}
        body = json.dumps({"state": redacted, "model": settings.model, "questions": wire},
                          ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": USER_AGENT}
        if key:
            headers["Authorization"] = "Bearer " + key
        url = settings.base_url + ENDPOINT_PATH
        started = self.clock()
        self.calls += 1
        attempt = 0
        try:
            while True:
                left = min(settings.timeout_seconds, remaining - (self.clock() - started))
                if left <= 0.05:
                    raise DecisionError("timeout", "budget exhausted")
                try:
                    raw = self.transport(body, headers, left, url)
                    break
                except DecisionError as error:
                    attempt += 1
                    if error.code not in RETRYABLE or attempt > 1:
                        raise
                    time.sleep(min(0.25, max(0.0, remaining - (self.clock() - started) - 0.1)))
            try:
                payload = json.loads(raw)
            except (UnicodeDecodeError, ValueError):
                raise DecisionError("malformed", "reply is not JSON")
            answers = payload.get("answers") if isinstance(payload, dict) else None
            if not isinstance(answers, dict):
                raise DecisionError("malformed", "reply has no answers")
            checked = {name: check_answer(name, question, answers.get(name))
                       for name, question in battery["questions"].items()}
        except DecisionError as error:
            self.spent_seconds += self.clock() - started
            result["latency_ms"] = int((self.clock() - started) * 1000)
            self._record(self._no_opinion(result, error.code, error.detail))
            return result
        elapsed = self.clock() - started
        self.spent_seconds += elapsed
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        tokens = usage.get("input_tokens")
        if isinstance(tokens, int) and not isinstance(tokens, bool):
            self.input_tokens += tokens
        self.answered += 1
        result.update(status="answered", reason="", answers=checked, latency_ms=int(elapsed * 1000),
                      usage={k: v for k, v in usage.items() if k in ("input_tokens", "output_tokens")},
                      served_model=payload.get("model") if isinstance(payload.get("model"), str) else None)
        self._record(result)
        return result


# ---------------------------------------------------------------------------
# 给调用方的小工具
# ---------------------------------------------------------------------------

def read_records(path: Path) -> List[Dict[str, Any]]:
    """读一份 decisions.jsonl；坏行跳过。"""
    records: List[Dict[str, Any]] = []
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return records
    for line in lines:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def latest_by_point(records: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for item in records:
        point = item.get("point")
        if isinstance(point, str):
            latest[point] = dict(item)
    return latest


def answer_value(answer: Mapping[str, Any]) -> Tuple[str, float]:
    """一条回答的可读形式：(文本, 置信度)。noul 的置信度按 |2p-1|。"""
    kind = answer.get("type")
    if kind == "noul":
        p = float(answer.get("noul", 0.0))
        return "p=%.2f" % p, noul_confidence(p)
    if kind == "choice":
        return str(answer.get("choice")), float(answer.get("confidence", 0.0))
    return "%.2f/%d" % (float(answer.get("score", 0.0)), int(answer.get("levels", 0)) - 1), float(answer.get("confidence", 0.0))


def usage_totals(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    calls = len(records)
    answered = sum(1 for r in records if r.get("status") == "answered")
    tokens = sum(int((r.get("usage") or {}).get("input_tokens") or 0) for r in records
                 if isinstance((r.get("usage") or {}).get("input_tokens"), int))
    reasons: Dict[str, int] = {}
    for item in records:
        if item.get("status") != "answered":
            reasons[str(item.get("reason"))] = reasons.get(str(item.get("reason")), 0) + 1
    return {"calls": calls, "answered": answered, "no_opinion": calls - answered, "input_tokens": tokens,
            "estimated_cost_usd": round(tokens * PRICE_USD_PER_MILLION_INPUT / 1_000_000, 8),
            "no_opinion_reasons": reasons}


def _stored_secret(name: str) -> Optional[str]:
    """环境变量没有时问凭据库（2.7.0，codekit/secrets.py）；值只在这里经过一次。进程级开关 CODEKIT_SECRET_STORE。"""
    try:
        from . import secrets as store
    except ImportError:  # pragma: no cover - the module sits next to this one
        return None
    try:
        return store.resolve(name)
    except (store.SecretError, OSError):
        return None


def _secret_source(name: str, environ: Mapping[str, str]) -> str:
    if environ.get(name):
        return "env"
    try:
        from . import secrets as store
        return store.source(name)
    except (ImportError, OSError):  # pragma: no cover
        return "none"


def describe(settings: Settings, plugin_dir: Optional[Path], environ: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """给 doctor 的事实：生效模式与原因、凭据环境变量名、是否已设置与来源（只记名字与来源）、清单摘要、SDK 对照。"""
    environ = environ if environ is not None else os.environ
    facts = settings.as_dict()
    facts["api_key_set"] = bool(environ.get(settings.api_key_env))
    facts["api_key_source"] = _secret_source(settings.api_key_env, environ)
    try:
        from . import secrets as store
        facts["secret_store_mode"] = store.store_mode()
    except ImportError:  # pragma: no cover
        facts["secret_store_mode"] = None
    facts["official_endpoint"] = settings.official
    facts["plugin_dir"] = str(plugin_dir) if plugin_dir else None
    batteries: List[Dict[str, Any]] = []
    problems: List[str] = []
    facts["battery_lock"] = None
    if plugin_dir and (Path(plugin_dir) / "questions").is_dir():
        try:
            verify_battery_lock(Path(plugin_dir))
            facts["battery_lock"] = "ok"
        except DecisionError as exc:
            facts["battery_lock"] = "drift"
            problems.append(str(exc))
        try:
            for battery in load_batteries(Path(plugin_dir) / "questions").values():
                batteries.append({"id": battery["id"], "version": battery["version"], "sha256": battery["sha256"],
                                  "questions": sorted(battery["questions"]), "thresholds": battery["thresholds"]})
        except DecisionError as exc:
            problems.append(str(exc))
    facts["batteries"] = batteries
    facts["battery_problems"] = problems
    facts["sdk_reference"] = SDK_REFERENCE
    return facts


def probe(settings: Settings, *, transport: Optional[Transport] = None,
          environ: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """一次最小请求（一个 noul，几十个 token）：会联网、会花钱，只在用户批准后由 doctor --probe-decisions 调用。"""
    battery = {"id": "probe", "version": "1.0.0", "sha256": "0" * 64,
               "questions": {"ok": noul("The text reports that every test passed.")}}
    probe_settings = Settings()
    probe_settings.__dict__.update(settings.__dict__)
    probe_settings.mode, probe_settings.reason, probe_settings.points = "shadow", "probe", ["probe"]
    session = Session(probe_settings, None, transport=transport, environ=environ)
    result = session.ask(battery, "The build finished and all 12 tests passed.")
    return {"ok": result["status"] == "answered", "reason": result.get("reason", ""),
            "detail": result.get("detail", ""), "latency_ms": result.get("latency_ms"),
            "served_model": result.get("served_model"), "usage": result.get("usage"),
            "answer": result["answers"].get("ok", {}).get("noul") if result["status"] == "answered" else None}


def main(argv: Optional[Sequence[str]] = None) -> int:
    """``python scripts/codekit/decisions.py --check-battery <目录或文件>...``：校验问题清单（插件的确定性检查）。

    ``--check-lock <插件目录>`` 核对清单与内容锁一致；``--write-lock <插件目录>`` 在复审过的改动之后重算锁（2.8.0）。
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 2 and args[0] in ("--check-lock", "--write-lock"):
        try:
            if args[0] == "--write-lock":
                print("OK    lock written %s" % write_lock(Path(args[1]))[:12])
            else:
                print("OK    %d batteries match the lock" % len(verify_battery_lock(Path(args[1]))))
        except (DecisionError, OSError, ValueError, KeyError) as exc:
            print("ERROR %s" % exc)
            return 1
        return 0
    if not args or args[0] != "--check-battery" or len(args) < 2:
        print("usage: decisions.py --check-battery <directory or file>... | --check-lock <plugin dir> "
              "| --write-lock <plugin dir>", file=sys.stderr)
        return 2
    failures = 0
    for target in args[1:]:
        path = Path(target)
        try:
            batteries = load_batteries(path) if path.is_dir() else {load_battery(path)["id"]: load_battery(path)}
        except DecisionError as exc:
            print("ERROR %s" % exc)
            failures += 1
            continue
        for battery in batteries.values():
            print("OK    %s %s (%d questions) %s" % (battery["id"], battery["version"], len(battery["questions"]),
                                                     battery["sha256"][:12]))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
