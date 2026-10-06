# Evaluator input

`arena.py evaluate` reads a CSV, or JSON as a list of rows or `{"ads": [...]}`. Headers match without regard to case, spaces or underscores. The aliases cover the Marketing API metric names and the usual English Ads Manager labels ([TikTok](tiktok.md)).

## Rows

Give one row per ad for the window, or one row per ad per day with a `date`. Daily rows for the same ad are summed, and CTR and hold are recomputed from the sums. A count left blank on one day counts as zero when another day has it. An ad repeated without a date, or twice on the same date, is refused rather than double counted.

## Columns

| Column | When | Meaning |
|---|---|---|
| `ad_id` | always | The join key. Never join on names. |
| `group` | always | Ad group name or ID. |
| `spend` | always | In the config currency. |
| `role` | always, in practice | `test` or `winner`. A missing role is judged as `test` and flagged in a warning, because a winner judged as a test ad can only graduate: it never gets scale, fatigue or pull-back. |
| `round` | test ads | The round's ID from memory (a launch date works). Starvation and the one-graduate limit apply per round. Without it they apply per group, with a warning. |
| `date` | daily rows | `YYYY-MM-DD`; the API's `stat_time_day` works as sent. |
| `name` | optional | For people; defaults to the ID. |
| `impressions`, `clicks` | for CTR | |
| `plays`, `views_2s` | for hold | Hold is 2-second views ÷ video plays. |
| `trials`, `purchases` | for revenue verdicts | From attribution, not the platform's own count. Both blank means payers unknown: engagement verdicts only. |
| `ctr`, `hold` | only without the counts | Ignored when the counts are present. |
| `peak_ctr`, `peak_hold` | winners, optional | The best 3-day value from before the pull. |

## Rates need a % sign

Write `ctr`, `hold`, `peak_ctr` and `peak_hold` as percentages with the sign: `0.45%`. A bare number is refused, because it is ambiguous: TikTok's API sends `ctr` as a percent without the sign (`"0.45"` means 0.45%), while a fraction would read the same digits as 45%. Prefer the counts; a bare `ctr` or `hold` next to its counts is ignored rather than refused.

Numbers may carry `$` and thousands separators. NaN, infinity and negative counts are refused.

## Fatigue

With daily rows, a winner's fatigue compares its latest 3 days with its best 3-day stretch in the pull, or with `peak_ctr` and `peak_hold` when those are higher. A stretch counts only with at least `fatigueMinEvents` (100) clicks for CTR, or 100 2-second views for hold. With one row per ad, the check compares the row's rate over the whole window with the peak columns, which is coarser: pull daily rows for winners.

## Flags

- `--window "<dates, time zones>"`: printed at the top of the report.
- `--account-window`: the rows are every ad in the account over one trailing 7-day window. Only then does the governor run; otherwise the report says it was not applied.
- `--json`: the full result, including `warnings`, for logging in a decision record.

## Config

Break-even comes from `value` in config: `breakEvenPerPayer`, or `perTrial`, `perPurchase` and `trialShare` (0–1). The evaluator refuses to run without one and never derives it from the pull. It warns when a fixed `breakEvenPerPayer` is more than 5% from the mix. Every value and rule threshold must be a JSON number: `20`, not `"20"`. See [economics](economics.md) and [memory](memory.md).
