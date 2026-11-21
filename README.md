# Marketplace Listing Decoder

A small furniture-search prototype with a BM25 baseline and rule-based price,
dimension, material and condition checks. It reads listing text, not manual labels.
Python 3.10 or newer is sufficient; no third-party packages or API keys are needed.

## Run

Run these commands from the repository root:

```sh
python search.py 'desk under $200 and less than 48 inches wide' --limit 5
python search.py 'desk under $200 and less than 48 inches wide' --mode bm25 --limit 5
python search.py 'desk with a metal base under $250' --split development --json
python -m unittest discover -s tests -v
```

Use single quotes around queries containing `$` in PowerShell or a POSIX shell.
The default input is `data/furniture.csv.gz`. `--split` restricts the candidate
products before indexing using `benchmark_ids.csv`; it does not read item facts
or relevance labels. Final evaluation must also select the corresponding query
split as described in [data/LABELING.md](data/LABELING.md).

## Inputs from a website

The search engine accepts unsorted listing objects. CSV is only one input source.
A website collector can pass a list of objects directly to `SearchEngine`, or
write one JSON object per line and use `--input listings.jsonl`:

```json
{"url":"https://example.com/listing/desk","title":"Compact desk","description":"Price: $149; Width: 120 cm; 60 cm deep; 75 cm high; solid wood top; metal frame."}
```

`title` and a unique `url` or `parent_asin` are required. `description` and
`features` must be visible plain text. `price`, `category` and `details` are
optional. Category is inferred from an unambiguous title when absent. Dimensions,
prices and component materials can be extracted from the title and description
without structured columns. Results include the source URL and supporting text.

```sh
python search.py 'desk under $200 and less than 48 inches wide with a solid wood top' --input examples/web_listings.jsonl --json
```

The example file is synthetic; its URLs do not point to real products. This step
does not implement a crawler or connect to a live marketplace. A site-specific
collector must obtain each listing's visible text, URL and any available metadata.
Do not combine several products or navigation text into one listing description.

## Supported rules

- Categories: desks, tables, chairs, sofas/couches/loveseats, dressers and
  nightstands/bedside tables.
- USD prices: `under $200`, `at most 150 dollars`, `between $50 and $100`.
- Explicit width/depth/height: `less than 48 inches wide`, `depth under 24 inches`,
  `at least 120 cm wide`, `no taller than 30 inches`, `50 to 80 inches wide`.
  Inches, cm, mm and feet are normalized to inches. Repeat the unit on each axis.
- Component materials: wood/glass/engineered-wood top, solid wood, metal base,
  wood/metal frame and fabric upholstery. Table types and explicit chair/sofa
  types are also recognized. Bare `wood` means a wooden top in this limited grammar.
- `preferably` separates preferences from requirements. `new` and `used` check
  an explicit condition field or `Condition: new/used` in the text.

Unsupported numeric comparisons, OR and negative requirements produce errors.
Other unparsed words are used as keywords and reported as **keyword-only**;
they are not verified constraints. A `confirmed` result confirms only the parsed
requirements. The parsed requirements and preferences are printed for inspection.

Known hard mismatches are removed. Results with missing or conflicting facts remain
visible as `needs_review`, after confirmed matches. Preferences affect ordering,
but do not remove products. BM25 orders results within those groups. In `bm25`
mode no attribute filters are applied and results are marked `not_checked`.

## Limits and evaluation status

Extraction prefers available structured fields and also reads explicit statements
in listing text. It does not infer axis order from `48 x 24 x 30`, assume package
or seat dimensions are overall product dimensions, or assume that an absent
feature is false. Conflicting measurements remain unknown. Ambiguous product
variants, unlabeled dimensions, implicit material claims and arbitrary English
paraphrases still require manual review. Prices are in USD; currency conversion
is not implemented.

The tests check retrieval logic, development-query parsing and synthetic text
cases. They do not establish real-world extraction accuracy or retrieval quality.
Manual annotations, Precision@5/nDCG@10 evaluation, embeddings and the web UI
remain future work. Do not use the evaluation split to tune extraction rules.

BM25 uses `k1 = 1.2`, `b = 0.75`, and positive IDF
`log(1 + (N - df + 0.5) / (df + 0.5))`; see the
[Apache Lucene reference](https://lucene.apache.org/core/10_2_2/core/org/apache/lucene/search/similarities/BM25Similarity.html).
