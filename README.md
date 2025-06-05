# Telegram 商品價格監控機器人

這是一個 Telegram 機器人，用於監控特定購物網站上商品的價格，並在價格低於或等於使用者設定的目標價格時發送通知。

## ✨ 主要功能

* **多網站支援**：針對 PChome, momo, Shopee (蝦皮購物) 等台灣常用購物網站進行了價格擷取優化，並包含通用後備擷取邏zenia。
* **Telegram 通知**：當商品價格達到或低於設定的目標價格時，立即透過 Telegram 發送通知。
* **互動式按鈕介面**：大部分操作可透過 Inline Keyboard 按鈕完成，操作直觀方便。
* **商品管理**：
    * 新增商品追蹤 (輸入網址與目標價格)。
    * 查看目前追蹤的商品清單 (分頁顯示)。
    * 修改已追蹤商品的目標價格。
    * 刪除追蹤的商品。
* **價格檢查**：
    * 手動觸發「僅降價通知」檢查。
    * 手動觸發「價格總覽」檢查 (回報所有商品目前狀態)。
    * 背景自動定期檢查價格。
* **文字指令支援**：保留了傳統的文字指令操作方式作為備用。
* **模組化設計**：程式碼被拆分為多個模組，方便維護和擴展。

## 🔧 環境準備與安裝

1.  **Python 環境**：
    * 建議使用 Python 3.8 或更高版本。
    * 推薦建立並啟用虛擬環境：
        ```bash
        python -m venv venv
        source venv/bin/activate  # Linux/macOS
        # venv\Scripts\activate   # Windows
        ```

2.  **安裝依賴套件**：
    在專案根目錄下，執行：
    ```bash
    pip install python-telegram-bot beautifulsoup4 requests nest_asyncio python-dotenv
    ```
    (如果 `keep_alive.py` 使用 Flask，還需 `pip install Flask`)

3.  **設定環境變數**：
    * 你需要從 Telegram 的 BotFather 獲取你的機器人 `TOKEN`。
    * 你需要獲取你的 Telegram `CHAT_ID` (或機器人管理員的 Chat ID)，用於接收背景任務的通知。可以透過與 `@userinfobot` 等機器人對話獲取。

    有兩種方式設定環境變數：
    * **(推薦本地開發)** 在專案根目錄下建立一個名為 `.env` 的檔案，內容如下：
        ```env
        TELEGRAM_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
        TELEGRAM_CHAT_ID="YOUR_ADMIN_TELEGRAM_CHAT_ID"
        ```
        請將 `"YOUR_TELEGRAM_BOT_TOKEN"` 和 `"YOUR_ADMIN_TELEGRAM_CHAT_ID"` 替換為你自己的實際值。
    * **(伺服器部署)** 直接在你的伺服器環境中設定這兩個環境變數。

## 🚀 執行機器人

在專案根目錄下，執行：
```bash
python main.py