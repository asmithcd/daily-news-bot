import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import logging

# Configuring the logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

####################################################################################################################
# Change category variable below to fetch different news topics                                                    #
# Possible categories with NewsAPI are: business, entertainment, general, health, science, sports, technology      #
####################################################################################################################
categories = [
    "auto dealers", "auto manufacturers", "auto parts",
    "solar energy", "pool industry", "mattresses",
    "appliances", "powersports", "motorcycles", "RVs"
]


# Fetching top news across multiple industries from NewsAPI 
def get_news(api_key):
    try:
        date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d') # Get yesterday's date to fetch relevant news
        url = f"https://newsapi.org/v2/top-headlines?q={category}&from={date}&sortBy=popularity&apiKey={api_key}"
      
        # Making the API request with a timeout of 10 seconds
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise exception for 4xx/5xx errors (HTTP errors)
      
       all_articles = []
        for cat in categories:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": cat,
                    "apiKey": api_key,
                    "sortBy": "publishedAt",
                    "pageSize": 3
                },
                timeout=10
            )
            resp.raise_for_status()
            for art in resp.json().get("articles", []):
                all_articles.append((cat, art["title"], art["publishedAt"], art["url"]))

        if not all_articles:
            logging.warning("No articles found across all categories")

        return all_articles

    except requests.exceptions.RequestException as e: 
        logging.error(f"News API request failed: {str(e)}")
        return None # Return None in case of an error
      
# Function to send email with fetched news
def send_email(content, email_config):
    try:
        msg = MIMEMultipart() # Creating an email message using MIMEMultipart
        msg['From'] = email_config['sender_email'] # Set sender's email
        msg['To'] = email_config['receiver_email'] # Set recipient's email
        msg['Subject'] = f"📰 Daily Tech Digest - {datetime.utcnow().strftime('%Y-%m-%d')}" # Email subject with date
        
        # Creating the email body
        body = "📬 Your Daily Market News Digest:\n\n"
for cat, title, date, url in all_articles:
    body += f"[{cat.upper()}] {title} ({date})\n{url}\n\n"
msg.attach(MIMEText(body, 'plain'))
      
        # Connecting to SMTP server using SSL
        with smtplib.SMTP_SSL(email_config['smtp_server'], email_config['smtp_port'], timeout=15) as server:
            server.login(email_config['sender_email'], email_config['smtp_password']) 
            server.send_message(msg) # Send email
            logging.info("Email sent successfully") # Log success message
          
    # Handle email sending errors        
    except (smtplib.SMTPException, Exception) as e: 
        logging.error(f"Failed to send email: {str(e)}")
        raise # Raise the exception for debugging
      
# Function to check all required environment vars 
def validate_config(config):
    required_keys = ['sender_email', 'receiver_email', 'smtp_server',
                     'smtp_port', 'smtp_password', 'newsapi_key'] # List of the required keys
  
    # Check for missing keys by verifying if they are empty or not
    missing = [key for key in required_keys if not config.get(key) or str(config.get(key)).strip() == ""]

    if missing:
        logging.error(f"Missing configuration: {', '.join(missing)}") # Log missing keys
        raise ValueError("Missing environment variables") # And so raise an error

    try:
        config['smtp_port'] = int(config['smtp_port'])  # Making sure the SMTP_PORT is a valid integer
    except ValueError:
        logging.error("Invalid SMTP_PORT value") # And so log an error if conversion fails
        raise
      
# Running the main script 
if __name__ == "__main__":
    try:
      # Loading the environment variables into a dictionary
        config = {
            'sender_email': os.getenv('SENDER_EMAIL'),
            'receiver_email': os.getenv('RECEIVER_EMAIL'),
            'smtp_server': os.getenv('SMTP_SERVER'),
            'smtp_port': os.getenv('SMTP_PORT'),
            'smtp_password': os.getenv('SMTP_PASSWORD'),
            'newsapi_key': os.getenv('NEWSAPI_KEY')
        }

        # Debugging: Log environment variables 
        logging.info(f"Environment Variables: {os.environ}")  
        logging.info(f"Loaded config: {config}")  
        validate_config(config)
      
        validate_config(config) # Validate environment variables
        logging.info("Configuration validated successfully") # Log success message
      
        # Fetch news articles
        news_content = get_news(config['newsapi_key']) 
        
        if news_content: # If news content is available, send the email
            send_email(news_content, config)
        else:
            logging.warning("No news content to send") # And log a warning if no news found
            
    except Exception as e: # Catch any major failures
        logging.error(f"Major failure: {str(e)}")
        raise # And raise the exception for debugging
