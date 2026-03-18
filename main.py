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
    return "AI News Bot is running!"

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

def get_ai_news():
    url = f"https://newsapi.org/v2/everything?q=Artificial Intelligence&sortBy=publishedAt&apiKey={NEWS_API_KEY}&language=en"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get('articles', [])[:5]
    except Exception as e:
        logging.error(f"News API error: {e}")
    return []

async def send_news_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    news_articles = get_ai_news()
    
    if not news_articles:
        return

    for article in news_articles:
        title = article["title"]
        description = article["description"] or "No description available"
        news_url = article["url"]
        
        mm_title = translate_to_myanmar(title)
        mm_desc = translate_to_myanmar(description)
        
        message_text = f"🤖 *AI သတင်း - {mm_title}*\n\n{mm_desc}\n\n🔗 [မူရင်းသတင်းဖတ်ရန်]({news_url})"
        
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

def schedule_jobs_for_chat(application, chat_id):
    # Use chat_id in the name to manage jobs per user
    job_name_prefix = f"news_{chat_id}"
    
    # Remove existing jobs for this user to avoid duplicates
    current_jobs = application.job_queue.get_jobs_by_name(job_name_prefix)
    for job in current_jobs:
        job.schedule_removal()

    # Schedule at 9:00 AM, 12:00 PM, 5:00 PM Myanmar Time
    times = ["09:00", "12:00", "17:00"]
    for t_str in times:
        h, m = map(int, t_str.split(":"))
        # The python-telegram-bot job_queue handles timezone-aware time objects correctly
        job_time = dtime(hour=h, minute=m, tzinfo=MYANMAR_TZ)
        
        application.job_queue.run_daily(
            send_news_job, 
            time=job_time,
            chat_id=chat_id,
            name=job_name_prefix
        )
    logging.info(f"Scheduled 3 daily AI news jobs for chat_id: {chat_id} (MMT)")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id, 
        text="မင်္ဂလာပါ။ Artificial Intelligence (AI) ဆိုင်ရာ သတင်းများကို နေ့စဉ် ၉ နာရီ၊ ၁၂ နာရီ နှင့် ညနေ ၅ နာရီတို့တွင် ပို့ပေးပါမည်။"
    )
    
    chat_ids = set(load_chat_ids())
    if chat_id not in chat_ids:
        chat_ids.add(chat_id)
        save_chat_ids(chat_ids)

    schedule_jobs_for_chat(context.application, chat_id)
    
    # Send one latest news immediately as confirmation
    news_articles = get_ai_news()
    if news_articles:
        article = news_articles[0]
        title = translate_to_myanmar(article["title"])
        news_url = article["url"]
        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"AI သတင်းများ စတင်ပို့ဆောင်ပေးပါမည်။ လက်ရှိသတင်း - \n\n🤖 *{title}*\n\n🔗 [မူရင်းသတင်းဖတ်ရန်]({news_url})",
            parse_mode='Markdown'
        )

if __name__ == '__main__':
    # Start Flask for Render health check
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start Telegram Bot
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Register previously saved users and their jobs
    chat_ids = load_chat_ids()
    for cid in chat_ids:
        schedule_jobs_for_chat(application, cid)

    application.add_handler(CommandHandler('start', start))
    
    logging.info("AI News Bot is starting and ready to deliver news at 09:00, 12:00, 17:00 MMT.")
    application.run_polling()
