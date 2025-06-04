# 商品價格監控器（GitHub Actions 版）

本專案會每天自動檢查指定商品價格，若低於目標價格，透過 Telegram 通知你。

## ✅ 如何使用

1. 將本專案上傳至你的 GitHub repository。
2. 到 Settings → Secrets and variables → Actions 加入以下 Secrets：
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. 每天會在 09:00、15:00、21:00 自動執行一次。

## 📦 依賴套件

- requests
- beautifulsoup4
- python-telegram-bot==13.15
