import json, urllib.request
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

class TelegramNotifier:
    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.base = f"https://api.telegram.org/bot{self.token}"

    def send(self, text):
        if not self.token or not self.chat_id:
            return
        try:
            body = json.dumps({
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
            }).encode()
            req = urllib.request.Request(
                f"{self.base}/sendMessage",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            print(f"[Telegram error] {e}")

    def trade_entry(self, name, side, entry, sl, tp, confidence, reason):
        msg = (
            f"🚀 <b>TRADE ENTRY</b>\n"
            f"<b>{name}</b> {side}\n"
            f"Entry: {entry}\n"
            f"SL: {sl} | TP: {tp}\n"
            f"Confidence: {confidence:.0%}\n"
            f"Reason: {reason}"
        )
        self.send(msg)

    def trade_exit(self, name, side, entry, exit_price, pnl):
        emoji = "✅" if pnl > 0 else "❌"
        msg = (
            f"{emoji} <b>TRADE CLOSED</b>\n"
            f"<b>{name}</b> {side}\n"
            f"Entry: {entry} | Exit: {exit_price}\n"
            f"P&L: {pnl:+.2f}"
        )
        self.send(msg)

    def scan_report(self, summary_text):
        self.send(f"🔍 <b>Scan Report</b>\n{summary_text}")

    def error(self, err_text):
        self.send(f"⚠️ <b>Bot Error</b>\n{err_text}")

    def status(self, text):
        self.send(f"ℹ️ {text}")
