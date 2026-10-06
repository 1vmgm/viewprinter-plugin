# Reuse the approved phone mount

A phone mount is a versioned production asset, not an illustration to redraw for each video. Before editing a mounted demo, resolve `defaults.phoneMountPreset` from the project's content-memory `config.json`. Resolve that path relative to the memory directory. A format may name an explicitly chosen alternative; otherwise use the project default.

## Lock the hardware and screen fit

Load the preset and verify its frame file and SHA-256. Inspect its approved reference and reuse the exact asset, aperture, corner mask, layer order and any camera/island treatment. A different editor, agent, simulator model or new batch does not authorize replacing them. No custom CSS/SVG outline, generated mockup, extra border or substitute downloaded device unless the user requests a new hardware treatment. Do not replace a familiar asset merely because its filename identifies a different model from the capture device.

If the saved file is missing or its hash differs, locate a verified identical copy using the provenance. If none is available, report that dependency and continue other preparation. Do not silently recreate it. If the project has no preset, inspect existing approved outputs first; establish one reusable mount during the requested prototype review and save it. An already approved preset needs no new approval each session.

Keep project-specific artwork and filesystem paths in external project memory. The public skill defines the reuse contract; it does not impose one brand's phone on every customer.

## Preset contents

Store `assets/phone-mounts/<id>/v<revision>/preset.json`, its frame asset and an approved reference image or linked project. Record:

- Stable ID/revision, file path relative to the preset, SHA-256 and native image dimensions.
- Reference coordinate system; screen x/y/width/height; corner radius or exact mask asset; layer order and camera/island handling.
- Verified capture geometry and fit recipe. Identify any known legacy fit; do not call it model-exact without evidence.
- Reference composition or editable project, decision/provenance source and permitted variation.

For a reference frame width `Rw` and height `Rh`, placed at `(x,y)` with width `w`, use `k=w/Rw`. Frame height is `Rh*k`; aperture is `(x+sx*k, y+sy*k, sw*k, sh*k)`; corner radius is `r*k`. Round only when the renderer requires pixels. Use the preset's mask convention, not a newly guessed radius. Do not independently stretch the frame or animate its screen separately.

## Compose consistently

Treat frame, clipped recording and any hardware occlusion as one group. Scale, place and animate that group to suit the format; background, demo content, group position and reveal timing may vary when authorized. The bezel identity and internal geometry remain fixed. Reuse the template in the chosen editor rather than replacing the frame with native drawing primitives. A borderless crop is a different presentation treatment, not a substitute phone mount.

Use authentic screen pixels. Check capture aspect ratio against the preset's verified fit. For an incompatible capture, recapture at the supported geometry or resolve a deliberate fit adjustment; don't force it by stretching, covering controls or silently cropping navigation. Preserve one coherent status bar, camera/island and home indicator. Do not add fake hardware over an already captured island or replace the entire status strip by default.

Apply the preset's layer order exactly. Some established frames are backgrounds with an opaque opening and require a clipped screen above them; others are transparent overlays. Assuming every frame belongs on top can hide the demo. Scene annotations and captions remain separate from the hardware group and follow the approved creative treatment.

## Check before batch rendering

Inspect one fully composited frame at delivery size, including all four screen corners, the top island/status region and bottom navigation. Check for white boxes, seams, clipped UI, doubled borders and screen motion detached from hardware. Inspect entry/exit animation too. Compare against the approved reference at the same phone scale. Reuse that verified assembly throughout the batch.

Record `phoneMount: {presetId, revision, frameSha256}` plus placement/transform in each item manifest. A hardware or aperture change creates a new preset revision with its reason and review status; it never overwrites the established default silently. Preserve any explicitly authorized exception without applying it to unrelated formats.
