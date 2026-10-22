"""契约探针（Python 实现）：stdin 读一个 JSON 请求，stdout 写一个 JSON 结果。

只 import 仓库里的 scripts/ 与标准库，不改它们。请求与结果的形状见 test/harness.ts；
TS 实现的探针（ts_probe.ts）收发同样的 JSON，契约测试与对照测试对两边一视同仁。
stdin 按 UTF-8 读字节（Windows 上 sys.stdin 的缺省编码是 cp1252），stdout 只写 ASCII。
"""
import base64
import errno
import json
import os
import secrets
import struct
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # ts/packages/contracts/probes → 仓库根
sys.path.insert(0, str(ROOT / "scripts"))

import kit_config  # noqa: E402
import kit_hub  # noqa: E402
import kit_logs  # noqa: E402
import pi_dispatch  # noqa: E402
from codekit import decisions as codekit_decisions  # noqa: E402
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
    except (kit_hub.HubError, pi_dispatch.DispatchError, kit_config.ConfigError):
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
    if fn == "int":
        try:
            return {"ok": True, "text": str(int(request["text"]))}
        except ValueError:
            return {"ok": False, "error": "ValueError"}
    return {"ok": False, "error": "UNKNOWN_FN"}


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


OPS = {
    "publish_new": op_publish_new,
    "filelock.run": op_filelock_run,
    "secrets.call": op_secrets_call,
    "jsonl.append": op_jsonl_append,
    "jsonl.read": op_jsonl_read,
    "jsonl.records": op_jsonl_records,
    "pyfmt.call": op_pyfmt_call,
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


def main() -> int:
    request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    if request["op"] == "batch":
        result = {"ok": True, "results": [run_one(item) for item in request["items"]]}
    else:
        result = run_one(request)
    sys.stdout.buffer.write(json.dumps(result).encode("ascii"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
