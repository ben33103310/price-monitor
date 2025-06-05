import asyncio
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram import Update
from config import TELEGRAM_TOKEN
from bot_command_handlers import (
    start_command, help_command, list_command, add_command,
    delete_command, update_command, manual_check_notify_only_command, check_all_prices_command
)
from bot_callback_handlers import main_button_callback_router
from bot_message_handlers import handle_text_message
from price_checker import check_prices_task

async def main():
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN 未設定")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # 添加所有處理器 (Handler)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("delete", delete_command))
    application.add_handler(CommandHandler("update", update_command))
    application.add_handler(CommandHandler("manual", manual_check_notify_only_command))
    application.add_handler(CommandHandler("check", check_all_prices_command))
    application.add_handler(CallbackQueryHandler(main_button_callback_router))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    print("🤖 Bot 啟動中...")

    # 背景任務
    async def safe_background():
        try:
            await check_prices_task(application)
        except Exception as e:
            print(f"❌ 背景任務錯誤: {e}")

    # 在 run_polling 前註冊背景任務
    application.create_task(safe_background())

    try:
        await application.initialize()
        await application.start()
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"❌ 機器人運行時錯誤: {e}")
    finally:
        print("🔌 機器人已停止。")
        await application.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 手動中斷")
    except Exception as e:
        print(f"❌ 啟動時錯誤: {e}")
