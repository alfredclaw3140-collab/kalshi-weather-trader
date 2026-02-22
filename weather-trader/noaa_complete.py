"""NOAA Weather API client with high AND low temperature support."""
import requests
from datetime import datetime
from typing import Optional, Dict, List, Tuple

# NOAA grid points for major cities
CITY_GRIDS = {
    "NYC": {"gridId": "OKX", "gridX": 33, "gridY": 35},
    "LA": {"gridId": "LOX", "gridX": 155, "gridY": 45},
    "Chicago": {"gridId": "LOT", "gridX": 65, "gridY": 77},
    "Houston": {"gridId": "HGX", "gridX": 65, "gridY": 97},
    "Boston": {"gridId": "BOX", "gridX": 70, "gridY": 76},
    "Phoenix": {"gridId": "PSR", "gridX": 160, "gridY": 57},
    "Seattle": {"gridId": "SEW", "gridX": 125, "gridY": 68},
    "Atlanta": {"gridId": "FFC", "gridX": 52, "gridY": 87},
}

# Conservative position sizing - max 5% of bankroll per trade
DEFAULT_MAX_KELLY = 0.05


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
    def date(self):
        return self.start_time.date()
    
    def __repr__(self):
        return f"NOAAForecast({self.name}: {self.temperature}°{self.temperature_unit})"


def fetch_forecast(city: str = "NYC") -> List[NOAAForecast]:
    """Fetch 7-day forecast for a city."""
    if city not in CITY_GRIDS:
        raise ValueError(f"Unknown city: {city}. Available: {list(CITY_GRIDS.keys())}")
    
    grid = CITY_GRIDS[city]
    url = f"https://api.weather.gov/gridpoints/{grid['gridId']}/{grid['gridX']},{grid['gridY']}/forecast"
    
    headers = {"User-Agent": "weather-trader-bot/1.0 (research)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    
    periods = data["properties"]["periods"]
    return [NOAAForecast(p) for p in periods]


def get_high_temp_for_date(forecasts: List[NOAAForecast], target_date) -> Optional[int]:
    """Get the high temperature forecast for a specific date."""
    day_temps = [f.temperature for f in forecasts if f.date == target_date and f.is_daytime]
    return max(day_temps) if day_temps else None


def get_low_temp_for_date(forecasts: List[NOAAForecast], target_date) -> Optional[int]:
    """Get the low temperature forecast for a specific date."""
    night_temps = [f.temperature for f in forecasts if f.date == target_date and not f.is_daytime]
    return min(night_temps) if night_temps else None


def get_temps_for_date(forecasts: List[NOAAForecast], target_date) -> Tuple[Optional[int], Optional[int]]:
    """Get both high and low temps for a date.
    
    Returns: (high_temp, low_temp)
    """
    high = get_high_temp_for_date(forecasts, target_date)
    low = get_low_temp_for_date(forecasts, target_date)
    return high, low


def parse_temp_bucket(question: str) -> Optional[Dict]:
    """Parse a Kalshi market question to extract temp bucket info."""
    import re
    
    # Extract city
    city_match = re.search(r'(high|low) temp in ([A-Za-z\s]+)', question, re.IGNORECASE)
    temp_type = city_match.group(1).lower() if city_match else "high"
    city = city_match.group(2).strip() if city_match else None
    
    city_map = {
        "NYC": "NYC", "New York": "NYC", "New York City": "NYC",
        "LA": "LA", "Los Angeles": "LA",
        "Chicago": "Chicago",
        "Houston": "Houston",
        "Boston": "Boston",
        "Phoenix": "Phoenix",
        "Seattle": "Seattle",
        "Atlanta": "Atlanta",
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
    
    # Extract temp range with CORRECT boundaries
    # <38° means strictly less than 38, so max=37
    # >45° means strictly greater than 45, so min=46
    lt_match = re.search(r'<(\d+)°', question)
    gt_match = re.search(r'>(\d+)°', question)
    range_match = re.search(r'(\d+)-(\d+)°', question)
    
    if lt_match:
        return {"city": city_code, "temp_type": temp_type, "min": -999, "max": int(lt_match.group(1)) - 1, "date": date_str, "type": "lt"}
    elif gt_match:
        return {"city": city_code, "temp_type": temp_type, "min": int(gt_match.group(1)) + 1, "max": 999, "date": date_str, "type": "gt"}
    elif range_match:
        return {"city": city_code, "temp_type": temp_type, "min": int(range_match.group(1)), "max": int(range_match.group(2)), "date": date_str, "type": "range"}
    
    return None


def calculate_edge(forecast_temp: int, bucket: Dict, market_probability: float, 
                   confidence: float = 0.85, max_kelly: float = DEFAULT_MAX_KELLY) -> Dict:
    """Calculate trading edge with conservative Kelly sizing (capped at 5%)."""
    in_bucket = bucket["min"] <= forecast_temp <= bucket["max"]
    
    if in_bucket:
        our_probability = confidence
        edge = our_probability - market_probability
        
        # Kelly criterion: f* = (bp - q) / b
        if market_probability > 0:
            b = (1 / market_probability) - 1  # odds
            p = our_probability
            q = 1 - p
            kelly = (b * p - q) / b if b > 0 else 0
        else:
            kelly = 0
        
        # Apply conservative safety cap (5% default)
        kelly = min(max(kelly, 0), max_kelly)
        
        return {
            "forecast_temp": forecast_temp,
            "in_bucket": True,
            "our_probability": our_probability,
            "market_probability": market_probability,
            "edge": edge,
            "kelly_fraction": kelly,
            "recommendation": "BUY" if edge > 0.15 else "HOLD",
            "expected_return": (our_probability * (1/market_probability)) - 1 if market_probability > 0 else 0
        }
    else:
        our_probability = 1 - confidence  # We think the other side wins
        edge = market_probability - our_probability
        
        return {
            "forecast_temp": forecast_temp,
            "in_bucket": False,
            "our_probability": our_probability,
            "market_probability": market_probability,
            "edge": -edge,
            "kelly_fraction": 0,
            "recommendation": "AVOID",
            "expected_return": (our_probability * (1/market_probability)) - 1 if market_probability > 0 else 0
        }


if __name__ == "__main__":
    print("NOAA module with high/low temp support loaded.")
