"""Main weather trading bot engine."""
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

from noaa import fetch_forecast, get_high_temp_for_date, calculate_edge
from kalshi import KalshiClient, parse_kalshi_weather_market


@dataclass
class TradingOpportunity:
    """Represents a potential trade."""
    market_ticker: str
    market_title: str
    city: str
    forecast_date: date
    forecast_temp: int
    bucket_min: int
    bucket_max: int
    market_probability: float
    our_probability: float
    edge: float
    kelly_fraction: float
    recommendation: str
    expected_return: float


class WeatherTrader:
    """Weather prediction market trading bot."""
    
    def __init__(self, kalshi_client: KalshiClient = None, 
                 min_edge: float = 0.15, max_kelly: float = 0.25):
        """Initialize the trader.
        
        Args:
            kalshi_client: Kalshi API client (None for forecast-only mode)
            min_edge: Minimum edge to consider a trade (0.15 = 15%)
            max_kelly: Maximum Kelly fraction to use (safety cap)
        """
        self.kalshi = kalshi_client
        self.min_edge = min_edge
        self.max_kelly = max_kelly
        self.forecasts = {}  # Cache forecasts by city
    
    def fetch_noaa_forecasts(self, cities: List[str] = None) -> Dict:
        """Fetch forecasts for all tracked cities."""
        cities = cities or ["NYC", "LA", "Chicago"]
        
        for city in cities:
            try:
                print(f"Fetching forecast for {city}...")
                self.forecasts[city] = fetch_forecast(city)
            except Exception as e:
                print(f"  Error fetching {city}: {e}")
        
        return self.forecasts
    
    def get_kalshi_weather_markets(self, city: str = None) -> List[Dict]:
        """Get all relevant weather markets from Kalshi."""
        if not self.kalshi:
            print("No Kalshi client configured")
            return []
        
        # Map city to Kalshi series
        series_map = {
            "NYC": ["KXHIGHNY", "KXLOWNY"],
            "LA": ["KXHIGHLA", "KXLOWLA"],
            "Chicago": ["KXHIGHCHI", "KXLOWCHI"],
        }
        
        all_markets = []
        
        if city:
            series_list = series_map.get(city, [])
        else:
            series_list = [s for sl in series_map.values() for s in sl]
        
        for series in series_list:
            try:
                markets = self.kalshi.get_markets(event_ticker=series, status="open")
                all_markets.extend(markets)
            except Exception as e:
                print(f"  Error fetching {series}: {e}")
        
        return all_markets
    
    def find_opportunities(self, city: str = None, 
                          days_ahead: int = 7) -> List[TradingOpportunity]:
        """Find trading opportunities by matching forecasts to markets.
        
        Args:
            city: Specific city to check (None for all)
            days_ahead: How many days ahead to look
        """
        opportunities = []
        
        # Ensure we have forecasts
        if not self.forecasts:
            self.fetch_noaa_forecasts([city] if city else None)
        
        # Get Kalshi markets
        markets = self.get_kalshi_weather_markets(city)
        
        # Match markets to forecasts
        for market in markets:
            parsed = parse_kalshi_weather_market(market)
            if not parsed or not parsed["bucket"]:
                continue
            
            # Skip if no forecast for this city
            if parsed["city"] not in self.forecasts:
                continue
            
            # Skip if date is too far out
            if not parsed["date"]:
                continue
            
            days_until = (parsed["date"] - date.today()).days
            if days_until < 0 or days_until > days_ahead:
                continue
            
            # Get forecast temp for this date
            forecasts = self.forecasts[parsed["city"]]
            forecast_temp = get_high_temp_for_date(forecasts, parsed["date"])
            
            if forecast_temp is None:
                continue
            
            # Calculate edge
            bucket = parsed["bucket"]
            bucket["city"] = parsed["city"]
            bucket["date"] = parsed["date"].isoformat()
            
            market_prob = parsed.get("yes_price", 0)
            if market_prob <= 0:
                continue
            
            edge_analysis = calculate_edge(forecast_temp, bucket, market_prob)
            
            # Skip if edge is too small
            if edge_analysis["edge"] < self.min_edge:
                continue
            
            opp = TradingOpportunity(
                market_ticker=parsed["ticker"],
                market_title=parsed["title"],
                city=parsed["city"],
                forecast_date=parsed["date"],
                forecast_temp=forecast_temp,
                bucket_min=bucket["min"],
                bucket_max=bucket["max"],
                market_probability=market_prob,
                our_probability=edge_analysis["our_probability"],
                edge=edge_analysis["edge"],
                kelly_fraction=min(edge_analysis["kelly_fraction"], self.max_kelly),
                recommendation=edge_analysis["recommendation"],
                expected_return=edge_analysis["expected_return"]
            )
            
            opportunities.append(opp)
        
        # Sort by edge descending
        opportunities.sort(key=lambda x: x.edge, reverse=True)
        return opportunities
    
    def execute_trade(self, opportunity: TradingOpportunity, 
                     budget: float = 100) -> Dict:
        """Execute a trade on Kalshi.
        
        Args:
            opportunity: The opportunity to trade
            budget: Max dollars to risk
        """
        if not self.kalshi:
            return {"error": "No Kalshi client configured"}
        
        # Calculate position size
        # Risk = Kelly fraction * budget
        risk_amount = opportunity.kelly_fraction * budget
        
        # Number of contracts
        # Each contract costs market_probability * 1.00
        contract_cost = opportunity.market_probability
        max_contracts = int(risk_amount / contract_cost)
        
        if max_contracts < 1:
            return {"error": "Risk amount too small for minimum position"}
        
        print(f"Executing trade:")
        print(f"  Market: {opportunity.market_ticker}")
        print(f"  Side: YES")
        print(f"  Contracts: {max_contracts}")
        print(f"  Price: {opportunity.market_probability:.2%}")
        print(f"  Cost: ${max_contracts * contract_cost:.2f}")
        
        try:
            result = self.kalshi.place_order(
                market_ticker=opportunity.market_ticker,
                side="yes",
                quantity=max_contracts,
                price=opportunity.market_probability
            )
            return result
        except Exception as e:
            return {"error": str(e)}
    
    def run_scan(self, execute: bool = False, budget: float = 100):
        """Run a full scan and optionally execute trades.
        
        Args:
            execute: Actually place trades (False = dry run)
            budget: Max budget per trade
        """
        print("=" * 60)
        print(f"Weather Trader Scan - {datetime.now()}")
        print("=" * 60)
        
        # Fetch forecasts
        print("\n📡 Fetching NOAA forecasts...")
        self.fetch_noaa_forecasts()
        
        # Find opportunities
        print("\n🔍 Scanning Kalshi markets...")
        opportunities = self.find_opportunities()
        
        if not opportunities:
            print("\n❌ No opportunities found")
            return
        
        print(f"\n✅ Found {len(opportunities)} opportunities:")
        print()
        
        for i, opp in enumerate(opportunities[:5], 1):
            print(f"{i}. {opp.market_ticker}")
            print(f"   {opp.market_title[:60]}...")
            print(f"   📅 Date: {opp.forecast_date}")
            print(f"   🌡️  Forecast: {opp.forecast_temp}°F | Bucket: {opp.bucket_min}-{opp.bucket_max}°F")
            print(f"   📊 Market: {opp.market_probability:.1%} | Our: {opp.our_probability:.1%}")
            print(f"   📈 Edge: {opp.edge:.1%} | Kelly: {opp.kelly_fraction:.1%}")
            print(f"   💰 Expected Return: {opp.expected_return:.1%}")
            print(f"   🎯 Recommendation: {opp.recommendation}")
            print()
            
            if execute and opp.recommendation == "BUY":
                result = self.execute_trade(opp, budget)
                print(f"   📝 Trade result: {result}")
                print()


if __name__ == "__main__":
    # Demo run (no trades)
    trader = WeatherTrader(min_edge=0.10)
    trader.run_scan(execute=False)
