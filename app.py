import os
import logging
import flask
import telebot
import google.generativeai as genai

# --- 環境變數與設定 ---
# 建議從環境變數讀取，而不是寫死在程式碼裡
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL') # Render 會提供這個 URL

# --- 初始化 ---
# 設定日誌
logging.basicConfig(level=logging.INFO)

# 初始化 Flask App (用於接收 Webhook)
app = flask.Flask(__name__)

# 初始化 Telegram Bot
bot = telebot.TeleBot(BOT_TOKEN)

# 初始化 Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
    # 選擇模型，'gemini-pro' 是一個通用且強大的模型
    model = genai.GenerativeModel('gemini-pro') 
    logging.info("Gemini Model initialized successfully.")
except Exception as e:
    logging.error(f"Error initializing Gemini: {e}")
    model = None

# --- Flask Webhook 路由 ---

# 健康檢查路由，Render 會用這個來確認你的服務是否正常
@app.route('/', methods=['GET', 'HEAD'])
def index():
    return 'ok', 200

# Webhook 路由，Telegram 會把訊息 POST 到這裡
# URL 路徑設為 BOT_TOKEN 可以增加一點安全性，避免被亂猜到
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        flask.abort(403)

# --- Telegram Bot 指令處理 ---

# 處理 /start 和 /help 指令
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, 
        "你好！我是你的 Gemini AI 助理。\n"
        "直接傳送任何訊息給我，我就會用 Gemini Pro 模型回答你。\n"
        "請開始對話吧！"
    )

# 處理所有文字訊息
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text_message(message):
    if not model:
        bot.reply_to(message, "抱歉，AI 模型目前無法使用，請聯繫管理員。")
        return

    chat_id = message.chat.id
    user_input = message.text

    try:
        # 顯示 "思考中..." 的提示
        bot.send_chat_action(chat_id, 'typing')
        
        # 呼叫 Gemini API
        response = model.generate_content(user_input)
        
        # 處理可能的安全過濾
        if not response.parts:
            bot.reply_to(message, "抱歉，我無法回答這個問題，可能觸發了安全機制。")
            logging.warning(f"Gemini response blocked for prompt: {user_input}. Response: {response.prompt_feedback}")
            return
            
        # 傳送回覆
        # 使用 Markdown 格式可以讓回覆更漂亮，但要處理 Telegram 不支援的語法
        # 這裡我們先用純文字，確保穩定
        bot.reply_to(message, response.text)

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        bot.reply_to(message, "抱歉，處理你的請求時發生了錯誤。")

# --- 主程式啟動 ---
if __name__ == "__main__":
    # 僅在本地端測試時使用 polling
    # 部署到 Render 時，我們會用 Gunicorn 啟動 Flask App
    # bot.remove_webhook()
    # logging.info("Bot is polling...")
    # bot.polling(none_stop=True)
    
    # 在 Render 上，這段不會被直接執行
    # Gunicorn 會直接尋找 `app` 這個 Flask instance
    pass
