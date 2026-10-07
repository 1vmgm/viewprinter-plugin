# Structure

## One campaign, optimizing on the paying event

Keep the campaign that already has delivery history. A new campaign starts learning from zero, so rebuild only when the optimization event itself has to change. Every ad group optimizes on the event that starts paying: a trial start or a purchase. Don't optimize for installs or clicks: an ad group finds more of whatever it is told to optimize. When there are two paying events and the platform allows one per ad group, merge them at the attribution postback rather than splitting the ad groups (see [TikTok](tiktok.md)).

Keep targeting broad and the same across groups, so the difference between groups is the creative.

## Two kinds of ad group

**Winner groups.** One proven video each, alone. Budget moves only by the scaling rules. A winner shares its group with nothing, not even its own recut; a recut is a new video and belongs in a test round.

**Test groups.** Each runs a round: 3–4 new videos launched on the same day, answering one hypothesis ("the product in the first 2 seconds", "a price in the hook", "a before-and-after story").

## Why never add a new video beside an established one

TikTok's delivery chooses well among videos that start together: it tends to put most of a batch's spend on its favourite within a day. What delivery does not do is give a newcomer a fair chance beside a video that already has history. A new ad placed beside an incumbent gets a trickle of spend while the incumbent takes the rest, and no read is possible.

So:

- A round ends by pausing the whole batch, apart from a graduate, which moves out to its own group.
- The next batch goes into the test group with every previous ad paused, or into a fresh group.
- To challenge a winner, launch its would-be replacement in a test round and compare across groups, never inside the winner's group.

## Round cadence

A round runs 3 days from the first delivery, not from creation: ad review can take hours.

- **Day 1:** review clears, delivery starts, spend concentrates.
- **Days 2–3:** engagement checks fire, and paying events accumulate on the favourite.
- **Round end:** apply the round-end rules in [decision rules](decision-rules.md) and propose at most one graduate, pausing the rest, and the next hypothesis. Nothing moves without the user's yes.

When a rule flags an ad for an early cut, propose pausing it that day. Once the user approves, the rest of its round continues.

## Budgets

- **Test group:** enough for its favourite to pass the first engagement check within a day and its runners-up to get a read by round end. About 2.5–3× break-even per day per test group is a workable start. At a $30 break-even (an invented example) that is $75–90 a day, about $225–270 per round.
- **Winner group:** what its results have earned, moved by the scaling rules.
- **Split:** keep enough test budget to run at least two rounds in parallel. Winners wear out, and the pipeline is what replaces them. While no winner is proven, most spend is test spend.

## Graduation

A round's winner moves to its own group at a test-sized budget, then the scaling rules apply. Create the new group (or reuse a paused one) with that single ad; don't duplicate the ad inside its current group. The moved ad restarts ad-level learning, so expect a noisier first day before judging it.

## Changes that disturb learning

Keep these rare and batched:

- Budget jumps above about 25% a day.
- Changing the optimization event or bid strategy.
- Targeting edits, and creating a new campaign.

Pausing and adding ads inside a test group is the method working, not a disturbance.

Platform limits, such as a cap on active ad groups per campaign, decide how many winner and test groups fit at once. See [TikTok](tiktok.md).
