# Creative pipeline

Winners wear out in weeks. The pipeline of tested candidates, not any single video, is what keeps cost per payer down.

## Build the pool from organic posts

Spark Ads run existing organic posts, so the pool is what the user has already posted on accounts that can be authorized to their ad account.

1. `accounts_list` for the TikTok accounts. Confirm with the user which are authorized for Spark Ads on the ad account (see [TikTok](tiktok.md)).
2. `posts_list` per account for the period, following every `nextCursor`. Include external sources explicitly: posts made in the TikTok app count, and the default listing excludes them.
3. Keep single videos in the target length range; the account's winners define that range. The method is built on single videos.
4. Remove posts already running or already tested as ads. Match on the TikTok post ID, recorded in each round file in memory.

## Deduplicate the same video

The same video is often posted to several accounts with different captions. Test it once: two copies in one round compete with each other and split the read.

- Match on the platform post ID first.
- Then compare frames. Sample the video at fixed offsets (for example 1.5 s and 4 s), compute a perceptual hash for each frame, and treat near-identical hashes as one video. Captions and titles are not evidence of identity.
- Keep the copy on the account with the strongest authorization and history, and record the others as duplicates.

## Choose on structure, not views

Organic views at small account sizes are mostly noise ([measurement](measurement.md)). Choose on what the account's winners share instead:

- **Hook:** the first words on screen, and whether they carry a specific claim or number.
- **Product proof:** when the product first appears on screen, and whether it backs up the hook's claim.
- **Length and pacing:** total seconds, and whether the hook stays on screen long enough to read.
- **Tone:** for example proof and payoff, versus frustration, versus instruction.

Write that profile down as the account's current winning format (in memory `project.md`). Fill most test slots with candidates that fit it. Spend some slots on a deliberate structure test, where one group tests one hypothesis such as "a reveal after 8 seconds loses to one in the first 2". A clean negative result is worth a round.

## Using a model to read videos

A vision model is reliable at extracting facts: the on-screen hook text, the second the product first appears, whether a number appears in the first 3 seconds, and the length. Use it to filter the pool at scale.

Don't let a model score "will this win" until it is calibrated:

1. Score at least 10 past ads blind, without their results.
2. Compare the scores to their projected ROAS with a rank correlation (Spearman).
3. Below about 0.3, the score gets no vote. A detailed, plausible rubric can come out negative: worse than random.

Re-run the calibration when the format or the audience changes. Keep extracted facts and scores in separate fields so nobody mistakes a filter for a forecast.

## Naming

Name ads so a report reads without a lookup: `<group>-<short hook>`, for example `t2-price-first`. Record the post ID, account and hypothesis in the round file; names are for people, IDs are for joins.

## From a winner to a format

When a round produces a winner, write its format: hook shape, reveal time, length, proof and ending. Hand the format to [content production](../../content-production/SKILL.md) for variants. The next winner is most likely a variant of this one.

Keep 2–3 posted variants of each live winner's format ready as backups. When a winner's fatigue rule fires, its backups go into the next test round together.

## Winners back to organic

A proven ad is also proven organic material. Cross-posting it to other platforms is a separate, separately approved step through the content-publishing skill, with native captions per platform.
