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
    # 规划端补强：README 的全量命令把 --basetemp 放在仓库内（.agent/runs/_tmp/），git 会从 plain 往上找到
    # 本仓库。GIT_CEILING_DIRECTORIES 让 git 不越过 tmp_path，plain 才真的“不在 Git 仓库里”。
    with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(tmp_path)}):
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


# ---------------------------------------------------------------------------
# v2 增补（kit-plugins 返工）。每例只断言 v2 合同写明的词、退出码、插件 ID、文件字节，以及
# “被拒绝的路径从未被读取”。每例都断言输出里没有堆栈。字符串值用递归遍历查找，不依赖 JSON 键名。
# ---------------------------------------------------------------------------

_V2_LINK = "无效：链接"


def _v2_clean(out, err):
    assert "Traceback" not in out and "Traceback" not in err, (out, err)


def _v2_norm(path):
    return str(path).replace("\\", "/")


def _v2_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _v2_strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _v2_strings(value)


def _v2_title(out, plugin_id):
    """verify 的标题行：以“插件 ID 加一个空格”开头的行（问题行缩进两个空格，不会匹配）。"""
    lines = [line for line in out.splitlines() if line.startswith(plugin_id + " ")]
    assert lines, (plugin_id, out)
    return lines[0]


def _v2_row(out, plugin_id):
    """list 的一行：第一个词是插件 ID。"""
    lines = [line for line in out.splitlines() if line.split()[:1] == [plugin_id]]
    assert lines, (plugin_id, out)
    return lines[0]


@contextlib.contextmanager
def _v2_fail_reads(suffix, error):
    """读取路径以 suffix（/ 分隔）结尾的文件时抛 error；覆盖 Path 与 io 的读取入口，其余读取照常。"""
    def hit(file):
        return _v2_norm(file).endswith(suffix)

    real_rb, real_rt, real_po = pathlib.Path.read_bytes, pathlib.Path.read_text, pathlib.Path.open
    real_open, real_io_open = builtins.open, io.open

    def rb(self, *a, **k):
        if hit(self):
            raise error
        return real_rb(self, *a, **k)

    def rt(self, *a, **k):
        if hit(self):
            raise error
        return real_rt(self, *a, **k)

    def po(self, *a, **k):
        if hit(self):
            raise error
        return real_po(self, *a, **k)

    def op(file, *a, **k):
        if hit(file):
            raise error
        return real_open(file, *a, **k)

    def iop(file, *a, **k):
        if hit(file):
            raise error
        return real_io_open(file, *a, **k)

    with mock.patch.object(pathlib.Path, "read_bytes", rb), \
            mock.patch.object(pathlib.Path, "read_text", rt), \
            mock.patch.object(pathlib.Path, "open", po), \
            mock.patch.object(builtins, "open", op), \
            mock.patch.object(io, "open", iop):
        yield


@contextlib.contextmanager
def _v2_links_at(suffix):
    """只让 pi_dispatch.is_link_or_junction 把路径以 suffix 结尾的那一个路径判为链接；其余照常。"""
    real = pd.is_link_or_junction

    def fake(path):
        if _v2_norm(path).endswith(suffix):
            return True
        return real(path)

    with mock.patch.object(pd, "is_link_or_junction", fake):
        yield


@contextlib.contextmanager
def _v2_spy_permission_check():
    calls = []
    real = plugins.check_permission_intersection

    def wrapper(*args, **kwargs):
        calls.append(kwargs.get("allowed_permissions"))
        return real(*args, **kwargs)

    with mock.patch.object(plugins, "check_permission_intersection", wrapper):
        yield calls


def _v2_tamper_lock_sha(env, plugin_id):
    lock_path = env.plugin(plugin_id) / "lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["lock_sha256"] = "1" * 64
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    return lock


def _v2_break_decisions_battery_dir(env):
    question = env.plugin("decisions") / "questions" / "run-health.json"
    question.unlink()
    question.mkdir()


def _v2_move_dir_into_junction(env, tmp_path, plugin_id):
    real = tmp_path / ("real_" + plugin_id.replace("-", "_"))
    shutil.move(str(env.plugin(plugin_id)), str(real))
    assert make_dir_link(env.plugin(plugin_id), real)


# 01：verify --json 的退出码

def test_v2_01a_verify_json_all_consistent_exit_0(tmp_path):
    with make_env(tmp_path) as env:
        code, out, err = run(["verify", "--json"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        assert isinstance(json.loads(out), dict)


def test_v2_01b_verify_json_problem_exit_1(tmp_path):
    with make_env(tmp_path) as env:
        break_manifest(env, "docs-change")
        code, out, err = run(["verify", "--json"], env.repo)
        _v2_clean(out, err)
        assert code == 1
        assert isinstance(json.loads(out), dict)


def test_v2_01c_verify_one_json_problem_exit_1(tmp_path):
    with make_env(tmp_path) as env:
        break_manifest(env, "docs-change")
        code, out, err = run(["verify", "docs-change", "--json"], env.repo)
        _v2_clean(out, err)
        assert code == 1
        assert any("无效" in s for s in _v2_strings(json.loads(out)))


def test_v2_01d_verify_json_unknown_id_exit_2(tmp_path):
    with make_env(tmp_path) as env:
        code, out, err = run(["verify", "no-such-plugin", "--json"], env.repo)
        _v2_clean(out, err)
        assert code == 2


# 02：list 的启用列（是 / 否 / 不限制）

def test_v2_02a_enabled_column_unrestricted(tmp_path):
    with make_env(tmp_path) as env:
        code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        for pid in EIGHT_PLUGIN_IDS:
            assert "不限制" in _v2_row(out, pid), pid


def test_v2_02b_enabled_column_yes_and_no(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["docs-change"]}})
        code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        assert "是" in _v2_row(out, "docs-change")
        assert "否" in _v2_row(out, "code-change")
        assert "不限制" not in _v2_row(out, "code-change")


# 03：锁列只取四个值；链接变体（插件目录、manifest.json、资源）

def test_v2_03a_plugin_dir_junction_lock_invalid(tmp_path):
    with make_env(tmp_path) as env:
        _v2_move_dir_into_junction(env, tmp_path, "docs-change")
        code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0 and _V2_LINK in _v2_row(out, "docs-change")
        code, out, err = run(["verify", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 1
        assert _v2_title(out, "docs-change") == "docs-change 无效"
        assert _V2_LINK in out


def test_v2_03b_list_json_lock_value_is_plain_invalid(tmp_path):
    with make_env(tmp_path) as env:
        _v2_move_dir_into_junction(env, tmp_path, "docs-change")
        code, out, err = run(["list", "--json"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        strings = list(_v2_strings(json.loads(out)))
        assert "无效" in strings          # 锁列的值之一
        assert _V2_LINK not in strings    # “无效：链接”不作为单独的值出现
        assert any(_V2_LINK in s for s in strings)  # 只出现在原因或问题文字里


def test_v2_03c_manifest_junction_lock_invalid(tmp_path):
    with make_env(tmp_path) as env:
        env.plugin("docs-change").joinpath("manifest.json").unlink()
        target = tmp_path / "docs_change_manifest_dir"
        target.mkdir()
        assert make_dir_link(env.plugin("docs-change") / "manifest.json", target)
        code, out, err = run(["verify", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 1
        assert _v2_title(out, "docs-change") == "docs-change 无效"
        assert _V2_LINK in out


def test_v2_03d_resource_junction_lock_invalid(tmp_path):
    with make_env(tmp_path) as env:
        readme = env.plugin("docs-change") / "README.md"
        readme.unlink()
        target = tmp_path / "docs_change_readme_dir"
        target.mkdir()
        assert make_dir_link(readme, target)
        code, out, err = run(["verify", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 1
        assert _v2_title(out, "docs-change") == "docs-change 无效"
        assert _V2_LINK in out
        code, out, err = run(["show", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        rows = _resource_rows(out, "README.md")
        assert rows and all(_V2_LINK in row for row in rows), rows


# 04：资源读取失败（文件存在，读取抛 PermissionError）

def test_v2_04a_resource_read_failure_verify_and_show(tmp_path):
    with make_env(tmp_path) as env:
        with _v2_fail_reads("plugins/code-change/README.md", PermissionError("denied")):
            code_v, out_v, err_v = run(["verify", "code-change"], env.repo)
            code_s, out_s, err_s = run(["show", "code-change"], env.repo)
        _v2_clean(out_v, err_v)
        assert code_v == 1
        assert _v2_title(out_v, "code-change") == "code-change 无效"
        assert "资源读取失败" in out_v
        _v2_clean(out_s, err_s)
        assert code_s == 0
        rows = _resource_rows(out_s, "README.md")
        assert rows and all("不一致" in row for row in rows), rows


def test_v2_04b_resource_read_failure_list_row(tmp_path):
    with make_env(tmp_path) as env:
        with _v2_fail_reads("plugins/code-change/README.md", PermissionError("denied")):
            code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        row = _v2_row(out, "code-change")
        assert "不一致" in row and "无效" in row and "BLOCKED" in row


# 05：列入但未安装（枚举结果里没有的 ID 才算未安装；链接目录算已安装）

def test_v2_05a_enabled_not_installed_lines(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["docs-change", "ghost-plugin"]}})
        code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0 and "ghost-plugin 未安装" in out
        code, out, err = run(["verify"], env.repo)
        _v2_clean(out, err)
        assert code == 1 and "ghost-plugin 未安装" in out
        code, out, err = run(["verify", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 0


def test_v2_05b_linked_plugin_dir_counts_as_installed(tmp_path):
    with make_env(tmp_path) as env:
        _v2_move_dir_into_junction(env, tmp_path, "docs-change")
        env.write_config({"plugins": {"enabled": ["docs-change"]}})
        code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        assert "docs-change 未安装" not in out
        assert _V2_LINK in _v2_row(out, "docs-change")


# 06：plugins 段不是对象（None / [] / "x"）：五个子命令都拒绝；修复提示执行后成功；其他键保持

@pytest.mark.parametrize("bad", [None, [], "x"], ids=["null", "list", "string"])
def test_v2_06_plugins_not_object_all_subcommands(tmp_path, bad):
    with make_env(tmp_path) as env:
        env.write_config({"kill_grace_seconds": 20, "plugins": bad})
        path = env.repo / ".agent" / "dispatch.config.json"
        before = path.read_bytes()
        for argv in (["enable", "docs-change"], ["disable", "docs-change"]):
            code, out, err = run(argv, env.repo)
            _v2_clean(out, err)
            assert code == 1, argv
            assert "ERROR:" in err and "修复：" in err, argv
            assert path.read_bytes() == before, argv
        for argv in (["list"], ["show", "docs-change"], ["verify"], ["verify", "docs-change"]):
            code, out, err = run(argv, env.repo)
            _v2_clean(out, err)
            assert code == 1, argv
            assert "ERROR:" in err, argv
        assert path.read_bytes() == before
        code, out, err = run(["disable", "docs-change"], env.repo)
        hint_code, _, herr = run_hint(hint_from(err), env.repo)
        assert hint_code == 0, herr
        assert env.read_config()["kill_grace_seconds"] == 20
        code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0


# 07：修复提示只来自原配置，执行后成功

def test_v2_07a_hint_fixes_one_bad_subkey_keeps_others(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"kill_grace_seconds": 20,
                          "plugins": {"enabled": "docs-change", "allowed_permissions": ["read-candidate"]}})
        code, out, err = run(["disable", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 1 and "修复：" in err
        hint_code, _, herr = run_hint(hint_from(err), env.repo)
        assert hint_code == 0, herr
        cfg = env.read_config()
        assert cfg["plugins"]["allowed_permissions"] == ["read-candidate"]
        assert cfg["kill_grace_seconds"] == 20
        code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0


def test_v2_07b_hint_computed_from_original_config_runs(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"kill_grace_seconds": 20, "plugins": {"enabled": "x", "foo": 1}})
        code, out, err = run(["enable", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 1 and "修复：" in err
        hint_code, _, herr = run_hint(hint_from(err), env.repo)
        assert hint_code == 0, herr
        assert env.read_config()["kill_grace_seconds"] == 20
        code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0


# 08：无变化路径与写入共用题库门禁（决策插件生效且题库坏：门禁给恢复顺序，配置不变）

def test_v2_08a_no_change_path_runs_battery_gate(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"decisions": {"mode": "shadow"}, "plugins": {"enabled": ["decisions"]}})
        _v2_break_decisions_battery_dir(env)
        path = env.repo / ".agent" / "dispatch.config.json"
        before = path.read_bytes()
        code, out, err = run(["disable", "docs-change"], env.repo)  # docs-change 不在列表里：没有变化
        _v2_clean(out, err)
        assert code == 1
        assert "plugins disable decisions" in err and "config decisions off" in err
        assert "没有变化" not in out
        assert path.read_bytes() == before


def test_v2_08b_disable_decisions_recovers_exit_0(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"decisions": {"mode": "shadow"}, "plugins": {"enabled": ["decisions"]}})
        _v2_break_decisions_battery_dir(env)
        code, out, err = run(["disable", "decisions"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        assert "decisions" not in env.read_config()["plugins"]["enabled"]
        assert "决策插件会因此变为 off" in out


# 09：列表元素不合法：五个子命令都拒绝（退出 1），不冒堆栈，配置字节不变

@pytest.mark.parametrize("plugins_value", [
    {"enabled": ["code-change", 5]},
    {"allowed_permissions": ["network-decisions", 5]},
    {"enabled": [["x"]]},
], ids=["enabled-number", "allowed-number", "enabled-nested-list"])
def test_v2_09_list_element_invalid_all_subcommands(tmp_path, plugins_value):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": plugins_value})
        path = env.repo / ".agent" / "dispatch.config.json"
        before = path.read_bytes()
        for argv in (["list"], ["show", "docs-change"], ["verify"], ["verify", "docs-change"],
                     ["enable", "docs-change"], ["disable", "docs-change"]):
            code, out, err = run(argv, env.repo)
            _v2_clean(out, err)
            assert code == 1, argv
            assert "ERROR:" in err, argv
            assert path.read_bytes() == before, argv


# 10：检查顺序：G1 → ID 格式 → ID 存在 → 读配置；配置读不出时，ID 错误仍是 2

def test_v2_10_check_order_id_before_config(tmp_path):
    with make_env(tmp_path) as env:
        (env.repo / ".agent" / "dispatch.config.json").write_text("{ not json", encoding="utf-8")
        for argv, expected in (
                (["verify", "no-such-plugin"], 2), (["verify", "../x"], 2),
                (["show", "no-such-plugin"], 2), (["enable", "no-such-plugin"], 2),
                (["verify", "docs-change"], 1), (["list"], 1)):
            code, out, err = run(argv, env.repo)
            _v2_clean(out, err)
            assert code == expected, argv
            assert "ERROR:" in err, argv


# 11：show 的 generation 与 lock_sha256 原值；锁漂移时照常输出

def test_v2_11_show_lock_drift_prints_generation_and_value(tmp_path):
    with make_env(tmp_path) as env:
        lock = _v2_tamper_lock_sha(env, "docs-change")
        code, out, err = run(["show", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        assert "漂移" in out
        gen_lines = [line for line in out.splitlines() if "generation" in line]
        assert gen_lines and str(lock["generation"]) in gen_lines[0], out
        assert "1" * 64 in out


# 12：状态与权限核对：只有限制权限时才调用 check_permission_intersection；READY 与 BLOCKED 的依据

def test_v2_12a_unrestricted_does_not_call_permission_check(tmp_path):
    with make_env(tmp_path) as env:
        with _v2_spy_permission_check() as calls:
            code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0 and calls == []


def test_v2_12b_restricted_calls_permission_check(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["read-candidate", "network-decisions"]}})
        with _v2_spy_permission_check() as calls:
            code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0 and len(calls) > 0


def test_v2_12c_consistent_not_enabled_is_ready(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["decisions"], "allowed_permissions": ["read-candidate"]}})
        code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        row = _v2_row(out, "docs-change")
        assert "READY" in row and "否" in row


def test_v2_12d_drift_is_blocked_with_drift_word(tmp_path):
    with make_env(tmp_path) as env:
        _v2_tamper_lock_sha(env, "docs-change")
        env.write_config({"plugins": {"allowed_permissions": ["read-candidate"]}})
        code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        row = _v2_row(out, "docs-change")
        assert "BLOCKED" in row and "漂移" in row


def test_v2_12e_missing_permission_blocks_and_is_named(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["network-decisions"]}})
        code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        row = _v2_row(out, "docs-change")
        assert "BLOCKED" in row and "read-candidate" in row


# 13：变化摘要 plugins.<键>: 旧 → 新（写入与 --dry-run 都有）

def test_v2_13a_enable_writes_summary(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["decisions"]}})
        code, out, err = run(["enable", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        assert "plugins.enabled" in out and "→" in out
        assert env.read_config()["plugins"]["enabled"] == ["decisions", "docs-change"]


def test_v2_13b_enable_dry_run_summary_no_write(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["decisions"]}})
        path = env.repo / ".agent" / "dispatch.config.json"
        before = path.read_bytes()
        code, out, err = run(["enable", "docs-change", "--dry-run"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        assert "plugins.enabled" in out and "→" in out
        assert path.read_bytes() == before


def test_v2_13c_grant_summary_allowed_permissions(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["network-decisions"]}})
        code, out, err = run(["enable", "python-checks", "--allow-permission", "read-candidate"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        assert "plugins.allowed_permissions" in out and "→" in out


# 14：“没有变化”只说一次；决策插件的 off 提示只在它真的被关掉时出现

def test_v2_14a_no_change_printed_once_when_not_listed(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["decisions"]}})
        code, out, err = run(["disable", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        assert out.count("没有变化") == 1
        assert "决策插件会因此变为 off" not in out


def test_v2_14b_no_change_printed_once_when_unrestricted_enable(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({})
        code, out, err = run(["enable", "code-change"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        assert out.count("没有变化") == 1


def test_v2_14c_docs_change_disable_no_off_hint(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["decisions", "docs-change"]}})
        code, out, err = run(["disable", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        assert "决策插件会因此变为 off" not in out
        assert env.read_config()["plugins"]["enabled"] == ["decisions"]


def test_v2_14d_disable_decisions_not_listed_no_off_hint(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"enabled": ["docs-change"]}})
        code, out, err = run(["disable", "decisions"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        assert out.count("没有变化") == 1
        assert "决策插件会因此变为 off" not in out


# 15：悬空链接（指向已删除目标的 junction）仍按链接处理

def test_v2_15a_plugins_root_dangling_junction(tmp_path):
    with make_env(tmp_path) as env:
        moved = tmp_path / "moved_plugins"
        shutil.move(str(env.plugins), str(moved))
        assert make_dir_link(env.plugins, moved)
        shutil.rmtree(str(moved))
        code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0 and "无效：链接 plugins" in out
        code, out, err = run(["verify"], env.repo)
        _v2_clean(out, err)
        assert code == 1 and "无效：链接 plugins" in out


def test_v2_15b_dangling_plugin_dir_junction_is_link(tmp_path):
    with make_env(tmp_path) as env:
        moved = tmp_path / "moved_docs_change"
        shutil.move(str(env.plugin("docs-change")), str(moved))
        assert make_dir_link(env.plugin("docs-change"), moved)
        shutil.rmtree(str(moved))
        code, out, err = run(["verify", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 1
        assert _v2_title(out, "docs-change") == "docs-change 无效"
        assert _V2_LINK in out
        code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0 and _V2_LINK in _v2_row(out, "docs-change")


# 16：文件级链接（用 is_link_or_junction 替身判定）；被拒绝的路径从未被读取；
#     题库链接或非普通文件时不调用 verify_battery_lock；verify 标题行不把资源不一致打成“一致”

def test_v2_16a_manifest_link_not_read(tmp_path):
    with make_env(tmp_path) as env:
        with _v2_links_at("plugins/code-change/manifest.json"), read_spy() as reads:
            code, out, err = run(["verify", "code-change"], env.repo)
        _v2_clean(out, err)
        assert code == 1 and _V2_LINK in out
        assert _v2_title(out, "code-change") == "code-change 无效"
        assert not any(_v2_norm(p).endswith("plugins/code-change/manifest.json") for p in reads)


def test_v2_16b_lock_link_not_read(tmp_path):
    with make_env(tmp_path) as env:
        with _v2_links_at("plugins/code-change/lock.json"), read_spy() as reads:
            code, out, err = run(["verify", "code-change"], env.repo)
        _v2_clean(out, err)
        assert code == 1 and _V2_LINK in out
        assert _v2_title(out, "code-change") == "code-change 无效"
        assert not any(_v2_norm(p).endswith("plugins/code-change/lock.json") for p in reads)


def test_v2_16c_resource_link_not_read(tmp_path):
    with make_env(tmp_path) as env:
        with _v2_links_at("plugins/code-change/README.md"), read_spy() as reads:
            code, out, err = run(["verify", "code-change"], env.repo)
        _v2_clean(out, err)
        assert code == 1 and _V2_LINK in out
        assert _v2_title(out, "code-change") == "code-change 无效"
        assert not any(_v2_norm(p).endswith("plugins/code-change/README.md") for p in reads)


def test_v2_16d_battery_file_link_no_battery_call(tmp_path):
    with make_env(tmp_path) as env:
        add_extra_question(env)
        with _v2_links_at("plugins/decisions/questions/zz-extra.json"), \
                mock.patch.object(decisions, "verify_battery_lock",
                                  wraps=decisions.verify_battery_lock) as spy, \
                read_spy() as reads:
            code, out, err = run(["verify", "decisions"], env.repo)
        _v2_clean(out, err)
        assert code == 1 and _V2_LINK in out
        spy.assert_not_called()
        assert not any(_v2_norm(p).endswith("plugins/decisions/questions/zz-extra.json") for p in reads)


def test_v2_16e_battery_extra_dir_is_link_class_no_battery_call(tmp_path):
    with make_env(tmp_path) as env:
        (env.plugin("decisions") / "questions" / "zz-extra.json").mkdir()
        with mock.patch.object(decisions, "verify_battery_lock",
                               wraps=decisions.verify_battery_lock) as spy:
            code, out, err = run(["verify", "decisions"], env.repo)
        _v2_clean(out, err)
        assert code == 1 and _V2_LINK in out and "zz-extra.json" in out
        spy.assert_not_called()


def test_v2_16f_verify_title_resource_inconsistent(tmp_path):
    with make_env(tmp_path) as env:
        code, out, err = run(["verify", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 0 and _v2_title(out, "docs-change") == "docs-change 一致"
        readme = env.plugin("docs-change") / "README.md"
        readme.write_bytes(readme.read_bytes() + b"x")
        code, out, err = run(["verify", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 1
        title = _v2_title(out, "docs-change")
        assert "不一致" in title and "一致" not in title.replace("不一致", "")


# 17：授予路径上其他插件 manifest 的读取失败也要报告，不静默跳过

def test_v2_17_grant_path_read_failure_reported(tmp_path):
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["network-decisions"]}})
        with _v2_fail_reads("plugins/docs-change/manifest.json", PermissionError("denied")):
            code, out, err = run(["enable", "python-checks", "--allow-permission", "read-candidate"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        assert "docs-change" in out and "无效" in out
        impact = _impact_lines(out)
        assert impact and all("docs-change" not in line for line in impact), impact


# 18：argparse 自身的错误退出 2，不冒堆栈

def test_v2_18_argparse_errors_exit_2_no_traceback(tmp_path):
    with make_env(tmp_path) as env:
        for argv in (["show"], ["enable", "docs-change", "--bogus"], ["verify", "a", "b"]):
            code, out, err = run(argv, env.repo)
            _v2_clean(out, err)
            assert code == 2, argv


# ---------------------------------------------------------------------------
# 规划端补测（kit-plugins a002 复审：F1–F6 与变异 M19；attempt-002 判 REVISE，预算用完，由规划端补齐）
# ---------------------------------------------------------------------------

def test_v2_20_show_prints_problem_lines(tmp_path):
    # F1：show 的问题行以“问题：”开头，正常路径也输出（合同第二节）
    with make_env(tmp_path) as env:
        with _v2_fail_reads("plugins/code-change/README.md", PermissionError(13, "denied")):
            code, out, err = run(["show", "code-change"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        problems = [line for line in out.splitlines() if line.startswith("问题：")]
        assert any("资源读取失败" in line for line in problems), out


def test_v2_21_list_reason_names_the_link(tmp_path):
    # F2：清单路径是链接时，list 的原因含“无效：链接”，锁列仍是“无效”（裁定表第 3 行、第二节）
    with make_env(tmp_path) as env:
        manifest = env.plugin("docs-change") / "manifest.json"
        manifest.unlink()
        target = tmp_path / "docs_change_manifest_target"
        target.mkdir()
        assert make_dir_link(manifest, target)
        code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        row = _v2_row(out, "docs-change")
        assert _V2_LINK in row and "BLOCKED" in row, row
        code, out, err = run(["list", "--json"], env.repo)
        _v2_clean(out, err)
        values = list(_v2_strings(json.loads(out)))
        assert any(_V2_LINK in value for value in values), values
        assert _V2_LINK not in values, values  # 不出现恰为“无效：链接”的值


def test_v2_22_root_link_in_json(tmp_path):
    # F3：plugins 根是链接时，list --json 与 verify --json 都含“无效：链接 plugins”（裁定表第 1 行）
    with make_env(tmp_path) as env:
        real = tmp_path / "real_plugins"
        shutil.move(str(env.plugins), str(real))
        assert make_dir_link(env.plugins, real)
        for argv, expected in ((["list", "--json"], 0), (["verify", "--json"], 1)):
            code, out, err = run(argv, env.repo)
            _v2_clean(out, err)
            assert code == expected, argv
            assert any("无效：链接 plugins" in value for value in _v2_strings(json.loads(out))), (argv, out)


def test_v2_23_show_lock_info_when_manifest_invalid(tmp_path):
    # F4：manifest 没通过核对时，show 仍输出锁信息、“状态 <锁列值>”与问题行（第二节、第十四节）
    with make_env(tmp_path) as env:
        path = env.plugin("docs-change") / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["plugin_id"] = "docs-changed"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        lock = json.loads((env.plugin("docs-change") / "lock.json").read_text(encoding="utf-8"))
        code, out, err = run(["show", "docs-change"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        lines = out.splitlines()
        assert "generation" in out and str(lock["lock_sha256"]) in out, out
        assert any(line.startswith("状态 无效") for line in lines), out
        assert any(line.startswith("问题：") for line in lines), out


def test_v2_24_permission_check_failure_is_not_ready(tmp_path):
    # F5：权限核对抛 ValueError 时按不满足处理（BLOCKED），不放行
    with make_env(tmp_path) as env:
        env.write_config({"plugins": {"allowed_permissions": ["read-candidate", "network-decisions"]}})

        def boom(*args, **kwargs):
            raise ValueError("权限核对失败（替身）")

        with mock.patch.object(plugins, "check_permission_intersection", boom):
            code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        row = _v2_row(out, "code-change")
        assert "BLOCKED" in row and "READY" not in row, row


def test_v2_25_per_plugin_errors_are_collected(tmp_path):
    # M19：核对中抛出的 OSError 记为该插件“无效”，不冒堆栈、不拖垮其他插件（第十六节）。
    # Python 3.10 的 Path.is_file() 遇到 EACCES 会抛 PermissionError，这条路径真实存在。
    with make_env(tmp_path) as env:
        target = _v2_norm(env.plugin("docs-change") / "manifest.json")
        real_is_file = pathlib.Path.is_file

        def is_file(self, *args, **kwargs):
            if _v2_norm(self) == target:
                raise PermissionError(13, "拒绝访问（替身）", str(self))
            return real_is_file(self, *args, **kwargs)

        with mock.patch.object(pathlib.Path, "is_file", is_file):
            code, out, err = run(["verify"], env.repo)
            _v2_clean(out, err)
            assert code == 1
            assert "无效" in _v2_title(out, "docs-change")
            assert _v2_title(out, "code-change").split()[1:] == ["一致"]
            code, out, err = run(["list"], env.repo)
        _v2_clean(out, err)
        assert code == 0
        assert "BLOCKED" in _v2_row(out, "docs-change")


def test_v2_26_null_manifest_and_non_object_lock(tmp_path):
    # F6：清单内容是 JSON null、锁不是对象时，原因写具体情况（裁定表第 4、6 行），锁列“无效”
    with make_env(tmp_path) as env:
        (env.plugin("docs-change") / "manifest.json").write_text("null", encoding="utf-8")
        (env.plugin("code-change") / "lock.json").write_text("[]", encoding="utf-8")
        code, out, err = run(["verify"], env.repo)
        _v2_clean(out, err)
        assert code == 1
        assert "None" not in out, out
        assert "无效" in _v2_title(out, "docs-change")
        assert "无效" in _v2_title(out, "code-change")
