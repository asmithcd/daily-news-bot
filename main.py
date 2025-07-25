"""
Automated industry news digest using NewsAPI and Gmail.
"""

import datetime
import os
import smtplib
import sys
from email.message import EmailMessage
from typing import Dict, List
import requests

# ---- Configuration ----

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECIPIENT = os.environ.get("RECIPIENT_EMAIL", "asmith@channel-dynamics.com")
HOURS_LOOKBACK = 24
ARTICLES_PER_INDUSTRY = 3

QUERIES: Dict[str, Dict[str, str]] = {
    "APPLIANCES": {
        "q": "(appliance OR appliances) AND (industry OR recycling OR regulation)",
        "domains": "reuters.com, prnewswire.com, apnews.com",
    },
    "AUTO DEALERS": {
        "q": "(auto dealer OR car dealership OR dealer group) AND earnings",
        "domains": "reuters.com, apnews.com, cnbc.com, cbtnews.com",
    },
    "AUTO MANUFACTURERS": {
        "q": "(automaker OR auto manufacturer) AND (tariff OR regulation OR earnings)",
        "domains": "reuters.com, apnews.com, bloomberg.com, wsj.com",
    },
    "AUTO PARTS": {
        "q": "(auto parts OR aftermarket) AND (earnings OR outlook)",
        "domains": "reuters.com, apnews.com, investor.oreillyauto.com",
    },
    "MATTRESSES": {
        "q": "(mattress OR bedding) AND (launch OR collection OR line)",
        "domains": "bedtimesmagazine.com, furnituretoday.com, businesswire.com",
    },
    "MOTORCYCLES": {
        "q": "(motorcycle OR motorcycling) AND (training OR course OR license)",
        "domains": "electrek.co, visordown.com, prnewswire.com",
    },
    "POOL EQUIPMENT": {
        "q": "(pool equipment OR swimming pool) AND (earnings OR demand)",
        "domains": "reuters.com",
    },
    "POWERSPORTS": {
        "q": "(powersports OR snowmobile OR ATV OR UTV) AND show",
        "domains": "powersportsbusiness.com",
    },
    "SOLAR": {
        "q": "(solar OR renewable energy) AND (policy OR subsidy OR investment)",
        "domains": "reuters.com, apnews.com",
    },
}

def get_recent_timestamp(hours_back: int) -> str:
    from_dt = datetime.datetime.utcnow() - datetime.timedelta(hours=hours_back)
    return from_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def fetch_articles(q: str, domains: str = None) -> List[Dict]:
    if not NEWSAPI_KEY:
        raise ValueError(
            "NEWSAPI_KEY environment variable is not set. Please set your NewsAPI key."
        )
    params = {
        "apiKey": NEWSAPI_KEY,
        "q": q,
        "from": get_recent_timestamp(HOURS_LOOKBACK),
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": ARTICLES_PER_INDUSTRY,
    }
    if domains:
        params["domains"] = domains
    url = "https://newsapi.org/v2/everything"
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("articles", [])
    except Exception as e:
        print(f"Error fetching articles for query '{q}': {e}", file=sys.stderr)
        return []

def summarize(text: str, max_sentences: int = 3) -> str:
    if not text:
        return ""
    sentences = text.replace("\n", " ").split(". ")
    return ". ".join(sentences[:max_sentences]).strip()

def build_digest() -> str:
    lines: List[str] = []
    for industry in sorted(QUERIES.keys()):
        params = QUERIES[industry]
        articles = fetch_articles(params["q"], params.get("domains"))
        if not articles:
            continue
        heading_html = f"<p><strong><u>{industry}</u></strong></p>"
        lines.append(heading_html)
        for art in articles:
            title = art.get("title", "Untitled article").strip()
            url = art.get("url", "#")
            description = art.get("description") or art.get("content") or ""
            summary = summarize(description)
            article_html = f'<p><a href="{url}" target="_blank">{title}</a>: {summary}</p>'
            lines.append(article_html)
        lines.append("<br/>")
    return "\n".join(lines)

def send_email(html_body: str) -> None:
    if not (GMAIL_USER and GMAIL_APP_PASSWORD):
        raise ValueError(
            "GMAIL_USER or GMAIL_APP_PASSWORD environment variables are not set."
        )
    msg = EmailMessage()
    today = datetime.date.today().strftime("%B %d, %Y")
    msg["Subject"] = f"Daily News: {today}"
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT
    msg.set_content(
        "This email contains an HTML version of the digest. Please view it in an HTML-capable client.",
    )
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print(f"Digest email sent to {RECIPIENT}")

def main() -> None:
    html_digest = build_digest()
    if not html_digest.strip():
        print("No relevant articles found in the last 24 hours for any industry.")
        return
    send_email(html_digest)

if __name__ == "__main__":
    main()
