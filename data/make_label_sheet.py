import csv
import gzip
import json
import re
import sys

csv.field_size_limit(sys.maxsize)

FILL = ["price", "width_in", "depth_in", "height_in",
        "top_material", "frame_material", "base_material", "upholstery_material", "general_material",
        "table_type", "solid_wood_top", "fabric_upholstery", "reclining", "loveseat",
        "office_chair", "dining_chair", "also_counts_as"]


def read_rows(path):
    """Read a CSV or CSV.gz into a list of dicts."""
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def evidence(details, pattern):
    """Return the raw detail fields whose names match the pattern, as JSON text."""
    picked = {k: v for k, v in details.items() if re.search(pattern, k, re.I) and "package" not in k.lower()}
    return json.dumps(picked, ensure_ascii=False) if picked else ""


def main():
    """Write item_facts.csv: one row per benchmark listing with source text and blank columns to fill in."""
    corpus = {r["parent_asin"]: r for r in read_rows("furniture.csv.gz")}
    rows = []
    for b in read_rows("benchmark_ids.csv"):
        src = corpus[b["parent_asin"]]
        details = json.loads(src["details"] or "{}")
        row = {"parent_asin": b["parent_asin"], "category": b["category"], "split": b["split"],
               "title": src["title"],
               "source_dimensions": evidence(details, r"dimension|width|height|depth|length"),
               "source_materials": evidence(details, r"material")}
        row.update({c: "" for c in FILL})
        row["price"] = src["price"]
        row.update({"features": src["features"], "description": src["description"]})
        rows.append(row)
    with open("item_facts.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to item_facts.csv", file=sys.stderr)


if __name__ == "__main__":
    main()
