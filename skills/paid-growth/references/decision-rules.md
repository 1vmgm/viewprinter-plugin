# Decision rules

The evaluator (`scripts/arena.py evaluate`) applies these in the order written, using the thresholds in the project config. Spend thresholds are multiples of break-even cost per paying customer (BE), so the same rules work at any price point. The defaults below are starting points; tune them per account with a recorded finding (see [memory](memory.md)). What the evaluator reads is in [evaluator input](evaluator.md).

## Principles

- **Engagement can cut; only revenue can promote.** A weak click rate or hold predicts a loser early and cheaply. A strong one predicts nothing about who pays.
- **No read is not a loss.** An ad the platform barely served has not been tested.
- **Small numbers lie.** At 5 paying customers the true cost per payer can be anywhere from half to two and a half times the estimate. The evaluator prints the 90% range. Ads whose ranges overlap heavily have not been separated.
- **Move slowly.** Budget moves of 20–25% a day and changes at round boundaries keep learning intact and keep one lucky day from steering spend.

## Test ads (round to date)

A round is the ads in one test group that share a `round` value. Without that column the evaluator treats the whole group as one round and warns, because a 7-day pull usually still holds the previous round's paused ads.

| Order | Rule | Default | Verdict |
|---|---|---|---|
| 1 | The round has spent ≥ 4× BE and this ad has < 15% of it | 4×, 15% | **No read.** Ends with the round; it may re-enter one later batch |
| 2 | Spend below the first check | < 1.5× BE | **Wait** |
| 3 | CTR or 2-second hold below the floor, while under 15 payers | CTR 0.6%, hold 35% | **Cut** |
| 4 | No paying customer | ≥ 3× BE | **Cut** |
| 5 | Projected ROAS below the cut line on enough payers | < 0.8 on 5+ | **Cut** |
| 6 | 1–4 payers, and projected ROAS stays below break-even even at the top of their 90% range | < 1.0 | **Cut** |
| 7 | Paying customers at or under break-even | 4+ payers, ROAS ≥ 1.0 | **Graduate** at round end |
| 8 | Otherwise | | **Hold** |

At round end, propose at most one graduate per round (the best projected ROAS among those that qualify), pausing everything else in the batch, including ads on hold, and a fresh batch for the next hypothesis. Each is a proposal for the user's yes.

### Why 3× BE, and the few-payer line

Rules 4 and 6 are one test: read a small count at the optimistic end of its 90% range, and cut if the ad would still lose money there. At 0 payers the top of the range is about 3 payers, so an ad with none has had its fair chance at 3× BE. Rule 6 applies the same test to 1–4 payers. With payers worth about BE each, it fires at about 4.7× BE for 1 payer, 6.3× for 2, 7.7× for 3 and 9.2× for 4. From 5 payers the estimate is steady enough for rule 5. The line is `fewPayerRoas` in config.

## Winners (trailing 7 days)

| Order | Rule | Default | Verdict |
|---|---|---|---|
| 1 | Projected ROAS below the pull-back line on 5+ payers, no payer at 3× BE, or 1–4 payers failing the few-payer test | < 0.8 on 5+ | **Pull back** one step (−20%) |
| 2 | Latest 3-day CTR or 2-second hold down from its best 3-day value | −30% | **Fatigue:** propose its backup variant for a test round; don't scale |
| 3 | Enough payers above the scale line | 15+ payers, ROAS ≥ 1.2 | **Scale** one step (+20%) |
| 4 | Otherwise | | **Hold** |

Fatigue reads daily rows: the latest 3 days against the best 3-day stretch in the pull, or against a `peak_ctr` or `peak_hold` value from before the pull when that is higher. A stretch counts only with at least 100 clicks (for CTR) or 100 2-second views (for hold), so a thin first day can't set a false best.

Scale one step per day at most. Stop stepping when the last step's marginal cost per payer (extra spend ÷ extra payers against the previous 3 days) exceeds BE. Propose retiring a fatigued winner when its backup beats it on projected ROAS, or when it spends 7 days below 1.0.

## Account governor (all ads, one trailing 7-day window)

- Blended projected ROAS below 1.0: no scale-ups, and test budgets are not raised.
- Below 0.8 for two consecutive weeks: propose cutting total spend by 25% and review the value model, the tracking and the creative pipeline before spending back up.
- Raise total spend only after a full week at or above 1.2 blended.

The evaluator applies the governor only with `--account-window`, which says the rows are every ad over one trailing 7-day window.

## Setting the engagement floors

Floors come from the account's own winners:

- `ctrFloor` = 0.7 × the median CTR of ads that reached 4+ payers at ROAS ≥ 1.0.
- `holdFloor` = 0.65 × the median 2-second hold (2-second views ÷ video plays) of the same ads.

Until three such ads exist, use the provisional floors of 0.6% CTR and 35% hold. They are placeholders, not benchmarks: replace them with the account's own at the first weekly review after three winners exist, and record the change.

## What these rules prevent

Each rule guards against a mistake that costs real money:

- **Promoting on cheap early conversions.** An ad can buy a few paying customers cheaply in its first days on a click rate and hold far below the account's winners, then lose money for weeks once promoted. The weak engagement is visible on day one; the engagement gate cuts it at 1.5× BE.
- **Letting a loser run on a trickle of payers.** One or two payers keep an ad clear of the no-payer rule while it spends many times break-even. The few-payer rule cuts it once even the optimistic reading can't break even.
- **Judging a starved ad.** A new video placed beside an established winner gets almost no spend. That says nothing about the video, only about its placement.
- **Buying reach with the wrong audience.** A video can have the best CTR and hold in the account and the worst cost per paying customer, because it draws viewers who want the content, not the product. Engagement is a floor, not a target.
- **Scaling on a lucky week.** At 5 payers the true cost could be anywhere from half to two and a half times what it looks like. The 15-payer bar narrows the range to about two-thirds to 1.6×.
- **Spending past break-even on a loose governor.** A governor set on gross revenue sits above true break-even and loses money on every marginal customer until the value model is corrected to net.
