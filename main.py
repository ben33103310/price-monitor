import requests
from bs4 import BeautifulSoup
import re
import asyncio
import os
from telegram import Bot

PRODUCT_URL = "https://24h.pchome.com.tw/prod/DMAH02-A900AN6MB"
TARGET_PRICE = 1350
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_product_price():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(PRODUCT_URL, headers=headers)
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

async def send_telegram_notification(price):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        message = f"""🚨 價格警報！\n目前價格：${price:,}\n已低於目標價格 ${TARGET_PRICE:,}\n商品連結：{PRODUCT_URL}"""
        bot.send_message(chat_id=CHAT_ID, text=message)
        print("✅ 已發送 Telegram 通知")
    except Exception as e:
        print(f"❌ 發送通知錯誤: {e}")

def main():
    print("🔍 開始檢查價格")
    price = get_product_price()
    if price is not None:
        print(f"目前價格：${price:,}")
        if price <= TARGET_PRICE:
            asyncio.run(send_telegram_notification(price))
        else:
            print("目前價格尚未低於目標")
    else:
        print("無法取得價格")

if __name__ == "__main__":
    main()
