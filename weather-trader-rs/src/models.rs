use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Position {
    pub id: String,
    pub city: String,
    pub market_ticker: String,
    pub side: Side,
    pub entry_price: f64,
    pub contracts: u32,
    pub entry_time: DateTime<Utc>,
    pub resolution_date: DateTime<Utc>,
    pub forecast_temp: f64,
    pub market_temp: f64,
    pub edge: f64,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum Side {
    Yes,
    No,
}

impl std::fmt::Display for Side {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Side::Yes => write!(f, "YES"),
            Side::No => write!(f, "NO"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MarketInfo {
    pub ticker: String,
    pub title: String,
    pub yes_ask: f64,
    pub yes_bid: f64,
    pub last_price: f64,
    pub expiration_date: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WeatherForecast {
    pub city: String,
    pub date: String,
    pub high_temp: f64,
    pub low_temp: f64,
    pub source: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TradingOpportunity {
    pub city: String,
    pub market_ticker: String,
    pub side: Side,
    pub edge: f64,
    pub market_price: f64,
    pub forecast_temp: f64,
    pub market_temp: f64,
    pub days_to_resolution: i64,
}

#[derive(Debug, Clone)]
pub struct SizingInput {
    pub edge: f64,
    pub current_exposure: f64,
    pub open_positions_count: usize,
    pub days_to_resolution: i64,
    pub similar_city_positions: usize,
}
