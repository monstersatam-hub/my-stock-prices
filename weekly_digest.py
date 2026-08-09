import json
import os
import sys
import urllib.parse
import urllib.request

import yfinance as yf

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("warn: missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID, skip send", file=sys.stderr)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode()
    try:
        urllib.request.urlopen(url, data=data, timeout=10)
        print("sent weekly digest")
    except Exception as e:
        print(f"error sending telegram: {e}", file=sys.stderr)


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def market_snapshot_lines():
    lines = []
    try:
        vix_hist = yf.Ticker("^VIX").history(period="5d")
        vix_last = float(vix_hist["Close"].iloc[-1])
        if vix_last < 18:
            note = "ตลาดสงบมาก (ระวัง Complacency)"
        elif vix_last < 28:
            note = "ระดับปกติ"
        else:
            note = "ผันผวนสูง ระมัดระวัง"
        lines.append(f"VIX: {vix_last:.1f} — {note}")
    except Exception as e:
        print(f"warn: vix fetch failed: {e}", file=sys.stderr)

    try:
        spx_hist = yf.Ticker("^GSPC").history(period="250d")
        last = float(spx_hist["Close"].iloc[-1])
        ma200 = float(spx_hist["Close"].tail(200).mean())
        pos = "เหนือ MA200 (แนวโน้มขาขึ้น)" if last > ma200 else "ต่ำกว่า MA200 (ระวัง)"
        lines.append(f"S&P500: {last:,.0f} — {pos}")
    except Exception as e:
        print(f"warn: spx fetch failed: {e}", file=sys.stderr)

    return lines


def portfolio_lines(prices, portfolio):
    lines = []
    total_value = 0.0
    total_cost = 0.0
    weights = []

    for ticker, pos in portfolio.items():
        p = prices.get(ticker)
        shares = pos.get("shares", 0)
        cost = pos.get("cost", 0)
        value = (shares * p["price"]) if (p and shares) else cost
        total_value += value
        total_cost += cost
        pl = ((value - cost) / cost * 100) if cost else 0.0
        sym = "฿" if (p and p.get("currency") == "THB") else "$"
        lines.append(f"{ticker}: {sym}{value:,.2f}  P/L {pl:+.1f}%")
        weights.append((ticker, value))

    if total_cost:
        total_pl = (total_value - total_cost) / total_cost * 100
        lines.append(f"รวม: ${total_value:,.2f}  P/L {total_pl:+.1f}%")

    warn_lines = []
    if total_value:
        for ticker, value in weights:
            weight = value / total_value * 100
            if weight > 15:
                warn_lines.append(f"{ticker} น้ำหนัก {weight:.1f}% เกิน 15%")

    return lines, warn_lines


def watchlist_zone_lines(prices, alerts_cfg):
    lines = []
    for ticker, rule in alerts_cfg.items():
        p = prices.get(ticker)
        if not p:
            continue
        price = p["price"]
        stop = rule.get("stop_loss")
        target = rule.get("target")
        e_lo = rule.get("entry_low")
        e_hi = rule.get("entry_high")
        if stop is not None and price <= stop:
            lines.append(f"{ticker}: หลุด Stop Loss ({price})")
        elif target is not None and price >= target:
            lines.append(f"{ticker}: ถึง Target ({price})")
        elif e_lo is not None and e_hi is not None and e_lo <= price <= e_hi:
            lines.append(f"{ticker}: อยู่ใน Entry Zone ({price})")
    return lines


def load_alerts_config():
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            url = f"{SUPABASE_URL}/rest/v1/alerts?select=*"
            req = urllib.request.Request(
                url,
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                rows = json.loads(resp.read().decode("utf-8"))
            config = {}
            for row in rows:
                config[row["ticker"]] = {
                    "entry_low": row.get("entry_low"),
                    "entry_high": row.get("entry_high"),
                    "stop_loss": row.get("stop_loss"),
                    "target": row.get("target"),
                }
            return config
        except Exception as e:
            print(f"warn: supabase fetch failed, falling back to local config: {e}", file=sys.stderr)
    return load_json("alerts_config.json", {})


def main():
    prices = load_json("prices.json", {}).get("prices", {})
    portfolio = load_json("portfolio_config.json", {})
    alerts_cfg = load_alerts_config()

    lines = ["สรุปประจำสัปดาห์ — สมุดพกนักลงทุน", ""]

    lines.append("Market Snapshot")
    lines.extend(market_snapshot_lines())
    lines.append("")

    lines.append("Portfolio")
    pf_lines, warn_lines = portfolio_lines(prices, portfolio)
    lines.extend(pf_lines)
    for w in warn_lines:
        lines.append(f"เตือน: {w}")
    lines.append("")

    lines.append("Watchlist Zones")
    zone_lines = watchlist_zone_lines(prices, alerts_cfg)
    if zone_lines:
        lines.extend(zone_lines)
    else:
        lines.append("ไม่มีตัวไหนอยู่ในโซนสำคัญตอนนี้")

    send_telegram("\n".join(lines))


if __name__ == "__main__":
    main()
