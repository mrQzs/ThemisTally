"""契约探针（Python 实现）：stdin 读一个 JSON 请求，stdout 写一个 JSON 结果。

只 import 仓库里的 scripts/ 与标准库，不改它们。请求与结果的形状见 test/harness.ts；
TS 实现的探针（ts_probe.ts）收发同样的 JSON，契约测试与对照测试对两边一视同仁。
stdin 按 UTF-8 读字节（Windows 上 sys.stdin 的缺省编码是 cp1252），stdout 只写 ASCII。
"""
import argparse
import ast
import base64
import collections
import contextlib
import ctypes
import hashlib
import io
import datetime
import errno
import ipaddress
import json
import re
import os
import secrets
import shlex
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
import types
import unicodedata
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # ts/packages/contracts/probes → 仓库根
sys.path.insert(0, str(ROOT / "scripts"))

import kit_config  # noqa: E402
import kit_hub  # noqa: E402
import kit_logs  # noqa: E402
import kit_roles  # noqa: E402
import pi_dispatch  # noqa: E402
import builtins  # noqa: E402
from codekit import decisions as codekit_decisions  # noqa: E402
from codekit import plugins as codekit_plugins  # noqa: E402
from codekit import protocols as codekit_protocols  # noqa: E402
from codekit import secrets as codekit_secrets  # noqa: E402


def wait_for(barrier: str) -> None:
    """并发用例：先报“就绪”，等测试建好起跑文件再一起动手。"""
    sys.stderr.write("ready\n")
    sys.stderr.flush()
    while not os.path.exists(barrier):
        time.sleep(0.001)


# --- 带标签编码（与 src/tagged.ts 相同）---------------------------------------

def from_tagged(item):
    kind = item["t"]
    if kind == "none":
        return None
    if kind == "bool":
        return bool(item["v"])
    if kind == "int":
        return int(item["hex"], 16)
    if kind == "float":
        return struct.unpack(">d", bytes.fromhex(item["bits"]))[0]
    if kind == "str":
        return item["v"]
    if kind == "list":
        return [from_tagged(element) for element in item["v"]]
    if kind == "dict":
        out = {}
        for key, value in item["v"]:
            out[from_tagged(key)] = from_tagged(value)
        return out
    raise ValueError("unknown tag %r" % kind)


def to_tagged(value):
    if value is None:
        return {"t": "none"}
    if isinstance(value, bool):
        return {"t": "bool", "v": value}
    if isinstance(value, int):
        return {"t": "int", "hex": ("-" if value < 0 else "") + format(abs(value), "x")}
    if isinstance(value, float):
        return {"t": "float", "bits": struct.pack(">d", value).hex()}
    if isinstance(value, str):
        return {"t": "str", "v": value}
    if isinstance(value, list):
        return {"t": "list", "v": [to_tagged(element) for element in value]}
    if isinstance(value, dict):
        return {"t": "dict", "v": [[to_tagged(key), to_tagged(element)] for key, element in value.items()]}
    raise TypeError(type(value).__name__)


def dumps_kwargs(options):
    kwargs = {}
    for name in ("ensure_ascii", "indent", "sort_keys", "allow_nan"):
        if name in options:
            kwargs[name] = options[name]
    if options.get("separators") is not None:
        kwargs["separators"] = tuple(options["separators"])
    return kwargs


def text_result(text, encode):
    if encode:
        return {"ok": True, "b64": base64.b64encode(text.encode("utf-8")).decode("ascii")}
    return {"ok": True, "text": text}


# --- 各个 op ------------------------------------------------------------------

def op_publish_new(request):
    published = pi_dispatch.publish_new(Path(request["path"]), base64.b64decode(request["data_b64"]))
    return {"ok": True, "published": published}


def op_pyjson_dumps(request):
    text = json.dumps(from_tagged(request["value"]), **dumps_kwargs(request.get("options") or {}))
    return text_result(text, request.get("encode", False))


def op_pyjson_loads(request):
    return {"ok": True, "value": to_tagged(json.loads(request["text"]))}


def op_mutate_check_anchors(request):
    """④b5a：每份变异清单先校验，通过的再对 tree 做 _check_anchors（标准输出收进结果）。"""
    tree = Path(request["tree"]).resolve()
    results = []
    for spec_path in request["specs"]:
        spec, problems = pi_dispatch._load_mutation_spec(Path(spec_path))
        if problems:
            results.append({"problems": problems})
            continue
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pi_dispatch._check_anchors(tree, spec)
        results.append({"code": code, "out": out.getvalue()})
    return {"ok": True, "results": results}


def op_pystr_call(request):
    """str.find(sub, start)、str.count(sub)、str.replace(sub, new, limit)（④b5b，按码点）。"""
    text, sub = request["text"], request["sub"]
    return {"ok": True, "find": text.find(sub, request["start"]), "count": text.count(sub),
            "replace": text.replace(sub, request["new"], request["limit"])}


def op_pydifflib_call(request):
    """difflib.SequenceMatcher(None, a, b, autojunk)（④b5a）：ratio、匹配块与 opcodes。"""
    import difflib
    matcher = difflib.SequenceMatcher(None, request["a"], request["b"], autojunk=request.get("autojunk", True))
    return {"ok": True, "ratio": to_tagged(matcher.ratio()), "blocks": [list(block) for block in matcher.get_matching_blocks()],
            "opcodes": [list(code) for code in matcher.get_opcodes()]}


def op_pyjson_loads_bytes(request):
    """json.loads(bytes)（④b4a，决策端点的回复）：认编码、解码、解析；错误只分“解码”与“JSON”两类。"""
    try:
        return {"ok": True, "value": to_tagged(json.loads(base64.b64decode(request["data"])))}
    except UnicodeDecodeError:
        return {"ok": False, "error": "decode"}
    except json.JSONDecodeError:
        return {"ok": False, "error": "json"}


def op_pyjson_raw_decode(request):
    """json.JSONDecoder().raw_decode：index 与返回的 end 都按码点。"""
    value, end = json.JSONDecoder().raw_decode(request["text"], request.get("index", 0))
    return {"ok": True, "value": to_tagged(value), "end": end}


def op_pyjson_roundtrip(request):
    """读进来、改完、写回：loads 之后原样 dumps。"""
    text = json.dumps(json.loads(request["text"]), **dumps_kwargs(request.get("options") or {}))
    return text_result(text, request.get("encode", False))


def op_clock_sample(request):
    """时间与编号：各取 count 个样本。回合编号、attempt 目录名、审计编号在 Python 里是内联写的，这里照抄原式。"""
    out = {"utc_now": [], "pd_utc_now": [], "utc_compact": [], "turn_ids": [], "audit_ids": [],
           "msg_ids": {sender: [] for sender in request["senders"]}}
    for _ in range(request.get("count", 1)):
        out["utc_now"].append(kit_hub.utc_now())
        out["pd_utc_now"].append(pi_dispatch.utc_now())
        out["utc_compact"].append(kit_hub.utc_compact())
        out["turn_ids"].append("%s-%s" % (kit_hub.utc_compact(), os.urandom(2).hex()))  # kit_hub.TurnRunner.run
        out["audit_ids"].append("aud-%s" % secrets.token_hex(16))  # kit_config 的审计记录
        for sender in request["senders"]:
            out["msg_ids"][sender].append(kit_hub.new_msg_id(sender))
    out["attempt_dirs"] = ["attempt-%03d" % number for number in request["attempts"]]  # pi_dispatch.allocate_attempt
    return dict(ok=True, **out)


def op_fs_read_text(request):
    return {"ok": True, "text": kit_hub.read_text(Path(request["path"]))}


def op_fs_write_text_atomic(request):
    kit_hub.write_text_atomic(Path(request["path"]), request["text"])
    return {"ok": True}


def op_pid_alive(request):
    return {"ok": True, "alive": pi_dispatch.pid_alive(request["pid"])}


def make_lock(request):
    kind, wait = request["kind"], request.get("wait", 5)
    if kind == "dir":
        return kit_hub.DirLock(Path(request["path"]), wait_seconds=wait)
    if kind == "task":
        return pi_dispatch.TaskLock(types.SimpleNamespace(runs_dir=Path(request["root"])), request["task"],
                                    wait_seconds=wait, stale_seconds=request.get("stale", 300.0))
    return kit_config.ConfigLock(types.SimpleNamespace(agent_dir=Path(request["root"])), wait_seconds=wait)


def op_lock_run(request):
    """拿锁、记下 owner.json 的字节、持有 hold_ms 毫秒再释放。tamper：释放前把令牌改掉（锁已被别人重建）。"""
    lock = make_lock(request)
    try:
        lock.__enter__()
    except kit_config.ConfigError as exc:  # 配置锁的报错文字要逐字一致（第 ③b 片）
        return {"ok": False, "error": "busy", "message": str(exc)}
    except (kit_hub.HubError, pi_dispatch.DispatchError):
        return {"ok": False, "error": "busy"}
    acquired = time.time() * 1000
    owner = (lock.path / "owner.json").read_bytes()
    time.sleep(request.get("hold_ms", 0) / 1000)
    if request.get("tamper"):
        (lock.path / "owner.json").write_bytes(b'{"pid": 1, "token": "someone-else"}\n')
    lock.__exit__(None, None, None)
    return {"ok": True, "owner_b64": base64.b64encode(owner).decode("ascii"), "acquired_ms": acquired,
            "released_ms": time.time() * 1000, "left": lock.path.exists()}


def allow_check(spec):
    if spec["kind"] == "env_name":
        return pi_dispatch.allow_env_name
    if spec["kind"] == "id":
        return pi_dispatch.allow_id
    return pi_dispatch.allow_enum(*[from_tagged(choice) for choice in spec["choices"]])


def op_secrets_call(request):
    """疑似凭据的检测与脱敏：fn 选函数，text 或 value（带标签编码）作参数。"""
    fn, text = request["fn"], request.get("text")
    value = from_tagged(request["value"]) if "value" in request else None
    if fn == "redact_secrets":
        return {"ok": True, "text": pi_dispatch.redact_secrets(text)}
    if fn == "redact_tokens":
        return {"ok": True, "text": pi_dispatch.redact_tokens(text)}
    if fn == "redact_obj":
        return {"ok": True, "value": to_tagged(pi_dispatch.redact_obj(value))}
    if fn == "redact_json":
        allow = {tuple(item["path"]): allow_check(item["check"]) for item in request.get("allow") or []}
        return {"ok": True, "value": to_tagged(pi_dispatch.redact_json(value, allow or None))}
    if fn == "secret_like_paths":
        return {"ok": True, "paths": pi_dispatch.secret_like_paths(value)}
    if fn == "token_shaped":
        return {"ok": True, "result": pi_dispatch._token_shaped(text)}
    if fn == "looks_like_secret":
        return {"ok": True, "result": codekit_secrets.looks_like_secret(value)}
    if fn == "normalize":
        return {"ok": True, "text": codekit_decisions.normalize(text)}
    if fn == "is_sensitive":
        return {"ok": True, "result": codekit_decisions.is_sensitive(text)}
    if fn == "decisions_redact":
        return {"ok": True, "text": codekit_decisions.redact(text, request.get("limit", 4000))}
    if fn == "redact_state":
        result, changed = codekit_decisions.redact_state(value, request.get("limit", 6000))
        return {"ok": True, "value": to_tagged(result), "changed": changed}
    return {"ok": False, "error": "UNKNOWN_FN"}


def op_jsonl_append(request):
    """kit_hub.Hub.append_event：账本在 <repo>/.agent/mailbox/ledger/events.jsonl。count 次，每次 data 里加 seq。"""
    hub = kit_hub.Hub(Path(request["repo"]))
    data = from_tagged(request["data"]) if "data" in request else {}
    for seq in range(request.get("count", 1)):
        extra = dict(data)
        if request.get("count", 1) > 1:
            extra["seq"] = seq
        hub.append_event(request["event"], **extra)
    return {"ok": True, "done_ms": time.time() * 1000}


def op_jsonl_read(request):
    """kit_hub 读账本的写法（exec_metrics 等处内联）：read_text、jsonl_lines（第 56 轮起只按换行切）、
    逐行 json.loads，ValueError 跳过。"""
    ledger = Path(request["path"])
    out = []
    for line in kit_hub.jsonl_lines(kit_hub.read_text(ledger)) if ledger.exists() else []:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return {"ok": True, "value": to_tagged(out)}


def op_pyfmt_call(request):
    """Python 内置函数在 JSON 值上的语义（第 ② 步的 pyfmt、pyre.pyIntParse）。"""
    fn = request["fn"]
    if fn == "repr":
        return {"ok": True, "text": repr(request["text"])}
    if fn == "str":
        return {"ok": True, "text": str(from_tagged(request["value"]))}
    if fn == "sum":  # ④b4a 补：builtin_sum 的 float 补偿求和与 int 快速路径
        try:
            return {"ok": True, "value": to_tagged(sum(from_tagged(request["value"])))}
        except (TypeError, OverflowError) as exc:
            return {"ok": False, "error": type(exc).__name__}
    if fn == "int":
        try:
            return {"ok": True, "text": str(int(request["text"]))}
        except ValueError:
            return {"ok": False, "error": "ValueError"}
    return {"ok": False, "error": "UNKNOWN_FN"}


def op_pyregex_search(request):
    """kit_logs._compile_search 加逐段 search（第 ②b2 步）：编译的结果，与每段文本有没有匹配。"""
    try:
        pattern = kit_logs._compile_search(request["pattern"])
    except kit_logs.LogsError as exc:
        return {"ok": True, "outcome": "error", "message": str(exc)}
    except ValueError as exc:  # (?a)(?u) 之类：kit_logs 不接，命令行打堆栈
        return {"ok": True, "outcome": "crash", "error": type(exc).__name__}
    return {"ok": True, "outcome": "match", "hits": [pattern.search(text) is not None for text in request["texts"]]}


def op_pyregex_search_flags(request):
    """re.compile(pattern, flags) 加逐段 search（第 ④b3 片：检查的输出模式带 re.M，baseline 的找不到目标带 re.I）：
    编译的结果与每段的匹配起止（码点下标）。"""
    try:
        pattern = re.compile(request["pattern"], request["flags"])
    except re.error as exc:
        return {"ok": True, "outcome": "error", "message": str(exc)}
    except (ValueError, OverflowError) as exc:
        return {"ok": True, "outcome": "crash", "error": type(exc).__name__}
    spans = [pattern.search(text) for text in request["texts"]]
    return {"ok": True, "outcome": "match", "spans": [None if m is None else [m.start(), m.end()] for m in spans]}


def op_pydatetime_parse_iso(request):
    """kit_logs._parse_iso（第 ②c 步）：每段文本换成 UTC 之后距 0001-01-01 的微秒数，不可用为 None。"""
    epoch = datetime.datetime(1, 1, 1, tzinfo=datetime.timezone.utc)
    out = []
    for text in request["texts"]:
        moment = kit_logs._parse_iso(text)
        out.append(None if moment is None else str((moment - epoch) // datetime.timedelta(microseconds=1)))
    return {"ok": True, "values": out}


def op_jsonl_records(request):
    """kit_logs._jsonl_records；limit 给了就临时换掉 SAFE_MAX_LINE_BYTES（函数每次调用时才读这个全局量）。"""
    saved = kit_logs.SAFE_MAX_LINE_BYTES
    kit_logs.SAFE_MAX_LINE_BYTES = request.get("limit", saved)
    try:
        records = [[start, end, None if raw is None else base64.b64encode(raw).decode("ascii")]
                   for start, end, raw in kit_logs._jsonl_records(Path(request["path"]), request["start"], request["final"])]
    finally:
        kit_logs.SAFE_MAX_LINE_BYTES = saved
    return {"ok": True, "records": records}


def op_jsonl_iter_lines(request):
    return {"ok": True, "lines": list(kit_logs._iter_lines(Path(request["path"])))}


def op_jsonl_lines_before(request):
    return {"ok": True, "count": kit_logs._lines_before(Path(request["path"]), request["position"])}


def op_filelock_run(request):
    """kit_hub.file_lock：拿锁后（signal 时）往 stderr 报 ready，持有 hold_ms 毫秒再放。"""
    try:
        with kit_hub.file_lock(Path(request["path"]), wait_seconds=request.get("wait", 60)):
            acquired = time.time() * 1000
            if request.get("signal"):
                sys.stderr.write("ready\n")
                sys.stderr.flush()
            time.sleep(request.get("hold_ms", 0) / 1000)
            released = time.time() * 1000
    except kit_hub.HubError as exc:
        return {"ok": False, "error": "timeout", "message": str(exc)}
    return {"ok": True, "acquired_ms": acquired, "released_ms": released}


OPEN_MODES = {"create-new": "xb", "truncate": "wb", "append": "ab"}


def op_supervise_run(request):
    """pi_dispatch.run_supervised（迁移计划第 8.2 节 ④a）：env 是 [键, 值] 的列表，按次序还原成 dict；标准流写进
    request 给的两个文件（how 同 TS 的 OpenHow）。起子进程之后往 stderr 报 "spawned <pid>"（杀掉调用方的用例用）。
    参数错误（Popen 抛的 ValueError）照原文交回。"""
    env = {}
    for key, value in request["env"]:
        env[key] = value

    def on_spawn(pid):
        sys.stderr.write("spawned %d\n" % pid)
        sys.stderr.flush()

    out_spec, err_spec = request["stdout"], request["stderr"]
    with open(out_spec["path"], OPEN_MODES[out_spec["how"]]) as out, open(err_spec["path"], OPEN_MODES[err_spec["how"]]) as err:
        try:
            result = pi_dispatch.run_supervised(request["cmd"], Path(request["cwd"]), env, out, err, request.get("timeout"),
                                                request.get("grace", 15.0), on_spawn=on_spawn)
        except ValueError as exc:
            return {"ok": False, "error": "ValueError", "message": str(exc)}
    return {"ok": True, "result": result}


def _effective_env(env):
    """子进程实际看到的环境：大小写不同的同名变量留最后插入的那一个（CPython 的 getenvironment），按码点排序。"""
    last = {}
    for key, value in env.items():
        last.pop(key.upper(), None)
        last[key.upper()] = [key, value]
    return sorted(last.values())


def op_dispatch_child_env(request):
    """pi_dispatch.child_env（迁移第 ③d 片）：config 是 JSON 文本，extra 是 [键, 值] 的列表或 null。环境的键序只通过
    大小写相同的变量留哪个体现出来，所以交回排好序的键值、实际生效的环境与被移除的变量名。"""
    extra = None if request.get("extra") is None else {key: value for key, value in request["extra"]}
    env, removed = pi_dispatch.child_env(json.loads(request["config_json"]), extra)
    return {"ok": True, "items": sorted([key, value] for key, value in env.items()), "effective": _effective_env(env),
            "removed": removed}


def op_dispatch_run_capture(request):
    """pi_dispatch.run_capture：env 是 [键, 值] 的列表（按次序还原成 dict）或 null（继承）。"""
    env = None if request.get("env") is None else {key: value for key, value in request["env"]}
    cwd = Path(request["cwd"]) if request.get("cwd") else None
    code, out, err = pi_dispatch.run_capture(request["cmd"], cwd=cwd, env=env, timeout=request["timeout"])
    return {"ok": True, "code": code, "stdout": out, "stderr": err}


def op_dispatch_parse_cli(request):
    """pi_dispatch.parse_help 与 --list-models 的三个解析函数，同一段文字一起交回。"""
    text = request["text"]
    help_info = pi_dispatch.parse_help(text)
    return {"ok": True, "help": help_info, "lines": [list(row) for row in pi_dispatch.list_models_lines(text)],
            "rows": [list(row) for row in pi_dispatch.list_models_rows(text)],
            "empty_reason": pi_dispatch.list_models_empty_reason(text)}


def op_run_call(request):
    """run 之前的几步（迁移第 ④b7c1 片）：执行说明（render_instruction 与它的几个部件）、measured_check_seconds、
    shlex.quote、context_evidence、pi_preflight。值带标签；异常交回类名与 str(exc)。"""
    fn = request["fn"]

    def tagged(key):
        return from_tagged(request[key]) if request.get(key) is not None else None

    try:
        if fn == "shlex_quote":
            return {"ok": True, "value": shlex.quote(request["text"])}
        if fn == "render":
            return {"ok": True, "value": pi_dispatch.render_instruction(
                tagged("meta"), tagged("contract"), tagged("executor"), tagged("timeout"), request.get("extra", []),
                tagged("setup") or [], tagged("measured"))}
        if fn == "setup_facts":
            return {"ok": True, "value": pi_dispatch.setup_facts_text(tagged("setup"))}
        if fn == "self_check":
            return {"ok": True, "value": pi_dispatch.self_check_command(tagged("check"), request["tools"])}
        if fn == "machine_summary":
            return {"ok": True, "value": pi_dispatch.machine_summary(tagged("contract"), request.get("extra", []),
                                                                     request.get("tools", []), tagged("measured"))}
        if fn == "measured":
            return {"ok": True, "value": to_tagged(pi_dispatch.measured_check_seconds(Path(request["runs"]),
                                                                                       tagged("checks")))}
        if fn == "context_evidence":
            if request.get("agent_dir") is None:
                os.environ.pop("PI_CODING_AGENT_DIR", None)
            else:
                os.environ["PI_CODING_AGENT_DIR"] = request["agent_dir"]
            return {"ok": True, "value": to_tagged(pi_dispatch.context_evidence(Path(request["work_dir"]),
                                                                                 request["mode"]))}
        if fn == "preflight":
            env = {key: value for key, value in request["env"]}
            result = pi_dispatch.pi_preflight(list(request["pi_cmd"]), Path(request["cwd"]), tagged("executor"),
                                              Path(request["out_dir"]), env)
            return {"ok": True, "value": to_tagged(result)}
    except Exception as exc:  # noqa: BLE001 —— 崩溃的类名与文字也要两边一致
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    return {"ok": False, "error": "UNKNOWN_FN"}


def op_roles_cwd_relative(request):
    """kit_roles.cwd_relative_parts：先切到 request 给的目录（相对路径按它判断是否存在）。"""
    os.chdir(request["cwd"])
    return {"ok": True, "parts": kit_roles.cwd_relative_parts(request["command"])}


def op_pyshlex_split(request):
    """shlex.split(text)（posix，不认注释）：合同检查行的命令照它拆（迁移第 ④b1 片）。"""
    try:
        return {"ok": True, "argv": shlex.split(request["text"])}
    except ValueError as exc:
        return {"ok": False, "error": "ValueError", "message": str(exc)}


def op_patterns_call(request):
    """pi_dispatch 的路径模式（迁移第 ④b1 片）：re.escape、glob_regex 的正则文字、matches、pattern_error。"""
    fn = request["fn"]
    if fn == "re_escape":
        return {"ok": True, "value": re.escape(request["text"])}
    if fn == "glob_text":
        return {"ok": True, "value": pi_dispatch.glob_regex(request["pattern"]).pattern}
    if fn == "matches":
        compiled = pi_dispatch.compile_patterns(request["patterns"], request["ignore_case"])
        return {"ok": True, "value": [pi_dispatch.matches(compiled, path) for path in request["paths"]]}
    if fn == "pattern_error":
        return {"ok": True, "value": pi_dispatch.pattern_error(json.loads(request["value_json"]))}
    return {"ok": False, "error": "UNKNOWN_FN"}


def op_pypath_call(request):
    """路径的几个 Python 语义（④b6 复核补）：os.path.abspath、normpath、Path(p).resolve()、pi_dispatch.is_within。"""
    fn, value = request["fn"], request["path"]
    try:
        if fn == "abspath":
            return {"ok": True, "value": os.path.abspath(value)}
        if fn == "normcase":
            return {"ok": True, "value": os.path.normcase(value)}
        if fn == "normpath":
            return {"ok": True, "value": os.path.normpath(value)}
        if fn == "resolve":
            return {"ok": True, "value": str(Path(value).resolve())}
        if fn == "exists":
            return {"ok": True, "value": Path(value).exists()}
        if fn == "is_within":
            return {"ok": True, "value": pi_dispatch.is_within(Path(value), Path(request["root"]))}
    except Exception as exc:  # noqa: BLE001 —— 崩溃的类名与文字也要两边一致
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    return {"ok": False, "error": "UNKNOWN_FN"}


def op_events_call(request):
    """pi_dispatch 的事件流摘要与 summary.md（迁移第 ④b6 片）。写出的文件由测试自己读字节比较；异常交回类名与 str(exc)。"""
    fn = request["fn"]

    def path(key):
        return Path(request[key])

    try:
        if fn == "summarize":
            summary, final_text = pi_dispatch.summarize_events(
                path("events"), path("work_dir"), from_tagged(request["executor"]),
                stderr_path=path("stderr") if request.get("stderr") else None,
                expects_settled=request.get("expects_settled"),
                allowed_outside=[Path(item) for item in request.get("allowed_outside", [])],
                plan_text=request.get("plan_text", ""),
                protected_roots=[Path(item) for item in request.get("protected_roots", [])])
            return {"ok": True, "summary": to_tagged(summary), "final_text": final_text}
        if fn == "extract_report":
            return {"ok": True, "value": to_tagged(pi_dispatch.extract_report(request["text"], path("run_dir")))}
        if fn == "review_hints":
            return {"ok": True, "value": to_tagged(pi_dispatch.review_hints(path("patch")))}
        if fn == "write_summary":
            # kit 根（问题清单的位置）就是本仓库：KIT_ROOT 按 pi_dispatch 自己的位置算，请求里的 kit_root 只给 TS 用
            pi_dispatch.write_summary(path("run_dir"), pi_dispatch.Repo(path("root")))
            return {"ok": True}
        if fn == "message_text":
            return {"ok": True, "value": pi_dispatch._message_text(from_tagged(request["message"]))}
        if fn == "mentions":
            message = from_tagged(request["message"])
            return {"ok": True,
                    "ambiguity": to_tagged(pi_dispatch.ambiguity_mentions(message, request["line"], request.get("skip", []))),
                    "interpretation": to_tagged(pi_dispatch.interpretation_mentions(message, request["line"]))}
        if fn == "domain_words":
            return {"ok": True, "value": pi_dispatch.ambiguity_domain_words(request["text"])}
        if fn == "scan":
            command = request["command"]
            scan = pi_dispatch._mask_paths(command, request["own"])
            return {"ok": True, "masked": scan, "protected": pi_dispatch._protected_mentions(scan, request["protected"]),
                    "outside": pi_dispatch._outside_mentions(scan, request["protected"]),
                    "cache": pi_dispatch._cache_dir_cleanup(command), "exit": pi_dispatch._masked_exit_mention(command),
                    "leak": pi_dispatch._temp_dir_without_cleanup(command)}
        if fn == "path_forms":
            return {"ok": True, "value": pi_dispatch._path_forms([Path(item) for item in request["paths"]])}
        if fn == "excerpt":
            return {"ok": True, "value": pi_dispatch._match_excerpt(request["text"], request["start"], request["end"])}
    except Exception as exc:  # noqa: BLE001 —— 崩溃的类名与文字也要两边一致
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    return {"ok": False, "error": "UNKNOWN_FN"}

def op_contract_call(request):
    """pi_dispatch 的合同解析与校验（迁移第 ④b1 片）：derive_contract_json、validate_contract、invisible_char_warnings。
    异常交回类名与 str(exc)（命令行上它们是未捕获的崩溃，契约只比到这一层）。"""
    fn = request["fn"]
    try:
        if fn == "derive":
            contract, problems = pi_dispatch.derive_contract_json(request["md"], request.get("title"))
            return {"ok": True, "contract": to_tagged(contract), "problems": problems}
        if fn == "validate":
            raw = json.loads(request["json_text"])
            contract, errors, warnings = pi_dispatch.validate_contract(request["md"], raw, request["plan_key"],
                                                                       request.get("extra_protected", []))
            return {"ok": True, "contract": None if contract is None else to_tagged(contract), "errors": errors,
                    "warnings": warnings}
        if fn == "kernel_protected":
            saved = pi_dispatch.KERNEL_TS_ROOT
            pi_dispatch.KERNEL_TS_ROOT = Path(request["kit_root"]) / "ts"
            try:
                value = pi_dispatch.kernel_protected_paths(Path(request["root"]), dict(request["kernel_impl"]))
            finally:
                pi_dispatch.KERNEL_TS_ROOT = saved
            return {"ok": True, "value": value}
        if fn == "validate_plan":
            # 选择文件与 kit 根由请求给出（TS 一侧经 context 拿到同样的两样）
            impl = dict(request["kernel_impl"])
            saved = pi_dispatch.read_kernel_impl, pi_dispatch.KERNEL_TS_ROOT
            pi_dispatch.read_kernel_impl = lambda path=None: dict(impl)
            pi_dispatch.KERNEL_TS_ROOT = Path(request["kit_root"]) / "ts"
            try:
                contract, errors, warnings = pi_dispatch.validate_plan(pi_dispatch.Repo(Path(request["root"])),
                                                                     request["plan_key"])
            finally:
                pi_dispatch.read_kernel_impl, pi_dispatch.KERNEL_TS_ROOT = saved
            return {"ok": True, "contract": None if contract is None else to_tagged(contract), "errors": errors,
                    "warnings": warnings}
        if fn == "branch_subject":
            return {"ok": True, "value": pi_dispatch.branch_subject(request["task_id"], json.loads(request["title_json"]),
                                                                    json.loads(request["plan_version_json"]),
                                                                    request["attempt_no"])}
        if fn == "invisible":
            return {"ok": True, "value": pi_dispatch.invisible_char_warnings(request["text"], request["label"])}
    except Exception as exc:  # noqa: BLE001 —— 崩溃的类名与文字也要两边一致
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    return {"ok": False, "error": "UNKNOWN_FN"}


def op_pyfmt_number(request):
    """"%.Nf" % x 与 round(x, N)：x 是 float（位模式）或 int（十进制字符串）。round 的结果交回 repr。"""
    if "bits" in request:
        value = struct.unpack(">d", bytes.fromhex(request["bits"]))[0]
    else:
        value = int(request["int"])
    digits = request["digits"]
    return {"ok": True, "fixed": "%.*f" % (digits, value), "round": repr(round(value, digits))}


def op_argv_ensure_safe(request):
    """pi_dispatch.ensure_argv_safe：通过为 ok，拒绝时交回报错原文与退出码。"""
    try:
        pi_dispatch.ensure_argv_safe(request["cmd"])
    except pi_dispatch.DispatchError as exc:
        return {"ok": False, "error": "DispatchError", "message": str(exc), "code": exc.code}
    return {"ok": True}


# --- 第 ③ 步：配置中心 ----------------------------------------------------------
# 输入的 JSON 值以 JSON 文本传（两边各自 json.loads / pyjson.loads），结果用带标签编码；报错带 str(exc)。

def op_protocols_strict(request):
    """codekit.protocols.strict_json_loads：给定的字节，结果是值或 ProtocolError 的错误码（迁移第 ③e 片）。"""
    data = base64.b64decode(request["data_b64"])
    try:
        value = codekit_protocols.strict_json_loads(data)
    except codekit_protocols.ProtocolError as exc:
        return {"ok": False, "error": "ProtocolError", "code": exc.code}
    return {"ok": True, "value": to_tagged(value)}


def op_plugins_call(request):
    """codekit/plugins.py 的记录层：fn 选函数，json_args 是各个参数的 JSON 文本。"""
    fn = request["fn"]
    args = [json.loads(text) for text in request.get("json_args", [])]
    try:
        if fn == "validate_manifest":
            value = codekit_plugins.validate_manifest(args[0])
        elif fn == "validate_lock":
            value = codekit_plugins.validate_lock(*args)
        elif fn == "resolve_plugins":
            value = list(codekit_plugins.resolve_plugins(args[0], args[1]))
        elif fn == "check_permission_intersection":
            value = codekit_plugins.check_permission_intersection(
                args[0], allowed_permissions=args[1], platform_name=args[2] if len(args) > 2 else None)
        elif fn == "canonical_bytes":
            return {"ok": True, "b64": base64.b64encode(codekit_plugins.canonical_bytes(args[0])).decode("ascii")}
        elif fn == "digest":
            value = codekit_plugins.digest(args[0])
        else:
            return {"ok": False, "error": "UNKNOWN_FN"}
    except codekit_plugins.PluginError as exc:
        return {"ok": False, "error": "PluginError", "message": str(exc)}
    return {"ok": True, "value": to_tagged(value)}


def op_decisions_call(request):
    """codekit/decisions.py 里配置中心用到的部分，加上 pi_dispatch.battery_link_problem。"""
    fn = request["fn"]
    try:
        if fn == "check_question":
            value = codekit_decisions.check_question(request["name"], json.loads(request["question"]))
        elif fn == "check_questions":
            value = codekit_decisions.check_questions(json.loads(request["questions"]))
        elif fn == "load_battery":
            value = codekit_decisions.load_battery(Path(request["path"]))
        elif fn == "load_batteries":
            value = codekit_decisions.load_batteries(Path(request["root"]))
        elif fn == "verify_battery_lock":
            value = codekit_decisions.verify_battery_lock(Path(request["plugin_dir"]))
        elif fn == "settings_from_config":
            agent_dir, plugin_dir = request.get("agent_dir"), request.get("plugin_dir")
            value = codekit_decisions.settings_from_config(
                json.loads(request["config"]), Path(agent_dir) if agent_dir else None,
                Path(plugin_dir) if plugin_dir else None).as_dict()
        elif fn == "battery_link_problem":
            saved = pi_dispatch.KIT_ROOT, pi_dispatch.DECISIONS_PLUGIN_DIR
            pi_dispatch.KIT_ROOT, pi_dispatch.DECISIONS_PLUGIN_DIR = Path(request["kit_root"]), Path(request["plugin_dir"])
            try:
                value = pi_dispatch.battery_link_problem()
            finally:
                pi_dispatch.KIT_ROOT, pi_dispatch.DECISIONS_PLUGIN_DIR = saved
        else:
            return {"ok": False, "error": "UNKNOWN_FN"}
    except codekit_decisions.DecisionError as exc:
        return {"ok": False, "error": "DecisionError", "code": exc.code, "detail": exc.detail}
    except ValueError as exc:  # check_question 的报错；JSON 与 UTF-8 的错误在 load_battery 里已经包成 DecisionError
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    except (OverflowError, TypeError, RecursionError) as exc:  # Python 没接住、会打堆栈的：只比较类名
        return {"ok": False, "error": type(exc).__name__}
    return {"ok": True, "value": to_tagged(value)}


def op_decisions_client(request):
    """④b4a 的决策客户端：传输、回答校验、会话、用量合计、doctor 的事实与探测、decisions_session。

    值按 json.dumps 交回（int 与 float 照样分开）；决策调用的环境变量由测试经子进程的环境给。"""
    fn = request["fn"]

    def text(value):
        return json.dumps(value, ensure_ascii=False)

    def settings(plugin_dir=None):
        return codekit_decisions.settings_from_config(json.loads(request["config"]), None, plugin_dir)

    try:
        if fn == "transport":
            raw = codekit_decisions.http_transport(base64.b64decode(request["body"]), dict(request["headers"]),
                                                   request["timeout"], request["url"])
            return {"ok": True, "raw": base64.b64encode(raw).decode("ascii")}
        if fn == "check_answer":
            return {"ok": True, "value": text(codekit_decisions.check_answer(
                request["name"], json.loads(request["question"]), json.loads(request["answer"])))}
        if fn == "ask":
            battery = json.loads(request["battery"])
            battery["questions"] = codekit_decisions.check_questions(battery["questions"])
            record = Path(request["record"]) if request.get("record") else None
            session = codekit_decisions.Session(settings(), record)
            context = json.loads(request["context"]) if request.get("context") else None
            results = [session.ask(battery, json.loads(state), context) for state in request["states"]]
            return {"ok": True, "value": text({"results": results, "calls": session.calls, "answered": session.answered,
                                              "input_tokens": session.input_tokens})}
        if fn == "usage_totals":
            return {"ok": True, "value": text(codekit_decisions.usage_totals(json.loads(request["records"])))}
        if fn == "describe":
            plugin_dir = Path(request["plugin_dir"]) if request.get("plugin_dir") else None
            return {"ok": True, "value": text(codekit_decisions.describe(settings(plugin_dir), plugin_dir))}
        if fn == "probe":
            return {"ok": True, "value": text(codekit_decisions.probe(settings()))}
        if fn == "session":
            saved = pi_dispatch.KIT_ROOT, pi_dispatch.DECISIONS_PLUGIN_DIR
            pi_dispatch.KIT_ROOT = Path(request["kit_root"])
            pi_dispatch.DECISIONS_PLUGIN_DIR = pi_dispatch.KIT_ROOT / "plugins" / "decisions"
            out = io.StringIO()
            try:
                with contextlib.redirect_stdout(out):
                    session = pi_dispatch.decisions_session(
                        json.loads(request["config"]), Path(request["agent_dir"]) if request.get("agent_dir") else None,
                        Path(request["record"]) if request.get("record") else None, request.get("point"),
                        strict=bool(request.get("strict")))
            except pi_dispatch.DispatchError as exc:
                return {"ok": False, "error": "DispatchError", "message": str(exc), "code": exc.code, "stdout": out.getvalue()}
            finally:
                pi_dispatch.KIT_ROOT, pi_dispatch.DECISIONS_PLUGIN_DIR = saved
            value = None if session is None else {"mode": session.mode, "batteries": sorted(session.batteries)}
            return {"ok": True, "value": text(value), "stdout": out.getvalue()}
        if fn == "assess":  # ④b4b：同一个 tracker 连问几次 assess_run
            saved = pi_dispatch.KIT_ROOT, pi_dispatch.DECISIONS_PLUGIN_DIR
            pi_dispatch.KIT_ROOT = Path(request["kit_root"])
            pi_dispatch.DECISIONS_PLUGIN_DIR = pi_dispatch.KIT_ROOT / "plugins" / "decisions"
            try:
                session = pi_dispatch.decisions_session(json.loads(request["config"]), None, Path(request["record"]), "run-health")
                tracker = {}
                lines = [pi_dispatch.assess_run(Path(request["run_dir"]), session, tracker) for _ in range(request["ticks"])]
            finally:
                pi_dispatch.KIT_ROOT, pi_dispatch.DECISIONS_PLUGIN_DIR = saved
            return {"ok": True, "value": text({"lines": lines, "ticks": tracker.get("ticks"), "streak": tracker.get("streak")})}
    except codekit_decisions.DecisionError as exc:
        return {"ok": False, "error": "DecisionError", "code": exc.code, "detail": exc.detail}
    except (ValueError, OverflowError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        return {"ok": False, "error": type(exc).__name__}
    return {"ok": False, "error": "UNKNOWN_FN"}


def op_config_call(request):
    """kit_config 的整份校验与读配置、kit_roles.config_errors、pi_dispatch 的几个校验函数。

    kit_root 换成请求给的目录（第 ③ 步启动器经 pyargs 的 context 传 kit_root，决策插件在它之下）；env 里的变量在这次调用
    期间设上（值为 null 表示删掉），tempfile 的缓存清掉，worktree_root 按这一次的环境现算。
    """
    fn = request["fn"]
    saved_root = pi_dispatch.KIT_ROOT, pi_dispatch.DECISIONS_PLUGIN_DIR
    saved_env = {name: os.environ.get(name) for name in request.get("env", {})}
    pi_dispatch.KIT_ROOT = Path(request["kit_root"])
    pi_dispatch.DECISIONS_PLUGIN_DIR = pi_dispatch.KIT_ROOT / "plugins" / "decisions"
    for name, setting in request.get("env", {}).items():
        if setting is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = setting
    tempfile.tempdir = None
    try:
        repo = pi_dispatch.Repo(Path(request["repo"])) if request.get("repo") else None
        config = json.loads(request["config"]) if "config" in request else None
        if fn == "validate_config":
            value = kit_config.validate_config(config, repo, hints=request.get("hints", True))
        elif fn == "plugins_fix_hint":
            value = kit_config.plugins_fix_hint(config, repo)
        elif fn == "plugins_section_error":
            value = kit_config.plugins_section_error(config)
        elif fn == "load_config":
            value = kit_config.load_config(repo)
        elif fn == "config_errors":
            value = kit_roles.config_errors(config)
        elif fn == "pricing_table":
            value = pi_dispatch.pricing_table(config)
        elif fn == "worktree_root":
            value = str(repo.worktree_root(config))
        else:
            return {"ok": False, "error": "UNKNOWN_FN"}
    except kit_config.ConfigError as exc:
        return {"ok": False, "error": "ConfigError", "message": str(exc), "code": exc.code}
    except pi_dispatch.DispatchError as exc:
        return {"ok": False, "error": "DispatchError", "message": str(exc), "code": exc.code}
    except (OverflowError, TypeError, RecursionError) as exc:
        return {"ok": False, "error": type(exc).__name__}
    finally:
        pi_dispatch.KIT_ROOT, pi_dispatch.DECISIONS_PLUGIN_DIR = saved_root
        for name, setting in saved_env.items():
            if setting is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = setting
        tempfile.tempdir = None
    return {"ok": True, "value": to_tagged(value)}


def op_roles_call(request):
    """kit_roles 不起 CLI 的部分与它用到的 pi_dispatch 函数（迁移第 ③c 片）：shutil.which、resolve_pi_command、本机文件、
    runtime_command、resolve_role_executor、allowed_executor_check、load_binding_record。

    env 照 op_config_call 在这次调用期间设上；cwd 给出时在那里调用（shutil.which 先查当前目录）。
    """
    fn = request["fn"]
    saved_env = {name: os.environ.get(name) for name in request.get("env", {})}
    saved_cwd = os.getcwd()
    for name, setting in request.get("env", {}).items():
        if setting is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = setting
    if request.get("cwd"):
        os.chdir(request["cwd"])
    try:
        repo = pi_dispatch.Repo(Path(request["repo"])) if request.get("repo") else None
        config = json.loads(request["config"]) if "config" in request else {}
        if fn == "which":
            value = shutil.which(request["name"])
        elif fn == "resolve_pi_command":
            value = pi_dispatch.resolve_pi_command()
        elif fn == "read_local":
            commands, errors, warnings = kit_roles.read_local(repo, config)
            value = {"commands": commands, "errors": errors, "warnings": warnings}
        elif fn == "runtime_command":
            command, source, lines = kit_roles.runtime_command(repo, config, request["runtime"], request.get("adapter"))
            value = {"command": command, "source": source, "lines": lines}
        elif fn == "resolve_role_executor":
            resolved, error = kit_roles.resolve_role_executor(config, request["role"])
            value = {"value": resolved, "error": error}
        elif fn == "allowed_executor_check":
            problem = pi_dispatch.allowed_executor_check(config, *json.loads(request["args"]))
            value = list(problem) if problem is not None else None
        elif fn == "load_binding_record":
            value = pi_dispatch.load_binding_record(repo, request["task"], request["version"])
        else:
            return {"ok": False, "error": "UNKNOWN_FN"}
    except pi_dispatch.DispatchError as exc:
        return {"ok": False, "error": "DispatchError", "message": str(exc), "code": exc.code}
    finally:
        os.chdir(saved_cwd)
        for name, setting in saved_env.items():
            if setting is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = setting
    return {"ok": True, "value": to_tagged(value)}


def op_secret_store_call(request):
    """codekit/secrets.py：source、describe、remove、_check_name。env 照 op_config_call 在这次调用期间设上。

    契约只用测试专用的名字（THEMIS_CONTRACT_ 开头）与合成的假值；system 模式下只读不存在的测试目标（迁移计划第 ③ 步）。
    """
    fn, name = request["fn"], request["name"]
    saved_env = {key: os.environ.get(key) for key in request.get("env", {})}
    for key, setting in request.get("env", {}).items():
        if setting is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = setting
    try:
        if fn == "source":
            value = codekit_secrets.source(name)
        elif fn == "describe":
            value = codekit_secrets.describe(name)
        elif fn == "remove":
            value = codekit_secrets.remove(name)
        elif fn == "check_name":
            value = codekit_secrets._check_name(name)
        else:
            return {"ok": False, "error": "UNKNOWN_FN"}
    except codekit_secrets.SecretError as exc:
        return {"ok": False, "error": "SecretError", "code": exc.code, "detail": exc.detail}
    except UnicodeDecodeError:
        return {"ok": False, "error": "UnicodeDecodeError"}
    finally:
        for key, setting in saved_env.items():
            if setting is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = setting
    return {"ok": True, "value": to_tagged(value)}


def op_unicode_call(request):
    """str.lower、str.casefold、unicodedata.normalize("NFC")；fn 为 lower_table 时交回全部会被 lower 改变的码点。"""
    fn = request["fn"]
    if fn == "lower_table":
        table = []
        for cp in range(0x110000):
            if 0xD800 <= cp <= 0xDFFF:
                continue
            lowered = chr(cp).lower()
            if lowered != chr(cp):
                table.append([cp, lowered])
        return {"ok": True, "table": table}
    text = request["text"]
    if fn == "lower":
        return {"ok": True, "text": text.lower()}
    if fn == "casefold":
        return {"ok": True, "text": text.casefold()}
    if fn == "nfc":
        return {"ok": True, "text": unicodedata.normalize("NFC", text)}
    return {"ok": False, "error": "UNKNOWN_FN"}


def op_pyio_call(request):
    """Path.read_text / read_bytes 与 bytes.decode("utf-8") 的结果或报错原文。"""
    fn = request["fn"]
    try:
        if fn == "read_text":
            return {"ok": True, "text": Path(request["path"]).read_text(encoding="utf-8")}
        if fn == "read_bytes":
            return {"ok": True, "b64": base64.b64encode(Path(request["path"]).read_bytes()).decode("ascii")}
        if fn == "decode":
            return {"ok": True, "text": base64.b64decode(request["b64"]).decode("utf-8")}
    except (OSError, UnicodeDecodeError) as exc:
        return {"ok": False, "error": "OSError" if isinstance(exc, OSError) else "UnicodeDecodeError", "message": str(exc)}
    return {"ok": False, "error": "UNKNOWN_FN"}


def op_pyurl_call(request):
    """urlsplit 加 port、hostname、username、password；ip_address 认出的类型。抛 ValueError 时只交回类名。"""
    if request["fn"] == "ip_kind":
        try:
            address = ipaddress.ip_address(request["text"])
        except ValueError:
            return {"ok": True, "kind": None}
        return {"ok": True, "kind": "v4" if isinstance(address, ipaddress.IPv4Address) else "v6"}
    try:
        parts = urllib.parse.urlsplit(request["text"])
        port = parts.port
    except ValueError:
        return {"ok": False, "error": "ValueError"}
    return {"ok": True, "scheme": parts.scheme, "netloc": parts.netloc, "path": parts.path, "query": parts.query,
            "fragment": parts.fragment, "port": port, "hostname": parts.hostname, "username": parts.username,
            "password": parts.password}


def op_pypath_pure(request):
    """str(PurePath(text, *parts))：pathlib 的规整写法（按本机平台）。"""
    return {"ok": True, "text": str(Path(request["text"], *request.get("parts", [])))}


def op_pyvalue_eq(request):
    """json.loads 读出的两个值用 == 比：nested 时各包进一个 list 再比（容器里先比身份）。"""
    left, right = json.loads(request["a"]), json.loads(request["b"])
    return {"ok": True, "result": [left] == [right] if request.get("nested") else left == right}


def op_pyset_sorted(request):
    """sorted(json.loads(values))：交回 json.dumps 的结果，或 TypeError 与文字（混了类型时报的是哪一对，看 list.sort 比较的先后）。"""
    values = json.loads(request["values"])
    try:
        return {"ok": True, "result": json.dumps(sorted(values))}
    except TypeError as exc:
        return {"ok": False, "error": "TypeError", "message": str(exc)}


def op_replace_real(request):
    """os.replace(src, dst) 真失败一次，交回类型、winerror 与 str(exc)：kind 是 busy（源文件被不共享地打开，WinError 32）或 denied
    （目标是目录，WinError 5）。"""
    import _winapi
    src, dst = request["src"], request["dst"]
    handle = _winapi.CreateFile(src, _winapi.GENERIC_READ, 0, 0, _winapi.OPEN_EXISTING, 0, 0) if request["kind"] == "busy" else None
    try:
        os.replace(src, dst)
    except OSError as exc:
        return {"ok": True, "error": type(exc).__name__, "winerror": exc.winerror, "text": str(exc)}
    finally:
        if handle is not None:
            _winapi.CloseHandle(handle)
    return {"ok": False, "error": "NO_ERROR"}


def op_mtime_real(request):
    """第 ⑤g 片：把每个文件的修改时刻设成给定的纳秒数（os.utime(ns=...)），交回 kit_hub 3233、4271 两处的写法换成的秒
    （fromtimestamp(st_mtime, utc).strftime），以及设好之后 stat 读到的 st_mtime_ns（文件系统的精度会截掉一些）。纳秒数用字符串传。"""
    import datetime as _dt
    texts, stored = [], []
    for path, ns in request["files"]:
        os.utime(path, ns=(int(ns), int(ns)))
        texts.append(_dt.datetime.fromtimestamp(Path(path).stat().st_mtime, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        stored.append(str(Path(path).stat().st_mtime_ns))
    return {"ok": True, "texts": texts, "stored": stored}


def op_pyexc_real(request):
    """第 ⑤g1 片（base 的 pyexc 的对照）：names 里每个类名取 __mro__，截到 Exception；specs 里每一项造一个对应的异常，交回 type(exc).__name__
    （OSError(errno, "x") 与 OSError(0, "x", None, winerror) 构造时自己落到子类）。"""
    import builtins
    import re as re_module
    import subprocess
    special = {"JSONDecodeError": json.JSONDecodeError, "TimeoutExpired": subprocess.TimeoutExpired, "SubprocessError": subprocess.SubprocessError,
               "error": re_module.error}

    def cls(name):
        return special.get(name) or getattr(builtins, name)

    mro = {}
    for name in request["names"]:
        chain = []
        for item in cls(name).__mro__:
            chain.append(item.__name__)
            if item is Exception:
                break
        mro[name] = chain
    made = []
    for kind, arg in request["specs"]:
        if kind == "oserror":
            made.append(type(OSError(arg, "x")).__name__)
        elif kind == "winerror":
            made.append(type(OSError(0, "x", None, arg)).__name__)
        elif kind == "decode":
            try:
                bytes([0xFF]).decode("utf-8")
            except UnicodeDecodeError as exc:
                made.append(type(exc).__name__)
        elif kind == "json":
            made.append(type(json.JSONDecodeError("x", "", 0)).__name__)
        elif kind == "re-error":
            made.append(type(re_module.error("x")).__name__)
        else:  # re-value、re-overflow、crash：给的就是类名
            made.append(cls({"re-value": "ValueError", "re-overflow": "OverflowError"}.get(kind, arg)).__name__)
    return {"ok": True, "mro": mro, "names": made}


def op_pyexc_fs_real(request):
    """第 ⑤g2 片（pyexc 认 Node 的文件错误的对照）：在 request["dir"] 下每种各建一个目录（file、other 两个文件与 dir 目录），真触发一次，
    交回 type(exc).__name__；没报错是 None。"""
    base = Path(request["dir"])
    names = []
    for kind in request["kinds"]:
        work = base / kind
        work.mkdir(parents=True)
        (work / "file").write_text("x", encoding="utf-8")
        (work / "other").write_text("y", encoding="utf-8")
        (work / "dir").mkdir()
        actions = {
            "unlink-missing": lambda: os.unlink(work / "missing"),
            "read-dir": lambda: (work / "dir").read_bytes(),
            "unlink-dir": lambda: os.unlink(work / "dir"),
            "rename-onto-dir": lambda: os.rename(work / "file", work / "dir"),
            "rename-onto-file": lambda: os.rename(work / "file", work / "other"),
            "listdir-file": lambda: os.listdir(work / "file"),
            "mkdir-existing": lambda: os.mkdir(work / "dir"),
        }
        try:
            actions[kind]()
            names.append(None)
        except Exception as exc:  # noqa: BLE001  交回类名
            names.append(type(exc).__name__)
    return {"ok": True, "names": names}


def op_winerror_real(request):
    """真触发一次 Windows 错误，交回 str(exc)：kind 是 exe（跑一个不存在的程序，CreateProcess 的 WinError 2）或 mkdir（os.mkdir 一个已在的目录，
    WinError 183，带路径）。"""
    import subprocess
    try:
        if request["kind"] == "exe":
            subprocess.run([request["name"]], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.mkdir(request["path"])
    except OSError as exc:
        return {"ok": True, "error": type(exc).__name__, "text": str(exc)}
    return {"ok": False, "error": "NO_ERROR"}


def op_hub_call(request):
    """第 ⑤a 片：kit_hub 的纯函数（信件、schema、主任务状态与守卫）。结果带标签；HubError 交回文字与退出码，别的异常交回
    类型与文字。改状态的函数（invalidate_after、move_base）连同改过的 ts 一起交回。new_task_state 的 created_at 换成请求给的值。
    """
    fn = request["fn"]
    args = [from_tagged(item) for item in request["args"]]
    hub = types.SimpleNamespace(repo=Path(request.get("repo") or "."))
    try:
        if fn == "parse_letter":
            value = list(kit_hub.parse_letter(*args))
        elif fn == "routine_moves":
            value = list(kit_hub.routine_moves(*args))
        elif fn == "stage_of":
            value = list(kit_hub.stage_of(*args))
        elif fn == "invalidate_after":
            kit_hub.invalidate_after(*args)
            value = args[0]
        elif fn == "move_base":
            value = [kit_hub.move_base(*args), args[0]]
        elif fn == "new_task_state":
            value = kit_hub.new_task_state(*args[:5])
            value["created_at"] = args[5]
        elif fn in ("render_routine_brief", "stage_status_table"):
            value = getattr(kit_hub, fn)(hub, *args)
        elif fn in ("guard", "allowed_moves", "render_letter", "letter_errors", "schema_problems", "schema_errors", "return_stages",
                    "hotfix_reason", "upstream_notes", "dependents", "stage_busy", "gate_pattern", "gate_file"):
            value = getattr(kit_hub, fn)(*args)
        else:
            return {"ok": False, "error": "UNKNOWN_FN"}
    except kit_hub.HubError as exc:
        return {"ok": False, "error": "HubError", "message": str(exc), "code": exc.code}
    except Exception as exc:  # noqa: BLE001  类型与文字（⑤f 起文字也比）
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    return {"ok": True, "value": to_tagged(value)}

def op_hub_samples(request):
    """第 ⑤a 片：tests/test_kit_hub.py 里参数化的样例（只读），对照测试拿去交给三边，样例只有 pytest 这一个来源。
    test_letter_shape_errors 的 lambda 在这里照用例的写法先执行，交回具体的信头与正文。"""
    sys.path.insert(0, str(ROOT / "tests"))
    import test_kit_hub as cases  # noqa: E402

    def params(fn):
        return [mark.args[1] for mark in fn.pytestmark if mark.name == "parametrize"][0]

    shape = []
    for change, _expected in params(cases.test_letter_shape_errors):
        head = {"from": "planner-opus", "to": kit_hub.COORDINATOR, "task-id": "T001-1-plan", "in-reply-to": "none",
                "type": "交付"}
        body = cases.fields()
        change(head, body, 0)
        shape.append([head, body, 6])
    routine = [[cases.routine_letter(s, k, task, **extra) for s, k, task, extra in letters]
               for letters, _expected in params(cases.test_routine_letters_map_to_the_next_step)]
    exceptions = [[cases.routine_letter(s, k, task, **extra)]
                  for (s, k, task, extra), _reason in params(cases.test_exceptions_go_to_the_coordinator)]
    schema = [[schema, value] for schema, value, _ok in cases.SCHEMA_SAMPLES]
    value = {"shape": shape, "routine": routine, "exceptions": exceptions, "schema": schema,
             "fields": cases.fields(), "base": cases.BASE}
    return {"ok": True, "value": to_tagged(value)}

def op_hub_box(request):
    """第 ⑤b 片：在 repo 的信箱上按 steps 依次执行（Hub、HubState 三方合并、投递与收信、agent 记录、扣信与放回、目录锁……），
    交回每一步的结果（带标签）；HubError 记文字与退出码，别的异常记类型与文字，出错之后接着走下一步。
    signal 往 stderr 写 ready，wait 等起跑文件出现：混跑用例让一个进程停在两步之间。"""
    hub = kit_hub.Hub(Path(request["repo"]))
    states = {}
    results = []
    for step in request["steps"]:
        name, args = step[0], [from_tagged(item) for item in step[1:]]
        try:
            if name == "ensure":
                value = hub.ensure()
            elif name == "save_dict":
                value = hub.save_state(args[0])
            elif name == "load":
                states[args[0]] = hub.load_state()
                value = None
            elif name == "set":
                states[args[0]]["tasks"][args[1]][args[2]] = args[3]
                value = None
            elif name == "del":
                del states[args[0]]["tasks"][args[1]][args[2]]
                value = None
            elif name == "new_task":
                states[args[0]]["tasks"][args[1]] = args[2]
                value = None
            elif name == "save":
                value = hub.save_state(states[args[0]])
            elif name == "signal":
                sys.stderr.write("ready" + chr(10))
                sys.stderr.flush()
                value = None
            elif name == "wait":
                while not os.path.exists(args[0]):
                    time.sleep(0.005)
                value = None
            elif name == "read_state":
                value = hub._read_state()
            elif name == "deliver":
                value = hub.deliver(args[0], args[1])
            elif name == "unread":
                value = [path.name for path in hub.unread(args[0])]
            elif name == "take_first":
                value = hub.take(hub.unread(args[0])[0]).relative_to(hub.root).as_posix()
            elif name == "save_agent_record":
                value = hub.save_agent_record(args[0], args[1])
            elif name == "save_agent_session":
                value = hub.save_agent_session(args[0], args[1], args[2])
            elif name == "agent_record":
                value = hub.agent_record(args[0])
            elif name == "hold":
                state = hub.load_state()
                value = kit_hub.hold_letters(hub, state["tasks"][args[0]], *args[1:])
                hub.save_state(state)
            elif name == "hold_until_now":
                # 到点的边界：等到新的一秒开头再扣，until 就是这一秒；紧接着的 release 落在同一秒里
                time.sleep(1 - time.time() % 1)
                state = hub.load_state()
                value = kit_hub.hold_letters(hub, state["tasks"][args[0]], args[1], args[2], int(time.time()), *args[3:])
                hub.save_state(state)
            elif name == "hold_file_lock":
                with kit_hub.file_lock(hub.repo / args[0]):
                    sys.stderr.write("ready" + chr(10))
                    sys.stderr.flush()
                    time.sleep(args[1] / 1000)
                    (hub.repo / args[2]).write_text("", encoding="utf-8")
                value = None
            elif name == "exists":
                value = (hub.repo / args[0]).exists()
            elif name == "release":
                value = kit_hub.release_held(hub)
            elif name == "ledger_events":
                value = kit_hub.ledger_events(hub)
            elif name == "write_file":
                target = hub.repo / args[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(args[1], encoding="utf-8")
                value = None
            elif name == "keep_previous":
                value = kit_hub.keep_previous(hub.repo / args[0])
            elif name == "letter_main":
                value = kit_hub.letter_main(hub.repo / args[0])
            elif name == "dirlock":
                with kit_hub.DirLock(hub.repo / args[0], wait_seconds=args[1]):
                    time.sleep(args[2] / 1000)
                value = None
            else:
                value = {"unknown_step": name}
            results.append({"ok": True, "value": to_tagged(value)})
        except kit_hub.HubError as exc:
            results.append({"ok": False, "error": "HubError", "message": str(exc), "code": exc.code})
        except Exception as exc:  # noqa: BLE001  类型与文字（⑤f 起文字也比）
            results.append({"ok": False, "error": type(exc).__name__, "message": str(exc)})
    return {"ok": True, "results": results}

def op_fs_hold_exclusive(request):
    """第 ⑤b 片：用不许共享的方式打开一个文件、持有 hold_ms 毫秒（Windows 的共享冲突，别的进程读写都撞上 PermissionError）。"""
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = ctypes.c_void_p
    handle = kernel32.CreateFileW(request["path"], 0x80000000, 0, None, 3, 0, None)
    if handle in (None, ctypes.c_void_p(-1).value):
        return {"ok": False, "error": "OPEN_FAILED"}
    sys.stderr.write("ready" + chr(10))
    sys.stderr.flush()
    time.sleep(request["hold_ms"] / 1000)
    kernel32.CloseHandle(ctypes.c_void_p(handle))
    return {"ok": True}

def op_hub_constants(request):
    """第 132 轮：kit_hub 里与 @themis/hub/constants 同名的常量，转成 JSON 交回（元组成了列表，键的次序照原样）。"""
    return {"ok": True, "json": json.dumps({name: getattr(kit_hub, name) for name in request["names"]}, ensure_ascii=False)}


def op_hub_audit(request):
    """第 ⑤c 片：kit_hub 的回合审计。参数带标签，路径是字符串，照 kit_hub 的调用方转成 Path；结果带标签（元组成了列表）。
    home 给了时先设好 USERPROFILE 与 HOME（Path.home() 每次现读），调用完还原（⑤e1b：同一批里下一个没带 home 的请求不沿用，照 hub.turn）。
    HubError 交回文字与退出码，别的异常交回类型与文字。"""
    fn = request["fn"]
    args = [from_tagged(item) for item in request["args"]]
    saved_home = {name: os.environ.get(name) for name in ("USERPROFILE", "HOME")} if request.get("home") is not None else {}
    if request.get("home") is not None:
        os.environ["USERPROFILE"] = os.environ["HOME"] = request["home"]
    path = lambda value: None if value is None else Path(value)  # noqa: E731
    try:
        if fn == "turn_cost_usd":
            value = list(kit_hub.turn_cost_usd(*args))
        elif fn == "stream_events":
            value = list(kit_hub.stream_events(*args))
        elif fn == "session_cut_short":
            value = kit_hub.session_cut_short(kit_hub.Hub(Path(args[0])), *args[1:])
        elif fn in ("claude_path_rule", "path_forms"):
            value = getattr(kit_hub, fn)(Path(args[0]))
        elif fn in ("audit_claude_stream", "audit_pi_stream"):
            lines, spec, workspace, repo = args
            value = getattr(kit_hub, fn)(lines, spec, path(workspace), path(repo))
        elif fn == "pi_reach_problem":
            name, call_args, workspace, repo = args
            value = list(kit_hub.pi_reach_problem(name, call_args, Path(workspace), path(repo)))
        elif fn == "guard_config":
            value = kit_hub.guard_config(Path(args[0]), Path(args[1]))
        elif fn == "pi_flags_problem":
            value = kit_hub.pi_flags_problem(args[0], args[1], dict(os.environ))
        elif fn in ("jsonl_lines", "claude_session_effort"):
            value = getattr(kit_hub, fn)(*args)
        else:
            return {"ok": False, "error": "UNKNOWN_FN"}
    except kit_hub.HubError as exc:
        return {"ok": False, "error": "HubError", "message": str(exc), "code": exc.code}
    except Exception as exc:  # noqa: BLE001  类型与文字（⑤f 起文字也比）
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    finally:
        for name, before in saved_home.items():
            if before is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = before
    return {"ok": True, "value": to_tagged(value)}

def op_hub_prompt(request):
    """第 ⑤d 片：kit_hub 的回合输入与交差核对。参数带标签，仓库按路径给（Hub 由它建），路径参数照 kit_hub 的调用方转成 Path。
    template_dir、kernel_root 给了时，调用期间把 kit_hub 的 TEMPLATE_DIR、HERE 换成它（TS 那边以参数给同一个值），之后换回。
    worker_env 只交回排好序的变量名（迁移计划第 0 节：不比值）。HubError 交回文字与退出码，别的异常交回类型与文字。"""
    fn = request["fn"]
    args = [from_tagged(item) for item in request["args"]]
    saved = {}
    if request.get("template_dir") is not None:
        saved["TEMPLATE_DIR"] = kit_hub.TEMPLATE_DIR
        kit_hub.TEMPLATE_DIR = Path(request["template_dir"])
    if request.get("kernel_root") is not None:
        saved["HERE"] = kit_hub.HERE
        kit_hub.HERE = Path(request["kernel_root"]) / "scripts"
    path = lambda value: None if value is None else Path(value)  # noqa: E731
    hub = lambda repo: kit_hub.Hub(Path(repo))  # noqa: E731
    if request.get("started") is not None:  # 契约用：调用之前写一个标记，另一个进程据此掐时机
        Path(request["started"]).write_text("", encoding="utf-8")
    try:
        if fn in ("render_template", "role_prompt", "engineering_rules", "delivery_problem", "role_schema", "external_facts_section",
                  "interface_problem"):
            value = getattr(kit_hub, fn)(*args)
        elif fn in ("transitional_section", "worker_file_problem"):
            value = getattr(kit_hub, fn)(Path(args[0]))
        elif fn in ("letter_from_output", "delivered_output", "next_contract_version"):
            value = list(getattr(kit_hub, fn)(*args))
        elif fn == "input_path":
            repo, inputs, target = args
            value = kit_hub.input_path(hub(repo), path(inputs), target)
        elif fn == "turn_prompt":
            repo, ts, agent, task_id, letters, workspace, error, inputs, resume, routing_note = args
            value = kit_hub.turn_prompt(hub(repo), ts, agent, task_id, letters, Path(workspace), error, path(inputs), resume, routing_note)
        elif fn in ("regression_gates", "budget_usage"):
            value = getattr(kit_hub, fn)(hub(args[0]), args[1])
        elif fn == "worker_env":
            value = sorted(kit_hub.worker_env(*args))
        else:
            return {"ok": False, "error": "UNKNOWN_FN"}
    except kit_hub.HubError as exc:
        return {"ok": False, "error": "HubError", "message": str(exc), "code": exc.code}
    except Exception as exc:  # noqa: BLE001  类型与文字（⑤f 起文字也比）
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    finally:
        for name, original in saved.items():
            setattr(kit_hub, name, original)
    return {"ok": True, "value": to_tagged(value)}


def op_hub_contract(request):
    """第 ⑤e 片：kit_hub 的合同与战前门禁。参数带标签，路径参数照 kit_hub 的调用方转成 Path；结果带标签（元组成了列表）。
    HubError 交回文字与退出码，别的异常交回类型与文字。"""
    fn = request["fn"]
    args = [from_tagged(item) for item in request["args"]]
    for item in request.get("restores") or []:  # ⑤e2a：采样时调用当时的快照（带 .git），原地放回
        _restore_tree(item["from"], item["to"], item.get("links", []), with_git=bool(item.get("git")))
    given_env = request.get("env") or {}
    saved_env = {name: os.environ.get(name) for name in given_env}
    os.environ.update(given_env)
    saved_impl = pi_dispatch.KERNEL_IMPL_PATH
    if request.get("impl_path") is not None:
        pi_dispatch.KERNEL_IMPL_PATH = Path(request["impl_path"])
    try:
        if fn in ("tail", "strip_decisions", "decisions_section", "unparsed_check_ids", "external_fact_problems", "unverified_facts"):
            value = getattr(kit_hub, fn)(*args)
        elif fn == "resumed_session":  # ⑤i1：交回会话号或 None
            value = kit_hub.resumed_session(kit_hub.Hub(Path(args[0])), args[1], args[2], Path(args[3]))
        elif fn == "Engine.output_problem":  # ⑤i1：参数前两个是仓库与 only_task
            value = kit_hub.Engine(kit_hub.Hub(Path(args[0])), only_task=args[1]).output_problem(*args[2:])
        elif fn == "Engine.next_job":  # ⑤i2：（agent, [Path]）的路径交回字符串，同 _recorded_value
            found = kit_hub.Engine(kit_hub.Hub(Path(args[0])), only_task=args[1]).next_job()
            value = None if found is None else [found[0], [str(path) for path in found[1]]]
        elif fn == "finished_turn":  # ⑤i2：只看传进来的事件
            value = kit_hub.finished_turn(*args)
        elif fn in ("interrupted_letters", "stranded_stages", "letters_held", "supervisor_busy", "runner_may_idle_exit", "tasks_with_work"):
            value = getattr(kit_hub, fn)(kit_hub.Hub(Path(args[0])), *args[1:])
            value = list(value) if isinstance(value, tuple) else value  # ⑤i2：interrupted_letters 的（名字, 回合）元组成列表，同 _recorded_value
        elif fn == "runner_lock":  # ⑤i2：纯算路径，交回字符串
            value = str(kit_hub.runner_lock(kit_hub.Hub(Path(args[0])), args[1]))
        elif fn in ("turn_metrics", "exec_metrics"):  # ⑤j1：只读，参数是仓库
            value = getattr(kit_hub, fn)(kit_hub.Hub(Path(args[0])))
        elif fn == "uncommitted_references":  # ⑤j1：仓库与任务书的文字
            value = kit_hub.uncommitted_references(Path(args[0]), args[1])
        elif fn == "recorded_sum":  # ⑤j1：纯函数
            value = kit_hub.recorded_sum(*args)
        elif fn == "configured_parallel":  # ⑤j1：第二个参数记成 Namespace 的各键
            value = kit_hub.configured_parallel(kit_hub.Hub(Path(args[0])), argparse.Namespace(**args[1]))
        elif fn == "kernel_files":  # ⑤j2：hub 是 python 时的内核文件清单（路径交回字符串）
            value = [str(path) for path in kit_hub.kernel_files()]
        elif fn in ("code_fingerprint", "kernel_dirty", "kernel_changes"):  # ⑤j2：给了 files 照真的算；没给就是内核文件
            value = getattr(kit_hub, fn)(None if args[0] is None else [Path(item) for item in args[0]])
        elif fn in ("normalize_identity", "normalize_markup"):
            value = list(getattr(kit_hub, fn)(*args))
        elif fn == "tail_file":
            value = kit_hub.tail_file(Path(args[0]), *args[1:])
        elif fn == "pytest_outcomes":
            value = list(kit_hub.pytest_outcomes(Path(args[0])))
        elif fn == "contract_paths":  # ⑤e1b：Path 交回字符串（采样器的 _recorded_value 同样换）
            value = [str(path) for path in kit_hub.contract_paths(kit_hub.Hub(Path(args[0])), args[1])]
        elif fn in ("scope_missing_prefix", "contract_requirements", "dod_coverage_problems", "budget_problems", "answers_question"):
            value = getattr(kit_hub, fn)(kit_hub.Hub(Path(args[0])), *args[1:])
        elif fn == "read_kernel_impl":
            value = pi_dispatch.read_kernel_impl(Path(args[0]))
        elif fn == "argv_impl":  # impl 为 None 时读的选择文件换成给定的路径，调用完还原
            argv, impl, impl_path = args
            saved = pi_dispatch.KERNEL_IMPL_PATH
            pi_dispatch.KERNEL_IMPL_PATH = Path(impl_path)
            try:
                value = pi_dispatch.argv_impl(argv, impl)
            finally:
                pi_dispatch.KERNEL_IMPL_PATH = saved
        elif fn == "workspace_status":
            value = [list(item) for item in kit_hub.workspace_status(Path(args[0]))]
        elif fn in ("contract_digest", "hollow_baseline_problems"):
            value = getattr(kit_hub, fn)(kit_hub.Hub(Path(args[0])), *args[1:])
        elif fn == "run_pd":  # 交回结果与账本新增的行（不带 at）
            hub = kit_hub.Hub(Path(args[0]))
            ledger = hub.ledger()
            offset = ledger.stat().st_size if ledger.exists() else 0
            code, out = kit_hub.run_pd(hub, args[1], args[2])
            added = ledger.read_bytes()[offset:].decode("utf-8").splitlines() if ledger.exists() else []
            value = {"result": [code, out], "events": [{key: item for key, item in json.loads(line).items() if key != "at"} for line in added]}
        elif fn in ("kernel_env", "kernel_pytest_env"):  # 原样的名字（排好序）；值只交 PYTHONDONTWRITEBYTECODE 一个（不是凭据）
            env = getattr(kit_hub, fn)()
            value = [sorted(env), env.get("PYTHONDONTWRITEBYTECODE")]
        elif fn == "kernel_pytest":
            value = list(kit_hub.KERNEL_PYTEST)
        elif fn in ("mutant_timeout", "expected_missed_everywhere", "defect_matches", "defect_match_problems", "mutation_problems",
                    "unchanged_mismatches"):  # ⑤f 的纯函数
            value = getattr(kit_hub, fn)(*args)
        elif fn == "candidate_defects":
            value = list(kit_hub.candidate_defects(*args))
        elif fn == "gate_spec":
            value = list(kit_hub.gate_spec(Path(args[0]), args[1]))
        elif fn == "attempt_base":
            value = kit_hub.attempt_base(args[0], Path(args[1]))
        elif fn == "unmutated_problems":  # 连同改过的 ts["gate_post"]["unmutated"]，同采样器
            value = [kit_hub.unmutated_problems(*args), args[0]["gate_post"].get("unmutated")]
        elif fn in ("latest_checks", "cut_off", "checks_passed", "unfinished_why", "failed_checks_brief", "failure_lines", "report_leftovers",
                    "unreported_gate_claims"):  # ⑤g1：参数是 attempt 目录
            value = getattr(kit_hub, fn)(Path(args[0]))
        elif fn in ("interrupted_attempt", "carry_back", "carry_source", "rework_source", "failed_attempt"):  # 交回 Path 或（Path, 原因）
            given = [kit_hub.Hub(Path(args[0]))] + args[1:] if fn in ("interrupted_attempt", "carry_back", "carry_source") else args
            found = getattr(kit_hub, fn)(*given)
            value = None if found is None else str(found) if isinstance(found, Path) else [str(found[0]), found[1]]
        elif fn in ("attempts_left", "empty_commit"):
            value = getattr(kit_hub, fn)(kit_hub.Hub(Path(args[0])), *args[1:])
        elif fn == "rework_commits":  # 集合交回按 repr 排好的列表
            value = sorted(kit_hub.rework_commits(*args), key=repr)
        elif fn == "carryable":  # carried 给的是列表，照调用方换成集合
            value = kit_hub.carryable(Path(args[0]), set(args[1])) if len(args) > 1 else kit_hub.carryable(Path(args[0]))
        elif fn == "returned_blockers":
            value = kit_hub.returned_blockers(args[0], Path(args[1]))
        elif fn in ("retry_section", "rework_section"):
            value = getattr(kit_hub, fn)(Path(args[0]), *args[1:])
        elif fn == "add_modified_files":
            value = list(kit_hub.add_modified_files(*args))
        elif fn in ("gate_claims", "jev_flag"):
            value = getattr(kit_hub, fn)(*args)
        elif fn == "landing_records":  # ⑤h1
            value = kit_hub.landing_records(*args)
        elif fn == "landed_meanwhile":
            value = kit_hub.landed_meanwhile(kit_hub.Hub(Path(args[0])), *args[1:])
        elif fn == "read_owner_sweep":  # ⑤h2
            value = kit_hub.read_owner_sweep(kit_hub.Hub(Path(args[0])))
        elif fn == "sweep_gates":  # 真跑门禁基准：交回（退出码, 输出, 跑了哪几份）
            value = list(kit_hub.sweep_gates(Path(args[0])))
        elif fn == "gate_baselines":
            value = kit_hub.gate_baselines(Path(args[0]))
        elif fn in ("landing_chain", "on_branch"):  # 第三个参数是 Path 或 None
            value = getattr(kit_hub, fn)(kit_hub.Hub(Path(args[0])), args[1], None if args[2] is None else Path(args[2]))
        elif fn == "kernel_impl_tables":  # 几张转交名单的键，TS 那边逐张对照
            value = {name: [list(key) for key in sorted(getattr(pi_dispatch, name))]
                     for name in ("TS_READONLY_COMMANDS", "TS_ONLY_COMMANDS", "TS_CONFIG_COMMANDS", "TS_DISPATCHER_COMMANDS")}
            value["CONFIG_ACTION_FAMILIES"] = sorted(family for family, _dest in pi_dispatch.CONFIG_ACTION_DESTS)
        else:
            return {"ok": False, "error": "UNKNOWN_FN"}
    except kit_hub.HubError as exc:
        return {"ok": False, "error": "HubError", "message": str(exc), "code": exc.code}
    except pi_dispatch.DispatchError as exc:
        return {"ok": False, "error": "DispatchError", "message": str(exc), "code": exc.code}
    except Exception as exc:  # noqa: BLE001  类型与文字（⑤f 起文字也比）
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    finally:
        pi_dispatch.KERNEL_IMPL_PATH = saved_impl
        for name, before in saved_env.items():
            if before is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = before
    return {"ok": True, "value": to_tagged(value)}


def _tree_listing(root):
    """一个目录下的文件（相对路径用正斜杠、排好序）：字节数、可不可写、sha256。"""
    rows = []
    for folder, _dirs, files in os.walk(str(root)):
        for name in files:
            path = Path(folder) / name
            rows.append([path.relative_to(root).as_posix(), path.stat().st_size, os.access(str(path), os.W_OK),
                         hashlib.sha256(path.read_bytes()).hexdigest()])
    return sorted(rows)


def _inputs_artifacts(target, info):
    """stage_inputs 留下的东西：（目录，清单）、输入目录里每个文件的字节数、可写与否、sha256，INPUTS.json、SKIPPED.md 的原始字节（base64），
    以及上一层（<仓库名>-hub-inputs）里剩下的目录：这个主任务留下的旧目录清掉了、别的主任务的没动。"""
    raw = lambda name: base64.b64encode((target / name).read_bytes()).decode("ascii") if (target / name).is_file() else None  # noqa: E731
    return {"dir": str(target), "info": info, "files": _tree_listing(target), "index": raw(kit_hub.INPUTS_INDEX), "skipped": raw("SKIPPED.md"),
            "siblings": sorted(os.listdir(str(target.parent)))}


def op_hub_inputs(request):
    """第 ⑤d 片：kit_hub 的 stage_inputs（与 remove_inputs），交回 _inputs_artifacts。HubError 交回文字与退出码，别的异常交回类型与文字。
    采样的重放（⑤d2）另给 restore（照 op_hub_turn），以及 worktree_root、input_file_limit：调用期间换掉 kit_hub 的 worktree_root 与
    INPUT_FILE_LIMIT，对应 inputs_fixture 的 monkeypatch。"""
    hub = kit_hub.Hub(Path(request["repo"]))
    if request.get("restore") is not None:
        _restore_tree(request["restore"]["from"], request["restore"]["to"], request["restore"].get("links", []))
    saved = (kit_hub.worktree_root, kit_hub.INPUT_FILE_LIMIT)
    if request.get("worktree_root") is not None:
        kit_hub.worktree_root = lambda _repo: Path(request["worktree_root"])
    if request.get("input_file_limit") is not None:
        kit_hub.INPUT_FILE_LIMIT = request["input_file_limit"]
    try:
        if request.get("remove") is not None:
            kit_hub.remove_inputs(Path(request["remove"]))
            return {"ok": True, "value": to_tagged(Path(request["remove"]).exists())}
        target, info = kit_hub.stage_inputs(hub, from_tagged(request["ts"]), request["key"])
    except kit_hub.HubError as exc:
        return {"ok": False, "error": "HubError", "message": str(exc), "code": exc.code}
    except Exception as exc:  # noqa: BLE001  类型与文字（⑤f 起文字也比）
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    finally:
        kit_hub.worktree_root, kit_hub.INPUT_FILE_LIMIT = saved
    return {"ok": True, "value": to_tagged(_inputs_artifacts(target, info))}


#: 回合里内核自己定下的环境变量：比值（别的只比名字，迁移计划第 0 节）
KERNEL_SET_ENV = ("THEMIS_DELIVER_SCHEMA", "THEMIS_GUARD", "CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR")


def _turn_launcher(calls, inner):
    """包住一个 launcher：记下命令行、工作目录、环境的名字（内核自己定下的几个记值）与时限，再交给 inner。"""
    def launcher(cmd, cwd, env, out, err, timeout):
        calls.append({"cmd": list(cmd), "cwd": str(cwd), "env": sorted(env), "kernel_env": {name: env.get(name) for name in KERNEL_SET_ENV},
                      "timeout": timeout})
        return inner(cmd, cwd, env, out, err, timeout)
    return launcher


def _turn_artifacts(hub, summary, calls, inputs, agent, offset):
    """一个回合留下的东西：summary、launcher 的调用、回合目录里每个文件的原始字节、输入目录里的长输入、会话记录与账本新增的部分（base64）。"""
    turn_dir = Path(summary["turn_dir"])
    b64 = lambda path: base64.b64encode(path.read_bytes()).decode("ascii")  # noqa: E731
    files = {name: b64(turn_dir / name) for name in sorted(os.listdir(turn_dir))}
    long_prompts = {path.name: b64(path) for path in sorted(Path(inputs).glob("prompt-*.md"))} if inputs is not None else {}
    record = hub.agent_path(agent)
    ledger = hub.ledger()
    tail = ledger.read_bytes()[offset:] if ledger.exists() else b""
    return {"summary": summary, "calls": calls, "files": files, "long_prompts": long_prompts,
            "agent": b64(record) if record.exists() else None, "ledger": base64.b64encode(tail).decode("ascii")}


#: os.readlink 交回的长路径前缀（两个反斜杠、问号、反斜杠）：记链接的指向时去掉，与用例建链接时给的写法一样
LONG_PREFIX = chr(92) * 2 + "?" + chr(92)


def _snapshot_tree(source, target, with_git=False):
    """把 source 整份拷到 target（.git 不拷；with_git 时连 .git 一起拷，⑤e2a 的调用当时快照）：普通文件照 copy2，只读位跟着；符号链接与联接不拷，交回 [相对路径（正斜杠）, 指向, 种类]，
    重放时由 _restore_tree 照原样重建。shutil.copytree 会顺着联接把整棵树抄进来，Node 的 cpSync 会把联接建成目录符号链接。"""
    links = []

    def walk(folder, parts):
        os.makedirs(os.path.join(str(target), *parts), exist_ok=True)
        for entry in sorted(os.scandir(folder), key=lambda item: item.name):
            if entry.name == ".git" and not with_git:
                continue
            rel = parts + [entry.name]
            if entry.is_symlink() or os.path.isjunction(entry.path):
                pointed = os.readlink(entry.path)
                if pointed.startswith(LONG_PREFIX) and not pointed.startswith(LONG_PREFIX + "UNC"):
                    pointed = pointed[len(LONG_PREFIX):]
                kind = "junction" if os.path.isjunction(entry.path) else "dir" if entry.is_dir() else "file"
                links.append(["/".join(rel), pointed, kind])
            elif entry.is_dir():
                walk(entry.path, rel)
            else:
                shutil.copy2(entry.path, os.path.join(str(target), *rel))

    walk(str(source), [])
    _copy_dir_times(str(source), str(target), with_git)
    return links


def _copy_dir_times(source, target, with_git=False):
    """⑤g：目录的修改时刻照源目录设回去（文件的由 copy2 管）。在目录的内容放好之后设，由深到浅；链接与联接不进。
    kit_hub 的 final_audit_turn 在没有 candidate.patch 时读 attempt 目录本身的时刻。对应 TS 的 copyTreeTimes。"""
    for entry in os.scandir(source):
        if entry.name == ".git" and not with_git:
            continue
        if entry.is_dir(follow_symlinks=False) and not entry.is_symlink() and not os.path.isjunction(entry.path):
            _copy_dir_times(entry.path, os.path.join(target, entry.name), with_git)
    info = os.stat(source)
    os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns))


def _restore_tree(source, target, links=(), with_git=False):
    """把快照原样放回原来的位置（采样的重放：两边先后在调用当时的那个目录里跑），链接与联接照记下的重建。只读的文件先改回可写再删。"""
    def writable(func, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    if Path(target).exists():
        shutil.rmtree(str(target), onexc=writable)
    _snapshot_tree(source, target, with_git)
    for rel, pointed, kind in links:
        path = os.path.join(str(target), *rel.split("/"))
        if kind == "junction":
            import _winapi
            _winapi.CreateJunction(pointed, path)
        else:
            os.symlink(pointed, path, target_is_directory=kind == "dir")
    if links:  # 重建链接改了所在目录的时刻
        _copy_dir_times(str(source), str(target), with_git)


def op_hub_turn(request):
    """第 ⑤d 片：kit_hub.TurnRunner.run，配一个回放的 launcher：把 script 里的字节原样写进标准输出与标准错误，交回给定的
    退出码、是否超时与用时，记下命令行、工作目录、环境的名字（内核自己定下的几个记值）与时限。不确定的几样窄窄地换成给定的值
    （themistally-15 定的）：utc_compact；os.urandom 只在要 2 字节时；uuid4；time.time 只在 run() 期间。交回 summary、launcher 的调用、
    回合目录里每个文件的原始字节、输入目录里的长输入、会话记录与账本新增的部分（base64）。"""
    import uuid as uuid_module

    hub = kit_hub.Hub(Path(request["repo"]))
    script = from_tagged(request["script"]) if request.get("script") is not None else {}
    calls = []
    if request.get("restore") is not None:
        _restore_tree(request["restore"]["from"], request["restore"]["to"], request["restore"].get("links", []))

    def replayed(cmd, cwd, env, out, err, timeout):
        out.write(base64.b64decode(script.get("stdout", "")))
        err.write(base64.b64decode(script.get("stderr", "")))
        return {"exit_code": script.get("exit_code", 0), "timed_out": bool(script.get("timed_out")), "wall_seconds": script.get("wall_seconds", 1.5)}

    launcher = _turn_launcher(calls, replayed)

    sources = request.get("sources")  # 不给时什么都不换：形状核对用真的来源
    real_urandom = os.urandom
    saved = (kit_hub.utc_compact, os.urandom, uuid_module.uuid4, time.time)
    ledger = hub.ledger()
    offset = ledger.stat().st_size if ledger.exists() else 0
    agent, key, workspace, role, prompt, retry_of, fresh, inputs, session_id = [from_tagged(item) for item in request["args"]]
    overrides = [(kit_hub.ROSTER, request.get("roster") or {}), (kit_hub.DELIVERY_SHA256, request.get("delivery_sha256") or {})]
    saved_tables = [(table, {name: table.get(name, None) for name in given}, set(given) - set(table)) for table, given in overrides]
    for table, given in overrides:
        table.update(given)
    # home 也在调用期间设、调用完还原：同一批里下一个没带 home 的请求不沿用
    given_env = dict(request.get("env") or {}, **({"USERPROFILE": request["home"], "HOME": request["home"]} if request.get("home") is not None else {}))
    saved_env = {name: os.environ.get(name) for name in given_env}
    os.environ.update(given_env)
    if sources is not None:
        kit_hub.utc_compact = lambda: sources["compact"]
        os.urandom = lambda n: bytes.fromhex(sources["random2"]) if n == 2 else real_urandom(n)
        uuid_module.uuid4 = lambda: uuid_module.UUID(sources["uuid4"])
        time.time = lambda: float(sources["seconds"])
    try:
        summary = kit_hub.TurnRunner(hub, launcher=launcher).run(agent, key, Path(workspace), role, prompt, retry_of, fresh,
                                                                  None if inputs is None else Path(inputs), session_id)
    except kit_hub.HubError as exc:
        return {"ok": False, "error": "HubError", "message": str(exc), "code": exc.code}
    except Exception as exc:  # noqa: BLE001  类型与文字（⑤f 起文字也比）
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    finally:
        kit_hub.utc_compact, os.urandom, uuid_module.uuid4, time.time = saved
        for table, before, added in saved_tables:
            table.update({name: value for name, value in before.items() if name not in added})
            for name in added:
                table.pop(name, None)
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    return {"ok": True, "value": to_tagged(_turn_artifacts(hub, summary, calls, inputs, agent, offset))}


def _autouse_fixtures(path):
    """一个测试文件里带 autouse=True 的 pytest 夹具的函数名（照源码找，不靠导入）。"""
    names = []
    for node in ast.parse(Path(path).read_text(encoding="utf-8")).body:
        for deco in getattr(node, "decorator_list", []):
            if isinstance(deco, ast.Call) and any(item.arg == "autouse" and getattr(item.value, "value", None) is True for item in deco.keywords):
                names.append(node.name)
    return names


def _recorded_value(name, value):
    """采样当时的结果，形状照 op_hub_audit、op_hub_prompt 的后处理（元组成列表，worker_env 只记排好序的名字：值不进样本），
    存成 JSON 文字：随样本再经 to_tagged 也只是一个字符串，契约照原样拿去比。"""
    if name == "worker_env":
        value = sorted(value)
    elif name == "contract_paths":  # ⑤e1b：Path 记成字符串，照 op_hub_contract
        value = [str(path) for path in value]
    elif name == "workspace_status":  # ⑤e2a：（状态，路径）的元组成列表，照 op_hub_contract
        value = [list(item) for item in value]
    elif name == "kernel_files":  # ⑤j2：Path 的列表记成字符串，照 op_hub_contract
        value = [str(path) for path in value]
    elif name == "Engine.next_job" and value is not None:  # ⑤i2：（agent, [Path]）的路径记成字符串，照 op_hub_contract
        value = [value[0], [str(path) for path in value[1]]]
    elif isinstance(value, tuple):  # ⑤g1：carry_source、carry_back 交回（Path, 原因）
        value = [str(item) if isinstance(item, Path) else item for item in value]
    elif isinstance(value, Path):  # ⑤f：apply_candidate、ensure_worktree 交回 worktree 的路径
        value = str(value)
    try:
        return json.dumps({"ok": True, "value": to_tagged(value)})
    except Exception:  # noqa: BLE001
        return json.dumps({"ok": False, "error": "UNTAGGABLE"})


def _recorded_error(exc):
    if isinstance(exc, kit_hub.HubError):  # ⑤g2：子类（LandBusy）记自己的类名，引擎靠它扣信
        return json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc), "code": exc.code})
    return json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)})


#: ⑤e2b：用例当时换掉、契约照记录注入的内层函数（themistally-15 定的名单，设计稿第 8.8 节；⑤f 加 worktree_root；⑤g2 加
#: rework_added_files 与决策端的 Session、load_locked_batteries，Session 换成一个类，它的 ask 记成一次内层调用）
FLOW_INNER = ("run_pd", "contract_requirements", "budget_problems", "revalidate_contract", "worktree_root", "rework_added_files", "Session",
              "load_locked_batteries", "_running_attempts",  # ⑤h1：landing_blockers 调的调度器 _running_attempts
              "sweep_gates", "rehearse_landing", "find_bun", "read_kernel_impl", "ts_install_if_stale")  # ⑤h2
#: ⑤f：用例没换、也照记录注入的（themistally-15 定的，⑤f 设计稿第 3、10 节）：白盒测试那一次 run_supervised 只在 accept_gate_post 里录，
#: mkdtemp 在建 worktree 的两个函数里录
FLOW_ALWAYS = {"accept_gate_post": ("run_supervised",), "apply_candidate": ("mkdtemp",), "ensure_worktree": ("mkdtemp",),
               "run_exec": ("mkdtemp",),  # ⑤g2：rebase_candidate 的临时 worktree
               "landing_blockers": ("pid_alive",),  # ⑤h1：执行标记记的是采样进程的 pid，重放时它已经不在
               # ⑤h2：门禁基准不在重放里真跑（真跑放在手写场景），临时 worktree 照记录建
               "regression_sweep": ("sweep_gates", "mkdtemp"), "rehearse_landing": ("sweep_gates", "mkdtemp"),
               "owner_sweep": ("sweep_gates", "mkdtemp")}
#: ⑤h2：没有 ts 参数的流程函数（重放与比较时 ts 记成 None）
FLOW_NO_TS = ("owner_sweep", "mark_owner_moved", "ts_install_if_stale")
#: ⑤h2：内层名与它换掉的属性名不同的（ts_install_if_stale 的 runner：重放时 runner 为 None，走 pd.run_supervised）
FLOW_ATTR = {"ts_runner": "run_supervised", "Engine.verify_delivery": "verify_delivery", "Engine.auto_jev": "auto_jev",  # ⑤i1：Engine 的两个方法
             "Hub.deliver": "deliver",  # ⑤i2：peek_deliver 包的
             "Popen": "Popen", "sleep": "sleep", "Engine.step": "step"}  # ⑤j2：kit_hub.subprocess.Popen、kit_hub.time.sleep、Engine.step
#: 第二个参数是 ts、契约要比调用之后的 ts 的内层函数。⑤i1 加上 Engine 的用例会换掉、换上的假函数会改 ts 的那几个（Engine 的两个方法第二个
#: 参数是 ts 或 state，第一个是 Engine 本身）
FLOW_TS_INNER = ("contract_requirements", "budget_problems", "revalidate_contract",
                 "run_exec", "run_jev", "finalize", "tidy_finished", "regression_sweep", "apply_candidate", "seed_whitebox", "ensure_worktree",
                 "Engine.verify_delivery", "Engine.auto_jev",
                 # ⑤i1：4376 的假 rehearse_landing 会写 ts["rehearsal"]，after_land 接着存盘（⑤h2 注入过的那一次没改 ts，加上不影响它）
                 "rehearse_landing")
#: 重放时要转成 Path 的参数（按位置）
FLOW_PATH_ARGS = {"accept_gate_pre": (2,), "seed_whitebox": (2,), "accept_gate_post": (2,), "run_mutations": (2, 3), "finish_exec": (2,),
                  "write_review": (2,), "start_rework": (2,), "rebase_candidate": (2,), "start_retry": (2,), "final_audit_turn": (2,), "record_pass": (2,)}
#: ⑤e2b：最外层调用期间的提交作者与日期（采样与三边重放一样），门禁基准测试的提交 SHA 才钉得住
FLOW_GIT_ENV = {"GIT_AUTHOR_NAME": "themis-contract", "GIT_AUTHOR_EMAIL": "contract@example.invalid",
                "GIT_COMMITTER_NAME": "themis-contract", "GIT_COMMITTER_EMAIL": "contract@example.invalid",
                "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00"}
#: ⑤i1：Engine 的方法在名单里写成 "Engine.<方法名>"。它们与 land、release_dependents 是 ⑤i 的流程函数，另外几样（themistally-04 复核的
#: ⑤i 设计稿第 3、4 节）：认另一组用例会换掉的内层函数（FLOW_INNER_I，只在 ⑤i 的最外层调用里认，前几片的样本不变）；一路会走到的几样
#: 总照记录注入（FLOW_ALWAYS_I）；钉住 time.time（执行端等不到落地锁时扣信，解除时刻是 int(time.time()) + 120）；名册的改动随样本带上
FLOW_I_FUNCTIONS = ("land", "release_dependents", "requeue_interrupted", "requeue_task", "requeue_letters", "report_stranded_exec")  # ⑤i2 加续接一族
FLOW_INNER_I = ("role_prompt", "ensure_worktree", "apply_candidate", "seed_whitebox", "run_exec", "run_jev", "finalize", "tidy_finished",
                "regression_sweep", "Engine.verify_delivery", "Engine.auto_jev",
                "release_held")  # ⑤i2：4778 的 hold_until_called 换掉它，step 每一步先调
FLOW_ALWAYS_I = ("mkdtemp", "run_supervised", "sweep_gates", "pid_alive")
#: ⑤j1：站主命令。参数只有一个 Namespace，记成仓库与 Namespace 的各键（去掉 func）；调用期间另记读到的标准输入与写出的 stdout、stderr。
#: 照 ⑤i 的流程函数记（钉时刻、注入用例换掉的内层函数与 FLOW_ALWAYS_I）
FLOW_J1 = ("cmd_init", "cmd_task_new", "cmd_task_close", "cmd_task_rebase", "cmd_task_after", "cmd_task_unstick", "cmd_task_budget", "cmd_task_cap",
           "cmd_task_cleanup", "cmd_send", "cmd_exec_recheck", "cmd_take", "cmd_status", "cmd_metrics")
#: ⑤i1：Engine 的方法里要转成 Path 的参数（方法参数的位置，不含 self）；worker_job 的 paths 是一组路径，另转
FLOW_ENGINE_PATHS = {"Engine.worker_turns": (4, 6), "Engine.redeliver": (6,)}
#: 参数里一组路径（paths）的位置（方法参数的位置，不含 self）：⑤i1 的 worker_job，⑤i2 的几个
FLOW_ENGINE_PATH_LISTS = {"Engine.worker_job": 2, "Engine.fail_stage": 1, "Engine.coordinator_turn": 1, "Engine.route": 2, "Engine.report_step_error": 1}
#: TurnRunner.run 的参数名：Engine 调 runner 时有的按位置、有的按关键字给
RUNNER_ARGS = ("agent", "session_key", "workspace", "role_prompt", "prompt", "retry_of", "fresh", "inputs", "session_id")
#: 调用当时有活的持有者就不重放的目录锁，另加 .runners 下各主任务的：重放时持有者已经不在，接管与否两边会不同（⑤i 设计稿第 4 节的两类跳过）。
#: ⑤i2 起只算这次调用拿过或探过的（_TOUCHED_LOCKS）：⑤i1 中段为 release_dependents 单开的例外（它一路不碰锁）由这一条涵盖
FLOW_LOCKS = (".land", ".sweep", ".lock", ".runner", ".owner-sweep")


#: ⑤j2：进程模型。cmd_run、cmd_owner_sweep、cmd_exclusive 同站主命令记（仓库与 Namespace 的各键）；其余第一个参数是 hub。
FLOW_J2_COMMANDS = ("cmd_run", "cmd_owner_sweep", "cmd_exclusive")
FLOW_J2 = FLOW_J2_COMMANDS + ("supervise_tick", "owner_sweep_tick", "spawn_runner", "spawn_task_runner", "refuse_dirty_kernel", "pause_requested")
#: ⑤j2：用例换掉、契约照记录注入的内层函数（另有 FLOW_INNER_I 的 release_held 与 FLOW_ALWAYS_I 的 pid_alive）。交回进程对象的
#: spawn_task_runner、Popen 交回录制代理，它的 poll 记成内层调用 proc.poll（⑤j 设计稿第 3 节）
FLOW_INNER_J2 = ("spawn_task_runner", "spawn_runner", "kernel_dirty", "kernel_settled", "code_fingerprint", "kernel_changes", "tasks_with_work",
                 "requeue_interrupted", "owner_sweep_tick", "Popen", "sleep", "Engine.step")
COMMANDS = FLOW_J1 + FLOW_J2_COMMANDS  # 参数是 Namespace、仓库照 args.repo 找的
STREAMS = FLOW_J1 + FLOW_J2  # 调用期间截 stdout、stderr、记读到的标准输入的


def _flow_i(name):
    # ⑤j1：站主命令；⑤j2：进程模型（⑤i2 的跑到静止换成了真的 cmd_run）
    return name.startswith("Engine.") or name in FLOW_I_FUNCTIONS or name in FLOW_J1 or name in FLOW_J2


class _Tee:
    """⑤j1：站主命令调用期间的 stdout、stderr：照写进原来的流（用例照旧读得到），另记一份。"""

    def __init__(self, inner):
        self.inner, self.parts = inner, []

    def write(self, text):
        self.parts.append(text)
        return self.inner.write(text)

    def flush(self):
        self.inner.flush()

    def __getattr__(self, name):
        return getattr(self.inner, name)


class _StdinRecorder:
    """⑤j1：站主命令调用期间的 stdin：照读原来的流，记下读到的文字（cmd_send 的 --file - 只调 read()）；没读过记 None。"""

    def __init__(self, inner):
        self.inner, self.taken = inner, None

    def read(self, *args):
        text = self.inner.read(*args)
        self.taken = (self.taken or "") + text
        return text

    def __getattr__(self, name):
        return getattr(self.inner, name)


#: ⑤j2：进程代理的编号（整次采样里递增）与当前这次最外层调用的记录上下文（inner、roots、busy）；重放时各编号对应的假进程
_PROC = {"next": 0, "context": None, "replay": {}}


class _ProcRecorder:
    """⑤j2：用例造的假进程（或换掉的 Popen 起出来的）的录制代理。属性照转；poll 在有记录上下文、又不在别的内层调用里面时记成一次内层调用
    proc.poll（交回值、调用期间的文件改动，同内层函数），poll 里 take 信造成的改动就随这一次记下，重放时在同一个次序写回。"""

    def __init__(self, obj):
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_id", _PROC["next"])
        _PROC["next"] += 1

    def poll(self):
        context = _PROC["context"]
        if context is None or context[2][0]:
            return self._obj.poll()
        inner, roots, busy = context
        entry = {"fn": "proc.poll", "proc": self._id}
        before = _flow_listing(roots)
        busy[0] = True
        try:
            value = self._obj.poll()
        except Exception as exc:  # noqa: BLE001  录下来照样抛
            entry["raise"] = [type(exc).__name__, str(exc)]
            raise
        else:
            entry["value"] = to_tagged(_plain(value))
        finally:
            busy[0] = False
            entry["files"] = _flow_changes(roots, before)
            inner.append(entry)
        return value

    def __getattr__(self, name):
        return getattr(self._obj, name)

    def __setattr__(self, name, value):
        setattr(self._obj, name, value)


class _ProcReplay:
    """⑤j2：重放时的假进程。pid 照记录；poll 逐次核对记下的 proc.poll（编号相同），写回文件改动，交回记下的值；returncode 是最后一次 poll
    的值（owner_sweep_tick 在 poll 不是 None 之后读它，真的 Popen 与用例的 FakeProc 都是这样）。只有 poll、pid、returncode 三样：
    kit_hub 以后要是对这些进程调 kill、wait，重放报 AttributeError，正好当绊线（themistally-04 复核时要的；TS 的假进程照这个来）。"""

    def __init__(self, ident, pid, queue, roots):
        self._id, self.pid, self.returncode, self._queue, self._roots = ident, pid, None, queue, roots

    def poll(self):
        expected = self._queue.pop(0) if self._queue else None
        if expected is None or expected.get("fn") != "proc.poll" or expected.get("proc") != self._id:
            shown = expected and {key: expected.get(key) for key in ("fn", "proc")}
            raise _InjectionMismatch(json.dumps({"got": {"fn": "proc.poll", "proc": self._id}, "expected": shown}, ensure_ascii=False))
        _flow_apply_files(expected, self._roots)
        self.returncode = from_tagged(expected["value"])
        return self.returncode


def _proc_shown(value):
    """进程代理（录制的或重放的）记成编号与 pid。"""
    return {"__proc__": value._id, "pid": getattr(value, "pid", None)}


def _procs_of(value, queue, roots):
    """重放：参数与注入的交回值里记成 {"__proc__", "pid"} 的换回假进程，同一个编号是同一个对象。"""
    if isinstance(value, dict) and set(value) == {"__proc__", "pid"}:
        return _PROC["replay"].setdefault(value["__proc__"], _ProcReplay(value["__proc__"], value["pid"], queue, roots))
    if isinstance(value, dict):
        return {key: _procs_of(item, queue, roots) for key, item in value.items()}
    if isinstance(value, list):
        return [_procs_of(item, queue, roots) for item in value]
    return value


def _argv_shown(argv):
    """起子进程的命令行：Python 与 kit_hub.py 的路径换成占位（TS 起的是同一个启动器，路径各自取）。"""
    hub_file = os.path.normcase(str(Path(kit_hub.__file__).resolve()))
    shown = []
    for item in argv:
        text = str(item)
        if text == sys.executable:
            shown.append("<python>")
        elif text.endswith(".py") and os.path.normcase(str(Path(text).resolve())) == hub_file:
            shown.append("<kit_hub>")
        else:
            shown.append(text)
    return shown


def _sleep_clock(pin, runner):
    """⑤j2：跑到静止换成真的 cmd_run（⑤j 设计稿第 5 节，request["clock"] 是 "sleep"）要换上的几样，交回 {(对象, 属性): 新值}：
    - time.sleep(秒) 把钉住的时钟往后挪这么多秒、不真睡；第 400 次抛错（cmd_run 的 max_steps 只数办了事的步，空转靠这道封顶）；
    - time.monotonic、time.time 与 kit_hub.utc_now、utc_compact 跟着钉住的时钟走（new_msg_id 用 utc_compact，编号照次序接着编）；
    - code_fingerprint 交回常数、kernel_changes 交回 []：开发中的内核是脏的、还在变；
    - cmd_run 自己建的 Engine 用 TurnRunner：它的 run 照剧本交回（runner 是 None 就不换）。
    time 是整个进程的模块，DirLock 的等待也算在内；跑到静止时锁都没人抢，次数与 TS 一样（TS 只换 cmdRun 的 deps）。"""
    now, calls = [pin], [0]

    def sleep(seconds):
        calls[0] += 1
        if calls[0] >= 400:
            raise RuntimeError("跑到静止：sleep 调到第 400 次")
        now[0] += round(seconds * 1_000_000)

    def moment():
        return datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(microseconds=now[0])

    swaps = {(time, "sleep"): sleep, (time, "monotonic"): lambda: now[0] / 1_000_000, (time, "time"): lambda: now[0] / 1_000_000,
             (kit_hub, "utc_now"): lambda: moment().strftime("%Y-%m-%dT%H:%M:%SZ"),
             (kit_hub, "utc_compact"): lambda: moment().strftime("%Y%m%dT%H%M%S%fZ"),
             (kit_hub, "code_fingerprint"): lambda files=None: "quiesce", (kit_hub, "kernel_changes"): lambda files=None: []}
    if runner is not None:
        swaps[(kit_hub.TurnRunner, "run")] = lambda self, *args, **kwargs: runner(*args, **kwargs)
    return swaps


def _flow_attr(name):
    return FLOW_ATTR.get(name, name)


def _owner_attr(name):
    """名单里的名字落在哪个对象的哪个属性上：⑤i1 的 "Engine.<方法名>" 在 Engine 类上，其余在 kit_hub 上。"""
    return (kit_hub.Engine, name.split(".", 1)[1]) if name.startswith("Engine.") else (kit_hub, name)


def _inputs_files(inputs):
    """回合的输入目录在调用当时的文件：{相对路径（正斜杠）: sha256}；不是目录时记 None。"""
    if inputs is None or not Path(inputs).is_dir():
        return None
    found = {path.relative_to(inputs).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in Path(inputs).rglob("*") if path.is_file()}
    return dict(sorted(found.items()))  # 按相对路径的码点排：契约比 JSON 文字，TS 一侧同样排


def _live_locks(hub):
    """hub 底下有活的持有者的目录锁（owner.json 里的 pid）。用探针载入时的 pid_alive：用例可能把它换掉了。"""
    root = Path(hub.root)
    paths = [root / name for name in FLOW_LOCKS] + (sorted((root / ".runners").iterdir()) if (root / ".runners").is_dir() else [])
    held = []
    for path in paths:
        owner = path / "owner.json"
        try:
            pid = json.loads(owner.read_text(encoding="utf-8") or "{}").get("pid") if owner.is_file() else None
        except ValueError:
            pid = None
        if pid and _REAL_PID_ALIVE(int(pid)) is not False:
            held.append(path.relative_to(root).as_posix())
    return held


def _state_dirs(hub, ts=None, state=None):
    """⑤i1：状态里记着的 worktree 与 attempt 目录，调用当时还在、又不在仓库里的（快照照不到，文件改动也比不到）。看三处：盘上的
    state.json，以及参数里的 ts 与 state（用例手搭、没存盘的也算）。"""
    try:
        tasks = list(hub.load_state()["tasks"].values())
    except Exception:  # noqa: BLE001  用例拿不存在的仓库建 Hub
        tasks = []
    tasks += [ts] if isinstance(ts, dict) else []
    tasks += list((state.get("tasks") or {}).values()) if isinstance(state, dict) else []
    found = []
    for ts in [item for item in tasks if isinstance(item, dict)]:
        items = [record.get("path") for record in (ts.get("workspaces") or {}).values() if isinstance(record, dict)]
        items.append((ts.get("exec") or {}).get("run_dir"))
        for item in items:
            outside = (item and Path(item).is_dir() and not Path(item).resolve().is_relative_to(Path(hub.repo).resolve()))
            if outside and all(Path(item).resolve() != seen.resolve() for seen in found):
                found.append(Path(item))
    return found


def _outside_dirs(hub):
    """⑤j1：站主命令会看在不在的仓库外目录：.agent/runs 下各 attempt 的 meta.json 记的 worktree（retire_attempts），与 state.json 里各主任务
    workspaces 记的路径（remove_workspaces）。交回（在的，不在的）：在的随快照存，不在的重放前删掉。3276 在 cleanup 之后又建了同一个
    wt-attempt-001，删掉的 not-a-worktree 又被上一次重放的快照放回来。"""
    found = []
    for meta in sorted((Path(hub.repo) / ".agent" / "runs").glob("*/attempt-*/meta.json")):
        try:
            found.append(json.loads(meta.read_text(encoding="utf-8")).get("worktree"))
        except (OSError, ValueError):
            continue
    try:
        tasks = list(hub.load_state()["tasks"].values())
    except Exception:  # noqa: BLE001  同 _state_dirs
        tasks = []
    for ts in [item for item in tasks if isinstance(item, dict)]:
        found += [record.get("path") for record in (ts.get("workspaces") or {}).values() if isinstance(record, dict)]
    present, absent = [], []
    for item in found:  # 用例手搭的状态里有相对路径的占位（"old" 一类），不算
        if not isinstance(item, str) or not Path(item).is_absolute() or Path(item).resolve().is_relative_to(Path(hub.repo).resolve()):
            continue
        group = present if Path(item).is_dir() else absent
        if all(Path(item).resolve() != seen.resolve() for seen in group):
            group.append(Path(item))
    return present, absent


def _flow_after(bound):
    """⑤i1：调用之后要比的字典与列表参数（state、fields 这类被原地改的；ts 另在 _flow_state 里）。⑤i2：元组也算（requeue_interrupted 的
    skip 缺省是 ()，重放时从 JSON 来的是列表，两边都记成列表才对得上）。"""
    return {key: item for key, item in bound.arguments.items()
            if key not in ("self", "hub", "engine") and isinstance(item, (dict, list, tuple, set, frozenset))}


class _RunnerProxy:
    """⑤i1：Engine 的 runner 换成它，run 走录制或注入的包装。"""

    def __init__(self, run):
        self.run = run


class _EngineProxy:
    """⑤i1：land 收到用例自己写的假 Engine（只有 handle_pass、after_land，4001 那条）时换成它，两个方法走录制或注入的包装。"""

    def __init__(self, handle_pass, after_land):
        self.handle_pass, self.after_land = handle_pass, after_land


class _InjectionMismatch(Exception):
    """重放注入的内层调用与记录对不上（参数不同、多调）。"""


class _Capsys:
    """⑤i2：pytest 的 capsys 的替身（test_status_shows_the_parallel_runners 要）。采样器本来就把 sys.stdout、sys.stderr 截进两个 StringIO，
    readouterr 照 pytest 交回上次读之后写进的部分（out、err 两栏的具名元组）。"""

    def __init__(self, out, err):
        self.streams, self.read = (out, err), [0, 0]

    def readouterr(self):
        parts = []
        for index, stream in enumerate(self.streams):
            text = stream.getvalue()
            parts.append(text[self.read[index]:])
            self.read[index] = len(text)
        return _CaptureResult(*parts)


_CaptureResult = collections.namedtuple("CaptureResult", "out err")


def _plain(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, kit_hub.Hub):
        return str(value.repo)
    if isinstance(value, (_ProcRecorder, _ProcReplay)):  # ⑤j2
        return _proc_shown(value)
    if isinstance(value, argparse.Namespace):  # ⑤j2：spawn_task_runner、supervise_tick 的 args
        return {key: _plain(item) for key, item in vars(value).items() if key != "func"}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (set, frozenset)):  # ⑤i1：worker_turns 的 kinds，同采样器的 plain
        return sorted(_plain(item) for item in value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def _flow_target(name):
    """内层函数换在哪里：kit_hub 调的是 pd.run_supervised、pd._running_attempts、tempfile.mkdtemp 与 decisions 的两样，其余是 kit_hub 自己的。"""
    return {"run_supervised": kit_hub.pd, "_running_attempts": kit_hub.pd, "pid_alive": kit_hub.pd, "find_bun": kit_hub.pd,
            "read_kernel_impl": kit_hub.pd, "ts_runner": kit_hub.pd, "mkdtemp": tempfile, "Session": codekit_decisions,
            "load_locked_batteries": codekit_decisions, "Engine.verify_delivery": kit_hub.Engine, "Engine.auto_jev": kit_hub.Engine,
            "Hub.deliver": kit_hub.Hub, "Popen": kit_hub.subprocess, "sleep": kit_hub.time, "Engine.step": kit_hub.Engine}.get(name, kit_hub)


def _flow_install(name, original, make):
    """换上 make(内层调用名, 原函数) 包出来的函数。decisions.Session 换成一个类：run_jev 建一个会话问一次，它的 ask 就是那一次
    内层调用（记成 ask，参数是设置、账本路径、题库、state、context），原来的类留到 ask 时才建。"""
    if name != "Session":
        return make(name, original)
    call = make("ask", lambda settings, ledger, battery, state, context: original(settings, ledger).ask(battery, state, context=context))

    class Session:
        def __init__(self, settings, record_path=None):
            self.settings, self.record_path = settings, record_path

        def ask(self, battery, state, context=None):
            return call(self.settings, self.record_path, battery, state, context)
    return Session


def _env_check(env, expected=None):
    """传给 run_supervised 的环境变量与当场的 kernel_pytest_env()（⑤h2 的 find_bun 比 kernel_env()）整份比：相同记 True，不同只记对不上的名字
    （值不进记录）。"""
    expected = kit_hub.kernel_pytest_env() if expected is None else expected
    if env == expected:
        return True
    return sorted(name for name in set(env) | set(expected) if env.get(name) != expected.get(name))


def _flow_msg_id():
    """⑤h2：钉住时刻的调用里 kit_hub.new_msg_id 的尾巴照次序编（000000 起），不用 os.urandom，同 TS 的 newMsgId 在 withPinnedClock 期间。"""
    count = [0]

    def new_msg_id(sender):
        value = "%s-%s-%06x" % (kit_hub.utc_compact(), kit_hub.SENDER_ALIAS.get(sender, sender), count[0])
        count[0] += 1
        return value
    return new_msg_id


def _flow_pin(micros):
    """kit_hub.utc_now、utc_compact 钉成同一个时刻（Unix 微秒数）。"""
    moment = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc) + datetime.timedelta(microseconds=micros)
    return (lambda: moment.strftime("%Y-%m-%dT%H:%M:%SZ")), (lambda: moment.strftime("%Y%m%dT%H%M%S%fZ"))


def _flow_listing(roots):
    """几棵树里的文件：{“树的序号/相对路径（正斜杠）”: sha256}。.git 不进，链接与联接不跟。"""
    listing = {}
    for index, root in enumerate(roots):
        for folder, dirs, files in os.walk(str(root)):
            dirs[:] = [name for name in dirs if name != ".git" and not os.path.islink(os.path.join(folder, name))
                       and not os.path.isjunction(os.path.join(folder, name))]
            for name in files:
                path = os.path.join(folder, name)
                if name == ".git" or os.path.islink(path):
                    continue
                rel = os.path.relpath(path, str(root)).replace(os.sep, "/")
                data = b""
                if os.path.getsize(path):  # 空文件不读：别的进程按字节区间锁着的锁文件读不出来（⑤f 的 add_worktree 等锁场景）
                    with open(path, "rb") as handle:
                        data = handle.read()
                listing["%d/%s" % (index, rel)] = hashlib.sha256(data).hexdigest()
    return listing


def _flow_path(roots, key):
    index, rel = key.split("/", 1)
    return os.path.join(str(roots[int(index)]), *rel.split("/"))


def _flow_changes(roots, before):
    """与 before 比：新建与改动的文件（原始字节，base64），删掉的文件。键按码点排序。"""
    after = _flow_listing(roots)
    write = {}
    for key in sorted(after):
        if before.get(key) != after[key]:
            with open(_flow_path(roots, key), "rb") as handle:
                write[key] = base64.b64encode(handle.read()).decode("ascii")
    return {"write": write, "delete": sorted(key for key in before if key not in after)}


#: ⑤h2：探针载入时的 Popen。supervisor 的用例把 subprocess.Popen 换成了假的，采样器自己记 git 状态时不能跟着用假的
_REAL_POPEN = subprocess.Popen
#: ⑤i1：探针载入时的 pid_alive。判断目录锁有没有活的持有者时用它（用例可能把 pd.pid_alive 换掉了）
_REAL_PID_ALIVE = kit_hub.pd.pid_alive
#: ⑤i2：DirLock 接管时问的 pid_alive 不录也不注入，两边都用真的（TS 的 DirLock 自己判断，⑤i 设计稿第 3 节）。这一次最外层调用里，
#: 用例换掉了 pid_alive、DirLock 又问过它时记下，那次调用不重放
_DIRLOCK_FAKE_PID = [False]
#: 探针载入时 DirLock.__enter__ 的代码：采样期间 __enter__ 外面套了一层（记拿过的锁），pid_alive 仍由原来的 __enter__ 调
_DIRLOCK_ENTER_CODE = kit_hub.DirLock.__enter__.__code__
#: ⑤i2：这一次最外层调用里拿过（DirLock）或探过（lock_alive）的目录锁。活锁的跳过只看这些（themistally-04 要的：跳过收窄到调用
#: 真的拿过或探过的那把锁；串行 hub 的 .runner 由 cmd_run 拿着，requeue_interrupted、step 都不碰它）
_TOUCHED_LOCKS = []


def _from_dirlock(frame):
    return frame.f_code is _DIRLOCK_ENTER_CODE


def _touched_locks(hub):
    """_TOUCHED_LOCKS 里在 hub 底下的，写成相对 hub.root 的路径（同 _live_locks）。"""
    root = Path(hub.root).resolve()
    found = set()
    for path in _TOUCHED_LOCKS:
        try:
            found.add(Path(path).resolve().relative_to(root).as_posix())
        except ValueError:
            pass
    return found


def _flow_git(roots):
    """用命令读出的 git 状态：每棵树的 HEAD 与 status -z 的原文，第一棵树里的全部引用。不是仓库的记 None。"""

    def run(args, cwd):
        with _REAL_POPEN(["git"] + args, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc:
            out, _err = proc.communicate()
        return out.decode("utf-8", "replace") if proc.returncode == 0 else None

    trees = []
    for root in roots:
        if not Path(root).is_dir():  # ⑤g2：rebase_candidate 的临时 worktree 用完就收掉了
            trees.append({"head": None, "status": None})
            continue
        head = run(["rev-parse", "HEAD"], root)
        trees.append({"head": head.strip() if head is not None else None,
                      "status": run(["status", "--porcelain=v1", "--untracked-files=all", "-z"], root)})
    # ⑤h2：hub 的仓库不在时（用例拿不存在的目录建 Hub）没有引用可读，与 TS 一样记 None
    refs = run(["for-each-ref", "--format=%(refname) %(objectname)"], roots[0]) if Path(roots[0]).is_dir() else None
    return {"trees": trees, "refs": refs}


def _flow_state(result, ts, roots, before, ledger, offset, after=None):
    """一次最外层调用之后要比的：交回值、调用之后的 ts、几棵树里的文件改动、账本新增的部分、git 状态。⑤i1 另比调用之后的字典与
    列表参数（after，_flow_after 挑出来的）。"""
    tail = ledger.read_bytes()[offset:] if ledger is not None and ledger.exists() else b""
    state = {"result": result, "ts": to_tagged(_plain(ts)), "files": _flow_changes(roots, before),
             "ledger": base64.b64encode(tail).decode("ascii"), "git": _flow_git(roots)}
    if after is not None:
        state["args_after"] = {key: to_tagged(_plain(item)) for key, item in after.items()}
    return state


def _flow_inner_call(name, args, kwargs):
    """内层调用要核对的参数：run_pd 比 argv 与 timeout（没给是 None），另外三个比仓库路径与调用那一刻的整份 ts。"""
    if name == "runner":  # ⑤i1：Engine 的回合（用例的 FakeRunner 一类）；参数照 TurnRunner.run 补全，输入目录记调用当时的文件
        given = dict(zip(RUNNER_ARGS, args), **kwargs)
        inputs = given.get("inputs")
        return {"fn": name, "agent": given["agent"], "session_key": given["session_key"], "workspace": str(given["workspace"]),
                "role_prompt": given["role_prompt"], "prompt": given["prompt"], "retry_of": given.get("retry_of"),
                "fresh": bool(given.get("fresh", False)), "inputs": None if inputs is None else str(inputs),
                "session_id": given.get("session_id"), "inputs_files": _inputs_files(inputs)}
    if name == "engine.handle_pass":  # ⑤i1：用例自己写的假 Engine
        return {"fn": name, "state": to_tagged(_plain(args[0])), "meta": to_tagged(_plain(args[1]))}
    if name == "engine.after_land":
        return {"fn": name, "main": args[0]}
    if name == "role_prompt":  # ⑤i1
        return {"fn": name, "agent": args[0]}
    if name in ("Engine.verify_delivery", "Engine.auto_jev"):  # ⑤i1：第一个参数是 Engine 本身，不比
        return {"fn": name, "args": to_tagged(_plain(list(args[1:])))}
    if name == "spawn_task_runner":  # ⑤j2：args 记成 Namespace 的各键
        return {"fn": name, "repo": str(args[0].repo), "task": args[1], "args": to_tagged(_plain(args[2]))}
    if name == "spawn_runner":
        return {"fn": name, "repo": str(args[0].repo), "argv": _argv_shown(args[1])}
    if name in ("kernel_dirty", "code_fingerprint", "kernel_changes"):  # 用例换上的多是不看参数的 lambda：没给 files 记 None
        files = args[0] if args else kwargs.get("files")  # 记成 paths：files 这个键是调用期间的文件改动
        return {"fn": name, "paths": None if files is None else [str(item) for item in files]}
    if name == "kernel_settled":
        return {"fn": name, "wait": args[0], "poll": args[1]}
    if name == "tasks_with_work":
        return {"fn": name, "repo": str(args[0].repo)}
    if name == "requeue_interrupted":
        given = dict(zip(("hub", "skip"), args), **kwargs)
        return {"fn": name, "repo": str(given["hub"].repo), "skip": sorted(given.get("skip") or [])}
    if name == "owner_sweep_tick":
        return {"fn": name, "repo": str(args[0].repo), "holder": to_tagged(_plain(args[1]))}
    if name == "Popen":  # 比命令行、当前目录与输出写进哪个日志（文件名）
        stdout = kwargs.get("stdout")
        return {"fn": name, "argv": _argv_shown(args[0]), "cwd": kwargs.get("cwd"), "log": Path(stdout.name).name if hasattr(stdout, "name") else None}
    if name == "sleep":
        return {"fn": name, "seconds": args[0]}
    if name == "Engine.step":  # 第一个参数是 Engine 本身：记它的仓库与 only_task
        return {"fn": name, "repo": str(args[0].hub.repo), "only_task": args[0].only_task}
    if name == "release_held":  # ⑤i2：只有 hub 一个参数
        return {"fn": name, "repo": str(args[0].repo)}
    if name in FLOW_INNER_I:  # ⑤i1：hub、ts 之外的参数也比
        return {"fn": name, "repo": str(args[0].repo), "ts": to_tagged(_plain(args[1])), "rest": to_tagged(_plain(list(args[2:])))}
    if name == "run_pd":
        timeout = args[2] if len(args) > 2 else kwargs.get("timeout")
        return {"fn": name, "argv": [str(item) for item in args[1]], "timeout": timeout}
    if name == "worktree_root":
        return {"fn": name, "repo": str(args[0])}
    if name == "mkdtemp":  # kit_hub 只用关键字传 prefix 与 dir
        return {"fn": name, "prefix": kwargs.get("prefix"), "dir": kwargs.get("dir")}
    if name == "load_locked_batteries":  # ⑤g2
        return {"fn": name, "path": str(args[0])}
    if name == "ask":  # ⑤g2：设置比 run_jev 改过的四样，账本比整个路径（重放在同一处）
        settings = args[0]
        return {"fn": name, "settings": {"mode": settings.mode, "configured_mode": settings.configured_mode, "reason": settings.reason,
                                         "points": list(settings.points)},
                "ledger": str(args[1]), "battery": to_tagged(_plain(args[2])), "state": to_tagged(_plain(args[3])), "context": to_tagged(_plain(args[4]))}
    if name == "_running_attempts":  # ⑤h1：比仓库根
        return {"fn": name, "repo": str(args[0].root)}
    if name == "pid_alive":  # ⑤h1
        return {"fn": name, "pid": args[0]}
    if name == "sweep_gates":  # ⑤h2：比在哪个目录跑
        return {"fn": name, "path": str(args[0])}
    if name == "find_bun":
        return {"fn": name, "env": _env_check(args[0] if args else kwargs.get("env"), kit_hub.kernel_env())}
    if name == "read_kernel_impl":  # 内核目录下的选择文件，不带参数
        return {"fn": name, "args": len(args) + len(kwargs)}
    if name == "ts_install_if_stale":  # 用例换掉它时只比仓库
        return {"fn": name, "repo": str(args[0].repo)}
    if name == "ts_runner":  # ts_install_if_stale 的 runner：stdout、stderr 是文件对象时记成 <temporary>，同一个记成 same
        given = dict(zip(("cmd", "cwd", "env", "stdout", "stderr", "timeout"), args), **kwargs)
        out, err = given["stdout"], given["stderr"]
        shape = lambda handle: "<temporary>" if hasattr(handle, "write") else str(handle)  # noqa: E731
        return {"fn": name, "argv": [str(item) for item in given["cmd"]], "cwd": str(given["cwd"]),
                "env": _env_check(given["env"], kit_hub.kernel_env()), "stdout": shape(out), "stderr": "same" if err is out else shape(err),
                "timeout": given.get("timeout")}
    if name == "run_supervised":  # 标准输出是独占新建的日志，标准错误同一个句柄；grace 与中断处理照缺省
        given = dict(zip(("cmd", "cwd", "env", "stdout", "stderr", "timeout", "grace", "on_spawn"), args), **kwargs)
        log = given["stdout"]
        return {"fn": name, "argv": [str(item) for item in given["cmd"]], "cwd": str(given["cwd"]), "env": _env_check(given["env"]),
                "stdout": [str(log.name), "create-new" if "x" in log.mode else log.mode], "stderr": "stdout" if given["stderr"] is log else "other",
                "timeout": given.get("timeout"), "grace": float(given.get("grace", 15.0)),
                # pd.run_supervised 没有这个参数，总会装中断处理；TS 的 handleSignals 缺省也是 true，两边比的就是这一点
                "handle_signals": True,
                "on_spawn": given.get("on_spawn") is not None}
    return {"fn": name, "repo": str(args[0].repo), "ts": to_tagged(_plain(args[1]))}


def _flow_recorder(name, fn, roots, inner, busy):
    """采样：用例换上的内层函数包一层，记参数、交回值或异常、调用期间的文件改动、调用之后的 ts。假函数里面再调名单上的不另录。"""
    def record(*args, **kwargs):
        if name == "pid_alive" and _from_dirlock(sys._getframe(1)):
            _DIRLOCK_FAKE_PID[0] = _DIRLOCK_FAKE_PID[0] or fn is not _REAL_PID_ALIVE
            return fn(*args, **kwargs)
        if busy[0]:
            return fn(*args, **kwargs)
        entry = _flow_inner_call(name, args, kwargs)
        before = _flow_listing(roots)
        busy[0] = True
        try:
            value = fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001  录下来照样抛
            entry["raise"] = [type(exc).__name__, str(exc)]
            if isinstance(exc, kit_hub.HubError):  # ⑤i1：HubError 一族带退出码，重放照真的类抛（前几片的样本里没有内层抛 HubError 的）
                entry["raise"].append(exc.code)
            raise
        else:
            if name in ("spawn_task_runner", "Popen") and value is not None:  # ⑤j2：交回的进程换成录制代理，它的 poll 另记
                value = _ProcRecorder(value)
            entry["value"] = to_tagged(_plain(value))
            if name == "mkdtemp" and all(Path(value).resolve() != Path(root).resolve() for root in roots):
                roots.append(Path(value))  # ⑤f：新建的 worktree 当新的一棵树（调用之前不在，重放前先删）
        finally:
            busy[0] = False
            entry["files"] = _flow_changes(roots, before)
            if name == "ts_runner":  # ⑤h2：输出记原始字节，读完把文件位置放回原处
                handle = dict(zip(("cmd", "cwd", "env", "stdout"), args), **kwargs).get("stdout")
                if hasattr(handle, "read"):
                    position = handle.tell()
                    handle.seek(0)
                    entry["output"] = base64.b64encode(handle.read()).decode("ascii")
                    handle.seek(position)
            if name in FLOW_TS_INNER:
                entry["ts_after"] = to_tagged(_plain(args[1]))
            inner.append(entry)
        return value
    return record


def _flow_injector(name, queue, roots):
    """重放：照记录注入内层调用。参数逐次核对，对不上或多调报 _InjectionMismatch；照记录写文件、删文件、原地改 ts，再交回或抛出。"""
    def inject(*args, **kwargs):
        if name == "pid_alive" and _from_dirlock(sys._getframe(1)):
            return _REAL_PID_ALIVE(*args, **kwargs)  # ⑤i2：同 _flow_recorder，DirLock 接管时用真的，不消耗记录
        got = _flow_inner_call(name, args, kwargs)
        expected = queue.pop(0) if queue else None
        if expected is None or any(expected.get(key) != value for key, value in got.items()):
            raise _InjectionMismatch(json.dumps({"got": got, "expected": expected and {key: expected.get(key) for key in got}}, ensure_ascii=False))
        if name == "mkdtemp":
            made = from_tagged(expected["value"])
            if os.path.normcase(os.path.dirname(made)) != os.path.normcase(str(kwargs.get("dir"))):
                raise _InjectionMismatch("mkdtemp 记下的目录不在 dir 下：%s" % made)
            os.mkdir(made)
        _flow_apply_files(expected, roots)
        if "output" in expected:  # ⑤h2：ts_runner 的输出原样写进 stdout
            dict(zip(("cmd", "cwd", "env", "stdout"), args), **kwargs)["stdout"].write(base64.b64decode(expected["output"]))
        if "ts_after" in expected:
            ts = args[1]
            ts.clear()
            ts.update(from_tagged(expected["ts_after"]))
        if "raise" in expected:
            kind, message = expected["raise"][:2]
            if len(expected["raise"]) == 3:  # ⑤i1：HubError 一族照真的类抛（LandBusy 也在 kit_hub 里），带退出码
                raise getattr(kit_hub, kind)(message, expected["raise"][2])
            # ⑤h1：调度器的 DispatchError 与内置的 OSError 一族照真的类抛（采样当时就是真的类，被调用的一方 except 才接得住）；
            # 别的照旧是同名的新类（KeyError 一类的 str() 会给文字再加一层引号）
            real = pi_dispatch.DispatchError if kind == "DispatchError" else getattr(builtins, kind, None)
            if not (isinstance(real, type) and (real is pi_dispatch.DispatchError or issubclass(real, OSError))):
                real = type(kind, (Exception,), {})
            raise real(message)
        value = _procs_of(from_tagged(expected["value"]), queue, roots)  # ⑤j2：记下的进程换成假进程
        return Path(value) if name in ("worktree_root", "ensure_worktree", "apply_candidate") else value
    return inject


def _flow_apply_files(expected, roots):
    """照记录写文件、删文件（内层调用与 ⑤j2 假进程的 poll 共用）。"""
    for key, data in expected["files"]["write"].items():
        path = _flow_path(roots, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(base64.b64decode(data))
    for key in expected["files"]["delete"]:
        os.remove(_flow_path(roots, key))


def _flow_peek(roots, rel):
    """⑤i2：调用当时某个文件的内容（不是文件记 None）：剧本一项的 peek（C06），与投信那一刻的 peek_deliver（T06）。"""
    path = _flow_path(roots, rel)
    return open(path, "rb").read().decode("utf-8") if os.path.isfile(path) else None


def _flow_scripted(name, items, calls, roots):
    """⑤i1 手写场景的剧本（request["scripted"]）：照剧本按次交回、不核对参数，每次调用的参数照 _flow_inner_call 记进 calls，随结果交回、
    三边互相比。剧本的一项：value（带标签），或 raise（[类名, 文字, 退出码]，HubError 一族）；files 照 _flow_injector 写进几棵树；listing 是一个目录，
    调用当时它下面的文件名记进这次调用（L01：合入后回归的窗口标记只在窗口开着时在）；peek 是一个文件，调用当时它的内容记进这次调用。"""
    queue = list(items)

    def scripted(*args, **kwargs):
        calls.append(_flow_inner_call(name, args, kwargs))
        if not queue:
            raise RuntimeError("剧本用完了：%s" % name)
        item = queue.pop(0)
        for key, data in ((item.get("files") or {}).get("write") or {}).items():
            path = _flow_path(roots, key)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(base64.b64decode(data))
        if "listing" in item:  # 调用当时某个目录下的文件名（按码点排；不是目录记 None），记进这次调用
            folder = _flow_path(roots, item["listing"])
            calls[-1]["listing"] = sorted(os.listdir(folder)) if os.path.isdir(folder) else None
        if "peek" in item:  # ⑤i2 C06：协调人回合进行中的在办标记
            calls[-1]["peek"] = _flow_peek(roots, item["peek"])
        for path, data in item.get("ts_set") or []:  # ⑤i2 跑到静止：照剧本改 ts（键的路径加新值，带标签），两边只照着套用
            target = args[1]  # Engine 的方法第一个参数是 Engine 本身，ts 也在第二个
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = from_tagged(data)
        if "raise" in item:
            kind, message, code = item["raise"]
            raise getattr(kit_hub, kind)(message, code)
        value = from_tagged(item["value"])
        return Path(value) if name in ("worktree_root", "ensure_worktree", "apply_candidate") else value
    return scripted


def _flow_runner_by_agent(scripted, calls, roots):
    """⑤i2 跑到静止：回合剧本按 agent 分开（"runner:<agent>"），各自照次交回；记下的调用同 runner。剧本里没有这个 agent 时报 RuntimeError
    （step 接住，写阻塞信给站主），两边一样。"""
    queues = {key.split(":", 1)[1]: _flow_scripted("runner", items, calls, roots) for key, items in scripted.items() if key.startswith("runner:")}

    def run(*args, **kwargs):
        agent = dict(zip(RUNNER_ARGS, args), **kwargs)["agent"]
        if agent not in queues:
            raise RuntimeError("剧本里没有 %s 的回合" % agent)
        return queues[agent](*args, **kwargs)
    return run


def _jev_session(endpoint, key):
    """⑤g2 手写场景的真会话：run_jev 写死官方端点，传输层核对恰好是官方地址之后，一律改发本机的假端点（真的 HTTP），官方地址不交给
    真的传输层；环境只给假 key（非空，不去问凭据库）。"""
    if not endpoint.startswith("http://127.0.0.1:"):
        raise RuntimeError("假端点只能在本机")
    real = codekit_decisions.Session
    official = codekit_decisions.DEFAULT_BASE_URL + codekit_decisions.ENDPOINT_PATH

    def transport(body, headers, timeout, url):
        if url != official:
            raise RuntimeError("决策请求没有发往官方端点")
        return codekit_decisions.http_transport(body, headers, timeout, endpoint + codekit_decisions.ENDPOINT_PATH)
    return lambda settings, path: real(settings, path, transport=transport, environ={settings.api_key_env: key})


def _remove_fresh(fresh, inner):
    """⑤f：调用当时还不在的树（mkdtemp 建的 worktree），重放前先删掉；只删记下的 mkdtemp 的 dir 下的目录。"""
    dirs = {os.path.normcase(str(entry.get("dir"))) for entry in inner if entry.get("fn") == "mkdtemp"}
    for root in fresh:
        if os.path.normcase(os.path.dirname(root)) not in dirs:
            raise RuntimeError("新建的树不在 mkdtemp 的 dir 下：%s" % root)
        if os.path.exists(root):
            shutil.rmtree(root, onexc=lambda func, item, _exc: (os.chmod(item, stat.S_IWRITE), func(item)))


def _flow_roots(hub, workspace):
    roots = [Path(hub.repo)] if hub is not None else []  # ⑤f：hub 可以是 None（用不到它就交回的调用）
    if workspace is not None and all(Path(workspace).resolve() != root.resolve() for root in roots):
        roots.append(Path(workspace))
    return roots


def _flow_call(fn, hub, args, rest, queue, roots, request, runner=None):
    """⑤i1：重放时怎么调，交回（调用，参数绑定）；绑定用来取 ts 与调用之后的字典、列表参数。别的流程函数照旧，绑定是 None。
    - Engine 的方法与 land 先建一个 Engine（参数前两个是仓库与 only_task），runner 照记录注入；land 收到的当时是用例自己写的假 Engine
      （fake_engine）时，它的 handle_pass、after_land 照记录注入；
    - state 当时是 load_state 读出来的（state_seen 不是 None）时照样建 HubState，save_state 才照三方合并写；
    - ts 当时是 state 里的一项（ts_alias）时接回同一个对象。"""
    import inspect

    if not _flow_i(fn):
        return (lambda: getattr(kit_hub, fn)(hub, *args[1:2], *rest)), None
    if fn in COMMANDS:  # ⑤j1：站主命令，参数是仓库与 Namespace 的各键；⑤j2 的 cmd_run、cmd_owner_sweep、cmd_exclusive 同
        namespace = argparse.Namespace(**args[1])
        return (lambda: getattr(kit_hub, fn)(namespace)), None
    if fn in FLOW_J2:  # ⑤j2：第一个参数是 hub；参数名是 args 的照建回 Namespace，记下的进程照建假进程
        target = getattr(kit_hub, fn)
        params = list(inspect.signature(target).parameters)
        given = [hub] + [_procs_of(item, queue, roots) for item in args[1:]]
        given = [argparse.Namespace(**item) if params[at] == "args" and isinstance(item, dict) else item for at, item in enumerate(given)]
        bound = inspect.signature(target).bind(*given)
        return (lambda: target(*bound.args, **bound.kwargs)), bound
    runner = runner or _flow_injector("runner", queue, roots)  # 手写场景给了剧本就照剧本
    if fn in FLOW_I_FUNCTIONS and fn != "land":  # release_dependents 与 ⑤i2 的续接一族：模块函数，第一个参数是 hub
        target, given = getattr(kit_hub, fn), [hub] + list(args[1:])
    elif fn == "land":
        if request.get("fake_engine"):
            engine = _EngineProxy(_flow_injector("engine.handle_pass", queue, roots), _flow_injector("engine.after_land", queue, roots))
        else:
            engine = kit_hub.Engine(hub, runner=_RunnerProxy(runner), only_task=args[1])
        target, given = kit_hub.land, [hub, engine, Path(args[2]), args[3]]
    else:
        engine = kit_hub.Engine(hub, runner=_RunnerProxy(runner), only_task=args[1])
        target, given = getattr(kit_hub.Engine, fn.split(".", 1)[1]), [engine] + list(args[2:])
        if fn in FLOW_ENGINE_PATH_LISTS:  # 一组路径（paths）的参数位置，前面多一个 Engine
            given[FLOW_ENGINE_PATH_LISTS[fn] + 1] = [Path(item) for item in given[FLOW_ENGINE_PATH_LISTS[fn] + 1]]
        for index in FLOW_ENGINE_PATHS.get(fn, ()):  # 方法参数的位置，前面多一个 Engine
            given[index + 1] = None if given[index + 1] is None else Path(given[index + 1])
    bound = inspect.signature(target).bind(*given)
    if request.get("state_seen") is not None:
        state = kit_hub.HubState(bound.arguments["state"])
        state.seen = request["state_seen"]
        bound.arguments["state"] = state
    if request.get("ts_alias") is not None:
        bound.arguments["ts"] = bound.arguments["state"]["tasks"][request["ts_alias"]]
    return (lambda: target(*bound.args, **bound.kwargs)), bound


def op_hub_popen(request):
    """⑤j2：照 kit_hub 起长命子进程的写法起一个（stdin 接空设备；给了 log 就 open("ab") 追加、stderr 并进 stdout，没给就继承本进程的），
    每 0.05 秒 poll 一次到它退出（最多 timeout 秒，到了就结束它），交回 poll 拿到的退出码、returncode、pid 是不是正数与日志的字节。
    对照 TS 的 runner.ts 真 popen（Windows 上是 CreateProcessW）。
    ctrl_c_default：起之前先 SetConsoleCtrlHandler(NULL, FALSE) 恢复缺省的 Ctrl+C 处理、起完恢复成 TRUE（探针原来就忽略 Ctrl+C）。子进程继承
    这个属性，另起进程组的又会被隐式设成忽略，读它 PEB 里的 ConsoleFlags 就分得出有没有另起进程组（themistally-04 提的，不发任何信号）。
    inherit：起之前本进程另开这个文件的一个可继承句柄，命令行里的 <handle> 换成它的数值，起完关掉；Popen 只让子进程继承三个标准句柄
    （close_fds 时经 PROC_THREAD_ATTRIBUTE_HANDLE_LIST），拿不到它（N01 的变异让 CreateProcessW 不认属性表、全继承）。"""
    argv, cwd, log = request["argv"], request.get("cwd"), request.get("log")
    reset = bool(request.get("ctrl_c_default"))
    extra = os.open(request["inherit"], os.O_WRONLY | os.O_APPEND | os.O_CREAT) if request.get("inherit") else None
    if extra is not None:
        import msvcrt
        os.set_handle_inheritable(msvcrt.get_osfhandle(extra), True)
        argv = [str(msvcrt.get_osfhandle(extra)) if item == "<handle>" else item for item in argv]
    if reset:
        ctypes.windll.kernel32.SetConsoleCtrlHandler(None, False)
    try:
        if log is None:
            proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL)
        else:
            with open(log, "ab") as handle:
                proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT)
    except OSError as exc:
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    finally:
        if reset:
            ctypes.windll.kernel32.SetConsoleCtrlHandler(None, True)
        if extra is not None:
            os.close(extra)
    deadline = time.monotonic() + request.get("timeout", 30)
    code = proc.poll()
    while code is None and time.monotonic() < deadline:
        time.sleep(0.05)
        code = proc.poll()
    if code is None:
        proc.kill()
    return {"ok": True, "value": {"code": code, "returncode": proc.returncode if code is not None else None, "pid": proc.pid > 0,
                                  "log": None if log is None else base64.b64encode(Path(log).read_bytes()).decode("ascii")}}


def op_hub_contract_flow(request):
    """第 ⑤e2b 片：合同与战前门禁里改状态的六个函数，照调用当时重放。先原地放回快照（带 .git），钉住时刻与提交作者、日期，
    用例当时换掉的内层函数照记录注入（request["inner"]，逐次核对；用完了还有剩的报 INJECTION_LEFTOVER），交回 _flow_state。
    ⑤i1：Engine 的方法与 land 建一个 Engine，它的 runner 照记录注入；名册的改动照样本设上（roster、delivery_sha256）；⑤i 的流程函数
    time.time 也钉住；另比调用之后的字典与列表参数。"""
    for item in request.get("restores") or []:
        _restore_tree(item["from"], item["to"], item.get("links", []), with_git=bool(item.get("git")))
    _PROC["replay"] = {}  # ⑤j2：这一次重放的假进程（编号照样本）
    for path, data in (request.get("inputs") or {}).items():  # ⑤j1：站主命令的 --file、--brief 照调用当时的字节写回
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(base64.b64decode(data))
    fn = request["fn"]
    args = [from_tagged(item) for item in request["args"]]
    hub = kit_hub.Hub(Path(args[0])) if args[0] is not None else None
    for path in request.get("absent") or []:  # ⑤j1：调用当时不在的仓库外目录，重放前删掉；只删用例临时目录（仓库的上一层）下的
        if not Path(path).resolve().is_relative_to(Path(args[0]).resolve().parent):
            raise RuntimeError("调用当时不在的目录不在用例的临时目录下：%s" % path)
        if Path(path).exists():
            shutil.rmtree(path, onexc=lambda func, item, _exc: (os.chmod(item, stat.S_IWRITE), func(item)))
    ts = None if fn in FLOW_NO_TS or _flow_i(fn) else args[1]  # ⑤h2；⑤i1 的 ts 从参数绑定里取
    rest = [Path(item) if index in FLOW_PATH_ARGS.get(fn, ()) else item for index, item in enumerate(args[2:], start=2)]
    roots = [Path(root) for root in request["roots"]]
    _remove_fresh(request.get("fresh") or [], request.get("inner") or [])
    before = _flow_listing(roots)
    ledger = hub.ledger() if hub is not None else None
    offset = ledger.stat().st_size if ledger is not None and ledger.exists() else 0
    queue = list(request.get("inner") or [])
    replaced = list(request.get("replaced") or [])
    given_env = dict(FLOW_GIT_ENV, **(request.get("env") or {}))
    saved_env = {name: os.environ.get(name) for name in given_env}
    saved = {name: getattr(_flow_target(name), _flow_attr(name)) for name in replaced + ["utc_now", "utc_compact", "new_msg_id"]}
    saved_wait, saved_session, saved_time = kit_hub.EXEC_LAND_WAIT_SECONDS, codekit_decisions.Session, time.time
    # ⑤h2：后台回归的三个时限各有各的键，同 hub_probe.ts；land_wait 照旧只管 EXEC_LAND_WAIT_SECONDS
    waits = {"land_lock_wait": "LAND_WAIT_SECONDS", "sweep_wait": "SWEEP_WAIT_SECONDS", "sweep_seconds": "SWEEP_SECONDS"}
    saved_waits = {name: getattr(kit_hub, name) for name in waits.values()}
    for key, name in waits.items():
        if request.get(key) is not None:
            setattr(kit_hub, name, request[key])
    # ⑤i1：名册与交差文件的哈希照采样当时的改动设上，调用完还原（同 op_hub_turn）
    tables = [(kit_hub.ROSTER, request.get("roster") or {}), (kit_hub.DELIVERY_SHA256, request.get("delivery_sha256") or {})]
    saved_tables = [(table, {name: table.get(name, None) for name in given}, set(given) - set(table)) for table, given in tables]
    for table, given in tables:
        table.update(given)
    os.environ.update(given_env)
    kit_hub.utc_now, kit_hub.utc_compact = _flow_pin(request["pin"])
    kit_hub.new_msg_id = _flow_msg_id()
    if _flow_i(fn):  # ⑤i1：int(time.time()) 落在钉住的那一秒，同采样器
        time.time = lambda: request["pin"] / 1_000_000
    if request.get("land_wait") is not None:  # ⑤g2 手写场景：落地锁由另一个进程拿着，等锁的时限设短
        kit_hub.EXEC_LAND_WAIT_SECONDS = request["land_wait"]
    # ⑤i1：用例当时改过的 kit_hub 常量照设（INPUT_FILE_LIMIT 一类），调用完还原；原值是 Path 的转回 Path
    given_constants = request.get("constants") or {}
    saved_constants = {name: getattr(kit_hub, name) for name in given_constants}
    for name, item in given_constants.items():
        setattr(kit_hub, name, Path(item) if isinstance(saved_constants[name], Path) else item)
    if request.get("jev"):
        codekit_decisions.Session = _jev_session(request["jev"]["endpoint"], request["jev"]["key"])
    for name in replaced:
        setattr(_flow_target(name), _flow_attr(name), _flow_install(name, saved[name], lambda inner, _fn: _flow_injector(inner, queue, roots)))
    # ⑤i1 手写场景：照剧本交回的内层函数（runner 另由 _flow_call 用），调用完还原
    scripted, script_calls = request.get("scripted") or {}, []
    for name, items in scripted.items():
        if name != "runner" and not name.startswith("runner:"):
            saved.setdefault(name, getattr(_flow_target(name), _flow_attr(name)))
            setattr(_flow_target(name), _flow_attr(name), _flow_scripted(name, items, script_calls, roots))
    runner = _flow_scripted("runner", scripted["runner"], script_calls, roots) if "runner" in scripted else None
    if runner is None and any(name.startswith("runner:") for name in scripted):
        runner = _flow_runner_by_agent(scripted, script_calls, roots)
    peeks = []  # ⑤i2 T06：每次投信那一刻 peek_deliver 那个文件的内容，随结果交回（代办的在办标记只在投信前后那一刻在）
    if request.get("peek_deliver"):
        real_deliver = saved.setdefault("Hub.deliver", kit_hub.Hub.deliver)
        kit_hub.Hub.deliver = lambda self, *more, **kw: (peeks.append(_flow_peek(roots, request["peek_deliver"])), real_deliver(self, *more, **kw))[1]
    call, bound = _flow_call(fn, hub, args, rest, queue, roots, request, runner)
    clock_saved = {}  # ⑤j2 跑到静止：真的 cmd_run，时钟只靠 sleep 往后挪（_sleep_clock）；调用完最先还原，再还原上面钉住的那几样
    if request.get("clock") == "sleep":
        for (owner, attr), item in _sleep_clock(request["pin"], runner).items():
            clock_saved[(owner, attr)] = getattr(owner, attr)
            setattr(owner, attr, item)
    streams, captured = (sys.stdin, sys.stdout, sys.stderr), None
    saved_fds = None
    if fn in STREAMS:  # ⑤j1：站主命令读采样时读到的标准输入，stdout、stderr 截下来随结果交回；⑤j2 同
        sys.stdin, sys.stdout, sys.stderr = io.StringIO(request.get("stdin") or ""), io.StringIO(), io.StringIO()
        # ⑤j2：子进程不经 sys.stdout、直接写文件描述符 1、2（exclusive 起的 git status --short），探针的 stdout 是交回结果的通道：调用期间
        # 1、2 接到空设备，同采样器跑用例时
        streams[1].flush()
        saved_fds = [os.dup(1), os.dup(2), os.open(os.devnull, os.O_WRONLY)]
        os.dup2(saved_fds[2], 1)
        os.dup2(saved_fds[2], 2)
    try:
        value = call()
        result = json.loads(_recorded_value(fn, value))
        if queue:
            result = {"ok": False, "error": "INJECTION_LEFTOVER", "left": [entry["fn"] for entry in queue]}
    except _InjectionMismatch as exc:
        result = {"ok": False, "error": "INJECTION_MISMATCH", "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001  与当时的结果一样记类型与文字（HubError 另记退出码）
        result = json.loads(_recorded_error(exc))
    finally:
        for (owner, attr), item in clock_saved.items():
            setattr(owner, attr, item)
        if fn in STREAMS:
            captured = (sys.stdout.getvalue(), sys.stderr.getvalue())
            sys.stdin, sys.stdout, sys.stderr = streams
        if saved_fds is not None:
            os.dup2(saved_fds[0], 1)
            os.dup2(saved_fds[1], 2)
            for fd in saved_fds:
                os.close(fd)
        for name, item in saved.items():
            setattr(_flow_target(name), _flow_attr(name), item)
        kit_hub.EXEC_LAND_WAIT_SECONDS, codekit_decisions.Session, time.time = saved_wait, saved_session, saved_time
        for name, item in saved_constants.items():
            setattr(kit_hub, name, item)
        for name, item in saved_waits.items():
            setattr(kit_hub, name, item)
        for table, before_table, added in saved_tables:
            table.update({name: item for name, item in before_table.items() if name not in added})
            for name in added:
                table.pop(name, None)
        for name, item in saved_env.items():
            if item is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = item
    after = None if bound is None else _flow_after(bound)
    shown_ts = ts if bound is None else bound.arguments.get("ts")
    state = _flow_state(result, shown_ts, roots, before, ledger, offset, after)
    if captured is not None:
        state["stdout"], state["stderr"] = captured
    if fn in FLOW_J2:  # ⑤j2：探针自己的 pid，契约归一化时只换等于它的
        state["self_pid"] = os.getpid()
    if scripted:
        state["scripted_calls"] = script_calls
    if peeks:
        state["deliver_peeks"] = peeks
    return {"ok": True, "value": state}


def _instances(test, fn):
    """⑤i1：带 parametrize 的用例照 pytest 的次序展开成“名[i]”，每组交回（名字, 参数）。只认一层、普通的 argvalues：叠了几层、
    带 indirect 一类的参数、或者有 pytest.param，都直接报错，不悄悄跳过（themistally-04 定）。"""
    from _pytest.mark.structures import ParameterSet

    marks = [mark for mark in getattr(fn, "pytestmark", []) if mark.name == "parametrize"]
    if not marks:
        return [(test, {})]
    if len(marks) > 1 or set(marks[0].kwargs) - {"ids"} or len(marks[0].args) != 2:
        raise RuntimeError("%s：叠了几层 parametrize，或者带 %s，采样器不认" % (test, sorted(marks[0].kwargs)))
    names, values = marks[0].args
    names = [item.strip() for item in names.split(",")] if isinstance(names, str) else list(names)
    found = []
    for index, value in enumerate(values):
        if isinstance(value, ParameterSet):
            raise RuntimeError("%s：第 %d 组是 pytest.param，采样器不认" % (test, index))
        found.append(("%s[%d]" % (test, index), dict(zip(names, value)) if len(names) > 1 else {names[0]: value}))
    return found


def op_hub_audit_samples(request):
    """第 ⑤c、⑤d 片：跑 tests/test_kit_hub.py 里 request["tests"] 列出的用例，记下它们对 request["functions"] 的每一次顶层调用
    （内层的不记；参数照签名补全默认值，Path 换成字符串，Hub 换成仓库路径，元组换成列表）与当时的结果（_recorded_value），
    对照测试拿去交给三边重放，并先核对 Python 重放与当时的结果：重放读的是用例跑完时的文件、用例改过的全局已经撤销，
    对不上的那几条不算重放过这个场景。样例只有 pytest 这一个来源。tmp_path 给 request["tmp"] 下的新目录，monkeypatch 用 pytest
    的 MonkeyPatch，跑完撤销；pytest 每条用例先搭的 autouse 夹具照样先搭，两个文件里的 autouse 夹具与已知的不一样就不采。"""
    import copy
    import inspect
    import tempfile
    from _pytest.monkeypatch import MonkeyPatch

    sys.path.insert(0, str(ROOT / "tests"))
    import test_kit_hub as cases  # noqa: E402

    # 这里手搭的 autouse 夹具只有这两个：两个文件里再加了，采样会悄悄少搭一个（第 ⑤d 片撞过：Engine 的用例因此走了另一条路）
    found = sorted(_autouse_fixtures(ROOT / "tests" / "test_kit_hub.py") + _autouse_fixtures(ROOT / "tests" / "conftest.py"))
    if found != ["pi_knows_every_flag", "python_kernel_impl"]:
        return {"ok": False, "error": "AUTOUSE_CHANGED", "names": found}

    def plain(value):
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, kit_hub.Hub):  # 第 ⑤d 片：Hub 记成仓库路径，重放时由它再建
            return str(value.repo)
        if isinstance(value, (_ProcRecorder, _ProcReplay)):  # ⑤j2：进程记成编号与 pid
            return _proc_shown(value)
        if isinstance(value, argparse.Namespace):  # ⑤j1：站主命令与 configured_parallel 的参数记成各键（func 是函数，不记）
            return {key: plain(item) for key, item in vars(value).items() if key != "func"}
        if isinstance(value, (list, tuple)):
            return [plain(item) for item in value]
        if isinstance(value, (set, frozenset)):  # ⑤i1：worker_turns 的 kinds；它只拿来判断成员，记成排好序的列表
            return sorted(plain(item) for item in value)
        if isinstance(value, dict):
            return {key: plain(item) for key, item in value.items()}
        return value

    calls, depth, current = [], [0], [None]
    originals = {name: getattr(*_owner_attr(name)) for name in request["functions"] if name not in ("TurnRunner.run", "stage_inputs")}
    pristine = [(kit_hub.ROSTER, copy.deepcopy(kit_hub.ROSTER)), (kit_hub.DELIVERY_SHA256, dict(kit_hub.DELIVERY_SHA256))]
    # ⑤i1：kit_hub 大写常量在采样开始时的对象；⑤i 的调用记下当时被用例换掉的那些（名册与交差哈希另由 overrides 记）
    constants = {name: getattr(kit_hub, name) for name in dir(kit_hub) if name.isupper() and name not in ("ROSTER", "DELIVERY_SHA256")}

    def overrides():
        """用例此刻改过的名册岗位与交差文件哈希（与采样开始时比，对应 monkeypatch.setitem）：重放时两边设同一组。删掉的键重放设不回来，直接报错。"""
        changed = []
        for table, before in pristine:
            if set(before) - set(table):
                raise RuntimeError("用例删掉了 %s" % sorted(set(before) - set(table)))
            changed.append({name: plain(value) for name, value in table.items() if name not in before or before[name] != value})
        return json.dumps({"roster": changed[0], "delivery_sha256": changed[1]}, ensure_ascii=False)

    snapshot_functions = set(request.get("snapshot_functions") or [])

    def call_snapshots(bound, hub=None, extra=(), skip=()):
        """⑤e2a：调用当时的快照（带 .git），重放前原地放回（hub.contract 的 restores）。带 hub 的函数存仓库；workspace_status 存那个目录，
        它是仓库外的 worktree（.git 是指针文件）时连主仓库一起存（worktree 的元数据在主仓库的 .git/worktrees 下）。
        ⑤i1：Engine 的方法没有 hub 参数，由调用方给；extra 是状态里记着的仓库外的目录；skip 是不存的参数名。"""
        roots = []
        hub = bound.arguments.get("hub") if hub is None else hub
        # ⑤h2：用例拿不存在的仓库建 Hub（看 ts/ 不在时不装）：没有可存的
        if isinstance(hub, kit_hub.Hub) and Path(hub.repo).exists():
            roots.append(Path(hub.repo))
        # ⑤e2b：门禁草稿 worktree 叫 workspace；⑤g1：returned_blockers、rework_section 的上一轮 attempt 叫 previous；
        # ⑤h1：on_branch 在落地预演的临时 worktree 里看时叫 where（调用之后就收掉了）
        given = {key: bound.arguments.get(key) for key in ("path", "workspace", "run_dir", "previous", "where") if key not in skip}
        ts = bound.arguments.get("ts")
        if given.get("run_dir") is None and isinstance(ts, dict) and isinstance(ts.get("exec"), dict) and ts["exec"].get("run_dir"):
            given["run_dir"] = ts["exec"]["run_dir"]  # ⑤f：读 meta.json、scope.json、candidate.patch 的那个 attempt 目录
        for key, value in list(given.items()) + [("extra", path) for path in extra]:
            if value is None or (key in ("run_dir", "previous") and not Path(value).is_dir()):
                continue
            roots.append(Path(value))
            pointer = roots[-1] / ".git"
            if pointer.is_file():
                roots.append(Path(pointer.read_text(encoding="utf-8").split(":", 1)[1].strip()).parent.parent.parent)
        unique = []
        for root in roots:  # 指针指回的主仓库就是 hub 的仓库时只存一份
            if all(root.resolve() != seen.resolve() for seen in unique):
                unique.append(root)
        roots = unique
        restores = []
        for root in roots:
            snapshot = Path(request["tmp"]).resolve() / "call-snapshots" / str(len(calls)) / str(len(restores))
            links = _snapshot_tree(root, snapshot, with_git=True)
            restores.append({"from": str(snapshot), "to": str(root), "links": links, "git": True})
        return restores

    flow_functions = set(request.get("flow_functions") or [])
    installed = {}
    land_wait = kit_hub.EXEC_LAND_WAIT_SECONDS

    def flow_recorder(name, fn):
        """⑤e2b：改状态的函数在最外层被调时照调用当时记：快照（带 .git）、钉住的时刻、用例当时换掉的内层函数的每一次调用、
        调用之后的 _flow_state（交回值、ts、文件、账本、git 状态）。时刻与提交作者、日期只在这一次调用期间钉住。
        ⑤i1：Engine 的方法（"Engine.<方法名>"）与 land、release_dependents 另外记这几样（⑤i 设计稿第 3、4 节）：
        - 参数里的 Engine 记成仓库与 only_task，它的 runner 在调用期间换成录制包装（内层名 runner）；
        - 状态里记着的仓库外的 worktree 与 attempt 目录也存快照、也比文件；
        - 名册的改动（overrides）随样本带上；time.time 也钉住；调用之后的字典与列表参数一起比；
        - state 参数与调用当时的 state.json 是否相同当场核对（state_differs）；ts 是 state 里的哪一项（ts_alias），重放时接回去；
        - 目录锁有活的持有者时标 skip（重放时持有者已经不在）。"""
        signature = inspect.signature(fn)

        def wrapper(*args, **kwargs):
            if depth[0] > 0:
                depth[0] += 1
                try:
                    return fn(*args, **kwargs)
                finally:
                    depth[0] -= 1
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            flow_i = _flow_i(name)
            runner = bound.arguments.get("runner") if name == "ts_install_if_stale" else None
            if runner is not None:  # ⑤h2：给了 runner 时换成录制包装（内层名 ts_runner），样本里记成 None
                bound.arguments["runner"] = None
            engine = bound.arguments.get("self") if name.startswith("Engine.") else bound.arguments.get("engine") if name == "land" else None
            command, streamed = name in COMMANDS, name in STREAMS
            # ⑤j2：字典参数里用例自己造的进程对象（supervise_tick 的 children、owner_sweep_tick 的 holder）先换成录制代理，调用之后换回
            wrapped = []
            for item in bound.arguments.values() if name in FLOW_J2 else ():
                for key, value in list(item.items()) if isinstance(item, dict) else ():
                    if hasattr(value, "poll") and not isinstance(value, _ProcRecorder):
                        item[key] = _ProcRecorder(value)
                        wrapped.append((item, key, value, item[key]))
            if command:  # ⑤j1：站主命令自己照 args.repo 找仓库（同 find_repo，这里不经它的记录器）
                hub = kit_hub.Hub(kit_hub.pd.Repo.discover(bound.arguments["args"].repo).root)
            else:
                hub = engine.hub if name.startswith("Engine.") else bound.arguments["hub"]
            fake = name == "land" and not isinstance(engine, kit_hub.Engine)  # 4001：用例自己写的假 Engine
            if command:
                namespace = bound.arguments["args"]
                entry = {"test": current[0], "fn": name, "args": [str(hub.repo), plain(namespace)]}
                # --file、--brief 指向的文件照调用当时的字节记下：用例之后可能改写同一个文件（6579 先写 2001 字、再写短的），重放时先写回
                given = [str(getattr(namespace, key)) for key in ("file", "brief") if getattr(namespace, key, None) not in (None, "-")]
                relative = [path for path in given if not Path(path).is_absolute()]
                if relative:  # 重放时照这个路径写回：相对路径会写进探针的当前目录（themistally-04 要的保护）
                    raise RuntimeError("--file、--brief 要是绝对路径：%s" % "、".join(relative))
                entry["inputs"] = {path: base64.b64encode(Path(path).read_bytes()).decode("ascii") for path in given if Path(path).is_file()}
            elif engine is not None:
                given = [plain(item) for key, item in bound.arguments.items() if key not in ("self", "hub", "engine")]
                entry = {"test": current[0], "fn": name, "args": [str(hub.repo), None if fake else engine.only_task] + given}
                if name == "land":
                    entry["fake_engine"] = fake
            else:
                entry = {"test": current[0], "fn": name, "args": [plain(item) for item in bound.arguments.values()]}
            calls.append(entry)
            extra = _state_dirs(hub, bound.arguments.get("ts"), bound.arguments.get("state")) if flow_i else []
            if command:  # ⑤j1：仓库外的 attempt worktree 与阶段 worktree，在的随快照存，不在的记下、重放前删掉
                present, absent = _outside_dirs(hub)
                extra += [path for path in present if all(path.resolve() != seen.resolve() for seen in extra)]
                entry["absent"] = [str(path) for path in absent]
            roots = _flow_roots(hub, bound.arguments.get("workspace"))
            roots += [path for path in extra if all(path.resolve() != root.resolve() for root in roots)]
            entry["restores"] = json.dumps(call_snapshots(bound, hub, extra), ensure_ascii=False)
            known = len(roots)
            entry["pin"] = time.time_ns() // 1000
            names = FLOW_INNER + (FLOW_INNER_I if flow_i else ()) + (FLOW_INNER_J2 if name in FLOW_J2 else ())
            entry["replaced"] = [item for item in names if getattr(_flow_target(item), _flow_attr(item)) is not installed[item]] + list(FLOW_ALWAYS.get(name, ()))
            entry["replaced"] += ["ts_runner"] if runner is not None else []
            if flow_i:
                entry["replaced"] = list(dict.fromkeys(entry["replaced"] + list(FLOW_ALWAYS_I)))
            if name == "run_exec" and kit_hub.EXEC_LAND_WAIT_SECONDS != land_wait:
                # ⑤g2：用例自己拿着落地锁、等锁时限改短了（落地锁被占的那一条）。重放时拿锁的已经不在，不重放，契约钉住只跳这一条
                entry["skip"] = "EXEC_LAND_WAIT_SECONDS=%r" % (kit_hub.EXEC_LAND_WAIT_SECONDS,)
            if name in FLOW_J2:  # ⑤j2：这个进程自己的 pid（runner.started 一类写的），契约只把等于它的换成占位
                entry["self_pid"] = os.getpid()
            if name == "spawn_runner" and "Popen" not in entry["replaced"]:
                # ⑤j2：真起一个新 hub 子进程（1097），子进程号每次不同、写标记的时刻也不定，不重放（由手写场景覆盖，⑤j 设计稿第 4 节）
                entry["skip"] = "起真子进程"
            # ⑤i1：目录锁有活的持有者时，重放时持有者已经不在，接管与否两边不同，不重放（由手写场景覆盖）。⑤i2：只算这次调用拿过或
            # 探过的锁，调用之后再定
            held = _live_locks(hub) if flow_i and Path(hub.repo).exists() else []
            if flow_i:
                entry["overrides"] = overrides()
                entry["constants"] = {key: plain(getattr(kit_hub, key)) for key, item in constants.items() if getattr(kit_hub, key) is not item}
                state, ts_given = bound.arguments.get("state"), bound.arguments.get("ts")
                if isinstance(state, dict):  # 传进来的 state 与调用当时的 state.json 是否相同，当场核对（themistally-04 要的）
                    entry["state_differs"] = kit_hub.canonical_json(state) != kit_hub.canonical_json(hub.load_state())
                    aliases = [key for key, item in (state.get("tasks") or {}).items() if item is ts_given]
                    entry["ts_alias"] = aliases[0] if aliases else None
                    # load_state 读出来的才照三方合并写（save_state）：重放照样建 HubState，带上读出时的样子
                    # 拷一份：调用期间 save_state 会就地更新 seen
                    entry["state_seen"] = copy.deepcopy(state.seen) if isinstance(state, kit_hub.HubState) else None
            inner, busy = [], [False]
            before = _flow_listing(roots)
            ledger = hub.ledger() if hub is not None else None
            offset = ledger.stat().st_size if ledger is not None and ledger.exists() else 0
            patched = [item for item in entry["replaced"] if item != "ts_runner"]  # ts_runner 包的是参数，不换模块里的属性
            saved = {item: getattr(_flow_target(item), _flow_attr(item)) for item in patched + ["utc_now", "utc_compact", "new_msg_id"]}
            saved_env = {key: os.environ.get(key) for key in FLOW_GIT_ENV}
            saved_time = time.time
            os.environ.update(FLOW_GIT_ENV)
            kit_hub.utc_now, kit_hub.utc_compact = _flow_pin(entry["pin"])
            kit_hub.new_msg_id = _flow_msg_id()
            if flow_i:
                time.time = lambda: entry["pin"] / 1_000_000
            for item in patched:
                setattr(_flow_target(item), _flow_attr(item), _flow_install(item, saved[item], lambda inner_name, fn: _flow_recorder(inner_name, fn, roots, inner, busy)))
            if runner is not None:
                bound.arguments["runner"] = _flow_recorder("ts_runner", runner, roots, inner, busy)
            saved_runner = engine.runner if engine is not None and not fake else None
            if saved_runner is not None:
                engine.runner = _RunnerProxy(_flow_recorder("runner", saved_runner.run, roots, inner, busy))
            if fake:
                bound.arguments["engine"] = _EngineProxy(_flow_recorder("engine.handle_pass", engine.handle_pass, roots, inner, busy),
                                                         _flow_recorder("engine.after_land", engine.after_land, roots, inner, busy))
            _DIRLOCK_FAKE_PID[0] = False
            _TOUCHED_LOCKS.clear()
            streams, captured = (sys.stdin, sys.stdout, sys.stderr), None
            if streamed:  # ⑤j1：记下读到的标准输入与写出的 stdout、stderr，照样交给用例当时的流
                sys.stdin, sys.stdout, sys.stderr = _StdinRecorder(streams[0]), _Tee(streams[1]), _Tee(streams[2])
            saved_context, _PROC["context"] = _PROC["context"], (inner, roots, busy)  # ⑤j2：进程代理的 poll 记进这一次
            depth[0] += 1
            raised = None
            try:
                value = fn(*bound.args, **bound.kwargs)
                result = json.loads(_recorded_value(name, value))
            except Exception as exc:  # noqa: BLE001  记下之后照样抛回用例
                raised = exc
                result = json.loads(_recorded_error(exc))
            finally:
                depth[0] -= 1
                _PROC["context"] = saved_context
                if streamed:
                    entry["stdin"] = sys.stdin.taken
                    captured = ("".join(sys.stdout.parts), "".join(sys.stderr.parts))
                    sys.stdin, sys.stdout, sys.stderr = streams
                time.time = saved_time
                if saved_runner is not None:
                    engine.runner = saved_runner
                for item, original in saved.items():
                    setattr(_flow_target(item), _flow_attr(item), original)
                for key, original in saved_env.items():
                    if original is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = original
            entry["roots"] = [str(root) for root in roots]
            entry["fresh"] = [str(root) for root in roots[known:]]
            touched = _touched_locks(hub) if held else set()
            blocked = [item for item in held if item in touched]
            if blocked and not entry.get("skip"):
                entry["skip"] = "调用当时有活的持有者：%s" % "、".join(blocked)
            if flow_i and _DIRLOCK_FAKE_PID[0] and not entry.get("skip"):
                entry["skip"] = "DirLock 接管时问的是用例换掉的 pid_alive（重放时两边都用真的）"
            entry["inner"] = json.dumps(inner, ensure_ascii=False)
            after = _flow_after(bound) if flow_i and not command else None
            state = _flow_state(result, bound.arguments.get("ts"), roots, before, ledger, offset, after)
            if captured is not None:
                state["stdout"], state["stderr"] = captured
            entry["result"] = json.dumps(state, ensure_ascii=False)
            for item, key, raw, proxy in wrapped:  # ⑤j2：调用之后的参数记完了，还是那个代理的换回用例自己的对象
                if item.get(key) is proxy:
                    item[key] = raw
            if raised is not None:
                raise raised
            return value
        return wrapper

    def recorder(name, fn):
        signature = inspect.signature(fn)

        def wrapper(*args, **kwargs):
            entry = None
            if depth[0] == 0:
                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                engine = bound.arguments.get("self") if name.startswith("Engine.") else None
                if engine is not None:  # ⑤i1：Engine 记成仓库与 only_task
                    given = [str(engine.hub.repo), engine.only_task] + [plain(item) for key, item in bound.arguments.items() if key != "self"]
                else:
                    given = [plain(item) for item in bound.arguments.values()]
                entry = {"test": current[0], "fn": name, "args": given}
                calls.append(entry)
                if name in snapshot_functions:  # ⑤i1：resumed_session 只拿 workspace 比字符串，不存那个目录
                    # ⑤j1：uncommitted_references 的仓库参数叫 repo，另存它；⑤j2：给了 files 的指纹、git status 存那几个文件所在的目录
                    # （用例的临时目录；kit_hub.py 自己所在的内核目录不存，重放时就在原处）
                    extra = (bound.arguments["repo"],) if name == "uncommitted_references" else ()
                    if name in ("code_fingerprint", "kernel_dirty", "kernel_changes") and bound.arguments.get("files") is not None:
                        kernel_dir = Path(kit_hub.__file__).resolve().parent.parent
                        dirs = {Path(item).parent for item in bound.arguments["files"]}
                        extra = tuple(sorted((item for item in dirs if item.is_dir() and not item.resolve().is_relative_to(kernel_dir)), key=str))
                    restores = call_snapshots(bound, None if engine is None else engine.hub, extra=extra,
                                              skip=("workspace",) if name == "resumed_session" else ())
                    entry["restores"] = json.dumps(restores, ensure_ascii=False)  # 同 result：存成 JSON 文字
            depth[0] += 1
            try:
                value = fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001  记下之后照样抛回用例
                if entry is not None:
                    entry["result"] = _recorded_error(exc)
                raise
            finally:
                depth[0] -= 1
            if entry is not None:
                shown = [value, plain(bound.arguments["ts"]["gate_post"].get("unmutated"))] if name == "unmutated_problems" else value
                entry["result"] = _recorded_value(name, shown)
            return value
        return wrapper

    def turn_recorder(original):
        """TurnRunner.run 的记录器（第 ⑤d 片）：调用当时把用例的仓库整份拷进快照（不含 .git），记下 home、launcher 写下的字节与交回的结果、
        回合号与新会话号（重放时注入同一组）、当时的秒数；结束之后照 op_hub_turn 收集产物，存成“当时的结果”。"""
        def run(self, agent, session_key, workspace, role_prompt, prompt, retry_of=None, fresh=False, inputs=None, session_id=None):
            snapshot = Path(request["tmp"]).resolve() / "turn-snapshots" / str(len(calls))
            links = _snapshot_tree(self.hub.repo, snapshot)
            ledger = self.hub.ledger()
            offset = ledger.stat().st_size if ledger.exists() else 0
            entry = {"test": current[0], "fn": "TurnRunner.run", "repo": str(self.hub.repo), "snapshot": str(snapshot), "home": str(Path.home()),
                     "args": [agent, session_key, str(workspace), role_prompt, prompt, retry_of, fresh, None if inputs is None else str(inputs), session_id],
                     "seconds": int(time.time()), "links": links, "overrides": overrides(),
                     # 第 137、141 轮：quizs 回合的命令与真实请求的三份文件由环境给，重放时照样设上
                     "quizs_env": {name: os.environ[name] for name in ("QUIZS_CMD", "QUIZS_LIVE_PLAN", "QUIZS_PROVIDER_PROFILE", "QUIZS_QUALIFICATION") if os.environ.get(name)}}
            calls.append(entry)
            returned, recorded = [], []
            inner, saved = self.launcher, self.launcher

            def launcher(cmd, cwd, env, out, err, timeout):
                back = inner(cmd, cwd, env, out, err, timeout)
                returned.append(back)
                return back

            self.launcher = _turn_launcher(recorded, launcher)
            real_time = time.time
            # 回合里取的秒数钉成记下的那一个（重放注入的也是它）：不钉的话两次取时间之间跨了一秒，限流的解除时刻就差 1（全量跑时撞过）
            time.time = lambda: float(entry["seconds"])
            try:
                summary = original(self, agent, session_key, workspace, role_prompt, prompt, retry_of, fresh, inputs, session_id)
            except Exception as exc:  # noqa: BLE001  记下之后照样抛回用例
                entry["result"] = _recorded_error(exc)
                raise
            finally:
                self.launcher = saved
                time.time = real_time
            turn_dir = Path(summary["turn_dir"])
            back = returned[0] if returned else {}
            raw = lambda name: base64.b64encode((turn_dir / name).read_bytes()).decode("ascii")  # noqa: E731
            entry["script"] = {"stdout": raw("stream.jsonl"), "stderr": raw("stderr.log"), "exit_code": back.get("exit_code", 0),
                               "timed_out": bool(back.get("timed_out")), "wall_seconds": back.get("wall_seconds", 1.5)}
            compact, random2 = summary["turn_id"].rsplit("-", 1)
            new_claude = summary["first_turn"] and kit_hub.ROSTER[agent]["adapter"] == "claude"
            entry["sources"] = {"compact": compact, "random2": random2, "seconds": entry["seconds"],
                                "uuid4": summary["session_id"] if new_claude else "00000000-0000-4000-8000-000000000000"}
            entry["result"] = json.dumps({"ok": True, "value": to_tagged(_turn_artifacts(self.hub, summary, recorded, inputs, agent, offset))})
            return summary
        return run

    def inputs_recorder(original):
        """stage_inputs 的记录器（⑤d2，themistally-15 要的）：调用当时把用例的仓库整份拷进快照（链接与联接另记），记下当时的
        worktree 根目录与 INPUT_FILE_LIMIT（inputs_fixture 两样都换了），结束之后照 op_hub_inputs 收集产物，存成“当时的结果”。
        根目录不在仓库里时快照照不到输入目录的上一层，直接报错。"""
        def stage(hub, ts, key):
            root = kit_hub.worktree_root(hub.repo)
            if not Path(root).resolve().is_relative_to(Path(hub.repo).resolve()):
                raise RuntimeError("worktree 根目录不在用例的仓库里：快照照不到输入目录的上一层")
            snapshot = Path(request["tmp"]).resolve() / "inputs-snapshots" / str(len(calls))
            entry = {"test": current[0], "fn": "stage_inputs", "repo": str(hub.repo), "snapshot": str(snapshot), "links": _snapshot_tree(hub.repo, snapshot),
                     "ts": plain(ts), "key": key, "worktree_root": str(root), "input_file_limit": kit_hub.INPUT_FILE_LIMIT}
            calls.append(entry)
            try:
                target, info = original(hub, ts, key)
            except Exception as exc:  # noqa: BLE001  记下之后照样抛回用例
                entry["result"] = _recorded_error(exc)
                raise
            entry["result"] = json.dumps({"ok": True, "value": to_tagged(_inputs_artifacts(target, info))})
            return target, info
        return stage

    def raw(fixture):
        """pytest 夹具对象底下的原函数（pytest 8.4 起是 _get_wrapped_function）。"""
        return fixture._get_wrapped_function() if hasattr(fixture, "_get_wrapped_function") else fixture.__wrapped__

    for name, fn in originals.items():
        setattr(*_owner_attr(name), flow_recorder(name, fn) if name in flow_functions else recorder(name, fn))
    installed.update({name: getattr(_flow_target(name), _flow_attr(name)) for name in FLOW_INNER + FLOW_INNER_I + FLOW_INNER_J2})
    real_enter, real_alive = kit_hub.DirLock.__enter__, kit_hub.lock_alive

    def entering(lock):  # ⑤i2：记下拿过的锁（_TOUCHED_LOCKS）
        _TOUCHED_LOCKS.append(Path(lock.path))
        return real_enter(lock)

    def probing(path):  # ⑤i2：记下探过的锁
        _TOUCHED_LOCKS.append(Path(path))
        return real_alive(path)
    kit_hub.DirLock.__enter__, kit_hub.lock_alive = entering, probing
    original_run = kit_hub.TurnRunner.run
    if "TurnRunner.run" in request["functions"]:
        kit_hub.TurnRunner.run = turn_recorder(original_run)
    original_stage = kit_hub.stage_inputs
    if "stage_inputs" in request["functions"]:
        kit_hub.stage_inputs = inputs_recorder(original_stage)
    # 采样期间的环境（⑤d2）：契约给假 pi 的 PI_DISPATCH_PI_CMD，采样与重放的命令行里是同一个假 pi
    given_env = request.get("env") or {}
    saved_env = {name: os.environ.get(name) for name in given_env}
    os.environ.update(given_env)
    skipped = []
    try:
        for test, given in [item for name in request["tests"] for item in _instances(name, getattr(cases, name))]:
            fn = getattr(cases, test.split("[")[0])
            params = inspect.signature(fn).parameters
            patch = MonkeyPatch()
            kwargs = dict(given)  # ⑤i1：parametrize 展开的这一组参数
            tmp = Path(tempfile.mkdtemp(dir=Path(request["tmp"]).resolve()))  # 照 pytest 用解析过的长路径：短名写法与 path_forms 展开后的对不上
            if "tmp_path" in params:
                kwargs["tmp_path"] = tmp
            if "monkeypatch" in params:
                kwargs["monkeypatch"] = patch
            # 第 ⑤d 片：pytest 每条用例先搭的 autouse 夹具——test_kit_hub 的 pi_knows_every_flag（pi 认得全部参数、内核当成干净、
            # 协调人的内核代办关掉）与 conftest 的 python_kernel_impl（调度器的选择文件钉成不存在）
            raw(cases.pi_knows_every_flag)(patch)
            if "pi_dispatch" in sys.modules:
                patch.setattr(sys.modules["pi_dispatch"], "KERNEL_IMPL_PATH", tmp / "no-kernel-impl.json")
            if "engine_env" in params:  # test_kit_hub 自己的夹具（建信箱、换掉 worktree 与 role_prompt）
                kwargs["engine_env"] = raw(cases.engine_env)(tmp, patch)
            if "kernel_routing" in params:  # ⑤i1：打开协调人的内核代办（6 条用例）
                kwargs["kernel_routing"] = raw(cases.kernel_routing)(patch)
            out_buf, err_buf = io.StringIO(), io.StringIO()
            if "capsys" in params:  # ⑤i2
                kwargs["capsys"] = _Capsys(out_buf, err_buf)
            current[0] = test
            # 照 pytest 截下用例的输出（⑤e1a）：有的用例经 hub 往标准输出打印中文，探针的 stdout 不是 UTF-8 时会崩在打印上。
            # undo 也在截下的范围里：用例用 monkeypatch 换过 sys.stdout 的，undo 会还原成这里的 StringIO。
            # ⑤h1：子进程不经 sys.stdout，直接写文件描述符 1、2（exclusive 起的 git status --short），探针的 stdout 是交回结果的
            # 通道：跑用例期间 1、2 接到空设备（Windows 上 dup2 连标准句柄一起换，子进程继承到的也是空设备），跑完接回
            sys.stdout.flush()
            saved_fds, sink = [os.dup(1), os.dup(2)], os.open(os.devnull, os.O_WRONLY)
            os.dup2(sink, 1)
            os.dup2(sink, 2)
            try:
                with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
                    try:
                        fn(**kwargs)
                    except BaseException as exc:  # noqa: BLE001  pytest.skip 抛的是 BaseException 的子类
                        if type(exc).__name__ != "Skipped":
                            raise
                        skipped.append(test)
                    finally:
                        patch.undo()
            finally:
                for stream in (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__):  # 用例期间直接写进真流的，冲进空设备
                    stream.flush()
                os.dup2(saved_fds[0], 1)
                os.dup2(saved_fds[1], 2)
                for fd in saved_fds + [sink]:
                    os.close(fd)
    finally:
        for name, fn in originals.items():
            setattr(*_owner_attr(name), fn)
        kit_hub.DirLock.__enter__, kit_hub.lock_alive = real_enter, real_alive
        kit_hub.TurnRunner.run = original_run
        kit_hub.stage_inputs = original_stage
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    return {"ok": True, "value": to_tagged({"calls": calls, "skipped": skipped})}

def _shadow_one(fn):
    try:
        return {"ok": True, "value": to_tagged(fn())}
    except Exception as exc:  # noqa: BLE001  类型与文字（⑤f 起文字也比）
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}


def _shadow_text(b64):
    """影子传来的原始字节：写进临时文件，用 kit_hub.read_text 读出来（UTF-8、通用换行），这一步本身也在比。"""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "x"
        path.write_bytes(base64.b64decode(b64))
        return kit_hub.read_text(path)


def op_hub_shadow_task(request):
    """⑤-影子：一个主任务的只读结论。repo 是影子复制出来的快照（不是在用的信箱），探针自己读出状态；主任务不在状态里时
    ts 是 None，只比 guard。其余：内核此刻允许的下一步、阶段状态表、热修补的原因、门禁文件、主任务与各阶段的上游须知、
    guard 的整张表（request["metas"] 是一组信头）。每一项各自接住异常、交回类型，一项崩了不挡别的。"""
    hub = kit_hub.Hub(Path(request["repo"]))
    try:
        ts = hub.load_state()["tasks"].get(request["task"])
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "items": [["load_state", {"ok": False, "error": type(exc).__name__, "message": str(exc)}]]}
    items = []
    if ts is not None:
        items += [["allowed_moves", _shadow_one(lambda: kit_hub.allowed_moves(ts))],
                  ["stage_status_table", _shadow_one(lambda: kit_hub.stage_status_table(hub, ts))],
                  ["hotfix_reason", _shadow_one(lambda: kit_hub.hotfix_reason(ts))],
                  ["gate_pattern", _shadow_one(lambda: kit_hub.gate_pattern(ts))]]
        items += [["gate_file " + kind, _shadow_one(lambda kind=kind: kit_hub.gate_file(ts, kind))] for kind in ("baseline", "whitebox")]
        items += [["upstream_notes %s" % suffix, _shadow_one(lambda suffix=suffix: kit_hub.upstream_notes(ts, suffix))]
                  for suffix in [None] + list(kit_hub.STAGE_ORDER)]
    items += [["guard", _shadow_one(lambda meta=meta: kit_hub.guard(ts, meta))] for meta in request["metas"]]
    return {"ok": True, "items": items}


def op_hub_shadow_letter(request):
    """⑤-影子：一封信（影子取到的原始字节）的读出、解析、往返（渲染之后再解析）、形状校验与所属主任务；每一项各自接住异常。"""
    try:
        text = _shadow_text(request["b64"])
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "items": [["read_text", {"ok": False, "error": type(exc).__name__, "message": str(exc)}]]}
    items = [["read_text", _shadow_one(lambda: text)]]
    try:
        meta, fields, lines = kit_hub.parse_letter(text)
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "items": items + [["parse_letter", {"ok": False, "error": type(exc).__name__, "message": str(exc)}]]}
    items += [["parse_letter", _shadow_one(lambda: [meta, fields, lines])],
              ["render_letter", _shadow_one(lambda: kit_hub.render_letter(meta, fields))],
              ["reparse", _shadow_one(lambda: list(kit_hub.parse_letter(kit_hub.render_letter(meta, fields))))],
              ["letter_errors", _shadow_one(lambda: kit_hub.letter_errors(meta, fields, lines))],
              ["stage_of", _shadow_one(lambda: list(kit_hub.stage_of(meta.get("task-id"))))]]
    return {"ok": True, "items": items}


def op_hub_shadow_routine(request):
    """⑤-影子：写给协调人的一封信单独成批时，内核代办的结论（routine_moves），以及每个下一步的任务书（render_routine_brief，
    用信所属主任务在快照里的状态）。"""
    hub = kit_hub.Hub(Path(request["repo"]))
    try:
        text = _shadow_text(request["b64"])
        moves, reason = kit_hub.routine_moves([text])
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "items": [["routine_moves", {"ok": False, "error": type(exc).__name__, "message": str(exc)}]]}
    items = [["routine_moves", _shadow_one(lambda: [moves, reason])]]
    if not moves:
        return {"ok": True, "items": items}
    try:
        main = kit_hub.stage_of(kit_hub.parse_letter(text)[0].get("task-id", ""))[0]
        ts = hub.load_state()["tasks"].get(main or "")
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "items": items + [["ts", {"ok": False, "error": type(exc).__name__, "message": str(exc)}]]}
    if ts is not None:
        items += [["brief", _shadow_one(lambda move=move: kit_hub.render_routine_brief(hub, ts, move))] for move in moves]
    return {"ok": True, "items": items}


def op_hub_shadow_route(request):
    """⑤-影子：账本里一次 route.kernel 的那批信（原始字节），重算 routine_moves。"""
    try:
        texts = [_shadow_text(b64) for b64 in request["b64s"]]
        return {"ok": True, "value": to_tagged(list(kit_hub.routine_moves(texts)))}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "message": str(exc)}

OPS = {
    "plugins.call": op_plugins_call,
    "protocols.strict": op_protocols_strict,
    "decisions.call": op_decisions_call,
    "config.call": op_config_call,
    "roles.call": op_roles_call,
    "secret_store.call": op_secret_store_call,
    "unicode.call": op_unicode_call,
    "pyio.call": op_pyio_call,
    "pyurl.call": op_pyurl_call,
    "pyvalue.eq": op_pyvalue_eq,
    "pyset.sorted": op_pyset_sorted,
    "winerror.real": op_winerror_real,
    "mtime.real": op_mtime_real,
    "pyexc.real": op_pyexc_real,
    "pyexc.fs_real": op_pyexc_fs_real,
    "replace.real": op_replace_real,
    "pypath.pure": op_pypath_pure,
    "supervise.run": op_supervise_run,
    "argv.ensure_safe": op_argv_ensure_safe,
    "pyshlex.split": op_pyshlex_split,
    "patterns.call": op_patterns_call,
    "contract.call": op_contract_call,
    "events.call": op_events_call,
    "pypath.call": op_pypath_call,
    "pyfmt.number": op_pyfmt_number,
    "dispatch.child_env": op_dispatch_child_env,
    "roles.cwd_relative": op_roles_cwd_relative,
    "dispatch.run_capture": op_dispatch_run_capture,
    "dispatch.parse_cli": op_dispatch_parse_cli,
    "run.call": op_run_call,
    "publish_new": op_publish_new,
    "filelock.run": op_filelock_run,
    "secrets.call": op_secrets_call,
    "jsonl.append": op_jsonl_append,
    "jsonl.read": op_jsonl_read,
    "jsonl.records": op_jsonl_records,
    "pyfmt.call": op_pyfmt_call,
    "hub.call": op_hub_call,
    "hub.samples": op_hub_samples,
    "hub.box": op_hub_box,
    "hub.constants": op_hub_constants,
    "hub.audit": op_hub_audit,
    "hub.audit_samples": op_hub_audit_samples,
    "hub.prompt": op_hub_prompt,
    "hub.contract": op_hub_contract,
    "hub.contract_flow": op_hub_contract_flow,
    "hub.popen": op_hub_popen,
    "hub.inputs": op_hub_inputs,
    "hub.turn": op_hub_turn,
    "hub.shadow_task": op_hub_shadow_task,
    "hub.shadow_letter": op_hub_shadow_letter,
    "hub.shadow_routine": op_hub_shadow_routine,
    "hub.shadow_route": op_hub_shadow_route,
    "fs.hold_exclusive": op_fs_hold_exclusive,
    "pyregex.search": op_pyregex_search,
    "pyregex.search_flags": op_pyregex_search_flags,
    "pydatetime.parse_iso": op_pydatetime_parse_iso,
    "jsonl.iter_lines": op_jsonl_iter_lines,
    "jsonl.lines_before": op_jsonl_lines_before,
    "clock.sample": op_clock_sample,
    "fs.read_text": op_fs_read_text,
    "fs.write_text_atomic": op_fs_write_text_atomic,
    "pid_alive": op_pid_alive,
    "lock.run": op_lock_run,
    "pyjson.dumps": op_pyjson_dumps,
    "pyjson.loads": op_pyjson_loads,
    "pyjson.roundtrip": op_pyjson_roundtrip,
    "pyjson.raw_decode": op_pyjson_raw_decode,
    "pyjson.loads_bytes": op_pyjson_loads_bytes,
    "pydifflib.call": op_pydifflib_call,
    "pystr.call": op_pystr_call,
    "mutate.check_anchors": op_mutate_check_anchors,
    "decisions.client": op_decisions_client,
}


def run_one(request):
    if request.get("barrier"):
        wait_for(request["barrier"])
    handler = OPS.get(request["op"])
    if handler is None:
        return {"ok": False, "error": "UNKNOWN_OP"}
    try:
        return handler(request)
    except OSError as exc:
        return {"ok": False, "error": errno.errorcode.get(exc.errno or 0, "EUNKNOWN")}
    except (json.JSONDecodeError, TypeError, ValueError, UnicodeError, RecursionError) as exc:
        if request["op"].startswith("pyjson."):  # pyjson 的报错文字是契约的一部分（会经 str(exc) 写进输出）
            return {"ok": False, "error": type(exc).__name__, "message": str(exc)}
        return {"ok": False, "error": type(exc).__name__}


def _peak_bytes():
    """本进程到现在的峰值工作集（字节，Windows 的 PeakWorkingSetSize）；拿不到时是 None。影子按它记探针占了多少内存。"""
    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                                   "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                                                   "PagefileUsage", "PeakPagefileUsage")]

        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi")
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]  # 伪句柄 -1 要按句柄传
        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return None
        return counters.PeakWorkingSetSize
    except Exception:  # noqa: BLE001  不是 Windows 或调不到：不记
        return None

def main() -> int:
    request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    if request["op"] == "batch":
        result = {"ok": True, "results": [run_one(item) for item in request["items"]], "peak_bytes": _peak_bytes()}
    else:
        result = run_one(request)
    sys.stdout.buffer.write(json.dumps(result).encode("ascii"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
