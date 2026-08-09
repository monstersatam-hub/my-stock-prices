import json
import sys
from datetime import datetime, timezone

import yfinance as yf

# แก้ไขรายชื่อหุ้นตรงนี้ให้ตรงกับ Watchlist ของคุณ
# หุ้นไทยต้องมี .BK ต่อท้าย เช่น ADVANC.BK, DELTA.BK, KCE.BK
TICKERS = [
    "NVDA",
    "MSFT",
    "V",
    "AVGO",
    "PLTR",
    "ADVANC.BK",
    "DELTA.BK",
    "KCE.BK",
]


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
    prices = fetch_all(TICKERS)
    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "prices": prices,
    }
    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"wrote prices.json with {len(prices)} tickers")


if __name__ == "__main__":
    main()
