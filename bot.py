import os
import sys
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any
import threading
import time

import requests
import telebot
import feedparser
from bs4 import BeautifulSoup
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from openai import OpenAI

print(f"Python version: {sys.version}")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-rizvilrtphnzdusxuldevvueensntaqjzcubsusymxeumxdo")

AI_RSS_FEEDS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://www.theverge.com/rss/index.xml",
    "https://wired.com/feed/rss",
    "https://www.engadget.com/rss.xml",
    "https://venturebeat.com/feed/",
    "https://techcrunch.com/feed/",
    "https://www.artificialintelligence-news.com/feed/",
]

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

app = Flask(__name__)

user_chat_ids = set()

scheduler = BackgroundScheduler()

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://api.siliconflow.cn/v1"
)


def fetch_rss_news():
    articles = []
    
    for feed_url in AI_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                article = {
                    "title": entry.get("title", "No title"),
                    "link": entry.get("link", ""),
                    "description": entry.get("summary", entry.get("description", "")),
                    "published": entry.get("published", ""),
                    "source": feed.feed.get("title", "Unknown")
                }
                articles.append(article)
        except Exception as e:
            logger.error(f"RSS error: {e}")
            print(f"RSS error: {e}")
    
    return articles


def scrape_article_content(url: str) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
            element.decompose()
        
        article = soup.find('article') or soup.find('main') or soup.find('div', class_=lambda x: x and 'content' in x.lower())
        
        if article:
            text = article.get_text(separator=" ", strip=True)
        else:
            text = soup.get_text(separator=" ", strip=True)
        
        text = re.sub(r'\s+', ' ', text)
        
        sentences = text.split('. ')
        meaningful_sentences = []
        for s in sentences:
            if len(s) > 30:
                meaningful_sentences.append(s)
        
        text = '. '.join(meaningful_sentences[:15])
        
        return text[:3000]
    
    except Exception as e:
        logger.error(f"Scraper error: {e}")
        print(f"Scraper error: {e}")
        return ""


def translate_and_analyze(title: str, content: str) -> Dict[str, str]:
    prompt = f"""你是一位资深的AI行业分析师。请仔细阅读以下新闻，然后：

1. 将新闻标题精练地翻译成中文（不超过20字）
2. 用50字以内分析对AI股市的影响（关注相关股票涨跌、行业信心）
3. 用50字以内分析对AI学习者的影响（关注技能需求、学习方向）
4. 用50字以内分析对AI从业者的影响（关注岗位变化、技术趋势）

新闻标题：{title}
新闻内容：{content[:1500]}

严格按照这个格式回复（不要有任何额外内容）：
翻译：[中文标题]
股市：[分析]
学习：[分析]
从业：[分析]"""

    try:
        response = client.chat.completions.create(
            model="Qwen/Qwen2.5-14B-Instruct",
            messages=[
                {"role": "system", "content": "你是一位资深的AI行业分析师，擅长分析AI新闻对不同群体的影响。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=400
        )
        
        result = response.choices[0].message.content
        print(f"LLM result: {result}")
        
        lines = result.strip().split("\n")
        translation = ""
        stock_impact = ""
        learner_impact = ""
        practitioner_impact = ""
        
        for line in lines:
            if line.startswith("翻译："):
                translation = line[3:].strip()
            elif line.startswith("股市影响："):
                stock_impact = line[5:].strip()
            elif line.startswith("学习影响："):
                learner_impact = line[5:].strip()
            elif line.startswith("从业影响："):
                practitioner_impact = line[5:].strip()
        
        return {
            "translation": translation,
            "stock_impact": stock_impact,
            "learner_impact": learner_impact,
            "practitioner_impact": practitioner_impact
        }
    
    except Exception as e:
        logger.error(f"LLM error: {e}")
        print(f"LLM error: {e}")
        return {
            "translation": title,
            "stock_impact": "",
            "learner_impact": "",
            "practitioner_impact": ""
        }


def fetch_ai_news_with_content(max_results: int = 10) -> List[Dict[str, Any]]:
    articles = fetch_rss_news()
    
    for article in articles:
        content = scrape_article_content(article["link"])
        article["content"] = content or article.get("description", "")
        
        analysis = translate_and_analyze(article["title"], article["content"])
        article.update(analysis)
    
    return articles[:max_results]


def format_news_message(articles: List[Dict[str, Any]]) -> str:
    if not articles:
        return "No AI news found. Please try again later."
    
    message = "🤖 AI News Daily\n"
    message += "=" * 35 + "\n\n"
    
    for i, article in enumerate(articles, 1):
        translation = article.get("translation", article.get("title", ""))
        
        stock = article.get("stock_impact", "").strip()
        learner = article.get("learner_impact", "").strip()
        practitioner = article.get("practitioner_impact", "").strip()
        
        source = article.get("source", "Unknown")
        
        message += f"{i}. {translation}\n"
        
        if stock:
            message += f"   📈 {stock}\n"
        if learner:
            message += f"   📚 {learner}\n"
        if practitioner:
            message += f"   💼 {practitioner}\n"
        
        message += f"   📰 {source}\n"
        message += "\n"
    
    message += "-" * 35 + "\n"
    message += "/ai - 刷新 | /subscribe - 订阅每日"
    
    return message


def daily_push():
    if not user_chat_ids:
        return
    
    try:
        articles = fetch_ai_news_with_content(max_results=5)
        message = format_news_message(articles)
        
        for chat_id in user_chat_ids:
            try:
                bot.send_message(chat_id, message)
            except Exception as e:
                logger.error(f"Push error: {e}")
    except Exception as e:
        logger.error(f"Daily push error: {e}")


scheduler.add_job(daily_push, 'cron', hour=10, minute=0)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_chat_ids.add(message.chat.id)
    welcome_text = (
        "Welcome to AI News Bot!\n\n"
        "Commands:\n"
        "- /ai - Get latest AI news\n"
        "- /subscribe - Daily push at 10:00\n"
        "- /unsubscribe - Cancel\n"
    )
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "Commands:\n"
        "- /ai - Get AI news with LLM analysis\n"
        "- /subscribe - Daily push\n"
        "- /unsubscribe - Cancel\n"
    )
    bot.reply_to(message, help_text)


@bot.message_handler(commands=['ai'])
def send_ai_news(message):
    bot.reply_to(message, "Fetching AI news with LLM analysis...")
    
    try:
        articles = fetch_ai_news_with_content(max_results=5)
        message_text = format_news_message(articles)
        bot.reply_to(message, message_text)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        bot.reply_to(message, "Error. Try again later.")


@bot.message_handler(commands=['subscribe'])
def subscribe(message):
    user_chat_ids.add(message.chat.id)
    bot.reply_to(message, "Subscribed! Daily at 10:00 AM.")


@bot.message_handler(commands=['unsubscribe'])
def unsubscribe(message):
    user_chat_ids.discard(message.chat.id)
    bot.reply_to(message, "Unsubscribed.")


@bot.message_handler(func=lambda m: True)
def echo_message(message):
    bot.reply_to(message, "Try /ai")


def run_bot():
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)


@app.route('/')
def home():
    return 'AI News Bot is running!'


@app.route('/health')
def health():
    return 'OK'


def main():
    print("Starting AI News Bot...")
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        sys.exit(1)
    
    scheduler.start()
    print("Scheduler: daily 10:00 AM")
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    logger.info("Bot started!")
    print("Bot is running...")
    
    app.run(host='0.0.0.0', port=10000)


if __name__ == "__main__":
    main()
