import os
import pickle
import requests
import base64
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import time
from telegram import Bot, Update
from telegram.ext import CommandHandler, Updater, Application

# Telegram Bot Token & Chat ID
TELEGRAM_TOKEN = "7392297618:AAH8RqGhuF06lm9q4SLTO5lHXqHfUzgw8CM"
CHAT_ID = "1339713996"

# Gmail API Scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Authenticate Gmail API
def authenticate_gmail():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
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

        if "BTC/USDT" in email_body:  # Checking if the alert contains BTC/USDT
            send_telegram(f"Alert: {email_body}")

        # Mark email as read
        service.users().messages().modify(userId="me", id=msg["id"], body={"removeLabelIds": ["UNREAD"]}).execute()

# Send Telegram message
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": message})

# Command to start the bot
async def start(update, context):
    await update.message.reply_text("Bot has started and is checking for alerts...")

# Command to check if bot is running
async def status(update, context):
    await update.message.reply_text("Bot is online and monitoring TradingView alerts.")

# Loop to keep the bot running
def run_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add commands to the bot
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))

    # Start the bot
    application.run_polling()

    # Keep checking for new emails in a loop
    while True:
        check_email()
        time.sleep(60)  # Check every 60 seconds for new alerts

if __name__ == "__main__":
    run_bot()
