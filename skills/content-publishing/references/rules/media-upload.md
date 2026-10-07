# media-upload: Uploading is two steps, and the second is yours

## Priority: CRITICAL

## What goes wrong

`media_upload` looks like it uploads. It does not. The bytes never travel
through the API — they go straight to storage — so one tool call cannot do it.

Stopping after step one leaves nothing: the URL expires and no file exists.

## When the person has the file

They attached it in the chat, or it is on their phone or computer. Call
**`media_upload` with no arguments**, as an ordinary tool call — not from
code, and without trying to send the file yourself. Chat apps that show
widgets (Claude, ChatGPT) put an upload box under the call: tell the person to
use it. It takes one video or up to ten photos, and posts their media ids to
the chat, in picking order, when they are in. Where no box appears, give them
`upload_page` — any device, no sign-in, an hour.

## When you hold the file

A terminal agent or a server that can make HTTP requests:

1. **`media_upload`** — pass `kind` and the exact `mime_type` the PUT will send, and
   the file's `sha256` (hex) whenever you can: if the workspace already holds the
   file, the answer is its `id` with `existing: true`, and there is nothing to upload.
   Otherwise it returns an `id`, a `url`, the `headers` to send and
   `expires_in_seconds` (fifteen minutes). Several files: pass `items`, up to 50;
   the answers come back in the same order.
2. **PUT the bytes to that `url`** yourself, with exactly the `headers` the answer
   gives and no others: the signature covers them, and with `sha256` storage refuses
   bytes that don't match it.

   ```sh
   curl --fail -X PUT --upload-file "<file>" -H "<header>: <value>" ... "<url>"
   ```

   On Windows use `curl.exe`: in Windows PowerShell, `curl` is another command.
3. **Describe it** once it has landed: `media_save` with its `id` (or `items`, up to
   50) and `description`, `tags` and `metadata`. An upload you PUT can't carry them.
   A file that came back `existing: true` already has its own description and tags:
   `media_save` replaces them, so leave it alone unless the user asks.

Apps that show widgets never get `url` — the box is the way there.

Either way the file is recorded on its own once it arrives: pass the `id` to
`posts_save`, `media_save` or anything else that takes a media id. It shows in
`media_list` within a few minutes.

**Source material.** `purpose: source` keeps raw material to find and reuse —
generated takes, recordings, sound effects, saved memes. It is listed only by
`media_list` with `purpose: source`, never posted or used by a campaign as it is,
and `media_delete` can't remove it. The default, `library`, is a file to post. The
content-production archive prepares these uploads; see its
[guide](../../../content-production/references/archive.md#keep-originals-in-viewprinter-too).

**A file already on the web**, such as a model's output link: pass `from_url`, with
`description`, `tags`, `metadata` and `purpose`, instead of uploading. ViewPrinter
fetches it, answering `fetching: true`, and records it within minutes; check with
`media_list` and `media_id`.

If a flow is interrupted after a successful PUT, use the id you already have —
do not start a new upload.

## What the client must be able to do

Read the file and make an HTTP PUT. If it cannot, say which step is unavailable
and use an already uploaded file, or ask the user to upload through ViewPrinter.

- **Do not pass the id anywhere until the PUT has succeeded.** A post naming a
  file that never arrived is refused as unknown media.
- **Never expose the signed upload URL** in a public post or a user-facing log.

## Deleting media

`media_delete` erases the stored file and its bytes. Nothing restores it, and a pending
post that uses the file loses its media. Source material can't be deleted this way.

- Delete only files the user named in this conversation, or confirmed by name after you
  listed them. Never delete to tidy up, to free space, or because a file looks unused.
- Before deleting, check `posts_list` for scheduled and draft posts that use the file and
  name them. Deleting a file one of those posts uses needs its own yes.
- Report exactly which files were deleted.

## Context

- Size and type are read back from storage rather than trusted from what you
  claimed.
- If a post reports the media as unknown, the PUT did not land. Retry the PUT
  while the URL is still valid, or start a new upload once it has expired.
- Pass `sha256` so a file the workspace already holds is never uploaded twice.
  `media_list` finds files by what they are — `search`, `tags`, `kind`, `purpose` —
  and each comes with a `url` to download it from. Ask for that link when you need
  the file; don't keep it.
