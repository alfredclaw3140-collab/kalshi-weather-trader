"""Complete Weather Trading Bot for Kalshi.

This bot fetches NOAA forecasts and matches them to Kalshi temperature markets,
calculating edge and executing trades.
"""
import requests
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from kalshi_auth import get_auth_headers
from noaa import fetch_forecast, get_high_temp_for_date, calculate_edge

API_BASE = "https://api.elections.kalshi.com"

# City to series mapping
CITY_SERIES = {
    "NYC": "KXHIGHNY",
    "Chicago": "KXHIGHCHI", 
    "Houston": "KXHIGHTHOU",
    "Boston": "KXHIGHTBOS",
    "Phoenix": "KXHIGHTPHX",
    "Seattle": "KXHIGHTSEA",
    "LA": "KXHIGHLAX",
    "Atlanta": "KXHIGHTATL",
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
        return f"KalshiMarket({self.date}: {bucket_str} @ {self.yes_price:.0%})"


def fetch_kalshi_markets(series: str) -> List[KalshiMarket]:
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
        
        # Parse bucket from title
        bucket_min, bucket_max = parse_bucket(title)
        if bucket_min is None:
            continue
        
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
            close_date=m.get('close_date', '')
        ))
    
    return markets


def parse_bucket(title: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse temperature bucket from market title.
    
    Returns (min, max) where max=999 means >min, min=-999 means <max
    """
    # Pattern: >45°
    gt_match = re.search(r'>(\d+)°', title)
    if gt_match:
        return int(gt_match.group(1)), 999
    
    # Pattern: <38°
    lt_match = re.search(r'<(\d+)°', title)
    if lt_match:
        return -999, int(lt_match.group(1))
    
    # Pattern: 38-39° or 38° to 39°
    range_match = re.search(r'(\d+)[°\s]*(?:to|-)[°\s]*(\d+)°', title)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))
    
    return None, None


def find_matching_markets(forecast_temp: int, markets: List[KalshiMarket]) -> List[KalshiMarket]:
    """Find markets where the forecast temp falls in the bucket."""
    return [m for m in markets if m.bucket_min <= forecast_temp <= m.bucket_max]


def analyze_opportunity(forecast_temp: int, market: KalshiMarket, 
                       confidence: float = 0.85) -> Dict:
    """Analyze a trading opportunity.
    
    Args:
        forecast_temp: NOAA forecasted high temp
        market: Kalshi market
        confidence: Our confidence in the forecast (0-1)
    
    Returns:
        Analysis dict with edge, recommendation, sizing
    """
    in_bucket = market.bucket_min <= forecast_temp <= market.bucket_max
    
    if in_bucket:
        # We think YES wins
        our_prob = confidence
        edge = our_prob - market.yes_price
        
        # Kelly sizing
        b = (1 / market.yes_price) - 1 if market.yes_price > 0 else 0
        kelly = (b * our_prob - (1 - our_prob)) / b if b > 0 else 0
        
        return {
            "forecast_temp": forecast_temp,
            "in_bucket": True,
            "market": market,
            "our_probability": our_prob,
            "market_probability": market.yes_price,
            "edge": edge,
            "kelly_fraction": max(0, min(kelly, 0.25)),  # Cap at 25%
            "side": "YES",
            "recommendation": "BUY_YES" if edge > 0.15 else "HOLD",
            "expected_return": (our_prob * (1/market.yes_price)) - 1 if market.yes_price > 0 else 0
        }
    else:
        # We think NO wins
        our_prob = confidence
        edge = our_prob - market.no_price
        
        return {
            "forecast_temp": forecast_temp,
            "in_bucket": False,
            "market": market,
            "our_probability": our_prob,
            "market_probability": market.no_price,
            "edge": edge,
            "kelly_fraction": 0,  # Don't short for now
            "side": "NO",
            "recommendation": "BUY_NO" if edge > 0.15 else "HOLD",
            "expected_return": (our_prob * (1/market.no_price)) - 1 if market.no_price > 0 else 0
        }


def execute_trade(ticker: str, side: str, quantity: int, price: float) -> Dict:
    """Execute a trade on Kalshi.
    
    Args:
        ticker: Market ticker
        side: "yes" or "no"
        quantity: Number of contracts
        price: Price per contract (0.01 to 0.99)
    """
    path = "/trade-api/v2/portfolio/orders"
    headers = get_auth_headers("POST", path)
    
    # Kalshi prices are in cents
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


def run_weather_trader(cities: List[str] = None, days_ahead: int = 3, 
                       dry_run: bool = True):
    """Run the full weather trading bot.
    
    Args:
        cities: List of cities to trade (default: NYC only)
        days_ahead: How many days ahead to look
        dry_run: If True, only show opportunities without trading
    """
    cities = cities or ["NYC"]
    
    print("=" * 70)
    print("🌦️  WEATHER TRADING BOT")
    print("=" * 70)
    print(f"Cities: {', '.join(cities)}")
    print(f"Days ahead: {days_ahead}")
    print(f"Mode: {'DRY RUN (no trades)' if dry_run else 'LIVE TRADING'}")
    print()
    
    # Fetch NOAA forecasts
    print("📡 Fetching NOAA forecasts...")
    forecasts = {}
    for city in cities:
        try:
            forecasts[city] = fetch_forecast(city)
            print(f"  ✅ {city}: {len(forecasts[city])} periods")
        except Exception as e:
            print(f"  ❌ {city}: {e}")
    
    if not forecasts:
        print("\n❌ No forecasts available")
        return
    
    print()
    
    # Analyze each city
    for city in cities:
        if city not in forecasts:
            continue
        
        series = CITY_SERIES.get(city)
        if not series:
            print(f"⚠️  No series mapping for {city}")
            continue
        
        print(f"🏙️  Analyzing {city} ({series})...")
        
        # Fetch Kalshi markets
        try:
            markets = fetch_kalshi_markets(series)
            print(f"   Found {len(markets)} markets")
        except Exception as e:
            print(f"   ❌ Error fetching markets: {e}")
            continue
        
        # Filter for dates (today and forward)
        today = date.today()
        future_markets = [m for m in markets if m.date >= today and (m.date - today).days <= days_ahead]
        
        if not future_markets:
            print(f"   No markets in next {days_ahead} days")
            continue
        
        print(f"   {len(future_markets)} markets in date range")
        
        # Group by date
        by_date = {}
        for m in future_markets:
            if m.date not in by_date:
                by_date[m.date] = []
            by_date[m.date].append(m)
        
        # Analyze each date
        for market_date in sorted(by_date.keys()):
            print(f"\n   📅 {market_date.strftime('%A, %B %d')}:")
            
            forecast_temp = get_high_temp_for_date(forecasts[city], market_date)
            if forecast_temp is None:
                print(f"      No forecast available")
                continue
            
            print(f"      🌡️  NOAA Forecast: {forecast_temp}°F")
            
            # Find all opportunities for this date
            date_opportunities = []
            for market in by_date[market_date]:
                analysis = analyze_opportunity(forecast_temp, market)
                date_opportunities.append(analysis)
            
            # Sort by edge
            date_opportunities.sort(key=lambda x: x["edge"], reverse=True)
            
            # Show top opportunity
            if date_opportunities:
                best = date_opportunities[0]
                m = best["market"]
                
                print(f"\n      💰 BEST OPPORTUNITY:")
                print(f"         Market: {m.ticker}")
                print(f"         Bucket: {m.bucket_min}°-{m.bucket_max}°F")
                print(f"         Market Price: {m.yes_price:.0%} YES / {m.no_price:.0%} NO")
                print(f"         Edge: {best['edge']:.0%}")
                print(f"         Recommendation: {best['recommendation']}")
                
                if best['in_bucket']:
                    print(f"         ✅ Forecast {forecast_temp}°F is IN this bucket")
                else:
                    print(f"         ❌ Forecast {forecast_temp}°F is OUTSIDE this bucket")
                
                if not dry_run and best['recommendation'] != 'HOLD':
                    budget = 20  # $20 per trade
                    quantity = int((best['kelly_fraction'] * budget) / m.yes_price) if best['side'] == 'YES' else 0
                    
                    if quantity > 0:
                        side = best['side'].lower()
                        price = m.yes_price if side == 'yes' else m.no_price
                        
                        print(f"\n         🚀 EXECUTING TRADE:")
                        print(f"            Buy {quantity} {best['side']} at {price:.0%}")
                        result = execute_trade(m.ticker, side, quantity, price)
                        print(f"            Result: {result.get('order_id', 'ERROR')}")
    
    print()
    print("=" * 70)
    print("✅ Analysis complete")


if __name__ == "__main__":
    run_weather_trader(cities=["NYC"], days_ahead=5, dry_run=True)
