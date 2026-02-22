//! Severe weather trading - Tornadoes, Hurricanes, Tropical Storms, Geomagnetic Storms
use crate::{
    KalshiClient, Result, TradingError,
    weather_models::*,
};
use tracing::{info, debug, warn};

pub struct SevereWeatherTrader {
    kalshi: KalshiClient,
    bankroll: f64,
    dry_run: bool,
}

impl SevereWeatherTrader {
    pub fn new(kalshi: KalshiClient, bankroll: f64, dry_run: bool) -> Self {
        Self { kalshi, bankroll, dry_run }
    }
    
    pub async fn scan_severe_opportunities(&self) -> Result<Vec<WeatherOpportunity>> {
        let mut opportunities = Vec::new();
        
        // Tornado count
        opportunities.extend(self.check_tornado_markets().await?);
        
        // Tropical storms  
        opportunities.extend(self.check_tropical_storm_markets().await?);
        
        // Geomagnetic storms
        opportunities.extend(self.check_geomagnetic_storms().await?);
        
        opportunities.sort_by(|a, b| b.expected_value.partial_cmp(&a.expected_value).unwrap());
        Ok(opportunities)
    }
    
    async fn check_tornado_markets(&self) -> Result<Vec<WeatherOpportunity>> {
        let mut opportunities = Vec::new();
        let series = ["KXTONADO", "TORNADO"];
        
        for s in &series {
            let markets = self.kalshi.get_markets_by_series(s).await?;
            
            for m in markets {
                if let Some(threshold) = self.parse_count_threshold(&m.title) {
                    let forecast = self.fetch_storm_forecast().await;
                    
                    if let Some(f) = forecast {
                        let market = WeatherMarket {
                            ticker: m.ticker,
                            series_ticker: s.to_string(),
                            title: m.title.clone(),
                            market_type: WeatherMarketType::TornadoCount,
                            location: "US".to_string(),
                            threshold: threshold as f64,
                            yes_price: m.yes_ask,
                            no_price: 1.0 - m.yes_ask,
                            expiration_date: m.expiration_date,
                            resolution_date: None,
                        };
                        
                        if let Some(opp) = calculate_weather_edge(&f, &market) {
                            if opp.edge >= 0.30 && opp.expected_value > 0.0 {
                                opportunities.push(opp);
                            }
                        }
                    }
                }
            }
        }
        
        Ok(opportunities)
    }
    
    async fn check_tropical_storm_markets(&self) -> Result<Vec<WeatherOpportunity>> {
        let mut opportunities = Vec::new();
        let series = ["KXTROPSTORM", "TROPSTORM"];
        
        for s in &series {
            let markets = self.kalshi.get_markets_by_series(s).await?;
            
            for m in markets {
                if let Some(threshold) = self.parse_count_threshold(&m.title) {
                    let forecast = self.fetch_storm_forecast().await;
                    
                    if let Some(f) = forecast {
                        let market = WeatherMarket {
                            ticker: m.ticker,
                            series_ticker: s.to_string(),
                            title: m.title.clone(),
                            market_type: WeatherMarketType::TropicalStormCount,
                            location: "Atlantic".to_string(),
                            threshold: threshold as f64,
                            yes_price: m.yes_ask,
                            no_price: 1.0 - m.yes_ask,
                            expiration_date: m.expiration_date,
                            resolution_date: None,
                        };
                        
                        if let Some(opp) = calculate_weather_edge(&f, &market) {
                            if opp.edge >= 0.30 && opp.expected_value > 0.0 {
                                opportunities.push(opp);
                            }
                        }
                    }
                }
            }
        }
        
        Ok(opportunities)
    }
    
    async fn check_geomagnetic_storms(&self) -> Result<Vec<WeatherOpportunity>> {
        let mut opportunities = Vec::new();
        let series = ["GSTORM", "KXGSTORM"];
        
        for s in &series {
            let markets = self.kalshi.get_markets_by_series(s).await?;
            
            for m in markets {
                if let Some(threshold) = self.parse_count_threshold(&m.title) {
                    let forecast = self.fetch_geomagnetic_forecast().await;
                    
                    if let Some(f) = forecast {
                        let market = WeatherMarket {
                            ticker: m.ticker,
                            series_ticker: s.to_string(),
                            title: m.title.clone(),
                            market_type: WeatherMarketType::GeomagneticStorm,
                            location: "Earth".to_string(),
                            threshold: threshold as f64,
                            yes_price: m.yes_ask,
                            no_price: 1.0 - m.yes_ask,
                            expiration_date: m.expiration_date,
                            resolution_date: None,
                        };
                        
                        if let Some(opp) = calculate_weather_edge(&f, &market) {
                            if opp.edge >= 0.35 && opp.expected_value > 0.0 {
                                opportunities.push(opp);
                            }
                        }
                    }
                }
            }
        }
        
        Ok(opportunities)
    }
    
    fn parse_count_threshold(&self, title: &str) -> Option<u32> {
        let re = regex::Regex::new(r"(\d+)\+?").ok()?;
        re.captures(title)?.get(1)?.as_str().parse().ok()
    }
    
    async fn fetch_storm_forecast(&self) -> Option<WeatherForecast> {
        Some(WeatherForecast {
            location: "US".to_string(),
            market_type: WeatherMarketType::TornadoCount,
            forecast_date: chrono::Utc::now(),
            value: 15.0,
            min_value: 10.0,
            max_value: 25.0,
            probability: 0.5,
            confidence: ForecastConfidence::Low,
            source: "NOAA".to_string(),
        })
    }
    
    async fn fetch_geomagnetic_forecast(&self) -> Option<WeatherForecast> {
        Some(WeatherForecast {
            location: "Earth".to_string(),
            market_type: WeatherMarketType::GeomagneticStorm,
            forecast_date: chrono::Utc::now(),
            value: 3.0,
            min_value: 0.0,
            max_value: 5.0,
            probability: 0.3,
            confidence: ForecastConfidence::VeryLow,
            source: "SWPC".to_string(),
        })
    }
    
    pub async fn execute_severe_trade(&self, opp: &WeatherOpportunity) -> Result<String> {
        let position_size = opp.market.market_type.position_size_pct() * opp.confidence_score * self.bankroll;
        let contracts = (position_size / opp.market.yes_price) as u32;
        
        if contracts == 0 {
            return Ok("Position too small".to_string());
        }
        
        let emoji = match opp.market.market_type {
            WeatherMarketType::TornadoCount => "🌪️",
            WeatherMarketType::TropicalStormCount | WeatherMarketType::HurricaneCount => "🌀",
            WeatherMarketType::GeomagneticStorm => "🌌",
            _ => "⚠️",
        };
        
        let msg = format!(
            "{} SEVERE: {} {} @ {:.0}% ({} contracts, {:.1}% edge)",
            emoji, opp.market.ticker, opp.recommended_side, opp.market.yes_price * 100.0,
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
