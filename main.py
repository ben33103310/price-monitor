import requests
from bs4 import BeautifulSoup
import re
import asyncio
import os
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from keep_alive import keep_alive
import nest_asyncio
from telegram import ReplyKeyboardMarkup

# 讀取環境變數
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PRODUCT_FILE = "product.txt"

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
            match = re.search(r'\"price\":\s*(\d+)', response.text)
            if match:
                return int(match.group(1)) // 100000  # Shopee 價格是乘上 100000 的

        # fallback：找常見價格字樣
        price_elements = soup.find_all(['span', 'div'], class_=re.compile(r'price|amount|sale|current', re.I))
        for element in price_elements:
            text = element.get_text(strip=True)
            price_match = re.search(r'\d[\d,]*', text)
            if price_match:
                price = int(price_match.group().replace(",", ""))
                if price > 100:
                    return price

        return None
    except Exception as e:
        print(f"❌ 無法取得價格: {e}")
        return None
        
# 發送 Telegram 通知
async def send_telegram_notification(product_url, price, target_price):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        message = f"""🚨 價格警報！
目前價格：${price:,}
已低於目標價格 ${target_price:,}
商品連結：{product_url}"""
        await bot.send_message(chat_id=CHAT_ID, text=message)
        print("✅ 已發送 Telegram 通知")
    except Exception as e:
        print(f"❌ 發送通知錯誤: {e}")

# Telegram 指令處理

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = """🛒 價格監控機器人

可用指令：
/manual - 手動檢查並通知低於目標價格的商品
/list - 查看追蹤商品清單
/add [網址] [目標價格] - 新增追蹤商品
/delete [編號] - 刪除追蹤商品
/update [編號] [新目標價格] - 修改目標價格
/check - 手動檢查所有商品價格
/help - 顯示幫助訊息

範例：
/add https://24h.pchome.com.tw/prod/xxxxxxxxxxx 1400
/delete 1
/update 2 1500"""
    await update.message.reply_text(message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_command(update, context)

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = read_products_from_file()
    if not products:
        await update.message.reply_text("📝 目前沒有追蹤任何商品")
        return

    message = "📋 追蹤商品清單：\n\n"
    for i, (url, target_price) in enumerate(products, 1):
        display_url = url.split('/')[-1] if '/' in url else url
        message += f"{i}. {display_url}\n   目標價格：${target_price:,}\n\n"

    await update.message.reply_text(message)

async def manual_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔔 開始手動價格通知檢查...")

    products = read_products_from_file()
    if not products:
        await update.message.reply_text("📝 目前沒有追蹤任何商品")
        return

    found_any = False
    for url, target_price in products:
        price = get_product_price(url)
        if price is not None and price <= target_price:
            await send_telegram_notification(url, price, target_price)
            found_any = True

    if not found_any:
        await update.message.reply_text("📈 目前沒有低於目標價格的商品")

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) != 2:
            await update.message.reply_text("❌ 格式錯誤\n正確格式：/add [網址] [目標價格]")
            return

        url = context.args[0]
        target_price = int(context.args[1])

        if not url.startswith('http'):
            await update.message.reply_text("❌ 請提供有效的網址（需以 http 或 https 開頭）")
            return

        products = read_products_from_file()
        for existing_url, _ in products:
            if existing_url == url:
                await update.message.reply_text("❌ 此商品已在追蹤清單中")
                return

        products.append((url, target_price))
        if write_products_to_file(products):
            await update.message.reply_text(f"✅ 已新增追蹤商品\n網址：{url}\n目標價格：${target_price:,}")
        else:
            await update.message.reply_text("❌ 新增失敗，請稍後再試")
    except ValueError:
        await update.message.reply_text("❌ 價格必須是數字")
    except Exception as e:
        await update.message.reply_text(f"❌ 新增失敗：{str(e)}")

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) != 1:
            await update.message.reply_text("❌ 格式錯誤\n正確格式：/delete [編號]")
            return

        index = int(context.args[0]) - 1
        products = read_products_from_file()

        if not products:
            await update.message.reply_text("📝 目前沒有追蹤任何商品")
            return

        if index < 0 or index >= len(products):
            await update.message.reply_text(f"❌ 編號錯誤，請輸入 1 到 {len(products)} 之間的數字")
            return

        deleted_product = products.pop(index)

        if write_products_to_file(products):
            await update.message.reply_text(f"✅ 已刪除追蹤商品\n網址：{deleted_product[0]}")
        else:
            await update.message.reply_text("❌ 刪除失敗，請稍後再試")
    except ValueError:
        await update.message.reply_text("❌ 編號必須是數字")
    except Exception as e:
        await update.message.reply_text(f"❌ 刪除失敗：{str(e)}")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 開始檢查價格...")

    products = read_products_from_file()
    if not products:
        await update.message.reply_text("📝 目前沒有追蹤任何商品")
        return

    results = []
    for url, target_price in products:
        price = get_product_price(url)
        display_url = url.split('/')[-1] if '/' in url else url

        if price is not None:
            status = "🔥 低於目標" if price <= target_price else "📈 高於目標"
            results.append(f"{display_url}\n   目前：${price:,} | 目標：${target_price:,} {status}")

            if price <= target_price:
                await send_telegram_notification(url, price, target_price)
        else:
            results.append(f"{display_url}\n   ❌ 無法取得價格")

    message = "📊 價格檢查結果：\n\n" + "\n\n".join(results)
    await update.message.reply_text(message)

async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) != 2:
            await update.message.reply_text("❌ 格式錯誤\n正確格式：/update [編號] [新目標價格]")
            return

        index = int(context.args[0]) - 1
        new_price = int(context.args[1])

        products = read_products_from_file()
        if not products:
            await update.message.reply_text("📝 目前沒有追蹤任何商品")
            return

        if index < 0 or index >= len(products):
            await update.message.reply_text(f"❌ 編號錯誤，請輸入 1 到 {len(products)} 之間的數字")
            return

        url, _ = products[index]
        products[index] = (url, new_price)

        if write_products_to_file(products):
            await update.message.reply_text(f"✅ 已更新商品目標價格\n商品編號：{index+1}\n新目標價格：${new_price:,}")
        else:
            await update.message.reply_text("❌ 更新失敗，請稍後再試")
    except ValueError:
        await update.message.reply_text("❌ 編號和價格必須是數字")
    except Exception as e:
        await update.message.reply_text(f"❌ 更新失敗：{str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("請使用指令來操作機器人。輸入 /help 查看可用指令。")

# 定期檢查價格背景任務
async def check_prices_task():
    while True:
        try:
            print("🔍 開始定期檢查價格")
            products = read_products_from_file()

            for url, target_price in products:
                price = get_product_price(url)
                if price is not None:
                    print(f"目前價格：${price:,}")
                    if price <= target_price:
                        await send_telegram_notification(url, price, target_price)
                else:
                    print("無法取得價格")

            await asyncio.sleep(900)  # 30 分鐘
        except Exception as e:
            print(f"❌ 定期檢查錯誤: {e}")
            await asyncio.sleep(300)  # 出錯時 5 分鐘後重試

# 主程序
async def main_async():
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ 請設定 TELEGRAM_TOKEN 和 TELEGRAM_CHAT_ID 環境變數")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("manual", manual_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("delete", delete_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("update", update_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Telegram 機器人已啟動")

    asyncio.create_task(check_prices_task())

    await application.run_polling()

if __name__ == "__main__":
    nest_asyncio.apply()
    keep_alive()
    asyncio.run(main_async())
