# Time Handling

This is the navigation and behavior summary for the existing time helpers, replacing three overlapping time-refactor documents as the active entry point. The [original analysis, plan, and specification](../archive/README.md) remain archived for historical context.

| Concern | Source | Existing Behavior |
| --- | --- | --- |
| Backend clock | [Python helpers](../../common/time_utils.py) | `now_utc()` returns an aware UTC datetime. |
| Numeric storage | [Python helpers](../../common/time_utils.py) | `to_epoch_millis()` converts supported values to epoch milliseconds. |
| Relative query ranges | [Python helpers](../../common/time_utils.py) | `parse_time_range()` handles numeric `s/m/h/d` ranges and `all`. |
| Browser display | [Frontend helpers](../../services/website/frontend/v1/lib/time.ts) | Formatting uses JavaScript `Date` and the browser's local timezone. |

## Compatibility Caveats

The current Python helper uses a numeric magnitude heuristic to distinguish seconds from milliseconds. Naive datetime objects are treated as UTC, but ISO strings without an offset use Python's local-time interpretation. Invalid inputs can fall back to the current time. An unknown relative range falls back to the full range, not an empty result.

These are descriptions of existing behavior, not recommendations for new strict ingestion contracts. Validate timestamps at an API or ingestion boundary when ambiguity or silent fallback would be unsafe. Documentation organization does not change these semantics or migrate stored timestamps.
