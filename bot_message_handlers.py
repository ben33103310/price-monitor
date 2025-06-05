# bot_message_handlers.py
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from product_manager import read_products_from_file, write_products_to_file
from telegram_utils import get_main_menu_keyboard, get_cancel_keyboard

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_action = context.user_data.get('action')
    # 確保操作的是同一個用戶 (雖然在單用戶機器人中 user_data 已隔離)
    # 但如果是多用戶，context.user_data 是基於 user_id 的，所以天然隔離
    # chat_id 主要用於回應訊息
    
    if not update.message or not update.message.text: # 忽略非文字或空訊息
        return
        
    user_input_text = update.message.text.strip()
    chat_id = update.message.chat_id # 用於回應

    if user_action == 'awaiting_url':
        if not (user_input_text.startswith('http://') or user_input_text.startswith('https://')):
            await update.message.reply_text(
                "❌ 網址格式錯誤！\n請提供以 `http://` 或 `https://` 開頭的有效商品網址：",
                reply_markup=get_cancel_keyboard(callback_data_on_cancel='main_menu')
            )
            return
        
        # 檢查商品是否已存在
        products = read_products_from_file()
        if any(existing_url == user_input_text for existing_url, _ in products):
            await update.message.reply_text(
                "❌ 新增失敗！此商品已在您的追蹤清單中。",
                reply_markup=get_main_menu_keyboard()
            )
            context.user_data.clear() # 清除狀態
            return

        context.user_data['new_product_url'] = user_input_text
        context.user_data['action'] = 'awaiting_target_price'
        await update.message.reply_text(
            f"✅ 商品網址已收到：\n`{user_input_text[:70]}...`\n\n"
            "現在請輸入此商品的【目標價格】(純數字，例如：1500)：",
            parse_mode='Markdown',
            reply_markup=get_cancel_keyboard(callback_data_on_cancel='main_menu')
        )

    elif user_action == 'awaiting_target_price':
        try:
            target_price = int(user_input_text)
            if target_price <= 0:
                raise ValueError("價格必須是正數")

            url_to_add = context.user_data.get('new_product_url')
            if not url_to_add: # 安全檢查，如果 URL 丟失了
                await update.message.reply_text(
                    "❌ 發生內部錯誤！找不到先前輸入的商品網址，請從主選單重新開始新增。",
                    reply_markup=get_main_menu_keyboard()
                )
                context.user_data.clear() # 清除狀態
                return

            products = read_products_from_file()
            products.append((url_to_add, target_price))
            if write_products_to_file(products):
                await update.message.reply_text(
                    f"🎉 **商品已成功加入追蹤！** 🎉\n\n"
                    f"網址： `{url_to_add}`\n"
                    f"目標價格： `${target_price:,}`\n\n"
                    "機器人將會為您監控此商品價格。",
                    parse_mode='Markdown',
                    reply_markup=get_main_menu_keyboard()
                )
            else:
                await update.message.reply_text(
                    "❌ 新增失敗！無法寫入商品資料檔案，請檢查後台日誌或聯繫管理員。",
                    reply_markup=get_main_menu_keyboard()
                )
            context.user_data.clear() # 清除所有與新增相關的狀態
        except ValueError:
            await update.message.reply_text(
                "❌ 價格格式錯誤！\n目標價格必須是有效的【純數字】(例如：1500)。\n請重新輸入目標價格：",
                 reply_markup=get_cancel_keyboard(callback_data_on_cancel='main_menu')
            )
        except Exception as e:
            print(f"新增商品 (awaiting_target_price) 發生錯誤: {e}")
            await update.message.reply_text(
                f"❌ 新增商品時發生未知錯誤，請稍後再試或聯繫管理員。",
                reply_markup=get_main_menu_keyboard()
            )
            context.user_data.clear()

    elif user_action == 'awaiting_new_price':
        try:
            new_target_price = int(user_input_text)
            if new_target_price <= 0:
                raise ValueError("價格必須是正數")

            product_idx_to_update = context.user_data.get('product_index_for_edit')
            if product_idx_to_update is None: # 安全檢查
                await update.message.reply_text(
                    "❌ 發生內部錯誤！找不到要更新的商品索引，請從列表重新操作。",
                    reply_markup=get_main_menu_keyboard()
                )
                context.user_data.clear()
                return

            products = read_products_from_file()
            if 0 <= product_idx_to_update < len(products):
                url_of_product, old_price = products[product_idx_to_update]
                products[product_idx_to_update] = (url_of_product, new_target_price)
                if write_products_to_file(products):
                    await update.message.reply_text(
                        f"✅ **目標價格已更新！**\n\n"
                        f"商品：`{url_of_product.split('?')[0].split('/')[-1][:30]}...`\n"
                        f"原目標價：`${old_price:,}`\n"
                        f"新目標價：`${new_target_price:,}`",
                        parse_mode='Markdown',
                        reply_markup=get_main_menu_keyboard() # 或返回商品列表 get_cancel_keyboard('list_products')
                    )
                else:
                    await update.message.reply_text(
                        "❌ 更新失敗！無法寫入商品資料檔案。",
                        reply_markup=get_main_menu_keyboard()
                    )
            else: # 索引在此期間失效
                await update.message.reply_text(
                    "❌ 更新失敗！您嘗試更新的商品索引已失效 (可能已被刪除或列表已變動)。",
                    reply_markup=get_main_menu_keyboard()
                )
            context.user_data.clear() # 清除所有與更新相關的狀態
        except ValueError:
            await update.message.reply_text(
                "❌ 價格格式錯誤！\n新的目標價格必須是有效的【純數字】(例如：1200)。\n請重新輸入新目標價格：",
                reply_markup=get_cancel_keyboard(callback_data_on_cancel='list_products')
            )
        except Exception as e:
            print(f"更新價格 (awaiting_new_price) 發生錯誤: {e}")
            await update.message.reply_text(
                f"❌ 更新價格時發生未知錯誤，請稍後再試。",
                reply_markup=get_main_menu_keyboard()
            )
            context.user_data.clear()
            
    else: # 非預期狀態下的文字訊息
        # 可以選擇不回應，或者像之前一樣提示
        # await update.message.reply_text("我不明白你的意思。請使用按鈕或指令操作。", reply_markup=get_main_menu_keyboard())
        pass # 通常最好不要對每個非預期輸入都回應，避免打擾