"""scripts/codekit/decisions.py 的离线测试：没有网络，没有真实凭据，每个回复都是假传输给的。

覆盖：问题形状、脱敏与“整段不发”、回复校验（键集合、和为 1、argmax、score 均值）、配置与模式判定
（标记文件、插件启用、权限、自定义端点不得收官方凭据）、会话的 fail-open 与时钟预算、记录不存 state 原文、
清单目录与插件锁的绑定。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from codekit import decisions as d  # noqa: E402

QUESTIONS = ROOT / "plugins" / "decisions" / "questions"


def good_transport(p_noul=0.2, choice_index=0, score_level=1, tokens=42):
    """按问题类型给出形状正确的回答；记录每次请求。"""
    calls = []

    def transport(body, headers, timeout, url):
        request = json.loads(body)
        calls.append({"request": request, "headers": headers, "timeout": timeout, "url": url})
        answers = {}
        for name, question in request["questions"].items():
            kind = question["type"]
            if kind == "noul":
                answers[name] = {"type": "noul", "noul": p_noul}
            elif kind == "choice":
                options = list(question["criteria"])
                rest = (1.0 - 0.7) / (len(options) - 1)
                answers[name] = {"type": "choice", "choice": options[choice_index],
                                 "probabilities": {o: (0.7 if i == choice_index else rest) for i, o in enumerate(options)},
                                 "confidence": 0.55}
            else:
                n = len(question["criteria"])
                answers[name] = {"type": "score", "score": float(score_level),
                                 "probabilities": {str(i): (1.0 if i == score_level else 0.0) for i in range(n)},
                                 "confidence": 1.0, "legend": {str(i): "L%d" % i for i in range(n)}}
        return json.dumps({"model": "jev-test", "answers": answers,
                           "usage": {"input_tokens": tokens, "output_tokens": 0}}).encode("utf-8")

    transport.calls = calls
    return transport


def setUpModule():
    # 决策测试不碰真实凭据库：只认环境变量。
    os.environ["CODEKIT_SECRET_STORE"] = "off"


def settings(mode="shadow", **extra):
    config = {"decisions": dict({"mode": mode}, **extra)}
    return d.settings_from_config(config, None, ROOT / "plugins" / "decisions")


def battery(name):
    return d.load_battery(QUESTIONS / (name + ".json"))


class QuestionShape(unittest.TestCase):
    def test_builders_and_limits(self):
        self.assertEqual(d.noul("Is it done?")["type"], "noul")
        self.assertEqual(set(d.noul("Is it done?", "yes", "no")["criteria"]), {"true", "false"})
        self.assertEqual(d.choice("Which?", {"a": "A", "b": None})["criteria"], {"a": "A", "b": None})
        self.assertEqual(len(d.score("How bad?", ["none", "some"])["criteria"]), 2)
        with self.assertRaises(ValueError):
            d.choice("Which?", {"a": "A"})
        with self.assertRaises(ValueError):
            d.choice("Which?", {"o%d" % i: None for i in range(256)})
        with self.assertRaises(ValueError):
            d.score("How bad?", ["one"])
        with self.assertRaises(ValueError):
            d.score("How bad?", ["l%d" % i for i in range(11)])
        with self.assertRaises(ValueError):
            d.check_question("blocked", {"type": "noul", "instructions": "blocked?"})
        with self.assertRaises(ValueError):
            d.check_question("x", {"type": "noul", "instructions": "Is it?", "criteria": {"yes": "y"}})
        with self.assertRaises(ValueError):
            d.check_question("x", {"type": "maybe", "instructions": "Is it?"})
        with self.assertRaises(ValueError):
            d.check_question("x", {"type": "noul", "instructions": "Is it?", "extra": 1})
        self.assertEqual(d.check_question("x", {"type": "noul", "instructions": "Is it?", "label": "标签"}),
                         {"type": "noul", "instructions": "Is it?"})


class Privacy(unittest.TestCase):
    def test_redact_masks_shapes_and_keeps_names(self):
        text = ("GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123 and sk-abcdefghijklmnopqrstuvwxyz "
                "mail a.b@example.com digest 0123456789abcdef0123456789abcdef01234567 call +44 20 7946 0958")
        out = d.redact(text)
        self.assertIn("GITHUB_TOKEN=[secret]", out)
        self.assertNotIn("ghp_", out)
        self.assertIn("[email]", out)
        self.assertIn("[hex]", out)
        self.assertIn("[phone]", out)
        self.assertNotIn("sk-abcdef", out)

    def test_is_sensitive_and_redact_state(self):
        self.assertTrue(d.is_sensitive("here is my api_key: 123"))
        self.assertTrue(d.is_sensitive("AWS_SECRET_ACCESS_KEY=abc"))
        self.assertFalse(d.is_sensitive("pytest -q passed 12 tests"))
        value, changed = d.redact_state({"a": ["x@y.io", {"b": "plain"}], "c": 3})
        self.assertEqual(value, {"a": ["[email]", {"b": "plain"}], "c": 3})
        self.assertEqual(changed, 1)

    def test_long_text_keeps_head_and_tail(self):
        out = d.redact("A" * 5000 + "Z" * 5000, limit=1000)
        self.assertTrue(out.startswith("A") and out.endswith("Z") and "[...]" in out and len(out) < 1100)


class AnswerValidation(unittest.TestCase):
    def test_choice_invariants(self):
        q = d.choice("Which?", {"a": None, "b": None, "c": None})
        ok = {"type": "choice", "choice": "a", "probabilities": {"a": 0.5, "b": 0.3, "c": 0.2}, "confidence": 0.25}
        self.assertEqual(d.check_answer("q", q, ok)["choice"], "a")
        bad = [
            dict(ok, probabilities={"a": 0.5, "b": 0.5}),                        # key set
            dict(ok, probabilities={"a": 0.5, "b": 0.3, "c": 0.3}),              # mass
            dict(ok, choice="b"),                                                # argmax
            dict(ok, choice="zzz"),                                              # not offered
            dict(ok, type="noul"),                                               # wrong type
            dict(ok, confidence=1.5),                                            # range
        ]
        codes = []
        for answer in bad:
            with self.assertRaises(d.DecisionError) as ctx:
                d.check_answer("q", q, answer)
            codes.append(ctx.exception.code)
        self.assertEqual(codes, ["invalid_response", "invalid_response", "invalid_response", "malformed", "malformed", "malformed"])

    def test_score_invariants(self):
        q = d.score("How?", ["none", "some", "much"])
        ok = {"type": "score", "score": 1.43, "probabilities": {"0": 0.0, "1": 0.57, "2": 0.43}, "confidence": 0.35}
        checked = d.check_answer("q", q, ok)
        self.assertTrue(checked["spread_reported"])
        self.assertEqual(checked["levels"], 3)
        with self.assertRaises(d.DecisionError) as ctx:
            d.check_answer("q", q, dict(ok, score=2.4))
        self.assertEqual(ctx.exception.invariant, "score_matches_its_distribution")
        with self.assertRaises(d.DecisionError):
            d.check_answer("q", q, dict(ok, probabilities={"0": 0.0, "1": 0.57, "3": 0.43}))
        bare = d.check_answer("q", q, {"type": "score", "score": 1.0})
        self.assertFalse(bare["spread_reported"])
        self.assertEqual(bare["confidence"], 1.0)

    def test_noul_and_confidence(self):
        q = d.noul("Done?")
        self.assertEqual(d.check_answer("q", q, {"type": "noul", "noul": 0.8})["noul"], 0.8)
        with self.assertRaises(d.DecisionError):
            d.check_answer("q", q, {"type": "noul", "noul": "yes"})
        self.assertAlmostEqual(d.noul_confidence(0.8), 0.6)
        self.assertEqual(d.answer_value({"type": "noul", "noul": 0.25}), ("p=0.25", 0.5))


class Configuration(unittest.TestCase):
    def test_defaults_and_mode(self):
        s = d.settings_from_config({}, None, None)
        self.assertEqual((s.mode, s.reason, s.model, s.api_key_env), ("off", "not_configured", "jev-1.13.0", "TYPESAFE_API_KEY"))
        s = settings("shadow")
        self.assertEqual((s.mode, s.reason, s.active, s.official), ("shadow", "configured", True, True))
        s = settings("on", points=["mutation-equivalence"], timeout_seconds=2, budget_seconds=5, max_state_chars=1000)
        self.assertEqual((s.mode, s.points, s.timeout_seconds, s.budget_seconds, s.max_state_chars),
                         ("on", ["mutation-equivalence"], 2.0, 5.0, 1000))

    def test_invalid_configs(self):
        for bad in ({"mode": "maybe"}, {"mode": "on", "points": ["nope"]}, {"mode": "on", "timeout_seconds": 0},
                    {"mode": "on", "base_url": "http://example.com"}, {"mode": "on", "base_url": "https://u:p@h/"},
                    {"mode": "on", "base_url": "https://h/path"}, {"mode": "on", "api_key_env": "1bad"},
                    {"mode": "on", "unknown": 1}, {"mode": "on", "max_state_chars": 10}, "text"):
            with self.assertRaises(d.DecisionError, msg=repr(bad)) as ctx:
                d.settings_from_config({"decisions": bad}, None, None)
            self.assertEqual(ctx.exception.code, "config")

    def test_custom_endpoint_needs_its_own_env_var(self):
        with self.assertRaises(d.DecisionError):
            d.settings_from_config({"decisions": {"mode": "on", "base_url": "http://127.0.0.1:8099"}}, None, None)
        s = d.settings_from_config({"decisions": {"mode": "on", "base_url": "http://127.0.0.1:8099/",
                                                   "api_key_env": "LOCAL_DECISIONS_KEY"}}, None, None)
        self.assertEqual((s.base_url, s.official), ("http://127.0.0.1:8099", False))

    def test_marker_plugin_and_permission_turn_it_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = Path(tmp)
            s = d.settings_from_config({"decisions": {"mode": "on"}}, agent, ROOT / "plugins" / "decisions")
            self.assertEqual(s.mode, "on")
            (agent / d.OFF_MARKER).write_text("", encoding="utf-8")
            s = d.settings_from_config({"decisions": {"mode": "on"}}, agent, ROOT / "plugins" / "decisions")
            self.assertEqual((s.mode, s.reason, s.marker_present, s.configured_mode), ("off", "marker", True, "on"))
        s = d.settings_from_config({"decisions": {"mode": "on"}, "plugins": {"enabled": ["code-change"]}}, None, None)
        self.assertEqual((s.mode, s.reason), ("off", "plugin_disabled"))
        s = d.settings_from_config({"decisions": {"mode": "on"}, "plugins": {"enabled": ["decisions"],
                                                                             "allowed_permissions": ["read-candidate"]}}, None, None)
        self.assertEqual((s.mode, s.reason), ("off", "permission_missing"))
        s = d.settings_from_config({"decisions": {"mode": "on"}, "plugins": {"enabled": ["decisions"],
                                                                             "allowed_permissions": ["network-decisions"]}},
                                   None, ROOT / "plugins" / "decisions")
        self.assertEqual(s.mode, "on")
        with tempfile.TemporaryDirectory() as tmp:
            s = d.settings_from_config({"decisions": {"mode": "on"}}, None, Path(tmp) / "missing")
            self.assertEqual((s.mode, s.reason), ("off", "plugin_missing"))


class SessionBehaviour(unittest.TestCase):
    def test_answered_and_recorded_without_state_text(self):
        transport = good_transport()
        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp) / "x" / "decisions.jsonl"
            session = d.Session(settings("shadow"), record, transport=transport, environ={"TYPESAFE_API_KEY": "k-1"})
            result = session.ask(battery("report-screen"), {"executor_report": {"text": "SECRETWORD-not-a-secret"}},
                                 {"attempt": "a001"})
            self.assertEqual(result["status"], "answered")
            self.assertEqual(result["answers"]["severity"]["score"], 1.0)
            self.assertEqual(result["usage"], {"input_tokens": 42, "output_tokens": 0})
            self.assertEqual(result["served_model"], "jev-test")
            request = transport.calls[0]
            self.assertEqual(request["headers"]["Authorization"], "Bearer k-1")
            self.assertEqual(request["url"], "https://api.typesafe.ai/v1/systemone")
            self.assertEqual(request["request"]["model"], "jev-1.13.0")
            self.assertEqual(set(request["request"]["questions"]["severity"]), {"type", "instructions", "criteria"})
            line = record.read_text(encoding="utf-8").strip()
            self.assertNotIn("SECRETWORD", line)
            self.assertNotIn("k-1", line)
            stored = json.loads(line)
            self.assertEqual((stored["status"], stored["point"], stored["context"]), ("answered", "report-screen", {"attempt": "a001"}))
            self.assertEqual(len(stored["state_sha256"]), 64)
            self.assertEqual(session.answered, 1)
            self.assertEqual(session.input_tokens, 42)

    def test_fail_open_paths(self):
        b = battery("mutation-equivalence")
        off = d.Session(d.settings_from_config({}, None, None), None, transport=good_transport())
        self.assertEqual((off.ask(b, {})["status"], off.ask(b, {})["reason"]), ("no_opinion", "off:not_configured"))
        self.assertEqual(off.records, [])
        no_key = d.Session(settings("on"), None, transport=good_transport(), environ={})
        self.assertEqual(no_key.ask(b, {"x": 1})["reason"], "no_key")
        sensitive = d.Session(settings("on"), None, transport=good_transport(), environ={"TYPESAFE_API_KEY": "k"})
        self.assertEqual(sensitive.ask(b, {"text": "password: hunter2"})["reason"], "sensitive")
        big = d.Session(settings("on", max_state_chars=500), None, transport=good_transport(), environ={"TYPESAFE_API_KEY": "k"})
        self.assertEqual(big.ask(b, {"text": "x" * 600})["reason"], "state_too_large")
        disabled = d.Session(settings("on", points=["run-health"]), None, transport=good_transport(), environ={"TYPESAFE_API_KEY": "k"})
        self.assertEqual(disabled.ask(b, {"x": 1})["reason"], "point_disabled")

        def broken(body, headers, timeout, url):
            return b"not json"
        malformed = d.Session(settings("on"), None, transport=broken, environ={"TYPESAFE_API_KEY": "k"})
        self.assertEqual(malformed.ask(b, {"x": 1})["reason"], "malformed")

        def contradictory(body, headers, timeout, url):
            request = json.loads(body)
            answers = {name: {"type": "noul", "noul": 1.7} for name in request["questions"]}
            return json.dumps({"answers": answers}).encode("utf-8")
        out_of_range = d.Session(settings("on"), None, transport=contradictory, environ={"TYPESAFE_API_KEY": "k"})
        self.assertEqual(out_of_range.ask(b, {"x": 1})["reason"], "malformed")

        def http_error(body, headers, timeout, url):
            raise d.DecisionError("auth_failed")
        auth = d.Session(settings("on"), None, transport=http_error, environ={"TYPESAFE_API_KEY": "k"})
        self.assertEqual(auth.ask(b, {"x": 1})["reason"], "auth_failed")

    def test_retry_once_then_budget(self):
        attempts = []

        def flaky(body, headers, timeout, url):
            attempts.append(timeout)
            if len(attempts) == 1:
                raise d.DecisionError("rate_limited")
            return good_transport()(body, headers, timeout, url)
        session = d.Session(settings("on", budget_seconds=1.0, timeout_seconds=0.5), None, transport=flaky,
                            environ={"TYPESAFE_API_KEY": "k"})
        self.assertEqual(session.ask(battery("run-health"), {"goal": "g"})["status"], "answered")
        self.assertEqual(len(attempts), 2)
        self.assertLessEqual(attempts[0], 0.5)
        session.spent_seconds = 0.95
        self.assertEqual(session.ask(battery("run-health"), {"goal": "g"})["reason"], "budget")

    def test_custom_endpoint_sends_only_its_own_key(self):
        transport = good_transport()
        s = d.settings_from_config({"decisions": {"mode": "on", "base_url": "http://127.0.0.1:1",
                                                   "api_key_env": "LOCAL_KEY"}}, None, ROOT / "plugins" / "decisions")
        session = d.Session(s, None, transport=transport, environ={"TYPESAFE_API_KEY": "official", "LOCAL_KEY": ""})
        self.assertEqual(session.ask(battery("run-health"), {"goal": "g"})["status"], "answered")
        self.assertNotIn("Authorization", transport.calls[0]["headers"])
        self.assertEqual(transport.calls[0]["url"], "http://127.0.0.1:1/v1/systemone")

    def test_probe_and_describe(self):
        result = d.probe(settings("off"), transport=good_transport(p_noul=0.9), environ={"TYPESAFE_API_KEY": "k"})
        self.assertEqual((result["ok"], result["answer"], result["served_model"]), (True, 0.9, "jev-test"))
        facts = d.describe(settings("shadow"), ROOT / "plugins" / "decisions", environ={})
        self.assertEqual((facts["api_key_set"], facts["mode"], len(facts["batteries"])), (False, "shadow", 3))
        self.assertEqual(facts["sdk_reference"]["api_key_env"], "TYPESAFE_API_KEY")


class Batteries(unittest.TestCase):
    def test_shipped_batteries_match_manifest_and_lock(self):
        loaded = d.load_batteries(QUESTIONS)
        self.assertEqual(set(loaded), set(d.POINTS))
        manifest = json.loads((ROOT / "plugins" / "decisions" / "manifest.json").read_text(encoding="utf-8"))
        by_path = {r["path"]: r["sha256"] for r in manifest["resources"]}
        for battery_ in loaded.values():
            rel = "plugins/decisions/questions/%s.json" % battery_["id"]
            self.assertEqual(by_path[rel], battery_["sha256"], rel)
        self.assertIn("network-decisions", manifest["permissions"])
        from codekit import plugins
        lock = json.loads((ROOT / "plugins" / "decisions" / "lock.json").read_text(encoding="utf-8"))
        plugins.validate_lock(lock, {"decisions": manifest})
        readme = ROOT / "plugins" / "decisions" / "README.md"
        self.assertEqual(by_path["plugins/decisions/README.md"], hashlib.sha256(readme.read_bytes()).hexdigest())

    def test_battery_rejections(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            path.write_text(json.dumps({"id": "x", "version": "1.0.0", "questions": {"q": {"type": "noul", "instructions": "q"}}}),
                            encoding="utf-8")
            with self.assertRaises(d.DecisionError):
                d.load_battery(path)
            path.write_text(json.dumps({"id": "y", "version": "1.0.0", "questions": {"q": {"type": "noul", "instructions": "Done?"}},
                                        "thresholds": {"a": -1}}), encoding="utf-8")
            with self.assertRaises(d.DecisionError):
                d.load_battery(path)
            path.write_text(json.dumps({"id": "y", "version": "1.0.0", "questions": {"q": {"type": "noul", "instructions": "Done?"}}}),
                            encoding="utf-8")
            with self.assertRaises(d.DecisionError):
                d.load_batteries(Path(tmp))  # file name x != id y

    def test_main_check_battery(self):
        self.assertEqual(d.main(["--check-battery", str(QUESTIONS)]), 0)
        self.assertEqual(d.main([]), 2)


class Records(unittest.TestCase):
    def test_read_latest_and_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "decisions.jsonl"
            rows = [{"point": "report-screen", "status": "no_opinion", "reason": "no_key"},
                    {"point": "report-screen", "status": "answered", "usage": {"input_tokens": 100}},
                    {"point": "run-health", "status": "answered", "usage": {"input_tokens": 50}}]
            path.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n", encoding="utf-8")
            records = d.read_records(path)
            self.assertEqual(len(records), 3)
            self.assertEqual(d.latest_by_point(records)["report-screen"]["status"], "answered")
            totals = d.usage_totals(records)
            self.assertEqual((totals["calls"], totals["answered"], totals["input_tokens"], totals["no_opinion_reasons"]),
                             (3, 2, 150, {"no_key": 1}))
            self.assertAlmostEqual(totals["estimated_cost_usd"], 150 * 0.042 / 1_000_000)


if __name__ == "__main__":
    unittest.main()
