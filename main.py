import requests
from bs4 import BeautifulSoup
import re
import asyncio
import os
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup # 新增 InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler # 新增 CallbackQueryHandler
from keep_alive import keep_alive
import nest_asyncio

# 讀取環境變數
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") # 注意：如果要做成多用戶，CHAT_ID 的使用方式需要調整
PRODUCT_FILE = "product.txt"

# --- (read_products_from_file, write_products_to_file, get_product_price, send_telegram_notification 函數保持不變) ---
# 讀取商品清單
def read_products_from_file(filepath=PRODUCT_FILE):
    products = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    url, price = line.split()
                    products.append((url, int(price)))
    except Exception as e:
        print(f"❌ 無法讀取商品資料檔案: {e}")
    return products

# 寫入商品清單
def write_products_to_file(products, filepath=PRODUCT_FILE):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            for url, price in products:
                f.write(f"{url} {price}\n")
        return True
    except Exception as e:
        print(f"❌ 無法寫入商品資料檔案: {e}")
        return False

# 取得商品價格
def get_product_price(product_url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
        response = requests.get(product_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # PChome
        if "pchome.com.tw" in product_url:
            match = re.search(r'"Price":\s?(\d+)', response.text)
            if match:
                return int(match.group(1))

        # momo
        elif "momoshop.com.tw" in product_url:
            match = re.search(r'\"sellPrice\":\s*\"?(\d+)', response.text)
            if match:
                return int(match.group(1))

        # Shopee
        elif "shopee.tw" in product_url:
            # 蝦皮的價格有時在 script tag 中的 JSON，有時在 meta tag
            # 嘗試從 JSON 找 (通常是主要的 API 返回)
            script_tags = soup.find_all('script', type='application/ld+json')
            for tag in script_tags:
                try:
                    json_data = json.loads(tag.string)
                    if isinstance(json_data, list): # 有些頁面是 list of dict
                        for item_data in json_data:
                            if item_data.get('@type') == 'Product' and 'offers' in item_data:
                                if isinstance(item_data['offers'], list) and item_data['offers']:
                                    offer = item_data['offers'][0]
                                elif isinstance(item_data['offers'], dict): # 有時 offer 直接是 dict
                                    offer = item_data['offers']
                                else:
                                    continue

                                if offer.get('@type') == 'Offer' and 'price' in offer:
                                    return int(float(offer['price']))
                    elif json_data.get('@type') == 'Product' and 'offers' in json_data:
                        if isinstance(json_data['offers'], list) and json_data['offers']:
                            offer = json_data['offers'][0]
                        elif isinstance(json_data['offers'], dict):
                            offer = json_data['offers']
                        else:
                            continue
                        if offer.get('@type') == 'Offer' and 'price' in offer:
                             return int(float(offer['price']))
                except json.JSONDecodeError:
                    continue #忽略無法解析的json

            # 如果上面沒找到，嘗試從另一個常見的 JSON 結構 (API v4 item)
            # 這個結構比較複雜，且蝦皮經常變動，以下為一個簡化嘗試
            match = re.search(r'\"price\":\s*(\d+)', response.text) # 原始的正則
            if match:
                 # 蝦皮 API 返回的價格通常是實際價格的 100000 倍 (帶有5個0的小數)
                 # 但有些情況下，如果直接抓取頁面渲染的價格，可能已經是正確的了
                 # 需要根據實際情況調整，這裡假設仍然是需要除以100000的情況
                 price_val = int(match.group(1))
                 if price_val > 10000000: # 一個簡單的判斷，如果價格非常大，可能是帶小數的版本
                     return price_val // 100000
                 else: # 否則可能直接是整數價格 (例如某些活動頁面)
                     return price_val


        # fallback：找常見價格字樣
        price_elements = soup.find_all(['span', 'div'], class_=re.compile(r'price|amount|sale|current|Price', re.I))
        for element in price_elements:
            text = element.get_text(strip=True)
            # 嘗試移除 "NT$", "$", "售價", "優惠價", "元" 等非數字部分
            text = re.sub(r'[NT$\s元售價優惠價特價,]', '', text, flags=re.I)
            price_match = re.search(r'\d[\d]*', text) # 移除了逗號的匹配
            if price_match:
                price = int(price_match.group())
                if price > 50 and price < 5000000: # 避免抓到庫存數量等其他數字，設定一個較合理的價格範圍
                    return price
        
        print(f"ℹ️ Fallback: 無法從特定規則或通用規則找到價格 for {product_url}")
        return None
    except requests.exceptions.Timeout:
        print(f"❌ 請求超時: {product_url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ 請求錯誤: {e}")
        return None
    except Exception as e:
        print(f"❌ 無法取得價格 ({product_url}): {e}")
        return None

# 發送 Telegram 通知
async def send_telegram_notification(bot: Bot, chat_id_to_send: str, product_url, price, target_price): # 修改: 傳入 bot 和 chat_id
    try:
        message = f"""🚨 價格警報！
目前價格：${price:,}
已低於目標價格 ${target_price:,}
商品連結：{product_url}"""
        await bot.send_message(chat_id=chat_id_to_send, text=message) # 修改: 使用傳入的 bot 和 chat_id
        print(f"✅ 已發送 Telegram 通知至 {chat_id_to_send}")
    except Exception as e:
        print(f"❌ 發送通知錯誤: {e}")

# --- Telegram 指令與按鈕回調處理 ---

# 主選單
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📋 查看追蹤清單", callback_data='list_products')],
        [InlineKeyboardButton("➕ 新增追蹤商品", callback_data='add_product_start')],
        [InlineKeyboardButton("🔔 手動通知檢查", callback_data='manual_check')],
        [InlineKeyboardButton("📊 手動價格總覽", callback_data='check_all')],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = f"👋 你好 {user.first_name}！\n🛒 這是你的個人價格監控機器人。\n\n請選擇操作："
    await update.message.reply_text(message, reply_markup=get_main_menu_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """🛒 價格監控機器人 - 可用操作：

你可以透過下方按鈕或輸入指令來操作：

/start - 顯示主選單
/list - 查看追蹤商品清單
/add [網址] [目標價格] - 新增追蹤商品
/delete [編號] - 刪除追蹤商品 (建議使用清單中的按鈕)
/update [編號] [新目標價格] - 修改目標價格 (建議使用清單中的按鈕)
/check - 手動檢查所有商品價格並顯示總覽
/manual - 手動檢查並僅通知低於目標價格的商品
/help - 顯示此幫助訊息

範例 (指令)：
/add https://24h.pchome.com.tw/prod/xxxxxxxxxxx 1400
/delete 1
/update 2 1500
"""
    await update.message.reply_text(help_text, reply_markup=get_main_menu_keyboard())


async def list_products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # 重要：回應 Telegram 已收到回調

    products = read_products_from_file()
    if not products:
        await query.edit_message_text(text="📝 目前沒有追蹤任何商品", reply_markup=get_main_menu_keyboard())
        return

    message_text = "📋 追蹤商品清單：\n\n"
    keyboard_buttons = []
    for i, (url, target_price) in enumerate(products, 1):
        display_url = url.split('/')[-1][:30] + "..." if len(url.split('/')[-1]) > 30 else url.split('/')[-1]
        message_text += f"{i}. {display_url}\n    🎯目標：${target_price:,}\n"
        keyboard_buttons.append([
            InlineKeyboardButton(f"✏️ {i}.改價", callback_data=f'edit_price_start:{i-1}'),
            InlineKeyboardButton(f"🗑️ {i}.刪除", callback_data=f'delete_product:{i-1}')
        ])
    keyboard_buttons.append([InlineKeyboardButton("返回主選單", callback_data='main_menu')])
    
    # 確保訊息長度不超過 Telegram 限制
    if len(message_text) > 4000: # Telegram 訊息長度上限約 4096
        message_text = message_text[:4000] + "\n... (列表過長，僅顯示部分)"

    await query.edit_message_text(text=message_text, reply_markup=InlineKeyboardMarkup(keyboard_buttons))

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # 純指令版本，供直接輸入
    products = read_products_from_file()
    if not products:
        await update.message.reply_text("📝 目前沒有追蹤任何商品", reply_markup=get_main_menu_keyboard())
        return

    message = "📋 追蹤商品清單 (指令模式)：\n\n"
    for i, (url, target_price) in enumerate(products, 1):
        display_url = url.split('/')[-1] if '/' in url else url
        message += f"{i}. {display_url}\n    目標價格：${target_price:,}\n\n"
    message += "\n💡提示：你可以使用 /delete [編號] 或 /update [編號] [價格] 來管理，或使用按鈕操作。"
    await update.message.reply_text(message, reply_markup=get_main_menu_keyboard())


async def manual_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(text="🔔 開始手動價格通知檢查...", show_alert=False)

    products = read_products_from_file()
    if not products:
        await query.message.reply_text("📝 目前沒有追蹤任何商品")
        return

    found_any = False
    # 使用 query.message.chat_id 確保是同一個使用者的聊天室
    chat_id_to_notify = str(query.message.chat_id) if query.message else CHAT_ID

    for url, target_price in products:
        price = get_product_price(url)
        if price is not None and price <= target_price:
            await send_telegram_notification(context.bot, chat_id_to_notify, url, price, target_price)
            found_any = True
        await asyncio.sleep(0.5) # 避免請求過快

    if not found_any:
        await query.message.reply_text("📈 目前沒有低於目標價格的商品")
    else:
        await query.message.reply_text("✅ 手動通知檢查完成。")
    # 返回主選單
    await query.message.reply_text("請選擇操作:", reply_markup=get_main_menu_keyboard())


async def check_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(text="🔍 開始檢查所有價格...", show_alert=False)

    products = read_products_from_file()
    if not products:
        await query.message.reply_text("📝 目前沒有追蹤任何商品")
        return

    results = []
    found_low_price = False
    chat_id_to_notify = str(query.message.chat_id) if query.message else CHAT_ID

    for url, target_price in products:
        price = get_product_price(url)
        display_url = url.split('/')[-1][:20] + "..." if len(url.split('/')[-1]) > 20 else url.split('/')[-1]

        if price is not None:
            status_emoji = "🔥" if price <= target_price else "📈"
            status_text = "低於目標" if price <= target_price else "高於目標"
            results.append(f"{display_url}\n  現：${price:,} | 目：${target_price:,} {status_emoji} {status_text}")
            if price <= target_price:
                found_low_price = True
                # 在 check_all 中也發送通知
                await send_telegram_notification(context.bot, chat_id_to_notify, url, price, target_price)
        else:
            results.append(f"{display_url}\n  ❌ 無法取得價格")
        await asyncio.sleep(0.5) # 避免請求過快

    message = "📊 價格檢查結果：\n\n" + "\n\n".join(results)
    if len(message) > 4000:
        message = message[:4000] + "\n... (結果過長，僅顯示部分)"

    await query.message.reply_text(message)
    if not found_low_price and products: # 有商品但都沒低於目標價
        await query.message.reply_text("👍 所有追蹤商品目前價格均高於目標價。")
    elif not products: # 連商品都沒有
        pass # 上面已經處理
    # 返回主選單
    await query.message.reply_text("請選擇操作:", reply_markup=get_main_menu_keyboard())


async def add_product_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['action'] = 'awaiting_url' # 設定狀態
    await query.edit_message_text(text="請直接輸入或貼上【商品網址】：", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("取消新增", callback_data='main_menu')]]))

async def delete_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        # callback_data 格式是 'delete_product:index'
        index = int(query.data.split(':')[1])
        products = read_products_from_file()

        if 0 <= index < len(products):
            deleted_product = products.pop(index)
            if write_products_to_file(products):
                await query.edit_message_text(f"✅ 已刪除追蹤商品: {deleted_product[0][:50]}...", reply_markup=get_main_menu_keyboard()) # 顯示部分網址
            else:
                await query.edit_message_text("❌ 刪除失敗，無法寫入檔案。", reply_markup=get_main_menu_keyboard())
        else:
            await query.edit_message_text("❌ 編號錯誤，刪除失敗。", reply_markup=get_main_menu_keyboard())
    except (IndexError, ValueError) as e:
        print(f"刪除商品回調錯誤: {e}, data: {query.data}")
        await query.edit_message_text("❌ 處理刪除請求時發生錯誤。", reply_markup=get_main_menu_keyboard())


async def edit_price_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        index = int(query.data.split(':')[1])
        products = read_products_from_file()
        if 0 <= index < len(products):
            context.user_data['action'] = 'awaiting_new_price'
            context.user_data['product_index_for_edit'] = index
            url, old_price = products[index]
            display_url = url.split('/')[-1][:30] + "..." if len(url.split('/')[-1]) > 30 else url.split('/')[-1]
            await query.edit_message_text(
                text=f"準備更新商品：\n{display_url}\n目前目標價：${old_price:,}\n\n請輸入【新的目標價格】(純數字)：",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("取消更新", callback_data='list_products')]])
            )
        else:
            await query.edit_message_text("❌ 編號錯誤，無法開始更新。", reply_markup=get_main_menu_keyboard())
    except (IndexError, ValueError) as e:
        print(f"編輯價格回調錯誤: {e}, data: {query.data}")
        await query.edit_message_text("❌ 處理更新請求時發生錯誤。", reply_markup=get_main_menu_keyboard())

# --- 文字訊息處理 (用於新增商品、更新價格的後續步驟) ---
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_action = context.user_data.get('action')
    chat_id = update.message.chat_id # 確保操作的是同一個用戶

    if user_action == 'awaiting_url':
        url = update.message.text.strip()
        if not url.startswith('http'):
            await update.message.reply_text("❌ 請提供有效的網址（需以 http 或 https 開頭）。\n請重新輸入【商品網址】：",
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("取消新增", callback_data='main_menu')]]))
            return
        
        products = read_products_from_file()
        for existing_url, _ in products:
            if existing_url == url:
                await update.message.reply_text("❌ 此商品已在追蹤清單中。\n請重新輸入或選擇其他操作：", reply_markup=get_main_menu_keyboard())
                context.user_data.pop('action', None) # 清除狀態
                return

        context.user_data['new_product_url'] = url
        context.user_data['action'] = 'awaiting_target_price'
        await update.message.reply_text(f"商品網址：{url[:50]}...\n請輸入此商品的【目標價格】(純數字)：",
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("取消新增", callback_data='main_menu')]]))

    elif user_action == 'awaiting_target_price':
        try:
            target_price = int(update.message.text.strip())
            url = context.user_data.get('new_product_url')
            if not url: # 安全檢查
                await update.message.reply_text(" terjadi kesalahan, URL produk tidak ditemukan. Silakan mulai lagi.", reply_markup=get_main_menu_keyboard())
                context.user_data.clear()
                return

            products = read_products_from_file()
            products.append((url, target_price))
            if write_products_to_file(products):
                await update.message.reply_text(f"✅ 已新增追蹤商品\n網址：{url[:50]}...\n目標價格：${target_price:,}", reply_markup=get_main_menu_keyboard())
            else:
                await update.message.reply_text("❌ 新增失敗，無法寫入檔案。", reply_markup=get_main_menu_keyboard())
            context.user_data.clear() # 清除所有狀態
        except ValueError:
            await update.message.reply_text("❌ 價格必須是純數字。\n請重新輸入【目標價格】：",
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("取消新增", callback_data='main_menu')]]))
        except Exception as e:
            await update.message.reply_text(f"❌ 新增商品時發生未知錯誤: {e}", reply_markup=get_main_menu_keyboard())
            context.user_data.clear()


    elif user_action == 'awaiting_new_price':
        try:
            new_price = int(update.message.text.strip())
            index = context.user_data.get('product_index_for_edit')
            
            if index is None: # 安全檢查
                await update.message.reply_text("❌ 發生錯誤，未找到要更新的商品索引。請重試。", reply_markup=get_main_menu_keyboard())
                context.user_data.clear()
                return

            products = read_products_from_file()
            if 0 <= index < len(products):
                url, _ = products[index]
                products[index] = (url, new_price)
                if write_products_to_file(products):
                    await update.message.reply_text(f"✅ 已更新商品目標價格\n商品編號：{index+1}\n新目標價格：${new_price:,}", reply_markup=get_main_menu_keyboard())
                else:
                    await update.message.reply_text("❌ 更新失敗，無法寫入檔案。", reply_markup=get_main_menu_keyboard())
            else: # 索引在此期間失效
                await update.message.reply_text("❌ 商品索引已失效，更新失敗。", reply_markup=get_main_menu_keyboard())

            context.user_data.clear() # 清除狀態
        except ValueError:
            await update.message.reply_text("❌ 價格必須是純數字。\n請重新輸入【新的目標價格】：",
                                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("取消更新", callback_data='list_products')]]))
        except Exception as e:
            await update.message.reply_text(f"❌ 更新價格時發生未知錯誤: {e}", reply_markup=get_main_menu_keyboard())
            context.user_data.clear()

    else: # 非預期狀態下的文字訊息
        await update.message.reply_text("我不明白你的意思。請使用按鈕或指令操作。", reply_markup=get_main_menu_keyboard())


# --- 保留原有的指令式操作，作為備用或進階用戶使用 ---
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) != 2:
            await update.message.reply_text("❌ 格式錯誤\n正確格式：/add [網址] [目標價格]", reply_markup=get_main_menu_keyboard())
            return

        url = context.args[0]
        target_price = int(context.args[1])

        if not url.startswith('http'):
            await update.message.reply_text("❌ 請提供有效的網址（需以 http 或 https 開頭）", reply_markup=get_main_menu_keyboard())
            return

        products = read_products_from_file()
        for existing_url, _ in products:
            if existing_url == url:
                await update.message.reply_text("❌ 此商品已在追蹤清單中", reply_markup=get_main_menu_keyboard())
                return

        products.append((url, target_price))
        if write_products_to_file(products):
            await update.message.reply_text(f"✅ 已新增追蹤商品 (指令模式)\n網址：{url}\n目標價格：${target_price:,}", reply_markup=get_main_menu_keyboard())
        else:
            await update.message.reply_text("❌ 新增失敗，請稍後再試", reply_markup=get_main_menu_keyboard())
    except ValueError:
        await update.message.reply_text("❌ 價格必須是數字", reply_markup=get_main_menu_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ 新增失敗：{str(e)}", reply_markup=get_main_menu_keyboard())


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) != 1:
            await update.message.reply_text("❌ 格式錯誤\n正確格式：/delete [編號]", reply_markup=get_main_menu_keyboard())
            return

        index = int(context.args[0]) - 1
        products = read_products_from_file()

        if not products:
            await update.message.reply_text("📝 目前沒有追蹤任何商品", reply_markup=get_main_menu_keyboard())
            return

        if index < 0 or index >= len(products):
            await update.message.reply_text(f"❌ 編號錯誤，請輸入 1 到 {len(products)} 之間的數字", reply_markup=get_main_menu_keyboard())
            return

        deleted_product = products.pop(index)

        if write_products_to_file(products):
            await update.message.reply_text(f"✅ 已刪除追蹤商品 (指令模式)\n網址：{deleted_product[0]}", reply_markup=get_main_menu_keyboard())
        else:
            await update.message.reply_text("❌ 刪除失敗，請稍後再試", reply_markup=get_main_menu_keyboard())
    except ValueError:
        await update.message.reply_text("❌ 編號必須是數字", reply_markup=get_main_menu_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ 刪除失敗：{str(e)}", reply_markup=get_main_menu_keyboard())

async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) != 2:
            await update.message.reply_text("❌ 格式錯誤\n正確格式：/update [編號] [新目標價格]", reply_markup=get_main_menu_keyboard())
            return

        index = int(context.args[0]) - 1
        new_price = int(context.args[1])

        products = read_products_from_file()
        if not products:
            await update.message.reply_text("📝 目前沒有追蹤任何商品", reply_markup=get_main_menu_keyboard())
            return

        if index < 0 or index >= len(products):
            await update.message.reply_text(f"❌ 編號錯誤，請輸入 1 到 {len(products)} 之間的數字", reply_markup=get_main_menu_keyboard())
            return

        url, _ = products[index]
        products[index] = (url, new_price)

        if write_products_to_file(products):
            await update.message.reply_text(f"✅ 已更新商品目標價格 (指令模式)\n商品編號：{index+1}\n新目標價格：${new_price:,}", reply_markup=get_main_menu_keyboard())
        else:
            await update.message.reply_text("❌ 更新失敗，請稍後再試", reply_markup=get_main_menu_keyboard())
    except ValueError:
        await update.message.reply_text("❌ 編號和價格必須是數字", reply_markup=get_main_menu_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ 更新失敗：{str(e)}", reply_markup=get_main_menu_keyboard())


async def manual_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # 純指令版本
    await update.message.reply_text("🔔 開始手動價格通知檢查 (指令模式)...")
    products = read_products_from_file()
    if not products:
        await update.message.reply_text("📝 目前沒有追蹤任何商品", reply_markup=get_main_menu_keyboard())
        return

    found_any = False
    chat_id_to_notify = str(update.message.chat_id) # 指令模式下用當前聊天室ID
    for url, target_price in products:
        price = get_product_price(url)
        if price is not None and price <= target_price:
            await send_telegram_notification(context.bot, chat_id_to_notify, url, price, target_price)
            found_any = True
        await asyncio.sleep(0.5)

    if not found_any:
        await update.message.reply_text("📈 目前沒有低於目標價格的商品", reply_markup=get_main_menu_keyboard())
    else:
        await update.message.reply_text("✅ 手動通知檢查完成。", reply_markup=get_main_menu_keyboard())


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # 純指令版本
    await update.message.reply_text("🔍 開始檢查價格 (指令模式)...")
    products = read_products_from_file()
    if not products:
        await update.message.reply_text("📝 目前沒有追蹤任何商品", reply_markup=get_main_menu_keyboard())
        return

    results = []
    found_low_price = False
    chat_id_to_notify = str(update.message.chat_id)
    for url, target_price in products:
        price = get_product_price(url)
        display_url = url.split('/')[-1] if '/' in url else url

        if price is not None:
            status = "🔥 低於目標" if price <= target_price else "📈 高於目標"
            results.append(f"{display_url}\n    目前：${price:,} | 目標：${target_price:,} {status}")
            if price <= target_price:
                found_low_price = True
                await send_telegram_notification(context.bot, chat_id_to_notify, url, price, target_price)
        else:
            results.append(f"{display_url}\n    ❌ 無法取得價格")
        await asyncio.sleep(0.5)

    message = "📊 價格檢查結果：\n\n" + "\n\n".join(results)
    await update.message.reply_text(message, reply_markup=get_main_menu_keyboard())
    if not found_low_price and products:
         await update.message.reply_text("👍 所有追蹤商品目前價格均高於目標價。", reply_markup=get_main_menu_keyboard())


# 定期檢查價格背景任務
async def check_prices_task(application: Application): # 修改: 傳入 application 以便取得 bot
    bot = application.bot
    # 注意：這個背景任務的通知對象目前是固定的 CHAT_ID
    # 如果要做成多用戶，這裡需要遍歷所有儲存的用戶 chat_id
    # 且 product.txt 也需要按用戶區分，這會是個大改動
    # 目前假設是單一用戶使用，通知到環境變數的 CHAT_ID
    global_chat_id = CHAT_ID 
    if not global_chat_id:
        print("⚠️ 環境變數 TELEGRAM_CHAT_ID 未設定，定期檢查任務的通知將無法發送。")
        # return # 可以選擇在這裡直接返回，如果 CHAT_ID 是必須的

    while True:
        try:
            print("週期任務：🔍 開始定期檢查價格")
            products = read_products_from_file() # 假設 product.txt 是共用的

            if not products:
                print("週期任務：📝 目前沒有追蹤任何商品可供定期檢查。")
            else:
                notified_in_this_run = False
                for url, target_price in products:
                    price = get_product_price(url)
                    if price is not None:
                        print(f"週期任務：商品 {url[:30]}... 目前價格：${price:,}，目標：${target_price:,}")
                        if price <= target_price:
                            if global_chat_id: # 只有設定了全局 CHAT_ID 才發送
                                await send_telegram_notification(bot, global_chat_id, url, price, target_price)
                                notified_in_this_run = True
                            else:
                                print(f"週期任務：商品 {url[:30]}... 低於目標價，但未設定全局 CHAT_ID，無法發送通知。")
                    else:
                        print(f"週期任務：商品 {url[:30]}... 無法取得價格")
                    await asyncio.sleep(1) # 每次查詢間隔1秒
                
                if notified_in_this_run:
                    print("週期任務：✅ 定期價格檢查完成，已發送部分通知。")
                elif products: # 有商品但都沒發通知
                    print("週期任務：📈 定期價格檢查完成，所有商品均未達到通知條件。")


            await asyncio.sleep(900)  # 900秒 = 15 分鐘
        except Exception as e:
            print(f"❌ 定期檢查任務發生錯誤: {e}")
            await asyncio.sleep(300)  # 出錯時 5 分鐘後重試

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # 必須先 answer callback query
    # await query.answer() # 在各自的處理函數中 answer

    if data == 'list_products':
        await list_products_callback(update, context)
    elif data == 'add_product_start':
        await add_product_start_callback(update, context)
    elif data == 'manual_check':
        await manual_check_callback(update, context)
    elif data == 'check_all':
        await check_all_callback(update, context)
    elif data.startswith('delete_product:'):
        await delete_product_callback(update, context)
    elif data.startswith('edit_price_start:'):
        await edit_price_start_callback(update, context)
    elif data == 'main_menu':
        await query.answer()
        await query.edit_message_text("請選擇操作：", reply_markup=get_main_menu_keyboard())
    else:
        await query.answer(text="未知操作", show_alert=True)


# 主程序
async def main_async():
    if not TELEGRAM_TOKEN: # CHAT_ID 現在主要用於背景任務的預設通知
        print("❌ 請設定 TELEGRAM_TOKEN 環境變數")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # 指令處理器
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_command)) # 保留指令版本
    application.add_handler(CommandHandler("add", add_command)) # 保留指令版本
    application.add_handler(CommandHandler("delete", delete_command)) # 保留指令版本
    application.add_handler(CommandHandler("update", update_command)) # 保留指令版本
    application.add_handler(CommandHandler("check", check_command)) # 保留指令版本
    application.add_handler(CommandHandler("manual", manual_command)) # 保留指令版本

    # 按鈕回調處理器
    application.add_handler(CallbackQueryHandler(button_callback_handler))

    # 文字訊息處理器 (用於接收 URL 和價格)
    # 確保這個 Handler 在 CommandHandler 和 CallbackQueryHandler 之後，
    # 並且只處理非指令的文字訊息以及在特定 user_data['action'] 狀態下的訊息。
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    print("🤖 Telegram 機器人已啟動")

    # 將 application 傳遞給背景任務，以便它能使用 bot 對象
    asyncio.create_task(check_prices_task(application))

    await application.run_polling()

if __name__ == "__main__":
    nest_asyncio.apply()
    keep_alive() # 如果你在 Replit 上運行，需要這個
    asyncio.run(main_async())
