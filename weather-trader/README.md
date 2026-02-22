# Weather Prediction Market Trader

AI-powered trading bot that uses NOAA weather forecasts to trade temperature prediction markets on Kalshi.

## How It Works

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  NOAA API   │────▶│  Forecast   │────▶│  Kalshi     │
│  (free)     │     │  Engine     │     │  Markets    │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                    │
                           ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  Calculate  │────▶│   Execute   │
                    │    Edge     │     │   Trades    │
                    └─────────────┘     └─────────────┘
```

1. **Fetch NOAA forecast** for target cities
2. **Find Kalshi markets** matching those dates/cities
3. **Calculate edge**: NOAA forecast probability vs market price
4. **Trade** when edge > threshold (default 15%)

## The Math

### Edge Calculation

```
Edge = Our_Probability - Market_Probability

Where:
- Our_Probability = 0.85 (85% confidence in NOAA 1-3 day forecast)
- Market_Probability = Kalshi YES price (e.g., 0.40 = 40%)

If Edge > 0.15: BUY
If Edge < -0.15: SELL/AVOID
```

### Kelly Criterion (Position Sizing)

```
f* = (bp - q) / b

Where:
- b = odds = (1/market_probability) - 1
- p = our probability of winning
- q = 1 - p
- f* = fraction of bankroll to bet

Capped at 25% for safety.
```

### Expected Return

```
EV = (P_win * Payout) - (P_lose * Loss)
   = (0.85 * $1/$0.40) - (0.15 * $1)
   = 2.125 - 0.15
   = 1.975 (197% return if right!)
```

## Setup

### 1. Get Kalshi API Access

1. Sign up at [kalshi.com](https://kalshi.com)
2. Complete identity verification
3. Request API keys at: https://kalshi.com/account/api
4. Set environment variables:
   ```bash
   export KALSHI_API_KEY="your_key"
   export KALSHI_API_SECRET="your_secret"
   ```

### 2. Install Dependencies

```bash
pip3 install requests
```

### 3. Test NOAA Integration

```bash
python3 noaa.py
```

### 4. Run Dry-Run Scan

```bash
python3 trader.py
```

This fetches forecasts and shows opportunities without placing trades.

## Project Structure

```
weather-trader/
├── noaa.py          # NOAA API client + forecast parsing
├── kalshi.py        # Kalshi API client
├── trader.py        # Main trading engine
└── README.md        # This file
```

## Key Concepts

### Temperature Buckets

Kalshi weather markets use "buckets" — ranges of temperatures:

| Market | Bucket | Meaning |
|--------|--------|---------|
| KXHIGHNY-26FEB23-A | 35-37°F | High temp 35° to 37° |
| KXHIGHNY-26FEB23-B | 38-40°F | High temp 38° to 40° |
| KXHIGHNY-26FEB23-C | >40°F | High temp above 40° |

Only **one bucket resolves YES** per day. Others go to $0.

### Market Mechanics

- **Price**: Probability (0.01 = 1%, 0.99 = 99%)
- **Payout**: $1 per contract if correct
- **Cost**: Price × contracts
- **Return**: (1 / price) - 1

Example:
- Buy at 40¢ → Pay $0.40 per contract
- If right → Get $1.00 back
- Return: 150%

### Risks

1. **Forecast error**: NOAA isn't perfect, especially 5-7 days out
2. **Microclimates**: Airport weather station ≠ city center
3. **Timing**: Forecast updates can move markets before you trade
4. **Liquidity**: Thin markets have wide bid-ask spreads
5. **Fees**: Kalshi charges per trade (~0.5-1%)

## Strategy Parameters

Edit in `trader.py`:

```python
trader = WeatherTrader(
    min_edge=0.15,      # Minimum 15% edge to trade
    max_kelly=0.25      # Max 25% of budget per trade
)
```

## Future Enhancements

- [ ] Multi-city arbitrage (compare forecasts across sources)
- [ ] Ensemble forecasting (NOAA + Weather.com + Dark Sky)
- [ ] Volatility adjustment (trade more when forecasts disagree)
- [ ] Machine learning (train on forecast accuracy history)
- [ ] Webhook alerts (notify when opportunities appear)

## Resources

- [NOAA API Docs](https://www.weather.gov/documentation/services-web-api)
- [Kalshi API Docs](https://docs.kalshi.com/)
- [Kalshi Weather Markets](https://kalshi.com/markets)

## Disclaimer

This is for educational purposes. Prediction markets involve real money and risk of loss. Past performance doesn't guarantee future results. NOAA forecasts aren't guaranteed accurate. Start with small positions.
