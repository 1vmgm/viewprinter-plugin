# Bulk review and conversation feedback

## Build a useful review surface

The HTML is for seeing the work. The conversation is for feedback. Do not add note textareas, fake approval controls or a second feedback system the user must maintain. Stable IDs let the user say “approve 01 and 04; give 03 new music; move every headline higher.”

Follow [review UI quality](review-ui.md) for the dark purple workspace and generated galleries. Use this skill’s shared `scripts/review_gallery.py` after reading this reference. A brand skill’s summary does not replace the review workflow. If a reusable control exists only in a project-local fork, port and test that narrow improvement in the canonical helper; do not let later batches silently lose it. Keep brand-specific titles, descriptions and assets in manifests.

Every card exposes the exact `ID / vN` as selectable text and a **Copy ID** button. Copy only that reference, so the user can paste it into conversation. Support local-file clipboard restrictions with selection-copy fallback and an honest manual-copy message if copying fails. Announce the result accessibly; never show “Copied” on failure.

Video/audio galleries include one global playback-speed control: **0.5×, 0.75×, 1×, 1.25×, 1.5×, 2×**, default 1×. Apply it to final previews, previous versions and input media, including media loaded after the choice. Changing speed never starts playback and preserves the one-player-at-a-time rule. Speed is for review convenience; sound/loop approval still needs normal-speed listening. Image-only galleries do not need playback controls.

## Keep one review sheet per ongoing format

The review belongs to the project’s format, not to the agent or skill file. A format without its own recipe file is still reviewable under the project’s existing content skill. Multiple agents contribute named batches to the same destination; see [format ownership and coordination](../../content-production/references/formats.md#multiple-contributors-one-review) for independent source manifests and revision-safe registration.

Resolve the format's existing review sheet from project memory, the active batch or the user's last review link before choosing an output path. Keep that stable hub destination and recognizable title as the format grows. The generated HTML location may change atomically between accepted revisions. New hooks, characters, feature demos, dates, production batches and one-item prototypes belong in the existing sheet; they do not create a new review destination. Create a separate sheet only for a genuinely separate format/project or when the user asks for one. Shared source libraries, tools or the word “meme” do not make two explicitly distinct formats one format. When the user corrects a format boundary, give that format its own named hub tab, remove its cards from the incorrect current sheet, and update its canonical paths in the brand skill and memory. Preserve media, versions and unrelated cards.

Add new items and update the current versions in your contributor-owned source manifest while retaining the earlier items, stable IDs, exact-version approval states and previous-version links. Use named batches to make the latest work immediately findable; within the selected batch, retain the status lanes below. A one-prototype approval checkpoint limits production, not the gallery's contents. Separate production directories are fine; reference their assets from the shared sheet.

Keep immutable round manifests and media as history, then register the updated source into the same format review. An archive is not the next handoff URL. Save the stable hub entry and contributor source paths with the format in project memory/carry-forward so a later session resumes them. If a stray new sheet was created, merge its items into the established sheet, preserve its history, and retire or redirect the stray entry point. Open and link the established sheet; do not present two competing current pages.

## Make the latest batch easy to find

Once a sheet contains several production batches, declare root `batches` in newest-first order, each with a stable `id` and a readable `label` (concept or date plus the reference range when useful). Assign every item a `batch` matching one of those IDs. The first declared batch is the default **Latest batch** view. Provide the shared renderer's **Latest batch**, **All content**, and named batch selector, with counts; do not make the user scroll through earlier work to find a new handoff. Keep earlier items in the same sheet.

Example: `"batches": [{"id":"coffee-oct02","label":"Coffee stories · C01–C09"},{"id":"workout-oct01","label":"Workout stories · W01–W10"}]`; each coffee item has `"batch":"coffee-oct02"`. Move a batch to the front only when it is the current review focus; don't infer recency from ID prefixes, filenames, version numbers, or status. The list controls batch order within each status lane, preserving manifest order inside each batch. Legacy manifests without batches keep their existing behavior.

Changing batches clears status/format filters, pauses hidden media, and updates visible counts. A direct item anchor must reveal its batch. Verify the initial latest view, switching groups, All content coverage, older-item links and narrow layout. The hub's `--all-current` check samples every current preview across batches, not just the default view. An HTML-only navigation change preserves all media versions, hashes and approvals.

## Plan review checkpoints before dependent production

When the user wants staged review, record a short checkpoint plan with: the decision to make, exact deliverables and versions, what feedback is needed, what can continue independently, and which dependent work follows that review. Store it in the project's batch inventory or a linked plan, not in the plugin.

Choose checkpoints by uncertainty rather than imposing every stage on every project. A useful progression can be direction/source assets, a representative execution, a complete draft, then final delivery. For a static asset, some of these may be the same artifact. A known format or an authorized unattended run can skip or combine rounds.

Make the deliverable sufficient to answer the decision. Stills can establish identity, setting and composition; motion/voice require playback; a complete narrative requires a complete cut; a product claim needs the actual UI or export. A short execution sample cannot establish the whole story's pacing. Prefer a reusable segment of the planned piece to a disconnected teaser.

Lead each round with the current reviewable assets and one short review focus. Keep future checkpoints in the batch plan rather than filling the gallery with empty cards for distant stages. If an asset is the decision, show it as the main preview. Supporting references and production metadata stay secondary.

Preserve exact-version decisions and unresolved feedback. An approved source image does not approve animation or final output. Continue independent preparation while a requested checkpoint is pending; do not execute work whose premise the user explicitly wanted to choose first. Conversely, never turn these recommended phases into new approval gates against existing authorization.

## Hierarchy and stages

Lead with the current decision, not a production report. Use a short title and one optional `focus` sentence. The content preview is the largest element. Each card needs only its ID/version, title, status and stage above the preview. Put the exact thing to judge in optional `reviewFocus` when useful. No empty metadata panels or long mandatory instructions.

For registered social content, the generator groups current items by their next action: Changes requested, Needs review, Descriptions to review, Ready to schedule, In production, then Scheduled. A verified scheduling handoff is terminal for the exact version and intended destinations, even when older creative flags lag; do not rewrite those flags as approval. Approved intermediate assets remain in production. The Content pulse excludes Scheduled from active work and opens a selected action across batches.

Standalone non-social galleries retain the generic Needs review / In progress / Complete creative lanes. They remain outside the social workspace.

Any other status fails the build with the allowed list; nothing falls into a section by default. Leave rejected or withdrawn items out of the manifest; the batch inventory keeps their history.

Stages: `concept`, `source`, `demo`, `edit`, `final`. Legacy manifests without a stage show “Stage not recorded”; don't infer a finished video from an approved character image. Pending statuses may omit `src` and show a short `nextStep`; don't substitute a reference image and imply it is the finished output. Empty sections disappear.

Starting any audio or video pauses all other players. Input assets, previous versions, changes, copy and tool/cost details are collapsed by default. Top controls open or close each category across all items, including filtered items, or expand everything/collapse all. Prompt expansion also opens its parent tool panel. These controls change the local view only; they are not approval controls. Keep input references attached to the item they support. If an input is itself the current review decision, make it the main card at `stage: source` and state the decision. Do not bury what the user must review inside an input drawer.

## Manifest

Paths are local filesystem paths relative to the manifest. The existing minimal item schema still works. Add details only when known and useful:

```json
{
  "title": "Product stories", "round": "02",
  "focus": "Review the opening and the product payoff.",
  "items": [{
    "id": "clip-003", "version": 2, "title": "Kitchen question",
    "format": "Interview", "status": "revised", "stage": "edit",
    "kind": "video", "src": "media/clip-003-v2.mp4",
    "poster": "media/clip-003-v2.jpg",
    "reviewFocus": "Does the payoff answer the question?",
    "changes": ["Longer opening read"],
    "previous": {"kind": "video", "version": 1, "src": "media/clip-003-v1.mp4"},
    "inputs": [{"label": "Opening reference", "kind": "image", "src": "inputs/kitchen.png"}],
    "generation": [{
      "asset": "Character performance", "platform": "Generation provider", "model": "Recorded model/version",
      "jobId": "saved-job-id", "prompt": "Exact prompt when useful",
      "cost": {"status": "unknown"}, "note": "Reused from the approved prototype"
    }]
  }]
}
```

`kind` supports image, video and audio, including inputs. `generation` is one record per generated asset/job being described. State the actual platform and model; if one was not retained, say “not recorded.” Reused assets retain original provenance; label reuse in `note`, not as a new generation or new charge. Do not include credentials, signed URLs or whole raw API payloads in the gallery.

Cost is `{status: reported|estimated|unknown, amount, unit}`. Amount/unit are required for reported and estimated costs; for unknown omit them. Use the actual unit (`credits`, `USD`, etc.). A returned price estimate is not a charged amount. Keep platform costs separate and never sum a shared job multiple times across reused assets. The gallery deliberately does not calculate a batch total from repeated item rows. Record failures/retries in the production ledger; selected-asset rows are not a full account-spend audit.

Optional root `balances` entries contain `platform`, `amount`, `unit`, `asOf`. These are labeled snapshots with their observation times; omit them when unavailable. Never derive a remaining balance from a theoretical price or display an old receipt as live. Prefer a per-asset cost over a prominent financial dashboard.

Before gallery handoff, probe the encoded deliverables for actual width, height, duration and expected audio/video streams; compare them with the brief. A correct project canvas or preview does not prove the export used those dimensions. If a source-media profile overrides the canvas, correct the editable project or source preparation and render again so text and overlays are produced at delivery resolution. Record the tool defect and the measured before/after result; merely enlarging an undersized finished export does not validate a full-resolution render.

For an audio-led brief, final delivery includes the selected audio in the current preview unless the user chose platform-native placement. Before carrying a sound dependency into another round, reread current project instructions and existing user authorization. Do not repeat a resolved permission question or label a picture-only edit final. When listening is unavailable, record that precise review limit while completing the authorized local mix; listening uncertainty alone does not justify withholding the finished files.

Generate with `review_gallery.py --manifest <review.json> --output <review.html>`. The page is local and read-only; it does not save approvals or upload anything. It replaces the output file whole, so a failed build leaves the previous gallery intact. Check the final page in a browser at desktop and narrow sizes, including Copy ID, clipboard fallback, global speed on later-loaded media, filters, disclosures, and one-player-at-a-time behavior. Ensure hidden source/previous videos do not all preload with the main previews. Keep older round manifests and media immutable. For carousels, use stable slide IDs and retain parent/order; grouped carousel navigation is not implemented in this helper. Check pages headless (`review_hub.py check`), never in a window on the user's desktop; if that is unavailable, report the limit.

## Present through the ViewPrinter workspace

Follow [workspace](workspace.md) for explicit registration, scope, progress, native-copy fields, archive/restore, migration and local HTTP boundaries. The single browser tab is branded **ViewPrinter · Content**, with format reviews in Content and profile/asset briefs under Account Groups.

Maintain the existing project + format ID and direct hub link. Keep source manifests independently owned; let the shared runtime generate the canonical index. New batches, prototypes and revisions belong in that format. Register only declared social content; App Store and unrelated deliverables stay in standalone project reviews. Keep other agents' entries available. Reconcile every completed item/current version, cover, prior version and platform description before reporting coverage; distinguish total content from items needing review.

Run `review_hub.py ensure`, then `review_hub.py check <entry> --all-current --seconds 2`. Use the existing visible tab; `review_hub.py open` opens one only if none is connected. Do not make separate browser windows for a new batch. A rebuilt gallery gets an Updated reload control. Leave the server running. Headless decoding verifies media loading, not listening or creative approval.

Archive removes work from active review without touching publication schedules. Use `archive`/`restore`, never the retired `posted` command. Historical review snapshots and media remain immutable while the current format can continue growing.

## Scheduling is the review finish line

Add `"delivery": {"snapshot": "delivery.json", "timezone": "America/Chicago"}` to the social gallery manifest, using the project's timezone. Record the complete intended account/workspace targets, exact item/version, native descriptions, copy revision and media hash. Initialize missing snapshots with `{"placements": []}`. No verified receipt means completion is unknown; never infer it from a planned time or approved creative.

After an accepted save, use ViewPrinter's `learn.py link` for each destination, save dated readbacks and run:

```sh
python3 scripts/review_delivery.py --memory <project>/.viewprinter/content-memory \
  --posts <saved-posts-list.json> --output <gallery-folder>/delivery.json
python3 scripts/review_gallery.py --manifest <review.json> --output <review.html>
```

Repeat `--posts` for paginated readbacks. Match exact post/account and item/version links, never captions. `review_readiness.py` derives the next action and preserves the accepted scheduling handoff. Published evidence can establish a past handoff, but creates no additional Posted lane. Later delivery failures and performance belong in ViewPrinter; they do not reopen completed review work. A new version, new required destination or changed approved copy/media needs its own matching handoff. Partial scheduling leaves the remaining work active.

Do not poll publication status to maintain this page. Keep dated receipts for provenance, preserve historical delivery fields for learning, and show only actionable review/scheduling states. The local browser makes no ViewPrinter API calls. See [workspace](workspace.md) for scope and the completion rules.

## Process each feedback round

1. Save the user's original words as an immutable feedback event with batch/round and source time.
2. Translate them into targets, versions, operations, scope and exceptions. Resolve “all” against the batch/format the user is reviewing, not every project asset. Preserve uncertainty rather than guess destructive changes.
3. Acknowledge a compact action list when useful, then perform authorized revisions. Don't ask the user to retype feedback into HTML.
4. Preserve approved versions; create new versions for changes. Example: “approve 01, then raise every title” approves 01's displayed version but changes its next version. Record both; the new result isn't automatically user-approved. An explicit instruction to finalize those changes without further review can authorize delivery, and should be recorded as such.
5. Apply shared feedback consistently across affected items. Exclusions and protected invariants are explicit. A different song for one item isn't a new music policy for the whole brand.
6. Respect “do not remake”: skill, planning or gallery feedback alone does not authorize changing protected media. An HTML-only update keeps the same media versions/hashes, advances the gallery round, and records future production guidance separately.
7. Register the updated source into the format’s canonical review with the latest batch selected, concise changes and optional before/after; retain the earlier items and version history. Report remaining questions and what is ready.

Suggested batch inventory: `id`, `formatRevisions`, `currentRound`, `owner`, `items` with stable ID, current version, status, output path/hash, feedback references, and approval references. The gallery manifest is a round-specific view of that inventory, not a competing approval database. Update its statuses from the inventory.

## Keep feedback and outcomes separate

“Looks great” is creative approval. “Post these tomorrow” is a publishing request to resolve through the content-publishing skill. “It got 10k views” is reach evidence whose platform, source, date, trial/ordinary context and age matter. Installs, subscriptions and paid efficiency require their own attributable evidence. Avoid treating a liked design or one successful post as a universal rule.
