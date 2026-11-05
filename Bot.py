import os
import threading
import time
import requests
import telebot
from flask import Flask

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

@app.route('/')
def home():
    return "ELLIOTT PRO V37 RUNNING"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT", "LINKUSDT"]

def get_price(symbol):
    try:
        url = f"https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}"
        r = requests.get(url, timeout=10).json()
        return float(r['price'])
    except:
        return None

@bot.message_handler(commands=['start', 'test'])
def start(message):
    bot.send_message(message.chat.id, "🟢 <b>ELLIOTT PRO V37 RENDER ACTIVE</b>\n\nالبوت خدام ✅\nابعث /price باش تشوف الأسعار")

@bot.message_handler(commands=['price'])
def price(message):
    text = "📊 <b>الأسعار الحالية:</b>\n\n"
    for s in SYMBOLS:
        p = get_price(s)
        if p:
            text += f"{s}: {p}\n"
    bot.send_message(message.chat.id, text)

def run_bot():
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            print(f"Bot error: {e}")
            time.sleep(5)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()
