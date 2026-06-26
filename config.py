import os

# === cTrader MCP ===
MCP_BASE_URL = "https://mcp.ctrader.com/trading/mcp"
MCP_TOKEN = os.environ.get(
    "MCP_TOKEN",
    "eyJwbGFudCI6ImN0cmFkZXIiLCJlbnZpcm9ubWVudCI6ImRlbW8iLCJ0b2tlbiI6ImdCMDdlT25tV29td2Y1RjFuWElFZzhnMCt1SE50WEJidUxwcDhRSXBGMGM9In0"
)

# === LLM (OpenAI-compatible) ===
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://opencode.ai/zen/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-v4-flash-free")
LLM_ENABLED = True

# === Telegram ===
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# === Account ===
MONEY_DIGITS = 2

# === Symbols to monitor ===
FOREX_MAJORS = {
    1: ("EURUSD", 100000),
    2: ("GBPUSD", 100000),
    4: ("USDJPY", 100000),
    5: ("AUDUSD", 100000),
    6: ("USDCHF", 100000),
    8: ("USDCAD", 100000),
    12: ("NZDUSD", 100000),
}

FOREX_CROSSES = {
    3: ("EURJPY", 100000),
    7: ("GBPJPY", 100000),
    9: ("EURGBP", 100000),
    10: ("EURCHF", 100000),
    14: ("EURAUD", 100000),
    17: ("EURCAD", 100000),
    66: ("EURNZD", 100000),
    67: ("AUDNZD", 100000),
}

COMMODITIES = {
    41: ("XAUUSD", 100000),
    42: ("XAGUSD", 100000),
    10091: ("BRENT", 100000),
    10092: ("WTI", 100000),
}

INDICES = {
    21499: ("US500", 100000),
    21501: ("USTECH", 100000),
    21502: ("DAX40", 100000),
    21576: ("UK100", 100000),
}

CRYPTO = {
    22395: ("BTCUSD", 100000),
    22397: ("ETHUSD", 100000),
}

ALL_SYMBOLS = {}
for d in [FOREX_MAJORS, FOREX_CROSSES, COMMODITIES, INDICES, CRYPTO]:
    ALL_SYMBOLS.update(d)

SCAN_LIST = {**FOREX_MAJORS, **CRYPTO, **{41: ("XAUUSD", 100000)}}

# === Scan timing (Nigeria WAT = UTC+1) ===
KILLZONE_LONDON = (7, 10)
KILLZONE_NY = (12, 15)
LONDON_NY_OVERLAP = (13, 16)
BASE_INTERVAL_MINS = 15
KILLZONE_INTERVAL_MINS = 5
ACTIVE_POSITION_INTERVAL_MINS = 1

# === Risk (corrected after post-mortem) ===
MAX_RISK_PERCENT = 1.0
MAX_POSITIONS = 3
MIN_RR = 2.0
MIN_SL_PIPS_EURUSD = 10
MIN_SL_PERCENT_INDICES = 1.0
ENTRY_CONFIRMATION_REQUIRED = True  # Wait for M1 CHoCH, no pre-positioning in FVG

# === SMC parameters ===
SWING_PIVOT_M15 = 3
SWING_PIVOT_M5 = 2
SWING_PIVOT_M1 = 2
FVG_MIN_PIPS_EURUSD = 1.5
