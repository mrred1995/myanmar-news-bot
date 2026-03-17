# Myanmar News Telegram Bot

A Telegram Bot that sends Myanmar-related news translated into Burmese.

## Features
- Fetches news from News API about Myanmar.
- Translates titles and descriptions to Burmese using Google Translate.
- Schedules news updates at 9:00 AM, 12:00 PM, and 5:00 PM (Myanmar Time).
- Deployed on Render with a Flask health check endpoint.

## Setup
1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`
3. Set environment variables in a `.env` file:
   - `TELEGRAM_TOKEN`: Your Telegram Bot Token.
   - `NEWS_API_KEY`: Your News API Key.
4. Run the bot: `python main.py`

## Deployment on Render
1. Connect your GitHub repository to Render.
2. Create a new Web Service.
3. Set the build command: `pip install -r requirements.txt`
4. Set the start command: `python main.py`
5. Add Environment Variables in the Render dashboard:
   - `TELEGRAM_TOKEN`: Your Telegram Bot Token.
   - `NEWS_API_KEY`: Your News API Key.
