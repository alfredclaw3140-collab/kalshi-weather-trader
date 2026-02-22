"""Get markets using different query methods."""
import requests
from kalshi_auth import get_auth_headers

API_BASE = "https://api.elections.kalshi.com"

# Try event ticker instead of series
series_list = ["HIGHNY", "KXHIGHNY", "KXHIGHTNY", "HIGHNY0"]

for series in series_list:
    print(f"\n🔍 Trying series: {series}")
    
    path = f"/trade-api/v2/markets?series_ticker={series}&limit=50"
    headers = get_auth_headers("GET", path)
    
    resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
    markets = resp.json().get("markets", [])
    
    print(f"   Found {len(markets)} markets")
    
    if markets:
        for m in markets[:3]:
            print(f"   - {m.get('ticker')}: {m.get('title', '')[:50]}")

# Also try getting all markets and filtering
print("\n\n🔍 Getting all open markets (limit 100)...")
path = "/trade-api/v2/markets?status=open&limit=100"
headers = get_auth_headers("GET", path)

resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
all_markets = resp.json().get("markets", [])

# Filter for temperature markets
temp_markets = [m for m in all_markets if 'temp' in m.get('title', '').lower() or 'high' in m.get('title', '').lower()]

print(f"Found {len(temp_markets)} temperature-related markets")

for m in temp_markets[:5]:
    ticker = m.get('ticker', '')
    title = m.get('title', '')
    yes_price = m.get('yes_ask', 0) / 100
    print(f"\n  🌡️  {ticker}")
    print(f"     {title}")
    print(f"     YES Price: {yes_price:.0%}")
