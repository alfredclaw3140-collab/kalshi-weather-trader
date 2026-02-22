//! Data models for snow trading
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SnowForecast {
    pub city: String,
    pub date: String,
    pub min_accumulation: f64,  // inches
    pub max_accumulation: f64,  // inches
    pub probability: f64,       // 0-1
    pub confidence: SnowConfidence,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum SnowConfidence {
    Low,      // ±5 inches
    Medium,   // ±3 inches  
    High,     // ±1 inch
}

impl SnowConfidence {
    pub fn range(&self) -> f64 {
        match self {
            SnowConfidence::Low => 5.0,
            SnowConfidence::Medium => 3.0,
            SnowConfidence::High => 1.0,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SnowMarket {
    pub ticker: String,
    pub city: String,
    pub threshold: f64,  // e.g., "Will Chicago get 6+ inches?" → 6.0
    pub yes_price: f64,
    pub no_price: f64,
    pub resolution_date: DateTime<Utc>,
    pub market_type: SnowMarketType,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum SnowMarketType {
    DailyTotal,      // Total snow in 24h
    StormTotal,      // Total from a storm system
    MonthlyTotal,    // Monthly accumulation
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SnowOpportunity {
    pub market: SnowMarket,
    pub forecast: SnowForecast,
    pub edge: f64,
    pub recommended_side: SnowSide,
    pub confidence_score: f64,  // 0-1
    pub expected_value: f64,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum SnowSide {
    Yes,
    No,
}

impl std::fmt::Display for SnowSide {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SnowSide::Yes => write!(f, "YES"),
            SnowSide::No => write!(f, "NO"),
        }
    }
}

impl SnowForecast {
    /// Calculate probability of exceeding a threshold
    pub fn prob_exceeds(&self, threshold: f64) -> f64 {
        let mid = (self.min_accumulation + self.max_accumulation) / 2.0;
        let range = self.max_accumulation - self.min_accumulation;
        
        if range == 0.0 {
            return if mid >= threshold { 1.0 } else { 0.0 };
        }
        
        // Simple model: assume uniform distribution within range
        // P(X > threshold) based on where threshold falls in range
        if threshold <= self.min_accumulation {
            1.0
        } else if threshold >= self.max_accumulation {
            0.0
        } else {
            (self.max_accumulation - threshold) / range
        }
    }
    
    /// Expected snowfall
    pub fn expected_snow(&self) -> f64 {
        (self.min_accumulation + self.max_accumulation) / 2.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_snow_forecast_probabilities() {
        let forecast = SnowForecast {
            city: "NYC".to_string(),
            date: "2026-02-22".to_string(),
            min_accumulation: 14.0,
            max_accumulation: 20.0,
            probability: 0.99,
            confidence: SnowConfidence::Medium,
        };
        
        // P(X > 10) should be ~1.0 (threshold below min)
        assert_eq!(forecast.prob_exceeds(10.0), 1.0);
        
        // P(X > 25) should be 0.0 (threshold above max)
        assert_eq!(forecast.prob_exceeds(25.0), 0.0);
        
        // P(X > 17) should be ~0.5 (midpoint)
        let prob_17 = forecast.prob_exceeds(17.0);
        assert!(prob_17 > 0.4 && prob_17 < 0.6);
    }
}
