"""解析与引句校验、三档记分的单元测试。运行：python -m unittest discover -s tests -v"""

import json
import unittest

from src import judge as judge_mod
from src import providers
from src.judge import fill_user, load_prompt, run_judge
from src.scoring import JudgeFormatError, normalize, parse_judge_output, quote_ok, score

RESPONSE = """## 一、货币需求
货币需求是人们想以现金和活期存款形式持有的钱。
利率升高时，拿着钱就放弃了更多利息，  所以货币需求减少。

## 二、均衡
央行把货币供给定在 600，利率会一直变动，直到想持有的钱等于现有的钱。
解得 i = 5%。"""

ITEM = {
    "id": "T-001",
    "reader_known": {"learned": ["解一元一次方程"], "not_learned": ["货币需求"]},
    "material": "Md/P = 0.5Y - 5000i",
    "request": "讲一下",
    "knowledge_errors": ["均衡利率算错"],
    "gate_questions": [
        {"id": "q1", "text": "问题一", "accept": "a1"},
        {"id": "q2", "text": "问题二", "accept": "a2"},
        {"id": "q3", "text": "问题三", "accept": "a3"},
    ],
    "recommended_steps": [
        {"id": "s1", "text": "步骤一"},
        {"id": "s2", "text": "步骤二"},
        {"id": "s3", "text": "步骤三"},
    ],
}

GOOD = "货币需求是人们想以现金和活期存款形式持有的钱。"
GOOD_WS = "拿着钱就放弃了更多利息， 所以货币需求减少"   # 原文这里是两个空格，压缩后应匹配
GOOD2 = "利率会一直变动，直到想持有的钱等于现有的钱"
BAD = "这句话讲解里根本没有"


def judge_json(gate=None, steps=None, knowledge=False, which=None, kquotes=None, **over):
    gate = gate if gate is not None else [(True, [GOOD]), (True, [GOOD2]), (True, [GOOD_WS])]
    steps = steps if steps is not None else [(True, [GOOD]), (True, [GOOD2]), (True, [GOOD_WS])]
    if which is None:
        which = ["均衡利率算错"] if knowledge else []
    if kquotes is None:
        kquotes = ["解得 i = 5%。"] if knowledge else []
    d = {
        "knowledge_error": {"found": knowledge, "which": which, "quotes": kquotes, "note": ""},
        "incomplete": {"found": False, "missing": [], "note": ""},
        "gate": [{"id": f"q{i + 1}", "answered": a, "quotes": q, "reason": "r"} for i, (a, q) in enumerate(gate)],
        "steps": [{"id": f"s{i + 1}", "done": a, "quotes": q, "reason": "r"} for i, (a, q) in enumerate(steps)],
        "extra_steps": [],
        "gaps": [],
        "redundancy": [],
    }
    d.update(over)
    return json.dumps(d, ensure_ascii=False)


def parse(raw):
    return parse_judge_output(raw, ITEM, RESPONSE)


class QuoteTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize("  a \n\t b  "), "a b")

    def test_whitespace_collapsed(self):
        self.assertTrue(quote_ok(GOOD_WS, normalize(RESPONSE)))
        self.assertTrue(quote_ok("  " + GOOD + "\n", normalize(RESPONSE)))

    def test_bad_and_empty(self):
        self.assertFalse(quote_ok(BAD, normalize(RESPONSE)))
        self.assertFalse(quote_ok("   ", normalize(RESPONSE)))
        self.assertFalse(quote_ok(None, normalize(RESPONSE)))

    def test_ellipsis_splice_rejected(self):
        self.assertFalse(quote_ok("货币需求是……持有的钱", normalize(RESPONSE)))


class ParseTests(unittest.TestCase):
    def test_gate_all_quotes_invalid_goes_to_rejudge_not_downgrade(self):
        p = parse(judge_json(gate=[(True, [BAD]), (True, [GOOD2]), (True, [GOOD])]))
        g1 = p.gate[0]
        self.assertTrue(g1.answered_raw)
        self.assertTrue(g1.quote_invalid)
        self.assertEqual(p.flags()["gate_quote_invalid"], ["q1"])
        self.assertEqual(p.problems, ["gate q1 answered=true 但没有一条引句通过校验"])
        with self.assertRaises(ValueError):   # 不改判成没答上去计分
            score(p)

    def test_one_valid_quote_is_enough(self):
        p = parse(judge_json(gate=[(True, [BAD, GOOD]), (True, [GOOD2]), (True, [GOOD])]))
        self.assertTrue(p.gate[0].answered)
        self.assertFalse(p.gate[0].quote_invalid)
        self.assertEqual(p.flags()["invalid_quotes"]["gate"], 1)

    def test_answered_without_quotes_goes_to_rejudge(self):
        p = parse(judge_json(gate=[(True, []), (True, [GOOD2]), (True, [GOOD])]))
        self.assertTrue(p.gate[0].quote_invalid)
        self.assertTrue(p.problems)

    def test_unanswered_with_no_quotes_is_not_flagged(self):
        p = parse(judge_json(gate=[(False, []), (True, [GOOD2]), (True, [GOOD])]))
        self.assertFalse(p.gate[0].answered)
        self.assertFalse(p.gate[0].quote_invalid)

    def test_step_all_quotes_invalid_goes_to_rejudge(self):
        p = parse(judge_json(steps=[(True, [GOOD]), (True, [BAD]), (True, [GOOD2])]))
        self.assertTrue(p.steps[1].quote_invalid)
        self.assertEqual(p.flags()["step_quote_invalid"], ["s2"])
        self.assertEqual(p.problems, ["steps s2 done=true 但没有一条引句通过校验"])
        with self.assertRaises(ValueError):
            score(p)

    def test_not_done_with_bad_quote_is_fine(self):
        # done=false 时引句可以是“最接近但不够的那句”，抄错了也不影响计分
        p = parse(judge_json(steps=[(True, [GOOD]), (False, [BAD]), (True, [GOOD2])]))
        self.assertEqual(p.problems, [])
        self.assertEqual(score(p).step_num, 2)

    def test_code_fence_stripped(self):
        p = parse("```json\n" + judge_json() + "\n```")
        self.assertEqual(len(p.gate), 3)

    def test_invalid_json(self):
        with self.assertRaises(JudgeFormatError):
            parse("{不是 JSON")

    def test_missing_top_field(self):
        d = json.loads(judge_json())
        del d["gaps"]
        with self.assertRaises(JudgeFormatError):
            parse(json.dumps(d, ensure_ascii=False))

    def test_missing_answered(self):
        d = json.loads(judge_json())
        del d["gate"][1]["answered"]
        with self.assertRaises(JudgeFormatError):
            parse(json.dumps(d, ensure_ascii=False))

    def test_gate_ids_mismatch(self):
        d = json.loads(judge_json())
        d["gate"] = d["gate"][:2]
        with self.assertRaises(JudgeFormatError):
            parse(json.dumps(d, ensure_ascii=False))
        d = json.loads(judge_json())
        d["steps"][2]["id"] = "s9"
        with self.assertRaises(JudgeFormatError):
            parse(json.dumps(d, ensure_ascii=False))

    def test_ids_out_of_order_accepted_and_reordered(self):
        d = json.loads(judge_json())
        d["gate"] = list(reversed(d["gate"]))
        p = parse(json.dumps(d, ensure_ascii=False))
        self.assertEqual([g.id for g in p.gate], ["q1", "q2", "q3"])

    def test_bad_gap_enum(self):
        raw = judge_json(gaps=[{"quote": GOOD, "subtype": "别的类型", "severity": "只是不顺", "why": "w"}])
        with self.assertRaises(JudgeFormatError):
            parse(raw)

    def test_gap_quote_validity_and_blocking_count(self):
        raw = judge_json(gaps=[
            {"quote": GOOD, "subtype": "术语未先定义", "severity": "读者没法往下读", "why": "w"},
            {"quote": BAD, "subtype": "前提未交代", "severity": "读者没法往下读", "why": "w"},
            {"quote": GOOD2, "subtype": "切换处漏连接", "severity": "只是不顺", "why": "w"},
        ])
        p = parse(raw)
        self.assertEqual([g["quote_valid"] for g in p.gaps], [True, False, True])
        self.assertEqual(score(p).n_gaps_blocking, 1)


class KnowledgeEvidenceTests(unittest.TestCase):
    """知识清零必须同时：found=true；which 非空且每条对得上清单；至少一条有效引句。否则进重判，不清零。"""

    def test_found_with_empty_which_and_quotes_does_not_zero(self):
        # GPT 复现的情形：found=true，which、quotes 都空
        p = parse(judge_json(knowledge=True, which=[], kquotes=[]))
        self.assertIn("knowledge_error.found=true 但 which 为空", p.problems)
        self.assertIn("knowledge_error.found=true 但没有一条引句通过校验", p.problems)
        with self.assertRaises(ValueError):
            score(p)

    def test_found_with_unlisted_which_does_not_zero(self):
        p = parse(judge_json(knowledge=True, which=["利率单位写错"]))
        self.assertEqual(len(p.problems), 1)
        self.assertIn("对不上知识错误清单", p.problems[0])
        with self.assertRaises(ValueError):
            score(p)

    def test_found_with_one_listed_one_unlisted_which_does_not_zero(self):
        p = parse(judge_json(knowledge=True, which=["均衡利率算错", "别的错"]))
        self.assertTrue(p.problems)

    def test_found_with_listed_which_but_invalid_quote_does_not_zero(self):
        p = parse(judge_json(knowledge=True, kquotes=[BAD]))
        self.assertEqual(p.problems, ["knowledge_error.found=true 但没有一条引句通过校验"])

    def test_which_whitespace_tolerated(self):
        p = parse(judge_json(knowledge=True, which=["  均衡利率算错 "]))
        self.assertEqual(p.problems, [])
        self.assertFalse(score(p).knowledge_pass)

    def test_found_valid_zeroes(self):
        p = parse(judge_json(knowledge=True))
        self.assertEqual(p.problems, [])
        sc = score(p)
        self.assertFalse(sc.knowledge_pass)
        self.assertEqual((sc.gate_num, sc.step_num), (0, 0))


class RejudgeTests(unittest.TestCase):
    """run_judge：证据不合格就重判同一份回答，最多 2 次；仍不合格整份 needs_review。"""

    def setUp(self):
        self._orig = judge_mod.providers.call
        self.calls = 0

    def tearDown(self):
        judge_mod.providers.call = self._orig

    def _feed(self, outputs):
        def fake(model_cfg, config, system, user, log=print):
            text = outputs[min(self.calls, len(outputs) - 1)]
            self.calls += 1
            return providers.CallOutcome(ok=True, text=text, finish_reason="stop", input_tokens=10,
                                         output_tokens=5, params_sent={}, attempts=1, latency_s=0.0)
        judge_mod.providers.call = fake

    def run_(self):
        return run_judge({}, {}, "sys", "user", ITEM, RESPONSE, log=lambda m: None)

    def test_empty_knowledge_claim_rejudged_then_needs_review(self):
        self._feed([judge_json(knowledge=True, which=[], kquotes=[])])
        res = self.run_()
        self.assertEqual(res.status, "needs_review")
        self.assertEqual(self.calls, 3)                      # 首判 + 重判 2 次
        self.assertEqual(res.n_rejudge, 2)
        self.assertIn("which 为空", res.error)
        self.assertEqual(res.input_tokens, 30)

    def test_invalid_gate_quote_rejudged_then_ok(self):
        self._feed([judge_json(gate=[(True, [BAD]), (True, [GOOD2]), (True, [GOOD])]), judge_json()])
        res = self.run_()
        self.assertEqual(res.status, "ok")
        self.assertEqual(self.calls, 2)
        self.assertEqual(res.history[0]["kind"], "evidence")
        self.assertEqual(score(res.parsed).gate_num, 3)    # 用的是重判那次的结果

    def test_unlisted_which_rejudged_then_valid_knowledge_error(self):
        self._feed([judge_json(knowledge=True, which=["清单外的错"]), judge_json(knowledge=True)])
        res = self.run_()
        self.assertEqual(res.status, "ok")
        self.assertFalse(score(res.parsed).knowledge_pass)

    def test_format_error_then_evidence_problem_ends_needs_review(self):
        self._feed(["不是 JSON", "也不是", judge_json(steps=[(True, [BAD]), (True, [GOOD]), (True, [GOOD2])])])
        res = self.run_()
        self.assertEqual(res.status, "needs_review")
        self.assertEqual([h["kind"] for h in res.history], ["format", "format"])

    def test_always_bad_format_is_error(self):
        self._feed(["不是 JSON"])
        res = self.run_()
        self.assertEqual(res.status, "error")
        self.assertEqual(self.calls, 3)


class ScoreTests(unittest.TestCase):
    def test_knowledge_fail_zeroes_numerators(self):
        p = parse(judge_json(knowledge=True))
        sc = score(p)
        self.assertFalse(sc.knowledge_pass)
        self.assertEqual((sc.gate_num, sc.gate_den), (0, 3))
        self.assertEqual((sc.step_num, sc.step_den), (0, 3))
        self.assertFalse(sc.gate_all)
        # 原始判断照常保留
        self.assertTrue(all(g.answered for g in p.gate))
        self.assertTrue(all(s.done for s in p.steps))

    def test_two_of_three_answered(self):
        p = parse(judge_json(gate=[(True, [GOOD]), (False, []), (True, [GOOD2])]))
        sc = score(p)
        self.assertEqual((sc.gate_num, sc.gate_den), (2, 3))
        self.assertFalse(sc.gate_all)

    def test_steps_independent_of_gate(self):
        p = parse(judge_json(gate=[(False, []), (True, [GOOD]), (True, [GOOD2])],
                             steps=[(True, [GOOD]), (True, [GOOD2]), (False, [])]))
        sc = score(p)
        self.assertEqual((sc.gate_num, sc.gate_den), (2, 3))
        self.assertEqual((sc.step_num, sc.step_den), (2, 3))

    def test_all_answered(self):
        sc = score(parse(judge_json()))
        self.assertTrue(sc.knowledge_pass)
        self.assertEqual((sc.gate_num, sc.gate_den), (3, 3))
        self.assertTrue(sc.gate_all)

    def test_incomplete_does_not_fail_knowledge(self):
        raw = judge_json(incomplete={"found": True, "missing": ["第 (b) 问"], "note": ""})
        sc = score(parse(raw))
        self.assertTrue(sc.knowledge_pass)
        self.assertTrue(sc.incomplete)
        self.assertEqual(sc.gate_num, 3)


class PromptTests(unittest.TestCase):
    def test_placeholders_filled_once(self):
        pr = load_prompt(__import__("pathlib").Path("prompts/judge_v1.md"))
        tricky = "讲解里写了 {{material}} 这几个字"
        u = fill_user(pr.user_template, ITEM, tricky)
        self.assertIn(tricky, u)
        self.assertNotIn("{{reader_learned}}", u)
        self.assertIn("- id: q2\n  问题：问题二\n  accept：a2", u)
        self.assertNotIn("{{", u.replace(tricky, ""))


if __name__ == "__main__":
    unittest.main()
