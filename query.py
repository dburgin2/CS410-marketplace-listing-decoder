"""Parse a small, explicit English query grammar; unknown words stay keywords."""

import math
import re

from attributes import AXES, NUMBER, UNIT, inches


CATEGORIES = {"nightstands": r"nightstands?|bedside\s+tables?",
              "desks": r"desks?", "tables": r"tables?", "chairs": r"chairs?",
              "sofas": r"sofas?|couch(?:es)?|love\s*seats?", "dressers": r"dressers?"}
OPERATORS = {"no more than": "le", "at most": "le", "no wider than": "le", "no taller than": "le",
             "no deeper than": "le", "no less than": "ge", "at least": "ge",
             "less than": "lt", "under": "lt", "below": "lt", "more than": "gt",
             "over": "gt", "above": "gt", "wider than": "gt", "taller than": "gt"}
OP = "|".join(sorted(OPERATORS, key=len, reverse=True))
AXIS = r"width|wide|depth|deep|height|high|tall"
NUMERIC = re.compile(
    rf'(?<![\w.])(?:(?P<before>{AXIS}|price)\s+)?(?:(?P<op>{OP})\s+|between\s+)?'
    rf'(?P<dollar>\$)?(?P<first>{NUMBER})'
    rf'(?:\s*(?:to|and|-)\s*(?P<dollar2>\$)?(?P<second>{NUMBER}))?'
    rf'\s*(?P<unit>{UNIT}|dollars?|usd)?(?:\s*(?P<after>{AXIS})\b)?', re.I)
STOP = {"a", "an", "the", "and", "with", "of", "for", "that", "is", "are", "has", "whose",
        "includes", "include", "overall", "i", "want", "find", "me", "please"}


def infer_category(text):
    found = [category for category, pattern in CATEGORIES.items() if re.search(rf"\b(?:{pattern})\b", text, re.I)]
    if "nightstands" in found and "tables" in found:
        found.remove("tables")
    return found[0] if len(found) == 1 else None


def parse_query(text):
    if not text.strip():
        raise ValueError("Enter a query.")
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text.lower()).replace("\u2013", "-")
    if re.search(r"-\s*\$|\$\s*-|(?:^|\s)-\s*\d", text):
        raise ValueError("Negative values are not supported. Write ranges using 'to'.")
    if re.search(r"\b(or|not|without|except|excluding)\b|\bnon[- ]|\b[a-z]+-free\b", text):
        raise ValueError("OR and negative conditions are not supported; use positive requirements joined by AND.")
    parts = re.split(r"\bpreferably\b", text, maxsplit=1)
    category = infer_category(parts[0])
    if not category:
        raise ValueError("Specify one category: desk, table, chair, sofa, dresser or nightstand.")
    groups, keywords = [], []
    for part in parts:
        conditions = []
        leftover = list(part)
        previous_dimension_op = None
        for m in NUMERIC.finditer(part):
            unit = m["unit"] or ""
            axis = m["before"] or m["after"]
            op_text = m["op"] or ""
            if not axis:
                axis = "width" if "wider" in op_text else "height" if "taller" in op_text else "depth" if "deeper" in op_text else None
            is_price = bool(m["dollar"] or m["dollar2"] or unit in ("dollar", "dollars", "usd") or axis == "price")
            if is_price:
                if axis not in (None, "price") or (unit and unit not in ("dollar", "dollars", "usd")):
                    raise ValueError("Do not mix currency with dimension units.")
                field = "price"
            elif axis and unit:
                field = AXES[axis]
            else:
                raise ValueError("Dimensions need an axis and a unit; prices need $ or 'dollars'.")
            value = float(m["first"]) if is_price else inches(m["first"], unit)
            if not math.isfinite(value):
                raise ValueError("Use finite numeric values.")
            operator = OPERATORS.get(op_text, previous_dimension_op if not is_price else None) or "eq"
            if m["second"]:
                end = float(m["second"]) if is_price else inches(m["second"], unit)
                if not math.isfinite(end) or end < value or op_text:
                    raise ValueError("Use an increasing range such as '50 to 80 inches wide'.")
                value, operator = [value, end], "between"
            conditions.append({"field": field, "operator": operator, "value": value})
            previous_dimension_op = operator if not is_price and operator != "between" else None
            leftover[m.start():m.end()] = " " * (m.end() - m.start())

        rules = [(r"\bsolid[- ]wood(?:en)?(?:\s+top)?\b", "solid_top", True),
                 (r"\bengineered[- ]wood(?:\s+top)?\b", "top_engineered" if category != "dressers" else "general_engineered", True),
                 (r"\b(?:wood|wooden)\s+frame\b", "frame_wood", True),
                 (r"\bmetal\s+frame\b", "frame_metal", True),
                 (r"\bmetal\s+(?:base|legs?)\b", "base_metal", True),
                 (r"\bglass(?:\s+top)?\b", "top_glass", True),
                 (r"\b(?:wood|wooden)(?:\s+top)?\b", "top_wood", True),
                 (r"\bfabric(?:[- ]upholstered)?\b", "fabric", True),
                 (r"\breclin(?:ing|er)\b", "reclining", True),
                 (r"\blove\s*seats?\b", "loveseat", True),
                 (r"\boffice\s+chairs?\b", "office_chair", True),
                 (r"\bdining\s+chairs?\b", "dining_chair", True),
                 (r"\b(?:side|end)\s+tables?\b", "table_type", "side"),
                 (r"\bcoffee\s+tables?\b", "table_type", "coffee"),
                 (r"\bconsole\s+tables?\b", "table_type", "console"),
                 (r"\bdining\s+tables?\b", "table_type", "dining"),
                 (r"\bnew\b", "condition", "new"), (r"\bused\b", "condition", "used")]
        remaining = "".join(leftover)
        for pattern, field, value in rules:
            if re.search(pattern, remaining):
                conditions.append({"field": field, "operator": "eq", "value": value})
                remaining = re.sub(pattern, " ", remaining)
        for pattern in CATEGORIES.values():
            remaining = re.sub(rf"\b(?:{pattern})\b", " ", remaining)
        if re.search(r"\b(?:under|over|above|below|between|less|more|least|most|no|max|min|maximum|minimum|around|approximately)\b", remaining):
            raise ValueError("A comparison could not be parsed. Use an explicit value, axis and unit.")
        keywords.extend(w for w in re.findall(r"[a-z]+", remaining) if w not in STOP)
        groups.append(conditions)
    return {"category": category, "hard_constraints": groups[0],
            "preferences": groups[1] if len(groups) > 1 else [],
            "warnings": ["Keyword-only terms, not verified as constraints: " + ", ".join(dict.fromkeys(keywords))] if keywords else []}
