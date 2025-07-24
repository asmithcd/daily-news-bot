import os
import smtplib
import requests
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

RELEVANT_KEYWORDS = [
    "earnings", "tariff", "tariffs", "trade war", "acquisition", "merger", "guidance",
    "forecast", "ipo", "strike", "regulation", "bill", "legislation", "lawsuit",
    "settlement", "antitrust", "sec", "layoff", "restructuring", "chapter 11",
    "guidelines", "inflation", "deflation", "revenue", "profit", "quarter", "sales",
    "recall", "investigation", "class action", "price increase", "price hike", "costs",
    "supply chain", "union", "agreement", "deal", "fine", "settlement"
]

DOMAINS = (
    "reuters.com,wsj.com,bloomberg.com,marketwatch.com,ft.com,cnbc.com,forbes.com,"
    "finance.yahoo.com,nytimes.com,bizjournals.com,autonews.com,greentechmedia.com,"
    "pv-magazine.com,rvbusiness.com,cycleworld.com,motorcycle.com,appliancebusiness.com"
)

SECTOR_TERMS = {
    "auto dealers": [
        "auto dealer", "dealership", "car dealership", "car sales", "autonation", "group 1 automotive", "lad", "pag", "an", "cargurus", "carmax", "autotrader"
    ],
    "auto manufacturers": [
        "automaker", "car maker", "vehicle manufacturer", "ford", "gm", "general motors", "tesla", "toyota", "stellantis", "hyundai", "honda", "volkswagen", "f", "tsla", "tm", "hmc", "stla", "vw"
    ],
    "auto parts": [
        "auto part", "autoparts", "supplier", "magna", "dormakaba", "aap", "genuine parts", "borgwarner", "delphi", "components", "aftermarket"
    ],
    "solar": [
        "solar", "pv", "photovoltaic", "first solar", "enphase", "solar edge", "maxeon", "sunpower"
    ],
    "pool industry": [
        "pool supply", "poolcorp", "swimming pool", "pool equipment", "hayward"
    ],
    "mattress": [
        "mattress", "sleep number", "tempur", "sealy", "casper", "simmons"
    ],
    "appliances": [
        "appliance", "whirlpool", "electrolux", "frigidaire", "maytag", "lg electronics", "haier", "samsung appliances", "bosch appliances"
    ],
    "powersports": [
        "powersport", "atv", "utv", "polaris", "brp", "yamaha", "can-am", "arctic cat"
    ],
    "motorcycles": [
        "motorcycle", "harley-davidson", "ducati", "yamaha", "honda", "ktm", "indian motorcycle"
    ],
    "rv": [
        "rv", "recreational vehicle", "winnebago", "thor", "forest river", "jayco", "motorhome", "travel trailer"
    ]
}

categories = list(SECTOR_TERMS.keys())

def is_fresh(article, hours=36):
    published = article.get("publishedAt")
    if not published:
        return False
    try:
        published_dt = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - published_dt) <= timedelta(hours=hours)

def is_final_match(article, sector_terms):
    title = (article.get('title') or "").lower()
    desc = (article.get('description') or "").lower()
    return (
        any(word in title or word in desc for word in RELEVANT_KEYWORDS) and
        any(term in title or term in desc for term in sector_terms)
    )

def get_news(api_key):
    try:
        sector_results = {}
        for cat in categories:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": cat,
                    "apiKey": api_key,
                    "sortBy": "publishedAt",
                    "pageSize": 30,
                    "domains": DOMAINS
                },
                timeout=10
            )
            resp.raise_for_status()
            sector_terms = SECTOR_TERMS[cat]
            articles = []
            for art in resp.json().get("articles", []):
                if is_fresh(art) and is_final_match(art, sector_terms):
                    articles.append((art["title"], art["publishedAt"], art["url"]))
            if articles:
                sector_results[cat] = articles
        if not sector_results:
            logging.warning("No market-moving articles found across all categories")
        return sector_results
    except Exception as e:
        logging.error(f"News API request failed: {str(e)}")
        return None

def send_email(content, email_config):
    try:
        msg = MIMEMultipart()
        msg['From'] = email_config['sender_email']
        msg['To'] = email_config['receiver_email']
        msg['Subject'] = f"📰 <b>Daily Market-Moving News Digest</b> - {datetime.utcnow().strftime('%Y-%m-%d')}"
        
        # HTML body start
        if not content:
            body = "<p><b>No market-moving articles were found today.</b></p>"
        else:
            body = "<h2 style='color:#293241;'>📬 Your Daily Market-Moving Industry News</h2>"
            for cat, articles in content.items():
                body += f"<h3 style='color:#1565c0;'>{cat.upper()}</h3><ul>"
                for title, date, url in articles:
                    # Each article: title as bold link, date small
                    body += (
                        f"<li style='margin-bottom:10px;'>"
                        f"<a href='{url}' style='font-weight:bold; color:#183153; text-decoration:none;'>{title}</a> "
                        f"<span style='color:#888; font-size:90%;'>({date[:10]})</span>"
                        f"</li>"
                    )
                body += "</ul>"
        msg.attach(MIMEText(body, 'html'))

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
