"""Weather Trading Bot v2 with correct bucket parsing."""
import requests
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional

from kalshi_auth import get_auth_headers
from noaa import fetch_forecast, get_high_temp_for_date
from position_tracker import PositionTracker, Position

API_BASE = "https://api.elections.kalshi.com"

CITY_SERIES = {"NYC": "KXHIGHNY", "Chicago": "KXHIGHCHI"}


def fetch_kalshi_markets(series: str):
    """Fetch all markets for a series."""
    path = f"/trade-api/v2/markets?series_ticker={series}&limit=50"
    headers = get_auth_headers("GET", path)
    
    resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
    resp.raise_for_status()
    
    markets = []
    for m in resp.json().get("markets", []):
        ticker = m.get('ticker', '')
        title = m.get('title', '')
        
        # Parse date from ticker
        date_match = re.search(r'-26([A-Z]{3})(\d{2})-', ticker)
        if not date_match:
            continue
        
        month_map = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                     'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
        month = month_map.get(date_match.group(1), 1)
        day = int(date_match.group(2))
        market_date = date(2026, month, day)
        
        # Parse bucket CORRECTLY
        # <38° means temp <= 37 (strictly less than 38)
        # >45° means temp >= 46 (strictly greater than 45)
        # 38-39° means 38 <= temp <= 39 (inclusive)
        if '<' in title:
            match = re.search(r'<(\d+)°', title)
            bucket_min, bucket_max = -999, int(match.group(1)) - 1  # Strictly less
        elif '>' in title:
            match = re.search(r'>(\d+)°', title)
            bucket_min, bucket_max = int(match.group(1)) + 1, 999  # Strictly greater
        else:
            match = re.search(r'(\d+)-(\d+)°', title)
            bucket_min, bucket_max = int(match.group(1)), int(match.group(2))
        
        markets.append({
            'ticker': ticker,
            'date': market_date,
            'bucket_min': bucket_min,
            'bucket_max': bucket_max,
            'yes_price': m.get('yes_ask', 0) / 100,
            'no_price': m.get('no_ask', 0) / 100,
            'title': title
        })
    
    return markets


def execute_trade(ticker: str, side: str, quantity: int, price: float):
    """Execute a trade on Kalshi."""
    path = "/trade-api/v2/portfolio/orders"
    headers = get_auth_headers("POST", path)
    
    payload = {
        "ticker": ticker,
        "side": side,
        "type": "limit",
        "count": quantity,
        "price": int(price * 100)
    }
    
    resp = requests.post(f"{API_BASE}{path}", headers=headers, json=payload, timeout=30)
    return resp.json()


def run_trading_cycle(cities: List[str] = None, budget: int = 20, 
                     min_edge: float = 0.15, dry_run: bool = True):
    """Run one trading cycle with entry + exit logic."""
    cities = cities or ["NYC"]
    tracker = PositionTracker()
    
    print("=" * 70)
    print("🌦️  WEATHER TRADING BOT v2 (FIXED)")
    print("=" * 70)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Budget: ${budget}/trade | Min Edge: {min_edge:.0%}")
    print()
    
    # Step 1: Monitor existing positions
    print("📊 STEP 1: Monitor Existing Positions")
    print("-" * 70)
    
    open_positions = tracker.get_open_positions()
    if open_positions:
        print(f"Found {len(open_positions)} open positions\n")
        
        for pos in open_positions:
            city = pos.city
            forecasts = fetch_forecast(city)
            res_date = date.fromisoformat(pos.resolution_date)
            current_forecast = get_high_temp_for_date(forecasts, res_date)
            
            if current_forecast is None:
                continue
            
            # Get current market price
            path = f"/trade-api/v2/markets/{pos.ticker}"
            headers = get_auth_headers("GET", path)
            
            try:
                resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
                if resp.status_code == 200:
                    market = resp.json().get("market", {})
                    current_price = market.get("yes_ask" if pos.side == "yes" else "no_ask", 0) / 100
                    
                    # Check if forecast still supports position (with correct boundaries)
                    in_bucket = pos.bucket_min <= current_forecast <= pos.bucket_max
                    
                    # Calculate current edge
                    if pos.side == "yes":
                        current_edge = 0.85 - current_price if in_bucket else -0.85 + current_price
                    else:
                        current_edge = 0.85 - current_price if not in_bucket else -0.85 + current_price
                    
                    edge_decay = pos.entry_edge - current_edge
                    
                    print(f"\n{pos.ticker}")
                    print(f"   Bucket: {pos.bucket_min}°-{pos.bucket_max}°F")
                    print(f"   Entry: {pos.side.upper()} {pos.contracts} @ {pos.entry_price:.0%}")
                    print(f"   Current: {current_price:.0%} | P&L: ${(current_price - pos.entry_price) * pos.contracts:.2f}")
                    print(f"   Forecast: {current_forecast}°F ({'IN' if in_bucket else 'OUT'} bucket)")
                    print(f"   Edge: {pos.entry_edge:.0%} → {current_edge:.0%} (decay: {edge_decay:.0%})")
                    
                    # Exit logic
                    exit_reason = None
                    
                    if (pos.side == "yes" and not in_bucket) or (pos.side == "no" and in_bucket):
                        exit_reason = "FORECAST_CHANGED"
                    elif pos.entry_edge > 0 and edge_decay / pos.entry_edge > 0.5:
                        exit_reason = "EDGE_DECAY_50"
                    elif current_edge < 0:
                        exit_reason = "EDGE_NEGATIVE"
                    elif pos.side == "yes" and current_price > 0.85:
                        profit_pct = (current_price - pos.entry_price) / pos.entry_price
                        if profit_pct > 0.5:
                            exit_reason = "TAKE_PROFITS"
                    
                    if exit_reason:
                        print(f"   ⚠️  EXIT TRIGGER: {exit_reason}")
                        if not dry_run:
                            result = execute_trade(pos.ticker, "no" if pos.side == "yes" else "yes", 
                                                  pos.contracts, current_price)
                            tracker.close_position(pos.ticker, current_price, exit_reason)
                            print(f"   🚀 EXIT EXECUTED")
                        else:
                            print(f"   💡 Would exit at {current_price:.0%}")
                    else:
                        print(f"   ✅ HOLD (no exit triggers)")
                        
            except Exception as e:
                print(f"   ❌ Error: {e}")
    else:
        print("No open positions")
    
    print()
    
    # Step 2: Find new opportunities
    print("📈 STEP 2: Find New Opportunities")
    print("-" * 70)
    
    for city in cities:
        series = CITY_SERIES.get(city)
        if not series:
            continue
        
        # Get forecast
        try:
            forecasts = fetch_forecast(city)
        except Exception as e:
            print(f"❌ {city}: {e}")
            continue
        
        # Get markets
        try:
            markets = fetch_kalshi_markets(series)
        except Exception as e:
            print(f"❌ {series}: {e}")
            continue
        
        # Filter for today and tomorrow
        today = date.today()
        target_markets = [m for m in markets if today <= m['date'] <= today + timedelta(days=2)]
        
        if not target_markets:
            print(f"📭 {city}: No markets for next 2 days")
            continue
        
        print(f"\n🏙️  {city}:")
        
        for m in target_markets:
            forecast_temp = get_high_temp_for_date(forecasts, m['date'])
            if forecast_temp is None:
                continue
            
            # Check if forecast is in bucket (with correct boundaries)
            in_bucket = m['bucket_min'] <= forecast_temp <= m['bucket_max']
            
            if in_bucket:
                edge = 0.85 - m['yes_price']
                side = "yes"
                price = m['yes_price']
            else:
                # Check if we should buy NO
                edge = 0.85 - m['no_price']
                side = "no"
                price = m['no_price']
            
            if edge < min_edge:
                continue
            
            # Check if we already have this position
            existing = [p for p in open_positions if p.ticker == m['ticker']]
            if existing:
                continue
            
            print(f"\n   🎯 {m['ticker']}")
            print(f"      {m['title'][:60]}")
            print(f"      Bucket: {m['bucket_min']}°-{m['bucket_max']}°F")
            print(f"      Forecast: {forecast_temp}°F ({'IN' if in_bucket else 'OUT'} bucket)")
            print(f"      Trade: {side.upper()} @ {price:.0%}")
            print(f"      Edge: {edge:.0%}")
            
            # Calculate position size
            if price > 0:
                kelly = min(edge / (1 - price), 0.25)
                quantity = int((kelly * budget) / price)
            else:
                quantity = 0
            
            if quantity < 1:
                print(f"      ⚠️  Quantity too small")
                continue
            
            print(f"      💰 Suggested: Buy {quantity} {side.upper()} at {price:.0%}")
            
            if not dry_run:
                result = execute_trade(m['ticker'], side, quantity, price)
                order_id = result.get('order_id')
                
                if order_id:
                    position = Position(
                        ticker=m['ticker'],
                        entry_date=today.isoformat(),
                        resolution_date=m['date'].isoformat(),
                        side=side,
                        contracts=quantity,
                        entry_price=price,
                        entry_edge=edge,
                        forecast_temp_at_entry=forecast_temp,
                        bucket_min=m['bucket_min'],
                        bucket_max=m['bucket_max'],
                        city=city
                    )
                    tracker.add_position(position)
                    print(f"      🚀 ENTERED: {order_id}")
    
    print()
    print("=" * 70)
    tracker.print_summary()


if __name__ == "__main__":
    run_trading_cycle(cities=["NYC"], budget=20, min_edge=0.15, dry_run=True)
