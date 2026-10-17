"""pi CLI（0.87 JSON 模式）的桩程序：不调用模型，供 tests/test_dispatch.py 验证 pi_dispatch.py。

场景由 STUB_SCENARIO 选择：ok、scope、error、hang、commit、outside、touchmain、model、noreport、nosettle、startfail、
readplan、typo、planner、ambiguous、conflict、checkonly、textcall、tmpclean。
STUB_PTL 设置时在 assistant 消息中回报 providerThinkingLevel；STUB_NOCOST=1 时不给出费用；
STUB_AUTH_DETAIL 设置时，auth check 的输出里带上这段文字（例如错误信息里带出的凭据）。
STUB_LIST_FAIL=1 时 --list-models 失败退出，错误里带出 models.json 的片段；--list-models 与 pi 0.87 一样按参数筛选，
STUB_MODELS 为空或没有匹配时输出一句说明，不输出表格。
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
args = sys.argv[1:]


def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def opt(name, default=None):
    if name in args:
        i = args.index(name)
        return args[i + 1] if i + 1 < len(args) else default
    return default


if "--help" in args:
    print((HERE / "stub_pi_help.txt").read_text(encoding="utf-8"))
    sys.exit(0)
if "--version" in args:
    print("0.87.0")
    sys.exit(0)
if args and args[0] == "auth":
    status = os.environ.get("STUB_AUTH", "ready")
    auth_report = {"status": status, "provider": opt("--provider"), "model": opt("--model")}
    if os.environ.get("STUB_AUTH_DETAIL"):
        auth_report["error"] = os.environ["STUB_AUTH_DETAIL"]
    print(json.dumps(auth_report))
    sys.exit(0 if status == "ready" else 1)
if "--list-models" in args:
    if os.environ.get("STUB_LIST_FAIL") == "1":  # 例如沙箱阻止 pi 读取 ~/.pi/agent；Node 的 JSON 错误会带出输入片段
        sys.stderr.write("Warning: errors loading models.json:\n")
        sys.stderr.write('Unexpected token \'D\', "{"apiKey": DEMO_TOKEN_FOR_REVIEW}" is not valid JSON\n')
        sys.stderr.write("Error: EPERM: operation not permitted, open '~/.pi/agent/models.json'\n")
        sys.exit(1)
    pattern = opt("--list-models")
    pairs = [pair.split() for pair in os.environ.get("STUB_MODELS", "step step-5-preview").split(";") if pair.strip()]
    if not pairs:
        print("No models available. Use /login to log into a provider via OAuth or API key. See:")
        print("  /pi/docs/providers.md")
        sys.exit(0)
    shown = [pair for pair in pairs if not pattern or pattern.startswith("-") or pattern in " ".join(pair)]
    if not shown:
        print('No models matching "%s"' % pattern)
        sys.exit(0)
    print("provider    model                     context  max-out  thinking  images")
    for provider, model in shown:
        print("%-11s %-25s 256K     230.4K   yes       no" % (provider, model))
    sys.exit(0)

scenario = os.environ.get("STUB_SCENARIO", "ok")
provider, model, thinking = opt("--provider"), opt("--model"), opt("--thinking")
files = [a[1:] for a in args if a.startswith("@")]
prompt = "".join(Path(f).read_text(encoding="utf-8") for f in files)
cwd = Path.cwd()
emit({"type": "session", "version": 3, "id": "stub", "timestamp": "2026-09-22T00:00:00Z", "cwd": str(cwd)})
if scenario == "startfail":
    sys.stderr.write("Error: No API key found for provider %s\n" % provider)
    sys.exit(1)
messages = [a for a in args if not a.startswith("-") and not a.startswith("@")
            and args[args.index(a) - 1] not in ("--provider", "--model", "--thinking", "--tools", "--mode")]
if not files and messages:
    text = messages[-1]
    emit({"type": "agent_start"})
    if "smoke.txt" in text:
        emit({"type": "tool_execution_start", "toolCallId": "w", "toolName": "write", "args": {"path": "smoke.txt"}})
        (cwd / "smoke.txt").write_text("PI_TOOL_OK", encoding="utf-8")
        emit({"type": "tool_execution_end", "toolCallId": "w", "toolName": "write", "result": {}, "isError": False})
        emit({"type": "tool_execution_start", "toolCallId": "r", "toolName": "read", "args": {"path": "smoke.txt"}})
        emit({"type": "tool_execution_end", "toolCallId": "r", "toolName": "read", "result": {}, "isError": False})
        reply = "DONE"
    else:
        reply = "PI_SMOKE_OK"
    msg = {"role": "assistant", "content": [{"type": "text", "text": reply}], "provider": provider, "model": model,
           "stopReason": "stop",
           "usage": {"input": 10, "output": 2, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 12,
                     "cost": {"total": 0.00001}}}
    emit({"type": "message_end", "message": msg})
    emit({"type": "agent_end", "messages": [], "willRetry": False})
    emit({"type": "agent_settled"})
    sys.exit(0)
if "TASK:" not in prompt or "执行说明" not in prompt:
    sys.stderr.write("stub: prompt did not include plan and instruction\n")
    sys.exit(3)

actual_model = "stepfun/step-3.5-flash" if scenario == "model" else model
usage = {"input": 1000, "output": 200, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 1200,
         "cost": {"input": 0.0002, "output": 0.00023, "cacheRead": 0, "cacheWrite": 0, "total": 0.00043}}
if os.environ.get("STUB_NOCOST") == "1":
    usage["cost"] = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "total": 0}


def assistant(content, stop, error=None):
    msg = {"role": "assistant", "content": content, "api": "anthropic-messages", "provider": provider,
           "model": actual_model, "responseModel": actual_model, "usage": usage, "stopReason": stop, "timestamp": 1}
    if os.environ.get("STUB_PTL"):  # 真实 Pi 只在特定 compat 条件下回报这个字段
        msg["providerThinkingLevel"] = os.environ["STUB_PTL"]
    if error:
        msg["errorMessage"] = error
    return msg


def tool(name, path, action):
    emit({"type": "tool_execution_start", "toolCallId": "c1", "toolName": name, "args": {"path": path}})
    action()
    emit({"type": "tool_execution_end", "toolCallId": "c1", "toolName": name, "result": {}, "isError": False})


emit({"type": "agent_start"})
emit({"type": "turn_start"})
emit({"type": "message_start", "message": {"role": "system", "content": ""}})
emit({"type": "message_end", "message": {"role": "system", "content": "", "sections": {"base": "x", "context": "y"}}})
first = assistant([{"type": "toolCall", "id": "c1", "name": "write", "arguments": {}}], "toolUse")
emit({"type": "message_start", "message": first})
emit({"type": "message_update", "usage": usage, "assistantMessageEvent": {"type": "text_delta", "delta": "x"}})
emit({"type": "message_end", "message": first})


def write(rel, text):
    path = cwd / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


tool("write", "src/normalize.py", lambda: write("src/normalize.py",
     "def normalize(q):\n    return ' '.join(q.split()).lower()\n"))
tool("write", "tests/test_normalize.py", lambda: write("tests/test_normalize.py",
     "import unittest\nfrom normalize import normalize\n\n\nclass T(unittest.TestCase):\n"
     "    def test_spaces(self):\n        self.assertEqual(normalize('  A  B '), 'a b')\n\n"
     "    def test_empty(self):\n        self.assertEqual(normalize(''), '')\n"))
if scenario == "scope":
    tool("edit", "README.md", lambda: write("README.md", "# changed\n"))
    tool("edit", "package.json", lambda: write("package.json", '{"name":"t","dependencies":{"left-pad":"1"}}\n'))
    write(".env", "SECRET=1\n")
    emit({"type": "tool_execution_start", "toolCallId": "c9", "toolName": "bash",
          "args": {"command": "git push origin HEAD"}})
    emit({"type": "tool_execution_end", "toolCallId": "c9", "toolName": "bash", "result": {}, "isError": True})
if scenario == "commit":
    subprocess.run(["git", "add", "-A"], cwd=str(cwd), check=True)
    subprocess.run(["git", "-c", "user.name=stub", "-c", "user.email=s@s", "commit", "-qm", "stub"],
                   cwd=str(cwd), check=True)
if scenario == "tmpclean":  # 删除自建的 mktemp 临时目录（照常列为可疑）；一条删除其子路径的长命令（可疑）；
    # 用 tempfile 自建目录并切换进去（Codex 规划端试跑的原样命令，复审关注）；用绝对路径 cd 进自己的 worktree
    # （测试的 worktree 建在系统临时目录下，不能算作使用临时目录）
    safe = ('TMPD="$(mktemp -d)"\ncat > "$TMPD/cfg.yaml" <<\'EOF\'\na: 1\nEOF\npython -m app --output "$TMPD/out"\n'
            'python -c "print(open(\'$TMPD/out/x\').read())"\nrm -rf "$TMPD"')
    risky = "T=$(mktemp -d)\n" + "\n".join("echo step %d %s" % (i, "x" * 60) for i in range(5)) + '\nrm -rf "$T"/build'
    cache = 'rm -rf src/__pycache__ tests/__pycache__ && git status --porcelain'
    tmppy = ('PYTHONIOENCODING=utf-8 python -c "\nimport os, tempfile, pathlib\nd = tempfile.mkdtemp()\nos.chdir(d)\n'
             'print(os.path.abspath(\'x\'))\n"')
    own = 'cd "%s" && git status --porcelain' % str(cwd).replace("\\", "/")
    for cid, command in (("m1", safe), ("m2", risky), ("m3", cache), ("m4", tmppy), ("m5", own)):
        emit({"type": "tool_execution_start", "toolCallId": cid, "toolName": "bash", "args": {"command": command}})
        emit({"type": "tool_execution_end", "toolCallId": cid, "toolName": "bash", "result": {}, "isError": False})
if scenario == "touchmain":  # 改写主工作区中运行前就已经是脏文件的 README.md
    (Path(os.environ["STUB_MAIN_REPO"]) / "README.md").write_text("rewritten by executor", encoding="utf-8")
if scenario == "tempsequence":  # Evidence only: never execute the external write/delete commands.
    commands = ['T=$(mktemp -d)\necho "$T" >/tmp/backup_dir',
                'T=$(cat /tmp/backup_dir); run "$T"',
                'rm -rf "$T" /tmp/backup_dir; echo CLEANED',
                'T=$(mktemp -d); echo ' + 'x' * 200 + '; echo "$T" >/tmp/backup_dir']
    commands += ['T=$(mktemp -d); run "$T"; rm -rf "$T"'] * 50
    for i, command in enumerate(commands):
        emit({"type": "tool_execution_start", "toolCallId": "ts%d" % i, "toolName": "bash", "args": {"command": command}})
        emit({"type": "tool_execution_end", "toolCallId": "ts%d" % i, "toolName": "bash", "result": {}, "isError": False})
if scenario == "outside":
    leak = Path(os.environ["STUB_MAIN_REPO"]) / "leak.txt"
    tool("write", str(leak), lambda: leak.write_text("leak\n", encoding="utf-8"))
if scenario == "readplan":  # 执行器重新读取随消息附上的 plan.md（位于 attempt 运行目录）
    emit({"type": "tool_execution_start", "toolCallId": "p1", "toolName": "read", "args": {"path": files[0]}})
    emit({"type": "tool_execution_end", "toolCallId": "p1", "toolName": "read", "result": {}, "isError": False})
if scenario == "typo":  # 手写绝对路径时拼错目录名：路径不存在，调用失败
    bogus = str(cwd.parent / (cwd.name + "-typo") / "src" / "normalize.py")
    emit({"type": "tool_execution_start", "toolCallId": "t1", "toolName": "edit", "args": {"path": bogus}})
    emit({"type": "tool_execution_end", "toolCallId": "t1", "toolName": "edit", "result": {}, "isError": True})
if scenario == "planner":  # 模拟规划器在运行期间往主工作区的 .agent/plans/ 写了新合同
    note = Path(os.environ["STUB_MAIN_REPO"]) / ".agent" / "plans" / "next-task.v1.md"
    note.write_text("# TASK: next-task\n", encoding="utf-8")
if scenario in ("ambiguous", "conflict"):  # 执行器在推理中发现合同前后矛盾，并自行选了一种
    thought = assistant([{"type": "thinking", "thinking": "The contract says A in the behavior section, but step 4 "
                          "says B. This is ambiguous. I'll follow the behavior section."},
                         {"type": "toolCall", "id": "c2", "name": "read", "arguments": {}}], "toolUse")
    emit({"type": "message_end", "message": thought})
if scenario == "checkonly":  # 只是在检查合同有没有矛盾，结论是没有（Codex 规划端试跑的原文）；不是最后一条消息
    thought = assistant([{"type": "thinking", "thinking": "contract_conflicts: none found. Let me double check for "
                          "inconsistencies between plan.md and machine contract summary: - plan says X"},
                         {"type": "text", "text": "### 合同矛盾\n未发现。"},
                         {"type": "toolCall", "id": "c3", "name": "read", "arguments": {}}], "toolUse")
    emit({"type": "message_end", "message": thought})
if scenario == "hang":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    (cwd / "child.pid").write_text(str(child.pid), encoding="utf-8")
    time.sleep(600)
emit({"type": "turn_end", "message": first, "toolResults": []})
emit({"type": "turn_start"})
report = {"task_id": "normalize-query", "plan_version": 1, "attempt_id": "x", "executor_status": "completed",
          "changed_files": ["src/normalize.py", "tests/test_normalize.py"],
          "self_checks": [{"id": "V01", "command": "python run_tests.py", "reported_exit_code": 0}],
          "dod": [{"id": "D01", "status": "done"}], "unresolved_questions": [], "limitations": []}
if scenario == "conflict":
    report["contract_conflicts"] = [{"quotes": ["行为说明：A", "步骤 4：B"], "adopted": "按行为说明实现",
                                     "reason": "两处对同一行为说法不同"}]
    report["dod"] = [{"id": "D01", "status": "blocked", "note": "合同前后矛盾，待裁定"}]
text = "## 执行报告\nD01 完成。\n\n```json\n%s\n```\n" % json.dumps(report, ensure_ascii=False, indent=2)
if scenario == "noreport":
    text = "Done."
if scenario == "textcall":  # 模型把工具调用写进了正文（Hermes 风格），Pi 不会执行
    text = "Let me fix the tests:<tool_call>\n<function=edit>\n<parameter=path>\ntests/x.py\n</parameter>\n</function>\n</tool_call>"
if scenario == "error":
    final = assistant([], "error", "429 rate limited")
else:
    final = assistant([{"type": "text", "text": text}], "stop")
emit({"type": "message_start", "message": final})
emit({"type": "message_end", "message": final})
emit({"type": "turn_end", "message": final, "toolResults": []})
emit({"type": "agent_end", "messages": [], "willRetry": False})
if scenario != "nosettle":
    emit({"type": "agent_settled"})
sys.exit(0)
