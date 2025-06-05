import asyncio
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes # 雖然這裡沒有直接用到 ContextTypes，但保留是好的習慣
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

# keep_alive
try:
    from keep_alive import keep_alive
    KEEP_ALIVE_ENABLED = True
except ImportError:
    KEEP_ALIVE_ENABLED = False
    def keep_alive(): pass

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
    if KEEP_ALIVE_ENABLED:
        print("🌐 Keep_alive 功能已啟用")

    # 背景任務：包 try，避免 silent fail
    async def safe_background():
        try:
            # 將 application 傳遞給背景任務，以便它需要時可以和 bot 互動
            await check_prices_task(application)
        except Exception as e:
            print(f"❌ 背景任務錯誤: {e}")

    # 創建背景任務，但不要等待它完成
    asyncio.create_task(safe_background())

    # 主輪詢
    try:
        # 關鍵點：設置 close_loop=False
        # 這會告訴 run_polling 方法不要在停止時嘗試關閉事件迴圈
        # 而是讓 asyncio.run() 或運行環境來管理迴圈的關閉
        await application.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)
    except Exception as e:
        print(f"❌ 機器人運行時錯誤: {e}")
        # 在這裡通常不需要再手動呼叫 application.shutdown()，因為
        # run_polling 已經設計成能自行處理關閉或由外部信號觸發關閉。
        # 如果錯誤發生，可能事件迴圈已經處於無法正確關閉的狀態，
        # 再呼叫 shutdown 可能會導致 "Cannot close a running event loop" 錯誤。
    finally:
        print("🔌 機器人已停止。")

if __name__ == "__main__":
    keep_alive()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 手動中斷")
    except Exception as e:
        print(f"❌ 啟動時錯誤: {e}")
