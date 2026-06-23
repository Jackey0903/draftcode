# Real-Time Intel Agent

DraftCode's real-time intel agent keeps the fetch layer outside the engine. A
WebFetch job, crawler, API client, or manual operator supplies raw news text; the
engine only performs extraction, structured application, and audit.

## Three-Stage Flow

1. Capture: external tooling provides a news excerpt and optional source label.
2. Structure: `extract_intel()` asks gpt-5.5 for a strict JSON object with
   `picks_moved_2026_round1`, `team_needs_delta`, and
   `affects_our_draft_order`. If the LLM is unavailable or returns invalid JSON,
   the function returns an empty `IntelReport`.
3. Apply: `apply_intel()` previews or writes the resulting changes to
   `data/processed/draft_order.csv` and `team_needs.csv`. The default CLI mode is
   dry-run; `--apply` is required to mutate the CSVs. Every run writes an audit
   file under `outputs/intel/intel_<seq>.json`.

## Giannis Case

Validated input:

```text
Heat acquire Giannis from Bucks; Milwaukee gets the No. 13 pick in 2026
```

Validated structured output:

```json
{
  "picks_moved_2026_round1": [
    {"pick_number": 13, "from_team": "Miami Heat", "to_team": "Milwaukee Bucks"}
  ],
  "team_needs_delta": [
    {
      "team": "Milwaukee Bucks",
      "new_timeline": "retool",
      "position_focus": "forward upside"
    },
    {
      "team": "Miami Heat",
      "new_timeline": "win-now",
      "position_focus": "cheap guard/wing"
    }
  ],
  "affects_our_draft_order": true
}
```

DraftCode normalizes the pick move to `PickMove(13, "MIA", "MIL")`. In dry-run,
the CLI previews pick 13 moving from Miami to Milwaukee and writes an audit trace.
With `--apply`, `draft_order.csv` updates pick 13 to `Milwaukee Bucks,MIL`,
sets `via_trade=true`, and preserves `original_team=MIA`.

## CLI

```bash
draftcode intel \
  --news-text "Heat acquire Giannis from Bucks; Milwaukee gets the No. 13 pick in 2026"

draftcode intel \
  --news-text "Heat acquire Giannis from Bucks; Milwaukee gets the No. 13 pick in 2026" \
  --apply
```

`--news-file <path>` can be used instead of `--news-text`. The command never
performs network fetches internally.
