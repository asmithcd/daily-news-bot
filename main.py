import os
import smtplib
import requests
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

# Logging setup
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

RELEVANT_KEYWORDS = [
    "earnings", "tariff", "tariffs", "trade war", "acquisition", "merger", "guidance",
    "forecast", "ipo", "strike", "regulation", "bill", "legislation", "lawsuit",
    "settlement", "antitrust", "sec", "layoff", "guidance", "restructuring", "chapter 11",
    "guidelines", "inflation", "deflation", "revenue", "profit", "quarter", "sales",
    "recall", "investigation", "class action"
]

DOMAINS = "reuters.com,wsj.com,bloomberg.com,marketwatch.com,ft.com,cnbc.com,forbes.com,finance.yahoo.com,nytimes.com,bizjournals.com"

categories = [
    "auto dealers", "auto manufacturers", "auto parts",
    "solar", "pool industry", "mattress", "appliances",
    "powersports", "motorcycles", "rv"
]

def is_fresh(article, hours=36):
    published = article.get("publishedAt")
    if not published:
        return False
    try:
        published_dt = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - published_dt) <= timedelta(hours=hours)

def is_relevant(article, industry):
    title = article.get('title', '').lower()
    desc = article.get('description', '').lower()
    industry_term = industry.split()[0].lower()
    return (
        (industry_term in title or industry_term in desc)
        and any(word in title or word in desc for word in RELEVANT_KEYWORDS)
    )

def get_news(api_key):
    try:
        all_articles = []
        for cat in categories:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": cat,
                    "apiKey": api_key,
                    "sortBy": "publishedAt",
                    "pageSize": 10,
                    "domains": DOMAINS
                },
                timeout=10
            )
            resp.raise_for_status()
            for art in resp.json().get("articles", []):
                if is_fresh(art) and is_relevant(art, cat):
                    all_articles.append((cat, art["title"], art["publishedAt"], art["url"]))
        if not all_articles:
            logging.warning("No market-moving articles found across all categories")
        return all_articles
    except Exception as e:
        logging.error(f"News API request failed: {str(e)}")
        return None

def send_email(content, email_config):
    try:
        msg = MIMEMultipart()
        msg['From'] = email_config['sender_email']
        msg['To'] = email_config['receiver_email']
        msg['Subject'] = f"📰 Daily Market-Moving News Digest - {datetime.utcnow().strftime('%Y-%m-%d')}"

        if not content:
            body = "No market-moving articles were found today."
        else:
            body = "📬 Your Daily Market-Moving Industry News:\n\n"
            last_cat = None
            for cat, title, date, url in sorted(content, key=lambda x: x[0]):
                if cat != last_cat:
                    body += f"\n==== {cat.upper()} ====\n"
                    last_cat = cat
                body += f"- {title} ({date[:10]})\n  {url}\n"
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL(email_config['smtp_server'], email_config['smtp_port'], timeout=15) as server:
            server.login(email_config['sender_email'], email_config['smtp_password'])
            server.send_message(msg)
            logging.info("Email sent successfully")
    except (smtplib.SMTPException, Exception) as e: 
        logging.error(f"Failed to send email: {str(e)}")
        raise

def validate_config(config):
    required_keys = ['sender_email', 'receiver_email', 'smtp_server',
                     'smtp_port', 'smtp_password', 'newsapi_key']
    missing = [key for key in required_keys if not config.get(key) or str(config.get(key)).strip() == ""]
    if missing:
        logging.error(f"Missing configuration: {', '.join(missing)}")
        raise ValueError("Missing environment variables")
    try:
        config['smtp_port'] = int(config['smtp_port'])
    except ValueError:
        logging.error("Invalid SMTP_PORT value")
        raise

if __name__ == "__main__":
    try:
        config = {
            'sender_email': os.getenv('SENDER_EMAIL'),
            'receiver_email': os.getenv('RECEIVER_EMAIL'),
            'smtp_server': os.getenv('SMTP_SERVER'),
            'smtp_port': os.getenv('SMTP_PORT'),
            'smtp_password': os.getenv('SMTP_PASSWORD'),
            'newsapi_key': os.getenv('NEWSAPI_KEY')
        }

        logging.info(f"Loaded config: {config}")
        validate_config(config)
        logging.info("Configuration validated successfully")

        news_content = get_news(config['newsapi_key'])

        if news_content:
            send_email(news_content, config)
        else:
            logging.warning("No news content to send")
    except Exception as e:
        logging.error(f"Major failure: {str(e)}")
        raise
