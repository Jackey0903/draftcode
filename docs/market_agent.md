# Market Capture Agent

DraftCode's market capture agent converts externally supplied mock draft text
into consensus market signals. It follows the same separation as the real-time
intel agent: scraping and fetching are outside the engine, while extraction,
aggregation, application, and audit are local and testable.

## Boundary

The agent does not browse the web or scrape pages. WebFetch, a crawler, an API
job, or a manual operator writes mock draft text and passes it to:

```bash
draftcode market --mock-file ESPN=data/raw/mocks/espn.txt --mock-file CBS=data/raw/mocks/cbs.txt
draftcode market --mock-dir data/raw/mocks
```

`--mock-dir` reads every file in the directory and uses the filename stem as the
source label.

## Extraction

For each `(source, text)` pair, `aggregate_mocks` calls `llm_client.complete`
with a JSON schema. gpt-5.5 extracts projected pick numbers and maps player names
to the Chinese `prospects.csv` name pool. The prompt explicitly asks for exact
pool strings, so English text such as:

```json
{
  "rankings": [
    {"raw_player_name": "AJ Dybantsa", "matched_prospect_name": "AJ 迪班萨", "projected_pick": 1},
    {"raw_player_name": "Cameron Boozer", "matched_prospect_name": "卡梅隆 布泽尔", "projected_pick": 3}
  ]
}
```

becomes source-level `SourceRanking` rows. Code then does a final exact and
normalized Chinese-name check against the supplied pool. Invalid JSON, no LLM,
timeouts, or unmatched names skip only that source.

## Aggregation

`aggregate_mocks` groups matched players across successful sources:

```json
{
  "prospect_name": "AJ 迪班萨",
  "consensus_pick": 1.5,
  "n_sources": 2,
  "sources": ["ESPN", "CBS"]
}
```

Consensus pick is the arithmetic mean of unique source projections for that
player. Reports are sorted by consensus pick.

## Application

`apply_market` reads `prospects.csv` and `draft_order.csv`, then previews or
applies two changes:

- `prospects.csv.market_rank` is set to the consensus pick.
- `mock_signals.csv` is rewritten from consensus pick proximity to each draft
  slot, preserving real source labels such as `ESPN`, `CBS`, `Ringer`, and
  `NBA.com`.

The default is dry-run. CSVs are written only with:

```bash
draftcode market --mock-dir data/raw/mocks --apply
```

Every run writes `outputs/market/market_<seq>.json` with source rankings,
consensus rows, and application changes. If all sources fail, the report is
empty and apply mode leaves existing CSV files untouched.
