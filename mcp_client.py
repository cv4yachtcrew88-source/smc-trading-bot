import json, urllib.request, time
from datetime import datetime, timezone, timedelta
from config import MCP_BASE_URL, MCP_TOKEN

class MCPClient:
    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {MCP_TOKEN}",
        }
        self.session_id = None
        self.symbol_cache = {}

    def init_session(self):
        body = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "trading-bot", "version": "1.0.0"}
            }
        }
        req = urllib.request.Request(
            MCP_BASE_URL, data=json.dumps(body).encode(),
            headers=self.headers, method="POST"
        )
        resp = urllib.request.urlopen(req)
        self.session_id = resp.headers.get("Mcp-Session-Id", "")
        self.headers["Mcp-Session-Id"] = self.session_id
        req2 = urllib.request.Request(
            MCP_BASE_URL,
            data=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}).encode(),
            headers=self.headers, method="POST"
        )
        urllib.request.urlopen(req2)

    def _parse_result(self, resp_bytes):
        for line in resp_bytes.decode().split("\n"):
            if line.startswith("data: "):
                d = json.loads(line[6:])
                if "result" in d:
                    for c in d["result"].get("content", []):
                        txt = c.get("text", "")
                        if txt.startswith("{"):
                            return json.loads(txt)
                        return {"text": txt}
        return {}

    def call(self, name, args):
        body = {
            "jsonrpc": "2.0", "id": int(time.time() * 1000) % 100000,
            "method": "tools/call",
            "params": {"name": name, "arguments": args}
        }
        req = urllib.request.Request(
            MCP_BASE_URL, data=json.dumps(body).encode(),
            headers=self.headers, method="POST"
        )
        try:
            resp = urllib.request.urlopen(req, timeout=20)
            return self._parse_result(resp.read())
        except urllib.error.HTTPError as e:
            err = e.read().decode()[:300]
            return {"error": f"HTTP {e.code}: {err}"}
        except Exception as e:
            return {"error": str(e)}

    def get_balance(self):
        return self.call("get_balance", {})

    def get_symbols(self):
        return self.call("get_symbols", {})

    def get_spot_prices(self, symbol_ids):
        return self.call("get_spot_prices", {"symbolId": symbol_ids})

    def get_trendbars(self, symbol_id, period, hours_back=12):
        now = datetime.now(timezone.utc)
        from_ts = (now - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
        to_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.call("get_trendbars", {
            "symbolId": symbol_id,
            "period": period,
            "fromTimestamp": from_ts,
            "toTimestamp": to_ts,
        })

    def get_positions(self):
        r = self.call("get_positions", {})
        return r.get("positions", [])

    def get_pending_orders(self):
        r = self.call("get_pending_orders", {})
        return r.get("orders", [])

    def create_order(self, symbol_id, order_type, trade_side, volume,
                     limit_price=None, stop_loss=None, take_profit=None,
                     label="", comment=""):
        args = {
            "symbolId": symbol_id,
            "orderType": order_type,
            "tradeSide": trade_side,
            "volume": volume,
            "label": label,
            "comment": comment,
        }
        if limit_price is not None:
            args["limitPrice"] = limit_price
        if stop_loss is not None:
            args["stopLoss"] = stop_loss
        if take_profit is not None:
            args["takeProfit"] = take_profit
        return self.call("create_order", args)

    def close_position(self, position_id, volume):
        return self.call("close_position", {
            "positionId": position_id, "volume": volume
        })

    def amend_position(self, position_id, stop_loss=None, take_profit=None):
        args = {"positionId": position_id}
        if stop_loss is not None:
            args["stopLoss"] = stop_loss
        if take_profit is not None:
            args["takeProfit"] = take_profit
        return self.call("amend_position", args)

    def get_symbol_name(self, sid):
        if sid in self.symbol_cache:
            return self.symbol_cache[sid]
        syms = self.call("get_symbols", {})
        for s in syms.get("symbols", []):
            self.symbol_cache[s["symbolId"]] = s["symbolName"]
        return self.symbol_cache.get(sid, f"ID{sid}")
