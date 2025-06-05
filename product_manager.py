# product_manager.py
from config import PRODUCT_FILE

def read_products_from_file(filepath=PRODUCT_FILE):
    products = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    # 處理可能只有 URL 沒有價格的情況 (雖然目前邏輯都會寫入價格)
                    parts = line.split()
                    if len(parts) == 2:
                        url, price_str = parts
                        try:
                            price = int(price_str)
                            products.append((url, price))
                        except ValueError:
                            print(f"⚠️ 警告：無法解析價格 '{price_str}' 於檔案 '{filepath}' 的行: '{line}'")
                    elif len(parts) == 1:
                         print(f"⚠️ 警告：檔案 '{filepath}' 的行 '{line}' 缺少價格資訊，已忽略。")
                    # else: 忽略空行或格式不正確的行
    except FileNotFoundError:
        print(f"ℹ️ 資訊：商品資料檔案 '{filepath}' 不存在，將會自動建立。")
    except Exception as e:
        print(f"❌ 錯誤：無法讀取商品資料檔案 '{filepath}': {e}")
    return products

def write_products_to_file(products, filepath=PRODUCT_FILE):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            for url, price in products:
                f.write(f"{url} {price}\n")
        return True
    except Exception as e:
        print(f"❌ 錯誤：無法寫入商品資料檔案 '{filepath}': {e}")
        return False
