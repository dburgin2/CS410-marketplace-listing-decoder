# How the labels get made

Nothing is judged directly. I fill in plain facts about 120 listings, and a script turns those facts into every label.

1. `python make_label_sheet.py` makes `item_facts.csv` (one row per benchmark listing, with its source text)
2. Fill in the blank columns by hand (Excel or Google Sheets), then save it back as CSV with the same name
3. `python make_labels.py` writes `attribute_labels.csv` and `relevance_labels.csv`

The 120 listings are 20 random picks per category (seed 20261115), split 60 development / 60 evaluation. They're in `benchmark_ids.csv`.

## Filling in the sheet

Use only what the listing says (title, `source_dimensions`, `source_materials`, features, description). Leave a cell blank if the listing doesn't say, and put `?` if it's unclear or contradicts itself.

- `price`: already filled from the source, leave it
- `width_in`, `depth_in`, `height_in`: overall size in inches. Use `?` if the numbers have no W/D/H labels, or two fields disagree
- `top_material`, `frame_material`, `base_material`, `upholstery_material`: copy the material words for that part, e.g. `engineered wood` or `metal; glass`
- `general_material`: a material the listing gives without saying which part
- `table_type` (tables and nightstands): `side`, `coffee`, `dining`, `console`, `drafting` or `set`
- `solid_wood_top`, `fabric_upholstery`, `reclining`, `loveseat`, `office_chair`, `dining_chair`: `yes`, `no`, or blank
- `also_counts_as`: `nightstands` for a table sold as a bedside/side table, `desks` for a drafting table. Nightstands count as tables automatically

Every row needs the sizes and at least one material. Beyond that, only these matter per category:

| Category | Also fill |
|---|---|
| desks | `top_material`, `base_material` |
| tables | `table_type`, `top_material`, `solid_wood_top`, `also_counts_as` |
| chairs | `frame_material`, `dining_chair`, `office_chair`, `reclining` |
| sofas | `loveseat`, `reclining`, `fabric_upholstery` |
| dressers | any material column |
| nightstands | `table_type` (usually `side`), `top_material` |

## How grades work

Each query is graded against every one of the 120 listings:

- **0**: wrong category, or breaks a requirement
- **1**: nothing broken, but a requirement can't be confirmed (that fact is blank or `?`)
- **2**: all requirements confirmed, but a "preferably" isn't met or can't be confirmed
- **3**: everything confirmed

Material words are matched by fixed rules:

- **engineered wood**: engineered or manufactured wood, MDF, particleboard, fiberboard or chipboard. Plain "wood" can't confirm or rule it out
- **wood**: any of those, plus wood, veneer and wood species (pine, oak, acacia...)
- **metal**: metal, steel, iron, aluminum, brass or copper
- **solid wood top**: your `yes`/`no` if given. Otherwise it's ruled out when the top is engineered, veneer or not wood at all
