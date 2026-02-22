pub mod cities;
pub mod position_sizing;
pub mod models;
pub mod noaa;
pub mod kalshi;
pub mod bot;

// Re-export main types
pub use kalshi::KalshiClient;
pub use noaa::NoaaClient;
pub use bot::TradingBot;

use thiserror::Error;

#[derive(Error, Debug)]
pub enum TradingError {
    #[error("API error: {0}")]
    ApiError(String),
    #[error("Auth error: {0}")]
    AuthError(String),
    #[error("Position error: {0}")]
    PositionError(String),
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
    #[error("Serialization error: {0}")]
    SerializationError(#[from] serde_json::Error),
    #[error("Request error: {0}")]
    RequestError(#[from] reqwest::Error),
}

pub type Result<T> = std::result::Result<T, TradingError>;
