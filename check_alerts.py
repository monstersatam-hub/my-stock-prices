import json
import os
import sys
import urllib.parse
import urllib.request

CONFIG_FILE = "alerts_config.json"
PRICES_FILE = "prices.json"
STATE_FILE = "alert_state.json"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("warn: missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID, skip send", file=sys.stderr)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode()
    try:
        urllib.request.urlopen(url, data=data, timeout=10)
        print("sent telegram alert")
    except Exception as e:
        print(f"error sending telegram: {e}", file=sys.stderr)


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def main():
    config = load_json(CONFIG_FILE, {})
    prices = load_json(PRICES_FILE, {}).get("prices", {})
    state = load_json(STATE_FILE, {})
    changed = False

    for ticker, rule in config.items():
        p = prices.get(ticker)
        if not p:
            continue
        price = p["price"]
        currency = p.get("currency", "USD")
        sym = "฿" if currency == "THB" else "$"
        prev = state.get(ticker, {})

        stop = rule.get("stop_loss")
        target = rule.get("target")
        e_lo = rule.get("entry_low")
        e_hi = rule.get("entry_high")

        zone = None
        if stop is not None and price <= stop:
            zone = "stop_loss"
        elif target is not None and price >= target:
            zone = "target"
        elif e_lo is not None and e_hi is not None and e_lo <= price <= e_hi:
            zone = "entry_zone"

        # ส่งแจ้งเตือนเฉพาะตอนที่ "เพิ่งเข้าเงื่อนไข" ไม่ส่งซ้ำทุกรอบที่รัน
        if zone and prev.get("zone") != zone:
            messages = {
                "stop_loss": (
                    f"หลุด Stop Loss: {ticker}\n"
                    f"ราคาปัจจุบัน {sym}{price}  (Stop Loss {sym}{stop})\n"
                    f"ทบทวน Exit Plan ตาม Exit Strategy Module ทันที"
                ),
                "target": (
                    f"ถึงเป้าหมาย: {ticker}\n"
                    f"ราคาปัจจุบัน {sym}{price}  (Target {sym}{target})\n"
                    f"พิจารณา Trim หรือ Exit บางส่วนตามแผน"
                ),
                "entry_zone": (
                    f"เข้าสู่ Entry Zone: {ticker}\n"
                    f"ราคาปัจจุบัน {sym}{price}  (โซน {sym}{e_lo}-{sym}{e_hi})\n"
                    f"พิจารณา Scale-in ตาม Entry Strategy"
                ),
            }
            send_telegram(messages[zone])
            state[ticker] = {"zone": zone, "price": price}
            changed = True
        elif not zone and prev.get("zone"):
            # ราคาหลุดออกจากโซนเดิมแล้ว เคลียร์สถานะไว้เพื่อให้แจ้งเตือนใหม่ได้ถ้ากลับเข้ามาอีก
            state[ticker] = {"zone": None, "price": price}
            changed = True

    if changed:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print("alert_state.json updated")
    else:
        print("no alert state changes")


if __name__ == "__main__":
    main()
