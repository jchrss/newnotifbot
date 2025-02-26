import os
import pickle
import json
import base64
import time
import asyncio
import requests
from io import BytesIO
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

# Load environment variables
load_dotenv()

# Environment Variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CREDENTIALS_JSON_BASE64 = os.getenv("CREDENTIALS_JSON")  # Base64 encoded credentials.json

# Gmail API Scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Authenticate Gmail API
def authenticate_gmail():
    creds = None

    # Decode credentials.json from Base64
    if CREDENTIALS_JSON_BASE64:
        try:
            decoded_credentials = base64.b64decode(CREDENTIALS_JSON_BASE64)
            credentials_data = json.loads(decoded_credentials.decode("utf-8"))
        except Exception as e:
            print(f"Error decoding credentials: {e}")
            return None
    else:
        print("CREDENTIALS_JSON is missing in environment variables.")
        return None

    # Load token if available
    token_path = "token.pickle"
    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)

    # Refresh or create new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(credentials_data, SCOPES)

            # Use manual authorization instead of browser
            auth_url, _ = flow.authorization_url(prompt="consent")
            print(f"\n🔗 Open this link in your browser to authorize: {auth_url}")

            # Ask the user to enter the authorization code
            auth_code = input("\n📌 Enter the authorization code here: ").strip()
            creds = flow.fetch_token(code=auth_code)

            # Save credentials for future use
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)

    return build("gmail", "v1", credentials=creds)

# Fetch unread TradingView alerts
def check_email():
    service = authenticate_gmail()
    if not service:
        return

    results = service.users().messages().list(userId="me", labelIds=["INBOX"], q="is:unread").execute()
    messages = results.get("messages", [])

    for msg in messages:
        msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
        email_body = msg_data["snippet"]

        if "BTC/USDT" in email_body:  # Checking if the alert contains BTC/USDT
            send_telegram(f"🚀 TradingView Alert: {email_body}")

        # Mark email as read
        service.users().messages().modify(userId="me", id=msg["id"], body={"removeLabelIds": ["UNREAD"]}).execute()

# Send Telegram message
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": message})

# Telegram command handlers
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("🚀 Bot is active and monitoring TradingView alerts!")

async def status(update: Update, context: CallbackContext):
    await update.message.reply_text("✅ Bot is online and checking TradingView alerts.")

# Run the bot
async def run_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))

    # Initialize and start the bot properly
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    print("✅ Telegram bot is running!")

    # Keep checking emails in a loop
    while True:
        check_email()
        await asyncio.sleep(60)  # Check emails every 60 seconds

if __name__ == "__main__":
    asyncio.run(run_bot())
