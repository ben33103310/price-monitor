import os
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, MessageHandler, Filters

TOKEN = os.environ.get("TELEGRAM_TOKEN")
app = Flask(__name__)
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

def echo(update, context):
    text = update.message.text
    update.message.reply_text(text)

dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

@app.route('/')
def index():
    return "🤖 Telegram Bot is running."

@app.route('/hook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
