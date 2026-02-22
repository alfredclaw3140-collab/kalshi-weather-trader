//! Rain trading bot - Seattle, NYC, Dallas, Houston, etc.
use crate::{
    KalshiClient, Result, TradingError,
    weather_models::*,
    cities::GRID_POINTS,
};
use regex::Regex;
use tracing::{info, debug, warn};
use serde::Deserialize;

pub struct RainTrader {
    kalshi: KalshiClient,
    bankroll: f64,
    dry_run: bool,
}

const RAIN_CITIES: &[(&str, &str)] = &[
    ("NYC", "RAINNYC"),
    ("Seattle", "KXRAINSEAM"),
    ("Dallas", "KXRAINDALM"),
    ("Houston", "KXRAINHOU"),
    ("Miami", "KXRAINMIAM"),
    ("Austin", "KXRAINAUSM"),
    ("NewOrleans", "KXRAINNO"),
    ("Chicago", "KXRAINCHIM"),
    ("LA", "KXRAINLAXM"),
    ("SanFrancisco", "KXRAINSFOM"),
];

impl RainTrader {
    pub fn new(kalshi: KalshiClient, bankroll: f64, dry_run: bool) -> Self {
        Self { kalshi, bankroll, dry_run }
    }
    
    pub async fn scan_rain_opportunities(&self) -> Result<Vec<WeatherOpportunity>> {
        let mut opportunities = Vec::new();
        
        for (city, series) in RAIN_CITIES {
            debug!("Scanning rain markets for {} ({})", city, series);
            
            let markets = self.fetch_rain_markets(series, city).await?;
            
            for market in markets {
                if let Some(forecast) = self.fetch_rain_forecast(city, &market).await {
                    if let Some(opp) = calculate_weather_edge(&forecast, &market) {
                        let threshold = market.market_type.edge_threshold();
                        if opp.edge >= threshold && opp.expected_value > 0.0 {
                            opportunities.push(opp);
                        }
                    }
                }
            }
        }
        
        opportunities.sort_by(|a, b| b.expected_value.partial_cmp(&a.expected_value).unwrap());
        Ok(opportunities)
    }
    
    async fn fetch_rain_markets(&self, series: &str, city: &str) -> Result<Vec<WeatherMarket>> {
        let kalshi_markets = self.kalshi.get_markets_by_series(series).await?;
        let mut markets = Vec::new();
        
        for m in kalshi_markets {
            if let Some(threshold) = self.parse_rain_threshold(&m.title) {
                let market_type = if m.title.to_lowercase().contains("month") {
                    WeatherMarketType::RainMonthly
                } else {
                    WeatherMarketType::RainDaily
                };
                
                markets.push(WeatherMarket {
                    ticker: m.ticker,
                    series_ticker: series.to_string(),
                    title: m.title,
                    market_type,
                    location: city.to_string(),
                    threshold,
                    yes_price: m.yes_ask,
                    no_price: 1.0 - m.yes_ask,
                    expiration_date: m.expiration_date,
                    resolution_date: None,
                });
            }
        }
        
        Ok(markets)
    }
    
    fn parse_rain_threshold(&self, title: &str) -> Option<f64> {
        // Match patterns like "7 days of rain" or "5+ days"
        let re = Regex::new(r"(\d+(?:\.\d+)?)\+?\s*(?:day|inch)").ok()?;
        re.captures(title)?.get(1)?.as_str().parse().ok()
    }
    
    async fn fetch_rain_forecast(&self, city: &str, market: &WeatherMarket) -> Option<WeatherForecast> {
        let grid = GRID_POINTS.get(city)?;
        
        // Fetch from NOAA
        let url = format!(
            "https://api.weather.gov/gridpoints/{}/{},{}/forecast",
            grid.office, grid.grid_x, grid.grid_y
        );
        
        let client = reqwest::Client::new();
        let response = client.get(&url).header("User-Agent", "WeatherTrader/1.0").send().await.ok()?;
        
        #[derive(Deserialize)]
        struct ForecastResponse {
            properties: ForecastProperties,
        }
        
        #[derive(Deserialize)]
        struct ForecastProperties {
            periods: Vec<ForecastPeriod>,
        }
        
        #[derive(Deserialize)]
        struct ForecastPeriod {
            #[serde(rename = "probabilityOfPrecipitation")]
            pop: Option<ValueUnit>,
            name: String,
        }
        
        #[derive(Deserialize)]
        struct ValueUnit {
            value: Option<f64>,
        }
        
        let data: ForecastResponse = response.json().await.ok()?;
        
        // Count rainy days
        let mut rainy_days = 0.0;
        let mut total_pop = 0.0;
        let count = data.properties.periods.len().min(14) as f64;
        
        for period in data.properties.periods.iter().take(14) {
            let pop = period.pop.as_ref().and_then(|p| p.value).unwrap_or(0.0) / 100.0;
            total_pop += pop;
            if pop > 0.5 {
                rainy_days += 0.5; // Each period is ~12 hours
            }
        }
        
        let avg_pop = total_pop / count;
        
        Some(WeatherForecast {
            location: city.to_string(),
            market_type: market.market_type,
            forecast_date: chrono::Utc::now(),
            value: rainy_days,
            min_value: rainy_days * 0.7,
            max_value: rainy_days * 1.3,
            probability: avg_pop,
            confidence: if avg_pop > 0.7 { ForecastConfidence::High } 
                       else if avg_pop > 0.4 { ForecastConfidence::Medium }
                       else { ForecastConfidence::Low },
            source: "NOAA".to_string(),
        })
    }
    
    pub async fn execute_rain_trade(&self, opp: &WeatherOpportunity) -> Result<String> {
        let position_size = opp.market.market_type.position_size_pct() * opp.confidence_score * self.bankroll;
        let contracts = (position_size / opp.market.yes_price) as u32;
        
        if contracts == 0 {
            return Ok("Position too small".to_string());
        }
        
        let msg = format!(
            "🌧️ RAIN TRADE: {} {} @ {:.0}% ({} contracts, {:.1}% edge)",
            opp.market.ticker, opp.recommended_side, opp.market.yes_price * 100.0,
            contracts, opp.edge * 100.0
        );
        
        if self.dry_run {
            info!("[DRY RUN] {}", msg);
            return Ok(format!("[DRY RUN] {}", msg));
        }
        
        info!("{}", msg);
        Ok(msg)
    }
}
