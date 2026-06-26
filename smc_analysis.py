from config import SWING_PIVOT_M15, SWING_PIVOT_M5, SWING_PIVOT_M1, FVG_MIN_PIPS_EURUSD

class SMCAnalyzer:
    def detect_swings(self, highs, lows, pivot=3):
        sh, sl = [], []
        hi_idxs, lo_idxs = [], []
        for i in range(pivot, len(highs) - pivot):
            if highs[i] == max(highs[i - pivot:i + pivot + 1]):
                sh.append(highs[i])
                hi_idxs.append(i)
            if lows[i] == min(lows[i - pivot:i + pivot + 1]):
                sl.append(lows[i])
                lo_idxs.append(i)
        return sh, sl

    def detect_structure(self, sw_highs, sw_lows):
        if len(sw_highs) < 2 or len(sw_lows) < 2:
            return "MIXED"
        if sw_highs[-1] >= sw_highs[-2] and sw_lows[-1] >= sw_lows[-2]:
            return "BULLISH"
        if sw_highs[-1] <= sw_highs[-2] and sw_lows[-1] <= sw_lows[-2]:
            return "BEARISH"
        return "MIXED"

    def detect_cho_ch(self, sw_highs, sw_lows, close):
        if len(sw_highs) < 3 or len(sw_lows) < 3:
            return None, 0
        if (sw_highs[-3] > sw_highs[-2] > sw_highs[-1]
                and close < sw_lows[-1]):
            return "BEARISH", 1
        if (sw_lows[-3] < sw_lows[-2] < sw_lows[-1]
                and close > sw_highs[-1]):
            return "BULLISH", 1
        return None, 0

    def detect_fvgs(self, highs, lows, div, min_gap_price=None, lookback=20):
        if min_gap_price is None:
            min_gap_price = 0.00015
        fvgs = {"bullish": [], "bearish": []}
        start = max(2, len(highs) - lookback)
        for i in range(start, len(highs) - 1):
            gap_up = lows[i] - highs[i - 2]
            if gap_up > min_gap_price:
                fvgs["bullish"].append({
                    "top": lows[i], "bottom": highs[i - 2],
                    "gap": round(gap_up, 6)
                })
            gap_dn = lows[i - 2] - highs[i]
            if gap_dn > min_gap_price:
                fvgs["bearish"].append({
                    "top": lows[i - 2], "bottom": highs[i],
                    "gap": round(gap_dn, 6)
                })
        return fvgs

    def analyze_trendbars(self, raw_bars, div, pivot=SWING_PIVOT_M15):
        if not raw_bars:
            return None
        hi = [b["high"] / div for b in raw_bars]
        lo = [b["low"] / div for b in raw_bars]
        cl = [b["close"] / div for b in raw_bars]
        op = [b["open"] / div for b in raw_bars]

        sh, sl = self.detect_swings(hi, lo, pivot)
        struct = self.detect_structure(sh, sl)
        choch, qual = self.detect_cho_ch(sh, sl, cl[-1])
        fvgs = self.detect_fvgs(hi, lo, div)

        return {
            "close": cl[-1],
            "open": op[-1],
            "high": hi[-1],
            "low": lo[-1],
            "range_high": max(hi),
            "range_low": min(lo),
            "structure": struct,
            "choch": choch,
            "choch_quality": qual,
            "swing_highs": sh[-4:] if len(sh) >= 4 else sh,
            "swing_lows": sl[-4:] if len(sl) >= 4 else sl,
            "bullish_fvgs": fvgs["bullish"],
            "bearish_fvgs": fvgs["bearish"],
            "bar_count": len(raw_bars),
        }

    def multi_timeframe_analysis(self, m15_result, m5_result, m1_result):
        bias = "NEUTRAL"
        strength = 0
        reasons = []

        if m15_result and m15_result["choch"]:
            bias = m15_result["choch"]
            strength += 2
            reasons.append(f"M15 {m15_result['choch']} CHoCH")

        if m15_result and m15_result["structure"] == "BULLISH":
            if bias == "NEUTRAL":
                bias = "BULLISH"
            strength += 1
            reasons.append("M15 bullish structure")
        elif m15_result and m15_result["structure"] == "BEARISH":
            if bias == "NEUTRAL":
                bias = "BEARISH"
            strength += 1
            reasons.append("M15 bearish structure")

        if m5_result and m5_result["structure"] == bias:
            strength += 1
            reasons.append(f"M5 aligns with M15")
        elif m5_result and m5_result["structure"] == "MIXED":
            strength -= 1
            reasons.append("M5 mixed (pullback)")

        if m1_result:
            if m1_result["choch"] == bias:
                strength += 2
                reasons.append(f"M1 {m1_result['choch']} CHoCH confirms")
            elif m1_result["structure"] == bias:
                strength += 1
                reasons.append("M1 structure aligns")

        return {
            "bias": bias,
            "strength": strength,
            "reasons": reasons,
            "score": min(strength, 5),
        }
