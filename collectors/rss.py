"""RSS news feeds to crypto-news."""

import hashlib
import html
from html.parser import HTMLParser
import logging
import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from collectors.common import producer, publish, utc_now


LOG = logging.getLogger(__name__)


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(value: str) -> str:
    parser = _TextParser()
    parser.feed(value or "")
    return " ".join(html.unescape(" ".join(parser.parts)).split())


def published_iso(entry: dict) -> str:
    for field in ("published", "updated"):
        if entry.get(field):
            try:
                parsed = parsedate_to_datetime(entry[field])
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            except (TypeError, ValueError):
                pass
    for field in ("published_parsed", "updated_parsed"):
        if entry.get(field):
            return datetime(*entry[field][:6], tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return utc_now()


def normalize_article(entry: dict, source: str) -> dict:
    url = str(entry.get("link", "")).strip()
    title = plain_text(str(entry.get("title", "")))
    if not url or not title:
        raise ValueError("Article needs a title and link")
    identity = str(entry.get("id") or url).strip()
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    timestamp = published_iso(entry)
    return {
        "event_id": f"rss:{digest}",
        "source": source,
        "title": title,
        "summary": plain_text(str(entry.get("summary", ""))),
        "url": url,
        "event_time": timestamp,
        "published_at": timestamp,
        "ingested_at": utc_now(),
    }


def run() -> None:
    import feedparser
    import requests

    client = producer()
    session = requests.Session()
    session.headers["User-Agent"] = "CryptoPulse/0.1 (educational RSS reader)"
    feeds = [url.strip() for url in os.getenv("RSS_FEEDS", "").split(",") if url.strip()]
    if not feeds:
        raise ValueError("RSS_FEEDS cannot be empty")
    interval = max(60, int(os.getenv("RSS_POLL_SECONDS", "300")))
    seen: set[str] = set()
    validators: dict[str, dict] = {}
    while True:
        for url in feeds:
            try:
                response = session.get(url, timeout=25, headers=validators.get(url, {}))
                if response.status_code == 304:
                    continue
                response.raise_for_status()
                validators[url] = {}
                if response.headers.get("ETag"):
                    validators[url]["If-None-Match"] = response.headers["ETag"]
                if response.headers.get("Last-Modified"):
                    validators[url]["If-Modified-Since"] = response.headers["Last-Modified"]
                parsed = feedparser.parse(response.content)
                if parsed.bozo and not parsed.entries:
                    raise ValueError(f"Invalid feed: {parsed.bozo_exception}")
                source = parsed.feed.get("title") or url
                for entry in parsed.entries:
                    try:
                        event = normalize_article(entry, source)
                    except ValueError as error:
                        LOG.warning("Skipping RSS article: %s", error)
                        continue
                    if event["event_id"] not in seen:
                        publish(client, "crypto-news", event, wait=True)
                        seen.add(event["event_id"])
                LOG.info("Read %s articles from %s", len(parsed.entries), source)
            except (requests.RequestException, ValueError, RuntimeError, TimeoutError):
                LOG.exception("RSS fetch failed for %s", url)
        if client.flush(20):
            LOG.warning("Some RSS messages remain in the Kafka producer queue")
        time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
