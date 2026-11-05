import os
import threading
import time
import requests
import telebot
from flask import Flask
from io import BytesIO

# ═══════════════════════════════════════
# ELLIOTT PRO V42 - TOP 100 + DIVERGENCE
# ═══════════════════════════════════════

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
app = Flask(__name__)

@app.route('/')
def home():
    return "ELLIOTT PRO V42 TOP100 + DIVERGENCE RUNNING"

CHAT_IDS = set()
SENT = {}
TOP100 = []

# ─── جلب Top 100 عملة ───
def get_top100():
    try:
        url = "https://data-api.binance.vision/api/v3/ticker/24hr"
        r = requests.get(url, timeout=15).json()
        bad = ["USDCUSDT","FDUSDUSDT","TUSDUSDT","USDPUSDT","DAIUSDT","EURUSDT","BRLUSDT","AEURUSDT"]
        filt = [x for x in r if x['symbol'].endswith('USDT') and x['symbol'] not in bad and float(x['quoteVolume']) > 5000000]
        filt.sort(key=lambda x: float(x['quoteVolume']), reverse=True)
        return [x['symbol'] for x in filt[:100]]
    except Exception as e:
        print("Top100 error:", e)
        return ["BTCUSDT","ETHUSDT","SOLUSDT","DOGEUSDT","XRPUSDT","LINKUSDT","ADAUSDT","AVAXUSDT","DOTUSDT","ATOMUSDT"]

def get_klines(symbol, interval="15m", limit=100):
    try:
        url = f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        r = requests.get(url, timeout=10).json()
        closes = [float(x[4]) for x in r]
        volumes = [float(x[5]) for x in r]
        return closes, volumes
    except:
        return [], []

def ema(data, period):
    if len(data) < period:
        return data[-1] if data else 0
    k = 2 / (period + 1)
    e = sum(data[:period]) / period
    for p in data[period:]:
        e = p * k + e * (1 - k)
    return e

def ema_list(data, period):
    out = []
    k = 2 / (period + 1)
    e = sum(data[:period]) / period
    out.extend([e]*period)
    for p in data[period:]:
        e = p * k + e * (1 - k)
        out.append(e)
    return out

def rsi_calc(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = 0, 0
    for i in range(1, period + 1):
        d = closes[-i] - closes[-i-1]
        if d > 0:
            gains += d
        else:
            losses += -d
    if losses == 0:
        return 75
    rs = (gains/period) / (losses/period)
    return 100 - (100/(1+rs))

# ─── V42: RSI كامل للقائمة باش نحسبو الديفرجنس ───
def rsi_list(closes, period=14):
    out = [50.0]*len(closes)
    if len(closes) < period + 1:
        return out
    gains = []
    losses = []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(closes)):
        if i > period:
            avg_gain = (avg_gain*(period-1) + gains[i-1]) / period
            avg_loss = (avg_loss*(period-1) + losses[i-1]) / period
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100 - (100/(1+rs))
    return out

# ─── V42: كشف الديفرجنس ───
def detect_divergence(closes, rsi_vals):
    if len(closes) < 30 or len(rsi_vals) < 30:
        return None, None
    p = closes[-30:]
    r = rsi_vals[-30:]
    # قاعين
    i1_low = p[:15].index(min(p[:15]))
    i2_low = 15 + p[15:].index(min(p[15:]))
    # قمتين
    i1_high = p[:15].index(max(p[:15]))
    i2_high = 15 + p[15:].index(max(p[15:]))

    # Bullish: سعر قاع أقل بصح RSI قاع أعلى
    if p[i2_low] < p[i1_low] and r[i2_low] > r[i1_low]:
        return 'bullish', {'x1': i1_low, 'x2': i2_low, 'p1': p[i1_low], 'p2': p[i2_low], 'r1': r[i1_low], 'r2': r[i2_low]}
    # Bearish: سعر قمة أعلى بصح RSI قمة أقل
    if p[i2_high] > p[i1_high] and r[i2_high] < r[i1_high]:
        return 'bearish', {'x1': i1_high, 'x2': i2_high, 'p1': p[i1_high], 'p2': p[i2_high], 'r1': r[i1_high], 'r2': r[i2_high]}
    return None, None

def macd_calc(closes):
    if len(closes) < 26:
        return 0
    return ema(closes, 12) - ema(closes, 26)

# ─── رسم صورة النموذج V42 + خط الديفرجنس ───
def create_chart(symbol, closes, entry, tp1, tp2, sl, direction, div_type=None, div_data=None):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        data = closes[-50:]
        e21 = ema_list(closes, 21)[-50:]
        e50 = ema_list(closes, 50)[-50:]
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 5))
        fig.patch.set_facecolor('#0E1117')
        ax.set_facecolor('#0E1117')
        ax.plot(data, color='#00E5FF', linewidth=2, label='Price')
        ax.plot(e21, color='#FFD700', linewidth=1.2, linestyle='--', label='EMA 21')
        ax.plot(e50, color='#FF6B6B', linewidth=1.2, linestyle='--', label='EMA 50')
        ax.axhline(entry, color='white', linestyle='-', linewidth=1.5)
        ax.axhline(tp1, color='#00FF88', linestyle='--', linewidth=1.2)
        ax.axhline(tp2, color='#00FF88', linestyle=':', linewidth=1.2)
        ax.axhline(sl, color='#FF3333', linestyle='--', linewidth=1.5)
        # V42: خط الديفرجنس - نحولو من 30 الأخيرة لـ 50 الأخيرة (20+)
        if div_type and div_data:
            col = '#00FF88' if div_type == 'bullish' else '#FF3333'
            x1 = 20 + div_data['x1']
            x2 = 20 + div_data['x2']
            ax.plot([x1, x2], [div_data['p1'], div_data['p2']], color=col, linewidth=2.5, linestyle='--', label=f'Divergence {div_type}')
            ax.scatter([x1, x2], [div_data['p1'], div_data['p2']], color=col, s=80, zorder=6, edgecolors='white')
            ax.text(x2, div_data['p2'], f'  DIV {div_type.upper()}', color=col, fontsize=9, fontweight='bold', va='bottom')
        ax.text(len(data)-1, entry, f' ENTRY {entry:.4f}', color='white', fontsize=9, fontweight='bold', va='bottom')
        ax.text(len(data)-1, tp1, f' TP1 {tp1:.4f}', color='#00FF88', fontsize=9, va='bottom')
        ax.text(len(data)-1, sl, f' SL {sl:.4f}', color='#FF3333', fontsize=9, va='top')
        color_dot = '#00FF88' if direction == "LONG" else '#FF3333'
        ax.scatter([len(data)-1], [entry], color=color_dot, s=120, zorder=5, edgecolors='white')
        ax.set_title(f'{symbol} - {direction} | Elliott V42 + Divergence', color='white', fontsize=13, fontweight='bold', pad=12)
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.2)
        ax.tick_params(colors='white', labelsize=8)
        buf = BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=130, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return buf
    except Exception as e:
        print("Chart error:", e)
        return None

# ─── تحليل قوي V42 ───
def analyze(symbol):
    closes, volumes = get_klines(symbol)
    if len(closes) < 50:
        return None
    price = closes[-1]
    rsi = rsi_calc(closes)
    rsi_vals = rsi_list(closes)
    e9 = ema(closes, 9)
    e21 = ema(closes, 21)
    e50 = ema(closes, 50)
    macd = macd_calc(closes)
    vol_avg = sum(volumes[-20:]) / 20 if volumes else 1
    vol_now = volumes[-1] if volumes else 1
    vol_strong = vol_now > vol_avg * 1.2
    wave = "Wave 3" if rsi < 35 else "Wave 5 - Reversal" if rsi > 65 else "Wave 2 - Correction" if 45 < rsi < 55 else "Wave 3"
    # V42: حساب الديفرجنس
    div_type, div_data = detect_divergence(closes, rsi_vals)
    score = 0
    direction = None
    if price > e21 > e50 and macd > 0 and rsi < 45:
        direction = "LONG"
        score += 40
        if rsi < 32:
            score += 20
        elif rsi < 40:
            score += 12
        if vol_strong:
            score += 15
        if price > e9:
            score += 10
        if macd > 0:
            score += 10
    elif price < e21 < e50 and macd < 0 and rsi > 55:
        direction = "SHORT"
        score += 40
        if rsi > 68:
            score += 20
        elif rsi > 60:
            score += 12
        if vol_strong:
            score += 15
        if price < e9:
            score += 10
        if macd < 0:
            score += 10

    if direction:
        # V42 فلتر: ديفرجنس عكس الاتجاه = الغي الصفقة
        if direction == "LONG" and div_type == 'bearish':
            return None
        if direction == "SHORT" and div_type == 'bullish':
            return None
        # V42 بونيس: ديفرجنس مع الاتجاه = +15
        if (direction == "LONG" and div_type == 'bullish') or (direction == "SHORT" and div_type == 'bearish'):
            score += 15

    if direction and score >= 80:
        if direction == "LONG":
            tp1, tp2, tp3, sl = price*1.015, price*1.03, price*1.05, price*0.985
        else:
            tp1, tp2, tp3, sl = price*0.985, price*0.97, price*0.95, price*1.015
        return {"symbol": symbol, "price": price, "rsi": rsi, "direction": direction, "score": score, "wave": wave, "macd": macd, "vol": vol_strong, "closes": closes, "tp1": tp1, "tp2": tp2, "tp3": tp3, "sl": sl, "div_type": div_type, "div_data": div_data}
    return None

# ─── رسالة مزخرفة ───
def build_msg(s, rank):
    sym = s["symbol"]; p = s["price"]
    is_long = s["direction"] == "LONG"
    emoji = "🟢" if is_long else "🔴"
    trend = "📈 صاعد" if is_long else "📉 هابط"
    div_txt = ""
    if s.get("div_type") == 'bullish':
        div_txt = "\n┣ 🔥 Divergence: <b>صاعد ✅ +15%</b>"
    elif s.get("div_type") == 'bearish':
        div_txt = "\n┣ 🔥 Divergence: <b>هابط ✅ +15%</b>"
    return f"""╔═══════════════════╗
{emoji} <b>ELLIOTT PRO V42</b> {emoji}
╚═══════════════════╝
🏆 <b>Rank #{rank} من Top 100</b>
🎯 <b>{sym}</b> | {s["direction"]} {emoji}
━━━━━━━━━━━━━━━━━━━
📊 <b>الاستراتيجية:</b>
┣ 🌊 Elliott: <b>{s["wave"]}</b>
┣ 📈 Trend: <b>{trend}</b>
┣ 💪 Score: <b>{s["score"]}% 🔥</b>
┣ 📉 RSI (15m): <b>{s["rsi"]:.1f}</b>
┣ 📊 MACD: <b>{'Bullish ✅' if s["macd"]>0 else 'Bearish ❌'}</b>{div_txt}
┗ 🔊 Volume: <b>{'قوي ✅' if s["vol"] else 'عادي'}</b>
━━━━━━━━━━━━━━━━━━━
💰 <b>نقطة الدخول:</b>
┣ Entry: <code>{p:.4f}</code>
┣ Leverage: <b>5x - 10x</b>
┗ ⚠️ Risk: 1-2% فقط
━━━━━━━━━━━━━━━━━━━
🎯 <b>الأهداف:</b>
┣ TP1: <code>{s["tp1"]:.4f}</code> (+1.5%)
┣ TP2: <code>{s["tp2"]:.4f}</code> (+3%)
┗ TP3: <code>{s["tp3"]:.4f}</code> (+5%)
🛑 <b>وقف الخسارة:</b>
┗ SL: <code>{s["sl"]:.4f}</code> (-1.5%)
━━━━━━━━━━━━━━━━━━━
📸 <b>شوف الصورة الفوق 👆</b>
النموذج + Entry + TP + SL + خط الديفرجنس مرسومين
⏰ Timeframe: 15m | فحص Top 100
#Elliott_V42 #TOP100 #Divergence
"""

def check_signals():
    global TOP100
    TOP100 = get_top100()
    while True:
        time.sleep(600)
        TOP100 = get_top100()
        if not CHAT_IDS:
            continue
        results = []
        for sym in TOP100:
            try:
                if SENT.get(sym, 0) > time.time() - 3600:
                    continue
                res = analyze(sym)
                if res:
                    results.append(res)
                time.sleep(0.15)
            except:
                continue
        results.sort(key=lambda x: x["score"], reverse=True)
        for idx, res in enumerate(results[:3], start=1):
            SENT[res["symbol"]] = time.time()
            msg = build_msg(res, idx)
            chart = create_chart(res["symbol"], res["closes"], res["price"], res["tp1"], res["tp2"], res["sl"], res["direction"], res.get("div_type"), res.get("div_data"))
            for cid in list(CHAT_IDS):
                try:
                    if chart:
                        chart.seek(0)
                        bot.send_photo(cid, chart, caption=msg)
                    else:
                        bot.send_message(cid, msg)
                except:
                    pass
            time.sleep(2)

@bot.message_handler(commands=['start'])
def start(m):
    CHAT_IDS.add(m.chat.id)
    bot.reply_to(m, """╔═══════════════════╗
🟢 <b>ELLIOTT PRO V42</b>
╚═══════════════════╝
✅ <b>البوت خدام</b>
✅ يحلل <b>Top 100 عملة</b>
✅ يبعث غي أحسن 3 صفقات +80%
✅ مع صورة الشارت + خط الديفرجنس 📸
✅ فلتر ديفرجنس 🔥
📌 <b>الأوامر:</b>
/price - الأسعار
/top100 - شوف Top 100
/signals - حالة الفحص
━━━━━━━━━━━
استنى الصفقات تجيك هنا تلقائيا 📩
""")

@bot.message_handler(commands=['price'])
def price(m):
    CHAT_IDS.add(m.chat.id)
    txt = "💰 <b>PRICES LIVE - TOP 8</b>\n━━━━━━━━━━━\n"
    for s in TOP100[:8] if TOP100 else ["BTCUSDT","ETHUSDT","SOLUSDT"]:
        closes,_ = get_klines(s, limit=2)
        if closes:
            txt += f"• {s}: <code>{closes[-1]:.4f}</code>\n"
    bot.reply_to(m, txt)

@bot.message_handler(commands=['top100'])
def top100_cmd(m):
    CHAT_IDS.add(m.chat.id)
    if not TOP100:
        bot.reply_to(m, "⏳ راني نجيب Top 100... عاود بعد دقيقة")
        return
    txt = "🏆 <b>TOP 100 - أقوى العملات بالـ Volume</b>\n━━━━━━━━━━━\n"
    for i, s in enumerate(TOP100[:20], start=1):
        txt += f"{i}. {s}\n"
    txt += "\n... + 80 عملة أخرى يتم فحصها تلقائيا 🔍"
    bot.reply_to(m, txt)

@bot.message_handler(commands=['signals'])
def sig(m):
    CHAT_IDS.add(m.chat.id)
    bot.reply_to(m, f"🔍 <b>راني نفحص {len(TOP100) if TOP100 else 100} عملة...</b>\nالاستراتيجية: Elliott + RSI + EMA + MACD + Divergence + Top100 + صورة الشارت 📸\nنبعثلك غي أحسن 3 صفقات +80% 🔥")

threading.Thread(target=check_signals, daemon=True).start()
threading.Thread(target=lambda: bot.infinity_polling(skip_pending=True), daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
