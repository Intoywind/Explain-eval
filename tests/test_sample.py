import unittest

from src.judge import stratified_sample
from src.run import UsageError


def pool(n_per_course):
    out, cid = [], 1
    for c, n in n_per_course.items():
        for _ in range(n):
            out.append({"call_id": cid, "course": c})
            cid += 1
    return out


class StratifiedSampleTests(unittest.TestCase):
    def test_even_split_and_fixed_seed(self):
        p = pool({"COMP2711": 90, "ECON1221": 90, "IEDA1280": 90})
        a = stratified_sample(p, 30, 20261111)
        b = stratified_sample(list(reversed(p)), 30, 20261111)   # 输入顺序不影响结果
        self.assertEqual([r["call_id"] for r in a], [r["call_id"] for r in b])
        self.assertEqual({c: sum(r["course"] == c for r in a) for c in ("COMP2711", "ECON1221", "IEDA1280")},
                         {"COMP2711": 10, "ECON1221": 10, "IEDA1280": 10})
        self.assertEqual(len({r["call_id"] for r in a}), 30)
        c = stratified_sample(p, 30, 1)
        self.assertNotEqual([r["call_id"] for r in a], [r["call_id"] for r in c])

    def test_remainder_and_too_small(self):
        p = pool({"A": 5, "B": 5, "C": 5})
        r = stratified_sample(p, 4, 0)
        self.assertEqual([sum(x["course"] == c for x in r) for c in "ABC"], [2, 1, 1])
        with self.assertRaises(UsageError):
            stratified_sample(pool({"A": 1, "B": 5}), 4, 0)


if __name__ == "__main__":
    unittest.main()
