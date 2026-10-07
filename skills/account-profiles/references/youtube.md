# YouTube

Official sources checked 2026-10-05 (America/Chicago); see the `yt-*` fact rows.

Record the stable connected channel ID, handle, owner/Brand Account context when
known, and Studio feature eligibility. Never create a second channel merely because
one existing channel serves several content groups. Share its identity/asset decision
across those groups.

- Channel profile links: up to 14, with the first emphasized. Configure in Studio →
  Customization → Profile → Links. A first link titled for its destination/action is
  usually sufficient. `yt-links` records the official rule.
- Shorts description/comment URLs are not clickable. Channel profile links work.
  A Short's related-video link points to a public/unlisted video on that same channel,
  requires advanced features, and is added in Studio (`yt-short-related`). It is not
  an arbitrary external app link.
- Phone verification grants intermediate features. Advanced features require phone
  verification plus sufficient channel history or ID/video verification where offered.
  Only the primary owner can verify identity; see `yt-unlocks`. Keep monetization,
  subscriber thresholds, a public verification badge and these features separate.
  Inspect Studio → Settings → Channel → Feature eligibility for actual state.
- Banner: recommend 2560×1440; minimum 2048×1152; file ≤6MB. Official text/logo safe
  area is 1235×338 **at the minimum dimensions**. Proportional scaling is a calculation,
  not another official spec: at 2560×1440 use a centered conservative 1543×422 zone.
  Verify Studio's device previews after upload. `yt-branding` records this distinction.
- Profile image: official guidance permits JPG/GIF/BMP/PNG, no animated GIF, ≤15MB;
  it renders at 98×98. A larger square master is a production choice. No tiny text.

Post description/title limits come from the live ViewPrinter schema (5,000/100 in
this observation), not the channel-description field. Keep the channel description
concise and verify its native editor limit. For Shorts overlay text, use a project
layout guide and actual UI review; banner safe areas do not apply to video content.

## Banner handoff check

Do not present a Facebook cover as a reusable YouTube banner merely because both
are 16:9. The canvas and the area surviving the smallest device crop are different
checks. Give platform exports explicit filenames, titles and download labels.
Place the actual central all-device crop first in the review, with full TV artwork
secondary. Measure both complete headline lines (including descenders and contrast
edges) in the final export; retain a useful inner margin and verify the Studio preview.
Use the renderer's `cropPreview` for a labeled source-pixel simulation. A requested
generation size or a full-image preview does not validate the output or saved crop.
