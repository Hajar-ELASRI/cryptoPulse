"""Read approved Reddit OAuth API posts and publish to crypto-social."""

import logging
import os
import time

from collectors.common import iso_from_epoch, producer, publish, utc_now


LOG = logging.getLogger(__name__)


def normalize_post(post: dict) -> dict:
    post_id = str(post["id"])
    subreddit = str(post["subreddit"])
    title = str(post.get("title", "")).strip()
    if not title:
        raise ValueError("Post needs a title")
    return {
        "event_id": f"reddit:{post_id}",
        "source": "reddit",
        "subreddit": subreddit,
        "title": title,
        "text": str(post.get("selftext") or ""),
        "url": f"https://www.reddit.com{post['permalink']}",
        "score": int(post.get("score") or 0),
        "num_comments": int(post.get("num_comments") or 0),
        "event_time": iso_from_epoch(post["created_utc"]),
        "ingested_at": utc_now(),
    }


def oauth_token(session, client_id: str, secret: str, user_agent: str) -> tuple[str, float]:
    response = session.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(client_id, secret),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": user_agent},
        timeout=25,
    )
    response.raise_for_status()
    data = response.json()
    return data["access_token"], time.monotonic() + int(data["expires_in"]) - 60


def run() -> None:
    import requests

    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    user_agent = os.getenv("REDDIT_USER_AGENT", "")
    if not all((client_id, secret, user_agent)) or "YOUR_REDDIT_USERNAME" in user_agent:
        raise ValueError("Configure Reddit OAuth credentials and a real REDDIT_USER_AGENT in .env")
    subreddits = [part.strip() for part in os.getenv("REDDIT_SUBREDDITS", "CryptoCurrency,Bitcoin").split(",") if part.strip()]
    interval = max(60, int(os.getenv("REDDIT_POLL_SECONDS", "300")))
    session = requests.Session()
    client = producer()
    seen: set[str] = set()
    token, expires = "", 0.0
    while True:
        for subreddit in subreddits:
            try:
                if time.monotonic() >= expires:
                    token, expires = oauth_token(session, client_id, secret, user_agent)
                response = session.get(
                    f"https://oauth.reddit.com/r/{subreddit}/new",
                    params={"limit": 50},
                    headers={"Authorization": f"bearer {token}", "User-Agent": user_agent},
                    timeout=25,
                )
                if response.status_code == 429:
                    wait = min(int(response.headers.get("Retry-After", "60")), 900)
                    LOG.warning("Reddit rate limited; waiting %s seconds", wait)
                    time.sleep(wait)
                    continue
                if response.status_code == 401:
                    expires = 0
                response.raise_for_status()
                posts = response.json()["data"]["children"]
                for item in posts:
                    try:
                        event = normalize_post(item["data"])
                    except (KeyError, TypeError, ValueError) as error:
                        LOG.warning("Skipping Reddit post: %s", error)
                        continue
                    if event["event_id"] not in seen:
                        publish(client, "crypto-social", event, wait=True)
                        seen.add(event["event_id"])
                LOG.info("Read %s posts from r/%s", len(posts), subreddit)
            except (requests.RequestException, KeyError, ValueError, RuntimeError, TimeoutError):
                LOG.exception("Reddit fetch failed for r/%s", subreddit)
        if client.flush(20):
            LOG.warning("Some Reddit messages remain in the Kafka producer queue")
        time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
