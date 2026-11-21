# How the labels get made

1. Use the existing `item_facts.csv` (one row per benchmark listing). `python make_label_sheet.py` creates a new sheet only when that file is absent; back up and rename an existing sheet before intentionally starting over.
2. Review the source text and fill in the annotation columns by hand (Excel or Google Sheets), then save it back as CSV with the same name. Price is copied from the source; the supplied sheet's other annotation fields are not yet filled in.
3. `python make_labels.py` writes `attribute_labels.csv` and `relevance_labels.csv`

The 120 listings are 20 random picks per category. They're in `benchmark_ids.csv`.

Each query is graded against every one of the 120 listings:

- **0**: wrong category, or breaks a requirement
- **1**: nothing broken, but a requirement can't be confirmed (that fact is blank or `?`)
- **2**: all requirements confirmed, but a "preferably" isn't met or can't be confirmed
- **3**: everything confirmed

## Development and evaluation splits

Keep the existing assignments in `queries.csv` and `benchmark_ids.csv`. The `split` in `item_facts.csv` must match `benchmark_ids.csv` for each `parent_asin`.

| Purpose | Queries | Candidate items | Query/item pairs |
| --- | --- | --- | --- |
| Development and tuning | 15 `development` | 60 `development` | 900 |
| Final retrieval evaluation | 25 `evaluation` | 60 `evaluation` | 1,500 |
| Search demo | User input | All 21,408 corpus items | Not a benchmark score |

- Each item split has 10 items per category. Tune extraction, query parsing, ranking and thresholds using development data only. Freeze the implementation and scoring policy before final evaluation; do not tune against evaluation labels or results.
- For attribute extraction, use the 300 attribute labels from development items for development, and the 300 from evaluation items for final reporting.
- `make_labels.py` still generates all 4,800 query/item pairs. Its relevance `split` column identifies the **query** split only. Join `benchmark_ids.csv` by `parent_asin` to obtain the **item** split. Keep a pair only when both splits equal the split being evaluated. Exclude the 2,400 cross-split pairs from development and final scoring.
- Run both the baseline and improved retrieval system against the same 60 candidate items for the selected split. Restrict the candidate pool before ranking, not after taking the top results from the full corpus.
- The remaining corpus items have no relevance judgments. Do not treat them as irrelevant or claim full-corpus benchmark scores from this 120-item annotation set.
- Review all 120 sheets before final scoring. Record queries with no confirmed relevant candidate (grade 2 or 3), and define how they are handled before looking at system results. Grade 1 means unconfirmed, not confirmed relevance; document its metric treatment separately.

Generate the labels, then join the files and apply these filters in the evaluation code. The label generator does not enforce this evaluation policy by itself.
