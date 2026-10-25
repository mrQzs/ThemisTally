"""scripts/kit_plugins.py 的执行端测试（kit-plugins v2）。只覆盖 review 第 1–5 项（D11）：

  1. 授予路径：链接目录的问题行（不在“满足权限条件”清单里）；
  2. 锁列只取四个值，list --json 的字符串值里“无效：链接”只作为子串出现；
  3. 资源读取失败：锁列“无效”、资源列“不一致”；
  4. plugins 段不合法：五个子命令都退出 1、带修复提示、不写配置；
  5. 无变化路径上的题库门禁给出恢复字样、配置字节不变。

约定同仓库其它测试：pytest 函数写法 + tmp_path；只改合成副本，不动仓库真实的 plugins/；
Windows 上用 `cmd /c mklink /J` 建 junction，建不了就 skip。文件名与键名写字面量，不从被测模块 import。
断言只用合同写明的固定词、退出码与文件字节，以及“被拒绝的路径从未被读取”。
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
from unittest import mock

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import pi_dispatch as pd  # noqa: E402
import kit_config  # noqa: E402

_LINK = "无效：链接"


def _kp():
    import kit_plugins  # noqa: PLC0415
    return kit_plugins


class Env:
    def __init__(self, kit, repo):
        self.kit = kit
        self.repo = repo
        self.plugins = kit / "plugins"

    def plugin(self, plugin_id):
        return self.plugins / plugin_id

    def write_config(self, config):
        (self.repo / ".agent" / "dispatch.config.json").write_text(
            json.dumps(config, ensure_ascii=False), encoding="utf-8")

    def read_config(self):
        path = self.repo / ".agent" / "dispatch.config.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


@contextlib.contextmanager
def make_env(tmp_path):
    kit = tmp_path / "kit"
    shutil.copytree(str(ROOT / "plugins"), str(kit / "plugins"))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".agent").mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    with mock.patch.object(kit_config.pd, "KIT_ROOT", kit), \
            mock.patch.object(kit_config.pd, "DECISIONS_PLUGIN_DIR", kit / "plugins" / "decisions"):
        yield Env(kit, repo)


def run(argv, repo):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = _kp().main(list(argv), repo=str(repo))
        except SystemExit as exc:  # argparse 用法错误
            code = exc.code if isinstance(exc.code, int) else 2
    return code, out.getvalue(), err.getvalue()


def make_dir_link(link, target):
    link = pathlib.Path(link)
    target = pathlib.Path(target)
    if os.name == "nt":
        proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                              capture_output=True, check=False)
        return proc.returncode == 0
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return True
    except OSError:
        return False


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _strings(value)


def _impact_lines(text):
    return [line for line in text.splitlines() if "满足权限条件" in line]


@contextlib.contextmanager
def fail_reads(suffix, error):
    """读取路径以 suffix（/ 分隔）结尾时抛 error；其余读取照常。"""
    def norm(path):
        return str(path).replace("\\", "/")

    real_rb = pathlib.Path.read_bytes

    def rb(self, *a, **k):
        if norm(self).endswith(suffix):
            raise error
        return real_rb(self, *a, **k)

    with mock.patch.object(pathlib.Path, "read_bytes", rb):
        yield


def tamper_lock_sha(env, plugin_id):
    path = env.plugin(plugin_id) / "lock.json"
    lock = json.loads(path.read_text(encoding="utf-8"))
    lock["lock_sha256"] = "1" * 64
    path.write_text(json.dumps(lock), encoding="utf-8")


def break_battery(env):
    # 多出一份锁里没有的清单：verify_battery_lock 会抛 battery_drift。
    (env.plugin("decisions") / "questions" / "zz-extra.json").write_text(
        json.dumps({"id": "zz-extra", "version": "1.0.0", "questions": {}}), encoding="utf-8")


# --- 第 1 项：授予路径的链接目录问题行，不在清单中 -------------------------------

def test_d11_01_grant_path_link_dir_reported_not_in_impact(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["network-decisions"]}})
        real = tmp_path / "real_docs_change"
        shutil.move(str(env.plugin("docs-change")), str(real))
        assert make_dir_link(env.plugin("docs-change"), real)
        code, out, err = run(["enable", "python-checks", "--allow-permission", "read-candidate"], env.repo)
        assert code == 0
        assert "Traceback" not in out and "Traceback" not in err
        assert "docs-change" in out and _LINK in out
        impact = _impact_lines(out)
        assert impact and all("docs-change" not in line for line in impact), impact
        # 权限照常写入，链接目录不影响退出码
        assert env.read_config()["plugins"]["allowed_permissions"] == ["network-decisions", "read-candidate"]


# --- 第 2 项：锁列四值；list --json 的字符串值 ---------------------------------

def test_d11_02a_list_json_lock_values_are_the_four(tmp_path):
    with make_env(tmp_path) as env:
        # 四种锁列同屏：code-change 一致；decisions 漂移；docs-change 变链接目录（无效）；
        # dep-x 带 depends_on（本轮不支持）。
        manifest = {
            "record_type": "builtin-task-plugin-manifest", "schema_version": 1, "plugin_id": "dep-x",
            "version": "1.0.0", "api_version": "08-plugin-v1", "roles": ["planner"],
            "capabilities": ["offline-reference"], "permissions": ["read-candidate"],
            "platforms": ["windows", "linux", "macos"], "depends_on": ["code-change"], "conflicts": [],
            "entrypoints": [], "resources": [], "checks": [{"id": "c", "command": ["true"], "deterministic": True}],
        }
        lock = {"record_type": "plugin-lock", "schema_version": 1, "generation": 1,
                "compiler_sha256": "0" * 64, "plugins": [], "lock_sha256": "0" * 64}
        write = env.plugin("dep-x")
        write.mkdir()
        (write / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (write / "lock.json").write_text(json.dumps(lock), encoding="utf-8")
        tamper_lock_sha(env, "decisions")
        real = tmp_path / "real_docs_change"
        shutil.move(str(env.plugin("docs-change")), str(real))
        assert make_dir_link(env.plugin("docs-change"), real)
        code, out, err = run(["list", "--json"], env.repo)
        assert code == 0
        assert "Traceback" not in err
        strings = list(_strings(json.loads(out)))
        for word in ("一致", "漂移", "无效", "本轮不支持"):
            assert word in strings, word
        assert _LINK not in strings  # “无效：链接”绝不作为单独的值出现
        assert any(_LINK in s for s in strings)  # 只作为原因文字的子串出现


def test_d11_02b_verify_titles_use_lock_word(tmp_path):
    with make_env(tmp_path) as env:
        tamper_lock_sha(env, "decisions")
        code, out, err = run(["verify", "decisions"], env.repo)
        assert code == 1 and "漂移" in out
        title = [line for line in out.splitlines() if line.startswith("decisions ")][0]
        assert title == "decisions 漂移"


# --- 第 3 项：资源读取失败 -----------------------------------------------------

def test_d11_03_resource_read_failure_columns(tmp_path):
    with make_env(tmp_path) as env:
        with fail_reads("plugins/code-change/README.md", PermissionError("denied")):
            code_v, out_v, err_v = run(["verify", "code-change"], env.repo)
            code_s, out_s, _ = run(["show", "code-change"], env.repo)
            code_l, out_l, _ = run(["list"], env.repo)
        assert code_v == 1
        assert "Traceback" not in err_v
        assert "资源读取失败" in out_v
        title = [line for line in out_v.splitlines() if line.startswith("code-change ")][0]
        assert title == "code-change 无效"  # 锁列“无效”
        # show 的资源行是不一致
        rows = [line.strip() for line in out_s.splitlines()
                if line.strip().startswith("资源") and "README.md" in line]
        assert rows and all("不一致" in row for row in rows), rows
        # list 行：资源列“不一致”、锁列“无效”、状态 BLOCKED
        assert code_l == 0
        row = [line for line in out_l.splitlines() if line.split()[:1] == ["code-change"]][0]
        assert "不一致" in row and "无效" in row and "BLOCKED" in row


# --- 第 4 项：plugins 段不合法，五个子命令都拒绝 -------------------------------

@pytest.mark.parametrize("bad", [None, "x", {"enabled": None}], ids=["null", "string", "enabled-null"])
def test_d11_04_plugins_section_invalid_all_subcommands(tmp_path, bad):
    with make_env(tmp_path) as env:
        env.write_config({"kill_grace_seconds": 20, "plugins": bad})
        path = env.repo / ".agent" / "dispatch.config.json"
        before = path.read_bytes()
        # 只读三命令：退出 1、ERROR、带修复提示、不写（规划端补强：合同第七节五个子命令都附提示）
        for argv in (["list"], ["show", "docs-change"], ["verify"], ["verify", "docs-change"]):
            code, out, err = run(argv, env.repo)
            assert code == 1, argv
            assert "ERROR:" in err and "修复：" in err, argv
            assert "Traceback" not in out and "Traceback" not in err, argv
            assert path.read_bytes() == before, argv
        # 写命令：退出 1、带修复提示、不写
        for argv in (["enable", "docs-change"], ["disable", "docs-change"]):
            code, out, err = run(argv, env.repo)
            assert code == 1, argv
            assert "ERROR:" in err and "修复：" in err, argv
            assert path.read_bytes() == before, argv
        # 修复提示执行后成功，其它键保持
        code, _, err = run(["disable", "docs-change"], env.repo)
        hint = err.split("修复：", 1)[1].strip().splitlines()[0]
        assert hint.startswith("config "), hint
        parts = hint[len("config "):].split(" ", 2)
        if len(parts) == 3 and parts[2].startswith("'") and parts[2].endswith("'"):
            parts[2] = parts[2][1:-1]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                hcode = kit_config.main(parts, repo=str(env.repo))
            except SystemExit as exc:
                hcode = exc.code if isinstance(exc.code, int) else 2
        assert hcode == 0, err.getvalue()
        assert env.read_config()["kill_grace_seconds"] == 20
        code, out, err = run(["list"], env.repo)
        assert code == 0


# --- 第 5 项：无变化路径上的题库门禁 -----------------------------------------

def test_d11_05_no_change_path_battery_gate(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"decisions": {"mode": "on"},
                          "plugins": {"enabled": ["decisions", "docs-change"]}})
        break_battery(env)
        path = env.repo / ".agent" / "dispatch.config.json"
        before = path.read_bytes()
        # repo-analysis 不在 enabled 里：没有变化，但仍要走题库门禁
        code, out, err = run(["disable", "repo-analysis"], env.repo)
        assert code == 1
        assert "Traceback" not in out and "Traceback" not in err
        assert "plugins disable decisions" in err and "config decisions off" in err
        assert "没有变化" not in out
        assert path.read_bytes() == before


# --- 桌面端 D2（第 116 轮）：enable、disable 的预览与令牌（设计 D6、D13） ----------------------

_GRANT = ["enable", "python-checks", "--allow-permission", "read-candidate"]
#: 带 --dry-run 的插件写命令在这个夹具里的一条合法参数；新加了 --dry-run 的命令要在这里补一条
_PREVIEW_ARGV = {("enable",): _GRANT, ("disable",): ["disable", "docs-change"]}


def _plugin_preview_commands():
    found = []
    for action in _kp().build_parser()._actions:
        if hasattr(action, "choices") and isinstance(action.choices, dict):
            for name, child in action.choices.items():
                if any("--dry-run" in a.option_strings for a in child._actions):
                    found.append((name,))
    return sorted(found)


def _agent_files(env):
    root = env.repo / ".agent"
    return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
            for path in sorted(root.rglob("*"))}


def test_d2_every_plugin_preview_writes_nothing_and_prints_one_json(tmp_path):
    """与配置中心的写命令同一条要求（themistally-15）：.agent/ 前后逐字节一致，stdout 恰好一份 JSON。"""
    assert _plugin_preview_commands() == sorted(_PREVIEW_ARGV)
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["network-decisions"]}})
        assert run(["disable", "code-change"], env.repo)[0] == 0  # 先有历史与审计
        for path, argv in sorted(_PREVIEW_ARGV.items()):
            before = _agent_files(env)
            code, out, err = run(argv + ["--dry-run", "--json"], env.repo)
            assert code == 0, (path, err)
            assert json.loads(out)["dry_run"] is True
            assert _agent_files(env) == before, path


def test_d2_the_text_dry_run_is_unchanged(tmp_path):
    """不带 --json 的 --dry-run 仍是原有的文字预览（设计 §8），一字不差，后面也不跟预览 JSON。"""
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["network-decisions"]}})
        code, out, err = run(_GRANT + ["--dry-run"], env.repo)
        assert (code, err) == (0, "")
        assert out == ('plugins.allowed_permissions: ["network-decisions"] → ["network-decisions", "read-candidate"]\n'
                       "以下插件也将满足权限条件：code-change、docs-change、docs-checks、mutation-review、"
                       "regression-tests、repo-analysis\n"
                       "当前不限制，所有插件都算启用\n"
                       "plugins 段（dry-run，未写入）：\n"
                       '{\n  "allowed_permissions": [\n    "network-decisions",\n    "read-candidate"\n  ]\n}\n')


def test_d2_the_json_preview_carries_the_permission_difference_as_notes(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["network-decisions"]}})
        config_bytes = (env.repo / ".agent" / "dispatch.config.json").read_bytes()
        code, out, err = run(_GRANT + ["--dry-run", "--json"], env.repo)
        assert code == 0, err
        payload = json.loads(out)
        assert payload["action"] == "plugin.enable" and payload["changed"] is True
        assert payload["resources"] == [{"resource": "config", "changed": True,
                                         "changed_keys": ["plugins.allowed_permissions"]}]
        assert payload["notes"] == [
            'plugins.allowed_permissions: ["network-decisions"] → ["network-decisions", "read-candidate"]',
            "以下插件也将满足权限条件：code-change、docs-change、docs-checks、mutation-review、regression-tests、"
            "repo-analysis",
            "当前不限制，所有插件都算启用"]
        assert payload["state"] == "v1;config=%s" % hashlib.sha256(config_bytes).hexdigest()
        code, out, err = run(["disable", "decisions", "--dry-run", "--json"], env.repo)
        assert code == 0, err
        assert json.loads(out)["notes"][-2:] == ["从不限制改为显式列表，之后新增的插件不会自动启用", "决策插件会因此变为 off"]


def test_d2_expect_state_writes_when_it_matches_and_exits_4_when_stale(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["decisions"]}})
        path = env.repo / ".agent" / "dispatch.config.json"
        state = json.loads(run(["enable", "docs-change", "--dry-run", "--json"], env.repo)[1])["state"]
        env.write_config({"plugins": {"enabled": ["decisions"]}, "kill_grace_seconds": 20})  # 预览之后被改
        before = path.read_bytes()
        code, out, err = run(["enable", "docs-change", "--expect-state", state], env.repo)
        assert code == 4, (out, err)
        assert "在预览之后被改过" in err and path.read_bytes() == before
        state = json.loads(run(["enable", "docs-change", "--dry-run", "--json"], env.repo)[1])["state"]
        code, out, err = run(["enable", "docs-change", "--expect-state", state], env.repo)
        assert code == 0, err
        assert env.read_config()["plugins"]["enabled"] == ["decisions", "docs-change"]


def test_d2_the_preview_does_not_take_the_lock(tmp_path):
    """行为变化（第 116 轮）：文字 dry-run 以前拿着配置锁跑，现在不拿：别人的锁挡不住预览，预览也挡不住别人的写入。
    带令牌的执行照旧等锁。"""
    with make_env(tmp_path) as env, mock.patch.object(kit_config, "LOCK_WAIT_SECONDS", 0.3):
        env.write_config({"plugins": {"enabled": ["decisions"]}})
        lock = env.repo / ".agent" / kit_config.LOCK_NAME
        lock.mkdir()
        (lock / "owner.json").write_text(json.dumps({"pid": 1, "host": "elsewhere", "token": "t"}), encoding="utf-8")
        assert run(["enable", "docs-change", "--dry-run"], env.repo)[0] == 0
        code, out, err = run(["enable", "docs-change", "--dry-run", "--json"], env.repo)
        assert code == 0, err
        code, _out, err = run(["enable", "docs-change", "--expect-state", json.loads(out)["state"]], env.repo)
        assert code == 1 and "配置锁被占用" in err


def test_d2_json_without_dry_run_is_a_usage_error(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["decisions"]}})
        path = env.repo / ".agent" / "dispatch.config.json"
        before = path.read_bytes()
        for extra in (["--json"], ["--json", "--expect-state", "v1;config=absent"]):
            code, out, err = run(["enable", "docs-change"] + extra, env.repo)
            assert (code, out) == (2, ""), err
            assert "--json 只与 --dry-run 一起用" in err
        assert path.read_bytes() == before
