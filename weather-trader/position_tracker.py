"""Position tracking and auto-exit logic for weather trading."""
import json
import os
from datetime import datetime, date
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from pathlib import Path


@dataclass
class Position:
    """Represents an active trading position."""
    ticker: str
    entry_date: str
    resolution_date: str
    side: str  # "yes" or "no"
    contracts: int
    entry_price: float
    entry_edge: float
    forecast_temp_at_entry: int
    bucket_min: int
    bucket_max: int
    city: str
    status: str = "open"  # open, closed, resolved
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None


class PositionTracker:
    """Tracks positions and manages exits based on edge decay."""
    
    def __init__(self, positions_file: str = None):
        """Initialize tracker.
        
        Args:
            positions_file: Path to JSON file for storing positions
        """
        if positions_file is None:
            positions_file = str(Path.home() / ".config" / "kalshi" / "positions.json")
        
        self.positions_file = positions_file
        self.positions: List[Position] = []
        self.load()
    
    def load(self):
        """Load positions from file."""
        if os.path.exists(self.positions_file):
            with open(self.positions_file) as f:
                data = json.load(f)
                self.positions = [Position(**p) for p in data.get("positions", [])]
    
    def save(self):
        """Save positions to file."""
        os.makedirs(os.path.dirname(self.positions_file), exist_ok=True)
        data = {
            "last_updated": datetime.now().isoformat(),
            "positions": [asdict(p) for p in self.positions]
        }
        with open(self.positions_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_position(self, position: Position):
        """Add a new position."""
        self.positions.append(position)
        self.save()
        print(f"📊 Position added: {position.ticker}")
        print(f"   Entry: {position.side.upper()} {position.contracts} @ {position.entry_price:.0%}")
        print(f"   Edge: {position.entry_edge:.0%}")
    
    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return [p for p in self.positions if p.status == "open"]
    
    def get_positions_for_date(self, target_date: date) -> List[Position]:
        """Get positions resolving on a specific date."""
        return [p for p in self.positions 
                if p.status == "open" and p.resolution_date == target_date.isoformat()]
    
    def close_position(self, ticker: str, exit_price: float, reason: str):
        """Close a position and record P&L."""
        for p in self.positions:
            if p.ticker == ticker and p.status == "open":
                p.status = "closed"
                p.exit_price = exit_price
                p.exit_reason = reason
                
                # Calculate P&L
                if p.side == "yes":
                    p.pnl = (exit_price - p.entry_price) * p.contracts
                else:
                    p.pnl = (p.entry_price - exit_price) * p.contracts
                
                self.save()
                print(f"✅ Position closed: {ticker}")
                print(f"   Exit: {exit_price:.0%} | P&L: ${p.pnl:.2f}")
                print(f"   Reason: {reason}")
                return p
        return None
    
    def check_exit_triggers(self, current_forecast: int, current_price: float) -> Dict:
        """Check if position should be exited.
        
        Args:
            current_forecast: Latest NOAA forecast
            current_price: Current market price
        
        Returns:
            Dict with exit recommendation
        """
        results = []
        
        for p in self.get_open_positions():
            # Calculate current edge
            in_bucket = p.bucket_min <= current_forecast <= p.bucket_max
            
            if p.side == "yes":
                if in_bucket:
                    current_edge = 0.85 - current_price  # Still think YES wins
                else:
                    current_edge = -0.85 + current_price  # Think YES loses
            else:  # side == "no"
                if not in_bucket:
                    current_edge = 0.85 - current_price  # Think NO wins
                else:
                    current_edge = -0.85 + current_price  # Think NO loses
            
            # Edge decay = how much edge we lost
            edge_decay = p.entry_edge - current_edge
            
            # Check triggers
            triggers = []
            
            # 1. Forecast changed against us
            if (p.side == "yes" and not in_bucket) or (p.side == "no" and in_bucket):
                triggers.append("FORECAST_CHANGED")
            
            # 2. Edge decay > 50% (lost half our edge)
            if p.entry_edge > 0 and edge_decay / p.entry_edge > 0.5:
                triggers.append("EDGE_DECAY_50")
            
            # 3. Edge turned negative (now wrong side)
            if current_edge < 0:
                triggers.append("EDGE_NEGATIVE")
            
            # 4. Profitable exit (took profits)
            if p.side == "yes" and current_price > 0.80:
                profit_pct = (current_price - p.entry_price) / p.entry_price
                if profit_pct > 1.0:  # >100% profit
                    triggers.append("TAKE_PROFITS")
            
            # 5. Loss limit hit (-30%)
            if p.side == "yes":
                loss_pct = (p.entry_price - current_price) / p.entry_price
            else:
                loss_pct = (current_price - p.entry_price) / (1 - p.entry_price)
            
            if loss_pct > 0.30:
                triggers.append("STOP_LOSS")
            
            results.append({
                "position": p,
                "current_forecast": current_forecast,
                "in_bucket": in_bucket,
                "current_price": current_price,
                "current_edge": current_edge,
                "edge_decay": edge_decay,
                "triggers": triggers,
                "should_exit": len(triggers) > 0
            })
        
        return results
    
    def print_summary(self):
        """Print position summary."""
        open_pos = self.get_open_positions()
        closed_pos = [p for p in self.positions if p.status == "closed"]
        
        print("=" * 70)
        print("📊 POSITION SUMMARY")
        print("=" * 70)
        
        print(f"\n🟢 Open Positions: {len(open_pos)}")
        total_exposure = sum(p.contracts * p.entry_price for p in open_pos)
        print(f"   Total Exposure: ${total_exposure:.2f}")
        
        for p in open_pos:
            print(f"\n   {p.ticker}")
            print(f"   {p.side.upper()} {p.contracts} @ {p.entry_price:.0%} (edge: {p.entry_edge:.0%})")
            print(f"   Forecast: {p.forecast_temp_at_entry}°F | Bucket: {p.bucket_min}-{p.bucket_max}°F")
        
        if closed_pos:
            print(f"\n🔴 Closed Positions: {len(closed_pos)}")
            total_pnl = sum(p.pnl for p in closed_pos if p.pnl)
            print(f"   Total P&L: ${total_pnl:.2f}")
            
            for p in closed_pos[-3:]:  # Show last 3
                print(f"\n   {p.ticker}: {p.exit_reason}")
                print(f"   P&L: ${p.pnl:.2f} | Exit: {p.exit_price:.0%}")
        
        print("=" * 70)


def monitor_positions(city: str = "NYC"):
    """Monitor open positions and suggest exits."""
    from noaa import fetch_forecast, get_high_temp_for_date
    import requests
    from kalshi_auth import get_auth_headers
    
    API_BASE = "https://api.elections.kalshi.com"
    tracker = PositionTracker()
    
    print("🔍 Monitoring positions...")
    tracker.print_summary()
    
    open_pos = tracker.get_open_positions()
    if not open_pos:
        print("\n✅ No open positions to monitor")
        return
    
    # Get fresh forecast
    print(f"\n📡 Fetching fresh NOAA forecast for {city}...")
    forecasts = fetch_forecast(city)
    
    # Check each position
    for p in open_pos:
        # Parse resolution date
        res_date = date.fromisoformat(p.resolution_date)
        current_forecast = get_high_temp_for_date(forecasts, res_date)
        
        if current_forecast is None:
            print(f"⚠️  No forecast for {p.ticker}")
            continue
        
        # Get current market price
        path = f"/trade-api/v2/markets/{p.ticker}"
        headers = get_auth_headers("GET", path)
        
        try:
            resp = requests.get(f"{API_BASE}{path}", headers=headers, timeout=30)
            if resp.status_code == 200:
                market = resp.json().get("market", {})
                current_price = market.get("yes_ask", 0) / 100 if p.side == "yes" else market.get("no_ask", 0) / 100
                
                # Check triggers
                results = tracker.check_exit_triggers(current_forecast, current_price)
                
                for r in results:
                    if r["should_exit"]:
                        print(f"\n⚠️  EXIT ALERT: {p.ticker}")
                        print(f"   Triggers: {', '.join(r['triggers'])}")
                        print(f"   Entry edge: {p.entry_edge:.0%} | Current edge: {r['current_edge']:.0%}")
                        print(f"   Entry price: {p.entry_price:.0%} | Current price: {current_price:.0%}")
                        print(f"   Recommendation: SELL")
                    else:
                        print(f"\n✅ HOLD: {p.ticker}")
                        print(f"   Edge: {r['current_edge']:.0%} (decay: {r['edge_decay']:.0%})")
                        print(f"   Current forecast: {current_forecast}°F {'IN' if r['in_bucket'] else 'OUTSIDE'} bucket")
        except Exception as e:
            print(f"❌ Error checking {p.ticker}: {e}")


if __name__ == "__main__":
    # Demo: show summary
    tracker = PositionTracker()
    tracker.print_summary()
