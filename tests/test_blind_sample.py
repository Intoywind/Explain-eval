import unittest
from collections import Counter

from src.blind import sample_by_outcome
from src.run import UsageError

GROUPS = ["g1", "g2", "g3", "g4"]
COURSES = ["A", "B", "C"]


def pool():
    rows, cid = [], 1
    for g in GROUPS:
        for c in COURSES:
            for i in range(10):          # 每门课 10 个条目
                for rep in range(3):
                    part = "fail" if (i + rep) % 7 == 0 else "pass"
                    rows.append({"id": cid, "item_id": f"{c}-{i}", "group": g, "course": c, "part": part})
                    cid += 1
    return rows


class OutcomeSampleTests(unittest.TestCase):
    def test_balanced_and_capped(self):
        p = pool()
        a = sample_by_outcome(p, 15, 7)
        self.assertEqual(Counter(r["part"] for r in a), {"fail": 15, "pass": 15})
        for part in ("fail", "pass"):
            sub = [r for r in a if r["part"] == part]
            self.assertLessEqual(max(Counter(r["group"] for r in sub).values()) -
                                 min(Counter(r["group"] for r in sub).values()), 1)
            self.assertEqual(sorted(Counter(r["course"] for r in sub).values()), [5, 5, 5])
        self.assertLessEqual(max(Counter(r["item_id"] for r in a).values()), 3)
        self.assertEqual(len({r["id"] for r in a}), 30)
        b = sample_by_outcome(list(reversed(p)), 15, 7)
        self.assertEqual(sorted(r["id"] for r in a), sorted(r["id"] for r in b))

    def test_not_enough(self):
        p = [{"id": 1, "item_id": "x", "group": "g1", "course": "A", "part": "fail"}]
        with self.assertRaises(UsageError):
            sample_by_outcome(p, 2, 0)


if __name__ == "__main__":
    unittest.main()
