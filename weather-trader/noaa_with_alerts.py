"""NOAA Weather API with alert checking and forecast change detection."""
import requests
import hashlib
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, asdict

from noaa_complete import fetch_forecast, get_high_temp_for_date, get_low_temp_for_date


def fetch_noaa_alerts(city: str = "NYC") -> List[Dict]:
    """Fetch active weather alerts for a city.
    
    Returns list of alerts like:
    - Winter Storm Warning
    - High Wind Warning  
    - Blizzard Warning
    - Extreme Cold Warning
    """
    # Map cities to NWS zones (simplified - just NYC for now)
    zone_map = {
        "NYC": "NYZ072",  # New York County
        "Chicago": "ILZ014",
        "Boston": "MAZ016",
    }
    
    zone = zone_map.get(city)
    if not zone:
        return []
    
    url = f"https://api.weather.gov/alerts/active?zone={zone}"
    headers = {"User-Agent": "weather-trader-bot/1.0 (research)"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        alerts = []
        for alert in data.get("features", []):
            props = alert.get("properties", {})
            alerts.append({
                "event": props.get("event", "Unknown"),
                "severity": props.get("severity", "Unknown"),
                "headline": props.get("headline", ""),
                "description": props.get("description", "")[:200],
                "effective": props.get("effective"),
                "expires": props.get("expires"),
            })
        
        return alerts
    except Exception as e:
        print(f"⚠️  Error fetching alerts for {city}: {e}")
        return []


def check_significant_weather_events(city: str = "NYC") -> Dict:
    """Check for weather events that could move markets.
    
    Returns dict with:
    - has_significant_event: bool
    - events: list of event descriptions
    - should_check_now: bool (if major event detected)
    """
    alerts = fetch_noaa_alerts(city)
    
    significant_events = []
    should_check_now = False
    
    high_impact_events = [
        "Winter Storm", "Blizzard", "Hurricane", "Tropical Storm",
        "Extreme Cold", "Extreme Heat", "High Wind", "Severe Thunderstorm",
        "Tornado", "Flood", "Flash Flood"
    ]
    
    for alert in alerts:
        event = alert["event"]
        severity = alert["severity"]
        
        # Check if this is a high-impact event
        is_high_impact = any(impact in event for impact in high_impact_events)
        is_extreme = severity in ["Extreme", "Severe"]
        
        if is_high_impact or is_extreme:
            significant_events.append(f"{severity} {event}")
            should_check_now = True
    
    return {
        "has_significant_event": len(significant_events) > 0,
        "events": significant_events,
        "should_check_now": should_check_now,
        "total_alerts": len(alerts),
        "raw_alerts": alerts
    }


@dataclass
class ForecastSnapshot:
    """Snapshot of a forecast for comparison."""
    city: str
    date: str
    high_temp: Optional[int]
    low_temp: Optional[int]
    fetched_at: str
    update_time: str  # NOAA's update timestamp
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @property
    def fingerprint(self) -> str:
        """Unique fingerprint for this forecast."""
        return hashlib.md5(
            f"{self.city}:{self.date}:{self.high_temp}:{self.low_temp}:{self.update_time}".encode()
        ).hexdigest()[:16]


def get_forecast_snapshot(city: str, target_date: date) -> ForecastSnapshot:
    """Get a snapshot of the forecast for a specific date."""
    forecasts = fetch_forecast(city)
    
    # Get NOAA update time from metadata
    grid = {"gridId": "OKX", "gridX": 33, "gridY": 35} if city == "NYC" else None
    if city in ["LA", "Chicago", "Houston", "Boston", "Phoenix", "Seattle", "Atlanta"]:
        from noaa_complete import CITY_GRIDS
        grid = CITY_GRIDS.get(city)
    
    update_time = datetime.now().isoformat()
    if grid:
        try:
            url = f"https://api.weather.gov/gridpoints/{grid['gridId']}/{grid['gridX']},{grid['gridY']}/forecast"
            headers = {"User-Agent": "weather-trader-bot/1.0"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                props = resp.json().get("properties", {})
                update_time = props.get("updateTime", update_time)
        except:
            pass
    
    high = get_high_temp_for_date(forecasts, target_date)
    low = get_low_temp_for_date(forecasts, target_date)
    
    return ForecastSnapshot(
        city=city,
        date=target_date.isoformat(),
        high_temp=high,
        low_temp=low,
        fetched_at=datetime.now().isoformat(),
        update_time=update_time
    )


def has_forecast_changed(old_snapshot: ForecastSnapshot, 
                         new_snapshot: ForecastSnapshot) -> Dict:
    """Compare two forecast snapshots to detect changes.
    
    Returns:
        {
            "changed": bool,
            "changes": list of change descriptions,
            "high_changed": bool,
            "low_changed": bool,
            "high_diff": int (new - old),
            "low_diff": int (new - old)
        }
    """
    changes = []
    high_changed = old_snapshot.high_temp != new_snapshot.high_temp
    low_changed = old_snapshot.low_temp != new_snapshot.low_temp
    
    high_diff = None
    low_diff = None
    
    if high_changed:
        if old_snapshot.high_temp and new_snapshot.high_temp:
            high_diff = new_snapshot.high_temp - old_snapshot.high_temp
            direction = "up" if high_diff > 0 else "down"
            changes.append(f"High temp changed from {old_snapshot.high_temp}°F to {new_snapshot.high_temp}°F ({direction} {abs(high_diff)}°F)")
        elif new_snapshot.high_temp:
            changes.append(f"High temp now available: {new_snapshot.high_temp}°F")
    
    if low_changed:
        if old_snapshot.low_temp and new_snapshot.low_temp:
            low_diff = new_snapshot.low_temp - old_snapshot.low_temp
            direction = "up" if low_diff > 0 else "down"
            changes.append(f"Low temp changed from {old_snapshot.low_temp}°F to {new_snapshot.low_temp}°F ({direction} {abs(low_diff)}°F)")
        elif new_snapshot.low_temp:
            changes.append(f"Low temp now available: {new_snapshot.low_temp}°F")
    
    # Check if NOAA updated their forecast
    noaa_updated = old_snapshot.update_time != new_snapshot.update_time
    if noaa_updated:
        changes.append(f"NOAA updated forecast at {new_snapshot.update_time}")
    
    return {
        "changed": high_changed or low_changed or noaa_updated,
        "changes": changes,
        "high_changed": high_changed,
        "low_changed": low_changed,
        "high_diff": high_diff,
        "low_diff": low_diff,
        "noaa_updated": noaa_updated
    }


class ForecastTracker:
    """Track forecast history to detect changes."""
    
    def __init__(self):
        self.history: Dict[str, ForecastSnapshot] = {}
    
    def record_snapshot(self, snapshot: ForecastSnapshot):
        """Record a new forecast snapshot."""
        key = f"{snapshot.city}:{snapshot.date}"
        self.history[key] = snapshot
    
    def get_last_snapshot(self, city: str, target_date: date) -> Optional[ForecastSnapshot]:
        """Get the last recorded snapshot for a city/date."""
        key = f"{city}:{target_date.isoformat()}"
        return self.history.get(key)
    
    def check_and_update(self, city: str, target_date: date) -> Dict:
        """Check for forecast changes and update history.
        
        Returns comparison result with changes detected.
        """
        new_snapshot = get_forecast_snapshot(city, target_date)
        old_snapshot = self.get_last_snapshot(city, target_date)
        
        if old_snapshot is None:
            # First time checking this date
            self.record_snapshot(new_snapshot)
            return {
                "first_check": True,
                "changed": False,
                "changes": ["First forecast check"],
                "snapshot": new_snapshot
            }
        
        # Compare
        comparison = has_forecast_changed(old_snapshot, new_snapshot)
        
        # Update history
        self.record_snapshot(new_snapshot)
        comparison["snapshot"] = new_snapshot
        comparison["first_check"] = False
        
        return comparison


if __name__ == "__main__":
    # Test
    print("Testing NOAA alerts for NYC...")
    alerts = check_significant_weather_events("NYC")
    print(f"Significant events: {alerts['has_significant_event']}")
    if alerts['has_significant_event']:
        print(f"Events: {alerts['events']}")
