# The Fragrance Gazette — v4

Rebuilt to match the person's own design mockup: launches first, then
events, then the three named YouTube influencers, then everything else
last. No week/month recap framing anywhere — this rebuilds "current
state" fresh each run, so nothing repeats between editions the way a
weekly-vs-monthly split was doing before.

## What changed from v3

- **Dropped**: Top-Buyed (FragranceX), the separate Trends section
  (Pantone/Pinterest/regional table), the heavy per-section warning
  boxes. None of these were in the person's mockup, and the wordiness
  was an explicit complaint.
- **Added**: Top-Discussed Fragrance — Jeremy Fragrance, CurlyFragrance,
  and Redolessence's YouTube uploads from the last 60 days, tagged by
  brand where detectable, with a best-effort "characterization" pulled
  from sentiment words in the title/description.
- **Reordered** to match the mockup exactly: Launches → Events →
  Influencers → Feeds.

## Confidence per source (short version — see comments in the script for detail)

| Source | Method | Confidence |
|---|---|---|
| Now Smell This | RSS, filtered by URL pattern | High |
| T3 | Guessed monthly URL, no feed exists | Low |
| TrendAroma | Live scrape | Medium |
| 3 YouTube influencers | Channel ID resolved live, official RSS | Medium-High — the RSS mechanism is rock solid once the ID resolves; resolving the ID is the one step that could break if YouTube changes its page structure |
| Givaudan / IFF / Symrise / dsm-firmenich | Generic keyword-link scrape | Medium |
| Nez / Fragrantica / Premium Beauty News | RSS, best-guess URLs | Low-Medium |

## On the "characterization" column — read this before trusting it

It is a keyword match against SENTIMENT_WORDS in `fetch_and_build.py`
(words like "obsessed," "disappointing," "overhyped") found in the video's
own title or description. It is **not** a transcript summary — I cannot
watch or transcribe the videos. When no sentiment word is found, it
honestly says "mentioned in a recent video" rather than inventing one.
Treat it as a rough signal, not a quote of what was actually said.

## On images

No real product photos — a published page can't load external images,
and generating fake photos of real trademarked bottles (Chanel, Dior,
etc.) isn't something built here regardless of format. The design uses
typography and a red accent instead, in the spirit of the mockup rather
than a literal photographic copy of it.

## Setup — from scratch (your second attempt also failed, so full detail this time)

1. **Delete both old repos**, or at minimum don't reuse either — start
   completely clean to rule out leftover settings causing confusion.
2. New repo → Public → no README/gitignore/license checkboxes ticked.
3. "Uploading an existing file" → select everything **inside** the
   extracted folder (not the folder itself) → drag in → commit.
4. **Settings → Actions → General → Workflow permissions → "Read and
   write permissions" → Save.** This is the single most commonly missed
   step and the most likely reason nothing updated last time.
5. **Settings → Pages → Source: "Deploy from a branch" → Branch: main,
   folder: /docs → Save.**
6. **Actions tab → "Update Fragrance Gazette" → Run workflow** (the
   dropdown button, then the green button that appears).
7. Click into the run, open "Build the page," read the last two lines
   of the log. It prints an exact count for every single source:
   `launches: nst=X t3=Y | events=Z | Jeremy Fragrance=A CurlyFragrance=B
   Redolessence=C | feed_items=D`
   Any zero tells you exactly which source needs attention — not a
   guess, an exact number.
8. Visit your Pages URL. If it 404s, wait 2 minutes and refresh — Pages
   takes a moment to go live after first enabling.

## If a YouTube influencer shows 0

Most likely `resolve_channel_id` couldn't find the channel ID pattern
on the @handle page — YouTube's page structure is stable but not
contractually guaranteed. Check the log for which handle failed; if
this becomes a recurring problem, the channel ID can be hardcoded
directly in `INFLUENCERS` in `fetch_and_build.py` instead of resolved
live (ask for help doing this if the log shows a persistent failure).
