# bot_command_handlers.py
from telegram import Update
from telegram.ext import ContextTypes

from product_manager import read_products_from_file, write_products_to_file
from telegram_utils import get_main_menu_keyboard, send_telegram_notification
from price_checker import get_product_price
import asyncio # 用於 manual_command 和 check_command 的 sleep

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = f"👋 你好 {user.first_name}！\n🛒 這是你的個人價格監控機器人。\n\n請選擇操作："
    await update.message.reply_text(message, reply_markup=get_main_menu_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """📖 **價格監控機器人 - 使用說明** 📖

您可以透過下方的按鈕或輸入對應的文字指令來操作機器人。

🤖 **主要功能按鈕** (建議使用)：
* `📋 查看追蹤清單`: 列出所有追蹤的商品，並提供單獨管理按鈕。
* `➕ 新增追蹤商品`: 引導您新增想要追蹤的商品網址和目標價格。
* `🔔 手動降價通知`: 立即檢查所有商品，僅對價格低於目標的商品發送通知。
* `📊 手動價格總覽`: 立即檢查所有商品，並回報所有商品的目前價格與狀態。

⌨️ **文字指令** (可作為備用)：
* `/start` - 顯示主選單與歡迎訊息。
* `/help` - 顯示此幫助訊息。
* `/list` - (同按鈕) 查看追蹤商品清單。
* `/add [網址] [目標價格]` - 快速新增商品。
    * 範例: `/add https://shopee.tw/product/12345/67890 1500`
* `/delete [編號]` - 刪除清單中指定編號的商品 (編號從 /list 取得)。
    * 範例: `/delete 1`
* `/update [編號] [新目標價格]` - 修改指定商品的目標價格。
    * 範例: `/update 1 1400`
* `/check` - (同「手動價格總覽」按鈕) 手動檢查所有商品價格並顯示總覽。
* `/manual` - (同「手動降價通知」按鈕) 手動檢查並僅通知低於目標價格的商品。

💡 **提示**:
* 新增商品時，請確保提供完整的商品網址。
* 目標價格請輸入純數字。
* 機器人會定期在背景自動檢查價格。

如果您在使用上遇到任何問題，可以嘗試使用 `/start` 重置到主選單。
"""
    await update.message.reply_text(help_text, reply_markup=get_main_menu_keyboard(), parse_mode='Markdown')


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = read_products_from_file()
    if not products:
        await update.message.reply_text("📝 目前沒有追蹤任何商品。", reply_markup=get_main_menu_keyboard())
        return

    message = "📋 **追蹤商品清單 (指令模式)**：\n\n"
    for i, (url, target_price) in enumerate(products, 1):
        # 嘗試從 URL 中提取一個較短的標識符，例如最後一部分
        url_display = url.split('?')[0].split('/')[-1] # 取路徑的最後一部分，並移除查詢參數
        if not url_display or len(url_display) < 5 : # 如果最後一部分太短或不存在
            try:
                # 嘗試取域名之後的兩段路徑
                path_parts = url.split('//', 1)[1].split('/', 2)
                if len(path_parts) > 2:
                    url_display = f"{path_parts[1]}/{path_parts[2][:20]}"
                elif len(path_parts) > 1:
                     url_display = path_parts[1][:30]
                else:
                    url_display = url[:40] # 最差情況，取 URL 前缀
            except IndexError:
                 url_display = url[:40] # 出錯時的備援

        message += f"**{i}.** {url_display}...\n    🎯目標價：${target_price:,}\n    🔗[原始連結]({url})\n\n"
    
    message += "\n💡提示：您可以使用 `/delete [編號]` 或 `/update [編號] [價格]` 來管理，或透過主選單按鈕操作更方便。"
    
    # Telegram Markdown 訊息長度限制約 4096 字元
    if len(message) > 4000:
        await update.message.reply_text("📋 **追蹤商品清單 (指令模式)**：\n\n您的商品列表過長，請使用按鈕介面分頁查看，或精簡您的追蹤列表。", reply_markup=get_main_menu_keyboard())
    else:
        await update.message.reply_text(message, parse_mode='Markdown', disable_web_page_preview=True, reply_markup=get_main_menu_keyboard())


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args is None or len(context.args) != 2:
        await update.message.reply_text(
            "❌ 格式錯誤！\n正確格式：`/add [網址] [目標價格]`\n範例：`/add https://example.com/item 1000`",
            reply_markup=get_main_menu_keyboard()
        )
        return

    url = context.args[0].strip()
    try:
        target_price_str = context.args[1].strip()
        target_price = int(target_price_str)
        if target_price <= 0:
            raise ValueError("價格必須是正數")
    except ValueError:
        await update.message.reply_text("❌ 價格錯誤！目標價格必須是有效的正整數。", reply_markup=get_main_menu_keyboard())
        return

    if not (url.startswith('http://') or url.startswith('https://')):
        await update.message.reply_text("❌ 網址錯誤！請提供以 `http://` 或 `https://` 開頭的有效網址。", reply_markup=get_main_menu_keyboard())
        return

    products = read_products_from_file()
    if any(existing_url == url for existing_url, _ in products):
        await update.message.reply_text("❌ 新增失敗！此商品已存在於追蹤清單中。", reply_markup=get_main_menu_keyboard())
        return

    products.append((url, target_price))
    if write_products_to_file(products):
        await update.message.reply_text(f"✅ 已新增追蹤商品 (指令模式):\n網址：{url}\n目標價格：${target_price:,}", reply_markup=get_main_menu_keyboard())
    else:
        await update.message.reply_text("❌ 新增失敗！無法寫入商品資料檔案，請檢查後台日誌。", reply_markup=get_main_menu_keyboard())


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args is None or len(context.args) != 1:
        await update.message.reply_text("❌ 格式錯誤！\n正確格式：`/delete [編號]`\n請先使用 `/list` 查看商品編號。", reply_markup=get_main_menu_keyboard())
        return

    try:
        item_number_str = context.args[0].strip()
        item_number = int(item_number_str)
        if item_number <= 0:
            raise ValueError("編號必須是正數")
    except ValueError:
        await update.message.reply_text("❌ 編號錯誤！請提供有效的商品編號 (正整數)。", reply_markup=get_main_menu_keyboard())
        return

    products = read_products_from_file()
    index_to_delete = item_number - 1

    if not products:
        await update.message.reply_text("📝 目前沒有追蹤任何商品可供刪除。", reply_markup=get_main_menu_keyboard())
        return

    if 0 <= index_to_delete < len(products):
        deleted_product_url, _ = products.pop(index_to_delete)
        if write_products_to_file(products):
            await update.message.reply_text(f"✅ 已刪除追蹤商品 (指令模式):\n{deleted_product_url}", reply_markup=get_main_menu_keyboard())
        else:
            await update.message.reply_text("❌ 刪除失敗！無法寫入商品資料檔案。", reply_markup=get_main_menu_keyboard())
    else:
        await update.message.reply_text(f"❌ 編號錯誤！找不到編號為 {item_number} 的商品。有效編號範圍為 1 到 {len(products)}。", reply_markup=get_main_menu_keyboard())


async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args is None or len(context.args) != 2:
        await update.message.reply_text(
            "❌ 格式錯誤！\n正確格式：`/update [編號] [新目標價格]`\n請先使用 `/list` 查看商品編號。\n範例：`/update 1 900`",
            reply_markup=get_main_menu_keyboard()
        )
        return

    try:
        item_number_str = context.args[0].strip()
        item_number = int(item_number_str)
        if item_number <= 0:
            raise ValueError("編號必須是正數")

        new_price_str = context.args[1].strip()
        new_target_price = int(new_price_str)
        if new_target_price <= 0:
            raise ValueError("價格必須是正數")
            
    except ValueError:
        await update.message.reply_text("❌ 輸入錯誤！編號和價格都必須是有效的正整數。", reply_markup=get_main_menu_keyboard())
        return

    products = read_products_from_file()
    index_to_update = item_number - 1

    if not products:
        await update.message.reply_text("📝 目前沒有追蹤任何商品可供更新。", reply_markup=get_main_menu_keyboard())
        return

    if 0 <= index_to_update < len(products):
        url, old_price = products[index_to_update]
        products[index_to_update] = (url, new_target_price)
        if write_products_to_file(products):
            await update.message.reply_text(
                f"✅ 已更新商品目標價格 (指令模式):\n商品編號：{item_number}\n舊目標價格：${old_price:,}\n新目標價格：${new_target_price:,}",
                reply_markup=get_main_menu_keyboard()
            )
        else:
            await update.message.reply_text("❌ 更新失敗！無法寫入商品資料檔案。", reply_markup=get_main_menu_keyboard())
    else:
        await update.message.reply_text(f"❌ 編號錯誤！找不到編號為 {item_number} 的商品。有效編號範圍為 1 到 {len(products)}。", reply_markup=get_main_menu_keyboard())


async def manual_check_notify_only_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # 原 manual_command
    await update.message.reply_text("🔔 開始手動降價通知檢查 (指令模式)...")
    products = read_products_from_file()
    if not products:
        await update.message.reply_text("📝 目前沒有追蹤任何商品。", reply_markup=get_main_menu_keyboard())
        return

    found_any_to_notify = False
    chat_id_to_notify = str(update.message.chat_id) # 指令模式下用當前聊天室ID
    
    processing_message = await update.message.reply_text("正在處理中，請稍候...")
    
    for i, (url, target_price) in enumerate(products):
        await processing_message.edit_text(f"正在檢查商品 {i+1}/{len(products)}...\n{url[:50]}...")
        price = get_product_price(url)
        if price is not None and price <= target_price:
            await send_telegram_notification(context.bot, chat_id_to_notify, url, price, target_price)
            found_any_to_notify = True
        await asyncio.sleep(1) # 避免請求過快

    if found_any_to_notify:
        await processing_message.edit_text("✅ 手動降價通知檢查完成，已發送相關通知。", reply_markup=get_main_menu_keyboard())
    else:
        await processing_message.edit_text("📈 本次檢查未發現價格低於目標的商品。", reply_markup=get_main_menu_keyboard())

async def check_all_prices_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # 原 check_command
    await update.message.reply_text("📊 開始手動價格總覽檢查 (指令模式)...")
    products = read_products_from_file()
    if not products:
        await update.message.reply_text("📝 目前沒有追蹤任何商品。", reply_markup=get_main_menu_keyboard())
        return

    results_header = "📊 **價格總覽結果**：\n\n"
    results_body = []
    any_price_found = False
    chat_id_to_notify = str(update.message.chat_id)
    
    processing_message = await update.message.reply_text("正在處理中，請稍候...")

    for i, (url, target_price) in enumerate(products):
        await processing_message.edit_text(f"正在檢查商品 {i+1}/{len(products)}...\n{url[:50]}...")
        price = get_product_price(url)
        # 簡化 URL 顯示
        url_display = url.split('?')[0].split('/')[-1][:30] + "..." if len(url.split('?')[0].split('/')[-1]) > 30 else url.split('?')[0].split('/')[-1]
        if not url_display: url_display = url[:30]+"..."


        if price is not None:
            any_price_found = True
            status_emoji = "🔥" if price <= target_price else "📈"
            status_text = "低於目標" if price <= target_price else "高於目標"
            results_body.append(f"**{i+1}. {url_display}**\n  🏷️目前：`${price:,}` | 🎯目標：`${target_price:,}` {status_emoji}*{status_text}*")
            if price <= target_price:
                 # 在總覽中也發送降價通知
                await send_telegram_notification(context.bot, chat_id_to_notify, url, price, target_price)
        else:
            results_body.append(f"**{i+1}. {url_display}**\n  ❌ 無法取得價格")
        await asyncio.sleep(1)

    if not any_price_found and products:
        final_message = "⚠️ 所有商品均無法取得目前價格。"
    elif not products:
        final_message = "📝 目前沒有追蹤任何商品。" # 理論上前面已攔截
    else:
        final_message = results_header + "\n\n".join(results_body)

    if len(final_message) > 4000: # Telegram Markdown 訊息長度限制
        await processing_message.edit_text(results_header + "您的商品列表結果過長，部分結果可能被截斷。", reply_markup=get_main_menu_keyboard())
        # 可以考慮分多條訊息發送，或提示用戶使用按鈕介面
    else:
        await processing_message.edit_text(final_message, parse_mode='Markdown', reply_markup=get_main_menu_keyboard())