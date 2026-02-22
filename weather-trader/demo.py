"""Demo of weather trading with simulated Kalshi markets."""
from datetime import date, timedelta
from trader import WeatherTrader, TradingOpportunity
from noaa import fetch_forecast, get_high_temp_for_date


def simulate_kalshi_markets(forecasts_by_city):
    """Simulate Kalshi-style markets for demo purposes."""
    markets = []
    
    for city, forecasts in forecasts_by_city.items():
        # Get high temps for next few days
        for days in range(1, 5):
            target_date = date.today() + timedelta(days=days)
            high = get_high_temp_for_date(forecasts, target_date)
            
            if high is None:
                continue
            
            # Create 3 buckets around the forecast
            # Bucket A: 2° below forecast
            # Bucket B: forecast ±1° (most likely)
            # Bucket C: 2° above forecast
            
            base = high
            date_str = target_date.strftime("%y%b%d").upper()
            
            buckets = [
                {
                    "ticker": f"KXHIGH{city[:3].upper()}-{date_str}-A",
                    "title": f"{city} High Temp {target_date.strftime('%b %d')} (A) {base-3}° to {base-1}°",
                    "min": base - 3,
                    "max": base - 1,
                    "yes_price": 0.15,  # Market thinks unlikely
                },
                {
                    "ticker": f"KXHIGH{city[:3].upper()}-{date_str}-B",
                    "title": f"{city} High Temp {target_date.strftime('%b %d')} (B) {base}° to {base+2}°",
                    "min": base,
                    "max": base + 2,
                    "yes_price": 0.45,  # Market thinks possible
                },
                {
                    "ticker": f"KXHIGH{city[:3].upper()}-{date_str}-C",
                    "title": f"{city} High Temp {target_date.strftime('%b %d')} (C) >{base+2}°",
                    "min": base + 3,
                    "max": 999,
                    "yes_price": 0.25,  # Market thinks less likely
                }
            ]
            
            markets.extend(buckets)
    
    return markets


def demo_trade():
    """Run a demo trading session."""
    print("=" * 70)
    print("WEATHER TRADER DEMO (Simulated Markets)")
    print("=" * 70)
    
    # Initialize trader (no Kalshi connection)
    trader = WeatherTrader(min_edge=0.10, max_kelly=0.25)
    
    # Fetch real NOAA forecasts
    print("\n📡 Fetching REAL NOAA forecasts...")
    forecasts_by_city = trader.fetch_noaa_forecasts(["NYC", "Chicago"])
    
    # Show forecast summary
    print("\n📊 FORECAST SUMMARY:")
    for city, forecasts in forecasts_by_city.items():
        print(f"\n  {city}:")
        for i, f in enumerate(forecasts[:4]):
            if f.is_daytime:
                print(f"    {f.name}: {f.temperature}°F high")
    
    # Simulate Kalshi markets
    print("\n🏛️  SIMULATING KALSHI MARKETS...")
    simulated_markets = simulate_kalshi_markets(forecasts_by_city)
    
    # Find opportunities manually
    print("\n🔍 SCANNING FOR OPPORTUNITIES...\n")
    opportunities = []
    
    for market in simulated_markets:
        city_code = market["ticker"].split("-")[0][6:]  # Extract city from ticker
        city_map = {"NYC": "NYC", "CHI": "Chicago"}
        city = city_map.get(city_code, "NYC")
        
        if city not in forecasts_by_city:
            continue
        
        # Parse date from ticker
        date_code = market["ticker"].split("-")[1]
        try:
            year = 2000 + int(date_code[:2])
            month_str = date_code[2:5].upper()
            day = int(date_code[5:])
            month_map = {
                'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
            }
            market_date = date(year, month_map.get(month_str, 1), day)
        except:
            continue
        
        # Get forecast temp
        forecast_temp = get_high_temp_for_date(forecasts_by_city[city], market_date)
        if forecast_temp is None:
            continue
        
        # Check if forecast is in this bucket
        bucket = {
            "min": market["min"],
            "max": market["max"],
            "type": "range",
            "city": city,
            "date": market_date.isoformat()
        }
        
        market_prob = market["yes_price"]
        
        # Calculate edge
        from noaa import calculate_edge
        edge_analysis = calculate_edge(forecast_temp, bucket, market_prob)
        
        if edge_analysis["edge"] >= trader.min_edge:
            opp = TradingOpportunity(
                market_ticker=market["ticker"],
                market_title=market["title"],
                city=city,
                forecast_date=market_date,
                forecast_temp=forecast_temp,
                bucket_min=bucket["min"],
                bucket_max=bucket["max"],
                market_probability=market_prob,
                our_probability=edge_analysis["our_probability"],
                edge=edge_analysis["edge"],
                kelly_fraction=min(edge_analysis["kelly_fraction"], trader.max_kelly),
                recommendation=edge_analysis["recommendation"],
                expected_return=edge_analysis["expected_return"]
            )
            opportunities.append(opp)
    
    # Sort by edge
    opportunities.sort(key=lambda x: x.edge, reverse=True)
    
    if not opportunities:
        print("❌ No opportunities found (market prices too efficient)")
        return
    
    print(f"✅ Found {len(opportunities)} opportunities:\n")
    
    budget = 100
    
    for i, opp in enumerate(opportunities[:5], 1):
        print(f"OPPORTUNITY #{i}")
        print("-" * 70)
        print(f"  Market: {opp.market_ticker}")
        print(f"  {opp.market_title}")
        print()
        print(f"  📅 Date: {opp.forecast_date.strftime('%A, %B %d')}")
        print(f"  🌡️  NOAA Forecast: {opp.forecast_temp}°F")
        print(f"  🎯 Bucket: {opp.bucket_min}° to {opp.bucket_max}°F")
        print()
        print(f"  📊 MARKET DATA:")
        print(f"     Market Price (YES): {opp.market_probability:.0%}")
        print(f"     Our Probability:    {opp.our_probability:.0%}")
        print(f"     EDGE:               {opp.edge:.0%} ✅" if opp.edge > 0 else f"     EDGE:               {opp.edge:.0%}")
        print()
        print(f"  💰 TRADE MATH:")
        print(f"     Kelly Fraction:     {opp.kelly_fraction:.0%}")
        print(f"     Risk Amount:        ${opp.kelly_fraction * budget:.2f}")
        
        # Calculate contracts
        contract_cost = opp.market_probability
        contracts = int((opp.kelly_fraction * budget) / contract_cost)
        print(f"     Contracts:          {contracts}")
        print(f"     Total Cost:         ${contracts * contract_cost:.2f}")
        print(f"     Potential Payout:   ${contracts * 1.00:.2f}")
        print(f"     Expected Return:    {opp.expected_return:.0%}")
        print()
        print(f"  🎯 RECOMMENDATION: {opp.recommendation}")
        print()
        
        if opp.recommendation == "BUY":
            print(f"  ✅ EXECUTE: Buy {contracts} YES contracts at {opp.market_probability:.0%}")
            print(f"     Rationale: NOAA predicts {opp.forecast_temp}°F, which falls in")
            print(f"     bucket {opp.bucket_min}-{opp.bucket_max}°F. Market only pricing at {opp.market_probability:.0%},")
            print(f"     giving us {opp.edge:.0%} edge.")
        print()


if __name__ == "__main__":
    demo_trade()
