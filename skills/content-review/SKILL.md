---
name: content-review
description: Present work for the user's review in the ViewPrinter workspace — the local review hub kept open in one browser tab. One review per project and format, influencer or account group; batches newest first; creative approval, native-copy readiness and delivery tracked up to verified scheduling. Use whenever prototypes, batches, revisions or account-profile proposals need the user's review, or the user asks what is ready.
---

# Content review

Everything the user reviews lives in one local workspace, **ViewPrinter · Content**, served from this machine and kept open in a single tab. Content formats come first; account groups and the archive are secondary. The local workflow ends at verified scheduling: delivery and performance are managed in the ViewPrinter product.

## Keep one review per project and format

Follow [review](references/review.md) and [workspace](references/workspace.md): reuse the running localhost hub, maintain one canonical review per project + format or influencer, and name your format with its direct hub link. Content is the pulse of unfinished review work. A format is active while included current content remains unscheduled. App Store and other product-listing work stays in standalone project reviews. Reconcile all session batches and prototypes, then verify every current preview over HTTP before reporting coverage. Keep other agents' registered galleries available in the same hub.

For all review presentation changes, follow [review UI quality](references/review-ui.md): a sharp dark workspace, restrained purple accents, aligned review queues, media-first galleries and verified narrow layouts are the shared default.

## Build the gallery

Read [review and iteration](references/review.md) before building a review page, even when a project skill summarizes the gallery requirements. Resolve and reuse the format’s existing review sheet, registering prototypes and later batches under that same project + format ID; see [review continuity](references/review.md#keep-one-review-sheet-per-ongoing-format). Keep contributor-owned source manifests separate and register them into the shared format review with this skill’s `scripts/review_gallery.py`. Don't fork a custom gallery. The review helpers ship with the plugin: don't edit an installed copy, which an update replaces. When a reusable control is missing, use what exists and tell the user the gap; changes to the helpers belong in the plugin's own repository. Keep stable IDs and versions, a Copy ID button per card, and global playback speed for video/audio. For a sheet spanning batches, declare named batches newest first: open on Latest batch and offer a batch selector plus All content. Lead with the next review action, separate work in production, and show Scheduled as the final state for social content. Creative approval and native-copy readiness remain separate prerequisites; do not keep scheduled items on the active review list because older flags are stale. Show the production stage; keep input assets, previous versions, generation platform/model, prompts and per-asset costs in compact disclosures below the main preview. Distinguish reported costs, estimates and unknown charges; never guess credits or present a stale balance as live. One video plays at a time, nothing autoplays. No notes boxes, approval forms or required in-page feedback: the user reviews visually and gives feedback in conversation.

```sh
python3 <skill-directory>/scripts/review_gallery.py --manifest <owned-review.json> --output <owned-review.html>
# For a changed registered source, also pass --source-revision <observed-revision>.
```

A gallery joins the workspace only inside a ViewPrinter project: a folder with `.viewprinter/content-memory`. For a project without one, run content-production's `scripts/memory.py init --project <project-root> --name <project-name>` once; the generator says so when a gallery is outside a project.

## Present it in the workspace

Present social galleries through the [workspace](references/workspace.md), the one page the user keeps open. Declare `reviewHub.kind: social-content` and a stable format ID; generic HTML is not automatically registered. `review_hub.py` manages typed entries, accurate progress and reversible archives. Never open a gallery in a new browser tab or window. Before handing off, verify every current preview with `review_hub.py check <entry> --all-current --seconds 2`, which samples each one in a throwaway headless Chrome; writing the HTML alone does not complete this step, and a hidden automation tab never loads media. Name the project/group and exact hub tab in the handoff, link its stable hub URL, and report the reconciled completed-content count. Keep the shared server running for review. If verification is unavailable, state the specific limit; do not silently host private assets on a public site.

## Account groups

The [account profiles](../account-profiles/SKILL.md) skill registers a group's review here with `--kind account-group`; see [workspace](references/workspace.md#explicit-registration). A local group review never changes ViewPrinter's remote destination groups or scheduled posts.

## After review

Feedback arrives in conversation, and the skill that made the work acts on it: [content production](../content-production/SKILL.md) for content, [account profiles](../account-profiles/SKILL.md) for accounts. Approval belongs to an exact version. Scheduling goes through [content publishing](../content-publishing/SKILL.md).
