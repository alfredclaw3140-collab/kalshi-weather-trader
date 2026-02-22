//! Lake Michigan surface water temperature trading
use crate::{
    KalshiClient, Result, TradingError,
    weather_models::*,
};
use regex::Regex;
use tracing::{info, debug, warn};

pub struct LakeTrader {
    kalshi: KalshiClient,
    bankroll: f64,
    dry_run: bool,
}

// Lake Michigan buoy stations for temperature readings
const LAKE_BUOYS: &[(&str, &str)] = &[
    ("45007", "Southern Lake Michigan"),
    ("45002", "Northern Lake Michigan"),
];

// Series tickers for Lake Michigan temp markets
const LAKE_SERIES: &[&str] = &["KXMICHTEMP", "MICHTEMP"];

impl LakeTrader {
    pub fn new(kalshi: KalshiClient, bankroll: f64, dry_run: bool) -> Self {
        Self { kalshi, bankroll, dry_run }
    }
    
    pub async fn scan_lake_opportunities(&self) -> Result<Vec<WeatherOpportunity>> {
        let mut opportunities = Vec::new();
        
        // Try to fetch lake temperature from available sources
        let lake_temp = match self.fetch_lake_temperature().await {
            Some(t) => t,
            None => {
                debug!("Could not fetch Lake Michigan temperature");
                return Ok(opportunities);
            }
        };
        
        // Check for open markets
        for series in LAKE_SERIES {
            let markets = self.fetch_lake_markets(series).await?;
            
            for market in markets {
                if let Some(opp) = self.calculate_lake_edge(&lake_temp, &market) {
                    let threshold = 0.15; // Standard temp threshold
                    if opp.edge >= threshold && opp.expected_value > 0.0 {
                        opportunities.push(opp);
                    }
                }
            }
        }
        
        opportunities.sort_by(|a, b| b.expected_value.partial_cmp(&a.expected_value).unwrap());
        Ok(opportunities)
    }
    
    async fn fetch_lake_temperature(&self) -> Option<LakeTemperature> {
        // Try multiple data sources
        
        // Source 1: NDBC Buoy data
        if let Some(temp) = self.fetch_ndbc_temperature().await {
            return Some(temp);
        }
        
        // Source 2: NOAA CoastWatch
        if let Some(temp) = self.fetch_coastwatch_temperature().await {
            return Some(temp);
        }
        
        // Source 3: GLERL (Great Lakes Environmental Research Laboratory)
        if let Some(temp) = self.fetch_glerl_temperature().await {
            return Some(temp);
        }
        
        None
    }
    
    async fn fetch_ndbc_temperature(&self) -> Option<LakeTemperature> {
        // NDBC buoy 45007 - Southern Lake Michigan
        let url = "https://www.ndbc.noaa.gov/data/realtime2/45007.txt";
        
        let client = reqwest::Client::new();
        let response = client.get(url)
            .header("User-Agent", "WeatherTrader/1.0")
            .send()
            .await
            .ok()?;
        
        let text = response.text().await.ok()?;
        
        // Parse NDBC format - looking for water temperature (WTMP)
        // Format: YY MM DD hh mm WDIR WSPD GST WVHT DPD APD MWD PRES ATMP WTMP DEWP VIS TIDE
        for line in text.lines().skip(2) { // Skip header
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 14 {
                if let Ok(wtemp) = parts[13].parse::<f64>() {
                    if wtemp > 0.0 && wtemp < 40.0 { // Valid temp range (Celsius)
                        return Some(LakeTemperature {
                            location: "Lake Michigan".to_string(),
                            temperature_c: wtemp,
                            temperature_f: c_to_f(wtemp),
                            source: "NDBC Buoy 45007".to_string(),
                            timestamp: chrono::Utc::now(),
                        });
                    }
                }
            }
        }
        
        None
    }
    
    async fn fetch_coastwatch_temperature(&self) -> Option<LakeTemperature> {
        // NOAA CoastWatch Great Lakes data
        // This would require API integration - placeholder for now
        None
    }
    
    async fn fetch_glerl_temperature(&self) -> Option<LakeTemperature> {
        // GLERL Great Lakes data
        // This would require scraping or API integration - placeholder for now
        None
    }
    
    async fn fetch_lake_markets(&self, series: &str) -> Result<Vec<WeatherMarket>> {
        let kalshi_markets = self.kalshi.get_markets_by_series(series).await?;
        let mut markets = Vec::new();
        
        for m in kalshi_markets {
            if let Some(threshold) = self.parse_temp_threshold(&m.title) {
                markets.push(WeatherMarket {
                    ticker: m.ticker,
                    series_ticker: series.to_string(),
                    title: m.title,
                    market_type: WeatherMarketType::LakeTemperature,
                    location: "Lake Michigan".to_string(),
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
    
    fn parse_temp_threshold(&self, title: &str) -> Option<f64> {
        // Match patterns like "50+ degrees" or "above 55°F"
        let re = Regex::new(r"(\d+(?:\.\d+)?)\+?\s*(?:°?F|degrees)").ok()?;
        re.captures(title)?.get(1)?.as_str().parse().ok()
    }
    
    fn calculate_lake_edge(&self, lake_temp: &LakeTemperature, market: &WeatherMarket) -> Option<WeatherOpportunity> {
        // Lake temps change slowly - use smaller uncertainty range
        let temp_f = lake_temp.temperature_f;
        let min_temp = temp_f - 2.0;  // Very stable
        let max_temp = temp_f + 2.0;
        
        let prob_exceeds = prob_exceeds(min_temp, max_temp, market.threshold);
        let market_prob = market.yes_price;
        let edge = (prob_exceeds - market_prob).abs();
        
        let recommended_side = if prob_exceeds > market_prob {
            WeatherSide::Yes
        } else {
            WeatherSide::No
        };
        
        // High confidence for lake temps (very stable)
        let confidence_score = 0.9;
        
        let win_prob = match recommended_side {
            WeatherSide::Yes => prob_exceeds,
            WeatherSide::No => 1.0 - prob_exceeds,
        };
        
        let potential_win = match recommended_side {
            WeatherSide::Yes => 1.0 - market.yes_price,
            WeatherSide::No => 1.0 - market.no_price,
        };
        
        let potential_loss = match recommended_side {
            WeatherSide::Yes => market.yes_price,
            WeatherSide::No => market.no_price,
        };
        
        let expected_value = win_prob * potential_win - (1.0 - win_prob) * potential_loss;
        
        let forecast = WeatherForecast {
            location: "Lake Michigan".to_string(),
            market_type: WeatherMarketType::LakeTemperature,
            forecast_date: lake_temp.timestamp,
            value: temp_f,
            min_value: min_temp,
            max_value: max_temp,
            probability: confidence_score,
            confidence: ForecastConfidence::High,
            source: lake_temp.source.clone(),
        };
        
        Some(WeatherOpportunity {
            market: market.clone(),
            forecast,
            edge,
            recommended_side,
            confidence_score,
            expected_value,
        })
    }
    
    pub async fn execute_lake_trade(&self, opp: &WeatherOpportunity) -> Result<String> {
        let position_size = 0.05 * opp.confidence_score * self.bankroll; // Standard temp sizing
        let contracts = (position_size / opp.market.yes_price) as u32;
        
        if contracts == 0 {
            return Ok("Position too small".to_string());
        }
        
        let msg = format!(
            "🌊 LAKE MICHIGAN: {} {} @ {:.0}% ({} contracts, {:.1}% edge, {:.1}°F threshold, {:.1}°F actual)",
            opp.market.ticker, opp.recommended_side, opp.market.yes_price * 100.0,
            contracts, opp.edge * 100.0, opp.market.threshold, opp.forecast.value
        );
        
        if self.dry_run {
            info!("[DRY RUN] {}", msg);
            return Ok(format!("[DRY RUN] {}", msg));
        }
        
        info!("{}", msg);
        Ok(msg)
    }
}

fn c_to_f(c: f64) -> f64 {
    c * 9.0 / 5.0 + 32.0
}

#[derive(Debug, Clone)]
struct LakeTemperature {
    location: String,
    temperature_c: f64,
    temperature_f: f64,
    source: String,
    timestamp: chrono::DateTime<chrono::Utc>,
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_parse_temp_threshold() {
        let trader = LakeTrader::new(
            crate::KalshiClient::new(), 1000.0, true
        );
        
        assert_eq!(trader.parse_temp_threshold("Will Lake Michigan be above 50°F?"), Some(50.0));
        assert_eq!(trader.parse_temp_threshold("60 degrees or higher"), Some(60.0));
        assert_eq!(trader.parse_temp_threshold("45+ degrees"), Some(45.0));
        assert_eq!(trader.parse_temp_threshold("No temperature here"), None);
    }
    
    #[test]
    fn test_c_to_f() {
        assert_eq!(c_to_f(0.0), 32.0);
        assert_eq!(c_to_f(100.0), 212.0);
        assert_eq!(c_to_f(10.0), 50.0);
    }
}
