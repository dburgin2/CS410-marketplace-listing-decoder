# How the labels get made

1. `python make_label_sheet.py` makes `item_facts.csv` (one row per benchmark listing)
2. Fill in the blank columns by hand (Excel or Google Sheets), then save it back as CSV with the same name
3. `python make_labels.py` writes `attribute_labels.csv` and `relevance_labels.csv`

The 120 listings are 20 random picks per category. They're in `benchmark_ids.csv`.

Each query is graded against every one of the 120 listings:

- **0**: wrong category, or breaks a requirement
- **1**: nothing broken, but a requirement can't be confirmed (that fact is blank or `?`)
- **2**: all requirements confirmed, but a "preferably" isn't met or can't be confirmed
- **3**: everything confirmed
