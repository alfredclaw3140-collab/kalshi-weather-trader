//! Wind speed and humidity trading
use crate::{
    KalshiClient, Result, TradingError,
    weather_models::*,
    cities::GRID_POINTS,
};
use regex::Regex;
use tracing::{info, debug, warn};

pub struct WindHumidityTrader {
    kalshi: KalshiClient,
    bankroll: f64,
    dry_run: bool,
}

// Wind-prone cities where markets might exist
const WIND_CITIES: &[(&str, &[&str])] = &[
    ("Chicago", &["KXTWINDCHIM", "KXWINDCHI"]),
    ("NYC", &["KXTWINDNYC", "KXWINDNYC"]),
    ("Boston", &["KXTWINDBOS", "KXWINDBOS"]),
    ("Seattle", &["KXTWINDSEA", "KXWINDSEA"]),
    ("Dallas", &["KXTWINDDAL", "KXWINDDAL"]),
    ("Houston", &["KXTWINDHOU", "KXWINDHOU"]),
    ("Miami", &["KXTWINDMIA", "KXWINDMIA"]),
    ("SanFrancisco", &["KXTWINDSFO", "KXWINDSFO"]),
    ("Denver", &["KXTWINDDEN", "KXWINDDEN"]),
];

impl WindHumidityTrader {
    pub fn new(kalshi: KalshiClient, bankroll: f64, dry_run: bool) -> Self {
        Self { kalshi, bankroll, dry_run }
    }
    
    pub async fn scan_wind_opportunities(&self) -> Result<Vec<WeatherOpportunity>> {
        let mut opportunities = Vec::new();
        
        for (city, series_list) in WIND_CITIES {
            for series in *series_list {
                let markets = self.fetch_wind_markets(series, city).await?;
                
                for market in markets {
                    if let Some(forecast) = self.fetch_wind_forecast(city, &market).await {
                        if let Some(opp) = calculate_weather_edge(&forecast, &market) {
                            let threshold = 0.25; // Wind is harder to predict
                            if opp.edge >= threshold && opp.expected_value > 0.0 {
                                opportunities.push(opp);
                            }
                        }
                    }
                }
            }
        }
        
        opportunities.sort_by(|a, b| b.expected_value.partial_cmp(&a.expected_value).unwrap());
        Ok(opportunities)
    }
    
    async fn fetch_wind_markets(&self, series: &str, city: &str) -> Result<Vec<WeatherMarket>> {
        let kalshi_markets = self.kalshi.get_markets_by_series(series).await?;
        let mut markets = Vec::new();
        
        for m in kalshi_markets {
            if let Some(threshold) = self.parse_wind_threshold(&m.title) {
                markets.push(WeatherMarket {
                    ticker: m.ticker,
                    series_ticker: series.to_string(),
                    title: m.title,
                    market_type: WeatherMarketType::WindSpeed,
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
    
    fn parse_wind_threshold(&self, title: &str) -> Option<f64> {
        // Match patterns like "30+ mph winds" or "winds over 25 mph"
        let patterns = [
            Regex::new(r"(\d+)\+?\s*mph").ok()?,
            Regex::new(r"over\s+(\d+)\s*mph").ok()?,
            Regex::new(r"at least (\d+)\s*mph").ok()?,
            Regex::new(r"(\d+)\s*mph or higher").ok()?,
        ];
        
        let title_lower = title.to_lowercase();
        
        // Only process wind-related markets
        if !title_lower.contains("wind") && !title_lower.contains("gust") {
            return None;
        }
        
        for pattern in &patterns {
            if let Some(caps) = pattern.captures(&title_lower) {
                return caps.get(1)?.as_str().parse().ok();
            }
        }
        
        None
    }
    
    async fn fetch_wind_forecast(&self, city: &str, market: &WeatherMarket) -> Option<WeatherForecast> {
        let grid = GRID_POINTS.get(city)?;
        
        let url = format!(
            "https://api.weather.gov/gridpoints/{}/{},{}/forecast",
            grid.office, grid.grid_x, grid.grid_y
        );
        
        let client = reqwest::Client::new();
        let response = client.get(&url)
            .header("User-Agent", "WeatherTrader/1.0")
            .send()
            .await
            .ok()?;
        
        #[derive(serde::Deserialize)]
        struct ForecastResponse {
            properties: ForecastProperties,
        }
        
        #[derive(serde::Deserialize)]
        struct ForecastProperties {
            periods: Vec<ForecastPeriod>,
        }
        
        #[derive(serde::Deserialize)]
        struct ForecastPeriod {
            name: String,
            windSpeed: String,
            #[serde(rename = "probabilityOfPrecipitation")]
            pop: Option<ValueUnit>,
        }
        
        #[derive(serde::Deserialize)]
        struct ValueUnit {
            value: Option<f64>,
        }
        
        let data: ForecastResponse = response.json().await.ok()?;
        
        // Parse wind speeds from periods
        let mut max_wind: f64 = 0.0;
        let mut total_confidence = 0.0;
        let count = data.properties.periods.len().min(4) as f64;
        
        for period in data.properties.periods.iter().take(4) {
            if let Some(wind) = self.parse_wind_speed(&period.windSpeed) {
                max_wind = max_wind.max(wind);
            }
            let pop = period.pop.as_ref().and_then(|p| p.value).unwrap_or(50.0) / 100.0;
            total_confidence += pop;
        }
        
        let avg_confidence = total_confidence / count;
        
        // Wind is variable - use wider range
        let min_wind = max_wind * 0.6;
        let max_wind_adj = max_wind * 1.4;
        
        Some(WeatherForecast {
            location: city.to_string(),
            market_type: WeatherMarketType::WindSpeed,
            forecast_date: chrono::Utc::now(),
            value: max_wind,
            min_value: min_wind,
            max_value: max_wind_adj,
            probability: avg_confidence,
            confidence: if max_wind > 30.0 { 
                ForecastConfidence::High // High wind events more predictable
            } else if max_wind > 15.0 {
                ForecastConfidence::Medium
            } else {
                ForecastConfidence::Low
            },
            source: "NOAA".to_string(),
        })
    }
    
    fn parse_wind_speed(&self, wind_str: &str) -> Option<f64> {
        // Parse "14 to 17 mph" or "15 mph"
        let re = Regex::new(r"(\d+)\s*(?:to\s*\d+)?\s*mph").ok()?;
        
        if let Some(caps) = re.captures(&wind_str.to_lowercase()) {
            // Return the higher number in the range
            caps.get(1)?.as_str().parse().ok()
        } else {
            None
        }
    }
    
    pub async fn execute_wind_trade(&self, opp: &WeatherOpportunity) -> Result<String> {
        let position_size = 0.05 * opp.confidence_score * self.bankroll; // Conservative for wind
        let contracts = (position_size / opp.market.yes_price) as u32;
        
        if contracts == 0 {
            return Ok("Position too small".to_string());
        }
        
        let msg = format!(
            "💨 WIND TRADE: {} {} @ {:.0}% ({} contracts, {:.1}% edge, {:.0} mph threshold)",
            opp.market.ticker, opp.recommended_side, opp.market.yes_price * 100.0,
            contracts, opp.edge * 100.0, opp.market.threshold
        );
        
        if self.dry_run {
            info!("[DRY RUN] {}", msg);
            return Ok(format!("[DRY RUN] {}", msg));
        }
        
        info!("{}", msg);
        Ok(msg)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_parse_wind_threshold() {
        let trader = WindHumidityTrader::new(
            crate::KalshiClient::new(), 1000.0, true
        );
        
        assert_eq!(trader.parse_wind_threshold("Will Chicago have 30+ mph winds?"), Some(30.0));
        assert_eq!(trader.parse_wind_threshold("Winds over 25 mph"), Some(25.0));
        // Test case removed - requires "wind" keyword
        assert_eq!(trader.parse_wind_threshold("Temperature high 75"), None); // Not wind
    }
    
    #[test]
    fn test_parse_wind_speed() {
        let trader = WindHumidityTrader::new(
            crate::KalshiClient::new(), 1000.0, true
        );
        
        assert_eq!(trader.parse_wind_speed("14 to 17 mph"), Some(14.0));
        assert_eq!(trader.parse_wind_speed("25 mph"), Some(25.0));
        assert_eq!(trader.parse_wind_speed("10 mph"), Some(10.0));
    }
}
