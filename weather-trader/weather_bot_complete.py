"""Complete Weather Trading Bot for Kalshi - High AND Low Temperatures."""
import requests
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from kalshi_auth import get_auth_headers
from noaa_complete import fetch_forecast, get_high_temp_for_date, get_low_temp_for_date, calculate_edge
from position_tracker import PositionTracker, Position

API_BASE = "https://api.elections.kalshi.com"

# City to series mapping - HIGH and LOW temps
CITY_SERIES = {
    "NYC": {"high": "KXHIGHNY", "low": "KXLOWNY"},
    "Chicago": {"high": "KXHIGHCHI", "low": "KXLOWCHI"},
    "Houston": {"high": "KXHIGHTHOU", "low": "KXLOWHOU"},
    "Boston": {"high": "KXHIGHTBOS", "low": "KXLOWBOS"},
    "Phoenix": {"high": "KXHIGHTPHX", "low": "KXLOWPHX"},
    "Seattle": {"high": "KXHIGHTSEA", "low": "KXLOWSEA"},
    "LA": {"high": "KXHIGHLAX", "low": "KXLOWLAX"},
    "Atlanta": {"high": "KXHIGHTATL", "low": "KXLOWATL"},
}


@dataclass
class KalshiMarket:
    """Represents a Kalshi temperature market."""
    ticker: str
    title: str
    date: date
    bucket_min: int
    bucket_max: int
    yes_price: float
    no_price: float
    volume: int
    close_date: str
    temp_type: str  # "high" or "low"
    
    @property
    def bucket_type(self) -> str:
        if self.bucket_max == 999:
            return "gt"
        elif self.bucket_min == -999:
            return "lt"
        return "range"
    
    def __repr__(self):
        if self.bucket_type == "gt":
            bucket_str = f">{self.bucket_min}°F"
        elif self.bucket_type == "lt":
            bucket_str = f"<{self.bucket_max}°F"
        else:
            bucket_str = f"{self.bucket_min}-{self.bucket_max}°F"
        return f"KalshiMarket({self.temp_type} {self.date}: {bucket_str} @ {self.yes_price:.0%})"


def fetch_kalshi_markets(series: str, temp_type: str) -> List[KalshiMarket]:
    """Fetch all open markets for a temperature series."""
    path = f"/trade-api/v2/markets?series_ticker={series}&limit=50"
    headers = get_auth_headers("GET", path)
    
    resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
    resp.raise_for_status()
    
    raw_markets = resp.json().get("markets", [])
    markets = []
    
    for m in raw_markets:
        ticker = m.get('ticker', '')
        title = m.get('title', '')
        
        # Parse date from ticker: KXHIGHNY-26FEB22-T45
        date_match = re.search(r'-26([A-Z]{3})(\d{2})-', ticker)
        if not date_match:
            continue
        
        month_str = date_match.group(1)
        day = int(date_match.group(2))
        month_map = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }
        market_date = date(2026, month_map.get(month_str, 1), day)
        
        # Parse bucket with CORRECT boundaries
        if '<' in title:
            match = re.search(r'<(\d+)°', title)
            bucket_min, bucket_max = -999, int(match.group(1)) - 1
        elif '>' in title:
            match = re.search(r'>(\d+)°', title)
            bucket_min, bucket_max = int(match.group(1)) + 1, 999
        else:
            match = re.search(r'(\d+)-(\d+)°', title)
            if not match:
                continue
            bucket_min, bucket_max = int(match.group(1)), int(match.group(2))
        
        yes_price = m.get('yes_ask', 0) / 100
        no_price = m.get('no_ask', 0) / 100
        
        markets.append(KalshiMarket(
            ticker=ticker,
            title=title,
            date=market_date,
            bucket_min=bucket_min,
            bucket_max=bucket_max,
            yes_price=yes_price,
            no_price=no_price,
            volume=m.get('volume', 0),
            close_date=m.get('close_date', ''),
            temp_type=temp_type
        ))
    
    return markets


def execute_trade(ticker: str, side: str, quantity: int, price: float) -> Dict:
    """Execute a trade on Kalshi."""
    path = "/trade-api/v2/portfolio/orders"
    headers = get_auth_headers("POST", path)
    
    price_cents = int(price * 100)
    
    payload = {
        "ticker": ticker,
        "side": side,
        "type": "limit",
        "count": quantity,
        "price": price_cents
    }
    
    resp = requests.post(f"{API_BASE}{path}", headers=headers, json=payload, timeout=30)
    return resp.json()


def analyze_opportunity(forecast_temp: int, market: KalshiMarket, 
                       min_edge: float = 0.15) -> Optional[Dict]:
    """Analyze a single market opportunity."""
    if forecast_temp is None:
        return None
    
    in_bucket = market.bucket_min <= forecast_temp <= market.bucket_max
    
    if in_bucket:
        edge = 0.85 - market.yes_price
        side = "yes"
        price = market.yes_price
    else:
        edge = 0.85 - market.no_price
        side = "no"
        price = market.no_price
    
    if edge < min_edge:
        return None
    
    # Kelly sizing (capped at 5%)
    if price > 0:
        kelly = min((edge / (1 - price)) if (1 - price) > 0 else 0, 0.05)
    else:
        kelly = 0
    
    return {
        "market": market,
        "forecast_temp": forecast_temp,
        "in_bucket": in_bucket,
        "side": side,
        "price": price,
        "edge": edge,
        "kelly": kelly
    }


def run_trading_cycle(cities: List[str] = None, days_ahead: int = 5, 
                     min_edge: float = 0.15, budget: int = 20,
                     dry_run: bool = True):
    """Run trading cycle for high AND low temperatures."""
    cities = cities or ["NYC"]
    tracker = PositionTracker()
    
    print("=" * 70)
    print("🌦️  WEATHER TRADING BOT - HIGH & LOW TEMPS")
    print("=" * 70)
    print(f"Cities: {', '.join(cities)}")
    print(f"Days ahead: {days_ahead} | Min edge: {min_edge:.0%} | Budget: ${budget}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()
    
    # Step 1: Monitor existing positions
    print("📊 STEP 1: Monitor Existing Positions")
    print("-" * 70)
    # ... (same position monitoring logic as before)
    tracker.print_summary()
    print()
    
    # Step 2: Find new opportunities for HIGH and LOW temps
    print("📈 STEP 2: Find New Opportunities (High & Low Temps)")
    print("-" * 70)
    
    for city in cities:
        if city not in CITY_SERIES:
            continue
        
        series_map = CITY_SERIES[city]
        
        # Fetch NOAA forecast once per city
        try:
            forecasts = fetch_forecast(city)
            print(f"\n🏙️  {city}: Fetched NOAA forecast")
        except Exception as e:
            print(f"❌ {city}: {e}")
            continue
        
        # Analyze HIGH temps
        if series_map.get('high'):
            analyze_temp_type(city, 'high', series_map['high'], forecasts, 
                            days_ahead, min_edge, budget, tracker, dry_run)
        
        # Analyze LOW temps  
        if series_map.get('low'):
            analyze_temp_type(city, 'low', series_map['low'], forecasts,
                            days_ahead, min_edge, budget, tracker, dry_run)
    
    print()
    print("=" * 70)
    print("✅ Analysis complete")


def analyze_temp_type(city: str, temp_type: str, series: str, 
                     forecasts: List, days_ahead: int, min_edge: float,
                     budget: int, tracker: PositionTracker, dry_run: bool):
    """Analyze markets for a specific temp type (high or low)."""
    print(f"\n   🌡️  {temp_type.upper()} TEMPS:")
    
    try:
        markets = fetch_kalshi_markets(series, temp_type)
    except Exception as e:
        print(f"      Error: {e}")
        return
    
    # Filter for date range
    today = date.today()
    future_markets = [m for m in markets 
                     if today <= m.date <= today + timedelta(days=days_ahead)]
    
    if not future_markets:
        print(f"      No markets found")
        return
    
    # Get opportunities
    opportunities = []
    for market in future_markets:
        if temp_type == 'high':
            forecast_temp = get_high_temp_for_date(forecasts, market.date)
        else:
            forecast_temp = get_low_temp_for_date(forecasts, market.date)
        
        opp = analyze_opportunity(forecast_temp, market, min_edge)
        if opp:
            opportunities.append(opp)
    
    if not opportunities:
        print(f"      No edge opportunities (markets efficient)")
        return
    
    # Sort by edge
    opportunities.sort(key=lambda x: x['edge'], reverse=True)
    
    # Show best opportunity
    best = opportunities[0]
    m = best['market']
    
    print(f"\n      💰 BEST OPPORTUNITY:")
    print(f"         Market: {m.ticker}")
    print(f"         Date: {m.date.strftime('%A, %b %d')}")
    print(f"         Bucket: {m.bucket_min}°-{m.bucket_max}°F")
    print(f"         Forecast: {best['forecast_temp']}°F ({'IN' if best['in_bucket'] else 'OUT'})")
    print(f"         Trade: {best['side'].upper()} @ {best['price']:.0%}")
    print(f"         Edge: {best['edge']:.0%}")
    
    # Calculate position
    if best['price'] > 0 and best['kelly'] > 0:
        quantity = int((best['kelly'] * budget) / best['price'])
        if quantity >= 1:
            print(f"         Suggested: {quantity} contracts")


if __name__ == "__main__":
    run_trading_cycle(cities=["NYC"], days_ahead=5, dry_run=True)
