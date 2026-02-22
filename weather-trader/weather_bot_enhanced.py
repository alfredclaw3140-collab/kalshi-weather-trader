"""Enhanced Weather Trading Bot with Alerts, Pre-Resolution Checks, and Price Monitoring."""
import requests
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

from kalshi_auth import get_auth_headers
from noaa_complete import fetch_forecast, get_high_temp_for_date, get_low_temp_for_date
from noaa_with_alerts import (
    check_significant_weather_events, ForecastTracker, 
    get_forecast_snapshot, has_forecast_changed
)
from position_tracker import PositionTracker, Position

API_BASE = "https://api.elections.kalshi.com"

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
class TradingAlert:
    """Represents a trading alert condition."""
    alert_type: str  # "weather", "price_movement", "pre_resolution"
    severity: str    # "high", "medium", "low"
    message: str
    action_required: bool
    market_ticker: Optional[str] = None


def check_price_movement(ticker: str, entry_price: float, 
                        threshold: float = 0.10) -> TradingAlert:
    """Check if market price has moved significantly from entry.
    
    Args:
        ticker: Market ticker
        entry_price: Price when position was entered
        threshold: Movement threshold (0.10 = 10%)
    
    Returns:
        TradingAlert if movement detected, None otherwise
    """
    path = f"/trade-api/v2/markets/{ticker}"
    headers = get_auth_headers("GET", path)
    
    try:
        resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
        if resp.status_code != 200:
            return None
        
        market = resp.json().get("market", {})
        current_price = market.get("yes_ask", 0) / 100
        
        price_change = abs(current_price - entry_price) / entry_price if entry_price > 0 else 0
        
        if price_change >= threshold:
            direction = "up" if current_price > entry_price else "down"
            return TradingAlert(
                alert_type="price_movement",
                severity="high" if price_change > 0.20 else "medium",
                message=f"Price moved {price_change:.0%} {direction} from entry",
                action_required=True,
                market_ticker=ticker
            )
        
        return None
    except Exception as e:
        print(f"⚠️  Error checking price for {ticker}: {e}")
        return None


def check_pre_resolution_positions(tracker: PositionTracker, 
                                  hours_before: int = 6) -> List[TradingAlert]:
    """Check positions that resolve soon and need verification.
    
    Args:
        tracker: Position tracker
        hours_before: Hours before resolution to trigger check
    
    Returns:
        List of alerts for positions needing attention
    """
    alerts = []
    open_positions = tracker.get_open_positions()
    now = datetime.now()
    
    for pos in open_positions:
        res_date = datetime.fromisoformat(pos.resolution_date)
        time_until = res_date - now
        hours_until = time_until.total_seconds() / 3600
        
        if 0 < hours_until <= hours_before:
            alerts.append(TradingAlert(
                alert_type="pre_resolution",
                severity="high",
                message=f"{pos.ticker} resolves in {hours_until:.1f} hours - verify forecast",
                action_required=True,
                market_ticker=pos.ticker
            ))
    
    return alerts


def run_weather_check_with_alerts(cities: List[str] = None, 
                                  check_alerts: bool = True,
                                  dry_run: bool = True):
    """Run weather check with all alert types integrated."""
    cities = cities or ["NYC"]
    tracker = PositionTracker()
    forecast_tracker = ForecastTracker()
    
    print("=" * 70)
    print("🌦️  ENHANCED WEATHER TRADING BOT")
    print("=" * 70)
    print(f"Features: Weather Alerts | Price Movement | Pre-Resolution Checks")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print()
    
    all_alerts = []
    
    # 1. Check for significant weather events
    if check_alerts:
        print("🚨 CHECKING WEATHER ALERTS")
        print("-" * 70)
        
        for city in cities:
            weather_check = check_significant_weather_events(city)
            
            if weather_check["has_significant_event"]:
                alert = TradingAlert(
                    alert_type="weather",
                    severity="high",
                    message=f"{city}: {', '.join(weather_check['events'])}",
                    action_required=True
                )
                all_alerts.append(alert)
                print(f"   ⚠️  {alert.message}")
                print(f"      Action: Check markets immediately!")
            else:
                print(f"   ✅ {city}: No significant weather alerts")
        
        print()
    
    # 2. Check pre-resolution positions
    print("⏰ CHECKING PRE-RESOLUTION POSITIONS")
    print("-" * 70)
    
    pre_res_alerts = check_pre_resolution_positions(tracker, hours_before=6)
    all_alerts.extend(pre_res_alerts)
    
    if pre_res_alerts:
        for alert in pre_res_alerts:
            print(f"   ⚠️  {alert.message}")
    else:
        print("   ✅ No positions resolving in next 6 hours")
    
    print()
    
    # 3. Check price movements on open positions
    print("📈 CHECKING PRICE MOVEMENTS")
    print("-" * 70)
    
    open_positions = tracker.get_open_positions()
    price_alerts = []
    
    for pos in open_positions:
        alert = check_price_movement(pos.ticker, pos.entry_price, threshold=0.10)
        if alert:
            price_alerts.append(alert)
            print(f"   ⚠️  {pos.ticker}: {alert.message}")
    
    if not price_alerts and not open_positions:
        print("   ℹ️  No open positions to monitor")
    elif not price_alerts:
        print("   ✅ No significant price movements")
    
    all_alerts.extend(price_alerts)
    print()
    
    # 4. Forecast change detection
    print("🔄 CHECKING FORECAST CHANGES")
    print("-" * 70)
    
    today = date.today()
    for city in cities:
        for days in range(1, 3):  # Check next 2 days
            check_date = today + timedelta(days=days)
            result = forecast_tracker.check_and_update(city, check_date)
            
            if result.get("first_check"):
                print(f"   📊 {city} {check_date}: First check recorded")
            elif result.get("changed"):
                print(f"   🔄 {city} {check_date}: Forecast changed!")
                for change in result["changes"]:
                    print(f"      - {change}")
            else:
                print(f"   ✅ {city} {check_date}: No change")
    
    print()
    
    # 5. Summary
    print("=" * 70)
    print("📋 ALERT SUMMARY")
    print("=" * 70)
    
    high_priority = [a for a in all_alerts if a.severity == "high" and a.action_required]
    medium_priority = [a for a in all_alerts if a.severity == "medium" and a.action_required]
    
    if high_priority:
        print(f"\n🔴 HIGH PRIORITY ({len(high_priority)}):")
        for alert in high_priority:
            print(f"   - {alert.alert_type}: {alert.message}")
    
    if medium_priority:
        print(f"\n🟡 MEDIUM PRIORITY ({len(medium_priority)}):")
        for alert in medium_priority:
            print(f"   - {alert.alert_type}: {alert.message}")
    
    if not all_alerts:
        print("\n✅ No alerts - all clear!")
    
    print()
    return all_alerts


if __name__ == "__main__":
    # Run enhanced check
    alerts = run_weather_check_with_alerts(
        cities=["NYC"],
        check_alerts=True,
        dry_run=True
    )
