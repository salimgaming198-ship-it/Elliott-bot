import os
import threading
import time
import requests
import telebot
from flask import Flask
from io import BytesIO

# ============================================
# ELLIOTT PRO V43 - TOP 100 + DIVERGENCE + FIX
# ============================================

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

@app.route('/')
def home():
    return "ELLIOTT PRO V43 TOP100 + DIVERGENCE RUNNING"

CHAT_IDS = set()
SENT = {}
TOP100 = []

# ----- جلب Top 100 عملة -----
def get_top100():
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false"
        r = requests.get(url, timeout=20)
        data = r.json()
        coins = []
        for c in data:
            coins.append({
                'id': c['id'],
                'symbol': c['symbol'].upper(),
                'name': c['name'],
                'price': c['current_price'],
                'change': c.get('price_change_percentage_24h', 0) or 0
            })
        return coins
    except Exception as e:
        print("Top100 Error:", e)
        return TOP100

def get_klines(coin_id, days=3):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days={days}&interval=hourly"
        r = requests.get(url, timeout=20)
        prices = r.json().get('prices', [])
        return [p[1] for p in prices]
    except:
        return []

def calc_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(prices)):
        d = prices[i] - prices[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    # RSI simple
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def check_divergence(prices):
    # دايفرجنس بسيط: السعر يدير قاع جديد و RSI ما يديرش
    if len(prices) < 30:
        return None
    p1, p2 = min(prices[-30:-15]), min(prices[-15:])
    r1 = calc_rsi(prices[:-15])
    r2 = calc_rsi(prices)
    if p2 < p1 and r2 > r1:
        return "BULLISH ✅"
    if max(prices[-15:]) > max(prices[-30:-15]) and r2 < r1:
        return "BEARISH 🔴"
    return None

def scan_loop():
    global TOP100
    while True:
        try:
            TOP100 = get_top100()
            print(f"Scanned {len(TOP100)} coins - V43")
            for coin in TOP100:
                prices = get_klines(coin['id'])
                if not prices:
                    continue
                rsi = calc_rsi(prices)
                div = check_divergence(prices)
                # اشارة قوية
                signal = None
                if div == "BULLISH ✅" and rsi < 35:
                    signal = f"🟢 <b>{coin['symbol']} / USDT</b>\n💰 السعر: ${coin['price']}\n📊 RSI: {round(rsi,1)} - تشبع بيع\n📈 دايفرجنس: صعودي ✅\n🎯 توقع موجة Elliott صاعدة"
                elif div == "BEARISH 🔴" and rsi > 65:
                    signal = f"🔴 <b>{coin['symbol']} / USDT</b>\n💰 السعر: ${coin['price']}\n📊 RSI: {round(rsi,1)} - تشبع شراء\n📉 دايفرجنس: هبوطي 🔴\n⚠️ توقع تصحيح"

                if signal:
                    key = coin['symbol'] + div
                    now = time.time()
                    if key not in SENT or now - SENT[key] > 3600*4: # كل 4 ساعات برك
                        for chat in list(CHAT_IDS):
                            try:
                                bot.send_message(chat, signal)
                            except:
                                pass
                        SENT[key] = now
                time.sleep(1.5) # باش ما نبلوكيش API
            time.sleep(300) # عاود كل 5 دقائق
        except Exception as e:
            print("Scan Error:", e)
            time.sleep(60)

@bot.message_handler(commands=['start'])
def start(m):
    CHAT_IDS.add(m.chat.id)
    bot.reply_to(m, "👋 <b>مرحبا بيك في ELLIOTT PRO V43</b>\n\n✅ Top 100 عملة\n✅ كشف الدايفرجنس\n✅ تنبيهات كل 4 ساعات باش ما يسباميش\n\n📡 البوت راه يخدم درك، استنى الاشارات\n\n/start - تشغيل\n/top - Top 100\n/status - حالة البوت")

@bot.message_handler(commands=['top'])
def top_cmd(m):
    if not TOP100:
        bot.reply_to(m, "⏳ مزال نجبد في Top 100... استنى شوية")
        return
    txt = "🏆 <b>TOP 10 - V43</b>\n\n"
    for i, c in enumerate(TOP100[:10], 1):
        emoji = "🟢" if c['change'] >= 0 else "🔴"
        txt += f"{i}. {c['symbol']} - ${c['price']} {emoji} {round(c['change'],2)}%\n"
    bot.reply_to(m, txt)

@bot.message_handler(commands=['status'])
def status_cmd(m):
    bot.reply_to(m, f"✅ <b>V43 خدام</b>\n📊 عملات مراقبة: {len(TOP100)}\n👥 مشتركين: {len(CHAT_IDS)}\n⏰ آخر تحديث: الآن")

def run_bot():
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print("Polling Error:", e)
            time.sleep(10)

if __name__ == '__main__':
    threading.Thread(target=scan_loop, daemon=True).start()
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    run_bot()
