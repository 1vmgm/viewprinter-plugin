# Instagram

Research attempted 2026-10-05 (America/Chicago). Fact IDs below are in `research.json`.

Record native subtype `personal`, `creator`, `business`, or `unknown`; do not equate
the connector's login path with a verified subtype. Keep connection capabilities
separate from features visible in the Instagram app.

- Profile copy: `ig-copy` records ViewPrinter's observed 150-character bio and
  30-character username limits; post captions have their own 2,200 API limit.
- Links: `ig-links` retains the official profile-link help URL. It was inaccessible
  in this research pass. The reported five-link allowance and absence of a follower
  gate still need direct confirmation; do not mark an account unlocked from this.
  Inspect Edit profile → Links, add the main destination as the first link when
  available, and record its exact title and saved URL. Plain bio/caption text and a
  dedicated clickable link are different fields.
- Story link stickers, contact buttons and partner action buttons are separate
  placements. Check the actual account and current official instructions before
  promising a button or a follower threshold. `ig-professional` records the pending
  native subtype/source check. No subscription or account switch should be purchased
  or performed just to complete a profile audit.
- Avatar: use a square master and preview a circle at small sizes. This is a design
  recommendation, not a verified upload minimum. Instagram has no banner field in
  this brief; do not turn a feed cover into a profile banner.
- ViewPrinter reports 1080×1920 for Reels and Stories; its Story note reserves 250px
  at top/bottom (`ig-story-guide`). Do not apply that Story note as an official Reel
  safe area. Review captions/actions and profile-grid crop separately on a current app.

Profile review should include name, handle, bio, category visibility if available,
ordered links, avatar, pinned content and the first visible grid. Mark unobserved
fields unknown. Publishing can work while analytics permissions need reconnecting.
