#!/bin/bash
# Weather Trading Bot - Main Run Script
# Runs every 30 minutes via cron

BOT_DIR="/Users/alfred/.openclaw/workspace/weather-trader"
LOG_FILE="$BOT_DIR/bot.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "============================================" >> "$LOG_FILE"
echo "🤖 BOT RUN: $TIMESTAMP" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

cd "$BOT_DIR"

# Run the enhanced bot
/usr/bin/python3 weather_bot_enhanced.py >> "$LOG_FILE" 2>&1

# Log separator
echo "" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
