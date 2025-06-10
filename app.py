import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TELEGRAM_TOKEN")

application = Application.builder().token(TOKEN).build()

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    await update.message.reply_text(text)

application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

if __name__ == "__main__":
    application.run_polling()
