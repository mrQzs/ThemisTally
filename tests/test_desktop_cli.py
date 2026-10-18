"""3.0 桌面端 D1-A：内核命令行的补充（docs/themis-tally-3.0-桌面端.md 的 D4、D7、D13；测试计划 10.1）。

覆盖：
- 公开的结构脱敏 `pd.redact_json` 与路由白名单（r4-B1、r5-B1、r6-S1；U22 的白名单部分）；
- 证据的安全读取与 `logs cat`（r2-B1、r3-B1、r3-S3、r3-S4、r4-S1；U14、U14b、U14d）；
- `logs search` 只在脱敏之后的文本里搜，并有 `--json`（r3-B1；U14c）；
- `status --json` 给运行中的 attempt 补 `live`，不改 `events_ok`（D7；U9 的命令行一半）；
- `config validate --json`。

夹具都在 pytest 的 tmp_path 里现场生成；凭据一律是虚构的测试值。命令在进程内调用；只有测耗时的那一条在子进程里跑，
超时就失败。
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import kit_config  # noqa: E402
import kit_logs  # noqa: E402
import pi_dispatch as pd  # noqa: E402

FAKE = "examplevalue"  # 虚构的凭据值：任何输出里都不许出现
TOKEN_KEY = "sk-" + "abcdefghijklmnopqrstuv"  # 键名本身像令牌


# ---------------------------------------------------------------------------
# 夹具
# ---------------------------------------------------------------------------

def make_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".agent" / "runs").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    return repo


def attempt_dir(repo, task="task-a", number=1, state="NEEDS_REVIEW"):
    directory = repo / ".agent" / "runs" / task / ("attempt-%03d" % number)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "state.json").write_text(json.dumps({"state": state, "at": "2026-10-19T01:00:00Z"}),
                                          encoding="utf-8")
    return directory


def run(main, argv, repo):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv), repo=str(repo))
        except SystemExit as exc:  # argparse
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def cat(repo, target, rel, *extra):
    return run(kit_logs.main, ["cat", target, rel, "--json"] + list(extra), repo)


def all_pages(repo, target, rel, limit):
    """按页读完，返回每一页的 JSON。"""
    pages, cursor = [], None
    for _ in range(10000):
        argv = ["--limit", str(limit)] + (["--cursor", cursor] if cursor else [])
        code, out, err = cat(repo, target, rel, *argv)
        assert code == 0, err
        page = json.loads(out)
        pages.append(page)
        if page["done"]:
            return pages
        cursor = page["next_cursor"]
    raise AssertionError("没有读完")


# ---------------------------------------------------------------------------
# redact_json 与白名单（r4-B1、r5-B1、r6-S1）
# ---------------------------------------------------------------------------

def test_redact_json_masks_by_key_and_token_shaped_keys():
    assert pd.redact_json({"api_key": FAKE}) == {"api_key": "<redacted>"}
    masked = pd.redact_json({TOKEN_KEY: "ordinary"})
    assert TOKEN_KEY not in json.dumps(masked)
    # 不看键名的 redact_obj 会漏：这正是改用 redact_json 的原因
    assert FAKE in json.dumps(pd.redact_obj({"api_key": FAKE}))


def test_redact_json_allowlist_keeps_validated_metadata_only():
    allow = {
        ("profiles", "*", "credential_env", "*"): pd.allow_env_name,
        ("decisions", "secret", "source"): pd.allow_enum("env", "credential_store", "file", "none"),
    }
    data = {"profiles": [{"id": "step-high", "credential_env": ["STEP_API_KEY"]}],
            "decisions": {"secret": {"source": "credential_store", "store_mode": "system"}}}
    out = pd.redact_json(data, allow=allow)
    assert out["profiles"][0]["credential_env"] == ["STEP_API_KEY"]
    assert out["decisions"]["secret"]["source"] == "credential_store"
    assert out["decisions"]["secret"]["store_mode"] == "<redacted>"  # 没登记的照样遮
    # 没有白名单时，credential_env 会被整组遮掉（第 5 轮 B1 的误伤）
    assert pd.redact_json(data)["profiles"][0]["credential_env"] == ["<redacted>"]
    # 白名单字段的值不合规：照样遮
    bad = {"profiles": [{"credential_env": ["sk-" + "q" * 24, "not a name"]}],
           "decisions": {"secret": {"source": "bogus"}}}
    out = pd.redact_json(bad, allow=allow)
    assert out["profiles"][0]["credential_env"] == ["<redacted>", "<redacted>"]
    assert out["decisions"]["secret"]["source"] == "<redacted>"


def test_redact_json_allowlist_row_condition_and_used_by():
    allow = {
        ("keys", "[key=env_remove]", "value", "*"): pd.allow_env_name,
        ("secrets", "*", "name"): pd.allow_env_name,
        ("secrets", "*", "source"): pd.allow_enum("env", "credential_store", "file", "none"),
        ("secrets", "*", "used_by", "*", "kind"): pd.allow_enum("profile", "decisions"),
        ("secrets", "*", "used_by", "*", "id"): pd.allow_id,
    }
    data = {"keys": [{"key": "env_remove", "value": ["FOO_KEY", "not a name!"]},
                     {"key": "other", "value": ["not a name!"]}],
            "secrets": [{"name": "STEP_API_KEY", "source": "credential_store", "note": "free text",
                         "used_by": [{"kind": "profile", "id": "step-high"}, {"kind": "decisions"},
                                     {"kind": "profile", "id": "sk-" + "w" * 24},
                                     {"kind": "free text"}]}]}
    out = pd.redact_json(data, allow=allow)
    assert out["keys"][0]["value"] == ["FOO_KEY", "<redacted>"]
    assert out["keys"][1]["value"] == ["not a name!"]  # 行条件不符，不受这条规则约束，按缺省处理
    row = out["secrets"][0]
    assert (row["name"], row["source"]) == ("STEP_API_KEY", "credential_store")
    assert row["note"] == "<redacted>"  # 敏感祖先键下的任意文本：不豁免
    assert row["used_by"][0] == {"kind": "profile", "id": "step-high"}
    assert row["used_by"][1] == {"kind": "decisions"}
    assert row["used_by"][2]["id"] == "<redacted>"
    assert row["used_by"][3]["kind"] == "<redacted>"


# ---------------------------------------------------------------------------
# 安全读取与 logs cat（U14、U14b、U14d）
# ---------------------------------------------------------------------------

def test_cat_jsonl_redacts_valid_lines_and_hides_bad_and_long_lines(tmp_path):
    repo = make_repo(tmp_path)
    directory = attempt_dir(repo)
    lines = [
        '{"type":"agent_start"}',
        json.dumps({"api_key": FAKE}),
        json.dumps({TOKEN_KEY: "ordinary"}),
        "api_key=",
        FAKE,
        "",
        json.dumps({"big": "x" * 200}),
    ]
    (directory / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with mock.patch.object(kit_logs, "SAFE_MAX_LINE_BYTES", 100):
        code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl")
    assert code == 0, err
    page = json.loads(out)
    assert page["mode"] == "jsonl" and page["done"] is True
    got = {line["n"]: line for line in page["lines"]}
    assert got[1]["text"] == '{"type": "agent_start"}'  # json.dumps 的缺省格式
    assert "<redacted>" in got[2]["text"]
    assert got[4] == {"n": 4, "hidden": "not_json"}
    assert got[5] == {"n": 5, "hidden": "not_json"}
    assert got[6] == {"n": 6, "text": ""}
    assert got[7] == {"n": 7, "hidden": "too_long"}
    assert FAKE not in out and TOKEN_KEY not in out


def test_cat_text_redacts_the_whole_file_before_paging(tmp_path):
    repo = make_repo(tmp_path)
    directory = attempt_dir(repo)
    pem = "-----BEGIN PRIVATE KEY-----\nMIIBVAIBADANBgkqhkiG9w0BAQEFAASCAT4wggE6AgEAAkEA\n-----END PRIVATE KEY-----\n"
    body = "first line\napi_key=\n" + FAKE + "\n" + pem + "tail\n"
    (directory / "stderr.log").write_bytes(body.encode("utf-8"))  # 按字节写：Windows 的文本模式会改换行
    for limit in (5, 8, 13, 64, 4096):
        pages = all_pages(repo, "task-a/attempt-001", "stderr.log", limit)
        joined = "".join(page["text"] for page in pages)
        assert FAKE not in joined and "MIIBVAIBADAN" not in joined, limit
        assert joined == pd.redact_secrets(body), limit  # 分页首尾相接、不重复不遗漏
        assert all(page["mode"] == "text" for page in pages)


def test_cat_json_is_pretty_printed_and_redacted_by_key(tmp_path):
    repo = make_repo(tmp_path)
    directory = attempt_dir(repo)
    (directory / "meta.json").write_text(json.dumps({"task_id": "task-a", "auth": {"token": FAKE}}, indent=2),
                                         encoding="utf-8")
    code, out, err = cat(repo, "task-a/attempt-001", "meta.json")
    assert code == 0, err
    page = json.loads(out)
    assert FAKE not in page["text"]
    assert page["text"].count("\n") >= 4  # 仍是多行，没有被压成一行
    assert json.loads(page["text"])["task_id"] == "task-a"


def test_cat_long_lines_are_split_into_parts_without_gaps(tmp_path):
    repo = make_repo(tmp_path)
    directory = attempt_dir(repo)
    long_text = "".join(chr(ord("a") + i % 26) for i in range(1000))
    (directory / "log.txt").write_bytes(("short\n" + long_text + "\nend\n").encode("utf-8"))
    pages = all_pages(repo, "task-a/attempt-001", "log.txt", 100)
    assert "".join(page["text"] for page in pages) == "short\n" + long_text + "\nend\n"
    parts = [page for page in pages if "part" in page]
    assert parts and all(page["parts"] >= page["part"] >= 1 for page in parts)
    assert all(len(page["text"]) <= 100 for page in pages)
    # JSONL：一条合法的长记录也分片，片与片首尾相接
    record = {"type": "tool_result", "output": long_text}
    (directory / "events.jsonl").write_text('{"type":"a"}\n' + json.dumps(record) + "\n" + '{"type":"b"}\n',
                                            encoding="utf-8")
    pages = all_pages(repo, "task-a/attempt-001", "events.jsonl", 100)
    pieces = [line for page in pages for line in page["lines"] if line["n"] == 2]
    assert len(pieces) > 1 and [piece["part"] for piece in pieces] == list(range(1, len(pieces) + 1))
    assert "".join(piece["text"] for piece in pieces) == json.dumps(record, ensure_ascii=False)
    numbers = [line["n"] for page in pages for line in page["lines"]]
    assert numbers[0] == 1 and numbers[-1] == 3


def test_cat_cursor_is_bound_to_the_file_identity(tmp_path):
    repo = make_repo(tmp_path)
    directory = attempt_dir(repo)
    path = directory / "log.txt"
    path.write_text("".join("line %d\n" % i for i in range(50)), encoding="utf-8")
    code, out, err = cat(repo, "task-a/attempt-001", "log.txt", "--limit", "40")
    first = json.loads(out)
    assert not first["done"]
    replacement = directory / "log.txt.new"
    replacement.write_text("".join("other %d\n" % i for i in range(50)), encoding="utf-8")
    os.replace(str(replacement), str(path))  # 文件被替换：文件号变了
    code, out, err = cat(repo, "task-a/attempt-001", "log.txt", "--limit", "40", "--cursor", first["next_cursor"])
    assert code == 2 and "文件已变化" in err, (code, err)
    # JSONL 只增长时，旧游标继续有效
    events = directory / "events.jsonl"
    events.write_text("".join('{"n": %d}\n' % i for i in range(20)), encoding="utf-8")
    code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl", "--limit", "30")
    first = json.loads(out)
    with open(str(events), "a", encoding="utf-8") as handle:
        handle.write('{"n": 20}\n')
    pages = [first]
    cursor = first["next_cursor"]
    while cursor:
        code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl", "--limit", "30", "--cursor", cursor)
        assert code == 0, err
        page = json.loads(out)
        pages.append(page)
        cursor = None if page["done"] else page["next_cursor"]
    assert [line["n"] for page in pages for line in page["lines"]] == list(range(1, 22))


def test_cat_refuses_paths_outside_the_evidence_and_large_text(tmp_path):
    repo = make_repo(tmp_path)
    directory = attempt_dir(repo)
    (directory / "log.txt").write_text("hello\n", encoding="utf-8")
    (repo / ".agent" / "runs" / "task-a" / "outside.txt").write_text("x\n", encoding="utf-8")
    for rel in ("../outside.txt", "missing.txt", "/etc/passwd", "sub/../../outside.txt"):
        code, out, err = cat(repo, "task-a/attempt-001", rel)
        assert code == 2 and out == "", (rel, code, out)
    with mock.patch.object(kit_logs, "SAFE_MAX_TEXT_BYTES", 3):
        code, out, err = cat(repo, "task-a/attempt-001", "log.txt")
    assert code == 2 and out == "" and "超过" in err, (code, err)


# ---------------------------------------------------------------------------
# logs search（U14c）
# ---------------------------------------------------------------------------

def test_search_never_returns_masked_values(tmp_path):
    repo = make_repo(tmp_path)
    directory = attempt_dir(repo)
    (directory / "stderr.log").write_text("api_key=\n" + FAKE + "\n", encoding="utf-8")
    (directory / "events.jsonl").write_text(json.dumps({"api_key": FAKE}) + "\n" + "api_key=\n" + FAKE + "\n",
                                            encoding="utf-8")
    code, out, err = run(kit_logs.main, ["search", FAKE[:6]], repo)
    assert code == 0, err
    assert FAKE not in out and FAKE[:6] not in out
    code, out, err = run(kit_logs.main, ["search", FAKE[:6], "--json"], repo)
    assert code == 0, err
    data = json.loads(out)
    assert data["matches"] == [] and FAKE not in out
    # 正常的匹配照常有：字段齐全
    (directory / "summary.md").write_text("alpha one\nbeta\n", encoding="utf-8")
    code, out, err = run(kit_logs.main, ["search", "alpha", "--json"], repo)
    data = json.loads(out)
    assert data["matches"] == [{"task": "task-a", "attempt": "attempt-001", "path": "summary.md", "line": 1,
                                "text": "alpha one"}]
    assert (data["truncated"], data["skipped_links"], data["skipped_large"]) == (False, 0, 0)


# 闸二 D1-A 第 1 轮 B1：返回与否只取决于脱敏之后的文本；在原文上预筛会变成猜值的通道
def test_search_result_does_not_depend_on_masked_values(tmp_path):
    repo = make_repo(tmp_path)
    directory = attempt_dir(repo)
    (directory / "events.jsonl").write_text(json.dumps({"api_key": FAKE}) + "\n", encoding="utf-8")
    results = []
    for guess in (FAKE, "wrongvalue"):
        for argv in (["search", "%s|<redacted>" % guess, "--json"], ["search", "%s|<redacted>" % guess]):
            code, out, err = run(kit_logs.main, argv, repo)
            assert code == 0, err
            assert FAKE not in out
            results.append(json.loads(out)["matches"] if "--json" in argv else out)
    assert results[0] == results[2] and results[1] == results[3] and results[0], results


# ---------------------------------------------------------------------------
# 闸二 D1-A 第 1 轮：游标与读取的边界（B2、B3、S1、N1）
# ---------------------------------------------------------------------------

def test_cat_rejects_cursors_that_do_not_start_a_line(tmp_path):
    repo = make_repo(tmp_path)
    directory = attempt_dir(repo)
    events = directory / "events.jsonl"
    events.write_bytes(('api_key={"value":"%s"}\n' % FAKE).encode("utf-8"))
    code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl")
    page = json.loads(out)
    assert page["lines"] == [{"n": 1, "hidden": "not_json"}]
    fields = page["next_cursor"].split(":")
    forged = ":".join(fields[:1] + ["8"] + fields[2:])  # 偏移改到行中间：从这里起的后半截是合法的 JSON
    code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl", "--cursor", forged)
    assert code == 2 and FAKE not in out + err, (code, out, err)
    # 没有换行的尾行按写完读过之后，文件又在同一行接着写：旧游标落在了行中间，同样拒绝
    events.write_bytes(b'{"x": 1}\napi_key=')
    code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl")
    page = json.loads(out)
    # 文件没变时，停在没有换行的末尾的游标仍然有效：什么也不再给
    code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl", "--cursor", page["next_cursor"])
    assert code == 0 and json.loads(out)["lines"] == [] and json.loads(out)["done"], (code, out, err)
    with open(str(events), "ab") as handle:
        handle.write(('{"value":"%s"}\n' % FAKE).encode("utf-8"))
    code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl", "--cursor", page["next_cursor"])
    assert code == 2 and FAKE not in out + err, (code, out, err)


def test_cat_jsonl_rewrites_invalidate_the_cursor(tmp_path):
    repo = make_repo(tmp_path)
    directory = attempt_dir(repo)
    events = directory / "events.jsonl"
    events.write_bytes(('{"output": "%s"}\n' % ("a" * 500)).encode("utf-8"))
    code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl", "--limit", "100")
    first = json.loads(out)
    assert not first["done"] and first["lines"][0]["part"] == 1
    info = os.stat(str(events))
    events.write_bytes(('{"output": "%s"}\n' % ("b" * 500)).encode("utf-8"))  # 原地改写，长度不变
    os.utime(str(events), ns=(info.st_atime_ns, info.st_mtime_ns + 10 ** 9))
    code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl", "--limit", "100", "--cursor", first["next_cursor"])
    assert code == 2 and "文件已变化" in err, (code, out, err)
    # 改写这一行之后又在末尾追加：文件变长了，但这一行已经变了，旧游标同样失效
    events.write_bytes(('{"output": "%s"}\n' % ("a" * 500)).encode("utf-8"))
    code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl", "--limit", "100")
    first = json.loads(out)
    events.write_bytes(('{"output": "%s"}\n{"more": 1}\n' % ("c" * 500)).encode("utf-8"))
    code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl", "--limit", "100", "--cursor", first["next_cursor"])
    assert code == 2 and "文件已变化" in err, (code, out, err)
    # 改写已经读过、又在核对窗口之外的那一段（长度不变）：只有修改时间能发现
    lines = ['{"line": "%s"}' % ("x" * 90)] * 80
    events.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl", "--limit", "6000")
    first = json.loads(out)
    assert not first["done"] and int(first["next_cursor"].split(":")[1]) > kit_logs.CURSOR_WINDOW + 200
    info = os.stat(str(events))
    lines[0] = '{"line": "%s"}' % ("y" * 90)
    events.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    os.utime(str(events), ns=(info.st_atime_ns, info.st_mtime_ns + 10 ** 9))
    code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl", "--limit", "6000", "--cursor", first["next_cursor"])
    assert code == 2 and "文件已变化" in err, (code, out, err)


def test_cat_reads_are_bounded(tmp_path):
    import tracemalloc
    import types
    repo = make_repo(tmp_path)
    directory = attempt_dir(repo)
    (directory / "log.txt").write_bytes((b"x" * 1023 + b"\n") * 8192)  # 8 MiB，短行：脱敏本身很快
    real_lstat = os.lstat

    def stale_lstat(path, *args, **kwargs):  # 检查大小时文件还小，读的时候已经变大
        info = real_lstat(path, *args, **kwargs)
        if str(path).endswith("log.txt"):
            return types.SimpleNamespace(st_mode=info.st_mode, st_size=10, st_mtime_ns=info.st_mtime_ns,
                                         st_ino=info.st_ino)
        return info

    with mock.patch.object(kit_logs, "SAFE_MAX_TEXT_BYTES", 1024 * 1024), \
            mock.patch.object(kit_logs.os, "lstat", stale_lstat):
        tracemalloc.start()
        try:
            code, out, err = cat(repo, "task-a/attempt-001", "log.txt")
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
    assert code == 2 and out == "" and "超过" in err, (code, out[:100], err)
    assert peak < 4 * 1024 * 1024, peak  # 只读了上限加 1 字节，没有把整份读进内存
    # 空行也计分页成本：一页不能塞进无数个空行
    (directory / "events.jsonl").write_bytes(b"\n" * 1000)
    code, out, err = cat(repo, "task-a/attempt-001", "events.jsonl", "--limit", "100")
    page = json.loads(out)
    assert 1 <= len(page["lines"]) <= 100 // 16 + 1 and not page["done"], len(page["lines"])


# 一长串 [\w.-]（十六进制、base64url）原来让键值规则在每个位置都回溯一遍：20 万个字符要几十分钟。
# 在子进程里跑、超时就失败，免得回归时把整个测试挂住。
def test_cat_redaction_time_is_linear_in_long_runs(tmp_path):
    repo = make_repo(tmp_path)
    directory = attempt_dir(repo)
    dump = "deadbeef" * 25000
    record = {"output": "Ab9-_" * 40000}
    (directory / "dump.txt").write_bytes((dump + "\n").encode("utf-8"))
    (directory / "events.jsonl").write_bytes((json.dumps(record) + "\n").encode("utf-8"))
    for rel, expected in (("dump.txt", dump + "\n"), ("events.jsonl", json.dumps(record))):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "kit_logs.py"), "--repo", str(repo), "cat",
                                 "task-a/attempt-001", rel, "--json"], capture_output=True, timeout=60)
        assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
        page = json.loads(result.stdout.decode("utf-8"))
        assert (page["text"] if rel == "dump.txt" else page["lines"][0]["text"]) == expected  # 没有误遮


def test_cat_text_parts_are_stable_for_one_line(tmp_path):
    repo = make_repo(tmp_path)
    directory = attempt_dir(repo)
    (directory / "log.txt").write_bytes(("short\n" + "a" * 1000 + "\nend\n").encode("utf-8"))
    pages = all_pages(repo, "task-a/attempt-001", "log.txt", 100)
    fragments = [page for page in pages if "part" in page]
    assert [page["part"] for page in fragments] == list(range(1, 11))
    assert {page["parts"] for page in fragments} == {10}
    assert pages[-1]["text"].startswith("\n") and "part" not in pages[-1]


# ---------------------------------------------------------------------------
# status --json 的 live（U9 的命令行一半）
# ---------------------------------------------------------------------------

def test_status_json_adds_live_for_running_attempts_only(tmp_path):
    repo = make_repo(tmp_path)
    running = attempt_dir(repo, "task-a", 1, state="RUNNING")
    (running / "events.jsonl").write_bytes(b'{"type":"tool_execution_end"}\n' * 3 + b'{"type":"message_update"}\n')
    attempt_dir(repo, "task-b", 1, state="NEEDS_REVIEW")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = pd.main(["--repo", str(repo), "status", "--json"])
    assert code == 0
    rows = {row["attempt"].split("/")[0]: row for row in json.loads(out.getvalue())}
    live = rows["task-a"]["live"]
    assert (live["tool_calls"], live["deltas_since_last_tool"], live["long_idle"]) == (3, 1, False)
    assert rows["task-a"]["events_ok"] == "live:3t"  # 现有字段不变
    assert "live" not in rows["task-b"]


# ---------------------------------------------------------------------------
# config validate --json
# ---------------------------------------------------------------------------

def test_config_validate_json(tmp_path):
    repo = make_repo(tmp_path)
    config = repo / ".agent" / "dispatch.config.json"
    config.write_text(json.dumps({"kill_grace_seconds": 10}), encoding="utf-8")
    code, out, err = run(kit_config.main, ["validate", "--json"], repo)
    assert code == 0, err
    data = json.loads(out)
    assert (data["valid"], data["errors"]) == (True, [])
    config.write_text(json.dumps({"kill_grace_seconds": "x", "_note": "sk-" + "n" * 24}), encoding="utf-8")
    code, out, err = run(kit_config.main, ["validate", "--json"], repo)
    assert code == 1
    data = json.loads(out)
    assert data["valid"] is False and data["errors"] and "n" * 24 not in out
