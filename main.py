import os
import requests
import time
import pytz
import logging
import json
from datetime import datetime, time as dtime
from deep_translator import GoogleTranslator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Load environment variables
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
MYANMAR_TZ = pytz.timezone('Asia/Yangon')
CHAT_IDS_FILE = "chat_ids.json"

# Flask app for health check (needed for Render)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

translator = GoogleTranslator(source='en', target='my')

def translate_to_myanmar(text):
    if not text:
        return ""
    try:
        translated = translator.translate(text)
        return translated
    except Exception as e:
        logging.error(f"Translation error: {e}")
        return text

def get_myanmar_news():
    url = f"https://newsapi.org/v2/everything?q=Myanmar&sortBy=publishedAt&apiKey={NEWS_API_KEY}&language=en"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get('articles', [])[:5]  # Get top 5 news
    except Exception as e:
        logging.error(f"News API error: {e}")
    return []

async def send_news_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    news_articles = get_myanmar_news()
    
    if not news_articles:
        # Avoid sending "no news" message during scheduled jobs to reduce noise
        return

    for article in news_articles:
        title = article["title"]
        description = article["description"] or "No description available"
        news_url = article["url"]
        
        # Translate title and description
        mm_title = translate_to_myanmar(title)
        mm_desc = translate_to_myanmar(description)
        
        message_text = f"📰 *{mm_title}*\n\n{mm_desc}\n\n🔗 [မူရင်းသတင်းဖတ်ရန်]({news_url})"
        
        keyboard = [[InlineKeyboardButton("သတင်းအပြည့်အစုံဖတ်ရန်", url=news_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await context.bot.send_message(
                chat_id=chat_id, 
                text=message_text, 
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            logging.error(f"Error sending message to {chat_id}: {e}")

def load_chat_ids():
    if os.path.exists(CHAT_IDS_FILE):
        try:
            with open(CHAT_IDS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading chat IDs: {e}")
    return []

def save_chat_ids(chat_ids):
    try:
        with open(CHAT_IDS_FILE, 'w') as f:
            json.dump(list(chat_ids), f)
    except Exception as e:
        logging.error(f"Error saving chat IDs: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id, 
        text="မင်္ဂလာပါ။ မြန်မာနိုင်ငံသတင်းများကို နေ့စဉ် ၉ နာရီ၊ ၁၂ နာရီ နှင့် ညနေ ၅ နာရီတို့တွင် ပို့ပေးပါမည်။"
    )
    
    # Add chat_id to persistence
    chat_ids = set(load_chat_ids())
    if chat_id not in chat_ids:
        chat_ids.add(chat_id)
        save_chat_ids(chat_ids)

    # Schedule news updates for this user
    schedule_jobs_for_chat(context.application, chat_id)
    
    # Send news immediately for confirmation
    news_articles = get_myanmar_news()
    if news_articles:
        for article in news_articles[:1]: # Just send 1 for confirmation
            title = translate_to_myanmar(article["title"])
            news_url = article["url"]
            await context.bot.send_message(
                chat_id=chat_id, 
                text=f"စမ်းသပ်မှု အောင်မြင်ပါသည်။ လက်ရှိသတင်း - \n\n📰 *{title}*\n\n🔗 [မူရင်းသတင်းဖတ်ရန်]({news_url})",
                parse_mode='Markdown'
            )

def schedule_jobs_for_chat(application, chat_id):
    # Clear existing jobs for this chat_id to prevent duplicates
    current_jobs = application.job_queue.get_jobs_by_name(f"news_{chat_id}")
    for job in current_jobs:
        job.schedule_removal()

    times = ["09:00", "12:00", "17:00"]
    for t_str in times:
        h, m = map(int, t_str.split(":"))
        # Create a time object in Myanmar TZ
        job_time = dtime(hour=h, minute=m, tzinfo=MYANMAR_TZ)
        
        application.job_queue.run_daily(
            send_news_job, 
            time=job_time,
            chat_id=chat_id,
            name=f"news_{chat_id}" # Group name for easier management
        )
    logging.info(f"Scheduled jobs for chat_id: {chat_id}")

if __name__ == '__main__':
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start Telegram Bot
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Setup jobs for previously registered chat IDs
    chat_ids = load_chat_ids()
    for cid in chat_ids:
        schedule_jobs_for_chat(application, cid)

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)
    
    logging.info("Bot is starting...")
    application.run_polling()
