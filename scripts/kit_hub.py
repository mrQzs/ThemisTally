#!/usr/bin/env python3
"""七端信箱（3.0 第三轮）：以协调人为中心的星型信箱、按信唤醒的后台工人、由内核校验的阶段状态机。

设计：docs/themis-tally-3.0-r3-七端与信箱.md（边跑边改）。

- 信箱在 .agent/mailbox/（Git 忽略），只有本内核写；工人的工作目录是 worktree，看不到它。
- 一封信唤醒一个回合：claude 工人 `claude -p --session-id/--resume`，pi 工人 `pi --session-id`。回合结束时工人在最后一条
  消息里交出一个 ```json 代码块；内核审计回合（白名单之外的 tool_use / server_tool_use 一律作废）、校验信件、按状态机
  核对前置条件之后，才以工人的名义投递（设计 §3.3：工人不自己调 mail-send）。
- 执行端与 JEV 端由内核代办：前者走调度器的 prepare / run / check，后者调决策 API（shadow 语义，门禁不读）。
- 状态只由本内核写：ledger/events.jsonl（只追加）与 ledger/state.json（投影）。

子命令：init、task new、send、take、run、status。只依赖标准库。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pi_dispatch as pd  # noqa: E402

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_BLOCKED = 0, 1, 2, 3
MAILBOX = Path(".agent") / "mailbox"
TEMPLATE_DIR = HERE / "hub"
OWNER = "站主"
KERNEL = "内核"
COORDINATOR = "womovie-c8"
#: 发信人的 ASCII 别名：只用在 msg-id 与文件名里，信件正文照写中文名。
SENDER_ALIAS = {OWNER: "owner", KERNEL: "kernel"}
WORKER_TYPES = ("交付", "返工完成", "提问", "阻塞", "交接", "进度")
COORDINATOR_TYPES = ("开工", "返工", "通过", "等待", "停止", "汇报", "提问")
OWNER_TYPES = ("任务", "回复", "停止")
KERNEL_TYPES = ("核验", "阻塞")
#: 发给工人时只登记、不唤醒（每唤醒一次就是一个付费回合）。
INFO_TYPES = ("通过", "等待", "停止")
FIELDS = ("摘要", "提交", "验证", "偏离", "需协调人决定", "证据")
VERDICT_FIELDS = ("结论", "退回", "阻塞项")
KERNEL_FIELDS = ("内核核验",)
KNOWN_FIELDS = FIELDS + VERDICT_FIELDS + KERNEL_FIELDS
MAX_BODY_LINES = 40
VERDICTS = ("通过", "返工")
STAGES = (
    ("1-plan", "planner-opus"),
    ("2-contract", "contract-glm"),
    ("3-gate-pre", "gate-sonnet"),
    ("3j-jev", "jev-judge"),
    ("4-audit-pre", "audit-sonnet"),
    ("5-exec", "exec-step"),
    ("6-gate-post", "gate-sonnet"),
    ("6j-jev", "jev-judge"),
    ("7-audit-post", "audit-sonnet"),
)
STAGE_ORDER = tuple(suffix for suffix, _ in STAGES)
STAGE_WORKER = dict(STAGES)
#: 阶段之间的数据依赖：上游重新交付，下游（传递闭包）的结论一律作废。JEV 只依赖它评的那一份交付。
DEPENDS = {
    "1-plan": (), "2-contract": ("1-plan",), "3-gate-pre": ("2-contract",), "3j-jev": ("2-contract",),
    "4-audit-pre": ("3-gate-pre", "3j-jev"), "5-exec": ("4-audit-pre",), "6-gate-post": ("5-exec",),
    "6j-jev": ("5-exec",), "7-audit-post": ("6-gate-post", "6j-jev"),
}
#: 交付通过后由内核接着跑的 JEV（用户 2026-10-19 同意，不为 JEV 单独唤醒协调人）。
AUTO_JEV = {"2-contract": "3j-jev", "6-gate-post": "6j-jev"}
#: 审核端“退回”的对象 → 阶段。
#: “门禁端”指基准测试本身有错（走热修补）；“战后门禁”指白盒测试或变异清单不够，重做战后门禁。
RETURN_TARGETS = {"合同端": "2-contract", "门禁端": "3-gate-pre", "战后门禁": "6-gate-post", "执行端": "5-exec",
                  "规划端": "1-plan"}
MAIN_TASK_RE = re.compile(r"^T\d{3,6}$")
STAGE_TASK_RE = re.compile(r"^(T\d{3,6})-(%s)$" % "|".join(re.escape(s) for s in STAGE_ORDER))
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
JSON_BLOCK_RE = re.compile(r"```json[ \t]*\r?\n(.*?)\r?\n[ \t]*```", re.S)
FIELD_LINE_RE = re.compile(r"^(\S+?)[:：][ \t]?(.*)$")
PENDING_MARK_RE = re.compile(r"待(?:站主|协调人)?(?:确认|拍板|决定)")
#: 回合输入超过这个长度就写进文件，命令行只给路径（Windows 命令行上限约 32K 字符）。
MAX_INLINE_PROMPT = 20000
#: 只有内核调决策 API 时需要它；工人与调度器子进程一律拿不到。
DECISIONS_KEY_ENV = "TYPESAFE_API_KEY"
#: 工人进程不继承的会话变量：让 hub 无论从哪里启动，工人的行为都一样。
WORKER_ENV_DROP = (DECISIONS_KEY_ENV, "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT")
CLAUDE_SETTINGS = {"autoMemoryEnabled": False, "advisorModel": ""}

ROSTER: Dict[str, Dict[str, Any]] = {
    # 协调人 high（原为 max；用户 2026-10-19 同意降档：T001 里每回合 1–4.5 分钟，大头是 max 档的思考输出）
    COORDINATOR: {"role": "coordinator", "label": "调度代理端（协调人）", "adapter": "claude",
                  "model": "claude-haiku-5-5", "effort": "high", "tools": ["Read", "Grep", "Glob"],
                  "timeout": 1200, "workspace": "base"},
    "planner-opus": {"role": "planner", "label": "规划端", "adapter": "claude", "model": "claude-opus-5-5",
                     "effort": "max", "tools": ["Read", "Grep", "Glob"], "timeout": 2400, "workspace": "base"},
    "contract-glm": {"role": "contract", "label": "合同端", "adapter": "pi", "provider": "cc-switch-zhipu-glm",
                     "model": "glm-5.3", "thinking": "max", "tools": ["read", "grep", "find", "ls"],
                     "timeout": 2400, "workspace": "base"},
    "gate-sonnet": {"role": "gate", "label": "门禁端", "adapter": "claude", "model": "claude-sonnet-5-5",
                    "effort": "high", "tools": ["Read", "Grep", "Glob", "Edit", "Write", "Bash"],
                    "allowed_rules": ["Bash(python -m pytest:*)"], "timeout": 2400, "workspace": "stage"},
    "audit-sonnet": {"role": "audit", "label": "审核端", "adapter": "claude", "model": "claude-sonnet-5-5",
                     "effort": "max", "tools": ["Read", "Grep", "Glob"], "timeout": 2400, "workspace": "stage"},
    # provider 是本机 pi 登记的名字，要与 `pi --list-models` 和 .agent/environment.md 一致（旧机器上是 bb）。
    "exec-step": {"role": "exec", "label": "执行端", "adapter": "dispatcher", "provider": "step",
                  "model": "step-5-preview", "thinking": "high"},
    "jev-judge": {"role": "jev", "label": "JEV 端", "adapter": "jev"},
}
WORKERS = tuple(name for name in ROSTER if name != COORDINATOR)
EXECUTOR = tuple(ROSTER["exec-step"][key] for key in ("provider", "model", "thinking"))
CONTRACT_EXECUTOR_LINE = "- executor: %s/%s · thinking %s" % EXECUTOR


#: 本次进程载入的内核代码的哈希（载入时算一次）：运行中改了源文件，记录里的仍是正在跑的那一份。
HUB_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class HubError(Exception):
    def __init__(self, message: str, code: int = EXIT_FAIL) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_compact() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> Optional[str]:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def write_text_atomic(path: Path, text: str) -> None:
    """整份替换：独立的临时文件写完再 os.replace，读者只会看到旧版或新版。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / ("%s.%s.tmp" % (path.name, os.urandom(6).hex()))
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(str(tmp), str(path))


def read_text(path: Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def keep_previous(path: Path) -> None:
    """要覆盖的 brief.md、report.md 先改名留档：brief.1.md、brief.2.md……"""
    if path.exists():
        index = len(list(path.parent.glob("%s.*%s" % (path.stem, path.suffix)))) + 1
        os.replace(str(path), str(path.with_name("%s.%d%s" % (path.stem, index, path.suffix))))


def stage_of(task_id: str) -> Tuple[Optional[str], Optional[str]]:
    """'T001-3-gate-pre' → ('T001', '3-gate-pre')；'T001' → ('T001', None)；其他 → (None, None)。"""
    match = STAGE_TASK_RE.match(task_id or "")
    if match:
        return match.group(1), match.group(2)
    if MAIN_TASK_RE.match(task_id or ""):
        return task_id, None
    return None, None


def worker_env(config: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """工人进程的环境：调度器的过滤（推送类凭据、仓库重定向变量、配置的 env_remove）之外，
    再去掉决策 API 的 key 与宿主会话变量。"""
    env, _removed = pd.child_env(config or {})
    for name in list(env):
        if name.upper() in WORKER_ENV_DROP:
            env.pop(name)
    return env


#: 内核自己在工人的工作目录里跑 pytest：不写字节码与缓存，免得把工作区弄脏、干扰“只新增一个文件”的核对。
KERNEL_PYTEST = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider"]


def kernel_pytest_env() -> Dict[str, str]:
    env = worker_env()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def kernel_env() -> Dict[str, str]:
    """内核调起的调度器子进程：只去掉决策 API 的 key（调度器自己的决策提问本来就是 off）。"""
    env = dict(os.environ)
    for name in list(env):
        if name.upper() == DECISIONS_KEY_ENV:
            env.pop(name)
    return env


# ---------------------------------------------------------------------------
# 信件
# ---------------------------------------------------------------------------

def new_msg_id(sender: str) -> str:
    alias = SENDER_ALIAS.get(sender, sender)
    return "%s-%s-%s" % (utc_compact(), alias, os.urandom(3).hex())


def render_letter(meta: Dict[str, str], fields: Dict[str, str]) -> str:
    lines = ["---"]
    for key in ("msg-id", "from", "to", "task-id", "in-reply-to", "type"):
        lines.append("%s: %s" % (key, meta.get(key, "")))
    lines.append("---")
    ordered = [k for k in KNOWN_FIELDS if k in fields] + [k for k in fields if k not in KNOWN_FIELDS]
    for key in ordered:
        value = str(fields[key]).strip() or "无"
        parts = value.splitlines()
        lines.append("%s: %s" % (key, parts[0]))
        lines.extend("  " + part for part in parts[1:])
    return "\n".join(lines) + "\n"


def parse_letter(text: str) -> Tuple[Dict[str, str], Dict[str, str], int]:
    """解析信件：返回 (头部, 正文字段, 正文行数)。不认识的行接到上一个字段后面（续行）。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise HubError("信件要以 --- 开头")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise HubError("信件头部没有结束的 ---")
    meta: Dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    body = [line for line in lines[end + 1:]]
    while body and not body[-1].strip():
        body.pop()
    fields: Dict[str, str] = {}
    current: Optional[str] = None
    for line in body:
        match = FIELD_LINE_RE.match(line)
        if match and match.group(1) in KNOWN_FIELDS:
            current = match.group(1)
            fields[current] = match.group(2).strip()
        elif current is not None:
            fields[current] = (fields[current] + "\n" + line[2:] if line.startswith("  ") else
                               fields[current] + "\n" + line).strip("\n")
    return meta, fields, len(body)


def letter_errors(meta: Dict[str, str], fields: Dict[str, str], body_lines: int) -> List[str]:
    """形状校验（不看状态）：头部齐全、类型与发信人相符、正文六个字段都在、不超过 40 行。"""
    errors: List[str] = []
    for key in ("from", "to", "task-id", "in-reply-to", "type"):
        if not meta.get(key):
            errors.append("头部缺 %s" % key)
    sender, kind = meta.get("from", ""), meta.get("type", "")
    allowed = (OWNER_TYPES if sender == OWNER else COORDINATOR_TYPES if sender == COORDINATOR
               else KERNEL_TYPES if sender == KERNEL else WORKER_TYPES if sender in WORKERS else ())
    if not allowed:
        errors.append("发信人 %s 不在名册里" % sender)
    elif kind not in allowed:
        errors.append("%s 不能发 %s（可以发：%s）" % (sender, kind or "空类型", " | ".join(allowed)))
    receiver = meta.get("to", "")
    if receiver and receiver not in ROSTER and receiver != OWNER:
        errors.append("收信人 %s 不在名册里" % receiver)
    main, _suffix = stage_of(meta.get("task-id", ""))
    if meta.get("task-id") and main is None:
        errors.append("task-id %s 不是主任务号（T001）或阶段任务（T001-1-plan）" % meta.get("task-id"))
    for key in FIELDS:
        if not str(fields.get(key, "")).strip():
            errors.append("正文缺“%s”（没有就写“无”）" % key)
    if body_lines > MAX_BODY_LINES:
        errors.append("正文 %d 行，超过 %d 行：细节放进 report.md" % (body_lines, MAX_BODY_LINES))
    if sender == "audit-sonnet" and kind == "交付":
        if fields.get("结论") not in VERDICTS:
            errors.append("审核端的交付要写“结论: 通过”或“结论: 返工”")
        elif fields.get("结论") == "返工":
            if fields.get("退回") not in RETURN_TARGETS:
                errors.append("返工要写“退回: %s”之一" % " | ".join(RETURN_TARGETS))
            elif _suffix == "4-audit-pre" and RETURN_TARGETS[fields["退回"]] not in ("1-plan", "2-contract", "3-gate-pre"):
                errors.append("一审只能退回规划端、合同端或门禁端（还没有执行）")
            if str(fields.get("阻塞项", "")).strip() in ("", "无"):
                # 复审封板：下一轮只复核这些阻塞项，没列的建议不能在下一轮升级成打回理由
                errors.append("返工要写“阻塞项”：逐条列出必须改的问题（只列会导致打回的）")
    return errors


# ---------------------------------------------------------------------------
# 信箱、账本与锁
# ---------------------------------------------------------------------------

class Hub:
    def __init__(self, repo: Path) -> None:
        self.repo = Path(repo)
        self.root = self.repo / MAILBOX

    def inbox(self, agent: str, box: str = "new") -> Path:
        return self.root / "inbox" / agent / box

    def task_dir(self, task_id: str) -> Path:
        return self.root / "tasks" / task_id

    def ledger(self) -> Path:
        return self.root / "ledger" / "events.jsonl"

    def state_path(self) -> Path:
        return self.root / "ledger" / "state.json"

    def agent_path(self, agent: str) -> Path:
        return self.root / "agents" / ("%s.json" % SENDER_ALIAS.get(agent, agent))

    def ensure(self) -> None:
        for agent in list(ROSTER) + [OWNER]:
            for box in ("new", "cur"):
                self.inbox(agent, box).mkdir(parents=True, exist_ok=True)
        for sub in ("tasks", "turns", "agents", "ledger", "sessions"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    # -- 账本与状态 ----------------------------------------------------------
    def append_event(self, event: str, **data: Any) -> None:
        record = dict(data)
        record.update(at=utc_now(), event=event)
        path = self.ledger()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def load_state(self) -> Dict[str, Any]:
        text = read_text(self.state_path())
        if not text.strip():
            return {"tasks": {}}
        data = json.loads(text)
        data.setdefault("tasks", {})
        return data

    def save_state(self, state: Dict[str, Any]) -> None:
        write_text_atomic(self.state_path(), json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    def agent_record(self, agent: str) -> Dict[str, Any]:
        text = read_text(self.agent_path(agent))
        return json.loads(text) if text.strip() else {"name": agent, "sessions": {}}

    def save_agent_record(self, agent: str, record: Dict[str, Any]) -> None:
        write_text_atomic(self.agent_path(agent), json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    # -- 投递与收信 ------------------------------------------------------------
    def deliver(self, meta: Dict[str, str], fields: Dict[str, str]) -> str:
        meta = dict(meta)
        meta["msg-id"] = meta.get("msg-id") or new_msg_id(meta["from"])
        text = render_letter(meta, fields)
        box = self.inbox(meta["to"])
        box.mkdir(parents=True, exist_ok=True)
        path = box / ("%s.md" % meta["msg-id"])
        if not pd.publish_new(path, text.encode("utf-8")):
            raise HubError("信件编号冲突：%s" % meta["msg-id"])
        self.append_event("letter.delivered", msg_id=meta["msg-id"], sender=meta["from"], to=meta["to"],
                          type=meta["type"], task_id=meta["task-id"], sha256=sha256_text(text))
        return meta["msg-id"]

    def unread(self, agent: str) -> List[Path]:
        box = self.inbox(agent)
        return sorted(box.glob("*.md")) if box.is_dir() else []

    def take(self, path: Path) -> Path:
        """读信：从 new 移到 cur（同盘改名，移动即回执）。"""
        target = path.parent.parent / "cur" / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        os.rename(str(path), str(target))
        self.append_event("letter.taken", msg_id=path.stem, agent=path.parent.parent.name)
        return target


class DirLock:
    """mkdir 加 owner.json 的目录锁（照 ConfigLock 的做法）。持有者进程已经不在时才接管，并记一条事件。"""

    def __init__(self, path: Path, wait_seconds: float = 30.0) -> None:
        self.path = path
        self.wait_seconds = wait_seconds
        self.token = os.urandom(8).hex()

    def __enter__(self) -> "DirLock":
        deadline = time.monotonic() + self.wait_seconds
        while True:
            try:
                self.path.mkdir(parents=True)
                write_text_atomic(self.path / "owner.json", json.dumps(
                    {"pid": os.getpid(), "token": self.token, "at": utc_now()}) + "\n")
                return self
            except FileExistsError:
                owner = self.owner()
                if owner.get("pid") and pd.pid_alive(int(owner["pid"])) is False:
                    shutil.rmtree(str(self.path), ignore_errors=True)
                    continue
                if time.monotonic() >= deadline:
                    raise HubError("锁被占用：%s（持有者 %s）" % (self.path, owner or "未知"), EXIT_BLOCKED)
                time.sleep(0.5)

    def owner(self) -> Dict[str, Any]:
        try:
            return json.loads(read_text(self.path / "owner.json") or "{}")
        except ValueError:
            return {}

    def __exit__(self, *exc: Any) -> None:
        if self.owner().get("token") == self.token:
            shutil.rmtree(str(self.path), ignore_errors=True)


# ---------------------------------------------------------------------------
# 主任务状态与内核校验（设计 §5）
# ---------------------------------------------------------------------------

def new_task_state(task: str, slug: str, title: str, base_head: str, jev_enabled: bool) -> Dict[str, Any]:
    return {
        "task": task, "slug": slug, "title": title, "status": "active", "created_at": utc_now(),
        "base_head": base_head, "contract_task": "%s-%s" % (task.lower(), slug), "jev_enabled": jev_enabled,
        "stages": {suffix: {"status": "idle"} for suffix in STAGE_ORDER},
        "contract": {}, "oracle": {}, "audit_pre": {"fails": 0}, "exec": {}, "gate_post": {},
        "jev": {}, "audit_post": {}, "workspaces": {}, "notes": [], "coordinator_rejections": 0,
    }


def gate_pattern(ts: Dict[str, Any]) -> str:
    return "tests/test_gate_%s_*.py" % ts["task"].lower()


def gate_file(ts: Dict[str, Any], kind: str) -> str:
    return "tests/test_gate_%s_%s.py" % (ts["task"].lower(), kind)


def dependents(suffix: str) -> List[str]:
    found: List[str] = []
    for name in STAGE_ORDER:
        if any(dep == suffix or dep in found for dep in DEPENDS[name]):
            found.append(name)
    return found


def invalidate_after(ts: Dict[str, Any], suffix: str) -> None:
    """上游重新交付后，依赖它的下游结论一律作废：阶段回到 idle，相关记录清空（设计 §5）。"""
    later = dependents(suffix)
    for name in later:
        ts["stages"][name] = {"status": "idle"}
    if "3-gate-pre" in later:
        ts["oracle"] = {}
    if "3j-jev" in later:
        ts["jev"].pop("3j-jev", None)
    if "4-audit-pre" in later:
        ts["audit_pre"] = {"fails": ts["audit_pre"].get("fails", 0)}
    if "5-exec" in later:
        ts["exec"] = {}
    if "6-gate-post" in later:
        ts["gate_post"] = {}
    if "6j-jev" in later:
        ts["jev"].pop("6j-jev", None)
    if "7-audit-post" in later:
        ts["audit_post"] = {}


def _guard_start(ts: Dict[str, Any], suffix: str) -> Optional[str]:
    stages = ts["stages"]
    if stages[suffix]["status"] == "assigned":
        return "阶段 %s 已经开工、还没交付" % suffix
    if suffix == "1-plan":
        return None
    if suffix == "2-contract":
        return None if stages["1-plan"]["status"] == "delivered" else "规划端还没交付（1-plan）"
    if suffix == "3-gate-pre":
        return None if ts["contract"].get("validated") else "合同还没写进 .agent/plans/ 并通过 validate"
    if suffix == "3j-jev":
        return None if stages["2-contract"]["status"] == "delivered" else "合同端还没交付（2-contract）"
    if suffix == "4-audit-pre":
        if not ts["oracle"].get("locked"):
            return "基准测试还没锁定：要有基线提交、在基线上失败、合同的 base_sha 指向它并重新通过 validate"
        if ts.get("jev_enabled") and "3j-jev" not in ts["jev"]:
            return "JEV 已启用，还没有合同概述的判断（3j-jev）"
        return None
    if suffix == "5-exec":
        audit = ts["audit_pre"]
        if audit.get("verdict") != "通过":
            return "一审还没有通过"
        if (audit.get("contract_sha256") != ts["contract"].get("sha256")
                or audit.get("oracle_sha") != ts["oracle"].get("sha")):
            return "一审之后合同或基线提交变了，要重新一审"
        return None
    if suffix == "6-gate-post":
        return None if ts["exec"].get("check_ok") else "执行端的检查还没全部通过（check --fresh 与范围门禁）"
    if suffix == "6j-jev":
        return None if ts["gate_post"].get("ok") else "战后门禁还没全部通过"
    if suffix == "7-audit-post":
        if not ts["gate_post"].get("ok"):
            return "战后门禁还没全部通过"
        if ts.get("jev_enabled") and "6j-jev" not in ts["jev"]:
            return "JEV 已启用，还没有执行概述的判断（6j-jev）"
        return None
    return "未知阶段 %s" % suffix


def hotfix_reason(ts: Dict[str, Any]) -> Optional[str]:
    """执行之后能不能热修补基准测试：执行端举证（报了合同矛盾），或终审退回门禁端。

    热修补之后的代价由内核保证：合同出新版本（旧版本已派遣，不能再改）、一审重做（审核端只看测试差异）、
    执行端必须重跑——下游的结论都依赖 3-gate-pre，会被 invalidate_after 一并作废。"""
    if ts["exec"].get("conflicts"):
        return "执行端报了 %d 条合同矛盾" % ts["exec"]["conflicts"]
    audit_post = ts["audit_post"]
    if audit_post.get("verdict") == "返工" and RETURN_TARGETS.get(audit_post.get("target", "")) == "3-gate-pre":
        return "终审退回门禁端"
    return None


def _guard_rework(ts: Dict[str, Any], suffix: str) -> Optional[str]:
    status = ts["stages"][suffix]["status"]
    if status == "assigned":
        return "阶段 %s 正在进行，不能返工" % suffix
    if status == "failed":
        return None  # 内核核验没过
    if (ts.get("owner_rework") or {}).get("suffix") == suffix:
        return None  # 站主用 send --rework 指定的返工（站主是最终拍板人）
    audit_pre, audit_post = ts["audit_pre"], ts["audit_post"]

    def returned_by(audit: Dict[str, Any]) -> bool:
        return audit.get("verdict") == "返工" and RETURN_TARGETS.get(audit.get("target", "")) == suffix

    if suffix == "3-gate-pre" and hotfix_reason(ts):
        return None  # 门禁热修补（用户 2026-10-19 按推荐拍板）
    if suffix in ("2-contract", "3-gate-pre"):
        if returned_by(audit_pre) or (suffix == "2-contract" and returned_by(audit_post)):
            return None
        return "没有一审或终审退回 %s 的记录，也没有内核核验失败，站主也没有指定返工" % suffix
    if suffix == "6-gate-post":
        return None if returned_by(audit_post) else "没有终审退回战后门禁的记录，也没有内核核验失败"
    if suffix == "1-plan":
        if audit_pre.get("fails", 0) >= 3:
            return None
        if audit_post.get("verdict") == "返工" and RETURN_TARGETS.get(audit_post.get("target", "")) == "1-plan":
            return None
        return "一审连续没过不到 3 次，也没有终审退回规划端"
    if suffix == "5-exec":
        execution, gate_post = ts["exec"], ts["gate_post"]
        if execution.get("run_dir") and not execution.get("check_ok"):
            return None
        if gate_post.get("ran") and not gate_post.get("ok"):
            return None
        if audit_post.get("verdict") == "返工" and RETURN_TARGETS.get(audit_post.get("target", "")) == "5-exec":
            return None
        return "没有执行之后的失败记录，也没有终审退回执行端"
    return "阶段 %s 没有核验失败的记录" % suffix


def guard(ts: Optional[Dict[str, Any]], meta: Dict[str, str]) -> Optional[str]:
    """协调人这封信能不能投递：返回拒收原因，能投递时返回 None。前置条件只看内核写下的状态。"""
    kind, receiver, task_id = meta.get("type", ""), meta.get("to", ""), meta.get("task-id", "")
    main, suffix = stage_of(task_id)
    if ts is None:
        return "没有登记主任务 %s" % (main or task_id)
    if receiver == OWNER:
        return None if kind in ("汇报", "提问") else "给站主只能发 汇报 或 提问"
    if kind in ("汇报", "提问"):
        return "汇报、提问只发给站主"
    if ts.get("status") != "active":
        return "主任务 %s 已%s" % (ts["task"], "结项" if ts.get("status") == "done" else "停止")
    if receiver not in WORKERS:
        return "收信人 %s 不是工人" % receiver
    if suffix is None:
        return "发给工人的信要写阶段任务（例如 %s-1-plan）" % ts["task"]
    if STAGE_WORKER[suffix] != receiver:
        return "阶段 %s 归 %s，不归 %s" % (suffix, STAGE_WORKER[suffix], receiver)
    if kind == "开工":
        return _guard_start(ts, suffix)
    if kind == "返工":
        return _guard_rework(ts, suffix)
    if kind == "通过":
        if suffix == "5-exec":
            return None if ts["audit_post"].get("verdict") == "通过" else "终审还没有通过，不能结项"
        return None if ts["stages"][suffix]["status"] == "delivered" else "阶段 %s 还没交付" % suffix
    if kind in ("等待", "停止"):
        return None
    return "协调人不能发 %s" % kind


def allowed_moves(ts: Dict[str, Any]) -> List[str]:
    """给协调人看的“内核此刻允许的下一步”（只是提示；投递时照样逐封校验）。"""
    moves: List[str] = []
    for suffix in STAGE_ORDER:
        worker = STAGE_WORKER[suffix]
        for kind in ("开工", "返工"):
            meta = {"type": kind, "to": worker, "task-id": "%s-%s" % (ts["task"], suffix)}
            if guard(ts, meta) is None:
                moves.append("%s → %s（%s-%s）" % (kind, worker, ts["task"], suffix))
    if guard(ts, {"type": "通过", "to": "exec-step", "task-id": "%s-5-exec" % ts["task"]}) is None:
        moves.append("通过 → exec-step（%s-5-exec）：结项，内核随后 verdict PASS 并 integrate" % ts["task"])
    return moves


# ---------------------------------------------------------------------------
# Git 与工作区
# ---------------------------------------------------------------------------

def git(args: Sequence[str], cwd: Path, check: bool = True, timeout: int = 120) -> str:
    proc = subprocess.run(["git"] + list(args), cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout)
    out = proc.stdout.decode("utf-8", "replace")
    if check and proc.returncode != 0:
        raise HubError("git %s 失败：%s" % (" ".join(args), proc.stderr.decode("utf-8", "replace").strip()[:400]))
    return out


def worktree_root(repo: Path) -> Path:
    pd_repo = pd.Repo(repo)
    root = pd_repo.worktree_root(pd_repo.config())
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_worktree(hub: Hub, ts: Dict[str, Any], kind: str, commit: str) -> Path:
    """阶段用的分离 HEAD worktree；同一种类在同一主任务里复用（会话续接要求工作目录不变）。"""
    recorded = ts["workspaces"].get(kind) or {}
    path = Path(recorded["path"]) if recorded.get("path") else None
    if path is not None and path.is_dir() and recorded.get("commit") == commit:
        return path
    prefix = "%s-hub-%s-%s-" % (hub.repo.name[:16], ts["task"].lower(), kind)
    path = Path(tempfile.mkdtemp(prefix=prefix, dir=str(worktree_root(hub.repo))))
    git(["worktree", "add", "--detach", str(path), commit], hub.repo)
    ts["workspaces"][kind] = {"path": str(path), "commit": commit, "created_at": utc_now()}
    hub.append_event("workspace.created", task=ts["task"], kind=kind, path=str(path), commit=commit)
    return path


def workspace_status(path: Path) -> List[Tuple[str, str]]:
    out = git(["status", "--porcelain=v1", "--untracked-files=all", "-z"], path)
    entries: List[Tuple[str, str]] = []
    for item in out.split("\0"):
        if len(item) > 3:
            entries.append((item[:2], item[3:]))
    return entries


# ---------------------------------------------------------------------------
# 回合：启动、审计、解析
# ---------------------------------------------------------------------------

ROLE_BLOCK_RE = re.compile(r"<!-- 角色:([a-z]+) -->\n(.*?)<!-- /角色 -->\n?", re.S)


def render_template(name: str, values: Dict[str, str], role: Optional[str] = None) -> str:
    """代入占位符；给了 role 时只保留这个角色的职责段（`<!-- 角色:x -->…<!-- /角色 -->`），别的角色的规则不给它看。"""
    text = read_text(TEMPLATE_DIR / name)
    if not text:
        raise HubError("找不到提示词模板：%s" % (TEMPLATE_DIR / name))
    if role is not None:
        text = ROLE_BLOCK_RE.sub(lambda m: m.group(2) if m.group(1) == role else "", text)
    for key, value in values.items():
        text = text.replace("{{%s}}" % key, value)
    return text


def extract_json_block(text: str) -> Dict[str, Any]:
    blocks = JSON_BLOCK_RE.findall(text or "")
    if not blocks:
        raise HubError("最后一条消息里没有 ```json 代码块")
    try:
        data = json.loads(blocks[-1])
    except ValueError as exc:
        raise HubError("JSON 代码块解析失败：%s" % exc)
    if not isinstance(data, dict):
        raise HubError("JSON 代码块顶层必须是对象")
    return data


def claude_session_effort(session_id: str) -> Optional[str]:
    """claude 的会话文件里每条 assistant 记录带 effort：读出实际生效的档位（设计 §6.1）。"""
    base = Path.home() / ".claude" / "projects"
    for path in base.glob("*/%s.jsonl" % session_id):
        efforts = []
        for line in read_text(path).splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") == "assistant" and entry.get("effort"):
                efforts.append(str(entry["effort"]))
        return efforts[-1] if efforts else None
    return None


def claude_path_rule(path: Path) -> str:
    """claude 权限规则里绝对路径的写法：`//c/Code/Repo/**`（盘符小写、正斜杠；2026-10-19 在 Windows 上实测）。"""
    text = Path(path).resolve().as_posix()
    if len(text) > 1 and text[1] == ":":
        text = text[0].lower() + text[2:]
    return "//%s/**" % text.strip("/")


def audit_claude_stream(lines: Sequence[str], spec: Dict[str, Any]) -> Dict[str, Any]:
    """读内核自己截下的事件流：白名单之外的 tool_use / server_tool_use、init 的工具与 MCP、模型；
    以及模型接口的报错（claude 把它合成为一条 `<synthetic>` 消息，带 error 与 api_error_status）。"""
    allowed = set(spec["tools"])
    violations: List[str] = []
    tool_calls: Dict[str, int] = {}
    init: Dict[str, Any] = {}
    result: Dict[str, Any] = {}
    models = set()
    api_error: Optional[str] = None
    outside: Dict[str, str] = {}  # 白名单之外的 tool_use：id → 工具名
    refused: set = set()
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            init = event
        elif kind == "assistant":
            message = event.get("message") or {}
            if message.get("model"):
                models.add(message["model"])
            if event.get("error") or event.get("is_api_error_message"):
                text = "".join(b.get("text", "") for b in message.get("content") or []
                               if isinstance(b, dict) and b.get("type") == "text")
                api_error = "%s %s：%s" % (event.get("api_error_status") or "", event.get("api_error_code")
                                          or event.get("error") or "", text.strip()[:300])
            elif message.get("model") != "<synthetic>":
                api_error = None  # 报错之后模型又正常回复了：以最后的为准
            for block in message.get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") in ("tool_use", "server_tool_use"):
                    name = str(block.get("name"))
                    tool_calls[name] = tool_calls.get(name, 0) + 1
                    if block.get("type") == "server_tool_use":  # 服务端工具（advisor）在服务端执行：一律作废
                        violations.append("调用了白名单之外的工具：%s（%s）" % (name, block.get("type")))
                    elif name not in allowed:
                        outside[str(block.get("id"))] = name
        elif kind == "user":
            content = (event.get("message") or {}).get("content")
            for block in content if isinstance(content, list) else []:
                if (isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error")
                        and block.get("tool_use_id") in outside and "No such tool available" in str(block.get("content"))):
                    refused.add(block["tool_use_id"])
        elif kind == "result":
            result = event
    if not init:
        violations.append("事件流里没有 init")
    else:
        if set(init.get("tools") or []) != allowed:
            violations.append("init 的工具 %s 与白名单 %s 不一致" % (sorted(init.get("tools") or []), sorted(allowed)))
        if init.get("mcp_servers"):
            violations.append("加载了 MCP 服务器：%s" % [s.get("name") for s in init["mcp_servers"] if isinstance(s, dict)])
        if init.get("memory_paths"):
            violations.append("自动记忆没有关掉：%s" % init["memory_paths"])
        if init.get("model") and init["model"] != spec["model"]:
            violations.append("init 的模型 %s 不是 %s" % (init["model"], spec["model"]))
    models.discard("<synthetic>")  # claude 自己合成的消息（例如接口报错时）没有真实模型
    if models - {spec["model"]}:
        violations.append("实际模型 %s 与要求 %s 不一致" % (sorted(models), spec["model"]))
    if api_error is None and result.get("terminal_reason") == "api_error":
        api_error = "terminal_reason=api_error：%s" % str(result.get("result") or "")[:300]
    # 白名单之外的客户端调用：被 CLI 当场拒绝（“No such tool available”）的没有任何效果，只记警告
    # （T001 的终审为一次被拒的 Bash 白白作废了 16 分钟）；看不到拒绝结果的照旧作废。
    warnings = ["试图调用白名单之外的工具 %s，被 CLI 拒绝" % name for tid, name in outside.items() if tid in refused]
    violations += ["调用了白名单之外的工具：%s（tool_use）" % name for tid, name in outside.items() if tid not in refused]
    return {"violations": violations, "warnings": warnings, "tool_calls": tool_calls,
            "init_session": init.get("session_id"),
            "final_text": str(result.get("result") or ""), "is_error": bool(result.get("is_error")),
            "cost_usd": result.get("total_cost_usd"), "usage": result.get("usage") or {},
            "models": sorted(models), "terminal": bool(result), "api_error": api_error}


def audit_pi_stream(lines: Sequence[str], spec: Dict[str, Any]) -> Dict[str, Any]:
    allowed = set(spec["tools"])
    violations: List[str] = []
    tool_calls: Dict[str, int] = {}
    final_text, levels, models, stop = "", set(), set(), None
    api_error: Optional[str] = None
    usage: Dict[str, Any] = {}
    terminal = False
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        if kind == "tool_execution_start":
            name = str(event.get("toolName"))
            tool_calls[name] = tool_calls.get(name, 0) + 1
            if name not in allowed:
                violations.append("调用了白名单之外的工具：%s" % name)
        elif kind == "message_end" and (event.get("message") or {}).get("role") == "assistant":
            message = event["message"]
            models.add("%s/%s" % (message.get("provider"), message.get("model")))
            if message.get("thinkingLevel"):
                levels.add(str(message["thinkingLevel"]))
            text = "".join(b.get("text", "") for b in message.get("content") or []
                           if isinstance(b, dict) and b.get("type") == "text")
            if text.strip():
                final_text = text
            stop = message.get("stopReason")
            # 只认最后一条：pi 自己重试成功时，前面那条出错的消息不算
            api_error = str(message.get("errorMessage") or "stopReason=error")[:300] if stop == "error" else None
            for key, value in (message.get("usage") or {}).items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    usage[key] = usage.get(key, 0) + value
        elif kind in ("agent_settled", "agent_end"):
            terminal = True
    expected = "%s/%s" % (spec["provider"], spec["model"])
    if models - {expected}:
        violations.append("实际模型 %s 与要求 %s 不一致" % (sorted(models), expected))
    return {"violations": violations, "tool_calls": tool_calls, "final_text": final_text,
            "effective_levels": sorted(levels), "stop_reason": stop, "usage": usage, "models": sorted(models),
            "terminal": terminal, "is_error": stop not in (None, "stop"), "api_error": api_error}


class TurnRunner:
    """启动一个工人回合：一个后台进程，Job Object 监督（pd.run_supervised），事件流由内核截下。"""

    def __init__(self, hub: Hub, launcher: Any = None) -> None:
        self.hub = hub
        self.launcher = launcher or pd.run_supervised

    def run(self, agent: str, session_key: str, workspace: Path, role_prompt: str, prompt: str,
            retry_of: Optional[str] = None, fresh: bool = False) -> Dict[str, Any]:
        """fresh=True：不续接旧会话，开一个干净的新会话（返工时用，旧会话里失败的历史不再带着走）。"""
        spec = ROSTER[agent]
        turn_id = "%s-%s" % (utc_compact(), os.urandom(2).hex())
        turn_dir = self.hub.root / "turns" / agent / turn_id
        turn_dir.mkdir(parents=True)
        role_path = turn_dir / "role.md"
        role_path.write_text(role_prompt, encoding="utf-8", newline="\n")
        (turn_dir / "prompt.md").write_text(prompt, encoding="utf-8", newline="\n")
        record = self.hub.agent_record(agent)
        session = record["sessions"].get(session_key)
        generation = int((session or {}).get("generation", 0))
        if session and (fresh or session.get("cwd") != str(workspace)):
            session, generation = None, generation + 1  # 返工重开，或工作目录变了（claude 按目录找会话）
        first = session is None
        if first:
            session = {"id": str(uuid.uuid4()) if spec["adapter"] == "claude" else "%s-g%d" % (session_key, generation),
                       "cwd": str(workspace), "turns": 0, "created_at": utc_now(), "generation": generation}
        inline = prompt if len(prompt) <= MAX_INLINE_PROMPT else (
            "本回合的输入很长，已写在文件里，先完整读它再开始：%s" % (turn_dir / "prompt.md"))
        if spec["adapter"] == "claude":
            cmd = ["claude", "-p", "--model", spec["model"], "--effort", spec["effort"],
                   "--output-format", "stream-json", "--verbose", "--setting-sources", "project",
                   "--settings", json.dumps(CLAUDE_SETTINGS), "--strict-mcp-config", "--disable-slash-commands",
                   "--tools", ",".join(spec["tools"])]
            if spec.get("allowed_rules"):
                cmd += ["--allowedTools"] + list(spec["allowed_rules"])
            # 主工作区只读：合同（.agent/plans/）、信箱、长输入文件与执行证据都在那里，worktree 里没有。
            cmd += ["--add-dir", str(self.hub.repo)]
            writes = sorted({"Edit", "Write"} & set(spec["tools"]))
            if writes:
                # 没有人能答权限提示，默认模式下连工作目录里的写入也会被拒（2026-10-19 实测）：
                # 工作目录里的写入自动放行，主工作区的写入一律拒绝（拒绝规则优先）。
                cmd += ["--permission-mode", "acceptEdits", "--disallowedTools"] + [
                    "%s(%s)" % (tool, claude_path_rule(self.hub.repo)) for tool in writes]
            cmd += ["--permission-prompts", "none", "--append-system-prompt-file", str(role_path)]
            cmd += (["--session-id", session["id"]] if first else ["--resume", session["id"]]) + [inline]
            cmd[0] = shutil.which("claude") or "claude"
        else:
            sessions_dir = self.hub.root / "sessions" / agent
            sessions_dir.mkdir(parents=True, exist_ok=True)
            # pi 的输入一律用 @文件 附上（与调度器给执行器附合同的做法相同），命令行只放一句话。
            cmd = pd.resolve_pi_command() + [
                "--provider", spec["provider"], "--model", spec["model"], "--thinking", spec["thinking"],
                "--mode", "json"] + list(pd.RESOURCE_FLAGS) + [
                "--no-context-files", "--tools", ",".join(spec["tools"]),
                "--append-system-prompt", str(role_path), "--session-dir", str(sessions_dir),
                "--session-id", session["id"], "@%s" % (turn_dir / "prompt.md"), "按附件里的本回合输入办事。"]
        started = utc_now()
        try:
            config = pd.Repo(self.hub.repo).config()
        except pd.DispatchError:
            config = {}
        with open(turn_dir / "stream.jsonl", "xb") as out, open(turn_dir / "stderr.log", "xb") as err:
            result = self.launcher(cmd, workspace, worker_env(config), out, err, int(spec.get("timeout", 1800)))
        lines = read_text(turn_dir / "stream.jsonl").splitlines()
        audit = audit_claude_stream(lines, spec) if spec["adapter"] == "claude" else audit_pi_stream(lines, spec)
        if spec["adapter"] == "claude":
            audit["effort_requested"] = spec["effort"]
            audit["effort_effective"] = claude_session_effort(session["id"])
        else:
            audit["effort_requested"] = spec["thinking"]
            audit["effort_effective"] = ",".join(audit.get("effective_levels") or []) or None
        output, output_error = None, None
        if audit.get("api_error"):
            output_error = "模型接口报错（环境问题，不是工人的输出问题）：%s" % audit["api_error"]
        elif not audit["violations"]:
            try:
                output = extract_json_block(audit["final_text"])
            except HubError as exc:
                output_error = str(exc)
        session["turns"] = int(session.get("turns", 0)) + 1
        session["last_turn"] = turn_id
        record["sessions"][session_key] = session
        record["last_turn_at"] = utc_now()
        self.hub.save_agent_record(agent, record)
        summary = {
            "turn_id": turn_id, "agent": agent, "session_key": session_key, "session_id": session["id"],
            "first_turn": first, "retry_of": retry_of, "started_at": started, "finished_at": utc_now(),
            "exit_code": result.get("exit_code"), "timed_out": bool(result.get("timed_out")),
            "wall_seconds": result.get("wall_seconds"), "workspace": str(workspace),
            "model_requested": spec.get("model"), "models": audit.get("models"),
            "effort_requested": audit["effort_requested"], "effort_effective": audit["effort_effective"],
            "tool_calls": audit["tool_calls"], "violations": audit["violations"], "cost_usd": audit.get("cost_usd"),
            "usage": audit.get("usage"), "terminal": audit.get("terminal"), "output_error": output_error,
            "api_error": audit.get("api_error"), "warnings": audit.get("warnings") or [],
            "role_prompt_sha256": sha256_text(role_prompt), "hub_sha256": HUB_SHA256,
        }
        pd.write_json(turn_dir / "result.json", summary, exclusive=True)
        self.hub.append_event("turn.finished", turn_id=turn_id, agent=agent, session_key=session_key,
                              exit_code=summary["exit_code"], timed_out=summary["timed_out"],
                              violations=len(audit["violations"]), output_ok=output is not None,
                              effort_requested=summary["effort_requested"], effort_effective=summary["effort_effective"])
        summary["output"] = output
        summary["turn_dir"] = str(turn_dir)
        return summary


# ---------------------------------------------------------------------------
# 调度器子命令（内核代办执行端、合同与基线）
# ---------------------------------------------------------------------------

def run_pd(hub: Hub, args: Sequence[str], timeout: int = 600) -> Tuple[int, str]:
    cmd = [sys.executable, str(HERE / "pi_dispatch.py"), "--repo", str(hub.repo)] + list(args)
    try:
        proc = subprocess.run(cmd, cwd=str(hub.repo), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=timeout, env=kernel_env())
    except subprocess.TimeoutExpired:
        return 124, "超时（%d 秒）：%s" % (timeout, " ".join(args))
    text = proc.stdout.decode("utf-8", "replace")
    hub.append_event("dispatcher.called", args=list(args), exit_code=proc.returncode)
    return proc.returncode, text


def tail(text: str, lines: int = 30) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def tail_file(path: Path, lines: int = 30, limit: int = 65536) -> str:
    """文件末尾几行：只读最后 limit 字节（输出可能很大）。"""
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        handle.seek(max(0, handle.tell() - limit))
        return tail(handle.read().decode("utf-8", "replace"), lines)


# ---------------------------------------------------------------------------
# 各阶段的交付核验（内核，确定性）
# ---------------------------------------------------------------------------

def contract_paths(hub: Hub, ts: Dict[str, Any]) -> Tuple[Path, Path]:
    key = ts["contract"]["key"]
    return hub.repo / ".agent" / "plans" / (key + ".md"), hub.repo / ".agent" / "plans" / (key + ".json")


def contract_digest(hub: Hub, ts: Dict[str, Any]) -> str:
    md, js = contract_paths(hub, ts)
    return sha256_text((sha256_file(md) or "") + (sha256_file(js) or ""))


def revalidate_contract(hub: Hub, ts: Dict[str, Any]) -> List[str]:
    """derive-json 后 validate；返回问题清单（空表示通过），并更新合同的哈希与状态。"""
    key = ts["contract"]["key"]
    code, out = run_pd(hub, ["derive-json", key, "--force"])
    problems: List[str] = []
    if code != 0:
        problems.append("derive-json 失败：\n%s" % tail(out))
    else:
        code, out = run_pd(hub, ["validate", key])
        if code != 0:
            problems.append("validate 失败：\n%s" % tail(out))
    if not problems:
        problems.extend(contract_requirements(hub, ts))
    ts["contract"]["validated"] = not problems
    ts["contract"]["sha256"] = contract_digest(hub, ts)
    ts["contract"]["problems"] = problems
    return problems


def contract_requirements(hub: Hub, ts: Dict[str, Any]) -> List[str]:
    """内核另外要求的几项：门禁测试路径禁改、门禁检查在基线上失败、执行模型与集成授权（设计 §7）；
    合同里不能留“待确认”一类的未决标注。"""
    md, js = contract_paths(hub, ts)
    try:
        data = json.loads(read_text(js))
    except ValueError:
        return ["合同 JSON 读不出来"]
    problems: List[str] = []
    pending = PENDING_MARK_RE.findall(read_text(md))
    if pending:
        # T001（2026-10-19）：合同端把 4 个待站主确认的问题写成 13 处标注留在正文里，执行端会当成未决事项
        problems.append("合同里还有 %d 处未决标注（%s）：拿不准的事先发“提问”，等站主或协调人答复后再交合同，"
                        "合同里只写已经定下的做法" % (len(pending), "、".join(sorted(set(pending)))))
    if gate_pattern(ts) not in (data.get("scope") or {}).get("forbidden_paths", []):
        problems.append("Scope 的 forbidden_paths 要包含 %s" % gate_pattern(ts))
    baseline_file = gate_file(ts, "baseline")
    gate_checks = [c for c in data.get("checks") or [] if baseline_file in (c.get("argv") or [])]
    if not gate_checks:
        problems.append("Validation commands 要有一条运行 %s 的必要检查" % baseline_file)
    elif not any(c.get("expect_on_base") == "fail" and c.get("required", True) for c in gate_checks):
        problems.append("运行 %s 的检查要标“必要”与“基线应失败”" % baseline_file)
    executor = data.get("executor") or {}
    if (executor.get("provider"), executor.get("model"), executor.get("thinking")) != EXECUTOR:
        problems.append("执行模型要写成：%s" % CONTRACT_EXECUTOR_LINE)
    integration = set((data.get("authorization") or {}).get("integration") or [])
    if not {"local_branch", "merge"} <= integration:
        problems.append("integration_actions 要写 local_branch, merge")
    return problems


def dod_coverage_problems(hub: Hub, ts: Dict[str, Any], report: str) -> List[str]:
    """一审报告要有“DoD → 测试 → 断言”映射：合同里每个 DoD 的 id 都要在报告里出现（docs/实际问题/审核端.md）。"""
    try:
        dod = json.loads(read_text(contract_paths(hub, ts)[1])).get("definition_of_done") or []
    except (ValueError, KeyError):
        return []
    ids = [str(item.get("id")) for item in dod if isinstance(item, dict) and item.get("id")]
    missing = [i for i in ids if not re.search(r"(?<![A-Za-z0-9])%s(?![0-9])" % re.escape(i), report)]
    if missing:
        return ["一审报告的“DoD → 测试 → 断言”映射表漏了 %s（每条 DoD 都要写由哪条测试的哪个断言证明，"
                "或者写明“只能人工审阅”）" % "、".join(missing)]
    return []


def accept_contract(hub: Hub, ts: Dict[str, Any], output: Dict[str, Any]) -> List[str]:
    text = output.get("contract_md")
    if not isinstance(text, str) or not text.strip():
        return ["输出里没有 contract_md（合同 Markdown 全文）"]
    version = int(ts["contract"].get("version", 0)) + 1
    header = "# TASK: %s" % ts["contract_task"]
    if text.lstrip().splitlines()[0].strip() != header:
        return ["合同第一行必须是“%s”" % header]
    key = "%s.v%d" % (ts["contract_task"], version)
    path = hub.repo / ".agent" / "plans" / (key + ".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return ["%s 已存在，合同版本只增不改" % path.name]
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
    ts["contract"] = {"version": version, "key": key, "md": str(path.relative_to(hub.repo).as_posix()),
                      "json": str(path.with_suffix(".json").relative_to(hub.repo).as_posix())}
    hub.append_event("contract.written", task=ts["task"], key=key)
    return revalidate_contract(hub, ts)


def bump_contract_version(hub: Hub, ts: Dict[str, Any]) -> List[str]:
    """已派遣过的合同不再改：复制成下一个版本（只改 plan_version），之后的 base_sha 改在新版本上。"""
    old_md, _js = contract_paths(hub, ts)
    version = int(ts["contract"]["version"]) + 1
    key = "%s.v%d" % (ts["contract_task"], version)
    new_md = old_md.with_name(key + ".md")
    if new_md.exists():
        return ["%s 已存在，合同版本只增不改" % new_md.name]
    text, count = re.subn(r"(?m)^- plan_version:\s*\d+\s*$", "- plan_version: %d" % version, read_text(old_md))
    if count != 1:
        return ["合同 Identity 里找不到唯一的“- plan_version:”行"]
    new_md.write_text(text, encoding="utf-8", newline="\n")
    ts["contract"] = {"version": version, "key": key, "md": new_md.relative_to(hub.repo).as_posix(),
                      "json": new_md.with_suffix(".json").relative_to(hub.repo).as_posix(),
                      "bumped_from": int(version) - 1}
    hub.append_event("contract.bumped", task=ts["task"], key=key)
    return []


def set_contract_base(hub: Hub, ts: Dict[str, Any], sha: str) -> List[str]:
    md, _js = contract_paths(hub, ts)
    text = read_text(md)
    updated, count = re.subn(r"(?m)^- base_sha:\s*\S+\s*$", "- base_sha: %s" % sha, text)
    if count != 1:
        return ["合同 Identity 里找不到唯一的“- base_sha:”行"]
    md.write_text(updated, encoding="utf-8", newline="\n")
    return revalidate_contract(hub, ts)


def accept_gate_pre(hub: Hub, ts: Dict[str, Any], workspace: Path) -> List[str]:
    """门禁端只能新增 tests/test_gate_<t>_baseline.py；内核提交、挂引用、改合同 base_sha、跑 baseline。"""
    changes = workspace_status(workspace)
    expected = gate_file(ts, "baseline")
    if not changes:
        return ["门禁草稿 worktree 里没有新增文件：要新增 %s" % expected]
    bad = [path for status, path in changes if status != "??" or path != expected]
    if bad:
        return ["只能新增 %s，不能改动别的文件：%s" % (expected, ", ".join(bad[:8]))]
    # 基准测试要“收集得到、在断言上失败”：语法错误或模块级导入失败的测试在基线上也是失败，
    # 不先挡下，就会被当成合格的基准锁进禁改路径（docs/实际问题/门禁端.md）
    proc = subprocess.run(KERNEL_PYTEST + ["--collect-only", "-q", expected], cwd=str(workspace),
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600,
                          env=kernel_pytest_env())
    if proc.returncode != 0:
        return ["%s 收集失败（pytest --collect-only 退出码 %d：语法错误、模块级导入失败或没有用例；"
                "被测的新符号要在用例函数里再 import）：\n%s" % (expected, proc.returncode,
                                                         tail(proc.stdout.decode("utf-8", "replace"), 15))]
    previous = (ts.get("hotfix") or {}).get("previous_oracle")
    if ts["contract"].get("dispatched"):
        problems = bump_contract_version(hub, ts)
        if problems:
            return problems
    git(["add", "--", expected], workspace)
    git(["commit", "-q", "-m", "门禁端基准测试：%s（gate-sonnet，hub）" % ts["task"]], workspace)
    sha = git(["rev-parse", "HEAD"], workspace).strip()
    ref = "refs/themis/oracle/%s/v%d" % (ts["contract_task"], ts["contract"]["version"])
    git(["update-ref", ref, sha], hub.repo)
    ts["workspaces"]["gate"]["commit"] = sha
    ts["oracle"] = {"sha": sha, "ref": ref, "files": [expected], "locked": False}
    hub.append_event("oracle.committed", task=ts["task"], sha=sha, ref=ref)
    if previous:  # 热修补：把测试差异留给重做的一审（审核端只看这一份差异）
        diff = git(["diff", previous, sha, "--", expected], hub.repo)
        evidence = hub.task_dir("%s-3-gate-pre" % ts["task"]) / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        diff_path = evidence / ("hotfix-%s.diff" % utc_compact())
        diff_path.write_text(diff, encoding="utf-8", newline="\n")
        ts["oracle"]["hotfix_diff"] = diff_path.relative_to(hub.repo).as_posix()
        ts["oracle"]["hotfix_from"] = previous
    problems = set_contract_base(hub, ts, sha)
    if problems:
        return problems
    code, out = run_pd(hub, ["baseline", ts["contract"]["key"]], timeout=1800)
    ts["oracle"]["baseline_exit"] = code
    ts["oracle"]["baseline_tail"] = tail(out, 20)
    if code != 0:
        return ["baseline 不符合预期（基准测试应在基线上失败，其余检查按合同）：\n%s" % tail(out, 20)]
    ts["oracle"]["locked"] = True
    ts["contract"]["sha256"] = contract_digest(hub, ts)
    if ts.get("hotfix"):
        ts.setdefault("hotfixes", []).append(dict(ts.pop("hotfix"), oracle=sha, contract=ts["contract"]["key"]))
    return []


def apply_candidate(hub: Hub, ts: Dict[str, Any]) -> Path:
    """战后与终审用的候选 worktree：基线提交（含基准测试）加候选补丁，不提交。"""
    run_dir = Path(ts["exec"]["run_dir"])
    workspace = ensure_worktree(hub, ts, "post-%s" % run_dir.name, ts["oracle"]["sha"])
    if not ts["workspaces"]["post-%s" % run_dir.name].get("patched"):
        patch = run_dir / "candidate.patch"
        if patch.exists() and patch.stat().st_size:
            git(["apply", "--whitespace=nowarn", str(patch)], workspace)
        ts["workspaces"]["post-%s" % run_dir.name]["patched"] = True
        ts["workspaces"]["post-%s" % run_dir.name]["baseline_status"] = workspace_status(workspace)
    return workspace


def accept_gate_post(hub: Hub, ts: Dict[str, Any], workspace: Path, output: Dict[str, Any]) -> List[str]:
    """只增不改：只能新增 tests/test_gate_<t>_whitebox.py；内核在候选上跑白盒测试与变异清单。"""
    key = "post-%s" % Path(ts["exec"]["run_dir"]).name
    before = {tuple(item) for item in ts["workspaces"][key].get("baseline_status") or []}
    after = set(workspace_status(workspace))
    added = sorted(after - before)
    expected = gate_file(ts, "whitebox")
    bad = [path for status, path in added if status != "??" or path != expected]
    ts["gate_post"] = {"ran": True, "ok": False}
    if bad:
        return ["战后只能新增 %s（只增不改）：%s" % (expected, ", ".join(bad[:8]))]
    if not (workspace / expected).exists():
        return ["没有新增 %s" % expected]
    stage_dir = hub.task_dir("%s-6-gate-post" % ts["task"])
    (stage_dir / "evidence").mkdir(parents=True, exist_ok=True)
    whitebox_log = stage_dir / "evidence" / ("whitebox-%s.log" % utc_compact())
    with open(whitebox_log, "xb") as log:  # Job Object 监督：超时连同子进程一起清掉；输出进文件，不整份读进内存
        result = pd.run_supervised(KERNEL_PYTEST + [expected, "-q"], workspace, kernel_pytest_env(), log, log, 1800)
    whitebox_tail = tail_file(whitebox_log, 15)
    ts["gate_post"]["whitebox_exit"] = result.get("exit_code")
    ts["gate_post"]["whitebox_tail"] = whitebox_tail
    ts["gate_post"]["whitebox_log"] = whitebox_log.relative_to(hub.repo).as_posix()
    problems: List[str] = []
    if result.get("exit_code") != 0 or result.get("timed_out"):
        problems.append("白盒测试在候选上没有全部通过%s：\n%s" % ("（超时）" if result.get("timed_out") else "",
                                                             whitebox_tail))
    spec = output.get("mutation_spec")
    if not isinstance(spec, dict) or not spec.get("mutations"):
        problems.append("输出里没有 mutation_spec（mutate --spec 的格式，至少一条变异）")
    else:
        spec_path = stage_dir / ("mutation-spec-%s.json" % utc_compact())
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        # 变异记录放在信箱的证据目录：终审能读主工作区（--add-dir），放系统临时目录它就读不到（T001 终审的意见）
        out_dir = stage_dir / "evidence" / ("mutate-%s" % utc_compact())
        code, out = run_pd(hub, ["mutate", "--tree", str(workspace), "--spec", str(spec_path), "--out", str(out_dir)],
                           timeout=3600)
        try:
            record = json.loads(read_text(out_dir / "mutations.json") or "{}")
        except ValueError:
            record = {}
        ts["gate_post"].update(mutate_exit=code, mutate_tail=tail(out, 25), mutate_spec=str(spec_path),
                               mutate_record=(out_dir / "mutations.json").relative_to(hub.repo).as_posix(),
                               mutation_counts=record.get("counts"),
                               equivalent=["%s：%s" % (m.get("name"), m["equivalent"]) for m in spec["mutations"]
                                           if isinstance(m, dict) and m.get("equivalent")])
        problems.extend(mutation_problems(code, record, out))
    ts["gate_post"]["ok"] = not problems
    return problems


def mutation_problems(code: int, record: Dict[str, Any], out: str) -> List[str]:
    """判定变异检查。mutate --tree 的退出码只说明它跑完了：变异漏网时也是 0（pi_dispatch.py 的 cmd_mutate），
    所以读它写下的 mutations.json：意外漏网、没生效或出错的变异都不行，至少要抓住一条。"""
    results = record.get("results") or []
    if code != 0 or not results:
        return ["变异检查没有跑完（退出码 %d）：\n%s" % (code, tail(out, 25))]

    def statuses(item: Dict[str, Any]) -> Dict[str, str]:
        runs = item.get("commands") or {}
        return {cid: run.get("status") for cid, run in runs.items()} or {"": item.get("status")}

    problems: List[str] = []
    missed = [r.get("id") for r in results
              if any(statuses(r).get(cid, r.get("status")) == "missed" for cid in r.get("unexpected") or [])]
    broken = [r.get("id") for r in results if ({r.get("status")} | set(statuses(r).values())) & {"skipped", "error"}]
    if missed:
        problems.append("%d 条变异漏网、也没有声明等价：%s" % (len(missed), "、".join(map(str, missed))))
    if broken:
        problems.append("%d 条变异没有生效或运行出错（skipped / error；old 片段要在文件里逐字出现）：%s" % (
            len(broken), "、".join(map(str, broken))))
    if not any("caught" in statuses(r).values() for r in results):
        problems.append("没有一条变异被抓住：变异检查什么也没证明")
    return problems


# ---------------------------------------------------------------------------
# 内核代办：执行端、JEV、结项
# ---------------------------------------------------------------------------

def run_exec(hub: Hub, ts: Dict[str, Any]) -> Dict[str, str]:
    """执行端的一个 attempt：prepare → run（同步等待）→ check --fresh；从执行报告生成交付信的正文。"""
    key = ts["contract"]["key"]
    code, out = run_pd(hub, ["prepare", key], timeout=1800)
    match = re.search(r"(\.agent[\\/]runs[\\/][a-z0-9-]+[\\/]attempt-\d{3})", out)
    if code != 0 or not match:
        ts["exec"] = {"run_dir": None, "check_ok": False, "error": "prepare 失败：%s" % tail(out, 15)}
        return {"摘要": "prepare 失败，执行端没有开始", "提交": "无", "验证": tail(out, 15), "偏离": "无",
                "需协调人决定": "无", "证据": "无"}
    run_dir = (hub.repo / match.group(1)).resolve()
    ts["contract"]["dispatched"] = True  # 这个版本派遣过了：之后再改（热修补）就要出新版本
    budget = 1800
    try:
        contract = json.loads(read_text(contract_paths(hub, ts)[1]))
        budget = int((contract.get("budget") or {}).get("max_wall_seconds_per_attempt", 1200)) + 900
    except (ValueError, TypeError):
        pass
    hub.append_event("exec.started", task=ts["task"], run_dir=str(run_dir))
    run_code, _run_out = run_pd(hub, ["run", str(run_dir)], timeout=budget)
    return finish_exec(hub, ts, run_dir, run_code)


def finish_exec(hub: Hub, ts: Dict[str, Any], run_dir: Path, run_code: Optional[int]) -> Dict[str, str]:
    """attempt 跑完之后的核验：check --fresh、范围门禁与 attempt 状态；从执行报告生成交付信的正文。
    exec-recheck 也走这里：内核中途停下或判定逻辑修过之后，对已有的 attempt 重新核验，不占新的尝试次数。"""
    # 状态在 state.json 的 "state" 键（pi_dispatch.get_state）；T001 时这里读成了 "status"，恒为空，执行阶段永远判不过
    status = pd.get_state(run_dir)
    check_code, check_out = run_pd(hub, ["check", str(run_dir), "--fresh"], timeout=3600)
    scope = json.loads(read_text(run_dir / "scope.json") or "{}")
    violations = scope.get("violations") or []
    report = json.loads(read_text(run_dir / "executor-report.json") or "{}")
    rel = run_dir.resolve().relative_to(hub.repo.resolve()).as_posix()
    ts["exec"] = {"run_dir": str(run_dir), "status": status, "run_exit": run_code, "check_exit": check_code,
                  "scope_violations": len(violations), "check_ok": status == "NEEDS_REVIEW" and check_code == 0
                  and not violations, "check_tail": tail(check_out, 20),
                  "conflicts": len(report.get("contract_conflicts") or [])}
    hub.append_event("exec.finished", task=ts["task"], run_dir=str(run_dir), status=status,
                     check_exit=check_code, scope_violations=len(violations))

    def listing(name: str) -> str:
        values = report.get(name) or []
        return "；".join(str(v.get("text") if isinstance(v, dict) and v.get("text") else v) for v in values) or "无"

    dod = report.get("dod") or []
    done = "、".join("%s:%s" % (d.get("id"), d.get("status")) for d in dod if isinstance(d, dict)) or "（报告没有 DoD）"
    verdict_line = "内核 check --fresh：%s；范围违规 %d 条；attempt 状态 %s" % (
        "通过" if check_code == 0 else "失败（退出码 %d）" % check_code, len(violations), status)
    return {"摘要": ("执行端自述 %s；DoD：%s；改动 %d 个文件" % (
                report.get("executor_status") or "未知", done, len(report.get("changed_files") or [])))[:400],
            "提交": "无（候选补丁 %s/candidate.patch）" % rel,
            "验证": verdict_line,
            "偏离": "解读：%s；局限：%s" % (listing("interpretations"), listing("limitations")),
            "需协调人决定": "合同矛盾：%s；未决问题：%s" % (listing("contract_conflicts"), listing("unresolved_questions")),
            "证据": "%s/summary.md、%s/executor-report.md、%s/checks/" % (rel, rel, rel)}


def load_contract_screen() -> Dict[str, Any]:
    from codekit import decisions
    path = TEMPLATE_DIR / "questions"
    batteries = decisions.load_batteries(path)
    return batteries["contract-screen"]


def jev_flag(answer: Dict[str, Any], question: Dict[str, Any], thresholds: Dict[str, Any]) -> str:
    """按题库阈值标出要审核端留意的题，附上那一档的判据：JEV 只回概率，不写理由（T001 的 3j 只有四个数）。"""
    criteria = question.get("criteria")
    if answer.get("type") == "noul":
        p = float(answer.get("noul", 0.0))
        level = ("需关注" if p >= float(thresholds.get("action", 2)) else
                 "留意" if p >= float(thresholds.get("review", 2)) else "")
        criterion = criteria.get("true") if isinstance(criteria, dict) else None
    elif answer.get("type") == "score":
        score = float(answer.get("score", 0.0))
        level = "需关注" if score >= float(thresholds.get("severity_action", 99)) else ""
        index = int(round(score))
        criterion = criteria[index] if isinstance(criteria, list) and 0 <= index < len(criteria) else None
    else:
        return ""
    if not level:
        return ""
    return " ——【%s】%s" % (level, "判据：%s" % criterion if criterion else "")


def run_jev(hub: Hub, ts: Dict[str, Any], suffix: str) -> Dict[str, str]:
    """JEV 端：取被评对象那封信正文的四个字段，用题库调用决策 API（shadow 语义：只给审核端参考）。"""
    from codekit import decisions
    subject_stage = "2-contract" if suffix == "3j-jev" else "5-exec"
    subject = ts["stages"][subject_stage].get("fields") or {}
    summary = {k: subject.get(k, "") for k in ("摘要", "验证", "偏离", "需协调人决定")}
    contract = {}
    try:
        contract = json.loads(read_text(contract_paths(hub, ts)[1]))
    except (ValueError, KeyError):
        pass
    if suffix == "3j-jev":
        battery = load_contract_screen()
        plan_report = read_text(hub.task_dir("%s-1-plan" % ts["task"]) / "report.md")[:4000]
        state = {"planned_goal": plan_report, "contract_summary": summary,
                 "contract_scope": contract.get("scope"), "definition_of_done": contract.get("definition_of_done")}
    else:
        battery = decisions.load_locked_batteries(hub.repo / "plugins" / "decisions")["report-screen"]
        run_dir = Path(ts["exec"]["run_dir"])
        report = json.loads(read_text(run_dir / "executor-report.json") or "{}")
        scope = json.loads(read_text(run_dir / "scope.json") or "{}")
        observed = json.loads(read_text(run_dir / "observations.json") or "{}")
        # 客观指纹与执行端的自述放在一起：JEV 才能看出“自述完成而无证据”“弱化测试”（docs/实际问题/决策端.md）
        state = {"contract_goal": contract.get("title"), "contract_scope": contract.get("scope"),
                 "definition_of_done": contract.get("definition_of_done"),
                 "executor_report": {"text": json.dumps(summary, ensure_ascii=False),
                                     "contract_conflicts": len(report.get("contract_conflicts") or []),
                                     "unresolved_questions": len(report.get("unresolved_questions") or [])},
                 "observations": {"check_exit": ts["exec"].get("check_exit"),
                                  "scope_violations": ts["exec"].get("scope_violations"),
                                  "changed_files": [f.get("path") for f in scope.get("files") or [] if isinstance(f, dict)],
                                  "review_hints": observed.get("review_hints"),
                                  "whitebox_exit": ts["gate_post"].get("whitebox_exit"),
                                  "mutation_counts": ts["gate_post"].get("mutation_counts")}}
    settings = decisions.Settings()
    settings.mode, settings.configured_mode, settings.reason = "shadow", "shadow", "hub"
    settings.points = [battery["id"]]
    session = decisions.Session(settings, hub.root / "ledger" / "decisions.jsonl")
    result = session.ask(battery, state, context={"task": ts["task"], "stage": suffix})
    lines = []
    questions = battery.get("questions") or {}
    for name, answer in sorted((result.get("answers") or {}).items()):
        text, confidence = decisions.answer_value(answer)
        question = questions.get(name) or {}
        label = (battery.get("labels") or {}).get(name, name)
        lines.append("%s：%s（置信 %.2f）%s" % (label, text, confidence,
                                            jev_flag(answer, question, battery.get("thresholds") or {})))
    ts["jev"][suffix] = {"status": result["status"], "reason": result.get("reason"), "answers": result.get("answers"),
                         "battery": battery["id"], "battery_version": battery["version"], "at": utc_now()}
    report_md = "# JEV 判断（%s）\n\n- 题库：%s %s\n- 结果：%s %s\n\n%s\n" % (
        suffix, battery["id"], battery["version"], result["status"], result.get("reason") or "",
        "\n".join("- " + line for line in lines) or "- （无意见）")
    write_text_atomic(hub.task_dir("%s-%s" % (ts["task"], suffix)) / "report.md", report_md)
    verdict = "；".join(lines) if lines else "无意见（%s）" % (result.get("reason") or result["status"])
    return {"摘要": ("JEV（%s）：%s" % (battery["id"], verdict))[:600], "提交": "无",
            "验证": "决策 API %s，%s ms" % (result["status"], result.get("latency_ms")),
            "偏离": "无", "需协调人决定": "无（JEV 只是参考，门禁不读）",
            "证据": ".agent/mailbox/tasks/%s-%s/report.md" % (ts["task"], suffix)}


def finalize(hub: Hub, ts: Dict[str, Any]) -> Tuple[bool, str]:
    """结项：把终审报告写成复审记录，verdict PASS，再 integrate（本地分支，ff-only，不推送）。
    可以重试：attempt 已经是 PASS 就不再记一次结论。"""
    run_dir = Path(ts["exec"]["run_dir"])
    if pd.get_state(run_dir) != "PASS":
        problem = record_pass(hub, ts, run_dir)
        if problem:
            return False, problem
    oracle = ts["oracle"].get("sha")
    if oracle and subprocess.run(["git", "merge-base", "--is-ancestor", oracle, "HEAD"], cwd=str(hub.repo),
                                 stdin=subprocess.DEVNULL).returncode != 0:
        # 候选以门禁的基准测试提交为基线：它不在当前分支上时，integrate 只挑“基线→候选”的改动，
        # 当前末端上没有基准测试，合同检查跑不通（T001 第一次结项就卡在这里）。它是一审审过、锁定的验收测试，先带上。
        try:
            git(["merge", "--ff-only", oracle], hub.repo)
        except HubError as exc:
            return False, "基准测试提交 %s 不能 ff 到当前分支（分支已经分叉？）：%s" % (oracle[:12], exc)
        ts["oracle"]["landed_at"] = utc_now()
        hub.append_event("oracle.landed", task=ts["task"], sha=oracle)
    code, out = run_pd(hub, ["integrate", str(run_dir)], timeout=3600)
    ts["integrated"] = {"exit": code, "tail": tail(out, 15), "at": utc_now()}
    if code != 0:
        return False, "integrate 没有落地（退出码 %d）：\n%s" % (code, tail(out, 15))
    return True, tail(out, 6)


def record_pass(hub: Hub, ts: Dict[str, Any], run_dir: Path) -> Optional[str]:
    """把终审报告写成复审记录，记 verdict PASS；返回问题（成功时为 None）。"""
    review_dir = hub.repo / ".agent" / "reviews" / ts["contract_task"]
    review_dir.mkdir(parents=True, exist_ok=True)
    review_path = review_dir / ("%s-hub.md" % run_dir.name)
    audit_report = read_text(hub.task_dir("%s-7-audit-post" % ts["task"]) / "report.md")
    gate = ts["gate_post"]
    body = [
        "# 复审记录：%s %s（七端信箱 hub）" % (ts["contract_task"], run_dir.name), "",
        "- 合同：%s（base %s）" % (ts["contract"]["key"], ts["oracle"].get("sha")),
        "- 内核 check --fresh：退出码 %s；范围违规 %s" % (ts["exec"].get("check_exit"), ts["exec"].get("scope_violations")),
        "- 战后门禁：白盒测试退出码 %s；变异检查退出码 %s" % (gate.get("whitebox_exit"), gate.get("mutate_exit")),
        "- JEV：一审前 %s；终审前 %s" % ((ts["jev"].get("3j-jev") or {}).get("status"),
                                       (ts["jev"].get("6j-jev") or {}).get("status")),
        "- 复审者：audit-sonnet（claude-sonnet-5-5，max），终审报告如下", "", "## 终审报告", "",
        audit_report.strip() or "（终审报告为空）", "", "Verdict: PASS", ""]
    if review_path.exists():
        review_path = review_dir / ("%s-hub-%s.md" % (run_dir.name, utc_compact()))
    review_path.write_text("\n".join(body), encoding="utf-8", newline="\n")
    code, out = run_pd(hub, ["verdict", str(run_dir), "--verdict", "PASS", "--review", str(review_path)])
    if code != 0:
        return "verdict PASS 被门禁拒绝：\n%s" % tail(out, 20)
    return None


# ---------------------------------------------------------------------------
# 回合的输入与输出
# ---------------------------------------------------------------------------

OUTPUT_SPECS = {
    "coordinator": '{"letters": [{"to": "<收信人>", "type": "开工|返工|通过|等待|停止|汇报|提问", "task_id": "<阶段任务或主任务>", '
                   '"in_reply_to": "<msg-id 或 none>", "摘要": "…", "提交": "无", "验证": "…", "偏离": "无", '
                   '"需协调人决定": "无", "证据": "…", "brief": "<开工、返工时必填：下一阶段任务书的 Markdown 全文>"}], '
                   '"state": "<你的进度断点，Markdown>"}',
    "worker": '{"letter": {"type": "交付|返工完成|提问|阻塞|交接|进度", "in_reply_to": "<msg-id>", "摘要": "…", '
              '"提交": "…", "验证": "…", "偏离": "…", "需协调人决定": "…", "证据": "…"}, '
              '"report": "<report.md 全文>", "state": "<state.md 全文>"}',
}
ROLE_EXTRA_OUTPUT = {
    "contract": '另加 "contract_md": "<合同 Markdown 全文>"',
    "gate": '战后模式另加 "mutation_spec": {"commands": [{"id": "W1", "argv": ["python", "-m", "pytest", "<文件>", "-q"]}], '
            '"mutations": [{"name": "…", "file": "<相对路径>", "old": "<原文片段>", "new": "<改坏后的片段>"}]}；'
            '确实测不出来的等价改写，在那一条里加 "equivalent": "<为什么改了行为也不变>"（终审会逐条复核），'
            '其余每条都必须被抓住',
    "audit": 'letter 里另加 "结论": "通过|返工"；返工时再加 "退回": "合同端|门禁端|战后门禁|执行端|规划端"'
             '（一审只能退回规划端、合同端、门禁端）与 "阻塞项": "<逐条列出必须改的问题，只列会导致打回的>"',
}


def role_prompt(agent: str) -> str:
    spec = ROSTER[agent]
    values = {"名字": agent, "角色": spec["label"], "协调人": COORDINATOR, "仓库": "ThemisTally"}
    if agent == COORDINATOR:
        return render_template("coordinator.md", values)
    return render_template("worker.md", values, role=spec["role"])


def stage_status_table(hub: Hub, ts: Dict[str, Any]) -> str:
    rows = ["| 阶段 | 工人 | 状态 | 备注 |", "|---|---|---|---|"]
    for suffix in STAGE_ORDER:
        stage = ts["stages"][suffix]
        rows.append("| %s-%s | %s | %s | %s |" % (ts["task"], suffix, STAGE_WORKER[suffix], stage["status"],
                                                 (stage.get("note") or "").replace("\n", " ")[:160]))
    facts = [
        "- 合同：%s（validate %s）" % (ts["contract"].get("key") or "无",
                                      "通过" if ts["contract"].get("validated") else "未通过/未写"),
        "- 基准测试：%s" % ("已锁定 %s" % ts["oracle"]["sha"][:10] if ts["oracle"].get("locked") else "未锁定"),
        "- 一审：%s；终审：%s" % (ts["audit_pre"].get("verdict") or "无", ts["audit_post"].get("verdict") or "无"),
        "- 执行：%s" % (("check 通过" if ts["exec"].get("check_ok") else "check 未通过")
                        if ts["exec"].get("run_dir") else "未开始"),
        "- 战后门禁：%s" % (("通过" if ts["gate_post"].get("ok") else "未通过") if ts["gate_post"].get("ran") else "未开始"),
        "- JEV：%s" % ("启用" if ts.get("jev_enabled") else "未启用"),
    ]
    moves = allowed_moves(ts)
    return "\n".join(rows + [""] + facts + ["", "**内核此刻允许的下一步**（只是提示，投递时照样逐封校验）：",
                                           "\n".join("- " + m for m in moves) or "- （没有：等待工人或站主）"])


def turn_prompt(hub: Hub, ts: Dict[str, Any], agent: str, task_id: str, letters: List[str],
                workspace: Path, error: Optional[str] = None) -> str:
    spec = ROSTER[agent]
    role = spec["role"]
    task_dir = hub.task_dir(task_id)
    parts = ["# 本回合输入（内核）", "",
             "- 你：%s（%s）" % (agent, spec["label"]),
             "- 主任务：%s %s" % (ts["task"], ts["title"]),
             "- 本回合的任务：%s" % task_id,
             "- 工作目录：%s" % workspace,
             "- 仓库主工作区（只读参考）：%s" % hub.repo,
             "- 你的 state.md：%s" % (task_dir / "state.md"),
             "- 你的 report.md：%s（内核按你的输出写）" % (task_dir / "report.md")]
    if error:
        parts += ["", "## 上一次输出没有通过内核校验，请改正后重新交出", "", error]
    parts += ["", "## 新信", ""] + (letters or ["（没有新信）"])
    if role == "coordinator":
        parts += ["", "## 主任务状态（内核）", "", stage_status_table(hub, ts)]
        owner_brief = read_text(hub.task_dir(ts["task"]) / "brief.md")
        if owner_brief and any("\ntype: 任务\n" in letter for letter in letters):
            parts += ["", "## 站主的任务书（%s）" % (hub.task_dir(ts["task"]) / "brief.md"), "", owner_brief]
    else:
        brief = read_text(task_dir / "brief.md")
        parts += ["", "## 任务书（%s）" % (task_dir / "brief.md"), "", brief or "（没有任务书）"]
        state = read_text(task_dir / "state.md")
        if state:
            parts += ["", "## 你上次留下的 state.md", "", state]
        if role == "audit":
            stage = stage_of(task_id)[1]
            history = [h for h in ts.get("audit_history") or [] if h.get("stage") == stage]
            if history and history[-1].get("verdict") == "返工":
                parts += ["", "## 上一轮你列的阻塞项（复审封板）", "", history[-1].get("blockers") or "（空）", "",
                          "- 先逐条复核这些阻塞项是否已经解决，在报告里逐条写结论。",
                          "- 新的打回理由只能来自本轮新改动的内容，或者会导致错误结果的严重问题；"
                          "上一轮没提的建议类意见不能在这一轮升级成阻塞项。"]
            if stage == "7-audit-post" and ts["gate_post"].get("mutate_record"):
                parts += ["", "- 内核的变异记录（逐条结果）：%s" % (hub.repo / ts["gate_post"]["mutate_record"]),
                          "- 白盒测试的输出：%s" % (hub.repo / (ts["gate_post"].get("whitebox_log") or ""))]
            if stage == "7-audit-post" and ts["gate_post"].get("equivalent"):
                parts += ["", "## 门禁端声明的等价变异（逐条复核：改了真的测不出来吗）", ""] + [
                    "- " + item for item in ts["gate_post"]["equivalent"]]
        if role == "contract":
            parts += ["", "## 合同要求（内核会逐项核对）", "",
                      "- 第一行：`# TASK: %s`；Identity 的 plan_version 写 %d；base_sha 先写 %s（门禁提交后内核会改）。" % (
                          ts["contract_task"], int(ts["contract"].get("version", 0)) + 1, ts["base_head"]),
                      "- executor 行照抄：`%s`；integration_actions 写 `local_branch, merge`。" % CONTRACT_EXECUTOR_LINE,
                      "- Scope 的 forbidden_paths 包含 `%s`（门禁测试，执行端不能碰）。" % gate_pattern(ts),
                      "- Validation commands 要有一条门禁检查，照这个格式写（ID 可以换）："
                      "`- VG1（必要，基线应失败）：`python -m pytest %s -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · "
                      "输出须匹配：`\\d+ passed``。门禁测试由门禁端稍后写好、内核做成基线提交，你只写这一行。" % gate_file(ts, "baseline"),
                      "- 格式照 .agents/skills/plan-task/contract-template.md 与 contract-guide.md（在工作目录里，先读）。"]
        if role == "gate":
            stage = stage_of(task_id)[1]
            target = gate_file(ts, "baseline" if stage == "3-gate-pre" else "whitebox")
            parts += ["", "## 门禁要求（内核会核对）", "",
                      "- 只新增 `%s` 这一个文件，不改动任何已有文件；在工作目录里写。" % target,
                      "- 用 `python -m pytest %s -q` 自己跑一遍：%s。" % (
                          target, "战前的基准测试应当在当前基线上失败（目标功能还没实现）" if stage == "3-gate-pre"
                          else "战后的白盒测试应当在候选上全部通过")]
    parts += ["", "## 输出格式", "", "最后一条消息末尾附一个 ```json 代码块（只认最后一个）：", "",
              "```", OUTPUT_SPECS["coordinator" if role == "coordinator" else "worker"], "```"]
    if role in ROLE_EXTRA_OUTPUT:
        parts.append(ROLE_EXTRA_OUTPUT[role])
    return "\n".join(parts) + "\n"


def letter_from_output(agent: str, task_id: str, data: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, str]]:
    raw = data.get("letter") if isinstance(data.get("letter"), dict) else {}
    meta = {"from": agent, "to": COORDINATOR, "task-id": task_id,
            "in-reply-to": str(raw.get("in_reply_to") or "none"), "type": str(raw.get("type") or "")}
    fields = {key: str(raw.get(key, "")).strip() for key in FIELDS}
    for key in VERDICT_FIELDS:
        if raw.get(key):
            fields[key] = str(raw[key]).strip()
    return meta, fields


# ---------------------------------------------------------------------------
# 调度循环
# ---------------------------------------------------------------------------

class Engine:
    def __init__(self, hub: Hub, runner: Optional[TurnRunner] = None) -> None:
        self.hub = hub
        self.runner = runner or TurnRunner(hub)

    # -- 选下一件事 -------------------------------------------------------------
    def next_job(self) -> Optional[Tuple[str, List[Path]]]:
        best: Optional[Tuple[str, str, List[Path]]] = None
        for agent in ROSTER:
            letters = self.hub.unread(agent)
            if letters and (best is None or letters[0].name < best[1]):
                best = (agent, letters[0].name, letters)
        if best is None:
            return None
        agent, _first, letters = best
        if agent == COORDINATOR:
            return agent, letters
        task_id = parse_letter(read_text(letters[0]))[0].get("task-id", "")
        same = [p for p in letters if parse_letter(read_text(p))[0].get("task-id", "") == task_id]
        return agent, same

    def step(self) -> bool:
        job = self.next_job()
        if job is None:
            return False
        agent, paths = job
        state = self.hub.load_state()
        if agent == COORDINATOR:
            self.coordinator_turn(state, paths)
        else:
            self.worker_job(state, agent, paths)
        return True

    # -- 协调人 ---------------------------------------------------------------
    def coordinator_turn(self, state: Dict[str, Any], paths: List[Path]) -> None:
        """协调人一个回合只处理一个主任务的信（最早那封所属的主任务）；别的主任务的信留在 new 里。"""
        mains = [stage_of(parse_letter(read_text(p))[0].get("task-id", ""))[0] for p in paths]
        main = mains[0]
        if main is None or main not in state["tasks"]:
            taken = self.hub.take(paths[0])
            self.hub.append_event("coordinator.skipped", reason="信里没有登记过的主任务", letters=[taken.name])
            return
        paths = [p for p, m in zip(paths, mains) if m == main]
        texts = [read_text(p) for p in paths]
        for path in paths:
            self.hub.take(path)
        ts = state["tasks"][main]
        if ts.get("status") != "active":
            self.hub.append_event("coordinator.skipped", reason="主任务 %s 状态为 %s" % (main, ts.get("status")),
                                  letters=[p.name for p in paths])
            return
        workspace = ensure_worktree(self.hub, ts, "base", ts["base_head"])
        self.hub.save_state(state)
        prompt = turn_prompt(self.hub, ts, COORDINATOR, main, texts, workspace)
        turn = self.runner.run(COORDINATOR, main, workspace, role_prompt(COORDINATOR), prompt)
        if turn["output"] is None and not turn["violations"] and not turn.get("api_error"):
            prompt = turn_prompt(self.hub, ts, COORDINATOR, main, texts, workspace, error=turn["output_error"])
            turn = self.runner.run(COORDINATOR, main, workspace, role_prompt(COORDINATOR), prompt,
                                   retry_of=turn["turn_id"])
        state = self.hub.load_state()
        ts = state["tasks"][main]
        if turn["violations"] or turn["output"] is None:
            reason = "；".join(turn["violations"]) or turn["output_error"] or "没有输出"
            self.escalate(ts, "协调人回合作废：%s（回合 %s）" % (reason, turn["turn_id"]))
            self.hub.save_state(state)
            return
        output = turn["output"]
        if isinstance(output.get("state"), str):
            write_text_atomic(self.hub.task_dir(main) / "state.md", output["state"])
        rejected: List[str] = []
        delivered = 0
        for item in output.get("letters") or []:
            reason = self.deliver_coordinator_letter(state, item)
            if reason:
                rejected.append("%s → %s（%s）：%s" % (item.get("type"), item.get("to"), item.get("task_id"), reason))
            else:
                delivered += 1
        ts = state["tasks"][main]
        if rejected:
            ts["coordinator_rejections"] = int(ts.get("coordinator_rejections", 0)) + 1
            if ts["coordinator_rejections"] >= 3:
                self.escalate(ts, "协调人连续 %d 个回合的信被内核拒收：\n%s" % (ts["coordinator_rejections"], "\n".join(rejected)))
            else:
                self.hub.deliver({"from": KERNEL, "to": COORDINATOR, "task-id": main, "in-reply-to": "none",
                                  "type": "核验"},
                                 {"摘要": "你上一回合有 %d 封信被内核拒收，%d 封已投递" % (len(rejected), delivered),
                                  "提交": "无", "验证": "内核按状态机核对", "偏离": "\n".join(rejected)[:1500],
                                  "需协调人决定": "按“内核此刻允许的下一步”改发", "证据": turn["turn_dir"]})
        else:
            ts["coordinator_rejections"] = 0
        self.hub.save_state(state)

    def deliver_coordinator_letter(self, state: Dict[str, Any], item: Dict[str, Any]) -> Optional[str]:
        if not isinstance(item, dict):
            return "信不是对象"
        meta = {"from": COORDINATOR, "to": str(item.get("to") or ""), "task-id": str(item.get("task_id") or ""),
                "in-reply-to": str(item.get("in_reply_to") or "none"), "type": str(item.get("type") or "")}
        fields = {key: str(item.get(key, "")).strip() or "无" for key in FIELDS}
        body_lines = len(render_letter(dict(meta, **{"msg-id": "x"}), fields).splitlines()) - 8
        errors = letter_errors(meta, fields, body_lines)
        if errors:
            return "；".join(errors)
        main, suffix = stage_of(meta["task-id"])
        ts = state["tasks"].get(main or "")
        reason = guard(ts, meta)
        if reason:
            self.hub.append_event("letter.rejected", sender=COORDINATOR, to=meta["to"], type=meta["type"],
                                  task_id=meta["task-id"], reason=reason)
            return reason
        if meta["type"] in ("开工", "返工") and meta["to"] in WORKERS:
            brief = item.get("brief")
            if ROSTER[meta["to"]]["adapter"] in ("claude", "pi"):
                if not isinstance(brief, str) or not brief.strip():
                    return "开工、返工要附 brief（下一阶段任务书的 Markdown 全文）"
                self.write_brief(meta["task-id"], brief)
            if meta["type"] == "返工" and suffix == "3-gate-pre" and hotfix_reason(ts):
                ts["hotfix"] = {"reason": hotfix_reason(ts), "at": utc_now(), "previous_oracle": ts["oracle"].get("sha")}
                self.hub.append_event("hotfix.started", task=ts["task"], reason=ts["hotfix"]["reason"])
            if meta["type"] == "返工" and (ts.get("owner_rework") or {}).get("suffix") == suffix:
                self.hub.append_event("owner_rework.used", task=ts["task"], **ts.pop("owner_rework"))
            ts["stages"][suffix]["status"] = "assigned"
            ts["stages"][suffix]["assigned_at"] = utc_now()
            ts["stages"][suffix]["kind"] = meta["type"]
        self.hub.deliver(meta, fields)
        self.hub.save_state(state)
        return None

    def write_brief(self, task_id: str, brief: str) -> None:
        directory = self.hub.task_dir(task_id)
        directory.mkdir(parents=True, exist_ok=True)
        current = directory / "brief.md"
        keep_previous(current)
        write_text_atomic(current, brief.rstrip() + "\n")

    def escalate(self, ts: Dict[str, Any], text: str) -> None:
        """协调人自己出了问题（回合作废，或连续三个回合的信都被拒收）：主任务转为 blocked，写信给站主。
        站主发“回复”之后恢复为 active。"""
        ts["notes"].append({"at": utc_now(), "text": text[:2000]})
        ts["status"] = "blocked"
        self.hub.deliver({"from": KERNEL, "to": OWNER, "task-id": ts["task"], "in-reply-to": "none", "type": "阻塞"},
                         {"摘要": text.splitlines()[0][:200], "提交": "无", "验证": "内核", "偏离": text[:1500],
                          "需协调人决定": "请站主处理后用 kit_hub.py send %s --type 回复 恢复" % ts["task"],
                          "证据": ".agent/mailbox/ledger/events.jsonl"})

    # -- 工人 -----------------------------------------------------------------
    def worker_job(self, state: Dict[str, Any], agent: str, paths: List[Path]) -> None:
        texts = [read_text(p) for p in paths]
        metas = [parse_letter(t)[0] for t in texts]
        task_id = metas[0].get("task-id", "")
        main, suffix = stage_of(task_id)
        ts = state["tasks"].get(main or "")
        taken = [self.hub.take(p) for p in paths]
        kinds = {m.get("type") for m in metas}
        if ts is None or suffix is None or kinds <= set(INFO_TYPES):
            self.hub.append_event("worker.not_woken", agent=agent, task_id=task_id, kinds=sorted(kinds),
                                  letters=[p.name for p in taken])
            return
        adapter = ROSTER[agent]["adapter"]
        if adapter == "dispatcher":
            fields = run_exec(self.hub, ts)
            self.finish_kernel_stage(state, ts, agent, suffix, fields, ok=ts["exec"].get("check_ok", False))
            return
        if adapter == "jev":
            fields = run_jev(self.hub, ts, suffix)
            self.finish_kernel_stage(state, ts, agent, suffix, fields, ok=True)
            return
        workspace = self.stage_workspace(ts, agent, suffix)
        self.hub.save_state(state)
        prompt = turn_prompt(self.hub, ts, agent, task_id, texts, workspace)
        # 返工：干净重启，只带任务书、state 与这封返工信（用户评审建议 2）
        fresh = "返工" in kinds
        turn = self.runner.run(agent, task_id, workspace, role_prompt(agent), prompt, fresh=fresh)
        error = self.output_problem(agent, task_id, turn)
        if error and not turn["violations"] and not turn.get("api_error"):  # 接口报错重试也没用
            prompt = turn_prompt(self.hub, ts, agent, task_id, texts, workspace, error=error)
            turn = self.runner.run(agent, task_id, workspace, role_prompt(agent), prompt, retry_of=turn["turn_id"])
            error = self.output_problem(agent, task_id, turn)
        state = self.hub.load_state()
        ts = state["tasks"][main]
        if turn["violations"] or error:
            reason = "；".join(turn["violations"]) or error
            ts["stages"][suffix].update(status="failed", note="回合作废：%s" % reason)
            if turn.get("api_error") and not turn["violations"]:
                # 环境问题（例如 2026-10-19 旧机器上的 403）：协调人也会遇到同样的错，直接交给站主
                self.escalate(ts, "%s 的回合遇到模型接口报错，阶段已标为 failed：%s（回合 %s）" % (
                    agent, turn["api_error"], turn["turn_id"]))
                self.hub.save_state(state)
                return
            self.hub.save_state(state)
            self.hub.deliver({"from": KERNEL, "to": COORDINATOR, "task-id": task_id, "in-reply-to": "none",
                              "type": "阻塞"},
                             {"摘要": "%s 的回合作废，信没有投递" % agent, "提交": "无", "验证": "内核审计与校验",
                              "偏离": reason[:1500], "需协调人决定": "可以发“返工”让它重做（阶段已标为 failed）",
                              "证据": turn["turn_dir"]})
            return
        output = turn["output"]
        directory = self.hub.task_dir(task_id)
        if isinstance(output.get("report"), str):
            keep_previous(directory / "report.md")  # 返工前的报告留着：上一轮的意见不丢
            write_text_atomic(directory / "report.md", output["report"])
        if isinstance(output.get("state"), str):
            write_text_atomic(directory / "state.md", output["state"])
        meta, fields = letter_from_output(agent, task_id, output)
        problems: List[str] = []
        if meta["type"] in ("交付", "返工完成"):
            problems = self.verify_delivery(ts, agent, suffix, output, fields)
        stage = ts["stages"][suffix]
        stage["fields"] = fields
        if meta["type"] in ("交付", "返工完成"):
            if problems:
                stage.update(status="failed", note="；".join(problems)[:600])
                fields["内核核验"] = "未通过：" + "；".join(problems)[:1200]
            else:
                stage.update(status="delivered", note="", delivered_at=utc_now())
                fields["内核核验"] = "通过"
                invalidate_after(ts, suffix)
                self.after_delivery(ts, suffix, fields)
        self.hub.save_state(state)
        self.hub.deliver(meta, fields)
        if stage["status"] == "delivered":
            self.auto_jev(state, ts, suffix)

    def auto_jev(self, state: Dict[str, Any], ts: Dict[str, Any], suffix: str) -> None:
        """JEV 由内核接着跑（用户 2026-10-19 同意）：上游交付通过、前置条件满足时直接调决策 API，
        不为它单独唤醒协调人；交付信与 JEV 的信一起进协调人信箱，协调人一个回合处理。"""
        jev = AUTO_JEV.get(suffix)
        if not jev or not ts.get("jev_enabled") or _guard_start(ts, jev) is not None:
            return
        ts["stages"][jev].update(status="assigned", assigned_at=utc_now(), kind="内核自动")
        self.hub.append_event("jev.auto", task=ts["task"], stage=jev)
        self.finish_kernel_stage(state, ts, "jev-judge", jev, run_jev(self.hub, ts, jev), ok=True)

    def output_problem(self, agent: str, task_id: str, turn: Dict[str, Any]) -> Optional[str]:
        if turn["output"] is None:
            return turn.get("output_error") or "没有输出"
        meta, fields = letter_from_output(agent, task_id, turn["output"])
        errors = letter_errors(meta, fields, len(render_letter(dict(meta, **{"msg-id": "x"}), fields).splitlines()) - 8)
        return "；".join(errors) if errors else None

    def stage_workspace(self, ts: Dict[str, Any], agent: str, suffix: str) -> Path:
        if suffix == "3-gate-pre":
            record = ts["workspaces"].get("gate") or {}
            if record.get("path") and Path(record["path"]).is_dir() and record.get("commit") != ts["base_head"]:
                # 返工：退回基线、保留文件（基准测试回到“新增”状态），工作目录不变，门禁端的会话才能续接
                git(["reset", "-q", "--mixed", ts["base_head"]], Path(record["path"]))
                record["commit"] = ts["base_head"]
            return ensure_worktree(self.hub, ts, "gate", ts["base_head"])
        if suffix == "4-audit-pre":
            if ts["oracle"].get("sha"):
                return ensure_worktree(self.hub, ts, "gate", ts["oracle"]["sha"])
            return ensure_worktree(self.hub, ts, "base", ts["base_head"])
        if suffix in ("6-gate-post", "7-audit-post"):
            return apply_candidate(self.hub, ts)
        return ensure_worktree(self.hub, ts, "base", ts["base_head"])

    def verify_delivery(self, ts: Dict[str, Any], agent: str, suffix: str, output: Dict[str, Any],
                        fields: Dict[str, str]) -> List[str]:
        if suffix == "1-plan":
            return [] if str(output.get("report") or "").strip() else ["规划端的 report 为空"]
        if suffix == "2-contract":
            return accept_contract(self.hub, ts, output)
        if suffix == "3-gate-pre":
            return accept_gate_pre(self.hub, ts, Path(ts["workspaces"]["gate"]["path"]))
        if suffix == "6-gate-post":
            key = "post-%s" % Path(ts["exec"]["run_dir"]).name
            return accept_gate_post(self.hub, ts, Path(ts["workspaces"][key]["path"]), output)
        if suffix in ("4-audit-pre", "7-audit-post"):
            if fields.get("结论") not in VERDICTS:
                return ["审核结论缺失"]
            if suffix == "4-audit-pre":
                return dod_coverage_problems(self.hub, ts, str(output.get("report") or ""))
        return []

    def after_delivery(self, ts: Dict[str, Any], suffix: str, fields: Dict[str, str]) -> None:
        if suffix in ("4-audit-pre", "7-audit-post"):
            # 不随 invalidate_after 清掉：返工之后的下一轮审核要拿上一轮的阻塞项来复核（复审封板）
            ts.setdefault("audit_history", []).append({
                "stage": suffix, "verdict": fields.get("结论"), "target": fields.get("退回"),
                "blockers": fields.get("阻塞项", ""), "at": utc_now()})
        if suffix == "4-audit-pre":
            ts["audit_pre"].update(verdict=fields.get("结论"), target=fields.get("退回"),
                                   contract_sha256=ts["contract"].get("sha256"), oracle_sha=ts["oracle"].get("sha"))
            if fields.get("结论") == "返工":
                ts["audit_pre"]["fails"] = int(ts["audit_pre"].get("fails", 0)) + 1
        if suffix == "7-audit-post":
            ts["audit_post"].update(verdict=fields.get("结论"), target=fields.get("退回"))

    def finish_kernel_stage(self, state: Dict[str, Any], ts: Dict[str, Any], agent: str, suffix: str,
                            fields: Dict[str, str], ok: bool) -> None:
        stage = ts["stages"][suffix]
        stage["fields"] = fields
        if ok:
            stage.update(status="delivered", delivered_at=utc_now(), note="")
            invalidate_after(ts, suffix)
        else:
            stage.update(status="failed", note=fields.get("验证", "")[:300])
            if suffix == "5-exec":
                invalidate_after(ts, suffix)
        fields["内核核验"] = "通过" if ok else "未通过（短路：只能返工给执行端）"
        self.hub.save_state(state)
        self.hub.deliver({"from": agent, "to": COORDINATOR, "task-id": "%s-%s" % (ts["task"], suffix),
                          "in-reply-to": "none", "type": "交付"}, fields)

    def recheck_exec(self, main: str) -> Dict[str, Any]:
        """站主命令 exec-recheck：对最近一次 attempt 重新核验，不重跑执行端、不占新的尝试次数。
        只在执行阶段判为失败、attempt 目录还在时可用；结果照常作为执行端的交付信送给协调人。"""
        state = self.hub.load_state()
        ts = state["tasks"].get(main)
        if ts is None:
            raise HubError("没有登记主任务 %s" % main, EXIT_USAGE)
        run_dir = ts["exec"].get("run_dir")
        if ts["stages"]["5-exec"]["status"] != "failed" or not run_dir or not Path(run_dir).is_dir():
            raise HubError("只有执行阶段判为失败、attempt 目录还在时才能重新核验（现在：%s）"
                           % ts["stages"]["5-exec"]["status"], EXIT_USAGE)
        fields = finish_exec(self.hub, ts, Path(run_dir), ts["exec"].get("run_exit"))
        fields["验证"] = "（站主 exec-recheck 重新核验，没有重跑执行端）" + fields["验证"]
        self.hub.append_event("exec.rechecked", task=main, run_dir=run_dir, check_ok=ts["exec"]["check_ok"])
        self.finish_kernel_stage(state, ts, "exec-step", "5-exec", fields, ok=ts["exec"]["check_ok"])
        return ts["exec"]

    def handle_pass(self, state: Dict[str, Any], meta: Dict[str, str]) -> None:
        """协调人对执行端发“通过”：结项（verdict PASS 与 integrate）。"""
        main, _suffix = stage_of(meta["task-id"])
        ts = state["tasks"][main]
        ok, detail = finalize(self.hub, ts)
        ts["status"] = "done" if ok else ts["status"]
        self.hub.save_state(state)
        self.hub.deliver({"from": KERNEL, "to": OWNER, "task-id": main, "in-reply-to": "none",
                          "type": "核验" if ok else "阻塞"},
                         {"摘要": "%s 结项%s" % (main, "：verdict PASS，已 integrate" if ok else "失败"),
                          "提交": detail.splitlines()[-1][:200] if detail else "无", "验证": "内核 verdict 与 integrate",
                          "偏离": "无" if ok else detail[:1500], "需协调人决定": "无" if ok else "请站主处理",
                          "证据": ".agent/reviews/%s/" % ts["contract_task"]})


# ---------------------------------------------------------------------------
# 命令行
# ---------------------------------------------------------------------------

def find_repo(arg: Optional[str]) -> Path:
    return pd.Repo.discover(arg).root


def cmd_init(args: argparse.Namespace) -> int:
    hub = Hub(find_repo(args.repo))
    hub.ensure()
    ignored = subprocess.run(["git", "check-ignore", "-q", str(MAILBOX / "x")], cwd=str(hub.repo)).returncode == 0
    print("信箱：%s%s" % (hub.root, "" if ignored else "\nWARN  .agent/mailbox/ 没有被 .gitignore 忽略"))
    return EXIT_OK


def cmd_task_new(args: argparse.Namespace) -> int:
    hub = Hub(find_repo(args.repo))
    hub.ensure()
    if not MAIN_TASK_RE.match(args.task):
        raise HubError("主任务号要像 T001", EXIT_USAGE)
    if not SLUG_RE.match(args.slug):
        raise HubError("--slug 只能是小写字母、数字与连字符", EXIT_USAGE)
    brief = Path(args.brief).read_text(encoding="utf-8")
    head = git(["rev-parse", "HEAD"], hub.repo).strip()
    with DirLock(hub.root / ".lock"):
        state = hub.load_state()
        if args.task in state["tasks"]:
            raise HubError("主任务 %s 已存在" % args.task, EXIT_USAGE)
        state["tasks"][args.task] = new_task_state(args.task, args.slug, args.title, head, not args.no_jev)
        write_text_atomic(hub.task_dir(args.task) / "brief.md", brief.rstrip() + "\n")
        hub.save_state(state)
        hub.append_event("task.created", task=args.task, slug=args.slug, base_head=head)
        msg = hub.deliver({"from": OWNER, "to": COORDINATOR, "task-id": args.task, "in-reply-to": "none",
                           "type": "任务"},
                          {"摘要": args.title, "提交": "无", "验证": "无", "偏离": "无", "需协调人决定": "无",
                           "证据": ".agent/mailbox/tasks/%s/brief.md" % args.task})
    print("已登记 %s（基线 %s），任务信 %s 已投给 %s" % (args.task, head[:10], msg, COORDINATOR))
    return EXIT_OK


def cmd_send(args: argparse.Namespace) -> int:
    hub = Hub(find_repo(args.repo))
    text = Path(args.file).read_text(encoding="utf-8") if args.file != "-" else sys.stdin.read()
    fields = {key: "无" for key in FIELDS}
    fields["摘要"] = text.strip()[:2000] or "无"
    meta = {"from": OWNER, "to": COORDINATOR, "task-id": args.task, "in-reply-to": args.reply_to or "none",
            "type": args.type}
    if args.rework:
        if args.type != "回复" or args.rework not in STAGE_ORDER or args.rework in ("3j-jev", "6j-jev"):
            raise HubError("--rework 只能随“回复”发，写阶段后缀（例如 2-contract；JEV 不用返工）", EXIT_USAGE)
        fields["需协调人决定"] = "站主要求 %s-%s 返工：给它发“返工”，brief 写清站主要改的地方" % (args.task, args.rework)
    errors = letter_errors(meta, fields, len(fields["摘要"].splitlines()) + 5)
    if errors:
        raise HubError("；".join(errors), EXIT_USAGE)
    with DirLock(hub.root / ".lock"):
        state = hub.load_state()
        ts = state["tasks"].get(args.task)
        if args.rework and ts is None:
            raise HubError("没有登记主任务 %s" % args.task, EXIT_USAGE)
        msg = hub.deliver(meta, fields)
        if ts is not None and args.type == "停止":
            ts["status"] = "stopped"
        elif ts is not None and ts.get("status") == "blocked":
            ts["status"], ts["coordinator_rejections"] = "active", 0
        if args.rework:
            # 一审之前站主也能要合同改版（T001：此前只有审核退回或核验失败才放行返工）
            ts["owner_rework"] = {"suffix": args.rework, "msg": msg, "requested_at": utc_now()}
            hub.append_event("owner_rework.requested", task=args.task, suffix=args.rework, msg=msg)
        hub.save_state(state)
    print("已投递 %s" % msg)
    return EXIT_OK


def cmd_exec_recheck(args: argparse.Namespace) -> int:
    hub = Hub(find_repo(args.repo))
    with DirLock(hub.root / ".runner", wait_seconds=1.0):  # 不和正在跑的 hub 抢状态
        result = Engine(hub).recheck_exec(args.task)
    print("%s 执行阶段重新核验：%s（attempt 状态 %s，check --fresh 退出码 %s，范围违规 %s）" % (
        args.task, "通过" if result["check_ok"] else "未通过", result.get("status"), result.get("check_exit"),
        result.get("scope_violations")))
    return EXIT_OK if result["check_ok"] else EXIT_FAIL


def cmd_take(args: argparse.Namespace) -> int:
    hub = Hub(find_repo(args.repo))
    letters = hub.unread(OWNER)
    for path in letters:
        print(read_text(path))
        if not args.peek:
            hub.take(path)
    if not letters:
        print("（站主没有未读信）")
    return EXIT_OK


def cmd_status(args: argparse.Namespace) -> int:
    hub = Hub(find_repo(args.repo))
    state = hub.load_state()
    unread = {agent: len(hub.unread(agent)) for agent in list(ROSTER) + [OWNER]}
    if args.json:
        print(json.dumps({"tasks": state["tasks"], "unread": unread}, ensure_ascii=False, indent=2))
        return EXIT_OK
    for ts in state["tasks"].values():
        print("## %s %s（%s）" % (ts["task"], ts["title"], ts["status"]))
        print(stage_status_table(hub, ts))
        print()
    print("未读：" + ("、".join("%s %d" % (k, v) for k, v in unread.items() if v) or "无"))
    runner = hub.root / ".runner"
    print("运行中的 hub：%s" % (read_text(runner / "owner.json").strip() if runner.is_dir() else "无"))
    return EXIT_OK


def cmd_run(args: argparse.Namespace) -> int:
    hub = Hub(find_repo(args.repo))
    hub.ensure()
    engine = Engine(hub)
    turns = 0
    with DirLock(hub.root / ".runner", wait_seconds=1.0):
        hub.append_event("runner.started", pid=os.getpid(), hub_sha256=HUB_SHA256)
        idle_since = time.monotonic()
        while turns < args.max_steps:
            pending = hub.load_state()
            passes = [p for p in hub.unread("exec-step")
                      if parse_letter(read_text(p))[0].get("type") == "通过"]
            if passes:  # 结项信由内核办，不唤醒任何进程
                meta = parse_letter(read_text(passes[0]))[0]
                hub.take(passes[0])
                engine.handle_pass(pending, meta)
                turns += 1
                continue
            if engine.step():
                turns += 1
                idle_since = time.monotonic()
                continue
            if time.monotonic() - idle_since >= args.idle_exit:
                break
            time.sleep(args.poll)
        hub.append_event("runner.stopped", pid=os.getpid(), steps=turns)
    print("hub 退出：处理了 %d 件事；站主未读 %d 封" % (turns, len(hub.unread(OWNER))))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kit_hub.py", description="七端信箱（3.0 第三轮）")
    parser.add_argument("--repo", help="仓库路径（默认当前目录）")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="建信箱目录").set_defaults(func=cmd_init)
    task = sub.add_parser("task", help="主任务").add_subparsers(dest="task_command", required=True)
    new = task.add_parser("new", help="登记主任务并把任务信投给协调人")
    new.add_argument("task")
    new.add_argument("--slug", required=True, help="合同 task-id 的后半段，例如 desktop-doc")
    new.add_argument("--title", required=True)
    new.add_argument("--brief", required=True, help="站主的任务书（Markdown 文件）")
    new.add_argument("--no-jev", action="store_true", help="本任务不调 JEV")
    new.set_defaults(func=cmd_task_new)
    send = sub.add_parser("send", help="站主给协调人发信（回复、停止）")
    send.add_argument("task")
    send.add_argument("--type", choices=("回复", "停止"), required=True)
    send.add_argument("--file", default="-")
    send.add_argument("--reply-to")
    send.add_argument("--rework", help="随“回复”指定某一阶段返工（阶段后缀，例如 2-contract）")
    send.set_defaults(func=cmd_send)
    recheck = sub.add_parser("exec-recheck", help="对最近一次 attempt 重新核验（不重跑执行端）")
    recheck.add_argument("task")
    recheck.set_defaults(func=cmd_exec_recheck)
    take = sub.add_parser("take", help="站主收信")
    take.add_argument("--peek", action="store_true", help="只看，不移到 cur")
    take.set_defaults(func=cmd_take)
    status = sub.add_parser("status", help="主任务与信箱概况")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)
    run = sub.add_parser("run", help="调度循环（在后台运行；没有事可做 idle-exit 秒后退出）")
    run.add_argument("--max-steps", type=int, default=60)
    run.add_argument("--idle-exit", type=float, default=30.0)
    run.add_argument("--poll", type=float, default=2.0)
    run.set_defaults(func=cmd_run)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    # 控制台代码页不是 UTF-8 时（例如 cp1252）：中文输出会抛错，`send` 从管道读进来的中文会变成乱码
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except HubError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return exc.code
    except pd.DispatchError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return getattr(exc, "code", EXIT_FAIL)


if __name__ == "__main__":
    sys.exit(main())
