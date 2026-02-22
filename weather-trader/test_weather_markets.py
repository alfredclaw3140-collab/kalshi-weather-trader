"""Find and analyze weather markets on Kalshi."""
import requests
from kalshi_auth import get_auth_headers

API_BASE = "https://api.elections.kalshi.com"

def get_weather_events():
    """Find weather-related events on Kalshi."""
    print("🔍 Searching for weather markets...")
    print()
    
    # Get all events
    path = "/trade-api/v2/events?active=true&limit=100"
    headers = get_auth_headers("GET", path)
    
    resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
    
    if resp.status_code != 200:
        print(f"❌ Error: {resp.status_code}")
        return []
    
    events = resp.json().get("events", [])
    print(f"Found {len(events)} total events")
    print()
    
    # Filter for weather events
    weather_events = []
    for event in events:
        ticker = event.get("event_ticker", "")
        title = event.get("title", "").lower()
        
        if "temp" in title or "high" in title or "low" in title:
            weather_events.append(event)
    
    print(f"Found {len(weather_events)} temperature events:")
    for e in weather_events[:10]:
        print(f"  📊 {e.get('event_ticker', 'N/A')}: {e.get('title', 'N/A')[:60]}")
    
    return weather_events


def get_markets_for_event(event_ticker):
    """Get all markets for a specific event."""
    path = f"/trade-api/v2/markets?event_ticker={event_ticker}&status=open&limit=50"
    headers = get_auth_headers("GET", path)
    
    resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
    
    if resp.status_code != 200:
        return []
    
    return resp.json().get("markets", [])


def analyze_weather_market(market):
    """Parse a weather market for key info."""
    ticker = market.get("ticker", "")
    title = market.get("title", "")
    
    # Extract temperature bucket from title
    import re
    
    # Pattern: "35° to 37°" or ">40°" or "<35°"
    range_match = re.search(r'(\d+)°?\s*to\s*(\d+)°?', title)
    gt_match = re.search(r'>(\d+)°', title)
    lt_match = re.search(r'<(\d+)°', title)
    
    bucket = None
    if range_match:
        bucket = {"min": int(range_match.group(1)), "max": int(range_match.group(2))}
    elif gt_match:
        bucket = {"min": int(gt_match.group(1)) + 1, "max": 999}
    elif lt_match:
        bucket = {"min": -999, "max": int(lt_match.group(1)) - 1}
    
    # Get prices
    yes_price = market.get("yes_ask", 0) / 100  # Convert cents to decimal
    no_price = market.get("no_ask", 0) / 100
    
    return {
        "ticker": ticker,
        "title": title,
        "bucket": bucket,
        "yes_price": yes_price,
        "no_price": no_price,
        "volume": market.get("volume", 0),
        "open_interest": market.get("open_interest", 0),
        "close_date": market.get("close_date", ""),
    }


if __name__ == "__main__":
    # Find weather events
    events = get_weather_events()
    
    if not events:
        print("No weather events found")
        exit()
    
    # Get markets for first event
    first_event = events[0]
    event_ticker = first_event.get('event_ticker', '')
    print(f"\n📈 Getting markets for {event_ticker}...")
    markets = get_markets_for_event(event_ticker)
    
    print(f"Found {len(markets)} markets\n")
    
    for m in markets[:5]:
        analysis = analyze_weather_market(m)
        print(f"🎯 {analysis['ticker']}")
        print(f"   {analysis['title'][:70]}")
        if analysis['bucket']:
            print(f"   Bucket: {analysis['bucket']['min']}° to {analysis['bucket']['max']}°F")
        print(f"   YES Price: {analysis['yes_price']:.0%}")
        print(f"   Volume: {analysis['volume']}")
        print()
