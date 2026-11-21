"""Conservative attribute extraction from the supplied listing fields."""

import json
import math
import re

from data.make_label_sheet import FILL
from data.make_labels import facts


NUMBER = r"(?:\d+(?:\.\d+)?|\.\d+)"
UNIT = r'(?:inches|inch|in\b|cm\b|centimeters?|centimetres?|mm\b|millimeters?|feet|foot|ft\b|["\u2033\u2032\x27])'
AXES = {"w": "width", "width": "width", "wide": "width",
        "d": "depth", "depth": "depth", "deep": "depth",
        "h": "height", "height": "height", "high": "height", "tall": "height"}


def inches(value, unit):
    unit = unit.lower()
    factor = 1 / 25.4 if unit.startswith("mm") or unit.startswith("millimeter") else (
        1 / 2.54 if unit.startswith("cm") or unit.startswith("centimet") else (
            12 if unit in ("ft", "feet", "foot", "'", "\u2032") else 1))
    value = float(value) * factor
    if not math.isfinite(value) or value < 0:
        raise ValueError("Measurements must be finite and nonnegative.")
    return round(value, 6)


def extract_attributes(row):
    item = dict.fromkeys(FILL, "")
    evidence = {}
    snippets = [s.strip() for key in ("title", "features", "description")
                for s in re.split(r"[;\n|]+|(?<=[.!?])\s+", row.get(key, "")) if s.strip()]
    try:
        price = float(row.get("price", ""))
        if math.isfinite(price) and price >= 0 and not isinstance(row.get("price"), bool):
            item["price"] = str(price)
            evidence["price"] = "price: " + str(row["price"])
    except (TypeError, ValueError):
        pass
    try:
        raw = row.get("details") or {}
        details = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        details = {}
    if not isinstance(details, dict):
        details = {}
    details = {k.lower().strip(): str(v) for k, v in details.items()
               if isinstance(k, str) and isinstance(v, (str, int, float))}
    if not item["price"]:
        prices = [(float(m[1].replace(",", "")), s) for s in snippets
                  if not re.search(r"\b(shipping|delivery|deposit|monthly|coupon|save|discount|off)\b|-\s*\$", s, re.I)
                  for m in re.finditer(r"\$\s*(\d[\d,]*(?:\.\d+)?)", s)]
        if prices:
            values = {v for v, _ in prices}
            item["price"] = str(next(iter(values))) if len(values) == 1 and all(math.isfinite(v) for v in values) else "?"
            evidence["price"] = " | ".join(dict.fromkeys(s for _, s in prices))

    measurements = {axis: [] for axis in ("width", "depth", "height")}
    dimension_text = [(f"{k}: {v}", v) for k, v in details.items()
                      if k in ("product dimensions", "assembled dimensions", "item dimensions l x w x h")]
    dimension_text.extend((s, s) for s in snippets
                          if not re.search(r"\b(package|packaging|shipping|seat|arm|interior)\b", s, re.I))
    # shortcut: only explicitly labeled axes; add unlabeled layouts after human review.
    for source, text in dimension_text:
        if re.search(rf"{NUMBER}\s*[-\u2013]\s*{NUMBER}|-\s*{NUMBER}", text):
            continue
        for m in re.finditer(rf'({NUMBER})\s*({UNIT})\s*(width|wide|depth|deep|height|high|tall|[wdh])\b', text, re.I):
            measurements[AXES[m[3].lower()]].append((inches(m[1], m[2]), source))
        for m in re.finditer(rf'\b(width|depth|height)\s*[:=]?\s*({NUMBER})\s*({UNIT})', text, re.I):
            measurements[AXES[m[1].lower()]].append((inches(m[2], m[3]), source))
    for key, text in details.items():
        for axis in measurements:
            if key in ("item " + axis, "assembled " + axis, "product " + axis, "overall " + axis):
                m = re.fullmatch(rf'\s*({NUMBER})\s*({UNIT})\s*', text, re.I)
                if m:
                    measurements[axis].append((inches(m[1], m[2]), f"{key}: {text}"))
    for axis, candidates in measurements.items():
        values = {value for value, _ in candidates}
        if values:
            item[axis + "_in"] = str(next(iter(values))) if len(values) == 1 and min(values) > 0 else "?"
            evidence[axis] = " | ".join(dict.fromkeys(source for _, source in candidates))

    material_keys = {
        "top_material": ("top material type", "top material"),
        "frame_material": ("frame material",), "base_material": ("base material",),
        "upholstery_material": ("upholstery fabric type", "upholstery material", "seat material type"),
        "general_material": ("material", "material type"),
    }
    for field, keys in material_keys.items():
        entries = [(k, details[k]) for k in keys if details.get(k)]
        if entries:
            value = "; ".join(v for _, v in entries)
            item[field] = "?" if re.search(r"\b(not|no|without|unknown|unspecified|n/a)\b", value, re.I) else value
            evidence[field] = " | ".join(f"{k}: {v}" for k, v in entries)

    material = r"solid[- ]wood|engineered[- ]wood|particleboard|mdf|wooden|wood|metal|steel|iron|aluminum|glass|polyester|linen|fabric|leather"
    for field, part in {"top_material": "top|tabletop|desktop", "frame_material": "frame",
                        "base_material": "base|legs?", "upholstery_material": "upholstery|cover"}.items():
        if item[field]:
            continue
        matches = []
        for snippet in snippets:
            if re.search(r"\b(not|no|without)\b|\bnon-", snippet, re.I):
                continue
            for m in re.finditer(rf'\b({material})\s+(?:{part})\b|\b(?:{part})\s+(?:is |made of |made from )?({material})\b', snippet, re.I):
                matches.append(((m[1] or m[2]).replace("-", " "), snippet))
        if matches:
            item[field] = "; ".join(dict.fromkeys(v for v, _ in matches))
            evidence[field] = " | ".join(dict.fromkeys(s for _, s in matches))

    title = row.get("title", "")
    design = details.get("table design", "")
    types = {kind for kind, pattern in {"side": r"side|end|bedside", "coffee": "coffee",
                                       "console": "console", "dining": "dining"}.items()
             if re.search(rf"\b(?:{pattern})\s+table\b", design or title, re.I)}
    if len(types) == 1:
        item["table_type"] = types.pop()
        evidence["table_type"] = design or title
    if row.get("category") == "nightstands":
        item["table_type"] = "side"
        evidence["table_type"] = "category: nightstands"
    for field, pattern in {"office_chair": r"office\s+chair", "dining_chair": r"dining\s+chair",
                           "loveseat": r"love\s*seat", "reclining": r"reclin(?:ing|er)"}.items():
        if re.search(rf"\b(?:{pattern})\b", title, re.I) and not re.search(r"\b(?:not|non|no)\b", title, re.I):
            item[field] = "yes"
            evidence[field] = title
    upholstery = item["upholstery_material"]
    if upholstery not in ("", "?"):
        if re.search(r"fabric|polyester|cotton|linen|velvet|microfiber", upholstery, re.I):
            item["fabric_upholstery"] = "yes"
        elif re.search(r"leather|vinyl", upholstery, re.I):
            item["fabric_upholstery"] = "no"

    attributes = facts(item)
    if attributes["general_engineered"] is False and item["general_material"] in ("", "?"):
        attributes["general_engineered"] = None
    condition = details.get("condition", "").lower()
    if not condition:
        found = {m[1].lower() for s in snippets for m in re.finditer(r"\bcondition\s*:\s*(new|used)\b", s, re.I)}
        condition = found.pop() if len(found) == 1 else ""
    attributes["condition"] = condition if condition in ("new", "used") else None
    if attributes["condition"]:
        evidence["condition"] = "condition: " + condition
    for field, part in {"top_wood": "top_material", "top_glass": "top_material",
                        "top_engineered": "top_material", "solid_top": "top_material",
                        "frame_wood": "frame_material", "frame_metal": "frame_material",
                        "base_metal": "base_material", "fabric": "upholstery_material"}.items():
        if part in evidence:
            evidence[field] = evidence[part]
    evidence["general_engineered"] = " | ".join(evidence[k] for k in material_keys if k in evidence)
    attributes["materials"] = {k: v for k, v in item.items() if k in material_keys and v not in ("", "?")}
    return attributes, evidence
