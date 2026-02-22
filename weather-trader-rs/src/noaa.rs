//! NOAA Weather API client
use crate::{Result, TradingError};
use crate::models::WeatherForecast;
use chrono::NaiveDate;
use serde::Deserialize;

const NOAA_BASE: &str = "https://api.weather.gov";

#[derive(Debug, Deserialize)]
struct ForecastResponse {
    properties: ForecastProperties,
}

#[derive(Debug, Deserialize)]
struct ForecastProperties {
    periods: Vec<ForecastPeriod>,
}

#[derive(Debug, Deserialize)]
struct ForecastPeriod {
    name: String,
    #[serde(rename = "startTime")]
    start_time: String,
    #[serde(rename = "endTime")]
    end_time: String,
    temperature: f64,
    #[serde(rename = "temperatureUnit")]
    temperature_unit: String,
}

pub struct NoaaClient {
    client: reqwest::Client,
}

impl NoaaClient {
    pub fn new() -> Self {
        let client = reqwest::Client::builder()
            .user_agent("WeatherTrader/1.0")
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .expect("Failed to build HTTP client");
        
        Self { client }
    }
    
    pub async fn fetch_forecast(&self, office: &str, grid_x: u32, grid_y: u32) -> Result<Vec<ForecastPeriod>> {
        let url = format!("{}/gridpoints/{}/{},{}/forecast", NOAA_BASE, office, grid_x, grid_y);
        
        let response = self.client
            .get(&url)
            .send()
            .await?;
        
        if !response.status().is_success() {
            return Err(TradingError::ApiError(
                format!("NOAA API error: {}", response.status())
            ));
        }
        
        let forecast: ForecastResponse = response.json().await?;
        Ok(forecast.properties.periods)
    }
    
    pub async fn get_high_low_for_date(
        &self,
        office: &str,
        grid_x: u32,
        grid_y: u32,
        target_date: &str,
    ) -> Result<Option<(f64, f64)>> {
        let periods = self.fetch_forecast(office, grid_x, grid_y).await?;
        
        let target = NaiveDate::parse_from_str(target_date, "%Y-%m-%d")
            .map_err(|e| TradingError::ApiError(format!("Date parse error: {}", e)))?;
        
        let mut high_temp: Option<f64> = None;
        let mut low_temp: Option<f64> = None;
        
        for period in periods {
            let period_date = period.start_time.split('T').next()
                .and_then(|d| NaiveDate::parse_from_str(d, "%Y-%m-%d").ok());
            
            if let Some(date) = period_date {
                if date == target {
                    let temp_f = if period.temperature_unit == "F" {
                        period.temperature
                    } else {
                        period.temperature * 9.0 / 5.0 + 32.0 // Convert C to F
                    };
                    
                    // Simple heuristic: afternoon temps are highs, overnight/morning are lows
                    let hour = period.start_time.split('T').nth(1)
                        .and_then(|t| t.split(':').next())
                        .and_then(|h| h.parse::<u32>().ok())
                        .unwrap_or(12);
                    
                    if hour >= 12 && hour <= 18 {
                        high_temp = Some(temp_f.max(high_temp.unwrap_or(temp_f)));
                    } else {
                        low_temp = Some(temp_f.min(low_temp.unwrap_or(temp_f)));
                    }
                }
            }
        }
        
        match (high_temp, low_temp) {
            (Some(h), Some(l)) => Ok(Some((h, l))),
            _ => Ok(None),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_noaa_client_creation() {
        let client = NoaaClient::new();
        // Just verify it doesn't panic
        assert!(true);
    }
}
