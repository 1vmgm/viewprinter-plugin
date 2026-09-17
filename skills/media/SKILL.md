---
name: media
description: Upload images or video to ViewPrinter so they can be attached to a post, using the reserve/PUT/confirm flow. Use when attaching media to a post, uploading a file, or listing, describing or deleting files already uploaded.
---

# Uploading media

Uploading is **three steps, not one.** The bytes never travel through the API —
they go straight to storage — so a single tool call cannot do it.

The client must be able to read the file and make an HTTP PUT. If it cannot,
explain which upload step is unavailable and use an already uploaded file or
ask the user to upload through ViewPrinter. Do not call `media_confirm` until
the bytes have actually been uploaded. Never expose the signed upload URL in
a public post or user-facing log.

## The flow

1. **`media_upload`** — pass `kind` and the exact `mime_type` the PUT will send.
   Returns an `id`, a short-lived `url`, and `expires_in_seconds`. This records
   nothing; it mints a write credential.
2. **PUT the bytes to that `url`** yourself, with a `Content-Type` matching the
   `mime_type` you declared. A mismatch fails the upload.
3. **`media_confirm`** with the same `id` and `kind`. Only now does the file
   exist as far as ViewPrinter is concerned.

**Skipping step 3 loses the file.** The URL expires, the bytes may be in storage,
and nothing references them. If a flow is interrupted, the fix is to confirm the
id you already have — not to start a new upload.

`media_confirm` is safe to call again if the first response was lost. It reads
size and type back from storage rather than trusting what you claimed, so a
confirm that disagrees with the actual bytes fails rather than recording
something wrong.

If confirm reports no uploaded file for that id, the PUT did not land. Retry the
PUT before minting a new id.

## Describing a file

Pass `description` to `media_confirm`, or set it later with `media_update`.
Confirming again never overwrites a description already written.

This is not decoration. For a base image the description is **who is on camera** —
"a woman in her early twenties, blonde hair in a loose bun" — and it is read back
so the same person appears across renders instead of changing between them. A
vague description produces inconsistent results; write what is actually visible.

`media_update` sets only the description. Everything else about a file was read
from the file itself and cannot be edited. Send `null` to clear it.

## Reusing what is already there

Call `media_list` before uploading anything. It returns every file in the user's
workspaces, newest first, with the ids `posts_schedule` takes. Re-uploading a
file the user already has wastes their time and leaves a duplicate behind.

## Deleting

`media_delete` removes the file and its stored bytes. **This cannot be undone,
and any post still using it loses it.** Check `posts_list` for pending posts
referencing the file before deleting, and confirm with the user — an unscheduled
post that quietly loses its video is worse than a file left lying around.
