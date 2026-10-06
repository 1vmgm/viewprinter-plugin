# Economics: what a paying customer is worth

Every decision rests on net revenue per ad dollar. Get this wrong and every rule downstream is wrong in the same direction. The usual way it goes wrong: attribution revenue is gross, the store's cut never comes off, and break-even sits too high for weeks while every marginal customer loses money.

## Paying events

Count everything that starts paying: trial starts and direct purchases. Keep them as separate columns everywhere, because they are worth different amounts and arrive through different funnels. If the ad platform optimizes on one merged event, the split still comes from attribution (see [measurement](measurement.md)).

## Value per event

Pick one horizon and keep it: first-year revenue is the usual conservative choice. State it beside every value and every ROAS.

```
net_factor     = 1 − store or processor fee − tax withheld
value_trial    = trial_to_paid × revenue_in_horizon × (1 − refund_rate) × net_factor
value_purchase = revenue_in_horizon × (1 − refund_rate) × net_factor
```

`revenue_in_horizon` for a subscription is the first charge plus the renewals expected inside the horizon, from the account's own retention. For one-off purchases it is the order value.

## Break-even and ROAS

```
break_even_per_payer = mix_trial × value_trial + mix_purchase × value_purchase
projected_roas       = (trials × value_trial + purchases × value_purchase) / spend
realized_roas        = matured net revenue / spend
```

The mix is the account's share of trials versus purchases over a recent month or more, re-read at the weekly true-up. Projected ROAS values pending trials at the historical conversion rate. Realized ROAS waits for trials to mature and refunds to settle, so it lags by the trial length plus the refund window. Decisions use projected ROAS, and the weekly true-up keeps it honest.

## Worked example (invented numbers)

- Annual plan $60 with a 7-day trial. 40% of trials convert and 10% of those are refunded. Net factor 0.85. First-year horizon, so the annual plan has no renewal inside it.
  `value_trial = 0.40 × 60 × 0.90 × 0.85 = $18.36`
- Monthly plan $10, bought directly. It averages 2.5 paid months in the first year, with 5% refunded.
  `value_purchase = 10 × 2.5 × 0.95 × 0.85 = $20.19`
- The mix is 70% trials and 30% purchases.
  `break_even = 0.7 × 18.36 + 0.3 × 20.19 = $18.91 per paying customer`
- An ad that spent $150 for 6 trials and 2 purchases:
  `projected ROAS = (6 × 18.36 + 2 × 20.19) / 150 = 1.00`, or $18.75 per payer. That is break-even, not a winner.

## Targets

| Line | Default | Why |
|---|---|---|
| Break-even | projected ROAS 1.0 | Below it, each customer costs more than they bring |
| Graduate a test ad | ROAS ≥ 1.0 on 4+ payers | Cheap to try alone; not yet evidence |
| Scale a winner | ROAS ≥ 1.2 on 15+ payers | Margin for model error and small samples |
| Governor | Blended 7-day ROAS < 1.0 | Stop scaling; the account is losing money on the margin |

These live in the project config (`rules` in [memory](memory.md)) and can be tuned per account with a recorded reason.

## Break-even in config

Record break-even in `value` in config: a fixed `breakEvenPerPayer`, or `perTrial`, `perPurchase` and `trialShare` (the mix's trial share, 0–1). The evaluator refuses to run without one. It never derives the mix from the ads it is judging: a pull's own mix moves with every window, and every threshold would move with it. When both are set, it warns if they differ by more than 5%. Change either deliberately, with a finding.

## Weekly true-up

Trials are promises. Each week, read the trials that have matured since the last true-up: how many converted, and how many were refunded. If the matured rate differs from the model by more than about 5 points across 20 or more trials, update the model, record a finding, and re-score open decisions. Don't update on fewer: a handful of matured trials swings by chance.

## Traps

- **Gross revenue.** MMP and attribution revenue is usually the customer price. Apply the net factor once and write down that you did.
- **Double counting.** Two integrations feeding the same revenue table (for example, a subscription platform and a store connection) can report every transaction twice. Reconcile a month against the store's own financial report before trusting a raw sum.
- **Refund signs.** Some store exports encode a return with a negative quantity and a negative price, so multiplying them makes refunds add to revenue.
- **Currencies.** Convert before summing, or report per currency.
- **Other cohorts' renewals.** Revenue this month is mostly renewals from customers acquired earlier. It is not this ad's revenue.
- **A stale model.** A price change, a new trial length or a new paywall changes the value per event. Re-derive it rather than carrying the old number forward.
