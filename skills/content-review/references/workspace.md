# ViewPrinter local workspace

Use this for registering social reviews, tracking review, native copy and scheduling handoff, and archiving work. Runtime code and UI assets ship together in this skill. No credentials or external API calls are needed by the local server.

For presentation changes follow [review UI quality](review-ui.md): shared dark mode and purple accents, with desktop and narrow validation.

## Scope and navigation

The single browser tab opens **ViewPrinter · Content**. Content formats are primary; Account Groups and Archive are secondary. One canonical review destination per project + format; independently owned batch manifests contribute to its generated index. Search includes titles/hooks, item references, batches and account names. The Content overview is a pulse: actionable counts, an Up next review, and active formats ordered by next action. Scheduled formats have a separate completed view; search can still find them. Inside a format retain Latest batch, All content, Copy ID, speed, previous versions and provenance.

App Store screenshots, product-listing packages, website design and unrelated documents stay in their own project directories with a standalone index. Rendering HTML does not register it automatically. Never add those deliverables just because a gallery helper can display them.

## Format identity and contributors

Use one shared server across projects and agents. Runtime v5 groups social contributions by persisted project identity + stable `formatId`, not HTML path. Read the project's content skill and reuse its existing format ID. Different dates, creators, treatments, tools and agents do not create another format. Each source manifest has one writer; sources may live in separate production directories. See [develop project formats](../../content-production/references/formats.md).

Project identity is stored as `reviewProjectId` in `.viewprinter/content-memory/config.json`. `contentSkill` optionally names the project's one content skill relative to its root. A format's optional `recipeRef` names its own reference. These links appear under Format details; missing recipe files do not prevent review. Moving or cloning a project with an already registered identity requires explicit reconciliation.

The registry record lists `sources` with each source's manifest, owner and revision. Generated manifests/HTML live in `.viewprinter/content-memory/reviews/<formatId>/`; do not edit or register those generated files as contributions. The stable hub link stays the same as generated files change. Only an accepted registration updates content; another agent's on-disk draft is not silently imported. Missing sources are reported while their last accepted review remains available.

Influencers have a separate identity (`kind: influencer` + `influencerId`), using the same contribution/review machinery. Multiple influencers can coexist without being formats. See [influencer management](../../content-production/references/influencers.md). Their historical reviews appear within the active influencer’s history; retirement remains explicit.

## Explicit registration

Declare this in each contributor-owned social review manifest; use unique batch and item IDs within the format:

```json
{"reviewHub":{"kind":"social-content","formatId":"product-demo","entry":"example--product-demo","projectId":"example","owner":"current-task","variant":"Live action","recipeRef":".agents/skills/example-content/references/formats/product-demo.md","accountGroups":["example--people-accounts"]}}
```

`review_gallery.py --manifest review.json --output review.html` registers only a declared `social-content` review inside a project with `.viewprinter/content-memory`. `VIEWPRINTER_REVIEW_HUB=0` renders standalone; `VIEWPRINTER_REVIEW_AUTOSTART=0` registers without starting. Registrations with the same project + format ID join one review automatically. Alternate entry names become aliases. The generator exits with an error if hub registration fails, and says so when the gallery is outside a project, where nothing is registered; a standalone HTML success is not a completed social handoff.

For an update, first read the source revision from the registry or `/api/queue`, reread the source manifest, and change only owned work. Pass that observed value with `--source-revision N` to `review_gallery.py` or `review_hub.py add`. Alternatively set `reviewHub.sourceRevision` to N+1 in the edited source. New sources need no revision. A stale update fails without replacing the accepted review; refresh and reconcile rather than blindly incrementing. Repeating an unchanged source adds no duplicate items. Changed media for the same item/version is rejected: make a new version. Conflicting item or batch IDs from different sources require resolution.

Import scheduling receipts into the source's existing `delivery.snapshot`. The workspace refreshes its accepted aggregate when that receipt file changes. Receipt observation times and exact-version checks remain intact.

Other registered reviews use explicit commands (paths are examples):

```sh
python3 scripts/review_hub.py add /project/format/review.html --manifest /project/format/review.json --kind social-content --format-id product-demo --name example--product-demo --owner task-name
python3 scripts/review_hub.py add /project/accounts/review.html --manifest /project/accounts/group.json --kind account-group --format-id people-accounts --name example--people-accounts
python3 scripts/review_hub.py ensure
```

Account-group rendering uses the account-profiles skill. The local group does not change ViewPrinter's remote destination groups.

The registry lives under `~/ViewPrinter/.hub/entries`; `in-review` retains Finder shortcuts. `VIEWPRINTER_REVIEW_ROOT` and `VIEWPRINTER_REVIEW_PORT` override defaults. Registry writes are locked and atomic. UI lifecycle writes require the revision the user saw; a conflict requires refresh, not blind retry. Each source has a separate optimistic revision, so unrelated contributors can register concurrently. Registry publication is atomic after a complete generation is rendered. Batch archive state is held at the format level and survives later source registrations.

## Review ends at scheduling

Each exact item/version can declare:

```json
{
  "id":"A01","version":2,"status":"approved",
  "sha256":"sha256-of-final-media","copyRevision":3,"captionStatus":"approved",
  "captions":{"instagram":{"caption":"Instagram-native description"},"youtube":{"title":"Short title","caption":"YouTube-native description"}},
  "distribution":{"targets":[{"organizationId":"workspace-id","accountId":"account-id","platform":"instagram","accountName":"@handle"}]}
}
```

Use `captionStatus: approved` for version-specific approval or `finalized` for copy finalized under existing publishing authorization; retain the corresponding evidence. `captionsByAccount` supports different copy for two accounts on the same platform. A target explicitly withdrawn from a plan requires `state: withdrawn` and a reason. Excluding an entire prototype uses `distribution: {status: excluded, reason: ...}`. Cancellation alone does not fulfil a destination. A media revision is a new item version; copy changes increment copyRevision.

- **Active format**: at least one included current item remains unscheduled. Show its next action: review, requested changes, native descriptions, production or scheduling. Empty and explicitly excluded work do not inflate the active count.
- **Scheduled**: every included current item has a verified accepted handoff for every intended workspace/account. This is the final review state. Published evidence also establishes a completed handoff, without a separate Posted state.
- Partial or unverified scheduling remains active. A proposed time is not a receipt. An approved intermediate source is still production; Ready to schedule requires an approved creative and finalized/approved native copy. Destination selection can be completed during scheduling, but an unknown plan cannot establish completion.
- `handoff` retains accepted receipt fields and their original observation time. Later publication/failure observations do not reopen this review; delivery and metrics are managed in ViewPrinter. New item versions, added required destinations and changed copy/media require matching scheduling evidence. Never infer approval from scheduling or change old creative flags merely to match the dashboard.
- Archiving is an independent organization choice. Scheduled formats remain findable and automatically become active when new unscheduled content is added. No automatic archive or remote mutation occurs.

Use ViewPrinter's posting/read workflow to record scheduling evidence, then import sanitized exact-version receipts with `review_delivery.py`. `review_readiness.py` calculates the pulse and gallery states. The browser never contacts ViewPrinter itself. A saved `posts_list` envelope should include `observedAt` and `posts`; import time is separate. Re-importing an old receipt must not make it freshly verified. Legacy undated receipts use file mtime and label that limitation. There is no ongoing publication-monitoring requirement for this workspace.

The receipt importer retains the existing conservative removal behavior for learning records; those live delivery details are not the review UI:

A missing target may be marked removed only when that post is present in a complete, unfiltered target read:

```json
{"observedAt":"2026-10-05T18:00:00Z","readScope":{"completeTargets":true,"accountFilter":false,"postIds":["post-id"]},"posts":[]}
```

The empty example does not remove anything: the matching post must actually be present. Partial pages and filtered account reads cannot remove targets. Retain removal evidence and a separately reasoned change to intended placement if a destination is moved.

## Archive, restore and migration

Archive/Restore controls and CLI preserve IDs and schedules. Archiving freezes the HTML, manifest and referenced media into a content-addressed local snapshot (copy-on-write where supported; never mutable hardlinks). Originals stay put. Archive may take time for a large format. Do not add it as a routine approval gate.

```sh
python3 scripts/review_hub.py archive example--product-demo --reason "Finished this format"
python3 scripts/review_hub.py archive example--product-demo --batch october-hooks --reason "Batch complete"
python3 scripts/review_hub.py restore example--product-demo
python3 scripts/review_hub.py restore example--product-demo--batch-october-hooks
```

`posted` is retired; import receipts to establish scheduling completion. Archive remains searchable without an age cutoff. A format archive explicitly puts the whole format aside; registration cannot silently revive it. Restore recomputes current readiness. A batch archive affects only that batch; restoring rejoins the same parent. Historical reviews are immutable snapshots with a date and parent link, not retired formats. Open their current parent rather than restoring a duplicate. Recipes and shared guidance are preserved; scheduling never implies archive.

For an older hub, run `migrate` for a dry run, inspect kinds/exclusions, then `migrate --apply`. It preserves old entry hashes and historical aliases; legacy Posted entries become historical reviews with scheduling handoff unverified; this does not retire their current parent. Unknown HTML stays unclassified, not silently social content. Migration writes a before receipt under `.hub/migrations`; preserve it for rollback. Use `rollback-migration <before.json>` only before newer registry edits; it refuses to overwrite work created after migration. Snapshot media is retained during rollback.

For legacy path-based registrations, use an explicit JSON mapping: `{"formats":[{"entries":["old-live","old-motion"],"entry":"project--product-demo","formatId":"product-demo","label":"Product demo"}]}`. Preview with `review_hub.py reconcile-formats mapping.json`, then apply the authorized mapping with `--apply`. All original source manifests/media stay in place. Old entry links alias the combined format, selecting their source where available. The migration writes before/after receipts; `rollback-formats <receipt-directory>` refuses to overwrite later changes. Do not infer migrations from similar labels.

`ensure` checks the loaded runtime signature; an older process cannot masquerade as current code. After an authorized update, stop and ensure once, then refresh the existing tab. Leave the server running at handoff.

## Served files and handoff checks

The server binds loopback and permits only review HTML/CSS/scripts inside registered review folders, plus supported media in their project roots. Project JSON, credentials and arbitrary documents remain blocked. `/guidance/<entry>/project` and `/guidance/<entry>/format` expose only explicitly linked Markdown inside that project; links are revalidated on each request. A manifest may explicitly list public artifacts in `downloads: [{id, title, path}]`; contained JSON/CSV/ZIP/Markdown/PDF artifacts are available through `/downloads/<entry>/<id>`. Do not list files with secrets.

Verify the served overview, exact format link, current media, controls and downloads. Use `review_hub.py check <entry> --all-current --seconds 2` for media decoding; separately listen when audio quality is in scope. Check desktop and narrow layout without opening extra user-facing tabs. Name the format and direct `http://127.0.0.1:8765/#entry` link in the handoff. Do not change publishing, profile assets or campaign membership merely to make a dashboard status look complete.
