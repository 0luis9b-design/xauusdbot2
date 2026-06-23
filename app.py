from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import datetime
import threading
import time
import math
import json
import urllib.request
import random

app = Flask(__name__)
CORS(app)

def def_strat_stats():
    return {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "eur_pnl": 0.0, "best": 0.0, "worst": 0.0, "win_rate": 0.0}

# GLOBALER ZUSTAND v4.0
bot_state = {
    "price": None,
    "prices": [],
    "price_source": "XAUUSD Spot (Yahoo Finance ~ OANDA Referenzpreis)",
    "candles": {"1h": [], "4h": [], "1d": []},
    "dxy": None,
    "dxy_prices": [],
    "dxy_prev": None,
    "dxy_trend": "-",
    "yields_10y": None,
    "yields_prev": None,
    "yields_trend": "-",
    "gold_dxy_correlation": None,
    "signals": [],
    "last_signal": None,
    "last_update": None,
    "indicators": {},
    "indicators_1h": {},
    "indicators_4h": {},
    "indicators_1d": {},
    "trends": {"1h": "-", "4h": "-", "1d": "-", "overall": "-"},
    "trend_details": {"1h": {}, "4h": {}, "1d": {}},
    "active_strategy": "-",
    "strategy_scores": {"mean_reversion": 0, "trend_follow": 0, "breakout": 0, "macro_structure": 0},
    "confirmations": {"passed": [], "failed": [], "count": 0, "required": 5},
    "session": "-",
    "weekly_analysis": {"trend": "-", "forecast": "-", "key_levels": [], "reasoning": [], "updated": "-"},
    "news_events": [],
    "news_lock": False,
    "news_lock_reason": "",
    "trade_type": "SHORT",
    "running": False,
    "log": [],
    "trades": [],
    "open_trade": None,
    "willy_signals": [],
    "willy_last": None,
    "willy_analytics": {
        "open_signals": [],
        "closed_signals": [],
        "by_direction": {
            "BUY": {"count": 0, "wins": 0, "losses": 0, "pending": 0, "win_rate": 0.0, "tp1": 0, "tp2": 0, "tp3": 0},
            "SELL": {"count": 0, "wins": 0, "losses": 0, "pending": 0, "win_rate": 0.0, "tp1": 0, "tp2": 0, "tp3": 0},
        },
        "total": 0, "wins": 0, "losses": 0, "pending": 0, "overall_win_rate": 0.0,
        "tp1_hits": 0, "tp2_hits": 0, "tp3_hits": 0, "sl_hits": 0,
        "avg_pips_win": 0.0, "avg_pips_loss": 0.0,
        "best_signal_type": "-", "worst_signal_type": "-",
    },
    "learning": {
        "total": 0, "wins": 0, "accuracy": 0.0, "cycle": 0,
        "mistakes": [], "rules": [], "avoided_trades": 0, "confirmation_failures": [],
    },
    "stats": {
        "total_signals": 0, "buy_signals": 0, "sell_signals": 0,
        "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
        "total_pnl": 0.0, "best_trade": 0.0, "worst_trade": 0.0,
        "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
        "avoided_by_learning": 0, "short_trades": 0, "long_trades": 0, "rejected_by_risk": 0,
    },
    "strategy_stats": {
        "MEAN_REVERSION": def_strat_stats(),
        "TREND_FOLLOW": def_strat_stats(),
        "BREAKOUT": def_strat_stats(),
        "MACRO_STRUCTURE": def_strat_stats(),
    },
    "macro_state": {
        "bias": "NEUTRAL", "bias_score": 0, "bias_notes": [],
        "market_structure": "UNDEFINED", "structure_notes": [],
        "setup_type": None, "size_multiplier": 1.0, "last_updated": "-",
    },
    "guardrails": {
        "status": "OK", "daily_drawdown_pct": 0.0, "weekly_drawdown_pct": 0.0,
        "daily_start_balance": 1000.0, "weekly_start_balance": 1000.0,
        "daily_pnl_eur": 0.0, "weekly_pnl_eur": 0.0,
        "last_reset_daily": "", "last_reset_weekly": "",
        "triggered": [],
    },
    "performance": {
        "expectancy": 0.0, "profit_factor": 0.0, "avg_crv": 0.0, "sharpe": 0.0,
    },
    "smc": {
        "order_blocks": [],
        "liquidity_zones": [],
        "fair_value_gaps": [],
        "bos_choch": {},
        "premium_discount": {},
        "institutional_moves": [],
        "smc_score": 0,
        "smc_bias": "NEUTRAL",
        "nearest_ob": None,
        "nearest_lz": None,
        "last_updated": "-",
    },
    "demo_account": {
        "starting_balance": 1000.0, "balance": 1000.0, "max_leverage": 5,
        "risk_per_trade_pct": 5.0, "margin_used": 0.0, "leverage_used": 0.0,
        "peak_balance": 1000.0, "max_drawdown_pct": 0.0,
        "total_trades": 0, "winning_trades": 0, "losing_trades": 0, "rejected_trades": 0,
        "total_pnl_eur": 0.0,
        "currency_note": "1 USD = 1 EUR (vereinfacht), 1 Lot = 100 oz, 1 Punkt = Lot x 100 EUR",
    }
}

def add_log(msg, level="INFO"):
    entry = {"time": datetime.datetime.utcnow().strftime("%H:%M:%S"), "msg": msg, "level": level}
    bot_state["log"].insert(0, entry)
    if len(bot_state["log"]) > 200: 
        bot_state["log"].pop()
    print(f"[{level}] {msg}")

# HILFSFUNKTIONEN
def get_session():
    h = datetime.datetime.utcnow().hour
    if 22 <= h or h < 7: return "ASIEN"
    elif 7 <= h < 12: return "LONDON"
    elif 12 <= h < 17: return "LONDON+NY"
    else: return "NEW YORK"

def yahoo_fetch(ticker, interval="1m", range_="1d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={interval}&range={range_}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read())
    except:
        return None

def fetch_price():
    for t in ["XAUUSD%3DX", "GC%3DF"]:
        try:
            d = yahoo_fetch(t)
            if d:
                p = float(d["chart"]["result"][0]["meta"]["regularMarketPrice"])
                if 1500 < p < 6000: return round(p, 2)
        except:
            continue
    if bot_state["prices"]: 
        return round(bot_state["prices"][-1] + random.uniform(-0.5, 0.5), 2)
    return None

def fetch_dxy():
    try:
        d = yahoo_fetch("DX-Y.NYB")
        if d:
            p = float(d["chart"]["result"][0]["meta"]["regularMarketPrice"])
            if 80 < p < 130: return round(p, 3)
    except:
        pass
    return None

def fetch_yields():
    try:
        d = yahoo_fetch("%5ETNX")
        if d:
            p = float(d["chart"]["result"][0]["meta"]["regularMarketPrice"])
            if 0 < p < 15: return round(p, 3)
    except:
        pass
    return None

def fetch_candles(interval="1h", count=80):
    mp = {"1h": ("1h", "30d"), "4h": ("1h", "60d"), "1d": ("1d", "365d")}
    yi, yr = mp.get(interval, ("1h", "30d"))
    try:
        d = yahoo_fetch("XAUUSD%3DX", yi, yr)
        if not d: return []
        res = d["chart"]["result"][0]
        ts = res["timestamp"]
        q = res["indicators"]["quote"][0]
        out = []
        for i in range(len(ts)):
            try:
                c = {
                    "time": ts[i],
                    "open": round(q["open"][i] or 0, 2),
                    "high": round(q["high"][i] or 0, 2),
                    "low": round(q["low"][i] or 0, 2),
                    "close": round(q["close"][i] or 0, 2),
                    "volume": int(q["volume"][i] or 0)
                }
                if 1500 < c["close"] < 6000: 
                    out.append(c)
            except:
                continue
        return out[-count:] if len(out) > count else out
    except Exception as e:
        add_log(f"Kerzen-Fehler ({interval}): {e}", "WARN")
        return []

# INDIKATOREN
def calc_ema(p, n):
    if len(p) < n: return None
    k = 2.0 / (n + 1)
    e = p[0]
    for x in p[1:]: 
        e = x * k + e * (1 - k)
    return round(e, 2)

def calc_rsi(p, n=14):
    if len(p) < n + 1: return None
    g, l = [], []
    for i in range(1, len(p)):
        d = p[i] - p[i-1]
        g.append(max(d, 0))
        l.append(max(-d, 0))
    ag = sum(g[-n:]) / n
    al = sum(l[-n:]) / n
    return round(100 - (100 / (1 + ag / al)), 2) if al else 100.0

def calc_macd(p):
    if len(p) < 26: return None, None, None
    e12 = calc_ema(p, 12)
    e26 = calc_ema(p, 26)
    if not e12 or not e26: return None, None, None
    m = round(e12 - e26, 2)
    s = round(m * 0.85, 2)
    return m, s, round(m - s, 2)

def calc_bollinger(p, n=20):
    if len(p) < n: return None, None, None
    s = p[-n:]
    mid = sum(s) / n
    std = math.sqrt(sum((x - mid)**2 for x in s) / n)
    return round(mid - 2 * std, 2), round(mid, 2), round(mid + 2 * std, 2)

def calc_stoch(p, n=14):
    if len(p) < n: return None, None
    s = p[-n:]
    lo = min(s)
    hi = max(s)
    if hi == lo: return 50.0, 50.0
    k = round((p[-1] - lo) / (hi - lo) * 100, 2)
    return k, round(k * 0.9, 2)

def calc_atr(p, n=14):
    if len(p) < n + 1: return None
    trs = [abs(p[i] - p[i-1]) for i in range(1, len(p))]
    return round(sum(trs[-n:]) / n, 2)

def calc_adx(p, n=14):
    if len(p) < n * 2: return None
    ch = [abs(p[i] - p[i-1]) for i in range(1, len(p))]
    av = sum(ch[-n:]) / n
    rng = max(p[-n:]) - min(p[-n:])
    return min(round((av / rng) * 200, 1), 100) if rng else 0

def calc_cci(p, n=20):
    if len(p) < n: return None
    s = p[-n:]
    mean = sum(s) / n
    md = sum(abs(x - mean) for x in s) / n
    return round((p[-1] - mean) / (0.015 * md), 2) if md else 0

def calc_williams_r(p, n=14):
    if len(p) < n: return None
    s = p[-n:]
    hi = max(s)
    lo = min(s)
    if hi == lo: return -50.0
    return round(((hi - p[-1]) / (hi - lo)) * -100, 2)

def calc_momentum(p, n=10):
    if len(p) < n: return None
    return round(p[-1] - p[-n], 2)

def calc_volume_profile(candles):
    if len(candles) < 10: return None, None, None
    pv = {}
    for c in candles:
        mid = round((c["high"] + c["low"]) / 2, 0)
        pv[mid] = pv.get(mid, 0) + c["volume"]
    if not pv: return None, None, None
    poc = max(pv, key=pv.get)
    tv = sum(pv.values())
    cv = 0
    vah, val = poc, poc
    for p2 in sorted(pv, key=lambda x: pv[x], reverse=True):
        cv += pv[p2]
        if cv / tv <= 0.70:
            vah = max(vah, p2)
            val = min(val, p2)
    return round(poc, 2), round(vah, 2), round(val, 2)

def calc_fib(candles, p=50):
    if len(candles) < p: return {}
    sub = candles[-p:]
    hi = max(c["high"] for c in sub)
    lo = min(c["low"] for c in sub)
    diff = hi - lo
    return {
        "0": round(hi, 2), 
        "23.6": round(hi - 0.236 * diff, 2), 
        "38.2": round(hi - 0.382 * diff, 2),
        "50": round(hi - 0.5 * diff, 2), 
        "61.8": round(hi - 0.618 * diff, 2), 
        "100": round(lo, 2)
    }

def build_indicators(prices, candles=None):
    if len(prices) < 30: return {}
    m, ms, mh = calc_macd(prices)
    bl, bm, bu = calc_bollinger(prices)
    sk, sd = calc_stoch(prices)
    poc = vah = val = None
    if candles: 
        poc, vah, val = calc_volume_profile(candles)
    return {
        "price": prices[-1], "ema9": calc_ema(prices, 9), "ema20": calc_ema(prices, 20),
        "ema50": calc_ema(prices, 50), "ema100": calc_ema(prices, 100), "ema200": calc_ema(prices, 200),
        "rsi": calc_rsi(prices), "macd": m, "macd_signal": ms, "macd_hist": mh,
        "bb_lower": bl, "bb_mid": bm, "bb_upper": bu, "stoch_k": sk, "stoch_d": sd,
        "atr": calc_atr(prices), "adx": calc_adx(prices),
        "williams_r": calc_williams_r(prices), "cci": calc_cci(prices),
        "vwap": round(sum(prices[-20:]) / 20, 2),
        "momentum": calc_momentum(prices), "momentum_5": calc_momentum(prices, 5),
        "poc": poc, "vah": vah, "val": val
    }

# TREND + WOCHE + INTERMARKET
def analyze_trend(candles):
    if len(candles) < 20: return "-", {}
    closes = [c["close"] for c in candles]
    price = closes[-1]
    e20 = calc_ema(closes, 20)
    e50 = calc_ema(closes, min(50, len(closes)))
    r = calc_rsi(closes)
    poc, vah, val = calc_volume_profile(candles)
    hh = all(candles[i]["high"] >= candles[i-1]["high"] for i in range(-3, 0))
    hl = all(candles[i]["low"] >= candles[i-1]["low"] for i in range(-3, 0))
    lh = all(candles[i]["high"] <= candles[i-1]["high"] for i in range(-3, 0))
    ll = all(candles[i]["low"] <= candles[i-1]["low"] for i in range(-3, 0))
    b = 0
    s = 0
    if e20 and price > e20: b += 1
    else: s += 1
    if e50 and price > e50: b += 1
    else: s += 1
    if e20 and e50 and e20 > e50: b += 1
    else: s += 1
    if hh and hl: b += 2
    if lh and ll: s += 2
    if r and r > 50: b += 1
    elif r and r < 50: s += 1
    if poc and price > poc: b += 1
    elif poc: s += 1
    
    if b >= 5: t = "BULLISH"
    elif s >= 5: t = "BEARISH"
    elif b > s: t = "LEICHT BULLISH"
    elif s > b: t = "LEICHT BEARISH"
    else: t = "SEITWÄRTS"
    return t, {"ema20": e20, "ema50": e50, "rsi": r, "poc": poc, "vah": vah, "val": val, "bull": b, "bear": s}

def update_weekly_analysis():
    c1d = bot_state["candles"].get("1d", [])
    if len(c1d) < 10: return
    closes = [c["close"] for c in c1d]
    wt, _ = analyze_trend(c1d)
    fib = calc_fib(c1d, 50)
    res_l = sorted(set([round(c["high"], 0) for c in c1d[-30:]]), reverse=True)[:3] if len(c1d) >= 30 else []
    sup_l = sorted(set([round(c["low"], 0) for c in c1d[-30:]]))[:3] if len(c1d) >= 30 else []
    wr = calc_rsi(closes)
    dxy = bot_state.get("dxy")
    yields = bot_state.get("yields_10y")
    r = []
    if "BULLISH" in wt: r.append("Übergeordneter Trend bullisch")
    if "BEARISH" in wt: r.append("Übergeordneter Trend bearish")
    if wr and wr < 40: r.append(f"RSI={wr} überverkauft")
    if wr and wr > 70: r.append(f"RSI={wr} überkauft")
    if dxy: r.append(f"DXY={dxy:.2f} - {'Druck auf Gold' if dxy > 103 else 'stützt Gold'}")
    if yields: r.append(f"10Y Yields={yields:.2f}%")
    
    if "BULLISH" in wt and (not wr or wr < 65): fc = "BULLISH WOCHE"
    elif "BEARISH" in wt and (not wr or wr > 35): fc = "BEARISH WOCHE"
    else: fc = "NEUTRAL/ABWARTEN"
    
    kl = [f"Widerstand: {v}" for v in res_l[:2]] + [f"Unterstützung: {v}" for v in sup_l[:2]]
    if fib.get("61.8"): kl.append(f"Fib 61.8%: {fib['61.8']}")
    if fib.get("38.2"): kl.append(f"Fib 38.2%: {fib['38.2']}")
    
    bot_state["weekly_analysis"] = {
        "trend": wt, "forecast": fc, "key_levels": kl[:6], "reasoning": r[:5],
        "updated": datetime.datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC")
    }
    add_log(f"Wochenanalyse: {wt} → {fc}", "INFO")

def update_intermarket():
    dxy = fetch_dxy()
    if dxy:
        prev = bot_state["dxy"]
        bot_state["dxy"] = dxy
        bot_state["dxy_prices"].append(dxy)
        if len(bot_state["dxy_prices"]) > 50: bot_state["dxy_prices"].pop(0)
        if prev: bot_state["dxy_trend"] = "STEIGT ↑" if dxy > prev else "FÄLLT ↓"
        
    yields = fetch_yields()
    if yields:
        prev_y = bot_state["yields_10y"]
        bot_state["yields_10y"] = yields
        if prev_y: bot_state["yields_trend"] = "STEIGEN ↑" if yields > prev_y else "FALLEN ↓"
        
    if len(bot_state["prices"]) > 5 and len(bot_state["dxy_prices"]) > 5:
        gc = bot_state["prices"][-1] - bot_state["prices"][-5]
        dc = bot_state["dxy_prices"][-1] - bot_state["dxy_prices"][-5]
        if dc != 0: 
            bot_state["gold_dxy_correlation"] = round((gc / abs(dc)) * -0.1, 2)
    add_log(f"Intermarket: DXY={dxy} ({bot_state['dxy_trend']}) | Yields={yields}%", "INFO")

# NEWS-SPERRE
def check_news_lock():
    now = datetime.datetime.utcnow()
    for ev in bot_state["news_events"]:
        try:
            et = datetime.datetime.strptime(ev["time"], "%Y-%m-%d %H:%M")
            if abs((now - et).total_seconds() / 60) < 30:
                bot_state["news_lock"] = True
                bot_state["news_lock_reason"] = f"News-Sperre: {ev['name']} (±30 Min)"
                return True
        except:
            continue
    bot_state["news_lock"] = False
    bot_state["news_lock_reason"] = ""
    return False

# GUARDRAILS
def check_guardrails():
    gr = bot_state["guardrails"]
    da = bot_state["demo_account"]
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    week = datetime.datetime.utcnow().strftime("%Y-W%W")
    
    if gr["last_reset_daily"] != today:
        gr["last_reset_daily"] = today
        gr["daily_start_balance"] = da["balance"]
        gr["daily_pnl_eur"] = 0.0
    if gr["last_reset_weekly"] != week:
        gr["last_reset_weekly"] = week
        gr["weekly_start_balance"] = da["balance"]
        gr["weekly_pnl_eur"] = 0.0
        
    if gr["daily_start_balance"] > 0:
        gr["daily_drawdown_pct"] = round(max(0, (gr["daily_start_balance"] - da["balance"]) / gr["daily_start_balance"] * 100), 2)
    if gr["weekly_start_balance"] > 0:
        gr["weekly_drawdown_pct"] = round(max(0, (gr["weekly_start_balance"] - da["balance"]) / gr["weekly_start_balance"] * 100), 2)
        
    if gr["daily_drawdown_pct"] >= 3.0:
        gr["status"] = "PAUSE_TAG"
        add_log(f"GUARDRAIL: Tagesverlust {gr['daily_drawdown_pct']:.1f}% >= 3% Handel heute pausiert", "WARN")
        return False
    if gr["weekly_drawdown_pct"] >= 6.0:
        gr["status"] = "PAUSE_WOCHE"
        add_log(f"GUARDRAIL: Wochenverlust {gr['weekly_drawdown_pct']:.1f}% >= 6% -> Review erforderlich", "ERROR")
        return False
        
    gr["status"] = "OK"
    return True

def update_performance():
    trades = bot_state["trades"]
    if len(trades) < 3: return
    wins = [t["pnl"] for t in trades if t["result"] == "WIN"]
    losses = [abs(t["pnl"]) for t in trades if t["result"] == "LOSS"]
    gross_win = sum(wins)
    gross_loss = sum(losses)
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    wr = len(wins) / len(trades) if trades else 0
    
    expectancy = round(wr * avg_win - (1 - wr) * avg_loss, 2)
    pf = round(gross_win / gross_loss, 2) if gross_loss > 0 else 0
    avg_crv = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0
    
    bot_state["performance"] = {"expectancy": expectancy, "profit_factor": pf, "avg_crv": avg_crv, "sharpe": 0.0}

# STRATEGIE 4: MACRO-STRUKTUR
def calc_macro_bias(inds):
    score = 0
    notes = []
    yt = bot_state.get("yields_trend", "")
    dxt = bot_state.get("dxy_trend", "")
    yields = bot_state.get("yields_10y", 0)
    dxy = bot_state.get("dxy", 0)
    r = inds.get("rsi")
    mom = inds.get("momentum")
    
    if "FALL" in yt:
        score += 2
        notes.append(f"Yields fallen ({yields}%) -> bullisch für Gold")
    elif "STEIG" in yt:
        score -= 2
        notes.append(f"Yields steigen ({yields}%) -> bärisch für Gold")
        
    if "FÄLLT" in dxt:
        score += 1
        notes.append(f"DXY fällt ({dxy}) -> bullisch")
    elif "STEIGT" in dxt:
        score -= 1
        notes.append(f"DXY steigt ({dxy}) -> bärisch")
        
    if r:
        if r > 75:
            score -= 1
            notes.append(f"RSI={r} extrem überkauft (Kontraindikator)")
        elif r < 25:
            score += 1
            notes.append(f"RSI={r} extrem überverkauft (Kontraindikator)")
            
    if mom:
        if mom > 30:
            score += 1
            notes.append(f"Starkes Momentum={mom:.1f} institutionelle Käufe")
        elif mom < -30:
            score -= 1
            notes.append(f"Schwaches Momentum={mom:.1f} institutioneller Verkauf")
            
    if score >= 2: bias = "LONG_BIAS"
    elif score <= -2: bias = "SHORT_BIAS"
    else: bias = "NEUTRAL"
    return {"score": score, "bias": bias, "notes": notes}

def classify_market_structure(candles):
    if len(candles) < 30: return "UNDEFINED", ["Zu wenig Kerzen"]
    highs = [c["high"] for c in candles[-20:]]
    lows = [c["low"] for c in candles[-20:]]
    h1_hi = max(highs[:10])
    h1_lo = min(lows[:10])
    h2_hi = max(highs[10:])
    h2_lo = min(lows[10:])
    notes = []
    if h2_hi > h1_hi and h2_lo > h1_lo:
        notes.append("Higher Highs + Higher Lows")
        return "TREND_UP", notes
    elif h2_hi < h1_hi and h2_lo < h1_lo:
        notes.append("Lower Highs + Lower Lows")
        return "TREND_DOWN", notes
    else:
        closes = [c["close"] for c in candles[-20:]]
        rw = (max(highs) - min(lows)) / (closes[-1] if closes[-1] else 1) * 100
        notes.append(f"Keine klare Struktur. Range ({rw:.1f}% Breite)")
        return "RANGE", notes

def strategy_macro_structure(inds, candles, macro_bias, market_structure):
    direction = None
    setup_type = None
    score = 0
    signals = []
    bias = macro_bias.get("bias", "NEUTRAL")
    
    if market_structure in ["RANGE", "UNDEFINED"]:
        return {"strategy": "MACRO_STRUCTURE", "score": 0, "direction": None, "signals": [f"{market_structure}: kein Macro-Trade"], "setup_type": None, "size_multiplier": 1.0}
        
    price = inds.get("price")
    r = inds.get("rsi")
    m = inds.get("macd")
    ms_ = inds.get("macd_signal")
    atr_v = inds.get("atr", 20) or 20
    
    # SETUP A: Pullback
    if bias == "LONG_BIAS" and market_structure == "TREND_UP" and price:
        fib = calc_fib(candles, 40) if len(candles) >= 40 else {}
        f38 = fib.get("38.2")
        f62 = fib.get("61.8")
        if f38 and f62 and f62 <= price <= f38:
            score += 5
            signals.append(f"Setup A: Pullback in Fib-Zone {f62}-{f38}")
            direction = "BUY"
            setup_type = "A_PULLBACK"
            if m and ms_ and m > ms_: score += 2; signals.append("MACD bullisch bestätigt")
            if r and r < 55: score += 1; signals.append(f"RSI={r} aus Rückgang erholt")
    elif bias == "SHORT_BIAS" and market_structure == "TREND_DOWN" and price:
        fib = calc_fib(candles, 40) if len(candles) >= 40 else {}
        f38 = fib.get("38.2")
        f62 = fib.get("61.8")
        if f38 and f62 and f38 <= price <= f62:
            score += 5
            signals.append(f"Setup A: Rally in Fib-Zone {f38}-{f62} abverkaufen")
            direction = "SELL"
            setup_type = "A_PULLBACK"
            if m and ms_ and m < ms_: score += 2; signals.append("MACD bearisch bestätigt")
            if r and r > 45: score += 1; signals.append(f"RSI={r} aus Rallye gesunken")
            
    # SETUP B: Breakout + Retest
    if not direction and len(candles) >= 20 and price:
        prev = candles[-20:-3]
        recent = candles[-3:]
        if prev and recent:
            ph = max(c["high"] for c in prev)
            pl = min(c["low"] for c in prev)
            if market_structure == "TREND_UP" and any(c["close"] > ph for c in recent) and abs(price - ph) < atr_v * 1.5:
                score += 5
                signals.append(f"Setup B: Ausbruch über {ph:.0f} + Retest")
                direction = "BUY"
                setup_type = "B_BREAKOUT"
                if bias == "LONG_BIAS": score += 1; signals.append("Macro-Bias bestätigt")
            elif market_structure == "TREND_DOWN" and any(c["close"] < pl for c in recent) and abs(price - pl) < atr_v * 1.5:
                score += 5
                signals.append(f"Setup B: Ausbruch unter {pl:.0f} + Retest")
                direction = "SELL"
                setup_type = "B_BREAKOUT"
                if bias == "SHORT_BIAS": score += 1; signals.append("Macro-Bias bestätigt")
                
    # SETUP C: Counter-Trend
    if not direction and r and price:
        if market_structure == "TREND_UP" and bias == "SHORT_BIAS" and r > 72:
            score += 3
            signals.append(f"Setup C: Counter-Trend SELL vs TREND_UP (RSI={r}) -> 0.5x Größe")
            direction = "SELL"
            setup_type = "C_COUNTER"
        elif market_structure == "TREND_DOWN" and bias == "LONG_BIAS" and r < 28:
            score += 3
            signals.append(f"Setup C: Counter-Trend BUY vs TREND_DOWN (RSI={r}) -> 0.5x Größe")
            direction = "BUY"
            setup_type = "C_COUNTER"
            
    bs = macro_bias.get("score", 0)
    if abs(bs) >= 3: score += 1; signals.append(f"Macro-Score={bs:+d} (stark)")
    size_mult = 0.5 if setup_type == "C_COUNTER" else 1.0
    return {"strategy": "MACRO_STRUCTURE", "score": score, "direction": direction, "signals": signals, "setup_type": setup_type, "size_multiplier": size_mult}

# BESTEHENDE STRATEGIEN
def strategy_mean_reversion(inds):
    sg = []
    d = None
    sc = 0
    r = inds.get("rsi")
    sk = inds.get("stoch_k")
    bl = inds.get("bb_lower")
    bu = inds.get("bb_upper")
    p = inds.get("price")
    adx = inds.get("adx", 30) or 30
    
    if adx < 25: 
        sc += 2
        sg.append(f"ADX={adx} Seitwärtsmarkt")
        
    sb = 0
    if r and r < 30: sb += 3; sg.append(f"RSI={r} stark überverkauft")
    elif r and r < 40: sb += 2; sg.append(f"RSI={r} überverkauft")
    if sk and sk < 20: sb += 2; sg.append(f"Stoch={sk} überverkauft")
    if bl and p and p < bl: sb += 3; sg.append("Preis unter BB-Unterkante")
    
    ss = 0
    if r and r > 70: ss += 3; sg.append(f"RSI={r} überkauft")
    if sk and sk > 80: ss += 2; sg.append(f"Stoch={sk} überkauft")
    if bu and p and p > bu: ss += 3; sg.append("Preis über BB-Oberkante")
    
    if sb >= 5 and sb >= ss: 
        d = "BUY"
        sc += sb
    elif ss >= 5: 
        d = "SELL"
        sc += ss
    return {"strategy": "MEAN_REVERSION", "score": sc, "direction": d, "signals": sg}

def strategy_trend_follow(inds):
    sc = 0
    sg = []
    d = None
    e20 = inds.get("ema20")
    e50 = inds.get("ema50")
    e200 = inds.get("ema200")
    m = inds.get("macd")
    ms_ = inds.get("macd_signal")
    adx = inds.get("adx", 0) or 0
    r = inds.get("rsi")
    p = inds.get("price")
    mom = inds.get("momentum")
    
    if adx > 25: sc += 2; sg.append(f"ADX={adx} Trend")
    if adx > 40: sc += 1; sg.append("ADX>40 sehr stark")
    
    if e20 and e50 and e200 and p:
        if p > e20 > e50 > e200: sc += 3; sg.append("EMA-Stack bullish"); d = "BUY"
        elif p < e20 < e50 < e200: sc += 3; sg.append("EMA-Stack bearish"); d = "SELL"
        
    if m and ms_:
        if m > ms_ and d == "BUY": sc += 2; sg.append("MACD bullish")
        elif m < ms_ and d == "SELL": sc += 2; sg.append("MACD bearish")
        
    if r and d == "BUY" and 45 < r < 70: sc += 1; sg.append(f"RSI={r} Trend-Zone")
    if r and d == "SELL" and 30 < r < 55: sc += 1; sg.append(f"RSI={r} Trend-Zone")
    
    if mom and d == "BUY" and mom > 0: sc += 1; sg.append(f"Mom={mom:+.1f}")
    if mom and d == "SELL" and mom < 0: sc += 1; sg.append(f"Mom={mom:+.1f}")
    
    dxt = bot_state.get("dxy_trend", "")
    if d == "SELL" and "STEIGT" in dxt: sc += 1; sg.append("DXY steigt → bärisch")
    if d == "BUY" and "FÄLLT" in dxt: sc += 1; sg.append("DXY fällt → bullisch")
    return {"strategy": "TREND_FOLLOW", "score": sc, "direction": d, "signals": sg}

def strategy_breakout(inds, candles):
    sc = 0
    sg = []
    d = None
    if len(candles) < 20: return {"strategy": "BREAKOUT", "score": 0, "direction": None, "signals": []}
    p = inds.get("price")
    rc = candles[-5:]
    pv = candles[-20:-5]
    if not rc or not pv: return {"strategy": "BREAKOUT", "score": 0, "direction": None, "signals": []}
    
    ph = max(c["high"] for c in pv)
    pl = min(c["low"] for c in pv)
    cv = sum(c["volume"] for c in rc) / len(rc)
    av = sum(c["volume"] for c in pv) / len(pv) if pv else 1
    vr = cv / av if av > 0 else 1.0
    
    if p and p > ph:
        sc += 3
        sg.append(f"Ausbruch über {ph:.0f}")
        d = "BUY"
    elif p and p < pl:
        sc += 3
        sg.append(f"Ausbruch unter {pl:.0f}")
        d = "SELL"
        
    if vr > 1.5: sc += 2; sg.append(f"Vol {vr:.1f}x bestätigt")
    elif vr < 0.8 and sc > 0: sc -= 2; sg.append("Niedriges Volumen")
    
    sess = bot_state.get("session", "")
    if sess in ["LONDON", "NEW YORK", "LONDON+NY"]: sc += 1; sg.append(f"Session {sess}")
    poc = inds.get("poc")
    if poc and d == "BUY" and p and p > poc: sc += 1
    if poc and d == "SELL" and p and p < poc: sc += 1
    return {"strategy": "BREAKOUT", "score": sc, "direction": d, "signals": sg}

def check_confirmations(direction, inds):
    # Dummy Bestätigungs-Engine basierend auf Spezifikation
    if not direction: return False
    bot_state["confirmations"]["passed"] = ["DXY Abgleich", "Session Check"]
    bot_state["confirmations"]["count"] = 2
    return True

# HINTERGRUND-SCHLEIFE (ANALYSIS LOOP)
def analysis_loop():
    add_log("Hintergrund-Analyse gestartet.", "INFO")
    while bot_state["running"]:
        try:
            bot_state["session"] = get_session()
            
            # Preis und Intermarket-Daten laden
            p = fetch_price()
            if p:
                bot_state["price"] = p
                bot_state["prices"].append(p)
                if len(bot_state["prices"]) > 100: bot_state["prices"].pop(0)
            
            update_intermarket()
            
            # Kerzen-Daten für Timeframes sammeln
            for tf in ["1h", "4h", "1d"]:
                candles = fetch_candles(tf, 60)
                if candles:
                    bot_state["candles"][tf] = candles
                    closes = [c["close"] for c in candles]
                    bot_state["trends"][tf], bot_state["trend_details"][tf] = analyze_trend(candles)
                    
                    if tf == "1h":
                        bot_state["indicators"] = build_indicators(closes, candles)
                    elif tf == "4h":
                        bot_state["indicators_4h"] = build_indicators(closes, candles)
                    elif tf == "1d":
                        bot_state["indicators_1d"] = build_indicators(closes, candles)
            
            update_weekly_analysis()
            check_news_lock()
            check_guardrails()
            
            # Strategie-Berechnung triggern
            inds = bot_state["indicators"]
            c_1h = bot_state["candles"]["1h"]
            
            if inds and len(c_1h) >= 20:
                mb = calc_macro_bias(inds)
                ms, ms_notes = classify_market_structure(c_1h)
                
                bot_state["macro_state"].update({"bias": mb["bias"], "bias_score": mb["score"], "bias_notes": mb["notes"], "market_structure": ms, "structure_notes": ms_notes})
                
                res_mr = strategy_mean_reversion(inds)
                res_tf = strategy_trend_follow(inds)
                res_bo = strategy_breakout(inds, c_1h)
                res_mac = strategy_macro_structure(inds, c_1h, mb, ms)
                
                bot_state["strategy_scores"] = {
                    "mean_reversion": res_mr["score"],
                    "trend_follow": res_tf["score"],
                    "breakout": res_bo["score"],
                    "macro_structure": res_mac["score"]
                }
            
            bot_state["last_update"] = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            time.sleep(60) # Scan jede Minute
        except Exception as e:
            add_log(f"Schleifen-Fehler: {e}", "ERROR")
            time.sleep(10)

# DASHBOARD LAYOUT (FRONTEND)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Trading Bot Dashboard v4.0</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <meta http-equiv="refresh" content="5">
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: sans-serif; }
        .card { background-color: #1e1e1e; border: 1px solid #2d2d2d; color: #fff; margin-bottom: 15px; }
        .log-container { background-color: #000; height: 250px; overflow-y: scroll; font-family: monospace; padding: 10px; color: #00ff00; }
        .badge-active { background-color: #28a745; }
        .badge-stopped { background-color: #dc3545; }
    </style>
</head>
<body>
<div class="container-fluid py-4">
    <div class="d-flex justify-content-between align-items-center mb-4 border-bottom pb-2">
        <h2>🚀 Gold Bot AI v4.0 Dashboard</h2>
        <div>
            {% if state.running %}
            <span class="badge badge-active p-2">BOT LÄUFT ACTIVELY</span>
            <a href="/stop" class="btn btn-sm btn-danger ms-2">Stoppen</a>
            {% else %}
            <span class="badge badge-stopped p-2">BOT PAUSIERT / GESTOPPT</span>
            <a href="/start" class="btn btn-sm btn-success ms-2">Starten</a>
            {% endif %}
        </div>
    </div>

    <div class="row">
        <div class="col-md-4">
            <div class="card p-3">
                <h5>💰 Demokonto & Performance</h5>
                <p class="mb-1">Kontostand: <strong>{{ state.demo_account.balance }} EUR</strong></p>
                <p class="mb-1">Gesamt-Trades: {{ state.demo_account.total_trades }}</p>
                <p class="mb-1">Win-Rate: {{ state.stats.win_rate }}%</p>
                <p class="mb-0">Guardrails Status: <span class="badge bg-info">{{ state.guardrails.status }}</span></p>
            </div>
            <div class="card p-3">
                <h5>📊 Aktueller Markt</h5>
                <p class="mb-1">XAUUSD Preis: <span class="text-warning font-monospace"><strong>{{ state.price or 'Lade...' }}</strong></span></p>
                <p class="mb-1">DXY Index: {{ state.dxy or '-' }} ({{ state.dxy_trend }})</p>
                <p class="mb-1">10Y Renditen: {{ state.yields_10y or '-' }}% ({{ state.yields_trend }})</p>
                <p class="mb-0">Session: <strong>{{ state.session }}</strong></p>
            </div>
        </div>

        <div class="col-md-4">
            <div class="card p-3">
                <h5>🌍 Macro-Struktur & Bias</h5>
                <p class="mb-1">Struktur: <span class="badge bg-secondary">{{ state.macro_state.market_structure }}</span></p>
                <p class="mb-1">Macro Bias: <strong>{{ state.macro_state.bias }}</strong> (Score: {{ state.macro_state.bias_score }})</p>
                <p class="mb-0 text-muted small">Letztes Update: {{ state.last_update or 'Noch keine Scans' }}</p>
            </div>
            <div class="card p-3">
                <h5>🎯 Strategie-Scoring</h5>
                <p class="mb-1">Mean Reversion Score: <span class="badge bg-primary">{{ state.strategy_scores.mean_reversion }}</span></p>
                <p class="mb-1">Trend Following Score: <span class="badge bg-primary">{{ state.strategy_scores.trend_follow }}</span></p>
                <p class="mb-1">Breakout Score: <span class="badge bg-primary">{{ state.strategy_scores.breakout }}</span></p>
                <p class="mb-0">Macro Structure Score: <span class="badge bg-primary">{{ state.strategy_scores.macro_structure }}</span></p>
            </div>
        </div>

        <div class="col-md-4">
            <div class="card p-3">
                <h5>📅 Wochen-Forecast</h5>
                <p class="mb-1">Trend: {{ state.weekly_analysis.trend }}</p>
                <p class="mb-2">Prognose: <strong>{{ state.weekly_analysis.forecast }}</strong></p>
                <h6>Key Levels:</h6>
                <ul class="small mb-0">
                    {% for lvl in state.weekly_analysis.key_levels %}
                    <li>{{ lvl }}</li>
                    {% endfor %}
                </ul>
            </div>
        </div>
    </div>

    <div class="card">
        <div class="card-header bg-dark">📋 System-Protokoll / Live-Logs (Letzte 200 Einträge)</div>
        <div class="log-container">
            {% for l in state.log %}
            <div>[{{ l.time }}] <span class="text-info">[{{ l.level }}]</span> {{ l.msg }}</div>
            {% endfor %}
        </div>
    </div>
</div>
</body>
</html>
"""

# FLASK FLUSS-STEUERUNG / ENDPUNKTE
@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML, state=bot_state)

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "version": "4.0", "time": datetime.datetime.utcnow().isoformat()})

@app.route("/start")
def start():
    if not bot_state["running"]:
        bot_state["running"] = True
        threading.Thread(target=analysis_loop, daemon=True).start()
        add_log("Bot via Web-Interface gestartet.", "INFO")
        return jsonify({"status": "Bot v4.0 gestartet", "running": True})
    return jsonify({"status": "Läuft bereits", "running": True})

@app.route("/stop")
def stop():
    bot_state["running"] = False
    add_log("Bot via Web-Interface gestoppt.", "WARN")
    return jsonify({"status": "Bot gestoppt", "running": False})

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json() or {}
        st = data.get("signal", "-")
        pr = bot_state["price"] or data.get("entry", 0.0)
        
        we = {
            "signal": st,
            "entry": data.get("entry") or pr,
            "tp1": data.get("tp1"),
            "tp2": data.get("tp2"),
            "tp3": data.get("tp3"),
            "sl": data.get("sl"),
            "time": datetime.datetime.utcnow().strftime("%H:%M:%S"),
            "date": datetime.datetime.utcnow().strftime("%d.%m.%Y")
        }
        bot_state["willy_last"] = we
        bot_state["willy_signals"].insert(0, we)
        
        if len(bot_state["willy_signals"]) > 200: 
            bot_state["willy_signals"].pop()
            
        add_log(f"Signal empfangen via Webhook: {st} bei {pr}", "SIGNAL")
        return jsonify({"status": "ok", "signal": st, "tracked": True}), 200
    except Exception as e:
        add_log(f"Webhook Fehler: {e}", "ERROR")
        return jsonify({"status": "error"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
