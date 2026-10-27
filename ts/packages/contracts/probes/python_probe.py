"""契约探针（Python 实现）：stdin 读一个 JSON 请求，stdout 写一个 JSON 结果。

只 import 仓库里的 scripts/ 与标准库，不改它们。请求与结果的形状见 test/harness.ts；
TS 实现的探针（ts_probe.ts）收发同样的 JSON，契约测试与对照测试对两边一视同仁。
stdin 按 UTF-8 读字节（Windows 上 sys.stdin 的缺省编码是 cp1252），stdout 只写 ASCII。
"""
import base64
import contextlib
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
    "publish_new": op_publish_new,
    "filelock.run": op_filelock_run,
    "secrets.call": op_secrets_call,
    "jsonl.append": op_jsonl_append,
    "jsonl.read": op_jsonl_read,
    "jsonl.records": op_jsonl_records,
    "pyfmt.call": op_pyfmt_call,
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
