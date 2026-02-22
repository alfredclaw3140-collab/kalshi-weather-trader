"""BTC 15-minute arbitrage strategy for Kalshi."""
import requests
import json
import time
from datetime import datetime
from typing import Optional, Dict, Tuple

from kalshi_auth import get_auth_headers

API_BASE = "https://api.elections.kalshi.com"


class BTCPriceFeed:
    """Get real-time BTC price from Coinbase."""
    
    @staticmethod
    def get_price() -> Optional[float]:
        """Get current BTC price from Coinbase API."""
        try:
            resp = requests.get(
                "https://api.coinbase.com/v2/exchange-rates?currency=BTC",
                timeout=10
            )
            if resp.status_code == 200:
                rates = resp.json().get("data", {}).get("rates", {})
                if "USD" in rates:
                    # Rate is USD per 1 BTC
                    return float(rates["USD"])
        except Exception as e:
            print(f"⚠️  Coinbase API error: {e}")
        
        # Fallback to CoinGecko
        try:
            resp = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "bitcoin", "vs_currencies": "usd"},
                timeout=10
            )
            if resp.status_code == 200:
                return resp.json()["bitcoin"]["usd"]
        except Exception as e:
            print(f"⚠️  CoinGecko API error: {e}")
        
        return None


class KalshiBTCMarket:
    """Represents a Kalshi BTC market."""
    
    def __init__(self, ticker: str, title: str, yes_price: float, no_price: float,
                 reference_price: float, close_date: str):
        self.ticker = ticker
        self.title = title
        self.yes_price = yes_price  # 0.0 to 1.0
        self.no_price = no_price    # 0.0 to 1.0
        self.reference_price = reference_price  # The BTC price this market is based on
        self.close_date = close_date
    
    @property
    def implied_btc_price(self) -> float:
        """Calculate implied BTC price from YES price."""
        # If YES is at 60%, market implies BTC will be above strike
        # This is a simplification - actual calculation depends on market structure
        return self.reference_price
    
    @property
    def price_sum(self) -> float:
        """YES + NO should equal $1.00 (or close to it)."""
        return self.yes_price + self.no_price
    
    @property
    def has_internal_arbitrage(self) -> Tuple[bool, float]:
        """Check if YES + NO != $1.00."""
        # Allow 1% tolerance for spreads
        if self.price_sum < 0.98:
            # Buy both YES and NO for less than $1
            profit = 1.0 - self.price_sum
            return True, profit
        return False, 0.0
    
    def calculate_edge(self, real_btc_price: float) -> Dict:
        """Calculate edge vs real BTC price."""
        # Simple gap calculation
        price_gap = (real_btc_price - self.reference_price) / self.reference_price
        
        # Determine which side to trade
        if price_gap > 0.005:  # Real BTC 0.5% higher than Kalshi reference
            # Real BTC > Kalshi price → Buy YES
            edge = price_gap
            recommendation = "BUY_YES"
        elif price_gap < -0.005:  # Real BTC 0.5% lower
            # Real BTC < Kalshi price → Buy NO
            edge = abs(price_gap)
            recommendation = "BUY_NO"
        else:
            edge = 0
            recommendation = "HOLD"
        
        return {
            "real_btc": real_btc_price,
            "kalshi_ref": self.reference_price,
            "gap": price_gap,
            "edge": edge,
            "recommendation": recommendation,
            "yes_price": self.yes_price,
            "no_price": self.no_price
        }


def fetch_kalshi_btc_markets() -> list:
    """Fetch all BTC markets from Kalshi."""
    # Look for BTC or crypto series
    series_list = ["KXBTC", "KXBTCD", "KXXRP", "KXETH"]
    markets = []
    
    for series in series_list:
        try:
            path = f"/trade-api/v2/markets?series_ticker={series}&status=open&limit=50"
            headers = get_auth_headers("GET", path)
            
            resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("markets", []):
                    # Parse reference price from title if available
                    title = m.get("title", "")
                    yes_price = m.get("yes_ask", 0) / 100
                    no_price = m.get("no_ask", 0) / 100
                    
                    # Extract strike price from title (e.g., "BTC above $50,000")
                    import re
                    price_match = re.search(r'\$([\d,]+)', title)
                    ref_price = float(price_match.group(1).replace(',', '')) if price_match else 50000
                    
                    markets.append(KalshiBTCMarket(
                        ticker=m.get("ticker"),
                        title=title,
                        yes_price=yes_price,
                        no_price=no_price,
                        reference_price=ref_price,
                        close_date=m.get("close_date", "")
                    ))
        except Exception as e:
            print(f"⚠️  Error fetching {series}: {e}")
    
    return markets


def check_all_arbitrage_opportunities(dry_run: bool = True):
    """Main arbitrage checker."""
    print("=" * 70)
    print("₿ BTC ARBITRAGE SCANNER")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Get real BTC price
    real_btc = BTCPriceFeed.get_price()
    if not real_btc:
        print("❌ Could not fetch BTC price")
        return
    
    print(f"📊 Real BTC Price: ${real_btc:,.2f}")
    print()
    
    # Get Kalshi markets
    markets = fetch_kalshi_btc_markets()
    
    if not markets:
        print("❌ No BTC markets found on Kalshi")
        return
    
    print(f"Found {len(markets)} BTC markets")
    print()
    
    opportunities = []
    
    for market in markets:
        print(f"📈 {market.ticker}")
        print(f"   {market.title[:60]}")
        print(f"   YES: {market.yes_price:.0%} | NO: {market.no_price:.0%}")
        print(f"   Reference: ${market.reference_price:,.0f}")
        print(f"   Sum: ${market.price_sum:.2f} {'⚠️ ARBITRAGE!' if market.price_sum < 0.99 else '✓'}")
        
        # Check internal arbitrage
        has_arb, profit = market.has_internal_arbitrage
        if has_arb:
            print(f"   🚨 INTERNAL ARBITRAGE: Buy YES+NO for ${market.price_sum:.2f}, get $1.00")
            print(f"      Risk-free profit: {profit:.1%}")
            opportunities.append({
                "type": "internal",
                "market": market,
                "profit": profit
            })
        
        # Check external arbitrage (price gap)
        edge_data = market.calculate_edge(real_btc)
        if edge_data["edge"] > 0.005:  # 0.5% edge threshold
            print(f"   🚀 EXTERNAL ARBITRAGE: {edge_data['recommendation']}")
            print(f"      Real BTC: ${real_btc:,.0f} vs Kalshi ref: ${market.reference_price:,.0f}")
            print(f"      Edge: {edge_data['edge']:.1%}")
            opportunities.append({
                "type": "external",
                "market": market,
                "edge": edge_data
            })
        
        print()
    
    # Summary
    print("=" * 70)
    print("📋 OPPORTUNITY SUMMARY")
    print("=" * 70)
    
    if opportunities:
        print(f"Found {len(opportunities)} opportunities:")
        for opp in opportunities:
            if opp["type"] == "internal":
                print(f"  🚨 Internal: {opp['market'].ticker} - {opp['profit']:.1%} risk-free")
            else:
                print(f"  🚀 External: {opp['market'].ticker} - {opp['edge']['recommendation']}")
    else:
        print("No arbitrage opportunities found (markets efficient)")
    
    print("=" * 70)


if __name__ == "__main__":
    check_all_arbitrage_opportunities(dry_run=True)
