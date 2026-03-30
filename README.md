# AI News Telegram Bot

Telegram bot that fetches latest AI news, ranked by popularity and influence.

## Setup

1. **Create Telegram Bot**
   - Open @BotFather in Telegram
   - Send `/newbot`
   - Follow instructions to get your Bot Token

2. **Get NewsData.io API Key**
   - Sign up at https://newsdata.io
   - Get your free API key (200 requests/day)

3. **Deploy to Render (Free)**
   - Create GitHub repository with this code
   - Go to https://dashboard.render.com
   - Create new Web Service
   - Connect your GitHub repository
   - Add environment variables:
     - `TELEGRAM_BOT_TOKEN`: your telegram bot token
     - `NEWSDATA_API_KEY`: your newsdata.io API key
   - Deploy!

## Commands

- `/ai` - Get latest AI news
- `/start` - Welcome message
- `/help` - Help

## Local Development

```bash
cp .env.example .env
# Edit .env with your tokens
pip install -r requirements.txt
python bot.py
```
