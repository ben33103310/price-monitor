import os
import re
import requests
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, MessageHandler, Filters

# --- 設定 ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
app = Flask(__name__)
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# --- 價格擷取函式（目前支援 PChome） ---
def extract_price_from_url(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status()
        html = res.text

        if "pchome.com.tw" in url:
            match = re.search(r'"price"\s*:\s*"(\d+)"', html)
            if match:
                return f"💰 PChome 價格：{match.group(1)} 元"
            else:
                return "⚠️ 找不到價格，可能不是商品頁"

        return "❓ 暫時只支援 PChome 網址"
    except Exception as e:
        return f"⚠️ 無法抓取價格：{e}"

# --- 處理訊息 ---
def handle_message(update, context):
    text = update.message.text.strip()
    if text.startswith("http"):
        reply = extract_price_from_url(text)
    else:
        reply = "請貼上商品網址，我會幫你查詢價格 🛒"
    update.message.reply_text(reply)

dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

# --- Flask 路由 ---
@app.route('/')
def index():
    return "🤖 Telegram 價格查詢機器人運行中！"

@app.route('/hook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

# --- 主程式 ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
