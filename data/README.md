# data

Furniture listings plus the labels we're testing against. Everything joins on `parent_asin`.

- `furniture.csv.gz` - 21,408 Amazon furniture listings (desks, tables, chairs, sofas, dressers, nightstands)
- `pd.read_csv("furniture.csv.gz")`
- `corpus_index.csv` - just the ID and category for every listing
- `build_corpus.py` - rebuilds `furniture.csv` from the original Amazon data, if you ever need to
- `queries.csv` - 40 test queries ("desk under $150", "sofa at least 50 inches wide")
- `benchmark_ids.csv` - the 120 listings we label
- `item_facts.csv` - annotation sheet for those 120 listings; price is copied from the source, while size, materials and type still need manual review and entry
- `make_label_sheet.py` - creates `item_facts.csv` only if it does not already exist
- `make_labels.py` - applies our 0-3 grading rules to the hand-recorded facts
- `attribute_labels.csv` - price, width, depth, height and material for the 120 listings
- `relevance_labels.csv` - all 4,800 query/item pairs scored 0-3 by `make_labels.py`; filter by both query and item split before evaluation
- `LABELING.md` - annotation instructions, the 0-3 rubric and the development/evaluation split policy

**How the labels are made:** review and fill in `item_facts.csv` from each listing's source text. `make_labels.py` applies the grading rules in `LABELING.md` to those facts to produce both label files. Successful generation does not mean the annotations are complete.

**Evaluation split:** develop with 15 development queries and 60 development items (900 pairs). Report final retrieval results on 25 evaluation queries and 60 evaluation items (1,500 pairs). Attribute extraction uses the same 60/60 item split. The generated relevance file's `split` is the query split only; join `benchmark_ids.csv` on `parent_asin` and require the item split to match. See [LABELING.md](LABELING.md) for the full policy.

## Running things

The supplied `item_facts.csv` is the sheet to edit. Do not regenerate it before each annotation session. If a new blank sheet is needed, first back up and rename the existing file, then run `python make_label_sheet.py` from `data`. The command refuses to overwrite an existing sheet.

Regenerate the labels after editing `item_facts.csv`:

```
cd data
python make_labels.py
```

Rebuilding the corpus if necessary:

```
cd data
python build_corpus.py
```

`make_labels.py` replaces its derived `attribute_labels.csv` and `relevance_labels.csv` outputs; it does not edit `item_facts.csv`.

Run the regression checks from the repository root:

```
python -m unittest discover -s tests -v
```

No third-party packages are needed for these scripts or checks.

Data from Amazon Reviews 2023 (McAuley Lab). Cite: Hou et al., "Bridging Language and Items for Retrieval and Recommendation," arXiv:2403.03952, 2024.
