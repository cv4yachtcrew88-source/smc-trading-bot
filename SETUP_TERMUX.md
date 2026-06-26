# Termux Setup — One Time

## 1. Install
```bash
pkg update && pkg install python tmux
```

## 2. Export secrets (add to ~/.bashrc)
```bash
export LLM_API_KEY="your-key"
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"
```

## 3. Disable battery optimization
- Android Settings → Apps → Termux → Battery → Unrestricted

## 4. Run
```bash
cd trading_bot
tmux new -s bot
./run.sh
```
- Close Termux? Bot keeps running in tmux.
- Reopen Termux → `tmux attach -t bot` to see it.
