"""Dynamic position sizing with risk management."""
from typing import Optional

# Import weather regions for correlation tracking
try:
    from city_config import WEATHER_REGIONS
except ImportError:
    # Fallback if city_config not available
    WEATHER_REGIONS = {
        "northeast": ["NYC", "Boston", "Philadelphia", "DC"],
        "midwest": ["Chicago", "Detroit", "Minneapolis"],
        "southeast": ["Atlanta", "Miami", "NewOrleans"],
        "southwest": ["Phoenix", "LA", "Dallas"],
        "northwest": ["Seattle", "Portland", "SanFrancisco"],
        "mountain": ["Denver"],
        "texas": ["Houston", "Dallas", "NewOrleans"],
    }

# Risk limits
DEFAULT_KELLY = 0.05          # 5% base sizing
MODERATE_EDGE_KELLY = 0.04    # 4% for moderate edge (15-20%)
HIGH_EDGE_KELLY = 0.10        # 10% for high edge (>25%)
REDUCED_KELLY = 0.03          # 3% when over-exposed
MAX_TOTAL_EXPOSURE = 0.30     # 30% max bankroll deployed
MAX_CONCURRENT_POSITIONS = 6  # Hard limit on positions
HIGH_EDGE_THRESHOLD = 0.25    # 25% edge triggers higher sizing
MODERATE_EDGE_THRESHOLD = 0.20  # 20% edge threshold


def calculate_position_size(
    edge: float,
    current_exposure: float,
    open_positions_count: int,
    days_to_resolution: int,
    similar_city_positions: int = 0
) -> float:
    """Calculate position size with dynamic risk management.
    
    Args:
        edge: Calculated edge (0.15 = 15%)
        current_exposure: Current % of bankroll deployed
        open_positions_count: Number of open positions
        days_to_resolution: Days until market resolves
        similar_city_positions: Positions in same weather region
    
    Returns:
        Kelly fraction (0.0 to 0.10)
    """
    
    # Determine base Kelly from edge
    if edge >= HIGH_EDGE_THRESHOLD:
        kelly = HIGH_EDGE_KELLY  # 10% for 25%+ edge
    elif edge < MODERATE_EDGE_THRESHOLD:
        kelly = MODERATE_EDGE_KELLY  # 4% for <20% edge
    else:
        kelly = DEFAULT_KELLY  # 5% for 20-25% edge
    
    # Reduce if near-term resolution (less time for thesis to play out)
    if days_to_resolution < 1:
        kelly *= 0.5  # 50% reduction for same-day resolution
    elif days_to_resolution == 1:
        kelly *= 0.8  # 20% reduction for next-day resolution
    
    # Reduce if already over-exposed
    if current_exposure >= 0.20:  # Already 20% deployed
        kelly = REDUCED_KELLY
    
    # Zero if max exposure hit
    if current_exposure >= MAX_TOTAL_EXPOSURE:
        return 0.0
    
    # Zero if too many positions
    if open_positions_count >= MAX_CONCURRENT_POSITIONS:
        return 0.0
    
    # Reduce if similar city exposure (weather correlation risk)
    if similar_city_positions >= 2:
        kelly *= 0.5  # 50% reduction if 2+ similar positions
    
    # Final cap check
    potential_new_exposure = current_exposure + kelly
    if potential_new_exposure > MAX_TOTAL_EXPOSURE:
        # Adjust down to fit within limit
        kelly = MAX_TOTAL_EXPOSURE - current_exposure
        if kelly < 0.01:  # Less than 1% not worth trading
            return 0.0
    
    return max(0.0, min(kelly, HIGH_EDGE_KELLY))


def check_weather_correlation_risk(
    new_city: str,
    existing_positions: list
) -> int:
    """Check how many positions are in same weather region.
    
    Returns:
        Count of positions in similar weather region
    """
    # Find which region new city is in
    new_city_region = None
    for region, cities in WEATHER_REGIONS.items():
        if new_city in cities:
            new_city_region = region
            break
    
    if not new_city_region:
        return 0
    
    # Count existing positions in same region
    count = 0
    for pos in existing_positions:
        city = pos.get("city", "")
        if city in WEATHER_REGIONS.get(new_city_region, []):
            count += 1
    
    return count


def get_regional_exposure(
    city: str,
    existing_positions: list
) -> tuple:
    """Get regional exposure info for a city.
    
    Returns:
        (region_name, count_of_positions_in_region)
    """
    region = None
    for r, cities in WEATHER_REGIONS.items():
        if city in cities:
            region = r
            break
    
    if not region:
        return ("unknown", 0)
    
    count = sum(1 for pos in existing_positions 
                if pos.get("city", "") in WEATHER_REGIONS[region])
    
    return (region, count)


def calculate_contract_quantity(
    kelly_fraction: float,
    bankroll: float,
    market_price: float
) -> int:
    """Calculate number of contracts to buy.
    
    Args:
        kelly_fraction: Position size (0.05 = 5%)
        bankroll: Total account balance
        market_price: Price per contract (0.40 = 40¢)
    
    Returns:
        Number of contracts (integer)
    """
    if kelly_fraction <= 0 or market_price <= 0:
        return 0
    
    position_dollar_amount = kelly_fraction * bankroll
    contract_price = market_price  # Price is already in dollars (0.40 = $0.40)
    
    quantity = int(position_dollar_amount / contract_price)
    
    # Minimum trade size
    if quantity < 1:
        return 0
    
    # Maximum single position (safety) - 15% of bankroll
    max_position_value = bankroll * 0.15
    max_contracts = int(max_position_value / market_price)
    
    return min(quantity, max_contracts)


if __name__ == "__main__":
    # Test examples
    print("Position Sizing Examples:")
    print("-" * 60)
    
    # Example 1: Base case (15% edge = moderate = 4%)
    size = calculate_position_size(edge=0.15, current_exposure=0.05, 
                                   open_positions_count=1, days_to_resolution=3)
    print(f"15% edge (<20%), 5% exposed, 3 days: {size:.1%} Kelly")
    
    # Example 2: 20% edge = default = 5%
    size = calculate_position_size(edge=0.20, current_exposure=0.05,
                                   open_positions_count=1, days_to_resolution=2)
    print(f"20% edge (20-25%), 5% exposed, 2 days: {size:.1%} Kelly")
    
    # Example 3: High edge = 10%
    size = calculate_position_size(edge=0.30, current_exposure=0.05,
                                   open_positions_count=1, days_to_resolution=2)
    print(f"30% edge (>25%), 5% exposed, 2 days: {size:.1%} Kelly (boosted)")
    
    # Example 4: Over-exposed
    size = calculate_position_size(edge=0.20, current_exposure=0.25,
                                   open_positions_count=5, days_to_resolution=2)
    print(f"20% edge, 25% exposed, 5 positions: {size:.1%} Kelly (reduced)")
    
    # Example 5: Max exposure hit
    size = calculate_position_size(edge=0.25, current_exposure=0.30,
                                   open_positions_count=3, days_to_resolution=2)
    print(f"25% edge, 30% exposed: {size:.1%} Kelly (blocked)")
    
    # Example 6: Same day resolution
    size = calculate_position_size(edge=0.20, current_exposure=0.05,
                                   open_positions_count=1, days_to_resolution=0)
    print(f"20% edge, same-day resolution: {size:.1%} Kelly (50% reduced)")
    
    # Regional exposure test
    print("\nRegional Exposure Examples:")
    print("-" * 60)
    
    existing = [{"city": "NYC"}, {"city": "Boston"}]
    region, count = get_regional_exposure("Philadelphia", existing)
    print(f"Philly with {count} existing northeast positions: {region} region")
    
    region, count = get_regional_exposure("Dallas", existing)
    print(f"Dallas with northeast exposure: {region} region (no correlation)")
