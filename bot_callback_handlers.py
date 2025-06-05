# bot_callback_handlers.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from product_manager import read_products_from_file, write_products_to_file
from telegram_utils import get_main_menu_keyboard, send_telegram_notification, get_cancel_keyboard
from price_checker import get_product_price
import asyncio # 用於檢查時的 sleep

# --- Callback Handlers for buttons ---

async def list_products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    if query: # 如果是按鈕觸發
      await query.answer()

    products = read_products_from_file()
    if not products:
        text = "📝 目前沒有追蹤任何商品。"
        reply_markup = get_main_menu_keyboard()
        if query: await query.edit_message_text(text=text, reply_markup=reply_markup)
        else: await update.effective_message.reply_text(text=text, reply_markup=reply_markup) # e.g. from a text command
        return

    items_per_page = 5 # 每頁顯示5個商品
    start_index = page * items_per_page
    end_index = start_index + items_per_page
    current_page_products = products[start_index:end_index]

    if not current_page_products and page > 0: # 如果請求的頁面超出範圍但不是第一頁，則顯示最後一頁
        page = (len(products) -1) // items_per_page
        start_index = page * items_per_page
        end_index = start_index + items_per_page
        current_page_products = products[start_index:end_index]
        
    message_text = f"📋 **追蹤商品清單 (第 {page + 1} / {(len(products) - 1) // items_per_page + 1} 頁)**：\n\n"
    keyboard_buttons = []

    for i_global, (url, target_price) in enumerate(current_page_products, start=start_index):
        # 簡化 URL 顯示
        url_display = url.split('?')[0].split('/')[-1][:30] # 取路徑的最後一部分，並移除查詢參數
        if not url_display or len(url_display) < 5: url_display = url[:30] + "..."

        message_text += f"**{i_global + 1}.** {url_display}\n    🎯目標：`${target_price:,}`\n    🔗[原始連結]({url})\n\n"
        keyboard_buttons.append([
            InlineKeyboardButton(f"✏️ {i_global + 1}.改價", callback_data=f'edit_price_start:{i_global}'),
            InlineKeyboardButton(f"🗑️ {i_global + 1}.刪除", callback_data=f'delete_product:{i_global}')
        ])
    
    # 分頁按鈕
    pagination_buttons = []
    if page > 0:
        pagination_buttons.append(InlineKeyboardButton("⬅️ 上一頁", callback_data=f'list_page:{page-1}'))
    if end_index < len(products):
        pagination_buttons.append(InlineKeyboardButton("下一頁 ➡️", callback_data=f'list_page:{page+1}'))
    
    if pagination_buttons:
        keyboard_buttons.append(pagination_buttons)

    keyboard_buttons.append([InlineKeyboardButton("返回主選單", callback_data='main_menu')])
    
    reply_markup = InlineKeyboardMarkup(keyboard_buttons)

    if query:
        await query.edit_message_text(text=message_text, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)
    elif update.effective_message: # 若由指令觸發 (無 query)
        await update.effective_message.reply_text(text=message_text, reply_markup=reply_markup, parse_mode='Markdown', disable_web_page_preview=True)


async def check_all_prices_callback(update: Update, context: ContextTypes.DEFAULT_TYPE): # 原 check_all_callback
    query = update.callback_query
    await query.answer(text="📊 開始手動價格總覽...", show_alert=False)
    await query.edit_message_text(text="📊 處理中：正在獲取所有商品的目前價格...", reply_markup=None) # 移除按鈕

    products = read_products_from_file()
    if not products:
        await query.message.reply_text("📝 目前沒有追蹤任何商品。", reply_markup=get_main_menu_keyboard())
        return

    results_header = "📊 **價格總覽結果**：\n\n"
    results_body = []
    any_price_found = False
    notified_on_low_price = False
    chat_id_to_notify = str(query.message.chat_id)

    for i, (url, target_price) in enumerate(products):
        # Optional: Send progress update
        if i % 5 == 0 and i > 0:
            await query.message.reply_text(f"總覽進度：{i}/{len(products)}...")

        price = get_product_price(url)
        url_display = url.split('?')[0].split('/')[-1][:30] + "..." if len(url.split('?')[0].split('/')[-1]) > 30 else url.split('?')[0].split('/')[-1]
        if not url_display: url_display = url[:30]+"..."

        if price is not None:
            any_price_found = True
            status_emoji = "🔥" if price <= target_price else "📈"
            status_text = "低於目標" if price <= target_price else "高於目標"
            results_body.append(f"**{i+1}. {url_display}**\n  🏷️目前：`${price:,}` | 🎯目標：`${target_price:,}` {status_emoji}*{status_text}*")
            if price <= target_price:
                notified_on_low_price = True
                await send_telegram_notification(context.bot, chat_id_to_notify, url, price, target_price)
        else:
            results_body.append(f"**{i+1}. {url_display}**\n  ❌ 無法取得價格")
        await asyncio.sleep(1)

    final_message_text = results_header + "\n\n".join(results_body)
    if not any_price_found and products:
        final_message_text = "⚠️ 所有商品均無法取得目前價格。"
    elif not products: # Should have been caught earlier
        final_message_text = "📝 目前沒有追蹤任何商品可供檢查。"
    
    # Handle message length limit for Telegram
    if len(final_message_text) > 4096:
        await query.message.reply_text(results_header + "您的商品列表結果過長，可能無法完整顯示。請考慮減少追蹤商品數量或分批檢查。", reply_markup=get_main_menu_keyboard(), parse_mode='Markdown')
    else:
        await query.message.reply_text(final_message_text, reply_markup=get_main_menu_keyboard(), parse_mode='Markdown')

    if notified_on_low_price:
        await query.message.reply_text("ℹ️ 部分商品價格已達標並已發送通知。", reply_markup=get_main_menu_keyboard())
    elif products and any_price_found:
        await query.message.reply_text("👍 所有可查詢到價格的商品目前均未低於目標價。", reply_markup=get_main_menu_keyboard())


async def add_product_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['action'] = 'awaiting_url' # 設定狀態
    context.user_data['chat_id_for_add'] = query.message.chat_id # 儲存發起者的 chat_id
    await query.edit_message_text(
        text="請直接【輸入或貼上商品網址】進行追蹤：",
        reply_markup=get_cancel_keyboard(callback_data_on_cancel='main_menu')
    )

async def delete_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Acknowledge callback
    
    try:
        # callback_data 格式是 'delete_product:index'
        product_index_to_delete = int(query.data.split(':')[1])
        products = read_products_from_file()

        if 0 <= product_index_to_delete < len(products):
            deleted_product_url, _ = products.pop(product_index_to_delete)
            if write_products_to_file(products):
                await query.edit_message_text(
                    f"✅ 已成功刪除追蹤商品: \n`{deleted_product_url[:70]}...`",
                    parse_mode='Markdown'
                )
                # 自動刷新列表到第一頁或留在當前頁面 (如果能獲取)
                # 為簡單起見，先返回主選單，讓使用者重新點擊列表
                await query.message.reply_text("請選擇下一步操作：", reply_markup=get_main_menu_keyboard())

            else:
                await query.edit_message_text("❌ 刪除失敗！無法寫入商品資料檔案。", reply_markup=get_main_menu_keyboard())
        else:
            await query.edit_message_text("❌ 編號錯誤！您嘗試刪除的商品可能已被修改或不存在。", reply_markup=get_main_menu_keyboard())
    except (IndexError, ValueError) as e:
        print(f"處理刪除商品回調時發生錯誤: {e}, data: {query.data}")
        await query.edit_message_text("❌ 處理您的刪除請求時發生內部錯誤，請稍後再試。", reply_markup=get_main_menu_keyboard())


async def edit_price_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        product_index_to_edit = int(query.data.split(':')[1])
        products = read_products_from_file()

        if 0 <= product_index_to_edit < len(products):
            # 設定狀態，準備接收使用者輸入的新價格
            context.user_data['action'] = 'awaiting_new_price'
            context.user_data['product_index_for_edit'] = product_index_to_edit
            context.user_data['chat_id_for_edit'] = query.message.chat_id


            url, old_price = products[product_index_to_edit]
            url_display = url.split('?')[0].split('/')[-1][:30] + "..." if len(url.split('?')[0].split('/')[-1]) > 30 else url.split('?')[0].split('/')[-1]
            if not url_display: url_display = url[:30]+"..."

            await query.edit_message_text(
                text=f"準備更新商品：\n`{url_display}`\n目前目標價：`${old_price:,}`\n\n"
                     "請直接輸入【新的目標價格】(純數字)：",
                parse_mode='Markdown',
                reply_markup=get_cancel_keyboard(callback_data_on_cancel='list_products') # 取消則返回列表
            )
        else:
            await query.edit_message_text("❌ 編號錯誤！您嘗試編輯的商品可能已被修改或不存在。", reply_markup=get_main_menu_keyboard())
    except (IndexError, ValueError) as e:
        print(f"處理編輯價格回調時發生錯誤: {e}, data: {query.data}")
        await query.edit_message_text("❌ 處理您的編輯請求時發生內部錯誤，請稍後再試。", reply_markup=get_main_menu_keyboard())

# --- Main Callback Router ---
async def main_button_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # query.answer() is called within specific handlers to allow for custom responses (e.g. alerts)
    
    data = query.data.split(':')[0] # Get action part, e.g. 'list_page' from 'list_page:1'

    if data == 'list_products':
        await list_products_callback(update, context, page=0)
    elif data == 'list_page':
        page = int(query.data.split(':')[1])
        await list_products_callback(update, context, page=page)
    elif data == 'add_product_start':
        await add_product_start_callback(update, context)
    elif data == 'manual_check_notify_only': # Renamed
        await manual_check_notify_only_callback(update, context)
    elif data == 'check_all_prices': # Renamed
        await check_all_prices_callback(update, context)
    elif data == 'delete_product':
        await delete_product_callback(update, context)
    elif data == 'edit_price_start':
        await edit_price_start_callback(update, context)
    elif data == 'main_menu':
        await query.answer()
        await query.edit_message_text("請選擇操作：", reply_markup=get_main_menu_keyboard())
    else:
        await query.answer(text="未知操作或操作已過期。", show_alert=True)
