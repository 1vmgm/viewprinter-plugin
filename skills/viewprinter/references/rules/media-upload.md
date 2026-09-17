# media-upload: Uploading is three steps, and the third is the one that counts

## Priority: CRITICAL

## What goes wrong

`media_upload` looks like it uploads. It does not. The bytes never travel
through the API — they go straight to storage — so one tool call cannot do it.

Stopping after step one or two leaves a file that does not exist as far as
ViewPrinter is concerned: the URL expires, the bytes may be sitting in storage,
and nothing references them.

## The flow

1. **`media_upload`** — pass `kind` and the exact `mime_type` the PUT will send.
   Returns an `id`, a short-lived `url`, and `expires_in_seconds`. This records
   nothing; it mints a write credential.
2. **PUT the bytes to that `url`** yourself, with a `Content-Type` matching the
   `mime_type` you declared. A mismatch fails the upload.
3. **`media_confirm`** with the same `id` and `kind`. Only now does the file
   exist.

If a flow is interrupted, the fix is to confirm the id you already have — not to
start a new upload.

## What the client must be able to do

Read the file and make an HTTP PUT. If it cannot, say which step is unavailable
and use an already uploaded file, or ask the user to upload through ViewPrinter.

- **Do not call `media_confirm` until the bytes are actually uploaded.**
- **Never expose the signed upload URL** in a public post or a user-facing log.

## Context

- `media_confirm` is safe to call again if the first response was lost. It reads
  size and type back from storage rather than trusting what you claimed, so a
  confirm that disagrees with the bytes fails rather than recording something
  wrong.
- If confirm reports no uploaded file for that id, the PUT did not land. Retry
  the PUT before minting a new id.
- Call `media_list` before uploading anything. Re-uploading a file the user
  already has wastes their time and leaves a duplicate behind.
