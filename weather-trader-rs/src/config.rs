//! Configuration management for the trading bot
use crate::{Result, TradingError};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Config {
    pub kalshi: KalshiConfig,
    pub trading: TradingConfig,
    pub noaa: NOAAConfig,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct KalshiConfig {
    pub key_id: String,
    pub private_key_path: String,
    pub email: String,
    pub api_base: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct TradingConfig {
    pub bankroll: f64,
    pub edge_threshold: f64,
    pub dry_run: bool,
    pub check_interval_minutes: u64,
    pub max_positions: usize,
    pub max_exposure: f64,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct NOAAConfig {
    pub user_agent: String,
    pub base_url: String,
}

// Structure for the credentials.json file
#[derive(Debug, Deserialize)]
struct KalshiCredentials {
    key_id: String,
    private_key: String,
}

impl Config {
    pub fn load() -> Result<Self> {
        let config_paths = [
            "config.json",
            "/Users/alfred/.config/weather-trader/config.json",
            "/etc/weather-trader/config.json",
        ];
        
        for path in &config_paths {
            if Path::new(path).exists() {
                let contents = fs::read_to_string(path)?;
                let config: Config = serde_json::from_str(&contents)?;
                return Ok(config);
            }
        }
        
        // Return default config if no file found
        Ok(Config::default())
    }
    
    /// Load credentials from Kalshi credentials.json
    pub fn load_credentials(&self) -> Result<(String, String)> {
        let creds_path = Path::new("/Users/alfred/.config/kalshi/credentials.json");
        
        if !creds_path.exists() {
            return Err(TradingError::AuthError(
                "Credentials file not found at ~/.config/kalshi/credentials.json".to_string()
            ));
        }
        
        let contents = fs::read_to_string(creds_path)?;
        let creds: KalshiCredentials = serde_json::from_str(&contents)?;
        
        Ok((creds.key_id, creds.private_key))
    }
    
    /// Load private key from PEM file (fallback)
    pub fn load_private_key(&self) -> Result<String> {
        let path = Path::new(&self.kalshi.private_key_path);
        if !path.exists() {
            return Err(TradingError::AuthError(
                format!("Private key not found at: {}", self.kalshi.private_key_path)
            ));
        }
        Ok(fs::read_to_string(path)?)
    }
    
    pub fn save(&self, path: &str) -> Result<()> {
        let json = serde_json::to_string_pretty(self)?;
        fs::write(path, json)?;
        Ok(())
    }
}

impl Default for Config {
    fn default() -> Self {
        Self {
            kalshi: KalshiConfig {
                key_id: String::new(),
                private_key_path: "/Users/alfred/.config/kalshi/private_key.pem".to_string(),
                email: "jmuller3140@gmail.com".to_string(),
                api_base: "https://api.elections.kalshi.com".to_string(),
            },
            trading: TradingConfig {
                bankroll: 100.0,
                edge_threshold: 0.15,
                dry_run: true,
                check_interval_minutes: 30,
                max_positions: 6,
                max_exposure: 0.30,
            },
            noaa: NOAAConfig {
                user_agent: "WeatherTrader/1.0".to_string(),
                base_url: "https://api.weather.gov".to_string(),
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_default_config() {
        let config = Config::default();
        assert_eq!(config.trading.bankroll, 100.0);
        assert_eq!(config.trading.edge_threshold, 0.15);
        assert!(config.trading.dry_run);
    }
}
