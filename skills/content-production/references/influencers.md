# Manage influencers and their content reviews

Use this when the user manages a recurring creator or influencer, including a synthetic character. An influencer is an ongoing identity with a voice, audience, appearance, account relationships and content history. It does not have to be a format. Multiple influencers can coexist in one project and one ViewPrinter workspace.

## Identity and ownership

Use one stable `influencerId` per identity within a project, independent of display name, account handles, agents, batch directories or generation providers. Keep identity information in `.viewprinter/content-memory/influencers/<id>/profile.json`. Record only known facts: name, identity type, audience, voice, appearance references, identity constraints, lore, linked account/group references and production guidance. Label proposed references and unproven hypotheses; do not silently make them approved identity assets. Preserve a real creator's supplied permissions and scope when relevant.

Keep one project content skill. Shared project rules continue to apply; put unique influencer guidance in a linked reference within that skill. Existing performance/format recipes can remain linked production resources. Do not create a new SKILL.md per creator or force every influencer into a format. Do not invent a hierarchy of nested formats before the user develops that need.

Keep account branding and asset reviews in Account Groups and link the appropriate groups to the influencer. The local influencer profile does not create, rename or repurpose remote accounts. Publishing, account changes and performance reads continue through the content-publishing and account-profiles skills and existing user authorization.

## One review per influencer

Each agent owns a source manifest. Declare the same project and influencer ID in every contribution:

```json
{"reviewHub":{"kind":"influencer","influencerId":"creator-id","label":"Creator name","owner":"contributor","influencerRef":".viewprinter/content-memory/influencers/creator-id/profile.json","recipeRef":".agents/skills/project-content/references/influencers/creator-id.md","accountGroups":["project--creator-accounts"]}}
```

Registration groups these sources into one influencer review using the same source revisions, batch ownership, item/version conflict checks and exact-version scheduling receipts as other content. See [workspace](../../content-review/references/workspace.md). An influencer and a format with the same slug remain separate identities. Existing references to a format used by their content can be retained as provenance; they do not determine the influencer's identity.

The review shows the creator's name and identity context, current content and native descriptions, source/previous versions, production evidence and an expandable history. Keep the actual work prominent. Profile details, prompts and long guidance are secondary. The Content pulse can filter influencers or formats; it does not need a separate review server or browser tab per creator.

A project's legacy review can be converted locally with `review_hub.py manage-influencer <entry> --influencer-id <id> --profile <relative-profile.json> --guide <relative-guide.md>`. This retains its stable URL and source media. The conversion records a before receipt. Historical review snapshots belong under the active influencer's Review history, not as a misleading archived influencer in the general Archive.

Scheduling completes review of those exact content versions; it does not retire the influencer. New content reopens review work. Archive an influencer only when the user deliberately retires or pauses management of that identity; preserve identity, account references, recipes and history. Incidental registration cannot silently restore a deliberately archived influencer.

## Production continuity

Read the current influencer profile, project skill and relevant production guide before new work. Preserve approved appearance, voice and character constraints across batches. Record deliberate wardrobe, location and performance variations per item. Do not overwrite an identity reference because a new generator produced a plausible face.

For Higgsfield or another specialized workflow, retain identity references, source performance and timing, model/settings, job IDs, measured or unknown costs, feedback and approved examples. Inspect available provider tools and current workflow guidance when production is authorized. Managing a review does not itself authorize paid generation, outreach or posting.
