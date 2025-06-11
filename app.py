import os
import requests
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# 環境變數
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
HF_API_TOKEN = os.environ.get("HF_API_TOKEN")

app = Flask(__name__)
application = Application.builder().token(TELEGRAM_TOKEN).build()

HF_API_URL = "https://api-inference.huggingface.co/models/gpt2"  # 這邊可換別的聊天模型

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
            # gpt2 是文本生成，回傳格式可能是 list，取生成文字即可
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
    print("handle_message 被觸發，收到訊息:", update.message.text)
    reply = query_hf_api(user_text)
    await update.message.reply_text(reply)

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.route("/hook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    print("收到 webhook 資料：", update)  # 幫你看 webhook 原始資料
    return "ok"

@app.route("/")
def home():
    return "🤖 Telegram Bot with Hugging Face API is running."

if __name__ == "__main__":
    import threading
    threading.Thread(target=application.run_polling, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
