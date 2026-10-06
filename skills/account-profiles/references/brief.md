# Persistent group brief

Keep account data in the project, outside the skill. Start from `templates/group.json`.
The renderer accepts any nonempty accounts array, including multiple accounts on one
platform; no platform count or complete platform set is required.

- `id`, `title`, `revision`, `checkedAt`, `timezone`, `status`, `focus`: stable identity
  and decision. `remoteGroup` can be null without blocking local review.
- `accounts[]`: human reference `ref`; exact `accountId`, `organizationId`, `platform`,
  `handle`, `url`, `role`, `nativeType` (unknown allowed), `sharedWith`; `current` and
  `proposed` fields; `connection`, `features`, `actions`, `assetIds`.
- `current`: observed name/bio/website plus evidence/time. Null means unobserved.
  `proposed`: name, bio, website, linkTitle, optional bioLimit/countUnit, change note.
  Do not conflate video-caption and channel-description limits.
- `application`: optional per-account update status, separate from connection health.
  Use `status`, human `label`, `note`, `reportedAt`, `reportedBy`, and evidence.
  An owner saying the account is updated can be recorded as `applied-unverified`
  with label “Updated · owner confirmed”; reserve `live-verified` for an actual
  saved-profile observation. Preserve older current-field snapshots and synchronize
  shared account IDs across groups. Do not infer that other same-platform accounts
  were updated.
- `features[]`: label, placement, state, requirement, action, evidence, checkedAt.
  States: enabled / disabled / eligible-unverified / unknown / not-applicable.
- `assets[]`: id, title, local src, kind (avatar/banner/guide), dimensions, sha256,
  provenance, note. Guides are review-only, never default upload files.
- `featuredAssets`: optional asset IDs to show before account metadata when artwork
  is the current decision. Assets may add `ref`, `version`, `status`, `reviewFocus`,
  `reviewLinks` (title/url) and `previous` (title/src). Preserve asset versions
  independently from the overall group revision; make prior artwork accessible.
  Context and previous-version links remain available in the ordinary asset grid
  when the current decision is copy and the asset is no longer featured.
- `sections`: optional title/text/items summaries; text preserves deliberate line breaks.
- `content`: ready counts, inventory/review/copy links, cadence proposal and existing
  shared-account reservations with observedAt. Approval does not imply scheduling.
- `sources[]`: title/url/status/checkedAt/note for this review. Snapshot relevant
  generic fact rows separately if needed; do not copy account data into the skill.
- `history[]`: revision, original feedback/evidence, changes, application/approval.
  Archive under `history/` before changing the current manifest.

Unknown current copy and native feature states stay visible. Optional keys may be
omitted. Asset paths are relative to the manifest, must exist, and cannot escape the
bundle. Output HTML stays beside the manifest so downloaded bundles remain portable.
No credentials, identity documents or signed source URLs belong in HTML.

Shared accounts reference the owning identity brief. Field/version creative approval
and application remain separate: proposed / approved / applied-unverified / live-verified.

- Featured banner assets may use `downloadLabel` and a measured `cropPreview` with
  `x`, `y`, `width`, `height`, `sourceWidth`, `sourceHeight`, and `label`. The crop
  uses source pixels and displays before the full artwork. Record its platform and
  whether it is a local simulation or an observed saved crop; verify export dimensions.

## Shared account identity

Match organizationId + accountId, never display name. For an account in multiple local groups, keep one project-owned JSON record and point each account's `identityRef` to it (relative to group.json). Keep group role, ref, actions and content lane in the group. The shared record owns identity/proposed copy/application state and canonical asset revisions:

```json
{"schemaVersion":1,"revision":1,"identity":{"organizationId":"workspace-id","accountId":"account-id","platform":"youtube","handle":"@example","url":"https://www.youtube.com/@example","current":{"name":"Example"},"proposed":{"name":"Example"}},"assets":[{"id":"channel-banner","src":"assets/banner.jpg","sha256":"verified-sha256"}]}
```

An account can declare `assetBindings: {"youtube-cover":"channel-banner"}`. The renderer resolves the shared identity, verifies the asset hash and materializes immutable content-addressed copies inside each review bundle. Copy revisions and application evidence are authoritative in the shared record, not independently edited in each group. Both identity and asset source must stay in the same project marked by `.viewprinter/content-memory`. Preserve owner-confirmed state; do not downgrade it because a different group is older.

After changing a shared record, increment its revision, rebuild every referencing group and verify both served reviews. Save immutable previous manifests and shared record revisions. The exported group JSON includes resolved identity values; the source group retains identityRef for future builds.

Register with the content workspace's `review_hub.py add review.html --manifest group.json --kind account-group --format-id <group-id> --name <stable-entry>`. This is a local grouping operation, not a change to ViewPrinter's remote accounts or campaigns.
