import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import yfinance as yf

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# ใช้เฉพาะตอนดึงจาก Supabase ไม่ได้ (เช่น ยังไม่ได้ตั้งค่า Secret หรือ Supabase ล่ม)
FALLBACK_TICKERS = [
    "NVDA",
    "MSFT",
    "V",
    "AVGO",
    "PLTR",
    "UBER",
    "ADVANC.BK",
    "DELTA.BK",
    "KCE.BK",
]


def load_watchlist_tickers():
    """
    ดึงรายชื่อหุ้นจาก Watchlist ในหน้าเว็บ (เก็บอยู่ใน Supabase table app_state,
    key='watchlist') โดยอัตโนมัติ — เพิ่มหุ้นในหน้าเว็บแล้วรอบถัดไปที่ Action รัน
    จะดึงราคาให้เองโดยไม่ต้องมาแก้ไฟล์นี้
    หุ้นตลาดไทย (market == 'TH') จะถูกเติม .BK ต่อท้ายให้อัตโนมัติ
    """
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            url = f"{SUPABASE_URL}/rest/v1/app_state?key=eq.watchlist&select=value"
            req = urllib.request.Request(
                url,
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                rows = json.loads(resp.read().decode("utf-8"))
            if rows and rows[0].get("value"):
                tickers = []
                for s in rows[0]["value"]:
                    t = (s.get("ticker") or "").strip().upper()
                    if not t:
                        continue
                    if s.get("market") == "TH" and not t.endswith(".BK"):
                        t = t + ".BK"
                    tickers.append(t)
                if tickers:
                    print(f"loaded {len(tickers)} tickers from Supabase watchlist: {tickers}")
                    return tickers
        except Exception as e:
            print(f"warn: failed to load tickers from Supabase, using fallback list: {e}", file=sys.stderr)
    print("using fallback static ticker list")
    return FALLBACK_TICKERS


def fetch_all(tickers):
    data = {}
    for t in tickers:
        try:
            tk = yf.Ticker(t)
            hist = tk.history(period="5d")
            if hist.empty:
                print(f"warn: no data for {t}", file=sys.stderr)
                continue
            last_close = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else last_close
            change_pct = (
                ((last_close - prev_close) / prev_close * 100) if prev_close else 0.0
            )
            currency = "THB" if t.endswith(".BK") else "USD"
            key = t.replace(".BK", "")
            data[key] = {
                "price": round(last_close, 2),
                "change_pct": round(change_pct, 2),
                "currency": currency,
            }
            print(f"ok: {key} = {data[key]}")
        except Exception as e:
            print(f"error fetching {t}: {e}", file=sys.stderr)
    return data


def main():
    tickers = load_watchlist_tickers()
    prices = fetch_all(tickers)
    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "prices": prices,
    }
    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"wrote prices.json with {len(prices)} tickers")


if __name__ == "__main__":
    main()
