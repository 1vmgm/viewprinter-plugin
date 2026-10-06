# Connections

The method needs four sources of truth. The user brings their own ad-platform, attribution and revenue access. ViewPrinter does not proxy ad accounts, and this skill never asks for credentials in chat.

## Check what the session has

List the available tools before planning anything. Look for:

- **ViewPrinter:** `posts_list`, `accounts_list`.
- **TikTok Ads:** tools that return ad-level reports and change ad status or ad group budgets. They may come from TikTok's official MCP server or a third-party server. Alternatively, a local script can call the Marketing API with the user's own stored token.
- **Attribution:** an MMP's reporting tools (AppsFlyer, Adjust, Branch, Singular, Kochava), or web analytics that carry TikTok click IDs.
- **Revenue:** a subscription platform (RevenueCat, Superwall, Adapty), store reports (App Store Connect, Google Play), or checkout (Stripe, Shopify).

A server listed as configured but failing to connect is a broken connection. Tell the user it failed so they can fix it. Don't report it as missing, and don't route around it with guesses.

## 1. TikTok Ads (required)

What the skill needs:

- **Read:** per ad, per day: spend, impressions, clicks, video plays and 2-second views, plus the ad's name, ID, ad group and status.
- **Act:** pause and enable ads, change ad group budgets, create Spark ads from existing posts. This is optional; without it the user applies the changes.

Ways to connect, in order of preference:

1. **TikTok for Business MCP server.** TikTok's official remote server, launched in 2026. TikTok's guide describes signing in with the TikTok for Business account, with no developer app or API key. As published by TikTok:
   - `https://business-api.tiktok.com/open_mcp/tt-ads-mcp-flat`: the full tool set, suited to large-context clients.
   - `https://business-api.tiktok.com/open_mcp/tt-ads-mcp-layer`: core tools first, the rest discovered on demand.

   Add it as a remote HTTP MCP server in the client, then complete the browser sign-in. In Claude Code, for example: `claude mcp add --transport http tiktok-ads <url>`, then `/mcp` to authenticate. Check TikTok's current guide before connecting, because URLs and tool names change. The signed-in user must have access to the advertiser account that runs the campaign.
2. **Marketing API directly.** Needs a developer app approved for the Marketing API, an access token authorized for the advertiser, and the advertiser ID. The user stores the token in their own credential file or environment. The endpoints this skill relies on are in [TikTok](tiktok.md).
3. **By hand.** The user exports an ad-level custom report from Ads Manager as CSV (columns in [TikTok](tiktok.md)) and applies approved changes themselves. Analysis works fully in this mode; the handoff is an exact change list.

For Spark Ads from several accounts, each posting account must be authorized to the Business Center **and** assigned to the ad account. The second step is the one people miss: an account can be linked to the Business Center and still not be selectable in the ad account.

## 2. Attribution (strongly recommended)

What the skill needs: paying events per ad (trial starts and direct purchases, separately), with revenue if available, by day.

- **Apps:** an MMP with TikTok as an integrated partner, reporting in-app events at ad level. Check that the paying event is posted back to TikTok as the optimization event (see [TikTok](tiktok.md)).
- **Web:** the TikTok Pixel with the Events API, plus the site's own analytics or checkout records that keep the click ID.

**Without it:** TikTok's own conversion count is the only count. It is self-attributed and partly modeled. Use it to rank ads inside the same campaign. Don't compute ROAS for scale decisions on it alone, and say so in every report.

## 3. Revenue truth (recommended)

What the skill needs to build the value model ([economics](economics.md)):

- Prices.
- Trial-to-paid rate and refund rate.
- Store or processor fees and taxes withheld.
- Expected renewals within the chosen horizon.

**Without it:** the user states these numbers. Record them as assumptions with a recheck date, and label every ROAS provisional until measured values replace them.

## 4. ViewPrinter (MCP server)

Supplies the organic pool: which posts exist on which accounts, their views and native insights, and media for deduplication. If the tools are not signed in, follow the connection guidance in the content-publishing skill: OAuth only, and there is no ViewPrinter API key. Without it, the user provides post links and the skill builds the pool from them.

## Operating modes

| Mode | Needs | Can do |
|---|---|---|
| Full | TikTok Ads read and write, attribution, revenue | Every decision, executed after approval |
| Recommend | TikTok Ads read (tool or CSV), attribution | Every decision as an exact change list the user applies |
| Directional | TikTok Ads read only | Engagement cuts, starvation reads, relative ranking. No ROAS, graduation or scaling calls |

State the mode at the top of the first report and whenever it changes.

## Explaining a gap

Keep it to one block, then carry on with what works. For example:

> To judge ads on revenue I need your attribution data, meaning which ad produced each trial or purchase. That comes from your MMP (AppsFlyer, Adjust, Branch or Singular) with TikTok as a partner. If it has an MCP server or API you can connect here, I'll read it directly; otherwise export trials and purchases by ad for the same dates. Until then I can rank ads on engagement and TikTok's own conversion count, but I won't recommend scaling anything.

Don't lecture, don't list every option when one fits, and don't stop the session over a missing source that the current question doesn't need.
