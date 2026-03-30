import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

import requests
import telegram
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

print(f"Python version: {sys.version}")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")

NEWS_API_URL = "https://newsdata.io/api/1/latest"

AI_KEYWORDS = (
    '"AI" OR "artificial intelligence" OR "machine learning" OR '
    '"LLM" OR "GPT" OR "OpenAI" OR "Claude" OR "Gemini" OR '
    '"neural network" OR "deep learning" OR "AGI" OR "generative AI"'
)


def fetch_ai_news(max_results: int = 20) -> List[Dict[str, Any]]:
    now = datetime.now()
    from_date = (now - timedelta(hours=12)).strftime("%Y-%m-%d")
    
    params = {
        "apikey": NEWSDATA_API_KEY,
        "category": "technology",
        "q": AI_KEYWORDS,
        "language": "en",
        "country": "us,gb,ca,au",
        "from_date": from_date,
        "size": max_results,
    }
    
    try:
        response = requests.get(NEWS_API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.error(f"API request failed: {e}")
        print(f"API request failed: {e}")
        return []
    
    if data.get("status") not in ("ok", "success"):
        logger.error(f"API error: {data}")
        print(f"API error: {data}")
        return []
    
    return data.get("results", [])


def calculate_relevance_score(article: Dict[str, Any]) -> float:
    score = 0.0
    
    source_priority = article.get("source_priority", 50)
    score += source_priority * 0.5
    
    if article.get("image_url"):
        score += 15
    
    if article.get("video_url"):
        score += 20
    
    if article.get("content"):
        score += 10
    if article.get("description"):
        score += 5
    
    pub_date = article.get("pubDate", "")
    if pub_date:
        try:
            article_date = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
            hours_ago = (datetime.now(article_date.tzinfo) - article_date).total_seconds() / 3600
            if hours_ago < 3:
                score += 10
            elif hours_ago < 6:
                score += 5
        except:
            pass
    
    return score


def rank_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for article in articles:
        article["relevance_score"] = calculate_relevance_score(article)
    
    return sorted(articles, key=lambda x: x["relevance_score"], reverse=True)


def truncate_content(content: str, max_length: int = 100) -> str:
    if not content:
        return ""
    
    content = " ".join(content.split())
    
    if len(content) <= max_length:
        return content
    
    truncated = content[:max_length].rsplit(" ", 1)[0]
    return truncated + "..."


def format_news_message(articles: List[Dict[str, Any]], limit: int = 10) -> str:
    if not articles:
        return "No AI news found. Please try again later."
    
    ranked = rank_articles(articles)[:limit]
    
    message = "Todays AI News\n"
    message += "--------------------------------\n\n"
    
    for i, article in enumerate(ranked, 1):
        title = article.get("title", "No title")
        title = title.replace("*", "").replace("_", "").replace("`", "")
        
        content = article.get("content") or article.get("description") or ""
        summary = truncate_content(content, 100)
        
        source = article.get("source_name", article.get("source_id", "Unknown"))
        
        pub_date = article.get("pubDate", "")
        if pub_date:
            try:
                article_date = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                time_str = article_date.strftime("%H:%M")
            except:
                time_str = ""
        else:
            time_str = ""
        
        message += f"[{i}] {title}\n"
        if summary:
            message += f"   {summary}\n"
        message += f"   {source}"
        if time_str:
            message += f" - {time_str}"
        message += "\n\n"
    
    message += "--------------------------------\n"
    message += "/ai - Refresh news"
    
    return message


def start_command(update: Update, context):
    welcome_text = (
        "Welcome to AI News Bot!\n\n"
        "I fetch the latest AI news from around the world, "
        "ranked by popularity and influence.\n\n"
        "Commands:\n"
        "- /ai - Get latest AI news\n"
        "- /help - Show this help\n\n"
        "Let's go!"
    )
    update.message.reply_text(welcome_text)


def help_command(update: Update, context):
    help_text = (
        "Help\n"
        "- /ai - Fetch latest AI news (last 12 hours)\n"
        "- /start - Welcome message\n"
        "- /help - Show this help\n\n"
        "News is ranked by source credibility, content engagement, and recency.\n"
        "Each news item is summarized to 100 characters."
    )
    update.message.reply_text(help_text)


def ai_command(update: Update, context):
    update.message.reply_text("Fetching latest AI news...")
    
    try:
        articles = fetch_ai_news(max_results=20)
        
        message = format_news_message(articles, limit=10)
        context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=update.message.message_id + 1,
            text=message
        )
        
    except Exception as e:
        logger.error(f"Error in /ai command: {e}")
        context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=update.message.message_id + 1,
            text="Error fetching news. Please try again later."
        )


def handle_message(update: Update, context):
    update.message.reply_text(
        "I only understand commands. Try /ai to get AI news!"
    )


def main():
    print("Starting AI News Bot...")
    print(f"Python: {sys.version}")
    print(f"TELEGRAM_BOT_TOKEN set: {bool(TELEGRAM_BOT_TOKEN)}")
    print(f"NEWSDATA_API_KEY set: {bool(NEWSDATA_API_KEY)}")
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        print("Error: Please set TELEGRAM_BOT_TOKEN environment variable")
        sys.exit(1)
    
    if not NEWSDATA_API_KEY:
        logger.error("NEWSDATA_API_KEY not set!")
        print("Error: Please set NEWSDATA_API_KEY environment variable")
        sys.exit(1)
    
    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
    dispatcher.add_handler(CommandHandler("start", start_command))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("ai", ai_command))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    logger.info("Bot started!")
    print("Bot is running...")
    
    updater.start_polling(poll_interval=1.0)
    updater.idle()


if __name__ == "__main__":
    main()
