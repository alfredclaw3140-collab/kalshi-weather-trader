# Weather Trading Bot - Rust Edition

High-performance automated trading bot for Kalshi prediction markets.

## Features

- **18 Cities**: Weather markets for major US cities
- **BLS Economic Data**: Jobs reports, CPI, PPI tracking
- **Dynamic Position Sizing**: Kelly criterion with risk management
- **Web Dashboard**: Real-time monitoring at http://localhost:8080
- **100x Faster**: Rust implementation vs Python

## Quick Start

```bash
# Build release binary
cargo build --release

# Run the bot (dry-run mode by default)
./target/release/weather-trader

# Run with live trading (set your credentials first)
DRY_RUN=false ./target/release/weather-trader
```

## Configuration

Create `~/.config/weather-trader/config.json`:

```json
{
  "kalshi": {
    "key_id": "YOUR_KEY_ID",
    "private_key_path": "~/.config/kalshi/private_key.pem",
    "email": "your@email.com",
    "api_base": "https://api.elections.kalshi.com"
  },
  "trading": {
    "bankroll": 100.0,
    "edge_threshold": 0.15,
    "dry_run": true,
    "check_interval_minutes": 30,
    "max_positions": 6,
    "max_exposure": 0.30
  },
  "noaa": {
    "user_agent": "WeatherTrader/1.0",
    "base_url": "https://api.weather.gov"
  }
}
```

## Dashboard

Access the web dashboard at: http://localhost:8080

Shows:
- Account balance
- Open positions
- Total P&L
- Opportunities found
- Bot status

## Automated Scheduling

### macOS (LaunchAgent)
```bash
./install.sh
launchctl start com.weather-trader.bot
```

### Linux (systemd)
```bash
./install.sh
sudo systemctl start weather-trader
```

## Testing

```bash
cargo test
```

26 tests covering:
- City/regional correlation
- Position sizing logic
- BLS economic events
- Dashboard state

## Architecture

```
src/
├── main.rs          # Entry point & scheduler
├── lib.rs           # Module exports
├── bot.rs           # Trading logic
├── cities.rs        # 18 city configs
├── position_sizing.rs # Risk management
├── noaa.rs          # Weather API
├── kalshi.rs        # Trading API
├── bls.rs           # Economic data
├── dashboard.rs     # Web UI
├── config.rs        # Settings
└── models.rs        # Data types
```

## Performance

| Metric | Python | Rust | Improvement |
|--------|--------|------|-------------|
| Execution | ~100ms | ~1ms | 100x faster |
| Memory | 50-100MB | 5-10MB | 10x less |
| Startup | 2-3s | 50ms | 60x faster |
| Binary size | - | 8MB | - |

## License

MIT
