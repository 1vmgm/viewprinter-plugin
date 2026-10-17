# Source CC audio from Openverse

Openverse is a free search of openly licensed audio at `https://api.openverse.org`. Basic use needs no API key. The catalog holds about five million recordings, effects and ambience as well as music. Search it only in the cases below. Every other audio decision stays on [audio](audio.md).

## When to search

Search Openverse when the user asks for sound effects, SFX, ambience, sound design, a music bed, background music, or royalty-free or CC music, or when they name Openverse. Also search when a video being produced needs a bed or effects, and neither the brief, the project library, nor the [source archive](archive.md) already has a suitable clip.

Leave Openverse alone for a still, a carousel, a concept list, a revision that does not change audio, and a tool check that is not yet sourcing a clip. Dialogue or a narrator that already carries the story does not gain a bed. A saved audio direction that names a treatment is followed; Openverse fills a bed or an effect that direction asks for and does not already have.

A trending platform sound stays on the audio page. Openverse is not that catalog, and a request for fresh or trending music does not start a search here. A supplied track, a sound ID, or an archive hit is used as the audio page says. When the user said not to call external services, write the query and the fields you would record, and send nothing.

An editor is still chosen the way [tools](tools.md) describes. Sourcing a clip does not install or replace it.

## Search

`GET https://api.openverse.org/v1/audio/` with `Accept: application/json`. The site root is HTML documentation, not the search. One request per cue, `page_size` 10, first page only. Refine the words once if that page has nothing usable. Do not walk `page_count`, and do not bulk-download the catalog.

| Parameter | Use |
|---|---|
| `q` | The cue, at most 200 characters. Spaces mean both terms. Quotes mark an exact phrase, a vertical bar means either term, and a leading minus excludes a word. |
| `source` | `freesound` for effects and ambience. Names come from `GET /v1/audio/stats/` (`source_name`). |
| `category` | `music` for a bed. Documented values also include `sound_effect`, `audiobook`, `news`, `podcast`, and `pronunciation`. |
| `length` | `shortest` (under 30 seconds), `short` (30 seconds up to two minutes), `medium` (two to ten minutes), `long` (longer). |
| `license` | A comma-separated list: `cc0`, `pdm`, `by`, `by-sa`, `by-nd`, `by-nc`, `by-nc-sa`, `by-nc-nd`. `sampling+` and `nc-sampling+` are deprecated. |
| `license_type` | `commercial` (no non-commercial clause), `modification` (derivatives allowed), `all`, or `all-cc`. Comma-separated types intersect. |

`duration` on each result is the exact length in milliseconds, or null. The `length` band is only a pre-filter. `creator`, `title`, and `tags` cannot be combined with `q`. Leave `mature` off. Leave `filter_dead` at its default, true. Skip any parameter whose name starts with `unstable__`.

Effects and ambience on Freesound leave `category` empty. `category=sound_effect` can return nothing while the same words match those recordings. For an effect, set `source=freesound` or omit `category`. If a `sound_effect` search is empty, search again without `category` before deciding the catalog has no match. For a bed, keep `category=music`. If that page is thin, widen the license or the words; dropping `category` mixes effects into a music search.

```sh
curl -fsSL -H "Accept: application/json" \
  "https://api.openverse.org/v1/audio/?q=whoosh&source=freesound&license=cc0&length=shortest&page_size=10"
```

```sh
curl -fsSL -H "Accept: application/json" \
  "https://api.openverse.org/v1/audio/?q=acoustic&category=music&license=by&length=medium&page_size=10"
```

Pass either `license` or `license_type`. Passing both keeps only licenses that sit in both sets. Anonymous responses report `x-ratelimit-limit-anon_burst`, `x-ratelimit-limit-anon_sustained`, and the matching `x-ratelimit-available-*` counts. A recent ceiling is 20 requests a minute and 200 a day; the headers are the limit that applies. A few searches per batch is the shape. On HTTP 429, or when the sustained remaining count is nearly spent, stop and say so. Do not register an Openverse application, and do not ask for a token, unless the user already has one. A token the user already supplied is `Authorization: Bearer`; it never goes into project memory or the archive record.

## Pick

Read `title`, `tags`, `creator`, `source`, `category`, `duration`, `license`, `license_version`, and `attribution` before choosing. A title match is not a fit. Listen to the file. If it cannot be played here, say the pick is unlistened and leave it uncommitted. Prefer a clean effect over a clip that already mixes speech. One clip per cue. The mix judgment stays on the audio page: not every action needs a sound.

For a paid ad or any commercial use, start an effect or ambience search with `license=cc0,pdm`. Widen to `license_type=commercial,modification` only when that page has nothing that fits, and then prefer `by` over `by-sa`.

Music is different. Everything under `category=music` comes from Jamendo under a CC BY-family license, so `category=music&license=cc0,pdm` returns nothing, and its tracks are whole songs: `length=short` or `shortest` usually returns nothing too, so search `medium` and cut the excerpt (checked against the live API in October 2026; `GET /v1/audio/stats/` lists the sources). A commercial bed from Openverse is therefore `license=by`, with its attribution shipped, or `by-sa` once the user has heard what share-alike asks. When the ad cannot carry a credit, look for a CC0 loop or bed on Freesound instead (`source=freesound&license=cc0`, no `category`, words such as `loop`, `ambient` or `beat`), or use a supplied or licensed track.

For any of these, refuse a license that contains `nc` (no commercial use) or `nd` (no derivatives) once the track will be cut, mixed, or synced to picture. `by-sa` allows commercial use and edits, and it also requires the adaptation to stay share-alike: tell the user before it goes into an ad. Skip `sampling+` and `nc-sampling+` unless the user asks for that license.

## Download

Download the result's `url`. If that request fails, take the next result. For Freesound, `url` is its high-quality MP3 preview, and the original file in `alt_files` needs a Freesound login (anonymous requests get HTTP 401), so use `alt_files` only with a Freesound token the user already has. Do not scrape the landing page for a different file. Name the file with the Openverse id plus the result's `filetype`. A Wikimedia title can contain HTML, so the title is not a filename. Jamendo's `mp32` is that provider's mp3 download; keep the bytes as returned and record the filetype, without transcoding at this step.

Search the archive before downloading. `archive.py find --text` matches the Openverse id once a record stores it. A hit is checked out, not downloaded again.

```sh
python3 <skill-directory>/scripts/archive.py find --text "<openverse id>"
python3 <skill-directory>/scripts/archive.py add --file <download> --format <format-id> --record - <<'JSON'
{"origin": "licensed", "tool": "openverse",
 "rights": {"source": "https://api.openverse.org/v1/audio/<id>/", "license": "<license>",
            "allowedUses": ["commercial"]},
 "tags": ["sound-effect"],
 "openverseId": "<id>", "title": "<title>", "creator": "<creator>",
 "attribution": "<attribution, verbatim>", "licenseUrl": "<license_url>",
 "foreignLandingUrl": "<foreign_landing_url>", "durationMs": 3155,
 "batchId": "<batch>", "itemId": "<item>"}
JSON
```

Use the tag `music` for a bed and `sound-effect` for an effect or ambience. `allowedUses` lists only what the license actually allows; a non-commercial license does not get `commercial`. Omit the download URL after the file is archived. It is not needed, and a signed or tokenized URL does not belong in the record. Leave `cost` out: the search and the file are free, and a zero is not a figure the API reported.

## Record the license

Copy `attribution` verbatim. It is the plain-text credit Openverse generated for that recording. `cc0` and `pdm` do not require credit; still record the license, the Openverse id, `license_url`, and the attribution string so a later reuse knows why no credit is owed. `by` and `by-sa` require credit. The string travels with the clip: in the archive record, and on the credit surface the project already uses (caption, description, or end card). If the project has none, keep the string on the item and tell the user it has to ship with the published video.

Also record `license_version`, `creator_url` when present, `source`, `category`, and `detail_url`. The download is that license and no more. Do not infer a platform-sound clearance, an exclusive, or a right the deed does not give.

The excerpt, the loop, and the mix are the audio page's, after the file is archived. Selected clips join that page's library question once per batch. This page does not upload them.
