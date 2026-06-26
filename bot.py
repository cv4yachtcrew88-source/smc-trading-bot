#!/usr/bin/env python3
import json, time, os, traceback
from datetime import datetime, timezone, timedelta
from config import (
    SCAN_LIST, ALL_SYMBOLS,
    BASE_INTERVAL_MINS, KILLZONE_INTERVAL_MINS,
    ACTIVE_POSITION_INTERVAL_MINS,
    KILLZONE_LONDON, KILLZONE_NY,
    MAX_RISK_PERCENT,
)
from mcp_client import MCPClient
from smc_analysis import SMCAnalyzer
from llm_advisor import LLMAdvisor
from telegram_notifier import TelegramNotifier
from trade_executor import TradeExecutor

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

class TradingBot:
    def __init__(self):
        self.mcp = MCPClient()
        self.analyzer = SMCAnalyzer()
        self.llm = LLMAdvisor()
        self.notifier = TelegramNotifier()
        self.executor = TradeExecutor(self.mcp, self.notifier)
        self.state = self._load_state()
        self.name_map = {sid: name for sid, (name, _) in ALL_SYMBOLS.items()}

    def _load_state(self):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            return {"position_ids": [], "pending_order_ids": []}

    def _save_state(self):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(self.state, f, indent=2)
        except:
            pass

    def _current_hour_wat(self):
        return (datetime.now(timezone.utc) + timedelta(hours=1)).hour

    def _is_weekend(self):
        return datetime.now(timezone.utc).weekday() in (5, 6)

    def _in_killzone(self, hour):
        return (KILLZONE_LONDON[0] <= hour < KILLZONE_LONDON[1] or
                KILLZONE_NY[0] <= hour < KILLZONE_NY[1])

    def _scan_interval_mins(self):
        if self._is_weekend():
            return 30
        hour = self._current_hour_wat()
        in_kz = self._in_killzone(hour)
        has_pos = len(self.state.get("position_ids", [])) > 0
        if has_pos:
            return ACTIVE_POSITION_INTERVAL_MINS
        if in_kz:
            return KILLZONE_INTERVAL_MINS
        return BASE_INTERVAL_MINS

    def _fetch_and_analyze(self, sid, period, div, hours_back, pivot):
        data = self.mcp.get_trendbars(sid, period, hours_back=hours_back)
        bars = data.get("trendbars", [])
        if not bars:
            return None
        return self.analyzer.analyze_trendbars(bars, div, pivot=pivot)

    def scan_all(self):
        results = []
        symbols = {22395: ("BTCUSD", 100000), 22397: ("ETHUSD", 100000)} if self._is_weekend() else SCAN_LIST
        for sid, (name, div) in symbols.items():
            try:
                r = self._fetch_and_analyze(sid, "M_15", div, 24, 3)
                if not r:
                    continue
                r["symbol_id"] = sid
                r["symbol_name"] = name

                m5 = self._fetch_and_analyze(sid, "M_5", div, 6, 2)
                if m5:
                    r["m5"] = m5

                m1 = self._fetch_and_analyze(sid, "M_1", div, 2, 2)
                if m1:
                    r["m1"] = m1

                if r.get("m5") and r.get("m1"):
                    r["mtf"] = self.analyzer.multi_timeframe_analysis(r, r["m5"], r["m1"])

                r["fvg_count"] = len(r.get("bullish_fvgs", [])) + len(r.get("bearish_fvgs", []))
                results.append(r)
            except Exception as e:
                print(f"  ✗ {name}: {e}")
        return results

    def summarise_scan(self, results):
        lines = [f"Scan {datetime.now(timezone.utc).strftime('%H:%M')} UTC"]
        for r in results:
            sig = "★" if r.get("choch") else "·"
            choch = r.get("choch") or ""
            mtf = r.get("mtf", {})
            score = mtf.get("score", 0)
            lines.append(
                f"{sig} {r['symbol_name']:<7} {r['structure']:<8} "
                f"{r['close']:<12} {choch} fvg={r.get('fvg_count',0)} s={score}"
            )
        return "\n".join(lines)

    def run_cycle(self):
        wat_hour = self._current_hour_wat()
        in_kz = self._in_killzone(wat_hour)
        ts = datetime.now(timezone.utc).strftime('%H:%M:%S')

        is_we = self._is_weekend()
        if is_we:
            print(f"\n{'─'*60}")
            print(f"  [{ts}] 🏁 WEEKEND — crypto only")
        else:
            print(f"\n{'─'*60}")
            print(f"  [{ts}] WAT {wat_hour}:00 {'🟢 KILLZONE' if in_kz else '🔴 OFF-PEAK'}")

        # 1. Fetch live state
        balance = self.mcp.get_balance()
        balance_eur = balance.get("balance", 0) / 100
        positions = self.mcp.get_positions()
        pending = self.mcp.get_pending_orders()
        print(f"  Balance: {balance_eur:.2f} EUR")
        print(f"  Positions: {len(positions)} | Pending: {len(pending)}")

        self.state["position_ids"] = [p["positionId"] for p in positions]
        self.state["pending_order_ids"] = [o["orderId"] for o in pending]

        # 2. Scan
        results = self.scan_all()
        summary = self.summarise_scan(results)
        print(summary)

        # 3. Build scan map (symbol_id → analysis)
        scan_map = {}
        for r in results:
            sid = r.get("symbol_id")
            if sid:
                scan_map[sid] = r

        # 4. Manage exits (CHoCH reversal)
        exits = self.executor.manage_exits(positions, scan_map)
        for sid, xprice, entry, pnl in exits:
            n = self.name_map.get(sid, f"ID{sid}")
            self.notifier.trade_exit(n, "BUY" if pnl > 0 else "SELL", entry, xprice, pnl)
            # Update state
            self.state["position_ids"] = [
                pid for pid in self.state["position_ids"]
                if pid != next((p["positionId"] for p in positions if p["symbolId"] == sid), None)
            ]

        # 5. Check for entry (only in killzone, with room)
        if in_kz and len(positions) < 3 and len(pending) < 3:
            active = [{"symbol": p.get("symbolId"), "side": p.get("tradeSide"),
                       "entry": p.get("entryPrice")} for p in positions]
            pends = [{"symbolId": o.get("symbolId"), "orderType": o.get("orderType"),
                      "limitPrice": o.get("limitPrice")} for o in pending]

            decision = self.llm.analyze(results, active, pends, balance, wat_hour)
            print(f"  → Decision: {decision.get('decision')} — {decision.get('reason','')[:80]}")

            if decision.get("decision") == "ENTRY":
                result = self.executor.handle_decision(decision, balance_eur, self.name_map)
                print(f"  → Order: {result.get('status','?')} — {result.get('error','')[:60]}")

        # 6. Telegram scan report — always send (brief off-peak, full in killzone)
        has_choch = any(r.get("choch") for r in results[:5])
        if has_choch or self._cycle_count % 2 == 0:
            self.notifier.scan_report(summary)

        # 7. Heartbeat every 30 min (3 cycles off-peak, ~15 min in killzone)
        if self._cycle_count % 3 == 0:
            self.notifier.heartbeat(balance_eur, len(positions), wat_hour, in_kz, weekend=self._is_weekend())

        self._save_state()

    def run(self):
        print("╔══════════════════════════════════════════════════╗")
        print("║        SMC SCALPING BOT  v2                     ║")
        print("╠══════════════════════════════════════════════════╣")
        print(f"║  Pairs: {len(SCAN_LIST)}")
        print(f"║  Telegram: {'ON' if self.notifier.token else 'OFF'}")
        print(f"║  LLM: {'ON' if self.llm.api_key else 'OFF (rule-based)'}")
        print(f"║  Killzones: London {KILLZONE_LONDON[0]}-{KILLZONE_LONDON[1]}WAT")
        print(f"║              NY {KILLZONE_NY[0]}-{KILLZONE_NY[1]}WAT")
        print(f"║  Max risk: {MAX_RISK_PERCENT}% per trade")
        print(f"║  Min R:R: 1:2")
        print("╚══════════════════════════════════════════════════╝")

        self.mcp.init_session()
        self.notifier.status("Bot v2 started")
        self._cycle_count = 0

        while True:
            self._cycle_count += 1
            try:
                self.run_cycle()
            except KeyboardInterrupt:
                print("\n  Stopped by user")
                break
            except Exception as e:
                traceback.print_exc()
                self.notifier.error(f"Cycle error: {str(e)[:200]}")
                time.sleep(60)

            interval = self._scan_interval_mins()
            print(f"  Next scan in {interval} min")
            time.sleep(interval * 60)


if __name__ == "__main__":
    TradingBot().run()
