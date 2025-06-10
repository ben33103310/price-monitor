import os
import logging
import requests
from flask import Flask, request

from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, ContextTypes, filters

# --- 設定 ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")  # 在 Render 上設為環境變數

# --- Flask 初始化 ---
app = Flask(__name__)

# --- 機器人應用初始化 ---
application = Application.builder().token(TOKEN).build()

# --- 價格擷取函式 ---
def extract_price_from_url(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status()
        html = res.text

        if "pchome.com.tw" in url:
            import re
            match = re.search(r'\"Price\":(\d+)', html)
            if match:
                return f"PChome 價格：{match.group(1)} 元"

        return "❓ 尚未支援這個網站或抓不到價格"

    except Exception as e:
        logging.error(f"抓取價格失敗: {e}")
        return "⚠️ 價格抓取失敗，請確認網址是否正確"

# --- 處理訊息 ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("http"):
        price_info = extract_price_from_url(text)
        await update.message.reply_text(price_info)
    else:
        await update.message.reply_text("請貼上商品網址，我會幫你查詢價格 🛒")

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- Webhook 接收端點 ---
@app.route("/hook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok"

# --- Render 根目錄健康檢查 ---
@app.route("/")
def home():
    return "🤖 Telegram 價格查詢機器人運行中！"

if __name__ == "__main__":
    import threading
    threading.Thread(target=application.run_polling, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
