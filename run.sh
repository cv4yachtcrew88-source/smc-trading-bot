#!/data/data/com.termux/files/usr/bin/bash
# Run on Termux (Android)
# Set these env vars before running:
#   export LLM_API_KEY="your-opencode-zen-api-key"
#   export TELEGRAM_BOT_TOKEN="your-bot-token"
#   export TELEGRAM_CHAT_ID="your-chat-id"

cd "$(dirname "$0")"

# Optional: keep phone awake
# termux-wake-lock

python3 bot.py
