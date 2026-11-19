#!/usr/bin/env python3
"""Update Fieldnotes from publisher RSS/Atom feeds; no secrets or third-party packages."""
from __future__ import annotations

import datetime as dt
import email.utils
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "latest.json"
CENTRAL = ZoneInfo("America/Chicago")
TOPICS = {
    "ai": "AI & Local Tech",
    "cyber": "Cybersecurity & GRC",
    "kc": "Kansas City",
    "business": "Business & Economy",
    "policy": "Policy & Infrastructure",
    "maker": "Maker Lab",
    "home": "Smart Home",
    "garden": "Homestead & Garden",
}
# Each source is a publisher feed, not a scraped search result.
# A matching pattern is optional; it limits broad publications to pertinent stories.
FEEDS = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "ai", None),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/", "ai", r"\b(ai|artificial intelligence|machine learning|llms?|agents?|ollama|nvidia|local models?)\b"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "ai", r"\b(ai|local models?|gpu|rtx|ollama|automation|agents?|microsoft)\b"),
    ("The Record", "https://therecord.media/feed", "cyber", None),
    ("BleepingComputer", "https://www.bleepingcomputer.com/feed/", "cyber", None),
    ("KCUR", "https://www.kcur.org/feed", "kc", r"\b(kansas city|missouri|kansas|lee.s summit|jackson county|independence|business|housing|transportation|jobs|election)\b"),
    ("Startland News", "https://startlandnews.com/feed/", "kc", None),
    ("NPR Business", "https://feeds.npr.org/1006/rss.xml", "business", None),
    ("WSJ Markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "business", None),
    ("NPR Politics", "https://feeds.npr.org/1014/rss.xml", "policy", None),
    ("Hackaday", "https://hackaday.com/blog/feed/", "maker", r"\b(laser|cut|cnc|print|design|cad|wood|electronics|robot|project|build|repair|microcontroller|maker)\b"),
    ("Make:", "https://makezine.com/feed/", "maker", None),
    ("The Verge", "https://www.theverge.com/rss/index.xml", "home", r"\b(smart home|wifi|wi-fi|router|matter|thread|home automation|security|robot vacuum|appliance|mesh|iot)\b"),
    ("Joe Gardener", "https://joegardener.com/feed/", "garden", r"\b(garden|soil|compost|seed|plant|vegetable|harvest|homestead|greenhouse|mulch)\b"),
]
WHY = {
    "ai": "Relevant to your interest in Ollama, Windows AI agents, local computing, and hardware upgrades.",
    "cyber": "Relevant to your GRC and AI compliance career goals, security controls, and risk management.",
    "kc": "Potential impact on Kansas City-area businesses, infrastructure, and community opportunities.",
    "business": "Useful context for entrepreneurship, investing, and the economy affecting small businesses.",
    "policy": "Useful for tracking policy, government accountability, infrastructure, and economic consequences.",
    "maker": "Potentially useful for laser-cutting, vector design, fabrication, and a maker business.",
    "home": "Relevant to practical smart-home networking, IoT systems, appliances, and product reliability.",
    "garden": "Practical homesteading and gardening ideas; compare timing with western Missouri seasons.",
}
AGE_LIMIT = {"garden": 50, "maker": 21, "home": 14}
FEATURED = [
    (r"\b(ollama|on-device|local llm|nvidia|rtx|gpu)\b", "ai", "Worth checking against the local AI setup and GPU upgrades you've been evaluating."),
    (r"\b(ai governance|ai agents?|nist|audit|compliance|security framework)\b", "cyber", "Especially relevant to moving into GRC and AI compliance work."),
    (r"\b(laser cut|lightburn|cnc|vector)\b", "maker", "Could help with design workflows or equipment for your laser-cutting business."),
    (r"\b(compost|mulch|soil|seed|harvest)\b", "garden", "A hands-on gardening or soil-improvement idea to consider for a Missouri homestead."),
]

class Stripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)

def plain(value, limit=250):
    parser = Stripper()
    try:
        parser.feed(html.unescape(value or ""))
        text = " ".join(" ".join(parser.parts).split())
    except Exception:
        text = ""
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(".,:;") + "…"
    return text

def element_text(elem, name):
    for sub in elem:
        if sub.tag.rsplit("}", 1)[-1].lower() == name.lower():
            return "".join(sub.itertext()).strip()
    return ""

def article_link(elem):
    for sub in elem:
        if sub.tag.rsplit("}", 1)[-1].lower() == "link":
            if sub.get("href") and sub.get("rel", "alternate") == "alternate":
                return sub.get("href")
            if (sub.text or "").strip():
                return sub.text.strip()
    return ""

def article_date(elem):
    raw = next((element_text(elem, key) for key in ("pubDate", "published", "updated", "date") if element_text(elem, key)), None)
    if not raw:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        try:
            parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed.replace(tzinfo=dt.timezone.utc) if parsed.tzinfo is None else parsed

def read_publisher(name, url, category, pattern, now):
    req = urllib.request.Request(url, headers={
        "User-Agent": "FieldnotesNewsReader/1.0 (personal RSS reader)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read(1_250_000)
    root = ET.fromstring(body)
    entries = [e for e in root.iter() if e.tag.rsplit("}", 1)[-1].lower() in ("item", "entry")]
    result = []
    for entry in entries[:35]:
        title = plain(element_text(entry, "title"), 190)
        url = html.unescape(article_link(entry) or "")
        if not title or not url.startswith("https://"):
            continue
        date = article_date(entry)
        if date is None:
            continue
        age = (now - date.astimezone(dt.timezone.utc)).total_seconds() / 86400
        if age < -0.1 or age > AGE_LIMIT.get(category, 7):
            continue
        summary = plain(element_text(entry, "description") or element_text(entry, "summary") or element_text(entry, "content"), 180)
        if pattern and not re.search(pattern, title + " " + summary, flags=re.I):
            continue
        if not summary:
            summary = "New reporting from " + name + ". Open the publisher's article for details."
        why = WHY[category]
        for needle, matchcat, custom in FEATURED:
            if category == matchcat and re.search(needle, title + " " + summary, flags=re.I):
                why = custom
                break
        result.append({
            "id": "rss-" + hashlib.sha1(url.encode()).hexdigest()[:13],
            "category": TOPICS[category], "kind": "News",
            "date": date.astimezone(CENTRAL).date().isoformat(),
            "source": name, "headline": title, "summary": summary,
            "why": why, "url": url, "score": max(40, round(95 - 3 * max(0, age))),
            "read": 4, "tag": "Publisher RSS", "note": "RSS summary; read original reporting",
            "catKey": category,
        })
    return result

def main():
    now = dt.datetime.now(dt.timezone.utc)
    stories = []
    successful_sources = 0
    for name, feed, category, pattern in FEEDS:
        try:
            batch = read_publisher(name, feed, category, pattern, now)
            stories.extend(batch)
            successful_sources += 1
            print(f"OK {name}: {len(batch)} matching items")
        except Exception as exc:
            print(f"WARN {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
    # Keep old content if feed availability is too low; do not invent freshness.
    keys = set()
    by_topic = {key: [] for key in TOPICS}
    for item in sorted(stories, key=lambda x: (x["score"], x["date"]), reverse=True):
        key = re.sub(r"[^a-z0-9]", "", item["headline"].lower())[:100]
        if key in keys:
            continue
        keys.add(key)
        by_topic[item["catKey"]].append(item)
    selected = []
    for category in TOPICS:
        selected.extend(by_topic[category][:5])
    if len(selected) < 5:
        print("Not enough current publisher stories; retaining existing snapshot", file=sys.stderr)
        return 3
    try:
        existing = json.loads(DEST.read_text(encoding="utf-8"))
        old_guides = [
            x for x in existing.get("stories", [])
            if x.get("kind") == "Guide" and x.get("catKey") in ("garden", "maker")
        ]
        for guide in old_guides:
            if guide.get("url") not in {story["url"] for story in selected}:
                selected.append(guide)
    except (OSError, ValueError):
        pass
    selected.sort(key=lambda x: (x.get("score", 0), x.get("date", "")), reverse=True)
    payload = {
        "updated_at": now.astimezone(CENTRAL).isoformat(timespec="seconds"),
        "mode": "rss", "source_count": successful_sources, "stories": selected[:45],
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    temp = DEST.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(DEST)
    print(f"Prepared {len(payload['stories'])} stories from {successful_sources} feeds")
    return 0

if __name__ == "__main__":
    sys.exit(main())
