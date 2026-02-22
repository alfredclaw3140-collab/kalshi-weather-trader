//! Unified weather models for all market types
use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc, NaiveDate};

/// Types of weather markets we can trade
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum WeatherMarketType {
    TemperatureHigh,
    TemperatureLow,
    RainDaily,
    RainMonthly,
    SnowDaily,
    SnowMonthly,
    SnowTotal,
    TornadoCount,
    TropicalStormCount,
    HurricaneCount,
    GeomagneticStorm,
    HeatWarning,
    ColdWarning,
    WindSpeed,
    Humidity,
    LakeTemperature,
    GlobalTemperature,
    WhiteChristmas,
    SpecialEvent,
}

impl WeatherMarketType {
    pub fn edge_threshold(&self) -> f64 {
        match self {
            // Standard thresholds
            WeatherMarketType::TemperatureHigh | WeatherMarketType::TemperatureLow => 0.15,
            WeatherMarketType::RainDaily | WeatherMarketType::RainMonthly => 0.20,
            WeatherMarketType::SnowDaily | WeatherMarketType::SnowMonthly | WeatherMarketType::SnowTotal => 0.25,
            
            // High uncertainty = higher threshold
            WeatherMarketType::TornadoCount | WeatherMarketType::TropicalStormCount | 
            WeatherMarketType::HurricaneCount => 0.30,
            
            WeatherMarketType::GeomagneticStorm => 0.35, // Very hard to predict
            WeatherMarketType::HeatWarning | WeatherMarketType::ColdWarning => 0.20,
            WeatherMarketType::WindSpeed | WeatherMarketType::Humidity => 0.25,
            
            // Specialty
            WeatherMarketType::LakeTemperature => 0.15,
            WeatherMarketType::GlobalTemperature => 0.10, // Very predictable
            WeatherMarketType::WhiteChristmas => 0.30, // Seasonal, emotional betting
            WeatherMarketType::SpecialEvent => 0.25,
        }
    }
    
    pub fn position_size_pct(&self) -> f64 {
        match self {
            // Conservative for high uncertainty
            WeatherMarketType::TornadoCount | WeatherMarketType::TropicalStormCount |
            WeatherMarketType::HurricaneCount | WeatherMarketType::GeomagneticStorm => 0.05,
            
            // Standard
            WeatherMarketType::TemperatureHigh | WeatherMarketType::TemperatureLow |
            WeatherMarketType::LakeTemperature | WeatherMarketType::GlobalTemperature => 0.05,
            
            // Aggressive for less efficient markets
            WeatherMarketType::SnowDaily | WeatherMarketType::SnowMonthly | WeatherMarketType::SnowTotal => 0.08,
            WeatherMarketType::RainDaily | WeatherMarketType::RainMonthly => 0.06,
            WeatherMarketType::WhiteChristmas | WeatherMarketType::SpecialEvent => 0.06,
            
            _ => 0.05,
        }
    }
}

/// Generic weather forecast
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WeatherForecast {
    pub location: String,
    pub market_type: WeatherMarketType,
    pub forecast_date: DateTime<Utc>,
    pub value: f64,           // Temperature, rainfall amount, etc.
    pub min_value: f64,       // For ranges
    pub max_value: f64,
    pub probability: f64,     // 0.0 to 1.0
    pub confidence: ForecastConfidence,
    pub source: String,       // NOAA, NHC, etc.
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ForecastConfidence {
    VeryLow = 1,
    Low = 2,
    Medium = 3,
    High = 4,
    VeryHigh = 5,
}

/// Generic weather market from Kalshi
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WeatherMarket {
    pub ticker: String,
    pub series_ticker: String,
    pub title: String,
    pub market_type: WeatherMarketType,
    pub location: String,
    pub threshold: f64,
    pub yes_price: f64,       // 0.0 to 1.0
    pub no_price: f64,
    pub expiration_date: DateTime<Utc>,
    pub resolution_date: Option<NaiveDate>,
}

/// Trading opportunity
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WeatherOpportunity {
    pub market: WeatherMarket,
    pub forecast: WeatherForecast,
    pub edge: f64,
    pub recommended_side: WeatherSide,
    pub confidence_score: f64,
    pub expected_value: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum WeatherSide {
    Yes,
    No,
}

impl std::fmt::Display for WeatherSide {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            WeatherSide::Yes => write!(f, "YES"),
            WeatherSide::No => write!(f, "NO"),
        }
    }
}

/// Calculate probability of exceeding threshold given forecast range
pub fn prob_exceeds(min: f64, max: f64, threshold: f64) -> f64 {
    if threshold <= min {
        1.0
    } else if threshold >= max {
        0.0
    } else {
        (max - threshold) / (max - min)
    }
}

/// Calculate edge and expected value
pub fn calculate_weather_edge(
    forecast: &WeatherForecast,
    market: &WeatherMarket,
) -> Option<WeatherOpportunity> {
    let prob_exceeds = prob_exceeds(forecast.min_value, forecast.max_value, market.threshold);
    let market_prob = market.yes_price;
    let edge = (prob_exceeds - market_prob).abs();
    
    let recommended_side = if prob_exceeds > market_prob {
        WeatherSide::Yes
    } else {
        WeatherSide::No
    };
    
    let confidence_multiplier = forecast.confidence as u8 as f64 / 3.0; // Medium = 1.0
    let confidence_score = forecast.probability * confidence_multiplier;
    
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
    
    Some(WeatherOpportunity {
        market: market.clone(),
        forecast: forecast.clone(),
        edge,
        recommended_side,
        confidence_score,
        expected_value,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_prob_exceeds() {
        assert_eq!(prob_exceeds(10.0, 20.0, 5.0), 1.0);
        assert_eq!(prob_exceeds(10.0, 20.0, 25.0), 0.0);
        assert_eq!(prob_exceeds(10.0, 20.0, 15.0), 0.5);
        assert_eq!(prob_exceeds(0.0, 10.0, 6.0), 0.4);
    }
    
    #[test]
    fn test_market_type_thresholds() {
        assert_eq!(WeatherMarketType::TemperatureHigh.edge_threshold(), 0.15);
        assert_eq!(WeatherMarketType::SnowDaily.edge_threshold(), 0.25);
        assert_eq!(WeatherMarketType::TornadoCount.edge_threshold(), 0.30);
        assert_eq!(WeatherMarketType::GeomagneticStorm.edge_threshold(), 0.35);
    }
}
