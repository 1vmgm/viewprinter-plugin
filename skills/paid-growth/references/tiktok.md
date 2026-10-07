# TikTok

Platform facts as observed on the Marketing API v1.3 and in Ads Manager in September 2026. Limits and field names change. Check them against the live response before relying on one, and record anything that has changed as a finding.

## Spark Ads and identities

A Spark Ad runs an existing organic post as the ad, keeping its account, caption and engagement. This method runs on Spark Ads.

- **Business Center identity (`BC_AUTH_TT`):** the posting account is authorized to the Business Center, and any of its posts can run. This is the one to use for a pool across several accounts.
- **Authorization code (`AUTH_CODE`):** one code per post, generated in the TikTok app. It works for a single post and doesn't scale to a pool.

Authorizing an account to the Business Center is not enough on its own: the account must also be **assigned to the ad account** (Business Center → Assets → TikTok accounts → assign). Until then it is missing from `identity/get`, even though it is linked. `identity/video/get` lists an identity's videos, where `item_id` is the TikTok post ID. Carousels are not listed.

## Campaign shape

- **Objective:** for apps, App Promotion with in-app event optimization. For web, the conversion objective with the pixel event. Optimize on the event that starts paying (see [structure](structure.md)).
- **One optimization event per ad group.** When trial starts and direct purchases are both paying events, map the direct purchase onto the trial event in the MMP's TikTok postback settings. That way the ad groups learn from both without being rebuilt. TikTok's trial count then includes purchases; read the true split from attribution.
- **Active ad group cap.** iOS 14+ dedicated app campaigns have capped active ad groups per campaign (5 when last observed, with API error 40002 on the next). Plan winner and test groups inside the cap; with more winners than fit, retire a test group or the weakest winner.

## Ad review and delivery

New ads enter review (`AD_STATUS_AUDIT`), usually for hours. A round starts at first delivery, not at creation. A rejected ad is a swap, not a verdict on the video: replace it with the next candidate. A sound without commercial rights is a common cause of rejection. Check every ad reaches a delivering status before counting its round.

## Reading performance

API: `report/integrated/get` with `report_type: BASIC`, `data_level: AUCTION_AD`, `dimensions: ["ad_id", "stat_time_day"]`, a date range and a campaign filter. That returns one row per ad per day; pass the rows to the evaluator as they are, and it sums each ad's days ([evaluator input](evaluator.md)). Metrics this skill uses:

| Evaluator column | API metric | Ads Manager column (typical English labels) |
|---|---|---|
| `spend` | `spend` | Cost |
| `impressions` | `impressions` | Impressions |
| `clicks` | `clicks` | Clicks (destination) |
| `plays` | `video_play_actions` | Video views |
| `views_2s` | `video_watched_2s` | 2-second video views |
| `date` | `stat_time_day` | Date (with a by-day breakdown) |

Send counts, not the API's `ctr`: it is a percent without the % sign, so the evaluator ignores it beside clicks and impressions and refuses it without them. The platform knows nothing of `role`, `round`, trials or purchases; add role and round from memory and the paying events from attribution.

Also useful: `video_watched_6s` and `average_video_play`, plus the in-app event counts (for example `total_start_trial` and `total_subscribe`), which are TikTok's own attribution. Reports use the ad account's time zone. Page through results; one call does not return every row of a large account.

With TikTok's MCP server, find the reporting tool that returns ad-level daily metrics and map its fields to the table above. Ads Manager labels vary by language and version; map them the same way.

## Making changes

| Change | API |
|---|---|
| Pause or enable ads | `ad/status/update` |
| Pause or enable ad groups | `adgroup/status/update` |
| Ad group budget | `adgroup/budget/update`. The body takes a list: `{"budget": [{"adgroup_id", "budget", "budget_mode"}]}` |
| Spark ad | `ad/create` with a creative carrying `ad_format: SINGLE_VIDEO`, `tiktok_item_id`, `identity_type`, `identity_id`, `identity_authorized_bc_id`, a call to action and the MMP's click and impression tracking URLs |

Log every write request and response (in memory `history/decisions`) and read the object back afterwards. A 200 response with a non-zero `code` in the body is a failure.

## Views and Spark Ads

Once a post runs as a Spark Ad, its public view count includes paid impressions. Organic comparisons must use posts that never ran as ads, or views before the ad started ([measurement](measurement.md)).
