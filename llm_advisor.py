import json, urllib.request
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, MAX_RISK_PERCENT

SYSTEM_PROMPT = """You are an SMC/ICT scalping trading bot. Analyze scan data and decide: ENTRY, EXIT, or WAIT.

RULES:
- ENTRY only when M15 CHoCH confirmed AND M1 CHoCH confirms same direction
- ENTRY only during killzones (London 07-10 WAT / NY 12-15 WAT)
- SL below nearest swing low (BUY) or above nearest swing high (SELL)
- Minimum R:R = 1:2
- Max 1% risk per trade
- Max 3 concurrent positions
- Never same symbol twice
- Never revenge trade
- Exit when CHoCH reverses against position

Respond ONLY in this JSON format:
{
  "decision": "ENTRY|EXIT|WAIT",
  "reason": "brief explanation",
  "symbol_id": int,
  "side": "BUY|SELL",
  "entry_price": float,
  "stop_loss": float,
  "take_profit": float,
  "confidence": 0.0-1.0
}"""

class LLMAdvisor:
    def __init__(self):
        self.api_key = LLM_API_KEY
        self.base_url = LLM_BASE_URL.rstrip("/")
        self.model = LLM_MODEL

    def analyze(self, scan_results, active_positions, pending_orders, balance_data, current_hour_wat):
        if self.api_key:
            try:
                return self._llm_call(scan_results, active_positions, pending_orders, balance_data, current_hour_wat)
            except Exception:
                pass
        return self._rule_based(scan_results, active_positions, pending_orders, current_hour_wat)

    def _llm_call(self, scan_results, active_positions, pending_orders, balance_data, current_hour_wat):
        msg = {
            "scan": [{
                "symbol": r.get("symbol_name"),
                "price": r.get("close"),
                "structure": r.get("structure"),
                "choch": r.get("choch"),
                "fvg_count": r.get("fvg_count", 0),
                "m5_structure": r.get("m5", {}).get("structure"),
                "m1_structure": r.get("m1", {}).get("structure"),
                "m1_choch": r.get("m1", {}).get("choch"),
                "mtf_score": r.get("mtf", {}).get("score", 0),
            } for r in scan_results[:8]],
            "positions": active_positions,
            "pending": pending_orders,
            "balance": balance_data,
            "hour_wat": current_hour_wat,
        }
        body = json.dumps({
            "model": self.model, "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(msg)},
            ], "temperature": 0.1, "max_tokens": 300,
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST"
        )
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read())
        return json.loads(data["choices"][0]["message"]["content"])

    def _rule_based(self, scan_results, active_positions, pending_orders, current_hour_wat):
        in_kz = (7 <= current_hour_wat < 10) or (12 <= current_hour_wat < 15)
        if not in_kz:
            return {"decision": "WAIT", "reason": f"WAT {current_hour_wat}:00 — outside killzone", "confidence": 0.0}

        if len(active_positions) >= 3:
            return {"decision": "WAIT", "reason": "Max 3 positions reached", "confidence": 0.0}

        active_symbols = {p.get("symbol") for p in active_positions}
        pending_symbols = {o.get("symbolId") for o in pending_orders}

        candidates = []
        for r in scan_results:
            sid = r.get("symbol_id")

            # Must have M15 CHoCH
            if not r.get("choch"):
                continue
            # Must not already have position or pending on this symbol
            if sid in active_symbols or sid in pending_symbols:
                continue

            m1 = r.get("m1", {})
            # Prefer M1 confirmation, but accept strong M15 alone
            m1_choch = m1.get("choch")
            m1_aligns = m1_choch == r["choch"]

            # Get nearest swing for SL
            price = r.get("close", 0)
            is_bull = r["choch"] == "BULLISH"
            sw_highs = [x for x in r.get("swing_highs", []) if isinstance(x, (int, float))]
            sw_lows = [x for x in r.get("swing_lows", []) if isinstance(x, (int, float))]

            if is_bull and sw_lows:
                nearest_sl = max(x for x in sw_lows if x < price) if any(x < price for x in sw_lows) else min(sw_lows)
            elif not is_bull and sw_highs:
                nearest_sl = min(x for x in sw_highs if x > price) if any(x > price for x in sw_highs) else max(sw_highs)
            else:
                nearest_sl = price * (0.99 if is_bull else 1.01)

            sl_distance = abs(price - nearest_sl)

            # Score: 2 for CHoCH + 1 for M1 confirm + 1 for FVGs + 1 for MTF alignment
            score = 2
            if m1_aligns:
                score += 1
            if r.get("fvg_count", 0) > 0:
                score += 1
            mtf = r.get("mtf", {})
            if mtf.get("score", 0) >= 3:
                score += 1

            candidates.append({
                "score": score,
                "sid": sid,
                "side": "BUY" if is_bull else "SELL",
                "entry": price,
                "sl": nearest_sl,
                "tp": price + (sl_distance * 2) if is_bull else price - (sl_distance * 2),
                "rr": sl_distance * 2 / sl_distance if sl_distance > 0 else 0,
                "reason": f"M15 {r['choch']} CHoCH" + (" + M1 confirm" if m1_aligns else ""),
                "confidence": min(score / 5.0, 0.95),
            })

        if not candidates:
            return {"decision": "WAIT", "reason": "No CHoCH candidates", "confidence": 0.0}

        # Pick best by score, then R:R
        candidates.sort(key=lambda c: (c["score"], c["rr"]), reverse=True)
        best = candidates[0]

        if best["rr"] < 2.0:
            return {"decision": "WAIT", "reason": f"{best['reason']} — R:R {best['rr']:.1f} < 2.0", "confidence": 0.0}

        return {
            "decision": "ENTRY",
            "reason": best["reason"],
            "symbol_id": best["sid"],
            "side": best["side"],
            "entry_price": round(best["entry"], 5),
            "stop_loss": round(best["sl"], 5),
            "take_profit": round(best["tp"], 5),
            "confidence": best["confidence"],
        }
