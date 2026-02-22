# Setup Cron Job for Weather Trading Bot

The bot is configured to run every 30 minutes.

## Quick Setup

Open your terminal and run:

```bash
# Edit crontab
crontab -e

# Add this line (runs every 30 minutes):
*/30 * * * * /Users/alfred/.openclaw/workspace/weather-trader/run_bot.sh

# Save and exit (Ctrl+X, then Y, then Enter)
```

## Verify Setup

```bash
# Check if cron job is added
crontab -l

# Should show:
# */30 * * * * /Users/alfred/.openclaw/workspace/weather-trader/run_bot.sh
```

## Monitoring

### View Logs (real-time)
```bash
tail -f /Users/alfred/.openclaw/workspace/weather-trader/bot.log
```

### View Dashboard
```bash
cd /Users/alfred/.openclaw/workspace/weather-trader
python3 monitor.py
```

### Check Positions
```bash
cat ~/.config/kalshi/positions.json
```

## Files Created

| File | Purpose |
|------|---------|
| `run_bot.sh` | Main script that runs every 30 min |
| `bot.log` | Log of all bot activity |
| `monitor.py` | Dashboard to view performance |
| `positions.json` | Tracks your open/closed positions |

## Stop the Bot

```bash
# Remove cron job
crontab -e
# Delete the line with run_bot.sh
# Save and exit
```

## Manual Run (for testing)

```bash
cd /Users/alfred/.openclaw/workspace/weather-trader
python3 weather_bot_enhanced.py
```
