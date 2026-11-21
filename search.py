"""BM25 baseline and rule-based furniture search. No labels are read."""

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re

from attributes import extract_attributes
from data.make_label_sheet import read_rows
from data.make_labels import check, counts_for
from query import CATEGORIES, infer_category, parse_query


DATA = Path(__file__).resolve().parent / "data"
ALIASES = {"desks": "desk", "tables": "table", "chairs": "chair", "sofas": "sofa",
           "couch": "sofa", "couches": "sofa", "dressers": "dresser", "nightstands": "nightstand"}
STOP = {"a", "an", "the", "and", "with", "of", "for", "to", "is", "in"}


def tokenize(text):
    return [ALIASES.get(w, w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


class BM25:
    def __init__(self, documents):
        self.postings = defaultdict(list)
        self.lengths = []
        for index, document in enumerate(documents):
            terms = Counter(tokenize(document))
            self.lengths.append(sum(terms.values()))
            for term, frequency in terms.items():
                self.postings[term].append((index, frequency))
        self.average = sum(self.lengths) / len(self.lengths) if self.lengths else 0

    def scores(self, query):
        scores = defaultdict(float)
        if not self.average:
            return scores
        for term in sorted(set(tokenize(query))):
            postings = self.postings.get(term, [])
            idf = math.log(1 + (len(self.lengths) - len(postings) + 0.5) / (len(postings) + 0.5))
            for index, frequency in postings:
                denominator = frequency + 1.2 * (0.25 + 0.75 * self.lengths[index] / self.average)
                scores[index] += idf * frequency * 2.2 / denominator
        return scores


class SearchEngine:
    def __init__(self, rows):
        self.rows = []
        seen = set()
        for source in rows:
            if not isinstance(source, dict):
                raise ValueError("Each listing must be an object.")
            row = dict(source)
            for key in ("title", "description", "features"):
                row[key] = "" if row.get(key) is None else row[key]
                if not isinstance(row[key], str):
                    raise ValueError(f"{key} must be plain text.")
            row["parent_asin"] = row.get("parent_asin") or row.get("url")
            if not isinstance(row["parent_asin"], str) or not row["parent_asin"] or not row["title"].strip() or row["parent_asin"] in seen:
                raise ValueError("Each listing needs a unique parent_asin or URL and a nonempty title.")
            seen.add(row["parent_asin"])
            if not isinstance(row.get("category"), str) or row["category"] not in CATEGORIES:
                row["category"] = infer_category(row["title"])
            self.rows.append(row)
        self.index = BM25(" ".join(r[k] for k in ("title", "features", "description")) for r in self.rows)
        self.attributes = {}

    def search(self, query, limit=10, mode="rules"):
        if mode not in ("bm25", "rules") or limit < 1 or not query.strip():
            raise ValueError("Use a nonempty query, a positive limit, and mode bm25 or rules.")
        parsed = parse_query(query) if mode == "rules" else None
        results = []
        scores = self.index.scores(query)
        candidates = scores if parsed else sorted(scores, key=lambda i: (-scores[i], self.rows[i]["parent_asin"]))[:limit]
        for index in candidates:
            score = scores[index]
            row = self.rows[index]
            if parsed and row["category"] and not counts_for({**row, "also_counts_as": ""}, parsed["category"]):
                continue
            if index not in self.attributes:
                self.attributes[index] = extract_attributes(row)
            attrs, evidence = self.attributes[index]
            unknown, pref_violated, pref_unknown = [], [], []
            if parsed:
                violated, unknown = check(parsed["hard_constraints"], attrs)
                if violated:
                    continue
                if not row["category"]:
                    unknown.append("category")
                pref_violated, pref_unknown = check(parsed["preferences"], attrs)
            results.append({"parent_asin": row["parent_asin"], "title": row["title"],
                            "url": row.get("url"),
                            "category": row["category"], "bm25_score": score,
                            "status": "not_checked" if not parsed else "needs_review" if unknown else "confirmed",
                            "unconfirmed": unknown, "unmet_preferences": pref_violated,
                            "unconfirmed_preferences": pref_unknown, "attributes": attrs, "evidence": evidence})
        results.sort(key=lambda r: (bool(r["unconfirmed"]),
                                   len(r["unmet_preferences"]) + len(r["unconfirmed_preferences"]),
                                   -r["bm25_score"], r["parent_asin"]))
        return {"query": query, "mode": mode, "parsed": parsed, "total_matches": len(results) if parsed else len(scores),
                "candidate_count": len(self.rows), "results": results[:limit]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--input", type=Path, default=DATA / "furniture.csv.gz",
                        help="CSV/CSV.gz corpus or JSONL listings containing title, description and URL.")
    parser.add_argument("--mode", choices=("bm25", "rules"), default="rules")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--split", choices=("development", "evaluation"),
                        help="Restrict candidates before indexing; does not read annotation labels.")
    parser.add_argument("--json", action="store_true", help="Print parsed conditions, results and evidence as JSON.")
    args = parser.parse_args()
    try:
        if args.limit < 1 or not args.query.strip():
            raise ValueError("Enter a nonempty query and a positive limit.")
        if args.mode == "rules":
            parse_query(args.query)
        if args.input.suffix.lower() == ".jsonl":
            with args.input.open(encoding="utf-8-sig") as f:
                rows = [json.loads(line) for line in f if line.strip()]
            if any(not isinstance(row, dict) for row in rows):
                raise ValueError("Each JSONL line must contain a listing object.")
        else:
            rows = read_rows(str(args.input))
        if args.split:
            ids = {r["parent_asin"] for r in read_rows(str(DATA / "benchmark_ids.csv")) if r["split"] == args.split}
            rows = [r for r in rows if r.get("parent_asin") in ids]
            if not rows:
                raise ValueError("No benchmark IDs from the selected split are present in this input.")
        result = SearchEngine(rows).search(args.query, args.limit, args.mode)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
        return
    if result["parsed"]:
        for warning in result["parsed"]["warnings"]:
            print("Warning:", warning)
        print("Parsed conditions:", json.dumps(result["parsed"]["hard_constraints"]))
        print("Preferences:", json.dumps(result["parsed"]["preferences"]))
    print(f"{result['total_matches']} matches from {result['candidate_count']} candidate listings")
    for rank, row in enumerate(result["results"], 1):
        attrs = row["attributes"]
        print(f"\n{rank}. {row['title']} [{row['parent_asin']}] ({row['status']})")
        if row["url"]:
            print("   URL:", row["url"])
        print(f"   Price: {attrs['price']}; W/D/H (in): {attrs['width']}/{attrs['depth']}/{attrs['height']}")
        print("   Materials:", json.dumps(attrs["materials"], ensure_ascii=True))
        if row["unconfirmed"]:
            print("   Needs review:", ", ".join(row["unconfirmed"]))
        if row["unmet_preferences"] or row["unconfirmed_preferences"]:
            print("   Preferences not confirmed:", ", ".join(row["unmet_preferences"] + row["unconfirmed_preferences"]))
        if result["parsed"]:
            fields = {c["field"] for c in result["parsed"]["hard_constraints"] + result["parsed"]["preferences"]}
            for field in sorted(fields):
                print(f"   {field}: {row['evidence'].get(field, 'No explicit evidence found')}")


if __name__ == "__main__":
    main()
