"""Find all events on Kalshi to see what's available."""
import requests
from kalshi_auth import get_auth_headers

API_BASE = "https://api.elections.kalshi.com"

path = "/trade-api/v2/events?active=true&limit=100"
headers = get_auth_headers("GET", path)

resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
events = resp.json().get("events", [])

print(f"Total events: {len(events)}\n")
print("All event tickers:")
for e in events:
    ticker = e.get('event_ticker', 'N/A')
    title = e.get('title', 'N/A')
    print(f"  {ticker}: {title[:50]}")
