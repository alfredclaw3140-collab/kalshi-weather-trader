"""Trade monitoring and dashboard for weather trading bot."""
import json
import os
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from position_tracker import PositionTracker, Position


@dataclass
class PerformanceMetrics:
    """Performance metrics for the trading bot."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_trade_pnl: float
    largest_win: float
    largest_loss: float
    sharpe_ratio: float  # Simplified
    current_exposure: float
    open_positions: int


class TradeMonitor:
    """Monitor and report on trading performance."""
    
    def __init__(self, positions_file: str = None):
        self.tracker = PositionTracker(positions_file)
        self.log_file = Path.home() / ".config" / "kalshi" / "trade_log.json"
    
    def get_performance_metrics(self) -> PerformanceMetrics:
        """Calculate performance metrics."""
        closed = [p for p in self.tracker.positions if p.status == "closed"]
        open_pos = self.tracker.get_open_positions()
        
        total_trades = len(closed)
        if total_trades == 0:
            return PerformanceMetrics(
                total_trades=0, winning_trades=0, losing_trades=0,
                win_rate=0, total_pnl=0, avg_trade_pnl=0,
                largest_win=0, largest_loss=0, sharpe_ratio=0,
                current_exposure=0, open_positions=len(open_pos)
            )
        
        pnls = [p.pnl for p in closed if p.pnl is not None]
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p < 0]
        
        total_pnl = sum(pnls)
        win_rate = len(winning) / total_trades if total_trades > 0 else 0
        
        # Calculate current exposure
        current_exposure = sum(
            p.contracts * p.entry_price for p in open_pos
        )
        
        return PerformanceMetrics(
            total_trades=total_trades,
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_trade_pnl=total_pnl / total_trades,
            largest_win=max(winning) if winning else 0,
            largest_loss=min(losing) if losing else 0,
            sharpe_ratio=self._calculate_sharpe(closed),
            current_exposure=current_exposure,
            open_positions=len(open_pos)
        )
    
    def _calculate_sharpe(self, closed_positions: List[Position]) -> float:
        """Calculate simplified Sharpe ratio."""
        pnls = [p.pnl for p in closed_positions if p.pnl is not None]
        if len(pnls) < 2:
            return 0
        
        avg = sum(pnls) / len(pnls)
        variance = sum((p - avg) ** 2 for p in pnls) / len(pnls)
        std = variance ** 0.5
        
        return avg / std if std > 0 else 0
    
    def print_dashboard(self):
        """Print a formatted dashboard."""
        metrics = self.get_performance_metrics()
        open_pos = self.tracker.get_open_positions()
        
        print("=" * 70)
        print("📊 WEATHER TRADING BOT - DASHBOARD")
        print("=" * 70)
        print(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Performance Summary
        print("💰 PERFORMANCE SUMMARY")
        print("-" * 70)
        print(f"Total Trades:     {metrics.total_trades}")
        print(f"Winning Trades:   {metrics.winning_trades} ({metrics.win_rate:.1%})")
        print(f"Losing Trades:    {metrics.losing_trades}")
        print(f"Total P&L:        ${metrics.total_pnl:+.2f}")
        print(f"Avg Trade P&L:    ${metrics.avg_trade_pnl:+.2f}")
        print(f"Largest Win:      ${metrics.largest_win:+.2f}")
        print(f"Largest Loss:     ${metrics.largest_loss:+.2f}")
        print(f"Sharpe Ratio:     {metrics.sharpe_ratio:.2f}")
        print()
        
        # Current Positions
        print(f"📈 CURRENT POSITIONS ({metrics.open_positions} open)")
        print("-" * 70)
        print(f"Total Exposure:   ${metrics.current_exposure:.2f}")
        print()
        
        if open_pos:
            for p in open_pos:
                print(f"  {p.ticker}")
                print(f"    {p.side.upper()} {p.contracts} @ {p.entry_price:.0%} (edge: {p.entry_edge:.0%})")
                print(f"    Forecast: {p.forecast_temp_at_entry}°F | Bucket: {p.bucket_min}-{p.bucket_max}°F")
                
                # Calculate days until resolution
                res_date = date.fromisoformat(p.resolution_date)
                days_until = (res_date - date.today()).days
                print(f"    Resolves: {p.resolution_date} ({days_until} days)")
                print()
        else:
            print("  No open positions")
            print()
        
        # Recent Closed Trades
        closed = [p for p in self.tracker.positions if p.status == "closed"]
        if closed:
            print("📉 RECENT CLOSED TRADES (last 5)")
            print("-" * 70)
            for p in closed[-5:]:
                pnl_str = f"${p.pnl:+.2f}" if p.pnl else "N/A"
                print(f"  {p.ticker}: {pnl_str} ({p.exit_reason})")
            print()
        
        print("=" * 70)
    
    def log_trade(self, action: str, details: Dict):
        """Log a trade action."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        }
        
        # Load existing log
        logs = []
        if self.log_file.exists():
            with open(self.log_file) as f:
                logs = json.load(f)
        
        logs.append(log_entry)
        
        # Save log
        os.makedirs(self.log_file.parent, exist_ok=True)
        with open(self.log_file, 'w') as f:
            json.dump(logs, f, indent=2)
    
    def get_daily_summary(self, target_date: date = None) -> Dict:
        """Get summary for a specific day."""
        if target_date is None:
            target_date = date.today()
        
        target_str = target_date.isoformat()
        
        # Trades entered today
        entered_today = [
            p for p in self.tracker.positions
            if p.entry_date == target_str
        ]
        
        # Trades closed today
        closed_today = [
            p for p in self.tracker.positions
            if p.status == "closed" and hasattr(p, 'exit_date') 
            and p.exit_date == target_str
        ]
        
        pnl_today = sum(
            p.pnl for p in closed_today if p.pnl is not None
        )
        
        return {
            "date": target_str,
            "trades_entered": len(entered_today),
            "trades_closed": len(closed_today),
            "pnl": pnl_today,
            "positions_opened": [
                {"ticker": p.ticker, "side": p.side, "contracts": p.contracts}
                for p in entered_today
            ]
        }
    
    def export_report(self, filename: str = None):
        """Export full report to file."""
        if filename is None:
            filename = f"weather_trading_report_{date.today().isoformat()}.json"
        
        metrics = self.get_performance_metrics()
        open_pos = self.tracker.get_open_positions()
        closed = [p for p in self.tracker.positions if p.status == "closed"]
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "performance": {
                "total_trades": metrics.total_trades,
                "win_rate": metrics.win_rate,
                "total_pnl": metrics.total_pnl,
                "sharpe_ratio": metrics.sharpe_ratio,
            },
            "open_positions": [
                {
                    "ticker": p.ticker,
                    "side": p.side,
                    "contracts": p.contracts,
                    "entry_price": p.entry_price,
                    "entry_edge": p.entry_edge,
                    "forecast_temp": p.forecast_temp_at_entry,
                    "resolution_date": p.resolution_date
                }
                for p in open_pos
            ],
            "closed_trades": [
                {
                    "ticker": p.ticker,
                    "side": p.side,
                    "pnl": p.pnl,
                    "exit_reason": p.exit_reason
                }
                for p in closed
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 Report exported to: {filename}")


def main():
    """Main entry point for monitoring."""
    monitor = TradeMonitor()
    monitor.print_dashboard()


if __name__ == "__main__":
    main()
