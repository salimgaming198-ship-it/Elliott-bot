import os, time, threading, requests
import telebot
from flask import Flask
TOKEN = os.environ.get9211490560:"AAEJ4AQ4YFmjWzIH7WkUsGPQQOUEUMoxcVE"
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
CHAT_ID = "1419681693"
SENT = {}
app = Flask(__name__)
@app.route('/')
def home():
    return "ELLIOTT PRO V37 RUNNING"
@bot.message_handler(commands=['start','test'])
def start(m):
    global CHAT_ID
    CHAT_ID = m.chat.id
    bot.send_message(CHAT_ID, "🟢 <b>ELLIOTT PRO V37 RENDER ACTIVE</b>\n\n📐 Elliott 5 Waves + Fibonacci\n☁️ Running 24/24 on Render\n🛡️ R:R 2:1 Minimum")
SYMBOLS = ["BTCUSDT","ETHUSDT","SOLUSDT","DOGEUSDT","XRPUSDT","LINKUSDT","AVAXUSDT","NEARUSDT","SUIUSDT","APTUSDT","ARBUSDT","OPUSDT","TIAUSDT","INJUSDT","FETUSDT","RENDERUSDT","SEIUSDT","ATOMUSDT","FILUSDT","LDOUSDT"]
def get_data(sym, interval="1h", limit=100):
    try:
        url = f"https://data-api.binance.vision/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}"
        r = requests.get(url, timeout=10).json()
        closes = [float(x[4]) for x in r]
        highs = [float(x[2]) for x in r]
        lows = [float(x[3]) for x in r]
        vols = [float(x[5]) for x in r]
        return closes, highs, lows, vols
    except: return [], [], [], []
def get_rsi(closes, period=14):
    if len(closes) < period+1: return 50
    gains=0; losses=0
    for i in range(-period,0):
        d = closes[i]-closes[i-1]
        if d>0: gains+=d
        else: losses+=-d
    if losses==0: return 100
    rs=(gains/period)/(losses/period)
    return 100-(100/(1+rs))
def find_swings(highs, lows):
    sh=[]; sl=[]
    for i in range(2, len(highs)-2):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1] and highs[i] > highs[i-2] and highs[i] > highs[i+2]:
            sh.append((i, highs[i]))
        if lows[i] < lows[i-1] and lows[i] < lows[i+1] and lows[i] < lows[i-2] and lows[i] < lows[i+2]:
            sl.append((i, lows[i]))
    return sh, sl
def analyze(sym):
    closes, highs, lows, vols = get_data(sym, "1h", 100)
    if len(closes) < 50: return None
    btc_closes, _, _, _ = get_data("BTCUSDT", "1h", 50)
    if btc_closes:
        btc_trend = (btc_closes[-1] - btc_closes[-10]) / btc_closes[-10] * 100
        if btc_trend < -1.5: return None
    sh, sl = find_swings(highs, lows)
    if len(sh) < 2 or len(sl) < 2: return None
    last_high = sh[-1][1]; last_low = sl[-1][1]
    prev_high = sh[-2][1]; prev_low = sl[-2][1]
    price = closes[-1]
    wave1_len = prev_high - prev_low
    if wave1_len <= 0: return None
    fib_50 = prev_high - wave1_len * 0.5
    fib_618 = prev_high - wave1_len * 0.618
    fib_382 = prev_high - wave1_len * 0.382
    in_fib_zone = fib_618 <= price <= fib_382
    avg_vol = sum(vols[-20:]) / 20
    vol_ok = vols[-1] > avg_vol * 0.8
    rsi = get_rsi(closes)
    rsi_ok = 35 < rsi < 60
    higher_low = last_low > prev_low
    score = 0; reasons=[]
    if in_fib_zone: score+=35; reasons.append("Fib 0.5-0.618 ✅")
    if higher_low: score+=20; reasons.append("Higher Low ✅")
    if vol_ok: score+=15; reasons.append("Volume ✅")
    if rsi_ok: score+=15; reasons.append(f"RSI {rsi:.0f} ✅")
    if closes[-1] > closes[-2]: score+=15; reasons.append("شمعة انعكاس ✅")
    sl_price = last_low * 0.998
    tp_price = prev_high + wave1_len * 0.618
    risk = price - sl_price
    reward = tp_price - price
    rr = reward / risk if risk>0 else 0
    if rr < 2: return None
    return {'sym':sym,'score':score,'price':price,'rsi':rsi,'sl':sl_price,'tp':tp_price,'rr':rr,'reasons':reasons}
def main_loop():
    global CHAT_ID
    while True:
        try:
            candidates=[]
            for sym in SYMBOLS:
                res=analyze(sym)
                if res is None: continue
                if res['score']>=80:
                    if time.time()-SENT.get(sym,0)<14400: continue
                    candidates.append(res)
                time.sleep(0.5)
            candidates.sort(key=lambda x: x['score'], reverse=True)
            top=candidates[:2]
            if top and CHAT_ID:
                for c in top:
                    txt=f"🟢 <b>PRO TRADE {c['sym']}</b>\n📐 Elliott Wave 3 Setup\n📊 Score: {c['score']}% | RSI: {c['rsi']:.0f}\n💰 Entry: {c['price']:.4f}\n🛑 SL: {c['sl']:.4f}\n🎯 TP: {c['tp']:.4f}\n⚖️ R:R: 1:{c['rr']:.1f}\n\n✅ " + "\n✅ ".join(c['reasons'])
                    bot.send_message(CHAT_ID, txt)
                    SENT[c['sym']]=time.time()
            time.sleep(300)
        except Exception as e:
            print(e); time.sleep(10)
def run_polling():
    while True:
        try: bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except: time.sleep(10)
threading.Thread(target=run_polling, daemon=True).start()
threading.Thread(target=main_loop, daemon=True).start()
port = int(os.environ.get("PORT", 10000))
app.run(host="0.0.0.0", port=port)
