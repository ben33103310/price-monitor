# config.py
import os
from dotenv import load_dotenv

# 從 .env 文件加載環境變數 (如果有的話，方便本地開發)
# 在伺服器環境中，通常直接設定環境變數
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# CHAT_ID 主要用於背景任務的預設通知對象，若要做多用戶則需調整
# 對於指令互動，會使用觸發者的 chat_id
TELEGRAM_CHAT_ID_OWNER = os.getenv("TELEGRAM_CHAT_ID") # 更名以區分用途

PRODUCT_FILE = "product.txt"

# 檢查必要的環境變數
if not TELEGRAM_TOKEN:
    print("❌ 錯誤：請設定 TELEGRAM_TOKEN 環境變數。")
    exit()

# TELEGRAM_CHAT_ID_OWNER 是可選的，如果未設定，背景任務的通知可能會受影響
if not TELEGRAM_CHAT_ID_OWNER:
    print("⚠️ 警告：環境變數 TELEGRAM_CHAT_ID (TELEGRAM_CHAT_ID_OWNER) 未設定，")
    print("      定期檢查任務的通知可能無法發送給預設管理員。")