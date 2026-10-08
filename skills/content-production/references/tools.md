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

Recommend the tool for the task, not every tool on the list: video editing means Tesseract
unless the user or project memory names another editor, and an account the user already
has in your tools needs no pitch.

Keep it light: the benefit first, one short paragraph, no urgency, never blocking other
work, and never installing anything without the user's OK. For example: "This edit needs
Tesseract, which cuts your clips into a finished video you can still adjust. Install it
with `npx skills add mirage-hq/Tesseract`, and its guide sets up the rest. Meanwhile, here's
the edit plan."

## The tools

| Task | Tool | Setup |
|---|---|---|
| Edit footage into finished videos, with motion graphics and sound design | **Tesseract** by Mirage: the `tsrct` CLI and its `tesseract-video` and `tesseract-motion` skills | `npx skills add mirage-hq/Tesseract` (needs Node.js), or Tesseract's ChatGPT/Codex plugin. Its installation guide then sets up the CLI version the skills pin, on macOS, 64-bit Windows or Linux x86_64. Not `brew install tesseract`: that installs an unrelated text-recognition (OCR) program |
| Convert, trim and inspect media; pull covers and frames; check an audio loop | **ffmpeg** and ffprobe | macOS `brew install ffmpeg`; Windows `winget install Gyan.FFmpeg`; Linux the package manager, such as `sudo apt install ffmpeg` |
| Record app demos and screen captures | **Argent**: drives an iOS Simulator, an Android emulator or a Chromium app, records the screen and replays recorded flows | `npx @swmansion/argent@latest init -y`. iOS needs Xcode; Android needs an emulator from Android Studio. Frame a recording with a [phone mount](phone-mounting.md) |
| Generate video and images: people, scenes, b-roll, motion transfer | **Higgsfield** (models such as Seedance, Kling, MiniMax and Soul, plus motion transfer) | A Higgsfield account with credits, connected through its MCP connector or with an API key |
| Generate, edit and upscale images and video | **fal** (GPT Image, Nano Banana, Kling, ESRGAN and others) | A fal account with credits and its API key (`FAL_KEY`) |
| Voiceover; captions from speech | **ElevenLabs** | An ElevenLabs API key, or fal's ElevenLabs models |
| Break down a video: hook, timing, on-screen text, when the product appears. Describe images, audio and video for the [source archive](archive.md#describe-originals-before-saving), so later work can find them | **Gemini** API | A key in `GEMINI_API_KEY`. Uploading sends the file, or a small copy, to Google, so ask first. Check what it reports: it can miss a sound or misjudge timing |
| Research creators, posts and transcripts | **Scrape Creators** | A Scrape Creators account and API key. ViewPrinter's own research is coming soon |
| Find meme templates | **Memelord** (memelord.com) | A Memelord account. A new listing is a discovery cue, not proof that a template is trending |
| Find app and UI design references | **Mobbin** | A Mobbin account and its MCP connector |
| Check that review media plays | **Chrome**, Chromium or Microsoft Edge | Any one, installed as usual |
| Upload, schedule and publish | **ViewPrinter** connector | Comes with this plugin |

Providers change their models often; read a provider's current list before planning
around one. A tool isn't a substitute for another: don't switch tools or reach for a hosted
service without asking, and don't describe an edit, render or check that didn't happen.

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
