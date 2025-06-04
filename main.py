import requests
from bs4 import BeautifulSoup
import re
import asyncio
import os
from telegram import Bot

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def read_products_from_file(filepath="product.txt"):
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

def get_product_price(product_url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
        response = requests.get(product_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        price_elements = soup.find_all(['span', 'div'], class_=re.compile(r'price|amount'))
        for element in price_elements:
            text = element.get_text(strip=True)
            price_match = re.search(r'[\d,]+', text.replace(',', ''))
            if price_match and len(price_match.group()) >= 2:
                price = int(price_match.group().replace(',', ''))
                if price > 100:
                    return price

        price_text = soup.find(text=re.compile(r'[\$\$元][\d,]+|[\d,]+[\$元]'))
        if price_text:
            price_match = re.search(r'[\d,]+', price_text.replace(',', ''))
            if price_match:
                return int(price_match.group().replace(',', ''))

        return None
    except Exception as e:
        print(f"❌ 取得價格錯誤: {e}")
        return None

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

def main():
    print("🔍 開始檢查價格")
    products = read_products_from_file()
    if not products:
        print("❌ 商品資訊讀取失敗，請確認 product.txt 格式")
        return

    for url, target_price in products:
        print(f"\n📦 商品網址：{url}")
        price = get_product_price(url)
        if price is not None:
            print(f"目前價格：${price:,}")
            if price <= target_price:
                asyncio.run(send_telegram_notification(url, price, target_price))
            else:
                print("目前價格尚未低於目標")
        else:
            print("無法取得價格")

if __name__ == "__main__":
    main()
