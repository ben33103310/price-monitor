import os
import requests
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
HF_API_TOKEN = os.environ.get("HF_API_TOKEN")

app = Flask(__name__)

application = Application.builder().token(TELEGRAM_TOKEN).build()

HF_API_URL = "https://api-inference.huggingface.co/models/gpt2"

def query_hf_api(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {HF_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"inputs": prompt}
    response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=10)
    if response.status_code == 200:
        try:
            data = response.json()
            if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
                return data[0]["generated_text"]
            else:
                return "🤖 無法取得回應，請稍後再試"
        except Exception:
            return "🤖 回應解析失敗"
    else:
        return f"🤖 API 呼叫失敗，狀態碼：{response.status_code}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print("handle_message 被觸發，收到訊息:", user_text, flush=True)
    reply = query_hf_api(user_text)
    await update.message.reply_text(reply)

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

import asyncio

@app.route("/hook", methods=["POST"])
def webhook():
    try:
        json_data = request.get_json(force=True)
        print("收到 webhook 資料：", json_data, flush=True)
        update = Update.de_json(json_data, application.bot)
        # 初始化 Application（只在第一次）
        if not getattr(application, "_is_initialized", False):
            asyncio.run(application.initialize())
            application._is_initialized = True
        # 執行 update 處理
        asyncio.run(application.process_update(update))
        print("已將 update 交給 application 處理", flush=True)
    except Exception as e:
        print("webhook 發生例外:", e, flush=True)
    return "ok"

@app.route("/")
def home():
    return "🤖 Telegram Bot with Hugging Face API is running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
