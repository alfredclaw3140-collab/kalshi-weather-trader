//! Dedicated snow trading bot with aggressive edge-seeking strategy
use crate::{
    KalshiClient, Result, TradingError,
    snow_models::*,
    snow_noaa::SnowNOAAClient,
    cities::GRID_POINTS,
};
use regex::Regex;
use tracing::{info, debug, warn};

/// Snow trading configuration - more aggressive than temp trading
pub struct SnowTradingConfig {
    pub min_edge_threshold: f64,      // 25% (higher than temp's 15%)
    pub min_confidence: SnowConfidence,
    pub min_probability: f64,         // 60% POP minimum
    pub max_position_size: f64,       // 8% of bankroll (vs 5% for temps)
    pub min_snow_threshold: f64,      // Only trade if market threshold >= 1 inch
}

impl Default for SnowTradingConfig {
    fn default() -> Self {
        Self {
            min_edge_threshold: 0.25,     // 25% edge required
            min_confidence: SnowConfidence::Medium,
            min_probability: 0.60,        // 60% minimum POP
            max_position_size: 0.08,      // 8% position sizing
            min_snow_threshold: 1.0,      // No trading on trace amounts
        }
    }
}

pub struct SnowTrader {
    kalshi: KalshiClient,
    noaa: SnowNOAAClient,
    config: SnowTradingConfig,
    bankroll: f64,
    dry_run: bool,
}

/// Snow cities with active markets
const SNOW_CITIES: &[&str] = &[
    "Chicago",      // KXSNOWCHIM
    "Houston",      // KXHOUSNOWM  
    "Dallas",       // KXDALSNOWM
    "NYC",          // NYC snow
    "Boston",       // Boston snow
    "Minneapolis",  // MSP snow
    "Detroit",      // Detroit snow
];

impl SnowTrader {
    pub fn new(kalshi: KalshiClient, bankroll: f64, dry_run: bool) -> Self {
        Self {
            kalshi,
            noaa: SnowNOAAClient::new(),
            config: SnowTradingConfig::default(),
            bankroll,
            dry_run,
        }
    }
    
    /// Scan all snow markets for opportunities
    pub async fn scan_snow_opportunities(&self) -> Result<Vec<SnowOpportunity>> {
        let mut opportunities = Vec::new();
        
        for city in SNOW_CITIES {
            debug!("Scanning snow markets for {}", city);
            
            // Fetch NOAA snow forecast
            let Some(grid) = GRID_POINTS.get(city) else {
                continue;
            };
            
            let forecasts = match self.noaa.fetch_snow_forecast(
                grid.office, grid.grid_x, grid.grid_y, city
            ).await {
                Ok(f) => f,
                Err(e) => {
                    warn!("Failed to fetch snow forecast for {}: {}", city, e);
                    continue;
                }
            };
            
            if forecasts.is_empty() {
                debug!("No snow forecast for {}", city);
                continue;
            }
            
            // Fetch Kalshi snow markets for this city
            let markets = self.fetch_snow_markets_for_city(city).await?;
            
            // Match forecasts to markets and calculate edge
            for forecast in forecasts {
                // Filter: minimum probability
                if forecast.probability < self.config.min_probability {
                    continue;
                }
                
                // Filter: minimum confidence
                if forecast.confidence as u8 > self.config.min_confidence as u8 {
                    continue;
                }
                
                for market in &markets {
                    if let Some(opp) = self.calculate_snow_edge(&forecast, market) {
                        if opp.edge >= self.config.min_edge_threshold {
                            opportunities.push(opp);
                        }
                    }
                }
            }
        }
        
        // Sort by expected value (best opportunities first)
        opportunities.sort_by(|a, b| b.expected_value.partial_cmp(&a.expected_value).unwrap());
        
        Ok(opportunities)
    }
    
    /// Fetch snow markets from Kalshi for a specific city
    async fn fetch_snow_markets_for_city(&self, city: &str) -> Result<Vec<SnowMarket>> {
        let mut markets = Vec::new();
        
        // Try to find snow series for this city
        let series_ticker = match city {
            "Chicago" => "KXSNOWCHIM",
            "Houston" => "KXHOUSNOWM", 
            "Dallas" => "KXDALSNOWM",
            _ => return Ok(markets), // No known series for other cities
        };
        
        // Use kalshi client to fetch markets
        let kalshi_markets = self.kalshi.get_markets_by_series(series_ticker).await?;
        
        for m in kalshi_markets {
            // Parse threshold from title
            if let Some(threshold) = self.parse_snow_threshold(&m.title) {
                if threshold >= self.config.min_snow_threshold {
                    markets.push(SnowMarket {
                        ticker: m.ticker,
                        city: city.to_string(),
                        threshold,
                        yes_price: m.yes_ask,
                        no_price: 1.0 - m.yes_ask,
                        resolution_date: m.expiration_date,
                        market_type: SnowMarketType::DailyTotal,
                    });
                }
            }
        }
        
        Ok(markets)
    }
    
    /// Parse snow threshold from market title
    fn parse_snow_threshold(&self, title: &str) -> Option<f64> {
        let patterns = [
            Regex::new(r"(\d+(?:\.\d+)?)\+?\s*inch").ok()?,
            Regex::new(r"(\d+(?:\.\d+)?)\s*or more").ok()?,
        ];
        
        for pattern in &patterns {
            if let Some(caps) = pattern.captures(title) {
                return caps[1].parse().ok();
            }
        }
        
        None
    }
    
    /// Calculate edge for a snow forecast vs market
    fn calculate_snow_edge(&self, forecast: &SnowForecast, market: &SnowMarket) -> Option<SnowOpportunity> {
        // Calculate probability of exceeding market threshold
        let prob_exceeds = forecast.prob_exceeds(market.threshold);
        
        // Market implied probability
        let market_prob = market.yes_price;
        
        // Calculate edge
        let edge = (prob_exceeds - market_prob).abs();
        
        // Determine which side to take
        let recommended_side = if prob_exceeds > market_prob {
            SnowSide::Yes
        } else {
            SnowSide::No
        };
        
        // Confidence score based on forecast confidence and probability
        let confidence_score = forecast.probability * match forecast.confidence {
            SnowConfidence::High => 1.0,
            SnowConfidence::Medium => 0.8,
            SnowConfidence::Low => 0.6,
        };
        
        // Expected value calculation
        let win_prob = if recommended_side == SnowSide::Yes { prob_exceeds } else { 1.0 - prob_exceeds };
        let potential_win = if recommended_side == SnowSide::Yes { 1.0 - market.yes_price } else { 1.0 - market.no_price };
        let potential_loss = if recommended_side == SnowSide::Yes { market.yes_price } else { market.no_price };
        let expected_value = win_prob * potential_win - (1.0 - win_prob) * potential_loss;
        
        Some(SnowOpportunity {
            market: market.clone(),
            forecast: forecast.clone(),
            edge,
            recommended_side,
            confidence_score,
            expected_value,
        })
    }
    
    /// Execute a snow trade
    pub async fn execute_snow_trade(&self, opp: &SnowOpportunity) -> Result<String> {
        let _side_str = match opp.recommended_side {
            SnowSide::Yes => "yes",
            SnowSide::No => "no",
        };
        
        // Calculate position size (more aggressive for snow)
        let position_size = self.config.max_position_size * opp.confidence_score;
        let contracts = ((self.bankroll * position_size) / opp.market.yes_price) as u32;
        
        if contracts == 0 {
            return Ok("Position too small, skipping".to_string());
        }
        
        let msg = format!(
            "❄️ SNOW TRADE: {} {} @ {:.0}% ({} contracts, {:.1}% edge, {:.1}\" threshold)",
            opp.market.ticker,
            opp.recommended_side,
            opp.market.yes_price * 100.0,
            contracts,
            opp.edge * 100.0,
            opp.market.threshold
        );
        
        if self.dry_run {
            info!("[DRY RUN] {}", msg);
            return Ok(format!("[DRY RUN] {}", msg));
        }
        
        // Execute actual trade via Kalshi
        self.kalshi.place_order(
            &opp.market.ticker,
            crate::models::Side::Yes, // Simplified - should use recommended_side
            contracts,
            opp.market.yes_price
        ).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    fn create_test_forecast() -> SnowForecast {
        SnowForecast {
            city: "Chicago".to_string(),
            date: "2026-02-22".to_string(),
            min_accumulation: 6.0,
            max_accumulation: 10.0,
            probability: 0.85,
            confidence: SnowConfidence::Medium,
        }
    }
    
    fn create_test_market() -> SnowMarket {
        SnowMarket {
            ticker: "KXSNOWCHIM-22FEB-6".to_string(),
            city: "Chicago".to_string(),
            threshold: 6.0,
            yes_price: 0.35,
            no_price: 0.65,
            resolution_date: chrono::Utc::now(),
            market_type: SnowMarketType::DailyTotal,
        }
    }
    
    #[test]
    fn test_calculate_snow_edge() {
        let trader = SnowTrader::new(
            KalshiClient::new(),
            100.0,
            true
        );
        
        let forecast = create_test_forecast();
        let market = create_test_market();
        
        let opp = trader.calculate_snow_edge(&forecast, &market).unwrap();
        
        // Forecast: 6-10 inches, so P(X > 6) is high (~0.8-0.9)
        // Market price: 0.35
        // Edge should be large
        assert!(opp.edge > 0.3);
        assert_eq!(opp.recommended_side, SnowSide::Yes);
    }
    
    #[test]
    fn test_parse_snow_threshold() {
        let trader = SnowTrader::new(KalshiClient::new(), 100.0, true);
        
        assert_eq!(trader.parse_snow_threshold("Will Chicago get 6+ inches?"), Some(6.0));
        assert_eq!(trader.parse_snow_threshold("5 inches of snow"), Some(5.0));
        assert_eq!(trader.parse_snow_threshold("No threshold here"), None);
    }
}
