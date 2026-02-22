//! Weather trading bot
use crate::{
    KalshiClient, NoaaClient,
    models::{MarketInfo, Side, SizingInput, TradingOpportunity},
    position_sizing::{calculate_contract_quantity, calculate_position_size},
    cities::{get_all_cities, get_regional_exposure, GRID_POINTS, CITY_SERIES},
};
use crate::Result;
use chrono::{Datelike, NaiveDate, Utc};
use regex::Regex;
use tracing::{info, debug};

pub struct TradingBot {
    kalshi: KalshiClient,
    noaa: NoaaClient,
    bankroll: f64,
    edge_threshold: f64,
    dry_run: bool,
}

impl TradingBot {
    pub fn new(kalshi: KalshiClient, bankroll: f64, edge_threshold: f64, dry_run: bool) -> Self {
        Self {
            kalshi,
            noaa: NoaaClient::new(),
            bankroll,
            edge_threshold,
            dry_run,
        }
    }
    
    pub async fn scan_for_opportunities(&self) -> Result<Vec<TradingOpportunity>> {
        let mut opportunities = Vec::new();
        let cities = get_all_cities();
        
        for city in cities {
            debug!("Scanning {}...", city);
            
            let Some(series) = CITY_SERIES.get(city) else {
                continue;
            };
            
            // Scan high temp markets
            if let Ok(high_markets) = self.kalshi.get_markets_by_series(series.high).await {
                for market in high_markets {
                    if let Some(opp) = self.analyze_market(city, &market, "high").await {
                        opportunities.push(opp);
                    }
                }
            }
            
            // Scan low temp markets
            if let Ok(low_markets) = self.kalshi.get_markets_by_series(series.low).await {
                for market in low_markets {
                    if let Some(opp) = self.analyze_market(city, &market, "low").await {
                        opportunities.push(opp);
                    }
                }
            }
        }
        
        Ok(opportunities)
    }
    
    async fn analyze_market(
        &self,
        city: &str,
        market: &MarketInfo,
        temp_type: &str,
    ) -> Option<TradingOpportunity> {
        // Extract target temp and date from ticker
        let re = Regex::new(r"-(\d{2})([A-Z]{3})(\d{2})-([AB])(\d+\.?\d*)").ok()?;
        let caps = re.captures(&market.ticker)?;
        
        let day: u32 = caps[1].parse().ok()?;
        let month_str = &caps[2];
        let year: i32 = 2000 + caps[3].parse::<i32>().ok()?;
        let target_temp: f64 = caps[5].parse().ok()?;
        
        let month = match month_str {
            "JAN" => 1, "FEB" => 2, "MAR" => 3, "APR" => 4,
            "MAY" => 5, "JUN" => 6, "JUL" => 7, "AUG" => 8,
            "SEP" => 9, "OCT" => 10, "NOV" => 11, "DEC" => 12,
            _ => return None,
        };
        
        let target_date = NaiveDate::from_ymd_opt(year, month, day)?;
        let date_str = target_date.format("%Y-%m-%d").to_string();
        
        // Fetch NOAA forecast
        let grid = GRID_POINTS.get(city)?;
        
        let temps = match self.noaa.get_high_low_for_date(
            grid.office, grid.grid_x, grid.grid_y, &date_str
        ).await {
            Ok(Some(t)) => t,
            _ => return None,
        };
        
        let (forecast_high, forecast_low) = temps;
        let forecast_temp = if temp_type == "high" { forecast_high } else { forecast_low };
        
        // Calculate probability
        let forecast_prob = if temp_type == "high" {
            if forecast_temp > target_temp { 0.75 } else { 0.25 }
        } else {
            if forecast_temp < target_temp { 0.75 } else { 0.25 }
        };
        
        let market_price = market.yes_ask;
        let edge = (forecast_prob - market_price).abs();
        
        if edge < self.edge_threshold {
            return None;
        }
        
        let side = if forecast_prob > market_price { Side::Yes } else { Side::No };
        let today = Utc::now().date_naive();
        let days_to_resolution = (target_date - today).num_days();
        
        Some(TradingOpportunity {
            city: city.to_string(),
            market_ticker: market.ticker.clone(),
            side,
            edge,
            market_price,
            forecast_temp,
            market_temp: target_temp,
            days_to_resolution,
        })
    }
    
    pub async fn execute_trade(&self, opp: &TradingOpportunity, existing_positions: &[String]) -> Result<String> {
        let existing_refs: Vec<&str> = existing_positions.iter().map(|s| s.as_str()).collect();
        let similar_count = get_regional_exposure(&opp.city, &existing_refs);
        
        let sizing = SizingInput {
            edge: opp.edge,
            current_exposure: 0.15,
            open_positions_count: existing_positions.len(),
            days_to_resolution: opp.days_to_resolution,
            similar_city_positions: similar_count,
        };
        
        let kelly = calculate_position_size(&sizing);
        
        if kelly <= 0.0 {
            return Ok("Position size 0 - trade blocked by risk limits".to_string());
        }
        
        let contracts = calculate_contract_quantity(kelly, self.bankroll, opp.market_price);
        
        if contracts == 0 {
            return Ok("Contract quantity 0 - not enough capital".to_string());
        }
        
        let msg = format!(
            "Trade: {} {} @ {:.0}% ({} contracts, {:.1}% edge)",
            opp.market_ticker, opp.side, opp.market_price * 100.0, contracts, opp.edge * 100.0
        );
        
        if self.dry_run {
            info!("[DRY RUN] {}", msg);
            return Ok(format!("[DRY RUN] {}", msg));
        }
        
        self.kalshi.place_order(&opp.market_ticker, opp.side, contracts, opp.market_price).await
    }
    
    pub async fn get_account_summary(&self) -> Result<String> {
        let balance = self.kalshi.get_balance().await?;
        
        Ok(format!(
            "Account Summary:\n  Balance: ${:.2}\n  Edge Threshold: {:.0}%\n  Mode: {}",
            balance,
            self.edge_threshold * 100.0,
            if self.dry_run { "DRY RUN" } else { "LIVE" }
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_bot_creation() {
        let kalshi = KalshiClient::new();
        let _bot = TradingBot::new(kalshi, 100.0, 0.15, true);
    }
}
