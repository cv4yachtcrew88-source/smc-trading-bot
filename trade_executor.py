from config import ALL_SYMBOLS, MAX_RISK_PERCENT, MIN_RR
from mcp_client import MCPClient

class TradeExecutor:
    def __init__(self, mcp: MCPClient, notifier):
        self.mcp = mcp
        self.notifier = notifier

    def _calc_volume_cents(self, symbol_id, entry, stop_loss, balance_eur):
        risk_eur = balance_eur * (MAX_RISK_PERCENT / 100)
        sl_dist = abs(entry - stop_loss)
        if sl_dist == 0:
            return 100
        point_val_eur = self._point_value_eur(symbol_id)
        risk_per_unit = sl_dist * point_val_eur
        if risk_per_unit <= 0.001:
            return 100
        units = risk_eur / risk_per_unit

        sym_info = self._get_symbol_info(symbol_id)
        min_vol = sym_info.get("min_volume_cents", 100)
        max_vol = sym_info.get("max_volume_cents", 10000000)

        vol_cents = max(min_vol, min(int(round(units * 100)), max_vol))
        return vol_cents

    def _point_value_eur(self, symbol_id):
        if symbol_id in (41, 42):  # XAUUSD, XAGUSD
            return 1.0
        if symbol_id in (10091, 10092, 22344):  # BRENT, WTI, NAT.GAS
            return 10.0
        if symbol_id in (21499, 21500, 21501, 21502, 21576,
                          21577, 21503, 21506, 21507, 21497, 21498, 21644):
            return 1.0
        if symbol_id in (22395,):  # BTCUSD
            return 1.0
        if symbol_id in (22397,):  # ETHUSD
            return 0.1
        return 0.0001

    def _get_symbol_info(self, symbol_id):
        info = {"min_volume_cents": 100, "max_volume_cents": 10000000}
        syms = self.mcp.call("get_symbols", {})
        for s in syms.get("symbols", []):
            if s["symbolId"] == symbol_id:
                info["name"] = s.get("symbolName", "")
                break
        return info

    def place_limit(self, symbol_id, side, price, sl, tp, balance_eur, label=""):
        vol_cents = self._calc_volume_cents(symbol_id, price, sl, balance_eur)
        result = self.mcp.create_order(
            symbol_id=symbol_id, order_type="LIMIT",
            trade_side=side, volume=vol_cents,
            limit_price=price, stop_loss=sl, take_profit=tp,
            label=label, comment="SMC auto"
        )
        et = result.get("executionType", "")
        if et == "ORDER_ACCEPTED":
            return {"status": "pending", "order_id": result.get("orderId"),
                    "volume": vol_cents}
        if et == "ORDER_FILLED":
            return {"status": "filled", "position_id": result.get("positionId"),
                    "entry": result.get("position", {}).get("entryPrice"),
                    "volume": vol_cents}
        return {"status": "rejected", "error": str(result.get("error", result))[:200]}

    def place_market(self, symbol_id, side, sl, tp, balance_eur, label=""):
        price = sl * 0.995 if side == "BUY" else sl * 1.005
        vol_cents = self._calc_volume_cents(symbol_id, price, sl, balance_eur)
        result = self.mcp.create_order(
            symbol_id=symbol_id, order_type="MARKET",
            trade_side=side, volume=vol_cents,
            stop_loss=sl, take_profit=tp,
            label=label, comment="SMC auto"
        )
        et = result.get("executionType", "")
        if et == "ORDER_FILLED":
            return {"status": "filled", "position_id": result.get("positionId"),
                    "entry": result.get("position", {}).get("entryPrice"),
                    "volume": vol_cents}
        return {"status": "rejected", "error": str(result.get("error", result))[:200]}

    def manage_exits(self, positions, scan_map):
        closed = []
        for pos in positions:
            sid = pos.get("symbolId")
            if sid not in scan_map:
                continue
            s = scan_map[sid]
            choch = s.get("choch")
            side = pos.get("tradeSide")
            entry = pos.get("entryPrice")
            price = s.get("close", 0)
            # Exit if CHoCH reverses against position
            if side == "BUY" and choch == "BEARISH":
                r = self.mcp.close_position(pos["positionId"], pos["volume"])
                pnl = (price - entry) if entry else 0
                closed.append((sid, price, entry, pnl))
            elif side == "SELL" and choch == "BULLISH":
                r = self.mcp.close_position(pos["positionId"], pos["volume"])
                pnl = (entry - price) if entry else 0
                closed.append((sid, price, entry, pnl))
        return closed

    def handle_decision(self, decision, balance_eur, name_map):
        action = decision.get("decision")
        if action == "ENTRY":
            sid = decision["symbol_id"]
            result = self.place_limit(
                symbol_id=sid,
                side=decision["side"],
                price=decision["entry_price"],
                sl=decision["stop_loss"],
                tp=decision["take_profit"],
                balance_eur=balance_eur,
                label=f"smc-{name_map.get(sid,'?').lower()}-auto"
            )
            self.notifier.trade_entry(
                name_map.get(sid, f"ID{sid}"),
                decision["side"], decision["entry_price"],
                decision["stop_loss"], decision["take_profit"],
                decision.get("confidence", 0.5),
                decision.get("reason", "Auto")
            )
            return result
        return {"action": action, "reason": decision.get("reason")}
