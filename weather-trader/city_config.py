"""City configuration for weather trading bot."""

# Kalshi ticker series for each city
CITY_SERIES = {
    # Original cities
    "NYC": {"high": "KXHIGHNY", "low": "KXLOWNY"},
    "Chicago": {"high": "KXHIGHCHI", "low": "KXLOWCHI"},
    "Houston": {"high": "KXHIGHTHOU", "low": "KXLOWHOU"},
    "Boston": {"high": "KXHIGHTBOS", "low": "KXLOWBOS"},
    "Phoenix": {"high": "KXHIGHTPHX", "low": "KXLOWPHX"},
    "Seattle": {"high": "KXHIGHTSEA", "low": "KXLOWSEA"},
    "LA": {"high": "KXHIGHLAX", "low": "KXLOWLAX"},
    "Atlanta": {"high": "KXHIGHTATL", "low": "KXLOWATL"},
    
    # New cities
    "Dallas": {"high": "KXHIGHTDAL", "low": "KXLOWTDAL"},
    "Denver": {"high": "KXHIGHTDEN", "low": "KXLOWTDEN"},
    "Minneapolis": {"high": "KXHIGHTMSP", "low": "KXLOWTMSP"},
    "NewOrleans": {"high": "KXHIGHTMSY", "low": "KXLOWTMSY"},
    "Philadelphia": {"high": "KXHIGHTPHL", "low": "KXLOWTPHL"},
    "SanFrancisco": {"high": "KXHIGHTSFO", "low": "KXLOWTSFO"},
    "DC": {"high": "KXHIGHTDCA", "low": "KXLOWTDCA"},
    "Miami": {"high": "KXHIGHTMIA", "low": "KXLOWTMIA"},
    "Detroit": {"high": "KXHIGHTDTW", "low": "KXLOWTDTW"},
    "Portland": {"high": "KXHIGHTPDX", "low": "KXLOWTPDX"},
}

# NOAA grid points for each city (for forecast fetching)
CITY_GRID_POINTS = {
    # Original
    "NYC": {"office": "OKX", "gridX": 33, "gridY": 35},
    "Chicago": {"office": "LOT", "gridX": 68, "gridY": 73},
    "Houston": {"office": "HGX", "gridX": 65, "gridY": 97},
    "Boston": {"office": "BOX", "gridX": 71, "gridY": 90},
    "Phoenix": {"office": "PSR", "gridX": 158, "gridY": 58},
    "Seattle": {"office": "SEW", "gridX": 124, "gridY": 68},
    "LA": {"office": "LOX", "gridX": 154, "gridY": 44},
    "Atlanta": {"office": "FFC", "gridX": 51, "gridY": 87},
    
    # New
    "Dallas": {"office": "FWD", "gridX": 89, "gridY": 109},
    "Denver": {"office": "BOU", "gridX": 63, "gridY": 61},
    "Minneapolis": {"office": "MPX", "gridX": 107, "gridY": 71},
    "NewOrleans": {"office": "LIX", "gridX": 71, "gridY": 84},
    "Philadelphia": {"office": "PHI", "gridX": 49, "gridY": 75},
    "SanFrancisco": {"office": "MTR", "gridX": 85, "gridY": 105},
    "DC": {"office": "LWX", "gridX": 97, "gridY": 71},
    "Miami": {"office": "MFL", "gridX": 110, "gridY": 50},
    "Detroit": {"office": "DTX", "gridX": 63, "gridY": 34},
    "Portland": {"office": "PQR", "gridX": 116, "gridY": 87},
}

# Weather correlation regions (cities affected by same storm systems)
WEATHER_REGIONS = {
    "northeast": ["NYC", "Boston", "Philadelphia", "DC"],
    "midwest": ["Chicago", "Detroit", "Minneapolis"],
    "southeast": ["Atlanta", "Miami", "NewOrleans"],
    "southwest": ["Phoenix", "LA", "Dallas"],
    "northwest": ["Seattle", "Portland", "SanFrancisco"],
    "mountain": ["Denver"],
    "texas": ["Houston", "Dallas", "NewOrleans"],
}

def get_city_region(city: str) -> str:
    """Get weather region for a city."""
    for region, cities in WEATHER_REGIONS.items():
        if city in cities:
            return region
    return "unknown"

def get_cities_in_region(region: str) -> list:
    """Get all cities in a weather region."""
    return WEATHER_REGIONS.get(region, [])

def check_regional_correlation(city1: str, city2: str) -> bool:
    """Check if two cities are in the same weather region."""
    region1 = get_city_region(city1)
    region2 = get_city_region(city2)
    return region1 == region2 and region1 != "unknown"


if __name__ == "__main__":
    print("Cities Configured:")
    print(f"Total cities: {len(CITY_SERIES)}")
    print("\nBy Region:")
    for region, cities in WEATHER_REGIONS.items():
        print(f"  {region}: {', '.join(cities)}")
    
    print("\nCity Ticker Examples:")
    for city in ["NYC", "Dallas", "Miami", "Denver"]:
        if city in CITY_SERIES:
            print(f"  {city}: {CITY_SERIES[city]}")
