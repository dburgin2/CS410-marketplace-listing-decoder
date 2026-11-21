import csv
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from attributes import extract_attributes, inches
from query import parse_query
from search import BM25, SearchEngine


ROOT = Path(__file__).resolve().parents[1]


def listing(identifier, price="99", dimensions='24"D x 40"W x 30"H', **extra):
    return {"parent_asin": identifier, "title": "Wood desk", "category": "desks", "price": price,
            "details": json.dumps({"Product Dimensions": dimensions, "Top Material Type": "Solid Wood"}), **extra}


class AttributeTests(unittest.TestCase):
    def test_labeled_axes_and_units(self):
        attrs, evidence = extract_attributes(listing("a", dimensions='30"H x 120 cm W x 2 ft D'))
        self.assertAlmostEqual(attrs["width"], 120 / 2.54, places=5)
        self.assertEqual((attrs["depth"], attrs["height"]), (24, 30))
        self.assertTrue(attrs["solid_top"])
        self.assertIn("120 cm", evidence["width"])
        self.assertEqual(inches("254", "mm"), 10)

    def test_raw_web_text_needs_no_csv_columns(self):
        row = {"title": "Office desk", "description": "Price: $149; 48 inches wide; depth: 60 cm; height: 75 cm; solid wood top; metal frame; Condition: used."}
        attrs, evidence = extract_attributes(row)
        self.assertEqual((attrs["price"], attrs["width"], attrs["condition"]), (149, 48, "used"))
        self.assertTrue(attrs["solid_top"])
        self.assertTrue(attrs["frame_metal"])
        self.assertIn("solid wood top", evidence["solid_top"])

    def test_package_and_seat_dimensions_are_not_overall_dimensions(self):
        row = {"details": json.dumps({"Package Dimensions": '10"D x 20"W x 30"H', "Seat Height": "18 inches"}),
               "description": "Package: 50 inches wide; seat: 20 inches high."}
        attrs, _ = extract_attributes(row)
        self.assertIsNone(attrs["width"])
        self.assertIsNone(attrs["height"])

    def test_conflicting_and_unlabeled_dimensions_stay_unknown(self):
        attrs, _ = extract_attributes(listing("a", description="Width: 50 inches"))
        self.assertIsNone(attrs["width"])
        attrs, _ = extract_attributes(listing("a", dimensions="40 x 24 x 30 inches"))
        self.assertIsNone(attrs["width"])

    def test_missing_or_malformed_details_do_not_invent_values(self):
        attrs, _ = extract_attributes({"price": "nan", "details": "{bad json"})
        self.assertIsNone(attrs["price"])
        self.assertIsNone(attrs["width"])
        self.assertIsNone(attrs["top_wood"])
        attrs, _ = extract_attributes({"details": {"Condition": "Unknown"}})
        self.assertIsNone(attrs["condition"])

    def test_ambiguous_prices_and_negative_or_adjustable_sizes(self):
        attrs, _ = extract_attributes({"description": 'Was $200, now $150; -40"W; adjustable 20-30"H'})
        self.assertIsNone(attrs["price"])
        self.assertIsNone(attrs["width"])
        self.assertIsNone(attrs["height"])
        attrs, _ = extract_attributes({"description": "Save $50 off; -$10 discount"})
        self.assertIsNone(attrs["price"])

    def test_negated_materials_are_not_positive_evidence(self):
        attrs, _ = extract_attributes({"description": "Not a solid wood top; no metal frame."})
        self.assertIsNone(attrs["solid_top"])
        self.assertIsNone(attrs["frame_metal"])

    def test_partial_materials_cannot_rule_out_engineered_wood_elsewhere(self):
        attrs, _ = extract_attributes({"details": {"Frame Material": "Steel"}})
        self.assertIsNone(attrs["general_engineered"])


class QueryTests(unittest.TestCase):
    def test_development_queries_match_their_structured_conditions(self):
        with (ROOT / "data/queries.csv").open(newline="", encoding="utf-8") as f:
            queries = [q for q in csv.DictReader(f) if q["split"] == "development"]
        self.assertEqual(len(queries), 15)
        order = lambda c: json.dumps(c, sort_keys=True)
        for q in queries:
            with self.subTest(query=q["query"]):
                parsed = parse_query(q["query"])
                self.assertEqual(parsed["category"], q["category"])
                for field in ("hard_constraints", "preferences"):
                    self.assertEqual(sorted(parsed[field], key=order), sorted(json.loads(q[field + "_json"]), key=order))

    def test_preferences_units_and_inclusive_bounds(self):
        parsed = parse_query("desk no wider than 120 cm and at least 2 ft deep, preferably under $100")
        self.assertEqual(parsed["hard_constraints"], [
            {"field": "width", "operator": "le", "value": inches(120, "cm")},
            {"field": "depth", "operator": "ge", "value": 24}])
        self.assertEqual(parsed["preferences"], [{"field": "price", "operator": "lt", "value": 100}])

    def test_range_and_inherited_comparison(self):
        p = parse_query("sofa 50 to 80 inches wide and at least 20 inches deep and 25 inches high")
        self.assertEqual(p["hard_constraints"][0]["value"], [50, 80])
        self.assertEqual(p["hard_constraints"][-1]["operator"], "ge")
        self.assertEqual(parse_query("couch under $500")["category"], "sofas")

    def test_unsupported_constraints_are_rejected_or_flagged(self):
        for text in ("", "desk or chair", "desk without wood", "desk under 48", "desk under -$10",
                     "desk 80 to 50 inches wide", "desk under 200 euros", "desk under $20 inches wide",
                     "wood-free desk", "desk max $200"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_query(text)
        self.assertIn("red", parse_query("red desk under $100")["warnings"][0])


class SearchTests(unittest.TestCase):
    def test_bm25_frequency_length_and_missing_terms(self):
        scores = BM25(["desk desk", "desk", "chair"]).scores("desk")
        self.assertAlmostEqual(scores[0], 0.5665797174469143)
        self.assertGreater(scores[0], scores[1])
        self.assertNotIn(2, scores)
        self.assertFalse(BM25([]).scores("desk"))
        self.assertFalse(BM25([""]).scores("desk"))

    def test_known_mismatches_removed_unknowns_retained_and_ranked_last(self):
        rows = [listing("good"), listing("wide", dimensions='24"D x 60"W x 30"H'),
                listing("boundary", price="100"), listing("unknown", dimensions="", title="desk " * 10),
                listing("chair", category="chairs")]
        result = SearchEngine(rows).search("desk under $100 and less than 48 inches wide")
        self.assertEqual([r["parent_asin"] for r in result["results"]], ["good", "unknown"])
        self.assertEqual(result["results"][0]["status"], "confirmed")
        self.assertEqual(result["results"][1]["unconfirmed"], ["width"])

    def test_baseline_does_not_apply_conditions(self):
        result = SearchEngine([listing("expensive", price="999")]).search("desk under $100", mode="bm25")
        self.assertEqual(result["total_matches"], 1)
        self.assertEqual(result["results"][0]["status"], "not_checked")

    def test_baseline_only_extracts_attributes_for_displayed_results(self):
        engine = SearchEngine([listing("a"), listing("b"), listing("c")])
        with patch("search.extract_attributes", wraps=extract_attributes) as extract:
            result = engine.search("desk", mode="bm25", limit=1)
            self.assertEqual(result["total_matches"], 3)
            self.assertEqual(len(result["results"]), 1)
            self.assertEqual(extract.call_count, 1)

    def test_preferences_rank_without_filtering(self):
        engine = SearchEngine([listing("expensive", price="150"), listing("cheap", price="50")])
        result = engine.search("desk less than 48 inches wide, preferably under $100")
        self.assertEqual([r["parent_asin"] for r in result["results"]], ["cheap", "expensive"])
        self.assertEqual(result["results"][1]["unmet_preferences"], ["price"])

    def test_raw_listing_order_does_not_change_results(self):
        rows = [json.loads(line) for line in (ROOT / "examples/web_listings.jsonl").read_text().splitlines()]
        query = "desk under $200 and less than 48 inches wide with a solid wood top"
        result = SearchEngine(rows).search(query)
        reverse = SearchEngine(list(reversed(rows))).search(query)
        self.assertEqual([r["parent_asin"] for r in result["results"]], [r["parent_asin"] for r in reverse["results"]])
        self.assertEqual(result["total_matches"], 2)
        self.assertEqual(result["results"][0]["status"], "confirmed")
        self.assertEqual(result["results"][1]["status"], "needs_review")

    def test_unknown_category_is_not_claimed_as_confirmed(self):
        row = {"url": "https://example.com/a", "title": "Home workstation", "description": "Useful as a desk. Price: $99."}
        result = SearchEngine([row]).search("desk under $100")
        self.assertIn("category", result["results"][0]["unconfirmed"])

    def test_invalid_inputs(self):
        for rows in ([{}], [listing("a"), listing("a")], [{"url": "x", "title": []}]):
            with self.assertRaises(ValueError):
                SearchEngine(rows)
        with self.assertRaises(ValueError):
            SearchEngine([]).search("desk", limit=0)

    def test_cli_accepts_raw_web_text_and_outputs_valid_json(self):
        result = subprocess.run([sys.executable, str(ROOT / "search.py"),
                                 "desk under $200 and less than 48 inches wide", "--input",
                                 str(ROOT / "examples/web_listings.jsonl"), "--json"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["candidate_count"], 3)
        self.assertEqual(output["total_matches"], 2)


if __name__ == "__main__":
    unittest.main()
