"""契约探针（Python 实现）：stdin 读一个 JSON 请求，stdout 写一个 JSON 结果。

只 import 仓库里的 scripts/ 与标准库，不改它们。请求与结果的形状见 test/harness.ts；
TS 实现的探针（ts_probe.ts）收发同样的 JSON，契约测试与对照测试对两边一视同仁。
stdin 按 UTF-8 读字节（Windows 上 sys.stdin 的缺省编码是 cp1252），stdout 只写 ASCII。
"""
import ast
import base64
import contextlib
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
              "load_locked_batteries")
#: ⑤f：用例没换、也照记录注入的（themistally-15 定的，⑤f 设计稿第 3、10 节）：白盒测试那一次 run_supervised 只在 accept_gate_post 里录，
#: mkdtemp 在建 worktree 的两个函数里录
FLOW_ALWAYS = {"accept_gate_post": ("run_supervised",), "apply_candidate": ("mkdtemp",), "ensure_worktree": ("mkdtemp",),
               "run_exec": ("mkdtemp",)}  # ⑤g2：rebase_candidate 的临时 worktree
#: 第二个参数是 ts、契约要比调用之后的 ts 的内层函数
FLOW_TS_INNER = ("contract_requirements", "budget_problems", "revalidate_contract")
#: 重放时要转成 Path 的参数（按位置）
FLOW_PATH_ARGS = {"accept_gate_pre": (2,), "seed_whitebox": (2,), "accept_gate_post": (2,), "run_mutations": (2, 3), "finish_exec": (2,),
                  "write_review": (2,), "start_rework": (2,), "rebase_candidate": (2,), "start_retry": (2,), "final_audit_turn": (2,)}
#: ⑤e2b：最外层调用期间的提交作者与日期（采样与三边重放一样），门禁基准测试的提交 SHA 才钉得住
FLOW_GIT_ENV = {"GIT_AUTHOR_NAME": "themis-contract", "GIT_AUTHOR_EMAIL": "contract@example.invalid",
                "GIT_COMMITTER_NAME": "themis-contract", "GIT_COMMITTER_EMAIL": "contract@example.invalid",
                "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00"}


class _InjectionMismatch(Exception):
    """重放注入的内层调用与记录对不上（参数不同、多调）。"""


def _plain(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, kit_hub.Hub):
        return str(value.repo)
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def _flow_target(name):
    """内层函数换在哪里：kit_hub 调的是 pd.run_supervised、tempfile.mkdtemp 与 decisions 的两样，其余是 kit_hub 自己的。"""
    return {"run_supervised": kit_hub.pd, "mkdtemp": tempfile, "Session": codekit_decisions,
            "load_locked_batteries": codekit_decisions}.get(name, kit_hub)


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


def _env_check(env):
    """传给 run_supervised 的环境变量与当场的 kernel_pytest_env() 整份比：相同记 True，不同只记对不上的名字（值不进记录）。"""
    expected = kit_hub.kernel_pytest_env()
    if env == expected:
        return True
    return sorted(name for name in set(env) | set(expected) if env.get(name) != expected.get(name))


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


def _flow_git(roots):
    """用命令读出的 git 状态：每棵树的 HEAD 与 status -z 的原文，第一棵树里的全部引用。不是仓库的记 None。"""
    import subprocess

    def run(args, cwd):
        done = subprocess.run(["git"] + args, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return done.stdout.decode("utf-8", "replace") if done.returncode == 0 else None

    trees = []
    for root in roots:
        if not Path(root).is_dir():  # ⑤g2：rebase_candidate 的临时 worktree 用完就收掉了
            trees.append({"head": None, "status": None})
            continue
        head = run(["rev-parse", "HEAD"], root)
        trees.append({"head": head.strip() if head is not None else None,
                      "status": run(["status", "--porcelain=v1", "--untracked-files=all", "-z"], root)})
    return {"trees": trees, "refs": run(["for-each-ref", "--format=%(refname) %(objectname)"], roots[0])}


def _flow_state(result, ts, roots, before, ledger, offset):
    """一次最外层调用之后要比的：交回值、调用之后的 ts、几棵树里的文件改动、账本新增的部分、git 状态。"""
    tail = ledger.read_bytes()[offset:] if ledger is not None and ledger.exists() else b""
    return {"result": result, "ts": to_tagged(_plain(ts)), "files": _flow_changes(roots, before),
            "ledger": base64.b64encode(tail).decode("ascii"), "git": _flow_git(roots)}


def _flow_inner_call(name, args, kwargs):
    """内层调用要核对的参数：run_pd 比 argv 与 timeout（没给是 None），另外三个比仓库路径与调用那一刻的整份 ts。"""
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
        if busy[0]:
            return fn(*args, **kwargs)
        entry = _flow_inner_call(name, args, kwargs)
        before = _flow_listing(roots)
        busy[0] = True
        try:
            value = fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001  录下来照样抛
            entry["raise"] = [type(exc).__name__, str(exc)]
            raise
        else:
            entry["value"] = to_tagged(_plain(value))
            if name == "mkdtemp" and all(Path(value).resolve() != Path(root).resolve() for root in roots):
                roots.append(Path(value))  # ⑤f：新建的 worktree 当新的一棵树（调用之前不在，重放前先删）
        finally:
            busy[0] = False
            entry["files"] = _flow_changes(roots, before)
            if name in FLOW_TS_INNER:
                entry["ts_after"] = to_tagged(_plain(args[1]))
            inner.append(entry)
        return value
    return record


def _flow_injector(name, queue, roots):
    """重放：照记录注入内层调用。参数逐次核对，对不上或多调报 _InjectionMismatch；照记录写文件、删文件、原地改 ts，再交回或抛出。"""
    def inject(*args, **kwargs):
        got = _flow_inner_call(name, args, kwargs)
        expected = queue.pop(0) if queue else None
        if expected is None or any(expected.get(key) != value for key, value in got.items()):
            raise _InjectionMismatch(json.dumps({"got": got, "expected": expected and {key: expected.get(key) for key in got}}, ensure_ascii=False))
        if name == "mkdtemp":
            made = from_tagged(expected["value"])
            if os.path.normcase(os.path.dirname(made)) != os.path.normcase(str(kwargs.get("dir"))):
                raise _InjectionMismatch("mkdtemp 记下的目录不在 dir 下：%s" % made)
            os.mkdir(made)
        for key, data in expected["files"]["write"].items():
            path = _flow_path(roots, key)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(base64.b64decode(data))
        for key in expected["files"]["delete"]:
            os.remove(_flow_path(roots, key))
        if "ts_after" in expected:
            ts = args[1]
            ts.clear()
            ts.update(from_tagged(expected["ts_after"]))
        if "raise" in expected:
            raise type(expected["raise"][0], (Exception,), {})(expected["raise"][1])
        value = from_tagged(expected["value"])
        return Path(value) if name == "worktree_root" else value
    return inject


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


def op_hub_contract_flow(request):
    """第 ⑤e2b 片：合同与战前门禁里改状态的六个函数，照调用当时重放。先原地放回快照（带 .git），钉住时刻与提交作者、日期，
    用例当时换掉的内层函数照记录注入（request["inner"]，逐次核对；用完了还有剩的报 INJECTION_LEFTOVER），交回 _flow_state。"""
    for item in request.get("restores") or []:
        _restore_tree(item["from"], item["to"], item.get("links", []), with_git=bool(item.get("git")))
    fn = request["fn"]
    args = [from_tagged(item) for item in request["args"]]
    hub = kit_hub.Hub(Path(args[0])) if args[0] is not None else None
    ts = args[1]
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
    saved = {name: getattr(_flow_target(name), name) for name in replaced + ["utc_now", "utc_compact"]}
    saved_wait, saved_session = kit_hub.EXEC_LAND_WAIT_SECONDS, codekit_decisions.Session
    os.environ.update(given_env)
    kit_hub.utc_now, kit_hub.utc_compact = _flow_pin(request["pin"])
    if request.get("land_wait") is not None:  # ⑤g2 手写场景：落地锁由另一个进程拿着，等锁的时限设短
        kit_hub.EXEC_LAND_WAIT_SECONDS = request["land_wait"]
    if request.get("jev"):
        codekit_decisions.Session = _jev_session(request["jev"]["endpoint"], request["jev"]["key"])
    for name in replaced:
        setattr(_flow_target(name), name, _flow_install(name, saved[name], lambda inner, _fn: _flow_injector(inner, queue, roots)))
    try:
        value = getattr(kit_hub, fn)(hub, ts, *rest)
        result = json.loads(_recorded_value(fn, value))
        if queue:
            result = {"ok": False, "error": "INJECTION_LEFTOVER", "left": [entry["fn"] for entry in queue]}
    except _InjectionMismatch as exc:
        result = {"ok": False, "error": "INJECTION_MISMATCH", "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001  与当时的结果一样记类型与文字（HubError 另记退出码）
        result = json.loads(_recorded_error(exc))
    finally:
        for name, item in saved.items():
            setattr(_flow_target(name), name, item)
        kit_hub.EXEC_LAND_WAIT_SECONDS, codekit_decisions.Session = saved_wait, saved_session
        for name, item in saved_env.items():
            if item is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = item
    return {"ok": True, "value": _flow_state(result, ts, roots, before, ledger, offset)}


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
        if isinstance(value, (list, tuple)):
            return [plain(item) for item in value]
        if isinstance(value, dict):
            return {key: plain(item) for key, item in value.items()}
        return value

    calls, depth, current = [], [0], [None]
    originals = {name: getattr(kit_hub, name) for name in request["functions"] if name not in ("TurnRunner.run", "stage_inputs")}
    pristine = [(kit_hub.ROSTER, copy.deepcopy(kit_hub.ROSTER)), (kit_hub.DELIVERY_SHA256, dict(kit_hub.DELIVERY_SHA256))]

    def overrides():
        """用例此刻改过的名册岗位与交差文件哈希（与采样开始时比，对应 monkeypatch.setitem）：重放时两边设同一组。删掉的键重放设不回来，直接报错。"""
        changed = []
        for table, before in pristine:
            if set(before) - set(table):
                raise RuntimeError("用例删掉了 %s" % sorted(set(before) - set(table)))
            changed.append({name: plain(value) for name, value in table.items() if name not in before or before[name] != value})
        return json.dumps({"roster": changed[0], "delivery_sha256": changed[1]}, ensure_ascii=False)

    snapshot_functions = set(request.get("snapshot_functions") or [])

    def call_snapshots(bound):
        """⑤e2a：调用当时的快照（带 .git），重放前原地放回（hub.contract 的 restores）。带 hub 的函数存仓库；workspace_status 存那个目录，
        它是仓库外的 worktree（.git 是指针文件）时连主仓库一起存（worktree 的元数据在主仓库的 .git/worktrees 下）。"""
        roots = []
        if isinstance(bound.arguments.get("hub"), kit_hub.Hub):
            roots.append(Path(bound.arguments["hub"].repo))
        # ⑤e2b：门禁草稿 worktree 叫 workspace；⑤g1：returned_blockers、rework_section 的上一轮 attempt 叫 previous
        given = {key: bound.arguments.get(key) for key in ("path", "workspace", "run_dir", "previous")}
        ts = bound.arguments.get("ts")
        if given["run_dir"] is None and isinstance(ts, dict) and isinstance(ts.get("exec"), dict) and ts["exec"].get("run_dir"):
            given["run_dir"] = ts["exec"]["run_dir"]  # ⑤f：读 meta.json、scope.json、candidate.patch 的那个 attempt 目录
        for key, value in given.items():
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
        调用之后的 _flow_state（交回值、ts、文件、账本、git 状态）。时刻与提交作者、日期只在这一次调用期间钉住。"""
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
            entry = {"test": current[0], "fn": name, "args": [plain(item) for item in bound.arguments.values()]}
            calls.append(entry)
            hub = bound.arguments["hub"]
            roots = _flow_roots(hub, bound.arguments.get("workspace"))
            entry["restores"] = json.dumps(call_snapshots(bound), ensure_ascii=False)
            known = len(roots)
            entry["pin"] = time.time_ns() // 1000
            entry["replaced"] = [item for item in FLOW_INNER if getattr(_flow_target(item), item) is not installed[item]] + list(FLOW_ALWAYS.get(name, ()))
            if name == "run_exec" and kit_hub.EXEC_LAND_WAIT_SECONDS != land_wait:
                # ⑤g2：用例自己拿着落地锁、等锁时限改短了（落地锁被占的那一条）。重放时拿锁的已经不在，不重放，契约钉住只跳这一条
                entry["skip"] = "EXEC_LAND_WAIT_SECONDS=%r" % (kit_hub.EXEC_LAND_WAIT_SECONDS,)
            inner, busy = [], [False]
            before = _flow_listing(roots)
            ledger = hub.ledger() if hub is not None else None
            offset = ledger.stat().st_size if ledger is not None and ledger.exists() else 0
            saved = {item: getattr(_flow_target(item), item) for item in entry["replaced"] + ["utc_now", "utc_compact"]}
            saved_env = {key: os.environ.get(key) for key in FLOW_GIT_ENV}
            os.environ.update(FLOW_GIT_ENV)
            kit_hub.utc_now, kit_hub.utc_compact = _flow_pin(entry["pin"])
            for item in entry["replaced"]:
                setattr(_flow_target(item), item, _flow_install(item, saved[item], lambda inner_name, fn: _flow_recorder(inner_name, fn, roots, inner, busy)))
            depth[0] += 1
            raised = None
            try:
                value = fn(*args, **kwargs)
                result = json.loads(_recorded_value(name, value))
            except Exception as exc:  # noqa: BLE001  记下之后照样抛回用例
                raised = exc
                result = json.loads(_recorded_error(exc))
            finally:
                depth[0] -= 1
                for item, original in saved.items():
                    setattr(_flow_target(item), item, original)
                for key, original in saved_env.items():
                    if original is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = original
            entry["roots"] = [str(root) for root in roots]
            entry["fresh"] = [str(root) for root in roots[known:]]
            entry["inner"] = json.dumps(inner, ensure_ascii=False)
            entry["result"] = json.dumps(_flow_state(result, bound.arguments["ts"], roots, before, ledger, offset), ensure_ascii=False)
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
                entry = {"test": current[0], "fn": name, "args": [plain(item) for item in bound.arguments.values()]}
                calls.append(entry)
                if name in snapshot_functions:
                    entry["restores"] = json.dumps(call_snapshots(bound), ensure_ascii=False)  # 同 result：存成 JSON 文字
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
                     "seconds": int(time.time()), "links": links, "overrides": overrides()}
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
        setattr(kit_hub, name, flow_recorder(name, fn) if name in flow_functions else recorder(name, fn))
    installed.update({name: getattr(_flow_target(name), name) for name in FLOW_INNER})
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
        for test in request["tests"]:
            fn = getattr(cases, test)
            params = inspect.signature(fn).parameters
            patch = MonkeyPatch()
            kwargs = {}
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
            current[0] = test
            # 照 pytest 截下用例的输出（⑤e1a）：有的用例经 hub 往标准输出打印中文，探针的 stdout 不是 UTF-8 时会崩在打印上。
            # undo 也在截下的范围里：用例用 monkeypatch 换过 sys.stdout 的，undo 会还原成这里的 StringIO
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    fn(**kwargs)
                except BaseException as exc:  # noqa: BLE001  pytest.skip 抛的是 BaseException 的子类
                    if type(exc).__name__ != "Skipped":
                        raise
                    skipped.append(test)
                finally:
                    patch.undo()
    finally:
        for name, fn in originals.items():
            setattr(kit_hub, name, fn)
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
