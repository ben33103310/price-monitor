# telegram_utils.py
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

async def send_telegram_notification(bot: Bot, chat_id_to_send: str, product_url: str, price: int, target_price: int):
    try:
        message = f"""🚨 價格警報！
商品目前價格：${price:,}
已低於或等於您的目標價格 ${target_price:,}

商品連結：
{product_url}"""
        await bot.send_message(chat_id=str(chat_id_to_send), text=message) # 確保 chat_id 是字串
        print(f"✅ 已發送 Telegram 通知至 {chat_id_to_send}")
    except Exception as e:
        print(f"❌ 發送 Telegram 通知錯誤: {e}")

def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📋 查看追蹤清單", callback_data='list_products')],
        [InlineKeyboardButton("➕ 新增追蹤商品", callback_data='add_product_start')],
        [InlineKeyboardButton("🔔 手動降價通知", callback_data='manual_check_notify_only')], # 修改名稱更清晰
        [InlineKeyboardButton("📊 手動價格總覽", callback_data='check_all_prices')], # 修改名稱更清晰
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard(callback_data_on_cancel: str = 'main_menu'):
    keyboard = [[InlineKeyboardButton("🚫 取消操作", callback_data=callback_data_on_cancel)]]
    return InlineKeyboardMarkup(keyboard)