
# app.py
import os
import logging
import requests
from flask import Flask, request

from telegram import Bot, Update
from telegram.ext import Dispatcher, MessageHandler, filters

# --- Telegram Bot 設定 ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")  # 請在 Render 上設為環境變數
bot = Bot(token=TOKEN)

# --- Flask 設定 ---
app = Flask(__name__)

# --- Telegram Dispatcher ---
dispatcher = Dispatcher(bot=bot, update_queue=None)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 功能：抓取價格 ---
def extract_price_from_url(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status()
        html = res.text

        # PChome
        if "pchome.com.tw" in url:
            import re
            match = re.search(r'\"Price\":(\d+)', html)
            if match:
                return f"PChome 價格：{match.group(1)} 元"

        return "❓ 尚未支援這個網站或抓不到價格"

    except Exception as e:
        logger.error(f"抓取價格失敗: {e}")
        return "⚠️ 價格抓取失敗，請確認網址是否正確"

# --- 回覆處理器 ---
def handle_message(update: Update, context):
    text = update.message.text.strip()
    if text.startswith("http"):
        price_info = extract_price_from_url(text)
        update.message.reply_text(price_info)
    else:
        update.message.reply_text("請貼上商品網址，我會幫你查詢價格 🛒")

# 註冊 Handler
dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- Webhook 入口 ---
@app.route("/hook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

# --- 根目錄測試 ---
@app.route("/")
def home():
    return "🤖 Telegram 價格查詢機器人運行中！"

# --- 啟動 Flask App ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
