# Tools for each task

This plugin plans, reviews and publishes with Python and the ViewPrinter connector alone.
Making the media takes other tools, and the user gets the most from it with them set up.
Help them get there: when a task in front of you needs a tool they don't have, recommend
it, then respect their answer.

```sh
python3 <skill-directory>/scripts/tools.py check --json
```

`check` finds the local programs and reports, for every tool, its `id`, what it unlocks,
how to install it and `mention`: when to bring it up. An account whose API key is set shows
`ready: true` and `mention: ready`, with a `detail` naming the key and where it is set: the
environment, the project's `.env` or `.env.local`, or a keys file the user named (see
[keys and records](#keys-and-records)). It needs no pitch. Other accounts and connectors show
`ready: null`; see whether they are in your own tools. Argent's MCP tools in your tool list
count as Argent installed. The user's answers live in `~/ViewPrinter/tools.json`, so they
apply to every project on this machine.

## Recommend at the right moment

- **A task needs a missing tool** (`mention: offer`): say what the tool would do for this
  task, the step that installs it, and what you'll do meanwhile. Then run
  `tools.py remember <id> not-now` straight away, so it isn't raised again: no answer
  counts as "not now". It stays quiet for 14 days, then 30, then 60. If they say not to
  ask again, run `tools.py remember <id> never`. If they install it, `check` reports it
  ready; use it.
- **First production session on a machine** (`introduce` is true): once the user's request
  is under way, give one short setup summary: what's ready, then the tools still at
  `mention: offer` that their work is likely to need, each with what it unlocks and its
  install step. If the request needs one of them, lead with it: the summary is that tool's
  recommendation, so don't repeat it. Then run `tools.py introduced`. It is an overview,
  not a checklist to complete.
- **`mention: quiet`**: don't ask again. Do the work that doesn't need it, and name the gap
  in one clause so the result isn't mistaken for the whole deliverable.
- **`mention: never`**: don't suggest it. If the user asks for that task, say it needs the
  tool, and set it up only if they want to. When they want suggestions back,
  `tools.py remember <id> reset`.

Recommend the tool for the task, not every tool on the list. Footage editing defaults to
Tesseract unless the user or project memory names another editor, and a 3D device shot means
Remotion. HTML-authored motion graphics, slideshows and templated batches use HyperFrames
when it is installed or when the project or the user names it; Tesseract stays the default
otherwise. An account the user already has in your tools needs no pitch.

Keep it light: the benefit first, one short paragraph, no urgency, never blocking other
work, and never installing anything without the user's OK. For example: "This edit needs
Tesseract, which cuts your clips into a finished video you can still adjust. Install it
with `npx skills add mirage-hq/Tesseract`, and its guide sets up the rest. Meanwhile, here's
the edit plan."

## The tools

| Task | Tool | Setup |
|---|---|---|
| Edit footage into finished videos, with motion graphics and sound design | **Tesseract** by Mirage: the `tsrct` CLI and its `tesseract-video` and `tesseract-motion` skills | `npx skills add mirage-hq/Tesseract` (needs Node.js), or Tesseract's ChatGPT/Codex plugin. Its installation guide then sets up the CLI version the skills pin, on macOS, 64-bit Windows or Linux x86_64. Not `brew install tesseract`: that installs an unrelated text-recognition (OCR) program |
| 3D device shots, openers and motion graphics written as code: a lit 3D device with the real recording as its screen, UI layers lifted in depth, a camera move that lands on the edit's first frame | **Remotion** with `@remotion/three` (three.js), and Remotion's own agent skills | `npx skills add remotion-dev/skills` (needs Node.js); each video project installs `remotion` and `@remotion/three` with npm. See [3D shots](#3d-shots). Free for individuals and companies of up to 3 people; larger companies need a company licence from remotion.pro |
| Motion graphics, explainers, captioned clips, slideshows and product-launch videos from HTML, CSS and JS; a batch of variants from one template | **HyperFrames** by HeyGen, Apache-2.0. Compositions are HTML. Render-time variables fill each variant (`npx hyperframes render --batch`, or `--variables` for one set). A slideshow is a navigable deck (`present`, or `snapshot` for stills); `render` on a deck writes only the first slide | `npx hyperframes skills update`, or `npx skills add heygen-com/hyperframes`. Needs Node.js 22+ and Chromium; the CLI downloads a pinned Chrome (`npx hyperframes browser ensure`). A local render also needs FFmpeg. Renders on this machine, or through HeyGen's [Cloud Rendering API](https://developers.heygen.com/hyperframes-overview). A cloud render spends credits |
| Convert, trim and inspect media; pull covers and frames; check an audio loop | **ffmpeg** and ffprobe | macOS `brew install ffmpeg`; Windows `winget install Gyan.FFmpeg`; Linux the package manager, such as `sudo apt install ffmpeg` |
| Record app demos and screen captures | **Argent**: drives an iOS Simulator, an Android emulator or a Chromium app, records the screen and replays recorded flows | `npx @swmansion/argent@latest init -y`. iOS needs Xcode; Android needs an emulator from Android Studio. Frame a recording with a [phone mount](phone-mounting.md) |
| Generate video and images: people, scenes, b-roll, motion transfer | **Higgsfield** (models such as Seedance, Kling, MiniMax and Soul, plus motion transfer) | A Higgsfield account with credits, connected through its MCP connector or with an API key |
| Generate, edit and upscale images and video | **fal** (GPT Image, Nano Banana, Kling, ESRGAN and others) | A fal account with credits and its API key (`FAL_KEY`) |
| Voiceover; captions from speech | **ElevenLabs** | An ElevenLabs API key, or fal's ElevenLabs models |
| Break down a video: hook, timing, on-screen text, when the product appears. Describe images, audio and video for the [source archive](archive.md#describe-originals-before-saving), so later work can find them | **Gemini** API | A key in `GEMINI_API_KEY`. Uploading sends the file, or a small copy, to Google, so ask first. Check what it reports: it can miss a sound or misjudge timing |
| Find relevant social posts and examples | **ViewPrinter** `research_ask`, when exposed by the connected server | Use the live schema; see [research requests](#research-requests) |
| Research social videos and Meta ads, including video inspection | **Lightreel** connector | Connected account with research credits; save the conversation ID and poll the existing request |
| Retrieve creator posts and transcripts | **Scrape Creators** | A Scrape Creators account and API key |
| Find meme templates | **Memelord** (memelord.com) | A Memelord account. A new listing is a discovery cue, not proof that a template is trending |
| Find app and UI design references | **Mobbin** | A Mobbin account and its MCP connector |
| Check that review media plays | **Chrome**, Chromium or Microsoft Edge | Any one, installed as usual |
| Upload, schedule and publish | **ViewPrinter** connector | Comes with this plugin |

Providers change their models often; read a provider's current list before planning
around one. A tool isn't a substitute for another: don't switch tools or reach for a hosted
service without asking, and don't describe an edit, render or check that didn't happen.

A provider's MCP connector and direct API can expose different model IDs, availability
and billing. Before paid submission, apply any saved route or wallet preference and
verify the requested model and mode on that route. An available connector does not
override an API-first preference; record why a fallback is needed. A model-not-found
response applies to the endpoint tried, not to the whole
provider: check the chosen route's live catalog before declaring it unavailable or
proposing a different provider. Keep the user's provider choice and recover any accepted
job before submitting a replacement. Record the route, workspace or wallet, and quoted
units; don't transfer subscription discounts or credit balances to API-dollar estimates.
If a preflight rounds credits differently from its exact value, preserve both as an
estimate and reconcile against the completed job or transaction before reporting spend.

## 3D shots

Tesseract tilts flat layers in 3D but has no camera, lights or device body. For a real 3D
moment, such as a device floating in a lit studio, UI lifting off the screen or a fly-in, build
it in Remotion and import the render into the Tesseract edit as a clip:

- Keep the screen real: the device's screen is the actual recording, mapped as a texture
  with tone mapping off so the UI colours stay exact. Never generate or repaint UI.
- Land on the edit: the last frame matches the next shot's framing exactly, so the cut to the
  flat walkthrough is invisible. Render opaque on the edit's background, or ProRes 4444 with
  alpha when the edit composites it.
- On Remotion 4, render with `--gl=angle` (`--gl=swangle` on a machine without a GPU); its
  default renderer draws three.js scenes blank.
  Check stills with `npx remotion still --frame=N` before a full render.
- Mind the platform's device rules. Apple's marketing guidelines forbid 3D renders and
  simulations of Apple products and tilting, animating, or graphics that appear to come out
  of their screens, and ask for Apple's own bezels used as is. A 3D shot therefore uses a
  generic device with no maker's details, or the user decides that risk knowingly.

## Research requests

When the user asks for outside research, check the connected tools' live schemas.
For ViewPrinter `research_ask`, get the product ID from `products_list`, submit the
question once, save the returned thread ID, and poll that ID while it is working.
Include ads explicitly when researching paid creative; the default excludes posts
marked as ads. Use an explicit date window for historical examples. A broad format
study may need `fit: all` so product relevance does not hide cross-category examples.

Verify platform coverage from returned post URLs. A request for Instagram can return
TikTok examples; label them as adjacent evidence and obtain Instagram sources before
claiming Instagram research is complete. Preserve the provider’s metric names: video
views, plays, reach and impressions are not interchangeable. Retain retrieval dates
and distinguish sampled keyword comments from totals or conversion evidence.

Treat generated hooks, structures and explanations as leads to inspect, not measured
causes of performance. Views and outperformance do not establish conversion; an
unflagged post does not establish the absence of all paid support. Inspect the media
before publishing a timed breakdown, check times against its measured runtime, and
keep missing conversion data explicit. A schema description and populated response
fields can disagree: record the discrepancy rather than silently treating either as
verified creative evidence.

For technical video breakdowns, distinguish visible controls and demonstrated steps from
model-inferred explanations. Cross-check important model names, settings and timings
against legible source frames or the chosen route’s current schema. A plausible video
analysis is not proof of an exact workflow; label proposed prompts as untested until
they work on the intended footage.

## Keep the user informed on spending

Generation, research credits, voice and video analysis can all cost money. Paid generation
needs the spend limit in [the skill](../SKILL.md). For every paid step:

- Before it, say what it's for and what it should cost.
- After it, say what it cost, or that the provider didn't report a cost, and the running
  total, against the limit when there is one.
- Before a step that would take the total past the limit, stop and ask.
- At handoff, give the batch total beside the per-asset costs in the review.

Use the provider's reported figures where it gives them, and say when a figure is an
estimate. Never guess credits. Show a balance only with the time it was read.

## Keys and records

Keep API keys in the environment or the project's git-ignored secrets file, never in a
manifest, catalog record, review page or the conversation. When the user keeps their keys in
a file of their own, such as one `.env` shared by several projects, record it once:

```sh
python3 <skill-directory>/scripts/tools.py keys add <file>
```

Only its path is kept. `check` reads the names that file sets, never shows a value, and
reports an account ready when its key is there, so you don't recommend an account the user
already has. `keys list` shows each file and the accounts whose keys it sets; `keys remove
<file>` forgets one. Never print, copy or repeat a key's value. Record the tool, model and
version that made each asset, in its generation record and the [archive](archive.md), so a
later batch can repeat it or avoid it. `check` reports Tesseract ready when it finds the CLI;
Tesseract's own skills check that it is the version they pin, and their guide updates it.
`check` reports HyperFrames ready when it finds the `hyperframes` command on PATH or in the
project's `node_modules/.bin`.
