import os
from telegram import Bot
from dotenv import load_dotenv
import asyncio

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

async def send_notification(message):
    """Sends a notification message to the configured Telegram chat."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram environment variables not set. Skipping notification.")
        return False
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        print("Telegram notification sent successfully.")
        return True
    except Exception as e:
        print(f"Error sending Telegram notification: {e}")
        return False

def format_product_notification(title, price, url, platform):
    """Formats a message for a newly tracked product."""
    return f"""
🔔 <b>New Product Tracked</b>

📦 <b>Product:</b> {title}
💰 <b>Initial Price:</b> {price:.2f}
🛍️ <b>Platform:</b> {platform}
🔗 <a href="{url}">View Product</a>

Monitoring has started. We'll let you know about price drops!
"""

def format_price_alert(title, price, url, platform, target_price):
    """Formats a price drop alert message."""
    return f"""
⚠️ <b>Price Alert!</b>

The price for your tracked product has dropped!

📦 <b>Product:</b> {title}
💰 <b>Current Price: {price:.2f}</b>
🎯 <b>Your Target:</b> {target_price:.2f}
🛍️ <b>Platform:</b> {platform}
🔗 <a href="{url}">Buy Now!</a>
"""