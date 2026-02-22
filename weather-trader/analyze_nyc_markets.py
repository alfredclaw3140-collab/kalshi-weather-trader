"""Analyze NYC temperature markets."""
import requests
from kalshi_auth import get_auth_headers
import re

API_BASE = "https://api.elections.kalshi.com"

series = "KXHIGHNY"
path = f"/trade-api/v2/markets?series_ticker={series}&limit=50"
headers = get_auth_headers("GET", path)

resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
markets = resp.json().get("markets", [])

print(f"📊 NYC High Temperature Markets ({len(markets)} total)\n")
print("=" * 70)

# Group by date
date_groups = {}
for m in markets:
    ticker = m.get('ticker', '')
    # Parse date from ticker: KXHIGHNY-26FEB22-T45 -> Feb 22, 2026
    match = re.search(r'-26([A-Z]{3})(\d{2})-', ticker)
    if match:
        month = match.group(1)
        day = match.group(2)
        date_key = f"Feb {day}, 2026"
        
        if date_key not in date_groups:
            date_groups[date_key] = []
        
        date_groups[date_key].append(m)

# Show markets for each date
for date_str, ms in sorted(date_groups.items()):
    print(f"\n📅 {date_str} ({len(ms)} markets)")
    print("-" * 70)
    
    for m in sorted(ms, key=lambda x: x.get('yes_ask', 0)):
        ticker = m.get('ticker', '')
        title = m.get('title', '')
        yes_price = m.get('yes_ask', 0) / 100
        no_price = m.get('no_ask', 0) / 100
        volume = m.get('volume', 0)
        
        # Parse bucket from title
        bucket = ""
        if "be >" in title:
            match = re.search(r'>(\d+)°', title)
            if match:
                bucket = f">{match.group(1)}°F"
        elif "be <" in title:
            match = re.search(r'<(\d+)°', title)
            if match:
                bucket = f"<{match.group(1)}°F"
        else:
            match = re.search(r'(\d+)-(\d+)°', title)
            if match:
                bucket = f"{match.group(1)}-{match.group(2)}°F"
        
        print(f"  {bucket:12} | YES: {yes_price:>5.0%} | NO: {no_price:>5.0%} | Vol: {volume:>4} | {ticker}")

print("\n" + "=" * 70)
print("\n💡 Trading Logic:")
print("   1. Get NOAA forecast for target date")
print("   2. Find which bucket matches the forecast")
print("   3. If market price < 80%, buy YES")
print("   4. If forecast is OUTSIDE bucket, consider buying NO")
