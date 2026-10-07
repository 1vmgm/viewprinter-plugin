# Project memory

Media-buying decisions only compound if the next session starts from the last one's numbers, rules and reasons. Memory is local project state, owned by the project, never stored inside the installed plugin, and never containing credentials.

## Locate and initialize

`arena.py locate --start <directory>` walks up from the directory for `.viewprinter/paid-growth`. `VIEWPRINTER_PAID_GROWTH` selects an explicit directory and wins over discovery. An override that is missing or invalid is an error, not permission to create memory somewhere else.

`arena.py init --project <root> --name <name>` creates the standard layout and a config with default rules and an empty value model. It preserves existing memory and never overwrites a config.

## Layout

| Path | Contents | How it changes |
|---|---|---|
| `config.json` | Platform, currency, each source's time zone, ad account and campaign IDs, the value model, the rule thresholds | Deliberate edits, each with a finding that says why |
| `project.md` | The account's winning format profile, hypotheses tested and their outcomes, the user's standing preferences | Update the affected section |
| `state/carry-forward.json` | Open rounds, the next checks and their due dates, pending true-ups | Targeted edits; reread before writing |
| `snapshots/` | The exact per-ad pull behind each decision (CSV or JSON), named by date and window | New file per pull |
| `history/rounds/<id>.json` | A test round at launch: group, hypothesis, ads with post IDs and accounts, budget, first delivery date | Immutable |
| `history/decisions/<id>.json` | One proposal: the snapshot, the evaluator verdicts, the proposed change, the user's words, what was executed and the platform's response | Immutable |
| `history/findings/<id>.json` | What was learned, with evidence, confidence, scope, and the rule or threshold it changed | Immutable |

## The value model and rules in config

```json
{
  "value": {
    "horizon": "first-year",
    "perTrial": 18.36,
    "perPurchase": 20.19,
    "trialShare": 0.7,
    "breakEvenPerPayer": 18.91,
    "basis": "provisional",
    "assumptions": {"trialToPaid": 0.40, "refundRate": 0.10, "netFactor": 0.85},
    "asOf": "2026-09-29",
    "recheckWhen": "20 matured trials since asOf"
  },
  "rules": {"ctrFloor": 0.006, "holdFloor": 0.35, "floorsBasis": "provisional"}
}
```

`breakEvenPerPayer`, or `perTrial`, `perPurchase` and `trialShare` together, is required; the evaluator never derives break-even from a pull. `basis` is `provisional` until the numbers come from the revenue source; reports carry it. `rules` holds every threshold in [decision rules](decision-rules.md); `init` writes the defaults.

## Writing events

Create a JSON event with at least `id` and `createdAt`, then:

```sh
python3 <skill-directory>/scripts/arena.py append --memory <memory-root> --collection decisions --file <event.json>
```

The collections are `rounds`, `decisions` and `findings`. Each event is its own immutable file. Retrying an identical event is safe; reusing an ID with different content is refused. Parallel agents can append without overwriting each other. Give each mutable file (`config.json`, `state/carry-forward.json`) a single writer at a time, and reread it just before editing.

Suggested decision fields: `id`, `createdAt`, `window`, `snapshot` (path), `verdicts`, `proposal`, `userResponse` (verbatim), `executed`, `platformResponse`, `followUp`. Suggested finding fields: `question`, `evidence`, `verdict`, `confidence`, `scope`, `changes` (config keys, from → to), `recheckWhen`.

## Resume

At session start, read `config.json`, `state/carry-forward.json`, the open rounds and the latest decisions before pulling fresh numbers. At session end, update carry-forward with the next check and its date. Keep memory private: it holds ad account IDs and revenue figures. Never add it to a public repository.
