# captions: Write for this video on this platform, and edit words without touching delivery

## Priority: MEDIUM

## What goes wrong

- A generic one-liner plus hashtags, or a caption that repeats the on-screen text,
  wastes the description.
- A literal `\n` is sent instead of a newline, and the caption arrives as one block.
- Editing words also passes `scheduled_at`, which re-queues destinations that failed.
- A shared caption is edited for one platform and silently changes the others.

## Writing it

- **Start from the user's brief**: its voice, lengths, calls to action and punctuation
  rules. Those are the user's choices, not this skill's.
- **Give the caption one job**: deepen the story, explain a benefit, answer an
  objection, invite discussion, or drive one action. Do not stack a question, a save
  prompt, a link and a keyword request. When the description asks for a comment
  keyword to receive a link, omit a direct URL and a competing link-in-bio CTA.
  Deliver the requested link through the agreed reply or DM workflow.
- **Open with something specific** (an incident, a contradiction, a question, a
  payoff) that makes sense before the reader expands it. Add what the video does not
  already say, then keep the promise the opening made.
- **Stay truthful.** Check dates, names, numbers and the features shown. Never invent a
  customer's experience or promise a legal, medical or financial result.
- **Keep it readable**: one thought per sentence, short paragraphs, real newline
  characters, and hashtags in their own final block. A few relevant hashtags, not a
  wall of reach tags.
- **Write like a person talking about this moment.** Cut stock phrases ("game-changer",
  "let's dive in") and lessons the story has not earned. Test it: if the caption would
  fit three unrelated videos unchanged, it says nothing about this one.
- Check lengths with `platforms_list`; whitespace and emoji count.

## Per platform

- **Facebook** rewards a description worth opening. When the user wants traffic, put
  the approved link on its own line and check how it renders.
- **Instagram** Reels suit substantive copy with one clear next step. A keyword request
  ("comment GUIDE") is only a promise if someone will fulfil it; don't promise an
  automated DM unless it's set up and verified.
- **TikTok** wants a faster opening and a body sized to what the video already
  explains. Don't paste the Instagram caption by default.

No caption length is proven to win everywhere, and no hashtag guarantees
distribution. Treat a caption change as a test, compare posts of similar age, and
describe the expected effect as a hypothesis until results support it.

## Editing a queued post

Read the post's destinations first: `content` may be shared by all of them.
Check the full revised description for competing CTAs, including URLs in separate
paragraphs. When removing a link, also fix phrases such as "start below" or "take a
look below" so they do not point to a missing destination.

- When every affected destination is in scope, call `posts_save` with only `post_id`
  and `content`. Never pass `scheduled_at` just to change words.
- When only one destination's words should change, create that destination as its own
  held post with the same media, time and options, remove it from the original by
  sending the remaining account ids, verify the original can no longer deliver there,
  then release the new one. Keep the two post ids together.
- A published post's words change only through a supported edit. Never delete and
  re-upload one to change its caption, and say which posts stayed unchanged.

## Context

- Trial reels and disclosure labels are covered in `scheduling`; a caption edit changes
  neither.
