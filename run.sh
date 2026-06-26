#!/data/data/com.termux/files/usr/bin/bash
# Termux trading bot runner — crash-proof + wake-lock
# Usage: ./run.sh

export LLM_API_KEY="${LLM_API_KEY:-}"
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
export TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

cd "$(dirname "$0")"

# Keep phone awake
termux-wake-lock
echo "✓ Wake lock acquired"

# Counter for restart
N=0

while true; do
    N=$((N + 1))
    echo ""
    echo "═══════════════════════════════════════"
    echo "  Bot start #$N — $(date '+%H:%M:%S %Z')"
    echo "═══════════════════════════════════════"

    python3 bot.py

    EC=$?
    echo "Bot exited with code $EC at $(date '+%H:%M:%S')"

    if [ "$EC" -eq 0 ] || [ "$EC" -eq 130 ]; then
        echo "Clean stop (Ctrl+C or exit). Restarting in 10s..."
    else
        echo "Crash detected! Restarting in 5s..."
    fi
    sleep 5
done
