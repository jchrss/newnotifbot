import os
import pickle
import json
import base64
import requests
import time
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CREDENTIALS_JSON = os.getenv("CREDENTIALS_JSON")  # Base64 encoded credentials.json

# Function to decode credentials and authenticate Gmail API
def authenticate_gmail():
    creds = None
    
    # Decode credentials.json from environment variable
    credentials_path = "credentials.json"
    if CREDENTIALS_JSON:
        with open(credentials_path, "wb") as f:
            f.write(base64.b64decode(CREDENTIALS_JSON))

    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, ["https://www.googleapis.com/auth/gmail.modify"])
        creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    
    return build("gmail", "v1", credentials=creds)

# Fetch unread TradingView alerts
def check_email():
    service = authenticate_gmail()
    results = service.users().messages().list(userId="me", labelIds=["INBOX"], q="is:unread").execute()
    messages = results.get("messages", [])

    for msg in messages:
        msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
        email_body = msg_data["snippet"]

        send_telegram(f"🚀 TradingView Alert: {email_body}")

        # Mark email as read
        service.users().messages().modify(userId="me", id=msg["id"], body={"removeLabelIds": ["UNREAD"]}).execute()

# Send Telegram message
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": message})

if __name__ == "__main__":
    check_email()
