# main.pyMore actions
import asyncio
import nest_asyncio

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes # 雖然沒直接用，但 handler 簽名需要
)

# 匯入設定
from config import TELEGRAM_TOKEN

# 匯入處理函式
from bot_command_handlers import (
    start_command, help_command, list_command, add_command,
    delete_command, update_command, manual_check_notify_only_command, check_all_prices_command
)
from bot_callback_handlers import main_button_callback_router
from bot_message_handlers import handle_text_message
from telegram import Update

# 匯入背景任務
from price_checker import check_prices_task

# 匯入 keep_alive (如果需要)
try:
    from keep_alive import keep_alive
    KEEP_ALIVE_ENABLED = True
except ImportError:
    KEEP_ALIVE_ENABLED = False
    print("ℹ️ 提示：'keep_alive.py' 未找到，將不啟用 keep_alive 功能。")
    def keep_alive(): # Dummy function if not found
        pass


async def main():
    if not TELEGRAM_TOKEN:
        # config.py 應該已經處理了這個，但再次檢查以防萬一
        print("❌ 致命錯誤：TELEGRAM_TOKEN 未在環境變數或 config.py 中設定。程式無法啟動。")
        return

    # ApplicationBuilder 取代了 Application.builder()
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # 註冊指令處理器 (文字指令)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_command)) # 保留指令版本, 或讓它調用 callback
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("delete", delete_command))
    application.add_handler(CommandHandler("update", update_command))
    # 更新指令名稱以匹配 callback handler 的功能描述
    application.add_handler(CommandHandler("check", check_all_prices_command))       # 原 check_command

    # 註冊按鈕回調處理器
    application.add_handler(CallbackQueryHandler(main_button_callback_router))

    # 註冊一般文字訊息處理器 (用於新增/更新商品的對話流程)
    # 確保此 Handler 在 CommandHandler 和 CallbackQueryHandler 之後，
    # 並且只處理非指令的文字訊息。
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    print("🤖 Telegram 價格監控機器人已啟動！")
    print("🕒 Bot 會在背景定期檢查價格，並在價格達標時發送通知。")
    if KEEP_ALIVE_ENABLED:
        print("🚀 Keep_alive 功能已啟用。")


    # 啟動背景價格檢查任務
    # 將 application 傳遞給背景任務，以便它能使用 bot 對象
    asyncio.create_task(check_prices_task(application))

    # 啟動 Bot (開始輪詢)
    try:
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"❌ 機器人運行時發生錯誤: {e}")
    finally:
        print("🔌 機器人已停止。")

if __name__ == "__main__":
    nest_asyncio.apply() # 允許在某些環境中巢狀執行 asyncio 事件迴圈More actions
    if KEEP_ALIVE_ENABLED:
        keep_alive() # 啟動 keep_alive (例如在 Replit 上)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 使用者手動中斷程式。")
    except Exception as e:
        print(f"❌ 程式啟動時發生嚴重錯誤: {e}")
