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

## Check the brief against the actual result

Before editing, resolve the applicable project/format references and the latest feedback
into a short set of criteria in the existing batch record. Separate the intended outcome,
permitted treatments and prohibitions. Permission to overlap an element, for example,
does not make that overlap the composition's target. A new correction does not silently
waive the other requirements. Preserve choices the user did not ask to change.

Check a representative composition before propagating it. At handoff, tie each applicable
criterion to the exact output version/hash and observed evidence; for video, include the
relevant timestamps. Keep technical decoding, visual hierarchy, destination visibility,
product proof and listening results distinct. Pass, fail and unverified mean different
things: technical success cannot resolve a creative failure or a missing overlay check.
Recheck the requested change and the constraints it could displace. Known failures stay
changes-requested; missing evidence stays explicit. These are internal production checks,
not new user approval steps, and they do not prevent showing an honestly labeled draft.

Treat automated media reviews as evidence to verify, not approval or a new brief. If source and final reviews disagree about an observed feature, inspect the exact files and timestamps, retain both reports, and record the resolution against the output hash. A targeted review may resolve the disputed fact; do not rerun unchanged media until it receives a favorable score. Distinguish an actual defect from a draft treatment that was deliberately changed, and verify any editorial data graphic against the source records while keeping it visibly distinct from native product UI.

For product demonstrations, inspect narration **with the actual evidence visible**. A
readable caption is still a failure when its backing obscures the interface, labels or
figures that deliver the claim. Prefer restrained marks beside the relevant detail.
When the agreed treatment establishes a whole screen/document and then zooms, retain
the original complete asset; a detached excerpt is not an equivalent implementation.
Check labels and totals at the zoom endpoint. Explicit user visual constraints remain
acceptance criteria even when an automated reviewer reports a pass.

For generated scenes, check physical relationships as well as styling: perspective,
seating, doors, props and hands must belong to one coherent environment. A plausible
face does not establish a plausible scene. For seated portraits, trace each visible
arm from shoulder through elbow and wrist to the hand, and check that seat edges,
belts and props stay separate from the body. A tight crop that hides a suspect joint
does not resolve it; simplify the pose or widen the framing when necessary. After a
camera or pose correction, inspect for new artifacts such as visible filming
equipment and displaced framing before spending on dependent animation. Record failures explicitly instead of calling them
minor angle differences.

For text-led content, assess reading structure separately from placement and contrast.
Inspect a saved frame of the final render at the intended viewing size: do phrase breaks,
spacing and hierarchy make distinct thoughts easy to follow? Newline characters and a
box that fits do not establish this. Record the verdict, evidence and a brief reason;
if separate thoughts read as one dense block, revise before marking it ready. Preserve
the approved format's static or timed treatment; this does not mandate separate cards
or staggered captions.

When a user wants a fresh variation within an established social style, compare the
actual type treatment with a supplied or researched example at phone size. Check font
weight and proportions, letter outlines, backing and line grouping; contrast alone does
not establish that it fits the reference. Identify what is retained and what is a new
styling test. Seeing a treatment in a successful post does not prove it caused the result.
When a reaction carries the story, check that caption backings leave the expression
readable through the shot. Permission for lettering to overlap a face does not imply
that an opaque panel may hide its expression.

For motion narration that places an icon or font glyph inside a badge, inspect the rendered symbol at native resolution and phone size. Font line boxes and ascenders can leave the visible glyph off-center even when its layer is mathematically centered. Align the visible mark within its container, then check the entrance, travel and settled hold alongside the text; keep the symbol and its backing together. Verify pointer endpoints against the actual evidence after transforms.

## Prototype selection

Resolve the largest uncertainty early. Examples: one still for hierarchy; several motion seconds for a difficult interaction; one complete piece for audio and reveal pacing; a few slides for a carousel narrative. Do not call a still an approved video or create a paid large batch before a requested prototype review. If the user authorized an unattended run, select the strongest reference-supported direction, record assumptions and continue within scope.

Production tools are capabilities, not the concept. Inspect installed guidance and available schemas rather than assuming one generator has every feature. Identity references constrain the person, not necessarily clothing or location. Keep a per-job request/receipt before retrying generation; don't submit another paid job just because polling timed out. Archive each attempt's output as it arrives, with its job ID and prompt, and mark the selected one; see [archive](archive.md).

### Compare the generation mode the user wants

State whether a model comparison tests fresh generation, identity consistency or an edit.
For independent creative exploration, give each model the same concise directional brief
without an image reference. Keep required story and camera constraints, but leave
unspecified identity, wardrobe and composition choices open to the model. Inspect the
results and refine the prompt in small steps before another authorized fresh generation.
A shared source image is appropriate for comparing edits or preserving a chosen identity;
it constrains both outputs and does not test their independent creative interpretation.
Do not turn dissatisfaction with an unselected concept into a chain of reference repairs
unless that is the requested workflow. Record the mode, reference lineage and all attempt
costs, and judge each output against the requested scene before dependent production.

## Reference performances and scene replacement

Record the full source duration, selected source in/out and required action beats before generating from a performance reference. Confirm that the selected input includes the requested opening and ending. Keep source time distinct from the generated clip's time; compare gestures at the same source instant. A coherent-looking output or a positive sampled model review does not establish exact finger, wrist, mouth or action timing. Preserve user rejection and require the requested motion to be visible before spending on a dependent finishing pass.

For an intended silent reaction, inspect the exact selected source range and its finished cut for speech-like mouth articulation. Muting audio or an earlier source approval does not establish a silent performance. If the usable reaction is shorter than the readable hook, carry the next thought onto the proof shot or choose another authorized take; do not retain visible talking, freeze the face, or slow the shot merely to fill the hook. Record the chosen source in/out and inspect the handoff at normal speed.

When the environment must change while an accepted performance stays intact, inspect a separate foreground-matte/compositing route. A generative environment edit can resynthesize the person. Verify extraction edges and the editor's matte support; a matte preserves existing detail and cannot repair an omitted gesture. Distinguish a still reference from a moving background, and check camera/perspective compatibility before overlaying footage.

Verify model availability using the provider's active catalog and current schema. A failed guessed endpoint name does not prove a capability is unavailable. Preserve the supported endpoint and any discrepancy between current API fields and overview documentation; quote costs for the exact settings rather than an ambiguous base unit.

## Product captures

Use authentic app/web UI for feature demonstrations. Seed fictional demonstration data coherently and verify totals, dates, labels, avatars, units and visible entitlements. Coordinate shared devices and backend fixture state; separate simulators do not necessarily isolate accounts. Follow the installed interaction/capture skill. Never bypass its device rules from this generic skill.

Before recording, inspect every screen along the demo route at the planned framing. Dismiss unrelated invitation/referral CTAs, onboarding prompts, upsells and debug overlays through the genuine UI, or prepare a demo state that avoids them. Populate enough coherent history to make the promised result readable. If a persistent prompt dominates the evidence, choose a better route or flag the limitation before capture; do not paint over UI, invent a dismissal or hide necessary context with a weak crop. When the invitation itself is the feature being demonstrated, keep it and make that intent explicit.

Check event-marker and annotation density at the intended viewing size: correct data can still produce overlapping or unreadable evidence. For fictional demonstration data, choose a coherent example whose important events remain distinct; do not alter real records for a cleaner story. Match attachments to the specific event and emotional context they document. A correct account avatar is not automatically an appropriate journal or evidence photo.

When the story depends on a change, capture and show its original state before the changed state. Verify each capture after the app has refreshed; a successful backend update does not prove the visible UI has changed. Keep the framing comparable so the date, count or marker that moves is easy to follow, and tie the payoff to that observable difference. A final-state screenshot with an animated arrow alone does not establish the before-and-after claim.

Across product-screen changes, preserve the device frame, position and scale unless camera movement serves the explanation. Inspect the rendered joins at normal speed and adjacent frames: fading an incoming screen after removing the outgoing one can expose a white backing, while crossfading displaced device frames creates a distracting jump. Keep real evidence visible beneath the transition. Use compact narration and pointers beside the evidence; a large backing that hides the interface can defeat the demonstration. End on a concrete benefit established by the visible change, and remove unchanged holds that exist only to fill the music.

For a captured swipe, inspect the moving panel together with its linked selection indicator, dates and counters. Compare raw capture with the edit before blaming export or model quality. If settling trails the gesture, condense the complete genuine UI sequence and hold its settled state, or recapture; do not animate a separate indicator to imply behavior the app did not show. Record timing changes and any observed product delay separately from content quality.

Keep capture and scenery separate. For mounted demos, follow [phone mounting](phone-mounting.md): the saved hardware asset and fitted screen are one reusable composition. Generated scenery is not permission to replace the approved phone. A deliberately requested handheld or perspective shot is a separate treatment; record that exception instead of changing the default preset. Do not hide stale UI or capture defects with painted text. Use actual generated PDFs/exports for an export claim. If a concept needs unavailable evidence, adjust the concept or flag the missing dependency rather than manufacture product behavior.

Choose a demo route because it answers the opening. A single useful comparison can outperform a long tour editorially; that is not proof of measured conversion. Cut repeated navigation/loading/dead time, preserve enough context to understand the result, and annotate only evidence that benefits from attention. Match narration placement to readable space, not an arbitrary bottom strip hidden by platform controls. When narration explains highlighted evidence, group the complete phrase beside that evidence, including introductory words. If the highlight moves to another record, move the full callout with it; a detached heading can split attention even when the value caption is adjacent. Check the encoded result at the intended viewing size.

## Video editor adapter

Use the editor the user or project memory names, and any installed skill or documentation for it. Read its current setup and supported CLI/schema rather than pinning a command set in this skill. An editor cuts footage; it is not an avatar generator. If the named editor is unavailable, say what is missing. Use an alternative only when consistent with user intent; retain editable project/source requirements.

Keep source-time and timeline-time distinct. Work in versioned native projects, preserve IDs, and save layer/keyframe changes through supported operations. Use native editable text, shapes, footage and audio when supported. For revisions, check out the current project rather than regenerate from an old template that would erase animation or audio corrections. Track frame rate, source in/out, reveal/caption windows and final duration. Final transcoding must not discard sound or alter the approved crop.

When a demonstration should continue over a held creator background, use the actual last outgoing source frame with the same crop and transform, not the original generation still. Resolve the frame from the source frame rate and selected in/out, then compare the adjacent encoded frames. An intentional background hold after the creator segment is distinct from freezing a face to pad hook reading time.

Inspect the final encoded file's meaningful frames and motion. Verify dimensions, duration, audio streams, decode errors and matching content. Listen when capable; report when only automated measurements were possible. Filmstrips don't prove temporal continuity or audio quality. Use external audiovisual review only when authorized to send those specific assets.

For external model review, retain the exact export hash, submitted modalities and response usage. A video review that describes sound may be inferring from captions; its prose alone does not establish an audio check. When audio ingestion is uncertain, submit the authorized soundtrack explicitly for an audio-only or combined review and label it as model listening, not human approval. Treat generated findings as hypotheses: verify exact product figures, speaker timing and claimed visual defects against the original source. After a local correction, record which checks still apply and which version was actually reviewed.

### Export quality check

Compare matching moments in the final encoded video with the original source at the intended viewing size; inspect fine detail at native resolution too. Check faces, hair and product text for added blur, smearing or compression blocks, and motion for unintended freezes or uneven movement. Check normal-speed playback when available; metadata, a resolution label and filmstrips alone do not establish visual quality. Intentional stills and readable proof holds are not defects.

A correct resolution does not establish adequate export quality. A low-motion screen capture may carry a much lower bitrate than creator footage; compare the encoded creator and UI against the native preview when automatic export settings are used. If the exporter makes a visibly compressed result, set delivery quality explicitly or render a high-quality native master and transcode that for delivery. Re-encoding the already degraded MP4 cannot restore lost detail. Record the measured output and tool limitation.

Keep verification reports tied to the exact encoded file, for example with its checksum in the report filename. Some measurement helpers refuse to overwrite an earlier report; that failure does not mean the render failed. Preserve the completed export, write a new report, and resume its remaining checks rather than rerendering it. Reuse a report only when its recorded input checksum still matches.

At footage cuts, inspect the exact decoded frames immediately before and after the boundary, not only timestamp-seek screenshots: seek rounding can skip a one-frame gap. Container duration does not guarantee a decodable frame at the endpoint. Retain source handles or trim to verified frames; extra frozen performance is not a repair for an unintended gap.

For continuous music or loops, compare the decoded audio endpoint with the picture endpoint too: a full-length container can conceal a short audio stream or encoder-delay gap. Repair unintended gaps while preserving the editable mix, then recheck the final encoded file.

If the export looks worse than the source, check scaling, crop, compression and frame-rate conversion, correct the edit/export settings and recheck the finished file. Use the original footage rather than a compressed preview as the editing source. If the defect already exists in the source, record that separately before choosing a repair or regeneration. State any unverified playback checks; do not claim a clean export from encoding success alone.

## Delivery and scope

Deliver immutable versioned outputs and a current gallery; keep prior rounds available for comparison. Distinguish rendered, reviewed, approved, uploaded, scheduled and published. Use the content-publishing skill for external actions already authorized, and report exact blockers for anything refused. Don't add account strategies, AI-label ratios or automatic trial behavior as defaults for every project.
