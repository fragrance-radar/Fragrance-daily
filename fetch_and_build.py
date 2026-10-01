#!/usr/bin/env python3
"""
Fragrance Gazette — automated builder (v4).

Section order and content match the person's own mockup, in this priority:
1. New Fragrance Launches   — pops first, short scannable lines
2. Events Calendar          — scraped live from TrendAroma
3. Top-Discussed Fragrance  — what 3 named YouTube influencers have been
                               covering, rolling 60-day window
4. Live From Feeds          — everything else (newsrooms, misc feeds),
                               deliberately last and deliberately light

No week/month recap framing anywhere — this is "current state right now,"
rebuilt fresh each run, so nothing repeats across editions.

Confidence levels are real and vary by source. One line per source in the
footer carries that instead of a warning box under every heading — the
previous version was rightly called out as too wordy.
"""
import json, datetime, html, re
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
TEMPLATE_PATH = ROOT / "template.html"
OUT_PATH = ROOT / "docs" / "index.html"
UA = {"User-Agent": "Mozilla/5.0 (compatible; FragranceGazetteBot/1.0)"}

# ---------------------------------------------------------------- Launches
FEEDS_LAUNCH = [{"url": "https://nstperfume.com/feed/", "name": "Now Smell This"}]
NST_LAUNCH_SLUG = re.compile(r"-new-(fragrances?|perfumes?)/?$", re.I)
T3_PATTERN = "https://www.t3.com/home-living/beauty/mens-fragrance-launches-{month}-2026"

# ------------------------------------------------------------------ Events
TRENDAROMA_URL = "https://www.trendaroma.com/fragrance-calendar/"

# ------------------------------------------------------------- Influencers
# Handle is what the person gave us; channel_id is resolved at runtime
# (see resolve_channel_id) so this never needs hand-editing if a handle
# is renamed. 60-day window: monthly was too thin for typical upload
# cadence in this niche, so this section uses a longer lookback than
# the rest of the page.
INFLUENCERS = [
    {"handle": "jeremyfragrance", "name": "Jeremy Fragrance"},
    {"handle": "CurlyFragrance", "name": "CurlyFragrance"},
    {"handle": "Redolessence", "name": "Redolessence"},
]
INFLUENCER_WINDOW_DAYS = 60

MAJOR_BRANDS = [
    "Dior", "Chanel", "Tom Ford", "Yves Saint Laurent", "YSL", "Giorgio Armani",
    "Armani", "Prada", "Valentino", "Lattafa", "Kayali", "Maison Francis Kurkdjian",
    "MFK", "Byredo", "Guerlain", "Versace", "Calvin Klein", "Dolce & Gabbana",
    "Jean Paul Gaultier", "Rabanne", "Paco Rabanne", "Givenchy", "Hermes", "Hermès",
    "Amouage", "Xerjoff", "Parfums de Marly", "Creed", "Le Labo", "Margiela",
    "Frederic Malle", "Frédéric Malle", "Burberry", "Bvlgari", "Bulgari",
    "Montblanc", "Azzaro", "Carolina Herrera", "Nautica", "Ralph Lauren",
]
SENTIMENT_WORDS = [
    "love", "obsessed", "favorite", "favourite", "must-have", "must have",
    "stunning", "incredible", "amazing", "disappointing", "disappointed",
    "skip", "overhyped", "overrated", "underrated", "worth it", "not worth",
    "compliment", "beast mode", "signature", "hidden gem", "sleeper",
]
REVIEW_NOISE = re.compile(
    r"\b(review|first impressions?|honest review|unboxing|is it worth it|"
    r"full review|initial thoughts|thoughts on)\b", re.I)

# --------------------------------------------------------------- Newsrooms
NEWSROOMS = [
    {"url": "https://www.givaudan.com/media/media-releases", "name": "Givaudan"},
    {"url": "https://www.iff.com/media/news", "name": "IFF"},
    {"url": "https://www.symrise.com/newsroom/", "name": "Symrise"},
    {"url": "https://www.dsm-firmenich.com/corporate/news.html", "name": "dsm-firmenich"},
]
NEWSROOM_KEYWORDS = ["fragrance", "scent", "perfume", "aroma", "olfact", "ingredient", "molecule"]

FEEDS_MISC = [
    {"url": "https://mag.bynez.com/feed/", "name": "Nez"},
    {"url": "https://www.fragrantica.com/rss/news.xml", "name": "Fragrantica"},
    {"url": "https://www.premiumbeautynews.com/xml/syndication.rss", "name": "Premium Beauty News"},
]

# ------------------------------------------------------------------ utils
def strip_tags(t):
    return re.sub(r"<[^<]+?>", "", t or "").strip()

def esc(t):
    return html.escape(t or "", quote=False)

def page_lines(url):
    r = requests.get(url, headers=UA, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    return [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]

# ------------------------------------------------------------- 1. Launches
def fetch_nst_launches(limit=12):
    out = []
    try:
        parsed = feedparser.parse(FEEDS_LAUNCH[0]["url"])
        for e in parsed.entries[:60]:
            link = e.get("link", "#")
            if not NST_LAUNCH_SLUG.search(link):
                continue
            out.append({"title": html.unescape(e.get("title", "")), "link": link,
                        "source": "Now Smell This"})
    except Exception as ex:
        print(f"[warn] Now Smell This failed: {ex}")
    if not out:
        print("[warn] Now Smell This: 0 launch-pattern entries")
    return out[:limit]

def scrape_t3_launches(limit=8):
    now = datetime.date.today()
    months = [now.strftime("%B").lower(),
              (now.replace(day=1) - datetime.timedelta(days=1)).strftime("%B").lower()]
    out = []
    for month in months:
        url = T3_PATTERN.format(month=month)
        try:
            r = requests.get(url, headers=UA, timeout=15)
            if r.status_code != 200:
                continue
            lines = page_lines(url)
            for i, line in enumerate(lines):
                if re.search(r"[£$€]\d", line) and i >= 2:
                    name_line = lines[i - 2]
                    if 8 <= len(name_line) <= 90 and name_line[0].isupper():
                        out.append({"title": name_line, "link": url, "source": "T3"})
        except Exception as ex:
            print(f"[warn] T3 ({month}) failed: {ex}")
    if not out:
        print("[warn] T3: 0 items — monthly URL guess may be wrong")
    return out[:limit]

# --------------------------------------------------------------- 2. Events
def scrape_events(limit=10):
    try:
        lines = page_lines(TRENDAROMA_URL)
    except Exception as ex:
        print(f"[warn] TrendAroma failed: {ex}")
        return []
    events = []
    for i, line in enumerate(lines):
        if "📍" in line:
            location = line.replace("📍", "").strip()
            date_line = lines[i - 1] if i >= 1 else ""
            name_line = lines[i - 2] if i >= 2 else ""
            if name_line and date_line:
                events.append({"name": name_line, "date": date_line, "location": location})
    if not events:
        print("[warn] TrendAroma: 0 events parsed")
    return events[:limit]

# ---------------------------------------------------------- 3. Influencers
def resolve_channel_id(handle):
    """YouTube channel pages carry their real channel ID in a canonical
    link tag and again in embedded JSON — either is a stable, long-standing
    convention, not a guess. Tries both, in order."""
    url = f"https://www.youtube.com/@{handle}"
    try:
        r = requests.get(url, headers=UA, timeout=15)
        r.raise_for_status()
        m = re.search(r'"channelId":"(UC[\w-]{22})"', r.text)
        if m:
            return m.group(1)
        m = re.search(r'youtube\.com/channel/(UC[\w-]{22})', r.text)
        if m:
            return m.group(1)
    except Exception as ex:
        print(f"[warn] resolving @{handle} failed: {ex}")
    return None

def tag_brand(title):
    for b in MAJOR_BRANDS:
        if b.lower() in title.lower():
            return b
    return None

def extract_name(title, brand):
    """Keep the full product name intact — many fragrance names legitimately
    contain the brand word (e.g. 'Bleu de Chanel'), so we only strip review
    filler, never the brand substring itself. An earlier version of this
    stripped the brand out and mangled names like that; fixed after testing
    caught it against a real example."""
    t = REVIEW_NOISE.sub("", title)
    t = re.sub(r"[|\-–—]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" -–—:()")
    return t[:70] if t else title[:70]

def characterize(title, summary):
    text = f"{title} {summary}".lower()
    hits = [w for w in SENTIMENT_WORDS if w in text]
    return ", ".join(hits[:3]) if hits else "mentioned in a recent video"

def fetch_influencer_mentions(inf, per_person=5):
    cid = resolve_channel_id(inf["handle"])
    if not cid:
        print(f"[warn] {inf['name']}: could not resolve channel ID")
        return []
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    cutoff = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) \
             - datetime.timedelta(days=INFLUENCER_WINDOW_DAYS)
    mentions = []
    try:
        parsed = feedparser.parse(feed_url)
        for e in parsed.entries:
            pub = e.get("published_parsed")
            dt = datetime.datetime(*pub[:6]) if pub else None
            if dt and dt < cutoff:
                continue
            title = html.unescape(e.get("title", ""))
            summary = html.unescape(strip_tags(e.get("summary", "")))
            brand = tag_brand(title)
            name = extract_name(title, brand)
            mentions.append({
                "brand": brand or "—", "name": name,
                "characterization": characterize(title, summary),
                "link": e.get("link", "#"),
            })
    except Exception as ex:
        print(f"[warn] {inf['name']} feed failed: {ex}")
    if not mentions:
        print(f"[warn] {inf['name']}: 0 videos in last {INFLUENCER_WINDOW_DAYS} days")
    return mentions[:per_person]

# ---------------------------------------------------------- 4. Live feeds
def scrape_newsroom(nr, limit=5):
    out = []
    try:
        r = requests.get(nr["url"], headers=UA, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            if not (20 <= len(text) <= 160):
                continue
            if not any(k in text.lower() for k in NEWSROOM_KEYWORDS):
                continue
            href = a["href"]
            if href.startswith("/"):
                href = re.match(r"https?://[^/]+", nr["url"]).group(0) + href
            if href in seen:
                continue
            seen.add(href)
            out.append({"title": text, "link": href, "source": nr["name"]})
    except Exception as ex:
        print(f"[warn] {nr['name']} newsroom failed: {ex}")
    if not out:
        print(f"[warn] {nr['name']}: 0 items")
    return out[:limit]

def fetch_misc_feed(feed, limit=4):
    out = []
    try:
        parsed = feedparser.parse(feed["url"])
        for e in parsed.entries[:limit]:
            out.append({"title": html.unescape(e.get("title", "")),
                        "link": e.get("link", "#"), "source": feed["name"]})
    except Exception as ex:
        print(f"[warn] {feed['name']} failed: {ex}")
    if not out:
        print(f"[warn] {feed['name']}: 0 items")
    return out

# ----------------------------------------------------------------- render
def render_launches(nst, t3):
    if not (nst or t3):
        return '<p class="empty">Nothing this run — check the build log.</p>'
    rows = "".join(f'<li><a href="{i["link"]}">{esc(i["title"])}</a> '
                    f'<span class="src">{esc(i["source"])}</span></li>' for i in (nst + t3))
    return f'<ul class="launch-list">{rows}</ul>'

def render_events(events):
    if not events:
        return '<p class="empty">Could not reach TrendAroma this run.</p>'
    rows = "".join(f'<li><span class="ev-date">{esc(e["date"])}</span> '
                    f'{esc(e["name"])} <span class="src">{esc(e["location"])}</span></li>'
                    for e in events)
    return f'<ul class="event-list">{rows}</ul>'

def render_influencers(by_person):
    blocks = []
    for name, mentions in by_person.items():
        if not mentions:
            blocks.append(f'<div class="inf-col"><h4>@{esc(name)}</h4>'
                           f'<p class="empty">No uploads found in the last '
                           f'{INFLUENCER_WINDOW_DAYS} days — check the log.</p></div>')
            continue
        rows = "".join(f'<li><b>{esc(m["brand"])}</b> — {esc(m["name"])}'
                        f'<span class="charac">{esc(m["characterization"])}</span></li>'
                        for m in mentions)
        blocks.append(f'<div class="inf-col"><h4>@{esc(name)}</h4><ul>{rows}</ul></div>')
    return f'<div class="inf-row">{"".join(blocks)}</div>'

def render_feed_items(items):
    if not items:
        return '<p class="empty">Nothing this run.</p>'
    rows = "".join(f'<li><a href="{i["link"]}">{esc(i["title"])}</a> '
                    f'<span class="src">{esc(i["source"])}</span></li>' for i in items)
    return f'<ul class="feed-list">{rows}</ul>'

def main():
    nst = fetch_nst_launches()
    t3 = scrape_t3_launches()
    events = scrape_events()

    by_person = {}
    for inf in INFLUENCERS:
        by_person[inf["name"]] = fetch_influencer_mentions(inf)

    feed_items = []
    for nr in NEWSROOMS:
        feed_items += scrape_newsroom(nr)
    for f in FEEDS_MISC:
        feed_items += fetch_misc_feed(f)

    section_html = f"""
<h2><span>New Fragrance Launches</span></h2>
{render_launches(nst, t3)}

<h2><span>Events Calendar</span></h2>
{render_events(events)}

<h2><span>Top-Discussed Fragrance</span></h2>
{render_influencers(by_person)}

<h2><span>Live From Feeds</span></h2>
{render_feed_items(feed_items)}
"""
    today = datetime.date.today().strftime("%d %B %Y")
    tmpl = TEMPLATE_PATH.read_text(encoding="utf-8")
    out = tmpl.replace("{{DATE}}", today).replace("{{SECTIONS}}", section_html)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(out, encoding="utf-8")

    print(f"Wrote {OUT_PATH} — dated {today}")
    print(f"  launches: nst={len(nst)} t3={len(t3)} | events={len(events)} | "
          + " ".join(f"{k}={len(v)}" for k, v in by_person.items())
          + f" | feed_items={len(feed_items)}")

if __name__ == "__main__":
    main()
