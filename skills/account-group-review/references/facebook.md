# Facebook

Research checked/attempted 2026-10-05 (America/Chicago). See `fb-access`, `fb-button`,
`fb-cover`, and `fb-copy` in `research.json`.

Separate a **Page** from a personal profile or profile with professional mode. Match
the connected Page ID and account ID, not its display name. A public vanity URL or
redirected public profile ID can differ from the connector's Page ID; retain both
with evidence instead of rewriting the destination ID.

Record Page name, username if any, category, bio, About fields, website, action button,
avatar and cover. ViewPrinter currently reports 255 for Page bio; this is tool evidence
for that field, not a verified limit for every Facebook intro/About editor. Keep copy
short and inspect the owner editor's actual counter before saving.

An action-button edit requires Facebook access to the Page (`fb-button`); task access
and publishing API permissions are not proof of that access. Record the available
button choices and their destinations. Propose Learn more with the main website only
if that choice is available. Other buttons may depend on category, partners or region.
Do not describe every Page CTA as automatically unlocked by a follower milestone.

The official cover-dimensions page was inaccessible during this pass (`fb-cover`).
Treat planned desktop/mobile crops as simulations. Use a large master; keep essential
content central and clear of the profile picture. Inspect actual desktop and mobile
saved crops before confirming the cover. A feed link-preview image is not a Page cover.

Current ViewPrinter publishing uses videos as Reels and accepts images separately.
Read the live schema before composition. Native Facebook website/action-button links
are profile edits, not post scheduling options.
