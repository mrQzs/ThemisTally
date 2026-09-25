"""pi_dispatch.py 的端到端自测：用 stub_pi.py 模拟 Pi 0.87 的 JSON 事件流，不调用任何模型。

用法：
    python tests/test_dispatch.py                 # 运行全部场景
    python tests/test_dispatch.py test_timeout    # 只运行指定场景
    python tests/test_dispatch.py --keep          # 保留本次的临时仓库，便于排查

需要：Python 3.8+、git、bash（Windows 上为 Git Bash）。每次运行都在系统临时目录下新建一个唯一目录
（pi-dispatch-e2e-*），只清理本次创建的目录，可以并行运行。不会读写你的真实仓库，也不会调用 pi。
"""
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
WORK = Path(tempfile.mkdtemp(prefix="pi-dispatch-e2e-"))
PY = sys.executable
PROG = Path(PY).stem
IS_WINDOWS = os.name == "nt"
BASE_ENV = dict(os.environ)
BASE_ENV["PI_DISPATCH_PI_CMD"] = json.dumps([PY, str(HERE / "stub_pi.py")])
for _name in ("PI_EXEC_PROVIDER", "PI_EXEC_MODEL", "PI_EXEC_THINKING", "STUB_SCENARIO", "STUB_MODELS", "STUB_AUTH",
              "STUB_PTL", "STUB_NOCOST", "STUB_LIST_FAIL", "STUB_AUTH_DETAIL"):
    BASE_ENV.pop(_name, None)
RESULTS = []
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
sys.path.insert(0, str(KIT / "scripts"))
import pi_dispatch as pd  # noqa: E402


def sh(cmd, cwd, env=None, check=True):
    proc = subprocess.run(cmd, cwd=str(cwd), env=env or BASE_ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = proc.stdout.decode("utf-8", "replace")
    if check and proc.returncode != 0:
        raise AssertionError("command failed %s -> %s\n%s" % (cmd, proc.returncode, out))
    return proc.returncode, out


def git(repo, *args):
    return sh(["git"] + list(args), repo)[1].strip()


def tool(repo, *args, env=None):
    merged = dict(BASE_ENV)
    merged.update(env or {})
    return sh([PY, "scripts/pi_dispatch.py"] + list(args), repo, env=merged, check=False)


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else "  <- " + str(detail)[:1500]))


def alive(pid):
    pid = int(pid)
    if IS_WINDOWS:
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH"], stdout=subprocess.PIPE).stdout
        return str(pid) in out.decode("utf-8", "replace").split()
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:  # 已退出但尚未被回收的僵尸进程视为不存活
        with open("/proc/%d/stat" % pid) as handle:
            return handle.read().split(") ")[-1][:1] != "Z"
    except OSError:
        return True


def kill_hard(pid):
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.kill(int(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def remove_tree(path):
    """删除测试目录；Windows 上 git 对象文件是只读的，需要先去掉只读属性。"""
    def on_error(func, target, _info):
        os.chmod(target, 0o700)
        func(target)
    if Path(path).exists():
        shutil.rmtree(str(path), onerror=on_error)


def default_checks():
    return [{"id": "V01", "argv": [PY, "run_tests.py"], "cwd": ".", "timeout_seconds": 120,
             "required": True, "expected_exit_code": 0, "output_must_match": ["Tests [1-9][0-9]* passed"]}]


def contract(base, ver=1, attempts=3, thinking="high", **over):
    data = {
        "schema_version": 1, "task_id": "normalize-query", "plan_version": ver, "repository": "test",
        "base_sha": base, "risk_level": "low",
        "authorization": {"executor": ["local_edit", "local_test"], "integration": ["local_branch"]},
        "executor": {"provider": "step", "model": "step-5-preview", "thinking": thinking,
                     "tools": ["read", "grep", "find", "ls", "edit", "write", "bash"], "context_files": "project"},
        "scope": {"allowed_modified_files": ["src/normalize.py"], "allowed_new_files": ["tests/test_normalize.py"],
                  "allowed_deleted_files": [], "forbidden_paths": ["package.json"], "dependency_changes": "forbidden"},
        "setup": [],
        "checks": default_checks(),
        "definition_of_done": [{"id": "D01", "text": "行为正确", "evidence": ["V01"]},
                               {"id": "D02", "text": "范围合规", "evidence": ["scope"]}],
        "budget": {"max_attempts_total": attempts, "max_wall_seconds_per_attempt": 600,
                   "max_wall_seconds_total": 1800, "cost_budget": None},
    }
    data.update(over)
    return data


def build_md(c):
    """按合同 JSON 生成与之一致的 Markdown（校验器会比较两者）。"""
    ex = c["executor"] if isinstance(c.get("executor"), dict) else {}
    auth = c["authorization"] if isinstance(c.get("authorization"), dict) else {}
    scope = c["scope"] if isinstance(c.get("scope"), dict) else {}
    budget = c["budget"] if isinstance(c.get("budget"), dict) else {}
    join = lambda values: ", ".join(str(v) for v in values) if isinstance(values, list) else str(values)  # noqa
    lines = ["# TASK: %s" % c["task_id"], "", "## Identity", "- plan_version: %s" % c["plan_version"],
             "- repository: test", "- base_sha: %s" % c["base_sha"], "- risk_level: %s" % c["risk_level"],
             "- authorized_actions: %s" % join(auth.get("executor", [])),
             "- integration_actions: %s" % (join(auth.get("integration", [])) or "none"),
             "- executor: %s/%s · thinking %s" % (ex.get("provider"), ex.get("model"), ex.get("thinking")), "",
             "## Goal", "normalize() 折叠空白并转小写。", "", "## Non-goals", "- 不改其他模块。", "",
             "## Repository facts", "- src/normalize.py 中的 normalize(q)。", "", "## Scope"]
    for key in ("allowed_modified_files", "allowed_new_files", "allowed_deleted_files", "forbidden_paths"):
        lines.append("- %s: %s" % (key, join(scope.get(key, [])) or "无"))
    lines += ["- dependency_changes: %s" % scope.get("dependency_changes", "forbidden"), "",
              "## Behavior contract", "- '  A  B ' -> 'a b'", "", "## Steps", "1. 实现。", "",
              "## Validation commands"]
    for item in c.get("checks", []) if isinstance(c.get("checks"), list) else []:
        if isinstance(item, dict) and isinstance(item.get("argv"), list) and item["argv"]:
            lines.append("- %s: %s %s" % (item.get("id"), Path(str(item["argv"][0])).stem,
                                          " ".join(str(a) for a in item["argv"][1:])))
    lines += ["", "## Definition of done"]
    for item in c.get("definition_of_done", []):
        if isinstance(item, dict):
            lines.append("- %s: %s；证据：%s。" % (item.get("id"), item.get("text"), join(item.get("evidence", []))))
    lines += ["", "## Stop conditions", "- 需要改范围外文件。", "", "## Budget"]
    for key in ("max_attempts_total", "max_wall_seconds_per_attempt", "max_wall_seconds_total"):
        lines.append("- %s: %s" % (key, budget.get(key)))
    lines += ["", "## Report back", "- 最后一条消息为执行报告。", "", "## Forbidden", "- 不提交。", ""]
    return "\n".join(lines)


def write_config(repo, **extra):
    config = {"worktree_root": str(WORK / "worktrees")}
    config.update(extra)
    (repo / ".agent").mkdir(exist_ok=True)
    (repo / ".agent/dispatch.config.json").write_text(json.dumps(config), encoding="utf-8")


def make_repo(name, attempts=3, thinking="high", gitignore=".agent/runs/\n.env\nnode_modules/\n", **over):
    repo = WORK / name
    remove_tree(repo)
    for sub in ("src", "tests", "scripts"):
        (repo / sub).mkdir(parents=True)
    sh(["git", "init", "-q"], repo)
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "tester")
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / "src/normalize.py").write_text("def normalize(q):\n    return q\n", encoding="utf-8")
    (repo / "run_tests.py").write_text(
        "import sys, unittest\nsys.path.insert(0, 'src')\n"
        "r = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('tests'))\n"
        "ok = r.wasSuccessful() and r.testsRun > 0\n"
        "print('Tests %d passed' % r.testsRun if ok else 'FAILED')\nsys.exit(0 if ok else 1)\n", encoding="utf-8")
    (repo / "README.md").write_text("# Test\n", encoding="utf-8")
    (repo / "package.json").write_text('{"name":"t","dependencies":{}}\n', encoding="utf-8")
    (repo / ".gitignore").write_text(gitignore, encoding="utf-8")
    (repo / "AGENTS.md").write_text("# AGENTS\n只改合同允许的文件。\n", encoding="utf-8")
    for name_ in ("pi_dispatch.py", "dispatch-pi.sh"):
        shutil.copy(str(KIT / "scripts" / name_), str(repo / "scripts" / name_))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    base = git(repo, "rev-parse", "HEAD")
    write_config(repo)
    write_plan(repo, base, 1, attempts, thinking, **over)
    return repo, base


def write_plan(repo, base, ver, attempts=3, thinking="high", md=None, raw=None, **over):
    plans = repo / ".agent/plans"
    plans.mkdir(parents=True, exist_ok=True)
    data = contract(base, ver, attempts, thinking, **over)
    (plans / ("normalize-query.v%d.md" % ver)).write_text(md if md is not None else build_md(data), encoding="utf-8")
    (plans / ("normalize-query.v%d.json" % ver)).write_text(
        json.dumps(raw if raw is not None else data, ensure_ascii=False, indent=2), encoding="utf-8")


def rd(repo, n=1):
    return repo / (".agent/runs/normalize-query/attempt-%03d" % n)


def state(repo, n=1):
    return json.loads((rd(repo, n) / "state.json").read_text(encoding="utf-8"))["state"]


def jload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def review(repo, verdict):
    path = repo / ".agent/reviews/r.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# REVIEW\n\nVerdict: %s\n" % verdict, encoding="utf-8")
    return str(path)


def worktree_of(repo, n=1):
    return Path(jload(rd(repo, n) / "meta.json")["worktree"])


def run_ok(repo, n=1, **env):
    tool(repo, "prepare", "normalize-query.v1")
    env.setdefault("STUB_SCENARIO", "ok")
    return tool(repo, "run", "normalize-query/attempt-%03d" % n, env=env)


# ---------------------------------------------------------------------------
# 场景
# ---------------------------------------------------------------------------

def test_happy():
    repo, base = make_repo("happy")
    code, out = tool(repo, "validate", "normalize-query.v1")
    check("validate ok", code == 0, out)
    code, out = run_ok(repo)
    check("run ok -> NEEDS_REVIEW", code == 0 and state(repo) == "NEEDS_REVIEW", out)
    ev = jload(rd(repo) / "events-summary.json")
    check("events complete via agent_settled", ev["complete"] and ev["terminal_event"] == "agent_settled", ev)
    check("usage sums assistant message_end only",
          ev["usage"]["input"] == 2000 and ev["cost"]["status"] == "estimated", ev["usage"])
    check("thinking not reported -> evidence says so, no problem",
          ev["provider_thinking_levels"] == [] and ev["thinking_evidence"].startswith("not_reported") and ev["ok"], ev)
    instruction = (rd(repo) / "instruction.md").read_text(encoding="utf-8")
    check("instruction has machine summary from JSON", "机器合同摘要" in instruction
          and "`src/normalize.py`" in instruction and "run_tests.py" in instruction, instruction[-800:])
    reservation = jload(rd(repo) / "claim" / "reservation.json")
    check("claim records reserved timeout", reservation["timeout_seconds"] == 600, reservation)
    cand = jload(rd(repo) / "candidate.json")
    check("candidate roundtrip verified", cand["patch_roundtrip_verified"], cand)
    code, out = tool(repo, "check", "normalize-query/attempt-001")
    check("in-place check passes", code == 0, out)
    code, out = tool(repo, "check", "normalize-query/attempt-001", "--fresh")
    fresh = jload(rd(repo) / "checks/02/checks.json")
    check("fresh check passes in clean copy and removes it", code == 0 and fresh["mode"] == "fresh"
          and not Path(fresh["workspace"]).exists(), out)
    code, out = tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "PASS", "--review",
                     review(repo, "REVISE"))
    check("verdict line mismatch refused", code != 0, out)
    code, out = tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "PASS", "--review",
                     review(repo, "PASS"), "--human-minutes", "4")
    check("PASS accepted", code == 0 and state(repo) == "PASS", out)
    code, out = tool(repo, "branch", "normalize-query/attempt-001")
    check("branch tree == candidate tree", code == 0 and
          git(repo, "rev-parse", "pi/normalize-query-v1-a001^{tree}") == cand["tree"], out)
    check("branch parent == base", git(repo, "rev-parse", "pi/normalize-query-v1-a001^") == base)
    subject = git(repo, "log", "-1", "--format=%s", "pi/normalize-query-v1-a001")
    check("branch subject without a title", subject == "normalize-query: Pi 候选 v1 attempt 001", subject)
    code, out = tool(repo, "metrics")
    check("metrics first PASS 100%", "| 首次验收通过率（PASS） | 100% |" in out, out)
    worktree = worktree_of(repo)
    code, out = tool(repo, "cleanup", "normalize-query/attempt-001")
    check("cleanup removes worktree", code == 0 and not worktree.exists(), out)
    code, out = tool(repo, "mark", "normalize-query/attempt-001", "INTEGRATED", "--ref", "local-branch")
    check("mark integrated", code == 0 and state(repo) == "INTEGRATED", out)


def test_candidate_drift_and_artifacts():
    """Codex #1：检查前出现的候选之外文件不能被忽略；缓存类文件允许；检查自己产生的文件会让 G4 失败。"""
    repo, base = make_repo("drift")
    run_ok(repo)
    worktree = worktree_of(repo)
    (worktree / "src" / "helper.py").write_text("X = 1\n", encoding="utf-8")
    code, out = tool(repo, "check", "normalize-query/attempt-001")
    check("in-place check refuses unexpected extra file", code == pd.EXIT_DRIFT and "helper.py" in out, out)
    code, out = tool(repo, "check", "normalize-query/attempt-001", "--fresh")
    check("fresh check ignores worktree extras", code == 0, out)
    (worktree / "src" / "helper.py").unlink()
    cache = worktree / "src" / "__pycache__"
    cache.mkdir()
    (cache / "normalize.cpython-312.pyc").write_bytes(b"\0")
    code, out = tool(repo, "check", "normalize-query/attempt-001")
    check("python cache files are allowed artifacts", code == 0, out)
    repo2, base2 = make_repo("checkwrites", checks=[
        {"id": "V01", "argv": [PY, "-c", "open('report.txt','w').write('x'); print('Tests 1 passed')"],
         "cwd": ".", "timeout_seconds": 60, "required": True, "expected_exit_code": 0,
         "output_must_match": ["Tests [1-9][0-9]* passed"]}])
    run_ok(repo2)
    code, out = tool(repo2, "check", "normalize-query/attempt-001")
    check("check creating unexpected file -> exit 1", code == 1 and "report.txt" in out, out)
    code, out = tool(repo2, "verdict", "normalize-query/attempt-001", "--verdict", "PASS", "--review",
                     review(repo2, "PASS"))
    check("PASS refused when checks created files (G4)", code != 0 and "G4" in out, out)


def test_cleanup_protects_unsaved_work():
    """Codex #3：cleanup 不能静默删除候选之外的改动。"""
    repo, base = make_repo("cleanup")
    run_ok(repo)
    worktree = worktree_of(repo)
    (worktree / "src" / "normalize.py").write_text("# edited after candidate\n", encoding="utf-8")
    code, out = tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "REVISE", "--review",
                     review(repo, "REVISE"), "--class", "EXECUTION_ERROR")
    code, out = tool(repo, "cleanup", "normalize-query/attempt-001")
    check("cleanup refuses when candidate files were modified", code != 0 and worktree.exists()
          and "normalize.py" in out, out)
    code, out = tool(repo, "cleanup", "normalize-query/attempt-001", "--force")
    check("cleanup --force removes and logs discarded content", code == 0 and not worktree.exists(), out)


def test_budget_race():
    """Codex #4：两个已准备的 attempt 并发争用最后一次额度，只能有一个领取成功。"""
    repo, base = make_repo("race", attempts=2)
    run_ok(repo)
    tool(repo, "prepare", "normalize-query.v1")
    tool(repo, "prepare", "normalize-query.v1")
    env = dict(BASE_ENV, STUB_SCENARIO="ok")
    procs = [subprocess.Popen([PY, "scripts/pi_dispatch.py", "run", "normalize-query/attempt-%03d" % n],
                              cwd=str(repo), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
             for n in (2, 3)]
    outputs = [p.communicate()[0].decode("utf-8", "replace") for p in procs]
    claimed = [(rd(repo, n) / "claim").is_dir() for n in (2, 3)]
    check("exactly one attempt claims the last budget slot", claimed.count(True) == 1
          and any("BUDGET_EXCEEDED" in o for o in outputs), (claimed, outputs))


def test_scope():
    repo, base = make_repo("scope")
    run_ok(repo, STUB_SCENARIO="scope")
    kinds = sorted({(v["path"], v["kind"]) for v in jload(rd(repo) / "scope.json")["violations"]})
    check("README out_of_scope", ("README.md", "out_of_scope") in kinds, kinds)
    check("package.json forbidden + dependency", ("package.json", "forbidden_path") in kinds
          and ("package.json", "dependency_change") in kinds, kinds)
    check(".env reported as new ignored path", ".env" in jload(rd(repo) / "observations.json")["new_ignored_paths"])
    ev = jload(rd(repo) / "events-summary.json")
    check("git push flagged", any(s["label"] == "git 写操作" for s in ev["suspicious_commands"]), ev)
    tool(repo, "check", "normalize-query/attempt-001")
    code, out = tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "PASS", "--review",
                     review(repo, "PASS"))
    check("PASS refused on scope violation (G2)", code != 0 and "G2" in out, out)
    code, out = tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "REVISE", "--review",
                     review(repo, "REVISE"), "--class", "SCOPE_VIOLATION")
    check("REVISE recorded", code == 0 and state(repo) == "REVISE", out)
    code, out = tool(repo, "branch", "normalize-query/attempt-001", "--rework")
    check("rework branch from REVISE", code == 0 and "pi-rework/" in out, out)


def test_events_and_thinking():
    repo, base = make_repo("error")
    code, out = run_ok(repo, STUB_SCENARIO="error")
    check("error stopReason -> exit 1 but NEEDS_REVIEW", code == 1 and state(repo) == "NEEDS_REVIEW", out)
    tool(repo, "check", "normalize-query/attempt-001")
    code, out = tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "PASS", "--review",
                     review(repo, "PASS"))
    check("PASS refused on G1", code != 0 and "G1" in out, out)
    code, out = tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "ACCEPTED_WITH_EXCEPTION",
                     "--review", review(repo, "ACCEPTED_WITH_EXCEPTION"), "--waive", "G1=trial",
                     "--decided-by", "owner")
    check("ACCEPTED_WITH_EXCEPTION with waiver", code == 0, out)
    code, out = tool(repo, "metrics")
    check("metrics counts exception acceptance separately",
          "| 首次验收通过率（PASS） | 0% |" in out and "| 豁免接受（ACCEPTED_WITH_EXCEPTION）任务 | 1 |" in out, out)
    cases = (("model", {}, lambda ev, st: not ev["model_match"]),
             ("startfail", {}, lambda ev, st: st == "INFRA_FAILURE"),
             ("nosettle", {}, lambda ev, st: not ev["complete"] and any("agent_settled" in p for p in ev["problems"])),
             ("ok", {"STUB_PTL": "low"}, lambda ev, st: not ev["ok"] and any("思考级别" in p for p in ev["problems"])),
             ("ok", {"STUB_NOCOST": "1"}, lambda ev, st: ev["cost"]["total"] is None
              and ev["cost"]["status"] == "unknown"))
    for index, (scenario, extra_env, predicate) in enumerate(cases):
        repo, base = make_repo("events%d" % index)
        env = dict(extra_env, STUB_SCENARIO=scenario)
        run_ok(repo, **env)
        ev = jload(rd(repo) / "events-summary.json")
        check("events case %s %s" % (scenario, extra_env), predicate(ev, state(repo)), ev.get("problems"))
    code, out = tool(repo, "status")
    check("status shows unknown cost", "unknown" in out, out)
    repo, base = make_repo("noreport")
    run_ok(repo, STUB_SCENARIO="noreport")
    tool(repo, "check", "normalize-query/attempt-001")
    code, out = tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "PASS", "--review",
                     review(repo, "PASS"))
    check("missing JSON report does not block PASS", code == 0, out)


def test_commit_outside_main():
    repo, base = make_repo("commit")
    run_ok(repo, STUB_SCENARIO="commit")
    scope = jload(rd(repo) / "scope.json")
    check("HEAD moved is a violation", any(v["kind"] == "head_moved" for v in scope["violations"]), scope)
    repo, base = make_repo("outside")
    run_ok(repo, STUB_SCENARIO="outside", STUB_MAIN_REPO=str(repo))
    check("outside path flagged", jload(rd(repo) / "events-summary.json")["outside_worktree_paths"])
    check("main repo change detected", jload(rd(repo) / "observations.json")["main_repo_changed"])
    repo, base = make_repo("touchmain")
    (repo / "README.md").write_text("# locally edited before the run\n", encoding="utf-8")  # 运行前已是脏文件
    run_ok(repo, STUB_SCENARIO="touchmain", STUB_MAIN_REPO=str(repo))
    check("re-modification of an already dirty file detected (Codex #12)",
          jload(rd(repo) / "observations.json")["main_repo_changed"])
    changes = jload(rd(repo) / "observations.json")["main_repo_changes"]
    check("main repo change lists the non-planner path", any(p.endswith("README.md") for p in changes["other_paths"])
          and not changes["head_changed"], changes)
    summary = (rd(repo) / "summary.md").read_text(encoding="utf-8")
    check("summary names the changed main repo file", "README.md" in summary.split("## 复审需要关注")[-1], summary)


def test_timeout():
    repo, base = make_repo("hang")
    write_config(repo, kill_grace_seconds=2)
    tool(repo, "prepare", "normalize-query.v1")
    started = time.time()
    code, out = tool(repo, "run", "normalize-query/attempt-001", "--timeout", "6", env={"STUB_SCENARIO": "hang"})
    elapsed = time.time() - started
    run = jload(rd(repo) / "run.json")
    check("timeout -> TIMEOUT state", state(repo) == "TIMEOUT" and run["timed_out"], out)
    check("timeout enforced quickly (<40s)", elapsed < 40, "%.1fs" % elapsed)
    pid_file = worktree_of(repo) / "child.pid"
    grandchild = pid_file.read_text().strip() if pid_file.exists() else None
    time.sleep(1)
    check("grandchild process killed (%s)" % run.get("kill_method"), grandchild and not alive(grandchild), grandchild)
    if grandchild:
        kill_hard(grandchild)


def test_dispatcher_killed():
    """调度器自身被强制结束：Windows 由 Job Object 回收；Linux 由 PR_SET_PDEATHSIG 通知 Pi。"""
    repo, base = make_repo("killed")
    tool(repo, "prepare", "normalize-query.v1")
    env = dict(BASE_ENV, STUB_SCENARIO="hang")
    dispatcher = subprocess.Popen([PY, "scripts/pi_dispatch.py", "run", "normalize-query/attempt-001"], cwd=str(repo),
                                  env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    worktree = worktree_of(repo)
    for _ in range(150):
        if (rd(repo) / "pid.txt").exists() and (worktree / "child.pid").exists():
            break
        time.sleep(0.2)
    pi_pid = (rd(repo) / "pid.txt").read_text().strip()
    grandchild = (worktree / "child.pid").read_text().strip()
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/PID", str(dispatcher.pid), "/F"], stdout=subprocess.DEVNULL)
    else:
        kill_hard(dispatcher.pid)
    dispatcher.wait()
    time.sleep(2)
    if IS_WINDOWS:
        check("Job Object reaps pi and grandchild", not alive(pi_pid) and not alive(grandchild))
    elif sys.platform.startswith("linux"):
        check("PDEATHSIG stops pi", not alive(pi_pid), pi_pid)
        if alive(grandchild):
            print("NOTE Linux：Pi 的普通子进程在调度器被 SIGKILL 后可能残留（已知限制）")
    else:
        print("NOTE %s：调度器被 SIGKILL 时没有父进程死亡通知，Pi 可能残留（已知限制）" % sys.platform)
    for pid in (pi_pid, grandchild):
        kill_hard(pid)
    code, out = tool(repo, "mark", "normalize-query/attempt-001", "ABANDONED")
    check("mark ABANDONED on RUNNING requires --force", code != 0 and "--force" in out, out)
    code, out = tool(repo, "collect", "normalize-query/attempt-001", "--recover")
    check("recover after dispatcher death", code == 0 and state(repo) in ("CANCELLED", "INFRA_FAILURE"), out)


def test_stuck_states():
    """Codex #7：领取后、启动前中断的 attempt 可以恢复；PREPARING 可以强制放弃。"""
    repo, base = make_repo("stuck")
    tool(repo, "prepare", "normalize-query.v1")
    (rd(repo) / "claim").mkdir()  # 模拟领取后调度器立即退出
    code, out = tool(repo, "run", "normalize-query/attempt-001")
    check("claimed PREPARED attempt cannot run again", code != 0 and "已领取" in out, out)
    code, out = tool(repo, "collect", "normalize-query/attempt-001", "--recover")
    check("claimed-but-not-started attempt recovers as INFRA_FAILURE",
          code == 0 and state(repo) == "INFRA_FAILURE", out)
    tool(repo, "prepare", "normalize-query.v1")
    pd.set_state(rd(repo, 2), "PREPARING")  # 模拟 prepare 中途崩溃
    code, out = tool(repo, "mark", "normalize-query/attempt-002", "ABANDONED", "--force", "--reason", "stuck")
    check("PREPARING can be abandoned with --force", code == 0 and state(repo, 2) == "ABANDONED", out)


def test_preflight_and_budget():
    repo, base = make_repo("preflight", attempts=2)
    tool(repo, "prepare", "normalize-query.v1")
    code, out = tool(repo, "run", "normalize-query/attempt-001", env={"STUB_MODELS": "openrouter stepfun/step-3.7-flash"})
    check("model not listed -> preflight fail, stays PREPARED", code != 0 and state(repo) == "PREPARED"
          and not (rd(repo) / "claim").exists(), out)
    code, out = tool(repo, "run", "normalize-query/attempt-001", env={"STUB_AUTH": "not_ready"})
    check("auth not ready -> preflight fail", code != 0 and "auth" in out, out)
    code, out = tool(repo, "run", "normalize-query/attempt-001", env={"PI_EXEC_MODEL": "other/model"})
    check("env/contract model conflict refused", code != 0 and "冲突" in out, out)
    tool(repo, "run", "normalize-query/attempt-001", env={"STUB_SCENARIO": "ok"})
    check("run after fixing env", state(repo) == "NEEDS_REVIEW")
    tool(repo, "prepare", "normalize-query.v1")
    tool(repo, "run", "normalize-query/attempt-002", env={"STUB_SCENARIO": "ok"})
    code, out = tool(repo, "prepare", "normalize-query.v1")
    check("budget: 3rd attempt refused", code != 0 and "BUDGET_EXCEEDED" in out, out)
    repo, base = make_repo("allowlist")
    write_config(repo, allowed_executors=[{"provider": "step", "model": "step-5-preview", "thinking": "high"}])
    code, out = tool(repo, "prepare", "normalize-query.v1")
    check("allowlisted executor with pinned high thinking ok", code == 0, out)
    write_plan(repo, base, 2, thinking="low")
    code, out = tool(repo, "prepare", "normalize-query.v2")
    check("pinned thinking mismatch refused", code != 0 and "思考级别" in out, out)


def test_validate():
    repo, base = make_repo("validate")
    good = contract(base, 2)

    def expect_error(name, needle, md=None, raw=None, **over):
        version = expect_error.version = getattr(expect_error, "version", 1) + 1
        data = contract(base, version, **over)
        write_plan(repo, base, version, md=md(version) if md else None, raw=raw(version) if raw else None, **over)
        code, out = tool(repo, "validate", "normalize-query.v%d" % version)
        check(name, code != 0 and needle in out and "Traceback" not in out, out)
        return data

    expect_error("invalid thinking rejected", "thinking", thinking="turbo")
    expect_error("protected path in scope rejected", "受保护", scope=dict(good["scope"], allowed_modified_files=["AGENTS.md"]))
    expect_error("codex config dir is protected", "受保护", scope=dict(good["scope"], allowed_new_files=[".codex/config.toml"]))
    expect_error("parent traversal rejected", "'..'", scope=dict(good["scope"], allowed_modified_files=["../x.py"]))
    expect_error("wrong executor type reported, no crash", "executor", executor=["x"])
    expect_error("non-string authorization items, no crash (Codex #11)", "authorization.executor",
                 authorization={"executor": [{}], "integration": []})
    expect_error("non-string evidence items, no crash", "evidence",
                 definition_of_done=[{"id": "D01", "text": "x", "evidence": [{"a": 1}]}])
    expect_error("contract without required checks rejected (Codex #13)", "required", checks=[],
                 definition_of_done=[{"id": "D01", "text": "x", "evidence": ["review"]}])
    expect_error("missing md section rejected", "Budget",
                 md=lambda v: build_md(contract(base, v)).replace("## Budget", "## Budgets"))
    expect_error("placeholder rejected", "占位符", md=lambda v: build_md(contract(base, v)) + "\n【待填：x】\n")
    # Codex #5：Markdown 保持不变，只改 JSON 中与执行相关的字段
    for name, needle, mutate in (
            ("argv change detected", "argv", lambda d: d["checks"][0].__setitem__("argv", [PY, "-c", "pass"])),
            ("budget change detected", "max_attempts_total", lambda d: d["budget"].__setitem__("max_attempts_total", 20)),
            ("integration change detected", "integration_actions",
             lambda d: d["authorization"].__setitem__("integration", ["deploy"])),
            ("forbidden path change detected", "secrets.txt",
             lambda d: d["scope"].__setitem__("forbidden_paths", ["package.json", "secrets.txt"])),
            ("thinking change detected", "thinking", lambda d: d["executor"].__setitem__("thinking", "low"))):
        def raw_for(v, mutate=mutate):
            data = contract(base, v)
            mutate(data)
            return data
        expect_error(name, needle, md=lambda v: build_md(contract(base, v)), raw=raw_for)
    repo2, base2 = make_repo("noignore", gitignore="node_modules/\n")
    code, out = tool(repo2, "prepare", "normalize-query.v1")
    check("prepare refuses when .agent/runs not ignored", code != 0 and ".gitignore" in out, out)
    examples = KIT / ".agents" / "skills" / "plan-task" / "examples"
    # 示例合同的 Repository facts 点名了虚构仓库里的文件；2.2.1 起 validate 会核对这些文件在基线里是否存在，
    # 所以先把它们放进测试仓库的基线，示例才像在真实仓库里那样“0 个警告”。
    for fact_path in ("src/search/normalize.ts", "src/search/index.ts", "src/api/client.ts", "src/auth/store.ts",
                      "src/auth/refresh.ts"):
        target = repo / fact_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("export {};\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "example fact files")
    example_base = git(repo, "rev-parse", "HEAD")
    for key in ("normalize-query.v1", "auth-refresh-401.v1"):
        for ext in ("md", "json"):
            text = (examples / ("%s.%s" % (key, ext))).read_text(encoding="utf-8")
            for fake in ("0123456789abcdef0123456789abcdef01234567", "89abcdef0123456789abcdef0123456789abcdef"):
                text = text.replace(fake, example_base)
            (repo / ".agent/plans" / ("%s.%s" % (key, ext))).write_text(text, encoding="utf-8")
        code, out = tool(repo, "validate", key)
        check("example %s validates" % key, code == 0 and "0 个警告" in out, out)


def test_output_paths():
    """Codex #6：--out 不能覆盖仓库文件或 attempt 证据。"""
    repo, base = make_repo("outpaths")
    run_ok(repo)
    code, out = tool(repo, "metrics", "--out", "README.md")
    check("metrics --out README.md refused, README untouched",
          code == pd.EXIT_USAGE and (repo / "README.md").read_text(encoding="utf-8") == "# Test\n", out)
    code, out = tool(repo, "doctor", "--out", ".agent/runs/normalize-query/attempt-001/events.jsonl")
    check("doctor --out into evidence refused", code == pd.EXIT_USAGE, out)
    code, out = tool(repo, "metrics", "--out", ".agent/runs/_reports/metrics.md")
    check("metrics --out under _reports allowed", code == 0 and (repo / ".agent/runs/_reports/metrics.md").exists(), out)


def test_units():
    """不经过命令行的单元级检查（Codex #2、#10）。"""
    compiled = pd.compile_patterns(["src/a.py"])
    check("glob uses fullmatch (no trailing newline match)", not pd.matches(compiled, "src/a.py\n")
          and pd.matches(compiled, "src/a.py"))
    minimal = pd.normalize_contract(contract("0" * 40))
    changes = [{"path": "src/normalize.py\n", "status": "M", "old_mode": "100644", "new_mode": "100644"},
               {"path": "src/x\ufffd.py", "status": "A", "old_mode": "000000", "new_mode": "100644",
                "path_decode_error": "true"}]
    scope = pd.evaluate_scope(changes, minimal, "0" * 40, "0" * 40)
    check("control chars / decode errors are invalid_path violations",
          [v["kind"] for v in scope["violations"]] == ["invalid_path", "invalid_path"], scope)
    captured = []

    def boom(pid):
        captured.append(pid)
        raise RuntimeError("on_spawn failed")

    try:
        pd.run_supervised([PY, "-c", "import time; time.sleep(60)"], WORK, dict(os.environ), subprocess.DEVNULL,
                          subprocess.DEVNULL, 120, 2.0, on_spawn=boom)
        raised = False
    except RuntimeError:
        raised = True
    time.sleep(1)
    check("on_spawn failure terminates the child (Codex #2)", raised and captured and not alive(captured[0]), captured)


def test_repo_config_features():
    """仓库级只读路径（extra_protected_paths）与候选提交尾注（commit_trailers）。"""
    repo, base = make_repo("repoconfig")
    trailer = "Co-Authored-By: Example Bot <bot@example.invalid>"
    write_config(repo, extra_protected_paths=["spec.md", ".orchestration/**"], commit_trailers=[trailer])
    write_plan(repo, base, 2, scope={"allowed_modified_files": ["src/normalize.py", "spec.md"],
                                     "allowed_new_files": [], "allowed_deleted_files": [],
                                     "forbidden_paths": [], "dependency_changes": "forbidden"})
    code, out = tool(repo, "validate", "normalize-query.v2")
    check("repo-level protected path rejected in scope", code != 0 and "spec.md" in out and "受保护" in out, out)
    scope = pd.evaluate_scope([{"path": ".orchestration/plan.md", "status": "M", "old_mode": "100644",
                                "new_mode": "100644"}], pd.normalize_contract(contract(base)), base, base,
                              [".orchestration/**"])
    check("repo-level protected path is a violation", [v["kind"] for v in scope["violations"]] == ["protected_path"],
          scope)
    run_ok(repo)
    instruction = (rd(repo) / "instruction.md").read_text(encoding="utf-8")
    check("instruction lists repo read-only paths", "`.orchestration/**`" in instruction, instruction[-600:])
    tool(repo, "check", "normalize-query/attempt-001")
    tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "PASS", "--review", review(repo, "PASS"))
    code, out = tool(repo, "branch", "normalize-query/attempt-001")
    message = git(repo, "log", "-1", "--format=%B", "pi/normalize-query-v1-a001")
    check("branch commit carries executor and trailers", code == 0 and trailer in message
          and "Pi-Executor: step/step-5-preview (thinking high)" in message, message)
    write_config(repo, commit_trailers=["not a trailer\nwith newline"])
    code, out = tool(repo, "validate", "normalize-query.v1")
    check("invalid commit_trailers config is ignored by validate", code == 0, out)
    code, out = tool(repo, "branch", "normalize-query/attempt-001", "--name", "pi/second")
    check("invalid commit_trailers config rejected by branch", code == pd.EXIT_USAGE and "commit_trailers" in out, out)


def test_wrapper_interpreters_and_literal_arguments():
    """Exercise the real shell entry, including macOS /bin/bash 3.2 when present."""
    if IS_WINDOWS:
        return  # Git Bash plus the real interpreter is covered by test_setup_wrapper_doctor.
    shells = list(dict.fromkeys(str(Path(p).resolve()) for p in
                               (shutil.which("bash"), "/bin/bash") if p and Path(p).is_file()))
    root = WORK / "wrapper with spaces"
    root.mkdir()
    shutil.copyfile(KIT / "scripts/dispatch-pi.sh", root / "dispatch-pi.sh")
    (root / "pi_dispatch.py").write_text(
        "import json,sys\nprint(json.dumps(sys.argv[1:]))\nsys.exit(7)\n", encoding="utf-8")
    interpreter = root / "interpreter.py"
    interpreter.write_text(
        "import os,runpy,sys\n"
        "name, args = sys.argv[1], sys.argv[2:]\n"
        "if name == 'py':\n"
        "    assert args[0] == '-3', args\n"
        "    args = args[1:]\n"
        "if args[:1] == ['-c']:\n"
        "    assert 'sys.version_info' in args[1], args\n"
        "    sys.exit(0 if name == os.environ['WRAPPER_TEST_ACCEPT'] else 1)\n"
        "assert name == os.environ['WRAPPER_TEST_ACCEPT'], name\n"
        "sys.argv = args\nrunpy.run_path(args[0], run_name='__main__')\n", encoding="utf-8")
    bindir = root / "bin"
    bindir.mkdir()
    # Only our three candidates and dirname are visible; the host Python cannot hide a failure.
    (bindir / "dirname").symlink_to(shutil.which("dirname"))
    for candidate in ("python3", "python", "py"):
        shim = bindir / candidate
        shim.write_text("#!/bin/sh\nexec %s %s %s \"$@\"\n" % (
            shlex.quote(PY), shlex.quote(str(interpreter)), shlex.quote(candidate)), encoding="utf-8")
        shim.chmod(0o755)
    arguments = ["validate", "a plan.v1", "", "--literal=$(not-a-command)", "`not-a-command`", "中文"]
    for shell in shells:
        for accepted in ("python3", "python", "py", "none"):
            env = dict(BASE_ENV, PATH=str(bindir), WRAPPER_TEST_ACCEPT=accepted)
            code, out = sh([shell, str(root / "dispatch-pi.sh")] + arguments, root, env, check=False)
            if accepted == "none":
                check("wrapper reports unsupported interpreters: " + shell,
                      code == 2 and "需要 Python 3.8+" in out, out)
            else:
                check("wrapper preserves argv and exit code via %s: %s" % (accepted, shell),
                      code == 7 and json.loads(out) == arguments, out)


def test_setup_wrapper_doctor():
    repo, base = make_repo("setup", setup=[{"id": "S01", "argv": [PY, "-c", "print('deps ok')"], "cwd": ".",
                                           "timeout_seconds": 60}])
    code, out = tool(repo, "prepare", "normalize-query.v1")
    check("setup command runs in prepare", code == 0 and (rd(repo) / "setup/S01.log").exists(), out)
    repo, base = make_repo("setupdirty", setup=[{"id": "S01", "argv": [PY, "-c", "open('README.md','a').write('x')"],
                                                "cwd": ".", "timeout_seconds": 60}])
    code, out = tool(repo, "prepare", "normalize-query.v1")
    check("setup modifying tracked file -> PREPARE_FAILED", code != 0 and state(repo) == "PREPARE_FAILED", out)
    bash = r"C:\Program Files\Git\bin\bash.exe" if IS_WINDOWS and Path(r"C:\Program Files\Git\bin\bash.exe").exists() \
        else shutil.which("bash")
    if bash:
        code, out = sh([bash, "scripts/dispatch-pi.sh", "validate", "normalize-query.v1"], repo, check=False)
        check("bash wrapper finds python", code == 0 and "合同有效" in out, out)
    code, out = tool(repo, "doctor", "--provider", "step", "--model", "step-5-preview", "--thinking", "high")
    data = json.loads(out)
    check("doctor ok with stub", code == 0 and data["ok"] and data["executor_model_listed"], data.get("problems"))
    check("doctor records the model list and the git identity", data["executor_model_list"]["exit_code"] == 0
          and data["executor_model_list"]["rows"] == 1 and data["repository"]["git_identity"] is True, data)
    # 2.1.0：list-models 本身失败（例如在沙箱中）与模型不在列表中分开报告；错误输出先脱敏。
    code, out = tool(repo, "doctor", "--provider", "step", "--model", "step-5-preview", "--thinking", "high",
                     env={"STUB_LIST_FAIL": "1"})
    data = json.loads(out)
    check("doctor reports a failing list-models run as such", code != 0 and data["executor_model_listed"] is None
          and any("list-models 执行失败（退出码 1）" in p and "沙箱外" in p for p in data["problems"])
          and "EPERM" in data["executor_model_list"]["stderr_tail"]
          and not any("不在可用模型列表中" in p for p in data["problems"]), data["problems"])
    check("doctor redacts credentials echoed by pi", "DEMO_TOKEN_FOR_REVIEW" not in out and "<redacted>" in out,
          out[-800:])
    # pi 0.87 没有可用或匹配的模型时输出一句说明，不输出表格。
    code, out = tool(repo, "doctor", "--provider", "step", "--model", "step-5-preview", "--thinking", "high",
                     env={"STUB_MODELS": ""})
    data = json.loads(out)
    check("doctor explains that pi has no models at all", code != 0 and data["executor_model_listed"] is False
          and data["executor_model_list"]["empty_reason"] == "no_models"
          and any("pi 没有任何可用模型" in p for p in data["problems"]), data["problems"])
    code, out = tool(repo, "doctor", "--provider", "step", "--model", "step-5-preview", "--thinking", "high",
                     env={"STUB_MODELS": "step other-model"})
    data = json.loads(out)
    check("doctor explains that no model matches", code != 0
          and data["executor_model_list"]["empty_reason"] == "no_match"
          and any("没有与 step-5-preview 匹配的" in p for p in data["problems"]), data["problems"])
    code, out = tool(repo, "doctor", "--provider", "step", "--model", "step-5-preview", "--thinking", "high",
                     env={"STUB_MODELS": "other step-5-preview"})
    data = json.loads(out)
    check("a model listed under another provider keeps the short message", code != 0
          and any(p.endswith("不在可用模型列表中") for p in data["problems"]), data["problems"])
    code, out = tool(repo, "smoke", "--provider", "step", "--model", "step-5-preview")
    data = json.loads(out)
    check("smoke both steps ok", code == 0 and data["ok"] and len(data["steps"]) == 2, data)


DERIVE_MD = """# TASK: derived-task

## Identity
- plan_version: 1
- repository: test
- base_sha: {base}
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, commit
- executor: step/step-5-preview · thinking high

## Goal
让 normalize() 折叠空白并转小写。

## Non-goals
- 不改其他模块。

## Repository facts
- src/normalize.py 中的 normalize(q)。

## Scope
- allowed_modified_files:
  - src/normalize.py
- allowed_new_files: tests/test_normalize.py
- allowed_deleted_files: 无
- forbidden_paths: 无（另有全局只读）
- dependency_changes: forbidden

## Behavior contract
- '  A  B ' -> 'a b'

## Steps
1. 实现。

## Validation commands
- V01（必要）：`{prog} run_tests.py` · cwd：仓库根 · 超时：120s · 期望退出码：0 · 输出须匹配 `Tests [1-9][0-9]* passed`，不得出现 `FAILED`
- V02（必要，基线应失败）：`{prog} -c "from normalize import normalize; print('PROBE_OK')"` · cwd：src · 超时：60s · 期望退出码：0 · 输出须匹配 `PROBE_OK`
- V03（可选）：`{prog} -m unittest discover -s tests` · cwd：仓库根 · 超时：90s · 期望退出码：0

## Definition of done
- D01：空白折叠；证据：V01 中的 test_spaces、V02。
- D02：只改允许的文件；证据：scope。
- D03：没有弱化测试；证据：review。

## Stop conditions
- 需要改范围外文件。

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 1200
- max_wall_seconds_total: 2400
- cost_budget: tracking-only

## Report back
- 最后一条消息为执行报告。

## Forbidden
- 不提交。
"""


def test_feedback_v11():
    """实机反馈改进（1.1.0）：路径形式的计划标识、不可见字符、status 定位、运行目录读取、
    越界访问的结果、主工作区变化分类、范围重叠、baseline 与 derive-json。"""
    repo, base = make_repo("v11path")
    code, out = tool(repo, "validate", ".agent/plans/normalize-query.v1.md")
    check("validate accepts a relative md path", code == 0 and "normalize-query.v1" in out, out)
    code, out = tool(repo, "validate", str(repo / ".agent/plans/normalize-query.v1.json"))
    check("validate accepts an absolute json path", code == 0, out)
    code, out = tool(repo, "validate", "elsewhere/normalize-query.v1.md")
    check("plan path outside .agent/plans rejected", code != 0 and "必须位于" in out, out)
    code, out = tool(repo, "validate", "Not A Key")
    check("bad plan key still explains the format", code != 0 and "task-id.vN" in out, out)
    md = build_md(contract(base, 2)).replace("折叠空白", "折叠" + chr(0x200E) + "空白")
    write_plan(repo, base, 2, md=md)
    code, out = tool(repo, "validate", "normalize-query.v2")
    check("invisible format character is warned", code == 0 and "U+200E" in out, out)

    code, out = run_ok(repo)
    code, out = tool(repo, "status", "normalize-query/attempt-001")
    check("status accepts an attempt ref", code == 0 and "attempt-001" in out and "NEEDS_REVIEW" in out, out)
    code, out = tool(repo, "status", str(rd(repo)))
    check("status accepts an attempt path", code == 0 and out.count("attempt-") == 1, out)

    repo, base = make_repo("v11readplan")
    run_ok(repo, STUB_SCENARIO="readplan")
    ev = jload(rd(repo) / "events-summary.json")
    check("reading the attached plan.md is not an outside access",
          not ev["outside_worktree_paths"] and ev["own_run_paths"], ev.get("outside_worktree_paths"))
    summary = (rd(repo) / "summary.md").read_text(encoding="utf-8")
    check("own run-dir reads go to notes", "## 备注" in summary and "工作副本外路径" not in summary, summary)

    repo, base = make_repo("v11typo")
    run_ok(repo, STUB_SCENARIO="typo")
    record = jload(rd(repo) / "events-summary.json")["outside_worktree_paths"][0]
    check("failed outside access is marked failed and missing", record["failed"] is True
          and record["exists"] is False, record)
    summary = (rd(repo) / "summary.md").read_text(encoding="utf-8")
    check("summary explains the failed, missing path", "调用失败" in summary and "路径不存在" in summary, summary)
    instruction = (rd(repo) / "instruction.md").read_text(encoding="utf-8")
    check("instruction asks for relative paths", "读写工作目录中的文件一律使用相对路径" in instruction, instruction[:600])
    check("instruction forbids stashing own changes", "git stash" in instruction, instruction[:900])
    check("instruction tells the executor how to track elapsed time", "date +%s" in instruction
          and "五分之一" in instruction, instruction[:900])
    check("planner paths include the design folder by default",
          ".agent/design/**" in pd.planner_paths({}), pd.planner_paths({}))

    repo, base = make_repo("v11planner")
    run_ok(repo, STUB_SCENARIO="planner", STUB_MAIN_REPO=str(repo))
    changes = jload(rd(repo) / "observations.json")["main_repo_changes"]
    check("planner path change classified as planner", changes["planner_paths"] and not changes["other_paths"]
          and not changes["head_changed"], changes)
    summary = (rd(repo) / "summary.md").read_text(encoding="utf-8")
    attention = summary.split("## 复审需要关注")[1].split("\n## ")[0] if "## 复审需要关注" in summary else ""
    check("planner change is a note, not an attention item", "next-task.v1.md" not in attention
          and "规划路径有变化" in summary, summary)

    repo, base = make_repo("v11overlap")
    tool(repo, "prepare", "normalize-query.v1")
    other = contract(base, 1)
    other["task_id"] = "other-task"
    (repo / ".agent/plans/other-task.v1.md").write_text(build_md(other), encoding="utf-8")
    (repo / ".agent/plans/other-task.v1.json").write_text(json.dumps(other, ensure_ascii=False), encoding="utf-8")
    code, out = tool(repo, "prepare", "other-task.v1")
    check("prepare warns about an overlapping pending attempt", code == 0 and "改动范围重叠" in out
          and "src/normalize.py" in out, out)

    repo, base = make_repo("v11baseline")
    code, out = tool(repo, "baseline", "normalize-query.v1")
    check("baseline runs checks on base without an attempt", code == 0 and "V01" in out
          and not rd(repo).exists(), out)
    probe = {"id": "V02", "argv": [PY, "-c", "print('PROBE_OK')"], "cwd": ".", "timeout_seconds": 60,
             "required": True, "expected_exit_code": 0, "output_must_match": ["PROBE_OK"], "expect_on_base": "fail"}
    write_plan(repo, base, 2, checks=default_checks() + [probe])
    code, out = tool(repo, "baseline", "normalize-query.v2")
    check("baseline flags a probe that already passes on base", code != 0 and "区分不了" in out, out)
    record = jload(repo / ".agent/runs/normalize-query/baseline/02/checks.json")
    check("baseline record lists the mismatch", record["mismatches"] == ["V02"], record.get("mismatches"))
    write_plan(repo, base, 3, checks=default_checks() + [dict(probe, expect_on_base="sometimes")])
    code, out = tool(repo, "validate", "normalize-query.v3")
    check("invalid expect_on_base rejected", code != 0 and "expect_on_base" in out, out)

    repo, base = make_repo("v11derive")
    (repo / ".agent/plans/derived-task.v1.md").write_text(DERIVE_MD.format(base=base, prog=PROG), encoding="utf-8")
    code, out = tool(repo, "derive-json", "derived-task.v1", "--title", "派生测试")
    check("derive-json writes a contract that validates", code == 0 and "合同有效" in out, out)
    data = jload(repo / ".agent/plans/derived-task.v1.json")
    v01, v02, v03 = data["checks"]
    check("derived checks keep argv, cwd, timeout and patterns",
          v01["argv"] == [PROG, "run_tests.py"] and v01["timeout_seconds"] == 120
          and v01["output_must_match"] == ["Tests [1-9][0-9]* passed"] and v01["output_must_not_match"] == ["FAILED"]
          and v02["argv"][:2] == [PROG, "-c"] and v02["cwd"] == "src" and v02.get("expect_on_base") == "fail"
          and v03["required"] is False, data["checks"])
    check("derived scope and DoD", data["scope"]["allowed_modified_files"] == ["src/normalize.py"]
          and data["scope"]["allowed_new_files"] == ["tests/test_normalize.py"]
          and data["scope"]["forbidden_paths"] == []
          and [d["evidence"] for d in data["definition_of_done"]] == [["V01", "V02"], ["scope"], ["review"]]
          and data["authorization"]["integration"] == ["local_branch", "commit"]
          and data["budget"]["max_wall_seconds_total"] == 2400 and data["title"] == "派生测试", data)
    code, out = tool(repo, "derive-json", "derived-task.v1")
    check("derive-json refuses to overwrite without --force", code != 0 and "--force" in out, out)
    code, out = tool(repo, "derive-json", "derived-task.v1", "--print")
    check("derive-json --print takes the title from Goal", code == 0 and "让 normalize() 折叠空白并转小写。" in out, out)

    import re as _re
    git_write = pd.SUSPICIOUS_COMMANDS[0][0]
    readonly = ["git stash list", "git stash show -p", "git tag -l", "git status && git stash list"]
    writes = ["git stash", "git stash push -m x", "git tag v1", "git push origin HEAD"]
    check("read-only git stash/tag listing is not a write op",
          not any(_re.search(git_write, c, _re.I) for c in readonly)
          and all(_re.search(git_write, c, _re.I) for c in writes), git_write)


AMBIGUITY_PLAN = """# TASK: t

## Goal
对齐组的状态为 ambiguous；重叠不足时也是 ambiguous。

## Stop conditions
- 发现本合同内部前后矛盾：停止并报告两处原文。
"""


def test_feedback_v12():
    """实机反馈改进（1.2.0）：执行器发现合同前后矛盾后自行选了一种解释，报告里没有指出。"""
    repo, base = make_repo("v12ambiguous")
    run_ok(repo, STUB_SCENARIO="ambiguous")
    ev = jload(rd(repo) / "events-summary.json")
    check("ambiguity mention in thinking is recorded", ev["ambiguity_mention_count"] == 1
          and ev["ambiguity_mentions"][0]["kind"] == "thinking"
          and "step 4" in ev["ambiguity_mentions"][0]["excerpt"], ev.get("ambiguity_mentions"))
    summary = (rd(repo) / "summary.md").read_text(encoding="utf-8")
    attention = summary.split("## 复审需要关注")[1].split("\n## ")[0] if "## 复审需要关注" in summary else ""
    check("undeclared ambiguity is an attention item", "提到合同的歧义、矛盾或一致性" in attention
          and "都为空" in attention, summary)
    instruction = (rd(repo) / "instruction.md").read_text(encoding="utf-8")
    check("instruction asks to declare contract conflicts", "contract_conflicts" in instruction
          and "前后矛盾" in instruction and '"contract_conflicts": []' in instruction, instruction[-1500:])
    tool(repo, "check", "normalize-query/attempt-001")
    code, out = tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "REVISE", "--class", "PLAN_ERROR",
                     "--review", review(repo, "REVISE"))
    check("verdict prints the G3 note about undeclared ambiguity", code == 0 and "NOTE  G3" in out, out)

    repo, base = make_repo("v12conflict")
    run_ok(repo, STUB_SCENARIO="conflict")
    status = jload(rd(repo) / "report-status.json")
    check("report-status counts contract conflicts", status.get("contract_conflicts") == 1
          and status.get("unresolved_questions") == 0, status)
    summary = (rd(repo) / "summary.md").read_text(encoding="utf-8")
    attention = summary.split("## 复审需要关注")[1].split("\n## ")[0] if "## 复审需要关注" in summary else ""
    notes = summary.split("## 备注")[1].split("\n## ")[0] if "## 备注" in summary else ""
    check("declared conflicts need a ruling; the mention becomes a note",
          "报告了 1 处合同矛盾" in attention and "提到合同的歧义、矛盾或一致性" not in attention
          and "提到合同的歧义、矛盾或一致性" in notes, summary)

    msg = lambda text: {"content": [{"type": "thinking", "thinking": text}]}  # noqa: E731
    cases = [("The contract is ambiguous here: step 4 says one thing", 1),
             ("There is no ambiguity in the contract.", 0),
             ("The spec is unambiguous.", 0),
             ("they don't seem inconsistent with the plan", 0),
             ("合同中步骤 4 与行为说明矛盾。", 1),
             ("合同与代码没有矛盾。", 0),
             ("步骤 4 与行为说明的要求不一样，互相矛盾", 1),
             ("newline ambiguity: two inputs map to the same key", 0),
             ("let me check whether there is any inconsistency in the contract I should report", 0),
             ("I found an inconsistency between the contract and step 3", 1),
             # 2.1.0：关键词后面直接跟着独立否定答案的不算；泛用词 None 不算否定。
             # 只是在检查的句子也保留提示：靠上下文判断“只是在检查”总能被构造的句子绕过，提示写明了可能只是在检查。
             ("contract_conflicts: none found. Let me double check for inconsistencies between plan.md and "
              "machine contract summary:", 1),
             ("Checking for inconsistencies between the contract and the code... none found.", 1),
             ("Compared plan.md and the machine summary for contradictions: no conflicts.", 0),
             ("I checked the contract and found it inconsistent with step 3", 1),
             ("I looked for a while and the contract is inconsistent with step 3", 1),
             ("The contract contradicts itself: step 4 says return None but the behavior section says raise", 1),
             ("核对后发现合同的步骤 4 与行为说明矛盾。", 1),
             ("检查合同与测试是否矛盾", 1),  # 只有检查、没有结论：拿不准，保留提示
             ("检查合同与测试是否矛盾：没有矛盾。", 0),
             ("确认一下有没有矛盾：未发现。", 0),
             # Codex 复审：肯定的结论、隔着别的内容的否定词都不能把真实矛盾过滤掉；拿不准时保留提示。
             ("I checked whether the contract is inconsistent and confirmed it is.", 1),
             ("Let me check whether step 4 is inconsistent with the behavior section. It is: step 4 says B.", 1),
             ("核对是否一致后发现合同矛盾。", 1),
             ("合同存在矛盾，但未发现解决办法。", 1),
             ("The contract is inconsistent, but no issues were found in the tests.", 1),
             ("The spec is ambiguous: None of the steps say which comes first.", 1),
             ("Contradictions in the contract: none.", 1),
             ("Contract contradictions: none.", 0),
             ("### 合同矛盾\n未发现 plan.md 与“机器合同摘要”不一致之处，`contract_conflicts` 为空。", 1),
             ("### 合同矛盾\n未发现。", 0),
             ("### 合同矛盾\n- 无", 0),
             # Codex 第二轮：否定的必须是矛盾本身；结论的措辞认不出时保留提示。
             ("合同存在矛盾：未发现解决办法。", 1),
             ("The contract is inconsistent: no issues were found in the tests.", 1),
             ("I checked whether the contract is inconsistent. It definitely is.", 1),
             ("Inconsistencies: no issues found.", 0),
             ("Let me check whether step 4 is inconsistent with the behavior section. It is, though there are "
              "no conflicts with the tests.", 1),
             # Codex 第三轮：否定答案后面还有别的内容、相邻句子不是独立的否定结论时，都保留提示。
             ("合同存在矛盾：未发现解决冲突的办法。", 1),
             ("检查合同是否矛盾。未发现解决办法，步骤 4 要求返回 A 而步骤 5 要求返回 B。", 1),
             ("The contract is inconsistent: no conflicts in the tests were reported.", 1),
             ("I checked whether the contract is inconsistent. The files are consistent with each other. "
              "The answer is yes.", 1),
             # Codex 第四轮：相邻句子的否定可能在说别的；not merely / 不仅 是递进，不是否定。
             ("Missing tests? None found. I checked whether the contract is inconsistent. It definitely is.", 1),
             ("The contract is not merely inconsistent; step 4 requires A while step 5 requires B.", 1),
             ("合同不仅矛盾，而且步骤 4 要求 A、步骤 5 要求 B。", 1),
             ("The plan isn't only inconsistent, it contradicts step 5.", 1),
             # Codex 第五轮：否定必须紧挨关键词；单独的 no、编号缩写与换行续写都不是否定答案。
             ("The contract has no fix for this inconsistency; step 4 requires A while step 5 requires B.", 1),
             ("合同存在不可调和的矛盾，步骤 4 要求 A，步骤 5 要求 B。", 1),
             ("The contract is inconsistent: no. 4 requires A while no. 5 requires B.", 1),
             ("The contract is inconsistent: no\nimplementation can satisfy steps 4 and 5.", 1),
             ("I don't see any inconsistency in the contract.", 0),
             ("合同没有发现任何矛盾。", 0),
             ("There is no real inconsistency in the plan.", 0),
             ("合同与代码并不矛盾。", 0),
             ("Let me double-check there are no internal contradictions I should flag.", 0),
             ("Let me re-read the contract for any internal contradictions.", 0),
             ("合同没有内在矛盾。", 0),
             ("Contract contradictions: no.", 1),
             ("Contract contradictions: none\nof the listed steps agree with step 4.", 1),
             # Codex 第六轮：双重否定其实是肯定；句点后面紧跟标识符时不算句末。
             ("The contract cannot be implemented without contradictions:\nstep 4 requires A, while step 5 forbids A.", 1),
             ("合同并非没有矛盾：步骤 4 要求 A，步骤 5 禁止 A。", 1),
             ("The contract is inconsistent: None.__class__ is mandated by step 4,\nbut step 5 requires str.", 1),
             ("The plan is consistent, without any contradiction.", 0),
             # Codex 第七轮：isn't without、not un- 也是双重否定。
             ("The contract isn't without contradictions: step 4 requires A while step 5 requires B.", 1),
             ("The contract is not unambiguous: step 4 requires A while step 5 requires B.", 1)]
    wrong = [(text, want) for text, want in cases if len(pd.ambiguity_mentions(msg(text), 1)) != want]
    check("ambiguity detector handles negation and context", not wrong, wrong)
    check("domain words come from the plan body, not stop conditions",
          pd.ambiguity_domain_words(AMBIGUITY_PLAN) == ["ambigu"], pd.ambiguity_domain_words(AMBIGUITY_PLAN))
    check("domain words are skipped", not pd.ambiguity_mentions(
        msg("The contract says the group is ambiguous when IoU < 1/2."), 1, ["ambigu"]))

    # 1.2.1：范围重叠只看每个任务最新的 attempt。返工后新 attempt 已集成时，旧的 REVISE 不再提示。
    repo, base = make_repo("v121latest")
    tool(repo, "prepare", "normalize-query.v1")
    pd.set_state(rd(repo, 1), "REVISE")
    tool(repo, "prepare", "normalize-query.v1")
    other = contract(base, 1)
    other["task_id"] = "other-task"
    (repo / ".agent/plans/other-task.v1.md").write_text(build_md(other), encoding="utf-8")
    (repo / ".agent/plans/other-task.v1.json").write_text(json.dumps(other, ensure_ascii=False), encoding="utf-8")
    code, out = tool(repo, "prepare", "other-task.v1")
    overlap_lines = [line for line in out.splitlines() if "改动范围重叠" in line]
    check("overlap warning names the latest pending attempt only", code == 0 and len(overlap_lines) == 1
          and "normalize-query/attempt-002" in overlap_lines[0], out)
    pd.set_state(rd(repo, 2), "INTEGRATED")
    code, out = tool(repo, "prepare", "other-task.v1")
    check("no overlap warning once the latest attempt is integrated", code == 0 and "改动范围重叠" not in out, out)

    # 1.2.2：候选已并入后续提交（规划器补齐）时标为 SUPERSEDED，不再算“待集成”。
    repo, base = make_repo("v122superseded")
    tool(repo, "prepare", "normalize-query.v1")
    pd.set_state(rd(repo, 1), "REVISE")
    code, out = tool(repo, "mark", "normalize-query/attempt-001", "SUPERSEDED")
    check("SUPERSEDED needs --ref and --reason", code != 0 and "--ref" in out, out)
    code, out = tool(repo, "mark", "normalize-query/attempt-001", "SUPERSEDED", "--ref", "abc123",
                     "--reason", "预算用尽，规划器补齐测试后集成")
    check("REVISE attempt can be marked SUPERSEDED", code == 0 and pd.get_state(rd(repo, 1)) == "SUPERSEDED", out)
    other = contract(base, 1)
    other["task_id"] = "other-task"
    (repo / ".agent/plans/other-task.v1.md").write_text(build_md(other), encoding="utf-8")
    (repo / ".agent/plans/other-task.v1.json").write_text(json.dumps(other, ensure_ascii=False), encoding="utf-8")
    code, out = tool(repo, "prepare", "other-task.v1")
    check("a superseded attempt is not pending integration", code == 0 and "改动范围重叠" not in out, out)
    code, out = tool(repo, "mark", "other-task/attempt-001", "SUPERSEDED", "--ref", "x", "--reason", "y")
    check("SUPERSEDED is refused for an attempt that never ran", code != 0 and "PREPARED" in out, out)

    # 1.2.2：机器合同摘要把 expect_on_base 写成完成后的要求，避免执行器把“基线应失败”读成“应该失败”。
    probe = {"id": "V02", "argv": [PY, "-c", "print('PROBE_OK')"], "cwd": ".", "timeout_seconds": 60,
             "required": True, "expected_exit_code": 0, "output_must_match": ["PROBE_OK"], "expect_on_base": "fail"}
    summary_text = pd.machine_summary(contract(base, 1, checks=default_checks() + [probe]))
    line = [item for item in summary_text.splitlines() if "V02" in item]
    check("machine summary explains a base-failing probe", line and "完成后它必须通过" in line[0], summary_text)

    # 1.2.1：最终消息把工具调用写成了正文，运行“正常结束”却没有做完：G1 失败，并说明原因。
    repo, base = make_repo("v121textcall")
    run_ok(repo, STUB_SCENARIO="textcall")
    ev = jload(rd(repo) / "events-summary.json")
    check("textual tool call in the final message is an integrity problem",
          any("未执行的工具调用" in p for p in ev["problems"]), ev["problems"])
    tool(repo, "check", "normalize-query/attempt-001")
    code, out = tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "PASS", "--review", review(repo, "PASS"))
    check("PASS is refused when the run ended on a textual tool call", code != 0 and "G1" in out, out)

    # 1.2.7：分支提交的主题行不重复 task-id；derive-json 提示取自 Goal 的过长标题。
    subjects = {
        ("export-command", "export-command：导出与核验"): "export-command：导出与核验",
        ("t", "t: x"): "t: x",
        ("t", "t 导出"): "t 导出",
        ("t", "标题"): "t: 标题",
        ("t", "tx 标题"): "t: tx 标题",
        ("t", None): "t: Pi 候选 v2 attempt 003",
        ("t", "  "): "t: Pi 候选 v2 attempt 003",
    }
    got = {key: pd.branch_subject(key[0], key[1], 2, 3) for key in subjects}
    check("branch subject does not repeat the task id", got == subjects, got)
    repo, base = make_repo("v127title")
    long_goal = ("作业持久化与修订闭环的最后一步（路线图 10.7，设计见 design 第 5 节与决定 D2）："
                 "新增 export 子命令，把指定修订的目标 cue 导出为 SRT。")
    md = DERIVE_MD.format(base=base, prog=PROG).replace("让 normalize() 折叠空白并转小写。", long_goal)
    (repo / ".agent/plans/derived-task.v1.md").write_text(md, encoding="utf-8")
    code, out = tool(repo, "derive-json", "derived-task.v1")
    check("derive-json notes a long title taken from Goal",
          code == 0 and "NOTE" in out and "--title" in out and "合同有效" in out, out)
    code, out = tool(repo, "derive-json", "derived-task.v1", "--title", "导出命令", "--force")
    check("no title note when --title is given", code == 0 and "NOTE" not in out
          and jload(repo / ".agent/plans/derived-task.v1.json")["title"] == "导出命令", out)

    # 1.2.6：删除工作副本内的缓存目录（__pycache__ 等）改记备注。
    cache_cases = {
        'rm -rf subtitle_qa/__pycache__ tests/__pycache__ && find . -name x | head': "rm -rf subtitle_qa/__pycache__ tests/__pycache__",
        "rm -rf .pytest_cache": "rm -rf .pytest_cache",
        'rm -rf "pkg/.mypy_cache/"': 'rm -rf "pkg/.mypy_cache/"',
        "rm -rf ../__pycache__": None,
        "rm -rf /tmp/__pycache__": None,
        "rm -rf src": None,
        "rm -rf __pycache__ src": None,
        'rm -rf "$X"/__pycache__': None,
        "rm -rf ~/__pycache__": None,
    }
    got = {command: pd._cache_dir_cleanup(command) for command in cache_cases}
    check("cache dir cleanup is recognised only for relative cache paths", got == cache_cases, got)

    # 1.2.5：运行中的状态提示“长时间没有工具调用”。
    live_dir = WORK / "live-progress"
    live_dir.mkdir(parents=True, exist_ok=True)
    update = '{"type":"message_update","assistantMessageEvent":{"type":"thinking_delta","delta":"x"}}\n'
    tool_end = '{"type":"tool_execution_end","toolCallId":"c","toolName":"read","result":{},"isError":false}\n'
    (live_dir / "events.jsonl").write_text(tool_end * 3 + update * 50, encoding="utf-8")
    normal = pd._live_progress(live_dir)
    (live_dir / "events.jsonl").write_text(update * 5000 + tool_end * 3 + update * pd.LONG_THINKING_DELTAS,
                                           encoding="utf-8")
    quiet = pd._live_progress(live_dir)
    check("live status flags a long stretch without tool calls",
          normal.startswith("live:3t") and "没有工具调用" not in normal
          and quiet.startswith("live:3t") and "长时间没有工具调用（%d 个增量）" % pd.LONG_THINKING_DELTAS in quiet,
          (normal, quiet))

    # 1.2.4：可疑命令记下命中所在的行。2.1.0 起删除 mktemp 临时路径不再豁免，照常列为可疑命令：Codex 审查表明
    # 这类判断总能被构造的命令骗过（例如 `T=$(mktemp -d >/dev/null; printf %s src)` 之后的删除实际删的是源码），
    # 而 WoMovieSubCheck 的 50 个历史 attempt 中它只起过一次作用。
    repo, base = make_repo("v124tmp")
    run_ok(repo, STUB_SCENARIO="tmpclean")
    ev = jload(rd(repo) / "events-summary.json")
    matches = [item["match"] for item in ev["suspicious_commands"]]
    check("mktemp removals are listed like any other deletion", matches == ['rm -rf "$TMPD"', 'rm -rf "$T"/build']
          and "temp_dir_cleanups" not in ev, ev.get("suspicious_commands"))
    item = ev["suspicious_commands"][1]
    check("suspicious command records the matched line", item["match"] == 'rm -rf "$T"/build'
          and item["match_line"] == 7 and item["command_lines"] == 7 and "rm -rf" not in item["command"], item)
    summary = (rd(repo) / "summary.md").read_text(encoding="utf-8")
    check("summary shows the matched line", '命令第 7 / 7 行 `rm -rf "$T"/build`' in summary, summary)
    check("cache cleanup is a note, not a suspicious command",
          [c["command"] for c in ev["cache_dir_cleanups"]] == ["rm -rf src/__pycache__ tests/__pycache__"]
          and "工作副本内的缓存目录" in summary, ev.get("cache_dir_cleanups"))
    # 2.1.0：系统临时目录的创建或使用一律列入复审关注；执行器用绝对路径 cd 进自己的 worktree 不算。
    uses = ev.get("temp_path_uses", [])
    check("temp path uses are recorded, the worktree itself is not",
          [u["match"] for u in uses] == ['TMPD="$(mktemp -d)"', "T=$(mktemp -d)", "d = tempfile.mkdtemp()"]
          and uses[2]["match_line"] == 3 and ev["temp_path_use_count"] == 3, uses)
    attention = summary.split("## 复审需要关注")[1].split("\n## ")[0] if "## 复审需要关注" in summary else ""
    check("temp path uses are an attention item",
          '系统临时路径线索（3 个命中片段）' in attention
          and all('事件流第 %s 行，命令第 %s 行 `%s`' % (u["event_line"], u["match_line"], u["match"]) in attention
                  for u in uses),
          attention)

    # A later fixed path must survive both an earlier legal mktemp and subsequent cleanup.
    repo, base = make_repo("tempsequence")
    run_ok(repo, STUB_SCENARIO="tempsequence")
    ev = jload(rd(repo) / "events-summary.json")
    summary = (rd(repo) / "summary.md").read_text(encoding="utf-8")
    uses = ev["temp_path_uses"]
    check("later fixed temp path in the same command is recorded",
          uses[0]["event_line"] == uses[1]["event_line"]
          and uses[0]["match_line"] == 1 and uses[1]["match_line"] == 2
          and uses[1]["match"] == 'echo "$T" >/tmp/backup_dir', uses[:4])
    check("temp write read and cleanup evidence all remain in summary",
          all('事件流第 %s 行，命令第 %s 行 `%s`' % (u["event_line"], u["match_line"], u["match"]) in summary
              for u in uses[:4]) and "不能证明此前未覆盖既有内容" in summary, summary)
    check("a fixed temp path late on one long line remains visible",
          uses[4]["event_line"] == uses[5]["event_line"]
          and uses[4]["match_line"] == uses[5]["match_line"] == 1
          and "mktemp" in uses[4]["match"] and "/tmp/backup_dir" in uses[5]["match"]
          and all(u["match"] in summary for u in uses[4:6]), uses[4:6])
    check("summary makes truncated temp evidence explicit",
          ev["temp_path_use_count"] == 56 and len(uses) == 50
          and "另有 6 个命中片段未展示" in summary and "events.jsonl 原始命令" in summary, summary)

    # 1.2.3：单值字段后面带括号说明时，derive-json 与校验只取括号前的值。
    repo, base = make_repo("v123note")
    md = DERIVE_MD.format(base=base, prog=PROG) \
        .replace("- dependency_changes: forbidden", "- dependency_changes: forbidden（只加命令入口，不增删依赖）") \
        .replace("- risk_level: medium", "- risk_level: `medium` (改动集中)")
    (repo / ".agent/plans/derived-task.v1.md").write_text(md, encoding="utf-8")
    code, out = tool(repo, "derive-json", "derived-task.v1", "--title", "带说明")
    data = jload(repo / ".agent/plans/derived-task.v1.json")
    check("annotated single values are derived without the note", code == 0 and "合同有效" in out
          and data["scope"]["dependency_changes"] == "forbidden" and data["risk_level"] == "medium", out)


def test_mutate():
    """1.3.0：mutate 在干净副本上逐个套用变异，报告抓住 / 漏掉 / 跳过，不改动执行 worktree。"""
    repo, base = make_repo("v130mutate")
    run_ok(repo)
    spec = {
        "command": [PY, "run_tests.py"],
        "timeout_seconds": 120,
        "mutations": [
            {"name": "不转小写", "file": "src/normalize.py", "old": ".lower()", "new": ""},
            {"name": "等价改写", "file": "src/normalize.py", "old": "q.split()", "new": "q.split(None)"},
            {"name": "锚点不存在", "file": "src/normalize.py", "old": "strip()", "new": "lstrip()"},
            {"name": "次数不符", "file": "src/normalize.py", "old": ".lower()", "new": ".upper()", "count": 2},
            {"name": "多行锚点", "file": "src/normalize.py", "old": "def normalize(q):\n    return",
             "new": "def normalize(q):\n    q = q + ' x'\n    return"},
        ],
    }
    spec_path = WORK / "v130-spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    worktree = worktree_of(repo)
    before = (worktree / "src/normalize.py").read_bytes()
    code, out = tool(repo, "mutate", "normalize-query/attempt-001", "--spec", str(spec_path))
    record = jload(rd(repo) / "mutations/01/mutations.json")
    statuses = [r["status"] for r in record.get("results", [])]
    check("mutate reports caught / missed / skipped",
          code == 0 and statuses == ["caught", "missed", "skipped", "skipped", "caught"]
          and record["counts"] == {"caught": 2, "missed": 1, "skipped": 2, "error": 0}
          and "抓住 2，漏掉 1，跳过 2" in out and "锚点不存在" in out, (out, statuses))
    check("mutate records the reason for a skipped mutation",
          record["results"][3]["count_found"] == 1 and "出现 1 次，期望 2 次" in record["results"][3]["reason"],
          record["results"][3])
    check("mutate keeps logs and the spec", (rd(repo) / "mutations/01/M01.log").is_file()
          and (rd(repo) / "mutations/01/baseline.log").is_file() and (rd(repo) / "mutations/01/spec.json").is_file())
    check("mutate leaves the executor worktree and candidate untouched",
          (worktree / "src/normalize.py").read_bytes() == before and record["candidate_files_left_modified"] == []
          and not Path(record["workspace"]).exists(), record.get("workspace"))
    code, out = tool(repo, "check", "normalize-query/attempt-001")
    check("check still passes after mutate", code == 0, out)

    bad = {"command": [], "mutations": [{"name": "x", "file": "../a.py", "old": "a", "new": "a"}]}
    bad_path = WORK / "v130-bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    code, out = tool(repo, "mutate", "normalize-query/attempt-001", "--spec", str(bad_path))
    check("invalid mutation spec is rejected with every problem listed",
          code == 2 and "command" in out and "file" in out and "不构成变异" in out
          and not (rd(repo) / "mutations/02").exists(), out)

    failing = dict(spec, command=[PY, "-c", "import sys; sys.exit(3)"])
    failing_path = WORK / "v130-failing.json"
    failing_path.write_text(json.dumps(failing, ensure_ascii=False), encoding="utf-8")
    code, out = tool(repo, "mutate", "normalize-query/attempt-001", "--spec", str(failing_path))
    aborted = jload(rd(repo) / "mutations/02/mutations.json")
    check("mutate refuses when the command fails without mutations",
          code != 0 and "没有通过" in out and aborted.get("aborted") == "baseline_failed", out)


def test_v2_planner_adapters():
    """2.0.0：技能唯一来源在 .agents/skills，sync-adapters 生成 Claude Code 副本；wait；doctor 的规划端检查。"""
    missing, drift = pd.adapter_drift(KIT)
    check("kit adapters are in sync with .agents/skills", missing == [] and drift == [], (missing, drift[:5]))
    check("kit has no CLAUDE.md and no legacy rules", not (KIT / "CLAUDE.md").exists()
          and not (KIT / ".claude" / "rules").exists())
    agents_size = (KIT / "AGENTS.md").stat().st_size
    check("kit AGENTS.md fits Codex project_doc_max_bytes", agents_size <= pd.CODEX_PROJECT_DOC_MAX_BYTES, agents_size)

    repo, base = make_repo("v2adapters")
    code, out = tool(repo, "sync-adapters", "--check")
    check("sync-adapters refuses a repo without .agents/skills", code != 0 and "1.x" in out, out)
    for name in pd.KIT_SKILLS:
        skill = repo / ".agents/skills" / name
        (skill / "refs").mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: %s\ndescription: d\n---\n\n# %s\n" % (name, name), encoding="utf-8")
        (skill / "refs" / "note.md").write_text("note %s\n" % name, encoding="utf-8")
    other = repo / ".claude/skills/own-skill/SKILL.md"
    other.parent.mkdir(parents=True)
    other.write_text("---\nname: own-skill\ndescription: mine\n---\n", encoding="utf-8")
    code, out = tool(repo, "sync-adapters", "--check")
    check("sync-adapters --check reports missing copies", code == 1 and "DRIFT plan-task/SKILL.md" in out, out)
    code, out = tool(repo, "sync-adapters")
    copied = (repo / ".claude/skills/review-pi/refs/note.md").read_text(encoding="utf-8")
    check("sync-adapters copies whole skill directories", code == 0 and copied == "note review-pi\n", out)
    code, out = tool(repo, "sync-adapters", "--check")
    check("sync-adapters --check passes after sync", code == 0 and "一致" in out, out)
    (repo / ".claude/skills/plan-task/SKILL.md").write_text("edited copy\n", encoding="utf-8")
    (repo / ".claude/skills/plan-task/stray.md").write_text("stray\n", encoding="utf-8")
    code, out = tool(repo, "sync-adapters", "--check")
    check("sync-adapters --check reports edited and stray copies", code == 1 and "plan-task/SKILL.md：内容不同" in out
          and "plan-task/stray.md：副本多出" in out, out)
    code, out = tool(repo, "sync-adapters")
    check("sync-adapters restores the copy and leaves other skills alone",
          code == 0 and not (repo / ".claude/skills/plan-task/stray.md").exists()
          and other.read_text(encoding="utf-8").startswith("---") and "plan-task" in out, out)

    facts = {}
    notes = pd.planner_file_notes(repo, facts)
    check("doctor notes: nothing to report for a synced repo with AGENTS.md",
          notes == [] and facts["agents_md_bytes"] > 0, notes)
    (repo / "CLAUDE.md").write_text("# project rules\n", encoding="utf-8")
    notes = pd.planner_file_notes(repo, {})
    check("doctor notes a CLAUDE.md without @AGENTS.md", any("@AGENTS.md" in n for n in notes), notes)
    (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    notes = pd.planner_file_notes(repo, {})
    check("doctor accepts a CLAUDE.md that imports AGENTS.md", notes == [], notes)
    (repo / "AGENTS.md").write_text("x" * (pd.CODEX_PROJECT_DOC_MAX_BYTES + 1), encoding="utf-8")
    notes = pd.planner_file_notes(repo, {})
    check("doctor notes an AGENTS.md over the Codex limit", any("project_doc_max_bytes" in n for n in notes), notes)
    shutil.rmtree(str(repo / ".agents"))
    notes = pd.planner_file_notes(repo, {})
    check("doctor notes the 1.x layout", any("1.x" in n for n in notes), notes)

    repo, base = make_repo("v2wait")
    run_ok(repo)
    code, out = tool(repo, "wait", "normalize-query/attempt-001")
    check("wait returns at once for a finished attempt", code == 0 and "已结束" in out and "NEEDS_REVIEW" in out, out)
    pd.set_state(rd(repo), "RUNNING")
    code, out = tool(repo, "wait", "normalize-query/attempt-001", "--timeout", "1", "--interval", "0.2")
    check("wait times out on a running attempt with exit code 3", code == 3 and "仍在运行" in out, out)
    pd.set_state(rd(repo), "NEEDS_REVIEW")
    instruction = (rd(repo) / "instruction.md").read_text(encoding="utf-8")
    check("execution instructions protect .agents/ and .codex/", ".agents/、.claude/、.codex/" in instruction)
    tool(repo, "prepare", "normalize-query.v1")
    code, out = tool(repo, "wait", "normalize-query/attempt-002", "--timeout", "1", "--interval", "0.2")
    check("wait reports an attempt that never started", code == 3 and "PREPARED" in out, out)


def _dir_link(link, target):
    """建一个指向 target 的目录链接：先试符号链接，Windows 上再试 junction；都不行时返回 False。"""
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return True
    except (OSError, NotImplementedError, AttributeError):
        pass
    if os.name == "nt":
        try:
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
            return True
        except (OSError, ImportError, AttributeError):
            return False
    return False


def _junction_or_link(link, target):
    """Windows 上优先建 junction（Python 3.12 之前 islink 认不出它），其他平台建符号链接。"""
    if os.name == "nt":
        try:
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
            return "junction"
        except (OSError, ImportError, AttributeError):
            pass
    return "symlink" if _dir_link(link, target) else None


def _remove_dir_link(link):
    try:
        os.rmdir(str(link)) if os.name == "nt" else os.unlink(str(link))
    except OSError:
        pass


def test_v2_review_fixes():
    """2.0.0 的 Codex 审查修正：同步的路径边界、--check 与缺失源、仅 Codex 安装、wait 的未知状态。"""
    repo, base = make_repo("v2fixes")
    for name in pd.KIT_SKILLS:
        skill = repo / ".agents/skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: %s\ndescription: d\n---\n" % name, encoding="utf-8")

    facts = {}
    notes = pd.planner_file_notes(repo, facts)
    check("codex-only install is not reported as adapter drift",
          not any("不一致" in n for n in notes) and facts["claude_skill_adapters"]["installed"] is False, notes)

    code, out = tool(repo, "sync-adapters")
    check("sync-adapters creates the copies", code == 0 and (repo / ".claude/skills/plan-task/SKILL.md").is_file(), out)
    shutil.rmtree(str(repo / ".agents/skills/review-pi"))
    code, out = tool(repo, "sync-adapters", "--check")
    check("sync-adapters --check fails when one source is missing", code == 1 and "缺少源文件" in out, out)
    code, out = tool(repo, "sync-adapters")
    check("sync-adapters reports skills it could not sync", code == 1 and "review-pi" in out, out)
    (repo / ".agents/skills/review-pi").mkdir()
    (repo / ".agents/skills/review-pi/SKILL.md").write_text("---\nname: review-pi\ndescription: d\n---\n",
                                                           encoding="utf-8")

    outside = WORK / "v2fixes-outside"
    remove_tree(outside)
    (outside / "plan-task").mkdir(parents=True)
    (outside / "plan-task" / "keep.md").write_text("keep\n", encoding="utf-8")
    shutil.rmtree(str(repo / ".claude/skills"))
    if _dir_link(repo / ".claude/skills", outside):
        try:
            code, out = tool(repo, "sync-adapters")
            check("sync-adapters refuses a linked .claude/skills and leaves the target alone",
                  code != 0 and "链接" in out and (outside / "plan-task" / "keep.md").is_file()
                  and not (outside / "plan-task" / "SKILL.md").exists(), out)
        finally:
            _remove_dir_link(repo / ".claude/skills")
    else:
        check("directory links unavailable here; link refusal not exercised", True)
    remove_tree(outside)

    # 外部目录的内容与源完全相同：不做链接校验时 --check 会误报“一致”。
    mirror = WORK / "v2fixes-mirror"
    remove_tree(mirror)
    shutil.copytree(str(repo / ".agents/skills"), str(mirror))
    if (repo / ".claude/skills").exists():
        shutil.rmtree(str(repo / ".claude/skills"))
    if _junction_or_link(repo / ".claude/skills", mirror):
        try:
            code, out = tool(repo, "sync-adapters", "--check")
            check("sync-adapters --check refuses a linked copy even when its content matches",
                  code != 0 and "链接" in out and "一致。" not in out, out)
            notes = pd.planner_file_notes(repo, {})
            check("doctor reports a linked .claude/skills", any("链接" in n for n in notes), notes)
        finally:
            _remove_dir_link(repo / ".claude/skills")
    else:
        check("directory links unavailable here; linked copy not exercised", True)
    remove_tree(mirror)
    code, out = tool(repo, "sync-adapters")
    check("sync-adapters recreates real copies after the link is removed",
          code == 0 and (repo / ".claude/skills/plan-task/SKILL.md").is_file()
          and not pd._is_link_or_junction(str(repo / ".claude/skills")), out)

    secret = WORK / "v2fixes-secret"
    remove_tree(secret)
    secret.mkdir(parents=True)
    (secret / "outside.md").write_text("outside\n", encoding="utf-8")
    nested = repo / ".agents/skills/plan-task/linked"
    kind = _junction_or_link(nested, secret)
    if kind:
        try:
            code, out = tool(repo, "sync-adapters")
            copied = sorted(p.relative_to(repo / ".claude/skills/plan-task").as_posix()
                            for p in (repo / ".claude/skills/plan-task").rglob("*") if p.is_file())
            check("sync-adapters does not follow a nested %s in a source skill" % kind,
                  code == 0 and copied == ["SKILL.md"] and "outside.md" not in out, (kind, copied, out))
            check("drift check ignores the nested %s too" % kind, pd.adapter_drift(repo) == ([], []),
                  pd.adapter_drift(repo))
        finally:
            _remove_dir_link(nested)
    else:
        check("directory links unavailable here; nested link not exercised", True)
    remove_tree(secret)

    shutil.move(str(repo / ".agents/skills"), str(WORK / "v2fixes-moved-skills"))
    kind = _junction_or_link(repo / ".agents/skills", WORK / "v2fixes-moved-skills")
    if kind:
        try:
            before = sorted(p.as_posix() for p in (repo / ".claude/skills").rglob("*"))
            code, out = tool(repo, "sync-adapters")
            after = sorted(p.as_posix() for p in (repo / ".claude/skills").rglob("*"))
            check("sync-adapters refuses a linked .agents/skills (%s)" % kind,
                  code != 0 and "链接" in out and before == after, out)
            notes = pd.planner_file_notes(repo, {})
            check("doctor reports a linked .agents/skills instead of crashing", any("链接" in n for n in notes), notes)
        finally:
            _remove_dir_link(repo / ".agents/skills")
    else:
        check("directory links unavailable here; linked source not exercised", True)
    shutil.move(str(WORK / "v2fixes-moved-skills"), str(repo / ".agents/skills"))

    # 源缺失的技能：副本目录是链接时，doctor 也要报出，而不是跳过。
    shutil.rmtree(str(repo / ".agents/skills/review-pi"))
    shutil.rmtree(str(repo / ".claude/skills/review-pi"))
    elsewhere = WORK / "v2fixes-elsewhere"
    remove_tree(elsewhere)
    (elsewhere / "sub").mkdir(parents=True)
    if _junction_or_link(repo / ".claude/skills/review-pi", elsewhere):
        try:
            notes = pd.planner_file_notes(repo, {})
            check("doctor reports a linked copy even when its source is missing", any("链接" in n for n in notes), notes)
        finally:
            _remove_dir_link(repo / ".claude/skills/review-pi")
    else:
        check("directory links unavailable here; linked copy without source not exercised", True)
    remove_tree(elsewhere)

    # CLAUDE.md 是链接：指向本仓库的 AGENTS.md 属于合法做法；指向仓库之外时提示且不读取。
    outside_rules = WORK / "v2fixes-outside-rules.md"
    outside_rules.write_text("# outside\n", encoding="utf-8")
    try:
        os.symlink(str(repo / "AGENTS.md"), str(repo / "CLAUDE.md"))
        file_links = True
    except (OSError, NotImplementedError, AttributeError):
        file_links = False
    if file_links:
        notes = pd.planner_file_notes(repo, {})
        check("CLAUDE.md linked to AGENTS.md is accepted", not any("CLAUDE.md" in n for n in notes), notes)
        os.unlink(str(repo / "CLAUDE.md"))
        os.symlink(str(outside_rules), str(repo / "CLAUDE.md"))
        notes = pd.planner_file_notes(repo, {})
        check("CLAUDE.md linked outside the repo is reported", any("CLAUDE.md 是指向仓库之外的链接" in n for n in notes), notes)
        os.unlink(str(repo / "CLAUDE.md"))
    else:
        check("file symlinks unavailable here; CLAUDE.md link cases not exercised", True)
    outside_rules.unlink()

    repo, base = make_repo("v2waitstate")
    run_ok(repo)
    state_file = rd(repo) / "state.json"
    saved = state_file.read_bytes()
    state_file.write_text("{", encoding="utf-8")
    code, out = tool(repo, "wait", "normalize-query/attempt-001", "--timeout", "1", "--interval", "0.2")
    check("wait does not report an unreadable state as finished", code == 1 and "无法确定" in out, out)
    state_file.write_bytes(saved)


IDENTITY_VARS = ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL", "EMAIL")


def test_v21_codex_trial_feedback():
    """Codex 规划端试跑的反馈（2.1.0）与 Codex 复审：临时目录提示、歧义提示、doctor 的脱敏与模型列表、
    Git 身份预检、按次指定提交尾注、prepare 的提示。"""
    # 临时路径的写法：命中就列入复审关注，不判断是否已清理。
    hits = {
        "cd /tmp && ls": True, 'cp out "$TMPDIR/x"': True, "Get-Content $env:TEMP\\a.txt": True,
        "dir %TEMP%": True, r"type C:\Users\me\AppData\Local\Temp\x.log": True,
        "python -c 'import tempfile; print(tempfile.gettempdir())'": True,
        "cp x /var/tmp/y": True, "ls /private/tmp": True, 'echo "$TEMP"': True, "ls ${TMP}/x": True,
        r"dir C:\Windows\Temp": True, "from tempfile import mkdtemp": True, "d = mkdtemp()": True,
        "os.environ['TEMP']": True, 'os.getenv("TMP")': True,
        "python -m pytest -q --basetemp=.agent/runs/_tmp/pytest": False, "ls src/tmp tests/tmp_path ./tmp": False,
        "def test_x(tmp_path): pass": False, "cat ~/tmp/x": False, 'echo "$TMPD"': False, "ls $TMP_DIR": False,
        # Codex 第六轮：不带空格的重定向照常计入，只有 <worktree> 里的 tmp 子目录不算。
        "printf x >/tmp/pi-review-out": True, "run 2>/var/tmp/pi-review-error": True,
        "run >>/private/tmp/pi-review-log": True, "cd <worktree>/tmp/x": False,
    }
    got = {command: bool(pd.TEMP_PATH_RE.search(command)) for command in hits}
    check("temp path pattern covers common forms and skips workspace paths", got == hits, got)
    # 默认的 worktree 建在系统临时目录下：扫描前先把工作目录的各种写法换成 <worktree>。
    forms = pd._path_forms([Path(r"C:\Users\me\AppData\Local\Temp\2\pi-worktrees\wt-a001")])
    masked = pd._mask_paths('cd "C:/Users/me/AppData/Local/Temp/2/pi-worktrees/wt-a001" && ls; '
                            'cd /c/Users/me/AppData/Local/Temp/2/pi-worktrees/wt-a001/src; '
                            r'type C:\Users\me\AppData\Local\Temp\2\pi-worktrees\wt-a001\x.txt', forms)
    check("the worktree path is masked in every spelling before the temp scan",
          masked.count("<worktree>") == 3 and not pd.TEMP_PATH_RE.search(masked), masked)
    # 只屏蔽工作目录之内的路径：同名前缀的兄弟目录、用 .. 跳出去的路径照常计入。
    outside = ["ls C:/Users/me/AppData/Local/Temp/2/pi-worktrees/wt-a001-other/x",
               "ls C:/Users/me/AppData/Local/Temp/2/pi-worktrees/wt-a001/../victim/x",
               "ls C:/Users/me/AppData/Local/Temp/2/pi-worktrees/wt-a001/sub/../../victim"]
    check("paths outside the worktree are not masked",
          all(pd._mask_paths(command, forms) == command for command in outside)
          and pd._mask_paths("ls C:/Users/me/AppData/Local/Temp/2/pi-worktrees/wt-a001/sub/..", forms)
          == "ls <worktree>/sub/..", [pd._mask_paths(command, forms) for command in outside])
    # Codex 第五轮：左边界、引号拼接与带空格的参数都按完整参数判断；工作目录里名叫 tmp 的子目录不算临时路径。
    posix = pd._path_forms([Path("/tmp/pi-wt")])
    outside = ["ls /var/tmp/pi-wt/x", 'ls "/tmp/pi-wt"-other/x', 'ls "/tmp/pi-wt/dir with space/../../victim/x"']
    outside += ['ls "/var""/tmp/pi-wt/x"', r'ls "/tmp/pi-wt/dir\" with space/../../victim/x"',
                "ls /tmp/pi-wt/${SUB}/../x", r"ls /tmp/pi-wt/dir\ with\ space/../../victim/x"]
    inside = {'ls "/tmp/pi-wt/dir with space/x"': 'ls "<worktree>/dir with space/x"',
              "cd /tmp/pi-wt/tmp/x && ls": "cd <worktree>/tmp/x && ls", 'X="/tmp/pi-wt/y"': 'X="<worktree>/y"'}
    check("masking works on whole arguments",
          all(pd._mask_paths(command, posix) == command for command in outside)
          and all(pd._mask_paths(command, posix) == want and not pd.TEMP_PATH_RE.search(want)
                  for command, want in inside.items()),
          [pd._mask_paths(command, posix) for command in outside + list(inside)])

    # 摘要只保留 50 条临时路径记录，另记总数。
    stream = WORK / "v21-temp-truncation"
    stream.mkdir(parents=True, exist_ok=True)
    commands = ['T=$(mktemp -d); run "$T"; rm -rf "$T"'] * 50 + ['python -c "import tempfile; tempfile.mkdtemp()"']
    (stream / "events.jsonl").write_text("".join(json.dumps(
        {"type": "tool_execution_start", "toolCallId": "t%d" % i, "toolName": "bash", "args": {"command": c}}) + "\n"
        for i, c in enumerate(commands)), encoding="utf-8")
    ev, _text = pd.summarize_events(stream / "events.jsonl", stream,
                                    {"provider": "step", "model": "step-5-preview", "thinking": "high"})
    check("temp path uses keep 50 records and the full count", ev["temp_path_use_count"] == 51
          and len(ev["temp_path_uses"]) == 50, (ev["temp_path_use_count"], len(ev["temp_path_uses"])))

    # 只是在检查合同有没有矛盾（Codex 规划端试跑的原文）：仍然提示，但写明可能只是在检查；
    # 报告标题“### 合同矛盾”下一行的“未发现。”是紧跟的否定答案，不提示。
    repo, base = make_repo("v21checkonly")
    run_ok(repo, STUB_SCENARIO="checkonly")
    ev = jload(rd(repo) / "events-summary.json")
    summary = (rd(repo) / "summary.md").read_text(encoding="utf-8")
    check("a checking sentence is still mentioned, with a softened hint", ev["ambiguity_mention_count"] == 1
          and ev["ambiguity_mentions"][0]["kind"] == "thinking" and "可能只是在检查" in summary,
          ev.get("ambiguity_mentions"))

    # doctor 与预检记录外部命令的输出之前先脱敏；模型表格只解析表头之后的行。
    samples = {"apiKey=DEMO_TOKEN_FOR_REVIEW": "DEMO_TOKEN_FOR_REVIEW",
               '{"apiKey": "sk-demo-1234567890abcdef"}': "sk-demo-1234567890abcdef",
               "Authorization: Bearer abcdefghijklmnop": "abcdefghijklmnop", "PI_API_KEY=xyz123": "xyz123",
               "Authorization: Basic REVJRVdfU0VDUkVU": "REVJRVdfU0VDUkVU",
               '{"password":"demo pass phrase"}': "pass phrase", '"Authorization": "Basic abc123def"': "abc123def",
               # Codex 第三轮：嵌套在字符串里的 JSON、转义引号、Digest、按键名整体遮蔽的 JSON 值。
               '{"error":"{\\"apiKey\\":\\"DEMO_REVIEW_SECRET\\"}"}': "DEMO_REVIEW_SECRET",
               '{"password":"prefix\\"DEMO_REVIEW_SECRET2"}': "DEMO_REVIEW_SECRET2",
               'x password="prefix\\"DEMO_REVIEW_SECRET3" y': "DEMO_REVIEW_SECRET3",
               'Authorization: Digest username="alice", response="DEMO_REVIEW_SECRET4"': "DEMO_REVIEW_SECRET4",
               'error: {\\"apiKey\\":\\"DEMO_REVIEW_SECRET5\\"} while loading': "DEMO_REVIEW_SECRET5",
               '{"credentials": {"user": "a", "pass": "DEMO_REVIEW_SECRET6"}}': "DEMO_REVIEW_SECRET6",
               # Codex 第四轮：多层转义、未闭合的引号。
               r'error: {\"password\": \"prefix\\\"DEMO_REVIEW_SECRET7\"} while loading': "DEMO_REVIEW_SECRET7",
               'JSON parse error near {"apiKey":"DEMO_REVIEW_SECRET8': "DEMO_REVIEW_SECRET8",
               # Codex 第五轮：多层转义的 Authorization、不带引号且含反斜杠的值。
               r'error: {\\\"Authorization\\\": \\\"Basic REVJRVdfU0VDUkVU9\\\"} while loading': "REVJRVdfU0VDUkVU9",
               r'password=prefix\DEMO_REVIEW_SECRET10': "DEMO_REVIEW_SECRET10",
               r'password=\DEMO_REVIEW_SECRET11': "DEMO_REVIEW_SECRET11"}
    # Codex 第六轮：日志前缀后的多行 JSON、API key 的写法、键名后面的 ANSI 样式、折行的 Digest、不完整的多行对象。
    samples.update({
        'error: {\n  "credentials": {\n    "user": "demo",\n    "pass": "SYNTHETIC_CREDENTIAL1"\n  }\n}':
            "SYNTHETIC_CREDENTIAL1",
        "API key: SYNTHETIC_CREDENTIAL2": "SYNTHETIC_CREDENTIAL2",
        '"apiKey"' + chr(27) + '[0m: "SYNTHETIC_CREDENTIAL3"': "SYNTHETIC_CREDENTIAL3",
        'Authorization: Digest username="alice",\n    response="SYNTHETIC_CREDENTIAL4"': "SYNTHETIC_CREDENTIAL4",
        'broken: {\n  "credentials": {\n    "pass": "SYNTHETIC_CREDENTIAL5"\n': "SYNTHETIC_CREDENTIAL5",
        # Codex 第七轮：每行带前缀的日志、不缩进的 PEM 私钥、隔着空行的容器、换到下一行的值与折行的 Digest。
        '[ERROR] {\n[ERROR]   "credentials": {\n[ERROR]     "pass": "SYNTHETIC_CREDENTIAL6"\n[ERROR]   }\n[ERROR] }':
            "SYNTHETIC_CREDENTIAL6",
        "key file:\n-----BEGIN PRIVATE KEY-----\nMIIESYNTHETICCREDENTIAL7\n-----END PRIVATE KEY-----": "SYNTHETICCREDENTIAL7",
        'config: "credentials": {\n\n  "pass": "SYNTHETIC_CREDENTIAL8"\n}': "SYNTHETIC_CREDENTIAL8",
        "password:\nSYNTHETIC_CREDENTIAL9": "SYNTHETIC_CREDENTIAL9",
        'Authorization: Digest username="alice",\nresponse="SYNTHETIC_CREDENTIAL10"': "SYNTHETIC_CREDENTIAL10",
        "password: abc\n  SYNTHETIC_CREDENTIAL11\nnext: 1": "SYNTHETIC_CREDENTIAL11",
        # Codex 第八轮：YAML 块标量的值在下一行，可能还隔着日志前缀或空行。
        "[ERROR] password: |-\n[ERROR]   SYNTHETIC_CREDENTIAL12": "SYNTHETIC_CREDENTIAL12",
        "password: >\n\n  SYNTHETIC_CREDENTIAL13": "SYNTHETIC_CREDENTIAL13",
        # Codex 第九轮：重复的键（解码后只剩最后一个值）、带注释或数字在前的 YAML 块标量指示符。
        '{"apiKey":"SYNTHETIC_CREDENTIAL14","apiKey":null}': "SYNTHETIC_CREDENTIAL14",
        "password: | # comment\n\n  SYNTHETIC_CREDENTIAL15\nnext: 1": "SYNTHETIC_CREDENTIAL15",
        "password: |2-\n  SYNTHETIC_CREDENTIAL16": "SYNTHETIC_CREDENTIAL16",
    })
    leaked = [text for text, secret in samples.items() if secret in pd.redact_secrets(text)]
    check("embedded JSON keeps metadata and a JSON value of a secret key is masked whole",
          pd.redact_secrets('error: {"apiKey": "x", "tokenCount": 3} tail')
          == 'error: {"apiKey": "<redacted>", "tokenCount": 3} tail'
          and pd.redact_secrets('password: {"a": "s3cret"} tail') == "password: <redacted>"
          and pd.redact_secrets("[INFO] 5 tests passed") == "[INFO] 5 tests passed")
    check("PEM blocks are masked whole, NUL and deep nesting are harmless",
          pd.redact_secrets("key file:\n-----BEGIN PRIVATE KEY-----\nMII\n-----END PRIVATE KEY-----\nafter")
          == "key file:\n<redacted>\nafter"
          and pd.redact_secrets(chr(0) + "0" + chr(0) + ' {"n":1}') == '0 {"n": 1}'
          and pd.redact_secrets("[" * 3000 + " tail").endswith(" tail")
          and pd.redact_secrets("[" * 1100 + "0" + "]" * 1100).startswith("[[[")
          and pd.redact_secrets("at [2026-09-23 12:34:56] done") == "at [2026-09-23 12:34:56] done")
    # Codex 第十轮：重新写出 JSON 时，孤立的代理码点要恢复成转义，否则按 UTF-8 写不出去。
    surrogate = pd.redact_secrets('error: {"message": "' + chr(92) + 'ud800", "apiKey": "x"}')
    try:
        encodable = bool(surrogate.encode("utf-8"))
    except UnicodeEncodeError:
        encodable = False
    check("lone surrogates stay escaped so the output can be written as UTF-8", encodable
          and chr(92) + "ud800" in surrogate and '"apiKey": "<redacted>"' in surrogate, ascii(surrogate))
    check("redact_secrets masks common credential forms", not leaked
          and pd.redact_secrets("Unexpected token 'R' in JSON") == "Unexpected token 'R' in JSON", leaked)
    check("redacted JSON stays valid JSON",
          json.loads(pd.redact_secrets('{"password":"prefix\\"x", "n": 1}')) == {"password": "<redacted>", "n": 1})
    check("structured redaction keeps counts and flags", json.loads(pd.redact_secrets(
        '{"tokenCount":17,"maxTokens":8192,"hasApiKey":false,"apiKey":"x"}')) == {
        "tokenCount": 17, "maxTokens": 8192, "hasApiKey": False, "apiKey": "<redacted>"}
        and pd.redact_secrets("PI_API_KEY=abc path=/x/y\nnext line") == "PI_API_KEY=<redacted>\nnext line")
    # 最终错误先脱敏再截断：凭据跨过截断边界时也不能留下（smoke 的结果就用这段摘要）。
    stream = WORK / "v21-error-redaction"
    stream.mkdir(parents=True, exist_ok=True)
    final = {"role": "assistant", "content": [], "stopReason": "error",
             "errorMessage": "x" * 260 + ' password="' + "DEMO_REVIEW_SECRET" * 6 + '"'}
    (stream / "events.jsonl").write_text(json.dumps({"type": "message_end", "message": final}) + "\n",
                                         encoding="utf-8")
    ev, _text = pd.summarize_events(stream / "events.jsonl", stream,
                                    {"provider": "step", "model": "step-5-preview", "thinking": "high"})
    check("a long final error is redacted before it is cut", any("最终 assistant 错误" in p for p in ev["problems"])
          and "DEMO_REVIEW_SECRET" not in json.dumps(ev["problems"])
          and "DEMO_REVIEW_SECRET" not in json.dumps(ev["final_error"]), (ev["problems"], ev["final_error"]))
    check("model table parsing ignores pi's no-model messages",
          pd.list_models_rows("No models available. Use /login to log in. See:\n  /docs/providers.md") == []
          and pd.list_models_empty_reason("No models available. Use /login") == "no_models"
          and pd.list_models_empty_reason('No models matching "step-5-preview"') == "no_match"
          and pd.list_models_rows("provider  model  context\nstep  step-5-preview  256K") == [("step", "step-5-preview")])

    # 预检写出的 pi 输出同样先脱敏，例如 auth check 的错误里带出了凭据。
    repo, base = make_repo("v21preflight")
    tool(repo, "prepare", "normalize-query.v1")
    code, out = tool(repo, "run", "normalize-query/attempt-001",
                     env={"STUB_AUTH": "not_ready", "STUB_AUTH_DETAIL": "apiKey=DEMO_REVIEW_SECRET"})
    leaked = [str(path.relative_to(rd(repo))) for path in rd(repo).rglob("*") if path.is_file()
              and "DEMO_REVIEW_SECRET" in path.read_text(encoding="utf-8", errors="replace")]
    check("preflight records and output are redacted", code != 0 and "auth" in out
          and "DEMO_REVIEW_SECRET" not in out and not leaked, (leaked, out[-400:]))

    # 规则与执行说明中的临时文件例外写法一致；规划端文档带上 2.1.0 的指引。
    agents = (KIT / "AGENTS.md").read_text(encoding="utf-8")
    phrases = ["中间产物", "T=$(mktemp -d)", 'rm -rf "$T"', "不要切换到其中运行命令", "不受此限"]
    check("the temp-file exception reads the same in AGENTS.md and the executor instruction",
          all(p in agents and p in pd.INSTRUCTION_TEMPLATE for p in phrases),
          [p for p in phrases if p not in agents or p not in pd.INSTRUCTION_TEMPLATE])
    plan_task = (KIT / ".agents/skills/plan-task/SKILL.md").read_text(encoding="utf-8")
    check("planner docs carry the 2.1.0 guidance", "mkdir -p .agent/runs/_tmp" in agents
          and "; exit $LASTEXITCODE" in agents and "只选中新增测试节点" in plan_task)

    # 提交尾注与主题行：拒绝回车、换行等控制字符（回车会重新带出 CRLF）；标题中的换行合并成空格。
    check("trailers reject control characters", [pd.valid_trailer(v) for v in (
        "Key: value", "Key: value\r", "Key: value\rInjected: x", "Key: ", "Key: a\tb", "Key: a\nb")]
        == [True, False, False, False, False, False])
    check("branch subject is a single line", pd.branch_subject("t", "标题\r\n第二行", 1, 1) == "t: 标题 第二行")

    # prepare 的提示与 dispatch-pi 技能一致：缺依赖时出新版本合同补 setup，不在 worktree 里手工准备。
    repo, base = make_repo("v21identity")
    code, out = tool(repo, "prepare", "normalize-query.v1")
    check("prepare without setup points to a new contract version", code == 0 and "出新版本合同补上 setup" in out
          and "check --fresh 无法复现" in out, out)
    tool(repo, "run", "normalize-query/attempt-001", env={"STUB_SCENARIO": "ok"})
    tool(repo, "check", "normalize-query/attempt-001")
    tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "PASS", "--review", review(repo, "PASS"))

    # 没有 Git 身份：隔离全局与系统配置，去掉仓库配置，并禁止按主机名猜测。
    empty_global = WORK / "empty-gitconfig"
    empty_global.write_text("", encoding="utf-8")
    git(repo, "config", "--unset", "user.name")
    git(repo, "config", "--unset", "user.email")
    git(repo, "config", "user.useConfigOnly", "true")
    bare = {k: v for k, v in BASE_ENV.items() if k not in IDENTITY_VARS}
    bare.update(GIT_CONFIG_GLOBAL=str(empty_global), GIT_CONFIG_NOSYSTEM="1")
    code, out = sh([PY, "scripts/pi_dispatch.py", "doctor"], repo, env=bare, check=False)
    data = json.loads(out)
    check("doctor notes a missing git identity early", data["repository"]["git_identity"] is False
          and any("没有可用的 Git 作者身份" in n for n in data["notes"]), data.get("notes"))
    # 候选树对象丢失时，branch 会按补丁重建它。身份缺失时必须在重建之前拒绝，不写任何 Git 对象。
    tree = jload(rd(repo) / "candidate.json")["tree"]
    loose = repo / ".git" / "objects" / tree[:2] / tree[2:]
    os.chmod(str(loose), 0o600)
    loose.unlink()
    code, out = sh([PY, "scripts/pi_dispatch.py", "branch", "normalize-query/attempt-001"], repo, env=bare, check=False)
    exists = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "refs/heads/pi/normalize-query-v1-a001"],
                            cwd=str(repo), env=bare, stdout=subprocess.DEVNULL).returncode == 0
    rebuilt = subprocess.run(["git", "cat-file", "-e", tree], cwd=str(repo), env=bare,
                             stderr=subprocess.DEVNULL).returncode == 0
    check("branch refuses before rebuilding the tree or creating anything when the identity is missing", code != 0
          and "没有可用的 Git 作者身份" in out and "GIT_AUTHOR_NAME" in out and not exists and not rebuilt, out)

    # 提供身份后可以创建；--no-config-trailers 去掉仓库的固定尾注，--trailer 写上本次的署名。
    config_trailer = "Co-Authored-By: Example Bot <bot@example.invalid>"
    codex_trailer = "Co-Authored-By: Codex <codex@example.invalid>"
    write_config(repo, commit_trailers=[config_trailer])
    named = dict(bare, GIT_AUTHOR_NAME="planner", GIT_AUTHOR_EMAIL="p@example.invalid",
                 GIT_COMMITTER_NAME="planner", GIT_COMMITTER_EMAIL="p@example.invalid")
    for bad in ("Bad trailer", "Key: value\r", "Key: value\rInjected: extra"):
        code, out = sh([PY, "scripts/pi_dispatch.py", "branch", "normalize-query/attempt-001", "--name", "pi/bad",
                        "--trailer", bad], repo, env=named, check=False)
        check("an invalid --trailer is a usage error: %r" % bad, code == pd.EXIT_USAGE and "--trailer" in out, out)
    write_config(repo, commit_trailers=["Key: value\r"])
    code, out = sh([PY, "scripts/pi_dispatch.py", "branch", "normalize-query/attempt-001", "--name", "pi/bad"],
                   repo, env=named, check=False)
    check("a configured trailer with CR is rejected", code == pd.EXIT_USAGE and "commit_trailers" in out, out)
    write_config(repo, commit_trailers=[config_trailer])
    code, out = sh([PY, "scripts/pi_dispatch.py", "branch", "normalize-query/attempt-001", "--no-config-trailers",
                    "--trailer", codex_trailer], repo, env=named, check=False)
    message = git(repo, "log", "-1", "--format=%B", "pi/normalize-query-v1-a001") if code == 0 else out
    author = git(repo, "log", "-1", "--format=%an <%ae>", "pi/normalize-query-v1-a001") if code == 0 else ""
    check("branch rebuilds the tree and uses the per-run trailer instead of the configured one", code == 0
          and codex_trailer in message and config_trailer not in message
          and "Pi-Executor: step/step-5-preview (thinking high)" in message
          and author == "planner <p@example.invalid>", (message, author))
    code, out = sh([PY, "scripts/pi_dispatch.py", "branch", "normalize-query/attempt-001", "--name", "pi/second",
                    "--trailer", codex_trailer], repo, env=named, check=False)
    message = git(repo, "log", "-1", "--format=%B", "pi/second") if code == 0 else out
    check("--trailer is appended after the configured trailers", code == 0
          and message.rstrip().endswith(config_trailer + "\n" + codex_trailer), message)
    raw = subprocess.run(["git", "cat-file", "commit", "pi/second"], cwd=str(repo), stdout=subprocess.PIPE).stdout
    check("branch commit message has LF line endings only", code == 0 and b"\r" not in raw, raw[-200:])

def test_v22_netperf_feedback():
    """2.2.0：WoMovieTest netperf 项目（Claude Code 规划端）的反馈。"""
    # 1. base_sha 只落后规划路径的提交 → NOTE；落后代码提交 → WARN
    repo, base = make_repo("v22-note")
    git(repo, "add", "-A")  # 配置与合同先入库，再以这个提交为基线：真实流程里配置早就在基线中
    git(repo, "commit", "-qm", "config and plan")
    base = git(repo, "rev-parse", "HEAD")
    write_plan(repo, base, 1)
    (repo / ".agent/plans/other.md").write_text("# other\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "plans only")
    code, out = tool(repo, "validate", "normalize-query.v1")
    check("base behind HEAD by planner paths only is a NOTE", code == 0 and "NOTE  base_sha 不是当前 HEAD" in out
          and "WARN  base_sha" not in out, out)
    (repo / "src/other.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "code")
    code, out = tool(repo, "validate", "normalize-query.v1")
    check("base behind HEAD by code is still a WARN", code == 0 and "WARN  base_sha 不是当前 HEAD" in out, out)

    # 2. baseline：只新增的测试文件在基线上不存在 → 说明文字点明属正常
    repo, base = make_repo("v22-baseline")
    checks = default_checks() + [{"id": "V02", "argv": [PY, "tests/test_missing.py"], "cwd": ".",
                                  "timeout_seconds": 60, "required": True, "expected_exit_code": 0}]
    write_plan(repo, base, 1, checks=checks)
    code, out = tool(repo, "baseline", "normalize-query.v1")
    check("baseline explains a missing test file instead of implying a fix task", code == 0
          and "只新增测试文件的合同在基线上本就如此" in out, out)

    # 3. branch 按 HEAD 是否仍是基线给出集成命令
    repo, base = make_repo("v22-branch")
    run_ok(repo)
    tool(repo, "check", "normalize-query/attempt-001")
    tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "PASS", "--review", review(repo, "PASS"))
    code, out = tool(repo, "branch", "normalize-query/attempt-001")
    check("branch suggests ff-only while HEAD is still the base", code == 0 and "git merge --ff-only" in out, out)
    (repo / ".agent/plans/next.md").write_text("# next\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "contracts")
    code, out = tool(repo, "branch", "normalize-query/attempt-001", "--name", "pi/second")
    check("branch suggests cherry-pick once HEAD moved past the base", code == 0 and "git cherry-pick" in out
          and "git merge --ff-only" not in out, out)

    # 4. autocrlf 在运行后被改动：快照沿用 prepare 记录的值，G6 仍然通过
    repo, base = make_repo("v22-crlf")
    git(repo, "config", "core.autocrlf", "true")
    run_ok(repo)
    meta = jload(rd(repo) / "meta.json")
    check("prepare records the effective core.autocrlf", meta.get("git_autocrlf") == "true", meta.get("git_autocrlf"))
    code, out = tool(repo, "check", "normalize-query/attempt-001")
    check("check passes with autocrlf=true worktree", code == 0, out)
    git(repo, "config", "core.autocrlf", "false")
    code, out = tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "PASS", "--review", review(repo, "PASS"))
    check("verdict PASS survives a later autocrlf change (snapshot pinned to the recorded value)", code == 0, out)
    code, out = tool(repo, "branch", "normalize-query/attempt-001")
    check("branch rebuilds the tree with the recorded autocrlf", code == 0, out)
    # line_endings_only：只差行尾的两棵树被认出来
    (repo / "src/eol.py").write_bytes(b"a = 1\nb = 2\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "lf")
    tree_lf = git(repo, "rev-parse", "HEAD^{tree}")
    (repo / "src/eol.py").write_bytes(b"a = 1\r\nb = 2\r\n")
    git(repo, "-c", "core.autocrlf=false", "add", "-A")
    git(repo, "commit", "-qm", "crlf")
    tree_crlf = git(repo, "rev-parse", "HEAD^{tree}")
    (repo / "src/eol.py").write_bytes(b"a = 2\n")
    git(repo, "-c", "core.autocrlf=false", "add", "-A")
    git(repo, "commit", "-qm", "content")
    tree_other = git(repo, "rev-parse", "HEAD^{tree}")
    check("line_endings_only recognises CRLF-only drift", pd.line_endings_only(repo, tree_lf, tree_crlf)
          and not pd.line_endings_only(repo, tree_lf, tree_other))

    # 5. 执行说明写明 prepare 已运行的 setup，并说明不必自做突变反测
    repo, base = make_repo("v22-setup")
    setup = [{"id": "S01", "argv": [PY, "-c", "print('setup done')"], "cwd": ".", "timeout_seconds": 60}]
    write_plan(repo, base, 1, setup=setup)
    run_ok(repo)
    instruction = (rd(repo) / "instruction.md").read_text(encoding="utf-8")
    check("instruction tells the executor which setup already ran", "准备阶段已经做过的事" in instruction
          and "S01" in instruction and "退出码 0" in instruction, instruction[-1500:])
    check("instruction says the reviewer runs mutate, executor need not self-mutate",
          "变异检查（mutate）" in instruction, instruction[:200])
    repo, base = make_repo("v22-nosetup")
    run_ok(repo)
    instruction = (rd(repo) / "instruction.md").read_text(encoding="utf-8")
    check("instruction has no setup section when the contract has no setup", "准备阶段已经做过的事" not in instruction)

    # 6. Repository facts 点名的文件不在基线里 → WARN；已有文件与本任务要新建的文件不提示（2.2.1）
    repo, base = make_repo("v22-facts")
    md = build_md(contract(base)).replace(
        "- src/normalize.py 中的 normalize(q)。",
        "- 入口：`src/normalize.py`；上游类型（基线已含）：`src/report.ts` 的 `Report`；本任务新增 `tests/test_normalize.py`；模式 `src/**/*.py` 不查。")
    write_plan(repo, base, 1, md=md)
    code, out = tool(repo, "validate", "normalize-query.v1")
    check("validate warns about a Repository-facts file missing from the base", code == 0
          and "在基线" in out and "src/report.ts" in out and "src/normalize.py" not in out.split("不存在")[-1]
          and "tests/test_normalize.py" not in out, out)
    md = build_md(contract(base)).replace("- src/normalize.py 中的 normalize(q)。", "- 入口：`src/normalize.py`。")
    write_plan(repo, base, 1, md=md)
    code, out = tool(repo, "validate", "normalize-query.v1")
    check("validate is quiet when every Repository-facts file exists in the base", code == 0 and "在基线" not in out, out)

    # 6b. 路径写成相对检查 cwd 的形式（例如子项目目录）也算存在（2.2.2）
    repo, base = make_repo("v22-facts-cwd")
    (repo / "sub" / "src").mkdir(parents=True)
    (repo / "sub" / "src" / "x.py").write_text("x = 1\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "sub project")
    base = git(repo, "rev-parse", "HEAD")
    checks = [dict(default_checks()[0], cwd="sub")]
    md = build_md(contract(base, checks=checks)).replace("- src/normalize.py 中的 normalize(q)。", "- 入口：`src/x.py`（相对 sub/）；根上的 `src/normalize.py`。")
    write_plan(repo, base, 1, md=md, checks=checks)
    code, out = tool(repo, "validate", "normalize-query.v1")
    check("validate resolves Repository-facts paths against each check cwd too", code == 0 and "在基线" not in out, out)

    # 7. branch 另打印纯 ASCII 的 commit=<sha>（2.2.1）
    repo, base = make_repo("v22-branch-ascii")
    run_ok(repo)
    tool(repo, "check", "normalize-query/attempt-001")
    tool(repo, "verdict", "normalize-query/attempt-001", "--verdict", "PASS", "--review", review(repo, "PASS"))
    code, out = tool(repo, "branch", "normalize-query/attempt-001")
    sha = git(repo, "rev-parse", "pi/normalize-query-v1-a001")
    check("branch prints a machine-readable commit= line", code == 0 and ("commit=%s branch=pi/normalize-query-v1-a001" % sha) in out, out)


if __name__ == "__main__":
    argv = sys.argv[1:]
    keep = "--keep" in argv
    only = [a for a in argv if a != "--keep"]
    for name, fn in list(globals().items()):
        if name.startswith("test_") and (not only or name in only):
            print("== %s" % name)
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                RESULTS.append((name, False, repr(exc)))
    failed = [r for r in RESULTS if not r[1]]
    print("\n%d checks, %d failed" % (len(RESULTS), len(failed)))
    if keep:
        print("保留测试目录：%s" % WORK)
    else:
        for repo in WORK.iterdir():
            if (repo / ".git").exists():
                subprocess.run(["git", "worktree", "prune"], cwd=str(repo))
        remove_tree(WORK)
    sys.exit(1 if failed else 0)
