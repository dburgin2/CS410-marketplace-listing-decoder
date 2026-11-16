import argparse
import csv
import gzip
import http.client
import json
import sys
import time
import urllib.request

URL = ("https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/"
       "raw/meta_categories/meta_Home_and_Kitchen.jsonl")
COLUMNS = ["parent_asin", "category", "title", "store", "category_path", "price",
           "average_rating", "rating_number", "features", "description", "details", "image_url"]


def iter_lines(src, retries=10):
    if not src.startswith(("http://", "https://")):
        with (gzip.open if src.endswith(".gz") else open)(src, "rb") as f:
            yield from f
        return
    offset, failures = 0, 0
    while True:
        req = urllib.request.Request(src, headers={"Range": f"bytes={offset}-"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                total = int((resp.headers.get("Content-Range") or "/0").split("/")[-1] or 0)
                for line in resp:
                    if not line.endswith(b"\n") and offset + len(line) < total:
                        raise ConnectionError("partial line")
                    offset += len(line)
                    yield line
            return
        except (OSError, http.client.HTTPException) as exc:
            failures += 1
            if failures > retries:
                raise
            print(f"connection dropped ({exc}); resuming at byte {offset:,}", file=sys.stderr)
            time.sleep(min(60, 2 ** failures))


def load_index(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {row["parent_asin"]: row["category"] for row in csv.DictReader(f)}


def join(value, sep):

    return sep.join(str(v).strip() for v in value if v) if isinstance(value, list) else str(value or "").strip()


def first_image(images):

    for img in images or []:
        if isinstance(img, dict) and (url := img.get("large") or img.get("hi_res") or img.get("thumb")):
            return url
    return ""


def to_row(r, category):

    details = r.get("details") or {}
    return {
        "parent_asin": r["parent_asin"],
        "category": category,
        "title": (r.get("title") or "").strip(),
        "store": (r.get("store") or "").strip(),
        "category_path": " > ".join(r.get("categories") or []),
        "price": r.get("price"),
        "average_rating": r.get("average_rating"),
        "rating_number": r.get("rating_number"),
        "features": join(r.get("features"), " | "),
        "description": join(r.get("description"), " "),
        "details": details if isinstance(details, str) else json.dumps(details, ensure_ascii=False),
        "image_url": first_image(r.get("images")),
    }


def main():
    """Stream the source metadata and write the raw records listed in the corpus index."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="corpus_index.csv")
    ap.add_argument("--input", default=URL)
    ap.add_argument("--out", default="furniture.csv")
    args = ap.parse_args()

    index = load_index(args.index)
    found = {}
    for line in iter_lines(args.input):
        if b'"Furniture"' not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        asin = r.get("parent_asin")
        if asin in index and asin not in found:
            found[asin] = to_row(r, index[asin])
            if len(found) == len(index):
                break

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(found[a] for a in index if a in found)
    missing = [a for a in index if a not in found]
    print(f"wrote {len(found):,} of {len(index):,} records to {args.out}; missing {len(missing)}", file=sys.stderr)


if __name__ == "__main__":
    main()
