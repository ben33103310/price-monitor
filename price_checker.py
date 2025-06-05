# price_checker.py
import requests
from bs4 import BeautifulSoup
import re
import asyncio
import json # 移到頂部

from telegram import Bot
from telegram.ext import Application # Application 用於 type hinting

from product_manager import read_products_from_file
from telegram_utils import send_telegram_notification
from config import TELEGRAM_CHAT_ID_OWNER # 用於背景任務的預設通知對象

# get_product_price 函數 (從你之前提供的版本複製過來，確保是最新優化版)
def get_product_price(product_url: str):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # 增加 timeout
        response = requests.get(product_url, headers=headers, timeout=20)
        response.raise_for_status() # 如果請求失敗 (4xx 或 5xx)，會拋出異常
        soup = BeautifulSoup(response.content, 'html.parser')

        # PChome
        if "pchome.com.tw" in product_url:
            match = re.search(r'"price"\s*:\s*"(\d+)"', response.text)
            if match:
                return int(match.group(1))
            else:
                print("⚠️ 未在 HTML 中找到 'price' 欄位，可能頁面格式已更動")

        # momo
        elif "momoshop.com.tw" in product_url:
            match = re.search(r'\"sellPrice\":\s*\"?(\d+)', response.text) # momo 可能有引號也可能沒有
            if match:
                return int(match.group(1))
            # momo 的 schema.org JSON-LD
            script_tags = soup.find_all('script', type='application/ld+json')
            for tag in script_tags:
                try:
                    data = json.loads(tag.string)
                    if isinstance(data, list): data = data[0] # 有些頁面是 list of dict
                    if data.get('@type') == 'Product' and 'offers' in data:
                        offers = data['offers']
                        if isinstance(offers, list): offers = offers[0] # 取第一個 offer
                        if offers.get('@type') == 'Offer' and 'price' in offers:
                            return int(float(offers['price']))
                except (json.JSONDecodeError, TypeError, KeyError, IndexError):
                    continue


        # Shopee (蝦皮)
        elif "shopee.tw" in product_url:
            # 嘗試從 application/ld+json (通常更可靠)
            script_tags = soup.find_all('script', type='application/ld+json')
            for tag in script_tags:
                try:
                    json_data = json.loads(tag.string)
                    # 蝦皮的 JSON-LD 結構多樣
                    if isinstance(json_data, list): # 有些頁面是 list of dict
                        for item_data in json_data:
                            if item_data.get('@type') == 'Product' and 'offers' in item_data:
                                offers = item_data['offers']
                                if isinstance(offers, list): offers = offers[0] # 取第一個 offer
                                elif isinstance(offers, dict): offers = offers # 有時直接是 dict
                                else: continue

                                if offers.get('@type') == 'Offer' and 'price' in offers:
                                    return int(float(offers['price'])) # Shopee價格可能是字串或數字
                    elif json_data.get('@type') == 'Product' and 'offers' in json_data: # 單個 Product
                        offers = json_data['offers']
                        if isinstance(offers, list): offers = offers[0]
                        elif isinstance(offers, dict): offers = offers
                        else: continue

                        if offers.get('@type') == 'Offer' and 'price' in offers:
                             return int(float(offers['price']))
                except (json.JSONDecodeError, TypeError, KeyError, IndexError) as e:
                    # print(f"Shopee JSON-LD parsing error: {e} for {product_url}")
                    continue

            # 如果 JSON-LD 失敗，嘗試正則表達式 (作為備援)
            # 蝦皮API回傳的價格有時帶有5個0的小數位 (e.g., 12300000 for 123.00)
            # 有時是整數。這裡的正則嘗試抓取 "price": 後的數字。
            # 這個正則比較通用，可能需要根據蝦皮頁面結構的變化而調整
            match = re.search(r'"price":\s*(\d+)', response.text)
            if match:
                price_val = int(match.group(1))
                # 嘗試判斷是否為帶小數位的價格
                # 如果價格大於一個閾值 (e.g. 5000000, 表示 50元但有5個小數位)
                # 且能被100000整除，則認為是需要除的 (這只是一個啟發式規則)
                if price_val > 100000 and price_val % 100000 == 0 and str(price_val).endswith("00000"):
                     return price_val // 100000
                # 另一個可能是 "price_min" 或 "price_max" 也是如此
                # 也有可能是 "current_price" (美妝保健類別)
                # 如果不是，則直接返回 (可能已經是正確價格)
                return price_val # 需要使用者驗證這個邏輯是否符合他追蹤的商品

        # Fallback: 通用價格字樣搜尋
        # 優先找包含 itemprop="price" 或 class 類似 price 的 meta 或 span
        meta_price = soup.find("meta", itemprop="price")
        if meta_price and meta_price.get("content"):
            try: return int(float(meta_price.get("content")))
            except ValueError: pass

        # 更通用的 class name 搜尋
        price_elements = soup.find_all(
            ['span', 'div', 'strong', 'b', 'p'],
            class_=re.compile(r'price|Price|Pric|Namun|amount|SALE|CURRENT|prdPrice|money', re.I) # เพิ่มคลาสที่อาจมี
        )
        for element in price_elements:
            text = element.get_text(strip=True)
            # 清理常見的貨幣符號、文字、千分位逗號
            text = re.sub(r'[NT$\s元售價特價優惠價,₫Rp฿¥£€USD]', '', text, flags=re.I)
            text = text.replace('.', '') # 移除小數點 (假設價格為整數或轉換前處理)

            price_match = re.search(r'^\d+$', text) # 要求整個字串都是數字
            if price_match:
                price = int(price_match.group())
                # 合理的價格範圍，避免抓到庫存、評價數等
                if 50 < price < 50000000: # 例如 NT$50 到 NT$50,000,000
                    return price

        print(f"ℹ️ Fallback: 無法從特定規則或通用規則找到價格 for {product_url}")
        return None

    except requests.exceptions.Timeout:
        print(f"❌ 請求超時: {product_url}")
        return None
    except requests.exceptions.RequestException as e: # 更通用的 requests 錯誤
        print(f"❌ 請求錯誤 ({product_url}): {e}")
        return None
    except Exception as e:
        print(f"❌ 獲取價格時發生未知錯誤 ({product_url}): {e}")
        return None


async def check_prices_task(application: Application):
    bot = application.bot
    global_owner_chat_id = TELEGRAM_CHAT_ID_OWNER

    if not global_owner_chat_id:
        print("⚠️ 背景任務：TELEGRAM_CHAT_ID_OWNER 未設定，價格變動通知將不會發送給擁有者。")

    while True:
        try:
            print("週期任務：🔍 開始定期檢查價格")
            products = read_products_from_file()

            if not products:
                print("週期任務：📝 目前沒有追蹤任何商品可供定期檢查。")
            else:
                notified_in_this_run = False
                product_count = len(products)
                for i, (url, target_price) in enumerate(products):
                    print(f"週期任務：正在檢查商品 {i+1}/{product_count} - {url[:70]}...")
                    price = get_product_price(url)
                    if price is not None:
                        print(f"週期任務：商品 {url[:30]}... 目前價格：${price:,}，目標：${target_price:,}")
                        if price <= target_price:
                            if global_owner_chat_id: # 只有設定了全局 CHAT_ID 才發送
                                await send_telegram_notification(bot, global_owner_chat_id, url, price, target_price)
                                notified_in_this_run = True
                            else:
                                print(f"週期任務：商品 {url[:30]}... 低於目標價，但未設定擁有者 CHAT_ID，無法發送通知。")
                    else:
                        print(f"週期任務：商品 {url[:30]}... 無法取得價格")
                    
                    # 避免請求過於頻繁，尤其是在檢查多個商品時
                    # 在免費託管平台上，過快的請求也可能導致問題
                    await asyncio.sleep(5) # 每次查詢間隔5秒 (可調整)
                
                if notified_in_this_run:
                    print("週期任務：✅ 定期價格檢查完成，已發送部分通知。")
                elif products:
                    print("週期任務：📈 定期價格檢查完成，所有商品均未達到通知條件或無法取得價格。")

            # 調整檢查週期間隔，例如15分鐘到1小時
            # 900秒 = 15 分鐘, 1800秒 = 30分鐘, 3600秒 = 1小時
            check_interval = 900 # 預設15分鐘
            print(f"週期任務：下次檢查將在 {check_interval // 60} 分鐘後進行。")
            await asyncio.sleep(check_interval)
        except Exception as e:
            print(f"❌ 定期檢查任務發生嚴重錯誤: {e}")
            await asyncio.sleep(300)  # 出錯時 5 分鐘後重試
