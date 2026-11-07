import os, time, requests, asyncio, loggingimport threading
from flask import Flask
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is alive"
def run_web():
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
threading.Thread(target=run_web, daemon=True).start()
import numpy as np
import pandas as pd
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io

# ================= CONFIG =================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("V1-PRO")

STABLES = {"USDT","USDC","DAI","FDUSD","TUSD","USDE","PYUSD","USDP","EURC","XAUT","WBTC","STETH","WSTETH"}
EXCLUDE = {"BTC"}

# ================= INDICATORS =================
def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    sig = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - sig
    return macd_line, sig, hist

def find_divergence(price, indicator, lookback=60):
    if len(price) < lookback + 5:
        return None, 0
    p = price.values[-lookback:]
    ind = indicator.values[-lookback:]
    p_low1_idx = np.argmin(p[-30:-10])
    p_low2_idx = np.argmin(p[-10:]) + (len(p)-10)
    p_low1 = p[p_low1_idx]
    p_low2 = p[p_low2_idx]
    ind_low1 = ind[p_low1_idx]
    ind_low2 = ind[p_low2_idx]
    if p_low2 < p_low1 and ind_low2 > ind_low1:
        return "BULLISH", abs(ind_low2 - ind_low1)
    p_high1_idx = np.argmax(p[-30:-10])
    p_high2_idx = np.argmax(p[-10:]) + (len(p)-10)
    p_high1 = p[p_high1_idx]
    p_high2 = p[p_high2_idx]
    ind_high1 = ind[p_high1_idx]
    ind_high2 = ind[p_high2_idx]
    if p_high2 > p_high1 and ind_high2 < ind_high1:
        return "BEARISH", abs(ind_high1 - ind_high2)
    return None, 0

def get_top100():
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {"vs_currency":"usd","order":"market_cap_desc","per_page":130,"page":1,"sparkline":False}
        r = requests.get(url, params=params, timeout=20)
        data = r.json()
        coins = []
        for c in data:
            sym = c['symbol'].upper()
            if sym in STABLES: continue
            if sym in EXCLUDE: continue
            if c['id'] in ['tether','usd-coin']: continue
            coins.append({"symbol": sym, "name": c['name'], "price": c['current_price']})
            if len(coins) >= 100: break
        return coins
    except Exception as e:
        logger.error(f"Top100 error: {e}")
        return []

def get_klines(symbol, limit=500):
    try:
        pair = f"{symbol}USDT"
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": pair, "interval":"1h", "limit": limit}
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200: return None
        data = r.json()
        df = pd.DataFrame(data, columns=['time','open','high','low','close','volume','ct','qa','nt','tb','tq','ig'])
        for col in ['open','high','low','close','volume']:
            df[col] = pd.to_numeric(df[col])
        return df
    except:
        return None

def analyze_coin(coin):
    df = get_klines(coin['symbol'])
    if df is None or len(df) < 100: return None
    close = df['close']
    df['RSI'] = rsi(close)
    df['MACD'], df['SIGNAL'], df['HIST'] = macd(close)
    df['MA7'] = close.rolling(7).mean()
    df['MA25'] = close.rolling(25).mean()
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = float(last['close'])
    cross_up = prev['MA7'] <= prev['MA25'] and last['MA7'] > last['MA25']
    cross_down = prev['MA7'] >= prev['MA25'] and last['MA7'] < last['MA25']
    div_rsi, str_rsi = find_divergence(close, df['RSI'])
    div_macd, str_macd = find_divergence(close, df['MACD'])
    signal = None
    if div_rsi == "BULLISH" and div_macd == "BULLISH" and cross_up:
        signal = "LONG"; score = 95; reason = "ديفرجنس RSI + MACD صاعد + تقاطع MA7 فوق MA25"
    elif div_rsi == "BULLISH" and cross_up:
        signal = "LONG"; score = 85; reason = "ديفرجنس RSI صاعد + تقاطع MA7 فوق MA25"
    elif div_macd == "BULLISH" and cross_up:
        signal = "LONG"; score = 82; reason = "ديفرجنس MACD صاعد + تقاطع MA7 فوق MA25"
    elif div_rsi == "BEARISH" and div_macd == "BEARISH" and cross_down:
        signal = "SHORT"; score = 95; reason = "ديفرجنس RSI + MACD هابط + تقاطع MA7 تحت MA25"
    elif div_rsi == "BEARISH" and cross_down:
        signal = "SHORT"; score = 85; reason = "ديفرجنس RSI هابط + تقاطع MA7 تحت MA25"
    elif div_macd == "BEARISH" and cross_down:
        signal = "SHORT"; score = 82; reason = "ديفرجنس MACD هابط + تقاطع MA7 تحت MA25"
    else:
        return None
    recent_low = df['low'].tail(20).min()
    recent_high = df['high'].tail(20).max()
    atr = (df['high'] - df['low']).tail(14).mean()
    if signal == "LONG":
        entry = price
        sl = recent_low * 0.995
        risk = entry - sl
        if risk <= 0: risk = atr * 0.5
        tp1 = entry + risk * 1.5
        tp2 = entry + risk * 3.0
        tp3 = entry + risk * 5.0
    else:
        entry = price
        sl = recent_high * 1.005
        risk = sl - entry
        if risk <= 0: risk = atr * 0.5
        tp1 = entry - risk * 1.5
        tp2 = entry - risk * 3.0
        tp3 = entry - risk * 5.0
    return {
        "symbol": coin['symbol'], "name": coin['name'],
        "signal": signal, "score": score, "reason": reason,
        "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
        "rsi": float(last['RSI']), "macd": float(last['MACD']),
        "ma7": float(last['MA7']), "ma25": float(last['MA25']),
        "price": price, "df": df
    }

# ================= CHART =================
def generate_chart(df, s):
    data = df.tail(80).copy()
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5.5))
    fig.patch.set_facecolor('#0d1117')
    ax.set_facecolor('#0d1117')
    ax.plot(data['close'].values, color='white', linewidth=1.2, label='Price')
    ax.plot(data['MA7'].values, color='#FFD700', linewidth=1, label='MA7')
    ax.plot(data['MA25'].values, color='#00BFFF', linewidth=1, label='MA25')
    last_x = len(data)-1
    ax.axhline(s['entry'], color='white', linestyle='--', linewidth=1.2)
    ax.text(last_x, s['entry'], f"  ENTRY {s['entry']:.4f}", color='white', fontsize=9, va='center', fontweight='bold')
    ax.axhline(s['tp1'], color='#00FF7F', linestyle='--', linewidth=1)
    ax.text(last_x, s['tp1'], f"  TP1 {s['tp1']:.4f}", color='#00FF7F', fontsize=9, va='center')
    ax.axhline(s['tp2'], color='#00FF7F', linestyle='--', linewidth=1)
    ax.text(last_x, s['tp2'], f"  TP2 {s['tp2']:.4f}", color='#00FF7F', fontsize=9, va='center')
    ax.axhline(s['tp3'], color='#00FF7F', linestyle='--', linewidth=1)
    ax.text(last_x, s['tp3'], f"  TP3 {s['tp3']:.4f}", color='#00FF7F', fontsize=9, va='center')
    ax.axhline(s['sl'], color='red', linestyle='--', linewidth=1.2)
    ax.text(last_x, s['sl'], f"  SL {s['sl']:.4f}", color='red', fontsize=9, va='center', fontweight='bold')
    # خط الديفرجنس اصفر
    if s['signal'] == "LONG":
        ax.plot([len(data)-30, len(data)-5], [data['low'].iloc[-30], data['low'].iloc[-5]], color='yellow', linewidth=2)
    else:
        ax.plot([len(data)-30, len(data)-5], [data['high'].iloc[-30], data['high'].iloc[-5]], color='yellow', linewidth=2)
    color = "LONG" if s['signal']=="LONG" else "SHORT"
    ax.set_title(f"{s['symbol']}USDT - {color} | V1 PRO + Divergence", color='white', fontsize=12, fontweight='bold')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(True, alpha=0.2)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    return buf

# ================= FORMAT =================
def format_signal(s):
    emoji = "🟢" if s['signal']=="LONG" else "🔴"
    direction = "LONG" if s['signal']=="LONG" else "SHORT"
    return f"""
╔══════════════════════╗
   {emoji} V1 PRO {emoji}
╚══════════════════════╝

🏆 Rank من Top 100
🎯 {s['symbol']}USDT | {direction} {emoji}
━━━━━━━━━━━━━━━━━━━━━
📊 الاستراتيجية:
├ 🌊 Divergence: RSI + MACD
├ 📈 Trend: {'صاعد' if s['signal']=='LONG' else 'هابط'}
├ 💪 Score: {s['score']}%
├ 📉 RSI (1h): {s['rsi']:.1f}
├ 📊 MACD: {'Bullish ✅' if s['signal']=='LONG' else 'Bearish ❌'}
└ 📦 MA7 / MA25: تقاطع {'صاعد' if s['signal']=='LONG' else 'هابط'}
━━━━━━━━━━━━━━━━━━━━━
💰 نقطة الدخول:
├ Entry: {s['entry']:.4f}
├ Leverage: 5x - 10x
└ ⚠️ Risk: 1-2% فقط
━━━━━━━━━━━━━━━━━━━━━
🎯 الأهداف:
├ TP1: {s['tp1']:.4f} (+{abs(s['tp1']-s['entry'])/s['entry']*100:.1f}%) | اخرج 40%
├ TP2: {s['tp2']:.4f} (+{abs(s['tp2']-s['entry'])/s['entry']*100:.1f}%) | اخرج 30%
└ TP3: {s['tp3']:.4f} (+{abs(s['tp3']-s['entry'])/s['entry']*100:.1f}%) | خلي 30%
━━━━━━━━━━━━━━━━━━━━━
🛑 وقف الخسارة:
└ SL: {s['sl']:.4f} (-{abs(s['entry']-s['sl'])/s['entry']*100:.1f}%)
━━━━━━━━━━━━━━━━━━━━━
📸 شوف الصورة الفوق 👆
خط الديفرجنس + Entry + TP + SL + النموذج مرسومين
⏰ Timeframe: 1h | فحص Top 100
#V1_PRO #TOP100 #Divergence
"""

# ================= BOT COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلا بيك في V1 PRO\n\n"
        "🤖 يعتمد على:\n"
        "• ديفرجنس RSI + MACD\n"
        "• تقاطع MA7 / MA25\n"
        "• تحليل 100 عملة | فريم 1H | 500 شمعة\n\n"
        "الأوامر:\n"
        "/scan - فحص فوري\n"
        "/top - أفضل 10 عملات\n"
        "/status - حالة البوت"
    )

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 جاري فحص 100 عملة... 1H | 500 شمعة، دقيقة برك...")
    coins = get_top100()
    signals = []
    for c in coins:
        res = analyze_coin(c)
        if res: signals.append(res)
        time.sleep(0.1)
    if not signals:
        await update.message.reply_text("✅ تم الفحص، لا توجد إشارة قوية حاليا تحقق كل الشروط.")
        return
    signals = sorted(signals, key=lambda x: x['score'], reverse=True)
    for s in signals[:5]:
        try:
            chart = generate_chart(s['df'], s)
            await update.message.reply_photo(photo=chart, caption=format_signal(s))
        except Exception as e:
            await update.message.reply_text(format_signal(s))
        await asyncio.sleep(0.5)

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏆 جاري جلب Top 100...")
    coins = get_top100()
    text = "🏆 **Top 10 عملات**\n\n"
    for i, c in enumerate(coins[:10], 1):
        text += f"{i}. {c['symbol']} - ${c['price']}\n"
    await update.message.reply_text(text)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ V1 PRO خدام\n"
        "📊 عملات: 100 (بدون مستقرة)\n"
        "⏰ فريم: 1H | شموع: 500\n"
        "🎯 المؤشرات: RSI + MACD + MA7/MA25\n"
        "🔁 فحص تلقائي: كل ساعة"
    )

async def auto_scan(context: ContextTypes.DEFAULT_TYPE):
    coins = get_top100()
    signals = []
    for c in coins:
        res = analyze_coin(c)
        if res: signals.append(res)
        time.sleep(0.05)
    if not signals: return
    signals = sorted(signals, key=lambda x: x['score'], reverse=True)
    bot = context.bot
    chat_id = CHAT_ID
    if not chat_id: return
    for s in signals[:3]:
        try:
            chart = generate_chart(s['df'], s)
            await bot.send_photo(chat_id=int(chat_id), photo=chart, caption=format_signal(s))
        except Exception as e:
            logger.error(e)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.job_queue.run_repeating(auto_scan, interval=3600, first=30)
    print("V1 PRO Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
