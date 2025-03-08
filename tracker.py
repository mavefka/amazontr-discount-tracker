import requests
import json
import os
import logging
from bs4 import BeautifulSoup
from telegram import Bot
import asyncio

TELEGRAM_TOKEN = "bottoken"
CHAT_ID = "chatid"
bot = Bot(token=TELEGRAM_TOKEN)

PRODUCTS_FILE = "products.txt"
PRICE_HISTORY_FILE = "price_history.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "TE": "Trailers"
}

def load_price_history():
    if os.path.exists(PRICE_HISTORY_FILE):
        try:
            with open(PRICE_HISTORY_FILE, "r") as file:
                data = file.read().strip()
                if not data:
                    logging.warning("Fiyat geçmişi dosyası boş!")
                    return {}
                return json.loads(data)
        except (json.JSONDecodeError, ValueError):
            logging.error("Fiyat geçmişi JSON dosyası bozuk! Yeni bir tane oluşturuluyor...")
            return {}
    return {}

def save_price_history(price_history):
    with open(PRICE_HISTORY_FILE, "w") as file:
        json.dump(price_history, file, indent=4)

def get_amazon_price(url):
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        logging.error(f"Amazon ürün sayfası alınamadı: {url}")
        return None, None
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    price_tag = soup.select_one("span.a-price-whole")
    if not price_tag:
        price_tag = soup.select_one("span#priceblock_ourprice")
    
    if not price_tag:
        logging.error(f"Amazon fiyat bulunamadı: {url}")
        return None, None
    
    try:
        price = float(price_tag.get_text().replace(".", "").replace(",", "").strip())
    except ValueError:
        logging.error(f"Amazon fiyat dönüştürülemedi: {url}")
        return None, None
    
    title_tag = soup.select_one("span#productTitle")
    if title_tag:
        product_name = title_tag.get_text(strip=True)
    else:
        product_name = "Amazon Türkiye ürün adı bulunamadı"
    
    return price, product_name

def get_dore_price(url):
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        logging.error(f"Dore ürün sayfası alınamadı: {url}")
        return None, None
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    price_tag = soup.select_one("span.price.currency-net.c-orange")
    if not price_tag:
        logging.error(f"Dore fiyat bulunamadı: {url}")
        return None, None
    
    try:
        price_text = price_tag.get_text().strip()
        price = ''.join(c for c in price_text if c.isdigit() or c == '.')
        price = float(price)
    except ValueError:
        logging.error(f"Dore fiyat dönüştürülemedi: {url}")
        return None, None
    
    title_tag = soup.select_one("h1.product-title")
    if title_tag:
        product_name = title_tag.get_text(strip=True)
    else:
        product_name = "Dore ürün adı bulunamadı"
    
    return price, product_name

async def send_telegram_message(message):
    logging.info(f"Telegram mesajı gönderiliyor: {message}")
    await bot.send_message(chat_id=CHAT_ID, text=message)

async def check_prices():
    price_history = load_price_history()
    
    if not os.path.exists(PRODUCTS_FILE):
        logging.error("products.txt dosyası bulunamadı!")
        return
    
    with open(PRODUCTS_FILE, "r") as file:
        urls = [line.strip() for line in file.readlines() if line.strip()]
    
    messages = []
    for url in urls:
        if "do-re" in url:
            price, product_name = get_dore_price(url)
        else:
            price, product_name = get_amazon_price(url)
        
        if price is None:
            logging.error(f"Fiyat alınamadı: {url}")
            continue
        
        if url in price_history:
            if price < price_history[url]:
                discount = ((price_history[url] - price) / price_history[url]) * 100
                message = f"""📉 Fiyat düştü!
Ürün: {product_name} ({url})
Eski Fiyat: {price_history[url]} TL
Yeni Fiyat: {price} TL
İndirim: %{discount:.2f}"""
                messages.append(message)
            elif price > price_history[url]:
                increase = ((price - price_history[url]) / price_history[url]) * 100
                message = f"""📈 Fiyat arttı!
Ürün: {product_name} ({url})
Eski Fiyat: {price_history[url]} TL
Yeni Fiyat: {price} TL
Artış: %{increase:.2f}"""
                messages.append(message)
            else:
                message = f"""💡 Fiyat değişmedi.
Ürün: {product_name} ({url})
Fiyat: {price} TL"""
                messages.append(message)
        
        price_history[url] = price
    
    if messages:
        await send_telegram_message("\n\n".join(messages))
    
    save_price_history(price_history)

async def main():
    while True:
        await check_prices()
        logging.info("Fiyat kontrolü tamamlandı. 5 saat bekleniyor...")
        await asyncio.sleep(18000)

if __name__ == "__main__":
    asyncio.run(main())
