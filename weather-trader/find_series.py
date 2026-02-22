"""Find all series on Kalshi."""
import requests
from kalshi_auth import get_auth_headers

API_BASE = "https://api.elections.kalshi.com"

path = "/trade-api/v2/series?active=true&limit=100"
headers = get_auth_headers("GET", path)

resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
series_list = resp.json().get("series", [])

print(f"Total series: {len(series_list)}\n")
print("Looking for weather/temperature series:\n")

for s in series_list:
    ticker = s.get('ticker', '')
    title = s.get('title', '').lower()
    
    if any(word in title for word in ['temp', 'high', 'low', 'weather', 'rain', 'snow', 'nyc', 'chicago']):
        print(f"🌡️  {ticker}: {s.get('title', 'N/A')}")
    elif 'KXHIGH' in ticker or 'KXLOW' in ticker or 'KXRAIN' in ticker:
        print(f"🌡️  {ticker}: {s.get('title', 'N/A')}")

print("\n\nAll series tickers (first 30):")
for s in series_list[:30]:
    print(f"  {s.get('ticker', 'N/A')}: {s.get('title', 'N/A')[:40]}")
