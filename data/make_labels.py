import csv
import json
import re
import sys

ENGINEERED = r"engineered|manufactured|mdf|fiberboard|fibreboard|particle|chipboard"
WOOD = ENGINEERED + r"|wood|pine|oak|poplar|acacia|walnut|birch|maple|teak|bamboo|mango|rubberwood|veneer"
METAL = r"metal|steel|iron|alumin|brass|copper"
NUMERIC = {"price": "price", "width": "width_in", "depth": "depth_in", "height": "height_in"}
OPS = {"lt": lambda x, v: x < v, "le": lambda x, v: x <= v, "gt": lambda x, v: x > v,
       "ge": lambda x, v: x >= v, "between": lambda x, v: v[0] <= x <= v[1], "eq": lambda x, v: x == v}
MATERIAL_COLS = ["top_material", "frame_material", "base_material", "upholstery_material", "general_material"]


def read_csv(path):
    """Read a CSV into a list of dicts with stripped values."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def number(text):
    """Return a float, or None for blank or '?'."""
    return float(text) if text not in ("", "?") else None


def has(text, pattern):
    """Return True/False if the material text does or doesn't match, None if it's blank or '?'."""
    if text in ("", "?"):
        return None
    return re.search(pattern, text, re.I) is not None


def engineered(text):
    """Engineered wood: yes if named, unknown if only unspecified wood, no otherwise."""
    if text in ("", "?"):
        return None
    if re.search(ENGINEERED, text, re.I):
        return True
    if re.search(WOOD, text, re.I) and not re.search(r"solid", text, re.I):
        return None
    return False


def flag(text):
    """Turn yes/no/blank into True/False/None."""
    return {"yes": True, "no": False}.get(text.lower())


def solid_top(item):
    """Use the solid_wood_top answer if given, otherwise rule it out from an engineered, veneer or non-wood top."""
    answer, top = flag(item["solid_wood_top"]), item["top_material"]
    if answer is not None or top in ("", "?"):
        return answer
    if re.search(ENGINEERED + r"|veneer", top, re.I) or not re.search(WOOD, top, re.I):
        return False
    return True if re.search(r"solid", top, re.I) else None


def facts(item):
    """Derive every value a query can ask about from one filled-in row."""
    top, frame, base = item["top_material"], item["frame_material"], item["base_material"]
    every = "; ".join(item[c] for c in MATERIAL_COLS if item[c] not in ("", "?"))
    return {
        "price": number(item["price"]), "width": number(item["width_in"]),
        "depth": number(item["depth_in"]), "height": number(item["height_in"]),
        "table_type": item["table_type"].lower() or None,
        "top_wood": has(top, WOOD), "top_glass": has(top, "glass"), "top_engineered": engineered(top),
        "frame_wood": has(frame, WOOD), "frame_metal": has(frame, METAL), "base_metal": has(base, METAL),
        "general_engineered": engineered(every),
        "solid_top": solid_top(item), "fabric": flag(item["fabric_upholstery"]),
        "reclining": flag(item["reclining"]), "loveseat": flag(item["loveseat"]),
        "office_chair": flag(item["office_chair"]), "dining_chair": flag(item["dining_chair"]),
    }


def counts_for(item, query_category):
    """Return True if the item belongs to the query's category."""
    also = {c.strip().lower() for c in item["also_counts_as"].split(";") if c.strip()}
    if item["category"] == "nightstands":
        also.add("tables")
    return query_category == item["category"] or query_category in also


def check(conditions, f):
    """Split conditions into violated and unconfirmed field names."""
    violated, unknown = [], []
    for c in conditions:
        value = f[c["field"]]
        if value is None:
            unknown.append(c["field"])
        elif not OPS[c["operator"]](value, c["value"]):
            violated.append(c["field"])
    return violated, unknown


def grade(query, item):
    """Apply the 0-3 rubric to one query/item pair and return (grade, reason)."""
    if not counts_for(item, query["category"]):
        return 0, "wrong category"
    f = facts(item)
    if f["table_type"] is None and item["category"] == "nightstands":
        f["table_type"] = "side"
    violated, unknown = check(json.loads(query["hard_constraints_json"]), f)
    if violated:
        return 0, "violates " + ", ".join(violated)
    if unknown:
        return 1, "unconfirmed " + ", ".join(unknown)
    pref_violated, pref_unknown = check(json.loads(query["preferences_json"] or "[]"), f)
    if pref_violated or pref_unknown:
        return 2, "requirements confirmed; preference not fully met"
    return 3, "requirements and preferences confirmed"


def attribute_rows(item):
    """Turn one filled-in row into attribute label rows."""
    rows = []
    for attr in ("price", "width_in", "depth_in", "height_in"):
        raw = item[attr]
        status = "known" if raw not in ("", "?") else ("ambiguous" if raw == "?" else "missing")
        rows.append((attr, raw if status == "known" else "", status))
    parts = {c.replace("_material", ""): item[c] for c in MATERIAL_COLS if item[c] not in ("", "?")}
    unsure = any(item[c] == "?" for c in MATERIAL_COLS)
    status = "ambiguous" if unsure and not parts else ("known" if parts else "missing")
    rows.append(("material", json.dumps(parts) if parts else "", status))
    return [{"parent_asin": item["parent_asin"], "category": item["category"], "attribute": a,
             "value": v, "status": s, "split": item["split"]} for a, v, s in rows]


def write_csv(path, rows):
    """Write a list of dicts to CSV."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    """Build attribute_labels.csv and relevance_labels.csv from item_facts.csv and queries.csv."""
    items = read_csv(sys.argv[1] if len(sys.argv) > 1 else "item_facts.csv")
    queries = read_csv(sys.argv[2] if len(sys.argv) > 2 else "queries.csv")
    write_csv("attribute_labels.csv", [row for item in items for row in attribute_rows(item)])
    relevance = []
    for q in queries:
        for item in items:
            g, reason = grade(q, item)
            relevance.append({"query_id": q["query_id"], "parent_asin": item["parent_asin"],
                              "relevance": g, "reason": reason, "split": q["split"]})
    write_csv("relevance_labels.csv", relevance)
    print(f"wrote {len(items) * 5} attribute labels and {len(relevance)} relevance labels", file=sys.stderr)


if __name__ == "__main__":
    main()
