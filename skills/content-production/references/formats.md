# Develop project formats

Use this when establishing a format, turning feedback into a reusable recipe, or deciding whether new work belongs in an existing review.

## Separate the responsibilities

| Layer | Owns |
| --- | --- |
| content-production skill | Develop concepts and formats, select available capabilities, prototype, produce, review, preserve evidence and learn. Shared gallery behavior and the local server live here. |
| Generic starter | A reusable starting structure and capability map. Adapt it to the project; it is not a proven winner or a mandatory toolchain. |
| Project content skill | One content-creation SKILL.md per project, routing to many unique format references and shared audience, voice, proof, audio, description and production guidance. |
| Project format recipe | The recurring viewer experience, approved examples, invariants, allowed variants, tool workflows, quality checks and evidence from feedback/results. It lives in `references/formats/<format-id>.md` under the project’s one content skill, following the project’s established structure. |
| Format review record | Stable identity, current content, batches, descriptions, exact-version review and delivery history. Review works even when there is no skill or recipe yet. |

Keep one local ViewPrinter server per user workspace across projects and agents. A project owns its data and format identities. A format owns the review destination; a batch identifies a production run. The contributing agent is provenance, not a format or browser tab.

## Extend the existing project skill

Read the project’s content SKILL.md first. Preserve its structure: one entry skill, shared guidance, and many distinct format references. Do not create competing content skills or a separate skill for each format.

```text
<project>-content/
  SKILL.md                       shared rules and routing
  references/
    audience-and-casting.md      shared where relevant
    audio.md
    proof-and-capture.md
    descriptions.md
    formats/
      hook-demo.md               only this format’s recipe and exceptions
      street-interview.md
```

These filenames illustrate the existing pattern, not required new files. Reuse the project’s actual paths. Shared details may remain in SKILL.md or a shared reference; keep one authoritative source and link it from applicable formats. Put unique sequence, pacing, visual treatment and specialized requirements in the format reference. Keep exceptions scoped and resolve conflicts using the project’s existing precedence rules and current user instructions. Feedback that applies to several formats updates the shared guidance once; feedback about one format or batch stays there. A reusable provider workflow can also be a shared reference used by multiple formats.

## Start with a reviewable format, then develop its recipe

1. Read the project skill/memory and look for an existing matching format. Use its stable format ID even when the title, tool, directory or contributor changes.
2. If none fits, record a stable ID, display name, short concept and viewer sequence in project memory. A format-specific recipe file is optional; the existing project content skill still applies. Use the [hook/demo starter](formats/hook-demo.md) when that structure fits; other formats can start from a short brief.
3. Make the requested prototype within the user's production scope, put it in that format's review, and retain its sources and exact version. A new experimental format is reviewable immediately.
4. Translate accepted feedback into invariants and allowed variation. Preserve the user's actual decision and scope. Write or update a format reference under the existing project content skill when the project’s promotion criteria are met. If the project has no content skill yet, use installed skill-creator guidance to establish that one shared entry skill.
5. Link the recipe to the existing format ID and approved examples. Documenting the recipe later does not create another format, reset its review, or erase history.
6. Keep creative preference, technical success and measured audience performance distinct. Record model/workflow tests and evidence dates; one project's favorite model does not become the generic default.

Do not create a SKILL.md for every batch. Keep changing job receipts, media, account IDs, captions and schedules in project data. The recipe points to that evidence and captures reusable decisions. Improve shared ViewPrinter guidance when the lesson applies across projects.

## Decide format versus variant versus workflow

A format is the recurring experience the viewer recognizes: opening, progression, proof or reveal, and ending. A variant changes an agreed dimension within that experience. A workflow describes how to produce it. Switching a generator, editor or contributor alone does not establish a new format; sharing a tool does not combine different formats.

Follow the user's chosen boundary. If the user groups live action and motion treatments under one format, keep them as named variants/batches in one review. If the user explicitly separates green-screen reactions and video memes, preserve that boundary even if both use the same source library.

Special workflows can add their own inputs, stages and checks. For a Higgsfield influencer-based format, for example, the project recipe can reference the selected identity, approved source performance, chosen workflow, supported request fields, identity/motion checks and generation receipts. Inspect the connected provider's current workflow instructions before execution. Keep provider details in that workflow reference, and surface only relevant extra evidence in the review card's production disclosure. Do not force every format through influencer generation or require a paid dependency merely to review content.

A managed influencer is an identity, not necessarily a format. Use [influencer management](influencers.md) for their shared review and history; do not invent nested format navigation until it is needed.

## Multiple contributors, one review

Resolve the same project + format identity before choosing an output location. Agents may use separate production directories and own separate batches; their content still belongs in the same format review. Preserve stable item IDs, versions, creative decisions, native descriptions and delivery receipts. Conflicting reuse of an item/version with different media requires resolution, never last-writer-wins.

The workspace registers independent contributor manifests into one generated review using the persisted project identity and stable format ID. Each contributor edits only its source and submits the observed source revision; unrelated batches can register concurrently. Existing accepted content stays intact if a source conflicts, goes missing or fails rendering. Preserve unique item and batch IDs, and put allowed treatments in `reviewHub.variant` or item `variant` rather than inventing format IDs. The generated index is read-only. See [workspace](../../content-review/references/workspace.md) for registration, revision checks, migration and archive behavior.
