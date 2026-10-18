# -*- coding: utf-8 -*-
"""3.0 第二轮：角色绑定的配置（docs/themis-tally-3.0-r2-角色绑定与配置中心.md D1、D2、D8；测试计划 9.1、9.3 的 M7）。

配置命令在临时 Git 仓库上进程内运行（kit_config.main）；只拷旧文件、没有 kit_roles.py 的布局与 M7b 的交错用子进程。
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import kit_config  # noqa: E402
import kit_roles  # noqa: E402
import pi_dispatch as pd  # noqa: E402
from codekit import secrets as store  # noqa: E402

IGNORE_RULES = ".agent/runs/\n.agent/dispatch.local.json\n.agent/config-history/\n.agent/audit/\n.agent/.config.lock/\n"
RUNTIMES = {"pi": {"adapter": "pi"}, "oc": {"adapter": "opencode"}}
PROFILES = {"exec-step": {"runtime": "pi", "model": {"provider": "bb", "id": "step-5-preview"},
                          "options": {"thinking": "high"}},
            "exec-low": {"runtime": "pi", "model": {"provider": "bb", "id": "step-5-mini"},
                         "options": {"thinking": "low"}},
            "oc-x": {"runtime": "oc", "model": {"provider": "oc", "id": "x-1"}}}


def run_config(argv, repo):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = kit_config.main(list(argv), repo=str(repo))
        except SystemExit as exc:  # argparse
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class RolesRepo(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="kit-roles-")).resolve()
        self.addCleanup(lambda: subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", str(self.work)], check=False)
                        if os.name == "nt" else subprocess.run(["rm", "-rf", str(self.work)], check=False))
        self.repo = self.work / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=str(self.repo), check=True)
        (self.repo / ".agent").mkdir()
        (self.repo / ".gitignore").write_text(IGNORE_RULES, encoding="utf-8")
        for patcher in (mock.patch.dict(os.environ, {store.STORE_ENV: "file", "XDG_CONFIG_HOME": str(self.work / "x")}),
                        mock.patch.object(kit_config, "LOCK_WAIT_SECONDS", 0.5)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.config_file = self.repo / ".agent" / "dispatch.config.json"

    def write(self, config):
        self.config_file.write_bytes((json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    def base(self, **extra):
        config = {"runtimes": json.loads(json.dumps(RUNTIMES)), "profiles": json.loads(json.dumps(PROFILES))}
        config.update(extra)
        return config

    def errors(self, config):
        return kit_config.validate_config(config, pd.Repo.discover(str(self.repo)))

    def assertRefused(self, key, value, needle):
        before = self.config_file.read_bytes() if self.config_file.exists() else None
        code, _out, err = run_config(["set", key, json.dumps(value, ensure_ascii=False)], self.repo)
        self.assertEqual(code, 1, err)
        self.assertIn("没有写入", err)
        self.assertIn(needle, err)
        self.assertEqual(self.config_file.read_bytes() if self.config_file.exists() else None, before)


class Validation(RolesRepo):
    # C1
    def test_shapes_unknown_keys_and_ids(self):
        self.assertRefused("runtimes", {"pi": {"adapter": "pi", "label": "x"}}, "只接受 adapter")
        self.assertRefused("runtimes", {"Bad_ID": {"adapter": "pi"}}, "ID 不合法")
        self.assertRefused("runtimes", {"pi": {"adapter": "vim"}}, "adapter 必须是")
        self.assertRefused("profiles", [], "profiles 必须是对象")
        self.write(self.base())
        self.assertRefused("profiles.exec-step", {"runtime": "pi", "model": {"provider": "bb", "id": "m"}, "x": 1},
                           "未知键")
        self.assertRefused("roles", {"executor": {"mode": "headless", "profile": "exec-step"}}, "未知角色")

    # C2
    def test_modes_must_fit_the_role(self):
        self.write(self.base())
        self.assertRefused("roles", {"execution": {"mode": "manual"}}, "roles.execution.mode")
        self.assertRefused("roles", {"contract": {"mode": "interactive_host"}}, "roles.contract.mode")
        self.assertRefused("roles", {"planning_review": {"mode": "interactive_host", "host": "opencode"}}, "host 必须是")
        self.assertRefused("roles", {"scheduler_agent": {"mode": "headless", "profile": "exec-step",
                                                          "cadence_seconds": 5}}, "cadence_seconds")
        self.assertEqual(self.errors(self.base(roles={"planning_review": {"mode": "interactive_host", "host": "codex"},
                                                      "contract": {"mode": "manual"},
                                                      "execution": {"mode": "headless", "profile": "exec-step"},
                                                      "scheduler_agent": {"mode": "disabled"}})), [])

    # C3
    def test_references_must_exist(self):
        self.assertRefused("profiles", {"p": {"runtime": "nope", "model": {"provider": "bb", "id": "m"}}}, "没有登记")
        self.write(self.base())
        self.assertRefused("roles", {"execution": {"mode": "headless", "profile": "ghost"}}, "没有登记")
        self.assertRefused("active_preset", "ghost", "不是已有的方案")
        self.assertRefused("presets", {"eco": {"roles": {}}}, "至少写一个角色")

    # C4
    def test_suspected_secrets_are_refused(self):
        self.write(self.base())
        self.assertRefused("presets", {"eco": {"description": "token ghp_" + "a" * 36,
                                               "roles": {"execution": {"mode": "headless", "profile": "exec-step"}}}},
                           "疑似凭据")
        self.assertRefused("profiles.leak", {"runtime": "pi", "model": {"provider": "bb", "id": "sk-" + "b" * 30}},
                           "疑似凭据")
        ok = self.base()
        ok["profiles"]["exec-step"]["credential_env"] = ["STEP_API_KEY"]  # 变量名的字段豁免键名规则
        self.assertEqual(self.errors(ok), [])

    # 闸二第 2 片 B1：拒绝的时候也不回显疑似凭据
    def test_g2s2_b1_refusals_never_echo_secret_values(self):
        self.write(self.base())
        for key, value in (
                ("profiles.leak", {"runtime": "pi", "model": {"provider": "bb", "id": "Bearer abcdefghijklmnop"}}),
                ("profiles.leak", {"runtime": "sk-" + "q" * 30, "model": {"provider": "bb", "id": "m"}}),
                ("roles", {"execution": {"mode": "headless", "profile": "ghp_" + "w" * 36}}),
                ("active_preset", "xoxb-" + "e" * 20)):
            with self.subTest(key=key):
                code, out, err = run_config(["set", key, json.dumps(value)], self.repo)
                self.assertEqual(code, 1, err)
                for fragment in ("abcdefghijklmnop", "q" * 30, "w" * 36, "e" * 20):
                    self.assertNotIn(fragment, out + err)

    # 闸二第 2 片 S2：引用与枚举字段是 null、数组、对象时，拒绝而不冒堆栈
    def test_g2s2_s2_wrong_types_are_refused_cleanly(self):
        self.write(self.base())
        bad_values = (None, [], {}, 3)
        for value in bad_values:
            with self.subTest(value=value):
                for key, payload in (
                        ("runtimes", {"pi": {"adapter": value}}),
                        ("profiles.p", {"runtime": value, "model": {"provider": "bb", "id": "m"}}),
                        ("roles", {"execution": {"mode": value}}),
                        ("roles", {"planning_review": {"mode": "interactive_host", "host": value}}),
                        ("roles", {"execution": {"mode": "headless", "profile": value}}),
                        ("active_preset", value)):
                    code, _out, err = run_config(["set", key, json.dumps(payload)], self.repo)
                    self.assertEqual(code, 1, (key, payload, err))
                    self.assertNotIn("Traceback", err)
        self.assertEqual(kit_roles.binding_tuple({"roles": {"execution": {"mode": "headless", "profile": []}},
                                                  "profiles": {"p": {"runtime": {}}}}, "execution")[1], None)

    # 闸二第 2 片 S3：说明键与 cadence_seconds
    def test_g2s2_s3_notes_and_explicit_null_cadence(self):
        config = self.base(roles={"scheduler_agent": {"mode": "headless", "profile": "exec-low",
                                                       "cadence_seconds": None}})
        self.assertTrue(any("cadence_seconds" in e for e in self.errors(config)))
        notes = self.base(presets={"_note": "方案说明", "eco": {"roles": {"execution": {
            "mode": "headless", "profile": "exec-step"}}}})
        notes["runtimes"]["_note"] = "本机 CLI 登记"
        notes["profiles"]["_note"] = {"任意": "说明"}
        self.assertEqual(self.errors(notes), [])

    # C5
    def test_runtimes_carry_no_command(self):
        self.assertRefused("runtimes", {"pi": {"adapter": "pi", "command": ["evil.exe"]}}, "dispatch.local.json")

    # C7
    def test_profile_options_by_adapter(self):
        self.write(self.base())
        self.assertRefused("profiles.exec-step", {"runtime": "pi", "model": {"provider": "bb", "id": "m"},
                                                  "options": {"thinking": "turbo"}}, "options.thinking")
        self.assertRefused("profiles.oc-x", {"runtime": "oc", "model": {"provider": "oc", "id": "x"},
                                             "options": {"thinking": "high"}}, "opencode 不接受")
        config = self.base(roles={"execution": {"mode": "headless", "profile": "exec-low"}})
        value, error = kit_roles.resolve_role_executor(config, "execution")
        self.assertIsNone(error)
        self.assertEqual((value["provider"], value["model"], value["thinking"]), ("bb", "step-5-mini", "low"))
        del config["profiles"]["exec-low"]["options"]
        value, _ = kit_roles.resolve_role_executor(config, "execution")
        self.assertEqual(value["thinking"], "high")  # 不写 thinking 时按 high，与合同的缺省相同

    # C8
    def test_credential_env_names(self):
        self.write(self.base())
        self.assertRefused("profiles.exec-step", {"runtime": "pi", "model": {"provider": "bb", "id": "m"},
                                                  "credential_env": ["not a name"]}, "credential_env")

    # C9
    def test_without_v3_keys_show_and_validate_are_unchanged(self):
        code, out, _ = run_config(["show", "--json"], self.repo)
        self.assertEqual(code, 0)
        keys = [row["key"] for row in json.loads(out)["keys"]]
        self.assertEqual(keys[1], "worktree_root")
        self.assertEqual(keys[-5:], list(kit_roles.V3_KEYS))
        self.assertEqual(run_config(["validate"], self.repo)[0], 0)

    def test_resolution_errors_and_codes(self):
        config = self.base()
        _, error = kit_roles.resolve_role_executor(config, "execution")
        self.assertEqual(error["code"], pd.EXIT_USAGE)
        _, error = kit_roles.resolve_role_executor(dict(config, roles={"contract": {"mode": "manual"}}), "contract")
        self.assertIn("manual", error["message"])
        _, error = kit_roles.resolve_role_executor(
            dict(config, roles={"execution": {"mode": "headless", "profile": "oc-x"}}), "execution")
        self.assertEqual(error["code"], pd.EXIT_BLOCKED)  # 未接通的适配器（D6）
        value, error = kit_roles.resolve_role_executor(
            dict(config, roles={"contract": {"mode": "headless", "profile": "exec-step"}},
                 presets={"eco": {"roles": {"contract": {"mode": "headless", "profile": "exec-step"}}}},
                 active_preset="eco"), "contract")
        self.assertIsNone(error)
        self.assertEqual((value["role"], value["runtime"], value["adapter"], value["active_preset"]),
                         ("contract", "pi", "pi", "eco"))


class OldLayout(unittest.TestCase):
    """C9：只拷了旧文件、没有 kit_roles.py 的布局里，没有 v3 键的配置命令与插件写入照常可用（D12）。"""

    def test_old_files_only(self):
        work = Path(tempfile.mkdtemp(prefix="kit-roles-old-")).resolve()
        self.addCleanup(shutil.rmtree, str(work), True)
        kit = work / "kit"
        (kit / "scripts").mkdir(parents=True)
        for name in ("pi_dispatch.py", "kit_config.py", "kit_plugins.py"):
            shutil.copy(str(ROOT / "scripts" / name), str(kit / "scripts" / name))
        shutil.copytree(str(ROOT / "scripts" / "codekit"), str(kit / "scripts" / "codekit"))
        shutil.copytree(str(ROOT / "plugins"), str(kit / "plugins"))
        repo = work / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / ".gitignore").write_text(IGNORE_RULES, encoding="utf-8")
        env = dict(os.environ, PYTHONUTF8="1", CODEKIT_SECRET_STORE="off")

        def tool(*args):
            done = subprocess.run([sys.executable, str(kit / "scripts" / "pi_dispatch.py"), "--repo", str(repo)]
                                  + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=120)
            return done.returncode, done.stdout.decode("utf-8"), done.stderr.decode("utf-8", "replace")

        for args in (("config", "set", "kill_grace_seconds", "20"), ("config", "decisions", "off"),
                     ("config", "show"), ("config", "validate"), ("plugins", "disable", "code-change"),
                     ("plugins", "enable", "code-change")):
            code, out, err = tool(*args)
            self.assertEqual(code, 0, (args, out, err))
            self.assertNotIn("Traceback", err)
        config = json.loads((repo / ".agent" / "dispatch.config.json").read_text(encoding="utf-8"))
        config["roles"] = {"execution": {"mode": "headless", "profile": "p"}}
        config["runtimes"] = {"pi": {"adapter": "pi"}}
        config["profiles"] = {"p": {"runtime": "pi", "model": {"provider": "bb", "id": "m"}}}
        (repo / ".agent" / "dispatch.config.json").write_text(json.dumps(config), encoding="utf-8")
        code, out, err = tool("config", "validate")
        self.assertEqual(code, 1, (out, err))  # 缺模块经整份校验报出：一行 ERROR，不冒堆栈（D12）
        self.assertEqual([line for line in out.splitlines() if "kit_roles.py" in line and line.startswith("ERROR")],
                         ["ERROR 配置里有角色绑定的键，但 scripts/kit_roles.py 不在本工具旁边"])  # 三个键只报一次
        self.assertNotIn("Traceback", err)


class SwitchConfirmation(RolesRepo):
    """M7：写入改变 execution 或 contract 的生效绑定、而这一刻有在运行的 attempt 时，要 --yes（D8）。"""

    def setUp(self):
        super().setUp()
        self.write(self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}}))

    def attempt(self, state, claimed=False, name="t1/attempt-001"):
        run_dir = self.repo / ".agent" / "runs" / name
        run_dir.mkdir(parents=True)
        pd.set_state(run_dir, state)
        if claimed:
            (run_dir / "claim").mkdir()
        return run_dir

    def switch(self, *extra):
        return run_config(["set", "roles.execution", json.dumps({"mode": "headless", "profile": "exec-low"})]
                          + list(extra), self.repo)

    def last_confirmation(self):
        records, _ = kit_config.read_audit(pd.Repo.discover(str(self.repo)))
        return [r for r in records if r["phase"] == "intent"][-1]["confirmation"]

    def test_running_attempts_require_yes(self):
        for state, claimed in (("RUNNING", False), ("COLLECTING", False), ("PREPARED", True)):
            with self.subTest(state=state, claimed=claimed):
                run_dir = self.attempt(state, claimed)
                before = self.config_file.read_bytes()
                code, _, err = self.switch()
                self.assertEqual(code, 1, err)
                self.assertIn("t1/attempt-001", err)
                self.assertEqual(self.config_file.read_bytes(), before)
                code, _, err = self.switch("--yes")
                self.assertEqual(code, 0, err)
                self.assertEqual(self.last_confirmation(), "flag")
                shutil.rmtree(str(run_dir))
                self.write(self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}}))

    def test_finished_or_unclaimed_attempts_do_not(self):
        self.attempt("NEEDS_REVIEW", claimed=True, name="t1/attempt-001")
        self.attempt("PREPARED", claimed=False, name="t2/attempt-001")
        code, _, err = self.switch()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.last_confirmation(), "none")

    def test_writes_that_keep_the_binding_need_no_confirmation(self):
        self.attempt("RUNNING")
        self.assertEqual(run_config(["set", "kill_grace_seconds", "20"], self.repo)[0], 0)
        profiles = self.base()["profiles"]
        profiles["exec-low"]["model"]["id"] = "step-5-other"  # 没有绑定的 profile
        self.assertEqual(run_config(["set", "profiles", json.dumps(profiles)], self.repo)[0], 0)

    def test_every_entry_that_changes_the_binding_is_covered(self):
        self.attempt("RUNNING")
        profiles = self.base()["profiles"]
        profiles["exec-step"]["model"]["id"] = "step-5-other"
        cases = [["set", "profiles", json.dumps(profiles)],
                 ["set", "runtimes", json.dumps({"pi": {"adapter": "opencode"}, "oc": {"adapter": "opencode"}})],
                 ["unset", "roles.execution"]]
        for argv in cases:
            with self.subTest(argv=argv[:2]):
                config = self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}})
                if argv[1] == "runtimes":  # 改成 opencode 之后，profile 不能再带 pi 才有的 thinking
                    for profile in config["profiles"].values():
                        profile.pop("options", None)
                self.write(config)
                code, _, err = run_config(argv, self.repo)
                self.assertEqual(code, 1, (argv, err))
                self.assertIn("--yes", err)

    def test_g2s2_s4_an_unreadable_runs_directory_is_not_treated_as_idle(self):
        runs = self.repo / ".agent" / "runs"
        (runs / "t1").mkdir(parents=True)
        real = Path.iterdir

        def iterdir(path):
            if path == runs:
                raise PermissionError(13, "拒绝访问（替身）", str(path))
            return real(path)

        with mock.patch.object(Path, "iterdir", iterdir):
            code, _, err = self.switch()
            self.assertEqual(code, 1, err)
            self.assertIn("无法确认有没有在运行的 attempt", err)
            code, _, err = self.switch("--yes")
            self.assertEqual(code, 0, err)
        self.assertEqual(self.last_confirmation(), "flag")

    def test_rollback_to_a_config_without_bindings(self):
        self.config_file.unlink()
        run_config(["set", "kill_grace_seconds", "20"], self.repo)  # 第 1 条：没有 v3 键
        config = json.loads(self.config_file.read_text(encoding="utf-8"))
        config.update(self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}}))
        self.assertEqual(run_config(["set", "runtimes", json.dumps(config["runtimes"])], self.repo)[0], 0)
        self.assertEqual(run_config(["set", "profiles", json.dumps(config["profiles"])], self.repo)[0], 0)
        self.assertEqual(run_config(["set", "roles", json.dumps(config["roles"])], self.repo)[0], 0)
        self.attempt("RUNNING")
        code, _, err = run_config(["rollback", "1"], self.repo)
        self.assertEqual(code, 1, err)
        self.assertEqual(run_config(["rollback", "1", "--yes"], self.repo)[0], 0)


#: 子进程驱动（M7b）：在追加 intent 时（确认判定之后、替换之前）报告并等放行文件。
DRIVER = '''
import os, sys, time
sys.path.insert(0, sys.argv[1])
import kit_config
kit_config.LOCK_WAIT_SECONDS = 20.0
barrier = sys.argv[2]
original = kit_config._append_audit
def append(repo, record):
    if record.get("phase") == "intent":
        open(barrier + ".holding", "w").close()
        deadline = time.time() + 30
        while not os.path.exists(barrier + ".go") and time.time() < deadline:
            time.sleep(0.05)
    return original(repo, record)
kit_config._append_audit = append
sys.exit(kit_config.main(sys.argv[3:]))
'''


class SwitchCheckTime(RolesRepo):
    """M7b：判定在检查的那一刻；检查之后、替换之前才领取的 attempt 不纳入这次提醒（D8）。"""

    def test_attempt_claimed_after_the_check_is_not_part_of_this_reminder(self):
        self.write(self.base(roles={"execution": {"mode": "headless", "profile": "exec-step"}}))
        driver = self.work / "driver.py"
        driver.write_text(DRIVER, encoding="utf-8")
        barrier = self.work / "barrier"
        child = subprocess.Popen([sys.executable, str(driver), str(ROOT / "scripts"), str(barrier), "--repo",
                                  str(self.repo), "set", "roles.execution",
                                  json.dumps({"mode": "headless", "profile": "exec-low"})],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.time() + 30
            while not (self.work / "barrier.holding").exists() and time.time() < deadline:
                time.sleep(0.05)
            self.assertTrue((self.work / "barrier.holding").exists())
            run_dir = self.repo / ".agent" / "runs" / "t1" / "attempt-001"
            run_dir.mkdir(parents=True)
            pd.set_state(run_dir, "RUNNING")  # 检查之后才领取
            (self.work / "barrier.go").write_text("go", encoding="utf-8")
        finally:
            _out, err = child.communicate(timeout=60)
        self.assertEqual(child.returncode, 0, err.decode("utf-8", "replace"))
        records, _ = kit_config.read_audit(pd.Repo.discover(str(self.repo)))
        self.assertEqual([r for r in records if r["phase"] == "intent"][-1]["confirmation"], "none")


if __name__ == "__main__":
    unittest.main()
