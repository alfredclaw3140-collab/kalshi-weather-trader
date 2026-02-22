"""Detailed analysis of today's NYC markets."""
import requests
import re
from datetime import date
from kalshi_auth import get_auth_headers
from noaa import fetch_forecast, get_high_temp_for_date

API_BASE = "https://api.elections.kalshi.com"

# Fetch forecast
print("📡 Fetching NOAA forecast for NYC...")
forecasts = fetch_forecast("NYC")
today = date.today()
forecast_temp = get_high_temp_for_date(forecasts, today)
print(f"   Today's high: {forecast_temp}°F\n")

# Fetch Kalshi markets
print("📊 Fetching Kalshi markets...")
series = "KXHIGHNY"
path = f"/trade-api/v2/markets?series_ticker={series}&limit=50"
headers = get_auth_headers("GET", path)
resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
markets = resp.json().get("markets", [])

# Filter for today
today_markets = []
for m in markets:
    ticker = m.get('ticker', '')
    if '26FEB22' in ticker:
        today_markets.append(m)

print(f"   Found {len(today_markets)} markets for today\n")

print("=" * 70)
print("MARKET ANALYSIS")
print("=" * 70)

for m in sorted(today_markets, key=lambda x: x.get('yes_ask', 0)):
    ticker = m.get('ticker')
    title = m.get('title', '')
    yes = m.get('yes_ask', 0) / 100
    no = m.get('no_ask', 0) / 100
    vol = m.get('volume', 0)
    
    # Parse bucket
    if '<' in title:
        match = re.search(r'<(\d+)°', title)
        if match:
            bucket_max = int(match.group(1))
            bucket_str = f"<{bucket_max}°F"
            in_bucket = forecast_temp < bucket_max
    elif '>' in title:
        match = re.search(r'>(\d+)°', title)
        if match:
            bucket_min = int(match.group(1))
            bucket_str = f">{bucket_min}°F"
            in_bucket = forecast_temp > bucket_min
    else:
        match = re.search(r'(\d+)-(\d+)°', title)
        if match:
            bmin, bmax = int(match.group(1)), int(match.group(2))
            bucket_str = f"{bmin}-{bmax}°F"
            in_bucket = bmin <= forecast_temp <= bmax
    
    status = "✅ IN" if in_bucket else "❌ OUT"
    
    print(f"\n{ticker}")
    print(f"   {title}")
    print(f"   Bucket: {bucket_str} | Forecast: {forecast_temp}°F {status}")
    print(f"   YES: {yes:>5.0%} | NO: {no:>5.0%} | Vol: {vol}")
    
    if in_bucket:
        edge = 0.85 - yes  # 85% confidence - market price
        print(f"   📈 EDGE: {edge:.0%} (recommendation: {'BUY YES' if edge > 0.15 else 'HOLD'})")
    else:
        # Check if we should buy NO
        edge = 0.85 - no
        if edge > 0.15:
            print(f"   📉 EDGE ON NO: {edge:.0%} (recommendation: BUY NO)")
