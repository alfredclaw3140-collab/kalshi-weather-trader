"""Kalshi API client for weather market trading."""
import os
import requests
from typing import List, Dict, Optional
from datetime import datetime, date

KALSHI_API_BASE = "https://trading-api.kalshi.com/trade-api/v2"
DEMO_API_BASE = "https://demo-api.kalshi.com/trade-api/v2"


class KalshiClient:
    """Client for interacting with Kalshi API."""
    
    def __init__(self, api_key: str = None, api_secret: str = None, demo: bool = True):
        """Initialize Kalshi client.
        
        Args:
            api_key: Kalshi API key (or set KALSHI_API_KEY env var)
            api_secret: Kalshi API secret (or set KALSHI_API_SECRET env var)
            demo: Use demo environment (no real money)
        """
        self.api_key = api_key or os.getenv("KALSHI_API_KEY")
        self.api_secret = api_secret or os.getenv("KALSHI_API_SECRET")
        self.demo = demo
        self.base_url = DEMO_API_BASE if demo else KALSHI_API_BASE
        self.session = requests.Session()
        
        if self.api_key and self.api_secret:
            self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Kalshi API."""
        # Kalshi uses email/password login to get a token
        # Or API key/secret for programmatic access
        # This is simplified - actual auth may differ
        pass
    
    def get_markets(self, event_ticker: str = None, status: str = "open", 
                   limit: int = 100) -> List[Dict]:
        """Get markets from Kalshi.
        
        Args:
            event_ticker: Filter by event (e.g., "KXHIGHNY")
            status: "open", "closed", etc.
            limit: Max results
        """
        url = f"{self.base_url}/markets"
        params = {"limit": limit, "status": status}
        if event_ticker:
            params["event_ticker"] = event_ticker
        
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("markets", [])
    
    def get_events(self, series_ticker: str = None, limit: int = 100) -> List[Dict]:
        """Get events (collections of markets) from Kalshi.
        
        Weather events have tickers like:
        - KXHIGHNY (NYC high temp)
        - KXHIGHLA (LA high temp)
        - KXRAINNY (NYC rain)
        """
        url = f"{self.base_url}/events"
        params = {"limit": limit, "active": True}
        if series_ticker:
            params["series_ticker"] = series_ticker
        
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("events", [])
    
    def find_weather_events(self, city: str = None) -> List[Dict]:
        """Find weather-related events.
        
        City codes:
        - NYC: KXHIGHNY (high temp), KXLOWNY (low temp)
        - LA: KXHIGHLA, KXLOWLA
        - Chicago: KXHIGHCHI, KXLOWCHI
        """
        events = self.get_events()
        weather_events = []
        
        for event in events:
            ticker = event.get("ticker", "")
            title = event.get("title", "").lower()
            
            # Filter for temperature events
            if "high" in title or "low" in title or "temp" in title:
                if city:
                    city_map = {
                        "NYC": ["NY", "NYC", "NEW YORK"],
                        "LA": ["LA", "LOS ANGELES"],
                        "Chicago": ["CHI", "CHICAGO"],
                    }
                    city_keywords = city_map.get(city, [city.upper()])
                    if any(kw in ticker or kw in title.upper() for kw in city_keywords):
                        weather_events.append(event)
                else:
                    weather_events.append(event)
        
        return weather_events
    
    def get_order_book(self, market_ticker: str) -> Dict:
        """Get order book for a market."""
        url = f"{self.base_url}/markets/{market_ticker}/orderbook"
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    
    def get_balance(self) -> Dict:
        """Get account balance."""
        url = f"{self.base_url}/portfolio/balance"
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    
    def place_order(self, market_ticker: str, side: str, quantity: int, 
                   price: float, order_type: str = "limit") -> Dict:
        """Place an order.
        
        Args:
            market_ticker: Market to trade (e.g., "KXHIGHNY-26FEB19-A")
            side: "yes" or "no"
            quantity: Number of contracts
            price: Price per contract (0.01 to 0.99)
            order_type: "limit" or "market"
        """
        url = f"{self.base_url}/portfolio/orders"
        
        # Kalshi prices are in cents (1-99)
        price_cents = int(price * 100)
        
        payload = {
            "ticker": market_ticker,
            "side": side,
            "type": order_type,
            "count": quantity,
            "price": price_cents
        }
        
        resp = self.session.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()


def parse_kalshi_weather_market(market: Dict) -> Optional[Dict]:
    """Parse a Kalshi weather market to extract key info.
    
    Returns structured data about the market.
    """
    ticker = market.get("ticker", "")
    title = market.get("title", "")
    
    # Parse ticker format: KXHIGHNY-26FEB19-A
    # Series: KXHIGHNY, Date: 26FEB19, Contract: A
    parts = ticker.split("-")
    if len(parts) < 2:
        return None
    
    series = parts[0]
    date_code = parts[1] if len(parts) > 1 else ""
    contract = parts[2] if len(parts) > 2 else ""
    
    # Parse date code (26FEB19 -> 2026-02-19)
    try:
        year = 2000 + int(date_code[:2])
        month_str = date_code[2:5].upper()
        day = int(date_code[5:])
        month_map = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }
        month = month_map.get(month_str, 1)
        market_date = date(year, month, day)
    except:
        market_date = None
    
    # Extract city from series
    city_map = {
        "KXHIGHNY": ("NYC", "high"),
        "KXLOWNY": ("NYC", "low"),
        "KXHIGHLA": ("LA", "high"),
        "KXLOWLA": ("LA", "low"),
        "KXHIGHCHI": ("Chicago", "high"),
        "KXLOWCHI": ("Chicago", "low"),
    }
    city, temp_type = city_map.get(series, (None, "high"))
    
    # Extract temperature bucket from title
    # "NYC High Temp Feb 19, 2026 (A) 35° to 37°"
    import re
    range_match = re.search(r'(\d+)°?\s*to\s*(\d+)°?', title)
    gt_match = re.search(r'>(\d+)°', title)
    lt_match = re.search(r'<(\d+)°', title)
    
    bucket = None
    if range_match:
        bucket = {
            "min": int(range_match.group(1)),
            "max": int(range_match.group(2)),
            "type": "range"
        }
    elif gt_match:
        bucket = {
            "min": int(gt_match.group(1)) + 1,
            "max": 999,
            "type": "gt"
        }
    elif lt_match:
        bucket = {
            "min": -999,
            "max": int(lt_match.group(1)) - 1,
            "type": "lt"
        }
    
    return {
        "ticker": ticker,
        "title": title,
        "series": series,
        "date": market_date,
        "city": city,
        "temp_type": temp_type,
        "bucket": bucket,
        "yes_price": market.get("yes_ask", 0) / 100,  # Convert cents to probability
        "no_price": market.get("no_ask", 0) / 100,
        "volume": market.get("volume", 0),
        "open_interest": market.get("open_interest", 0),
    }


if __name__ == "__main__":
    # Test with demo API (no auth needed for public market data)
    print("Testing Kalshi client (demo mode)...")
    client = KalshiClient(demo=True)
    
    # Get some markets
    print("\nFetching markets...")
    try:
        markets = client.get_markets(limit=10)
        print(f"Found {len(markets)} markets")
        
        for m in markets[:3]:
            print(f"  {m.get('ticker')}: {m.get('title')[:50]}...")
    except Exception as e:
        print(f"Error (expected without API keys): {e}")
