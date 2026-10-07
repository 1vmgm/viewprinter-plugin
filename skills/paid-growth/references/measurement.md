# Measurement

## Which source owns which number

| Number | Source of truth | Not from |
|---|---|---|
| Spend, impressions, clicks, plays, 2-second views | Ad platform | Attribution (cost integrations lag and drift) |
| Trial starts, purchases per ad | Attribution (MMP, or pixel with Events API plus checkout) | Ad platform's own conversion count, except in directional mode |
| Revenue, refunds, trial-to-paid | Revenue source (subscription platform, store, checkout) | Attribution revenue, which is usually gross and often incomplete |
| Organic views, retention | ViewPrinter post metrics | An ad's post views, which include paid impressions once it runs |

Join sources on ad ID, never on ad name: names get edited and duplicated.

## Time zones and windows

Each source counts days in its own time zone. Ad accounts report in the account time zone, many MMPs in UTC, and stores in their own. So a "day" is not the same day across sources.

- Decide on windows of 3 or more days, where a few hours of offset barely matter.
- Name every window with dates and each source's time zone: "Mar 3–5, ad platform UTC−5, MMP UTC".
- Treat the current day as incomplete in every source. Postbacks arrive late and today undercounts.

## Trials versus purchases

Report them separately. When the platform optimizes on a merged event, its count mixes the two. Read the split from attribution, and never compare a merged platform count to a trials-only count from another period.

## Small samples

Paying events are rare, so their counts are noisy. The evaluator prints a 90% range on cost per payer from the Poisson interval on the count:

| Payers | Range around the point estimate |
|---|---|
| 3 | 0.4× – 3.7× |
| 5 | 0.5× – 2.5× |
| 8 | 0.55× – 2.0× |
| 15 | 0.65× – 1.6× |
| 30 | 0.74× – 1.4× |

Two ads whose ranges overlap mostly have not been separated. Say so rather than ranking them.

## Views are not a forecast

- **Organic views don't predict ad results.** At small account sizes they are mostly noise. A post with a large organic audience can lose money as an ad, and a winning ad can come from a post almost nobody saw organically.
- **Spark Ads count ad impressions as post views**, so a post's view count is inflated from the day it starts running as an ad. Compare organic performance only on posts that never ran, or on views before the ad started.

## Starved ads

When a batch concentrates spend on one video, the others get too little to judge. Report them as "no read" with their share of group spend. Don't average them into the batch's results, and don't call them losers.

## Weekly reconciliation

- Per-ad spend summed over the week equals campaign spend on the platform, within rounding.
- The ratio of attribution payers to platform conversions stays roughly stable. A sudden change means a tracking change, not a creative change. Check the postback mapping, the SDK or pixel release, and consent changes before judging ads on that week.
- Matured trials are trued up against the value model ([economics](economics.md)).

## Every report states

- The window, per source, with time zones.
- The operating mode (see [connections](connections.md)).
- The source of each column.
- Payers as trials plus purchases, with a range on cost per payer.
- Whether ROAS is projected or realized, and the value model version it used.
- As-of times for anything read from a sweep or cache.
