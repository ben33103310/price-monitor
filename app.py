import os
import requests
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import asyncio

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
HF_API_TOKEN = os.environ.get("HF_API_TOKEN")

app = Flask(__name__)
application = Application.builder().token(TELEGRAM_TOKEN).build()

# 啟動時就建立 event loop 並初始化
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(application.initialize())

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

@app.route("/hook", methods=["POST"])
def webhook():
    try:
        json_data = request.get_json(force=True)
        print("收到 webhook 資料：", json_data, flush=True)
        update = Update.de_json(json_data, application.bot)
        # 用先前建立好的 event loop 執行 process_update
        future = asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
        future.result()  # 等待執行完成，捕獲例外
        print("已將 update 交給 application 處理", flush=True)
    except Exception as e:
        import traceback
        print("webhook 發生例外:", e, flush=True)
        print(traceback.format_exc(), flush=True)
    return "ok"

@app.route("/")
def home():
    return "🤖 Telegram Bot with Hugging Face API is running."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
