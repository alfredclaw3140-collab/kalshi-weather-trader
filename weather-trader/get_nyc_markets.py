"""Get NYC temperature markets."""
import requests
from kalshi_auth import get_auth_headers
from datetime import datetime

API_BASE = "https://api.elections.kalshi.com"

# Get markets for NYC high temp
series = "HIGHNY"
path = f"/trade-api/v2/markets?series_ticker={series}&status=open&limit=50"
headers = get_auth_headers("GET", path)

resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
markets = resp.json().get("markets", [])

print(f"Found {len(markets)} markets for {series}\n")

for m in markets[:10]:
    ticker = m.get('ticker', 'N/A')
    title = m.get('title', 'N/A')
    yes_price = m.get('yes_ask', 0) / 100
    no_price = m.get('no_ask', 0) / 100
    volume = m.get('volume', 0)
    close_date = m.get('close_date', '')
    
    print(f"🌡️  {ticker}")
    print(f"   {title}")
    print(f"   YES: {yes_price:.0%} | NO: {no_price:.0%}")
    print(f"   Volume: {volume} | Closes: {close_date}")
    print()
