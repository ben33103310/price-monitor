# 🛒 Telegram 價格追蹤機器人

這是一個可部署於 Render 或 Replit 的 Telegram 機器人，可幫你**定期追蹤商品價格**並在價格低於目標時發送通知，支援 momo、蝦皮、PChome 等常見電商平台。

---

## 🚀 功能特色

- ✅ 支援以下網站價格擷取：
  - PChome（24h）
  - momo 購物網
  - Shopee 蝦皮
  - 其他網站（以 HTML 推測價格）
- 🧠 Telegram Bot 操作介面，支援文字指令操作
- 🔔 價格低於目標自動通知
- 🔄 每 30 分鐘自動檢查所有商品
- 📦 使用簡單的 `product.txt` 儲存追蹤清單
- 🌐 支援部署於 [Render](https://render.com) 或 [Replit](https://replit.com)

---

## 🛠️ 安裝與執行

### 1. Clone 專案

```bash
git clone https://github.com/你的帳號/price-monitor.git
cd price-monitor
