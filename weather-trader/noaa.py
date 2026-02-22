"""NOAA Weather API client for fetching forecasts."""
import requests
from datetime import datetime
from typing import Optional, Dict, List

# NOAA grid points for major cities
CITY_GRIDS = {
    "NYC": {"gridId": "OKX", "gridX": 33, "gridY": 35},
    "LA": {"gridId": "LOX", "gridX": 155, "gridY": 45},
    "Chicago": {"gridId": "LOT", "gridX": 65, "gridY": 77},
    "Houston": {"gridId": "HGX", "gridX": 65, "gridY": 97},
}

class NOAAForecast:
    """Represents a single period forecast."""
    def __init__(self, period_data: dict):
        self.name = period_data.get("name", "")
        self.start_time = datetime.fromisoformat(period_data["startTime"].replace("Z", "+00:00"))
        self.end_time = datetime.fromisoformat(period_data["endTime"].replace("Z", "+00:00"))
        self.temperature = period_data.get("temperature", 0)
        self.temperature_unit = period_data.get("temperatureUnit", "F")
        self.short_forecast = period_data.get("shortForecast", "")
        self.detailed_forecast = period_data.get("detailedForecast", "")
        self.is_daytime = period_data.get("isDaytime", True)
    
    @property
    def date(self) -> datetime.date:
        return self.start_time.date()
    
    def __repr__(self):
        return f"NOAAForecast({self.name}: {self.temperature}°{self.temperature_unit})"


def fetch_forecast(city: str = "NYC") -> List[NOAAForecast]:
    """Fetch 7-day forecast for a city."""
    if city not in CITY_GRIDS:
        raise ValueError(f"Unknown city: {city}. Available: {list(CITY_GRIDS.keys())}")
    
    grid = CITY_GRIDS[city]
    url = f"https://api.weather.gov/gridpoints/{grid['gridId']}/{grid['gridX']},{grid['gridY']}/forecast"
    
    headers = {
        "User-Agent": "weather-trader-bot/1.0 (research)"
    }
    
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    
    periods = data["properties"]["periods"]
    return [NOAAForecast(p) for p in periods]


def get_high_temp_for_date(forecasts: List[NOAAForecast], target_date: datetime.date) -> Optional[int]:
    """Get the high temperature forecast for a specific date.
    
    Returns the daytime (high) temperature. If multiple daytime periods
    exist, returns the highest temperature.
    """
    day_temps = [
        f.temperature for f in forecasts 
        if f.date == target_date and f.is_daytime
    ]
    return max(day_temps) if day_temps else None


def parse_temp_bucket(question: str) -> Optional[Dict]:
    """Parse a Kalshi market question to extract temp bucket info.
    
    Example: "Will the **high temp in NYC** be 37-38° on Feb 13, 2026"
    Returns: {"city": "NYC", "min": 37, "max": 38, "date": "2026-02-13"}
    """
    import re
    
    # Extract city
    city_match = re.search(r'high temp in ([A-Za-z\s]+)', question, re.IGNORECASE)
    city = city_match.group(1).strip() if city_match else None
    
    # Map common names to our city codes
    city_map = {
        "NYC": "NYC",
        "New York": "NYC",
        "New York City": "NYC",
        "LA": "LA",
        "Los Angeles": "LA",
        "Chicago": "Chicago",
        "Houston": "Houston",
    }
    city_code = city_map.get(city, city)
    
    # Extract date
    date_match = re.search(r'(\w{3})\s+(\d{1,2}),?\s+(\d{4})', question)
    date_str = None
    if date_match:
        month_str, day, year = date_match.groups()
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        month = month_map.get(month_str, 1)
        date_str = f"{year}-{month:02d}-{int(day):02d}"
    
    # Extract temp range
    # Pattern: "37-38°" or ">42°" or "<35°"
    range_match = re.search(r'(\d+)-(\d+)°', question)
    gt_match = re.search(r'>(\d+)°', question)
    lt_match = re.search(r'<(\d+)°', question)
    
    if range_match:
        min_temp = int(range_match.group(1))
        max_temp = int(range_match.group(2))
        return {
            "city": city_code,
            "city_raw": city,
            "min": min_temp,
            "max": max_temp,
            "date": date_str,
            "type": "range"
        }
    elif gt_match:
        temp = int(gt_match.group(1))
        return {
            "city": city_code,
            "city_raw": city,
            "min": temp + 1,
            "max": 999,
            "date": date_str,
            "type": "gt"
        }
    elif lt_match:
        temp = int(lt_match.group(1))
        return {
            "city": city_code,
            "city_raw": city,
            "min": -999,
            "max": temp - 1,
            "date": date_str,
            "type": "lt"
        }
    
    return None


def calculate_edge(forecast_temp: int, bucket: Dict, market_probability: float) -> Dict:
    """Calculate trading edge based on forecast vs market price.
    
    Returns edge analysis with recommendation.
    """
    # Is the forecast in this bucket?
    in_bucket = bucket["min"] <= forecast_temp <= bucket["max"]
    
    # Calculate expected value
    # EV = (Probability of being right * payout) - (Probability of being wrong * loss)
    # If forecast says YES: P(win) ≈ 1 (high confidence in NOAA)
    # If forecast says NO: P(win) ≈ 0
    
    if in_bucket:
        # We think this bucket wins
        our_probability = 0.85  # 85% confidence in NOAA
        edge = our_probability - market_probability
        
        # Kelly criterion for position sizing (simplified)
        # f* = (bp - q) / b
        # b = odds (1/market_probability - 1)
        b = (1 / market_probability) - 1 if market_probability > 0 else 0
        p = our_probability
        q = 1 - p
        kelly = (b * p - q) / b if b > 0 else 0
        
        return {
            "forecast_temp": forecast_temp,
            "in_bucket": True,
            "our_probability": our_probability,
            "market_probability": market_probability,
            "edge": edge,
            "kelly_fraction": max(0, kelly),
            "recommendation": "BUY" if edge > 0.1 else "HOLD",
            "expected_return": (our_probability * (1/market_probability)) - 1
        }
    else:
        # We think this bucket loses
        our_probability = 0.15  # 15% chance we're wrong
        edge = market_probability - our_probability  # Edge to sell/short
        
        return {
            "forecast_temp": forecast_temp,
            "in_bucket": False,
            "our_probability": our_probability,
            "market_probability": market_probability,
            "edge": -edge,
            "kelly_fraction": 0,
            "recommendation": "AVOID",
            "expected_return": (our_probability * (1/market_probability)) - 1
        }


if __name__ == "__main__":
    # Test: Fetch NYC forecast
    print("Fetching NYC forecast...")
    forecasts = fetch_forecast("NYC")
    
    print(f"\nGot {len(forecasts)} forecast periods:")
    for f in forecasts[:5]:
        print(f"  {f.name}: {f.temperature}°{f.temperature_unit} - {f.short_forecast}")
    
    # Test: Get high for a specific date
    from datetime import date
    test_date = date(2026, 2, 23)  # Monday
    high = get_high_temp_for_date(forecasts, test_date)
    print(f"\nForecast high for {test_date}: {high}°F")
    
    # Test: Parse a market question
    test_question = "Will the **high temp in NYC** be 37-38° on Feb 23, 2026 - 37° to 38°?"
    bucket = parse_temp_bucket(test_question)
    print(f"\nParsed bucket: {bucket}")
    
    # Test: Calculate edge
    if high and bucket:
        edge = calculate_edge(high, bucket, 0.40)  # Market trading at 40%
        print(f"\nEdge analysis:")
        for k, v in edge.items():
            print(f"  {k}: {v}")
