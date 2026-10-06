---
name: paid-growth
description: Run a data-driven TikTok test-and-scale loop on organic posts. Check the user's ad and attribution connections, build the value model and break-even, structure winner and test ad groups, apply cut, graduate, scale and fatigue rules on net revenue, and log every decision. Use for choosing which videos get spend, reading per-video ad performance, cutting losers, scaling winners or setting up Spark Ads testing. The user brings their own TikTok Ads access; ViewPrinter supplies the organic post pool. In early access — its rules are still being refined.
---

# Paid growth

Turn organic posts into a paid test-and-scale system where every dollar is judged on net revenue, not on views or the platform's own conversion count. Test new videos in cheap batches, cut on engagement early, promote only on paying customers, scale winners slowly, and replace them before they wear out.

The method is platform-general. The platform detail is TikTok's, the only platform this skill supports today: see [TikTok](references/tiktok.md).

**This skill proposes; the user decides.** Never pause, enable, create or delete an ad, or change a budget, bid, target or optimization event without the user's explicit yes to that specific change in the current conversation. Approval of one change does not carry to the next, and "reversible" does not lower the bar. A blanket instruction such as "do whatever the rules say" is not approval of a specific change: present the list and get a yes. Research and reporting requests never include edits.

## 0. Check the connections first

Before any analysis, establish what this session can actually see and change. Inspect the available tools; don't assume. A server that is configured but failing is a connection problem to report, not a missing capability.

| Connection | Answers | Without it |
|---|---|---|
| **TikTok Ads** (required) | Spend, impressions, clicks, 2-second views per ad per day; ad status and budget changes | Ask for an ad-level Ads Manager export and work read-only |
| **Attribution** (strongly recommended) | Which ad produced each trial or purchase | TikTok's own conversion count, for ranking only; no scale decisions |
| **Revenue truth** (recommended) | What a paying customer is worth, net | The user's stated numbers, labeled provisional on every ROAS |
| **ViewPrinter** (MCP server) | The organic post pool, per-post views and retention | Build the pool from post links by hand |

When one is missing, tell the user once, in a short block: what it is, what it unlocks, how to connect it and what you can do meanwhile. Then continue in the mode the available data supports. [Connections](references/connections.md) has the setup paths and the wording. Never ask for an access token, API key or password in chat, and never write one into memory.

## 1. Resume before reading fresh numbers

Find project memory by walking up from the working directory for `.viewprinter/paid-growth`, or use `VIEWPRINTER_PAID_GROWTH`. Read the config (value model, thresholds, account IDs), the open rounds and the recent decisions before pulling anything new. Keep memory out of the installed plugin. See [memory](references/memory.md). For a new project:

```sh
python3 <skill-directory>/scripts/arena.py init --project <project-root> --name <project-name>
```

## 2. Know what a paying customer is worth

Before judging any ad, establish the net value of a trial start and of a direct purchase over a stated horizon, and the break-even cost per paying customer. Record break-even in config, either fixed or as the value per trial and per purchase with the account's trial share. The evaluator refuses to run without it and never derives it from the ads being judged. Every threshold below is a multiple of that break-even. If the value model is unknown, build it with the user first. Until it is measured, label every ROAS provisional. See [economics](references/economics.md).

## 3. Structure: winners alone, new videos in batches

Keep one campaign, optimizing on the event that starts paying. Give each proven winner an ad group of its own. Every other group is a test group, running a round of 3–4 new videos launched the same day. Never add a new video beside an established one: the platform starves it and the read is lost. A round ends with the whole batch paused, then the next batch goes in fresh. See [structure](references/structure.md).

## 4. Choose what to test

Build the pool from the user's existing organic posts on accounts that can run as Spark Ads, deduplicate the same video across accounts, and pick on the structure the account's winners share, not on organic views. A model may read videos (hook text, when the product appears); it gets no vote on what will win until it is calibrated against past ads. Give each test group one hypothesis. See [creative pipeline](references/creative-pipeline.md).

## 5. Read, then decide

Pull per-ad numbers from the ad platform, join the paying events from attribution, add each ad's `role` (test or winner) and each test ad's `round` from memory, and run the evaluator. It applies the agreed rules the same way every time:

```sh
python3 <skill-directory>/scripts/arena.py evaluate --memory <memory-root> --ads <ads.csv> --window "<dates, time zones>" --account-window
```

One pull serves every rule: all ads in the campaign, one row per ad per day, over the trailing 7 days. The evaluator sums each ad's days, judges test ads within their round (a 3-day round fits inside the week) and winners on the whole week, reads fatigue from the latest 3 days against the best 3, and applies the account governor. Pass `--account-window` only when the rows are every ad over one trailing 7-day window; without it the governor is not applied. Columns, units and warnings: [evaluator input](references/evaluator.md).

The evaluator's verdict is a proposal. Read its reasons and any warning, check them against anything it cannot see (ad review status, a delivery problem, a known tracking outage), and present the change list for approval. See [decision rules](references/decision-rules.md) and [measurement](references/measurement.md).

The rules in one breath: cut early on weak engagement. Cut on no paying customers at 3× break-even, and on a few paying customers once even the optimistic end of their range can't break even. A starved ad is no read, not a loser. Graduate on paying customers, never on clicks. Scale only on 15+ paying customers at a margin above break-even, 20–25% a day. Start the backup when a winner's 3-day click rate or hold falls 30% from its best 3 days. Stop scaling when the account as a whole falls below break-even.

## The routine

- **Daily, short:** every ad approved and delivering; new ads past their first engagement check; winners' cost per payer and fatigue flags; blended cost per payer against break-even. Propose only what a rule triggers. A quiet day is a valid report.
- **Round end, every 3 days per test group:** propose the graduate, pausing the rest of the batch, and a fresh batch for the next hypothesis. Act on each only after the user's yes.
- **Weekly:** true up matured trials against the value model, recalibrate engagement floors from the account's own winners, decide scaling, check the governor, and record findings.

## Report format

Every report states the window with each source's timezone, where each number came from, payers split into trials and purchases, a range on every cost per payer, and whether ROAS is projected or realized. Show a per-ad table before any recommendation. Separate what the numbers show from what you infer. Don't round a small sample into a confident claim.

## Execute, log, learn

After the user approves, make exactly the approved changes, then read them back from the platform to confirm. Report failures as they happened. If the connection is read-only, hand over the exact change list for the user to apply.

Append a decision record for every executed or declined proposal: the numbers it rested on, the rule, the user's words and the result. When a later read shows a rule was wrong for this account, record a finding with evidence and change the threshold in config deliberately. Don't drift it silently. See [memory](references/memory.md).

Related skills: make variants of a winning format with [content production](../content-production/SKILL.md); cross-post winners organically and read organic post metrics with the content-publishing skill.
