import unittest

from src.merged import score_response, unit_of


def item(kind="短题", zero_rule="整份清零", each=1, parts=None, nq=2, ns=3, nk=1):
    return {"id": "X-001-零基础", "kind": kind, "zero_rule": zero_rule, "parts": parts,
            "knowledge_errors": [f"错误{i}" for i in range(1, nk + 1)],
            "gate_questions": [{"id": f"q{i}"} for i in range(1, nq + 1)],
            "recommended_steps": [{"id": f"s{i}"} for i in range(1, ns + 1)],
            "points": {"gate_each": each, "gate_total": each * nq, "step_each": each, "step_total": each * ns}}


def parsed(gate, steps, which=()):
    return {"gate": [{"question_id": k, "answered": v} for k, v in gate.items()],
            "steps": [{"step_id": k, "done": v} for k, v in steps.items()],
            "knowledge_error": {"found": bool(which), "which": list(which)}}


class MergedScoreTests(unittest.TestCase):
    def test_pass_no_zeroing(self):
        r = score_response(item(each=2), parsed({"q1": 1, "q2": 0}, {"s1": 1, "s2": 1, "s3": 0}), 1)
        self.assertEqual((r["gate_raw"], r["gate_score"], r["gate_max"]), (2, 2, 4))
        self.assertEqual((r["step_raw"], r["step_score"], r["step_max"]), (4, 4, 6))
        self.assertIsNone(r["zeroed_parts"])

    def test_short_whole_zero(self):
        r = score_response(item(), parsed({"q1": 1, "q2": 1}, {"s1": 1, "s2": 1, "s3": 1}, ["错误1"]), 0)
        self.assertEqual((r["gate_raw"], r["gate_score"], r["step_raw"], r["step_score"]), (2, 0, 3, 0))
        self.assertEqual(r["zeroed_parts"], "all")

    def test_problem_long_whole_zero(self):
        it = item(kind="做题类", each=2, nk=3)
        r = score_response(it, parsed({"q1": 1, "q2": 1}, {"s1": 1, "s2": 0, "s3": 1}, ["错误3"]), 0)
        self.assertEqual((r["gate_raw"], r["gate_score"], r["gate_max"]), (4, 0, 4))
        self.assertEqual((r["step_raw"], r["step_score"]), (4, 0))

    def _concept(self):
        parts = {"gates": {"q1": 1, "q2": 1, "q3": 2, "q4": 3},
                 "steps": {"s1": 1, "s2": 2, "s3": 3, "s4": None},
                 "knowledge_errors": [1, 2, 3]}
        return item(kind="概念理解类", zero_rule="只清讲错的那一部分", each=2, parts=parts, nq=4, ns=4, nk=3)

    def test_concept_zero_one_part_null_step_kept(self):
        all1 = parsed({f"q{i}": 1 for i in range(1, 5)}, {f"s{i}": 1 for i in range(1, 5)}, ["错误1"])
        r = score_response(self._concept(), all1, 0)
        # 第 1 部分：q1、q2、s1 清零；s4（null）不受影响
        self.assertEqual((r["gate_raw"], r["gate_score"], r["gate_max"]), (8, 4, 8))
        self.assertEqual((r["step_raw"], r["step_score"]), (8, 6))
        self.assertEqual(r["zeroed_parts"], [1])

    def test_concept_two_parts(self):
        all1 = parsed({f"q{i}": 1 for i in range(1, 5)}, {f"s{i}": 1 for i in range(1, 5)}, ["错误1", " 错误3 "])
        r = score_response(self._concept(), all1, 0)
        self.assertEqual(r["gate_score"], 2)          # 只剩第 2 部分的 q3
        self.assertEqual(r["step_score"], 4)          # 剩 s2（第 2 部分）和 s4（null）
        self.assertEqual(r["zeroed_parts"], [1, 3])

    def test_concept_which_must_match(self):
        bad = parsed({f"q{i}": 1 for i in range(1, 5)}, {f"s{i}": 1 for i in range(1, 5)}, ["清单里没有的"])
        with self.assertRaises(ValueError):
            score_response(self._concept(), bad, 0)

    def test_failed_scores_zero_full_denominator(self):
        r = score_response(item(kind="做题类", each=2, nq=8, ns=7), None, None, failed=True)
        self.assertEqual((r["gate_score"], r["gate_max"], r["step_score"], r["step_max"], r["failed"]), (0, 16, 0, 14, 1))

    def test_ids_must_match(self):
        with self.assertRaises(ValueError):
            score_response(item(), parsed({"q1": 1}, {"s1": 1, "s2": 1, "s3": 1}), 1)

    def test_unit(self):
        self.assertEqual(unit_of("ECON-T01-零基础"), "ECON-T01")
        self.assertEqual(unit_of("COMP-001-有前置"), "COMP-001")


if __name__ == "__main__":
    unittest.main()
