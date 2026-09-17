# platforms-first: Ask what each platform accepts, never recall it

## Priority: CRITICAL

## What goes wrong

A post is composed against remembered limits — a caption length, a media count,
"Instagram takes video" — and the server refuses it. The refusal arrives after
the work is done, and the guess at why is usually wrong.

Worse, a limit written into this file is true until the day it is not. Platforms
change what they accept, and a new platform can be added without this file
changing. Anything stated here is a claim with an expiry date.

## What to do instead

Call `platforms_list` **first**, naming the platforms you intend to post to.

With no arguments it returns every platform that can publish, with its accepted
media kinds, counts and caption limit. Naming platforms adds recommended sizes
and durations, the per-platform options, and the quirks that change how a post
is treated.

This is cheaper than composing a post, having it refused, and guessing.

## Three shapes that eliminate whole plans

Check these against `platforms_list` rather than trusting the summary here, but
know they exist, because each rules out an approach before you start:

- **A post is either a video or a set of images, never both.** There is no
  arrangement of `media_ids` that mixes them.
- **At least one platform cannot post images at all** and needs a video.
- **At least one platform accepts a caption with no media**, and the others
  refuse a text-only post.

`platforms_list` says which is which. Do not name them from memory.

## Context

- Applies before every compose, not once per conversation.
- `platform_options` keys are per platform and an unknown key is refused rather
  than ignored — `platforms_list` is where you learn what is valid.
