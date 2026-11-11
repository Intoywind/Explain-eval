import copy
import json
import tempfile
import unittest
from pathlib import Path

from src.schema import validate_file, validate_item

ROOT = Path(__file__).resolve().parents[1]
MERGED = ROOT / "data" / "items_merged.jsonl"


class MergedSchemaTests(unittest.TestCase):
    def test_merged_file_passes(self):
        items, errors = validate_file(MERGED)
        self.assertEqual(errors, [])
        self.assertEqual(len(items), 60)
        self.assertEqual(sum(it["tier"] == "长题" for it in items), 30)

    def _first(self, tier):
        return next(json.loads(l) for l in MERGED.read_text(encoding="utf-8").splitlines() if json.loads(l)["tier"] == tier)

    def test_merged_split_must_follow_tier(self):
        it = self._first("长题")
        it["split"] = "dev"
        self.assertTrue(any("split" in e for e in validate_item(it, "mixed")))

    def test_points_total_checked(self):
        it = self._first("长题")
        it["points"]["gate_total"] += 2
        self.assertTrue(any("gate_total" in e for e in validate_item(it, "mixed")))

    def test_concept_parts_checked(self):
        it = next(json.loads(l) for l in MERGED.read_text(encoding="utf-8").splitlines() if json.loads(l)["kind"] == "概念理解类")
        bad = copy.deepcopy(it)
        bad["parts"]["knowledge_errors"] = bad["parts"]["knowledge_errors"][:-1]
        self.assertTrue(any("parts.knowledge_errors" in e for e in validate_item(bad, "mixed")))
        bad = copy.deepcopy(it)
        bad["parts"]["gates"][next(iter(bad["parts"]["gates"]))] = None
        self.assertTrue(any("null" in e for e in validate_item(bad, "mixed")))

    def test_unknown_field_still_rejected(self):
        it = self._first("短题")
        it["oops"] = 1
        self.assertTrue(any("未定义字段" in e for e in validate_item(it, "mixed")))

    def test_old_files_unchanged(self):
        for f in ("items.jsonl", "items_long_dev.jsonl", "examples.jsonl", "holdout.jsonl"):
            self.assertEqual(validate_file(ROOT / "data" / f)[1], [], f)


if __name__ == "__main__":
    unittest.main()
