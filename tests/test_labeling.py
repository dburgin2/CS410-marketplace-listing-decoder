import csv
import gzip
import json
from collections import Counter
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


DATA = Path(__file__).resolve().parents[1] / "data"
csv.field_size_limit(2**31 - 1)


class LabelSheetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.features = "x" * 140_000
        source = {"parent_asin": "TEST", "title": "Desk", "price": "99.50",
                  "details": json.dumps({"Product Dimensions": '24"D x 48"W x 30"H'}),
                  "features": self.features, "description": ""}
        with gzip.open(self.directory / "furniture.csv.gz", "wt", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(source))
            writer.writeheader()
            writer.writerow(source)
        (self.directory / "benchmark_ids.csv").write_text(
            "parent_asin,category,split\nTEST,desks,development\n", encoding="utf-8")

    def run_sheet(self):
        return subprocess.run([sys.executable, str(DATA / "make_label_sheet.py")],
                              cwd=self.directory, capture_output=True, text=True)

    def test_creates_sheet_with_large_csv_field(self):
        result = self.run_sheet()
        self.assertEqual(result.returncode, 0, result.stderr)
        with (self.directory / "item_facts.csv").open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["features"], self.features)
        self.assertEqual(rows[0]["parent_asin"], "TEST")
        self.assertEqual(rows[0]["price"], "99.50")
        self.assertEqual(rows[0]["width_in"], "")
        self.assertEqual(rows[0]["split"], "development")

    def test_existing_annotations_are_not_overwritten(self):
        path = self.directory / "item_facts.csv"
        original = b"parent_asin,width_in\r\nTEST,48\r\n"
        path.write_bytes(original)
        result = self.run_sheet()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to overwrite item_facts.csv", result.stderr)
        self.assertNotIn("wrote", result.stderr)
        self.assertEqual(path.read_bytes(), original)


class EvaluationSplitTests(unittest.TestCase):
    def test_generated_labels_match_documented_partitions(self):
        with (DATA / "benchmark_ids.csv").open(newline="", encoding="utf-8-sig") as f:
            benchmark = list(csv.DictReader(f))
        item_splits = {r["parent_asin"]: r["split"] for r in benchmark}
        self.assertEqual(len(item_splits), 120)
        self.assertEqual(Counter(item_splits.values()), {"development": 60, "evaluation": 60})
        self.assertEqual(set(Counter((r["split"], r["category"]) for r in benchmark).values()), {10})
        with (DATA / "item_facts.csv").open(newline="", encoding="utf-8-sig") as f:
            facts = list(csv.DictReader(f))
        self.assertEqual(len(facts), 120)
        self.assertEqual({r["parent_asin"]: r["split"] for r in facts}, item_splits)
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(DATA / "make_labels.py"),
                 str(DATA / "item_facts.csv"), str(DATA / "queries.csv")],
                cwd=directory, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with (Path(directory) / "attribute_labels.csv").open(newline="", encoding="utf-8") as f:
                attributes = list(csv.DictReader(f))
            self.assertEqual(Counter(r["split"] for r in attributes),
                             {"development": 300, "evaluation": 300})
            with (Path(directory) / "relevance_labels.csv").open(newline="", encoding="utf-8") as f:
                relevance = list(csv.DictReader(f))
            self.assertEqual(len({(r["query_id"], r["parent_asin"]) for r in relevance}), 4_800)
            partitions = Counter((r["split"], item_splits[r["parent_asin"]]) for r in relevance)
            self.assertEqual(partitions, {("development", "development"): 900,
                                          ("evaluation", "evaluation"): 1_500,
                                          ("development", "evaluation"): 900,
                                          ("evaluation", "development"): 1_500})


if __name__ == "__main__":
    unittest.main()
