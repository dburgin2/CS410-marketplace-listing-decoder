# Furniture listings: corpus and reference labels

Data collection and labeling for the Marketplace Listing Decoder project.

## Files

| File | Contents |
|---|---|
| `corpus_index.csv` | `parent_asin` and `category` for all 21,408 corpus records (desks, tables, chairs, sofas, dressers, nightstands) |
| `build_corpus.py` | Rebuilds `furniture.csv` from the source data using `corpus_index.csv` |
| `furniture.csv` | Original source fields for each record, unparsed (not committed; build it locally) |
| `queries.csv` | 40 natural-language queries with category, split, required constraints and preferences |
| `attribute_labels.csv` | 600 reference attribute labels: price, width, depth, height and material for 120 benchmark records |
| `relevance_labels.csv` | 4,800 graded judgments (0–3): every query against every benchmark record |
| `manifest.json` | Collection rules, sampling seeds, labeling guidelines, relevance rubric and file checksums |

`parent_asin` is the join key across all files. Queries and attribute records are tagged `development` or `evaluation`.

## Build the corpus

```
python build_corpus.py
```

This streams the 11.8 GB Home & Kitchen metadata file from Hugging Face (about 5 minutes) and writes `furniture.csv`. Python standard library only. To use a downloaded copy instead: `python build_corpus.py --input meta_Home_and_Kitchen.jsonl`.

## Label status

Labels were proposed with AI assistance and are pending human review; see `annotation` in `manifest.json`.

## Source

Amazon Reviews 2023, McAuley Lab (Hou et al., *Bridging Language and Items for Retrieval and Recommendation*, 2024). https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023
