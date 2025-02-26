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
TOKEN_PICKLE_BASE64 = os.getenv("TOKEN_PICKLE")  # Base64 encoded token.pickle

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
            print(f"❌ Error decoding credentials: {e}")
            return None
    else:
        print("❌ CREDENTIALS_JSON is missing in environment variables.")
        return None

    # Try to load token from base64 environment variable
    if TOKEN_PICKLE_BASE64:
        try:
            decoded_token = base64.b64decode(TOKEN_PICKLE_BASE64)
            creds = pickle.loads(decoded_token)
            print("✅ Successfully loaded token from environment variable")
        except Exception as e:
            print(f"❌ Error decoding token from environment: {e}")
            # Fall back to file if environment variable fails

    # If no valid token from environment, try local file
    if not creds and os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token_file:
            creds = pickle.load(token_file)
            print("✅ Successfully loaded token from file")

    # Refresh or create new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token")
            creds.refresh(Request())
        else:
            print("🔑 Generating new token through authorization flow")
            flow = InstalledAppFlow.from_client_config(credentials_data, SCOPES)

            # Get manual authorization URL
            auth_url, _ = flow.authorization_url(prompt="consent")
            print(f"\n🔗 Open this link in your browser to authorize:\n{auth_url}")

            # Get authorization code from user
            auth_code = input("\n📌 Enter the authorization code here: ").strip()
            
            # Fetch the access token using the authorization code
            flow.fetch_token(code=auth_code)
            creds = flow.credentials

        # Save credentials to file
        with open("token.pickle", "wb") as token_file:
            pickle.dump(creds, token_file)
            
        # Generate and print base64 encoded token for environment variable
        token_bytes = pickle.dumps(creds)
        token_base64 = base64.b64encode(token_bytes).decode('utf-8')
        print("\n✅ New TOKEN_PICKLE for environment variable:")
        print(f"{token_base64}")
        
        # Optionally update the environment variable if possible
        os.environ["TOKEN_PICKLE"] = token_base64

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

# Utility command to generate base64 token from existing token.pickle
async def generate_token_base64(update: Update, context: CallbackContext):
    if str(update.message.chat_id) == CHAT_ID:  # Only allow for authorized chat
        try:
            if os.path.exists("token.pickle"):
                with open("token.pickle", "rb") as token_file:
                    token_data = token_file.read()
                    encoded = base64.b64encode(token_data).decode('utf-8')
                    # Send in multiple messages if too long
                    if len(encoded) > 4000:
                        chunks = [encoded[i:i+4000] for i in range(0, len(encoded), 4000)]
                        await update.message.reply_text(f"Token (part 1/{len(chunks)}):")
                        await update.message.reply_text(chunks[0])
                        for i, chunk in enumerate(chunks[1:], 2):
                            await update.message.reply_text(f"Token (part {i}/{len(chunks)}):")
                            await update.message.reply_text(chunk)
                    else:
                        await update.message.reply_text("Your TOKEN_PICKLE value:")
                        await update.message.reply_text(encoded)
            else:
                await update.message.reply_text("❌ token.pickle file not found")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
    else:
        await update.message.reply_text("⛔ Unauthorized")

# Run the bot
async def run_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("token", generate_token_base64))

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