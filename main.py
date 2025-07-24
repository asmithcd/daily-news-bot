import os
import smtplib
import requests
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DISPLAY_NAMES = {
    "appliances": "Appliances",
    "auto dealers": "Auto Dealers",
    "auto manufacturers": "Auto Manufacturers",
    "auto parts": "Auto Parts",
    "mattresses": "Mattresses",
    "motorcycles": "Motorcycles",
    "pool industry": "Pool Industry",
    "powersports": "Powersports",
    "rvs": "RVs",
    "solar": "Solar"
}

SECTOR_TERMS = {
    "auto dealers": [
        "auto dealer", "dealership", "car dealership", "car sales", "autonation", "group 1 automotive", "lithia",
        "sonic automotive", "penske automotive", "asbury automotive", "carmax", "cargurus"
    ],
    "auto manufacturers": [
        "automaker", "car maker", "vehicle manufacturer", "ford", "general motors", "gm", "tesla", "toyota",
        "stellantis", "hyundai", "honda", "volkswagen", "mercedes", "bmw", "nissan"
    ],
    "auto parts": [
        "auto part", "auto parts", "parts retailer", "oreilly", "o'reilly", "advance auto", "advance auto parts",
        "autozone", "genuine parts", "gpc", "dorman", "borgwarner", "delphi", "magna", "lkq", "standard motor products"
    ],
    "solar": [
        "solar", "photovoltaic", "pv", "first solar", "enphase", "solar edge", "maxeon", "sunpower", "sunrun", "solarcity"
    ],
    "pool industry": [
        "poolcorp", "hayward", "pentair", "leslie's", "fluidra", "zodiac pool", "commercial pool", "swimming pool equipment",
        "pool equipment", "pool manufacturer", "pool supply", "pool"
    ],
    "mattresses": [
        "mattress", "mattresses", "mattress company", "mattress manufacturer", "tempur", "sleep number", "sealy", "casper",
        "simmons", "purple innovation", "tuft & needle"
    ],
    "appliances": [
        "appliance", "appliances", "appliance manufacturer", "appliance company", "whirlpool", "electrolux", "frigidaire",
        "maytag", "lg electronics", "haier", "bosch", "samsung appliances", "ge appliances"
    ],
    "powersports": [
        "powersport", "powersports", "atv", "utv", "polaris", "brp", "can-am", "yamaha", "arctic cat", "sea-doo", "ski-doo"
    ],
    "motorcycles": [
        "motorcycle", "motorcycles", "harley-davidson", "ducati", "ktm", "yamaha", "honda", "indian motorcycle"
    ],
    "rvs": [
        "rv", "rvs", "motorhome", "travel trailer", "winnebago", "thor", "forest river", "jayco", "rev group", "newmar", "airstream"
    ]
}

categories = sorted(DISPLAY_NAMES.keys(), key=lambda x: DISPLAY_NAMES[x])

def is_fresh(article, hours=36):
    published = article.get("publishedAt")
    if not published:
        return False
    try:
        published_dt = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return False
    return (datetime.now(timezone.utc) - published_dt) <= timedelta(hours=hours)

def is_sector_related(article, sector_terms):
    title = (article.get('title') or "").lower()
    desc = (article.get('description') or "").lower()
    # Looser match: if any term in title or desc, count it
    return any(term in title or term in desc for term in sector_terms)

def get_news(api_key):
    try:
        sector_results = {}
        for cat in categories:
            # Use broad query for more catch
            query = cat.split()[0]
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "apiKey": api_key,
                    "sortBy": "publishedAt",
                    "pageSize": 50
                },
                timeout=10
            )
            resp.raise_for_status()
            sector_terms = SECTOR_TERMS[cat]
            # Keep only relevant, fresh articles
            relevant = []
            for art in resp.json().get("articles", []):
                if is_fresh(art) and is_sector_related(art, sector_terms):
                    relevant.append((art["title"], art["publishedAt"], art["url"]))
            if relevant:
                sector_results[cat] = relevant
        return sector_results
    except Exception as e:
        logging.error(f"News API request failed: {str(e)}")
        return {}

def send_email(content, email_config):
    try:
        msg = MIMEMultipart()
        msg['From'] = email_config['sender_email']
        msg['To'] = email_config['receiver_email']
        subject_date = datetime.now().strftime('%-m/%-d/%y') if hasattr(datetime.now(), 'strftime') else datetime.now().strftime('%m/%d/%y')
        msg['Subject'] = f"Daily News: {subject_date}"

        if not content or all(len(arts) == 0 for arts in content.values()):
            body = "<p><b>No sector news articles were found today.</b></p>"
        else:
            body = "<h2 style='color:#293241;font-family:sans-serif;'>📬 Your Daily News Digest</h2>"
            for cat in categories:
                if cat in content:
                    articles = content[cat]
                    section = DISPLAY_NAMES.get(cat, cat).upper()
                    body += f"<h3 style='color:#1565c0;font-family:sans-serif;margin-bottom:0;'>{section}</h3><ul style='margin-top:5px;'>"
                    for title, date, url in articles:
                        body += (
                            f"<li style='margin-bottom:10px;font-family:sans-serif;'>"
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
    except Exception as e:
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
    except Exception:
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
        send_email(news_content or {}, config)
    except Exception as e:
        logging.error(f"Major failure: {str(e)}")
        raise
