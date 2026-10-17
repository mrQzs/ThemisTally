"""scripts/kit_plugins.py 的合同端 oracle（kit-plugins，覆盖 3.0 第一轮设计 §9 的 P 组 P1–P17）。

全部夹具都是合成的：把仓库的 plugins/ 复制到 tmp_path 下的副本，只改副本；用 mock.patch.object 把
kit_config.pd 的 KIT_ROOT 与 DECISIONS_PLUGIN_DIR 指向副本。绝不修改仓库里真实的 plugins/（模块前后快照比对）。
pytest 函数写法 + tmp_path；Windows 上用 `cmd /c mklink /J` 建 junction（目标只在 tmp_path 内），建不了就 skip。
文件名与键名写字面量，不从被测模块导入。断言只针对退出码、合同写明的固定词、插件 ID、文件字节，
以及“被拒绝的路径从未被读取”。
"""
from __future__ import annotations

import builtins
import contextlib
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
from codekit import decisions as decisions  # noqa: E402
from codekit import plugins as plugins  # noqa: E402

CRLF = (chr(13) + chr(10)).encode()
LF = chr(10).encode()
HEX64 = "0" * 64


#: 仓库 plugins/ 根下现有的 8 个插件 ID（字面量；不调用被测模块的函数）。
EIGHT_PLUGIN_IDS = [
    "code-change", "decisions", "docs-change", "docs-checks",
    "mutation-review", "python-checks", "regression-tests", "repo-analysis",
]


def _kp():
    """每个用例内导入参考实现：没有它时逐例失败，不是收集错误。"""
    import kit_plugins  # noqa: PLC0415
    return kit_plugins


# ---------------------------------------------------------------------------
# 夹具与小工具
# ---------------------------------------------------------------------------

def _snapshot_plugins():
    root = ROOT / "plugins"
    snap = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            snap[str(path.relative_to(root))] = path.read_bytes()
    return snap


_PLUGINS_SNAPSHOT = _snapshot_plugins()


@pytest.fixture(autouse=True)
def _real_plugins_untouched():
    yield
    assert _snapshot_plugins() == _PLUGINS_SNAPSHOT, "真实的 plugins/ 被修改了"


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


def run_hint(hint, repo):
    assert hint.startswith("config "), hint
    parts = hint[len("config "):].split(" ", 2)
    if len(parts) == 3 and parts[2].startswith("'") and parts[2].endswith("'"):
        parts[2] = parts[2][1:-1]
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = kit_config.main(parts, repo=str(repo))
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 2
    return code, out.getvalue(), err.getvalue()


def hint_from(text):
    assert "修复：" in text, text
    return text.split("修复：", 1)[1].strip().splitlines()[0]


def make_dir_link(link, target):
    """建目录 junction（Windows）或目录符号链接（其他平台）；成功返回 True。"""
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


def make_file_symlink(link, target):
    """建文件符号链接（内容与 target 逐字节相同）；本机不允许时返回 False，调用方 skip。"""
    try:
        os.symlink(str(target), str(link))
        return True
    except OSError:
        return False


def replace_with_file_symlink(path, tmp_path, name):
    """把 path 换成指向 tmp_path 下副本的符号链接；建不了就 skip。"""
    path = pathlib.Path(path)
    data = path.read_bytes()
    target = tmp_path / name
    target.write_bytes(data)
    path.unlink()
    if not make_file_symlink(path, target):
        pytest.skip("本机无法创建文件符号链接（需要权限）")


def _resource_rows(text, name):
    """show 的资源行（行首是“资源”且含资源名）。"""
    return [line.strip() for line in text.splitlines()
            if line.strip().startswith("资源") and name in line]


def _impact_lines(text):
    return [line for line in text.splitlines() if "满足权限条件" in line]


@contextlib.contextmanager
def read_spy():
    reads = []
    real_rb, real_rt, real_open = pathlib.Path.read_bytes, pathlib.Path.read_text, builtins.open

    def rb(self, *a, **k):
        reads.append(str(self))
        return real_rb(self, *a, **k)

    def rt(self, *a, **k):
        reads.append(str(self))
        return real_rt(self, *a, **k)

    def op(file, *a, **k):
        reads.append(str(file))
        return real_open(file, *a, **k)

    with mock.patch.object(pathlib.Path, "read_bytes", rb), \
            mock.patch.object(pathlib.Path, "read_text", rt), \
            mock.patch.object(builtins, "open", op):
        yield reads


def add_extra_question(env):
    (env.plugin("decisions") / "questions" / "zz-extra.json").write_text(
        json.dumps({"id": "zz-extra", "version": "1.0.0", "questions": {}}), encoding="utf-8")


def break_manifest(env, plugin_id):
    (env.plugin(plugin_id) / "manifest.json").write_text("{ not json", encoding="utf-8")


def build_consistent(plugin_id, *, permissions=("read-candidate",), depends_on=None, resource_override=None):
    """用 codekit 公开函数造一份自洽的 manifest 与 lock。depends_on 在 build_lock 之后再加（本轮不支持核对锁）。"""
    resource_path = resource_override or ("plugins/%s/README.md" % plugin_id)
    manifest = {
        "record_type": "builtin-task-plugin-manifest", "schema_version": 1, "plugin_id": plugin_id,
        "version": "1.0.0", "api_version": "08-plugin-v1", "roles": ["planner"],
        "capabilities": ["offline-reference"], "permissions": list(permissions),
        "platforms": ["windows", "linux", "macos"], "depends_on": [], "conflicts": [], "entrypoints": [],
        "resources": [{"kind": "file", "id": "%s.readme" % plugin_id, "path": resource_path,
                       "sha256": "0" * 64}],
        "checks": [],
    }
    lock = plugins.build_lock([manifest], compiler_sha256=HEX64)
    if depends_on:
        manifest["depends_on"] = list(depends_on)
    return manifest, lock


def write_plugin(env, plugin_id, manifest, lock, resources=None):
    directory = env.plugin(plugin_id)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (directory / "lock.json").write_text(json.dumps(lock, ensure_ascii=False), encoding="utf-8")
    for rel, data in (resources or {}).items():
        target = env.kit / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


def test_pd_identity_and_bare_import():
    # 两种导入会得到两个模块对象；kit_plugins 暴露的 pd 必须与 kit_config.pd 是同一个。
    assert _kp().pd is kit_config.pd is pd


# ---------------------------------------------------------------------------
# P1：现有 8 个插件全部一致
# ---------------------------------------------------------------------------

def test_p01_eight_plugins_all_consistent(tmp_path):
    with make_env(tmp_path) as env:
        names = sorted(entry.name for entry in env.plugins.iterdir() if entry.is_dir())
        assert names == EIGHT_PLUGIN_IDS  # 复制的插件树就是这 8 个
        code, out, _ = run(["list"], env.repo)
        assert code == 0
        for pid in EIGHT_PLUGIN_IDS:
            assert pid in out
        assert "一致" in out and "READY" in out
        assert "漂移" not in out and "无效" not in out
        code, out, _ = run(["verify"], env.repo)
        assert code == 0
        assert "漂移" not in out and "无效" not in out


# ---------------------------------------------------------------------------
# P2：资源漂移（改一个字节 / 只差 CRLF / 多出题库清单）
# ---------------------------------------------------------------------------

def test_p02a_resource_one_byte(tmp_path):
    with make_env(tmp_path) as env:
        readme = env.plugin("code-change") / "README.md"
        data = readme.read_bytes()
        readme.write_bytes(data + b"x")
        code, out, _ = run(["verify"], env.repo)
        assert code == 1
        assert "不一致" in out
        code, out, _ = run(["list"], env.repo)
        assert code == 0  # list 继续列出其他插件，不崩


def test_p02b_resource_crlf_only(tmp_path):
    with make_env(tmp_path) as env:
        readme = env.plugin("code-change") / "README.md"
        data = readme.read_bytes().replace(CRLF, LF)
        readme.write_bytes(data.replace(LF, CRLF))
        code, out, _ = run(["verify"], env.repo)
        assert code == 1
        assert "不一致" in out and "CRLF" in out


def test_p02c_extra_question_no_traceback(tmp_path):
    with make_env(tmp_path) as env:
        add_extra_question(env)
        code, out, err = run(["verify"], env.repo)
        assert code == 1
        assert "zz-extra.json" in out and "不一致" in out
        assert "Traceback" not in err and "Traceback" not in out
        code, out, _ = run(["list"], env.repo)
        assert code == 0 and "decisions" in out  # list 继续列出其他插件


# ---------------------------------------------------------------------------
# P3：lock_sha256 被改 → 漂移
# ---------------------------------------------------------------------------

def test_p03_lock_sha_drift(tmp_path):
    with make_env(tmp_path) as env:
        lock = json.loads((env.plugin("decisions") / "lock.json").read_text(encoding="utf-8"))
        lock["lock_sha256"] = ("f" if lock["lock_sha256"][0] != "f" else "0") + lock["lock_sha256"][1:]
        (env.plugin("decisions") / "lock.json").write_text(json.dumps(lock), encoding="utf-8")
        code, out, _ = run(["verify", "decisions"], env.repo)
        assert code == 1
        assert "漂移" in out


# ---------------------------------------------------------------------------
# P4：manifest 被改（与锁绑定不符）→ 漂移
# ---------------------------------------------------------------------------

def test_p04_manifest_binding_drift(tmp_path):
    with make_env(tmp_path) as env:
        manifest = json.loads((env.plugin("code-change") / "manifest.json").read_text(encoding="utf-8"))
        manifest["version"] = "9.9.9"
        (env.plugin("code-change") / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        code, out, _ = run(["verify", "code-change"], env.repo)
        assert code == 1
        assert "漂移" in out


# ---------------------------------------------------------------------------
# P5：链接与边界；被拒绝的路径从未被读取；失败后不调用 verify_battery_lock
# 本节的 test_p05_plugin_dir_is_link、test_p05_manifest_is_link、test_p05_lock_is_link 与
# test_p05_questions_dir_is_link_no_battery_call 都是“目录链接变体”（junction / 目录符号链接）；
# 文件符号链接变体在后面的 test_p05_*_file_symlink 系列。
# ---------------------------------------------------------------------------

def test_p05_plugin_dir_is_link(tmp_path):
    # 目录链接变体：整个插件目录是 junction。
    with make_env(tmp_path) as env:
        real = tmp_path / "real_decisions"
        shutil.move(str(env.plugin("decisions")), str(real))
        assert make_dir_link(env.plugin("decisions"), real)
        with read_spy() as reads:
            code, out, _ = run(["verify", "decisions"], env.repo)
        assert code == 1
        assert "无效：链接" in out
        assert not any(p.endswith(os.sep + "manifest.json") and "decisions" in p for p in reads)


def test_p05_manifest_is_link(tmp_path):
    # 目录链接变体：manifest.json 所在位置是一个目录 junction。
    with make_env(tmp_path) as env:
        target = tmp_path / "mf_target"
        target.mkdir()
        mf = env.plugin("code-change") / "manifest.json"
        mf.unlink()
        assert make_dir_link(mf, target)
        with read_spy() as reads:
            code, out, _ = run(["verify", "code-change"], env.repo)
        assert code == 1 and "无效：链接" in out
        assert not any(p.endswith("manifest.json") and "code-change" in p for p in reads)


def test_p05_lock_is_link(tmp_path):
    # 目录链接变体：lock.json 所在位置是一个目录 junction。
    with make_env(tmp_path) as env:
        target = tmp_path / "lk_target"
        target.mkdir()
        lk = env.plugin("code-change") / "lock.json"
        lk.unlink()
        assert make_dir_link(lk, target)
        with read_spy() as reads:
            code, out, _ = run(["verify", "code-change"], env.repo)
        assert code == 1 and "无效：链接" in out
        assert not any(p.endswith("lock.json") and "code-change" in p for p in reads)


def test_p05_questions_dir_is_link_no_battery_call(tmp_path):
    # 目录链接变体：questions/ 目录是 junction。
    with make_env(tmp_path) as env:
        real = tmp_path / "real_questions"
        shutil.move(str(env.plugin("decisions") / "questions"), str(real))
        assert make_dir_link(env.plugin("decisions") / "questions", real)
        with mock.patch.object(decisions, "verify_battery_lock") as spy, read_spy() as reads:
            code, out, _ = run(["verify", "decisions"], env.repo)
        assert code == 1 and "无效：链接" in out
        spy.assert_not_called()
        question_files = {"mutation-equivalence.json", "report-screen.json", "run-health.json"}
        assert not any(pathlib.Path(p).name in question_files for p in reads)


def test_p05_resource_path_out_of_bounds(tmp_path):
    with make_env(tmp_path) as env:
        manifest, lock = build_consistent("zz-oob", resource_override="plugins/code-change/README.md")
        write_plugin(env, "zz-oob", manifest, lock)
        with read_spy() as reads:
            code, out, _ = run(["verify", "zz-oob"], env.repo)
        assert code == 1 and "无效：链接" in out
        assert not any(p.endswith("code-change" + os.sep + "README.md") for p in reads)


# ---------------------------------------------------------------------------
# P6：目录名与 plugin_id 不符 / 重复键 / 非法 JSON；坏插件不拖垮 list
# ---------------------------------------------------------------------------

def test_p06_dir_name_mismatch(tmp_path):
    with make_env(tmp_path) as env:
        src = env.plugin("code-change")
        dst = env.plugin("wrong-name")
        shutil.copytree(str(src), str(dst))
        code, out, _ = run(["verify", "wrong-name"], env.repo)
        assert code == 1 and "无效" in out and "plugin_id" in out


def test_p06_duplicate_key_and_bad_json(tmp_path):
    with make_env(tmp_path) as env:
        raw = (env.plugin("code-change") / "manifest.json").read_text(encoding="utf-8")
        (env.plugin("code-change") / "manifest.json").write_text(
            raw.rstrip()[:-1] + ',\n  "plugin_id": "code-change"\n}', encoding="utf-8")  # 重复键
        (env.plugin("docs-change") / "manifest.json").write_text("{ nope", encoding="utf-8")
        code, out, _ = run(["verify", "code-change"], env.repo)
        assert code == 1 and "无效" in out and "manifest.json" in out
        code, out, _ = run(["list"], env.repo)  # 坏插件不让 list 整体失败
        assert code == 0 and "code-change" in out and "docs-change" in out


# ---------------------------------------------------------------------------
# P7：enabled 缺省时 enable X 不改出只含 X 的列表
# ---------------------------------------------------------------------------

def test_p07_enable_when_unrestricted(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({})
        code, out, _ = run(["enable", "code-change"], env.repo)
        assert code == 0
        assert "不限制" in out
        cfg = env.read_config()
        assert cfg is None or "enabled" not in cfg.get("plugins", {})  # 没有写出 [code-change]


# ---------------------------------------------------------------------------
# P8：enabled 缺省时 disable X，坏插件仍进列表，并提示语义变化
# ---------------------------------------------------------------------------

def test_p08_disable_unrestricted_keeps_broken_plugin(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({})
        break_manifest(env, "docs-change")
        code, out, _ = run(["disable", "code-change"], env.repo)
        assert code == 0
        cfg = env.read_config()
        enabled = cfg["plugins"]["enabled"]
        assert "code-change" not in enabled and "docs-change" in enabled and "decisions" in enabled
        assert "不会自动启用" in out


# ---------------------------------------------------------------------------
# P9：缺权限 → BLOCKED；授予后列出因此满足的其他插件
# ---------------------------------------------------------------------------

def test_p09_permission_impact(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["network-decisions"]}})
        code, out, _ = run(["list"], env.repo)
        assert code == 0 and "python-checks" in out and "BLOCKED" in out
        code, _, err = run(["enable", "python-checks"], env.repo)  # 没给权限 → 用法错误
        assert code == 2
        code, out, _ = run(["enable", "python-checks", "--allow-permission", "read-candidate"], env.repo)
        assert code == 0
        for pid in ("code-change", "docs-change", "mutation-review", "repo-analysis"):
            assert pid in out
        assert env.read_config()["plugins"]["allowed_permissions"] == ["network-decisions", "read-candidate"]


# ---------------------------------------------------------------------------
# P10：--allow-permission 多于 / 少于 / 不限制时给了
# ---------------------------------------------------------------------------

def test_p10a_too_many(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["network-decisions"]}})
        code, _, _ = run(["enable", "python-checks", "--allow-permission", "read-candidate",
                          "--allow-permission", "network-decisions"], env.repo)
        assert code == 2


def test_p10b_too_few(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": []}})
        code, _, _ = run(["enable", "python-checks"], env.repo)
        assert code == 2


def test_p10c_grant_when_unrestricted(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({})
        code, _, _ = run(["enable", "python-checks", "--allow-permission", "read-candidate"], env.repo)
        assert code == 2


# ---------------------------------------------------------------------------
# P11：depends_on / conflicts 非空 → 本轮不支持（不是无效）；enable 拒绝
# ---------------------------------------------------------------------------

def test_p11_dependencies_unsupported(tmp_path):
    with make_env(tmp_path) as env:
        manifest, lock = build_consistent("dep-x", depends_on=["code-change"])
        write_plugin(env, "dep-x", manifest, lock)
        code, _, _ = run(["enable", "dep-x"], env.repo)
        assert code == 1
        code, out, _ = run(["list"], env.repo)
        assert code == 0 and "本轮不支持" in out
        code, out, _ = run(["verify", "dep-x"], env.repo)
        assert code == 1 and "本轮不支持" in out and "无效" not in out


# ---------------------------------------------------------------------------
# P12：坏插件不挡关闭；决策题库坏时的恢复路径
# ---------------------------------------------------------------------------

def test_p12a_disable_with_other_broken(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["code-change", "docs-change", "decisions"]}})
        break_manifest(env, "docs-change")
        code, out, _ = run(["disable", "code-change"], env.repo)
        assert code == 0
        assert "code-change" not in env.read_config()["plugins"]["enabled"]


def test_p12b_decisions_battery_recovery(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"decisions": {"mode": "on"}})
        add_extra_question(env)
        before = env.read_config()
        code, out, err = run(["disable", "code-change"], env.repo)
        assert code == 1
        assert env.read_config() == before  # 配置不变
        assert "plugins disable decisions" in (out + err) and "config decisions off" in (out + err)
        code, _, _ = run(["disable", "decisions"], env.repo)
        assert code == 0
        assert "decisions" not in env.read_config()["plugins"]["enabled"]
        code, _, _ = run(["disable", "code-change"], env.repo)
        assert code == 0
        enabled = env.read_config()["plugins"]["enabled"]
        assert "code-change" not in enabled and "decisions" not in enabled


# ---------------------------------------------------------------------------
# P13：非列表值 → 拒绝并给修复提示；提示执行后确实成功
# ---------------------------------------------------------------------------

def test_p13_single_null(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": None}, "kill_grace_seconds": 20})
        code, _, err = run(["enable", "code-change"], env.repo)
        assert code == 1 and "修复：" in err
        code, _, _ = run_hint(hint_from(err), env.repo)
        assert code == 0
        code, _, _ = run(["verify"], env.repo)
        assert code == 0


def test_p13_both_null(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": None, "allowed_permissions": None}, "kill_grace_seconds": 20})
        code, _, err = run(["disable", "code-change"], env.repo)
        assert code == 1 and "修复：" in err
        code, _, _ = run_hint(hint_from(err), env.repo)
        assert code == 0


def test_p13_both_null_with_broken_battery(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"decisions": {"mode": "on"},
                          "plugins": {"enabled": None, "allowed_permissions": None}, "kill_grace_seconds": 20})
        add_extra_question(env)
        code, _, err = run(["enable", "code-change"], env.repo)
        assert code == 1 and "修复：" in err
        hint = hint_from(err)
        assert hint.startswith("config set plugins ")
        code, _, herr = run_hint(hint, env.repo)
        assert code == 0, herr
        assert env.read_config()["plugins"]["enabled"] and "decisions" not in env.read_config()["plugins"]["enabled"]


# ---------------------------------------------------------------------------
# P14：启用锁不一致的插件被拒；配置另有无效键时 enable 不绕过整份校验
# ---------------------------------------------------------------------------

def test_p14a_enable_drifted_lock(tmp_path):
    with make_env(tmp_path) as env:
        lock = json.loads((env.plugin("code-change") / "lock.json").read_text(encoding="utf-8"))
        lock["lock_sha256"] = ("f" if lock["lock_sha256"][0] != "f" else "0") + lock["lock_sha256"][1:]
        (env.plugin("code-change") / "lock.json").write_text(json.dumps(lock), encoding="utf-8")
        env.write_config({"plugins": {"enabled": ["docs-change"]}})
        before = env.read_config()
        code, _, _ = run(["enable", "code-change"], env.repo)
        assert code == 1
        assert env.read_config() == before


def test_p14b_enable_with_other_invalid_key(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"surprise_key": 1, "plugins": {"enabled": ["docs-change"]}})
        before = env.read_config()
        code, _, err = run(["enable", "code-change"], env.repo)
        assert code == 1
        assert env.read_config() == before


# ---------------------------------------------------------------------------
# P15：写入中途失败，配置字节不变
# ---------------------------------------------------------------------------

def test_p15_write_failure_leaves_config(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["docs-change"]}})
        before = (env.repo / ".agent" / "dispatch.config.json").read_bytes()
        with mock.patch("os.replace", side_effect=OSError("disk full")):
            code, _, err = run(["enable", "code-change"], env.repo)
        assert code == 1
        assert (env.repo / ".agent" / "dispatch.config.json").read_bytes() == before


# ---------------------------------------------------------------------------
# P16：关掉 decisions 提示 off；--dry-run 不落盘
# ---------------------------------------------------------------------------

def test_p16a_disable_decisions_notes_off(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["code-change", "decisions"]}})
        code, out, _ = run(["disable", "decisions"], env.repo)
        assert code == 0 and "off" in out
        assert "决策插件会因此变为 off" in out
        assert "decisions" not in env.read_config()["plugins"]["enabled"]


def test_p16b_dry_run_no_write(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["code-change", "decisions"]}})
        before = (env.repo / ".agent" / "dispatch.config.json").read_bytes()
        code, out, _ = run(["disable", "decisions", "--dry-run"], env.repo)
        assert code == 0
        assert (env.repo / ".agent" / "dispatch.config.json").read_bytes() == before
        assert "enabled" in out


# ---------------------------------------------------------------------------
# P17：enabled 拼错 → verify 退出码 1，list 不崩
# ---------------------------------------------------------------------------

def test_p17_typo_enabled(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["decisons"]}})
        code, _, _ = run(["verify"], env.repo)
        assert code == 1
        code, out, _ = run(["list"], env.repo)
        assert code == 0 and "decisons" in out and "未安装" in out


def test_json_outputs_parse_to_objects(tmp_path):
    # S7 / T1：--json 的输出可解析为 JSON 对象（不断言键名）。
    with make_env(tmp_path) as env:
        for argv in (["list", "--json"], ["verify", "--json"], ["show", "decisions", "--json"]):
            code, out, _ = run(argv, env.repo)
            assert code == 0, argv
            assert isinstance(json.loads(out), dict), argv


# ---------------------------------------------------------------------------
# B1：不在 Git 仓库（G1）与未知插件 ID（G2）
# ---------------------------------------------------------------------------

def test_g1_outside_git_repo_all_subcommands_exit_2(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    for argv in (["list"], ["show", "decisions"], ["verify"],
                 ["enable", "code-change"], ["disable", "code-change"]):
        code, out, err = run(argv, plain)
        assert code == 2, argv
        assert "ERROR:" in (out + err), argv
        assert "Traceback" not in (out + err), argv


def test_g2_unknown_id_exit_2(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["code-change"]}})
        before = (env.repo / ".agent" / "dispatch.config.json").read_bytes()
        for argv in (["enable", "no-such-plugin"], ["disable", "no-such-plugin"],
                     ["show", "no-such-plugin"], ["verify", "no-such-plugin"]):
            code, out, err = run(argv, env.repo)
            assert code == 2, argv
            assert "ERROR:" in (out + err), argv
            assert "Traceback" not in (out + err), argv
        assert (env.repo / ".agent" / "dispatch.config.json").read_bytes() == before


def test_g4_dry_run_validation_failure_exit_1_bytes_unchanged(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"surprise_key": 1, "plugins": {"enabled": ["docs-change"]}})
        before = (env.repo / ".agent" / "dispatch.config.json").read_bytes()
        code, out, err = run(["enable", "code-change", "--dry-run"], env.repo)
        assert code == 1
        assert "ERROR:" in err
        assert "Traceback" not in err and "Traceback" not in out
        assert (env.repo / ".agent" / "dispatch.config.json").read_bytes() == before


def test_g4_dry_run_success_exit_0_no_write(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["code-change", "docs-change"]}})
        before = (env.repo / ".agent" / "dispatch.config.json").read_bytes()
        code, out, _ = run(["disable", "docs-change", "--dry-run"], env.repo)
        assert code == 0
        assert (env.repo / ".agent" / "dispatch.config.json").read_bytes() == before
        assert "plugins" in out


# ---------------------------------------------------------------------------
# B3：插件 ID 先按 PLUGIN_ID 校验
# ---------------------------------------------------------------------------

def test_b3_plugin_id_not_matching_exit_2_no_traceback(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["code-change"]}})
        before = (env.repo / ".agent" / "dispatch.config.json").read_bytes()
        for bad in ("../plugins/code-change", "a/b", ""):
            for argv in (["show", bad], ["verify", bad], ["enable", bad], ["disable", bad]):
                code, out, err = run(argv, env.repo)
                assert code == 2, argv
                assert "ERROR:" in (out + err), argv
                assert "Traceback" not in (out + err), argv
        assert (env.repo / ".agent" / "dispatch.config.json").read_bytes() == before


# ---------------------------------------------------------------------------
# M1：P5 的链接与边界子情形（plugins 根、中间目录、资源路径、文件符号链接）
# ---------------------------------------------------------------------------

def test_p05_plugins_root_is_junction(tmp_path):
    with make_env(tmp_path) as env:
        real = tmp_path / "real_plugins"
        shutil.move(str(env.plugins), str(real))
        assert make_dir_link(env.plugins, real)
        with read_spy() as reads:
            code, out, _ = run(["verify"], env.repo)
        assert code == 1
        assert "无效：链接" in out
        assert not any(("plugins" + os.sep) in p and p.endswith("manifest.json") for p in reads)


def test_p05_intermediate_dir_is_junction(tmp_path):
    with make_env(tmp_path) as env:
        manifest, lock = build_consistent("zz-mid", resource_override="plugins/zz-mid/sub/data.txt")
        write_plugin(env, "zz-mid", manifest, lock)
        real = tmp_path / "zz_mid_real"
        real.mkdir()
        (real / "data.txt").write_bytes(b"payload\n")
        assert make_dir_link(env.plugin("zz-mid") / "sub", real)
        with read_spy() as reads:
            code, out, _ = run(["verify", "zz-mid"], env.repo)
        assert code == 1
        assert "无效：链接" in out
        assert not any(p.endswith("data.txt") for p in reads)


def test_p05_resource_path_is_junction(tmp_path):
    with make_env(tmp_path) as env:
        manifest, lock = build_consistent("zz-res", resource_override="plugins/zz-res/res.bin")
        write_plugin(env, "zz-res", manifest, lock)
        real = tmp_path / "zz_res_real"
        real.mkdir()
        (real / "res.bin").write_bytes(b"payload\n")
        assert make_dir_link(env.plugin("zz-res") / "res.bin", real)
        with read_spy() as reads:
            code, out, _ = run(["verify", "zz-res"], env.repo)
        assert code == 1
        assert "无效：链接" in out
        assert not any(p.endswith("res.bin") for p in reads)


def test_p05_manifest_file_symlink_identical_content(tmp_path):
    with make_env(tmp_path) as env:
        mf = env.plugin("code-change") / "manifest.json"
        replace_with_file_symlink(mf, tmp_path, "mf_copy.json")
        with read_spy() as reads:
            code, out, _ = run(["verify", "code-change"], env.repo)
        assert code == 1 and "无效：链接" in out
        assert not any(p.endswith("manifest.json") and "code-change" in p for p in reads)


def test_p05_lock_file_symlink_identical_content(tmp_path):
    with make_env(tmp_path) as env:
        lk = env.plugin("code-change") / "lock.json"
        replace_with_file_symlink(lk, tmp_path, "lk_copy.json")
        with read_spy() as reads:
            code, out, _ = run(["verify", "code-change"], env.repo)
        assert code == 1 and "无效：链接" in out
        assert not any(p.endswith("lock.json") and "code-change" in p for p in reads)


def test_p05_questions_json_file_symlink(tmp_path):
    with make_env(tmp_path) as env:
        question = env.plugin("decisions") / "questions" / "run-health.json"
        replace_with_file_symlink(question, tmp_path, "run_health_copy.json")
        with mock.patch.object(decisions, "verify_battery_lock") as spy, read_spy() as reads:
            code, out, _ = run(["verify", "decisions"], env.repo)
        assert code == 1 and "无效：链接" in out
        spy.assert_not_called()
        assert not any(p.endswith("run-health.json") for p in reads)


def test_p05_resource_file_symlink(tmp_path):
    with make_env(tmp_path) as env:
        readme = env.plugin("code-change") / "README.md"
        replace_with_file_symlink(readme, tmp_path, "readme_copy.md")
        with read_spy() as reads:
            code, out, _ = run(["verify", "code-change"], env.repo)
        assert code == 1 and "无效：链接" in out
        assert not any(p.endswith("README.md") and "code-change" in p for p in reads)


# ---------------------------------------------------------------------------
# B2：授予权限时其他插件的 manifest 也要读前检查，问题不静默跳过
# ---------------------------------------------------------------------------

def test_b2_grant_path_other_plugin_dir_link_not_read_and_reported(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["network-decisions"]}})
        real = tmp_path / "real_docs_change"
        shutil.move(str(env.plugin("docs-change")), str(real))
        assert make_dir_link(env.plugin("docs-change"), real)
        with read_spy() as reads:
            code, out, _ = run(["enable", "python-checks", "--allow-permission", "read-candidate"], env.repo)
        assert code == 0
        assert not any(p.endswith("manifest.json") and "docs-change" in p for p in reads)
        assert "docs-change" in out and "无效：链接" in out
        impact = _impact_lines(out)
        assert impact and all("docs-change" not in line for line in impact), impact


def test_b2_grant_path_other_manifest_junction_not_read_and_reported(tmp_path):
    # 目录链接变体：另一个插件的 manifest.json 位置是目录 junction（文件链接需要权限，本机只能用这个）。
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["network-decisions"]}})
        env.plugin("docs-change").joinpath("manifest.json").unlink()
        target = tmp_path / "docs_change_manifest_target"
        target.mkdir()
        assert make_dir_link(env.plugin("docs-change") / "manifest.json", target)
        with read_spy() as reads:
            code, out, _ = run(["enable", "python-checks", "--allow-permission", "read-candidate"], env.repo)
        assert code == 0
        assert not any(p.endswith("manifest.json") and "docs-change" in p for p in reads)
        assert "docs-change" in out and "无效：链接" in out
        impact = _impact_lines(out)
        assert impact and all("docs-change" not in line for line in impact), impact


def test_b2_grant_path_broken_manifest_reported_not_silent(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["network-decisions"]}})
        break_manifest(env, "docs-change")
        code, out, _ = run(["enable", "python-checks", "--allow-permission", "read-candidate"], env.repo)
        assert code == 0
        assert "docs-change" in out and "无效" in out
        impact = _impact_lines(out)
        assert all("docs-change" not in line for line in impact), impact


# ---------------------------------------------------------------------------
# m1 / m2 / m3 / m5
# ---------------------------------------------------------------------------

def test_m1_allowed_permissions_written_sorted_unique(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["zeta-perm", "network-decisions"]}})
        code, _, _ = run(["enable", "python-checks", "--allow-permission", "read-candidate"], env.repo)
        assert code == 0
        assert env.read_config()["plugins"]["allowed_permissions"] == [
            "network-decisions", "read-candidate", "zeta-perm"]


def test_m2_show_generation_and_resource_hash(tmp_path):
    with make_env(tmp_path) as env:
        code, out, _ = run(["show", "code-change"], env.repo)
        assert code == 0
        assert "generation" in out
        rows = _resource_rows(out, "README.md")
        assert rows and all("不一致" not in row and "一致" in row for row in rows), rows
        readme = env.plugin("code-change") / "README.md"
        readme.write_bytes(readme.read_bytes() + b"x")
        code, out, _ = run(["show", "code-change"], env.repo)
        assert code == 0
        rows = _resource_rows(out, "README.md")
        assert rows and all("不一致" in row for row in rows), rows


def test_m3_plugins_root_link_enumeration_empty(tmp_path):
    with make_env(tmp_path) as env:
        real = tmp_path / "real_plugins"
        shutil.move(str(env.plugins), str(real))
        assert make_dir_link(env.plugins, real)
        env.write_config({"plugins": {"enabled": ["code-change"]}})
        before = (env.repo / ".agent" / "dispatch.config.json").read_bytes()
        code, out, _ = run(["list"], env.repo)
        assert code == 0 and "无效：链接 plugins" in out
        code, _, _ = run(["verify"], env.repo)
        assert code == 1
        code, _, err = run(["disable", "code-change"], env.repo)
        assert code == 2 and "ERROR:" in err
        assert (env.repo / ".agent" / "dispatch.config.json").read_bytes() == before


def test_m3_battery_oserror_collected_in_verify(tmp_path):
    with make_env(tmp_path) as env:
        with mock.patch.object(decisions, "verify_battery_lock", side_effect=OSError("boom")):
            code, out, err = run(["verify", "decisions"], env.repo)
        assert code == 1
        assert "Traceback" not in err and "Traceback" not in out
        assert "decisions" in out


def test_m3_battery_valueerror_refuses_enable(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"decisions": {"mode": "on"}, "plugins": {"enabled": ["decisions"]}})
        before = (env.repo / ".agent" / "dispatch.config.json").read_bytes()
        with mock.patch.object(decisions, "verify_battery_lock", side_effect=ValueError("bad battery")):
            code, out, err = run(["enable", "code-change"], env.repo)
        assert code == 1
        assert "ERROR:" in err
        assert "Traceback" not in err and "Traceback" not in out
        assert (env.repo / ".agent" / "dispatch.config.json").read_bytes() == before


def test_m5_disable_unrestricted_excludes_linked_plugin_dir(tmp_path):
    with make_env(tmp_path) as env:
        real = tmp_path / "real_docs_checks"
        shutil.move(str(env.plugin("docs-checks")), str(real))
        assert make_dir_link(env.plugin("docs-checks"), real)
        env.write_config({})
        code, _, _ = run(["disable", "code-change"], env.repo)
        assert code == 0
        enabled = env.read_config()["plugins"]["enabled"]
        assert "docs-checks" not in enabled and "code-change" not in enabled
        assert "decisions" in enabled


def test_m5_no_version_option(tmp_path):
    with make_env(tmp_path) as env:
        code, _, _ = run(["--version"], env.repo)
        assert code == 2


# ---------------------------------------------------------------------------
# 设计 §9 里还能写的小量用例
# ---------------------------------------------------------------------------

def test_p09b_dry_run_lists_impact_no_write(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["network-decisions"]}})
        before = (env.repo / ".agent" / "dispatch.config.json").read_bytes()
        code, out, _ = run(["enable", "python-checks", "--allow-permission", "read-candidate", "--dry-run"],
                           env.repo)
        assert code == 0
        assert "code-change" in out
        assert (env.repo / ".agent" / "dispatch.config.json").read_bytes() == before


def test_p11b_conflicts_unsupported(tmp_path):
    with make_env(tmp_path) as env:
        manifest, lock = build_consistent("conf-x")
        manifest["conflicts"] = ["code-change"]
        write_plugin(env, "conf-x", manifest, lock)
        code, _, _ = run(["enable", "conf-x"], env.repo)
        assert code == 1
        code, out, _ = run(["verify", "conf-x"], env.repo)
        assert code == 1 and "本轮不支持" in out


def test_p12c_two_broken_manifests_disable_one(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["code-change", "docs-change", "docs-checks"]}})
        break_manifest(env, "docs-change")
        break_manifest(env, "docs-checks")
        code, _, _ = run(["disable", "docs-change"], env.repo)
        assert code == 0
        assert env.read_config()["plugins"]["enabled"] == ["code-change", "docs-checks"]
