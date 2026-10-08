# Comparing results fairly

Most wrong content decisions come from comparing things that are not alike: a young post
with an old one, a trial reel with a follower-facing one, one account's numbers with
another's, a promoted post with organic ones. These are the rules the report applies,
and the ones to keep when reading it.

## Compare within the same account

Accounts differ by orders of magnitude. A post that gets 2,000 views is a hit on an
account that usually gets 500 and a flop on one that usually gets 20,000. Every
comparison is against the same account's median, never a cross-account number.

## Compare at the same age

Lifetime counters keep growing, so a two-day-old post always looks worse than a
two-week-old one. The report compares only within age buckets: under 1 day, 1–3 days,
3–7 days, 7–30 days, and older. Nothing is decided on posts under 72 hours old. A
lifetime total on an old post is not a measurement taken at 24 hours; don't present it
as one. Revisit a batch at similar ages (about 24 hours, 72 hours and 7 days).

## Compare like with like

- **Trial and regular.** Instagram trial reels go to non-followers first. Compare trials
  with trials. For a diagnosis about trial settings, also separate `MANUAL` from
  `SS_PERFORMANCE` and inspect the creative mix in each. The current report helper
  pools both as `trial`; supplement it with separate cohorts before attributing a
  difference to the setting. Keep initial mode distinct from any later sharing state.
  A field named promotion is not evidence of paid support without its documented
  meaning and an ad record.
- **Promoted and organic.** Promoted posts count ad impressions as views. Mark them and
  keep them out.
- **Platforms.** Never pool platforms. Watch time is not comparable either: Facebook
  averages per play and Instagram per viewer, so compare total watch time divided by
  views, within one platform.

## Know what each counter means

- Establish a counter's definition before combining anything with it. Facebook replays
  are reported separately; whether the view counter already includes them has changed
  over time, so check before adding, and label any derived total.
- Grouping lifetime views by publication date gives the accumulated results of that
  posting cohort, not views earned on that day. Daily traffic needs dated counter
  differences over aligned observation windows. To compare an earlier breakout with
  recent posts, use archived observations at similar ages when available; retain
  exact capture times and state the remaining creative and calendar-time confounds.
- A null is "not reported", not zero. A name in `unavailable` means the platform refused
  this time. A destination with no measurement is unmeasured, not a zero-view post.
- Retention (who kept watching) and interaction timing (when people liked or shared) are
  different; aggregate totals can't reconstruct either.
- Average watch time divided by length is not a completion rate.
- Engagement per view counts only the counters the platform reports. Instagram reports
  saves; Facebook does not. Compare engagement within a platform.

## Small samples and outliers

- One viral post is not a format. The report uses medians and the share of posts above
  baseline, so one outlier can't carry a format to "double down".
- Three comparable posts is the minimum for any suggestion, five for "retire". Below
  that, the answer is keep testing.
- At small account sizes, a few hundred views either way is noise. Prefer the structure
  of what worked (hook shape, proof timing, ending) over ranking near-identical numbers.

## Controlled tests versus exploration

Changing the hook, the song, the cover and the length at once is exploration: useful,
but it can't say which change mattered. A controlled test changes one thing and holds
the rest: same body, runtime, song, cover and posting slot where possible. Label which
kind each batch is before reading it.

## What a report states

- The window, the accounts and platforms, and the observation time of the data.
- How many linked publications were compared, how many were unmeasured or pending, and
  how many promoted posts were excluded.
- For each format: publications, how many were mature and comparable, the median against
  baseline for views and engagement, the share above baseline, the suggestion and why.
- What it cannot say: installs, revenue, anything the platform did not report.
