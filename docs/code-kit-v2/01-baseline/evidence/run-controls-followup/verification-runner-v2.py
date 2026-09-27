"""One-shot controlled verification; run with -B and a fresh -X pycache_prefix.

Usage: python -B -X pycache_prefix=<fresh path> <runner.py> <repo> <output-root>
Uses the current interpreter (install verification-requirements.txt in a venv).
The output root must be new, inside the ignored .agent/baseline directory.
"""
import sys
sys.dont_write_bytecode = True
import concurrent.futures
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess

repo = Path(sys.argv[1]).resolve(strict=True)
output = Path(sys.argv[2]).resolve()
if not output.is_relative_to(repo / ".agent" / "baseline"):
    raise SystemExit("output must be inside .agent/baseline")
output.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(repo / "tests"))
import legacy_harness as H

commands = {
    "dispatch": ["tests/test_dispatch.py"],
    "protocols": ["tests/test_protocols.py"],
    "fixtures": ["tests/test_codekit01_fixtures.py", "-v"],
    "baseline": ["tests/test_baseline_tool.py"],
    "gates": ["tests/test_legacy_gates.py"],
    "lifecycle": ["tests/test_legacy_lifecycle.py"],
    "cli": ["tests/test_legacy_cli.py"],
    "events": ["tests/test_legacy_events.py"],
    "legacy-check": ["tests/codekit01_legacy.py", "--check"],
    "stub-regen": ["tests/codekit01_legacy.py", "--check-stub-regen"],
}
if len(sys.argv) > 3:
    commands = {name: commands[name] for name in sys.argv[3:]}
for args in commands.values():
    if not (repo / args[0]).is_file():
        raise SystemExit("missing test: " + args[0])

def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

write_json(output / "packages.json", {
    name: importlib.metadata.version(name) for name in
    ("attrs", "jsonschema", "jsonschema-specifications", "referencing", "rpds-py", "typing-extensions")
})

def run(label, args):
    controls = output / "controls" / label
    controls.mkdir(parents=True)
    agent = controls / "empty-pi"
    agent.mkdir()
    pyc = controls / "empty-pyc"
    pyc.mkdir()
    git_config = controls / "empty-gitconfig"
    git_config.write_bytes(b"")
    env, report = H.isolated_env([sys.executable, str(repo / "tests/stub_pi.py")], agent,
                                  git_global_config=git_config, allowed_roots=[repo])
    env["PYTHONPYCACHEPREFIX"] = str(pyc)
    H.assert_isolated(env, allowed_roots=[repo])
    capture_id = "bl-01followup-" + label + "-20260926"
    argv = [sys.executable, "-B", "-X", "pycache_prefix=" + str(pyc),
            "scripts/codekit/baseline.py", "capture", "--out-root", str(output / "captures"),
            "--capture-id", capture_id, "--timeout", "1800", "--", sys.executable] + args
    control = {"label": label, "capture_id": capture_id, "test_argv": ["<PYTHON>"] + args,
               "env_removed_count": len(report["removed_env_names"]), "path_filter": report["path"],
               "which_after": report["which_after"], "pyc_entries_before": len(list(pyc.rglob("*"))),
               "pi_entries_before": len(list(agent.rglob("*"))), "pyc_redirected": True,
               "dont_write_bytecode": True, "empty_git_global_config": True,
               "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with (controls / "capture.stdout").open("wb") as stdout, (controls / "capture.stderr").open("wb") as stderr:
        result = subprocess.run(argv, cwd=repo, env=env, stdin=subprocess.DEVNULL,
                                stdout=stdout, stderr=stderr, timeout=2100)
    record_path = output / "captures" / capture_id / "capture.json"
    capture = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else {}
    control.update({"capture_returncode": result.returncode,
                    "test_returncode": capture.get("run", {}).get("returncode"),
                    "baseline_consistent": capture.get("comparison", {}).get("baseline_consistent"),
                    "pyc_entries_after": len(list(pyc.rglob("*"))),
                    "pi_entries_after": len(list(agent.rglob("*")))})
    write_json(controls / "controls.json", control)
    print(json.dumps({"label": label, "capture_returncode": result.returncode}), flush=True)
    return control

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    futures = [pool.submit(run, label, args) for label, args in commands.items()]
    results = [future.result() for future in futures]
write_json(output / "controls-summary.json", results)
raise SystemExit(any(row["capture_returncode"] != 0 or row["test_returncode"] != 0
                     or row["baseline_consistent"] is not True for row in results))
