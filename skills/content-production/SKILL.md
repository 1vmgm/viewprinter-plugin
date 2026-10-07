---
name: content-production
description: Turn a completed research brief or established creative direction into content through concept and format development, representative previews, batch production, conversational feedback and revision — and help a project build its own content skill and format references. Use for creating a content batch, developing a format, setting up or extending a project's content skill, making more of an approved example, iterating on videos, images, carousels and product demonstrations, managing recurring influencers, keeping and finding generated originals for reuse, or telling the user which tool a task needs and how to install it. Review, publishing and learning are their own skills in this plugin.
---

# Content production

Start where research ends. Establish what to make, prove how it should look and feel, then scale that direction into a reviewable batch. Preserve enough project memory that the next session can continue without rediscovering preferences or repeating rejected work.

## Review in the ViewPrinter workspace

Present every prototype and batch with the [content review](../content-review/SKILL.md) skill: one review per project and format, in the shared local workspace the user keeps open, ending at verified scheduling. Read it before building any review page.

For ongoing influencer management, read [influencers](references/influencers.md): an identity can own a review without being a format.

## Resume before restarting

Resolve this skill's directory from the loaded SKILL.md. Discover project memory by walking up from the working directory for `.viewprinter/content-memory`, or use `VIEWPRINTER_CONTENT_MEMORY`. Never put project state inside the installed plugin. Read config, project preferences, carry-forward, and only the active format/batch and relevant findings. See [memory](references/memory.md).

For a new project, initialize local memory with:

```sh
python3 <skill-directory>/scripts/memory.py init --project <project-root> --name <project-name>
```

### A project with no content skill yet

Make the first prototype before writing a skill: a format is reviewable before its recipe exists. Once the user approves a direction, create the project's one content skill:

- Claude Code reads `<project>/.claude/skills/<project>-content/SKILL.md`; Codex and most other agents read `<project>/.agents/skills/<project>-content/SKILL.md`. Use the folder the user's agent reads; for both, keep one copy and link the other folder to it.
- Give it frontmatter with a `name` and a `description` of when to use it, then only what the project has decided: audience, voice, proof, audio and captions. Route to one `references/formats/<format-id>.md` per format; see [develop project formats](references/formats.md).
- Record the path of its SKILL.md, relative to the project (for example `.agents/skills/<project>-content/SKILL.md`), as `contentSkill` in `.viewprinter/content-memory/config.json`, so the review workspace shows it as the project's guidance.

Write down the user's decisions, not guesses. A format's recipe grows from approved examples.

Use existing authorization and decisions from the conversation. These phases are production stages, not automatic permission gates. Paid generation is the exception: it needs a provider the user connected or named and a spend scope, a count or a budget, from the user or project memory. Ask once per batch when either is missing. Keep the user informed while spending: what each paid step should cost before it runs, what it cost and the running total after, and the batch total at handoff; see [spending](references/tools.md#keep-the-user-informed-on-spending). A request for concepts only stops before paid generation; a request for an entire unattended run permits reasonable local decisions within that scope. Stop at a review checkpoint the user actually requested. Do not invent approval because time elapsed.

## Choose the mode

- **Explore directions:** propose genuinely different concepts or formats; make a small set of representative previews when authorized. Do not produce a full batch of an unchosen direction if the user asked to choose first.
- **Establish a format:** turn the selected concept into one complete representative item, or the smallest useful prototype that resolves the uncertainty. Iterate until the requested review is satisfied.
- **Scale an approved format:** preserve its defining structure and treatment; vary the agreed dimensions. Skip redundant concept approval when the user says “more like this.”
- **Revise:** read the current item versions and exact feedback. Make the requested changes; don't restart research or redesign unrelated work.

## 1. Define the concept and format

For new formats or reusable project recipes, read [develop project formats](references/formats.md). This general skill helps build and improve the project’s one content-creation skill: shared rules plus many unique format references. Extend that existing structure; a new format can be reviewed before its recipe is documented. Use the [generic creator hook/demo starter](references/formats/hook-demo.md) when appropriate, adapting its structure and capability map to the project. Keep shared review behavior in content review and brand-specific creative decisions in the project.

Use the supplied research, reference content, brand facts and audience. Ask only for missing decisions that materially affect production; continue independent preparation while waiting. Tactical lookups for music, tools or a missing factual claim are allowed. Don't rerun the whole audience/competitor study by default.

Write a short format specification with:

- Audience, situation, intended reaction and desired action.
- Concept: the idea or tension; what the viewer learns or gets.
- Format: scene/slide sequence, footage style, composition, type treatment, pacing, audio, product proof and ending.
- Defining choices that stay consistent, dimensions allowed to vary, and any intentional exceptions.
- Real product capabilities or evidence needed to deliver the claim.
- Outputs, count, platforms/dimensions, prototype scope, review checkpoint, and authorized generation/spend scope where relevant.

For short-form video, carry the project’s audio direction into the format before editing. When the brief or saved preference calls for energetic trending sounds and replay potential, research current candidates and choose the excerpt around the hook, demo and payoff. A generic generated bed is not a substitute. Record the sound choice, evidence and loop plan; see [audio](references/audio.md).

Concept and format are distinct. One idea can have several presentations; one approved presentation can support many ideas. Store stable format IDs and revisions, with references to the exact prototype the user chose. See [production](references/production.md).

For staged review, define the decision and exact deliverable at each checkpoint before dependent production. See [review checkpoints](../content-review/references/review.md#plan-review-checkpoints-before-dependent-production). Adapt the rounds to the format and existing authorization; a source preview, execution sample and complete draft answer different questions.

## 2. Make the representative example

Inspect available tools and assets: `scripts/tools.py check --json` reports what this machine has, and [tools](references/tools.md) names the tool each task needs, how to install it and when to recommend it, including a one-time setup summary on a machine's first production session. Use the user's selected tools. For video, use the editor the user or project memory names, with its installed guidance for supported commands, version and native project structure; an editor cuts footage, it does not generate avatars. Load the corresponding capture or generation guidance only when needed. If a required tool is unavailable, recommend it as the tools page describes: once, with what it unlocks and its install step (for video editing, Tesseract, unless the user or project memory names another editor), remembering the answer. Prepare the unaffected work meanwhile; don't pretend a substitute meets the same deliverable.

Choose the smallest prototype that answers the open question: a layout for typography, a short motion test for physical plausibility, or a complete video for hook-to-proof timing. Check the actual result at the intended viewing size. A good still does not establish that motion or audio works.

Keep generation requests, job IDs, selected assets, source timings and editable projects. Check an existing job before retrying a paid request whose response was lost. Save every original into the project's [source archive](references/archive.md) with `scripts/archive.py add` as it arrives, rejected attempts included, and search it with `archive.py find` before paying for a new generation. When the project keeps originals in ViewPrinter too (ask once; see [the archive](references/archive.md#keep-originals-in-viewprinter-too)), store them there as well and search its source material before generating. Read [audio](references/audio.md) before sourcing or editing sound. When a batch creates or acquires new reusable audio, include its library decision in the handoff: ask whether to add the selected clips unless that action is already authorized.

## 3. Produce the batch

Map stable item IDs to concept, format revision, variation, asset sources and intended payoff. IDs survive reordering and rejected items; versions identify changed deliverables. Before scaling, identify what the user approved and which dimensions may vary. Do not turn an instruction to double down into a batch-wide format redesign.

Create fresh assets where variation needs them; reuse verified assets from the source archive when they still tell the intended story, working on a copy from `archive.py checkout`. Say which is which. Coordinate shared devices, render resources and backend fixtures. Batch independent preparation, but serialize work that shares mutable app data or paid job state.

For a phone-mounted demo, read [phone mounting](references/phone-mounting.md) and load the project’s saved mount preset before composition. Reuse its exact frame asset, screen aperture, mask and layer order. Do not draw a substitute bezel, generate a new phone, or switch hardware because a different editor is in use. Record the preset ID/revision and frame checksum in the item manifest.

For product demonstrations, every screen or artifact must substantiate the claim. Inspect the capture route for unrelated invite/referral CTAs, onboarding, promotions and empty placeholders before recording; resolve them through the real UI or prepare a suitable demo state. See [product captures](references/production.md#product-captures). Check names, dates, totals, avatars, navigation, device masking and feature truth. Generated scenery must not fabricate product UI. Use actual exports when the claim is about an export. A mockup can explore layout if clearly identified as a mockup during review.

Match copy length to a comfortable first read and dialogue to its real speaking time. Music supports that timing; it does not justify an unreadable hook. Don't stretch short footage with frozen expressions, obvious gesture repeats or unintended slow motion. Avoid imposing one duration, caption style, model, phone frame, visual motif or CTA on every format.

## 4. Review and revise

Hand each prototype and batch to [content review](../content-review/SKILL.md), registered under the same project and format ID as the work before it, with stable item IDs and versions, the production stage, and each asset's generation platform, model, prompt and cost. The user reviews visually and gives feedback in conversation.

Record the user's words plus an actionable interpretation: targets, versions, changes, scope and exceptions. Apply shared feedback across its actual scope. Approval belongs to an exact version, not an item forever. Changed approved files become new versions needing review unless the user already authorized finalizing that revision. Clarify consequential ambiguous targets; do not block unrelated clear edits.

## 5. Finish and learn

Inspect final exports, not just source previews. Verify content, readable timing, framing, continuity and product proof; check audio levels and playback boundaries where audio exists. For a trending/looping brief, verify current sound evidence, hook-to-payoff energy and the final end-to-start audition described in [audio](references/audio.md). Missing listening or trend evidence remains an explicit unresolved check; encoding success does not satisfy it. Distinguish measured checks from listening and from user review. Deliver playable/viewable outputs, editable sources when supported, approval status, unresolved limitations and the current gallery.

Update memory before handing off. Separate production changes from conclusions about results. Record a finding with evidence, scope, confidence and what would change the conclusion. Promote repeated lessons into the project's content skill; one batch's taste stays in project memory. A lesson that would hold for every project goes to the user to report; the installed plugin is not edited. See [hardening](references/hardening.md).

For uploads and reusable campaign assets, scheduling, captions, label choices, publishing, and delivery or performance checks, use [content publishing](../content-publishing/SKILL.md). To learn which formats worked and decide what to make next, use [content learning](../content-learning/SKILL.md): it links each publication to its item and version and compares results with each account's normal. An approved creative is not automatically authorized for every account, and views alone do not prove conversion. Preserve already authorized choices rather than asking again.
