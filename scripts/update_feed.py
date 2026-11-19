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
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.parse
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
    "property": "Home & 2-Acre Property",
    "comics": "Comics",
}
# Each source is a publisher feed, not a scraped search result.
# A matching pattern is optional; it limits broad publications to pertinent stories.
FEEDS = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "ai", None),
    ("MIT Technology Review", "https://www.technologyreview.com/feed/", "ai", r"\b(ai|artificial intelligence|machine learning|llms?|agents?|ollama|nvidia|local models?)\b"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "ai", r"\b(ai|local models?|gpu|rtx|ollama|automation|agents?|microsoft)\b"),
    ("The Record", "https://therecord.media/feed", "cyber", None),
    ("BleepingComputer", "https://www.bleepingcomputer.com/feed/", "cyber", None),
    ("Startland News", "https://startlandnews.com/feed/", "kc", None),
    ("NPR Business", "https://feeds.npr.org/1006/rss.xml", "business", None),
    ("NPR Politics", "https://feeds.npr.org/1014/rss.xml", "policy", None),
    ("Hackaday", "https://hackaday.com/blog/feed/", "maker", r"\b(laser|cut|cnc|print|design|cad|wood|electronics|robot|project|build|repair|microcontroller|maker)\b"),
    ("Make:", "https://makezine.com/feed/", "maker", None),
    ("The Verge", "https://www.theverge.com/rss/index.xml", "home", r"\b(smart|home|google|amazon|wifi|wi-fi|router|matter|security|robot|appliance|iot|nest|ring|gadgets|device)\b"),
    ("Savvy Gardening", "https://savvygardening.com/feed/", "garden", None),
    ("Missouri Independent", "https://missouriindependent.com/feed/", "kc", r"\b(missouri|kansas city|state|property|business|housing|legislature)\b"),
    ("Missourinet", "https://www.missourinet.com/feed/", "kc", None),
    ("NPR Technology", "https://feeds.npr.org/1019/rss.xml", "ai", r"\b(ai|technology|software|computer|robot|chips|models?|internet)\b"),
    ("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml", "ai", r"\b(ai|tech|software|chips|computer|cyber|robot|agents?)\b"),
    ("The Register", "https://www.theregister.com/headlines.atom", "cyber", r"\b(security|attack|breach|vulnerability|regulation|audit|cloud|ai|data)\b"),
    ("EFF", "https://www.eff.org/rss/updates.xml", "cyber", r"\b(privacy|security|ai|surveillance|policy|law|encryption|right)\b"),
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml", "business", None),
    ("Guardian Business", "https://www.theguardian.com/us/business/rss", "business", None),
    ("PBS Politics", "https://www.pbs.org/newshour/feeds/rss/politics", "policy", None),
    ("BBC US News", "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml", "policy", r"\b(congress|federal|election|policy|government|politics|regulation|infrastructure|trade)\b"),
    ("Family Handyman", "https://www.familyhandyman.com/feed/", "property", None),
    ("Bob Vila", "https://www.bobvila.com/feed/", "property", None),
    ("Fine Homebuilding", "https://www.finehomebuilding.com/feed", "property", None),
    ("xkcd", "https://xkcd.com/rss.xml", "comics", None),
    ("Engadget", "https://www.engadget.com/rss.xml", "home", r"\b(home|smart|wi.?fi|router|device|robot|matter|appliance|camera|network|gadgets?|homepod|doorbell)\b"),
    ("Tom's Hardware", "https://www.tomshardware.com/feeds/all", "ai", r"\b(ai|nvidia|gpu|rtx|local|processor|computer|model|ram|memory|pc)\b"),
    ("Guardian Technology", "https://www.theguardian.com/us/technology/rss", "ai", r"\b(ai|model|security|computing|chips|technology|internet)\b"),
    ("Guardian US News", "https://www.theguardian.com/us-news/rss", "policy", r"\b(congress|federal|government|election|policy|economy|court|regulation|infrastructure)\b"),
    ("Garden Betty", "https://gardenbetty.com/feed/", "garden", None),
    ("Fine Gardening", "https://www.finegardening.com/feed", "garden", None),
    ("SMBC", "https://www.smbc-comics.com/comic/rss", "comics", None),
    ("Kansas City Magazine", "https://kansascitymag.com/feed/", "kc", None),
    ("Flatland KC", "https://flatlandkc.org/feed/", "kc", None),
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
    "property": "Home and land ideas for your house and two-acre property: drainage, deck, HVAC, outdoor Wi-Fi, trees, soil and maintenance.",
    "comics": "A quick entertaining break between practical stories, from the original artist.",
}
AGE_LIMIT = {"garden": 90, "maker": 45, "home": 30, "property": 90, "comics": 30, "kc": 14, "ai": 12, "cyber": 14, "business": 14, "policy": 14}
FEATURED = [
    (r"\b(ollama|on-device|local llm|nvidia|rtx|gpu)\b", "ai", "Worth checking against the local AI setup and GPU upgrades you've been evaluating."),
    (r"\b(ai governance|ai agents?|nist|audit|compliance|security framework)\b", "cyber", "Especially relevant to moving into GRC and AI compliance work."),
    (r"\b(laser cut|lightburn|cnc|vector)\b", "maker", "Could help with design workflows or equipment for your laser-cutting business."),
    (r"\b(compost|mulch|soil|seed|harvest)\b", "garden", "A hands-on gardening or soil-improvement idea to consider for a Missouri homestead."),
    (r"\b(deck|basement|water pressure|drainage|gutters|trees|fencing|septic|hvac|insulation|acreage|property|roof|mold)\b", "property", "A practical repair, upkeep or improvement to evaluate for your house and two acres."),
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

def source_image(entry):
    # Prefer media attachments explicitly syndicated by the publisher.
    for sub in entry.iter():
        tag = sub.tag.rsplit("}", 1)[-1].lower()
        if tag in ("thumbnail", "content", "enclosure", "image"):
            url = (sub.get("url") or sub.get("href") or "").strip()
            mime = (sub.get("type") or "").lower()
            if url.startswith("https://") and (tag == "thumbnail" or "image/" in mime or re.search(r"\.(?:jpe?g|png|webp)(?:\?|$)", url, re.I)):
                return url
    raw = element_text(entry, "description") or element_text(entry, "summary") or element_text(entry, "content")
    match = re.search(r"<img\b[^>]*\bsrc\s*=\s*['\"](https://[^'\"]+)['\"]", html.unescape(raw or ""), re.I)
    return html.unescape(match.group(1)) if match else None


def topical_relevance(category, title, summary, age):
    weights = {"ai": 19, "cyber": 18, "kc": 16, "business": 11,
               "policy": 9, "maker": 22, "home": 15, "garden": 14,
               "property": 24, "comics": 7}
    # Personalized topical keywords get priority over mere recency.
    needles = [
        (r"\b(ollama|local ai|on.device|agents?|rtx|gpu|ai governance|cybersecurity|grc|compliance|nist)\b", 14),
        (r"\b(laser|lightburn|vector|cnc|cad|woodwork|fabricat|3d print)\b", 16),
        (r"\b(kansas city|lee.s summit|missouri|independence|jackson county)\b", 11),
        (r"\b(deck|basement|drainage|well|septic|yard|tree|fence|roof|hvac|wifi|wi.fi|iot|acreage|acre)\b", 14),
        (r"\b(compost|seed|soil|raised bed|homestead|garden|harvest|vegetable|irrigat)\b", 11),
    ]
    combined = title + " " + summary
    bonus = sum(weight for regex, weight in needles if re.search(regex, combined, re.I))
    return min(100, max(20, round(55 + weights[category] + min(bonus, 22) - min(max(age, 0), 35) * 0.6)))


def headline_terms(headline):
    stop = {"about","after","ahead","against","also","amid","another","around","been",
            "before","could","first","from","have","into","more","over","says",
            "than","that","their","there","these","this","through","under",
            "using","when","where","which","while","will","with","would",
            "news","report","update","latest","today","what","your","says"}
    return {w for w in re.findall(r"[a-z0-9]+", headline.lower())
            if len(w) > 3 and w not in stop}


def same_story(a, b):
    if a["source"] == b["source"] or a["catKey"] != b["catKey"]:
        return False
    if abs((dt.date.fromisoformat(a["date"]) - dt.date.fromisoformat(b["date"])).days) > 4:
        return False
    one, two = headline_terms(a["headline"]), headline_terms(b["headline"])
    intersection = one & two
    return len(intersection) >= 3 and len(intersection) / max(1, min(len(one), len(two))) >= 0.48


def attach_evidence(stories, candidates):
    for item in stories:
        if item.get("kind") in ("Comic", "Guide"):
            item["confidence_pct"] = None
            item["corroboration"] = []
            item["related_coverage"] = []
            item["confidence_basis"] = "Not scored: creative content or practical guide."
            continue
        peers = [other for other in candidates
                 if other["url"] != item["url"] and same_story(item, other)]
        seen = {item["source"]}
        unique = []
        for p in sorted(peers, key=lambda p: p["score"], reverse=True):
            if p["source"] not in seen:
                unique.append({"source": p["source"], "headline": p["headline"], "url": p["url"]})
                seen.add(p["source"])
            if len(unique) == 4:
                break
        item["corroboration"] = unique
        num = len(unique)
        # This is a source-corroboration rubric, NOT a measured probability
        # that the story or any specific factual assertion is true.
        item["confidence_pct"] = min(92, 35 + (37 if num else 0) + max(0, num - 1) * 9)
        item["confidence_basis"] = (
            f"{num + 1} distinct feed publisher(s) with closely matching headlines; "
            "headline-level comparison only; assertions have not been fact-checked."
        )
        item["perspective_note"] = (
            "Check links for differences in framing and sources; aligned headlines "
            "alone do not prove that every assertion agrees."
        ) if num else "Only one publisher reported this headline in the feed; no automatic corroboration found."
        # Other coverage can provide context or opposing perspectives; it is
        # explicitly NOT scored as independent corroboration of this story.
        related = []
        for other in candidates:
            if (other.get("source") == item.get("source") or
                other.get("url") == item.get("url") or
                other.get("catKey") != item.get("catKey") or
                other.get("url") in {v["url"] for v in unique}):
                continue
            if abs((dt.date.fromisoformat(item["date"]) -
                    dt.date.fromisoformat(other["date"])).days) > 7:
                continue
            common = headline_terms(item["headline"]) & headline_terms(other["headline"])
            if len(common) < 2:
                continue
            related.append((len(common), other))
        related.sort(key=lambda t: (t[0], t[1]["score"]), reverse=True)
        item["related_coverage"] = [
            {"source": other["source"], "headline": other["headline"], "url": other["url"]}
            for _, other in related[:3]
        ]
        item["verification_search_url"] = (
            "https://news.google.com/search?q=" +
            urllib.parse.quote(item["headline"], safe="")
        )
    return stories


def repair_xml(body):
    # Repair invalid HTML entities embedded in imperfect RSS without silently
    # treating entire HTML pages as valid XML.
    raw = body.decode("utf-8", "replace")
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
    raw = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)", "&amp;", raw)
    return raw



def parse_lenient(body):
    """Use tolerant feedparser if installed, preserving linked publisher images."""
    try:
        import feedparser
    except ImportError:
        return ET.fromstring(repair_xml(body))
    parsed = feedparser.parse(body)
    if not parsed.entries:
        raise ET.ParseError("No readable entries in malformed publisher response")
    root = ET.Element("rss")
    for record in parsed.entries:
        item = ET.SubElement(root, "item")
        for tag, key in (("title", "title"), ("description", "summary"),
                         ("link", "link"), ("pubDate", "published"),
                         ("updated", "updated")):
            value = record.get(key)
            if value:
                ET.SubElement(item, tag).text = str(value)
        for candidate in (record.get("media_thumbnail", []) +
                          record.get("media_content", []) +
                          record.get("enclosures", [])):
            url = candidate.get("url") or candidate.get("href")
            if url and str(url).startswith("https://"):
                ET.SubElement(item, "enclosure", {"url": str(url),
                    "type": candidate.get("type", "image/jpeg")})
                break
    return root

def read_publisher(name, url, category, pattern, now):
    req = urllib.request.Request(url, headers={
        "User-Agent": "FieldnotesNewsReader/1.0 (personal RSS reader)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read(1_250_000)
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        root = parse_lenient(body)
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
        summary = plain(element_text(entry, "description") or element_text(entry, "summary") or element_text(entry, "content"), 210)
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
            "category": TOPICS[category], "kind": "Comic" if category == "comics" else "News",
            "date": date.astimezone(CENTRAL).date().isoformat(),
            "source": name, "headline": title, "summary": summary,
            "why": why, "url": url, "score": topical_relevance(category, title, summary, age),
            "image": source_image(entry),
            "read": 4, "tag": "Publisher RSS", "note": "RSS summary; read original reporting",
            "catKey": category,
        })
    return result

def main():
    now = dt.datetime.now(dt.timezone.utc)
    stories = []
    successful_sources = 0
    feed_health = []
    # Slow/invalid publisher feeds no longer stall all the other categories.
    with ThreadPoolExecutor(max_workers=10) as pool:
        calls = {
            pool.submit(read_publisher, name, feed, cat, pattern, now): (name, cat)
            for name, feed, cat, pattern in FEEDS
        }
        for task in as_completed(calls):
            name, category = calls[task]
            try:
                batch = task.result()
                stories.extend(batch)
                successful_sources += 1
                status = "ok" if batch else "no_matching_recent_articles"
                feed_health.append({"source": name, "category": category, "status": status, "articles": len(batch)})
                print(f"OK {name}: {len(batch)} matching items")
            except Exception as exc:
                feed_health.append({"source": name, "category": category, "status": "failed", "articles": 0})
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
        desired = 6 if category in ("ai", "cyber", "maker", "property", "garden", "kc") else 4
        choices = []
        source_counts = {}
        for story in by_topic[category]:
            publisher = story["source"]
            if source_counts.get(publisher, 0) >= 2:
                continue
            choices.append(story)
            source_counts[publisher] = source_counts.get(publisher, 0) + 1
            if len(choices) >= desired:
                break
        if len(choices) < desired:
            for story in by_topic[category]:
                if story not in choices:
                    choices.append(story)
                if len(choices) >= desired:
                    break
        selected.extend(choices)
    if len(selected) < 5:
        print("Not enough current publisher stories; retaining existing snapshot", file=sys.stderr)
        return 3
    try:
        existing = json.loads(DEST.read_text(encoding="utf-8"))
        old_guides = [
            x for x in existing.get("stories", [])
            if x.get("kind") == "Guide" and x.get("catKey") in ("garden", "maker", "property")
        ]
        for guide in old_guides:
            if guide.get("url") not in {story["url"] for story in selected}:
                selected.append(guide)
    except (OSError, ValueError):
        pass
    attach_evidence(selected, stories)
    verified = sum(1 for article in selected if article.get("corroboration"))
    print(f"Independent headline corroboration: {verified} of {len(selected)} candidate stories")
    print(f"Selected publisher diversity: {len(set(x['source'] for x in selected))} publishers; publisher images: {sum(bool(x.get('image')) for x in selected)}")
    print(f"Related cross-source coverage: {sum(bool(x.get('related_coverage')) for x in selected)} stories")
    print("Source categories: " + str({topic: sum(1 for x in selected if x.get("catKey") == topic) for topic in TOPICS}))
    selected.sort(key=lambda x: (x.get("score", 0), x.get("date", "")), reverse=True)
    payload = {
        "updated_at": now.astimezone(CENTRAL).isoformat(timespec="seconds"),
        "mode": "rss", "source_count": successful_sources,
        "feed_count": len(FEEDS), "feed_health": sorted(feed_health, key=lambda x: x["source"]),
        "evidence_method": "Heuristic headline-matching support from distinct publisher feeds. 35% denotes single-source reporting, NOT 35% probability of truth. These percentages are NOT independently verified probabilities that individual facts are correct.",
        "stories": selected[:64],
    }
    DEST.parent.mkdir(parents=True, exist_ok=True)
    temp = DEST.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(DEST)
    print(f"Prepared {len(payload['stories'])} stories from {successful_sources} feeds")
    return 0

if __name__ == "__main__":
    sys.exit(main())
