# Concept, format and production

## Start from the brief

Inputs can be research findings, an existing winner, a script, reference images, or a user-specified idea. Extract the objective, audience, evidence, constraints and choices already made. Preserve original sources and dates; distinguish observed outcomes from creative interpretation. This skill does not need to repeat a competitor study to begin making content.

A compact format record can contain:

```json
{
  "id": "format-interview", "revision": 1,
  "concept": "A customer misconception resolved by a visible example",
  "audience": "First-time users", "objective": "Understand the feature",
  "sequence": ["question", "demonstration", "result"],
  "invariants": ["Readable question before the demonstration", "Real product output"],
  "variables": ["question", "setting", "speaker"],
  "presentation": {"aspectRatio": "9:16", "typography": "reference asset", "audio": "dialogue with restrained bed"},
  "prototype": {"itemId": "clip-001", "version": 2},
  "approval": {"state": "awaiting-review", "source": null}
}
```

The fields organize a decision; they are not a rigid creative template. Static posters, carousels, screen recordings, interviews and animations need different sequence/timing details. When exploring formats, make alternatives meaningfully different. When scaling one, preserve its distinguishing choices. Label an exploratory exception instead of letting it silently replace the baseline.

## Prototype selection

Resolve the largest uncertainty early. Examples: one still for hierarchy; several motion seconds for a difficult interaction; one complete piece for audio and reveal pacing; a few slides for a carousel narrative. Do not call a still an approved video or create a paid large batch before a requested prototype review. If the user authorized an unattended run, select the strongest reference-supported direction, record assumptions and continue within scope.

Production tools are capabilities, not the concept. Inspect installed guidance and available schemas rather than assuming one generator has every feature. Identity references constrain the person, not necessarily clothing or location. Keep a per-job request/receipt before retrying generation; don't submit another paid job just because polling timed out. Archive each attempt's output as it arrives, with its job ID and prompt, and mark the selected one; see [archive](archive.md).

## Reference performances and scene replacement

Record the full source duration, selected source in/out and required action beats before generating from a performance reference. Confirm that the selected input includes the requested opening and ending. Keep source time distinct from the generated clip's time; compare gestures at the same source instant. A coherent-looking output or a positive sampled model review does not establish exact finger, wrist, mouth or action timing. Preserve user rejection and require the requested motion to be visible before spending on a dependent finishing pass.

When the environment must change while an accepted performance stays intact, inspect a separate foreground-matte/compositing route. A generative environment edit can resynthesize the person. Verify extraction edges and the editor's matte support; a matte preserves existing detail and cannot repair an omitted gesture. Distinguish a still reference from a moving background, and check camera/perspective compatibility before overlaying footage.

Verify model availability using the provider's active catalog and current schema. A failed guessed endpoint name does not prove a capability is unavailable. Preserve the supported endpoint and any discrepancy between current API fields and overview documentation; quote costs for the exact settings rather than an ambiguous base unit.

## Product captures

Use authentic app/web UI for feature demonstrations. Seed fictional demonstration data coherently and verify totals, dates, labels, avatars, units and visible entitlements. Coordinate shared devices and backend fixture state; separate simulators do not necessarily isolate accounts. Follow the installed interaction/capture skill. Never bypass its device rules from this generic skill.

Before recording, inspect every screen along the demo route at the planned framing. Dismiss unrelated invitation/referral CTAs, onboarding prompts, upsells and debug overlays through the genuine UI, or prepare a demo state that avoids them. Populate enough coherent history to make the promised result readable. If a persistent prompt dominates the evidence, choose a better route or flag the limitation before capture; do not paint over UI, invent a dismissal or hide necessary context with a weak crop. When the invitation itself is the feature being demonstrated, keep it and make that intent explicit.

Keep capture and scenery separate. For mounted demos, follow [phone mounting](phone-mounting.md): the saved hardware asset and fitted screen are one reusable composition. Generated scenery is not permission to replace the approved phone. A deliberately requested handheld or perspective shot is a separate treatment; record that exception instead of changing the default preset. Do not hide stale UI or capture defects with painted text. Use actual generated PDFs/exports for an export claim. If a concept needs unavailable evidence, adjust the concept or flag the missing dependency rather than manufacture product behavior.

Choose a demo route because it answers the opening. A single useful comparison can outperform a long tour editorially; that is not proof of measured conversion. Cut repeated navigation/loading/dead time, preserve enough context to understand the result, and annotate only evidence that benefits from attention. Match narration placement to readable space, not an arbitrary bottom strip hidden by platform controls.

## Video editor adapter

Use the editor the user or project memory names, and any installed skill or documentation for it. Read its current setup and supported CLI/schema rather than pinning a command set in this skill. An editor cuts footage; it is not an avatar generator. If the named editor is unavailable, say what is missing. Use an alternative only when consistent with user intent; retain editable project/source requirements.

Keep source-time and timeline-time distinct. Work in versioned native projects, preserve IDs, and save layer/keyframe changes through supported operations. Use native editable text, shapes, footage and audio when supported. For revisions, check out the current project rather than regenerate from an old template that would erase animation or audio corrections. Track frame rate, source in/out, reveal/caption windows and final duration. Final transcoding must not discard sound or alter the approved crop.

Inspect the final encoded file's meaningful frames and motion. Verify dimensions, duration, audio streams, decode errors and matching content. Listen when capable; report when only automated measurements were possible. Filmstrips don't prove temporal continuity or audio quality. Use external audiovisual review only when authorized to send those specific assets.

## Delivery and scope

Deliver immutable versioned outputs and a current gallery; keep prior rounds available for comparison. Distinguish rendered, reviewed, approved, uploaded, scheduled and published. Use the content-publishing skill for external actions already authorized, and report exact blockers for anything refused. Don't add account strategies, AI-label ratios or automatic trial behavior as defaults for every project.
